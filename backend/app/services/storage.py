"""S3-compatible object storage service for alert snapshots.

Supports:
- Supabase Storage (via boto3 — requires path-based endpoint)
- MinIO / any S3-compatible backend (via minio client)
"""

import io
import logging
from datetime import timedelta

from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Manages alert snapshot storage in S3-compatible backends."""

    def __init__(self):
        endpoint = settings.minio_endpoint

        if "/storage/v1/s3" in endpoint:
            # Supabase S3 — use boto3 (MinIO client can't handle path-based endpoints)
            self._backend = "supabase"
            self._init_boto3(endpoint)
        else:
            # Standard MinIO / S3-compatible
            self._backend = "minio"
            self._init_minio(endpoint)

        self._bucket = settings.minio_bucket

    def _init_boto3(self, endpoint: str):
        import boto3
        from botocore.config import Config

        url = f"https://{endpoint}" if not endpoint.startswith("http") else endpoint
        self._endpoint_url = url
        self._s3 = boto3.client(
            "s3",
            endpoint_url=url,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            region_name="ap-south-1",
            config=Config(signature_version="s3v4"),
        )

    def _init_minio(self, endpoint: str):
        from minio import Minio

        self._client = Minio(
            endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    def ensure_bucket(self):
        """Create the bucket if it doesn't exist."""
        if self._backend == "supabase":
            try:
                self._s3.head_bucket(Bucket=self._bucket)
                logger.info("Bucket exists: %s", self._bucket)
            except Exception:
                try:
                    self._s3.create_bucket(Bucket=self._bucket)
                    logger.info("Created bucket: %s", self._bucket)
                except Exception:
                    logger.warning("Bucket check/create failed (non-fatal) for %s", self._bucket)
        else:
            from minio.error import S3Error
            try:
                if not self._client.bucket_exists(self._bucket):
                    self._client.make_bucket(self._bucket)
                    logger.info("Created bucket: %s", self._bucket)
                else:
                    logger.info("Bucket exists: %s", self._bucket)
            except S3Error as e:
                if "BucketAlreadyOwnedByYou" in str(e) or "BucketAlreadyExists" in str(e):
                    logger.info("Bucket already exists: %s", self._bucket)
                else:
                    logger.warning("Bucket check failed (non-fatal): %s", e)

    def upload_image(self, object_name: str, image_data: bytes,
                     content_type: str = "image/jpeg") -> bool:
        """Upload an alert snapshot image."""
        try:
            if self._backend == "supabase":
                self._s3.put_object(
                    Bucket=self._bucket,
                    Key=object_name,
                    Body=image_data,
                    ContentType=content_type,
                )
            else:
                data = io.BytesIO(image_data)
                self._client.put_object(
                    self._bucket, object_name, data, len(image_data),
                    content_type=content_type,
                )
            logger.info("Uploaded image: %s (%d bytes)", object_name, len(image_data))
            return True
        except Exception:
            logger.exception("Failed to upload image: %s", object_name)
            return False

    def get_presigned_url(self, object_name: str,
                          expires: timedelta = timedelta(hours=1)) -> str:
        """Generate a presigned URL for downloading an image."""
        try:
            if self._backend == "supabase":
                return self._s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self._bucket, "Key": object_name},
                    ExpiresIn=int(expires.total_seconds()),
                )
            else:
                return self._client.presigned_get_object(
                    self._bucket, object_name, expires=expires,
                )
        except Exception:
            logger.exception("Failed to generate presigned URL for %s", object_name)
            return ""

    def delete_image(self, object_name: str) -> bool:
        """Delete an image from storage."""
        try:
            if self._backend == "supabase":
                self._s3.delete_object(Bucket=self._bucket, Key=object_name)
            else:
                self._client.remove_object(self._bucket, object_name)
            return True
        except Exception:
            return False
