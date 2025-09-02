"""Chatroom domain models following clean architecture patterns."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from .common import (
    AuditMixin,
    ConsumptionMixin,
    ExpiryMixin,
    LastActivityMixin,
    PyObjectId,
    Schema,
    StartEndMixin,
)


class ChatroomStatus(str, Enum):
    """Chatroom status enumeration."""

    ACTIVE = "active"
    ENDED = "ended"
    ABANDONED = "abandoned"


class MatchType(str, Enum):
    """Match type enumeration for cleaner match record management."""

    INITIAL = "initial"  # First-time user bonus matches (granted once)
    DAILY_FREE = "daily_free"  # Daily refresh matches (1 per day)
    PAID = "paid"  # Purchased matches (costs credits)


class MatchStatus(str, Enum):
    """Match status enumeration for individual match lifecycle."""

    AVAILABLE = "available"  # Ready to use by user
    CONSUMED = "consumed"  # User has used this match (chatted/skipped)
    EXPIRED = "expired"  # Match has expired (time limit exceeded)


# Shared fields for Chatroom schemas
class ChatroomBase(Schema):
    """Base chatroom fields shared across different schemas."""

    user_id: str = Field(..., description="Reference to User._id")
    sub_account_id: str = Field(..., description="Reference to SubAccount._id")
    agent_id: str = Field(
        ..., description="Reference to Agent._id (for easier querying)"
    )
    status: ChatroomStatus = Field(
        default=ChatroomStatus.ACTIVE, description="Chatroom status"
    )
    channel_name: str = Field(..., description="Pusher channel name for this chatroom")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional chatroom metadata"
    )


# Shared fields for Match schemas (NEW: Individual match records)
class MatchRecordBase(ConsumptionMixin, ExpiryMixin):
    """Base match record fields for individual match records (one candidate per record)."""

    user_id: str = Field(..., description="Reference to User._id")
    match_type: MatchType = Field(
        ..., description="Type of match (initial/daily_free/paid)"
    )
    sub_account_id: str = Field(..., description="Reference to SubAccount._id")
    status: MatchStatus = Field(
        default=MatchStatus.AVAILABLE, description="Match lifecycle status"
    )
    credits_consumed: int = Field(
        default=0, ge=0, description="Credits consumed for this specific match"
    )


# Schema for creating a chatroom
class ChatroomCreate(ChatroomBase):
    """Schema for creating a new chatroom."""

    pass


# Schema for updating a chatroom (all fields optional)
class ChatroomUpdate(Schema):
    """Schema for updating a chatroom."""

    status: Optional[ChatroomStatus] = Field(None, description="Chatroom status")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional chatroom metadata"
    )


# Schema for creating individual match records
class MatchRecordCreate(MatchRecordBase):
    """Schema for creating individual match records."""

    pass


# Schema for updating individual match records
class MatchRecordUpdate(Schema):
    """Schema for updating individual match records."""

    status: Optional[MatchStatus] = Field(None, description="Match status")


# Schema for API responses
class ChatroomResponse(ChatroomBase, AuditMixin, StartEndMixin, LastActivityMixin):
    """Schema for chatroom API responses."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")


# Schema for individual match record API responses
class MatchRecordResponse(MatchRecordBase):
    """Schema for individual match record API responses."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")


# Internal schemas (for DB storage)
class ChatroomInDB(ChatroomBase, AuditMixin, StartEndMixin, LastActivityMixin):
    """Internal schema for chatroom database storage."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")


# Internal schema for individual match record database storage
class MatchRecordInDB(MatchRecordBase, AuditMixin):
    """Internal schema for individual match record database storage."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")


# Additional schemas for specific operations
class MatchCandidate(Schema):
    """Schema for match candidate (sub-account available for matching)."""

    sub_account_id: str = Field(..., description="Reference to SubAccount._id")
    agent_id: str = Field(..., description="Reference to Agent._id")
    agent_name: str = Field(..., description="Agent name")
    sub_account_name: str = Field(..., description="SubAccount name")
    display_name: str = Field(..., description="Display name for users")
    avatar_url: Optional[str] = Field(None, description="Avatar URL")
    bio: Optional[str] = Field(None, description="Biography")
    age: Optional[int] = Field(None, ge=13, le=120, description="Age")
    location: Optional[str] = Field(None, description="Location")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    photo_urls: List[str] = Field(default_factory=list, description="Photo URLs")
    match_id: Optional[str] = Field(default=None, description="Match record ID")
    match_type: Optional[MatchType] = Field(default=None, description="Type of match")


class MatchRequest(Schema):
    """Schema for match request."""

    user_id: str = Field(..., description="Reference to User._id requesting the match")
    use_paid_match: bool = Field(
        default=False,
        description="Whether to use paid match if free match already used",
    )


class MatchResponse(Schema):
    """Schema for match response."""

    candidates: List[MatchCandidate] = Field(
        default_factory=list, description="List of matched candidates"
    )
    credits_consumed: int = Field(
        default=0, ge=0, description="Credits consumed for this match"
    )
    remaining_credits: int = Field(
        default=0, ge=0, description="User's remaining credits"
    )
    has_remaining_matches: bool = Field(
        default=False, description="Whether user has remaining free matches"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional match metadata (e.g., last match info for UI)",
    )


class ChatRequest(Schema):
    """Schema for chat request (creating chatroom with selected sub-account)."""

    user_id: str = Field(..., description="Reference to User._id")
    sub_account_id: str = Field(..., description="Reference to SubAccount._id")


class AgentSendMessageRequest(Schema):
    """Schema for agent sending a message."""

    message: str = Field(
        ..., min_length=1, max_length=4000, description="Message content"
    )
    message_type: str = Field(default="text", description="Message type")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Message metadata"
    )


class AgentTypingRequest(Schema):
    """Schema for agent typing indicator."""

    is_typing: bool = Field(..., description="Whether agent is typing")


class SendMessageRequest(Schema):
    """Schema for sending a message."""

    message: str = Field(
        ..., min_length=1, max_length=4000, description="Message content"
    )
    message_type: str = Field(default="text", description="Message type")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Message metadata"
    )


class TypingIndicatorRequest(Schema):
    """Schema for typing indicator."""

    is_typing: bool = Field(..., description="Whether user is typing")


class JoinChatroomResponse(Schema):
    """Response for joining a chatroom."""

    chatroom: ChatroomResponse = Field(..., description="Chatroom details")
    pusher_auth: Dict[str, Any] = Field(..., description="Pusher authentication data")


# Convenience aliases for the main domain models
Chatroom = ChatroomInDB
MatchRecord = MatchRecordInDB


# Utility classes for match operations
class MatchBreakdown(Schema):
    """Breakdown of available matches by type."""

    initial: int = Field(default=0, description="Available initial matches")
    daily_free: int = Field(default=0, description="Available daily free matches")
    paid: int = Field(default=0, description="Available paid matches")
    total: int = Field(default=0, description="Total available matches")


class MatchSummary(Schema):
    """Summary of user's match status."""

    available_matches: MatchBreakdown = Field(default_factory=MatchBreakdown)
    has_initial_matches: bool = Field(
        default=False, description="User has initial matches available"
    )
    can_get_daily_free: bool = Field(
        default=False, description="User can get daily free match today"
    )
    last_daily_match_date: Optional[str] = Field(
        None, description="Date of last daily match (YYYY-MM-DD)"
    )
    total_matches_used: int = Field(
        default=0, description="Total matches consumed by user"
    )
