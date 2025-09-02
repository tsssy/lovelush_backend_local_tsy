"""Core exceptions module."""

from typing import Any, Dict, Optional


class BaseCustomException(Exception):
    """Base custom exception class."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        api_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.api_code = api_code or status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(BaseCustomException):
    """Validation error exception."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=400, api_code=400, details=details)


class NotFoundError(BaseCustomException):
    """Resource not found exception."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=404, api_code=404, details=details)


class UnauthorizedError(BaseCustomException):
    """Unauthorized access exception."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=401, api_code=401, details=details)


class ForbiddenError(BaseCustomException):
    """Forbidden access exception."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=403, api_code=403, details=details)


class ResourceConflictError(BaseCustomException):
    """Resource conflict exception."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=409, api_code=409, details=details)
