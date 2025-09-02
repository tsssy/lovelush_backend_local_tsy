"""Message domain models following clean architecture patterns."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from .common import AuditMixin, EditMixin, PyObjectId, Schema


class MessageType(str, Enum):
    """Message type enumeration."""

    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    SYSTEM = "system"
    TYPING_START = "typing_start"
    TYPING_STOP = "typing_stop"
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    CHAT_ENDED = "chat_ended"


class MessageSenderType(str, Enum):
    """Message sender type enumeration."""

    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


# Shared fields for Message schemas
class MessageBase(EditMixin):
    """Base message fields shared across different schemas."""

    chatroom_id: str = Field(..., description="Reference to Chatroom._id")
    sender_id: Optional[str] = Field(
        None, description="Reference to sender ID (null for system)"
    )
    sender_type: MessageSenderType = Field(..., description="Type of sender")
    message: str = Field(..., description="Message text content")
    message_type: MessageType = Field(
        default=MessageType.TEXT, description="Type of message"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional message metadata"
    )
    is_deleted: bool = Field(default=False, description="Whether message was deleted")
    read_by: List[str] = Field(
        default_factory=list, description="List of user IDs who read this message"
    )


# Schema for creating a message
class MessageCreate(MessageBase):
    """Schema for creating a new message."""

    pass


# Schema for updating a message (all fields optional)
class MessageUpdate(Schema):
    """Schema for updating a message."""

    message: Optional[str] = Field(
        None, min_length=1, max_length=4000, description="Updated message content"
    )
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")
    is_deleted: Optional[bool] = Field(None, description="Mark as deleted")


# Schema for API responses
class MessageResponse(MessageBase, AuditMixin):
    """Schema for message API responses."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    sender_details: Optional[Dict[str, Any]] = Field(
        default=None, description="Sender user/agent details (populated by service)"
    )


# Internal schema (for DB storage)
class MessageInDB(MessageBase, AuditMixin):
    """Internal schema for message database storage."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")


# Additional schemas for specific operations
class MessageHistory(Schema):
    """Schema for paginated message history."""

    messages: List[MessageResponse] = Field(
        default_factory=list, description="List of messages"
    )
    total_messages: int = Field(default=0, description="Total messages in chatroom")
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=50, description="Messages per page")
    has_more: bool = Field(default=False, description="Whether there are more messages")


class MessageReadReceipt(Schema):
    """Schema for message read receipts."""

    message_id: str = Field(..., description="Reference to Message._id")
    reader_id: str = Field(
        ..., description="Reference to User._id who read the message"
    )
    read_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the message was read",
    )


# Convenience alias for the main domain model (backwards compatibility)
Message = MessageInDB
