"""
Chatroom management API endpoints for user chat operations.
Provides endpoints for users to manage chatrooms, send messages, handle typing indicators,
and participate in real-time chat sessions with AI agents.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import ValidationError as PydanticValidationError

from app.core.dependencies import get_chatroom_service
from app.core.exceptions.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.responses import ResponseHelper
from app.domain.models.chatroom import SendMessageRequest, TypingIndicatorRequest
from app.domain.models.pagination import PaginationParams
from app.domain.models.user import User
from app.domain.services.chatroom_service import ChatroomService
from app.infrastructure.security.dependencies import get_current_active_user

router = APIRouter(prefix="/chatrooms", tags=["Chatrooms"])
logger = get_logger(__name__)


@router.get("/{chatroom_id}", response_model=dict, summary="Get chatroom details")
async def get_chatroom(
    chatroom_id: str = Path(
        ..., min_length=24, max_length=24, description="Chatroom ID"
    ),
    current_user: User = Depends(get_current_active_user),
    chatroom_service: ChatroomService = Depends(get_chatroom_service),
) -> Dict[str, Any]:
    """
    Get chatroom details by ID.

    Retrieves detailed chatroom information with participant details.
    Only accessible by users who are participants in the chatroom.

    Args:
        chatroom_id: MongoDB ObjectId of the chatroom
        current_user: Currently authenticated user
        chatroom_service: Injected chatroom service instance

    Returns:
        ResponseHelper.success with chatroom data

    Raises:
        HTTPException(400): Invalid chatroom ID format
        HTTPException(401): User not authenticated
        HTTPException(403): Access denied to chatroom
        HTTPException(404): Chatroom not found
        HTTPException(500): Internal server error during retrieval
    """
    try:
        chatroom = await chatroom_service.get_chatroom_by_id(chatroom_id)
        if not chatroom:
            logger.warning("Chatroom not found", extra={"chatroom_id": chatroom_id})
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chatroom not found",
            )

        # Verify user has access to this chatroom
        if chatroom.user_id != str(current_user.id):
            logger.warning(
                "Unauthorized chatroom access attempt",
                extra={
                    "chatroom_id": chatroom_id,
                    "user_id": str(current_user.id),
                    "chatroom_owner_id": chatroom.user_id,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this chatroom",
            )

        logger.debug("Chatroom retrieved", extra={"chatroom_id": chatroom_id})
        return ResponseHelper.success(
            data=chatroom, msg="Chatroom retrieved successfully"
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid chatroom ID format",
            extra={"chatroom_id": chatroom_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid chatroom ID format"
        )
    except Exception as e:
        logger.exception("Unexpected error getting chatroom: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/", response_model=dict, summary="Get user chatrooms")
async def get_user_chatrooms(
    current_user: User = Depends(get_current_active_user),
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of chatrooms to return"
    ),
    include_last_messages: int = Query(
        1,
        ge=0,
        le=10,
        description="Number of latest messages to include per chatroom (0=none)",
    ),
    chatroom_service: ChatroomService = Depends(get_chatroom_service),
) -> Dict[str, Any]:
    """
    Get current user's chatrooms with participant details and last messages.

    Retrieves a list of user's chatrooms with participant details,
    ordered by most recent activity first. Optionally includes the
    last N messages for each chatroom to provide UI context.

    Args:
        current_user: Currently authenticated user
        limit: Maximum number of chatrooms to return (1-100)
        include_last_messages: Number of latest messages per chatroom (0-10, 0=none)
        chatroom_service: Injected chatroom service instance

    Returns:
        ResponseHelper.success with chatrooms data including last messages

    Raises:
        HTTPException(400): Invalid limit or include_last_messages parameter
        HTTPException(401): User not authenticated
        HTTPException(500): Internal server error during retrieval
    """
    try:
        chatrooms = await chatroom_service.get_user_chatrooms(
            str(current_user.id), limit, include_last_messages
        )

        logger.info(
            "User chatrooms retrieved",
            extra={
                "user_id": str(current_user.id),
                "chatroom_count": len(chatrooms),
                "limit": limit,
                "include_last_messages": include_last_messages,
            },
        )

        return ResponseHelper.success(
            data={
                "chatrooms": chatrooms,
                "metadata": {
                    "returned_count": len(chatrooms),
                    "limit": limit,
                    "include_last_messages": include_last_messages,
                },
            },
            msg="Chatrooms retrieved successfully",
        )

    except ValueError as e:
        logger.warning(
            "Invalid parameter for user chatrooms",
            extra={
                "limit": limit,
                "include_last_messages": include_last_messages,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid parameter"
        )
    except Exception as e:
        logger.exception("Unexpected error getting user chatrooms: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/{chatroom_id}/join", response_model=dict, summary="Join chatroom")
async def join_chatroom(
    chatroom_id: str = Path(
        ..., min_length=24, max_length=24, description="Chatroom ID"
    ),
    current_user: User = Depends(get_current_active_user),
    chatroom_service: ChatroomService = Depends(get_chatroom_service),
) -> Dict[str, Any]:
    """
    Join a chatroom.

    Returns chatroom details and Pusher authentication info for real-time messaging.
    User must be a participant in the chatroom to join successfully.

    Args:
        chatroom_id: MongoDB ObjectId of the chatroom to join
        current_user: Currently authenticated user
        chatroom_service: Injected chatroom service instance

    Returns:
        ResponseHelper.success with chatroom and pusher authentication data

    Raises:
        HTTPException(400): Invalid chatroom ID format
        HTTPException(401): User not authenticated
        HTTPException(403): Access denied to chatroom
        HTTPException(404): Chatroom not found
        HTTPException(500): Internal server error during join
    """
    try:
        result = await chatroom_service.join_chatroom(chatroom_id, str(current_user.id))

        logger.info(
            "User joined chatroom successfully",
            extra={"chatroom_id": chatroom_id, "user_id": str(current_user.id)},
        )

        return ResponseHelper.success(data=result, msg="Joined chatroom successfully")

    except ValueError as e:
        logger.warning(
            "Invalid chatroom ID format for join",
            extra={"chatroom_id": chatroom_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid chatroom ID format"
        )
    except NotFoundError as e:
        logger.warning(
            "Chatroom not found for join",
            extra={"chatroom_id": chatroom_id, "error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        logger.warning("Chatroom join validation error", extra={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error joining chatroom: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to join chatroom",
        )


@router.post("/{chatroom_id}/leave", response_model=dict, summary="Leave chatroom")
async def leave_chatroom(
    chatroom_id: str = Path(
        ..., min_length=24, max_length=24, description="Chatroom ID"
    ),
    current_user: User = Depends(get_current_active_user),
    chatroom_service: ChatroomService = Depends(get_chatroom_service),
) -> Dict[str, Any]:
    """
    Leave a chatroom.

    Sends a system notification that the user has left and updates the chatroom status.
    User can only leave chatrooms they are currently participating in.

    Args:
        chatroom_id: MongoDB ObjectId of the chatroom to leave
        current_user: Currently authenticated user
        chatroom_service: Injected chatroom service instance

    Returns:
        ResponseHelper.success with operation confirmation

    Raises:
        HTTPException(400): Invalid chatroom ID format
        HTTPException(401): User not authenticated
        HTTPException(404): Chatroom not found or access denied
        HTTPException(500): Internal server error during leave
    """
    try:
        success = await chatroom_service.leave_chatroom(
            chatroom_id, str(current_user.id)
        )
        if not success:
            logger.warning(
                "Failed to leave chatroom",
                extra={"chatroom_id": chatroom_id, "user_id": str(current_user.id)},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chatroom not found or access denied",
            )

        logger.info(
            "User left chatroom successfully",
            extra={"chatroom_id": chatroom_id, "user_id": str(current_user.id)},
        )

        return ResponseHelper.success(
            data={"success": True}, msg="Left chatroom successfully"
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid chatroom ID format for leave",
            extra={"chatroom_id": chatroom_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid chatroom ID format"
        )
    except Exception as e:
        logger.exception("Unexpected error leaving chatroom: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to leave chatroom",
        )


@router.post("/{chatroom_id}/messages", response_model=dict, summary="Send message")
async def send_message(
    message_request: SendMessageRequest,
    chatroom_id: str = Path(
        ..., min_length=24, max_length=24, description="Chatroom ID"
    ),
    current_user: User = Depends(get_current_active_user),
    chatroom_service: ChatroomService = Depends(get_chatroom_service),
) -> Dict[str, Any]:
    """
    Send a message in a chatroom.

    Sends a message from the user to the chatroom and broadcasts it
    to all participants via real-time channels.

    Args:
        message_request: Message content and metadata
        chatroom_id: MongoDB ObjectId of the chatroom
        current_user: Currently authenticated user
        chatroom_service: Injected chatroom service instance

    Returns:
        ResponseHelper.success with message data

    Raises:
        HTTPException(400): Invalid input data or chatroom ID format
        HTTPException(401): User not authenticated
        HTTPException(404): Chatroom not found
        HTTPException(500): Internal server error during message sending
    """
    try:
        message_payload = await chatroom_service.send_message(
            chatroom_id=chatroom_id,
            sender_id=str(current_user.id),
            message=message_request.message,
            sender_type="user",
            message_type=message_request.message_type,
            metadata=message_request.metadata,
        )

        logger.info(
            "User message sent",
            extra={
                "chatroom_id": chatroom_id,
                "user_id": str(current_user.id),
                "message_length": len(message_request.message),
            },
        )

        return ResponseHelper.success(
            data=message_payload, msg="Message sent successfully"
        )

    except NotFoundError as e:
        logger.warning(
            "Chatroom not found for message",
            extra={"chatroom_id": chatroom_id, "error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        logger.warning("Message validation error", extra={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PydanticValidationError as e:
        logger.warning("Message format validation error", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid message format: {str(e)}",
        )
    except ValueError as e:
        logger.warning(
            "Invalid chatroom ID format for message",
            extra={"chatroom_id": chatroom_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid chatroom ID format"
        )
    except Exception as e:
        logger.exception("Unexpected error sending message: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/{chatroom_id}/typing", response_model=dict, summary="Send typing indicator"
)
async def send_typing_indicator(
    typing_request: TypingIndicatorRequest,
    chatroom_id: str = Path(
        ..., min_length=24, max_length=24, description="Chatroom ID"
    ),
    current_user: User = Depends(get_current_active_user),
    chatroom_service: ChatroomService = Depends(get_chatroom_service),
) -> Dict[str, Any]:
    """
    Send typing indicator.

    Broadcasts typing status to other participants in the chatroom.
    Provides real-time feedback about user activity.

    Args:
        typing_request: Typing indicator status data
        chatroom_id: MongoDB ObjectId of the chatroom
        current_user: Currently authenticated user
        chatroom_service: Injected chatroom service instance

    Returns:
        ResponseHelper.success with operation confirmation

    Raises:
        HTTPException(400): Invalid input data or chatroom ID format
        HTTPException(401): User not authenticated
        HTTPException(404): Chatroom not found
        HTTPException(500): Internal server error during typing indicator
    """
    try:
        success = await chatroom_service.notify_typing(
            chatroom_id, str(current_user.id), typing_request.is_typing
        )

        if not success:
            logger.warning(
                "Chatroom not found for typing indicator",
                extra={"chatroom_id": chatroom_id},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chatroom not found",
            )

        logger.debug(
            "Typing indicator sent",
            extra={
                "chatroom_id": chatroom_id,
                "user_id": str(current_user.id),
                "is_typing": typing_request.is_typing,
            },
        )

        return ResponseHelper.success(
            data={"success": True}, msg="Typing indicator sent"
        )

    except HTTPException:
        raise
    except PydanticValidationError as e:
        logger.warning("Typing request validation error", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid typing request: {str(e)}",
        )
    except ValueError as e:
        logger.warning(
            "Invalid chatroom ID format for typing",
            extra={"chatroom_id": chatroom_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid chatroom ID format"
        )
    except Exception as e:
        logger.exception("Unexpected error sending typing indicator: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send typing indicator",
        )


@router.post("/{chatroom_id}/end", response_model=dict, summary="End chatroom session")
async def end_chatroom(
    chatroom_id: str = Path(
        ..., min_length=24, max_length=24, description="Chatroom ID"
    ),
    current_user: User = Depends(get_current_active_user),
    chatroom_service: ChatroomService = Depends(get_chatroom_service),
) -> Dict[str, Any]:
    """
    End a chatroom.

    Ends the chatroom session and notifies all participants.
    This action is irreversible and closes the conversation.

    Args:
        chatroom_id: MongoDB ObjectId of the chatroom to end
        current_user: Currently authenticated user
        chatroom_service: Injected chatroom service instance

    Returns:
        ResponseHelper.success with operation confirmation

    Raises:
        HTTPException(400): Invalid chatroom ID format
        HTTPException(401): User not authenticated
        HTTPException(404): Chatroom not found or already ended
        HTTPException(500): Internal server error during chatroom termination
    """
    try:
        success = await chatroom_service.end_chatroom(chatroom_id, str(current_user.id))

        if not success:
            logger.warning(
                "Failed to end chatroom",
                extra={"chatroom_id": chatroom_id, "user_id": str(current_user.id)},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chatroom not found or already ended",
            )

        logger.info(
            "Chatroom ended by user",
            extra={"chatroom_id": chatroom_id, "user_id": str(current_user.id)},
        )

        return ResponseHelper.success(
            data={"success": True}, msg="Chatroom ended successfully"
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid chatroom ID format for ending",
            extra={"chatroom_id": chatroom_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid chatroom ID format"
        )
    except Exception as e:
        logger.exception("Unexpected error ending chatroom: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to end chatroom",
        )


@router.get(
    "/{chatroom_id}/messages",
    response_model=dict,
    summary="Get chatroom messages",
)
async def get_chatroom_messages(
    chatroom_id: str = Path(
        ..., min_length=24, max_length=24, description="Chatroom ID"
    ),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    chatroom_service: ChatroomService = Depends(get_chatroom_service),
) -> Dict[str, Any]:
    """
    Get chatroom messages with pagination.

    Retrieves messages from the specified chatroom in reverse chronological order
    (newest first) with proper pagination metadata. Only accessible by users who are
    participants in the chatroom.

    Args:
        chatroom_id: MongoDB ObjectId of the chatroom
        pagination: Pagination parameters (page, page_size)
        current_user: Currently authenticated user
        chatroom_service: Injected chatroom service instance

    Returns:
        ResponseHelper.success with PaginationResponse containing messages

    Raises:
        HTTPException(400): Invalid chatroom ID format or pagination parameters
        HTTPException(401): User not authenticated
        HTTPException(403): Access denied to chatroom
        HTTPException(404): Chatroom not found
        HTTPException(500): Internal server error during message retrieval
    """
    try:
        pagination_response = await chatroom_service.get_chatroom_messages(
            chatroom_id, str(current_user.id), pagination
        )

        logger.info(
            "Chatroom messages retrieved",
            extra={
                "chatroom_id": chatroom_id,
                "user_id": str(current_user.id),
                "message_count": len(pagination_response.items),
                "page": pagination.page,
                "page_size": pagination.page_size,
                "total_messages": pagination_response.total_items,
            },
        )

        return ResponseHelper.success(
            data=pagination_response, msg="Messages retrieved successfully"
        )

    except ValueError as e:
        logger.warning(
            "Invalid chatroom ID format for messages",
            extra={"chatroom_id": chatroom_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid chatroom ID format"
        )
    except ValidationError as e:
        logger.warning("Access denied to chatroom messages", extra={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except NotFoundError as e:
        logger.warning(
            "Chatroom not found for messages",
            extra={"chatroom_id": chatroom_id, "error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error getting chatroom messages: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get messages",
        )


@router.get(
    "/{chatroom_id}/participants",
    response_model=dict,
    summary="Get chatroom participants",
)
async def get_chatroom_participants(
    chatroom_id: str = Path(
        ..., min_length=24, max_length=24, description="Chatroom ID"
    ),
    current_user: User = Depends(get_current_active_user),
    chatroom_service: ChatroomService = Depends(get_chatroom_service),
) -> Dict[str, Any]:
    """
    Get chatroom participants.

    Returns details about all participants in the chatroom including
    the user and agent information. Includes access validation.

    Args:
        chatroom_id: MongoDB ObjectId of the chatroom
        current_user: Currently authenticated user
        chatroom_service: Injected chatroom service instance

    Returns:
        ResponseHelper.success with participants data

    Raises:
        HTTPException(400): Invalid chatroom ID format
        HTTPException(401): User not authenticated
        HTTPException(403): Access denied to chatroom
        HTTPException(404): Chatroom not found
        HTTPException(500): Internal server error during participant retrieval
    """
    try:
        participants = await chatroom_service.get_chatroom_participants(chatroom_id)

        # Verify user has access
        if participants["user"] and participants["user"]["id"] != str(current_user.id):
            logger.warning(
                "Unauthorized access to chatroom participants",
                extra={
                    "chatroom_id": chatroom_id,
                    "requesting_user_id": str(current_user.id),
                    "participant_user_id": participants["user"]["id"],
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this chatroom",
            )

        logger.debug(
            "Chatroom participants retrieved",
            extra={"chatroom_id": chatroom_id, "user_id": str(current_user.id)},
        )

        return ResponseHelper.success(
            data=participants, msg="Participants retrieved successfully"
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid chatroom ID format for participants",
            extra={"chatroom_id": chatroom_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid chatroom ID format"
        )
    except NotFoundError as e:
        logger.warning(
            "Chatroom not found for participants",
            extra={"chatroom_id": chatroom_id, "error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error getting participants: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get participants",
        )
