"""Application configuration loaded from environment variables."""

import logging
import os
import secrets
import sys

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

_INSECURE_JWT_DEFAULT = "change-this-to-a-random-secret-in-production"


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://atss:atss_secret@localhost:5432/atss"

    # MQTT
    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "alert-snapshots"
    minio_secure: bool = False

    # JWT
    jwt_secret_key: str = _INSECURE_JWT_DEFAULT
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 43200  # 30 days — farmers shouldn't need to re-login often

    # Firebase
    firebase_credentials_path: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS — comma-separated list of allowed origins
    cors_origins: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

_is_production = os.getenv("ENV", "development") == "production"

if settings.jwt_secret_key == _INSECURE_JWT_DEFAULT:
    if _is_production:
        logger.critical(
            "FATAL: JWT_SECRET_KEY is not set. Refusing to start in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
        sys.exit(1)
    else:
        settings.jwt_secret_key = secrets.token_urlsafe(32)
        logger.warning(
            "JWT_SECRET_KEY not set — using random ephemeral secret. "
            "Tokens will NOT survive server restarts. Set JWT_SECRET_KEY in .env for production."
        )
