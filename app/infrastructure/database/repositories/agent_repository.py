"""Agent repository for database operations."""

from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId

from app.core.logging import get_logger
from app.domain.models.agent import (
    Agent,
    AgentCreate,
    AgentUpdate,
    SubAccount,
    SubAccountCreate,
    SubAccountUpdate,
)
from app.infrastructure.database.repositories.base_repository import (
    BaseRepository,
    BaseRepositoryInterface,
)
from app.infrastructure.security.jwt_auth import get_password_hash

logger = get_logger(__name__)


class AgentRepositoryInterface(
    BaseRepositoryInterface[Agent, AgentCreate, AgentUpdate]
):
    """Agent repository interface with domain-specific methods."""

    async def get_by_name(self, agent_name: str) -> Optional[Agent]:
        """Get agent by name for authentication."""
        raise NotImplementedError

    async def get_active_agents(self) -> List[Agent]:
        """Get all active agents."""
        raise NotImplementedError

    async def update_last_assigned_index(self, agent_id: str, index: int) -> bool:
        """Update agent's last assigned sub-account index."""
        raise NotImplementedError


class SubAccountRepositoryInterface(
    BaseRepositoryInterface[SubAccount, SubAccountCreate, SubAccountUpdate]
):
    """Sub-account repository interface with domain-specific methods."""

    async def get_by_name(self, sub_account_name: str) -> Optional[SubAccount]:
        """Get sub-account by name for authentication."""
        raise NotImplementedError

    async def get_by_agent_id(self, agent_id: str) -> List[SubAccount]:
        """Get all sub-accounts for an agent."""
        raise NotImplementedError

    async def get_available_by_agent(self, agent_id: str) -> List[SubAccount]:
        """Get available sub-accounts for an agent."""
        raise NotImplementedError

    async def increment_chat_count(self, sub_account_id: str) -> bool:
        """Increment sub-account's current chat count."""
        raise NotImplementedError

    async def decrement_chat_count(self, sub_account_id: str) -> bool:
        """Decrement sub-account's current chat count."""
        raise NotImplementedError


