"""Centralized application component initializer."""

from abc import ABC, abstractmethod
from typing import List

from app.core.logging import get_logger

logger = get_logger(__name__)


class ComponentInitializer(ABC):
    """Abstract base class for component initializers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Component name for logging."""
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the component."""
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup the component."""
        pass


class ApplicationInitializer:
    """Centralized application initializer."""

    def __init__(self):
        self._initializers: List[ComponentInitializer] = []
        self._initialized_components: List[ComponentInitializer] = []

    def register_initializer(self, initializer: ComponentInitializer) -> None:
        """Register a component initializer."""
        self._initializers.append(initializer)

    async def initialize_all(self) -> None:
        """Initialize all registered components in order."""
        logger.info("Starting application component initialization...")

        for initializer in self._initializers:
            try:
                logger.info(f"Initializing {initializer.name}...")
                await initializer.initialize()
                self._initialized_components.append(initializer)
            except Exception as e:
                logger.error(f"Failed to initialize {initializer.name}: {e}")
                # Cleanup any components that were already initialized
                await self._cleanup_initialized()
                raise

        logger.info("All application components initialized successfully")

    async def cleanup_all(self) -> None:
        """Cleanup all initialized components in reverse order."""
        logger.info("Starting application component cleanup...")

        # Cleanup in reverse order
        for initializer in reversed(self._initialized_components):
            try:
                logger.info(f"Cleaning up {initializer.name}...")
                await initializer.cleanup()
                logger.info(f"{initializer.name} cleaned up successfully")
            except Exception as e:
                logger.error(f"Error cleaning up {initializer.name}: {e}")
                # Continue with other cleanup operations

        self._initialized_components.clear()
        logger.info("Application component cleanup completed")

    async def _cleanup_initialized(self) -> None:
        """Internal method to cleanup components during initialization failure."""
        logger.warning(
            "Cleaning up initialized components due to initialization failure..."
        )

        for initializer in reversed(self._initialized_components):
            try:
                await initializer.cleanup()
            except Exception as e:
                logger.error(
                    f"Error cleaning up {initializer.name} during rollback: {e}"
                )

        self._initialized_components.clear()


# Global application initializer instance
app_initializer = ApplicationInitializer()
