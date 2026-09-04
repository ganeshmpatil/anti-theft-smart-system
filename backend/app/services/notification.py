"""Push notification service using Firebase Cloud Messaging."""

import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Firebase is optional — if no credentials, fall back to console logging
_firebase_app = None


def init_firebase():
    """Initialize Firebase Admin SDK if credentials are configured."""
    global _firebase_app
    if not settings.firebase_credentials_path:
        logger.info("Firebase credentials not configured — notifications will be logged to console")
        return

    try:
        import firebase_admin
        from firebase_admin import credentials

        cred = credentials.Certificate(settings.firebase_credentials_path)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized successfully")
    except Exception:
        logger.exception("Failed to initialize Firebase — falling back to console logging")


def send_push_notification(
    fcm_token: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
    image_url: Optional[str] = None,
) -> bool:
    """Send a push notification to a device.

    Args:
        fcm_token: Firebase device token
        title: Notification title
        body: Notification body text
        data: Optional data payload (key-value pairs)
        image_url: Optional image URL to display in notification

    Returns:
        True if sent successfully (or logged in console mode)
    """
    if not fcm_token:
        logger.warning("No FCM token — skipping notification")
        return False

    if _firebase_app is None:
        # Console fallback mode
        logger.info(
            "PUSH NOTIFICATION (console mode):\n"
            "  To: %s\n  Title: %s\n  Body: %s\n  Data: %s",
            fcm_token[:20] + "...", title, body, data,
        )
        return True

    try:
        from firebase_admin import messaging

        notification = messaging.Notification(
            title=title,
            body=body,
            image=image_url,
        )

        message = messaging.Message(
            notification=notification,
            data={k: str(v) for k, v in (data or {}).items()},
            token=fcm_token,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id="intrusion_alerts",
                    priority="max",
                    sound="default",
                ),
            ),
        )

        response = messaging.send(message)
        logger.info("Push notification sent: %s", response)
        return True

    except Exception:
        logger.exception("Failed to send push notification")
        return False
