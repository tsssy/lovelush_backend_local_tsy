"""Agent service for managing agents and sub-accounts business logic."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.core.config.settings import settings
from app.core.exceptions.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.models.agent import (
    Agent,
    AgentAuthResponse,
    AgentResponse,
    SubAccount,
    SubAccountCreate,
    SubAccountResponse,
    SubAccountUpdate,
)
from app.infrastructure.database.repositories.agent_repository import (
    AgentRepository,
    SubAccountRepository,
)
from app.infrastructure.security.jwt_auth import (
    create_access_token,
    create_refresh_token,
    verify_password,
)

logger = get_logger(__name__)


class AgentService:
    """Service for handling agent and sub-account business logic."""

    def __init__(
        self,
        agent_repository: Optional[AgentRepository] = None,
        sub_account_repository: Optional[SubAccountRepository] = None,
    ) -> None:
        self.agent_repository = agent_repository or AgentRepository()
        self.sub_account_repository = sub_account_repository or SubAccountRepository()

    async def authenticate_agent(
        self, agent_name: str, password: str
    ) -> Optional[Agent]:
        """
        Authenticate an agent with name and password.

        Validates agent credentials and returns the agent if authentication succeeds.
        Includes proper logging for security audit trails.

        Args:
            agent_name: Agent's unique name for authentication
            password: Plain text password to verify

        Returns:
            Agent object if authentication succeeds, None otherwise

        Raises:
            ValidationError: If input parameters are invalid
        """
        try:
            # Input validation
            if not agent_name or not agent_name.strip():
                logger.warning("Agent authentication failed - empty agent name")
                raise ValidationError("Agent name is required")

            if not password or not password.strip():
                logger.warning(
                    "Agent authentication failed - empty password",
                    extra={"agent_name": agent_name},
                )
                raise ValidationError("Password is required")

            # Get agent by name
            agent = await self.agent_repository.get_by_name(agent_name.strip())
            if not agent:
                logger.warning(
                    "Agent authentication failed - agent not found",
                    extra={"agent_name": agent_name},
                )
                return None

            # Check if agent is active
            if not agent.is_active:
                logger.warning(
                    "Agent authentication failed - agent inactive",
                    extra={"agent_id": str(agent.id), "agent_name": agent_name},
                )
                return None

            # Check password
            if not agent.hashed_password:
                logger.warning(
                    "Agent authentication failed - no password set",
                    extra={"agent_id": str(agent.id), "agent_name": agent_name},
                )
                return None

            if not verify_password(password, agent.hashed_password):
                logger.warning(
                    "Agent authentication failed - invalid password",
                    extra={"agent_id": str(agent.id), "agent_name": agent_name},
                )
                return None

            logger.info(
                "Agent authenticated successfully",
                extra={"agent_id": str(agent.id), "agent_name": agent_name},
            )
            return agent

        except ValidationError:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during agent authentication: %s",
                str(e),
                extra={"agent_name": agent_name},
            )
            return None

    async def create_agent_tokens(self, agent: Agent) -> AgentAuthResponse:
        """Create JWT tokens for an authenticated agent."""
        # Create token payload
        token_data = {
            "sub": agent.name,  # Subject is the agent name
            "agent_id": str(agent.id),
            "agent_role": agent.role.value,  # Include role in token
            "type": "agent",
        }

        # Create tokens
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data=token_data, expires_delta=access_token_expires
        )

        refresh_token_expires = timedelta(days=settings.refresh_token_expire_days)
        refresh_token = create_refresh_token(
            data=token_data, expires_delta=refresh_token_expires
        )

        # Create response with agent info
        agent_response = self._to_agent_response(agent)
        expires_at = datetime.now(timezone.utc) + access_token_expires

        logger.info(
            "Agent tokens created successfully",
            extra={
                "agent_id": str(agent.id),
                "agent_name": agent.name,
                "expires_at": expires_at.isoformat(),
            },
        )

        return AgentAuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            agent=agent_response,
            expires_at=expires_at,
        )

    async def get_sub_accounts_by_agent_id(self, agent_id: str) -> List[SubAccount]:
        """
        Get sub accounts by agent id.

        Args:
            agent_id: Agent id to get sub accounts for

        Returns:
            List of sub accounts for the agent
        """
        return await self.sub_account_repository.get_by_agent_id(agent_id)

    def _to_agent_response(self, agent: Agent) -> AgentResponse:
        """
        Convert Agent model to AgentResponse.

        Args:
            agent: Agent domain model

        Returns:
            AgentResponse with properly formatted data
        """
        return AgentResponse(
            _id=agent.id,
            name=agent.name,
            description=agent.description,
            status=agent.status,
            role=agent.role,
            is_active=agent.is_active,
            priority=agent.priority,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )

    def _to_sub_account_response(self, sub_account: SubAccount) -> SubAccountResponse:
        """
        Convert SubAccount model to SubAccountResponse.

        Args:
            sub_account: SubAccount domain model

        Returns:
            SubAccountResponse with properly formatted data
        """
        return SubAccountResponse(
            _id=sub_account.id,
            agent_id=sub_account.agent_id,
            name=sub_account.name,
            display_name=sub_account.display_name,
            status=sub_account.status,
            avatar_url=sub_account.avatar_url,
            bio=sub_account.bio,
            age=sub_account.age,
            location=sub_account.location,
            gender=sub_account.gender,
            photo_urls=sub_account.photo_urls,
            tags=sub_account.tags,
            is_active=sub_account.is_active,
            current_chat_count=sub_account.current_chat_count,
            max_concurrent_chats=sub_account.max_concurrent_chats,
            last_activity_at=sub_account.last_activity_at,
            created_at=sub_account.created_at,
            updated_at=sub_account.updated_at,
        )

    # Sub-account CRUD operations

    async def create_sub_account(
        self, sub_account_data: SubAccountCreate
    ) -> SubAccountResponse:
        """
        Create a new sub-account.

        Args:
            sub_account_data: Sub-account creation data

        Returns:
            SubAccountResponse with created sub-account data

        Raises:
            ValidationError: If validation fails or agent_id is not provided
        """
        try:
            # Ensure agent_id is provided
            if not sub_account_data.agent_id:
                raise ValidationError("agent_id is required for sub-account creation")

            sub_account = await self.sub_account_repository.create(sub_account_data)
            logger.info(
                "Sub-account created successfully",
                extra={
                    "sub_account_id": str(sub_account.id),
                    "agent_id": str(sub_account.agent_id),
                    "sub_account_name": sub_account.name,
                },
            )
            return self._to_sub_account_response(sub_account)
        except Exception as e:
            logger.error(f"Failed to create sub-account: {e}")
            raise

    async def get_sub_account_by_id(
        self, sub_account_id: str
    ) -> Optional[SubAccountResponse]:
        """
        Get sub-account by ID.

        Args:
            sub_account_id: Sub-account ID

        Returns:
            SubAccountResponse if found, None otherwise
        """
        try:
            sub_account = await self.sub_account_repository.get_by_id(sub_account_id)
            return self._to_sub_account_response(sub_account) if sub_account else None
        except Exception as e:
            logger.error(f"Failed to get sub-account by ID {sub_account_id}: {e}")
            return None

    async def update_sub_account(
        self, sub_account_id: str, sub_account_data: SubAccountUpdate
    ) -> Optional[SubAccountResponse]:
        """
        Update sub-account.

        Args:
            sub_account_id: Sub-account ID
            sub_account_data: Sub-account update data

        Returns:
            SubAccountResponse with updated data if successful, None if not found

        Raises:
            NotFoundError: If sub-account not found
            ValidationError: If validation fails
        """
        try:
            updated_sub_account = await self.sub_account_repository.update(
                sub_account_id, sub_account_data
            )
            if not updated_sub_account:
                raise NotFoundError("Sub-account not found")

            logger.info(
                "Sub-account updated successfully",
                extra={
                    "sub_account_id": sub_account_id,
                    "agent_id": str(updated_sub_account.agent_id),
                },
            )
            return self._to_sub_account_response(updated_sub_account)
        except Exception as e:
            logger.error(f"Failed to update sub-account {sub_account_id}: {e}")
            raise

    async def delete_sub_account(self, sub_account_id: str) -> bool:
        """
        Delete sub-account (soft delete).

        Args:
            sub_account_id: Sub-account ID

        Returns:
            True if successful, False if not found

        Raises:
            NotFoundError: If sub-account not found
        """
        try:
            success = await self.sub_account_repository.delete(sub_account_id)
            if not success:
                raise NotFoundError("Sub-account not found")

            logger.info(
                "Sub-account deleted successfully",
                extra={"sub_account_id": sub_account_id},
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete sub-account {sub_account_id}: {e}")
            raise

    async def get_sub_accounts_list(self, agent_id: str) -> List[SubAccountResponse]:
        """
        Get all sub-accounts for an agent with response formatting.

        Args:
            agent_id: Agent ID

        Returns:
            List of SubAccountResponse objects
        """
        try:
            sub_accounts = await self.sub_account_repository.get_by_agent_id(agent_id)
            return [
                self._to_sub_account_response(sub_account)
                for sub_account in sub_accounts
            ]
        except Exception as e:
            logger.error(f"Failed to get sub-accounts for agent {agent_id}: {e}")
            return []

    async def verify_sub_account_access(
        self, sub_account_id: str, agent_id: str
    ) -> bool:
        """
        Verify that an agent has access to a specific sub-account.

        Args:
            sub_account_id: Sub-account ID
            agent_id: Agent ID

        Returns:
            True if agent has access, False otherwise
        """
        try:
            sub_account = await self.sub_account_repository.get_by_id(sub_account_id)
            if not sub_account:
                return False
            return str(sub_account.agent_id) == agent_id
        except Exception as e:
            logger.error(f"Failed to verify sub-account access: {e}")
            return False
