"""Telegram message handlers."""

from datetime import datetime, timezone
from typing import Optional

from app.core.logging import get_logger
from app.domain.models.user import OnboardingStatus, UserRole
from app.domain.services.user_service import UserService
from app.interfaces.telegram.command.config import command_config
from app.interfaces.telegram.command.messages import CommandMessages
from app.interfaces.telegram.common.types import (
    TelegramCallbackQuery,
    TelegramInlineQuery,
    TelegramMessage,
)
from app.interfaces.telegram.common.utils import get_miniapp_url
from app.interfaces.telegram.manager import telegram_workflow_manager
from app.interfaces.telegram.models.bot_message import (
    BotMessageCreate,
    BotMessageDirection,
    BotMessageMetadata,
    BotMessageType,
    BotPlatform,
)
from app.interfaces.telegram.services.bot_message_service import BotMessageService
from app.interfaces.telegram.services.sdk_service import telegram_sdk_service
from app.interfaces.telegram.skill.rendering import MessageFormatter
from app.interfaces.telegram.workflows.base_workflow import TelegramReplyMarkup

logger = get_logger(__name__)


class MessageHandler:
    """Handler for processing Telegram messages."""

    def __init__(self):
        self.user_service = UserService()
        self.bot_message_service = BotMessageService()

    async def _persist_incoming_message(
        self,
        message: TelegramMessage,
    ) -> Optional[str]:
        """Persist incoming message from user to bot."""
        if not message.from_user:
            return None

        try:
            # Get or create user for early creation
            user = await self.user_service.get_or_create_telegram_user(
                {
                    "id": message.from_user.id,
                    "username": message.from_user.username,
                    "first_name": message.from_user.first_name,
                    "last_name": message.from_user.last_name,
                }
            )

            message_create = BotMessageCreate.from_telegram_message(
                message=message,
                user_id=str(user.id),
                direction=BotMessageDirection.INCOMING,
            )

            saved_message = await self.bot_message_service.create_message(
                message_create
            )
            logger.debug(f"Persisted incoming Telegram message: {saved_message.id}")
            return saved_message.id

        except Exception as e:
            logger.error(f"Failed to persist incoming Telegram message: {e}")
            return None

    async def _persist_outgoing_message(
        self, chat_id: int, text: str, telegram_message_id: Optional[int] = None
    ) -> Optional[str]:
        """Persist outgoing message from bot to user."""
        try:
            # Get or create user (in case this is the first interaction)
            user = await self.user_service.get_or_create_telegram_user(
                {
                    "id": chat_id,  # For private chats, chat_id = user_id
                }
            )

            # Create simplified message data for outgoing messages
            message_data = {
                "text": text,
                "message_id": telegram_message_id,
                "chat": {"id": chat_id, "type": "private"},
                "from_user": None,  # Bot messages don't have from_user
                "date": datetime.now(timezone.utc).timestamp(),
            }

            metadata = BotMessageMetadata(
                telegram_message_id=telegram_message_id,
                telegram_chat_id=chat_id,
                telegram_user_id=None,
                telegram_username=None,
                command_name=None,
                command_args=None,
                workflow_id=None,
                workflow_step=None,
                context_data=None,
                extra_data={
                    "text": text,
                    "chat_id": chat_id,
                },
            )

            message_create = BotMessageCreate(
                user_id=str(user.id),
                platform=BotPlatform.TELEGRAM,
                direction=BotMessageDirection.OUTGOING,
                message_type=BotMessageType.TEXT,
                message_data=message_data,
                metadata=metadata,
                processing_error=None,
            )

            saved_message = await self.bot_message_service.create_message(
                message_create
            )
            logger.debug(f"Persisted outgoing Telegram message: {saved_message.id}")
            return saved_message.id

        except Exception as e:
            logger.error(f"Failed to persist outgoing Telegram message: {e}")
            return None

    async def handle_message(self, message: TelegramMessage):
        """Handle incoming message."""
        try:
            logger.debug(
                f"Processing message from chat {message.chat.id}: {message.text}"
            )

            if not message.from_user:
                logger.error("Failed to handle message: no from_user")
                return

            # Persist incoming message
            await self._persist_incoming_message(message)

            # Check for commands first, before workflow processing
            if message.text and message.text.startswith("/"):
                await self.handle_command(message)
                return

            # Process through workflow if not a command
            workflow_response = await telegram_workflow_manager.process_message(message)
            if workflow_response:
                await self.send_message(
                    message.chat.id,
                    workflow_response.text,
                    parse_mode=workflow_response.parse_mode,
                    reply_markup=workflow_response.reply_markup,
                )
                return

            # Handle regular text messages if no workflow processed them
            if message.text:
                await self.handle_text_message(message)

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await self.send_error_message(
                message.chat.id, CommandMessages.ERROR_GENERAL
            )

    async def handle_command(self, message: TelegramMessage):
        """Handle bot commands."""
        if not message.text or not message.from_user:
            return

        command = message.text.split()[0].lower()

        # Get user role to check command access
        user_role = UserRole.USER  # Default role
        try:
            telegram_user_id = str(message.from_user.id)
            existing_user = await self.user_service.get_user_by_telegram_id(
                telegram_user_id
            )
            if existing_user and existing_user.role:
                user_role = existing_user.role
        except Exception as e:
            logger.warning(f"Failed to get user role for command check: {e}")

        if not command_config.is_command_allowed(command, user_role):
            await self.send_message(
                message.chat.id,
                "Unknown command. Use /help to see available commands! ✨",
                parse_mode="Markdown",
            )
            return

        if command == "/start":
            await self.handle_start_command(message)
        elif command == "/cancel":
            await self.handle_cancel_command(message)
        elif command == "/help":
            await self.handle_help_command(message, user_role)
        elif command == "/status":
            await self.handle_status_command(message)
        elif command == "/restart":
            await self.handle_restart_command(message)
        elif command == "/resign":
            await self.handle_resign_command(message)
        elif command == "/products":
            await self.handle_products_command(message)

    async def handle_start_command(self, message: TelegramMessage):
        """Handle /start command."""
        if not message.from_user:
            return

        # Check user status to determine appropriate response
        existing_user = None
        try:
            telegram_user_id = str(message.from_user.id)
            existing_user = await self.user_service.get_user_by_telegram_id(
                telegram_user_id
            )

            # User exists and has completed onboarding, send welcome back message
            if (
                existing_user
                and existing_user.onboarding_status == OnboardingStatus.COMPLETED
            ):
                # Use Mini App URL - authentication via Telegram initData
                miniapp_url = get_miniapp_url()

                # Get user's location for button - first try user profile, then workflow history
                try:
                    user_location = (
                        existing_user.location
                    )  # Get from user profile first

                    # If no location in profile, check workflow history
                    if not user_location:
                        workflow_history = (
                            await telegram_workflow_manager.get_user_workflow_history(
                                message.from_user.id
                            )
                        )
                        # Find the most recent completed workflow with location data
                        for workflow in workflow_history:
                            if workflow.data.get("location"):
                                user_location = workflow.data.get("location")
                                break

                    # Always provide user_data dict for returning users
                    user_data = {"location": user_location} if user_location else {}
                    welcome_result = MessageFormatter.returning_user_message(
                        user_data, miniapp_url
                    )

                    await self.send_message(
                        message.chat.id,
                        welcome_result["text"],
                        reply_markup=welcome_result.get("reply_markup"),
                    )
                except Exception as e:
                    logger.error(f"Error getting user location: {e}")
                    # Fallback to simple message with empty user_data
                    welcome_result = MessageFormatter.returning_user_message(
                        {}, miniapp_url
                    )
                    await self.send_message(
                        message.chat.id,
                        welcome_result["text"],
                        reply_markup=welcome_result.get("reply_markup"),
                    )
                return

        except Exception as e:
            logger.error(f"Error checking existing user: {e}")

        # For users who exist but haven't completed onboarding, or new users,
        # proceed with onboarding workflow.
        if await telegram_workflow_manager.has_active_workflow(
            message.from_user.id, message.chat.id
        ):
            await self.send_message(
                message.chat.id,
                "You already have an active onboarding session. Complete it or use /cancel to start over.",
            )
            return

        # Start new workflow for users who need onboarding
        user_id = str(existing_user.id) if existing_user else ""
        workflow_response = await telegram_workflow_manager.start_workflow(
            "onboarding", user_id, message.from_user.id, message.chat.id
        )

        if workflow_response:
            await self.send_message(
                message.chat.id,
                workflow_response.text,
                parse_mode=workflow_response.parse_mode,
                reply_markup=workflow_response.reply_markup,
            )
        else:
            await self.send_message(message.chat.id, CommandMessages.WELCOME_TEXT)

    async def handle_cancel_command(self, message: TelegramMessage):
        """Handle /cancel command."""
        if not message.from_user:
            return

        if await telegram_workflow_manager.cancel_workflow(
            message.from_user.id, message.chat.id
        ):
            await self.send_message(
                message.chat.id,
                CommandMessages.CANCEL_SUCCESS_TEXT,
            )
        else:
            await self.send_message(
                message.chat.id, CommandMessages.CANCEL_NO_WORKFLOW_TEXT
            )

    async def handle_help_command(
        self, message: TelegramMessage, user_role: UserRole = UserRole.USER
    ):
        """Handle /help command."""
        help_text = CommandMessages.get_help_text(user_role)
        await self.send_message(message.chat.id, help_text, parse_mode="Markdown")

    async def handle_restart_command(self, message: TelegramMessage):
        """Handle /restart command."""
        if not message.from_user:
            return

        try:
            telegram_user_id = str(message.from_user.id)
            existing_user = await self.user_service.get_user_by_telegram_id(
                telegram_user_id
            )

            if not existing_user:
                # User doesn't exist, redirect to /start
                await self.send_message(
                    message.chat.id,
                    "❌ Profile not found yet!\n\n✨ Please use /start to create your LoveLush profile first! 💫",
                )
                return

            # Cancel any active workflow first
            await telegram_workflow_manager.cancel_workflow(
                message.from_user.id, message.chat.id
            )

            # Check if user has active workflow
            if await telegram_workflow_manager.has_active_workflow(
                message.from_user.id, message.chat.id
            ):
                await self.send_message(
                    message.chat.id,
                    "You already have an active restart session. Complete it or use /cancel to start over.",
                )
                return

            # Start restart workflow for existing user
            workflow_response = await telegram_workflow_manager.start_workflow(
                "restart", str(existing_user.id), message.from_user.id, message.chat.id
            )

            if workflow_response:
                await self.send_message(
                    message.chat.id,
                    workflow_response.text,
                    parse_mode=workflow_response.parse_mode,
                    reply_markup=workflow_response.reply_markup,
                )
            else:
                await self.send_message(
                    message.chat.id,
                    "❌ Failed to start restart workflow. Please try again.",
                )

        except Exception as e:
            logger.error(f"Error handling restart command: {e}")
            await self.send_error_message(
                message.chat.id, CommandMessages.ERROR_RESTART_COMMAND
            )

    async def handle_resign_command(self, message: TelegramMessage):
        """Handle /resign command - delete user and restart whole flow."""
        if not message.from_user:
            return

        try:
            telegram_user_id = str(message.from_user.id)
            existing_user = await self.user_service.get_user_by_telegram_id(
                telegram_user_id
            )

            if not existing_user:
                # User doesn't exist, redirect to /start
                await self.send_message(
                    message.chat.id,
                    "❌ No profile found to delete!\n\n✨ Use /start to create your LoveLush profile! 💫",
                )
                return

            # Cancel any active workflow first
            await telegram_workflow_manager.cancel_workflow(
                message.from_user.id, message.chat.id
            )

            # Delete the user from the database
            await self.user_service.delete_user(existing_user.id)

            # Send confirmation message
            await self.send_message(
                message.chat.id,
                "✅ Profile deleted successfully!\n\n🆕 Ready to start fresh! Use /start to create a new profile! 🚀",
            )

            logger.info(f"User resigned and deleted: {telegram_user_id}")

        except Exception as e:
            logger.error(f"Error handling resign command: {e}")
            await self.send_error_message(
                message.chat.id, CommandMessages.ERROR_RESIGN_COMMAND
            )

    async def handle_status_command(self, message: TelegramMessage):
        """Handle /status command."""
        await self.send_message(message.chat.id, CommandMessages.STATUS_TEXT)

    async def handle_products_command(self, message: TelegramMessage):
        """Handle /products command."""
        if not message.from_user:
            return

        try:
            telegram_user_id = str(message.from_user.id)
            existing_user = await self.user_service.get_user_by_telegram_id(
                telegram_user_id
            )

            if not existing_user:
                # User doesn't exist, redirect to /start
                await self.send_message(
                    message.chat.id,
                    "❌ Please create your profile first!\n\n✨ Use /start to create your LoveLush profile and then browse products! 💫",
                )
                return

            # Cancel any active workflow first
            await telegram_workflow_manager.cancel_workflow(
                message.from_user.id, message.chat.id
            )

            # Check if user has active workflow
            if await telegram_workflow_manager.has_active_workflow(
                message.from_user.id, message.chat.id
            ):
                await self.send_message(
                    message.chat.id,
                    "You already have an active session. Complete it or use /cancel to start over.",
                )
                return

            # Start products workflow for existing user
            workflow_response = await telegram_workflow_manager.start_workflow(
                "products", str(existing_user.id), message.from_user.id, message.chat.id
            )

            if workflow_response:
                await self.send_message(
                    message.chat.id,
                    workflow_response.text,
                    parse_mode=workflow_response.parse_mode,
                    reply_markup=workflow_response.reply_markup,
                )
            else:
                await self.send_message(
                    message.chat.id,
                    "❌ Failed to start products session. Please try again.",
                )

        except Exception as e:
            logger.error(f"Error handling products command: {e}")
            await self.send_error_message(
                message.chat.id, "Error loading products. Please try again later."
            )

    async def handle_text_message(self, message: TelegramMessage):
        """Handle regular text messages."""
        if not message.text:
            return

        # No longer echo messages - users can use commands instead
        logger.info(f"Received text message: {message.text}")

    async def handle_edited_message(self, message: TelegramMessage):
        """Handle edited messages."""
        logger.info(f"Message edited in chat {message.chat.id}")
        # You can implement custom logic for edited messages here

    async def handle_callback_query(self, callback_query: TelegramCallbackQuery):
        """Handle callback queries from inline keyboards."""
        logger.info(f"Callback query received: {callback_query}")

        try:
            user_data = callback_query.from_user
            message_data = callback_query.message
            callback_data = callback_query.data

            if not user_data or not message_data:
                return

            # Extract user data directly without TelegramUser model
            chat_id = message_data.chat.id

            if not chat_id:
                return

            workflow_response = await telegram_workflow_manager.process_callback_query(
                callback_data or "", user_data, chat_id
            )

            if workflow_response:
                await self.send_message(
                    chat_id,
                    workflow_response.text,
                    parse_mode=workflow_response.parse_mode,
                    reply_markup=workflow_response.reply_markup,
                )

        except Exception as e:
            logger.error(f"Error handling callback query: {e}")

    async def handle_inline_query(self, inline_query: TelegramInlineQuery):
        """Handle inline queries."""
        logger.info(f"Inline query received: {inline_query}")
        # Implement inline query handling logic here

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: Optional[TelegramReplyMarkup] = None,
    ):
        """Send message to chat."""
        try:
            response = await telegram_sdk_service.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )

            if response.success and response.data:
                # Persist outgoing message with the returned message ID
                await self._persist_outgoing_message(
                    chat_id, text, response.data.message_id
                )
            else:
                # Persist even if sending failed (for debugging)
                await self._persist_outgoing_message(chat_id, text)
                logger.error(
                    f"Failed to send message: {response.error_description}",
                    exc_info=True,
                )

        except Exception as e:
            # Persist even if sending failed (for debugging)
            await self._persist_outgoing_message(chat_id, text)
            logger.error(f"Error sending message: {e}", exc_info=True)

    async def send_error_message(self, chat_id: int, error_text: str):
        """Send error message to chat."""
        await self.send_message(chat_id, f"❌ {error_text}")
