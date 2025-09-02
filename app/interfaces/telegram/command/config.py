"""Telegram bot command configuration."""

from typing import Dict, Set

from app.core.logging import get_logger
from app.domain.models.user import UserRole

logger = get_logger(__name__)


class TelegramCommandConfig:
    """Configuration for Telegram bot commands."""

    # All command definitions with descriptions
    COMMAND_DEFINITIONS = {
        "/start": "🚀 Start LoveLush journey",
        "/restart": "🔄 Update your profile info",
        "/resign": "🗑️ Delete profile & start fresh",
        "/help": "❓ Show available commands",
        "/status": "📊 Check bot status",
        "/cancel": "❌ Cancel current action",
        "/products": "🛒 Browse and purchase products",
    }

    # User commands (only these 3 for regular users)
    USER_COMMANDS: Set[str] = {
        "/start",
        "/products",
        "/help",
    }

    # Admin commands (all commands)
    ADMIN_COMMANDS: Set[str] = {
        "/start",
        "/restart",
        "/resign",
        "/help",
        "/status",
        "/cancel",
        "/products",
    }

    # Commands that are always available (for backward compatibility)
    CORE_COMMANDS: Set[str] = USER_COMMANDS.copy()

    # Optional commands that can be enabled/disabled
    OPTIONAL_COMMANDS: Set[str] = {
        "/help",
        "/status",
    }

    # Commands currently allowed (can be modified at runtime)
    ALLOWED_COMMANDS: Set[str] = CORE_COMMANDS.copy()

    @classmethod
    def is_command_allowed(
        cls, command: str, user_role: UserRole = UserRole.USER
    ) -> bool:
        """Check if a command is allowed for the given user role."""
        command = command.lower()
        if user_role == UserRole.ADMIN:
            return command in cls.ADMIN_COMMANDS
        else:
            return command in cls.USER_COMMANDS

    @classmethod
    def enable_command(cls, command: str) -> bool:
        """Enable an optional command."""
        if command.lower() in cls.OPTIONAL_COMMANDS:
            cls.ALLOWED_COMMANDS.add(command.lower())
            return True
        return False

    @classmethod
    def disable_command(cls, command: str) -> bool:
        """Disable an optional command."""
        if command.lower() in cls.OPTIONAL_COMMANDS:
            cls.ALLOWED_COMMANDS.discard(command.lower())
            return True
        return False

    @classmethod
    async def update_telegram_commands(cls):
        """Update Telegram bot commands after configuration changes."""
        try:
            # avoided circular import
            from app.interfaces.telegram.setup import telegram_bot_setup

            await telegram_bot_setup.setup_bot_commands()
            return True
        except Exception as e:
            logger.error(f"Failed to update Telegram commands: {e}")
            return False

    @classmethod
    def get_allowed_commands(cls) -> Set[str]:
        """Get all currently allowed commands."""
        return cls.ALLOWED_COMMANDS.copy()

    @classmethod
    def get_optional_commands(cls) -> Set[str]:
        """Get all optional commands."""
        return cls.OPTIONAL_COMMANDS.copy()

    @classmethod
    def get_command_description(cls, command: str) -> str:
        """Get description for a command."""
        return cls.COMMAND_DEFINITIONS.get(command, "Unknown command")

    @classmethod
    def get_allowed_command_definitions(
        cls, user_role: UserRole = UserRole.USER
    ) -> Dict[str, str]:
        """Get definitions for all commands allowed for the given user role."""
        if user_role == UserRole.ADMIN:
            allowed_commands = cls.ADMIN_COMMANDS
        else:
            allowed_commands = cls.USER_COMMANDS

        return {
            cmd: cls.COMMAND_DEFINITIONS[cmd]
            for cmd in allowed_commands
            if cmd in cls.COMMAND_DEFINITIONS
        }


# Global instance
command_config = TelegramCommandConfig()
