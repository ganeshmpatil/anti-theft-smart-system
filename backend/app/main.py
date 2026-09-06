"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.session import engine
from app.models.database import Base
from app.services.mqtt_handler import MQTTHandler
from app.services.notification import init_firebase
from app.services.storage import StorageService
from app.api import admin, auth, devices, alerts, commands, live_feed

logger = logging.getLogger(__name__)

if settings.cors_origins:
    ALLOWED_ORIGINS = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
else:
    # Development fallback — restrict to common local dev ports
    ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:5000",
        "http://localhost:5500",
    ]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting Anti-Theft Smart System backend...")

    # In production, use Alembic migrations: cd backend && alembic upgrade head
    # create_all is safe as a fallback — it only creates tables that don't exist yet
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ready.")

    # Initialize Firebase for push notifications
    init_firebase()

    # Ensure MinIO bucket exists (skip if endpoint not configured)
    storage = None
    if settings.minio_endpoint:
        try:
            storage = StorageService()
            storage.ensure_bucket()
            app.state.storage = storage
            logger.info("MinIO storage ready.")
        except Exception:
            logger.warning("MinIO unavailable — image storage disabled.")

    # Start MQTT handler (skip if broker not configured)
    mqtt = None
    if settings.mqtt_broker:
        try:
            mqtt = MQTTHandler(storage)
            mqtt.start()
            app.state.mqtt_handler = mqtt
            commands.set_mqtt_handler(mqtt)
            live_feed.set_mqtt_handler(mqtt)
            admin.set_admin_mqtt_handler(mqtt)
            logger.info("MQTT handler started.")
        except Exception:
            logger.warning("MQTT broker unavailable — real-time features disabled.")

    yield

    # --- Shutdown ---
    logger.info("Shutting down...")
    if mqtt:
        mqtt.stop()


app = FastAPI(
    title="Anti-Theft Smart System",
    description="Backend API for AI-powered agricultural surveillance",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(alerts.router)
app.include_router(commands.router)
app.include_router(live_feed.router)


@app.get("/health")
def health_check():
    mqtt: MQTTHandler = getattr(app.state, "mqtt_handler", None)
    storage: StorageService = getattr(app.state, "storage", None)
    return {
        "status": "ok",
        "mqtt_connected": mqtt.is_connected if mqtt else False,
        "storage_enabled": storage is not None,
    }
