"""User repository interface and implementation."""

from typing import List, Optional, Union

from app.core.logging import get_logger
from app.domain.models.user import User, UserCreate, UserCreateByTelegram, UserUpdate
from app.infrastructure.database.repositories.base_repository import (
    BaseRepository,
    BaseRepositoryInterface,
)

logger = get_logger(__name__)


class UserRepositoryInterface(BaseRepositoryInterface[User, UserCreate, UserUpdate]):
    """User repository interface with domain-specific methods."""

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        raise NotImplementedError

    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        raise NotImplementedError

    async def get_by_telegram_id(self, telegram_id: str) -> Optional[User]:
        """Get user by Telegram ID."""
        raise NotImplementedError

    async def get_by_telegram_id_include_deleted(
        self, telegram_id: str
    ) -> Optional[User]:
        """Get user by Telegram ID including deleted users."""
        raise NotImplementedError

    async def create_with_password(
        self, user_data: UserCreate, hashed_password: Optional[str] = None
    ) -> User:
        """Create a new user with password handling."""
        raise NotImplementedError


class UserRepository(
    BaseRepository[User, UserCreate, UserUpdate], UserRepositoryInterface
):
    """MongoDB user repository implementation."""

    def __init__(self):
        super().__init__("users", User)

    async def create_with_password(
        self,
        user_data: Union[UserCreate, UserCreateByTelegram],
        hashed_password: Optional[str] = None,
    ) -> User:
        """Create a new user with password handling."""
        logger.debug(f"Creating new user with username: {user_data.username}")

        user_dict = user_data.model_dump()

        # Handle password for different user types
        if hashed_password:
            user_dict["hashed_password"] = hashed_password
        elif isinstance(user_data, UserCreateByTelegram):
            # Empty password for Telegram users
            user_dict["hashed_password"] = ""
        else:
            # For regular users, password is required
            raise ValueError("Password is required for user creation")

        # Remove plain password from dict
        user_dict.pop("password", None)

        user_dict = self._add_timestamps(user_dict)
        user = User(**user_dict)

        # Prepare document for insertion, excluding null values for partial index fields
        doc_to_insert = user.model_dump(by_alias=True, exclude={"id"})

        # Remove null email to prevent issues with partial unique index
        if doc_to_insert.get("email") is None:
            doc_to_insert.pop("email", None)

        # Remove null telegram_id to prevent issues with partial unique index
        if doc_to_insert.get("telegram_id") is None:
            doc_to_insert.pop("telegram_id", None)

        result = await self.collection.insert_one(doc_to_insert)
        user.id = result.inserted_id

        logger.info(f"User created successfully with ID: {user.id}")
        return user

    # Keep create method for compatibility, delegate to create_with_password
    async def create(
        self,
        data: Union[UserCreate, UserCreateByTelegram],
        hashed_password: Optional[str] = None,
    ) -> User:
        """Create a new user."""
        return await self.create_with_password(data, hashed_password)

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email (excludes deleted users)."""
        try:
            user_doc = await self.collection.find_one(
                {"email": email, "deleted_at": None}
            )
            return User(**user_doc) if user_doc else None
        except Exception as e:
            logger.error(f"Failed to get user by email {email}: {e}")
            return None

    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username (excludes deleted users)."""
        try:
            user_doc = await self.collection.find_one(
                {"username": username, "deleted_at": None}
            )
            return User(**user_doc) if user_doc else None
        except Exception as e:
            logger.error(f"Failed to get user by username {username}: {e}")
            return None

    async def get_by_telegram_id(self, telegram_id: str) -> Optional[User]:
        """Get user by Telegram ID (excludes deleted users)."""
        try:
            user_doc = await self.collection.find_one(
                {"telegram_id": telegram_id, "deleted_at": None}
            )
            return User(**user_doc) if user_doc else None
        except Exception as e:
            logger.error(f"Failed to get user by telegram_id {telegram_id}: {e}")
            return None

    async def get_by_telegram_id_include_deleted(
        self, telegram_id: str
    ) -> Optional[User]:
        """Get user by Telegram ID including deleted users."""
        try:
            user_doc = await self.collection.find_one({"telegram_id": telegram_id})
            return User(**user_doc) if user_doc else None
        except Exception as e:
            logger.error(
                f"Failed to get user by telegram_id (include deleted) {telegram_id}: {e}"
            )
            return None

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Get all users with pagination (excludes deleted users)."""
        try:
            cursor = (
                self.collection.find({"deleted_at": None})
                .skip(skip)
                .limit(limit)
                .sort("created_at", -1)
            )
            users = []
            async for user_doc in cursor:
                users.append(User(**user_doc))
            return users
        except Exception as e:
            logger.error(f"Failed to get all users: {e}")
            return []

    async def count_all(self) -> int:
        """Count total number of users (excludes deleted users)."""
        try:
            return await self.collection.count_documents({"deleted_at": None})
        except Exception as e:
            logger.error(f"Failed to count users: {e}")
            return 0
