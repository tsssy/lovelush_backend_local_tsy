"""Background job service for match system maintenance tasks."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.logging import get_logger
from app.domain.services.app_settings_service import AppSettingsService
from app.infrastructure.database.repositories.match_repository import (
    MatchRecordRepository,
)

logger = get_logger(__name__)


class MatchMaintenanceService:
    """Service for maintaining match system health through background jobs."""

    def __init__(
        self,
        match_repository: Optional[MatchRecordRepository] = None,
        app_settings_service: Optional[AppSettingsService] = None,
    ):
        """Initialize maintenance service with dependencies."""
        self.match_repository = match_repository or MatchRecordRepository()
        self.app_settings_service = app_settings_service or AppSettingsService()

    async def expire_old_matches(self) -> int:
        """
        Expire matches that have passed their expiration date.

        This job should be run periodically to clean up expired daily free matches
        and maintain database hygiene.

        Returns:
            Number of matches expired
        """
        try:
            now = datetime.now(timezone.utc)
            expired_count = await self.match_repository.expire_old_matches(now)

            if expired_count > 0:
                logger.info(f"Expired {expired_count} old matches")
            else:
                logger.debug("No matches to expire")

            return expired_count

        except Exception as e:
            logger.error(f"Failed to expire old matches: {e}")
            return 0

    async def cleanup_old_match_records(self, days_old: int = 30) -> int:
        """
        Clean up very old consumed match records for database optimization.

        Args:
            days_old: Remove consumed matches older than this many days

        Returns:
            Number of records cleaned up
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)

            # This would be a soft delete or archival operation
            # For now, just log what would be cleaned up
            collection = self.match_repository.collection

            old_consumed_count = await collection.count_documents(
                {"status": "consumed", "consumed_at": {"$lt": cutoff_date}}
            )

            if old_consumed_count > 0:
                logger.info(
                    f"Found {old_consumed_count} old consumed matches that could be archived"
                )
                # TODO: Implement archival strategy if needed

            return old_consumed_count

        except Exception as e:
            logger.error(f"Failed to cleanup old match records: {e}")
            return 0

    async def get_match_system_health(self) -> dict:
        """
        Get health statistics for the match system.

        Returns:
            Dictionary with system health metrics
        """
        try:
            collection = self.match_repository.collection
            now = datetime.now(timezone.utc)

            # Get overall statistics
            total_matches = await collection.count_documents({})
            available_matches = await collection.count_documents(
                {"status": "available"}
            )
            consumed_matches = await collection.count_documents({"status": "consumed"})
            expired_matches = await collection.count_documents({"status": "expired"})

            # Get matches expiring soon (next 24 hours)
            tomorrow = now + timedelta(days=1)
            expiring_soon = await collection.count_documents(
                {"status": "available", "expires_at": {"$gte": now, "$lt": tomorrow}}
            )

            # Get daily match statistics
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_matches = await collection.count_documents(
                {"match_type": "daily_free", "created_at": {"$gte": today_start}}
            )

            health_stats = {
                "timestamp": now.isoformat(),
                "total_matches": total_matches,
                "available_matches": available_matches,
                "consumed_matches": consumed_matches,
                "expired_matches": expired_matches,
                "expiring_soon": expiring_soon,
                "daily_matches_today": today_matches,
                "system_status": (
                    "healthy" if available_matches > 0 else "attention_needed"
                ),
            }

            logger.info(f"Match system health check completed: {health_stats}")
            return health_stats

        except Exception as e:
            logger.error(f"Failed to get match system health: {e}")
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "system_status": "error",
                "error": str(e),
            }

    async def run_daily_maintenance(self) -> dict:
        """
        Run all daily maintenance tasks for the match system.

        This method can be called by a scheduler or cron job once per day.

        Returns:
            Summary of maintenance tasks performed
        """
        logger.info("Starting daily match system maintenance")

        results = {"started_at": datetime.now(timezone.utc).isoformat(), "tasks": {}}

        try:
            # 1. Expire old matches
            logger.debug("Running match expiration cleanup")
            expired_count = await self.expire_old_matches()
            results["tasks"]["expire_matches"] = {
                "status": "success",
                "matches_expired": expired_count,
            }

            # 2. Clean up old records
            logger.debug("Running old record cleanup check")
            old_records = await self.cleanup_old_match_records()
            results["tasks"]["cleanup_old_records"] = {
                "status": "success",
                "records_found": old_records,
            }

            # 3. Health check
            logger.debug("Running system health check")
            health = await self.get_match_system_health()
            results["tasks"]["health_check"] = {
                "status": "success",
                "health_data": health,
            }

            results["completed_at"] = datetime.now(timezone.utc).isoformat()
            results["overall_status"] = "success"

            logger.info("Daily match system maintenance completed successfully")

        except Exception as e:
            logger.error(f"Daily maintenance failed: {e}")
            results["completed_at"] = datetime.now(timezone.utc).isoformat()
            results["overall_status"] = "error"
            results["error"] = str(e)

        return results

    async def run_hourly_maintenance(self) -> dict:
        """
        Run hourly maintenance tasks for the match system.

        This method can be called by a scheduler every hour for lighter maintenance.

        Returns:
            Summary of maintenance tasks performed
        """
        logger.debug("Starting hourly match system maintenance")

        results = {"started_at": datetime.now(timezone.utc).isoformat(), "tasks": {}}

        try:
            # Just expire old matches hourly
            expired_count = await self.expire_old_matches()
            results["tasks"]["expire_matches"] = {
                "status": "success",
                "matches_expired": expired_count,
            }

            results["completed_at"] = datetime.now(timezone.utc).isoformat()
            results["overall_status"] = "success"

            if expired_count > 0:
                logger.info(f"Hourly maintenance: expired {expired_count} matches")
            else:
                logger.debug("Hourly maintenance: no matches to expire")

        except Exception as e:
            logger.error(f"Hourly maintenance failed: {e}")
            results["completed_at"] = datetime.now(timezone.utc).isoformat()
            results["overall_status"] = "error"
            results["error"] = str(e)

        return results
