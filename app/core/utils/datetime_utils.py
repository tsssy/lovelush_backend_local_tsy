"""Datetime utility functions for consistent handling across the application."""

from datetime import datetime, timezone
from typing import Optional


def safe_isoformat(dt: Optional[datetime]) -> Optional[str]:
    """
    Safely convert datetime to ISO format string.

    Args:
        dt: Datetime object that might be None

    Returns:
        ISO format string if datetime exists, None otherwise
    """
    if dt is None:
        return None
    return dt.isoformat()


def safe_isoformat_or_now(dt: Optional[datetime]) -> str:
    """
    Safely convert datetime to ISO format string, using current time as fallback.

    Args:
        dt: Datetime object that might be None

    Returns:
        ISO format string of datetime or current UTC time as fallback
    """
    if dt is None:
        return datetime.now(timezone.utc).isoformat()
    return dt.isoformat()


def ensure_datetime_or_now(dt: Optional[datetime]) -> datetime:
    """
    Ensure we have a datetime object, using current time as fallback.

    Args:
        dt: Datetime object that might be None

    Returns:
        The datetime object or current UTC time as fallback
    """
    if dt is None:
        return datetime.now(timezone.utc)
    return dt
