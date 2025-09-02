"""Unified API response structure and helper methods."""

from typing import Any, Dict, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


def serialize_response_data(data: Any) -> Any:
    """Recursively serialize response data, converting Pydantic models to dicts."""
    if isinstance(data, BaseModel):
        return data.model_dump()
    elif isinstance(data, dict):
        return {k: serialize_response_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [serialize_response_data(item) for item in data]
    else:
        return data


class APIResponse(BaseModel, Generic[T]):
    """Unified API response structure."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"code": 200, "msg": "Success", "data": {}}}
    )

    code: int
    msg: str
    data: Optional[T] = None


class APIResponseHelper:
    """Helper class for creating standardized API responses."""

    # Success codes
    SUCCESS = 200
    CREATED = 201
    NO_CONTENT = 204

    # Client error codes
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    VALIDATION_ERROR = 422

    # Server error codes
    INTERNAL_SERVER_ERROR = 500
    SERVICE_UNAVAILABLE = 503

    # Success messages
    SUCCESS_MSG = "Success"
    CREATED_MSG = "Created successfully"
    UPDATED_MSG = "Updated successfully"
    DELETED_MSG = "Deleted successfully"

    # Error messages
    BAD_REQUEST_MSG = "Bad request"
    UNAUTHORIZED_MSG = "Unauthorized"
    FORBIDDEN_MSG = "Forbidden"
    NOT_FOUND_MSG = "Resource not found"
    CONFLICT_MSG = "Resource conflict"
    VALIDATION_ERROR_MSG = "Validation error"
    INTERNAL_SERVER_ERROR_MSG = "Internal server error"
    SERVICE_UNAVAILABLE_MSG = "Service unavailable"

    @classmethod
    def success(
        cls, data: Any = None, msg: str = SUCCESS_MSG, code: int = SUCCESS
    ) -> Dict[str, Any]:
        """Create a success response."""
        return {"code": code, "msg": msg, "data": serialize_response_data(data)}

    @classmethod
    def created(cls, data: Any = None, msg: str = CREATED_MSG) -> Dict[str, Any]:
        """Create a created response."""
        return cls.success(data=data, msg=msg, code=cls.CREATED)

    @classmethod
    def updated(cls, data: Any = None, msg: str = UPDATED_MSG) -> Dict[str, Any]:
        """Create an updated response."""
        return cls.success(data=data, msg=msg, code=cls.SUCCESS)

    @classmethod
    def deleted(cls, msg: str = DELETED_MSG) -> Dict[str, Any]:
        """Create a deleted response."""
        return cls.success(data=None, msg=msg, code=cls.NO_CONTENT)

    @classmethod
    def error(
        cls,
        msg: str = INTERNAL_SERVER_ERROR_MSG,
        code: int = INTERNAL_SERVER_ERROR,
        data: Any = None,
    ) -> Dict[str, Any]:
        """Create an error response."""
        return {"code": code, "msg": msg, "data": serialize_response_data(data)}

    @classmethod
    def bad_request(
        cls, msg: str = BAD_REQUEST_MSG, data: Any = None
    ) -> Dict[str, Any]:
        """Create a bad request response."""
        return cls.error(
            msg=msg, code=cls.BAD_REQUEST, data=serialize_response_data(data)
        )

    @classmethod
    def unauthorized(
        cls, msg: str = UNAUTHORIZED_MSG, data: Any = None
    ) -> Dict[str, Any]:
        """Create an unauthorized response."""
        return cls.error(
            msg=msg, code=cls.UNAUTHORIZED, data=serialize_response_data(data)
        )

    @classmethod
    def forbidden(cls, msg: str = FORBIDDEN_MSG, data: Any = None) -> Dict[str, Any]:
        """Create a forbidden response."""
        return cls.error(
            msg=msg, code=cls.FORBIDDEN, data=serialize_response_data(data)
        )

    @classmethod
    def not_found(cls, msg: str = NOT_FOUND_MSG, data: Any = None) -> Dict[str, Any]:
        """Create a not found response."""
        return cls.error(
            msg=msg, code=cls.NOT_FOUND, data=serialize_response_data(data)
        )

    @classmethod
    def conflict(cls, msg: str = CONFLICT_MSG, data: Any = None) -> Dict[str, Any]:
        """Create a conflict response."""
        return cls.error(msg=msg, code=cls.CONFLICT, data=serialize_response_data(data))

    @classmethod
    def validation_error(
        cls, msg: str = VALIDATION_ERROR_MSG, data: Any = None
    ) -> Dict[str, Any]:
        """Create a validation error response."""
        return cls.error(
            msg=msg, code=cls.VALIDATION_ERROR, data=serialize_response_data(data)
        )


# Convenience alias
ResponseHelper = APIResponseHelper
