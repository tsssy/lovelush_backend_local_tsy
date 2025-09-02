"""Repository for app settings database operations."""

from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.domain.models.settings import AppSettings, AppSettingsCreate, AppSettingsUpdate
from app.infrastructure.database.repositories.base_repository import (
    BaseRepository,
    BaseRepositoryInterface,
)

logger = get_logger(__name__)


class AppSettingsRepositoryInterface(
    BaseRepositoryInterface[AppSettings, AppSettingsCreate, AppSettingsUpdate]
):
    """Interface for app settings repository operations."""

    async def get_active_settings(self) -> Optional[AppSettings]:
        """Get current active settings."""
        pass

    async def get_default_settings(self) -> Optional[AppSettings]:
        """Get default settings."""
        pass

    async def set_as_active(self, settings_id: str) -> bool:
        """Set specific settings as active (deactivates others)."""
        raise NotImplementedError

    async def set_as_default(self, settings_id: str) -> bool:
        """Set specific settings as default (removes default from others)."""
        raise NotImplementedError

    async def get_by_name(self, name: str) -> Optional[AppSettings]:
        """Get settings by name."""
        raise NotImplementedError


class AppSettingsRepository(
    BaseRepository[AppSettings, AppSettingsCreate, AppSettingsUpdate],
    AppSettingsRepositoryInterface,
):
    """Repository for app settings database operations."""

    def __init__(self):
        super().__init__("app_settings", AppSettings)

    async def get_active_settings(self) -> Optional[AppSettings]:
        """
        Get current active settings.

        Returns:
            Active AppSettings if found, None otherwise
        """
        try:
            doc = await self.collection.find_one(
                {"is_active": True, "deleted_at": None},
                sort=[
                    ("updated_at", -1)
                ],  # Get most recently updated if multiple active
            )

            if doc:
                settings = AppSettings(**doc)
                logger.debug(f"Active settings found: {settings.name}")
                return settings

            logger.debug("No active settings found")
            return None

        except Exception as e:
            logger.error(f"Error getting active settings: {e}")
            return None

    async def get_default_settings(self) -> Optional[AppSettings]:
        """
        Get default settings.

        Returns:
            Default AppSettings if found, None otherwise
        """
        try:
            doc = await self.collection.find_one(
                {"is_default": True, "deleted_at": None}
            )

            if doc:
                settings = AppSettings(**doc)
                logger.debug(f"Default settings found: {settings.name}")
                return settings

            logger.debug("No default settings found")
            return None

        except Exception as e:
            logger.error(f"Error getting default settings: {e}")
            return None

    async def set_as_active(self, settings_id: str) -> bool:
        """
        Set specific settings as active (deactivates all others).

        Args:
            settings_id: ID of settings to activate

        Returns:
            True if successful, False otherwise
        """
        try:
            # First, deactivate all other settings
            await self.collection.update_many(
                {"deleted_at": None}, {"$set": {"is_active": False}}
            )

            # Then activate the specified settings
            result = await self.collection.update_one(
                {"_id": self._convert_to_object_id(settings_id), "deleted_at": None},
                {"$set": {"is_active": True}},
            )

            if result.modified_count > 0:
                logger.info(f"Settings {settings_id} set as active")
                return True
            else:
                logger.warning(
                    f"Failed to activate settings {settings_id} - not found or already active"
                )
                return False

        except Exception as e:
            logger.error(f"Error setting settings {settings_id} as active: {e}")
            return False

    async def set_as_default(self, settings_id: str) -> bool:
        """
        Set specific settings as default (unsets all others).

        Args:
            settings_id: ID of settings to set as default

        Returns:
            True if successful, False otherwise
        """
        try:
            # First, unset default flag from all settings
            await self.collection.update_many(
                {"deleted_at": None}, {"$set": {"is_default": False}}
            )

            # Then set the specified settings as default
            result = await self.collection.update_one(
                {"_id": self._convert_to_object_id(settings_id), "deleted_at": None},
                {"$set": {"is_default": True}},
            )

            if result.modified_count > 0:
                logger.info(f"Settings {settings_id} set as default")
                return True
            else:
                logger.warning(
                    f"Failed to set settings {settings_id} as default - not found"
                )
                return False

        except Exception as e:
            logger.error(f"Error setting settings {settings_id} as default: {e}")
            return False

    async def get_by_name(self, name: str) -> Optional[AppSettings]:
        """
        Get settings by name.

        Args:
            name: Name of the settings

        Returns:
            AppSettings if found, None otherwise
        """
        try:
            doc = await self.collection.find_one({"name": name, "deleted_at": None})

            if doc:
                settings = AppSettings(**doc)
                logger.debug(f"Settings found by name '{name}': {settings.id}")
                return settings

            return None

        except Exception as e:
            logger.error(f"Error getting settings by name '{name}': {e}")
            return None

    async def get_all_settings(
        self, include_inactive: bool = False
    ) -> List[AppSettings]:
        """
        Get all settings with optional filtering.

        Args:
            include_inactive: Whether to include inactive settings

        Returns:
            List of AppSettings
        """
        try:
            filter_criteria: Dict[str, Any] = {"deleted_at": None}
            if not include_inactive:
                filter_criteria["is_active"] = True

            cursor = self.collection.find(filter_criteria).sort("updated_at", -1)

            settings_list = []
            async for doc in cursor:
                try:
                    settings = AppSettings(**doc)
                    settings_list.append(settings)
                except Exception as e:
                    logger.warning(f"Failed to parse settings document: {e}")
                    continue

            logger.debug(f"Retrieved {len(settings_list)} settings")
            return settings_list

        except Exception as e:
            logger.error(f"Error getting all settings: {e}")
            return []

    async def create_default_settings_if_none(self) -> Optional[AppSettings]:
        """
        Create default settings if no settings exist.

        Returns:
            Created default settings or None if creation failed
        """
        try:
            # Check if any settings exist
            existing_count = await self.collection.count_documents({"deleted_at": None})

            if existing_count > 0:
                logger.debug("Settings already exist, skipping default creation")
                return None

            # Create default settings
            default_settings = AppSettingsCreate(
                name="default",
                description="Default app settings",
                is_active=True,
                is_default=True,
                metadata=None,
            )

            created_settings = await self.create(default_settings)
            logger.info(f"Created default settings: {created_settings.id}")
            return created_settings

        except Exception as e:
            logger.error(f"Error creating default settings: {e}")
            return None

    async def find_by_criteria(
        self,
        criteria: Dict[str, Any],
        skip: int = 0,
        limit: int = 50,
        sort_field: str = "updated_at",
        sort_direction: int = -1,
    ) -> List[AppSettings]:
        """
        Find settings by custom criteria.

        Args:
            criteria: MongoDB query criteria
            limit: Maximum number of results
            skip: Number of results to skip
            sort_field: Field to sort by
            sort_direction: Sort direction (1 for asc, -1 for desc)

        Returns:
            List of AppSettings matching criteria
        """
        try:
            # Always exclude soft-deleted records
            criteria["deleted_at"] = None

            cursor = (
                self.collection.find(criteria)
                .sort(sort_field, sort_direction)
                .skip(skip)
                .limit(limit)
            )

            settings_list = []
            async for doc in cursor:
                try:
                    settings = AppSettings(**doc)
                    settings_list.append(settings)
                except Exception as e:
                    logger.warning(f"Failed to parse settings document: {e}")
                    continue

            return settings_list

        except Exception as e:
            logger.error(f"Error finding settings by criteria: {e}")
            return []
