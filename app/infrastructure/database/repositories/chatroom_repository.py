"""Chatroom repository for database operations."""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.logging import get_logger
from app.domain.models.chatroom import Chatroom, ChatroomCreate, ChatroomUpdate
from app.infrastructure.database.repositories.base_repository import (
    BaseRepository,
    BaseRepositoryInterface,
)

logger = get_logger(__name__)


class ChatroomRepositoryInterface(
    BaseRepositoryInterface[Chatroom, ChatroomCreate, ChatroomUpdate]
):
    """Chatroom repository interface with domain-specific methods."""

    async def get_existing_chatroom(
        self, user_id: str, sub_account_id: str
    ) -> Optional[Chatroom]:
        """Get existing active chatroom between user and sub-account."""
        raise NotImplementedError

    async def get_user_chatrooms(self, user_id: str, limit: int = 20) -> List[Chatroom]:
        """Get user's chatrooms."""
        raise NotImplementedError

    async def get_sub_account_chatrooms(
        self, sub_account_id: str, limit: int = 50
    ) -> List[Chatroom]:
        """Get sub-account's chatrooms."""
        raise NotImplementedError

    async def end_chatroom(self, chatroom_id: str) -> bool:
        """End a chatroom."""
        raise NotImplementedError

    async def update_last_activity(self, chatroom_id: str) -> bool:
        """Update chatroom's last activity timestamp."""
        raise NotImplementedError


class ChatroomRepository(
    BaseRepository[Chatroom, ChatroomCreate, ChatroomUpdate],
    ChatroomRepositoryInterface,
):
    """MongoDB chatroom repository implementation."""

    def __init__(self):
        super().__init__("chatrooms", Chatroom)

    def _generate_channel_name(self, chatroom_id: str) -> str:
        """Generate standardized channel name for pusher/soketi."""
        return f"presence-chatroom-{chatroom_id}"

    async def create_chatroom(self, chatroom_data: ChatroomCreate) -> Chatroom:
        """Create a new chatroom."""
        try:
            chatroom_dict = chatroom_data.model_dump()

            # Use the channel_name from ChatroomCreate or generate one if not provided
            channel_name = chatroom_dict.get("channel_name")
            if not channel_name:
                # Temporary channel name - will be updated after insertion
                channel_name = "temp"

            chatroom_dict.update(
                {
                    "status": "active",  # Set default status
                    "channel_name": channel_name,
                }
            )

            chatroom_dict = self._add_timestamps(chatroom_dict)

            # Create final data dict for database insertion
            final_data = chatroom_dict.copy()
            result = await self.collection.insert_one(final_data)
            chatroom_id = str(result.inserted_id)

            # Update with correct channel name using the generated ID
            standard_channel_name = self._generate_channel_name(chatroom_id)
            await self.collection.update_one(
                {"_id": result.inserted_id},
                {"$set": {"channel_name": standard_channel_name}},
            )

            # Create response chatroom with the generated ID and correct channel name
            chatroom_dict["_id"] = chatroom_id
            chatroom_dict["channel_name"] = standard_channel_name
            final_chatroom = Chatroom(**chatroom_dict)
            logger.info(
                f"Chatroom created with ID: {final_chatroom.id} and channel: {standard_channel_name}"
            )
            return final_chatroom
        except Exception as e:
            logger.error(f"Failed to create chatroom: {e}")
            raise

    async def get_chatroom_by_id(self, chatroom_id: str) -> Optional[Chatroom]:
        """Alias for get_by_id method for service compatibility."""
        return await self.get_by_id(chatroom_id)

    async def get_existing_chatroom(
        self, user_id: str, sub_account_id: str
    ) -> Optional[Chatroom]:
        """Get existing chatroom between user and sub-account (any status)."""
        try:
            # Find most recent chatroom between user and sub-account (any status)
            chatroom_data = await self.collection.find_one(
                {
                    "user_id": user_id,
                    "sub_account_id": sub_account_id,
                    "deleted_at": None,
                },
                sort=[("created_at", -1)],  # Get most recent chatroom
            )
            return (
                Chatroom(**self._convert_doc_ids_to_strings(chatroom_data))
                if chatroom_data
                else None
            )
        except Exception as e:
            logger.error(f"Failed to get existing chatroom: {e}")
            return None

    async def get_user_chatrooms(self, user_id: str, limit: int = 20) -> List[Chatroom]:
        """Get user's chatrooms, most recent first."""
        try:
            cursor = (
                self.collection.find({"user_id": user_id, "deleted_at": None})
                .sort("created_at", -1)
                .limit(limit)
            )

            chatrooms = []
            async for chatroom_data in cursor:
                converted_data = self._convert_doc_ids_to_strings(chatroom_data)
                chatrooms.append(Chatroom(**converted_data))
            return chatrooms
        except Exception as e:
            logger.error(f"Failed to get user chatrooms: {e}")
            return []

    async def end_chatroom(self, chatroom_id: str) -> bool:
        """End a chatroom."""
        try:
            obj_id = self._convert_to_object_id(chatroom_id)
            result = await self.collection.update_one(
                {"_id": obj_id, "status": "active"},
                {
                    "$set": {
                        "status": "ended",
                        "ended_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            success = result.modified_count > 0
            if success:
                logger.info(f"Chatroom ended: {chatroom_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to end chatroom: {e}")
            return False

    async def get_sub_account_chatrooms(
        self, sub_account_id: str, limit: int = 50
    ) -> List[Chatroom]:
        """Get sub-account's chatrooms for agent dashboard."""
        try:
            # Use string comparison for sub_account_id
            cursor = (
                self.collection.find(
                    {
                        "sub_account_id": sub_account_id,
                        "status": "active",
                        "deleted_at": None,
                    }
                )
                .sort("last_activity_at", -1)
                .limit(limit)
            )

            chatrooms = []
            async for chatroom_data in cursor:
                converted_data = self._convert_doc_ids_to_strings(chatroom_data)
                chatrooms.append(Chatroom(**converted_data))
            return chatrooms
        except Exception as e:
            logger.error(f"Failed to get sub-account chatrooms: {e}")
            return []

    async def update_last_activity(self, chatroom_id: str) -> bool:
        """Update chatroom's last activity timestamp."""
        try:
            obj_id = self._convert_to_object_id(chatroom_id)
            result = await self.collection.update_one(
                {"_id": obj_id},
                {
                    "$set": {
                        "last_activity_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            success = result.modified_count > 0
            if success:
                logger.debug(f"Updated last activity for chatroom {chatroom_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to update last activity: {e}")
            return False
