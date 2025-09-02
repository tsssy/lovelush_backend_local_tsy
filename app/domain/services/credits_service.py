"""Credits service for managing user credits and financial transactions."""

from typing import List, Optional

from app.core.exceptions.exceptions import ValidationError
from app.core.logging import get_logger
from app.domain.models.credits import (
    CreditAdjustment,
    CreditTransaction,
    CreditTransactionResponse,
    TransactionReason,
    UserCredits,
    UserCreditsCreate,
    UserCreditsResponse,
)
from app.domain.services.app_settings_service import AppSettingsService
from app.infrastructure.database.repositories.credits_repository import (
    CreditsRepository,
)

logger = get_logger(__name__)


class CreditsService:
    """Service for handling user credits business logic."""

    def __init__(
        self,
        credits_repository: Optional[CreditsRepository] = None,
        app_settings_service: Optional[AppSettingsService] = None,
    ) -> None:
        self.credits_repository = credits_repository or CreditsRepository()
        self.app_settings_service = app_settings_service or AppSettingsService()

    async def create_user_credits(
        self, credits_data: UserCreditsCreate
    ) -> UserCreditsResponse:
        """
        Create user credits account with validation.

        Creates a new credits account for a user with initial balance
        and proper validation of input data.

        Args:
            credits_data: User credits creation data

        Returns:
            UserCreditsResponse with created credits information

        Raises:
            ValidationError: If credits data is invalid
        """
        try:
            # Validate credits data
            if not credits_data:
                logger.error("Cannot create user credits with null data")
                raise ValidationError("Credits data is required")

            if not credits_data.user_id:
                logger.warning("User credits creation failed - missing user_id")
                raise ValidationError("User ID is required")

            if credits_data.initial_balance < 0:
                logger.warning(
                    "User credits creation failed - negative initial balance",
                    extra={
                        "user_id": credits_data.user_id,
                        "initial_balance": credits_data.initial_balance,
                    },
                )
                raise ValidationError("Initial balance cannot be negative")

            # Create credits account
            credits = await self.credits_repository.create(credits_data)

            logger.info(
                "User credits account created successfully",
                extra={
                    "user_id": credits_data.user_id,
                    "initial_balance": credits_data.initial_balance,
                    "credits_id": str(credits.id),
                },
            )

            return self._to_credits_response(credits)

        except ValidationError:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error creating user credits: %s",
                str(e),
                extra={"user_id": credits_data.user_id if credits_data else None},
            )
            raise

    async def get_user_credits(self, user_id: str) -> Optional[UserCreditsResponse]:
        """
        Get user credits by user ID with validation.

        Retrieves the credits account for a specific user with proper
        input validation and error handling.

        Args:
            user_id: Unique identifier of the user

        Returns:
            UserCreditsResponse if found, None otherwise

        Raises:
            ValidationError: If user_id is invalid
        """
        try:
            # Validate input
            if not user_id or not user_id.strip():
                logger.warning("User credits retrieval failed - empty user_id")
                raise ValidationError("User ID is required")

            user_id = user_id.strip()

            # Get credits
            credits = await self.credits_repository.get_user_credits(user_id)
            if not credits:
                logger.debug("User credits not found", extra={"user_id": user_id})
                return None

            logger.debug(
                "User credits retrieved successfully",
                extra={"user_id": user_id, "current_balance": credits.current_balance},
            )

            return self._to_credits_response(credits)

        except ValidationError:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error retrieving user credits: %s",
                str(e),
                extra={"user_id": user_id},
            )
            return None

    async def get_or_create_user_credits(
        self, user_id: str, with_initial_credits: bool = True
    ) -> UserCreditsResponse:
        """
        Get existing user credits or create new one with initial credits from settings.

        Args:
            user_id: User ID to get or create credits for
            with_initial_credits: Whether to grant initial credits if creating new account

        Returns:
            UserCreditsResponse with user credits information
        """
        # Check if user already has credits
        existing_credits = await self.credits_repository.get_user_credits(user_id)
        if existing_credits:
            return self._to_credits_response(existing_credits)

        # Create new credits account with initial amount from settings
        initial_amount = 0
        if with_initial_credits:
            try:
                coin_config = await self.app_settings_service.get_coin_config()
                initial_amount = coin_config.initial_free_coins
            except Exception as e:
                logger.warning(
                    f"Failed to get initial coins from settings, using 0: {e}"
                )
                initial_amount = 0

        # Create credits account - repository will set initial balance and record as earned
        credits_create = UserCreditsCreate(
            user_id=user_id, initial_balance=initial_amount
        )
        credits = await self.credits_repository.create(credits_create)

        # No need to add credits again - repository already handles initial balance
        logger.info(
            "User credits account created with initial balance",
            extra={
                "user_id": user_id,
                "initial_amount": initial_amount,
                "current_balance": credits.current_balance,
            },
        )

        return self._to_credits_response(credits)

    async def add_credits(
        self,
        user_id: str,
        amount: int,
        reason: TransactionReason,
        description: Optional[str] = None,
    ) -> bool:
        """Add credits to user account."""
        return await self.credits_repository.add_credits(
            user_id=user_id, amount=amount, reason=reason, description=description
        )

    async def consume_credits(
        self,
        user_id: str,
        amount: int,
        reason: TransactionReason,
        reference_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """Consume credits from user account."""
        return await self.credits_repository.consume_credits(
            user_id=user_id,
            amount=amount,
            reason=reason,
            reference_id=reference_id,
            reference_type=(
                "matching" if reason == TransactionReason.MATCH_CONSUMPTION else None
            ),
            description=description,
        )

    async def adjust_credits(self, adjustment: CreditAdjustment) -> bool:
        """Manually adjust user credits (admin operation)."""
        if adjustment.amount > 0:
            return await self.credits_repository.add_credits(
                user_id=adjustment.user_id,
                amount=adjustment.amount,
                reason=adjustment.reason,
                description=adjustment.description,
            )
        else:
            return await self.credits_repository.consume_credits(
                user_id=adjustment.user_id,
                amount=abs(adjustment.amount),
                reason=adjustment.reason,
                description=adjustment.description,
            )

    async def get_user_transactions(
        self, user_id: str, limit: int = 50
    ) -> List[CreditTransactionResponse]:
        """Get user's credit transaction history."""
        transactions = await self.credits_repository.get_user_transactions(
            user_id, limit
        )
        return [
            self._to_transaction_response(transaction) for transaction in transactions
        ]

    async def grant_initial_credits(self, user_id: str) -> bool:
        """Grant initial credits to new user based on app settings."""
        try:
            coin_config = await self.app_settings_service.get_coin_config()
            amount = coin_config.initial_free_coins
        except Exception as e:
            logger.warning(
                f"Failed to get initial coins from settings, using fallback of 50: {e}"
            )
            amount = 50  # Fallback for backwards compatibility

        if amount <= 0:
            logger.debug(
                f"Initial credits amount is {amount}, skipping grant for user {user_id}"
            )
            return True  # Consider it successful if no credits to grant

        return await self.credits_repository.add_credits(
            user_id=user_id,
            amount=amount,
            reason=TransactionReason.INITIAL_GRANT,
            description=f"Welcome bonus: {amount} credits",
        )

    def _to_credits_response(self, credits: UserCredits) -> UserCreditsResponse:
        """Convert UserCredits model to UserCreditsResponse."""
        return UserCreditsResponse(
            _id=credits.id,
            user_id=str(credits.user_id),
            current_balance=credits.current_balance,
            total_earned=credits.total_earned,
            total_spent=credits.total_spent,
            created_at=credits.created_at,
            updated_at=credits.updated_at,
        )

    def _to_transaction_response(
        self, transaction: CreditTransaction
    ) -> CreditTransactionResponse:
        """Convert CreditTransaction model to CreditTransactionResponse."""
        return CreditTransactionResponse(
            _id=transaction.id,
            user_id=str(transaction.user_id),
            transaction_type=transaction.transaction_type,
            reason=transaction.reason,
            amount=transaction.amount,
            balance_before=transaction.balance_before,
            balance_after=transaction.balance_after,
            reference_id=transaction.reference_id,
            reference_type=transaction.reference_type,
            description=transaction.description,
            created_at=transaction.created_at,
        )
