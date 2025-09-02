"""User message stats repository for database operations."""

from datetime import datetime, timezone
from typing import Optional

from app.core.logging import get_logger
from app.domain.models.user_message_stats import (
    UserMessageStats,
    UserMessageStatsCreate,
    UserMessageStatsUpdate,
)
from app.infrastructure.database.repositories.base_repository import (
    BaseRepository,
    BaseRepositoryInterface,
)

logger = get_logger(__name__)


class UserMessageStatsRepositoryInterface(
    BaseRepositoryInterface[
        UserMessageStats, UserMessageStatsCreate, UserMessageStatsUpdate
    ]
):
    """User message stats repository interface with domain-specific methods."""

    async def get_user_stats(self, user_id: str) -> Optional[UserMessageStats]:
        """Get user message stats by user ID."""
        raise NotImplementedError

    async def get_or_create_user_stats(self, user_id: str) -> UserMessageStats:
        """Get existing user message stats or create new one."""
        raise NotImplementedError

    async def increment_free_messages_used(self, user_id: str) -> bool:
        """Increment the count of free messages used by user."""
        raise NotImplementedError

    async def reset_daily_free_messages(self, user_id: str) -> bool:
        """Reset daily free messages for user."""
        raise NotImplementedError


class UserMessageStatsRepository(BaseRepository, UserMessageStatsRepositoryInterface):
    """User message stats repository implementation."""

    def __init__(self):
        super().__init__("user_message_stats", UserMessageStats)

    async def get_user_stats(self, user_id: str) -> Optional[UserMessageStats]:
        """Get user message stats by user ID."""
        try:
            doc = await self.collection.find_one(
                {"user_id": user_id, "deleted_at": None}
            )
            return UserMessageStats(**doc) if doc else None
        except Exception as e:
            logger.error(f"Error getting user message stats: {e}")
            return None

    async def get_or_create_user_stats(self, user_id: str) -> UserMessageStats:
        """Get existing user message stats or create new one."""
        try:
            # Check if user stats already exist
            existing_stats = await self.get_user_stats(user_id)
            if existing_stats:
                return existing_stats

            # Create new stats
            stats_create = UserMessageStatsCreate(user_id=user_id)
            stats = await self.create(stats_create)

            logger.info(
                "User message stats created",
                extra={"user_id": user_id, "stats_id": str(stats.id)},
            )

            return stats

        except Exception as e:
            logger.exception(f"Error getting or creating user message stats: {e}")
            raise

    async def increment_free_messages_used(self, user_id: str) -> bool:
        """Increment the count of free messages used by user."""
        try:
            # Get or create stats
            stats = await self.get_or_create_user_stats(user_id)

            # Check if daily reset is needed
            now = datetime.now(timezone.utc)
            if stats.is_reset_needed():
                # Reset the count and update reset date
                update_data = {
                    "free_messages_used": 1,  # Start with 1 for this message
                    "last_reset_date": now,
                    "updated_at": now,
                }
            else:
                # Just increment the count
                update_data = {
                    "free_messages_used": stats.free_messages_used + 1,
                    "updated_at": now,
                }

            result = await self.collection.update_one(
                {"_id": stats.id, "deleted_at": None}, {"$set": update_data}
            )

            if result.modified_count > 0:
                logger.debug(
                    "Free messages used incremented",
                    extra={
                        "user_id": user_id,
                        "new_count": update_data["free_messages_used"],
                        "reset_applied": stats.is_reset_needed(),
                    },
                )
                return True

            logger.warning(f"Failed to increment free messages used for user {user_id}")
            return False

        except Exception as e:
            logger.exception(f"Error incrementing free messages used: {e}")
            return False

    async def reset_daily_free_messages(self, user_id: str) -> bool:
        """Reset daily free messages for user."""
        try:
            now = datetime.now(timezone.utc)
            result = await self.collection.update_one(
                {"user_id": user_id, "deleted_at": None},
                {
                    "$set": {
                        "free_messages_used": 0,
                        "last_reset_date": now,
                        "updated_at": now,
                    }
                },
            )

            if result.modified_count > 0:
                logger.info(f"Daily free messages reset for user {user_id}")
                return True

            logger.warning(f"Failed to reset daily free messages for user {user_id}")
            return False

        except Exception as e:
            logger.exception(f"Error resetting daily free messages: {e}")
            return False
