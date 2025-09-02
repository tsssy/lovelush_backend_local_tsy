"""Credit transaction repository for database operations."""

from typing import List, Optional

from app.core.logging import get_logger
from app.domain.models.credits import (
    CreditTransaction,
    CreditTransactionCreate,
    TransactionReason,
    TransactionType,
)
from app.infrastructure.database.repositories.base_repository import BaseRepository

logger = get_logger(__name__)


class CreditTransactionRepositoryInterface:
    """Interface for credit transaction repository operations."""

    async def get_user_transactions(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> List[CreditTransaction]:
        """Get user's credit transaction history."""
        raise NotImplementedError

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
        """Record a credit transaction."""
        raise NotImplementedError


class CreditTransactionRepository(BaseRepository, CreditTransactionRepositoryInterface):
    """Repository for credit transactions database operations."""

    def __init__(self):
        super().__init__("credit_transactions", CreditTransaction)

    async def get_user_transactions(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> List[CreditTransaction]:
        """
        Get user's credit transaction history.

        Args:
            user_id: ID of the user
            limit: Maximum number of transactions to return
            offset: Number of transactions to skip

        Returns:
            List of CreditTransaction objects
        """
        try:
            cursor = (
                self.collection.find({"user_id": user_id})
                .sort("created_at", -1)
                .skip(offset)
                .limit(limit)
            )

            transactions = []
            async for transaction_data in cursor:
                try:
                    transactions.append(CreditTransaction(**transaction_data))
                except Exception as e:
                    logger.warning(f"Failed to parse transaction document: {e}")
                    continue

            logger.debug(
                f"Retrieved {len(transactions)} transactions for user {user_id}"
            )
            return transactions

        except Exception as e:
            logger.error(f"Failed to get user transactions for {user_id}: {e}")
            return []

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
        """
        Record a credit transaction.

        Args:
            user_id: ID of the user
            transaction_type: Type of transaction (CREDIT/DEBIT/REFUND)
            reason: Reason for the transaction
            amount: Transaction amount
            balance_before: User balance before transaction
            balance_after: User balance after transaction
            reference_id: Optional reference to related entity
            reference_type: Optional type of referenced entity
            description: Optional transaction description

        Returns:
            Created CreditTransaction object

        Raises:
            Exception: If transaction creation fails
        """
        try:
            transaction_data = CreditTransactionCreate(
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

            transaction = await self.create(transaction_data)
            logger.debug(
                f"Recorded {transaction_type} transaction for user {user_id}: "
                f"amount={amount}, reason={reason}"
            )
            return transaction

        except Exception as e:
            logger.error(f"Failed to record transaction for user {user_id}: {e}")
            raise

    async def get_total_by_reason(self, user_id: str, reason: TransactionReason) -> int:
        """
        Get total transaction amount by reason for a user.

        Args:
            user_id: ID of the user
            reason: Transaction reason to filter by

        Returns:
            Total amount for the specified reason
        """
        try:
            pipeline = [
                {"$match": {"user_id": user_id, "reason": reason}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
            ]

            cursor = self.collection.aggregate(pipeline)
            result = await cursor.to_list(length=1)

            return result[0]["total"] if result else 0

        except Exception as e:
            logger.error(f"Failed to get total by reason for {user_id}: {e}")
            return 0

    async def get_transaction_count(self, user_id: str) -> int:
        """
        Get total number of transactions for a user.

        Args:
            user_id: ID of the user

        Returns:
            Total number of transactions
        """
        try:
            count = await self.collection.count_documents({"user_id": user_id})
            return count

        except Exception as e:
            logger.error(f"Failed to get transaction count for {user_id}: {e}")
            return 0
