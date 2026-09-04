"""Command and settings endpoints — send commands to edge devices."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.database import CommandLog, Device, DeviceFarmer, Farm, User
from app.models.schemas import CommandRequest, CommandResponse, DeviceSettings
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/v1", tags=["commands"])

# MQTT handler is injected at app startup via app.state
_mqtt_handler = None


def set_mqtt_handler(handler):
    global _mqtt_handler
    _mqtt_handler = handler


def _get_device_for_user(device_id: int, user: User, db: Session) -> Device:
    """Validate that the user is linked to the device via DeviceFarmer."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    link = (
        db.query(DeviceFarmer)
        .filter(DeviceFarmer.device_id == device_id, DeviceFarmer.user_id == user.id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=403, detail="Access denied")

    return device


@router.post("/commands", response_model=CommandResponse, status_code=201)
def send_command(
    body: CommandRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    valid_actions = {"arm", "disarm", "snapshot", "reboot", "live_feed_start", "live_feed_stop"}
    if body.action not in valid_actions:
        raise HTTPException(status_code=400,
                            detail=f"Invalid action. Must be one of: {valid_actions}")

    device = _get_device_for_user(body.device_id, user, db)

    # Publish via MQTT
    cmd_status = "sent"
    if _mqtt_handler and _mqtt_handler.is_connected:
        farm = db.query(Farm).filter(Farm.id == device.farm_id).first() if device.farm_id else None
        mqtt_farm_id = farm.name.lower().replace(" ", "_") if farm else "default"
        success = _mqtt_handler.publish_command(mqtt_farm_id, device.device_uid,
                                                 body.action, body.params)
        if not success:
            cmd_status = "failed"
    else:
        cmd_status = "failed"

    # Log the command
    log = CommandLog(
        user_id=user.id,
        device_id=device.id,
        command=body.action,
        payload_json=json.dumps(body.params),
        status=cmd_status,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    if cmd_status == "failed":
        raise HTTPException(status_code=503, detail="Failed to deliver command — device may be offline")

    return log


# --- Settings ---

@router.get("/settings/{device_id}")
def get_device_settings(
    device_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device = _get_device_for_user(device_id, user, db)
    try:
        config = json.loads(device.config_json) if device.config_json else {}
    except json.JSONDecodeError:
        config = {}
    return config


@router.put("/settings/{device_id}")
def update_device_settings(
    device_id: int,
    body: DeviceSettings,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device = _get_device_for_user(device_id, user, db)

    try:
        current = json.loads(device.config_json) if device.config_json else {}
    except json.JSONDecodeError:
        current = {}

    # Merge new settings into existing
    if body.schedule is not None:
        current["schedule"] = body.schedule
    if body.exclusion_zones is not None:
        current["exclusion_zones"] = body.exclusion_zones
    if body.confidence_threshold is not None:
        current["confidence_threshold"] = body.confidence_threshold
    if body.cooldown_seconds is not None:
        current["cooldown_seconds"] = body.cooldown_seconds

    device.config_json = json.dumps(current)
    db.commit()

    # Push config to device via MQTT
    if _mqtt_handler and _mqtt_handler.is_connected:
        farm = db.query(Farm).filter(Farm.id == device.farm_id).first() if device.farm_id else None
        mqtt_farm_id = farm.name.lower().replace(" ", "_") if farm else "default"
        _mqtt_handler.publish_config(mqtt_farm_id, device.device_uid, current)

    return current
