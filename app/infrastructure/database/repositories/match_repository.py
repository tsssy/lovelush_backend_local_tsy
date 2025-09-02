"""Match record repository for storing and retrieving individual match records."""

from datetime import datetime, time, timedelta, timezone
from typing import List, Optional

from bson import ObjectId

from app.core.logging import get_logger
from app.domain.models.chatroom import (
    MatchRecord,
    MatchRecordCreate,
    MatchRecordUpdate,
    MatchStatus,
    MatchType,
)
from app.infrastructure.database.repositories.base_repository import (
    BaseRepository,
    BaseRepositoryInterface,
)

logger = get_logger(__name__)


class MatchRecordRepositoryInterface(
    BaseRepositoryInterface[MatchRecord, MatchRecordCreate, MatchRecordUpdate]
):
    """Match record repository interface for individual match records."""

    # Individual match record methods
    async def get_available_matches(
        self, user_id: str, limit: int = 50
    ) -> List[MatchRecord]:
        """Get user's available matches (not consumed/expired)."""
        raise NotImplementedError

    async def get_available_matches_by_type(
        self, user_id: str, match_type: MatchType
    ) -> List[MatchRecord]:
        """Get user's available matches of specific type."""
        raise NotImplementedError

    async def consume_match(self, match_id: str, user_id: str) -> bool:
        """Mark a match as consumed by user."""
        raise NotImplementedError

    async def get_match_by_candidate(
        self, user_id: str, sub_account_id: str
    ) -> Optional[MatchRecord]:
        """Get available match for specific candidate."""
        raise NotImplementedError

    # Match granting methods
    async def grant_initial_matches(
        self, user_id: str, sub_account_ids: List[str], credits_per_match: int = 0
    ) -> List[MatchRecord]:
        """Grant initial matches to user."""
        raise NotImplementedError

    async def grant_daily_free_match(
        self, user_id: str, sub_account_id: str, expires_at: datetime
    ) -> MatchRecord:
        """Grant daily free match to user."""
        raise NotImplementedError

    async def grant_paid_match(
        self, user_id: str, sub_account_id: str, credits_consumed: int
    ) -> MatchRecord:
        """Grant paid match to user."""
        raise NotImplementedError

    # Analytics and status methods
    async def get_user_match_history(
        self, user_id: str, limit: int = 50
    ) -> List[MatchRecord]:
        """Get user's complete match history."""
        raise NotImplementedError

    async def get_match_counts_by_type(self, user_id: str) -> dict:
        """Get count of matches by type for user."""
        raise NotImplementedError

    async def has_daily_match_today(self, user_id: str) -> bool:
        """Check if user already got daily match today."""
        raise NotImplementedError

    async def get_total_matches_consumed(self, user_id: str) -> int:
        """Get total number of matches consumed by user."""
        raise NotImplementedError

    async def expire_old_matches(self, before_date: datetime) -> int:
        """Expire matches older than given date."""
        raise NotImplementedError


