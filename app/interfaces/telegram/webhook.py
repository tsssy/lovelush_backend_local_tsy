"""Telegram webhook handlers and bot management API endpoints.

Provides endpoints for handling Telegram bot webhooks, managing webhook configuration,
and retrieving bot information with proper security and error handling.
"""

from typing import Any, Dict, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import JSONResponse

from app.core.config.settings import settings
from app.core.dependencies import get_payment_service
from app.core.logging import get_logger
from app.core.responses import ResponseHelper
from app.core.utils.datetime_utils import safe_isoformat
from app.domain.models.user import User
from app.domain.services.payment_service import PaymentService
from app.infrastructure.security.dependencies import get_current_active_user
from app.integrations.pusher.client import pusher_client
from app.interfaces.telegram.common.types import TelegramMessage, TelegramUpdate
from app.interfaces.telegram.handlers import MessageHandler as TelegramMessageHandler
from app.interfaces.telegram.services.sdk_service import telegram_sdk_service

router = APIRouter(prefix="/telegram", tags=["Telegram"])
logger = get_logger(__name__)


@router.post("/webhook", summary="Handle Telegram webhook updates")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
) -> JSONResponse:
    """
    Handle Telegram webhook updates.

    Processes incoming webhook updates from Telegram Bot API with proper
    authentication and validation. Updates are processed asynchronously
    in the background to ensure quick response times.

    Args:
        request: FastAPI request object containing webhook payload
        background_tasks: FastAPI background tasks for async processing
        x_telegram_bot_api_secret_token: Optional webhook secret token header

    Returns:
        JSONResponse with processing status

    Raises:
        HTTPException(400): Invalid request format or processing error
        HTTPException(403): Missing or invalid secret token
        HTTPException(422): Invalid webhook payload format
    """
    try:
        # Verify secret token if configured
        if settings.telegram_webhook_secret:
            if not x_telegram_bot_api_secret_token:
                logger.warning("Telegram webhook missing secret token")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Missing secret token"
                )

            if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
                logger.warning("Telegram webhook invalid secret token")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret token"
                )

        # Parse update data
        body = await request.json()
        logger.info(
            f"Telegram webhook update received: {body}",
            extra={
                "update_id": body.get("update_id"),
                "message_present": "message" in body,
                "callback_query_present": "callback_query" in body,
            },
        )

        # Use SDK Update.de_json to parse the update
        update = TelegramUpdate.de_json(
            body, None
        )  # bot parameter not needed for parsing

        # Process update in background
        if update:
            background_tasks.add_task(process_telegram_update, update)
            logger.debug(
                "Telegram update queued for background processing",
                extra={"update_id": update.update_id},
            )
        else:
            logger.warning("Failed to parse Telegram update", extra={"body": body})

        return JSONResponse(content={"status": "ok"})

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning("Invalid JSON in Telegram webhook", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid JSON format",
        )
    except Exception as e:
        logger.exception("Unexpected error processing Telegram webhook: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook processing error"
        )


