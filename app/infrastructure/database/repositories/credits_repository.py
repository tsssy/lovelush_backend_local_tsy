"""Credits repository for database operations."""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.logging import get_logger
from app.domain.models.credits import (
    CreditTransaction,
    TransactionReason,
    TransactionType,
    UserCredits,
    UserCreditsCreate,
    UserCreditsUpdate,
)
from app.infrastructure.database.repositories.base_repository import (
    BaseRepository,
    BaseRepositoryInterface,
)
from app.infrastructure.database.repositories.credit_transaction_repository import (
    CreditTransactionRepository,
)

logger = get_logger(__name__)


class CreditsRepositoryInterface(
    BaseRepositoryInterface[UserCredits, UserCreditsCreate, UserCreditsUpdate]
):
    """Credits repository interface with domain-specific methods."""

    async def get_user_credits(self, user_id: str) -> Optional[UserCredits]:
        """Get user credits by user ID."""
        raise NotImplementedError

    async def get_or_create_user_credits(self, user_id: str) -> UserCredits:
        """Get existing user credits or create new one."""
        raise NotImplementedError

    async def consume_credits(
        self,
        user_id: str,
        amount: int,
        reason: TransactionReason,
        reference_id: Optional[str] = None,
        reference_type: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """Consume credits from user account."""
        raise NotImplementedError

    async def add_credits(
        self,
        user_id: str,
        amount: int,
        reason: TransactionReason,
        reference_id: Optional[str] = None,
        reference_type: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """Add credits to user account."""
        raise NotImplementedError


class CreditsRepository(
    BaseRepository[UserCredits, UserCreditsCreate, UserCreditsUpdate],
    CreditsRepositoryInterface,
):
    """MongoDB credits repository implementation."""

    def __init__(
        self,
        credit_transaction_repository: Optional[CreditTransactionRepository] = None,
    ):
        super().__init__("user_credits", UserCredits)
        # Use dependency injection for transaction repository
        # Will be set by dependency container to avoid circular imports
        self._credit_transaction_repository = credit_transaction_repository

    @property
    def transactions_collection(self):
        """Get transactions collection from transaction repository."""
        if not self._credit_transaction_repository:
            raise RuntimeError(
                "CreditTransactionRepository not injected. "
                "Use dependency container to initialize CreditsRepository."
            )
        return self._credit_transaction_repository.collection

    def set_transaction_repository(self, transaction_repository):
        """Set the transaction repository (called by dependency container)."""
        self._credit_transaction_repository = transaction_repository

    async def create(self, data: UserCreditsCreate) -> UserCredits:
        """Create user credits account."""
        try:
            credits_dict = data.model_dump()
            initial_balance = credits_dict.get("initial_balance", 0)

            # Set totals based on initial balance
            if initial_balance > 0:
                credits_dict.update(
                    {
                        "current_balance": initial_balance,
                        "total_earned": initial_balance,
                    }
                )

            credits_dict = self._add_timestamps(credits_dict)
            credits = UserCredits(**credits_dict)

            # Store in database (user_id remains as string)
            result = await self.collection.insert_one(
                credits.model_dump(by_alias=True, exclude={"id"})
            )
            credits.id = result.inserted_id

            # Record initial grant transaction if there was an initial balance
            if initial_balance > 0:
                await self.record_transaction(
                    user_id=credits.user_id,
                    transaction_type=TransactionType.CREDIT,
                    reason=TransactionReason.INITIAL_GRANT,
                    amount=initial_balance,
                    balance_before=0,
                    balance_after=initial_balance,
                    description=f"Welcome bonus: {initial_balance} credits",
                )

            logger.info(f"User credits created with ID: {credits.id}")
            return credits
        except Exception as e:
            logger.error(f"Failed to create user credits: {e}")
            raise

    async def get_user_credits(self, user_id: str) -> Optional[UserCredits]:
        """Get user credits by user ID."""
        try:
            credits_data = await self.collection.find_one(
                {"user_id": user_id, "deleted_at": None}
            )
            return UserCredits(**credits_data) if credits_data else None
        except Exception as e:
            logger.error(f"Failed to get user credits for {user_id}: {e}")
            return None

    async def get_or_create_user_credits(self, user_id: str) -> UserCredits:
        """Get existing user credits or create new one."""
        credits = await self.get_user_credits(user_id)
        if credits is None:
            credits_create = UserCreditsCreate(user_id=user_id, initial_balance=0)
            credits = await self.create(credits_create)
        return credits

    async def record_transaction(
        self,
        user_id: str,
        transaction_type: TransactionType,
        reason: TransactionReason,
        amount: int,
        balance_before: int,
        balance_after: int,
        reference_id: Optional[str] = None,
        reference_type: Optional[str] = None,
        description: Optional[str] = None,
    ) -> CreditTransaction:
        """Record a credit transaction using the transaction repository."""
        if not self._credit_transaction_repository:
            raise RuntimeError(
                "CreditTransactionRepository not injected. "
                "Cannot record transaction."
            )

        return await self._credit_transaction_repository.record_transaction(
            user_id=user_id,
            transaction_type=transaction_type,
            reason=reason,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            reference_id=reference_id,
            reference_type=reference_type,
            description=description,
        )

    async def consume_credits(
        self,
        user_id: str,
        amount: int,
        reason: TransactionReason,
        reference_id: Optional[str] = None,
        reference_type: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """Consume credits from user account (atomic operation)."""
        try:
            # Find user with sufficient balance
            credits_data = await self.collection.find_one(
                {
                    "user_id": user_id,
                    "current_balance": {"$gte": amount},
                    "deleted_at": None,
                }
            )

            if not credits_data:
                return False

            balance_before = credits_data["current_balance"]
            balance_after = balance_before - amount

            # Update credits atomically
            result = await self.collection.update_one(
                {
                    "user_id": user_id,
                    "current_balance": balance_before,  # Optimistic locking
                },
                {
                    "$inc": {"current_balance": -amount, "total_spent": amount},
                    "$set": {"updated_at": datetime.now(timezone.utc)},
                },
            )

            if result.modified_count > 0:
                # Record transaction
                await self.record_transaction(
                    user_id=user_id,
                    transaction_type=TransactionType.DEBIT,
                    reason=reason,
                    amount=-amount,  # Negative for debit
                    balance_before=balance_before,
                    balance_after=balance_after,
                    reference_id=reference_id,
                    reference_type=reference_type,
                    description=description,
                )
                logger.info(f"Consumed {amount} credits from user {user_id}")
                return True

            return False
        except Exception as e:
            logger.error(f"Failed to consume credits: {e}")
            return False

    async def add_credits(
        self,
        user_id: str,
        amount: int,
        reason: TransactionReason,
        reference_id: Optional[str] = None,
        reference_type: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """Add credits to user account."""
        try:
            # Ensure user credits exist (create if needed)
            credits = await self.get_or_create_user_credits(user_id)
            balance_before = credits.current_balance
            balance_after = balance_before + amount

            # Update credits
            result = await self.collection.update_one(
                {"user_id": user_id},
                {
                    "$inc": {"current_balance": amount, "total_earned": amount},
                    "$set": {"updated_at": datetime.now(timezone.utc)},
                },
            )

            if result.modified_count > 0:
                # Record transaction
                await self.record_transaction(
                    user_id=user_id,
                    transaction_type=TransactionType.CREDIT,
                    reason=reason,
                    amount=amount,
                    balance_before=balance_before,
                    balance_after=balance_after,
                    reference_id=reference_id,
                    reference_type=reference_type,
                    description=description,
                )
                logger.info(
                    f"Added {amount} credits to user {user_id}. Balance: {balance_before} -> {balance_after}"
                )
                return True

            return False
        except Exception as e:
            logger.error(f"Failed to add credits: {e}")
            return False

    async def get_user_transactions(
        self, user_id: str, limit: int = 50
    ) -> List[CreditTransaction]:
        """Get user's credit transaction history using transaction repository."""
        if not self._credit_transaction_repository:
            logger.warning(
                "CreditTransactionRepository not injected. Returning empty list."
            )
            return []

        return await self._credit_transaction_repository.get_user_transactions(
            user_id=user_id, limit=limit
        )
