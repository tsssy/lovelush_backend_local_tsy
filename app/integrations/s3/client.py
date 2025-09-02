"""S3-compatible storage integration using boto3 client."""

import uuid
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError

from app.core.config.settings import settings
from app.core.initializer import ComponentInitializer
from app.core.logging import get_logger

logger = get_logger(__name__)


class S3Client:
    """S3-compatible storage client for file operations."""

    def __init__(self):
        """Initialize S3 client with configuration."""
        self._client = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize boto3 S3 client for S3-compatible storage."""
        if self._initialized:
            return

        try:
            # Configure client for S3-compatible storage (R2, AWS S3, etc.)
            config = Config(
                region_name="auto", retries={"max_attempts": 3, "mode": "standard"}
            )

            self._client = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key_id,
                aws_secret_access_key=settings.s3_secret_access_key,
                config=config,
            )
            self._initialized = True
            logger.info("S3 client initialized successfully")
        except NoCredentialsError:
            logger.error("S3 credentials not found")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise

    def cleanup(self) -> None:
        """Cleanup the S3 client."""
        self._client = None
        self._initialized = False

    def generate_presigned_upload_url(
        self, file_key: str, content_type: str, expires_in: int = 600
    ) -> Optional[str]:
        """
        Generate presigned URL for file upload to S3-compatible storage.

        Args:
            file_key: S3 key for the file
            content_type: MIME type of the file
            expires_in: URL expiration time in seconds (default: 600)

        Returns:
            Presigned upload URL or None if failed
        """
        if not self._initialized or self._client is None:
            raise RuntimeError("S3 client not initialized. Call initialize() first.")

        try:
            presigned_url = self._client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": settings.s3_bucket_name,
                    "Key": file_key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_in,
            )
            logger.info(f"Generated presigned URL for key: {file_key}")
            return presigned_url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {file_key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating presigned URL: {e}")
            return None

    def get_file_url(self, file_key: str) -> str:
        """
        Get public URL for a file in S3-compatible storage.

        Args:
            file_key: S3 key for the file

        Returns:
            Public URL for the file
        """
        return f"{settings.s3_public_url}/{file_key}"

    def generate_file_key(
        self,
        agent_id: str,
        subaccount_id: str,
        file_extension: str,
        upload_type: str = "photos",
    ) -> str:
        """
        Generate structured file key for S3 storage.

        Args:
            agent_id: Agent ID
            subaccount_id: Subaccount ID
            file_extension: File extension (with dot)
            upload_type: Type of upload (avatar or photos)

        Returns:
            Structured file key
        """
        file_uuid = str(uuid.uuid4())
        return f"agents/{agent_id}/subaccounts/{subaccount_id}/{upload_type}/{file_uuid}{file_extension}"

    def delete_file(self, file_key: str) -> bool:
        """
        Delete file from S3-compatible storage.

        Args:
            file_key: S3 key for the file to delete

        Returns:
            True if successful, False otherwise
        """
        if not self._initialized or self._client is None:
            raise RuntimeError("S3 client not initialized. Call initialize() first.")

        try:
            self._client.delete_object(Bucket=settings.s3_bucket_name, Key=file_key)
            logger.info(f"Successfully deleted file: {file_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete file {file_key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting file: {e}")
            return False


class S3Initializer(ComponentInitializer):
    """S3 client component initializer."""

    def __init__(self, s3_client: S3Client):
        self._s3_client = s3_client

    @property
    def name(self) -> str:
        return "S3 Client"

    async def initialize(self) -> None:
        """Initialize S3 client."""
        self._s3_client.initialize()
        logger.info("S3 client initialized successfully")

    async def cleanup(self) -> None:
        """Cleanup S3 client."""
        self._s3_client.cleanup()
        logger.info("S3 client cleaned up successfully")


# Global instances
s3_client = S3Client()
s3_initializer = S3Initializer(s3_client)
