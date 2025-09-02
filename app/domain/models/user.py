"""User domain model following clean architecture patterns."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import EmailStr, Field

from .common import AuditMixin, LastActivityMixin, PyObjectId, Schema


class OnboardingStatus(str, Enum):
    """User onboarding status enumeration."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class Gender(str, Enum):
    """User gender enumeration."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class UserRole(str, Enum):
    """User role enumeration."""

    USER = "user"
    ADMIN = "admin"


class UserBase(Schema):
    """Base user fields shared across different schemas."""

    email: Optional[EmailStr] = Field(None, description="User email address")
    username: str = Field(
        ..., min_length=1, max_length=50, description="Unique username"
    )
    full_name: Optional[str] = Field(
        None, max_length=100, description="Full name of the user"
    )
    bio: Optional[str] = Field(None, max_length=500, description="User's biography")
    age: Optional[int] = Field(None, ge=13, le=120, description="User's age")
    location: Optional[str] = Field(None, max_length=100, description="User's location")
    gender: Optional[Gender] = Field(None, description="User's gender")
    avatar_url: Optional[str] = Field(None, description="URL to user's avatar image")
    telegram_id: Optional[str] = Field(
        None, max_length=50, description="Telegram user ID"
    )
    is_active: bool = Field(default=True, description="Whether the account is active")
    is_verified: bool = Field(
        default=False, description="Whether user email is verified"
    )
    onboarding_status: OnboardingStatus = Field(
        default=OnboardingStatus.NOT_STARTED, description="Current onboarding status"
    )
    role: UserRole = Field(default=UserRole.USER, description="User role in the system")


# Schema for creating a user via API
class UserCreate(UserBase):
    """Schema for creating a new user via API."""

    password: Optional[str] = Field(
        None, min_length=8, max_length=100, description="Password for the user"
    )


class UserCreateByTelegram(Schema):
    """Schema for creating a new user by telegram (early creation)."""

    username: str = Field(
        ..., min_length=1, max_length=50, description="Unique username"
    )
    telegram_id: str = Field(..., max_length=50, description="Telegram user ID")
    onboarding_status: OnboardingStatus = Field(
        default=OnboardingStatus.NOT_STARTED, description="Initial onboarding status"
    )


class UserUpdate(Schema):
    """Schema for updating user information - all fields optional."""

    email: Optional[EmailStr] = Field(None, description="User email address")
    username: Optional[str] = Field(
        None, min_length=1, max_length=50, description="Unique username"
    )
    full_name: Optional[str] = Field(
        None, max_length=100, description="Full name of the user"
    )
    bio: Optional[str] = Field(None, max_length=500, description="User's biography")
    age: Optional[int] = Field(None, ge=13, le=120, description="User's age")
    location: Optional[str] = Field(None, max_length=100, description="User's location")
    gender: Optional[Gender] = Field(None, description="User's gender")
    avatar_url: Optional[str] = Field(None, description="URL to user's avatar image")
    telegram_id: Optional[str] = Field(
        None, max_length=50, description="Telegram user ID"
    )
    password: Optional[str] = Field(
        None, min_length=8, max_length=100, description="New password"
    )
    is_active: Optional[bool] = Field(None, description="Whether the account is active")
    is_verified: Optional[bool] = Field(
        None, description="Whether user email is verified"
    )
    last_visited_url: Optional[str] = Field(None, description="Last visited URL/route")
    last_visited_page: Optional[str] = Field(None, description="Last visited page name")
    onboarding_status: Optional[OnboardingStatus] = Field(
        None, description="Current onboarding status"
    )
    role: Optional[UserRole] = Field(None, description="User role in the system")


class UserResponse(UserBase, AuditMixin, LastActivityMixin):
    """Schema for user API responses (excludes sensitive data)."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    onboarding_completed_at: Optional[datetime] = Field(
        None, description="Onboarding completion timestamp"
    )
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    last_visited_url: Optional[str] = Field(None, description="Last visited URL/route")
    last_visited_page: Optional[str] = Field(None, description="Last visited page name")


class UserInDB(UserBase, AuditMixin, LastActivityMixin):
    """Internal schema for database storage (includes hashed password)."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    hashed_password: str = Field(..., description="Hashed password")
    onboarding_completed_at: Optional[datetime] = Field(
        None, description="Onboarding completion timestamp"
    )
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    last_visited_url: Optional[str] = Field(None, description="Last visited URL/route")
    last_visited_page: Optional[str] = Field(None, description="Last visited page name")


# Auth-related schemas
class RefreshTokenRequest(Schema):
    """Schema for refresh token request."""

    refresh_token: str = Field(..., description="JWT refresh token")


class TelegramAuthRequest(Schema):
    """Schema for Telegram authentication request."""

    telegram_init_data: str = Field(..., description="Telegram initialization data")


# Convenience alias for the main User domain model (backwards compatibility)
User = UserInDB
