"""Response classes for Telegram SDK operations."""

from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

from telegram.error import TelegramError

from app.interfaces.telegram.common.types import TelegramMessage, TelegramUser

T = TypeVar("T")


@dataclass
class TelegramResponse(Generic[T]):
    """Generic response wrapper for Telegram operations."""

    success: bool
    data: Optional[T] = None
    error: Optional[TelegramError] = None
    error_code: Optional[int] = None
    error_description: Optional[str] = None

    @classmethod
    def success_response(cls, data: T) -> "TelegramResponse[T]":
        """Create a successful response."""
        return cls(success=True, data=data)

    @classmethod
    def error_response(
        cls, error: TelegramError, error_code: Optional[int] = None
    ) -> "TelegramResponse[T]":
        """Create an error response."""
        return cls(
            success=False,
            error=error,
            error_code=error_code or getattr(error, "error_code", 400),
            error_description=str(error),
        )


@dataclass
class MessageResult:
    """Result data for sent messages."""

    message: TelegramMessage
    message_id: int
    date_timestamp: float
    text: Optional[str]

    @classmethod
    def from_message(cls, message: TelegramMessage) -> "MessageResult":
        """Create MessageResult from Telegram Message."""
        return cls(
            message=message,
            message_id=message.message_id,
            date_timestamp=message.date.timestamp(),
            text=message.text,
        )


@dataclass
class BotInfo:
    """Bot information result."""

    user: TelegramUser
    id: int
    is_bot: bool
    first_name: str
    username: Optional[str]

    @classmethod
    def from_user(cls, user: TelegramUser) -> "BotInfo":
        """Create BotInfo from Telegram User."""
        return cls(
            user=user,
            id=user.id,
            is_bot=user.is_bot,
            first_name=user.first_name,
            username=user.username,
        )


# Type aliases for specific response types
MessageResponse = TelegramResponse[MessageResult]
BotInfoResponse = TelegramResponse[BotInfo]
WebhookResponse = TelegramResponse[bool]
