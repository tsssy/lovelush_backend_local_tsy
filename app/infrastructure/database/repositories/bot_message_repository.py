"""Bot message repository interface and implementation."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId

from app.core.logging import get_logger
from app.domain.models.common import PyObjectId
from app.infrastructure.database.repositories.base_repository import (
    BaseRepository,
    BaseRepositoryInterface,
)
from app.interfaces.telegram.models.bot_message import (
    BotMessage,
    BotMessageCreate,
    BotMessageUpdate,
    BotPlatform,
)

logger = get_logger(__name__)


class BotMessageRepositoryInterface(
    BaseRepositoryInterface[BotMessage, BotMessageCreate, BotMessageUpdate]
):
    """Bot message repository interface with domain-specific methods."""

    async def get_user_messages(
        self,
        user_id: str,
        platform: Optional[BotPlatform] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[BotMessage]:
        """Get bot messages for a specific user."""
        raise NotImplementedError

    async def mark_as_processed(
        self, message_id: str, processing_error: Optional[str] = None
    ) -> bool:
        """Mark bot message as processed."""
        raise NotImplementedError

    async def get_unprocessed_messages(
        self, platform: Optional[BotPlatform] = None, limit: int = 100
    ) -> List[BotMessage]:
        """Get unprocessed bot messages."""
        raise NotImplementedError


class BotMessageRepository(
    BaseRepository[BotMessage, BotMessageCreate, BotMessageUpdate],
    BotMessageRepositoryInterface,
):
    """MongoDB bot message repository implementation."""

    def __init__(self):
        super().__init__("bot_messages", BotMessage)

    async def create(self, data: BotMessageCreate) -> BotMessage:
        """Create a new bot message."""
        try:
            logger.debug(f"Creating new bot message for user: {data.user_id}")

            message_dict = data.model_dump()
            message_dict = self._add_timestamps(message_dict)

            # Create the BotMessage instance first (it will keep user_id as string)
            message = BotMessage(**message_dict)

            # For database insertion, convert user_id to ObjectId
            db_dict = message.model_dump(by_alias=True, exclude={"id"})
            db_dict["user_id"] = ObjectId(message.user_id)

            result = await self.collection.insert_one(db_dict)
            message.id = PyObjectId(result.inserted_id)

            logger.debug(f"Bot message created successfully with ID: {message.id}")
            return message
        except Exception as e:
            logger.error(f"Failed to create bot message: {e}")
            raise

    async def get_user_messages(
        self,
        user_id: str,
        platform: Optional[BotPlatform] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[BotMessage]:
        """Get bot messages for a specific user."""
        try:
            query: Dict[str, Any] = {"user_id": ObjectId(user_id)}
            if platform:
                query["platform"] = platform.value

            cursor = (
                self.collection.find(query)
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
            )

            messages = []
            async for message_doc in cursor:
                messages.append(BotMessage(**message_doc))

            return messages
        except Exception as e:
            logger.error(f"Failed to get user messages for user {user_id}: {e}")
            return []

    async def mark_as_processed(
        self, message_id: str, processing_error: Optional[str] = None
    ) -> bool:
        """Mark bot message as processed."""
        try:
            update_data = {
                "is_processed": True,
                "processed_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            if processing_error:
                update_data["processing_error"] = processing_error

            result = await self.collection.update_one(
                {"_id": ObjectId(message_id)}, {"$set": update_data}
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"Marked bot message as processed: {message_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to mark bot message as processed {message_id}: {e}")
            return False

    async def get_unprocessed_messages(
        self, platform: Optional[BotPlatform] = None, limit: int = 100
    ) -> List[BotMessage]:
        """Get unprocessed bot messages."""
        try:
            query: Dict[str, Any] = {"is_processed": False}
            if platform:
                query["platform"] = platform

            cursor = (
                self.collection.find(query)
                .sort("created_at", 1)  # Process oldest first
                .limit(limit)
            )

            messages = []
            async for message_doc in cursor:
                messages.append(BotMessage(**message_doc))

            return messages
        except Exception as e:
            logger.error(f"Failed to get unprocessed messages: {e}")
            return []
