"""Chatroom service for managing chatrooms and real-time messaging."""

from typing import Any, Dict, List, Optional

from app.core.exceptions.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.messages.greeting_messages import get_random_greeting
from app.core.utils.datetime_utils import safe_isoformat_or_now
from app.domain.models.chatroom import (
    Chatroom,
    ChatroomResponse,
    ChatroomStatus,
)
from app.domain.models.message import MessageCreate, MessageSenderType, MessageType
from app.domain.models.pagination import PaginationParams, PaginationResponse
from app.domain.services.message_credit_service import MessageCreditService
from app.domain.services.notification_service import NotificationService
from app.domain.services.presence_service import PusherPresenceService
from app.infrastructure.database.repositories.agent_repository import AgentRepository
from app.infrastructure.database.repositories.chatroom_repository import (
    ChatroomRepository,
)
from app.infrastructure.database.repositories.message_repository import (
    MessageRepository,
)
from app.infrastructure.database.repositories.user_repository import UserRepository
from app.integrations.pusher.chatroom_service import ChatroomPusherService

logger = get_logger(__name__)


class ChatroomService:
    """Service for handling chatroom business logic."""

    def __init__(
        self,
        chatroom_repository: Optional[ChatroomRepository] = None,
        agent_repository: Optional[AgentRepository] = None,
        user_repository: Optional[UserRepository] = None,
        message_repository: Optional[MessageRepository] = None,
        notification_service: Optional[NotificationService] = None,
        chatroom_pusher_service: Optional[ChatroomPusherService] = None,
        presence_service: Optional[PusherPresenceService] = None,
        message_credit_service: Optional[MessageCreditService] = None,
    ) -> None:
        """Initialize service with required dependencies."""
        self.chatroom_repository = chatroom_repository or ChatroomRepository()
        self.agent_repository = agent_repository or AgentRepository()
        self.user_repository = user_repository or UserRepository()
        self.message_repository = message_repository or MessageRepository()
        self.notification_service = notification_service or NotificationService()
        self.chatroom_pusher_service = (
            chatroom_pusher_service or ChatroomPusherService()
        )
        self.presence_service = presence_service or PusherPresenceService()
        self.message_credit_service = message_credit_service or MessageCreditService()

    async def get_chatroom_by_id(self, chatroom_id: str) -> Optional[ChatroomResponse]:
        """
        Get chatroom by ID with participant details and validation.

        Retrieves a chatroom with full participant information including
        user and agent details for the chatroom interface.

        Args:
            chatroom_id: Unique identifier of the chatroom

        Returns:
            ChatroomResponse with participant details if found, None otherwise

        Raises:
            ValidationError: If chatroom_id is invalid
        """
        try:
            # Validate input
            if not chatroom_id or not chatroom_id.strip():
                logger.warning("Chatroom retrieval failed - empty chatroom_id")
                raise ValidationError("Chatroom ID is required")

            chatroom_id = chatroom_id.strip()

            # Get chatroom
            chatroom = await self.chatroom_repository.get_chatroom_by_id(chatroom_id)
            if not chatroom:
                logger.debug("Chatroom not found", extra={"chatroom_id": chatroom_id})
                return None

            logger.debug(
                "Chatroom retrieved successfully",
                extra={
                    "chatroom_id": chatroom_id,
                    "user_id": chatroom.user_id,
                    "status": chatroom.status.value,
                },
            )

            return await self._to_chatroom_response_with_details(chatroom)

        except ValidationError:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error retrieving chatroom: %s",
                str(e),
                extra={"chatroom_id": chatroom_id},
            )
            return None

    async def get_user_chatrooms(
        self, user_id: str, limit: int = 20, include_last_messages: int = 1
    ) -> List[ChatroomResponse]:
        """
        Get user's chatrooms with participant details and last messages.

        Retrieves all chatrooms for a specific user with full participant
        information, proper input validation, and optionally includes the
        last N messages for each chatroom for UI convenience.

        Args:
            user_id: Unique identifier of the user
            limit: Maximum number of chatrooms to return (1-100)
            include_last_messages: Number of latest messages to include per chatroom (0-10)

        Returns:
            List of ChatroomResponse objects with participant details and last messages

        Raises:
            ValidationError: If user_id is invalid or limit is out of range
        """
        try:
            # Validate input
            if not user_id or not user_id.strip():
                logger.warning("User chatrooms retrieval failed - empty user_id")
                raise ValidationError("User ID is required")

            if limit <= 0 or limit > 100:
                logger.warning(
                    "Invalid limit for user chatrooms", extra={"limit": limit}
                )
                raise ValidationError("Limit must be between 1 and 100")

            if include_last_messages < 0 or include_last_messages > 10:
                logger.warning(
                    "Invalid include_last_messages for user chatrooms",
                    extra={"include_last_messages": include_last_messages},
                )
                raise ValidationError("include_last_messages must be between 0 and 10")

            user_id = user_id.strip()

            # Get chatrooms
            chatrooms = await self.chatroom_repository.get_user_chatrooms(
                user_id, limit
            )

            responses = []
            for chatroom in chatrooms:
                response = await self._to_chatroom_response_with_details(chatroom)

                # Include last messages if requested
                if include_last_messages > 0:
                    try:
                        # Get non-system messages directly from repository
                        non_system_messages = await self.message_repository.get_chatroom_non_system_messages(
                            str(chatroom.id), include_last_messages, 0
                        )

                        # Convert to response format
                        message_responses = []
                        for message in non_system_messages:
                            message_response = {
                                "id": str(message.id),
                                "sender_id": (
                                    str(message.sender_id)
                                    if message.sender_id
                                    else None
                                ),
                                "sender_type": message.sender_type.value,
                                "message": message.message,
                                "message_type": message.message_type.value,
                                "created_at": message.created_at,
                            }
                            message_responses.append(message_response)

                        # If no non-system messages found, add a random greeting
                        if not message_responses:
                            greeting_message = {
                                "id": "greeting",
                                "sender_id": str(chatroom.sub_account_id),
                                "sender_type": "agent",
                                "message": get_random_greeting(),
                                "message_type": "text",
                                "created_at": chatroom.created_at,
                                "is_greeting": True,  # Flag to indicate this is a generated greeting
                            }
                            message_responses.append(greeting_message)

                        # Add to metadata for frontend convenience
                        response.metadata["last_messages"] = message_responses

                    except Exception as e:
                        logger.warning(
                            f"Failed to get last messages for chatroom {chatroom.id}: {e}"
                        )
                        # Even on error, provide a greeting message as fallback
                        greeting_message = {
                            "id": "greeting",
                            "sender_id": str(chatroom.sub_account_id),
                            "sender_type": "agent",
                            "message": get_random_greeting(),
                            "message_type": "text",
                            "created_at": chatroom.created_at,
                            "is_greeting": True,
                        }
                        response.metadata["last_messages"] = [greeting_message]

                responses.append(response)

            logger.info(
                "User chatrooms retrieved successfully",
                extra={
                    "user_id": user_id,
                    "chatroom_count": len(responses),
                    "limit": limit,
                    "include_last_messages": include_last_messages,
                },
            )

            return responses

        except ValidationError:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error retrieving user chatrooms: %s",
                str(e),
                extra={"user_id": user_id, "limit": limit},
            )
            return []

    async def get_sub_account_chatrooms(
        self, sub_account_id: str, limit: int = 50
    ) -> List[ChatroomResponse]:
        """
        Get sub-account's active chatrooms for agent dashboard with validation.

        Retrieves all active chatrooms assigned to a specific sub-account
        for agent management and monitoring purposes.

        Args:
            sub_account_id: Unique identifier of the sub-account
            limit: Maximum number of chatrooms to return (1-100)

        Returns:
            List of ChatroomResponse objects for the sub-account

        Raises:
            ValidationError: If sub_account_id is invalid or limit is out of range
        """
        try:
            # Validate input
            if not sub_account_id or not sub_account_id.strip():
                logger.warning(
                    "Sub-account chatrooms retrieval failed - empty sub_account_id"
                )
                raise ValidationError("Sub-account ID is required")

            if limit <= 0 or limit > 100:
                logger.warning(
                    "Invalid limit for sub-account chatrooms", extra={"limit": limit}
                )
                raise ValidationError("Limit must be between 1 and 100")

            sub_account_id = sub_account_id.strip()

            # Get chatrooms from repository
            chatrooms = await self.chatroom_repository.get_sub_account_chatrooms(
                sub_account_id, limit
            )

            responses = []
            for chatroom in chatrooms:
                response = await self._to_chatroom_response_with_details(chatroom)
                responses.append(response)

            logger.info(
                "Sub-account chatrooms retrieved successfully",
                extra={
                    "sub_account_id": sub_account_id,
                    "chatroom_count": len(responses),
                    "limit": limit,
                },
            )

            return responses

        except ValidationError:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error retrieving sub-account chatrooms: %s",
                str(e),
                extra={"sub_account_id": sub_account_id, "limit": limit},
            )
            return []

    async def update_last_activity(self, chatroom_id: str) -> bool:
        """Update chatroom's last activity timestamp."""
        return await self.chatroom_repository.update_last_activity(chatroom_id)

    async def send_message(
        self,
        chatroom_id: str,
        sender_id: str,
        message: str,
        sender_type: str = "user",  # "user" or "agent"
        message_type: str = "text",
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Send a message in a chatroom via Pusher and store in database."""
        # Get chatroom to validate
        chatroom = await self.chatroom_repository.get_chatroom_by_id(chatroom_id)
        if not chatroom:
            raise NotFoundError(f"Chatroom {chatroom_id} not found")

        if chatroom.status != ChatroomStatus.ACTIVE:
            raise ValidationError("Cannot send message to inactive chatroom")

        # Validate sender belongs to chatroom
        if sender_type == "user":
            if str(chatroom.user_id) != sender_id:
                raise ValidationError("Sender not authorized for this chatroom")
        elif sender_type == "agent":
            if str(chatroom.sub_account_id) != sender_id:
                raise ValidationError("Agent not authorized for this chatroom")

        # Check and consume credits for user messages (agents can send free messages)
        if sender_type == "user":
            # Check if user can send message
            can_send = await self.message_credit_service.can_send_message(sender_id)
            if not can_send:
                logger.warning(
                    "User cannot send message due to insufficient credits",
                    extra={
                        "user_id": sender_id,
                        "chatroom_id": chatroom_id,
                    },
                )
                raise ValidationError(
                    "Insufficient credits to send message. Please add more credits to continue chatting."
                )

        # Convert sender type to enum
        sender_type_enum = (
            MessageSenderType.USER if sender_type == "user" else MessageSenderType.AGENT
        )
        message_type_enum = (
            MessageType.TEXT if message_type == "text" else MessageType.SYSTEM
        )

        # Store message in database first
        try:
            message_create = MessageCreate(
                chatroom_id=chatroom_id,
                sender_id=sender_id,
                sender_type=sender_type_enum,
                message=message,
                message_type=message_type_enum,
                metadata=metadata or {},
            )

            stored_message = await self.message_repository.create(message_create)

            # Consume credits for user messages (after successful message creation)
            if sender_type == "user":
                try:
                    credit_consumed = (
                        await self.message_credit_service.consume_message_credit(
                            user_id=sender_id, message_id=str(stored_message.id)
                        )
                    )
                    if not credit_consumed:
                        logger.error(
                            "Failed to consume message credit after message creation",
                            extra={
                                "user_id": sender_id,
                                "chatroom_id": chatroom_id,
                                "message_id": str(stored_message.id),
                            },
                        )
                        # Note: Message was already created, so we log but don't fail the operation
                except Exception as e:
                    logger.exception(
                        f"Error consuming message credit: {e}",
                        extra={
                            "user_id": sender_id,
                            "chatroom_id": chatroom_id,
                            "message_id": str(stored_message.id),
                        },
                    )

            # Create message payload for Pusher using stored message data
            message_payload = {
                "id": str(stored_message.id),
                "chatroom_id": chatroom_id,
                "sender_id": sender_id,
                "sender_type": sender_type,
                "message": message,
                "message_type": message_type,
                "metadata": metadata or {},
                "timestamp": safe_isoformat_or_now(stored_message.created_at),
                "is_stored": True,  # Indicate message is persisted
            }

            # Send via Pusher to presence channel for real-time messaging
            pusher_channel = self.chatroom_pusher_service.get_presence_channel_name(
                chatroom_id
            )
            pusher_payload = await self.chatroom_pusher_service.send_message_event(
                channel=pusher_channel,
                sender_id=sender_id,
                sender_type=sender_type,
                message=message,
                message_type=message_type,
                metadata=metadata,
                chatroom_id=chatroom_id,
            )

            # Update the payload with stored message info
            pusher_payload.update(message_payload)

            # Update last activity
            await self.update_last_activity(chatroom_id)

            # Check if recipient needs to be notified to auth + subscribe to chatroom
            try:
                # Determine recipient based on sender
                if sender_type == "user":
                    # User sent message -> notify parent agent (not sub-account)
                    recipient_id = str(
                        chatroom.agent_id
                    )  # Use parent agent_id instead of sub_account_id
                    recipient_type = "agent"

                    # Get user details for sender info and sub-account for context
                    user = await self.user_repository.get_by_id(sender_id)
                    sub_account = await self.agent_repository.get_sub_account_by_id(
                        str(chatroom.sub_account_id)
                    )
                    sender_info = {
                        "user_id": sender_id,
                        "name": user.full_name if user else "User",
                        "username": user.username if user else "Unknown",
                        # Include sub-account context for agent to know which identity to use
                        "target_sub_account_id": str(chatroom.sub_account_id),
                        "target_sub_account_name": (
                            sub_account.display_name if sub_account else "Sub-Account"
                        ),
                    }

                else:  # sender_type == "agent"
                    # Agent sent message -> check if user is subscribed to chatroom
                    recipient_id = str(chatroom.user_id)
                    recipient_type = "user"

                    # Get sub-account details for sender info
                    sub_account = await self.agent_repository.get_sub_account_by_id(
                        sender_id
                    )
                    sender_info = {
                        "agent_id": sender_id,
                        "name": sub_account.display_name if sub_account else "Agent",
                        "agent_name": sub_account.name if sub_account else "Unknown",
                    }

                # Send message with smart presence-aware routing for all recipients
                # This method handles all cases: subscribed, online, offline
                notification_result = (
                    await self.notification_service.send_message_with_presence_routing(
                        recipient_id=recipient_id,
                        recipient_type=recipient_type,
                        chatroom_id=chatroom_id,
                        message_data={
                            "message": message,
                            "message_id": str(stored_message.id),
                            "sender_id": sender_id,
                            "sender_type": sender_type,
                        },
                        sender_info=sender_info,
                    )
                )

                logger.info(
                    f"Message notification routed for {recipient_type} {recipient_id}",
                    extra={
                        "chatroom_id": chatroom_id,
                        "recipient_id": recipient_id,
                        "recipient_type": recipient_type,
                        "message_sent": notification_result.get("message_sent"),
                        "routing": notification_result.get("routing"),
                        "recipient_online": notification_result.get("recipient_online"),
                        "recipient_subscribed": notification_result.get(
                            "recipient_subscribed"
                        ),
                        "external_push_triggered": notification_result.get(
                            "external_push_triggered"
                        ),
                    },
                )

            except Exception as e:
                # Don't fail the entire message send if notification fails
                logger.warning(
                    f"Failed to check subscription or send notification: {e}",
                    extra={
                        "chatroom_id": chatroom_id,
                        "sender_id": sender_id,
                        "sender_type": sender_type,
                    },
                )

            return pusher_payload

        except Exception as e:
            logger.error(f"Failed to send and store message: {str(e)}")
            raise ValidationError(f"Failed to send message: {str(e)}")

    async def send_system_message(
        self,
        chatroom_id: str,
        message: str,
        message_type: str = "system",
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Send a system message in a chatroom and store in database."""
        chatroom = await self.chatroom_repository.get_chatroom_by_id(chatroom_id)
        if not chatroom:
            raise NotFoundError(f"Chatroom {chatroom_id} not found")

        # Store system message in database first
        try:
            message_create = MessageCreate(
                chatroom_id=chatroom_id,
                sender_id=None,  # System messages have no sender
                sender_type=MessageSenderType.SYSTEM,
                message=message,
                message_type=MessageType.SYSTEM,
                metadata=metadata or {},
            )

            stored_message = await self.message_repository.create(message_create)

            # Create system message payload
            message_payload = {
                "id": str(stored_message.id),
                "chatroom_id": chatroom_id,
                "sender_id": "system",
                "sender_type": "system",
                "message": message,
                "message_type": message_type,
                "metadata": metadata or {},
                "timestamp": safe_isoformat_or_now(stored_message.created_at),
                "is_stored": True,
            }

            # Send via Pusher to presence channel for system messages
            pusher_channel = self.chatroom_pusher_service.get_presence_channel_name(
                chatroom_id
            )
            pusher_payload = await self.chatroom_pusher_service.send_system_event(
                channel=pusher_channel,
                message=message,
                event_type=message_type,
                metadata=metadata,
                chatroom_id=chatroom_id,
            )

            # Update the payload with stored message info
            pusher_payload.update(message_payload)

            return pusher_payload

        except Exception as e:
            logger.error(f"Failed to send and store system message: {str(e)}")
            raise ValidationError(f"Failed to send system message: {str(e)}")

    async def notify_typing(
        self, chatroom_id: str, sender_id: str, is_typing: bool
    ) -> bool:
        """Send typing indicator via Pusher."""
        chatroom = await self.chatroom_repository.get_chatroom_by_id(chatroom_id)
        if not chatroom:
            return False

        try:
            # Use presence channel for typing indicators
            pusher_channel = self.chatroom_pusher_service.get_presence_channel_name(
                chatroom_id
            )
            return await self.chatroom_pusher_service.send_typing_indicator(
                pusher_channel, sender_id, is_typing
            )
        except Exception:
            return False

    async def join_chatroom(self, chatroom_id: str, user_id: str) -> Dict[str, Any]:
        """Handle user joining a chatroom."""
        chatroom = await self.chatroom_repository.get_chatroom_by_id(chatroom_id)
        if not chatroom:
            raise NotFoundError(f"Chatroom {chatroom_id} not found")

        # Validate user belongs to chatroom
        if str(chatroom.user_id) != user_id:
            raise ValidationError("User not authorized for this chatroom")

        # Update last activity when user joins (tracks engagement)
        await self.update_last_activity(chatroom_id)

        # Return chatroom details with auth info
        response = await self._to_chatroom_response_with_details(chatroom)

        return {
            "chatroom": response,
            "pusher_auth": {
                "channel": chatroom.channel_name,
                "socket_id": None,  # Will be provided by frontend
            },
        }

    async def leave_chatroom(self, chatroom_id: str, user_id: str) -> bool:
        """Handle user leaving a chatroom."""
        chatroom = await self.chatroom_repository.get_chatroom_by_id(chatroom_id)
        if not chatroom or str(chatroom.user_id) != user_id:
            return False

        # Update last activity when user leaves (tracks engagement)
        await self.update_last_activity(chatroom_id)

        return True

    async def end_chatroom(self, chatroom_id: str, ended_by: str) -> bool:
        """End a chatroom and notify participants."""
        chatroom = await self.chatroom_repository.get_chatroom_by_id(chatroom_id)
        if not chatroom or chatroom.status != ChatroomStatus.ACTIVE:
            return False

        # End chatroom in database
        success = await self.chatroom_repository.end_chatroom(chatroom_id)
        if not success:
            return False

        # Decrement sub-account chat count
        await self.agent_repository.decrement_sub_account_chat_count(
            str(chatroom.sub_account_id)
        )

        # Send system notification
        await self.send_system_message(
            chatroom_id,
            f"Chat ended by {ended_by}",
            message_type="chat_ended",
            metadata={"ended_by": ended_by},
        )

        return True

    async def get_chatroom_participants(self, chatroom_id: str) -> Dict[str, Any]:
        """Get chatroom participants with their details."""
        chatroom = await self.chatroom_repository.get_chatroom_by_id(chatroom_id)
        if not chatroom:
            raise NotFoundError(f"Chatroom {chatroom_id} not found")

        # Get user details
        user = await self.user_repository.get_by_id(str(chatroom.user_id))
        user_info = None
        if user:
            user_info = {
                "id": str(user.id),
                "username": user.username,
                "full_name": user.full_name,
                "avatar_url": user.avatar_url,
                "is_active": user.is_active,
            }

        # Get sub-account details
        sub_account = await self.agent_repository.get_sub_account_by_id(
            str(chatroom.sub_account_id)
        )
        agent_info = None
        if sub_account:
            agent_info = {
                "id": str(sub_account.id),
                "name": sub_account.name,
                "display_name": sub_account.display_name,
                "avatar_url": sub_account.avatar_url,
                "bio": sub_account.bio,
                "status": sub_account.status,
            }

        return {
            "chatroom_id": chatroom_id,
            "user": user_info,
            "agent": agent_info,
            "channel_name": chatroom.channel_name,
            "status": chatroom.status,
        }

    async def get_chatroom_messages(
        self, chatroom_id: str, user_id: str, pagination: PaginationParams
    ) -> PaginationResponse:
        """
        Get messages for a chatroom with access validation and proper pagination.

        Retrieves paginated messages from a chatroom, ensuring the requesting user
        has access to the chatroom. Messages are returned in reverse chronological
        order (newest first) with full pagination metadata.

        Args:
            chatroom_id: Unique identifier of the chatroom
            user_id: Unique identifier of the requesting user
            pagination: Pagination parameters (page, page_size)

        Returns:
            PaginationResponse with message data and pagination metadata

        Raises:
            ValidationError: If input parameters are invalid
            NotFoundError: If chatroom not found or access denied
        """
        try:
            # Validate input
            if not chatroom_id or not chatroom_id.strip():
                raise ValidationError("Chatroom ID is required")

            if not user_id or not user_id.strip():
                raise ValidationError("User ID is required")

            chatroom_id = chatroom_id.strip()
            user_id = user_id.strip()

            # Get and validate chatroom access
            chatroom = await self.chatroom_repository.get_chatroom_by_id(chatroom_id)
            if not chatroom:
                raise NotFoundError(f"Chatroom {chatroom_id} not found")

            # Verify user has access to this chatroom
            if str(chatroom.user_id) != user_id:
                raise ValidationError("Access denied to this chatroom")

            # Get messages from repository with pagination
            messages = await self.message_repository.get_chatroom_messages(
                chatroom_id, pagination.limit, pagination.skip
            )

            # Get total message count for pagination
            total_messages = await self.message_repository.count_chatroom_messages(
                chatroom_id
            )

            # Create proper pagination response
            pagination_response = PaginationResponse.create(
                items=messages,
                total_items=total_messages,
                page=pagination.page,
                page_size=pagination.page_size,
            )

            logger.info(
                "Chatroom messages retrieved successfully",
                extra={
                    "chatroom_id": chatroom_id,
                    "user_id": user_id,
                    "message_count": len(messages),
                    "page": pagination.page,
                    "page_size": pagination.page_size,
                    "total_messages": total_messages,
                },
            )

            return pagination_response

        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error retrieving chatroom messages: %s",
                str(e),
                extra={
                    "chatroom_id": chatroom_id,
                    "user_id": user_id,
                    "page": pagination.page,
                    "page_size": pagination.page_size,
                },
            )
            raise

    async def _to_chatroom_response_with_details(
        self, chatroom: Chatroom
    ) -> ChatroomResponse:
        """Convert Chatroom model to ChatroomResponse with participant details."""
        # Get basic response
        base_response = ChatroomResponse(
            _id=chatroom.id,
            user_id=str(chatroom.user_id),
            sub_account_id=str(chatroom.sub_account_id),
            agent_id=str(chatroom.agent_id),
            status=chatroom.status,
            channel_name=chatroom.channel_name,
            metadata=chatroom.metadata,
            started_at=chatroom.started_at,
            ended_at=chatroom.ended_at,
            last_activity_at=chatroom.last_activity_at,
            created_at=chatroom.created_at,
            updated_at=chatroom.updated_at,
        )

        # Add participant details to metadata for frontend convenience
        participants = await self.get_chatroom_participants(str(chatroom.id))

        # Enhanced metadata with participant info
        enhanced_metadata = {
            **base_response.metadata,
            "participants": participants,
        }

        base_response.metadata = enhanced_metadata
        return base_response