async def process_telegram_update(update: TelegramUpdate):
    """Process telegram update in background task."""
    try:
        handler = TelegramMessageHandler()

        logger.debug(
            "Processing Telegram update",
            extra={
                "update_id": update.update_id,
                "has_message": bool(update.message),
                "has_edited_message": bool(update.edited_message),
                "has_callback_query": bool(update.callback_query),
                "has_inline_query": bool(update.inline_query),
                "has_pre_checkout_query": bool(
                    getattr(update, "pre_checkout_query", None)
                ),
                "has_successful_payment": bool(
                    update.message
                    and getattr(update.message, "successful_payment", None)
                    if update.message
                    else False
                ),
            },
        )

        # Handle payment-related updates first
        if hasattr(update, "pre_checkout_query") and update.pre_checkout_query:
            # Get payment service instance via centralized dependencies
            payment_service = get_payment_service()
            await handle_pre_checkout_query(update.pre_checkout_query, payment_service)
            logger.debug(
                "Handled pre-checkout query update",
                extra={"update_id": update.update_id},
            )
            return

        if (
            update.message
            and hasattr(update.message, "successful_payment")
            and update.message.successful_payment
        ):
            await handle_successful_payment(update.message)
            logger.debug(
                "Handled successful payment update",
                extra={"update_id": update.update_id},
            )
            return

        # Handle other update types
        if update.message:
            await handler.handle_message(update.message)
            logger.debug(
                "Handled message update", extra={"update_id": update.update_id}
            )
        elif update.edited_message:
            await handler.handle_edited_message(update.edited_message)
            logger.debug(
                "Handled edited message update", extra={"update_id": update.update_id}
            )
        elif update.callback_query:
            await handler.handle_callback_query(update.callback_query)
            logger.debug(
                "Handled callback query update", extra={"update_id": update.update_id}
            )
        elif update.inline_query:
            await handler.handle_inline_query(update.inline_query)
            logger.debug(
                "Handled inline query update", extra={"update_id": update.update_id}
            )
        else:
            logger.info(
                "Unhandled update type",
                extra={
                    "update_id": update.update_id,
                    "update_type": type(update).__name__,
                },
            )

    except Exception as e:
        logger.exception(
            "Error processing Telegram update: %s",
            str(e),
            extra={"update_id": getattr(update, "update_id", None)},
        )


async def handle_pre_checkout_query(
    pre_checkout_query, payment_service: PaymentService
):
    """Handle Telegram pre-checkout query for payment validation."""
    try:
        logger.info(
            "Processing pre-checkout query",
            extra={
                "query_id": pre_checkout_query.id,
                "user_id": pre_checkout_query.from_user.id,
                "invoice_payload": pre_checkout_query.invoice_payload,
                "total_amount": pre_checkout_query.total_amount,
                "currency": pre_checkout_query.currency,
            },
        )

        # Find payment record by invoice payload
        payment = await payment_service.get_payment_by_invoice_payload(
            pre_checkout_query.invoice_payload
        )

        if not payment:
            logger.warning(
                "Payment not found for pre-checkout",
                extra={"invoice_payload": pre_checkout_query.invoice_payload},
            )
            # Answer pre-checkout query with error
            await telegram_sdk_service.answer_pre_checkout_query(
                pre_checkout_query.id,
                ok=False,
                error_message="Payment record not found",
            )
            return

        # Validate payment amount
        if not payment_service.validate_payment_amount(
            payment, pre_checkout_query.total_amount
        ):
            logger.warning(
                "Payment amount mismatch",
                extra={
                    "expected": payment.amount,
                    "received": pre_checkout_query.total_amount,
                    "payment_id": payment.id,
                },
            )
            await telegram_sdk_service.answer_pre_checkout_query(
                pre_checkout_query.id, ok=False, error_message="Payment amount mismatch"
            )
            return

        # Process pre-checkout validation
        try:
            await payment_service.process_pre_checkout(str(payment.id))

            # Answer pre-checkout query with success
            await telegram_sdk_service.answer_pre_checkout_query(
                pre_checkout_query.id, ok=True
            )

            logger.info(
                "Pre-checkout query approved",
                extra={"payment_id": payment.id, "query_id": pre_checkout_query.id},
            )

        except Exception as e:
            logger.error(f"Pre-checkout validation failed: {e}")
            await telegram_sdk_service.answer_pre_checkout_query(
                pre_checkout_query.id, ok=False, error_message=str(e)
            )

    except Exception as e:
        logger.exception(f"Error handling pre-checkout query: {e}")
        # Always try to answer the query to avoid user confusion
        try:
            await telegram_sdk_service.answer_pre_checkout_query(
                pre_checkout_query.id, ok=False, error_message="Internal server error"
            )
        except Exception:
            logger.exception("Failed to answer pre-checkout query")


