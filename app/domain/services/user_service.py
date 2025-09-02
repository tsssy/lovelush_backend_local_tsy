"""User service for business logic."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from app.core.exceptions.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.models.pagination import PaginationParams, PaginationResponse
from app.domain.models.user import (
    OnboardingStatus,
    User,
    UserCreate,
    UserCreateByTelegram,
    UserResponse,
    UserUpdate,
)
from app.infrastructure.database.repositories.user_repository import UserRepository
from app.infrastructure.security.jwt_auth import get_password_hash, verify_password

logger = get_logger(__name__)


class UserService:
    """User service for handling business logic."""

    def __init__(self, user_repository: Optional[UserRepository] = None) -> None:
        self.user_repository = user_repository or UserRepository()

    async def create_user(
        self, user_data: Union[UserCreate, UserCreateByTelegram]
    ) -> UserResponse:
        """Create a new user."""
        # Check if user already exists by email (if provided)
        if hasattr(user_data, "email"):
            existing_user = await self.user_repository.get_by_email(
                getattr(user_data, "email")
            )
            if existing_user:
                raise ValidationError("Email already registered")
        # Check if user already exists by telegram ID (if provided)
        if hasattr(user_data, "telegram_id"):
            existing_user = await self.user_repository.get_by_telegram_id(
                getattr(user_data, "telegram_id")
            )
            if existing_user:
                raise ValidationError("Telegram ID already registered")

        existing_username = await self.user_repository.get_by_username(
            user_data.username
        )
        if existing_username:
            raise ValidationError("Username already taken")

        # Check if user exists by Telegram ID (if provided)
        if user_data.telegram_id:
            existing_telegram = await self.user_repository.get_by_telegram_id(
                user_data.telegram_id
            )
            if existing_telegram:
                raise ValidationError("Telegram ID already registered")

        # Hash password if provided
        hashed_password = None
        if hasattr(user_data, "password"):
            hashed_password = get_password_hash(getattr(user_data, "password"))

        # Create user
        user = await self.user_repository.create(user_data, hashed_password)

        return self._to_user_response(user)

    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password."""
        user = await self.user_repository.get_by_username(username)
        if not user:
            return None

        if not password or not user.hashed_password:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        return user

    async def authenticate_telegram_user(self, telegram_id: str) -> Optional[User]:
        """Authenticate user with Telegram ID."""
        return await self.user_repository.get_by_telegram_id(telegram_id)

    async def get_user_by_id(self, user_id: str) -> Optional[UserResponse]:
        """Get user by ID."""
        user = await self.user_repository.get_by_id(user_id)
        return self._to_user_response(user) if user else None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email (internal use)."""
        return await self.user_repository.get_by_email(email)

    async def get_user_by_username(self, username: str) -> Optional[UserResponse]:
        """Get user by username."""
        user = await self.user_repository.get_by_username(username)
        return self._to_user_response(user) if user else None

    async def get_user_by_telegram_id(self, telegram_id: str) -> Optional[UserResponse]:
        """Get user by Telegram ID."""
        user = await self.user_repository.get_by_telegram_id(telegram_id)
        return self._to_user_response(user) if user else None

    async def get_or_create_telegram_user(
        self, telegram_user_data: dict
    ) -> UserResponse:
        """Get existing user or create early user for Telegram interaction."""
        telegram_id = str(telegram_user_data.get("id"))

        # First check if user exists (including deleted users)
        existing_user = await self.user_repository.get_by_telegram_id_include_deleted(
            telegram_id
        )

        if existing_user:
            # If user was deleted, reactivate them
            if existing_user.deleted_at:
                logger.info(
                    "Reactivating previously deleted user",
                    extra={
                        "user_id": str(existing_user.id),
                        "username": existing_user.username,
                    },
                )

                reactivation_data: Dict[str, Any] = {
                    "is_active": True,
                    "deleted_at": None,
                    "onboarding_status": OnboardingStatus.NOT_STARTED,
                    "onboarding_completed_at": None,
                }

                reactivated_user = await self.user_repository.update_fields(
                    str(existing_user.id), reactivation_data
                )
                if reactivated_user:
                    return self._to_user_response(reactivated_user)
            else:
                # User exists and is active
                return self._to_user_response(existing_user)

        # Create new user with minimal data
        username = (
            telegram_user_data.get("username")
            or f"user_{telegram_id}"
            or f"telegram_{telegram_id[:8]}"
        )

        # Ensure username is unique (considering only active users)
        base_username = username
        counter = 1
        while await self.user_repository.get_by_username(username):
            username = f"{base_username}_{counter}"
            counter += 1

        user_create_data = UserCreateByTelegram(
            username=username,
            telegram_id=telegram_id,
            onboarding_status=OnboardingStatus.NOT_STARTED,
        )

        try:
            return await self.create_user(user_create_data)
        except ValidationError:
            # If creation fails due to race condition, try to get existing user again
            existing_user = await self.user_repository.get_by_telegram_id(telegram_id)
            if existing_user:
                return self._to_user_response(existing_user)
            raise

    async def update_onboarding_status(
        self, user_id: str, status: OnboardingStatus
    ) -> UserResponse:
        """Update user's onboarding status."""
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        update_data: Dict[str, Any] = {"onboarding_status": status}
        if status == OnboardingStatus.COMPLETED:

            update_data["onboarding_completed_at"] = datetime.now(timezone.utc)

        updated_user = await self.user_repository.update_fields(user_id, update_data)
        if not updated_user:
            raise NotFoundError("User not found")

        return self._to_user_response(updated_user)

    async def update_user(self, user_id: str, user_data: UserUpdate) -> UserResponse:
        """Update user information."""
        user = await self.user_repository.update(user_id, user_data)
        if not user:
            raise NotFoundError("User not found")

        return self._to_user_response(user)

    async def delete_user(self, user_id: str) -> bool:
        """Delete user."""
        success = await self.user_repository.delete(user_id)
        if not success:
            raise NotFoundError("User not found")

        return success

    async def get_users(self, pagination: PaginationParams) -> PaginationResponse:
        """Get all users with pagination."""
        users = await self.user_repository.get_all(pagination.skip, pagination.limit)
        total_count = await self.user_repository.count_all()
        user_responses = [self._to_user_response(user) for user in users]

        return PaginationResponse.create(
            items=user_responses,
            total_items=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def update_user_last_visited(
        self,
        user_id: str,
        last_visited_url: Optional[str] = None,
        last_visited_page: Optional[str] = None,
    ) -> bool:
        """
        Update user's last visited location and activity timestamp.

        Args:
            user_id: User ID to update
            last_visited_url: Last visited URL/route
            last_visited_page: Last visited page name

        Returns:
            bool: True if update was successful
        """
        try:
            update_data: Dict[str, Any] = {
                "last_activity_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            if last_visited_url is not None:
                update_data["last_visited_url"] = last_visited_url

            if last_visited_page is not None:
                update_data["last_visited_page"] = last_visited_page

            # Create UserUpdate with only the fields that exist in the model
            user_update_data = {}
            if last_visited_url is not None:
                user_update_data["last_visited_url"] = last_visited_url
            if last_visited_page is not None:
                user_update_data["last_visited_page"] = last_visited_page

            # Update via repository
            updated_user = await self.user_repository.update(
                user_id, UserUpdate(**user_update_data)
            )

            if updated_user:
                logger.info(
                    "User last visited info updated",
                    extra={
                        "user_id": user_id,
                        "last_visited_url": last_visited_url,
                        "last_visited_page": last_visited_page,
                    },
                )
                return True
            return False

        except Exception as e:
            logger.error(
                "Failed to update user last visited info",
                extra={"user_id": user_id, "error": str(e)},
            )
            return False

    async def update_user_login_info(self, user_id: str) -> bool:
        """
        Update user's last login timestamp.

        Args:
            user_id: User ID to update

        Returns:
            bool: True if update was successful
        """
        try:
            update_data: Dict[str, Any] = {
                "last_login": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            updated_user = await self.user_repository.update(
                user_id, UserUpdate(**update_data)
            )

            if updated_user:
                logger.info("User login info updated", extra={"user_id": user_id})
                return True
            return False

        except Exception as e:
            logger.error(
                "Failed to update user login info",
                extra={"user_id": user_id, "error": str(e)},
            )
            return False

    def _to_user_response(self, user: User) -> UserResponse:
        """Convert User model to UserResponse."""
        return UserResponse(
            _id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            bio=user.bio,
            age=user.age,
            location=user.location,
            gender=user.gender,
            avatar_url=user.avatar_url,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            last_login=user.last_login,
            last_visited_url=user.last_visited_url,
            last_visited_page=user.last_visited_page,
            last_activity_at=user.last_activity_at,
            telegram_id=user.telegram_id,
            onboarding_status=user.onboarding_status,
            onboarding_completed_at=user.onboarding_completed_at,
            deleted_at=user.deleted_at,
        )
