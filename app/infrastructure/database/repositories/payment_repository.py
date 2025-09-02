"""Payment repository for database operations."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from app.core.logging import get_logger
from app.domain.models.payment import (
    Payment,
    PaymentCreate,
    PaymentStatus,
    PaymentUpdate,
)
from app.infrastructure.database.repositories.base_repository import (
    BaseRepository,
    BaseRepositoryInterface,
)

logger = get_logger(__name__)


class PaymentRepositoryInterface(
    BaseRepositoryInterface[Payment, PaymentCreate, PaymentUpdate]
):
    """Payment repository interface with domain-specific methods."""

    async def create(self, data: PaymentCreate) -> Payment:
        """Create a new payment record."""
        raise NotImplementedError

    async def find_by_id(self, payment_id: str) -> Optional[Payment]:
        """Find payment record by ID."""
        raise NotImplementedError

    async def find_by_invoice_payload(self, payload: str) -> Optional[Payment]:
        """Find payment record by invoice payload."""
        raise NotImplementedError

    async def find_by_user_id(self, user_id: str, limit: int = 50) -> List[Payment]:
        """Find payment records by MongoDB user ID."""
        raise NotImplementedError

    async def find_by_telegram_user_id(
        self, telegram_user_id: str, limit: int = 50
    ) -> List[Payment]:
        """Find payment records by telegram user ID."""
        raise NotImplementedError

    async def find_by_status(
        self, status: PaymentStatus, limit: int = 50
    ) -> List[Payment]:
        """Find payment records by status."""
        raise NotImplementedError

    async def find_expired_payments(self) -> List[Payment]:
        """Find expired payment records."""
        raise NotImplementedError

    async def find_pending_payments_by_user(self, user_id: str) -> List[Payment]:
        """Find user's pending payment records."""
        raise NotImplementedError

    async def count_by_user_and_status(
        self, user_id: str, status: PaymentStatus
    ) -> int:
        """Count user's payment records by status."""
        raise NotImplementedError


