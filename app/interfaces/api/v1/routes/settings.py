"""API endpoints for app settings management."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import get_app_settings_service
from app.core.exceptions.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.responses import ResponseHelper
from app.domain.models.settings import (
    AppSettingsCreate,
    AppSettingsUpdate,
)
from app.domain.models.user import User
from app.domain.services.app_settings_service import AppSettingsService
from app.infrastructure.security.dependencies import (
    get_current_active_user,
    get_current_admin_agent_only,
)

router = APIRouter(prefix="/settings", tags=["Settings"])
logger = get_logger(__name__)


@router.post(
    "/",
    summary="Create app settings",
    dependencies=[Depends(get_current_admin_agent_only)],
)
async def create_settings(
    settings_data: AppSettingsCreate,
    app_settings_service: AppSettingsService = Depends(get_app_settings_service),
) -> Dict[str, Any]:
    """
    Create new app settings.

    Args:
        settings_data: Settings creation data
        app_settings_service: Injected settings service

    Returns:
        ResponseHelper.created with settings data

    Raises:
        HTTPException(400): Validation error
        HTTPException(409): Settings name already exists
    """
    try:
        settings = await app_settings_service.create_settings(settings_data)

        logger.info(
            "App settings created successfully",
            extra={
                "settings_id": str(settings.id),
                "settings_name": settings.name,
                "is_active": settings.is_active,
                "is_default": settings.is_default,
            },
        )

        return ResponseHelper.created(
            data=settings.model_dump(), msg="Settings created successfully"
        )

    except ValidationError as e:
        logger.warning(f"Settings creation validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/",
    summary="List app settings",
    dependencies=[Depends(get_current_admin_agent_only)],
)
async def list_settings(
    include_inactive: bool = Query(False, description="Include inactive settings"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    app_settings_service: AppSettingsService = Depends(get_app_settings_service),
) -> Dict[str, Any]:
    """
    Get list of app settings.

    Args:
        include_inactive: Whether to include inactive settings
        limit: Maximum number of results
        offset: Number of results to skip
        app_settings_service: Injected settings service

    Returns:
        ResponseHelper.success with settings list
    """
    try:
        settings_list = await app_settings_service.list_settings(
            include_inactive=include_inactive, limit=limit, offset=offset
        )

        logger.info(
            "Settings list retrieved",
            extra={
                "count": len(settings_list),
                "include_inactive": include_inactive,
                "limit": limit,
                "offset": offset,
            },
        )

        return ResponseHelper.success(
            data={
                "settings": [settings.model_dump() for settings in settings_list],
                "total": len(settings_list),
                "limit": limit,
                "offset": offset,
            },
            msg="Settings retrieved successfully",
        )

    except Exception as e:
        logger.error(f"Error retrieving settings list: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/active",
    summary="Get active settings",
    dependencies=[Depends(get_current_admin_agent_only)],
)
async def get_active_settings(
    app_settings_service: AppSettingsService = Depends(get_app_settings_service),
) -> Dict[str, Any]:
    """
    Get current active settings.

    Args:
        app_settings_service: Injected settings service

    Returns:
        ResponseHelper.success with active settings

    Raises:
        HTTPException(404): No active settings found
    """
    try:
        settings = await app_settings_service.get_active_settings()

        logger.info(
            "Active settings retrieved",
            extra={
                "settings_id": str(settings.id),
                "settings_name": settings.name,
            },
        )

        return ResponseHelper.success(
            data=settings.model_dump(), msg="Active settings retrieved"
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving active settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/default",
    summary="Get default settings",
    dependencies=[Depends(get_current_admin_agent_only)],
)
async def get_default_settings(
    app_settings_service: AppSettingsService = Depends(get_app_settings_service),
) -> Dict[str, Any]:
    """
    Get default settings.

    Args:
        app_settings_service: Injected settings service

    Returns:
        ResponseHelper.success with default settings

    Raises:
        HTTPException(404): No default settings found
    """
    try:
        settings = await app_settings_service.get_default_settings()

        logger.info(
            "Default settings retrieved",
            extra={
                "settings_id": str(settings.id),
                "settings_name": settings.name,
            },
        )

        return ResponseHelper.success(
            data=settings.model_dump(), msg="Default settings retrieved"
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving default settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/by-name/{name}",
    summary="Get settings by name",
    dependencies=[Depends(get_current_admin_agent_only)],
)
async def get_settings_by_name(
    name: str,
    app_settings_service: AppSettingsService = Depends(get_app_settings_service),
) -> Dict[str, Any]:
    """
    Get settings by name.

    Args:
        name: Name of the settings
        app_settings_service: Injected settings service

    Returns:
        ResponseHelper.success with settings data

    Raises:
        HTTPException(404): Settings not found
    """
    try:
        settings = await app_settings_service.get_settings_by_name(name)

        logger.info(
            "Settings retrieved by name",
            extra={
                "settings_name": name,
                "settings_id": str(settings.id),
            },
        )

        return ResponseHelper.success(
            data=settings.model_dump(), msg="Settings retrieved successfully"
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving settings by name '{name}': {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/user",
    summary="Get user settings",
    response_model=Dict[str, Any],
)
async def get_user_settings(
    current_user: User = Depends(get_current_active_user),
    app_settings_service: AppSettingsService = Depends(get_app_settings_service),
) -> Dict[str, Any]:
    """
    Get common settings for the current user (cost per message, cost per match, etc.).

    Args:
        current_user: Authenticated user
        app_settings_service: Injected settings service

    Returns:
        ResponseHelper.success with user settings data

    Raises:
        HTTPException(500): Internal server error
    """
    try:
        user_settings = await app_settings_service.get_user_settings()

        logger.info(
            "User settings retrieved",
            extra={
                "user_id": str(current_user.id),
                "username": current_user.username,
            },
        )

        return ResponseHelper.success(
            data=user_settings.model_dump(), msg="User settings retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error retrieving user settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{settings_id}",
    summary="Get settings by ID",
    dependencies=[Depends(get_current_admin_agent_only)],
)
async def get_settings(
    settings_id: str,
    app_settings_service: AppSettingsService = Depends(get_app_settings_service),
) -> Dict[str, Any]:
    """
    Get app settings by ID.

    Args:
        settings_id: ID of the settings
        app_settings_service: Injected settings service

    Returns:
        ResponseHelper.success with settings data

    Raises:
        HTTPException(404): Settings not found
    """
    try:
        settings = await app_settings_service.get_settings(settings_id)

        logger.info(
            "Settings retrieved",
            extra={
                "settings_id": settings_id,
                "settings_name": settings.name,
            },
        )

        return ResponseHelper.success(
            data=settings.model_dump(), msg="Settings retrieved successfully"
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving settings {settings_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put(
    "/{settings_id}",
    summary="Update settings",
    dependencies=[Depends(get_current_admin_agent_only)],
)
async def update_settings(
    settings_id: str,
    settings_data: AppSettingsUpdate,
    app_settings_service: AppSettingsService = Depends(get_app_settings_service),
) -> Dict[str, Any]:
    """
    Update app settings.

    Args:
        settings_id: ID of settings to update
        settings_data: Settings update data
        app_settings_service: Injected settings service

    Returns:
        ResponseHelper.success with updated settings data

    Raises:
        HTTPException(400): Validation error
        HTTPException(404): Settings not found
    """
    try:
        settings = await app_settings_service.update_settings(
            settings_id, settings_data
        )

        logger.info(
            "Settings updated successfully",
            extra={
                "settings_id": settings_id,
                "settings_name": settings.name,
            },
        )

        return ResponseHelper.success(
            data=settings.model_dump(), msg="Settings updated successfully"
        )

    except ValidationError as e:
        logger.warning(f"Settings update validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error updating settings {settings_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete(
    "/{settings_id}",
    summary="Delete settings",
    dependencies=[Depends(get_current_admin_agent_only)],
)
async def delete_settings(
    settings_id: str,
    app_settings_service: AppSettingsService = Depends(get_app_settings_service),
) -> Dict[str, Any]:
    """
    Delete app settings (soft delete).

    Args:
        settings_id: ID of settings to delete
        app_settings_service: Injected settings service

    Returns:
        ResponseHelper.success with deletion confirmation

    Raises:
        HTTPException(400): Cannot delete active/default settings
        HTTPException(404): Settings not found
    """
    try:
        success = await app_settings_service.delete_settings(settings_id)

        if success:
            logger.info(
                "Settings deleted successfully",
                extra={"settings_id": settings_id},
            )
            return ResponseHelper.success(msg="Settings deleted successfully")
        else:
            raise HTTPException(status_code=500, detail="Failed to delete settings")

    except ValidationError as e:
        logger.warning(f"Settings deletion validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error deleting settings {settings_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{settings_id}/activate",
    summary="Activate settings",
    dependencies=[Depends(get_current_admin_agent_only)],
)
async def activate_settings(
    settings_id: str,
    app_settings_service: AppSettingsService = Depends(get_app_settings_service),
) -> Dict[str, Any]:
    """
    Set specific settings as active.

    Args:
        settings_id: ID of settings to activate
        app_settings_service: Injected settings service

    Returns:
        ResponseHelper.success with activated settings data

    Raises:
        HTTPException(404): Settings not found
        HTTPException(400): Activation failed
    """
    try:
        settings = await app_settings_service.activate_settings(settings_id)

        logger.info(
            "Settings activated successfully",
            extra={
                "settings_id": settings_id,
                "settings_name": settings.name,
            },
        )

        return ResponseHelper.success(
            data=settings.model_dump(), msg="Settings activated successfully"
        )

    except ValidationError as e:
        logger.warning(f"Settings activation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error activating settings {settings_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{settings_id}/set-default",
    summary="Set as default",
    dependencies=[Depends(get_current_admin_agent_only)],
)
async def set_default_settings(
    settings_id: str,
    app_settings_service: AppSettingsService = Depends(get_app_settings_service),
) -> Dict[str, Any]:
    """
    Set specific settings as default.

    Args:
        settings_id: ID of settings to set as default
        app_settings_service: Injected settings service

    Returns:
        ResponseHelper.success with default settings data

    Raises:
        HTTPException(404): Settings not found
        HTTPException(400): Operation failed
    """
    try:
        settings = await app_settings_service.set_default_settings(settings_id)

        logger.info(
            "Default settings set successfully",
            extra={
                "settings_id": settings_id,
                "settings_name": settings.name,
            },
        )

        return ResponseHelper.success(
            data=settings.model_dump(), msg="Default settings set successfully"
        )

    except ValidationError as e:
        logger.warning(f"Set default settings failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error setting default settings {settings_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
