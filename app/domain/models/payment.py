"""Payment and Product domain models following clean architecture patterns."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import Field

from app.core.logging import get_logger

from .common import (
    AuditMixin,
    CompletionMixin,
    CompletionUpdateMixin,
    ExpiryUpdateMixin,
    FailureUpdateMixin,
    PyObjectId,
    RequiredExpiryMixin,
    Schema,
    TimestampMixin,
)

logger = get_logger(__name__)


class Currency(str, Enum):
    """Supported currency types."""

    TELEGRAM_STARS = "XTR"  # Telegram Stars
    USD = "USD"  # US Dollar
    CNY = "CNY"  # Chinese Yuan


class PaymentStatus(str, Enum):
    """Payment status enumeration."""

    PENDING = "pending"  # Awaiting payment
    COMPLETED = "completed"  # Payment completed
    FAILED = "failed"  # Payment failed
    EXPIRED = "expired"  # Payment expired


class ProductCategory(str, Enum):
    """Product category enumeration."""

    CREDITS = "credits"  # Credit packages
    SUBSCRIPTION = "subscription"  # Subscription plans
    FEATURE = "feature"  # Feature unlocks


# Shared fields for Product schemas
class ProductBase(Schema):
    """Base product fields shared across different schemas."""

    title: str = Field(..., min_length=1, max_length=200, description="Product title")
    description: str = Field(
        ..., min_length=1, max_length=1000, description="Product description"
    )
    price: int = Field(
        ..., ge=0, description="Product price in smallest currency unit (cents)"
    )
    currency: Currency = Field(..., description="Currency type")
    credits: int = Field(..., ge=0, description="Number of credits provided")
    category: ProductCategory = Field(..., description="Product category")
    photo_url: Optional[str] = Field(None, description="Product image URL")
    feature_text: Optional[str] = Field(
        None, max_length=500, description="Product feature description"
    )
    show_feature: bool = Field(default=False, description="Whether to display features")
    sequence: int = Field(
        default=0,
        ge=0,
        description="Display order sequence (lower numbers appear first)",
    )
    stock_limit: Optional[int] = Field(
        None, ge=0, description="Stock limit, None for unlimited"
    )
    meta: Optional[Dict[str, Any]] = Field(None, description="Product metadata")
    is_active: bool = Field(default=True, description="Whether product is active")


# Shared fields for Payment schemas
class PaymentBase(Schema):
    """Base payment fields shared across different schemas."""

    user_id: Optional[str] = Field(None, description="MongoDB User ID")
    telegram_user_id: str = Field(..., description="Telegram user ID")
    product_id: str = Field(..., description="Reference to Product._id")
    amount: int = Field(
        ..., ge=0, description="Payment amount in smallest currency unit"
    )
    currency: Currency = Field(..., description="Currency type")
    status: PaymentStatus = Field(
        default=PaymentStatus.PENDING, description="Payment status"
    )
    invoice_payload: str = Field(..., description="Invoice payload")


# Schema for creating a product
class ProductCreate(ProductBase):
    """Schema for creating a new product."""

    pass


# Schema for updating a product (all fields optional)
class ProductUpdate(Schema):
    """Schema for updating a product."""

    title: Optional[str] = Field(
        None, min_length=1, max_length=200, description="Product title"
    )
    description: Optional[str] = Field(
        None, min_length=1, max_length=1000, description="Product description"
    )
    price: Optional[int] = Field(None, ge=0, description="Product price in cents")
    currency: Optional[Currency] = Field(None, description="Currency type")
    credits: Optional[int] = Field(None, ge=0, description="Number of credits")
    category: Optional[ProductCategory] = Field(None, description="Product category")
    photo_url: Optional[str] = Field(None, description="Product image URL")
    feature_text: Optional[str] = Field(
        None, max_length=500, description="Product feature text"
    )
    show_feature: Optional[bool] = Field(None, description="Whether to show features")
    sequence: Optional[int] = Field(None, ge=0, description="Display order sequence")
    stock_limit: Optional[int] = Field(None, ge=0, description="Stock limit")
    meta: Optional[Dict[str, Any]] = Field(None, description="Product metadata")
    is_active: Optional[bool] = Field(None, description="Whether product is active")

    @classmethod
    def from_product(cls, product: "ProductInDB", **overrides) -> "ProductUpdate":
        """Create ProductUpdate from Product model with optional field overrides."""
        product_data = {
            "title": product.title,
            "description": product.description,
            "price": product.price,
            "currency": product.currency,
            "credits": product.credits,
            "category": product.category,
            "photo_url": product.photo_url,
            "feature_text": product.feature_text,
            "show_feature": product.show_feature,
            "sequence": product.sequence,
            "stock_limit": product.stock_limit,
            "meta": product.meta,
            "is_active": product.is_active,
        }
        product_data.update(overrides)
        return cls(**product_data)


# Schema for creating a payment
class PaymentCreate(PaymentBase, RequiredExpiryMixin):
    """Schema for creating a new payment."""

    pass


# Schema for updating a payment (all fields optional)
class PaymentUpdate(
    CompletionUpdateMixin, FailureUpdateMixin, ExpiryUpdateMixin, Schema
):
    """Schema for updating a payment."""

    status: Optional[PaymentStatus] = Field(None, description="Payment status")
    telegram_payment_charge_id: Optional[str] = Field(
        None, description="Telegram charge ID"
    )
    provider_payment_charge_id: Optional[str] = Field(
        None, description="Provider charge ID"
    )
    retry_count: Optional[int] = Field(
        None, ge=0, description="Number of retry attempts"
    )


# Schema for API responses
class ProductResponse(ProductBase, AuditMixin):
    """Schema for product API responses."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    is_available: bool = Field(
        ..., description="Whether product is available for purchase"
    )


