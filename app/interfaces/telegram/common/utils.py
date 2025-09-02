"""Telegram utility functions."""

from app.core.config.settings import settings


class TelegramUtils:
    """Utility functions for Telegram bot operations."""

    @staticmethod
    def get_miniapp_url() -> str:
        """
        Get the Mini App URL without any parameters.
        Authentication will be handled through Telegram's initData.

        Returns:
            str: Clean Mini App URL
        """
        base_url = settings.telegram_mini_app_url.rstrip("/")

        if not base_url:
            raise ValueError("TELEGRAM_MINI_APP_URL is not configured")

        # Return clean URL without any parameters
        # Telegram will automatically include initData when user opens the Mini App
        return base_url


# For convenience, create module-level functions
def get_miniapp_url() -> str:
    """Get the Mini App URL without parameters - auth via initData."""
    return TelegramUtils.get_miniapp_url()
