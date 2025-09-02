"""User Credits domain models following clean architecture patterns."""

from enum import Enum
from typing import Optional

from pydantic import Field

from .common import AuditMixin, PyObjectId, Schema


class TransactionType(str, Enum):
    """Credit transaction type enumeration."""

    CREDIT = "credit"  # Adding credits
    DEBIT = "debit"  # Using/spending credits
    REFUND = "refund"  # Refunding creditas


class TransactionReason(str, Enum):
    """Transaction reason enumeration."""

    INITIAL_GRANT = "initial_grant"  # Initial free credits
    PURCHASE = "purchase"  # User purchased credits
    MATCH_CONSUMPTION = "match_consumption"  # Used credits for new matches
    MESSAGE_CONSUMPTION = "message_consumption"  # Used credits for sending messages
    ADMIN_ADJUSTMENT = "admin_adjustment"  # Manual admin adjustment
    REFUND_CANCELLED_CHAT = "refund_cancelled_chat"  # Refund for cancelled chat


# Shared fields for UserCredits schemas
class UserCreditsBase(Schema):
    """Base user credits fields shared across different schemas."""

    user_id: str = Field(..., description="Reference to User._id")
    current_balance: int = Field(default=0, ge=0, description="Current credit balance")
    total_earned: int = Field(default=0, ge=0, description="Total credits earned")
    total_spent: int = Field(default=0, ge=0, description="Total credits spent")


# Shared fields for CreditTransaction schemas
class CreditTransactionBase(Schema):
    """Base credit transaction fields shared across different schemas."""

    user_id: str = Field(..., description="Reference to User._id")
    transaction_type: TransactionType = Field(..., description="Type of transaction")
    reason: TransactionReason = Field(..., description="Reason for transaction")
    amount: int = Field(
        ...,
        description="Transaction amount (positive for credits, negative for debits)",
    )
    balance_before: int = Field(..., ge=0, description="Balance before transaction")
    balance_after: int = Field(..., ge=0, description="Balance after transaction")
    reference_id: Optional[str] = Field(
        None, description="Reference to related entity (chatroom, purchase, etc.)"
    )
    reference_type: Optional[str] = Field(None, description="Type of referenced entity")
    description: Optional[str] = Field(
        None, max_length=500, description="Transaction description"
    )


# Schema for creating user credits account
class UserCreditsCreate(Schema):
    """Schema for creating user credits account."""

    user_id: str = Field(..., description="Reference to User._id")
    initial_balance: int = Field(default=0, ge=0, description="Initial credit balance")


# Schema for updating user credits (all fields optional)
class UserCreditsUpdate(Schema):
    """Schema for updating user credits."""

    current_balance: Optional[int] = Field(
        None, ge=0, description="Current credit balance"
    )
    total_earned: Optional[int] = Field(None, ge=0, description="Total credits earned")
    total_spent: Optional[int] = Field(None, ge=0, description="Total credits spent")


# Schema for creating credit transaction
class CreditTransactionCreate(CreditTransactionBase):
    """Schema for creating credit transaction."""

    pass


# Schema for API responses
class UserCreditsResponse(UserCreditsBase, AuditMixin):
    """Schema for user credits API responses."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")


class CreditTransactionResponse(CreditTransactionBase, AuditMixin):
    """Schema for credit transaction API responses."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")


# Internal schemas (for DB storage)
class UserCreditsInDB(UserCreditsBase, AuditMixin):
    """Internal schema for user credits database storage."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")


class CreditTransactionInDB(CreditTransactionBase, AuditMixin):
    """Internal schema for credit transaction database storage."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")


# Additional schemas for specific operations
class CreditAdjustment(Schema):
    """Schema for manual credit adjustment."""

    user_id: str = Field(..., description="Reference to User._id")
    amount: int = Field(
        ..., description="Amount to adjust (positive to add, negative to subtract)"
    )
    reason: TransactionReason = Field(..., description="Reason for adjustment")
    description: Optional[str] = Field(
        None, max_length=500, description="Admin description"
    )


# Convenience aliases for the main domain models (backwards compatibility)
UserCredits = UserCreditsInDB
CreditTransaction = CreditTransactionInDB
