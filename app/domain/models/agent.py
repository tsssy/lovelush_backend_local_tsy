"""Agent and SubAccount domain models following clean architecture patterns."""

from enum import Enum
from typing import List, Optional

from pydantic import Field

from .common import (
    AuditMixin,
    LastActivityMixin,
    PyObjectId,
    RequiredExpiryMixin,
    Schema,
)
from .user import Gender


class AgentStatus(str, Enum):
    """Agent status enumeration."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class AgentRole(str, Enum):
    """Agent role enumeration for authorization."""

    ADMIN = "admin"
    AGENT = "agent"


class SubAccountStatus(str, Enum):
    """SubAccount status enumeration."""

    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"
    SUSPENDED = "suspended"


class UploadType(str, Enum):
    """Upload type enumeration."""

    AVATAR = "avatar"
    PHOTOS = "photos"


class AgentBase(Schema):
    """Base agent fields shared across different schemas."""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Agent company/team name"
    )
    description: Optional[str] = Field(
        None, max_length=500, description="Agent description"
    )
    status: AgentStatus = Field(default=AgentStatus.ACTIVE, description="Agent status")
    role: AgentRole = Field(
        default=AgentRole.AGENT, description="Agent role for authorization"
    )
    priority: int = Field(
        default=0, description="Agent priority for matching (higher = more priority)"
    )


class SubAccountBase(Schema):
    """Base sub-account fields shared across different schemas."""

    name: str = Field(..., min_length=1, max_length=100, description="SubAccount name")
    display_name: str = Field(
        ..., min_length=1, max_length=100, description="Display name for users"
    )
    status: SubAccountStatus = Field(
        default=SubAccountStatus.AVAILABLE, description="SubAccount status"
    )
    avatar_url: Optional[str] = Field(None, description="Avatar URL")
    bio: Optional[str] = Field(None, max_length=500, description="SubAccount biography")
    age: Optional[int] = Field(None, ge=13, le=120, description="SubAccount age")
    location: Optional[str] = Field(
        None, max_length=100, description="SubAccount location"
    )
    gender: Optional[Gender] = Field(None, description="SubAccount gender")
    photo_urls: List[str] = Field(
        default_factory=list, description="List of photo URLs for profile"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="List of tags for categorization and filtering",
    )
    max_concurrent_chats: int = Field(
        default=5, ge=1, description="Maximum concurrent chats"
    )


# Schema for creating an agent
class AgentCreate(AgentBase):
    """Schema for creating a new agent."""

    password: Optional[str] = Field(
        None, min_length=6, description="Password for agent login"
    )


class AgentUpdate(Schema):
    """Schema for updating an agent."""

    name: Optional[str] = Field(
        None, min_length=1, max_length=100, description="Agent company/team name"
    )
    description: Optional[str] = Field(
        None, max_length=500, description="Agent description"
    )
    status: Optional[AgentStatus] = Field(None, description="Agent status")
    role: Optional[AgentRole] = Field(None, description="Agent role for authorization")
    priority: Optional[int] = Field(None, description="Agent priority for matching")


# Schema for creating a sub-account
class SubAccountCreate(SubAccountBase):
    """Schema for creating a new sub-account."""

    agent_id: Optional[str] = Field(
        None, description="Parent agent ID (auto-populated)"
    )
    password: Optional[str] = Field(
        None, min_length=6, description="Password for agent login"
    )


class SubAccountUpdate(Schema):
    """Schema for updating a sub-account."""

    name: Optional[str] = Field(
        None, min_length=1, max_length=100, description="SubAccount name"
    )
    display_name: Optional[str] = Field(
        None, min_length=1, max_length=100, description="Display name for users"
    )
    status: Optional[SubAccountStatus] = Field(None, description="SubAccount status")
    avatar_url: Optional[str] = Field(None, description="Avatar URL")
    bio: Optional[str] = Field(None, max_length=500, description="SubAccount biography")
    age: Optional[int] = Field(None, ge=13, le=120, description="SubAccount age")
    location: Optional[str] = Field(
        None, max_length=100, description="SubAccount location"
    )
    gender: Optional[Gender] = Field(None, description="SubAccount gender")
    photo_urls: Optional[List[str]] = Field(
        None, description="List of photo URLs for profile"
    )
    tags: Optional[List[str]] = Field(
        None, description="List of tags for categorization"
    )
    max_concurrent_chats: Optional[int] = Field(
        None, ge=1, description="Maximum concurrent chats"
    )


class AgentResponse(AgentBase, AuditMixin):
    """Schema for agent API responses."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    last_assigned_sub_account_index: int = Field(
        default=-1, description="Round-robin tracking"
    )


class SubAccountResponse(SubAccountBase, AuditMixin, LastActivityMixin):
    """Schema for sub-account API responses."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    agent_id: PyObjectId = Field(..., description="Reference to Agent._id")
    current_chat_count: int = Field(
        default=0, ge=0, description="Current active chat count"
    )


class AgentInDB(AgentBase, AuditMixin):
    """Internal schema for agent database storage (includes hashed password)."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    hashed_password: Optional[str] = Field(
        None, description="Hashed password for agent login"
    )
    last_assigned_sub_account_index: int = Field(
        default=-1, description="Round-robin tracking"
    )


class SubAccountInDB(SubAccountBase, AuditMixin, LastActivityMixin):
    """Internal schema for sub-account database storage (includes hashed password)."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    agent_id: PyObjectId = Field(..., description="Reference to Agent._id")
    hashed_password: Optional[str] = Field(
        None, description="Hashed password for agent login"
    )
    current_chat_count: int = Field(
        default=0, ge=0, description="Current active chat count"
    )


# Agent Authentication Models
class AgentLogin(Schema):
    """Agent login request model."""

    agent_name: str = Field(..., description="Agent name for login")
    password: str = Field(..., description="Agent password")


class AgentAuthResponse(RequiredExpiryMixin, Schema):
    """Agent authentication response model."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    agent: AgentResponse


class AgentTokenPayload(Schema):
    """Agent JWT token payload model."""

    agent_id: str = Field(..., description="Agent ID")
    agent_name: str = Field(..., description="Agent name")
    type: str = Field(default="agent", description="Token type")


# Upload-related models
class UploadRequest(Schema):
    """Request model for upload presigned URL generation."""

    subaccount_id: str = Field(..., description="Subaccount ID for photo upload")
    file_type: str = Field(
        ..., description="File MIME type or extension (e.g., 'image/jpeg', '.jpg')"
    )
    upload_type: UploadType = Field(..., description="Type of upload: avatar or photos")


class UploadResponse(Schema):
    """Response model for upload presigned URL."""

    upload_url: str = Field(..., description="Presigned URL for file upload")
    file_key: str = Field(..., description="S3 file key for the uploaded file")
    public_url: str = Field(
        ..., description="Public URL for accessing the uploaded file"
    )
    expires_in: int = Field(..., description="URL expiration time in seconds")
    upload_type: UploadType = Field(..., description="Type of upload: avatar or photos")


# Convenience aliases for the main domain models (backwards compatibility)
Agent = AgentInDB
SubAccount = SubAccountInDB
