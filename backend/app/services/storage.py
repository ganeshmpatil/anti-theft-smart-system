"""MinIO object storage service for alert snapshots."""

import io
import logging
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Manages alert snapshot storage in S3-compatible backends (MinIO, Supabase, etc.)."""

    def __init__(self):
        endpoint = settings.minio_endpoint

        # Supabase S3 endpoint includes a path — extract host and set region
        # e.g. "hixzeyeijkhbhphmjynq.supabase.co/storage/v1/s3"
        if "/storage/v1/s3" in endpoint:
            host = endpoint.split("/storage/v1/s3")[0]
            self._client = Minio(
                host,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=True,
                region="ap-south-1",
            )
            # Supabase S3 uses path-style but Minio client handles it
        else:
            self._client = Minio(
                endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=settings.minio_secure,
            )
        self._bucket = settings.minio_bucket

    def ensure_bucket(self):
        """Create the bucket if it doesn't exist."""
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
                logger.info("Created bucket: %s", self._bucket)
            else:
                logger.info("Bucket exists: %s", self._bucket)
        except S3Error as e:
            # Supabase/some providers may not support bucket_exists — treat as OK
            if "BucketAlreadyOwnedByYou" in str(e) or "BucketAlreadyExists" in str(e):
                logger.info("Bucket already exists: %s", self._bucket)
            else:
                logger.warning("Bucket check failed (non-fatal): %s", e)

    def upload_image(self, object_name: str, image_data: bytes,
                     content_type: str = "image/jpeg") -> bool:
        """Upload an alert snapshot image.

        Args:
            object_name: e.g., 'FARM-MH-001/alert_20260904_221503_cam1.jpg'
            image_data: JPEG bytes
            content_type: MIME type

        Returns:
            True if upload successful
        """
        try:
            data = io.BytesIO(image_data)
            self._client.put_object(
                self._bucket, object_name, data, len(image_data),
                content_type=content_type,
            )
            logger.info("Uploaded image: %s (%d bytes)", object_name, len(image_data))
            return True
        except S3Error:
            logger.exception("Failed to upload image: %s", object_name)
            return False

    def get_presigned_url(self, object_name: str,
                          expires: timedelta = timedelta(hours=1)) -> str:
        """Generate a presigned URL for downloading an image.

        Args:
            object_name: MinIO object key
            expires: URL expiration time

        Returns:
            Presigned download URL
        """
        try:
            return self._client.presigned_get_object(
                self._bucket, object_name, expires=expires,
            )
        except S3Error:
            logger.exception("Failed to generate presigned URL for %s", object_name)
            return ""

    def delete_image(self, object_name: str) -> bool:
        """Delete an image from storage."""
        try:
            self._client.remove_object(self._bucket, object_name)
            return True
        except S3Error:
            return False
