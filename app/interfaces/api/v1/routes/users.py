"""
User management API endpoints providing user profile and account operations.
Provides endpoints for user profile management, user lookup, and user listing with pagination.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import ValidationError as PydanticValidationError

from app.core.dependencies import get_user_service
from app.core.exceptions.exceptions import (
    NotFoundError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.responses import ResponseHelper
from app.domain.models.pagination import PaginationParams
from app.domain.models.user import User, UserResponse, UserUpdate
from app.domain.services.user_service import UserService
from app.infrastructure.security.dependencies import get_current_active_user

router = APIRouter(prefix="/users", tags=["Users"])
logger = get_logger(__name__)


@router.get("/me", response_model=dict, summary="Get current user profile")
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Get current authenticated user's profile information.

    Returns detailed profile information for the currently logged-in user
    including personal details, account status, and timestamps.

    Args:
        current_user: Currently authenticated user from JWT token

    Returns:
        ResponseHelper.success with user profile data

    Raises:
        HTTPException(401): User not authenticated or token invalid
        HTTPException(500): Internal server error retrieving profile
    """
    try:
        user_data = UserResponse(
            _id=current_user.id,
            email=current_user.email,
            username=current_user.username,
            full_name=current_user.full_name,
            bio=current_user.bio,
            age=current_user.age,
            location=current_user.location,
            gender=current_user.gender,
            avatar_url=current_user.avatar_url,
            is_active=current_user.is_active,
            is_verified=current_user.is_verified,
            created_at=current_user.created_at,
            last_login=current_user.last_login,
            telegram_id=current_user.telegram_id,
            onboarding_status=current_user.onboarding_status,
            onboarding_completed_at=current_user.onboarding_completed_at,
            last_activity_at=current_user.last_activity_at,
            last_visited_page=current_user.last_visited_page,
            last_visited_url=current_user.last_visited_url,
            deleted_at=current_user.deleted_at,
        )

        logger.info("User profile retrieved", extra={"user_id": str(current_user.id)})
        return ResponseHelper.success(
            data=user_data, msg="User profile retrieved successfully"
        )

    except Exception as e:
        logger.exception("Error retrieving user profile: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/me", response_model=dict, summary="Update current user profile")
async def update_current_user_profile(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
) -> Dict[str, Any]:
    """
    Update current user's profile information.

    Allows users to update their profile fields such as full name, bio, avatar,
    and other personal information. Only the authenticated user can update their own profile.

    Args:
        user_data: User profile update data
        current_user: Currently authenticated user from JWT token
        user_service: Injected user service instance

    Returns:
        ResponseHelper.updated with updated user data

    Raises:
        HTTPException(400): Invalid input data or validation errors
        HTTPException(401): User not authenticated
        HTTPException(404): User not found during update
        HTTPException(500): Internal server error during update
    """
    try:
        updated_user = await user_service.update_user(str(current_user.id), user_data)
        if not updated_user:
            logger.error(
                "Failed to update user profile - user not found",
                extra={"user_id": str(current_user.id)},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        logger.info("User profile updated", extra={"user_id": str(current_user.id)})
        return ResponseHelper.updated(
            data=updated_user, msg="Profile updated successfully"
        )

    except HTTPException:
        raise
    except PydanticValidationError as e:
        logger.warning(
            "User profile update validation error",
            extra={"user_id": str(current_user.id), "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except ValidationError as e:
        logger.warning(
            "User profile update business validation error",
            extra={"user_id": str(current_user.id), "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except NotFoundError as e:
        logger.warning(
            "User not found during profile update",
            extra={"user_id": str(current_user.id), "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("Unexpected error updating user profile: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{user_id}", response_model=dict, summary="Get user by ID")
async def get_user_by_id(
    user_id: str = Path(..., min_length=24, max_length=24, description="User ID"),
    user_service: UserService = Depends(get_user_service),
) -> Dict[str, Any]:
    """
    Get user information by user ID.

    Returns public profile information for the specified user.
    Only public information is returned to protect user privacy.

    Args:
        user_id: MongoDB ObjectId string of the user
        user_service: Injected user service instance

    Returns:
        ResponseHelper.success with user data

    Raises:
        HTTPException(400): Invalid user ID format
        HTTPException(404): User not found
        HTTPException(500): Internal server error during lookup
    """
    try:
        user = await user_service.get_user_by_id(user_id)
        if not user:
            logger.warning("User not found", extra={"requested_user_id": user_id})
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        logger.debug("User retrieved by ID", extra={"user_id": user_id})
        return ResponseHelper.success(data=user, msg="User retrieved successfully")

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid user ID format", extra={"user_id": user_id, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
        )
    except NotFoundError as e:
        logger.warning(
            "User not found for lookup", extra={"user_id": user_id, "error": str(e)}
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error retrieving user by ID: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/", response_model=dict, summary="Get paginated users list")
async def get_users(
    pagination: PaginationParams = Depends(),
    user_service: UserService = Depends(get_user_service),
) -> Dict[str, Any]:
    """
    Get paginated list of all users.

    Returns a paginated list of users with skip and limit parameters.
    Only public user information is returned to protect privacy.

    Args:
        pagination: Pagination parameters (skip, limit)
        user_service: Injected user service instance

    Returns:
        ResponseHelper.success with paginated user data

    Raises:
        HTTPException(400): Invalid pagination parameters
        HTTPException(500): Internal server error during user retrieval
    """
    try:
        result = await user_service.get_users(pagination)

        logger.debug(
            "Users list retrieved",
            extra={
                "skip": pagination.skip,
                "limit": pagination.limit,
                "count": len(result.items),
            },
        )

        return ResponseHelper.success(
            data=result,
            msg="Users retrieved successfully",
        )

    except PydanticValidationError as e:
        logger.warning("Invalid pagination parameters", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pagination parameters: {str(e)}",
        )
    except ValidationError as e:
        logger.warning("Pagination validation error", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("Unexpected error retrieving users list: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
