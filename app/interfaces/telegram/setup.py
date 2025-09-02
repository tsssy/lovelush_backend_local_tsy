"""Telegram bot setup and management utilities."""

import asyncio

from app.core.config.settings import settings
from app.core.initializer import ComponentInitializer
from app.core.logging import get_logger
from app.interfaces.telegram.command.config import command_config
from app.interfaces.telegram.manager import telegram_workflow_manager
from app.interfaces.telegram.services.sdk_service import telegram_sdk_service
from app.interfaces.telegram.workflows.onboarding_workflow import (
    TelegramOnboardingWorkflow,
)
from app.interfaces.telegram.workflows.products_workflow import (
    TelegramProductsWorkflow,
)
from app.interfaces.telegram.workflows.restart_workflow import (
    TelegramRestartWorkflow,
)

logger = get_logger(__name__)


class TelegramBotSetup:
    """Setup and configuration for Telegram bot."""

    @staticmethod
    async def initialize_bot() -> bool:
        """Initialize bot without webhook (webhook will be set later)."""
        try:
            if not settings.telegram_bot_token:
                logger.warning("Telegram bot token not configured")
                return False

            # Register workflows
            await TelegramBotSetup.register_workflows()

            # Get bot info to verify token
            bot_info = await telegram_sdk_service.get_me()
            if not bot_info.success:
                logger.error(f"Failed to get bot info: {bot_info.error_description}")
                return False

            logger.info(f"Bot info: {bot_info.data}")

            # Set up bot commands
            await TelegramBotSetup.setup_bot_commands()

            # Start webhook setup task in background if URL is configured
            if settings.telegram_webhook_url:
                asyncio.create_task(TelegramBotSetup._setup_webhook_with_delay())

            return True

        except Exception as e:
            logger.error(f"Error initializing bot: {e}")
            return False

    @staticmethod
    async def _setup_webhook_with_delay() -> None:
        """Set up webhook with delay and retry mechanism."""
        delay = 10  # Initial delay in seconds
        max_retries = 5
        retry_count = 0

        logger.info(
            f"Starting delayed webhook setup (delay: {delay}s, max_retries: {max_retries})"
        )

        # Initial delay to allow container networking to stabilize
        await asyncio.sleep(delay)

        while retry_count < max_retries:
            try:
                webhook_response = await telegram_sdk_service.set_webhook()
                if webhook_response.success:
                    logger.info("Delayed webhook setup successful")
                    return
                else:
                    retry_count += 1
                    logger.warning(
                        f"Failed to set webhook (attempt {retry_count}/{max_retries}): "
                        f"{webhook_response.error_description}"
                    )

            except Exception as e:
                retry_count += 1
                logger.warning(
                    f"Webhook setup error (attempt {retry_count}/{max_retries}): {e}"
                )

            if retry_count < max_retries:
                # Exponential backoff: 15, 30, 60, 120 seconds
                retry_delay = 15 * (2 ** (retry_count - 1))
                logger.info(f"Retrying webhook setup in {retry_delay}s...")
                await asyncio.sleep(retry_delay)

        logger.error(
            "Failed to set webhook after all retry attempts. Bot will work without webhook."
        )

    @staticmethod
    async def setup_webhook_now() -> bool:
        """Immediately attempt to set webhook (for manual triggering)."""
        if not settings.telegram_webhook_url:
            logger.warning("Telegram webhook URL not configured")
            return False

        try:
            webhook_response = await telegram_sdk_service.set_webhook()
            if webhook_response.success:
                logger.info("Manual webhook setup successful")
                return True
            else:
                logger.error(
                    f"Manual webhook setup failed: {webhook_response.error_description}"
                )
                return False
        except Exception as e:
            logger.error(f"Manual webhook setup error: {e}")
            return False

    @staticmethod
    async def register_workflows():
        """Register all workflows with the workflow manager."""
        telegram_workflow_manager.register_workflow(
            "onboarding", TelegramOnboardingWorkflow
        )
        telegram_workflow_manager.register_workflow("restart", TelegramRestartWorkflow)
        telegram_workflow_manager.register_workflow(
            "products", TelegramProductsWorkflow
        )
        logger.info("Telegram workflows registered successfully")

    @staticmethod
    async def setup_bot_commands():
        """Set up bot commands based on user commands only (global bot commands)."""
        # Only register USER commands as global bot commands
        # Admin commands will be validated at runtime by handlers
        from app.domain.models.user import UserRole

        command_definitions = command_config.get_allowed_command_definitions(
            UserRole.USER
        )
        commands = []

        for command, description in command_definitions.items():
            commands.append(
                {"command": command.replace("/", ""), "description": description}
            )

        if not commands:
            logger.warning("No commands to register - using default start command")
            commands = [{"command": "start", "description": "Start the bot"}]

        response = await telegram_sdk_service.set_my_commands(commands)
        if response.success:
            for cmd in commands:
                logger.info(f"Bot command registered: {cmd['command']}")
            logger.info("Bot commands set successfully")
        else:
            logger.error(f"Failed to set bot commands: {response.error_description}")

    @staticmethod
    async def cleanup_bot():
        """Cleanup bot resources."""
        try:
            # Delete webhook
            response = await telegram_sdk_service.delete_webhook()
            if response.success:
                logger.info("Webhook deleted successfully")
            else:
                logger.error(f"Failed to delete webhook: {response.error_description}")

            # Close the session
            await telegram_sdk_service.close()

        except Exception as e:
            logger.error(f"Error cleaning up bot: {e}")


class TelegramInitializer(ComponentInitializer):
    """Telegram bot component initializer."""

    def __init__(self, telegram_setup: TelegramBotSetup):
        self._telegram_setup = telegram_setup

    @property
    def name(self) -> str:
        return "Telegram Bot"

    async def initialize(self) -> None:
        """Initialize Telegram bot without webhook dependency."""
        if not settings.telegram_bot_token:
            logger.info(
                "Telegram bot token not configured - skipping Telegram bot initialization"
            )
            return

        success = await self._telegram_setup.initialize_bot()
        if not success:
            raise RuntimeError("Failed to initialize Telegram bot")

        # Log success message noting webhook will be set later
        if settings.telegram_webhook_url:
            logger.info(
                "Telegram bot initialized successfully - webhook will be configured in background"
            )
        else:
            logger.info(
                "Telegram bot initialized successfully - no webhook URL configured"
            )

    async def cleanup(self) -> None:
        """Cleanup Telegram bot."""
        if not settings.telegram_bot_token:
            return
        await self._telegram_setup.cleanup_bot()


telegram_bot_setup = TelegramBotSetup()
telegram_initializer = TelegramInitializer(telegram_bot_setup)
