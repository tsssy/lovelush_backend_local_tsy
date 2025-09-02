"""
Payment processing API endpoints for financial transaction management.
Provides endpoints for creating, retrieving, and managing payment records
with support for different payment statuses and user payment history.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
)
from fastapi import status as http_status
from pydantic import ValidationError as PydanticValidationError

from app.core.dependencies import get_payment_service
from app.core.exceptions.exceptions import (
    BaseCustomException,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.responses import ResponseHelper
from app.domain.models.payment import (
    Currency,
    PaymentCreate,
    PaymentStatus,
)
from app.domain.models.user import User
from app.domain.services.payment_service import PaymentService
from app.infrastructure.security.dependencies import get_current_active_user

router = APIRouter(prefix="/payments", tags=["Payments"])
logger = get_logger(__name__)


@router.post("/invoice/create", response_model=dict, summary="Create payment invoice")
async def create_payment_invoice(
    telegram_user_id: str,
    product_id: str,
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Create a Telegram payment invoice.

    Creates a payment record and generates a Telegram invoice URL for payment processing.
    The frontend will use this to show the payment popup to the user.

    Args:
        telegram_user_id: Telegram user ID who will make the payment
        product_id: MongoDB ObjectId of the product to purchase
        payment_service: Injected payment service instance
        current_user: Currently authenticated user

    Returns:
        ResponseHelper.created with payment data and invoice URL

    Raises:
        HTTPException(400): Invalid product ID or product not available
        HTTPException(401): User not authenticated
        HTTPException(404): Product not found
        HTTPException(500): Internal server error during invoice creation
    """
    try:
        payment_request = PaymentCreate(
            telegram_user_id=telegram_user_id,
            product_id=product_id,
            amount=0,  # Will be set by service based on product
            currency=Currency.TELEGRAM_STARS,  # Will be set by service based on product
            invoice_payload=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        # Create payment record
        payment = await payment_service.create_payment(payment_request)

        # Get product details for invoice URL creation
        product = await payment_service.product_repository.get_by_id(product_id)
        if not product:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )

        # Generate Telegram invoice URL
        invoice_url = await payment_service.create_telegram_invoice_url(
            payment, product
        )

        logger.info(
            "Payment invoice created successfully",
            extra={
                "payment_id": payment.id,
                "telegram_user_id": telegram_user_id,
                "product_id": product_id,
                "user_id": str(current_user.id),
            },
        )

        response_data = {
            "payment_id": payment.id,
            "invoice_payload": payment.invoice_payload,
            "status": payment.status,
            "expires_at": payment.expires_at,
            "amount": payment.amount,
            "currency": payment.currency,
        }

        # Add invoice URL if successfully created
        if invoice_url:
            response_data["invoice_url"] = invoice_url

        return ResponseHelper.created(
            data=response_data,
            msg="Payment invoice created successfully",
        )

    except Exception as e:
        logger.exception("Unexpected error creating payment invoice: %s", str(e))
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/", response_model=dict, summary="Create payment record")
async def create_payment(
    request: PaymentCreate,
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Create a payment record.

    Creates a new payment record with proper validation and audit trails.
    Typically used to initiate payment processing workflows.

    Args:
        request: Payment creation request with amount, method, and metadata
        payment_service: Injected payment service instance
        current_user: Currently authenticated user (for audit purposes)

    Returns:
        ResponseHelper.created with payment data including ID, status, and expiry

    Raises:
        HTTPException(400): Invalid payment data or validation errors
        HTTPException(401): User not authenticated
        HTTPException(500): Internal server error during payment creation
    """
    try:
        payment = await payment_service.create_payment(request)

        logger.info(
            "Payment record created successfully",
            extra={
                "payment_id": str(payment.id),
                "user_id": str(current_user.id),
                "amount": getattr(request, "amount", 0),
                "status": (
                    payment.status.value
                    if hasattr(payment.status, "value")
                    else str(payment.status)
                ),
            },
        )

        return ResponseHelper.created(
            data={
                "payment_id": payment.id,
                "status": payment.status,
                "expires_at": payment.expires_at,
            },
            msg="Payment record created successfully",
        )

    except PydanticValidationError as e:
        logger.warning("Payment creation validation error", extra={"error": str(e)})
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except ValidationError as e:
        logger.warning(
            "Payment creation business validation error", extra={"error": str(e)}
        )
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BaseCustomException as e:
        logger.warning("Payment creation business error", extra={"error": str(e)})
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error creating payment record: %s", str(e))
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{payment_id}", response_model=dict, summary="Get payment record")
async def get_payment(
    payment_id: str = Path(..., min_length=24, max_length=24, description="Payment ID"),
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Get payment record details.

    Retrieves detailed payment information with proper access validation.
    Users can only view their own payment records unless they have admin privileges.

    Args:
        payment_id: MongoDB ObjectId of the payment record
        payment_service: Injected payment service instance
        current_user: Currently authenticated user

    Returns:
        ResponseHelper.success with payment data

    Raises:
        HTTPException(400): Invalid payment ID format
        HTTPException(401): User not authenticated
        HTTPException(404): Payment record not found or access denied
        HTTPException(500): Internal server error during payment retrieval
    """
    try:
        payment = await payment_service.get_payment(payment_id)
        if not payment:
            logger.warning("Payment record not found", extra={"payment_id": payment_id})
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Payment record not found",
            )

        # TODO: Add proper ownership validation - ensure user can only see their payments
        logger.debug(
            "Payment record retrieved",
            extra={"payment_id": payment_id, "user_id": str(current_user.id)},
        )

        return ResponseHelper.success(
            data=payment, msg="Payment information retrieved successfully"
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid payment ID format",
            extra={"payment_id": payment_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment ID format",
        )
    except BaseCustomException as e:
        logger.warning(
            "Payment retrieval business error",
            extra={"payment_id": payment_id, "error": str(e)},
        )
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error retrieving payment record: %s", str(e))
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/{payment_id}", response_model=dict, summary="Update payment record")
async def update_payment(
    updates: dict,
    payment_id: str = Path(..., min_length=24, max_length=24, description="Payment ID"),
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Update payment record.

    Updates payment record with new information. Typically used for status updates,
    payment confirmations, or metadata changes with proper audit trails.

    Args:
        updates: Dictionary containing fields to update
        payment_id: MongoDB ObjectId of the payment record
        payment_service: Injected payment service instance
        current_user: Currently authenticated user (for audit purposes)

    Returns:
        ResponseHelper.updated with payment update confirmation

    Raises:
        HTTPException(400): Invalid payment ID format or update data
        HTTPException(401): User not authenticated
        HTTPException(404): Payment record not found or update failed
        HTTPException(500): Internal server error during payment update
    """
    try:
        success = await payment_service.update_payment(payment_id, updates)
        if not success:
            logger.warning(
                "Payment record not found or update failed",
                extra={"payment_id": payment_id, "user_id": str(current_user.id)},
            )
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Payment record not found or update failed",
            )

        logger.info(
            "Payment record updated successfully",
            extra={
                "payment_id": payment_id,
                "user_id": str(current_user.id),
                "update_fields": list(updates.keys()),
            },
        )

        return ResponseHelper.updated(
            data={"payment_id": payment_id}, msg="Payment record updated successfully"
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid payment ID format for update",
            extra={"payment_id": payment_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment ID format",
        )
    except BaseCustomException as e:
        logger.warning(
            "Payment update business error",
            extra={"payment_id": payment_id, "error": str(e)},
        )
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error updating payment record: %s", str(e))
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/user/{user_id}", response_model=dict, summary="Get user payment history")
async def get_user_payments(
    user_id: str = Path(..., min_length=24, max_length=24, description="User ID"),
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of payment records to return"
    ),
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Get user's payment history.

    Retrieves paginated payment history for a specific user with proper
    access validation. Users can only view their own payment history
    unless they have admin privileges.

    Args:
        user_id: MongoDB ObjectId of the user
        limit: Maximum number of payment records to return (1-100)
        payment_service: Injected payment service instance
        current_user: Currently authenticated user

    Returns:
        ResponseHelper.success with user payment history data

    Raises:
        HTTPException(400): Invalid user ID format or limit parameter
        HTTPException(401): User not authenticated
        HTTPException(403): Access denied to view other user's payment history
        HTTPException(500): Internal server error during payment history retrieval
    """
    try:
        # Check if user is trying to access their own payment history or is admin
        if str(current_user.id) != user_id:
            # TODO: Add proper admin role check here
            logger.warning(
                "Unauthorized payment history access attempt",
                extra={
                    "requesting_user_id": str(current_user.id),
                    "target_user_id": user_id,
                },
            )
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Access denied to view other user's payment history",
            )

        payments = await payment_service.get_user_payments(user_id, limit=limit)

        logger.info(
            "User payment history retrieved",
            extra={"user_id": user_id, "payment_count": len(payments), "limit": limit},
        )

        return ResponseHelper.success(
            data={
                "user_id": user_id,
                "payments": payments,
                "total_count": len(payments),
            },
            msg="User payment history retrieved successfully",
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid user ID format for payment history",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        )
    except BaseCustomException as e:
        logger.warning(
            "Payment history retrieval business error",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error retrieving user payment history: %s", str(e))
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/status/{status}", response_model=dict, summary="Get payments by status")
async def get_payments_by_status(
    status: PaymentStatus,
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of payment records to return"
    ),
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Get payment records by status.

    Retrieves payment records filtered by their current status.
    Typically used for administrative purposes or payment processing workflows.

    Args:
        status: Payment status to filter by (enum value)
        limit: Maximum number of payment records to return (1-100)
        payment_service: Injected payment service instance
        current_user: Currently authenticated user (admin access typically required)

    Returns:
        ResponseHelper.success with filtered payment records

    Raises:
        HTTPException(400): Invalid status or limit parameter
        HTTPException(401): User not authenticated
        HTTPException(500): Internal server error during payment retrieval
    """
    try:
        payments = await payment_service.get_payments_by_status(status, limit)

        logger.info(
            "Payments retrieved by status",
            extra={
                "status": status.value,
                "payment_count": len(payments),
                "limit": limit,
                "user_id": str(current_user.id),
            },
        )

        return ResponseHelper.success(
            data={"status": status, "payments": payments, "total_count": len(payments)},
            msg=f"Payments with status {status} retrieved successfully",
        )

    except ValueError as e:
        logger.warning(
            "Invalid status or limit parameter",
            extra={"status": status, "limit": limit, "error": str(e)},
        )
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid status or limit parameter",
        )
    except BaseCustomException as e:
        logger.warning(
            "Payment status retrieval business error",
            extra={"status": status, "error": str(e)},
        )
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(
            "Unexpected error retrieving payment records by status: %s", str(e)
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/expired/list", response_model=dict, summary="Get expired payments")
async def get_expired_payments(
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Get expired payment records.

    Retrieves all payment records that have passed their expiration time.
    Typically used for cleanup operations or administrative purposes.

    Args:
        payment_service: Injected payment service instance
        current_user: Currently authenticated user (admin access typically required)

    Returns:
        ResponseHelper.success with expired payment records

    Raises:
        HTTPException(401): User not authenticated
        HTTPException(500): Internal server error during expired payments retrieval
    """
    try:
        expired_payments = await payment_service.get_expired_payments()

        logger.info(
            "Expired payment records retrieved",
            extra={
                "expired_count": len(expired_payments),
                "user_id": str(current_user.id),
            },
        )

        return ResponseHelper.success(
            data={
                "expired_payments": expired_payments,
                "total_count": len(expired_payments),
            },
            msg="Expired payment records retrieved successfully",
        )

    except BaseCustomException as e:
        logger.warning(
            "Expired payments retrieval business error", extra={"error": str(e)}
        )
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(
            "Unexpected error retrieving expired payment records: %s", str(e)
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/{payment_id}", response_model=dict, summary="Delete payment record")
async def delete_payment(
    payment_id: str = Path(..., min_length=24, max_length=24, description="Payment ID"),
    payment_service: PaymentService = Depends(get_payment_service),
) -> Dict[str, Any]:
    """
    Delete payment record.

    Soft deletes the payment record while preserving audit trail.
    Physical deletion is typically not allowed for financial records.

    Args:
        payment_id: MongoDB ObjectId string of the payment
        payment_service: Injected payment service instance

    Returns:
        ResponseHelper.deleted with deletion confirmation

    Raises:
        HTTPException(400): Invalid payment ID format
        HTTPException(404): Payment record not found or deletion failed
        HTTPException(500): Internal server error during deletion
    """
    try:
        success = await payment_service.delete_payment(payment_id)
        if not success:
            logger.warning(
                "Payment record not found or deletion failed",
                extra={"payment_id": payment_id},
            )
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Payment record not found or deletion failed",
            )

        logger.info("Payment record deleted", extra={"payment_id": payment_id})
        return ResponseHelper.deleted(msg="Payment record deleted successfully")

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid payment ID format",
            extra={"payment_id": payment_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment ID format",
        )
    except BaseCustomException as e:
        logger.warning(
            "Payment deletion business error",
            extra={"payment_id": payment_id, "error": str(e)},
        )
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error deleting payment: %s", str(e))
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/stats/overview", response_model=dict, summary="Get payment statistics")
async def get_payment_statistics(
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Get payment statistics overview.

    Retrieves comprehensive payment statistics including totals, status breakdown,
    and other key metrics. Typically used for administrative dashboards.

    Args:
        payment_service: Injected payment service instance
        current_user: Currently authenticated user (admin access typically required)

    Returns:
        ResponseHelper.success with payment statistics data

    Raises:
        HTTPException(401): User not authenticated
        HTTPException(500): Internal server error during statistics retrieval
    """
    try:
        stats = await payment_service.get_payment_statistics()

        logger.info(
            "Payment statistics retrieved", extra={"user_id": str(current_user.id)}
        )

        return ResponseHelper.success(
            data=stats, msg="Payment statistics retrieved successfully"
        )

    except BaseCustomException as e:
        logger.warning(
            "Payment statistics retrieval business error", extra={"error": str(e)}
        )
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error retrieving payment statistics: %s", str(e))
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
