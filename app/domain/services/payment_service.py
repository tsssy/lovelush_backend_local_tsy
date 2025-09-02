"""Payment service for managing payments and transactions."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.models.credits import TransactionReason
from app.domain.models.payment import (
    Payment,
    PaymentCreate,
    PaymentStatus,
    PaymentUpdate,
    Product,
    ProductUpdate,
)
from app.domain.services.credits_service import CreditsService
from app.domain.services.user_service import UserService
from app.infrastructure.database.repositories.payment_repository import (
    PaymentRepository,
)
from app.infrastructure.database.repositories.product_repository import (
    ProductRepository,
)
from app.interfaces.telegram.common.types import TelegramLabeledPrice
from app.interfaces.telegram.services.sdk_service import TelegramSDKService

logger = get_logger(__name__)


class PaymentService:
    """Service for handling payment business logic."""

    def __init__(
        self,
        payment_repository: PaymentRepository,
        product_repository: ProductRepository,
        credits_service: CreditsService,
        user_service: UserService,
        telegram_sdk_service: Optional[TelegramSDKService] = None,
    ) -> None:
        """Initialize service with required dependencies."""
        self.payment_repository = payment_repository
        self.product_repository = product_repository
        self.credits_service = credits_service
        self.user_service = user_service
        self.telegram_sdk_service = telegram_sdk_service

    async def create_payment(self, request: PaymentCreate) -> Payment:
        """Create new payment with business validation."""
        # Validate product exists and is purchasable
        product = await self.product_repository.get_by_id(request.product_id)
        if not product:
            raise NotFoundError(f"Product {request.product_id} not found")

        if not product.is_available:
            raise ValidationError(
                f"Product {request.product_id} is not available for purchase"
            )

        # Get MongoDB user ID from telegram_user_id
        user = await self.user_service.get_user_by_telegram_id(request.telegram_user_id)
        user_id = str(user.id) if user else None

        # Create payment request with all required fields
        payment_create = PaymentCreate(
            user_id=user_id,
            telegram_user_id=request.telegram_user_id,
            product_id=request.product_id,
            amount=product.price,
            currency=product.currency,
            invoice_payload=request.invoice_payload or str(uuid.uuid4()),
            expires_at=request.expires_at
            or datetime.now(timezone.utc) + timedelta(hours=1),
        )

        # Save payment record (repository handles ID generation)
        created_payment = await self.payment_repository.create(payment_create)

        # Update the invoice payload to use the payment ID for easier lookup
        # This ensures the invoice payload matches the payment ID
        if created_payment.invoice_payload != str(created_payment.id):
            await self.update_payment(
                str(created_payment.id), {"invoice_payload": str(created_payment.id)}
            )
            # Update the in-memory object to reflect the change
            created_payment.invoice_payload = str(created_payment.id)

        return created_payment

    async def get_payment(self, payment_id: str) -> Payment:
        """Get payment record by ID."""
        payment = await self.payment_repository.get_by_id(payment_id)
        if not payment:
            raise NotFoundError(f"Payment record {payment_id} not found")
        return payment

    async def process_pre_checkout(self, payment_id: str) -> Payment:
        """Process pre-checkout validation."""
        payment = await self.get_payment(payment_id)

        # Validate payment status
        if payment.status != PaymentStatus.PENDING:
            raise ValidationError(f"Payment {payment_id} status is incorrect")

        # Check if expired
        if payment.is_expired():
            payment.mark_expired()
            update_data = PaymentUpdate(status=payment.status)  # type: ignore  # type: ignore
            await self.payment_repository.update(str(payment.id), update_data)
            raise ValidationError("Payment expired")

        # Validate product is still purchasable
        product = await self.product_repository.get_by_id(payment.product_id)
        if not product or not product.is_available:
            payment.mark_failed("Product not available for purchase")
            update_data = PaymentUpdate(status=payment.status)  # type: ignore  # type: ignore
            await self.payment_repository.update(str(payment.id), update_data)
            raise ValidationError("Product not available for purchase")

        # Update payment timestamp (no PRE_CHECKOUT status in model)
        payment.updated_at = datetime.now(timezone.utc)

        update_data = PaymentUpdate(status=payment.status)  # type: ignore  # type: ignore
        await self.payment_repository.update(str(payment.id), update_data)

        return payment

    async def complete_payment(
        self, payment_id: str, charge_id: str, provider_charge_id: str
    ) -> Payment:
        """Complete payment and process rewards."""
        payment = await self.get_payment(payment_id)

        # Validate payment can be completed
        if payment.status not in [PaymentStatus.PENDING]:
            raise ValidationError(
                f"Payment {payment_id} cannot be completed from status {payment.status}"
            )

        # Get product information for reward processing
        product = await self.product_repository.get_by_id(payment.product_id)
        if not product:
            raise NotFoundError(f"Product {payment.product_id} not found")

        # Mark payment as completed
        payment.mark_payment_completed(charge_id, provider_charge_id)

        # Update payment record
        update_data = PaymentUpdate(  # type: ignore
            status=payment.status,
            telegram_payment_charge_id=payment.telegram_payment_charge_id,
            provider_payment_charge_id=payment.telegram_provider_payment_charge_id,
            completed_at=payment.completed_at,
        )
        await self.payment_repository.update(str(payment.id), update_data)

        # Process product rewards
        await self._process_payment_rewards(payment, product)

        # Consume product stock (if not unlimited)
        if product.stock_limit is not None:
            product.consume_stock()

            # Update product stock with only the stock_limit field
            product_update = ProductUpdate(stock_limit=product.stock_limit)  # type: ignore
            await self.product_repository.update(str(product.id), product_update)

        return payment

    async def fail_payment(self, payment_id: str, error_message: str) -> Payment:
        """Mark payment as failed."""
        payment = await self.get_payment(payment_id)
        payment.mark_failed(error_message)

        update_data = PaymentUpdate(status=payment.status)  # type: ignore
        await self.payment_repository.update(str(payment.id), update_data)

        return payment

    async def retry_payment(self, payment_id: str) -> Payment:
        """Retry failed payment."""
        payment = await self.get_payment(payment_id)

        if not payment.can_retry():
            raise ValidationError("Payment cannot be retried")

        payment.increment_retry()
        payment.status = PaymentStatus.PENDING
        payment.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        update_data = PaymentUpdate(status=payment.status)  # type: ignore
        await self.payment_repository.update(str(payment.id), update_data)

        return payment

    async def get_user_payments(
        self,
        user_id: str,
        status: Optional[PaymentStatus] = None,
        limit: int = 10,
    ) -> List[Payment]:
        """Get user's payment history by MongoDB user ID."""
        if status:
            # If status filter is needed, use find_by_criteria which can handle complex queries
            criteria = {"user_id": user_id, "status": status}
            return await self.payment_repository.find_by_criteria(criteria, limit)
        else:
            # Use the dedicated method for better performance
            return await self.payment_repository.find_by_user_id(user_id, limit)

    async def get_user_payments_by_telegram_id(
        self,
        telegram_user_id: str,
        status: Optional[PaymentStatus] = None,
        limit: int = 10,
    ) -> List[Payment]:
        """Get user's payment history by telegram user ID."""
        if status:
            # If status filter is needed, use find_by_criteria which can handle complex queries
            criteria = {"telegram_user_id": telegram_user_id, "status": status}
            return await self.payment_repository.find_by_criteria(criteria, limit)
        else:
            # Use the dedicated method for better performance
            return await self.payment_repository.find_by_telegram_user_id(
                telegram_user_id, limit
            )

    async def cleanup_expired_payments(self) -> int:
        """Clean up expired pending payment records."""
        expired_payments = await self.payment_repository.find_expired_payments()
        count = 0

        for payment in expired_payments:
            if payment.status == PaymentStatus.PENDING:
                payment.mark_failed("Payment expired")
                update_data = PaymentUpdate(status=payment.status)  # type: ignore
                await self.payment_repository.update(str(payment.id), update_data)
                count += 1

        return count

    async def _process_payment_rewards(
        self, payment: Payment, product: Product
    ) -> None:
        """Process rewards for completed payment (credits, membership, etc)."""
        # Get user by telegram_user_id to get the MongoDB user.id
        user = await self.user_service.get_user_by_telegram_id(payment.telegram_user_id)

        if not user:
            logger.error(
                f"User not found for telegram_user_id: {payment.telegram_user_id}"
            )
            return

        # Award credits using the MongoDB user.id
        if product.credits > 0:
            success = await self.credits_service.add_credits(
                user_id=str(user.id),  # Use MongoDB user.id instead of telegram_user_id
                amount=product.credits,
                reason=TransactionReason.PURCHASE,
                description=f"Credits from purchasing {product.title}",
            )

            if success:
                logger.info(
                    f"Awarded {product.credits} credits to user {user.id} (telegram: {payment.telegram_user_id}), payment ID: {payment.id}"
                )
            else:
                logger.error(
                    f"Failed to award {product.credits} credits to user {user.id} (telegram: {payment.telegram_user_id}), payment ID: {payment.id}"
                )

        # Handle premium activation
        if product.category == "subscription":
            duration_days = product.meta.get("premium_days", 30) if product.meta else 30
            # TODO: Implement premium activation when user service is integrated
            logger.info(
                f"TODO: Activate {duration_days} days premium for user {user.id} (telegram: {payment.telegram_user_id})"
            )

    async def get_payment_by_invoice_payload(self, payload: str) -> Optional[Payment]:
        """Find payment record by invoice payload."""
        # First try to find by invoice payload
        payment = await self.payment_repository.find_by_invoice_payload(payload)
        if payment:
            return payment

        # If not found and payload looks like a payment ID, try to find by ID directly
        # This handles cases where the payload is the payment ID
        if "_" in payload and len(payload) > 20:  # Business ID format check
            payment = await self.payment_repository.find_by_id(payload)
            if payment:
                return payment

        return None

    def validate_payment_amount(self, payment: Payment, expected_amount: int) -> bool:
        """Validate payment amount matches expected amount."""
        return payment.amount == expected_amount

    def calculate_payment_fees(self, amount: int, currency: str) -> int:
        """Calculate payment processing fees."""
        # Telegram Stars payments usually have no fees
        if currency == "XTR":
            return 0

        # Fee calculation for other currencies
        return int(amount * 0.029)  # 2.9% fee example

    async def get_payments_by_status(
        self, status: PaymentStatus, limit: int = 50
    ) -> List[Payment]:
        """Get payment records by status."""
        return await self.payment_repository.find_by_status(status, limit)

    async def get_expired_payments(self) -> List[Payment]:
        """Get expired payment records."""
        return await self.payment_repository.find_expired_payments()

    async def get_payment_statistics(self) -> Dict[str, Any]:
        """Get payment statistics."""
        try:
            # Get payment counts by status
            pending_count = len(
                await self.payment_repository.find_by_status(
                    PaymentStatus.PENDING, 1000
                )
            )
            completed_count = len(
                await self.payment_repository.find_by_status(
                    PaymentStatus.COMPLETED, 1000
                )
            )
            failed_count = len(
                await self.payment_repository.find_by_status(PaymentStatus.FAILED, 1000)
            )
            expired_count = len(await self.payment_repository.find_expired_payments())

            # Calculate total payment amount
            completed_payments = await self.payment_repository.find_by_status(
                PaymentStatus.COMPLETED, 1000
            )
            total_amount = sum(payment.amount for payment in completed_payments)

            return {
                "total_payments": pending_count + completed_count + failed_count,
                "pending_count": pending_count,
                "completed_count": completed_count,
                "failed_count": failed_count,
                "expired_count": expired_count,
                "total_amount": total_amount,
                "currency": "XTR",
            }
        except Exception as e:
            logger.error(f"Failed to get payment statistics: {e}")
            raise

    async def update_payment(self, payment_id: str, updates: Dict[str, Any]) -> bool:
        """Update payment record."""
        try:
            # Get payment record
            payment = await self.get_payment(payment_id)
            if not payment:
                return False

            # Apply updates
            for field, value in updates.items():
                if hasattr(payment, field):
                    setattr(payment, field, value)

            # Update timestamp
            payment.updated_at = datetime.now(timezone.utc)

            # Save changes
            # Convert updates dict to PaymentUpdate object
            update_data = PaymentUpdate(**updates)  # type: ignore
            await self.payment_repository.update(payment_id, update_data)
            return True

        except Exception as e:
            logger.error(f"Failed to update payment record: {e}")
            return False

    async def delete_payment(self, payment_id: str) -> bool:
        """Delete payment record."""
        try:
            # Get payment record
            payment = await self.get_payment(payment_id)
            if not payment:
                return False

            # Delete record
            await self.payment_repository.delete(payment_id)
            return True

        except Exception as e:
            logger.error(f"Failed to delete payment record: {e}")
            return False

    async def create_telegram_invoice_url(
        self, payment: Payment, product: Product
    ) -> Optional[str]:
        """Create Telegram invoice URL for payment."""
        if not self.telegram_sdk_service:
            logger.warning("Telegram SDK service not available")
            return None

        try:
            # Create price list in Telegram format
            prices = [TelegramLabeledPrice(label=product.title, amount=product.price)]

            # Get the actual currency value being passed
            currency_value = (
                product.currency.value
                if hasattr(product.currency, "value")
                else str(product.currency)
            )

            # For Telegram Stars (XTR) payments, provider_token should be completely omitted
            if currency_value == "XTR":
                response = await self.telegram_sdk_service.create_invoice_link(
                    title=product.title,
                    description=product.description or f"Purchase {product.title}",
                    payload=payment.invoice_payload,
                    currency=currency_value,
                    prices=prices,
                    # provider_token is intentionally omitted for XTR payments
                )
            else:
                # For other currencies, include provider_token (would need proper token)
                response = await self.telegram_sdk_service.create_invoice_link(
                    title=product.title,
                    description=product.description or f"Purchase {product.title}",
                    payload=payment.invoice_payload,
                    currency=currency_value,
                    prices=prices,
                    provider_token="",  # Would need proper provider token for non-XTR currencies
                )

            if response.success and response.data:
                return response.data.get("invoice_url")
            else:
                logger.error(
                    f"Failed to create invoice URL for payment {payment.id}: {response.error_description or 'Unknown error'}"
                )
                return None

        except Exception as e:
            logger.error(
                f"Error creating Telegram invoice URL for payment {payment.id}: {e}"
            )
            return None
