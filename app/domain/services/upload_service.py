"""Upload service for handling file uploads with S3-compatible storage."""

import mimetypes
from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.infrastructure.database.repositories.agent_repository import (
    SubAccountRepository,
)
from app.integrations.s3 import s3_client

logger = get_logger(__name__)


class UploadService:
    """Service for handling file upload operations."""

    def __init__(self, sub_account_repository: Optional[SubAccountRepository] = None):
        """Initialize upload service with dependencies."""
        self.sub_account_repository = sub_account_repository or SubAccountRepository()

    async def generate_presigned_upload_url(
        self,
        agent_id: str,
        subaccount_id: str,
        file_type: str,
        upload_type: str,
        expires_in: int = 600,
    ) -> Dict[str, Any]:
        """
        Generate presigned URL for subaccount photo or avatar upload.

        Args:
            agent_id: Agent ID
            subaccount_id: Subaccount ID
            file_type: File MIME type or extension
            upload_type: Type of upload (avatar or photos)
            expires_in: URL expiration time in seconds

        Returns:
            Dictionary with upload URL and file information

        Raises:
            ValueError: If validation fails
            RuntimeError: If presigned URL generation fails
        """
        # Validate subaccount ownership
        subaccount = await self.sub_account_repository.get_by_id(subaccount_id)
        if not subaccount:
            raise ValueError("Subaccount not found")

        if str(subaccount.agent_id) != agent_id:
            raise ValueError("Agent is not authorized for this subaccount")

        # Determine file extension from MIME type or extension
        file_extension = self._get_file_extension(file_type)
        if not self._is_allowed_file_type(file_extension):
            raise ValueError("File type not allowed. Only images are supported.")

        # Generate unique file key with upload type
        file_key = s3_client.generate_file_key(
            agent_id=agent_id,
            subaccount_id=subaccount_id,
            file_extension=file_extension,
            upload_type=upload_type,
        )

        # Generate presigned URL
        presigned_url = s3_client.generate_presigned_upload_url(
            file_key=file_key,
            content_type=self._get_content_type(file_extension),
            expires_in=expires_in,
        )

        if not presigned_url:
            raise RuntimeError("Failed to generate presigned URL")

        # Generate public file URL
        public_url = s3_client.get_file_url(file_key)

        logger.info(
            f"Generated presigned URL for subaccount {subaccount_id}, type: {upload_type}"
        )

        return {
            "upload_url": presigned_url,
            "file_key": file_key,
            "public_url": public_url,
            "expires_in": expires_in,
            "upload_type": upload_type,
        }

    def _get_file_extension(self, file_type: str) -> str:
        """Get file extension from MIME type or extension string."""
        if file_type.startswith("."):
            return file_type.lower()

        # Handle MIME types
        if "/" in file_type:
            extension = mimetypes.guess_extension(file_type)
            if extension:
                return extension.lower()

        # Assume it's already an extension if not a MIME type
        if not file_type.startswith("."):
            file_type = f".{file_type}"

        return file_type.lower()

    def _is_allowed_file_type(self, extension: str) -> bool:
        """Check if file extension is allowed for uploads."""
        allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
        return extension.lower() in allowed_extensions

    def _get_content_type(self, extension: str) -> str:
        """Get MIME content type from file extension."""
        content_type_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }
        return content_type_map.get(extension.lower(), "application/octet-stream")
