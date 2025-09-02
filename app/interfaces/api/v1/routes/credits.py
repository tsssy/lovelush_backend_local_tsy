"""
Credit management API endpoints for user credit operations.
Provides endpoints for managing user credits, transactions, balances,
and credit adjustments with proper authentication and validation.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import ValidationError as PydanticValidationError

from app.core.dependencies import get_credits_service, get_message_credit_service
from app.core.exceptions.exceptions import BaseCustomException, ValidationError
from app.core.logging import get_logger
from app.core.responses import ResponseHelper
from app.domain.models.credits import (
    CreditAdjustment,
    TransactionReason,
    TransactionType,
    UserCreditsCreate,
)
from app.domain.models.user import User
from app.domain.services.credits_service import CreditsService
from app.domain.services.message_credit_service import MessageCreditService
from app.infrastructure.security.dependencies import get_current_active_user

router = APIRouter(prefix="/credits", tags=["Credits"])
logger = get_logger(__name__)


@router.post("/users", response_model=dict, summary="Create user credits account")
async def create_user_credits(
    user_data: UserCreditsCreate,
    credits_service: CreditsService = Depends(get_credits_service),
    _current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Create a new user credits account.

    Creates a new credit account for a user with initial balance.
    This is typically an administrative operation.

    Args:
        user_data: User credits creation data with user_id and initial balance
        credits_service: Injected credits service instance
        _current_user: Currently authenticated user (admin access required)

    Returns:
        ResponseHelper.created with credits account data

    Raises:
        HTTPException(400): Invalid input data or user already has credits
        HTTPException(401): User not authenticated
        HTTPException(500): Internal server error during creation
    """
    try:
        credits = await credits_service.create_user_credits(user_data)

        logger.info(
            "User credits account created",
            extra={
                "user_id": user_data.user_id,
                "initial_balance": credits.current_balance,
            },
        )

        return ResponseHelper.created(
            data=credits, msg="User credits account created successfully"
        )

    except ValidationError as e:
        logger.warning("Credits creation validation error", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except BaseCustomException as e:
        logger.warning("Credits creation business error", extra={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error creating user credits: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/users/{user_id}", response_model=dict, summary="Get user credits")
async def get_user_credits(
    user_id: str = Path(..., min_length=24, max_length=24, description="User ID"),
    credits_service: CreditsService = Depends(get_credits_service),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Get user's credit balance and details.

    Retrieves the credit account information for a specific user.
    Users can only view their own credits unless they have admin privileges.

    Args:
        user_id: MongoDB ObjectId of the user
        credits_service: Injected credits service instance
        current_user: Currently authenticated user

    Returns:
        ResponseHelper.success with credits data

    Raises:
        HTTPException(400): Invalid user ID format
        HTTPException(401): User not authenticated
        HTTPException(403): Access denied to view other user's credits
        HTTPException(404): User credits not found
        HTTPException(500): Internal server error during retrieval
    """
    try:
        # Check if user is trying to access their own credits or is admin
        if str(current_user.id) != user_id:
            # TODO: Add proper admin role check here
            logger.warning(
                "Unauthorized credits access attempt",
                extra={
                    "requesting_user_id": str(current_user.id),
                    "target_user_id": user_id,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to view other user's credits",
            )

        credits = await credits_service.get_user_credits(user_id)
        if not credits:
            logger.warning("User credits not found", extra={"user_id": user_id})
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User credits not found"
            )

        logger.debug(
            "User credits retrieved",
            extra={"user_id": user_id, "balance": credits.current_balance},
        )
        return ResponseHelper.success(
            data=credits, msg="User credits retrieved successfully"
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid user ID format", extra={"user_id": user_id, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
        )
    except BaseCustomException as e:
        logger.warning(
            "Credits retrieval business error",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error retrieving user credits: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/users/{user_id}/transactions",
    response_model=dict,
    summary="Get user transactions",
)
async def get_user_transactions(
    user_id: str = Path(..., min_length=24, max_length=24, description="User ID"),
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of records to return"
    ),
    transaction_type: Optional[TransactionType] = Query(
        None, description="Filter by transaction type"
    ),
    credits_service: CreditsService = Depends(get_credits_service),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Get user's credit transaction history.

    Retrieves paginated transaction history for a user with optional filtering.
    Users can only view their own transactions unless they have admin privileges.

    Args:
        user_id: MongoDB ObjectId of the user
        limit: Maximum number of records to return (1-100)
        transaction_type: Optional transaction type filter (DEBIT/CREDIT)
        credits_service: Injected credits service instance
        current_user: Currently authenticated user

    Returns:
        ResponseHelper.success with transaction history data

    Raises:
        HTTPException(400): Invalid user ID format or parameters
        HTTPException(401): User not authenticated
        HTTPException(403): Access denied to view other user's transactions
        HTTPException(500): Internal server error during retrieval
    """
    try:
        # Check if user is trying to access their own transactions or is admin
        if str(current_user.id) != user_id:
            # TODO: Add proper admin role check here
            logger.warning(
                "Unauthorized transaction access attempt",
                extra={
                    "requesting_user_id": str(current_user.id),
                    "target_user_id": user_id,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to view other user's transactions",
            )

        transactions = await credits_service.get_user_transactions(user_id, limit)

        # Apply client-side filtering if transaction_type is specified
        if transaction_type:
            transactions = [
                t for t in transactions if t.transaction_type == transaction_type
            ]

        transaction_data = {
            "user_id": user_id,
            "transactions": [t for t in transactions],
            "total_count": len(transactions),
            "transaction_type_filter": transaction_type,
        }

        logger.info(
            "User transaction history retrieved",
            extra={
                "user_id": user_id,
                "transaction_count": len(transactions),
                "filter": transaction_type.value if transaction_type else None,
            },
        )

        return ResponseHelper.success(
            data=transaction_data,
            msg="User transaction history retrieved successfully",
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid parameters for transactions",
            extra={"user_id": user_id, "limit": limit, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid parameters"
        )
    except BaseCustomException as e:
        logger.warning(
            "Transaction retrieval business error",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error retrieving transactions: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/users/{user_id}/add", response_model=dict, summary="Add credits to user account"
)
async def add_user_credits(
    user_id: str = Path(..., min_length=24, max_length=24, description="User ID"),
    amount: int = Query(..., gt=0, description="Amount of credits to add"),
    reason: TransactionReason = Query(..., description="Reason for adding credits"),
    description: Optional[str] = Query(None, description="Transaction description"),
    credits_service: CreditsService = Depends(get_credits_service),
    _current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Add credits to user account.

    Administrative operation to add credits to a user's account with proper
    transaction tracking and validation.

    Args:
        user_id: MongoDB ObjectId of the user
        amount: Amount of credits to add (must be positive)
        reason: Reason for adding credits (enum value)
        description: Optional transaction description
        credits_service: Injected credits service instance
        _current_user: Currently authenticated user (admin access required)

    Returns:
        ResponseHelper.success with transaction data

    Raises:
        HTTPException(400): Invalid input data or user ID format
        HTTPException(401): User not authenticated
        HTTPException(404): User not found
        HTTPException(500): Internal server error during credit addition
    """
    try:
        success = await credits_service.add_credits(
            user_id=user_id, amount=amount, reason=reason, description=description
        )

        if success:
            logger.info(
                "Credits added successfully",
                extra={
                    "user_id": user_id,
                    "amount": amount,
                    "reason": reason.value,
                    "added_by": str(_current_user.id),
                },
            )

            return ResponseHelper.success(
                data={
                    "user_id": user_id,
                    "amount": amount,
                    "reason": reason.value,
                    "description": description,
                },
                msg="Credits added successfully",
            )
        else:
            logger.warning(
                "Failed to add credits",
                extra={"user_id": user_id, "amount": amount, "reason": reason.value},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to add credits"
            )

    except HTTPException:
        raise
    except BaseCustomException as e:
        logger.warning(
            "Credits addition business error",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PydanticValidationError as e:
        logger.warning("Credits addition validation error", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except ValueError as e:
        logger.warning(
            "Invalid user ID format for adding credits",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
        )
    except Exception as e:
        logger.exception("Unexpected error adding credits: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/users/{user_id}/consume",
    response_model=dict,
    summary="Consume credits from user account",
)
async def consume_user_credits(
    user_id: str = Path(..., min_length=24, max_length=24, description="User ID"),
    amount: int = Query(..., gt=0, description="Amount of credits to consume"),
    reason: TransactionReason = Query(..., description="Reason for consuming credits"),
    reference_id: Optional[str] = Query(
        None, description="Reference ID (e.g., chatroom ID)"
    ),
    description: Optional[str] = Query(None, description="Transaction description"),
    credits_service: CreditsService = Depends(get_credits_service),
    _current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Consume credits from user account.

    Processes credit consumption for user activities like paid matches or services.
    Includes validation to ensure sufficient balance and proper transaction recording.

    Args:
        user_id: MongoDB ObjectId of the user
        amount: Amount of credits to consume (must be positive)
        reason: Reason for consuming credits (enum value)
        reference_id: Optional reference ID (e.g., chatroom ID, match ID)
        description: Optional transaction description
        credits_service: Injected credits service instance
        _current_user: Currently authenticated user (for audit trail)

    Returns:
        ResponseHelper.success with transaction data

    Raises:
        HTTPException(400): Invalid input data, insufficient credits, or user ID format
        HTTPException(401): User not authenticated
        HTTPException(404): User not found
        HTTPException(500): Internal server error during credit consumption
    """
    try:
        success = await credits_service.consume_credits(
            user_id=user_id,
            amount=amount,
            reason=reason,
            reference_id=reference_id,
            description=description,
        )

        if success:
            logger.info(
                "Credits consumed successfully",
                extra={
                    "user_id": user_id,
                    "amount": amount,
                    "reason": reason.value,
                    "reference_id": reference_id,
                    "consumed_by": str(_current_user.id),
                },
            )

            return ResponseHelper.success(
                data={
                    "user_id": user_id,
                    "amount": amount,
                    "reason": reason.value,
                    "reference_id": reference_id,
                    "description": description,
                },
                msg="Credits consumed successfully",
            )
        else:
            logger.warning(
                "Credit consumption failed",
                extra={"user_id": user_id, "amount": amount, "reason": reason.value},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient credits or consumption failed",
            )

    except HTTPException:
        raise
    except BaseCustomException as e:
        logger.warning(
            "Credit consumption business error",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PydanticValidationError as e:
        logger.warning("Credit consumption validation error", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except ValueError as e:
        logger.warning(
            "Invalid user ID format for consuming credits",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
        )
    except Exception as e:
        logger.exception("Unexpected error consuming credits: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/users/{user_id}/adjust",
    response_model=dict,
    summary="Manually adjust user credits",
)
async def adjust_user_credits(
    adjustment: CreditAdjustment,
    user_id: str = Path(..., min_length=24, max_length=24, description="User ID"),
    credits_service: CreditsService = Depends(get_credits_service),
    _current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Manually adjust user credits (admin operation).

    Administrative operation for manual credit adjustments with proper validation
    and audit trails. Used for corrections, compensations, or other admin actions.

    Args:
        adjustment: Credit adjustment data including amount and reason
        user_id: MongoDB ObjectId of the user (must match adjustment data)
        credits_service: Injected credits service instance
        _current_user: Currently authenticated user (admin access required)

    Returns:
        ResponseHelper.success with adjustment data

    Raises:
        HTTPException(400): Invalid input data, user ID mismatch, or format errors
        HTTPException(401): User not authenticated
        HTTPException(404): User not found
        HTTPException(500): Internal server error during credit adjustment
    """
    try:
        # Ensure user_id in path matches adjustment data
        if adjustment.user_id != user_id:
            logger.warning(
                "User ID mismatch in credit adjustment",
                extra={
                    "path_user_id": user_id,
                    "adjustment_user_id": adjustment.user_id,
                    "admin_user_id": str(_current_user.id),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID in path must match adjustment data",
            )

        success = await credits_service.adjust_credits(adjustment)

        if success:
            logger.info(
                "Credits adjusted successfully",
                extra={
                    "user_id": user_id,
                    "amount": adjustment.amount,
                    "reason": adjustment.reason.value,
                    "adjusted_by": str(_current_user.id),
                },
            )

            return ResponseHelper.success(
                data=adjustment, msg="Credits adjusted successfully"
            )
        else:
            logger.warning(
                "Credit adjustment failed",
                extra={"user_id": user_id, "amount": adjustment.amount},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Credit adjustment failed",
            )

    except HTTPException:
        raise
    except ValidationError as e:
        logger.warning("Credit adjustment validation error", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except ValueError as e:
        logger.warning(
            "Invalid user ID format for credit adjustment",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
        )
    except BaseCustomException as e:
        logger.warning(
            "Credit adjustment business error",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error adjusting credits: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/users/{user_id}/grant-initial",
    response_model=dict,
    summary="Grant initial credits to new user",
)
async def grant_initial_credits(
    user_id: str = Path(..., min_length=24, max_length=24, description="User ID"),
    credits_service: CreditsService = Depends(get_credits_service),
    _current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Grant initial credits to new user.

    Provides new users with their initial credit allocation as part of the onboarding
    process. Typically used during user registration or first-time setup.

    Args:
        user_id: MongoDB ObjectId of the user
        credits_service: Injected credits service instance
        _current_user: Currently authenticated user (admin access required)

    Returns:
        ResponseHelper.success with granted credits data

    Raises:
        HTTPException(400): Invalid input data, user already has credits, or format errors
        HTTPException(401): User not authenticated
        HTTPException(404): User not found
        HTTPException(500): Internal server error during credit granting
    """
    try:
        success = await credits_service.grant_initial_credits(user_id)

        if success:
            logger.info(
                "Initial credits granted successfully",
                extra={
                    "user_id": user_id,
                    "granted_by": str(_current_user.id),
                },
            )

            return ResponseHelper.success(
                data={"user_id": user_id, "type": "initial_grant"},
                msg="Initial credits granted successfully",
            )
        else:
            logger.warning(
                "Failed to grant initial credits",
                extra={"user_id": user_id},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to grant initial credits",
            )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid user ID format for granting credits",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
        )
    except BaseCustomException as e:
        logger.warning(
            "Initial credit grant business error",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error granting initial credits: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/users/{user_id}/ensure",
    response_model=dict,
    summary="Ensure user has credits account",
)
async def ensure_user_credits(
    user_id: str = Path(..., min_length=24, max_length=24, description="User ID"),
    credits_service: CreditsService = Depends(get_credits_service),
    _current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Ensure user has a credits account, create if it doesn't exist.

    Utility endpoint that guarantees a user has a credits account. If the account
    doesn't exist, it creates one with default settings. Used for system initialization.

    Args:
        user_id: MongoDB ObjectId of the user
        credits_service: Injected credits service instance
        _current_user: Currently authenticated user (for audit purposes)

    Returns:
        ResponseHelper.success with credits account data

    Raises:
        HTTPException(400): Invalid user ID format
        HTTPException(401): User not authenticated
        HTTPException(500): Internal server error during account creation
    """
    try:
        credits = await credits_service.get_or_create_user_credits(user_id)

        logger.info(
            "User credits account ensured",
            extra={
                "user_id": user_id,
                "current_balance": (
                    credits.current_balance
                    if hasattr(credits, "current_balance")
                    else getattr(credits, "balance", 0)
                ),
                "ensured_by": str(_current_user.id),
            },
        )

        return ResponseHelper.success(data=credits, msg="User credits account ensured")

    except ValueError as e:
        logger.warning(
            "Invalid user ID format for ensuring credits",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
        )
    except BaseCustomException as e:
        logger.warning(
            "Credits account ensure business error",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error ensuring user credits: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/users/{user_id}/message-status",
    response_model=dict,
    summary="Get user's message sending status",
)
async def get_user_message_status(
    user_id: str = Path(..., min_length=24, max_length=24, description="User ID"),
    message_credit_service: MessageCreditService = Depends(get_message_credit_service),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Get user's current message sending status and available credits.

    Provides detailed information about user's messaging capabilities including
    available free messages, credit balance, and sending permissions.

    Args:
        user_id: MongoDB ObjectId of the user
        message_credit_service: Injected message credit service instance
        current_user: Currently authenticated user

    Returns:
        ResponseHelper.success with message status data

    Raises:
        HTTPException(400): Invalid user ID format
        HTTPException(401): User not authenticated
        HTTPException(403): Access denied to view other user's message status
        HTTPException(500): Internal server error during retrieval
    """
    try:
        # Check if user is trying to access their own message status or is admin
        if str(current_user.id) != user_id:
            logger.warning(
                "Unauthorized message status access attempt",
                extra={
                    "requesting_user_id": str(current_user.id),
                    "target_user_id": user_id,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to view other user's message status",
            )

        message_status = await message_credit_service.get_user_message_status(user_id)

        logger.debug(
            "User message status retrieved",
            extra={
                "user_id": user_id,
                "can_send_message": message_status["can_send_message"],
                "available_free_messages": message_status["available_free_messages"],
                "current_credits": message_status["current_credits"],
            },
        )

        return ResponseHelper.success(
            data=message_status, msg="User message status retrieved successfully"
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid user ID format for message status",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
        )
    except BaseCustomException as e:
        logger.warning(
            "Message status retrieval business error",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error retrieving message status: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
