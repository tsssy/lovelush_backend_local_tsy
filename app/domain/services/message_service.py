"""Message service for handling message business logic."""

from typing import List, Optional

from app.core.exceptions.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.models.message import (
    Message,
    MessageCreate,
    MessageHistory,
    MessageResponse,
    MessageSenderType,
)
from app.infrastructure.database.repositories.agent_repository import AgentRepository
from app.infrastructure.database.repositories.chatroom_repository import (
    ChatroomRepository,
)
from app.infrastructure.database.repositories.message_repository import (
    MessageRepository,
)
from app.infrastructure.database.repositories.user_repository import UserRepository

logger = get_logger(__name__)


class MessageService:
    """Service for handling message business logic."""

    def __init__(
        self,
        message_repository: Optional[MessageRepository] = None,
        chatroom_repository: Optional[ChatroomRepository] = None,
        user_repository: Optional[UserRepository] = None,
        agent_repository: Optional[AgentRepository] = None,
    ) -> None:
        """Initialize service with required dependencies."""
        self.message_repository = message_repository or MessageRepository()
        self.chatroom_repository = chatroom_repository or ChatroomRepository()
        self.user_repository = user_repository or UserRepository()
        self.agent_repository = agent_repository or AgentRepository()

    async def create_message(self, message_data: MessageCreate) -> MessageResponse:
        """Create a new message with validation."""
        try:
            # Validate chatroom exists and is active
            chatroom = await self.chatroom_repository.get_chatroom_by_id(
                message_data.chatroom_id
            )
            if not chatroom:
                raise NotFoundError(f"Chatroom {message_data.chatroom_id} not found")

            # Validate sender authorization
            await self._validate_sender_authorization(
                chatroom_id=message_data.chatroom_id,
                sender_id=message_data.sender_id,
                sender_type=message_data.sender_type,
            )

            # Create message
            message = await self.message_repository.create(message_data)

            # Update chatroom last activity
            await self.chatroom_repository.update_last_activity(
                message_data.chatroom_id
            )

            logger.info(
                "Message created successfully",
                extra={
                    "message_id": str(message.id),
                    "chatroom_id": message_data.chatroom_id,
                    "sender_type": message_data.sender_type.value,
                },
            )

            return await self._to_message_response(message)

        except (NotFoundError, ValidationError):
            raise
        except Exception as e:
            logger.exception(f"Unexpected error creating message: {str(e)}")
            raise ValidationError("Failed to create message")

    async def get_chatroom_messages(
        self,
        chatroom_id: str,
        page: int = 1,
        page_size: int = 50,
        user_id: Optional[str] = None,
    ) -> MessageHistory:
        """Get paginated message history for a chatroom."""
        try:
            # Validate inputs
            if page < 1:
                page = 1
            if page_size < 1 or page_size > 100:
                page_size = 50

            # Validate chatroom exists and user has access
            if user_id:
                await self._validate_chatroom_access(chatroom_id, user_id)

            skip = (page - 1) * page_size

            # Get messages (newest first)
            messages = await self.message_repository.get_chatroom_messages(
                chatroom_id, limit=page_size, skip=skip
            )

            # Get total count for pagination
            # Note: This could be optimized with a dedicated count method
            all_messages = await self.message_repository.get_chatroom_messages(
                chatroom_id, limit=10000, skip=0  # Get all for count
            )
            total_messages = len(all_messages)

            # Convert to responses
            message_responses = []
            for message in messages:
                response = await self._to_message_response(message)
                message_responses.append(response)

            # Reverse to show oldest first for chat display
            message_responses.reverse()

            has_more = skip + len(messages) < total_messages

            return MessageHistory(
                messages=message_responses,
                total_messages=total_messages,
                page=page,
                page_size=page_size,
                has_more=has_more,
            )

        except (NotFoundError, ValidationError):
            raise
        except Exception as e:
            logger.exception(f"Unexpected error getting chatroom messages: {str(e)}")
            return MessageHistory()

    async def mark_messages_as_read(
        self, chatroom_id: str, user_id: str, message_ids: Optional[List[str]] = None
    ) -> int:
        """Mark messages as read by a user."""
        try:
            # Validate chatroom access
            await self._validate_chatroom_access(chatroom_id, user_id)

            marked_count = 0

            if message_ids:
                # Mark specific messages
                for message_id in message_ids:
                    success = await self.message_repository.mark_message_as_read(
                        message_id, user_id
                    )
                    if success:
                        marked_count += 1
            else:
                # Mark all unread messages in chatroom
                messages = await self.message_repository.get_chatroom_messages(
                    chatroom_id
                )
                for message in messages:
                    if (
                        user_id not in message.read_by
                        and str(message.sender_id) != user_id
                    ):
                        success = await self.message_repository.mark_message_as_read(
                            str(message.id), user_id
                        )
                        if success:
                            marked_count += 1

            logger.info(
                f"Marked {marked_count} messages as read for user {user_id} in chatroom {chatroom_id}"
            )
            return marked_count

        except (NotFoundError, ValidationError):
            raise
        except Exception as e:
            logger.exception(f"Unexpected error marking messages as read: {str(e)}")
            return 0

    async def get_unread_count(self, chatroom_id: str, user_id: str) -> int:
        """Get unread message count for user in chatroom."""
        try:
            await self._validate_chatroom_access(chatroom_id, user_id)
            return await self.message_repository.get_unread_message_count(
                chatroom_id, user_id
            )
        except Exception as e:
            logger.error(f"Failed to get unread count: {str(e)}")
            return 0

    async def delete_message(self, message_id: str, user_id: str) -> bool:
        """Delete a message (soft delete)."""
        try:
            # Get message to validate ownership
            message = await self.message_repository.get_by_id(message_id)
            if not message:
                raise NotFoundError("Message not found")

            # Only sender can delete their own messages (or system messages by admins)
            if (
                message.sender_type != MessageSenderType.SYSTEM
                and str(message.sender_id) != user_id
            ):
                raise ValidationError("Can only delete your own messages")

            # Soft delete
            success = await self.message_repository.delete(message_id)

            if success:
                logger.info(f"Message {message_id} deleted by user {user_id}")

            return bool(success)

        except (NotFoundError, ValidationError):
            raise
        except Exception as e:
            logger.exception(f"Unexpected error deleting message: {str(e)}")
            return False

    async def _validate_sender_authorization(
        self, chatroom_id: str, sender_id: Optional[str], sender_type: MessageSenderType
    ) -> None:
        """Validate that sender is authorized to send messages in chatroom."""
        if sender_type == MessageSenderType.SYSTEM:
            return  # System messages are always allowed

        if not sender_id:
            raise ValidationError("Sender ID required for non-system messages")

        chatroom = await self.chatroom_repository.get_chatroom_by_id(chatroom_id)
        if not chatroom:
            raise NotFoundError("Chatroom not found")

        if sender_type == MessageSenderType.USER:
            if str(chatroom.user_id) != sender_id:
                raise ValidationError("User not authorized for this chatroom")
        elif sender_type == MessageSenderType.AGENT:
            if str(chatroom.sub_account_id) != sender_id:
                raise ValidationError("Agent not authorized for this chatroom")

    async def _validate_chatroom_access(self, chatroom_id: str, user_id: str) -> None:
        """Validate user has access to chatroom."""
        chatroom = await self.chatroom_repository.get_chatroom_by_id(chatroom_id)
        if not chatroom:
            raise NotFoundError("Chatroom not found")

        # User must be participant in chatroom
        if str(chatroom.user_id) != user_id:
            # Could also allow agent access here if needed
            raise ValidationError("Access denied to chatroom")

    async def _to_message_response(self, message: Message) -> MessageResponse:
        """Convert Message model to MessageResponse with sender details."""
        # Get sender details
        sender_details = None
        if message.sender_id and message.sender_type != MessageSenderType.SYSTEM:
            if message.sender_type == MessageSenderType.USER:
                user = await self.user_repository.get_by_id(str(message.sender_id))
                if user:
                    sender_details = {
                        "id": str(user.id),
                        "username": user.username,
                        "full_name": user.full_name,
                        "avatar_url": user.avatar_url,
                    }
            elif message.sender_type == MessageSenderType.AGENT:
                sub_account = await self.agent_repository.get_sub_account_by_id(
                    str(message.sender_id)
                )
                if sub_account:
                    sender_details = {
                        "id": str(sub_account.id),
                        "name": sub_account.name,
                        "display_name": sub_account.display_name,
                        "avatar_url": sub_account.avatar_url,
                    }

        return MessageResponse(
            _id=message.id,
            chatroom_id=str(message.chatroom_id),
            sender_id=str(message.sender_id) if message.sender_id else None,
            sender_type=message.sender_type,
            message=message.message,
            message_type=message.message_type,
            metadata=message.metadata,
            is_edited=message.is_edited,
            is_deleted=message.is_deleted,
            edited_at=message.edited_at,
            read_by=message.read_by,
            created_at=message.created_at,
            updated_at=message.updated_at,
            sender_details=sender_details,
        )
