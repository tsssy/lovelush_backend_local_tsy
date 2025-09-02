"""MongoDB database configuration and client setup."""

from urllib.parse import urlparse, urlunparse

from motor.core import AgnosticDatabase
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config.settings import settings
from app.core.initializer import ComponentInitializer
from app.core.logging import get_logger

logger = get_logger(__name__)


class MongoDB:
    """MongoDB database client manager."""

    def __init__(self):
        self.client = None
        self.database = None

    async def connect(self) -> None:
        """Connect to MongoDB database."""
        try:
            # Build connection URI with authentication if provided
            connection_uri = settings.mongo_uri

            if settings.mongodb_username and settings.mongodb_password:
                # Parse the URI to insert credentials
                parsed = urlparse(connection_uri)

                # Build netloc with credentials
                netloc = f"{settings.mongodb_username}:{settings.mongodb_password}@{parsed.hostname}"
                if parsed.port:
                    netloc += f":{parsed.port}"

                # Reconstruct the URI with credentials
                connection_uri = urlunparse(
                    (
                        parsed.scheme,
                        netloc,
                        parsed.path,
                        parsed.params,
                        parsed.query,
                        parsed.fragment,
                    )
                )

            self.client = AsyncIOMotorClient(
                connection_uri,
                maxPoolSize=10,
                minPoolSize=1,
                serverSelectionTimeoutMS=5000,
            )
            self.database = self.client[settings.mongodb_name]

            # Test connection
            await self.client.admin.command("ismaster")
            logger.info("Successfully connected to MongoDB")

        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from MongoDB database."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")

    def get_database(self) -> AgnosticDatabase:
        """Get database instance."""
        if self.database is None:
            raise RuntimeError("Database not initialized. Call connect() first.")
        return self.database


class MongoDBInitializer(ComponentInitializer):
    """MongoDB component initializer."""

    def __init__(self, mongodb: MongoDB):
        self._mongodb = mongodb

    @property
    def name(self) -> str:
        return "MongoDB"

    async def initialize(self) -> None:
        """Initialize MongoDB connection."""
        await self._mongodb.connect()

    async def cleanup(self) -> None:
        """Cleanup MongoDB connection."""
        await self._mongodb.disconnect()


# Global database instance
mongodb = MongoDB()
mongodb_initializer = MongoDBInitializer(mongodb)
