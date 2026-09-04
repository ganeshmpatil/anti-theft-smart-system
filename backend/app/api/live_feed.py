"""WebSocket endpoint for live camera feed relay."""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["live_feed"])

# MQTT handler is injected at app startup
_mqtt_handler = None


def set_mqtt_handler(handler):
    global _mqtt_handler
    _mqtt_handler = handler


@router.websocket("/api/v1/live/{device_uid}")
async def live_feed_ws(websocket: WebSocket, device_uid: str):
    """Stream JPEG frames from edge device to mobile app via WebSocket.

    The edge device publishes frames to MQTT topic farm/+/device/{device_uid}/live_frame.
    The backend MQTT handler pushes those frames into per-subscriber asyncio.Queues.
    This endpoint drains the queue and sends binary frames over the WebSocket.
    """
    logger = logging.getLogger(__name__)

    if not _mqtt_handler:
        await websocket.close(code=1011, reason="MQTT handler not available")
        return

    await websocket.accept()
    logger.info("Live feed WebSocket opened for device %s", device_uid)

    queue = _mqtt_handler.subscribe_live_feed(device_uid)

    try:
        while True:
            try:
                # Wait for the next frame with a timeout to detect dead connections
                frame = await asyncio.wait_for(queue.get(), timeout=15.0)
                await websocket.send_bytes(frame)
            except asyncio.TimeoutError:
                # Send a ping to check if client is still alive
                try:
                    await websocket.send_text("ping")
                except Exception:
                    break
    except WebSocketDisconnect:
        logger.info("Live feed WebSocket closed for device %s", device_uid)
    except Exception:
        logger.exception("Live feed WebSocket error for device %s", device_uid)
    finally:
        _mqtt_handler.unsubscribe_live_feed(device_uid, queue)