class MatchRecordRepository(
    BaseRepository[MatchRecord, MatchRecordCreate, MatchRecordUpdate],
    MatchRecordRepositoryInterface,
):
    """MongoDB repository for individual match records."""

    def __init__(self):
        super().__init__("match_records", MatchRecord)

    async def get_available_matches(
        self, user_id: str, limit: int = 50
    ) -> List[MatchRecord]:
        """Get user's available matches (not consumed/expired)."""
        try:
            now = datetime.now(timezone.utc)
            query = {
                "user_id": user_id,
                "status": MatchStatus.AVAILABLE,
                "$or": [
                    {"expires_at": None},  # No expiration
                    {"expires_at": {"$gt": now}},  # Not expired
                ],
            }

            cursor = self.collection.find(query).sort("created_at", -1).limit(limit)

            match_docs = await cursor.to_list(length=limit)
            return [
                MatchRecord(**self._convert_doc_ids_to_strings(doc))
                for doc in match_docs
            ]
        except Exception as e:
            logger.error(f"Failed to get available matches for user {user_id}: {e}")
            return []

    async def get_available_matches_by_type(
        self, user_id: str, match_type: MatchType
    ) -> List[MatchRecord]:
        """Get user's available matches of specific type."""
        try:
            now = datetime.now(timezone.utc)
            query = {
                "user_id": user_id,
                "match_type": match_type,
                "status": MatchStatus.AVAILABLE,
                "$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}],
            }

            cursor = self.collection.find(query).sort("created_at", -1)
            match_docs = await cursor.to_list(length=None)

            return [
                MatchRecord(**self._convert_doc_ids_to_strings(doc))
                for doc in match_docs
            ]
        except Exception as e:
            logger.error(
                f"Failed to get available matches by type {match_type} for user {user_id}: {e}"
            )
            return []

    async def consume_match(self, match_id: str, user_id: str) -> bool:
        """Mark a match as consumed by user."""
        try:
            now = datetime.now(timezone.utc)
            result = await self.collection.update_one(
                {
                    "_id": ObjectId(match_id),
                    "user_id": user_id,
                    "status": MatchStatus.AVAILABLE,
                },
                {
                    "$set": {
                        "status": MatchStatus.CONSUMED,
                        "consumed_at": now,
                        "updated_at": now,
                    }
                },
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"Match {match_id} consumed by user {user_id}")
            else:
                logger.warning(f"Failed to consume match {match_id} for user {user_id}")

            return success
        except Exception as e:
            logger.error(f"Failed to consume match {match_id} for user {user_id}: {e}")
            return False

    async def get_match_by_candidate(
        self, user_id: str, sub_account_id: str
    ) -> Optional[MatchRecord]:
        """Get available match for specific candidate."""
        try:
            now = datetime.now(timezone.utc)
            query = {
                "user_id": user_id,
                "sub_account_id": sub_account_id,
                "status": MatchStatus.AVAILABLE,
                "$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}],
            }

            doc = await self.collection.find_one(query)
            if doc:
                return MatchRecord(**self._convert_doc_ids_to_strings(doc))
            return None
        except Exception as e:
            logger.error(
                f"Failed to get match by candidate {sub_account_id} for user {user_id}: {e}"
            )
            return None

    # Match granting methods
    async def grant_initial_matches(
        self, user_id: str, sub_account_ids: List[str], credits_per_match: int = 0
    ) -> List[MatchRecord]:
        """Grant initial matches to user."""
        try:
            matches = []
            for sub_account_id in sub_account_ids:
                match_data = MatchRecordCreate(
                    user_id=user_id,
                    match_type=MatchType.INITIAL,
                    sub_account_id=sub_account_id,
                    status=MatchStatus.AVAILABLE,
                    credits_consumed=credits_per_match,
                )
                match = await self.create(match_data)
                matches.append(match)

            logger.info(f"Granted {len(matches)} initial matches to user {user_id}")
            return matches
        except Exception as e:
            logger.error(f"Failed to grant initial matches to user {user_id}: {e}")
            return []

    async def grant_daily_free_match(
        self, user_id: str, sub_account_id: str, expires_at: datetime
    ) -> MatchRecord:
        """Grant daily free match to user."""
        try:
            match_data = MatchRecordCreate(
                user_id=user_id,
                match_type=MatchType.DAILY_FREE,
                sub_account_id=sub_account_id,
                status=MatchStatus.AVAILABLE,
                credits_consumed=0,
                expires_at=expires_at,
            )

            match = await self.create(match_data)
            logger.info(f"Granted daily free match to user {user_id}")
            return match
        except Exception as e:
            logger.error(f"Failed to grant daily free match to user {user_id}: {e}")
            raise

    async def grant_paid_match(
        self, user_id: str, sub_account_id: str, credits_consumed: int
    ) -> MatchRecord:
        """Grant paid match to user."""
        try:
            match_data = MatchRecordCreate(
                user_id=user_id,
                match_type=MatchType.PAID,
                sub_account_id=sub_account_id,
                status=MatchStatus.AVAILABLE,
                credits_consumed=credits_consumed,
            )

            match = await self.create(match_data)
            logger.info(
                f"Granted paid match to user {user_id} for {credits_consumed} credits"
            )
            return match
        except Exception as e:
            logger.error(f"Failed to grant paid match to user {user_id}: {e}")
            raise

    # Analytics and status methods
    async def get_user_match_history(
        self, user_id: str, limit: int = 50
    ) -> List[MatchRecord]:
        """Get user's complete match history."""
        try:
            cursor = (
                self.collection.find({"user_id": user_id})
                .sort("created_at", -1)
                .limit(limit)
            )

            match_docs = await cursor.to_list(length=limit)
            return [
                MatchRecord(**self._convert_doc_ids_to_strings(doc))
                for doc in match_docs
            ]
        except Exception as e:
            logger.error(f"Failed to get user match history for user {user_id}: {e}")
            return []

    async def get_match_counts_by_type(self, user_id: str) -> dict:
        """Get count of matches by type for user."""
        try:
            pipeline = [
                {"$match": {"user_id": user_id}},
                {
                    "$group": {
                        "_id": "$match_type",
                        "total": {"$sum": 1},
                        "available": {
                            "$sum": {
                                "$cond": [
                                    {"$eq": ["$status", MatchStatus.AVAILABLE]},
                                    1,
                                    0,
                                ]
                            }
                        },
                        "consumed": {
                            "$sum": {
                                "$cond": [
                                    {"$eq": ["$status", MatchStatus.CONSUMED]},
                                    1,
                                    0,
                                ]
                            }
                        },
                    }
                },
            ]

            cursor = self.collection.aggregate(pipeline)
            results = await cursor.to_list(length=None)

            # Convert to dict format
            counts = {}
            for result in results:
                match_type = result["_id"]
                counts[match_type] = {
                    "total": result["total"],
                    "available": result["available"],
                    "consumed": result["consumed"],
                }

            return counts
        except Exception as e:
            logger.error(f"Failed to get match counts by type for user {user_id}: {e}")
            return {}

    async def has_daily_match_today(self, user_id: str) -> bool:
        """Check if user already got daily match today."""
        try:
            today = datetime.now(timezone.utc).date()
            tomorrow = today + timedelta(days=1)

            today_start = datetime.combine(today, time(0, 0, 0), tzinfo=timezone.utc)
            tomorrow_start = datetime.combine(
                tomorrow, time(0, 0, 0), tzinfo=timezone.utc
            )

            count = await self.collection.count_documents(
                {
                    "user_id": user_id,
                    "match_type": MatchType.DAILY_FREE,
                    "created_at": {"$gte": today_start, "$lt": tomorrow_start},
                }
            )

            return count > 0
        except Exception as e:
            logger.error(f"Failed to check daily match for user {user_id}: {e}")
            return False

    async def get_total_matches_consumed(self, user_id: str) -> int:
        """Get total number of matches consumed by user."""
        try:
            count = await self.collection.count_documents(
                {"user_id": user_id, "status": MatchStatus.CONSUMED}
            )
            return count
        except Exception as e:
            logger.error(
                f"Failed to get total matches consumed for user {user_id}: {e}"
            )
            return 0

    async def expire_old_matches(self, before_date: datetime) -> int:
        """Expire matches older than given date."""
        try:
            result = await self.collection.update_many(
                {"expires_at": {"$lt": before_date}, "status": MatchStatus.AVAILABLE},
                {
                    "$set": {
                        "status": MatchStatus.EXPIRED,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

            expired_count = result.modified_count
            if expired_count > 0:
                logger.info(f"Expired {expired_count} old matches")

            return expired_count
        except Exception as e:
            logger.error(f"Failed to expire old matches: {e}")
            return 0