async def handle_successful_payment(message: TelegramMessage):
    """Handle successful payment from Telegram."""
    try:
        successful_payment = message.successful_payment
        user_id = message.from_user.id if message.from_user else None

        if not successful_payment or not user_id:
            logger.error("Invalid successful payment data")
            return

        logger.info(
            "Processing successful payment",
            extra={
                "user_id": user_id,
                "invoice_payload": successful_payment.invoice_payload,
                "telegram_payment_charge_id": successful_payment.telegram_payment_charge_id,
                "provider_payment_charge_id": successful_payment.provider_payment_charge_id,
                "total_amount": successful_payment.total_amount,
                "currency": successful_payment.currency,
            },
        )

        # Get payment service instance via centralized dependencies
        payment_service = get_payment_service()

        # Find payment record by invoice payload
        payment = await payment_service.get_payment_by_invoice_payload(
            successful_payment.invoice_payload
        )

        if not payment:
            logger.error(
                "Payment not found for successful payment",
                extra={"invoice_payload": successful_payment.invoice_payload},
            )
            return

        # Complete the payment
        completed_payment = await payment_service.complete_payment(
            str(payment.id),
            successful_payment.telegram_payment_charge_id,
            successful_payment.provider_payment_charge_id,
        )

        logger.info(
            "Payment completed successfully",
            extra={
                "payment_id": completed_payment.id,
                "user_id": user_id,
                "amount": completed_payment.amount,
            },
        )

        # Send system message via Pusher
        await send_payment_success_notification(user_id, completed_payment)

    except Exception as e:
        logger.exception(f"Error handling successful payment: {e}")


async def send_payment_success_notification(user_id: int, payment) -> None:
    """Send payment success notification via Pusher."""
    try:
        # Create notification data
        notification_data = {
            "type": "payment_success",
            "message": f"Payment completed! You received {payment.amount} Telegram Stars worth of credits.",
            "payment_id": payment.id,
            "amount": payment.amount,
            "currency": payment.currency,
            "timestamp": (safe_isoformat(payment.completed_at)),
        }

        # Send to user's private channel
        channel = f"private-user-{user_id}"
        event = "payment.completed"

        pusher_client.trigger(channel, event, notification_data)

        logger.info(
            "Payment success notification sent",
            extra={
                "user_id": user_id,
                "payment_id": payment.id,
                "channel": channel,
                "event": event,
            },
        )

    except Exception as e:
        logger.exception(
            f"Failed to send payment success notification: {e}",
            extra={"user_id": user_id, "payment_id": payment.id},
        )


@router.get("/webhook/info", response_model=dict, summary="Get webhook information")
async def get_webhook_info(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Get current webhook information."""
    return ResponseHelper.success(
        data={"webhook_url": settings.telegram_webhook_url or "Not configured"},
        msg="Webhook info retrieved successfully",
    )


@router.post("/webhook/set", response_model=dict, summary="Set webhook URL")
async def set_webhook(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Set webhook URL for the bot."""
    try:
        if not settings.telegram_webhook_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Webhook URL not configured",
            )

        response = await telegram_sdk_service.set_webhook()
        if response.success:
            return ResponseHelper.success(
                data={"webhook_url": settings.telegram_webhook_url},
                msg="Webhook set successfully",
            )
        else:
            error_msg = response.error_description or "Failed to set webhook"
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error setting webhook: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/webhook", response_model=dict, summary="Delete webhook")
async def delete_webhook(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Delete webhook configuration."""
    try:
        response = await telegram_sdk_service.delete_webhook()
        if response.success:
            return ResponseHelper.success(msg="Webhook deleted successfully")
        else:
            error_msg = response.error_description or "Failed to delete webhook"
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error deleting webhook: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/me", response_model=dict, summary="Get bot information")
async def get_bot_info(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Get bot information."""
    try:
        response = await telegram_sdk_service.get_me()
        if response.success and response.data:
            return ResponseHelper.success(
                data={
                    "id": response.data.id,
                    "is_bot": response.data.is_bot,
                    "first_name": response.data.first_name,
                    "username": response.data.username,
                },
                msg="Bot info retrieved successfully",
            )
        else:
            error_msg = response.error_description or "Failed to get bot info"
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error getting bot info: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
