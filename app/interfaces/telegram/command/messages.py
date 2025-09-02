"""Constants for Telegram command messages."""

from app.domain.models.user import UserRole


class CommandMessages:
    """Constants for all Telegram command text messages."""

    # Help command message for regular users (only 3 commands)
    USER_HELP_TEXT = (
        "💕 *LoveLush Bot Commands* 💕\n\n"
        "🚀 /start - Begin your journey\n"
        "🛒 /products - Browse and purchase products\n"
        "❓ /help - Show this menu\n\n"
        "✨ Ready to find your match? Use /start! ✨\n"
        "🛍️ Want to explore products? Use /products! 🛍️"
    )

    # Help command message for admins (all commands)
    ADMIN_HELP_TEXT = (
        "💕 *LoveLush Bot Commands* (Admin) 💕\n\n"
        "🚀 /start - Begin your journey\n"
        "🔄 /restart - Update your profile\n"
        "🗑️ /resign - Start completely fresh\n"
        "🛒 /products - Browse and purchase products\n"
        "❌ /cancel - Cancel current action\n"
        "📊 /status - Check bot status\n"
        "❓ /help - Show this menu\n\n"
        "🛠️ Admin: You have access to all commands! 🛠️"
    )

    @classmethod
    def get_help_text(cls, user_role: UserRole = UserRole.USER) -> str:
        """Get help text based on user role."""
        if user_role == UserRole.ADMIN:
            return cls.ADMIN_HELP_TEXT
        else:
            return cls.USER_HELP_TEXT

    # Status command message
    STATUS_TEXT = (
        "📊 *Bot Status* 📊\n\n"
        "✅ Status: Online & Active\n"
        "🤖 LoveLush Bot ready to help!\n"
        "💕 All systems operational"
    )

    # Welcome message for new users
    WELCOME_TEXT = (
        "💕 *Welcome to LoveLush!* 💕\n\n"
        "✨ Your AI companion for meaningful connections!\n\n"
        "🚀 Ready to start? Use /start\n"
        "❓ Need help? Use /help"
    )

    # Cancel command success message
    CANCEL_SUCCESS_TEXT = "✅ Current workflow cancelled successfully."

    # Cancel command no workflow message
    CANCEL_NO_WORKFLOW_TEXT = "ℹ️ No active workflow to cancel."

    # Error messages
    ERROR_GENERAL = "❌ Sorry, something went wrong."
    ERROR_RESTART_COMMAND = "❌ Sorry, something went wrong with the restart command."
    ERROR_RESIGN_COMMAND = "❌ Sorry, something went wrong with the resign command."
