"""Service for handling message credit consumption logic."""

from typing import Optional

from app.core.exceptions.exceptions import ValidationError
from app.core.logging import get_logger
from app.domain.models.credits import TransactionReason
from app.domain.services.app_settings_service import AppSettingsService
from app.domain.services.credits_service import CreditsService
from app.infrastructure.database.repositories.user_message_stats_repository import (
    UserMessageStatsRepository,
)

logger = get_logger(__name__)


class MessageCreditService:
    """Service for handling message credit consumption."""

    def __init__(
        self,
        credits_service: Optional[CreditsService] = None,
        app_settings_service: Optional[AppSettingsService] = None,
        user_message_stats_repository: Optional[UserMessageStatsRepository] = None,
    ) -> None:
        self.credits_service = credits_service or CreditsService()
        self.app_settings_service = app_settings_service or AppSettingsService()
        self.user_message_stats_repository = (
            user_message_stats_repository or UserMessageStatsRepository()
        )

    async def can_send_message(self, user_id: str) -> bool:
        """
        Check if user can send a message (has free messages or enough credits).

        Args:
            user_id: User ID to check

        Returns:
            True if user can send message, False otherwise
        """
        try:
            # Get message configuration from settings
            message_config = await self.app_settings_service.get_message_config()

            # Get user message stats
            stats = await self.user_message_stats_repository.get_or_create_user_stats(
                user_id
            )

            # Check if user has free messages available
            available_free_messages = stats.get_available_free_messages(
                message_config.initial_free_messages
            )

            if available_free_messages > 0:
                logger.debug(
                    "User has free messages available",
                    extra={
                        "user_id": user_id,
                        "available_free_messages": available_free_messages,
                    },
                )
                return True

            # Check if user has enough credits
            user_credits = await self.credits_service.get_or_create_user_credits(
                user_id, with_initial_credits=True
            )

            if user_credits.current_balance >= message_config.cost_per_message:
                logger.debug(
                    "User has enough credits for message",
                    extra={
                        "user_id": user_id,
                        "current_balance": user_credits.current_balance,
                        "message_cost": message_config.cost_per_message,
                    },
                )
                return True

            logger.info(
                "User cannot send message - insufficient credits and no free messages",
                extra={
                    "user_id": user_id,
                    "current_balance": user_credits.current_balance,
                    "message_cost": message_config.cost_per_message,
                    "available_free_messages": available_free_messages,
                },
            )
            return False

        except Exception as e:
            logger.exception(f"Error checking if user can send message: {e}")
            return False

    async def consume_message_credit(
        self, user_id: str, message_id: Optional[str] = None
    ) -> bool:
        """
        Consume credit for sending a message.

        First tries to use free messages, then consumes credits.

        Args:
            user_id: User ID
            message_id: Optional message ID for reference

        Returns:
            True if credit was consumed successfully, False otherwise

        Raises:
            ValidationError: If user cannot send message
        """
        try:
            # Check if user can send message
            if not await self.can_send_message(user_id):
                raise ValidationError("Insufficient credits to send message")

            # Get message configuration from settings
            message_config = await self.app_settings_service.get_message_config()

            # Get user message stats
            stats = await self.user_message_stats_repository.get_or_create_user_stats(
                user_id
            )

            # Check if user has free messages available
            available_free_messages = stats.get_available_free_messages(
                message_config.initial_free_messages
            )

            if available_free_messages > 0:
                # Use free message
                success = await self.user_message_stats_repository.increment_free_messages_used(
                    user_id
                )
                if success:
                    logger.info(
                        "Free message consumed",
                        extra={
                            "user_id": user_id,
                            "message_id": message_id,
                            "remaining_free_messages": available_free_messages - 1,
                        },
                    )
                    return True
                else:
                    logger.error(f"Failed to consume free message for user {user_id}")
                    return False

            # Use credits
            success = await self.credits_service.consume_credits(
                user_id=user_id,
                amount=message_config.cost_per_message,
                reason=TransactionReason.MESSAGE_CONSUMPTION,
                reference_id=message_id,
                description=f"Message sent - cost: {message_config.cost_per_message} credits",
            )

            if success:
                logger.info(
                    "Credits consumed for message",
                    extra={
                        "user_id": user_id,
                        "message_id": message_id,
                        "credits_consumed": message_config.cost_per_message,
                    },
                )
                return True
            else:
                logger.error(f"Failed to consume credits for message - user {user_id}")
                raise ValidationError("Failed to process credit consumption")

        except ValidationError:
            raise
        except Exception as e:
            logger.exception(f"Error consuming message credit: {e}")
            raise ValidationError("Failed to process message credit consumption")

    async def get_user_message_status(self, user_id: str) -> dict:
        """
        Get user's current message sending status and available credits.

        Args:
            user_id: User ID

        Returns:
            Dictionary with message status information
        """
        try:
            # Get message configuration from settings
            message_config = await self.app_settings_service.get_message_config()

            # Get user message stats
            stats = await self.user_message_stats_repository.get_or_create_user_stats(
                user_id
            )

            # Get user credits
            user_credits = await self.credits_service.get_or_create_user_credits(
                user_id, with_initial_credits=True
            )

            # Calculate available free messages
            available_free_messages = stats.get_available_free_messages(
                message_config.initial_free_messages
            )

            # Calculate total messages user can send
            total_sendable_messages = available_free_messages
            if user_credits.current_balance >= message_config.cost_per_message:
                total_sendable_messages += (
                    user_credits.current_balance // message_config.cost_per_message
                )

            return {
                "can_send_message": await self.can_send_message(user_id),
                "available_free_messages": available_free_messages,
                "total_free_messages": message_config.initial_free_messages,
                "free_messages_used": (
                    stats.free_messages_used if not stats.is_reset_needed() else 0
                ),
                "current_credits": user_credits.current_balance,
                "message_cost": message_config.cost_per_message,
                "total_sendable_messages": total_sendable_messages,
                "reset_needed": stats.is_reset_needed(),
                "last_reset_date": stats.last_reset_date,
            }

        except Exception as e:
            logger.exception(f"Error getting user message status: {e}")
            return {
                "can_send_message": False,
                "available_free_messages": 0,
                "total_free_messages": 0,
                "free_messages_used": 0,
                "current_credits": 0,
                "message_cost": 0,
                "total_sendable_messages": 0,
                "reset_needed": False,
                "last_reset_date": None,
            }
