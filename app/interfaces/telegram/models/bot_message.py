"""Bot message domain models following clean architecture patterns."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union

from pydantic import Field

from app.domain.models.common import AuditMixin, PyObjectId, Schema
from app.interfaces.telegram.common.types import TelegramMessage


class BotMessageType(str, Enum):
    """Bot message type enumeration."""

    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    STICKER = "sticker"
    VOICE = "voice"
    VIDEO_NOTE = "video_note"
    LOCATION = "location"
    CONTACT = "contact"
    VENUE = "venue"
    POLL = "poll"
    DICE = "dice"
    GAME = "game"
    ANIMATION = "animation"
    PAID_MEDIA = "paid_media"
    STORY = "story"
    COMMAND = "command"
    SYSTEM = "system"
    ERROR = "error"


class BotPlatform(str, Enum):
    """Bot platform enumeration."""

    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    DISCORD = "discord"


class BotMessageDirection(str, Enum):
    """Bot message direction enumeration."""

    INCOMING = "incoming"  # User to bot
    OUTGOING = "outgoing"  # Bot to user


class BotMessageMetadata(Schema):
    """Bot message metadata for platform-specific information."""

    # Telegram-specific
    telegram_message_id: Optional[int] = Field(None, description="Telegram message ID")
    telegram_chat_id: Optional[int] = Field(None, description="Telegram chat ID")
    telegram_user_id: Optional[int] = Field(None, description="Telegram user ID")
    telegram_username: Optional[str] = Field(None, description="Telegram username")

    # Command-specific
    command_name: Optional[str] = Field(None, description="Command name")
    command_args: Optional[Dict[str, Any]] = Field(
        None, description="Command arguments"
    )

    # Context and workflow
    workflow_id: Optional[str] = Field(None, description="Reference to workflow ID")
    workflow_step: Optional[str] = Field(None, description="Current workflow step")
    context_data: Optional[Dict[str, Any]] = Field(None, description="Context data")

    # Extra data for platform-specific extensions
    extra_data: Optional[Dict[str, Any]] = Field(
        None, description="Extra platform-specific data"
    )


def _detect_message_type(message_data: Dict[str, Any]) -> BotMessageType:
    """Detect message type from Telegram message data."""
    if not message_data:
        return BotMessageType.TEXT

    # Check for media types first
    media_types = [
        ("photo", BotMessageType.PHOTO),
        ("video", BotMessageType.VIDEO),
        ("audio", BotMessageType.AUDIO),
        ("document", BotMessageType.DOCUMENT),
        ("sticker", BotMessageType.STICKER),
        ("voice", BotMessageType.VOICE),
        ("video_note", BotMessageType.VIDEO_NOTE),
        ("animation", BotMessageType.ANIMATION),
        ("location", BotMessageType.LOCATION),
        ("contact", BotMessageType.CONTACT),
        ("venue", BotMessageType.VENUE),
        ("poll", BotMessageType.POLL),
        ("dice", BotMessageType.DICE),
        ("game", BotMessageType.GAME),
        ("paid_media", BotMessageType.PAID_MEDIA),
        ("story", BotMessageType.STORY),
    ]

    for field, msg_type in media_types:
        if message_data.get(field):
            return msg_type

    # Check for command
    text = message_data.get("text", "")
    if text and text.startswith("/"):
        return BotMessageType.COMMAND

    # Default to text
    return BotMessageType.TEXT


# Shared fields for BotMessage schemas
class BotMessageBase(Schema):
    """Base bot message fields shared across different schemas."""

    user_id: str = Field(..., description="Reference to User._id")
    platform: BotPlatform = Field(..., description="Platform where message originated")
    direction: BotMessageDirection = Field(..., description="Message direction")
    message_type: BotMessageType = Field(
        default=BotMessageType.TEXT, description="Type of bot message"
    )
    message_data: Optional[Dict[str, Any]] = Field(
        None, description="Complete message object data"
    )
    metadata: Optional[BotMessageMetadata] = Field(
        None, description="Platform-specific metadata"
    )
    is_processed: bool = Field(
        default=False, description="Whether message has been processed by bot"
    )
    processing_error: Optional[str] = Field(
        None, description="Error message if processing failed"
    )


# Schema for creating a bot message
class BotMessageCreate(BotMessageBase):
    """Schema for creating a new bot message."""

    @classmethod
    def from_telegram_message(
        cls,
        message: TelegramMessage,
        user_id: str,
        direction: BotMessageDirection,
        **kwargs,
    ) -> "BotMessageCreate":
        """Create BotMessageCreate from Telegram Message object."""
        message_data = message.to_dict()
        message_type = _detect_message_type(message_data)

        metadata = BotMessageMetadata(
            telegram_message_id=message.message_id,
            telegram_chat_id=message.chat.id,
            telegram_user_id=message.from_user.id if message.from_user else None,
            telegram_username=message.from_user.username if message.from_user else None,
            command_name=None,
            command_args=None,
            workflow_id=None,
            workflow_step=None,
            context_data=None,
            extra_data=None,
        )

        if message_type == BotMessageType.COMMAND and message.text:
            parts = message.text.split()
            metadata.command_name = parts[0]
            if len(parts) > 1:
                metadata.command_args = {"args": parts[1:]}

        return cls(
            user_id=user_id,
            platform=BotPlatform.TELEGRAM,
            direction=direction,
            message_type=message_type,
            message_data=message_data,
            metadata=metadata,
            **kwargs,
        )


# Schema for updating a bot message (all fields optional)
class BotMessageUpdate(Schema):
    """Schema for updating a bot message."""

    is_processed: Optional[bool] = Field(
        None, description="Whether message has been processed"
    )
    processing_error: Optional[str] = Field(
        None, description="Error message if processing failed"
    )
    message_data: Optional[Dict[str, Any]] = Field(
        None, description="Message object data"
    )
    metadata: Optional[BotMessageMetadata] = Field(
        None, description="Platform-specific metadata"
    )


# Schema for API responses
class BotMessageResponse(BotMessageBase, AuditMixin):
    """Schema for bot message API responses."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    processed_at: Optional[datetime] = Field(
        None, description="Message processing timestamp"
    )


