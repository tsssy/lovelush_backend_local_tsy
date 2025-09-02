"""Pusher/Soketi client configuration and utilities."""

from typing import Any, Dict, Optional

import pusher

from app.core.config.settings import settings
from app.core.initializer import ComponentInitializer
from app.core.logging import get_logger

logger = get_logger(__name__)


class PusherClient:
    """Pusher/Soketi client wrapper."""

    def __init__(self):
        self.client: Optional[pusher.Pusher] = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the Pusher client."""
        if self._initialized:
            return

        app_id = settings.pusher_app_id
        self.client = pusher.Pusher(
            app_id=app_id,
            key=settings.pusher_key,
            secret=settings.pusher_secret,
            cluster=settings.pusher_cluster,
            ssl=settings.pusher_use_tls,
            host=settings.pusher_host,
            port=settings.pusher_port,
        )
        self._initialized = True

    def cleanup(self) -> None:
        """Cleanup the Pusher client."""
        self.client = None
        self._initialized = False

    def trigger(self, channel: str, event: str, data: Dict[str, Any]):
        """Trigger an event on a channel."""
        if not self._initialized or self.client is None:
            raise RuntimeError(
                "Pusher client not initialized. Call initialize() first."
            )
        return self.client.trigger(channel, event, data)

    def authenticate(
        self, channel: str, socket_id: str, custom_data: Optional[Dict[str, Any]] = None
    ) -> dict:
        """Authenticate a user for a private or presence channel."""
        if not self._initialized or self.client is None:
            raise RuntimeError(
                "Pusher client not initialized. Call initialize() first."
            )

        if channel.startswith("presence-"):
            return self.client.authenticate(
                channel=channel, socket_id=socket_id, custom_data=custom_data
            )
        else:
            return self.client.authenticate(channel=channel, socket_id=socket_id)

    def channel_info(
        self, channel: str, info: str = "user_count,subscription_count"
    ) -> Dict[str, Any]:
        """Get channel information."""
        if not self._initialized or self.client is None:
            raise RuntimeError(
                "Pusher client not initialized. Call initialize() first."
            )

        return self.client.channel_info(channel, attributes=info)

    def channel_users(self, channel: str) -> Dict[str, Any]:
        """Get users in a presence channel."""
        if not self._initialized or self.client is None:
            raise RuntimeError(
                "Pusher client not initialized. Call initialize() first."
            )

        return self.client.users_info(channel)


class PusherInitializer(ComponentInitializer):
    """Pusher client component initializer."""

    def __init__(self, pusher_client: PusherClient):
        self._pusher_client = pusher_client

    @property
    def name(self) -> str:
        return "Pusher Client"

    async def initialize(self) -> None:
        """Initialize Pusher client."""
        self._pusher_client.initialize()
        logger.info("Pusher client initialized successfully")

    async def cleanup(self) -> None:
        """Cleanup Pusher client."""
        self._pusher_client.cleanup()
        logger.info("Pusher client cleaned up successfully")


# Global instances
pusher_client = PusherClient()
pusher_initializer = PusherInitializer(pusher_client)
