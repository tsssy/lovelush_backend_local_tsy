"""Message repository for handling message storage and retrieval."""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.logging import get_logger
from app.domain.models.message import Message, MessageCreate, MessageUpdate
from app.infrastructure.database.repositories.base_repository import (
    BaseRepository,
    BaseRepositoryInterface,
)

logger = get_logger(__name__)


class MessageRepositoryInterface(
    BaseRepositoryInterface[Message, MessageCreate, MessageUpdate]
):
    """Message repository interface with domain-specific methods."""

    async def get_chatroom_messages(
        self, chatroom_id: str, limit: int = 50, skip: int = 0
    ) -> List[Message]:
        """Get messages for a chatroom with pagination."""
        raise NotImplementedError

    async def get_messages_after_timestamp(
        self, chatroom_id: str, after_timestamp: datetime
    ) -> List[Message]:
        """Get messages after a specific timestamp for real-time sync."""
        raise NotImplementedError

    async def mark_message_as_read(self, message_id: str, reader_id: str) -> bool:
        """Mark a message as read by a user."""
        raise NotImplementedError

    async def get_unread_message_count(self, chatroom_id: str, user_id: str) -> int:
        """Get count of unread messages for a user in a chatroom."""
        raise NotImplementedError

    async def delete_chatroom_messages(self, chatroom_id: str) -> bool:
        """Delete all messages in a chatroom (when chatroom is deleted)."""
        raise NotImplementedError

    async def get_latest_message(self, chatroom_id: str) -> Optional[Message]:
        """Get the latest message in a chatroom."""
        raise NotImplementedError

    async def count_chatroom_messages(self, chatroom_id: str) -> int:
        """Get total count of messages in a chatroom."""
        raise NotImplementedError


