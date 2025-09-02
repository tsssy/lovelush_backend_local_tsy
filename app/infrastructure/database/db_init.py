"""Database initialization service for indexes and setup."""

from app.core.initializer import ComponentInitializer
from app.core.logging import get_logger
from app.infrastructure.database.mongodb import mongodb

logger = get_logger(__name__)


class DatabaseInitService:
    """Service for database initialization and index management."""

    def __init__(self):
        self.db = mongodb

    async def initialize_indexes(self) -> None:
        """Initialize all database indexes."""
        logger.info("Starting database index initialization...")

        try:
            await self._create_user_indexes()
            await self._create_bot_message_indexes()
            await self._create_workflow_state_indexes()
            await self._create_message_indexes()
            await self._create_chatroom_indexes()
            await self._create_agent_indexes()
            await self._create_match_indexes()
            await self._create_credits_indexes()
            await self._create_credit_transaction_indexes()
            await self._create_payment_indexes()
            await self._create_product_indexes()
            await self._create_app_settings_indexes()
            logger.info("Database indexes initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database indexes: {e}")
            raise

    async def _create_user_indexes(self) -> None:
        """Create indexes for user collection."""
        logger.debug("Creating user collection indexes...")
        collection = self.db.get_database()["users"]

        # Create unique index on username
        await collection.create_index("username", unique=True)
        logger.debug("Created unique index on username")

        # Create unique partial index on email (only when email exists)
        await collection.create_index(
            "email", unique=True, partialFilterExpression={"email": {"$exists": True}}
        )
        logger.debug("Created unique partial index on email")

        # Create unique partial index on telegram_id (only when telegram_id exists)
        await collection.create_index(
            "telegram_id",
            unique=True,
            partialFilterExpression={"telegram_id": {"$exists": True}},
        )
        logger.debug("Created unique partial index on telegram_id")

        # Create index on created_at for sorting
        await collection.create_index("created_at")
        logger.debug("Created index on created_at")

        # Create index on is_active for filtering
        await collection.create_index("is_active")
        logger.debug("Created index on is_active")

        # Create index on last_login for analytics
        await collection.create_index("last_login")
        logger.debug("Created index on last_login")

        # Create index on onboarding_status for filtering
        await collection.create_index("onboarding_status")
        logger.debug("Created index on onboarding_status")

        # Create index on onboarding_completed_at for analytics
        await collection.create_index("onboarding_completed_at", sparse=True)
        logger.debug("Created sparse index on onboarding_completed_at")

        # Create index on deleted_at for logical deletion queries
        await collection.create_index("deleted_at", sparse=True)
        logger.debug("Created sparse index on deleted_at")

        logger.debug("User collection indexes created successfully")

    async def _create_bot_message_indexes(self) -> None:
        """Create indexes for bot_messages collection."""
        logger.debug("Creating bot_messages collection indexes...")
        collection = self.db.get_database()["bot_messages"]

        # Index on user_id for efficient user message queries
        await collection.create_index("user_id")
        logger.debug("Created index on user_id")

        # Index on platform for filtering by platform (Telegram, WhatsApp, etc.)
        await collection.create_index("platform")
        logger.debug("Created index on platform")

        # Index on direction for filtering incoming vs outgoing messages
        await collection.create_index("direction")
        logger.debug("Created index on direction")

        # Index on message_type for filtering by type (text, command, etc.)
        await collection.create_index("message_type")
        logger.debug("Created index on message_type")

        # Index on is_processed for finding unprocessed messages
        await collection.create_index("is_processed")
        logger.debug("Created index on is_processed")

        # Index on created_at for sorting (descending for recent first)
        await collection.create_index([("created_at", -1)])
        logger.debug("Created index on created_at")

        # Index on processed_at for tracking processing times
        await collection.create_index("processed_at", sparse=True)
        logger.debug("Created sparse index on processed_at")

        # Compound indexes for efficient user conversation queries
        await collection.create_index(
            [("user_id", 1), ("platform", 1), ("created_at", -1)]
        )
        logger.debug("Created compound index for user platform conversations")

        # Compound index for unprocessed message queries by platform
        await collection.create_index(
            [
                ("is_processed", 1),
                ("platform", 1),
                ("created_at", 1),  # Ascending to process oldest first
            ]
        )
        logger.debug("Created compound index for unprocessed messages")

        # Compound index for user conversation history with direction
        await collection.create_index(
            [("user_id", 1), ("direction", 1), ("created_at", -1)]
        )
        logger.debug("Created compound index for directional user conversations")

        # Indexes for Telegram-specific metadata queries
        await collection.create_index("metadata.telegram_message_id", sparse=True)
        await collection.create_index("metadata.telegram_chat_id", sparse=True)
        await collection.create_index("metadata.telegram_user_id", sparse=True)
        await collection.create_index("metadata.command_name", sparse=True)
        logger.debug("Created indexes for Telegram-specific metadata")

        # Index for workflow tracking
        await collection.create_index("metadata.workflow_id", sparse=True)
        await collection.create_index("metadata.workflow_step", sparse=True)
        logger.debug("Created indexes for workflow tracking")

        logger.debug("Bot messages collection indexes created successfully")

    async def _create_workflow_state_indexes(self) -> None:
        """Create indexes for workflow_states collection."""
        logger.debug("Creating workflow_states collection indexes...")
        collection = self.db.get_database()["workflow_states"]

        # Compound unique index on user_id and chat_id (only one workflow per user/chat)
        await collection.create_index([("user_id", 1), ("chat_id", 1)], unique=True)
        logger.debug("Created unique compound index on user_id and chat_id")

        # Index on workflow_type for filtering by type
        await collection.create_index("workflow_type")
        logger.debug("Created index on workflow_type")

        # Index on current_step for filtering by step
        await collection.create_index("current_step")
        logger.debug("Created index on current_step")

        # Index on expires_at for cleanup operations
        await collection.create_index("expires_at")
        logger.debug("Created index on expires_at")

        # Index on created_at for sorting
        await collection.create_index("created_at")
        logger.debug("Created index on created_at")

        # Index on updated_at for tracking recent activity
        await collection.create_index("updated_at")
        logger.debug("Created index on updated_at")

        logger.debug("Workflow states collection indexes created successfully")

    async def _create_message_indexes(self) -> None:
        """Create indexes for messages collection."""
        logger.debug("Creating messages collection indexes...")
        collection = self.db.get_database()["messages"]

        # Primary compound index for chatroom message queries (most important)
        await collection.create_index([("chatroom_id", 1), ("created_at", -1)])
        logger.debug("Created compound index for chatroom message queries")

        # Index for real-time message sync queries
        await collection.create_index([("chatroom_id", 1), ("created_at", 1)])
        logger.debug("Created compound index for message sync queries")

        # Index for filtering by sender type (user, agent, system)
        await collection.create_index(
            [("chatroom_id", 1), ("sender_type", 1), ("created_at", -1)]
        )
        logger.debug("Created compound index for sender type filtering")

        # Index for getting latest non-system messages
        await collection.create_index(
            [
                ("chatroom_id", 1),
                ("sender_type", 1),
                ("is_deleted", 1),
                ("created_at", -1),
            ]
        )
        logger.debug("Created compound index for non-system message queries")

        # Optimized index for non-deleted messages (works with simplified is_deleted check)
        await collection.create_index(
            [("chatroom_id", 1), ("is_deleted", 1), ("created_at", -1)]
        )
        logger.debug("Created compound index for optimized non-deleted message queries")

        # Index for sender-specific queries
        await collection.create_index([("sender_id", 1), ("created_at", -1)])
        logger.debug("Created index for sender message queries")

        # Index for message type filtering
        await collection.create_index([("chatroom_id", 1), ("message_type", 1)])
        logger.debug("Created compound index for message type queries")

        # Index for unread message counting (read_by array queries)
        await collection.create_index([("chatroom_id", 1), ("read_by", 1)])
        logger.debug("Created compound index for read receipt queries")

        # Index for soft deletion queries
        await collection.create_index("is_deleted")
        await collection.create_index("deleted_at", sparse=True)
        logger.debug("Created indexes for soft deletion")

        # Index for edited messages
        await collection.create_index("is_edited")
        await collection.create_index("edited_at", sparse=True)
        logger.debug("Created indexes for message editing")

        logger.debug("Messages collection indexes created successfully")

    async def _create_chatroom_indexes(self) -> None:
        """Create indexes for chatrooms collection."""
        logger.debug("Creating chatrooms collection indexes...")
        collection = self.db.get_database()["chatrooms"]

        # Index for user chatrooms
        await collection.create_index([("user_id", 1), ("created_at", -1)])
        logger.debug("Created compound index for user chatrooms")

        # Index for agent chatrooms
        await collection.create_index([("agent_id", 1), ("created_at", -1)])
        logger.debug("Created compound index for agent chatrooms")

        # Index for sub-account chatrooms
        await collection.create_index([("sub_account_id", 1), ("created_at", -1)])
        logger.debug("Created compound index for sub-account chatrooms")

        # Index for status filtering
        await collection.create_index([("status", 1), ("created_at", -1)])
        logger.debug("Created compound index for status filtering")

        # Index for active chatrooms by user
        await collection.create_index(
            [("user_id", 1), ("status", 1), ("last_activity_at", -1)]
        )
        logger.debug("Created compound index for active user chatrooms")

        # Unique index for user-sub_account pairs to prevent duplicates
        await collection.create_index(
            [("user_id", 1), ("sub_account_id", 1)],
            unique=True,
            partialFilterExpression={"deleted_at": None},
        )
        logger.debug("Created unique index for user-sub_account chatrooms")

        # Index for channel name (Pusher channel lookups)
        await collection.create_index("channel_name", unique=True, sparse=True)
        logger.debug("Created unique index on channel_name")

        # Index for soft deletion
        await collection.create_index("deleted_at", sparse=True)
        logger.debug("Created sparse index on deleted_at")

        # Index for last activity sorting
        await collection.create_index("last_activity_at")
        logger.debug("Created index on last_activity_at")

        logger.debug("Chatrooms collection indexes created successfully")

    async def _create_agent_indexes(self) -> None:
        """Create indexes for agents and sub_accounts collections."""
        logger.debug("Creating agents collection indexes...")

        # Agents collection
        agents_collection = self.db.get_database()["agents"]

        # Unique index on name (agent company/team name should be unique)
        await agents_collection.create_index("name", unique=True)
        logger.debug("Created unique index on agent name")

        # Index for active agents
        await agents_collection.create_index([("is_active", 1), ("created_at", -1)])
        logger.debug("Created compound index for active agents")

        # Index for status filtering
        await agents_collection.create_index("status")
        logger.debug("Created index on agent status")

        # Index for soft deletion
        await agents_collection.create_index("deleted_at", sparse=True)
        logger.debug("Created sparse index on agent deleted_at")

        # Sub-accounts collection
        logger.debug("Creating sub_accounts collection indexes...")
        sub_accounts_collection = self.db.get_database()["sub_accounts"]

        # Index for agent's sub-accounts
        await sub_accounts_collection.create_index(
            [("agent_id", 1), ("created_at", -1)]
        )
        logger.debug("Created compound index for agent sub-accounts")

        # Index for active sub-accounts by agent
        await sub_accounts_collection.create_index(
            [("agent_id", 1), ("is_active", 1), ("status", 1)]
        )
        logger.debug("Created compound index for active sub-accounts")

        # Index for sub-account name within agent (unique per agent)
        await sub_accounts_collection.create_index(
            [("agent_id", 1), ("name", 1)], unique=True
        )
        logger.debug("Created unique compound index on agent_id and sub-account name")

        # Index for status filtering
        await sub_accounts_collection.create_index("status")
        logger.debug("Created index on sub-account status")

        # Index for chat capacity management
        await sub_accounts_collection.create_index(
            [("current_chat_count", 1), ("max_concurrent_chats", 1)]
        )
        logger.debug("Created compound index for chat capacity")

        # Index for soft deletion
        await sub_accounts_collection.create_index("deleted_at", sparse=True)
        logger.debug("Created sparse index on sub-account deleted_at")

        logger.debug("Agents and sub-accounts collection indexes created successfully")

    async def _create_match_indexes(self) -> None:
        """Create indexes for match_records collection (individual match records)."""
        logger.debug("Creating match_records collection indexes...")
        collection = self.db.get_database()["match_records"]

        # Index for user match history (most common query)
        await collection.create_index([("user_id", 1), ("created_at", -1)])
        logger.debug("Created compound index for user match history")

        # Index for getting available matches by user
        await collection.create_index(
            [("user_id", 1), ("status", 1), ("expires_at", 1)]
        )
        logger.debug("Created compound index for available matches")

        # Index for match type filtering
        await collection.create_index(
            [("user_id", 1), ("match_type", 1), ("created_at", -1)]
        )
        logger.debug("Created compound index for match type queries")

        # Index for finding matches by candidate
        await collection.create_index(
            [("user_id", 1), ("candidate.sub_account_id", 1), ("status", 1)]
        )
        logger.debug("Created compound index for candidate matching")

        # Index for daily match tracking
        await collection.create_index(
            [("user_id", 1), ("match_type", 1), ("created_at", -1)]
        )
        logger.debug("Created compound index for daily match queries")

        # Index for match expiration cleanup
        await collection.create_index([("expires_at", 1), ("status", 1)])
        logger.debug("Created compound index for expiration cleanup")

        # Index for match status filtering
        await collection.create_index([("user_id", 1), ("status", 1)])
        logger.debug("Created compound index for status queries")

        # Index for credits tracking
        await collection.create_index([("user_id", 1), ("credits_consumed", 1)])
        logger.debug("Created compound index for credits tracking")

        # Index for consumed matches (for analytics)
        await collection.create_index(
            [("user_id", 1), ("consumed_at", -1)], sparse=True
        )
        logger.debug("Created compound index for consumption tracking")

        # Simple indexes for common fields
        await collection.create_index("match_type")
        await collection.create_index("status")
        await collection.create_index("created_at")
        logger.debug("Created simple indexes for common fields")

        logger.debug("Match records collection indexes created successfully")

    async def _create_credits_indexes(self) -> None:
        """Create indexes for credits collection."""
        logger.debug("Creating credits collection indexes...")
        collection = self.db.get_database()["credits"]

        # Unique index per user (one credit record per user)
        await collection.create_index("user_id", unique=True)
        logger.debug("Created unique index on user_id")

        # Index for balance queries
        await collection.create_index([("balance", 1), ("updated_at", -1)])
        logger.debug("Created compound index for balance queries")

        # Index for free matches tracking
        await collection.create_index([("free_matches_used", 1), ("updated_at", -1)])
        logger.debug("Created compound index for free matches")

        logger.debug("Credits collection indexes created successfully")

    async def _create_credit_transaction_indexes(self) -> None:
        """Create indexes for credit_transactions collection."""
        logger.debug("Creating credit_transactions collection indexes...")
        collection = self.db.get_database()["credit_transactions"]

        # Index for user transaction history (most important query)
        await collection.create_index([("user_id", 1), ("created_at", -1)])
        logger.debug("Created compound index for user transaction history")

        # Index for filtering by transaction type
        await collection.create_index([("user_id", 1), ("transaction_type", 1)])
        logger.debug("Created compound index for transaction type queries")

        # Index for filtering by reason
        await collection.create_index([("user_id", 1), ("reason", 1)])
        logger.debug("Created compound index for transaction reason queries")

        # Index for reference lookups (payments, matches, etc.)
        await collection.create_index(
            [("reference_type", 1), ("reference_id", 1)], sparse=True
        )
        logger.debug("Created compound index for reference lookups")

        # Index for amount range queries
        await collection.create_index([("user_id", 1), ("amount", 1)])
        logger.debug("Created compound index for amount queries")

        # Simple indexes for sorting and filtering
        await collection.create_index("created_at")
        await collection.create_index("transaction_type")
        await collection.create_index("reason")
        logger.debug("Created simple indexes for sorting and filtering")

        logger.debug("Credit transactions collection indexes created successfully")

    async def _create_payment_indexes(self) -> None:
        """Create indexes for payments collection."""
        logger.debug("Creating payments collection indexes...")
        collection = self.db.get_database()["payments"]

        # Index for user payment history
        await collection.create_index([("user_id", 1), ("created_at", -1)])
        logger.debug("Created compound index for user payments")

        # Index for payment status tracking
        await collection.create_index([("status", 1), ("created_at", -1)])
        logger.debug("Created compound index for payment status")

        # Index for successful payments
        await collection.create_index(
            [("user_id", 1), ("status", 1), ("created_at", -1)]
        )
        logger.debug("Created compound index for successful user payments")

        # Unique index on external transaction ID
        await collection.create_index(
            "external_transaction_id", unique=True, sparse=True
        )
        logger.debug("Created unique index on external_transaction_id")

        # Index for amount and currency
        await collection.create_index([("amount", 1), ("currency", 1)])
        logger.debug("Created compound index for amount queries")

        logger.debug("Payments collection indexes created successfully")

    async def _create_product_indexes(self) -> None:
        """Create indexes for products collection."""
        logger.debug("Creating products collection indexes...")
        collection = self.db.get_database()["products"]

        # Index for active products
        await collection.create_index([("is_active", 1), ("sort_order", 1)])
        logger.debug("Created compound index for active products")

        # Index for product type
        await collection.create_index("product_type")
        logger.debug("Created index on product_type")

        # Index for pricing
        await collection.create_index([("price", 1), ("currency", 1)])
        logger.debug("Created compound index for pricing")

        # Index for soft deletion
        await collection.create_index("deleted_at", sparse=True)
        logger.debug("Created sparse index on product deleted_at")

        logger.debug("Products collection indexes created successfully")

    async def _create_app_settings_indexes(self) -> None:
        """Create indexes for app_settings collection."""
        logger.debug("Creating app_settings collection indexes...")
        collection = self.db.get_database()["app_settings"]

        # Unique index on name (settings name must be unique)
        await collection.create_index("name", unique=True)
        logger.debug("Created unique index on name")

        # Index for active settings queries
        await collection.create_index("is_active")
        logger.debug("Created index on is_active")

        # Index for default settings queries
        await collection.create_index("is_default")
        logger.debug("Created index on is_default")

        # Compound index for active settings sorting
        await collection.create_index([("is_active", 1), ("updated_at", -1)])
        logger.debug("Created compound index for active settings")

        # Index for sorting by creation date
        await collection.create_index("created_at")
        logger.debug("Created index on created_at")

        # Index for sorting by update date (most commonly used for ordering)
        await collection.create_index("updated_at")
        logger.debug("Created index on updated_at")

        # Index for soft deletion queries
        await collection.create_index("deleted_at", sparse=True)
        logger.debug("Created sparse index on deleted_at")

        # Compound index for non-deleted settings by update order
        await collection.create_index(
            [("deleted_at", 1), ("updated_at", -1)],
            partialFilterExpression={"deleted_at": None},
        )
        logger.debug("Created compound index for non-deleted settings")

        logger.debug("App settings collection indexes created successfully")


class DatabaseInitializer(ComponentInitializer):
    """Database initialization component initializer."""

    def __init__(self, db_init_service: DatabaseInitService):
        self._db_init_service = db_init_service

    @property
    def name(self) -> str:
        return "Database Indexes"

    async def initialize(self) -> None:
        """Initialize database indexes."""
        await self._db_init_service.initialize_indexes()

    async def cleanup(self) -> None:
        """Cleanup database - no action needed for indexes."""
        pass


# Global database initialization service
db_init_service = DatabaseInitService()
db_init_initializer = DatabaseInitializer(db_init_service)