class PaymentRepository(
    BaseRepository[Payment, PaymentCreate, PaymentUpdate], PaymentRepositoryInterface
):
    """MongoDB payment repository implementation."""

    def __init__(self):
        super().__init__("payments", Payment)

    def _generate_business_id(self, product_id: str, telegram_user_id: str) -> str:
        """Generate unique business ID for payment."""
        return f"{product_id}_{telegram_user_id}_{uuid.uuid4().hex[:8]}"

    async def create(self, data: PaymentCreate) -> Payment:
        """Create a new payment record with custom business ID."""
        try:
            payment_dict = data.model_dump()

            # Generate business ID for payment
            business_id = self._generate_business_id(
                payment_dict["product_id"], payment_dict["telegram_user_id"]
            )

            # Add the business ID to the payment dict before creating Payment object
            payment_dict["id"] = business_id

            # Create payment with business ID
            payment = Payment(**payment_dict)

            # Create document for MongoDB (use _id instead of id)
            payment_doc = payment.model_dump(exclude={"id"})
            payment_doc["_id"] = business_id

            await self.collection.insert_one(payment_doc)

            logger.info(f"Payment created with business ID: {business_id}")
            return payment

        except Exception as e:
            logger.error(f"Failed to create payment record: {e}")
            raise

    async def get_by_id(self, entity_id: str) -> Optional[Payment]:
        """Get payment by ID (business ID)."""
        return await self.find_by_id(entity_id)

    async def find_by_id(self, payment_id: str) -> Optional[Payment]:
        """Find payment record by ID."""
        try:
            doc = await self.collection.find_one({"_id": payment_id})
            if doc:
                # Set id field from _id for Payment model
                doc["id"] = doc["_id"]
                return Payment(**doc)
            return None
        except Exception as e:
            logger.error(f"Failed to find payment record: {e}")
            raise

    async def update(self, entity_id: str, data: PaymentUpdate) -> Optional[Payment]:
        """Update payment record."""
        try:
            update_data = data.model_dump(exclude_unset=True)
            update_data["updated_at"] = datetime.now(timezone.utc)

            result = await self.collection.update_one(
                {"_id": entity_id}, {"$set": update_data}
            )

            if result.modified_count > 0:
                return await self.find_by_id(entity_id)
            return None
        except Exception as e:
            logger.error(f"Failed to update payment record: {e}")
            raise

    async def delete(self, entity_id: str) -> bool:
        """Delete payment record."""
        try:
            result = await self.collection.delete_one({"_id": entity_id})
            success = result.deleted_count > 0
            if success:
                logger.info(f"Payment record deleted: {entity_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to delete payment record: {e}")
            raise

    async def find_by_invoice_payload(self, payload: str) -> Optional[Payment]:
        """Find payment record by invoice payload."""
        try:
            doc = await self.collection.find_one({"invoice_payload": payload})
            if doc:
                # For business IDs that are not MongoDB ObjectIds, use the _id directly
                doc["id"] = doc["_id"]  # Keep as string, don't convert to PyObjectId
                return Payment(**doc)
            return None
        except Exception as e:
            logger.error(f"Failed to find payment by invoice payload: {e}")
            raise

    async def find_by_user_id(self, user_id: str, limit: int = 50) -> List[Payment]:
        """Find payment records by user ID (MongoDB user.id)."""
        try:
            cursor = (
                self.collection.find({"user_id": user_id})
                .sort("created_at", -1)
                .limit(limit)
            )
            documents = await cursor.to_list(length=limit)

            payments = []
            for doc in documents:
                doc["id"] = doc["_id"]
                payments.append(Payment(**doc))
            return payments
        except Exception as e:
            logger.error(f"Failed to find payments by user ID: {e}")
            raise

    async def find_by_telegram_user_id(
        self, telegram_user_id: str, limit: int = 50
    ) -> List[Payment]:
        """Find payment records by telegram user ID."""
        try:
            cursor = (
                self.collection.find({"telegram_user_id": telegram_user_id})
                .sort("created_at", -1)
                .limit(limit)
            )
            documents = await cursor.to_list(length=limit)

            payments = []
            for doc in documents:
                doc["id"] = doc["_id"]
                payments.append(Payment(**doc))
            return payments
        except Exception as e:
            logger.error(f"Failed to find payments by telegram user ID: {e}")
            raise

    async def find_by_status(
        self, status: PaymentStatus, limit: int = 50
    ) -> List[Payment]:
        """Find payment records by status."""
        try:
            cursor = (
                self.collection.find({"status": status})
                .sort("created_at", -1)
                .limit(limit)
            )
            documents = await cursor.to_list(length=limit)

            payments = []
            for doc in documents:
                doc["id"] = doc["_id"]
                payments.append(Payment(**doc))
            return payments
        except Exception as e:
            logger.error(f"Failed to find payments by status: {e}")
            raise

    async def find_expired_payments(self) -> List[Payment]:
        """Find expired payment records."""
        try:
            cursor = self.collection.find(
                {
                    "status": PaymentStatus.PENDING,
                    "expires_at": {"$lt": datetime.now(timezone.utc)},
                }
            ).sort("created_at", -1)

            documents = await cursor.to_list(length=None)
            payments = []
            for doc in documents:
                doc["id"] = doc["_id"]
                payments.append(Payment(**doc))
            return payments
        except Exception as e:
            logger.error(f"Failed to find expired payments: {e}")
            raise

    async def find_pending_payments_by_user(self, user_id: str) -> List[Payment]:
        """Find user's pending payment records by MongoDB user ID."""
        try:
            cursor = self.collection.find(
                {
                    "user_id": user_id,
                    "status": PaymentStatus.PENDING,
                    "expires_at": {"$gt": datetime.now(timezone.utc)},
                }
            ).sort("created_at", -1)

            documents = await cursor.to_list(length=None)
            payments = []
            for doc in documents:
                doc["id"] = doc["_id"]
                payments.append(Payment(**doc))
            return payments
        except Exception as e:
            logger.error(f"Failed to find pending payments by user: {e}")
            raise

    async def find_pending_payments_by_telegram_user(
        self, telegram_user_id: str
    ) -> List[Payment]:
        """Find user's pending payment records by telegram user ID."""
        try:
            cursor = self.collection.find(
                {
                    "telegram_user_id": telegram_user_id,
                    "status": PaymentStatus.PENDING,
                    "expires_at": {"$gt": datetime.now(timezone.utc)},
                }
            ).sort("created_at", -1)

            documents = await cursor.to_list(length=None)
            payments = []
            for doc in documents:
                doc["id"] = doc["_id"]
                payments.append(Payment(**doc))
            return payments
        except Exception as e:
            logger.error(f"Failed to find pending payments by telegram user: {e}")
            raise

    async def count_by_user_and_status(
        self, user_id: str, status: PaymentStatus
    ) -> int:
        """Count user's payment records by status using MongoDB user ID."""
        try:
            count = await self.collection.count_documents(
                {"user_id": user_id, "status": status}
            )
            return count
        except Exception as e:
            logger.error(f"Failed to count payments by user and status: {e}")
            raise

    async def count_by_telegram_user_and_status(
        self, telegram_user_id: str, status: PaymentStatus
    ) -> int:
        """Count user's payment records by status using telegram user ID."""
        try:
            count = await self.collection.count_documents(
                {"telegram_user_id": telegram_user_id, "status": status}
            )
            return count
        except Exception as e:
            logger.error(f"Failed to count payments by telegram user and status: {e}")
            raise

    async def find_recent_payments(self, limit: int = 20) -> List[Payment]:
        """Find recent payment records."""
        try:
            cursor = self.collection.find().sort("created_at", -1).limit(limit)
            documents = await cursor.to_list(length=limit)

            payments = []
            for doc in documents:
                doc["id"] = doc["_id"]
                payments.append(Payment(**doc))
            return payments
        except Exception as e:
            logger.error(f"Failed to find recent payments: {e}")
            raise
