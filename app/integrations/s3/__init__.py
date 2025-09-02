"""S3-compatible storage integration package."""

from .client import S3Client, s3_client, s3_initializer

__all__ = ["S3Client", "s3_client", "s3_initializer"]
