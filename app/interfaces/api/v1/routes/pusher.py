"""Pusher authentication and real-time messaging API endpoints.

Provides endpoints for Pusher channel authentication, private messaging,
webhook handling, and configuration management for real-time communication.

NOTE: This uses Pusher's built-in presence API - no custom presence tracking needed.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.core.config.settings import settings
from app.core.dependencies import (
    get_chatroom_service,
)
from app.core.logging import get_logger
from app.core.responses import ResponseHelper
from app.domain.services.chatroom_service import ChatroomService
from app.infrastructure.security.dependencies import get_current_user_or_agent
from app.integrations.pusher.client import pusher_client

router = APIRouter(prefix="/pusher", tags=["Pusher"])
logger = get_logger(__name__)


class PusherConfig(BaseModel):
    """Pusher configuration schema for frontend clients."""

    key: str
    cluster: str
    forceTLS: bool
    auth_endpoint: str
    wsHost: Optional[str] = None
    wsPort: Optional[int] = None
    wssPort: Optional[int] = None
    wsPath: Optional[str] = None  # Path for ws:// connections
    wssPath: Optional[str] = None  # Path for wss:// connections


def build_pusher_config() -> PusherConfig:
    """
    Build Pusher configuration for frontend clients.

    Returns PusherConfig with appropriate internal/external host separation.
    Uses external host for frontend clients, falls back to internal host.
    Properly separates domain and WebSocket paths (ws/wss), and handles HTTP/HTTPS ports.

    Returns:
        PusherConfig: Configuration object for frontend Pusher initialization
    """
    external_host = settings.pusher_external_host or settings.pusher_host
    ws_path = getattr(settings, "pusher_external_ws_path", "/ws")
    wss_path = getattr(settings, "pusher_external_wss_path", "/ws")

    config = {
        "key": settings.pusher_key,
        "cluster": settings.pusher_cluster,
        "forceTLS": settings.pusher_external_use_tls,  # Use external TLS for frontend
        "auth_endpoint": "/api/v1/pusher/auth",
    }

    if external_host and external_host != "pusher_default":
        config["wsHost"] = external_host
        config["wsPath"] = ws_path  # HTTP WebSocket path
        config["wssPath"] = wss_path  # HTTPS WebSocket path

        # Set appropriate ports based on external TLS setting (for frontend)
        if settings.pusher_external_use_tls:
            # HTTPS mode - use standard ports unless overridden
            config["wsPort"] = 80  # HTTP fallback
            config["wssPort"] = getattr(settings, "pusher_external_port", 443)
        else:
            # HTTP mode - use configured port or fallback
            external_port = getattr(settings, "pusher_external_port", 80)
            config["wsPort"] = external_port
            config["wssPort"] = 443  # HTTPS fallback

    return PusherConfig(**config)


@router.post("/auth", response_model=dict, summary="Authenticate Pusher channel access")
async def pusher_auth(
    request: Request,
    current_user_or_agent: Dict = Depends(get_current_user_or_agent),
    chatroom_service: ChatroomService = Depends(get_chatroom_service),
) -> Dict[str, Any]:
    """
    Authorize private and presence channels including chatrooms.

    Handles authentication for various Pusher channel types including chatroom channels,
    private user channels, private agent channels, and presence room channels with proper
    JWT validation and access control.

    Channel Types Supported:
    - presence-chatroom-{chatroom_id}: Chatroom conversations
    - private-user-{user_id}: User private notifications
    - private-agent-{agent_id}: Agent private notifications

    Args:
        request: FastAPI request object containing auth data
        current_user_or_agent: Authenticated user or agent from token
        chatroom_service: Injected chatroom service instance

    Returns:
        Pusher authentication data for channel access

    Raises:
        HTTPException(400): Invalid channel name or request format
        HTTPException(401): Missing/invalid token or user/agent not found
        HTTPException(403): Access denied to requested channel
        HTTPException(404): Chatroom not found
        HTTPException(422): Missing required parameters
        HTTPException(500): Internal server error during authentication
    """
    try:
        # Handle both JSON and form-data requests
        content_type = request.headers.get("content-type", "")

        if "application/json" in content_type:
            # JSON request
            body = await request.json()
            channel_name = body.get("channel_name")
            socket_id = body.get("socket_id")
        else:
            # Form-data request (default for Pusher.js)
            form = await request.form()
            channel_name = str(form.get("channel_name", ""))
            socket_id = str(form.get("socket_id", ""))

        if not channel_name or not socket_id:
            logger.warning(
                "Missing required parameters for Pusher auth",
                extra={
                    "channel_name": channel_name,
                    "socket_id_present": bool(socket_id),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Missing channel_name or socket_id",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error parsing pusher auth request: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid request format",
        )

    # Extract user/agent info from dependency injection
    user_type = current_user_or_agent.get("type")  # "user" or "agent"
    user_id = current_user_or_agent.get("user_id")
    agent_id = current_user_or_agent.get("agent_id")

    logger.info(
        "Pusher authentication attempt",
        extra={
            "user_type": user_type,
            "user_id": user_id,
            "agent_id": agent_id,
            "channel_name": channel_name,
            "socket_id": socket_id[:8] + "..." if len(socket_id) > 8 else socket_id,
        },
    )

    # Handle chatroom channels (presence-chatroom-{chatroom_id})
    if channel_name.startswith("presence-chatroom-"):
        # Extract chatroom ID
        chatroom_id = channel_name.replace("presence-chatroom-", "")

        # Get chatroom to validate access
        chatroom = await chatroom_service.get_chatroom_by_id(chatroom_id)
        if not chatroom:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chatroom not found"
            )

        # Check access permissions
        if user_type == "user":
            if not user_id or chatroom.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User not authorized for this chatroom",
                )
        elif user_type == "agent":
            if not agent_id or chatroom.agent_id != agent_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Agent not authorized for this chatroom",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user type for chatroom access",
            )

        # For presence channels, let frontend provide the channel_data
        # Frontend is already sending user_info in the channel_data
        if user_type == "user":
            custom_data = {
                "user_id": user_id,
                "user_info": {
                    "id": user_id,
                    "type": "user",
                    "name": current_user_or_agent.get("full_name", "User"),
                    "username": current_user_or_agent.get("username"),
                },
            }
        else:  # agent
            custom_data = {
                "user_id": agent_id,
                "user_info": {
                    "id": agent_id,
                    "type": "agent",
                    "name": current_user_or_agent.get("display_name", "Agent"),
                    "agent_name": current_user_or_agent.get("name"),
                },
            }

        auth_data = pusher_client.authenticate(channel_name, socket_id, custom_data)
        logger.info(
            f"Pusher authentication result - Channel: {channel_name}, "
            f"Auth data: {auth_data}"
        )

        return auth_data

    # Handle private user channels (private-user-{user_id})
    elif channel_name.startswith("private-user-"):
        if user_type != "user":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only users can access private user channels",
            )

        expected_user_id = channel_name.replace("private-user-", "")
        if not user_id or expected_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized to access this private user channel",
            )

        auth_data = pusher_client.authenticate(channel_name, socket_id)
        return auth_data

    # Handle private agent channels (private-agent-{agent_id})
    elif channel_name.startswith("private-agent-"):
        if user_type != "agent":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only agents can access private agent channels",
            )

        expected_agent_id = channel_name.replace("private-agent-", "")
        if not agent_id or expected_agent_id != agent_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized to access this private agent channel",
            )

        auth_data = pusher_client.authenticate(channel_name, socket_id)
        return auth_data

    else:
        logger.warning(f"Unknown channel type: {channel_name}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported channel type",
        )


@router.get("/config", response_model=dict, summary="Get Pusher configuration")
async def pusher_config(
    current_user_or_agent=Depends(get_current_user_or_agent),
) -> Dict[str, Any]:
    """
    Get public Pusher configuration for frontend clients.

    Returns Pusher configuration data needed for client-side Pusher initialization
    including app key, cluster, and connection settings with proper internal/external
    host separation.

    Returns:
        ResponseHelper.success with PusherConfig data

    Raises:
        HTTPException(401): User not authenticated
        HTTPException(500): Internal server error during configuration retrieval
    """
    try:
        config = build_pusher_config()
        return ResponseHelper.success(data=config, msg="Pusher config retrieved")
    except Exception as e:
        logger.exception("Error building Pusher config: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get Pusher configuration",
        )


class WebhookRequest(BaseModel):
    """Pusher webhook request model."""

    time_ms: int
    events: list


@router.post("/webhook", summary="Handle Pusher webhooks")
async def pusher_webhook(webhook_data: WebhookRequest) -> Dict[str, Any]:
    """
    Handle Pusher webhook events.

    Processes webhook events from Pusher including channel occupation changes,
    member additions/removals, and client connection events for presence tracking.

    Args:
        webhook_data: Webhook event data from Pusher

    Returns:
        Success response confirming webhook processing

    Raises:
        HTTPException(500): Error processing webhook events
    """
    try:
        logger.info(
            "Received Pusher webhook",
            extra={
                "event_count": len(webhook_data.events),
                "timestamp": webhook_data.time_ms,
            },
        )

        # Process webhook events if needed
        for event in webhook_data.events:
            event_name = event.get("name")
            channel = event.get("channel")

            logger.debug(
                "Processing webhook event",
                extra={
                    "event": event_name,
                    "channel": channel,
                    "data": event.get("data", {}),
                },
            )

        return ResponseHelper.success(msg="Webhook processed successfully")

    except Exception as e:
        logger.exception("Error processing Pusher webhook: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook",
        )
