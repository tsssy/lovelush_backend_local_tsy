"""
Authentication API endpoints providing secure user authentication and authorization.
Provides endpoints for user registration, login, token refresh, and Telegram-based authentication.
"""

import hashlib
import hmac
import json
import urllib.parse
from datetime import timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError

from app.core.config.settings import settings
from app.core.dependencies import get_user_service
from app.core.logging import get_logger
from app.core.responses import ResponseHelper
from app.domain.models.user import (
    RefreshTokenRequest,
    TelegramAuthRequest,
    UserCreate,
    UserCreateByTelegram,
)
from app.domain.services.user_service import UserService
from app.infrastructure.security.dependencies import get_current_active_user
from app.infrastructure.security.jwt_auth import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_logger(__name__)


def validate_telegram_init_data(init_data: str, bot_token: str) -> Dict[str, Any]:
    """
    Validate Telegram WebApp initData.

    Args:
        init_data: Raw initData string from Telegram WebApp
        bot_token: Telegram bot token for validation

    Returns:
        Dict containing parsed and validated data

    Raises:
        HTTPException: If validation fails
    """
    if not init_data or not bot_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing init_data or bot_token",
        )

    try:
        # Parse the init_data
        parsed_data = urllib.parse.parse_qs(init_data)

        # Extract hash
        received_hash = parsed_data.get("hash", [None])[0]
        if not received_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing hash in init_data",
            )

        # Remove hash from data for verification
        data_check_string_parts = []
        for key, values in parsed_data.items():
            if key != "hash":
                data_check_string_parts.append(f"{key}={values[0]}")

        data_check_string = "\n".join(sorted(data_check_string_parts))

        # Create secret key
        secret_key = hmac.new(
            b"WebAppData", bot_token.encode(), hashlib.sha256
        ).digest()

        # Calculate hash
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        # Verify hash
        if not hmac.compare_digest(calculated_hash, received_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telegram data hash",
            )

        # Parse user data
        user_data = {}
        if "user" in parsed_data:
            user_data = json.loads(parsed_data["user"][0])

        return {
            "user": user_data,
            "start_param": parsed_data.get("start_param", [None])[0],
            "auth_date": parsed_data.get("auth_date", [None])[0],
            "query_id": parsed_data.get("query_id", [None])[0],
        }

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON in init_data: {str(e)}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to validate init_data: {str(e)}",
        ) from e


@router.post("/register", response_model=dict, summary="Register new user")
async def register(
    user_data: UserCreate, user_service: UserService = Depends(get_user_service)
) -> Dict[str, Any]:
    """
    Register a new user account.

    Creates a new user with the provided credentials and returns user information.
    Validates input data and ensures unique email/username constraints.

    Args:
        user_data: User registration data with required fields
        user_service: Injected user service instance

    Returns:
        ResponseHelper.created with user data and success message

    Raises:
        HTTPException(400): Invalid input data or validation errors
        HTTPException(409): User already exists with given email/username
        HTTPException(500): Internal server error during registration
    """
    try:
        user = await user_service.create_user(user_data)
        logger.info("User registered successfully", extra={"user_id": user.id})
        return ResponseHelper.created(data=user, msg="User registered successfully")

    except ValidationError as e:
        logger.warning("User registration validation error", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except ValueError as e:
        logger.warning("User registration conflict", extra={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error during user registration: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/login", response_model=dict, summary="User login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    user_service: UserService = Depends(get_user_service),
) -> Dict[str, Any]:
    """
    Authenticate user and return access tokens.

    Validates user credentials and returns JWT access and refresh tokens
    for authenticated users.

    Args:
        form_data: OAuth2 form with username and password
        user_service: Injected user service instance

    Returns:
        ResponseHelper.success with tokens and user data

    Raises:
        HTTPException(401): Invalid credentials or inactive user
        HTTPException(500): Internal server error during authentication
    """
    try:
        user = await user_service.authenticate_user(
            form_data.username, form_data.password
        )
        if not user:
            logger.warning(
                "Failed login attempt", extra={"username": form_data.username}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user.username, "user_id": str(user.id), "type": "user"},
            expires_delta=access_token_expires,
        )

        refresh_token_expires = timedelta(days=settings.refresh_token_expire_days)
        refresh_token = create_refresh_token(
            data={"sub": user.username, "user_id": str(user.id), "type": "user"},
            expires_delta=refresh_token_expires,
        )

        # Update login timestamp
        await user_service.update_user_login_info(str(user.id))

        login_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user_service._to_user_response(user),
        }

        logger.info("User login successful", extra={"user_id": str(user.id)})
        return ResponseHelper.success(data=login_data, msg="Login successful")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error during user login: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/refresh", response_model=dict, summary="Refresh access token")