class PaymentResponse(PaymentBase, AuditMixin, RequiredExpiryMixin, CompletionMixin):
    """Schema for payment API responses."""

    id: str = Field(..., alias="_id", description="Payment ID")
    telegram_payment_charge_id: Optional[str] = Field(
        None, description="Telegram payment charge ID"
    )
    telegram_provider_payment_charge_id: Optional[str] = Field(
        None, description="Telegram provider payment charge ID"
    )
    retry_count: int = Field(default=0, ge=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")


# Internal schemas (for DB storage)
class ProductInDB(ProductBase, AuditMixin):
    """Internal schema for product database storage."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    @property
    def is_available(self) -> bool:
        """Check if product is available for purchase."""
        return self.is_active and (self.stock_limit is None or self.stock_limit > 0)

    def consume_stock(self, quantity: int = 1) -> bool:
        """Consume stock quantity.

        Args:
            quantity: Amount to consume

        Returns:
            True if stock was consumed, False if insufficient stock
        """
        if self.stock_limit is None:
            return True  # Unlimited supply

        if self.stock_limit >= quantity:
            self.stock_limit -= quantity
            return True
        return False


class PaymentInDB(PaymentBase, AuditMixin, RequiredExpiryMixin, CompletionMixin):
    """Internal schema for payment database storage."""

    id: str = Field(
        ..., alias="_id", description="Payment ID (can be ObjectId or business ID)"
    )
    telegram_payment_charge_id: Optional[str] = Field(
        None, description="Telegram payment charge ID"
    )
    telegram_provider_payment_charge_id: Optional[str] = Field(
        None, description="Telegram provider payment charge ID"
    )
    retry_count: int = Field(default=0, ge=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")

    def mark_payment_completed(
        self, telegram_payment_charge_id: str, telegram_provider_payment_charge_id: str
    ) -> None:
        """Mark payment as completed with Telegram details.

        Args:
            telegram_payment_charge_id: Telegram payment charge ID
            telegram_provider_payment_charge_id: Provider payment charge ID
        """
        self.status = PaymentStatus.COMPLETED
        self.telegram_payment_charge_id = telegram_payment_charge_id
        self.telegram_provider_payment_charge_id = telegram_provider_payment_charge_id
        # Use the mixin's mark_completed method for timestamp consistency
        super().mark_completed()
        self.updated_at = datetime.now(timezone.utc)

    def mark_failed(self, reason: str = "Payment failed") -> None:
        """Mark payment as failed.

        Args:
            reason: Failure reason (for logging purposes)
        """
        logger.info(f"Marking payment as failed: {reason}")
        self.status = PaymentStatus.FAILED
        self.updated_at = datetime.now(timezone.utc)

    def mark_expired(self) -> None:
        """Mark payment as expired."""
        self.status = PaymentStatus.EXPIRED
        self.updated_at = datetime.now(timezone.utc)

    def can_retry(self) -> bool:
        """Check if payment can be retried."""
        return (
            self.status == PaymentStatus.FAILED and self.retry_count < self.max_retries
        )

    def increment_retry(self) -> None:
        """Increment retry count."""
        self.retry_count += 1
        self.updated_at = datetime.now(timezone.utc)


# Additional request schemas for specific operations
class ProductSortRequest(Schema):
    """Request model for updating product display order."""

    product_sequences: list[dict[str, Any]] = Field(
        ...,
        description="List of product ID and sequence pairs",
        examples=[
            {"product_id": "64a1b2c3d4e5f6789a0b1c2d", "sequence": 1},
            {"product_id": "64a1b2c3d4e5f6789a0b1c2e", "sequence": 2},
        ],
    )

    def validate_sequences(self) -> bool:
        """Validate that all entries have required fields and valid sequences."""
        for item in self.product_sequences:
            if "product_id" not in item or "sequence" not in item:
                return False
            if not isinstance(item["sequence"], int) or item["sequence"] < 0:
                return False
        return True


# Legacy Response Models (for specific use cases)
class PaymentStatusResponse(
    RequiredExpiryMixin, CompletionMixin, TimestampMixin, Schema
):
    """Response model for payment status."""

    payment_id: str = Field(..., description="Payment ID")
    status: PaymentStatus = Field(..., description="Payment status")
    amount: int = Field(..., description="Payment amount")
    currency: Currency = Field(..., description="Currency type")


class ProductSortResponse(Schema):
    """Response model for product sorting operations."""

    updated_count: int = Field(..., description="Number of products updated")
    updated_products: list[dict[str, Any]] = Field(
        ..., description="List of updated product IDs and their new sequences"
    )


# Convenience aliases for the main domain models (backwards compatibility)
Product = ProductInDB
Payment = PaymentInDB
