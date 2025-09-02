"""Admin maintenance API routes for match system management."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.logging import get_logger
from app.core.responses import ResponseHelper
from app.domain.services.match_maintenance_service import MatchMaintenanceService
from app.infrastructure.security.dependencies import get_current_admin_agent_only
from app.interfaces.telegram.setup import telegram_bot_setup

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])
logger = get_logger(__name__)


@router.post("/matches/expire", response_model=dict, summary="Expire old matches")
async def expire_old_matches(
    current_admin: dict = Depends(get_current_admin_agent_only),
    maintenance_service: MatchMaintenanceService = Depends(
        lambda: MatchMaintenanceService()
    ),
) -> Dict[str, Any]:
    """
    Manually trigger expiration of old matches (Admin only).

    This endpoint allows administrators to manually run the match expiration
    process to clean up expired daily free matches and other time-limited matches.

    Args:
        current_admin: Currently authenticated admin user
        maintenance_service: Injected maintenance service

    Returns:
        ResponseHelper.success with expiration results

    Raises:
        HTTPException(401): User not authenticated as admin
        HTTPException(500): Internal server error during maintenance
    """
    try:
        expired_count = await maintenance_service.expire_old_matches()

        logger.info(
            f"Admin {current_admin['agent_name']} triggered match expiration: {expired_count} matches expired"
        )

        return ResponseHelper.success(
            data={"matches_expired": expired_count},
            msg=f"Successfully expired {expired_count} old matches",
        )

    except Exception as e:
        logger.exception(f"Failed to expire matches: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to expire matches",
        )


@router.get("/matches/health", response_model=dict, summary="Get match system health")
async def get_match_system_health(
    current_admin: dict = Depends(get_current_admin_agent_only),
    maintenance_service: MatchMaintenanceService = Depends(
        lambda: MatchMaintenanceService()
    ),
) -> Dict[str, Any]:
    """
    Get match system health statistics (Admin only).

    Provides comprehensive statistics about the match system including
    total matches, available matches, expired matches, and system status.

    Args:
        current_admin: Currently authenticated admin user
        maintenance_service: Injected maintenance service

    Returns:
        ResponseHelper.success with health statistics

    Raises:
        HTTPException(401): User not authenticated as admin
        HTTPException(500): Internal server error during health check
    """
    try:
        health_data = await maintenance_service.get_match_system_health()

        logger.info(
            f"Admin {current_admin['agent_name']} requested match system health check"
        )

        return ResponseHelper.success(
            data=health_data, msg="Match system health check completed"
        )

    except Exception as e:
        logger.exception(f"Failed to get match system health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system health",
        )


@router.post("/matches/daily", response_model=dict, summary="Run daily maintenance")
async def run_daily_maintenance(
    current_admin: dict = Depends(get_current_admin_agent_only),
    maintenance_service: MatchMaintenanceService = Depends(
        lambda: MatchMaintenanceService()
    ),
) -> Dict[str, Any]:
    """
    Manually trigger daily maintenance tasks (Admin only).

    Runs all daily maintenance tasks including match expiration,
    old record cleanup, and system health checks.

    Args:
        current_admin: Currently authenticated admin user
        maintenance_service: Injected maintenance service

    Returns:
        ResponseHelper.success with maintenance results

    Raises:
        HTTPException(401): User not authenticated as admin
        HTTPException(500): Internal server error during maintenance
    """
    try:
        results = await maintenance_service.run_daily_maintenance()

        logger.info(
            f"Admin {current_admin['agent_name']} triggered daily maintenance",
            extra={"maintenance_results": results},
        )

        return ResponseHelper.success(data=results, msg="Daily maintenance completed")

    except Exception as e:
        logger.exception(f"Failed to run daily maintenance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run daily maintenance",
        )


@router.post("/matches/cleanup", response_model=dict, summary="Clean up old records")
async def cleanup_old_records(
    days_old: int = Query(30, ge=1, le=365, description="Age in days for cleanup"),
    current_admin: dict = Depends(get_current_admin_agent_only),
    maintenance_service: MatchMaintenanceService = Depends(
        lambda: MatchMaintenanceService()
    ),
) -> Dict[str, Any]:
    """
    Clean up old consumed match records (Admin only).

    Identifies and optionally cleans up consumed match records older than
    the specified number of days for database optimization.

    Args:
        days_old: Age threshold in days for cleanup (1-365)
        current_admin: Currently authenticated admin user
        maintenance_service: Injected maintenance service

    Returns:
        ResponseHelper.success with cleanup results

    Raises:
        HTTPException(400): Invalid days_old parameter
        HTTPException(401): User not authenticated as admin
        HTTPException(500): Internal server error during cleanup
    """
    try:
        cleaned_count = await maintenance_service.cleanup_old_match_records(days_old)

        logger.info(
            f"Admin {current_admin['agent_name']} triggered record cleanup: "
            f"{cleaned_count} records found older than {days_old} days"
        )

        return ResponseHelper.success(
            data={
                "days_old_threshold": days_old,
                "records_found": cleaned_count,
                "note": "Records identified for potential archival (not deleted)",
            },
            msg=f"Found {cleaned_count} records older than {days_old} days",
        )

    except ValueError as e:
        logger.warning(f"Invalid cleanup parameters: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to cleanup old records: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup old records",
        )


@router.post("/telegram/webhook", response_model=dict, summary="Setup Telegram webhook")
async def setup_telegram_webhook(
    current_admin: dict = Depends(get_current_admin_agent_only),
) -> Dict[str, Any]:
    """
    Manually trigger Telegram webhook setup (Admin only).

    This endpoint allows administrators to manually set up the Telegram
    webhook if it failed during startup due to networking issues.

    Args:
        current_admin: Currently authenticated admin user

    Returns:
        ResponseHelper with webhook setup result

    Raises:
        HTTPException(401): User not authenticated as admin
        HTTPException(500): Internal server error during webhook setup
    """
    try:
        success = await telegram_bot_setup.setup_webhook_now()

        logger.info(
            f"Admin {current_admin['agent_name']} triggered manual webhook setup: {'success' if success else 'failed'}"
        )

        if success:
            return ResponseHelper.success(
                data={"webhook_status": "configured"},
                msg="Telegram webhook setup successful",
            )
        else:
            return ResponseHelper.error(
                msg="Failed to setup Telegram webhook - check logs for details",
                code=500,
            )

    except Exception as e:
        logger.exception(f"Failed to setup Telegram webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to setup Telegram webhook",
        )
