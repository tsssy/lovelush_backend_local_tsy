"""Application startup and initialization service."""

from pathlib import Path

from app.core.config.settings import settings
from app.core.initializer import app_initializer
from app.core.logging import get_logger
from app.infrastructure.database.db_init import db_init_initializer
from app.infrastructure.database.mongodb import mongodb_initializer
from app.integrations.pusher.client import pusher_initializer
from app.integrations.s3 import s3_initializer
from app.interfaces.telegram.setup import telegram_initializer

logger = get_logger(__name__)


class AppStartupService:
    """Service for application startup initialization."""

    # Project root path (calculated once)
    PROJECT_ROOT = Path(__file__).parent.parent.parent

    # Banner template (loaded once)
    _banner_template: str | None = None

    def __init__(self):
        self._register_initializers()

    def _register_initializers(self) -> None:
        """Register all component initializers in proper order."""
        # Register in dependency order:
        # 1. MongoDB (database connection first)
        # 2. Database Indexes (depends on MongoDB)
        # 3. S3 Client (independent service)
        # 4. Pusher Client (independent service)
        # 5. Telegram Bot (depends on database for workflows)

        app_initializer.register_initializer(mongodb_initializer)
        app_initializer.register_initializer(db_init_initializer)
        app_initializer.register_initializer(s3_initializer)
        app_initializer.register_initializer(pusher_initializer)
        app_initializer.register_initializer(telegram_initializer)

    def _load_banner_template(self) -> str:
        """Load banner template from file (cached)."""
        if self._banner_template is None:
            try:
                banner_path = self.PROJECT_ROOT / "app" / "resources" / "banner.txt"
                with open(banner_path, "r", encoding="utf-8") as f:
                    self._banner_template = f.read()
            except Exception as e:
                logger.warning(f"Could not load banner file: {e}")
                self._banner_template = "\n=== {app_name} v{server_version} ===\n"

        return self._banner_template

    def _print_banner(self) -> None:
        """Print startup banner."""
        try:
            # Load banner template (cached)
            banner_template = self._load_banner_template()

            # Format banner with version number
            banner = banner_template.format(
                app_name=settings.app_name, server_version=f"{settings.app_version:<16}"
            )
            print(banner)

        except Exception as e:
            logger.warning(f"Could not format banner: {e}")
            # Fallback to simple text banner
            print(f"\n=== {settings.app_name} v{settings.app_version} ===\n")

    async def initialize_application(self) -> None:
        """Initialize the application on startup."""
        # Print startup banner
        self._print_banner()

        logger.info("-> Starting application initialization")

        try:
            # Initialize all registered components using the centralized initializer
            await app_initializer.initialize_all()

            logger.info("Application initialized successfully<-")

        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            raise

    async def shutdown_application(self) -> None:
        """Shutdown the application gracefully."""
        logger.info("Starting application shutdown...")

        try:
            # Cleanup all initialized components using the centralized initializer
            await app_initializer.cleanup_all()

            logger.info("Application shutdown completed successfully")

        except Exception as e:
            logger.error(f"Error during application shutdown: {e}")
            raise


# Global application startup service
app_startup_service = AppStartupService()
