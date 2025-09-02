"""Service for app settings business logic and operations."""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.models.settings import (
    AppSettings,
    AppSettingsCreate,
    AppSettingsResponse,
    AppSettingsUpdate,
    CoinConfiguration,
    MatchConfiguration,
    MessageConfiguration,
    UserSettingsResponse,
)
from app.infrastructure.database.repositories.app_settings_repository import (
    AppSettingsRepository,
)

logger = get_logger(__name__)


class AppSettingsService:
    """Service for handling app settings business logic."""

    def __init__(
        self, app_settings_repository: Optional[AppSettingsRepository] = None
    ) -> None:
        """
        Initialize AppSettingsService with required dependencies.

        Args:
            app_settings_repository: Repository for settings operations
        """
        self.app_settings_repository = (
            app_settings_repository or AppSettingsRepository()
        )

    async def create_settings(self, request: AppSettingsCreate) -> AppSettingsResponse:
        """
        Create new app settings with business validation.

        Args:
            request: AppSettingsCreate with settings data

        Returns:
            AppSettingsResponse with created settings

        Raises:
            ValidationError: If validation fails
        """
        try:
            # Validate unique name
            existing = await self.app_settings_repository.get_by_name(request.name)
            if existing:
                raise ValidationError(
                    f"Settings with name '{request.name}' already exist"
                )

            # If this is set as default or active, validate business rules
            if request.is_default:
                await self._ensure_single_default(None)

            if request.is_active:
                await self._ensure_single_active(None)

            # Validate configuration values
            self._validate_configurations(request)

            # Create settings
            settings = await self.app_settings_repository.create(request)

            logger.info(f"App settings created: {settings.name} (ID: {settings.id})")
            return self._to_response(settings)

        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating app settings: {e}")
            raise ValidationError(f"Failed to create settings: {str(e)}")

    async def get_settings(self, settings_id: str) -> AppSettingsResponse:
        """
        Get app settings by ID.

        Args:
            settings_id: ID of the settings

        Returns:
            AppSettingsResponse with settings data

        Raises:
            NotFoundError: If settings not found
        """
        settings = await self.app_settings_repository.get_by_id(settings_id)
        if not settings:
            raise NotFoundError(f"Settings {settings_id} not found")

        return self._to_response(settings)

    async def get_active_settings(self) -> AppSettingsResponse:
        """
        Get current active settings.

        Returns:
            AppSettingsResponse with active settings

        Raises:
            NotFoundError: If no active settings found
        """
        settings = await self.app_settings_repository.get_active_settings()
        if not settings:
            # Try to create default settings if none exist
            settings = (
                await self.app_settings_repository.create_default_settings_if_none()
            )
            if not settings:
                raise NotFoundError(
                    "No active settings found and failed to create default"
                )

        return self._to_response(settings)

    async def get_default_settings(self) -> AppSettingsResponse:
        """
        Get default settings.

        Returns:
            AppSettingsResponse with default settings

        Raises:
            NotFoundError: If no default settings found
        """
        settings = await self.app_settings_repository.get_default_settings()
        if not settings:
            raise NotFoundError("No default settings found")

        return self._to_response(settings)

    async def list_settings(
        self, include_inactive: bool = False, limit: int = 50, offset: int = 0
    ) -> List[AppSettingsResponse]:
        """
        Get list of settings with optional filtering.

        Args:
            include_inactive: Whether to include inactive settings
            limit: Maximum number of settings to return
            offset: Number of settings to skip

        Returns:
            List of AppSettingsResponse
        """
        settings_list = await self.app_settings_repository.get_all_settings(
            include_inactive
        )

        # Apply manual pagination (since repository doesn't support it yet)
        paginated_list = settings_list[offset : offset + limit]

        return [self._to_response(settings) for settings in paginated_list]

    async def update_settings(
        self, settings_id: str, request: AppSettingsUpdate
    ) -> AppSettingsResponse:
        """
        Update app settings with business validation.

        Args:
            settings_id: ID of settings to update
            request: AppSettingsUpdate with update data

        Returns:
            AppSettingsResponse with updated settings

        Raises:
            NotFoundError: If settings not found
            ValidationError: If validation fails
        """
        try:
            # Get existing settings
            existing_settings = await self.app_settings_repository.get_by_id(
                settings_id
            )
            if not existing_settings:
                raise NotFoundError(f"Settings {settings_id} not found")

            # Validate name uniqueness if changing name
            if request.name and request.name != existing_settings.name:
                name_exists = await self.app_settings_repository.get_by_name(
                    request.name
                )
                if name_exists:
                    raise ValidationError(
                        f"Settings with name '{request.name}' already exist"
                    )

            # Handle default/active flag changes
            if request.is_default is True:
                await self._ensure_single_default(settings_id)

            if request.is_active is True:
                await self._ensure_single_active(settings_id)

            # Validate configuration updates
            if any([request.coin_config, request.message_config, request.match_config]):
                # Create temporary settings for validation
                temp_data = existing_settings.model_dump()
                update_data = request.model_dump(exclude_none=True)
                temp_data.update(update_data)
                temp_settings = AppSettingsCreate(**temp_data)
                self._validate_configurations(temp_settings)

            # Update timestamp
            update_data = request.model_dump(exclude_none=True)
            update_data["updated_at"] = datetime.now(timezone.utc)

            # Perform update
            updated_settings = await self.app_settings_repository.update(
                settings_id, AppSettingsUpdate(**update_data)
            )
            if not updated_settings:
                raise NotFoundError(f"Settings {settings_id} not found")

            logger.info(f"App settings updated: {settings_id}")
            return self._to_response(updated_settings)

        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating settings {settings_id}: {e}")
            raise ValidationError(f"Failed to update settings: {str(e)}")

    async def delete_settings(self, settings_id: str) -> bool:
        """
        Delete app settings (soft delete).

        Args:
            settings_id: ID of settings to delete

        Returns:
            True if successful

        Raises:
            NotFoundError: If settings not found
            ValidationError: If trying to delete active/default settings
        """
        try:
            settings = await self.app_settings_repository.get_by_id(settings_id)
            if not settings:
                raise NotFoundError(f"Settings {settings_id} not found")

            # Prevent deletion of active or default settings
            if settings.is_active:
                raise ValidationError(
                    "Cannot delete active settings. Set another settings as active first."
                )

            if settings.is_default:
                raise ValidationError(
                    "Cannot delete default settings. Set another settings as default first."
                )

            # Perform soft delete
            success = await self.app_settings_repository.delete(settings_id)

            if success:
                logger.info(f"App settings deleted: {settings_id}")

            return success

        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting settings {settings_id}: {e}")
            raise ValidationError(f"Failed to delete settings: {str(e)}")

    async def activate_settings(self, settings_id: str) -> AppSettingsResponse:
        """
        Set specific settings as active.

        Args:
            settings_id: ID of settings to activate

        Returns:
            AppSettingsResponse with activated settings

        Raises:
            NotFoundError: If settings not found
            ValidationError: If activation fails
        """
        # Verify settings exist
        settings = await self.app_settings_repository.get_by_id(settings_id)
        if not settings:
            raise NotFoundError(f"Settings {settings_id} not found")

        # Set as active
        success = await self.app_settings_repository.set_as_active(settings_id)
        if not success:
            raise ValidationError("Failed to activate settings")

        # Return updated settings
        updated_settings = await self.app_settings_repository.get_by_id(settings_id)
        if not updated_settings:
            raise NotFoundError(f"Settings {settings_id} not found")

        logger.info(f"Settings activated: {settings_id}")
        return self._to_response(updated_settings)

    async def set_default_settings(self, settings_id: str) -> AppSettingsResponse:
        """
        Set specific settings as default.

        Args:
            settings_id: ID of settings to set as default

        Returns:
            AppSettingsResponse with default settings

        Raises:
            NotFoundError: If settings not found
            ValidationError: If operation fails
        """
        # Verify settings exist
        settings = await self.app_settings_repository.get_by_id(settings_id)
        if not settings:
            raise NotFoundError(f"Settings {settings_id} not found")

        # Set as default
        success = await self.app_settings_repository.set_as_default(settings_id)
        if not success:
            raise ValidationError("Failed to set as default settings")

        # Return updated settings
        updated_settings = await self.app_settings_repository.get_by_id(settings_id)
        if not updated_settings:
            raise NotFoundError(f"Settings {settings_id} not found")

        logger.info(f"Default settings set: {settings_id}")
        return self._to_response(updated_settings)

    async def get_settings_by_name(self, name: str) -> AppSettingsResponse:
        """
        Get settings by name.

        Args:
            name: Name of the settings

        Returns:
            AppSettingsResponse with settings data

        Raises:
            NotFoundError: If settings not found
        """
        settings = await self.app_settings_repository.get_by_name(name)
        if not settings:
            raise NotFoundError(f"Settings with name '{name}' not found")

        return self._to_response(settings)

    # Configuration getters for other services
    async def get_coin_config(self) -> CoinConfiguration:
        """Get current coin configuration."""
        settings = await self.app_settings_repository.get_active_settings()
        return settings.coin_config if settings else CoinConfiguration()

    async def get_message_config(self) -> MessageConfiguration:
        """Get current message configuration."""
        settings = await self.app_settings_repository.get_active_settings()
        return settings.message_config if settings else MessageConfiguration()

    async def get_match_config(self) -> MatchConfiguration:
        """Get current match configuration."""
        settings = await self.app_settings_repository.get_active_settings()
        return settings.match_config if settings else MatchConfiguration()

    async def get_user_settings(self) -> UserSettingsResponse:
        """
        Get user-specific settings with common configuration values.

        Returns:
            UserSettingsResponse with cost settings and initial values
        """
        settings = await self.app_settings_repository.get_active_settings()

        if not settings:
            # Return default values if no active settings found
            coin_config = CoinConfiguration()
            message_config = MessageConfiguration()
            match_config = MatchConfiguration()
        else:
            coin_config = settings.coin_config
            message_config = settings.message_config
            match_config = settings.match_config

        return UserSettingsResponse(
            cost_per_message=message_config.cost_per_message,
            cost_per_match=match_config.cost_per_match,
            initial_free_coins=coin_config.initial_free_coins,
            initial_free_messages=message_config.initial_free_messages,
            initial_free_matches=match_config.initial_free_matches,
            daily_free_matches=match_config.daily_free_matches,
        )

    def _validate_configurations(self, settings: AppSettingsCreate) -> None:
        """
        Validate configuration values for business rules.

        Args:
            settings: Settings to validate

        Raises:
            ValidationError: If validation fails
        """
        # Coin configuration validation
        if settings.coin_config.initial_free_coins < 0:
            raise ValidationError("Initial free coins cannot be negative")

        # Message configuration validation
        if settings.message_config.cost_per_message < 0:
            raise ValidationError("Message cost cannot be negative")

        if settings.message_config.initial_free_messages < 0:
            raise ValidationError("Initial free messages cannot be negative")

        # Match configuration validation
        if settings.match_config.cost_per_match < 0:
            raise ValidationError("Match cost cannot be negative")

        if settings.match_config.initial_free_matches < 0:
            raise ValidationError("Initial free matches cannot be negative")

        if settings.match_config.daily_free_matches < 0:
            raise ValidationError("Daily free matches cannot be negative")

        # Business logic validation
        if (
            settings.message_config.cost_per_message > 0
            and settings.coin_config.initial_free_coins
            < settings.message_config.cost_per_message
        ):
            logger.warning(
                f"Initial coins ({settings.coin_config.initial_free_coins}) is less than "
                f"message cost ({settings.message_config.cost_per_message}). Users may not be able to send messages."
            )

    async def _ensure_single_default(self, exclude_id: Optional[str] = None) -> None:
        """Ensure only one default settings exists."""
        # This is handled in repository.set_as_default()
        pass

    async def _ensure_single_active(self, exclude_id: Optional[str] = None) -> None:
        """Ensure only one active settings exists."""
        # This is handled in repository.set_as_active()
        pass

    def _to_response(self, settings: AppSettings) -> AppSettingsResponse:
        """Convert AppSettings to AppSettingsResponse."""
        return AppSettingsResponse(
            _id=settings.id,
            name=settings.name,
            description=settings.description,
            coin_config=settings.coin_config,
            message_config=settings.message_config,
            match_config=settings.match_config,
            is_active=settings.is_active,
            is_default=settings.is_default,
            metadata=settings.metadata,
            created_at=settings.created_at,
            updated_at=settings.updated_at,
        )
