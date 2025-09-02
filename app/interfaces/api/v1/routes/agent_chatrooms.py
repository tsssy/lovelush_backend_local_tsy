"""
Agent chatroom management API endpoints for AI agent chat operations.
Provides endpoints for agents to manage chatrooms, send messages, handle typing indicators,
and interact with users in real-time chat sessions.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import ValidationError as PydanticValidationError

from app.core.dependencies import get_chatroom_service
from app.core.exceptions.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.responses import ResponseHelper
from app.domain.models.chatroom import AgentSendMessageRequest, AgentTypingRequest
from app.domain.models.pagination import PaginationParams
from app.domain.services.chatroom_service import ChatroomService
from app.infrastructure.security.dependencies import get_current_active_agent

router = APIRouter(prefix="/agent/chatrooms", tags=["Agent Chatrooms"])
logger = get_logger(__name__)


@router.get("/", response_model=dict, summary="Get agent chatrooms")
async def get_agent_chatrooms(
    sub_account_id: str = Query(
        ..., min_length=24, max_length=24, description="Sub-account ID"
    ),
    limit: int = Query(
        default=50, ge=1, le=100, description="Maximum number of chatrooms to return"
    ),
    _agent: dict = Depends(get_current_active_agent),
    chatroom_service: ChatroomService = Depends(get_chatroom_service),
) -> Dict[str, Any]:
    """
    Get agent's active chatrooms.

    Retrieves a list of active chatrooms assigned to the specified sub-account.
    Only returns chatrooms where the agent has active participation.

    Args:
        sub_account_id: MongoDB ObjectId of the sub-account
        limit: Maximum number of chatrooms to return (1-100)
        _agent: Currently authenticated agent from JWT token (for auth only)
        chatroom_service: Injected chatroom service instance

    Returns:
        ResponseHelper.success with chatrooms data

    Raises:
        HTTPException(400): Invalid sub-account ID format or parameters
        HTTPException(401): Agent not authenticated
        HTTPException(500): Internal server error during retrieval
    """
    try:
        chatrooms = await chatroom_service.get_sub_account_chatrooms(
            sub_account_id, limit
        )

        logger.info(
            "Agent chatrooms retrieved",
            extra={"sub_account_id": sub_account_id, "chatroom_count": len(chatrooms)},
        )

        return ResponseHelper.success(
            data=chatrooms, msg="Agent chatrooms retrieved successfully"
        )

    except ValueError as e:
        logger.warning(
            "Invalid sub-account ID format",
            extra={"sub_account_id": sub_account_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid sub-account ID format",
        )
    except Exception as e:
        logger.exception("Unexpected error getting agent chatrooms: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{chatroom_id}", response_model=dict, summary="Get agent chatroom details")
async def get_agent_chatroom(
    chatroom_id: str = Path(
        ..., min_length=24, max_length=24, description="Chatroom ID"
    ),
    sub_account_id: str = Query(
        ..., min_length=24, max_length=24, description="Sub-account ID"
    ),
    _agent: dict = Depends(get_current_active_agent),
    chatroom_service: ChatroomService = Depends(get_chatroom_service),
) -> Dict[str, Any]:
    """
    Get specific chatroom details for agent.

    Retrieves detailed chatroom information if the agent is authorized to access it.
    Includes validation to ensure the agent only accesses their assigned chatrooms.

    Args:
        chatroom_id: MongoDB ObjectId of the chatroom
        sub_account_id: MongoDB ObjectId of the sub-account
        _agent: Currently authenticated agent from JWT token (for auth only)
        chatroom_service: Injected chatroom service instance

    Returns:
        ResponseHelper.success with chatroom data

    Raises:
        HTTPException(400): Invalid chatroom or sub-account ID format
        HTTPException(401): Agent not authenticated
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

        # Verify agent has access to this chatroom
        if chatroom.sub_account_id != sub_account_id:
            logger.warning(
                "Access denied to chatroom",
                extra={
                    "chatroom_id": chatroom_id,
                    "sub_account_id": sub_account_id,
                    "chatroom_sub_account_id": chatroom.sub_account_id,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this chatroom",
            )

        logger.debug("Agent chatroom retrieved", extra={"chatroom_id": chatroom_id})
        return ResponseHelper.success(
            data=chatroom, msg="Chatroom retrieved successfully"
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid ID format",
            extra={
                "chatroom_id": chatroom_id,
                "sub_account_id": sub_account_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format"
        )
    except Exception as e:
        logger.exception("Unexpected error getting chatroom: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/{chatroom_id}/messages", response_model=dict, summary="Send agent message"
)
async def agent_send_message(
    message_request: AgentSendMessageRequest,
    chatroom_id: str = Path(
        ..., min_length=24, max_length=24, description="Chatroom ID"
    ),
    sub_account_id: str = Query(
        ..., min_length=24, max_length=24, description="Sub-account ID"
    ),
    _agent: dict = Depends(get_current_active_agent),
    chatroom_service: ChatroomService = Depends(get_chatroom_service),
) -> Dict[str, Any]:
    """
    Send message as agent in a chatroom.

    Sends a message from the agent to the user in the specified chatroom.
    The message is broadcast to all participants via real-time channels.

    Args:
        message_request: Message content and metadata
        chatroom_id: MongoDB ObjectId of the chatroom
        sub_account_id: MongoDB ObjectId of the sub-account
        _agent: Currently authenticated agent from JWT token (for auth only)
        chatroom_service: Injected chatroom service instance

    Returns:
        ResponseHelper.success with message data

    Raises:
        HTTPException(400): Invalid input data or ID format
        HTTPException(401): Agent not authenticated
        HTTPException(404): Chatroom not found
        HTTPException(500): Internal server error during message sending
    """
    try:
        message_payload = await chatroom_service.send_message(
            chatroom_id=chatroom_id,
            sender_id=sub_account_id,
            message=message_request.message,
            sender_type="agent",
            message_type=message_request.message_type,
            metadata=message_request.metadata,
        )

        logger.info(
            "Agent message sent",
            extra={
                "chatroom_id": chatroom_id,
                "sub_account_id": sub_account_id,
                "message_length": len(message_request.message),
            },
        )

        return ResponseHelper.success(
            data=message_payload, msg="Agent message sent successfully"
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
            "Invalid ID format for message",
            extra={"chatroom_id": chatroom_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format"
        )
    except Exception as e:
        logger.exception("Unexpected error sending agent message: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/{chatroom_id}/messages",
    response_model=dict,
    summary="Get chatroom messages for agent",
)
async def get_agent_chatroom_messages(
    chatroom_id: str = Path(
        ..., min_length=24, max_length=24, description="Chatroom ID"
    ),
    sub_account_id: str = Query(
        ..., min_length=24, max_length=24, description="Sub-account ID"
    ),
    pagination: PaginationParams = Depends(),
    _agent: dict = Depends(get_current_active_agent),
    chatroom_service: ChatroomService = Depends(get_chatroom_service),
) -> Dict[str, Any]:
    """
    Get chatroom messages from agent perspective.

    Retrieves messages from the specified chatroom in reverse chronological order
    (newest first) with proper pagination metadata. Only accessible by agents who are
    assigned to the chatroom via the sub-account.

    Args:
        chatroom_id: MongoDB ObjectId of the chatroom
        sub_account_id: MongoDB ObjectId of the sub-account
        pagination: Pagination parameters (page, page_size)
        _agent: Currently authenticated agent from JWT token (for auth only)
        chatroom_service: Injected chatroom service instance

    Returns:
        ResponseHelper.success with PaginationResponse containing messages

    Raises:
        HTTPException(400): Invalid chatroom ID format or pagination parameters
        HTTPException(401): Agent not authenticated
        HTTPException(403): Access denied to chatroom
        HTTPException(404): Chatroom not found
        HTTPException(500): Internal server error during message retrieval
    """
    try:
        # First verify the chatroom exists and agent has access
        chatroom = await chatroom_service.get_chatroom_by_id(chatroom_id)
        if not chatroom:
            logger.warning("Chatroom not found", extra={"chatroom_id": chatroom_id})
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chatroom not found",
            )

        # Verify agent has access to this chatroom via sub-account
        if chatroom.sub_account_id != sub_account_id:
            logger.warning(
                "Access denied to chatroom messages",
                extra={
                    "chatroom_id": chatroom_id,
                    "sub_account_id": sub_account_id,
                    "chatroom_sub_account_id": chatroom.sub_account_id,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this chatroom",
            )

        # Get messages using the user_id from the chatroom since the service expects user_id
        pagination_response = await chatroom_service.get_chatroom_messages(
            chatroom_id, chatroom.user_id, pagination
        )

        logger.info(
            "Agent chatroom messages retrieved",
            extra={
                "chatroom_id": chatroom_id,
                "sub_account_id": sub_account_id,
                "message_count": len(pagination_response.items),
                "page": pagination.page,
                "page_size": pagination.page_size,
                "total_messages": pagination_response.total_items,
            },
        )

        return ResponseHelper.success(
            data=pagination_response, msg="Messages retrieved successfully"
        )

    except HTTPException:
        raise
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
        logger.exception("Unexpected error getting agent chatroom messages: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get messages",
        )


@router.post(
    "/{chatroom_id}/typing", response_model=dict, summary="Send agent typing indicator"
)
async def agent_send_typing_indicator(
    typing_request: AgentTypingRequest,
    chatroom_id: str = Path(
        ..., min_length=24, max_length=24, description="Chatroom ID"
    ),
    sub_account_id: str = Query(
        ..., min_length=24, max_length=24, description="Sub-account ID"
    ),
    _agent: dict = Depends(get_current_active_agent),
    chatroom_service: ChatroomService = Depends(get_chatroom_service),
) -> Dict[str, Any]:
    """
    Send typing indicator as agent.

    Updates the typing status for the agent in the specified chatroom.
    This provides real-time feedback to users about agent activity.

    Args:
        typing_request: Typing indicator status
        chatroom_id: MongoDB ObjectId of the chatroom
        sub_account_id: MongoDB ObjectId of the sub-account
        _agent: Currently authenticated agent from JWT token (for auth only)
        chatroom_service: Injected chatroom service instance

    Returns:
        ResponseHelper.success with operation confirmation

    Raises:
        HTTPException(400): Invalid input data or ID format
        HTTPException(401): Agent not authenticated
        HTTPException(404): Chatroom not found
        HTTPException(500): Internal server error during typing indicator
    """
    try:
        success = await chatroom_service.notify_typing(
            chatroom_id, sub_account_id, typing_request.is_typing
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
            "Agent typing indicator sent",
            extra={
                "chatroom_id": chatroom_id,
                "sub_account_id": sub_account_id,
                "is_typing": typing_request.is_typing,
            },
        )

        return ResponseHelper.success(
            data={"success": True}, msg="Agent typing indicator sent"
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
            "Invalid ID format for typing indicator",
            extra={"chatroom_id": chatroom_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format"
        )
    except Exception as e:
        logger.exception("Unexpected error sending typing indicator: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/{chatroom_id}/end", response_model=dict, summary="End chatroom session")
async def agent_end_chatroom(
    chatroom_id: str = Path(
        ..., min_length=24, max_length=24, description="Chatroom ID"
    ),
    sub_account_id: str = Query(
        ..., min_length=24, max_length=24, description="Sub-account ID"
    ),
    _agent: dict = Depends(get_current_active_agent),
    chatroom_service: ChatroomService = Depends(get_chatroom_service),
) -> Dict[str, Any]:
    """
    End chatroom as agent.

    Terminates the chat session and notifies all participants.
    This action is irreversible and closes the conversation.

    Args:
        chatroom_id: MongoDB ObjectId of the chatroom
        sub_account_id: MongoDB ObjectId of the sub-account
        _agent: Currently authenticated agent from JWT token (for auth only)
        chatroom_service: Injected chatroom service instance

    Returns:
        ResponseHelper.success with operation confirmation

    Raises:
        HTTPException(400): Invalid chatroom or sub-account ID format
        HTTPException(401): Agent not authenticated
        HTTPException(404): Chatroom not found or already ended
        HTTPException(500): Internal server error during chatroom termination
    """
    try:
        success = await chatroom_service.end_chatroom(
            chatroom_id, f"agent:{sub_account_id}"
        )

        if not success:
            logger.warning(
                "Chatroom not found or already ended",
                extra={"chatroom_id": chatroom_id},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chatroom not found or already ended",
            )

        logger.info(
            "Chatroom ended by agent",
            extra={"chatroom_id": chatroom_id, "sub_account_id": sub_account_id},
        )

        return ResponseHelper.success(
            data={"success": True}, msg="Chatroom ended by agent"
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid ID format for chatroom ending",
            extra={"chatroom_id": chatroom_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format"
        )
    except Exception as e:
        logger.exception("Unexpected error ending chatroom: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/{chatroom_id}/participants",
    response_model=dict,
    summary="Get chatroom participants",
)
async def get_agent_chatroom_participants(
    chatroom_id: str = Path(
        ..., min_length=24, max_length=24, description="Chatroom ID"
    ),
    sub_account_id: str = Query(
        ..., min_length=24, max_length=24, description="Sub-account ID"
    ),
    _agent: dict = Depends(get_current_active_agent),
    chatroom_service: ChatroomService = Depends(get_chatroom_service),
) -> Dict[str, Any]:
    """
    Get chatroom participants from agent perspective.

    Retrieves details about all participants in the chatroom including
    the user and agent information. Includes access validation.

    Args:
        chatroom_id: MongoDB ObjectId of the chatroom
        sub_account_id: MongoDB ObjectId of the sub-account
        _agent: Currently authenticated agent from JWT token (for auth only)
        chatroom_service: Injected chatroom service instance

    Returns:
        ResponseHelper.success with participants data

    Raises:
        HTTPException(400): Invalid chatroom or sub-account ID format
        HTTPException(401): Agent not authenticated
        HTTPException(403): Access denied to chatroom
        HTTPException(404): Chatroom not found
        HTTPException(500): Internal server error during participant retrieval
    """
    try:
        participants = await chatroom_service.get_chatroom_participants(chatroom_id)

        # Verify agent has access to this chatroom
        if participants["agent"] and participants["agent"]["id"] != sub_account_id:
            logger.warning(
                "Access denied to chatroom participants",
                extra={
                    "chatroom_id": chatroom_id,
                    "sub_account_id": sub_account_id,
                    "participant_agent_id": participants["agent"]["id"],
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this chatroom",
            )

        logger.debug(
            "Chatroom participants retrieved", extra={"chatroom_id": chatroom_id}
        )
        return ResponseHelper.success(
            data=participants, msg="Participants retrieved successfully"
        )

    except HTTPException:
        raise
    except NotFoundError as e:
        logger.warning(
            "Chatroom not found for participants",
            extra={"chatroom_id": chatroom_id, "error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        logger.warning(
            "Invalid ID format for participants",
            extra={"chatroom_id": chatroom_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format"
        )
    except Exception as e:
        logger.exception("Unexpected error getting participants: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
