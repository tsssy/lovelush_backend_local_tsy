"""UI rendering utilities for Telegram workflows."""

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from app.core.config.settings import settings
from app.interfaces.telegram.common.types import (
    TelegramInlineKeyboardButton,
    TelegramInlineKeyboardMarkup,
    TelegramReplyKeyboardRemove,
)

LOCATION_MAP = {
    "united_states": "United States",
    "united_kingdom": "United Kingdom",
    "canada": "Canada",
    "australia": "Australia",
    "new_zealand": "New Zealand",
}

LOCATION_BUTTONS = [
    [
        {"text": "🇺🇸 United States", "callback_data": "location:united_states"},
        {"text": "🇬🇧 United Kingdom", "callback_data": "location:united_kingdom"},
    ],
    [
        {"text": "🇨🇦 Canada", "callback_data": "location:canada"},
        {"text": "🇦🇺 Australia", "callback_data": "location:australia"},
    ],
    [
        {"text": "🇳🇿 New Zealand", "callback_data": "location:new_zealand"},
    ],
]


class ButtonStyle(Enum):
    """Button styling options."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"


class UIRenderer:
    """Handles UI rendering for Telegram workflows."""

    @staticmethod
    def create_inline_keyboard(
        buttons: List[List[Dict[str, str]]],
    ) -> TelegramInlineKeyboardMarkup:
        """Create inline keyboard markup using SDK objects."""
        keyboard_rows = []
        for row in buttons:
            button_row = []
            for btn in row:
                if "callback_data" in btn:
                    button = TelegramInlineKeyboardButton(
                        text=btn["text"], callback_data=btn["callback_data"]
                    )
                elif "url" in btn:
                    button = TelegramInlineKeyboardButton(
                        text=btn["text"], url=btn["url"]
                    )
                else:
                    continue
                button_row.append(button)
            if button_row:
                keyboard_rows.append(button_row)

        return TelegramInlineKeyboardMarkup(keyboard_rows)

    @staticmethod
    def gender_selection_keyboard() -> TelegramInlineKeyboardMarkup:
        """Create gender selection keyboard using SDK objects directly."""
        return UIRenderer.create_inline_keyboard(
            [
                [
                    {"text": "👨 Male", "callback_data": "gender:male"},
                    {"text": "👩 Female", "callback_data": "gender:female"},
                ],
            ]
        )

    @staticmethod
    def location_selection_keyboard() -> TelegramInlineKeyboardMarkup:
        """Create location selection keyboard using SDK objects directly."""
        return UIRenderer.create_inline_keyboard(LOCATION_BUTTONS)

    @staticmethod
    def create_start_chat_button(
        location: Optional[str] = None, url: str = ""
    ) -> TelegramInlineKeyboardMarkup:
        """Create chat button using SDK objects directly."""
        button_text = f"💕 Open Love App"
        if location:
            location_name = LOCATION_MAP.get(location.lower(), location.title())
            button_text = f"💕 Chat with girls in {location_name}"
        button = TelegramInlineKeyboardButton(text=button_text, url=url)
        return TelegramInlineKeyboardMarkup([[button]])

    @staticmethod
    def create_chatroom_notification_keyboard(
        chatroom_id: str,
    ) -> TelegramInlineKeyboardMarkup:
        """Create inline keyboard for chatroom notification."""
        web_app_url = (
            f"{settings.telegram_mini_app_url}?startapp=chatroom-{chatroom_id}"
        )
        button = TelegramInlineKeyboardButton(text="💬 Open Chat", url=web_app_url)
        return TelegramInlineKeyboardMarkup([[button]])

    @staticmethod
    def create_remove_keyboard() -> TelegramReplyKeyboardRemove:
        """Create a remove keyboard markup using SDK objects."""
        return TelegramReplyKeyboardRemove()


class MessageFormatter:
    """Handles message text formatting."""

    @staticmethod
    def welcome_message() -> str:
        """Format welcome message."""
        return (
            "✨ Welcome to LoveLush! ✨\n\n"
            "💕 Your personal AI companion for meaningful connections!\n\n"
            "Let's set up your profile to get started 🚀\n\n"
            "👤 First, please select your gender:"
        )

    @staticmethod
    def gender_confirmed_message(gender: str) -> str:
        """Format gender confirmation message."""
        gender_emoji = "👨 Male" if gender == "male" else "👩 Female"
        return (
            f"✅ Perfect! You selected: {gender_emoji}\n\n"
            "🎂 Now, let's get your age information!\n\n"
            "👇 Please enter your age (must be between 18 and 100):\n"
            "💡 Just type a number and send it to me!"
        )

    @staticmethod
    def age_confirmed_message(age: Union[str, int]) -> str:
        """Format age confirmation message."""
        return (
            f"🎉 Awesome! Age: {age} ✨\n\n"
            "🌍 Finally, let's set your location!\n\n"
            "📍 Please select your country/region from the options below:"
        )

    @staticmethod
    def location_share_prompt() -> str:
        """Format location sharing prompt."""
        return "Please share your location using the button below:"

    @staticmethod
    def completion_message(
        user_data: Dict[str, Any], miniapp_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Format completion message with miniapp URL and return message with button."""
        gender_display = "👨 Male" if user_data.get("gender") == "male" else "👩 Female"
        age_display = user_data.get("age", "Not specified")
        location_display = user_data.get("location", "Not specified")

        message_text = (
            "🎉 Welcome to LoveLush! 🎉\n\n"
            "✨ Your profile is now complete! ✨\n\n"
            "📋 Your Profile Summary:\n"
            f"👤 Gender: {gender_display}\n"
            f"🎂 Age: {age_display}\n"
            f"🌍 Location: {location_display}\n\n"
            "🚀 You're all set to start your journey!"
        )

        result: Dict[str, Any] = {"text": message_text}

        if miniapp_url:
            location = user_data.get("location")
            result["reply_markup"] = UIRenderer.create_start_chat_button(
                location, miniapp_url
            )

        return result

    @staticmethod
    def returning_user_message(
        user_data: Optional[Dict[str, Any]] = None, miniapp_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Format returning user message with miniapp button."""
        message_text = (
            "🎉 Welcome back to LoveLush! 🎉\n\n"
            "✨ So great to see you again! Everything is ready and waiting for you."
        )

        result: Dict[str, Any] = {"text": message_text}

        # Always show app link button if miniapp_url is available
        if miniapp_url:
            location: Optional[str] = None
            if user_data:
                location = user_data.get("location")
            result["reply_markup"] = UIRenderer.create_start_chat_button(
                location, miniapp_url
            )

        return result

    @staticmethod
    def cancellation_message() -> str:
        """Format cancellation message."""
        return "❌ Setup cancelled. No worries! You can restart anytime with /start ✨"

    @staticmethod
    def invalid_input_message() -> str:
        """Format invalid input message."""
        return "🤔 Please use the buttons provided or type /cancel to exit. Thanks! 😊"

    @staticmethod
    def age_validation_error() -> str:
        """Format age validation error."""
        return "⚠️ Please enter a valid age between 18 and 100. 📅"

    @staticmethod
    def age_format_error() -> str:
        """Format age format error."""
        return "🔢 Please enter a valid number for your age. For example: 25"

    @staticmethod
    def location_fallback_message() -> str:
        """Format location fallback message."""
        return "Please use the location button or select from the cities above."

    @staticmethod
    def location_text_error() -> str:
        """Format location text input error."""
        return "Please enter a valid city name, use the location button, or select from the options above."

    @staticmethod
    def restart_welcome_message() -> str:
        """Format restart welcome message."""
        return (
            "🔄 Time to refresh your profile! 🔄\n\n"
            "✨ Let's update your information to make sure everything is current and accurate!\n\n"
            "🎯 This will help me provide you with better matches and experiences.\n\n"
            "👤 Let's start by confirming your gender:"
        )

    @staticmethod
    def restart_completion_message(
        user_data: Dict[str, Any], miniapp_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Format restart completion message with updated profile and return message with button."""
        gender_display = "👨 Male" if user_data.get("gender") == "male" else "👩 Female"
        age_display = user_data.get("age", "Not specified")
        location_display = user_data.get("location", "Not specified")

        message_text = (
            "🎉 Profile Update Complete! 🎉\n\n"
            "✅ Your information has been successfully updated! ✅\n\n"
            "📋 Updated Profile Summary:\n"
            f"👤 Gender: {gender_display}\n"
            f"🎂 Age: {age_display}\n"
            f"🌍 Location: {location_display}\n\n"
            "🚀 Ready to continue your LoveLush experience!"
        )

        result: Dict[str, Any] = {"text": message_text}

        if miniapp_url and user_data.get("location"):
            location = user_data.get("location")
            if isinstance(location, str):
                result["reply_markup"] = UIRenderer.create_start_chat_button(
                    location, miniapp_url
                )

        return result

    @staticmethod
    def format_chatroom_notification_message(
        sender_name: str,
        message_preview: str,
        chatroom_name: Optional[str] = None,
        chatroom_id: Optional[str] = None,
    ) -> str:
        """Format the notification message text."""
        # Truncate message preview if too long
        if len(message_preview) > 100:
            message_preview = message_preview[:97] + "..."

        # Create notification message
        chatroom_title = (
            chatroom_name or f"Chat {chatroom_id[:8] if chatroom_id else 'Unknown'}"
        )

        return (
            f"💬 *New message in {chatroom_title}*\n"
            f"👤 From: {sender_name}\n"
            f"📝 {message_preview}\n\n"
            f"Tap to open the chat!"
        )