class MessageRepository(
    BaseRepository[Message, MessageCreate, MessageUpdate], MessageRepositoryInterface
):
    """MongoDB message repository implementation."""

    def __init__(self):
        super().__init__("messages", Message)

    async def get_chatroom_non_system_messages(
        self, chatroom_id: str, limit: int = 50, skip: int = 0
    ) -> List[Message]:
        """Get non-system messages for a chatroom with pagination (newest first)."""
        try:
            # Optimized query that can use compound index (chatroom_id, sender_type, created_at)
            cursor = (
                self.collection.find(
                    {
                        "chatroom_id": chatroom_id,
                        "sender_type": {
                            "$in": ["user", "agent"]
                        },  # Exclude system messages
                        "is_deleted": {"$ne": True},  # Simplified soft deletion check
                    }
                )
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
            )

            messages = []
            async for doc in cursor:
                try:
                    # Convert ObjectIds to strings before creating model instance
                    converted_doc = self._convert_doc_ids_to_strings(doc)
                    message = Message(**converted_doc)
                    messages.append(message)
                except Exception as e:
                    logger.error(
                        f"Failed to parse message document: {e}",
                        extra={"doc_id": doc.get("_id")},
                    )
                    continue

            logger.debug(
                f"Retrieved {len(messages)} non-system messages for chatroom {chatroom_id}"
            )
            return messages

        except Exception as e:
            logger.error(
                f"Failed to get non-system chatroom messages for {chatroom_id}: {e}"
            )
            return []

    async def get_chatroom_messages(
        self, chatroom_id: str, limit: int = 50, skip: int = 0
    ) -> List[Message]:
        """Get messages for a chatroom with pagination (newest first)."""
        try:
            # Simplified query that can use the compound index (chatroom_id, created_at)
            cursor = (
                self.collection.find(
                    {
                        "chatroom_id": chatroom_id,
                        "is_deleted": {"$ne": True},  # Simplified soft deletion check
                    }
                )
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
            )

            messages = []
            async for doc in cursor:
                try:
                    # Convert ObjectIds to strings before creating model instance
                    converted_doc = self._convert_doc_ids_to_strings(doc)
                    message = Message(**converted_doc)
                    messages.append(message)
                except Exception as e:
                    logger.error(
                        f"Failed to parse message document: {e}",
                        extra={"doc_id": doc.get("_id")},
                    )
                    continue

            logger.debug(
                f"Retrieved {len(messages)} messages for chatroom {chatroom_id}"
            )
            return messages

        except Exception as e:
            logger.error(f"Failed to get chatroom messages for {chatroom_id}: {e}")
            return []

    async def get_messages_after_timestamp(
        self, chatroom_id: str, after_timestamp: datetime
    ) -> List[Message]:
        """Get messages after a specific timestamp for real-time sync."""
        try:
            cursor = self.collection.find(
                {
                    "chatroom_id": chatroom_id,
                    "created_at": {"$gt": after_timestamp},
                    "is_deleted": {"$ne": True},  # Simplified soft deletion check
                }
            ).sort("created_at", 1)

            messages = []
            async for doc in cursor:
                try:
                    # Convert ObjectIds to strings before creating model instance
                    converted_doc = self._convert_doc_ids_to_strings(doc)
                    message = Message(**converted_doc)
                    messages.append(message)
                except Exception as e:
                    logger.error(
                        f"Failed to parse message document: {e}",
                        extra={"doc_id": doc.get("_id")},
                    )
                    continue

            logger.debug(
                f"Retrieved {len(messages)} messages after {after_timestamp} for chatroom {chatroom_id}"
            )
            return messages

        except Exception as e:
            logger.error(
                f"Failed to get messages after timestamp for {chatroom_id}: {e}"
            )
            return []

    async def mark_message_as_read(self, message_id: str, reader_id: str) -> bool:
        """Mark a message as read by adding reader_id to read_by array."""
        try:
            result = await self.collection.update_one(
                {
                    "_id": self._convert_to_object_id(message_id),
                    "read_by": {"$ne": reader_id},  # Only update if not already read
                },
                {
                    "$push": {"read_by": reader_id},
                    "$set": {"updated_at": datetime.now(timezone.utc)},
                },
            )

            success = result.modified_count > 0
            if success:
                logger.debug(f"Message {message_id} marked as read by {reader_id}")
            return success

        except Exception as e:
            logger.error(
                f"Failed to mark message {message_id} as read by {reader_id}: {e}"
            )
            return False

    async def get_unread_message_count(self, chatroom_id: str, user_id: str) -> int:
        """Get count of unread messages for a user in a chatroom."""
        try:
            count = await self.collection.count_documents(
                {
                    "chatroom_id": chatroom_id,
                    "sender_id": {"$ne": user_id},  # Don't count own messages
                    "read_by": {"$ne": user_id},  # Not in read_by array
                    "is_deleted": {"$ne": True},  # Simplified soft deletion check
                }
            )

            logger.debug(
                f"User {user_id} has {count} unread messages in chatroom {chatroom_id}"
            )
            return count

        except Exception as e:
            logger.error(
                f"Failed to get unread message count for user {user_id} in chatroom {chatroom_id}: {e}"
            )
            return 0

    async def delete_chatroom_messages(self, chatroom_id: str) -> bool:
        """Soft delete all messages in a chatroom."""
        try:
            result = await self.collection.update_many(
                {"chatroom_id": chatroom_id},
                {
                    "$set": {
                        "is_deleted": True,
                        "deleted_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

            success = result.acknowledged
            logger.info(
                f"Deleted {result.modified_count} messages in chatroom {chatroom_id}"
            )
            return success

        except Exception as e:
            logger.error(f"Failed to delete messages in chatroom {chatroom_id}: {e}")
            return False

    async def get_latest_message(self, chatroom_id: str) -> Optional[Message]:
        """Get the most recent message in a chatroom."""
        try:
            doc = await self.collection.find_one(
                {
                    "chatroom_id": chatroom_id,
                    "is_deleted": {"$ne": True},  # Simplified soft deletion check
                },
                sort=[("created_at", -1)],
            )

            if not doc:
                return None

            # Convert ObjectIds to strings before creating model instance
            converted_doc = self._convert_doc_ids_to_strings(doc)
            message = Message(**converted_doc)
            logger.debug(f"Retrieved latest message for chatroom {chatroom_id}")
            return message

        except Exception as e:
            logger.error(
                f"Failed to get latest message for chatroom {chatroom_id}: {e}"
            )
            return None

    async def count_chatroom_messages(self, chatroom_id: str) -> int:
        """Get total count of messages in a chatroom."""
        try:
            count = await self.collection.count_documents(
                {
                    "chatroom_id": chatroom_id,
                    "is_deleted": {"$ne": True},  # Simplified soft deletion check
                }
            )
            logger.debug(f"Total {count} messages in chatroom {chatroom_id}")
            return count
        except Exception as e:
            logger.error(f"Failed to count messages in chatroom {chatroom_id}: {e}")
            return 0

    async def create(self, data: MessageCreate) -> Message:
        """Create a new message with proper validation."""
        try:
            # Convert to dict - keep IDs as strings
            message_data = data.model_dump()
            if not message_data.get("sender_id"):
                message_data["sender_id"] = None

            # Add timestamps
            now = datetime.now(timezone.utc)
            message_data["created_at"] = now
            message_data["updated_at"] = now

            # Insert into database
            result = await self.collection.insert_one(message_data)

            # Retrieve created message and convert ObjectIds to strings
            created_doc = await self.collection.find_one({"_id": result.inserted_id})
            if not created_doc:
                raise Exception(
                    f"Failed to retrieve created message with ID: {result.inserted_id}"
                )

            # Convert ObjectIds to strings before creating model instance
            converted_doc = self._convert_doc_ids_to_strings(created_doc)
            message = Message(**converted_doc)

            logger.info(
                f"Message created successfully",
                extra={
                    "message_id": str(message.id),
                    "chatroom_id": str(message.chatroom_id),
                    "sender_type": message.sender_type.value,
                },
            )

            return message

        except Exception as e:
            logger.error(f"Failed to create message: {e}")
            raise
