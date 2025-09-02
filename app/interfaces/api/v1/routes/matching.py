"""Matching API routes for user-agent matching and chatrooms."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import ValidationError as PydanticValidationError

from app.core.dependencies import get_credits_service, get_matching_service
from app.core.exceptions.exceptions import (
    NotFoundError,
    ResourceConflictError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.responses import ResponseHelper
from app.domain.models.chatroom import (
    ChatRequest,
)
from app.domain.models.user import User
from app.domain.services.credits_service import CreditsService
from app.domain.services.matching_service import MatchingService
from app.infrastructure.security.dependencies import get_current_active_user

router = APIRouter(prefix="/matching", tags=["Matching"])
logger = get_logger(__name__)


@router.get("/matches", response_model=dict, summary="Get current matches")
async def get_current_matches(
    current_user: User = Depends(get_current_active_user),
    matching_service: MatchingService = Depends(get_matching_service),
) -> Dict[str, Any]:
    """
    Get user's current available matches with UI context.

    Returns unused candidates from active match record, plus metadata about the last match
    for UI to display match history, progress, and context. This helps the UI show users
    their match journey and current status.

    Args:
        current_user: Currently authenticated user
        matching_service: Injected matching service instance

    Returns:
        ResponseHelper.success with available candidates, match status, and last match metadata

    Raises:
        HTTPException(401): User not authenticated
        HTTPException(500): Internal server error
    """
    try:
        result = await matching_service.get_current_matches(str(current_user.id))

        logger.info(
            "Current matches retrieved",
            extra={
                "user_id": str(current_user.id),
                "candidates_count": len(result.candidates),
                "has_remaining_matches": result.has_remaining_matches,
            },
        )

        return ResponseHelper.success(
            data=result, msg="Current matches retrieved successfully"
        )

    except Exception as e:
        logger.exception("Unexpected error getting current matches: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get current matches",
        )


@router.post("/matches", response_model=dict, summary="Request new matches")
async def request_new_matches(
    use_paid_match: bool = Query(
        False, description="Whether to use paid match if no free matches"
    ),
    current_user: User = Depends(get_current_active_user),
    matching_service: MatchingService = Depends(get_matching_service),
) -> Dict[str, Any]:
    """
    Request new matches for the user.

    Logic:
    1. FIRST: If user has unused candidates from current match → return those (no new matches)
    2. If no unused candidates and user has remaining free matches → create new free match
    3. If no unused candidates and no free matches left:
       - use_paid_match=false → error
       - use_paid_match=true → create paid match (if has credits)

    Args:
        use_paid_match: Whether to use paid match if no free matches available
        current_user: Currently authenticated user
        matching_service: Injected matching service instance

    Returns:
        ResponseHelper.success with match candidates (existing unused or new) and metadata

    Raises:
        HTTPException(400): Invalid request, insufficient credits, or no unused matches
        HTTPException(401): User not authenticated
        HTTPException(500): Internal server error during match request
    """
    try:
        result = await matching_service.request_new_matches(
            str(current_user.id), use_paid_match
        )

        logger.info(
            "New matches requested",
            extra={
                "user_id": str(current_user.id),
                "use_paid_match": use_paid_match,
                "candidates_count": len(result.candidates),
                "credits_consumed": result.credits_consumed,
                "remaining_credits": result.remaining_credits,
            },
        )

        return ResponseHelper.success(
            data=result, msg="New matches retrieved successfully"
        )

    except ResourceConflictError as e:
        logger.warning("Insufficient credits for paid match", extra={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except NotFoundError as e:
        logger.warning("No matches available", extra={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        logger.warning("Match request validation error", extra={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        logger.warning("Match request value error", extra={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error requesting new matches: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to request new matches",
        )


@router.post("/chat", response_model=dict, summary="Create or get chatroom")
async def create_chat(
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    matching_service: MatchingService = Depends(get_matching_service),
) -> Dict[str, Any]:
    """
    Create or get existing chatroom with selected sub-account.

    Creates a new chatroom between user and selected sub-account or returns
    existing chatroom if one already exists (idempotent behavior). This prevents
    duplicate chatrooms and allows users to resume conversations.

    SECURITY: New chatrooms can only be created with sub-accounts from the user's
    current unused matches. Existing chatrooms can always be accessed regardless
    of current match status.

    Args:
        chat_request: Chat request data with user_id and sub_account_id
        current_user: Currently authenticated user
        matching_service: Injected matching service instance

    Returns:
        ResponseHelper.success with chatroom details and creation status metadata

    Raises:
        HTTPException(400): Invalid input data, unauthorized sub-account, or validation errors
        HTTPException(401): User not authenticated
        HTTPException(403): Access denied - user ID mismatch
        HTTPException(404): Sub-account not found
        HTTPException(500): Internal server error during chat creation
    """
    try:
        # Ensure user can only create chats for themselves
        if chat_request.user_id != str(current_user.id):
            logger.warning(
                "Unauthorized chat creation attempt",
                extra={
                    "requesting_user_id": str(current_user.id),
                    "chat_request_user_id": chat_request.user_id,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only create chats for yourself",
            )

        result = await matching_service.create_chat(chat_request)

        logger.info(
            "Chat created successfully",
            extra={
                "user_id": str(current_user.id),
                "sub_account_id": chat_request.sub_account_id,
            },
        )

        return ResponseHelper.success(data=result, msg="Chat created successfully")

    except HTTPException:
        raise
    except PydanticValidationError as e:
        logger.warning("Chat request validation error", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except NotFoundError as e:
        logger.warning(
            "Sub-account not found for chat creation", extra={"error": str(e)}
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        logger.warning(
            "Chat creation business validation error", extra={"error": str(e)}
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        logger.warning("Chat creation value error", extra={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error creating chat: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create chat",
        )


@router.post("/chat/{chatroom_id}/end", response_model=dict, summary="End chat session")
async def end_chat(
    chatroom_id: str = Path(
        ..., min_length=24, max_length=24, description="Chatroom ID"
    ),
    current_user: User = Depends(get_current_active_user),
    matching_service: MatchingService = Depends(get_matching_service),
) -> Dict[str, Any]:
    """
    End a chatroom.

    Ends the specified chatroom and decrements the sub-account's active chat count.
    Includes proper ownership validation to ensure only the user who created
    the chatroom can end it.

    Args:
        chatroom_id: MongoDB ObjectId of the chatroom to end
        current_user: Currently authenticated user
        matching_service: Injected matching service instance

    Returns:
        ResponseHelper.success with operation confirmation

    Raises:
        HTTPException(400): Invalid chatroom ID format
        HTTPException(401): User not authenticated
        HTTPException(404): Chatroom not found or already ended
        HTTPException(500): Internal server error during chat termination
    """
    try:
        success = await matching_service.end_chat(chatroom_id)

        if not success:
            logger.warning(
                "Failed to end chat - chatroom not found or already ended",
                extra={"chatroom_id": chatroom_id, "user_id": str(current_user.id)},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chatroom not found or already ended",
            )

        logger.info(
            "Chat ended successfully",
            extra={"chatroom_id": chatroom_id, "user_id": str(current_user.id)},
        )

        return ResponseHelper.success(
            data={"success": True}, msg="Chat ended successfully"
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid chatroom ID format for ending chat",
            extra={"chatroom_id": chatroom_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid chatroom ID format"
        )
    except Exception as e:
        logger.exception("Unexpected error ending chat: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to end chat",
        )


@router.get(
    "/matches/history",
    response_model=dict,
    summary="Get user match history",
)
async def get_match_history(
    current_user: User = Depends(get_current_active_user),
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of match records to return"
    ),
    matching_service: MatchingService = Depends(get_matching_service),
) -> Dict[str, Any]:
    """
    Get current user's match history.

    Retrieves paginated match history for the authenticated user,
    showing all match activities including free and paid matches.

    Args:
        current_user: Currently authenticated user
        limit: Maximum number of match records to return (1-100)
        matching_service: Injected matching service instance

    Returns:
        ResponseHelper.success with match history data

    Raises:
        HTTPException(400): Invalid limit parameter
        HTTPException(401): User not authenticated
        HTTPException(500): Internal server error during match history retrieval
    """
    try:
        result = await matching_service.get_user_match_history(
            str(current_user.id), limit
        )

        logger.info(
            "Match history retrieved",
            extra={
                "user_id": str(current_user.id),
                "match_count": len(result) if isinstance(result, list) else 0,
                "limit": limit,
            },
        )

        return ResponseHelper.success(
            data={"match_history": result}, msg="Match history retrieved successfully"
        )

    except ValueError as e:
        logger.warning(
            "Invalid limit parameter for match history",
            extra={"limit": limit, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid limit parameter"
        )
    except Exception as e:
        logger.exception("Unexpected error getting match history: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get match history",
        )


@router.get("/credits", response_model=dict, summary="Get user credits")
async def get_user_credits(
    current_user: User = Depends(get_current_active_user),
    credits_service: CreditsService = Depends(get_credits_service),
) -> Dict[str, Any]:
    """
    Get current user's credits balance and free matches status.

    Retrieves the authenticated user's credit information including current balance,
    free matches remaining, and other credit-related metadata. Creates a credits
    account if one doesn't exist.

    Args:
        current_user: Currently authenticated user
        credits_service: Injected credits service instance

    Returns:
        ResponseHelper.success with user credits data

    Raises:
        HTTPException(401): User not authenticated
        HTTPException(500): Internal server error during credits retrieval
    """
    try:
        result = await credits_service.get_or_create_user_credits(str(current_user.id))

        logger.info(
            "User credits retrieved",
            extra={
                "user_id": str(current_user.id),
                "current_balance": getattr(result, "current_balance", 0),
            },
        )

        return ResponseHelper.success(data=result, msg="Credits retrieved successfully")

    except Exception as e:
        logger.exception("Unexpected error getting user credits: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get credits",
        )


@router.get(
    "/credits/transactions",
    response_model=dict,
    summary="Get credit transaction history",
)
async def get_credit_transactions(
    current_user: User = Depends(get_current_active_user),
    limit: int = Query(
        50, ge=1, le=500, description="Maximum number of transactions to return"
    ),
    credits_service: CreditsService = Depends(get_credits_service),
) -> Dict[str, Any]:
    """
    Get current user's credit transaction history.

    Retrieves paginated transaction history for the authenticated user,
    showing all credit-related activities including purchases, consumptions,
    and adjustments.

    Args:
        current_user: Currently authenticated user
        limit: Maximum number of transactions to return (1-500)
        credits_service: Injected credits service instance

    Returns:
        ResponseHelper.success with transaction history data

    Raises:
        HTTPException(400): Invalid limit parameter
        HTTPException(401): User not authenticated
        HTTPException(500): Internal server error during transaction retrieval
    """
    try:
        result = await credits_service.get_user_transactions(
            str(current_user.id), limit
        )

        logger.info(
            "Credit transaction history retrieved",
            extra={
                "user_id": str(current_user.id),
                "transaction_count": len(result) if isinstance(result, list) else 0,
                "limit": limit,
            },
        )

        return ResponseHelper.success(
            data=result, msg="Transaction history retrieved successfully"
        )

    except ValueError as e:
        logger.warning(
            "Invalid limit parameter for transactions",
            extra={"limit": limit, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid limit parameter"
        )
    except Exception as e:
        logger.exception("Unexpected error getting transaction history: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get transaction history",
        )
