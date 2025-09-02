"""
Bot message management API endpoints for handling bot platform messages.
Provides endpoints for retrieving, filtering, and managing messages from various bot platforms
with user authentication and permission controls.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.dependencies import get_bot_message_service
from app.core.logging import get_logger
from app.core.responses import ResponseHelper
from app.domain.models.pagination import PaginationParams
from app.domain.models.user import User
from app.infrastructure.security.dependencies import get_current_active_user
from app.interfaces.telegram.models.bot_message import BotPlatform
from app.interfaces.telegram.services.bot_message_service import BotMessageService

router = APIRouter(prefix="/bot-messages", tags=["Bot Messages"])
logger = get_logger(__name__)


@router.get("/me", response_model=dict, summary="Get my bot messages")
async def get_my_bot_messages(
    platform: Optional[BotPlatform] = Query(None, description="Filter by platform"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    bot_message_service: BotMessageService = Depends(get_bot_message_service),
) -> Dict[str, Any]:
    """
    Get bot messages for the current user.

    Retrieves bot messages filtered by platform and paginated for the authenticated user.
    Only returns messages that belong to the current user.

    Args:
        platform: Optional platform filter (e.g., telegram, discord)
        pagination: Pagination parameters (page, page_size)
        current_user: Currently authenticated user
        bot_message_service: Injected bot message service instance

    Returns:
        ResponseHelper.success with paginated bot messages

    Raises:
        HTTPException(401): User not authenticated
        HTTPException(500): Internal server error during message retrieval
    """
    try:
        result = await bot_message_service.get_user_messages(
            str(current_user.id), platform, pagination
        )

        logger.info(
            "User bot messages retrieved",
            extra={
                "user_id": str(current_user.id),
                "platform": platform.value if platform else "all",
                "message_count": len(result.items),
            },
        )

        return ResponseHelper.success(
            data=result, msg="Bot messages retrieved successfully"
        )
    except Exception as e:
        logger.exception("Unexpected error retrieving bot messages: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{message_id}", response_model=dict, summary="Get bot message by ID")
async def get_bot_message(
    message_id: str = Path(..., min_length=24, max_length=24, description="Message ID"),
    current_user: User = Depends(get_current_active_user),
    bot_message_service: BotMessageService = Depends(get_bot_message_service),
) -> Dict[str, Any]:
    """
    Get bot message by ID.

    Retrieves a specific bot message if the authenticated user owns it.
    Includes ownership validation for security.

    Args:
        message_id: MongoDB ObjectId of the bot message
        current_user: Currently authenticated user
        bot_message_service: Injected bot message service instance

    Returns:
        ResponseHelper.success with bot message data

    Raises:
        HTTPException(400): Invalid message ID format
        HTTPException(401): User not authenticated
        HTTPException(403): User doesn't own the message
        HTTPException(404): Bot message not found
        HTTPException(500): Internal server error during retrieval
    """
    try:
        message = await bot_message_service.get_message_by_id(message_id)
        if not message:
            logger.warning("Bot message not found", extra={"message_id": message_id})
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Bot message not found"
            )

        # Verify user owns this message
        if message.user_id != str(current_user.id):
            logger.warning(
                "Unauthorized bot message access attempt",
                extra={
                    "message_id": message_id,
                    "requesting_user_id": str(current_user.id),
                    "message_owner_id": message.user_id,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this message",
            )

        logger.debug("Bot message retrieved by user", extra={"message_id": message_id})
        return ResponseHelper.success(
            data=message, msg="Bot message retrieved successfully"
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid message ID format",
            extra={"message_id": message_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid message ID format"
        )
    except Exception as e:
        logger.exception("Unexpected error retrieving bot message: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.patch(
    "/{message_id}/processed", response_model=dict, summary="Mark message as processed"
)
async def mark_message_processed(
    message_id: str = Path(..., min_length=24, max_length=24, description="Message ID"),
    current_user: User = Depends(get_current_active_user),
    bot_message_service: BotMessageService = Depends(get_bot_message_service),
) -> Dict[str, Any]:
    """
    Mark bot message as processed.

    Updates the processing status of a bot message. Typically used for
    administrative purposes or debugging workflows.

    Args:
        message_id: MongoDB ObjectId of the bot message
        current_user: Currently authenticated user
        bot_message_service: Injected bot message service instance

    Returns:
        ResponseHelper.success with operation status

    Raises:
        HTTPException(400): Invalid message ID format
        HTTPException(401): User not authenticated
        HTTPException(404): Bot message not found
        HTTPException(500): Internal server error during processing
    """
    try:
        success = await bot_message_service.mark_message_as_processed(message_id)

        logger.info(
            "Bot message processing status updated",
            extra={
                "message_id": message_id,
                "success": success,
                "user_id": str(current_user.id),
            },
        )

        return ResponseHelper.success(
            data={"success": success},
            msg=(
                "Message marked as processed"
                if success
                else "Failed to mark message as processed"
            ),
        )

    except ValueError as e:
        logger.warning(
            "Invalid message ID format for processing",
            extra={"message_id": message_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid message ID format"
        )
    except Exception as e:
        logger.exception("Unexpected error marking message as processed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/unprocessed", response_model=dict, summary="Get unprocessed messages")
async def get_unprocessed_messages(
    platform: Optional[BotPlatform] = Query(None, description="Filter by platform"),
    limit: int = Query(
        100, ge=1, le=500, description="Maximum number of messages to return"
    ),
    current_user: User = Depends(get_current_active_user),
    bot_message_service: BotMessageService = Depends(get_bot_message_service),
) -> Dict[str, Any]:
    """
    Get unprocessed bot messages.

    Retrieves bot messages that haven't been processed yet, filtered by platform.
    Typically used for administrative or debugging purposes.

    Args:
        platform: Optional platform filter (e.g., telegram, discord)
        limit: Maximum number of messages to return (1-500)
        current_user: Currently authenticated user
        bot_message_service: Injected bot message service instance

    Returns:
        ResponseHelper.success with unprocessed messages data

    Raises:
        HTTPException(400): Invalid limit parameter
        HTTPException(401): User not authenticated
        HTTPException(500): Internal server error during message retrieval
    """
    try:
        messages = await bot_message_service.get_unprocessed_messages(platform, limit)

        logger.info(
            "Unprocessed bot messages retrieved",
            extra={
                "platform": platform.value if platform else "all",
                "limit": limit,
                "message_count": len(messages),
                "user_id": str(current_user.id),
            },
        )

        return ResponseHelper.success(
            data=messages, msg="Unprocessed messages retrieved successfully"
        )

    except ValueError as e:
        logger.warning(
            "Invalid parameter for unprocessed messages",
            extra={"limit": limit, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid parameters"
        )
    except Exception as e:
        logger.exception("Unexpected error retrieving unprocessed messages: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
