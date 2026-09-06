"""Admin endpoints — device provisioning and fleet health monitoring."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.database import Device, Farm

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# --- Device Provisioning ---

class ProvisionRequest(BaseModel):
    device_uid: str = Field(..., min_length=1, max_length=100)
    farm_id: int | None = None

class ProvisionResponse(BaseModel):
    id: int
    device_uid: str
    provisioned: bool
    farm_id: int | None
    status: str

    model_config = {"from_attributes": True}


@router.post("/devices/provision", response_model=ProvisionResponse, status_code=201)
def provision_device(
    body: ProvisionRequest,
    db: Session = Depends(get_db),
):
    """Pre-register a device UID so the edge device is accepted on first heartbeat."""
    existing = db.query(Device).filter(Device.device_uid == body.device_uid).first()
    if existing:
        if existing.provisioned:
            raise HTTPException(status_code=409, detail="Device already provisioned")
        existing.provisioned = True
        if body.farm_id:
            existing.farm_id = body.farm_id
        db.commit()
        db.refresh(existing)
        return existing

    if body.farm_id:
        farm = db.query(Farm).filter(Farm.id == body.farm_id).first()
        if not farm:
            raise HTTPException(status_code=404, detail="Farm not found")

    device = Device(
        device_uid=body.device_uid,
        farm_id=body.farm_id,
        provisioned=True,
        status="offline",
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.delete("/devices/{device_uid}/deprovision", status_code=204)
def deprovision_device(device_uid: str, db: Session = Depends(get_db)):
    """Revoke a device's provisioning — it will no longer be accepted."""
    device = db.query(Device).filter(Device.device_uid == device_uid).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.provisioned = False
    db.commit()


# --- Fleet Health ---

class DeviceHealth(BaseModel):
    device_uid: str
    farm_id: int | None
    status: str
    provisioned: bool
    last_heartbeat: datetime | None
    battery_pct: int
    cpu_temp: float
    signal_dbm: int
    firmware_version: str
    minutes_since_heartbeat: float | None

class FleetHealthResponse(BaseModel):
    total_devices: int
    online: int
    offline: int
    stale: int
    devices: list[DeviceHealth]


@router.get("/health/fleet", response_model=FleetHealthResponse)
def fleet_health(db: Session = Depends(get_db)):
    """Aggregate health status of all provisioned devices."""
    devices = db.query(Device).filter(Device.provisioned == True).all()
    now = datetime.now(timezone.utc)
    stale_threshold = now - timedelta(minutes=5)

    online = 0
    offline = 0
    stale = 0
    device_list = []

    for d in devices:
        minutes_since = None
        if d.last_heartbeat:
            delta = now - d.last_heartbeat.replace(tzinfo=timezone.utc) if d.last_heartbeat.tzinfo is None else now - d.last_heartbeat
            minutes_since = round(delta.total_seconds() / 60, 1)

        if d.status in ("armed", "disarmed", "online"):
            if d.last_heartbeat and d.last_heartbeat < stale_threshold:
                stale += 1
            else:
                online += 1
        else:
            offline += 1

        device_list.append(DeviceHealth(
            device_uid=d.device_uid,
            farm_id=d.farm_id,
            status=d.status,
            provisioned=d.provisioned,
            last_heartbeat=d.last_heartbeat,
            battery_pct=d.battery_pct,
            cpu_temp=d.cpu_temp,
            signal_dbm=d.signal_dbm,
            firmware_version=d.firmware_version,
            minutes_since_heartbeat=minutes_since,
        ))

    return FleetHealthResponse(
        total_devices=len(devices),
        online=online,
        offline=offline,
        stale=stale,
        devices=device_list,
    )