class AgentRepository(
    BaseRepository[Agent, AgentCreate, AgentUpdate], AgentRepositoryInterface
):
    """MongoDB agent repository implementation."""

    def __init__(self):
        super().__init__("agents", Agent)

    async def create(self, data: AgentCreate) -> Agent:
        """Create a new agent with password hashing."""
        try:
            agent_dict = data.model_dump()

            # Hash password if provided
            if agent_dict.get("password"):
                agent_dict["hashed_password"] = get_password_hash(
                    agent_dict.pop("password")
                )

            agent_dict = self._add_timestamps(agent_dict)
            agent = Agent(**agent_dict)

            result = await self.collection.insert_one(
                agent.model_dump(by_alias=True, exclude={"id"})
            )
            agent.id = result.inserted_id
            logger.info(f"Agent created with ID: {agent.id}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            raise

    async def get_by_name(self, agent_name: str) -> Optional[Agent]:
        """Get agent by name for authentication."""
        try:
            agent_data = await self.collection.find_one(
                {"name": agent_name, "is_active": True, "deleted_at": None}
            )
            return Agent(**agent_data) if agent_data else None
        except Exception as e:
            logger.error(f"Failed to get agent by name {agent_name}: {e}")
            return None

    async def get_active_agents(self) -> List[Agent]:
        """Get all active agents, ordered by priority desc."""
        try:
            cursor = self.collection.find(
                {"is_active": True, "status": "active", "deleted_at": None}
            ).sort([("priority", -1), ("_id", 1)])

            agents = []
            async for agent_data in cursor:
                agents.append(Agent(**agent_data))
            return agents
        except Exception as e:
            logger.error(f"Failed to get active agents: {e}")
            return []

    async def update_last_assigned_index(self, agent_id: str, index: int) -> bool:
        """Update agent's last assigned sub-account index."""
        try:
            obj_id = self._convert_to_object_id(agent_id)
            result = await self.collection.update_one(
                {"_id": obj_id},
                {
                    "$set": {
                        "last_assigned_sub_account_index": index,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            success = result.modified_count > 0
            if success:
                logger.debug(f"Updated last assigned index for agent {agent_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to update agent last assigned index: {e}")
            return False

    async def get_available_sub_accounts_by_agent(
        self, agent_id: str
    ) -> List[SubAccount]:
        """Get available sub-accounts for an agent through SubAccountRepository."""
        sub_account_repo = SubAccountRepository()
        return await sub_account_repo.get_available_by_agent(agent_id)

    async def update_agent_last_assigned_index(self, agent_id: str, index: int) -> bool:
        """Alias for update_last_assigned_index for service compatibility."""
        return await self.update_last_assigned_index(agent_id, index)

    async def get_sub_account_by_id(self, sub_account_id: str) -> Optional[SubAccount]:
        """Get sub-account by ID through SubAccountRepository."""
        sub_account_repo = SubAccountRepository()
        return await sub_account_repo.get_by_id(sub_account_id)

    async def increment_sub_account_chat_count(self, sub_account_id: str) -> bool:
        """Increment sub-account chat count through SubAccountRepository."""
        sub_account_repo = SubAccountRepository()
        return await sub_account_repo.increment_chat_count(sub_account_id)

    async def decrement_sub_account_chat_count(self, sub_account_id: str) -> bool:
        """Decrement sub-account chat count through SubAccountRepository."""
        sub_account_repo = SubAccountRepository()
        return await sub_account_repo.decrement_chat_count(sub_account_id)


class SubAccountRepository(
    BaseRepository[SubAccount, SubAccountCreate, SubAccountUpdate],
    SubAccountRepositoryInterface,
):
    """MongoDB sub-account repository implementation."""

    def __init__(self):
        super().__init__("sub_accounts", SubAccount)

    async def create(self, data: SubAccountCreate) -> SubAccount:
        """Create a new sub-account with password hashing."""
        try:
            sub_account_dict = data.model_dump()
            sub_account_dict["agent_id"] = ObjectId(sub_account_dict["agent_id"])

            # Hash password if provided
            if sub_account_dict.get("password"):
                sub_account_dict["hashed_password"] = get_password_hash(
                    sub_account_dict.pop("password")
                )

            sub_account_dict = self._add_timestamps(sub_account_dict)
            sub_account = SubAccount(**sub_account_dict)

            result = await self.collection.insert_one(
                sub_account.model_dump(by_alias=True, exclude={"id"})
            )
            sub_account.id = result.inserted_id
            logger.info(f"Sub-account created with ID: {sub_account.id}")
            return sub_account
        except Exception as e:
            logger.error(f"Failed to create sub-account: {e}")
            raise

    async def get_by_name(self, sub_account_name: str) -> Optional[SubAccount]:
        """Get sub-account by name for authentication."""
        try:
            sub_account_data = await self.collection.find_one(
                {"name": sub_account_name, "is_active": True, "deleted_at": None}
            )
            return SubAccount(**sub_account_data) if sub_account_data else None
        except Exception as e:
            logger.error(f"Failed to get sub-account by name {sub_account_name}: {e}")
            return None

    async def get_by_agent_id(self, agent_id: str) -> List[SubAccount]:
        """Get all sub-accounts for an agent."""
        try:
            cursor = self.collection.find(
                {"agent_id": agent_id, "is_active": True, "deleted_at": None}
            ).sort("created_at", 1)

            sub_accounts = []
            async for sub_account_data in cursor:
                sub_accounts.append(SubAccount(**sub_account_data))
            return sub_accounts
        except Exception as e:
            logger.error(f"Failed to get sub-accounts by agent ID {agent_id}: {e}")
            return []

    async def get_available_by_agent(self, agent_id: str) -> List[SubAccount]:
        """Get available sub-accounts for an agent."""
        try:
            cursor = self.collection.find(
                {
                    "agent_id": agent_id,
                    "is_active": True,
                    "status": "available",
                    "deleted_at": None,
                    "$expr": {"$lt": ["$current_chat_count", "$max_concurrent_chats"]},
                }
            )

            sub_accounts = []
            async for sub_account_data in cursor:
                sub_accounts.append(SubAccount(**sub_account_data))
            return sub_accounts
        except Exception as e:
            logger.error(
                f"Failed to get available sub-accounts by agent ID {agent_id}: {e}"
            )
            return []

    async def increment_chat_count(self, sub_account_id: str) -> bool:
        """Increment sub-account's current chat count."""
        try:
            obj_id = self._convert_to_object_id(sub_account_id)
            result = await self.collection.update_one(
                {"_id": obj_id},
                {
                    "$inc": {"current_chat_count": 1},
                    "$set": {
                        "last_activity_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    },
                },
            )
            success = result.modified_count > 0
            if success:
                logger.debug(f"Incremented chat count for sub-account {sub_account_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to increment chat count: {e}")
            return False

    async def decrement_chat_count(self, sub_account_id: str) -> bool:
        """Decrement sub-account's current chat count."""
        try:
            obj_id = self._convert_to_object_id(sub_account_id)
            result = await self.collection.update_one(
                {"_id": obj_id, "current_chat_count": {"$gt": 0}},
                {
                    "$inc": {"current_chat_count": -1},
                    "$set": {"updated_at": datetime.now(timezone.utc)},
                },
            )
            success = result.modified_count > 0
            if success:
                logger.debug(f"Decremented chat count for sub-account {sub_account_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to decrement chat count: {e}")
            return False
