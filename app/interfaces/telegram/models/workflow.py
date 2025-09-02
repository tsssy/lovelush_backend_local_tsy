"""Workflow domain models following clean architecture patterns."""

from enum import Enum
from typing import Any, Dict, Optional, Union

from bson import ObjectId
from pydantic import Field, field_validator

from app.domain.models.common import AuditMixin, ExpiryMixin, PyObjectId, Schema


class WorkflowStep(str, Enum):
    """Workflow step enumeration."""

    GENDER = "gender"
    AGE = "age"
    LOCATION = "location"
    PRODUCTS_LIST = "products_list"
    PRODUCT_DETAIL = "product_detail"
    PAYMENT_CONFIRMATION = "payment_confirmation"
    COMPLETE = "complete"


# Shared fields for Workflow schemas
class WorkflowStateBase(ExpiryMixin):
    """Base workflow state fields shared across different schemas."""

    user_id: str = Field(..., description="Reference to User._id")
    telegram_user_id: int = Field(..., description="Telegram user ID")
    chat_id: int = Field(..., description="Telegram chat ID")
    workflow_type: str = Field(..., description="Type of workflow")
    current_step: WorkflowStep = Field(..., description="Current workflow step")
    data: Dict[str, Any] = Field(default_factory=dict, description="Workflow data")
    last_message_id: Optional[int] = Field(None, description="Last message ID")

    @field_validator("current_step", mode="before")
    @classmethod
    def validate_current_step(cls, v: Union[str, WorkflowStep]) -> WorkflowStep:
        """Convert string values from database back to WorkflowStep enum."""
        if isinstance(v, str):
            try:
                return WorkflowStep(v)
            except ValueError:
                raise ValueError(f"Invalid workflow step: {v}")
        elif isinstance(v, WorkflowStep):
            return v
        else:
            raise ValueError(f"Invalid type for current_step: {type(v)}")

    @field_validator("user_id", mode="before")
    @classmethod
    def validate_user_id(cls, v: Union[str, ObjectId]) -> str:
        """Convert ObjectId to string for user_id."""
        if isinstance(v, ObjectId):
            return str(v)
        elif isinstance(v, str):
            return v
        else:
            raise ValueError(f"Invalid type for user_id: {type(v)}")


# Schema for creating a workflow state
class WorkflowStateCreate(WorkflowStateBase):
    """Schema for creating workflow state."""

    pass


# Schema for updating a workflow state (all fields optional)
class WorkflowStateUpdate(Schema):
    """Schema for updating workflow state."""

    current_step: Optional[WorkflowStep] = Field(
        None, description="Current workflow step"
    )
    data: Optional[Dict[str, Any]] = Field(None, description="Workflow data")
    last_message_id: Optional[int] = Field(None, description="Last message ID")


# Schema for API responses
class WorkflowStateResponse(WorkflowStateBase, AuditMixin):
    """Schema for workflow state API responses."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    model_config = {"json_encoders": {WorkflowStep: lambda v: v.value}}


# Internal schema (for DB storage)
class WorkflowStateInDB(WorkflowStateBase, AuditMixin):
    """Internal schema for workflow state database storage."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    model_config = {"json_encoders": {WorkflowStep: lambda v: v.value}}


# Convenience alias for the main domain model (backwards compatibility)
WorkflowState = WorkflowStateInDB
