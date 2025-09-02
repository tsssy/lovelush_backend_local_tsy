"""
Common model components and shared types for the domain layer.
Provides reusable Pydantic field types and validation classes.
"""

from datetime import datetime, timezone
from typing import Annotated, Optional

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field
from pydantic_core import core_schema


# Custom ObjectId for Pydantic v2 (MongoDB compatibility)
class PyObjectId(str):
    """
    Custom ObjectId class for Pydantic v2 models.

    Provides proper validation and serialization for MongoDB ObjectIds
    while maintaining compatibility with Pydantic v2 schemas and FastAPI responses.
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        """Get Pydantic core schema for ObjectId."""

        def validate_object_id(value):
            if isinstance(value, ObjectId):
                return str(value)
            if isinstance(value, str):
                try:
                    ObjectId(value)
                    return value
                except Exception:
                    raise ValueError("Invalid ObjectId")
            raise ValueError("Invalid ObjectId")

        return core_schema.no_info_plain_validator_function(validate_object_id)


# Base Schema with standardized configuration for all models
class Schema(BaseModel):
    """
    Base schema with standardized configuration for all domain models.

    All models should inherit from this base class to ensure consistent
    configuration across the application.
    """

    model_config = ConfigDict(
        # extra="forbid",
        from_attributes=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )


# Common audit fields for models that track creation/modification
class TimestampMixin(Schema):
    """Mixin for models that need timestamp tracking."""

    created_at: Annotated[
        Optional[datetime],
        Field(
            default_factory=lambda: datetime.now(timezone.utc),
            description="Creation timestamp",
        ),
    ] = None
    updated_at: Annotated[
        Optional[datetime],
        Field(
            default_factory=lambda: datetime.now(timezone.utc),
            description="Last update timestamp",
        ),
    ] = None


class SoftDeleteMixin(Schema):
    """Mixin for models that support soft deletion."""

    deleted_at: Annotated[
        Optional[datetime], Field(None, description="Deletion timestamp")
    ] = None
    is_active: Annotated[
        bool, Field(default=True, description="Whether the record is active")
    ] = True


class ExpiryMixin(Schema):
    """Mixin for models that have expiration functionality."""

    expires_at: Annotated[
        Optional[datetime], Field(None, description="Expiration timestamp")
    ] = None

    def is_expired(self) -> bool:
        """Check if the entity has expired."""
        if self.expires_at is None:
            return False

        # Ensure both datetimes are timezone-aware for comparison
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            # If expires_at is timezone-naive, assume it's UTC
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        return expires_at < datetime.now(timezone.utc)

    def is_valid(self) -> bool:
        """Check if the entity is still valid (not expired)."""
        return not self.is_expired()


class RequiredExpiryMixin(Schema):
    """Mixin for models that require expiration functionality."""

    expires_at: Annotated[datetime, Field(..., description="Expiration timestamp")]

    def is_expired(self) -> bool:
        """Check if the entity has expired."""
        # Ensure both datetimes are timezone-aware for comparison
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            # If expires_at is timezone-naive, assume it's UTC
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        return expires_at < datetime.now(timezone.utc)

    def is_valid(self) -> bool:
        """Check if the entity is still valid (not expired)."""
        return not self.is_expired()


class ConsumptionMixin(Schema):
    """Mixin for models that track consumption/usage."""

    consumed_at: Annotated[
        Optional[datetime], Field(None, description="Consumption timestamp")
    ] = None

    def is_consumed(self) -> bool:
        """Check if the entity has been consumed."""
        return self.consumed_at is not None

    def mark_consumed(self) -> None:
        """Mark entity as consumed with current timestamp."""
        self.consumed_at = datetime.now(timezone.utc)


class CompletionMixin(Schema):
    """Mixin for models that track completion status."""

    completed_at: Annotated[
        Optional[datetime], Field(None, description="Completion timestamp")
    ] = None

    def is_completed(self) -> bool:
        """Check if the entity has been completed."""
        return self.completed_at is not None

    def mark_completed(self) -> None:
        """Mark entity as completed with current timestamp."""
        self.completed_at = datetime.now(timezone.utc)


class ProcessingMixin(Schema):
    """Mixin for models that track processing status."""

    processed_at: Annotated[
        Optional[datetime], Field(None, description="Processing timestamp")
    ] = None

    def is_processed(self) -> bool:
        """Check if the entity has been processed."""
        return self.processed_at is not None

    def mark_processed(self) -> None:
        """Mark entity as processed with current timestamp."""
        self.processed_at = datetime.now(timezone.utc)


class EditMixin(Schema):
    """Mixin for models that track edit history."""

    edited_at: Annotated[
        Optional[datetime], Field(None, description="Last edit timestamp")
    ] = None
    is_edited: Annotated[
        bool, Field(default=False, description="Whether entity has been edited")
    ] = False

    def mark_edited(self) -> None:
        """Mark entity as edited with current timestamp."""
        self.edited_at = datetime.now(timezone.utc)
        self.is_edited = True


class FailureMixin(Schema):
    """Mixin for models that track failure status."""

    failed_at: Annotated[
        Optional[datetime], Field(None, description="Failure timestamp")
    ] = None
    error_message: Annotated[
        Optional[str], Field(None, description="Error message")
    ] = None

    def is_failed(self) -> bool:
        """Check if the entity has failed."""
        return self.failed_at is not None

    def mark_failed(self, error_message: Optional[str] = None) -> None:
        """Mark entity as failed with current timestamp and optional error message."""
        self.failed_at = datetime.now(timezone.utc)
        if error_message:
            self.error_message = error_message


class LastActivityMixin(Schema):
    """Mixin for models that track last activity time."""

    last_activity_at: Annotated[
        Optional[datetime], Field(None, description="Last activity timestamp")
    ] = None

    def update_last_activity(self) -> None:
        """Update last activity timestamp to current time."""
        self.last_activity_at = datetime.now(timezone.utc)

    def get_time_since_last_activity(self) -> Optional[float]:
        """Get seconds since last activity.

        Returns:
            Seconds since last activity if timestamp exists, None otherwise.
        """
        if self.last_activity_at is None:
            return None
        return (datetime.now(timezone.utc) - self.last_activity_at).total_seconds()


class StartEndMixin(Schema):
    """Mixin for models that track start and end times."""

    started_at: Annotated[
        Optional[datetime], Field(None, description="Start timestamp")
    ] = None
    ended_at: Annotated[
        Optional[datetime], Field(None, description="End timestamp")
    ] = None

    def is_started(self) -> bool:
        """Check if the entity has started."""
        return self.started_at is not None

    def is_ended(self) -> bool:
        """Check if the entity has ended."""
        return self.ended_at is not None

    def is_currently_active(self) -> bool:
        """Check if the entity is currently active (started but not ended)."""
        return self.is_started() and not self.is_ended()

    def mark_started(self) -> None:
        """Mark entity as started with current timestamp."""
        self.started_at = datetime.now(timezone.utc)

    def mark_ended(self) -> None:
        """Mark entity as ended with current timestamp."""
        self.ended_at = datetime.now(timezone.utc)

    def get_duration(self) -> Optional[float]:
        """Get duration in seconds between start and end times.

        Returns:
            Duration in seconds if both start and end times are set, None otherwise.
        """
        if self.started_at is None or self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds()


class CompletionUpdateMixin(Schema):
    """Mixin for update schemas that track completion status."""

    completed_at: Annotated[
        Optional[datetime], Field(None, description="Completion timestamp")
    ] = None


class FailureUpdateMixin(Schema):
    """Mixin for update schemas that track failure status."""

    failed_at: Annotated[
        Optional[datetime], Field(None, description="Failure timestamp")
    ] = None
    error_message: Annotated[
        Optional[str], Field(None, description="Error message")
    ] = None


class ExpiryUpdateMixin(Schema):
    """Mixin for update schemas that have expiration functionality."""

    expires_at: Annotated[
        Optional[datetime], Field(None, description="Expiration timestamp")
    ] = None


class AuditMixin(TimestampMixin, SoftDeleteMixin):
    """Complete audit trail for domain models."""

    pass
