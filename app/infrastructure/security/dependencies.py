"""Authentication dependencies for FastAPI."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.domain.models.agent import AgentRole
from app.domain.models.user import User
from app.domain.services.agent_service import AgentService
from app.domain.services.user_service import UserService
from app.infrastructure.security.jwt_auth import decode_token, verify_token

security = HTTPBearer()


def get_user_service() -> UserService:
    """Dependency to get UserService instance."""
    return UserService()


def get_agent_service() -> AgentService:
    """Dependency to get AgentService instance."""
    return AgentService()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """Get current authenticated user."""
    try:
        # Decode token to get username
        username = decode_token(credentials.credentials)

        # Get user from database
        user = await user_service.get_user_by_username(username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Convert UserResponse back to User for the dependency
        full_user = await user_service.user_repository.get_by_username(username)
        if not full_user or not full_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive user",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return full_user

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    return current_user


async def get_current_agent(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    agent_service: AgentService = Depends(get_agent_service),
) -> dict:
    """Get current authenticated agent."""
    try:
        # Verify and decode token
        payload = verify_token(credentials.credentials)

        # Check if this is an agent token
        if payload.get("type") != "agent":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get agent data from token
        agent_name = payload.get("sub")
        agent_id = payload.get("agent_id")
        agent_role = payload.get("agent_role")

        if not agent_name or not agent_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing subject or agent_id",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get agent from database to verify it still exists and is active
        agent = await agent_service.agent_repository.get_by_name(agent_name)
        if not agent or not agent.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive or missing agent",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "agent_role": agent_role
            or agent.role.value,  # Use token role or fallback to DB
            "agent": agent,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_active_agent(
    current_agent: dict = Depends(get_current_agent),
) -> dict:
    """Get current active agent."""
    agent = current_agent["agent"]
    if not agent.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive agent"
        )
    return current_agent


async def get_current_admin_agent(
    current_agent: dict = Depends(get_current_active_agent),
) -> dict:
    """Get current agent with admin authorization."""
    agent_role = current_agent.get("agent_role")

    # Check role from token first, then from database object
    if (
        agent_role != AgentRole.ADMIN.value
        and current_agent["agent"].role != AgentRole.ADMIN
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return current_agent


async def get_current_user_or_agent(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_service: UserService = Depends(get_user_service),
    agent_service: AgentService = Depends(get_agent_service),
) -> dict:
    """Get current authenticated user or agent."""
    try:
        # Verify and decode token
        payload = verify_token(credentials.credentials)
        token_type = payload.get("type")

        if token_type == "user":
            # Handle user authentication
            username = payload.get("sub")
            user_id = payload.get("user_id")

            if not username or not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token missing subject or user_id",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Get user from database
            user = await user_service.user_repository.get_by_username(username)
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Inactive or missing user",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            return {
                "type": "user",
                "user_id": user_id,
                "username": username,
                "user": user,
            }

        elif token_type == "agent":
            # Handle agent authentication
            agent_name = payload.get("sub")
            agent_id = payload.get("agent_id")
            agent_role = payload.get("agent_role")

            if not agent_name or not agent_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token missing subject or agent_id",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Get agent from database
            agent = await agent_service.agent_repository.get_by_name(agent_name)
            if not agent or not agent.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Inactive or missing agent",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            return {
                "type": "agent",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "agent_role": agent_role or agent.role.value,
                "agent": agent,
            }

        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_user_or_active_agent(
    current_auth: dict = Depends(get_current_user_or_agent),
) -> dict:
    """Get current authenticated user or active agent."""
    if current_auth["type"] == "user":
        user = current_auth["user"]
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
            )
    elif current_auth["type"] == "agent":
        agent = current_auth["agent"]
        if not agent.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive agent"
            )

    return current_auth


async def get_current_admin_agent_only(
    current_auth: dict = Depends(get_current_user_or_agent),
) -> dict:
    """Get current authenticated admin agent only. Returns 403 for users or non-admin agents."""
    # First check if it's an agent at all
    if current_auth["type"] != "agent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin agent access required"
        )

    # Check if agent is active
    agent = current_auth["agent"]
    if not agent.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive agent"
        )

    # Check if agent has admin role
    agent_role = current_auth.get("agent_role")
    if agent_role != AgentRole.ADMIN.value and agent.role != AgentRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin agent access required"
        )

    return current_auth
