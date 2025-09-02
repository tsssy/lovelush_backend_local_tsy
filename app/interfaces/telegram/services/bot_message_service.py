"""Bot message service for handling bot message business logic and processing."""

from typing import List, Optional

from app.core.exceptions.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.models.pagination import PaginationParams, PaginationResponse
from app.infrastructure.database.repositories.bot_message_repository import (
    BotMessageRepository,
)
from app.interfaces.telegram.models.bot_message import (
    BotMessage,
    BotMessageCreate,
    BotMessageResponse,
    BotPlatform,
)

logger = get_logger(__name__)


class BotMessageService:
    """Bot message service for handling business logic."""

    def __init__(
        self, bot_message_repository: Optional[BotMessageRepository] = None
    ) -> None:
        self.bot_message_repository = bot_message_repository or BotMessageRepository()

    async def create_message(
        self, message_data: BotMessageCreate
    ) -> BotMessageResponse:
        """
        Create a new bot message with validation.

        Validates the message data and creates a new bot message record
        for tracking bot interactions across different platforms.

        Args:
            message_data: Bot message creation data

        Returns:
            BotMessageResponse with created message information

        Raises:
            ValidationError: If message data is invalid
        """
        try:
            # Validate message data
            if not message_data:
                logger.error("Cannot create bot message with null data")
                raise ValidationError("Message data is required")

            if not message_data.user_id:
                logger.warning("Bot message creation failed - missing user_id")
                raise ValidationError("User ID is required")

            if not message_data.message_data:
                logger.warning(
                    "Bot message creation failed - empty message data",
                    extra={"user_id": str(message_data.user_id)},
                )
                raise ValidationError("Message data cannot be empty")

            # Create message
            message = await self.bot_message_repository.create(message_data)

            logger.debug(
                "Bot message created successfully",
                extra={
                    "message_id": str(message.id),
                    "user_id": str(message.user_id),
                    "platform": message.platform.value,
                    "direction": message.direction.value,
                },
            )

            return self._to_message_response(message)

        except ValidationError:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error creating bot message: %s",
                str(e),
                extra={
                    "user_id": (
                        str(message_data.user_id)
                        if message_data and message_data.user_id
                        else None
                    )
                },
            )
            raise

    async def get_message_by_id(self, message_id: str) -> Optional[BotMessageResponse]:
        """
        Get bot message by ID with validation.

        Retrieves a bot message by its unique identifier with proper
        input validation and error handling.

        Args:
            message_id: Unique identifier of the bot message

        Returns:
            BotMessageResponse if found, None otherwise

        Raises:
            ValidationError: If message_id is invalid
        """
        try:
            # Validate input
            if not message_id or not message_id.strip():
                logger.warning("Bot message retrieval failed - empty message_id")
                raise ValidationError("Message ID is required")

            message_id = message_id.strip()

            # Get message
            message = await self.bot_message_repository.get_by_id(message_id)
            if not message:
                logger.debug("Bot message not found", extra={"message_id": message_id})
                return None

            logger.debug(
                "Bot message retrieved successfully",
                extra={"message_id": message_id, "user_id": str(message.user_id)},
            )

            return self._to_message_response(message)

        except ValidationError:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error retrieving bot message: %s",
                str(e),
                extra={"message_id": message_id},
            )
            return None

    async def get_user_messages(
        self,
        user_id: str,
        platform: Optional[BotPlatform] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginationResponse:
        """Get bot messages for a specific user."""
        if not pagination:
            pagination = PaginationParams()

        messages = await self.bot_message_repository.get_user_messages(
            user_id, platform, pagination.skip, pagination.limit
        )

        # For simplicity, we'll return the found messages without total count
        # In a production system, you might want to add a count method
        message_responses = [self._to_message_response(message) for message in messages]

        return PaginationResponse.create(
            items=message_responses,
            total_items=len(message_responses),  # This is an approximation
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def mark_message_as_processed(
        self, message_id: str, processing_error: Optional[str] = None
    ) -> bool:
        """
        Mark bot message as processed with validation.

        Updates the message processing status and optionally records
        any processing errors that occurred.

        Args:
            message_id: Unique identifier of the bot message
            processing_error: Optional error message if processing failed

        Returns:
            True if successfully marked as processed

        Raises:
            ValidationError: If message_id is invalid
            NotFoundError: If message is not found
        """
        try:
            # Validate input
            if not message_id or not message_id.strip():
                logger.warning("Mark as processed failed - empty message_id")
                raise ValidationError("Message ID is required")

            message_id = message_id.strip()

            # Check if message exists
            message = await self.bot_message_repository.get_by_id(message_id)
            if not message:
                logger.warning(
                    "Cannot mark non-existent message as processed",
                    extra={"message_id": message_id},
                )
                raise NotFoundError("Bot message not found")

            # Mark as processed
            success = await self.bot_message_repository.mark_as_processed(
                message_id, processing_error
            )

            if success:
                log_extra = {
                    "message_id": message_id,
                    "user_id": str(message.user_id),
                    "has_error": bool(processing_error),
                }
                if processing_error:
                    logger.warning(
                        "Bot message marked as processed with error", extra=log_extra
                    )
                else:
                    logger.info(
                        "Bot message marked as processed successfully", extra=log_extra
                    )
            else:
                logger.error(
                    "Failed to mark bot message as processed",
                    extra={"message_id": message_id},
                )

            return success

        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error marking message as processed: %s",
                str(e),
                extra={"message_id": message_id},
            )
            raise

    async def get_unprocessed_messages(
        self, platform: Optional[BotPlatform] = None, limit: int = 100
    ) -> List[BotMessageResponse]:
        """
        Get unprocessed bot messages with validation.

        Retrieves bot messages that haven't been processed yet,
        optionally filtered by platform with proper limit validation.

        Args:
            platform: Optional platform filter for messages
            limit: Maximum number of messages to return (1-1000)

        Returns:
            List of unprocessed bot message responses

        Raises:
            ValidationError: If limit is invalid
        """
        try:
            # Validate limit
            if limit <= 0 or limit > 1000:
                logger.warning(
                    "Invalid limit for unprocessed messages", extra={"limit": limit}
                )
                raise ValidationError("Limit must be between 1 and 1000")

            # Get unprocessed messages
            messages = await self.bot_message_repository.get_unprocessed_messages(
                platform, limit
            )

            logger.info(
                "Unprocessed bot messages retrieved",
                extra={
                    "count": len(messages),
                    "platform": platform.value if platform else "all",
                    "limit": limit,
                },
            )

            return [self._to_message_response(message) for message in messages]

        except ValidationError:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error retrieving unprocessed messages: %s",
                str(e),
                extra={
                    "platform": platform.value if platform else None,
                    "limit": limit,
                },
            )
            raise

    def _to_message_response(self, message: BotMessage) -> BotMessageResponse:
        """Convert BotMessage model to BotMessageResponse."""
        return BotMessageResponse(
            _id=message.id,
            user_id=str(message.user_id),
            platform=message.platform,
            direction=message.direction,
            message_type=message.effective_message_type,  # Use effective type that auto-detects
            message_data=message.message_data,
            metadata=message.metadata,
            is_processed=message.is_processed,
            processing_error=message.processing_error,
            created_at=message.created_at,
            processed_at=message.processed_at,
        )