# Internal schema (for DB storage)
class BotMessageInDB(BotMessageBase, AuditMixin):
    """Internal schema for bot message database storage."""

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    processed_at: Optional[datetime] = Field(
        None, description="Message processing timestamp"
    )

    @property
    def text_content(self) -> Optional[str]:
        """Get text content from message data."""
        if self.message_data:
            return self.message_data.get("text") or self.message_data.get("caption")
        return None

    @property
    def media_content(self) -> Optional[Dict[str, Any]]:
        """Get media content (photo, video, audio, document, etc.) from message data."""
        if not self.message_data:
            return None

        media_fields = [
            "photo",
            "video",
            "audio",
            "document",
            "sticker",
            "voice",
            "video_note",
            "animation",
            "paid_media",
        ]

        for field in media_fields:
            if field in self.message_data and self.message_data[field]:
                return {field: self.message_data[field]}
        return None

    @property
    def location_content(self) -> Optional[Dict[str, Any]]:
        """Get location/venue content from message data."""
        if not self.message_data:
            return None

        if "location" in self.message_data:
            return {"location": self.message_data["location"]}
        elif "venue" in self.message_data:
            return {"venue": self.message_data["venue"]}
        return None

    @property
    def contact_content(self) -> Optional[Dict[str, Any]]:
        """Get contact content from message data."""
        if not self.message_data:
            return None

        if "contact" in self.message_data:
            return {"contact": self.message_data["contact"]}
        return None

    @property
    def effective_message_type(self) -> BotMessageType:
        """Get the effective message type, auto-detecting from message_data if available."""
        if self.message_data:
            return _detect_message_type(self.message_data)
        return self.message_type

    def get_telegram_message(self) -> Optional[TelegramMessage]:
        """Reconstruct Telegram Message object from stored data."""
        if not self.message_data:
            return None

        try:
            return TelegramMessage.de_json(self.message_data, bot=None)
        except Exception:
            return None

    @classmethod
    def from_telegram_message(
        cls,
        message: TelegramMessage,
        user_id: Union[str, PyObjectId],
        direction: BotMessageDirection,
        **kwargs,
    ) -> "BotMessageInDB":
        """Create BotMessage from Telegram Message object."""
        message_data = message.to_dict()
        message_type = _detect_message_type(message_data)

        # Create metadata from message
        metadata = BotMessageMetadata(
            telegram_message_id=message.message_id,
            telegram_chat_id=message.chat.id,
            telegram_user_id=message.from_user.id if message.from_user else None,
            telegram_username=message.from_user.username if message.from_user else None,
            command_name=None,
            command_args=None,
            workflow_id=None,
            workflow_step=None,
            context_data=None,
            extra_data=None,
        )

        if message_type == BotMessageType.COMMAND and message.text:
            parts = message.text.split()
            metadata.command_name = parts[0]
            if len(parts) > 1:
                metadata.command_args = {"args": parts[1:]}

        # Ensure user_id is string for consistency
        if isinstance(user_id, PyObjectId):
            user_id = str(user_id)

        return cls(
            user_id=user_id,
            platform=BotPlatform.TELEGRAM,
            direction=direction,
            message_type=message_type,
            message_data=message_data,
            metadata=metadata,
            **kwargs,
        )


# Convenience alias for the main domain model (backwards compatibility)
BotMessage = BotMessageInDB
