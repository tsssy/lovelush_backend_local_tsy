"""Settings models for app configuration management."""

from typing import Any, Dict, Optional

from pydantic import Field

from app.domain.models.common import AuditMixin, PyObjectId, Schema


class CoinConfiguration(Schema):
    """Configuration for coin/credits system."""

    initial_free_coins: int = Field(
        default=100, ge=0, description="Initial free coins given to new users"
    )


class MessageConfiguration(Schema):
    """Configuration for messaging system."""

    cost_per_message: int = Field(
        default=10, ge=0, description="Cost in coins per message sent"
    )
    initial_free_messages: int = Field(
        default=0, ge=0, description="Initial free messages given to new users"
    )


class MatchConfiguration(Schema):
    """Configuration for matching system."""

    cost_per_match: int = Field(
        default=5, ge=0, description="Cost in coins per match request"
    )
    initial_free_matches: int = Field(
        default=5, ge=0, description="Initial free matches given to new users"
    )
    daily_free_matches: int = Field(
        default=1, ge=0, description="Daily free matches for users"
    )


# Shared fields for AppSettings schemas
class AppSettingsBase(Schema):
    """Base app settings fields shared across different schemas."""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Settings name/identifier"
    )
    description: Optional[str] = Field(
        None, max_length=500, description="Settings description"
    )
    coin_config: CoinConfiguration = Field(
        default_factory=CoinConfiguration, description="Coin system configuration"
    )
    message_config: MessageConfiguration = Field(
        default_factory=MessageConfiguration, description="Message system configuration"
    )
    match_config: MatchConfiguration = Field(
        default_factory=MatchConfiguration, description="Match system configuration"
    )
    is_active: bool = Field(default=True, description="Whether settings are active")
    is_default: bool = Field(
        default=False, description="Whether this is the default settings"
    )
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


# Schema for creating app settings
class AppSettingsCreate(AppSettingsBase):
    """Schema for creating new app settings."""

    pass


# Schema for updating app settings (all fields optional)
class AppSettingsUpdate(Schema):
    """Schema for updating app settings."""

    name: Optional[str] = Field(
        None, min_length=1, max_length=100, description="Settings name/identifier"
    )
    description: Optional[str] = Field(
        None, max_length=500, description="Settings description"
    )
    coin_config: Optional[CoinConfiguration] = Field(
        None, description="Coin system configuration"
    )
    message_config: Optional[MessageConfiguration] = Field(
        None, description="Message system configuration"
    )
    match_config: Optional[MatchConfiguration] = Field(
        None, description="Match system configuration"
    )
    is_active: Optional[bool] = Field(None, description="Whether settings are active")
    is_default: Optional[bool] = Field(
        None, description="Whether this is the default settings"
    )
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @classmethod
    def from_app_settings(
        cls, settings: "AppSettingsInDB", **overrides
    ) -> "AppSettingsUpdate":
        """Create AppSettingsUpdate from AppSettings model with optional field overrides."""
        settings_data = {
            "name": settings.name,
            "description": settings.description,
            "coin_config": settings.coin_config,
            "message_config": settings.message_config,
            "match_config": settings.match_config,
            "is_active": settings.is_active,
            "is_default": settings.is_default,
            "metadata": settings.metadata,
        }
        settings_data.update(overrides)
        return cls(**settings_data)


# Schema for API responses
class AppSettingsResponse(AppSettingsBase, AuditMixin):
    """Schema for app settings API responses."""

    id: PyObjectId = Field(alias="_id")


# Internal schemas (for DB storage)
class AppSettingsInDB(AppSettingsBase, AuditMixin):
    """Internal schema for app settings database storage."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")


# Schema for user-specific settings API responses (only exposes common settings)
class UserSettingsResponse(Schema):
    """Schema for user-specific settings API responses."""

    cost_per_message: int = Field(description="Cost in coins per message sent")
    cost_per_match: int = Field(description="Cost in coins per match request")
    initial_free_coins: int = Field(description="Initial free coins given to new users")
    initial_free_messages: int = Field(
        description="Initial free messages given to new users"
    )
    initial_free_matches: int = Field(
        description="Initial free matches given to new users"
    )
    daily_free_matches: int = Field(description="Daily free matches for users")


# Convenience alias
AppSettings = AppSettingsInDB
