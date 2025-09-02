"""Telegram notifications for users."""

from typing import Optional

from app.core.logging import get_logger
from app.interfaces.telegram.services.sdk_service import telegram_sdk_service
from app.interfaces.telegram.skill.rendering import MessageFormatter, UIRenderer

logger = get_logger(__name__)


class TelegramNotificationService:
    """Service for sending Telegram notifications to users."""

    def __init__(self):
        """Initialize the Telegram notification service."""
        self.telegram_service = telegram_sdk_service

    async def send_chatroom_notification(
        self,
        user_telegram_id: str,
        sender_name: str,
        message_preview: str,
        chatroom_id: str,
        chatroom_name: Optional[str] = None,
    ) -> bool:
        """
        Send Telegram notification to offline user about new chatroom message.

        Args:
            user_telegram_id: Telegram ID of the offline user
            sender_name: Name of the message sender
            message_preview: Preview of the message content
            chatroom_id: ID of the chatroom
            chatroom_name: Optional name/title of the chatroom

        Returns:
            True if notification was sent successfully, False otherwise
        """
        try:
            # Format the message using centralized renderer
            notification_text = MessageFormatter.format_chatroom_notification_message(
                sender_name=sender_name,
                message_preview=message_preview,
                chatroom_name=chatroom_name,
                chatroom_id=chatroom_id,
            )

            # Create inline keyboard using centralized renderer
            keyboard = UIRenderer.create_chatroom_notification_keyboard(chatroom_id)

            # Send the notification
            response = await self.telegram_service.send_message(
                chat_id=int(user_telegram_id),
                text=notification_text,
                parse_mode="Markdown",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )

            if response.success:
                logger.info(
                    "Telegram notification sent to offline user",
                    extra={
                        "user_telegram_id": user_telegram_id,
                        "chatroom_id": chatroom_id,
                        "sender_name": sender_name,
                        "webapp_startapp": f"chatroom-{chatroom_id}",
                    },
                )
                return True
            else:
                logger.warning(
                    "Failed to send Telegram notification",
                    extra={
                        "user_telegram_id": user_telegram_id,
                        "chatroom_id": chatroom_id,
                        "error": response.data,
                    },
                )
                return False

        except ValueError as e:
            # Invalid telegram_id format
            logger.warning(
                f"Invalid Telegram ID format: {user_telegram_id}",
                extra={
                    "user_telegram_id": user_telegram_id,
                    "chatroom_id": chatroom_id,
                    "error": str(e),
                },
            )
            return False

        except Exception as e:
            logger.error(
                f"Unexpected error sending Telegram notification: {e}",
                extra={
                    "user_telegram_id": user_telegram_id,
                    "chatroom_id": chatroom_id,
                    "sender_name": sender_name,
                },
            )
            return False

    def is_available(self) -> bool:
        """Check if the Telegram notification service is available."""
        try:
            return self.telegram_service is not None
        except Exception:
            return False


# Global instance
telegram_notification_service = TelegramNotificationService()
