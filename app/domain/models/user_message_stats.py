"""User message statistics domain model following clean architecture patterns."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import Field

from .common import AuditMixin, PyObjectId, Schema


# Shared fields for UserMessageStats schemas
class UserMessageStatsBase(Schema):
    """Base user message stats fields shared across different schemas."""

    user_id: str = Field(..., description="Reference to User._id")
    free_messages_used: int = Field(
        default=0, ge=0, description="Number of free messages used"
    )
    last_reset_date: Optional[datetime] = Field(
        None, description="Last date when daily free messages were reset"
    )


# Schema for creating user message stats
class UserMessageStatsCreate(Schema):
    """Schema for creating user message stats."""

    user_id: str = Field(..., description="Reference to User._id")
    free_messages_used: int = Field(
        default=0, ge=0, description="Initial free messages used"
    )


# Schema for updating user message stats (all fields optional)
class UserMessageStatsUpdate(Schema):
    """Schema for updating user message stats."""

    free_messages_used: Optional[int] = Field(
        None, ge=0, description="Number of free messages used"
    )
    last_reset_date: Optional[datetime] = Field(
        None, description="Last date when daily free messages were reset"
    )


# Schema for API responses
class UserMessageStatsResponse(UserMessageStatsBase, AuditMixin):
    """Schema for user message stats API responses."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")


# Internal schema (for DB storage)
class UserMessageStatsInDB(UserMessageStatsBase, AuditMixin):
    """Internal schema for user message stats database storage."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    def is_reset_needed(self) -> bool:
        """Check if daily free messages should be reset."""
        if not self.last_reset_date:
            return True

        # Reset if it's a new day
        now = datetime.now(timezone.utc)
        return now.date() > self.last_reset_date.date()

    def get_available_free_messages(self, initial_free_messages: int) -> int:
        """Get number of available free messages for user."""
        if self.is_reset_needed():
            return initial_free_messages
        return max(0, initial_free_messages - self.free_messages_used)


# Convenience alias
UserMessageStats = UserMessageStatsInDB
