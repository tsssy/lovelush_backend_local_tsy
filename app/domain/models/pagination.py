"""Pagination models and utilities."""

from typing import Any, List

from pydantic import Field, computed_field

from .common import Schema


class PaginationParams(Schema):
    """Standardized pagination parameters."""

    page: int = Field(default=1, ge=1, description="Page number (starts from 1)")
    page_size: int = Field(
        default=20, ge=1, le=100, description="Number of items per page"
    )

    @computed_field
    @property
    def skip(self) -> int:
        """Calculate skip value for database queries."""
        return (self.page - 1) * self.page_size

    @computed_field
    @property
    def limit(self) -> int:
        """Get limit value for database queries."""
        return self.page_size


class PaginationResponse(Schema):
    """Standardized pagination response."""

    items: List[Any]
    total_items: int
    total_pages: int
    current_page: int
    page_size: int
    has_next: bool
    has_previous: bool

    @classmethod
    def create(
        cls, items: List[Any], total_items: int, page: int, page_size: int
    ) -> "PaginationResponse":
        """Create pagination response."""
        total_pages = (total_items + page_size - 1) // page_size  # Ceiling division

        return cls(
            items=items,
            total_items=total_items,
            total_pages=total_pages,
            current_page=page,
            page_size=page_size,
            has_next=page < total_pages,
            has_previous=page > 1,
        )
