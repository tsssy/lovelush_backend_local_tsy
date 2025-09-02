"""
Agent management API endpoints for AI agent operations.
Provides secure authentication and comprehensive sub-account CRUD operations
for managing AI personas/characters under agent accounts.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError as PydanticValidationError

from app.core.dependencies import (
    get_agent_service,
    get_notification_service,
    get_upload_service,
)
from app.core.exceptions.exceptions import ValidationError
from app.core.logging import get_logger
from app.core.responses import ResponseHelper
from app.domain.models.agent import (
    SubAccountCreate,
    SubAccountUpdate,
    UploadRequest,
    UploadResponse,
)
from app.domain.services.agent_service import AgentService
from app.domain.services.notification_service import NotificationService
from app.domain.services.upload_service import UploadService
from app.infrastructure.security.dependencies import (
    get_current_agent,
    get_current_user_or_active_agent,
)

router = APIRouter(prefix="/agents", tags=["Agents"])
logger = get_logger(__name__)


@router.post("/login", response_model=dict, summary="Agent login")
async def agent_login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    agent_service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """
    Authenticate agent and return access token.

    Validates agent credentials and returns JWT tokens for authenticated agents.
    Agents use username/password authentication similar to regular users.

    Args:
        form_data: OAuth2 form with agent username and password
        agent_service: Injected agent service instance

    Returns:
        ResponseHelper.success with tokens and agent data

    Raises:
        HTTPException(401): Invalid credentials or inactive agent
        HTTPException(500): Internal server error during authentication
    """
    try:
        # Authenticate the agent
        agent = await agent_service.authenticate_agent(
            form_data.username, form_data.password
        )

        if not agent:
            logger.warning(
                "Failed agent login attempt", extra={"agent_name": form_data.username}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect agent name or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Create JWT tokens
        auth_response = await agent_service.create_agent_tokens(agent)

        logger.info(
            "Agent login successful",
            extra={"agent_id": str(agent.id), "agent_name": form_data.username},
        )
        return ResponseHelper.success(data=auth_response, msg="Agent login successful")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error during agent login: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/sub-accounts", response_model=dict, summary="Get agent sub-accounts")
async def get_sub_accounts(
    agent: dict = Depends(get_current_agent),
    agent_service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """
    Get all sub-accounts for the authenticated agent.

    Retrieves the list of sub-accounts (AI personas/characters) managed by
    the authenticated agent including their status and configuration.
    Agent-only endpoint with full access to sub-account data.

    Args:
        agent: Currently authenticated agent from JWT token
        agent_service: Injected agent service instance

    Returns:
        ResponseHelper.success with sub-account data

    Raises:
        HTTPException(401): Agent not authenticated or token invalid
        HTTPException(500): Internal server error during sub-account retrieval
    """
    try:
        # Get sub-accounts for the authenticated agent
        sub_account_responses = await agent_service.get_sub_accounts_list(
            agent_id=agent["agent_id"]
        )

        logger.info(
            "Sub-accounts retrieved",
            extra={
                "agent_id": agent["agent_id"],
                "sub_account_count": len(sub_account_responses),
            },
        )

        return ResponseHelper.success(
            data={"sub_accounts": [resp for resp in sub_account_responses]},
            msg="Sub-accounts retrieved successfully",
        )

    except KeyError as e:
        logger.error("Invalid agent data structure", extra={"missing_key": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent authentication data",
        )
    except Exception as e:
        logger.exception("Unexpected error retrieving sub-accounts: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/sub-accounts", response_model=dict, summary="Create sub-account")
async def create_sub_account(
    sub_account_data: SubAccountCreate,
    agent: dict = Depends(get_current_agent),
    agent_service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """
    Create a new sub-account for the authenticated agent.

    Creates a new AI persona/character sub-account under the authenticated agent.
    The agent_id is automatically set from the authenticated agent - do not include it in the request body.

    Args:
        sub_account_data: Sub-account creation data (agent_id will be auto-populated)
        agent: Currently authenticated agent from JWT token
        agent_service: Injected agent service instance

    Returns:
        ResponseHelper.created with sub-account data

    Raises:
        HTTPException(400): Invalid input data or validation errors
        HTTPException(401): Agent not authenticated or token invalid
        HTTPException(409): Sub-account name already exists
        HTTPException(500): Internal server error during creation
    """
    try:
        # Override agent_id with authenticated agent's ID
        sub_account_data.agent_id = agent["agent_id"]

        # Create the sub-account
        sub_account_response = await agent_service.create_sub_account(sub_account_data)

        return ResponseHelper.created(
            data=sub_account_response,
            msg="Sub-account created successfully",
        )

    except PydanticValidationError as e:
        logger.warning(
            "Sub-account creation validation error",
            extra={"agent_id": agent["agent_id"], "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except ValidationError as e:
        logger.warning(
            "Sub-account creation business validation error",
            extra={"agent_id": agent["agent_id"], "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("Unexpected error creating sub-account: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/sub-accounts/{sub_account_id}",
    response_model=dict,
    summary="Get sub-account by ID",
)
async def get_sub_account(
    sub_account_id: str = Path(
        ..., min_length=24, max_length=24, description="Sub-account ID"
    ),
    current_auth: dict = Depends(get_current_user_or_active_agent),
    agent_service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """
    Get sub-account details by ID.

    Retrieves detailed information about a specific sub-account.
    - Agents: Can only access sub-accounts they own (full data)
    - Users: Can access any active sub-account (public profile data for chat)

    Args:
        sub_account_id: MongoDB ObjectId of the sub-account
        current_auth: Currently authenticated user or agent
        agent_service: Injected agent service instance

    Returns:
        ResponseHelper.success with sub-account data

    Raises:
        HTTPException(400): Invalid sub-account ID format
        HTTPException(401): User/Agent not authenticated
        HTTPException(403): Agent access denied to sub-account (agents only)
        HTTPException(404): Sub-account not found or inactive (for users)
        HTTPException(500): Internal server error during retrieval
    """
    try:
        # Get sub-account first
        sub_account_response = await agent_service.get_sub_account_by_id(sub_account_id)
        if not sub_account_response:
            logger.warning(
                "Sub-account not found",
                extra={
                    "sub_account_id": sub_account_id,
                    "auth_type": current_auth["type"],
                    "auth_id": current_auth.get("user_id")
                    or current_auth.get("agent_id"),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sub-account not found",
            )

        if current_auth["type"] == "agent":
            # Agent access: Check ownership and return full data
            if not await agent_service.verify_sub_account_access(
                sub_account_id, current_auth["agent_id"]
            ):
                logger.warning(
                    "Access denied to sub-account",
                    extra={
                        "agent_id": current_auth["agent_id"],
                        "sub_account_id": sub_account_id,
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this sub-account",
                )

            # Return full data for agent
            logger.debug(
                "Sub-account retrieved by agent",
                extra={
                    "sub_account_id": sub_account_id,
                    "agent_id": current_auth["agent_id"],
                },
            )
            return ResponseHelper.success(
                data=sub_account_response,
                msg="Sub-account retrieved successfully",
            )

        else:  # User access
            # Users can only see active sub-accounts with public data
            if not sub_account_response.is_active:
                logger.warning(
                    "Inactive sub-account requested by user",
                    extra={
                        "sub_account_id": sub_account_id,
                        "user_id": current_auth["user_id"],
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Sub-account not available",
                )

            # Return filtered public data for user
            public_data = {
                "id": sub_account_response.id,
                "display_name": sub_account_response.display_name,
                "bio": sub_account_response.bio,
                "age": sub_account_response.age,
                "location": sub_account_response.location,
                "gender": sub_account_response.gender,
                "avatar_url": sub_account_response.avatar_url,
                "photo_urls": sub_account_response.photo_urls,
                "tags": sub_account_response.tags,
                "status": sub_account_response.status,
            }

            logger.debug(
                "Sub-account public data retrieved by user",
                extra={
                    "sub_account_id": sub_account_id,
                    "user_id": current_auth["user_id"],
                },
            )
            return ResponseHelper.success(
                data=public_data,
                msg="Sub-account profile retrieved successfully",
            )

    except HTTPException:
        raise
    except ValueError as e:
        auth_id = current_auth.get("user_id") or current_auth.get("agent_id")
        logger.warning(
            "Invalid sub-account ID format",
            extra={
                "sub_account_id": sub_account_id,
                "auth_type": current_auth["type"],
                "auth_id": auth_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid sub-account ID format",
        )
    except Exception as e:
        logger.exception("Unexpected error retrieving sub-account: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put(
    "/sub-accounts/{sub_account_id}",
    response_model=dict,
    summary="Update sub-account",
)
async def update_sub_account(
    sub_account_data: SubAccountUpdate,
    sub_account_id: str = Path(
        ..., min_length=24, max_length=24, description="Sub-account ID"
    ),
    agent: dict = Depends(get_current_agent),
    agent_service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """
    Update sub-account information.

    Updates the specified sub-account with new information.
    Only allows updates to sub-accounts owned by the authenticated agent.
    This endpoint can be used to update avatar_url and photo_urls after file upload.

    Args:
        sub_account_data: Sub-account update data
        sub_account_id: MongoDB ObjectId of the sub-account
        agent: Currently authenticated agent from JWT token
        agent_service: Injected agent service instance

    Returns:
        ResponseHelper.updated with updated sub-account data

    Raises:
        HTTPException(400): Invalid input data or validation errors
        HTTPException(401): Agent not authenticated or token invalid
        HTTPException(403): Access denied to sub-account
        HTTPException(404): Sub-account not found
        HTTPException(500): Internal server error during update
    """
    try:
        # Verify access and update the sub-account
        if not await agent_service.verify_sub_account_access(
            sub_account_id, agent["agent_id"]
        ):
            logger.warning(
                "Access denied to update sub-account",
                extra={
                    "agent_id": agent["agent_id"],
                    "sub_account_id": sub_account_id,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this sub-account",
            )

        # Update the sub-account
        sub_account_response = await agent_service.update_sub_account(
            sub_account_id, sub_account_data
        )
        if not sub_account_response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sub-account not found",
            )

        return ResponseHelper.updated(
            data=sub_account_response,
            msg="Sub-account updated successfully",
        )

    except HTTPException:
        raise
    except PydanticValidationError as e:
        logger.warning(
            "Sub-account update validation error",
            extra={"sub_account_id": sub_account_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except ValidationError as e:
        logger.warning(
            "Sub-account update business validation error",
            extra={"sub_account_id": sub_account_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ValueError as e:
        logger.warning(
            "Invalid sub-account ID format for update",
            extra={"sub_account_id": sub_account_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid sub-account ID format",
        )
    except Exception as e:
        logger.exception("Unexpected error updating sub-account: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete(
    "/sub-accounts/{sub_account_id}",
    response_model=dict,
    summary="Delete sub-account",
)
async def delete_sub_account(
    sub_account_id: str = Path(
        ..., min_length=24, max_length=24, description="Sub-account ID"
    ),
    agent: dict = Depends(get_current_agent),
    agent_service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """
    Delete sub-account.

    Performs a soft delete of the specified sub-account.
    Only allows deletion of sub-accounts owned by the authenticated agent.

    Args:
        sub_account_id: MongoDB ObjectId of the sub-account
        agent: Currently authenticated agent from JWT token
        sub_account_repo: Injected sub-account repository instance

    Returns:
        ResponseHelper.deleted with confirmation message

    Raises:
        HTTPException(400): Invalid sub-account ID format
        HTTPException(401): Agent not authenticated or token invalid
        HTTPException(403): Access denied to sub-account
        HTTPException(404): Sub-account not found
        HTTPException(500): Internal server error during deletion
    """
    try:
        # Verify access and delete the sub-account
        if not await agent_service.verify_sub_account_access(
            sub_account_id, agent["agent_id"]
        ):
            logger.warning(
                "Access denied to delete sub-account",
                extra={
                    "agent_id": agent["agent_id"],
                    "sub_account_id": sub_account_id,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this sub-account",
            )

        # Delete the sub-account (soft delete)
        success = await agent_service.delete_sub_account(sub_account_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sub-account not found",
            )

        return ResponseHelper.deleted(msg="Sub-account deleted successfully")

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid sub-account ID format for deletion",
            extra={"sub_account_id": sub_account_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid sub-account ID format",
        )
    except Exception as e:
        logger.exception("Unexpected error deleting sub-account: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/notifications/send", response_model=dict, summary="Send notification to user"
)
async def send_user_notification(
    request: Dict[str, Any],
    agent_service: AgentService = Depends(get_agent_service),
    notification_service: NotificationService = Depends(get_notification_service),
    current_agent: dict = Depends(get_current_agent),
) -> Dict[str, Any]:
    """
    Send notification from agent to user via Pusher.

    Sends real-time notifications to users through their private Pusher channel.
    Used for agent-initiated chat requests, messages, and other notifications.

    Args:
        request: Notification request with user_id, message, and type
        agent_service: Injected agent service instance
        notification_service: Injected notification service instance
        current_agent: Currently authenticated agent

    Returns:
        ResponseHelper.success with notification delivery confirmation

    Raises:
        HTTPException(400): Invalid request data or missing required fields
        HTTPException(401): Agent not authenticated
        HTTPException(404): Target user not found
        HTTPException(500): Internal server error during notification send
    """
    try:
        # Validate required fields
        target_user_id = request.get("target_user_id")
        message = request.get("message")
        notification_type = request.get("notification_type", "agent.message")

        if not target_user_id or not message:
            logger.warning(
                "Missing required fields for notification",
                extra={"agent_id": current_agent["agent_id"], "request": request},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="target_user_id and message are required",
            )

        # Get agent info for the notification
        agent_id = current_agent["agent_id"]
        agent = await agent_service.agent_repository.get_by_id(agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
            )

        # Check if notification service is available
        if not notification_service.is_available():
            logger.error("Notification service not available")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Notification service temporarily unavailable",
            )

        # Prepare agent data for notification
        agent_data = {
            "agent_id": agent_id,
            "name": agent.name,
            "display_name": agent.name,
        }

        # Send notification based on type
        if notification_type == "agent.wants_chat":
            result = await notification_service.send_agent_chat_request(
                user_id=target_user_id,
                agent_data=agent_data,
                message=message,
                sub_account_id=request.get("sub_account_id"),
            )
        elif notification_type == "agent.message":
            result = await notification_service.send_agent_message_notification(
                user_id=target_user_id,
                agent_data=agent_data,
                message=message,
                chatroom_id=request.get("chatroom_id"),
            )
        else:
            # Use generic notification method
            sender_data = {
                "agent_id": agent_id,
                "agent_name": agent.name,
                "agent_display_name": agent.name,
                "sub_account_id": request.get("sub_account_id", agent_id),
            }

            result = await notification_service.send_user_notification(
                user_id=target_user_id,
                notification_type=notification_type,
                message=message,
                sender_data=sender_data,
                metadata=request.get("metadata", {}),
            )

        logger.info(
            "Agent notification sent successfully",
            extra={
                "agent_id": agent_id,
                "target_user_id": target_user_id,
                "notification_type": notification_type,
            },
        )

        return ResponseHelper.success(data=result, msg="Notification sent successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error sending user notification: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


@router.post(
    "/upload/presigned-url",
    response_model=UploadResponse,
    summary="Generate presigned URL for subaccount avatar or photo upload",
)
async def generate_upload_presigned_url(
    request: UploadRequest,
    current_agent: dict = Depends(get_current_agent),
    upload_service: UploadService = Depends(get_upload_service),
) -> UploadResponse:
    """
    Generate presigned URL for uploading subaccount avatar or photos to S3-compatible storage.

    Creates a secure, time-limited URL for direct file upload to cloud storage.
    Frontend can use this URL to upload files directly without routing through the backend.
    Supports both avatar (single image) and photos (multiple images) upload types.

    After successful upload, use PUT /sub-accounts/{id} to update avatar_url or photo_urls.

    Args:
        request: Upload request with subaccount_id, file_type, and upload_type
        current_agent: Currently authenticated agent from JWT token
        upload_service: Injected upload service instance

    Returns:
        UploadResponse with presigned URL and file information

    Raises:
        HTTPException(400): Invalid request data or file type not allowed
        HTTPException(401): Agent not authenticated
        HTTPException(403): Access denied to subaccount
        HTTPException(404): Subaccount not found
        HTTPException(500): Internal server error during URL generation
    """
    try:
        agent_id = current_agent["agent_id"]

        result = await upload_service.generate_presigned_upload_url(
            agent_id=agent_id,
            subaccount_id=request.subaccount_id,
            file_type=request.file_type,
            upload_type=request.upload_type.value,
            expires_in=600,  # 10 minutes
        )

        logger.info(
            "Generated presigned upload URL",
            extra={
                "agent_id": agent_id,
                "subaccount_id": request.subaccount_id,
                "file_type": request.file_type,
                "upload_type": request.upload_type.value,
            },
        )

        return UploadResponse(**result)

    except ValueError as e:
        logger.warning(
            "Upload validation error",
            extra={
                "agent_id": current_agent["agent_id"],
                "subaccount_id": request.subaccount_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except RuntimeError as e:
        logger.error(
            "Failed to generate presigned URL",
            extra={
                "agent_id": current_agent["agent_id"],
                "subaccount_id": request.subaccount_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate upload URL",
        )
    except Exception as e:
        logger.exception("Unexpected error generating presigned URL: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