async def refresh_access_token(
    request: RefreshTokenRequest,
    user_service: UserService = Depends(get_user_service),
) -> Dict[str, Any]:
    """
    Refresh expired access token using refresh token.

    Validates the provided refresh token and generates a new access token
    for continued authentication.

    Args:
        request: Refresh token request containing the refresh token
        user_service: Injected user service instance

    Returns:
        ResponseHelper.success with new access token

    Raises:
        HTTPException(401): Invalid or expired refresh token
        HTTPException(500): Internal server error during token refresh
    """
    try:
        payload = verify_refresh_token(request.refresh_token)
        username = payload.get("sub")

        if not username:
            logger.warning("Invalid refresh token - missing username")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        user = await user_service.user_repository.get_by_username(username)
        if not user or not user.is_active:
            logger.warning(
                "Refresh token user not found or inactive", extra={"username": username}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        new_access_token = create_access_token(
            data={"sub": user.username, "user_id": str(user.id), "type": "user"},
            expires_delta=access_token_expires,
        )

        logger.info(
            "Access token refreshed successfully", extra={"user_id": str(user.id)}
        )
        return ResponseHelper.success(
            data={"access_token": new_access_token, "token_type": "bearer"},
            msg="Token refreshed successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error during token refresh: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from e


@router.post("/telegram", response_model=dict, summary="Telegram authentication")
async def telegram_auth(
    request: TelegramAuthRequest,
    user_service: UserService = Depends(get_user_service),
) -> Dict[str, Any]:
    """
    Authenticate or register user via Telegram WebApp.

    Validates Telegram initData and either authenticates existing user
    or auto-registers new user based on Telegram credentials.

    Args:
        request: Telegram authentication request with initData and user info
        user_service: Injected user service instance

    Returns:
        ResponseHelper.success with tokens and user data

    Raises:
        HTTPException(400): Invalid initData or registration failure
        HTTPException(401): Authentication failure or inactive account
        HTTPException(500): Internal server error during authentication
    """
    try:
        # Validate initData with bot token
        validated_data = validate_telegram_init_data(
            request.telegram_init_data, settings.telegram_bot_token
        )

        telegram_user_data = validated_data.get("user", {})
        telegram_user_id = str(telegram_user_data.get("id"))
        username = telegram_user_data.get("username") or f"user_{telegram_user_id}"

        # Try to find existing user by Telegram ID
        user = await user_service.authenticate_telegram_user(telegram_user_id)

        if not user:
            # Auto-register user
            user_data = UserCreateByTelegram(
                username=username,
                telegram_id=telegram_user_id,
            )

            try:
                await user_service.create_user(user_data)
                user = await user_service.user_repository.get_by_username(username)
                logger.info(
                    "New Telegram user registered",
                    extra={"telegram_id": telegram_user_id, "username": username},
                )
            except Exception as e:
                logger.error(
                    "Failed to register Telegram user",
                    extra={"telegram_id": telegram_user_id, "error": str(e)},
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e),
                ) from e

        if not user or not user.is_active:
            logger.warning(
                "Telegram authentication failed - inactive or missing user",
                extra={"telegram_id": telegram_user_id},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is inactive or not found",
            )

        # Create tokens
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user.username, "user_id": str(user.id), "type": "user"},
            expires_delta=access_token_expires,
        )

        refresh_token_expires = timedelta(days=settings.refresh_token_expire_days)
        refresh_token = create_refresh_token(
            data={"sub": user.username, "user_id": str(user.id), "type": "user"},
            expires_delta=refresh_token_expires,
        )

        # Update login timestamp
        await user_service.update_user_login_info(str(user.id))

        login_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user_service._to_user_response(user),
            # Include additional Telegram user data for debugging/info
            "telegram_user_data": telegram_user_data,
        }

        logger.info(
            "Telegram authentication successful",
            extra={"user_id": str(user.id), "telegram_id": telegram_user_id},
        )
        return ResponseHelper.success(
            data=login_data, msg="Telegram authentication successful"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error during Telegram authentication: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/update-last-visited", response_model=dict, summary="Update last visited location"
)
async def update_last_visited(
    last_visited_data: Dict[str, str],
    current_user=Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
) -> Dict[str, Any]:
    """
    Update user's last visited location for navigation tracking.

    Args:
        last_visited_data: Dict with 'url' and/or 'page' keys
        current_user: Current authenticated user
        user_service: Injected user service instance

    Returns:
        ResponseHelper.success with update status

    Raises:
        HTTPException(400): Invalid request data
        HTTPException(500): Internal server error during update
    """
    try:
        url = last_visited_data.get("url")
        page = last_visited_data.get("page")

        if not url and not page:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either 'url' or 'page' must be provided",
            )

        success = await user_service.update_user_last_visited(
            str(current_user.id),
            last_visited_url=url,
            last_visited_page=page,
        )

        if not success:
            logger.warning(
                "Failed to update user last visited info",
                extra={"user_id": str(current_user.id)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update last visited information",
            )

        return ResponseHelper.success(
            data={"updated": True}, msg="Last visited location updated successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error updating last visited location: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
