"""Device management endpoints — link/unlink, schedule, monitoring toggle."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.database import Device, DeviceFarmer, Farm, User
from app.models.schemas import (
    AdHocToggle, DeviceLinkRequest, DeviceLinkResponse, DeviceResponse,
    FarmCreate, FarmResponse, MonitoringSchedule, SuspendRequest,
)
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/v1", tags=["devices"])


# --- Farms (kept for backwards compatibility) ---

@router.get("/farms", response_model=list[FarmResponse])
def list_farms(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Farm).filter(Farm.owner_id == user.id).all()


@router.post("/farms", response_model=FarmResponse, status_code=201)
def create_farm(
    body: FarmCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    farm = Farm(name=body.name, location=body.location, owner_id=user.id)
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return farm


# --- Device Link / Unlink ---

@router.post("/devices/link", response_model=DeviceLinkResponse, status_code=201)
def link_device(
    body: DeviceLinkRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Farmer links to an existing device by device_uid."""
    device = db.query(Device).filter(Device.device_uid == body.device_uid).first()
    if not device:
        raise HTTPException(
            status_code=404,
            detail="Device not found -- ensure the device is installed and powered on",
        )

    # Check if already linked
    existing = (
        db.query(DeviceFarmer)
        .filter(DeviceFarmer.device_id == device.id, DeviceFarmer.user_id == user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="You are already linked to this device")

    link = DeviceFarmer(device_id=device.id, user_id=user.id)
    db.add(link)
    db.commit()
    db.refresh(link)

    return DeviceLinkResponse(
        id=link.id,
        device_id=device.id,
        device_uid=device.device_uid,
        status=device.status,
        monitoring_enabled=link.monitoring_enabled,
        schedule_start_hour=link.schedule_start_hour,
        schedule_end_hour=link.schedule_end_hour,
        created_at=link.created_at,
    )


@router.delete("/devices/{device_id}/unlink", status_code=204)
def unlink_device(
    device_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Farmer unlinks from a device."""
    link = (
        db.query(DeviceFarmer)
        .filter(DeviceFarmer.device_id == device_id, DeviceFarmer.user_id == user.id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Device link not found")

    db.delete(link)
    db.commit()


# --- Device Listing ---

@router.get("/devices", response_model=list[DeviceResponse])
def list_devices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return devices linked to the current farmer via DeviceFarmer join."""
    links = db.query(DeviceFarmer).filter(DeviceFarmer.user_id == user.id).all()
    if not links:
        return []

    device_ids = [link.device_id for link in links]
    devices = db.query(Device).filter(Device.id.in_(device_ids)).all()

    # Build a map of link data keyed by device_id
    link_map = {link.device_id: link for link in links}

    results = []
    for device in devices:
        link = link_map.get(device.id)
        results.append(DeviceResponse(
            id=device.id,
            device_uid=device.device_uid,
            farm_id=device.farm_id,
            status=device.status,
            last_heartbeat=device.last_heartbeat,
            battery_pct=device.battery_pct,
            cpu_temp=device.cpu_temp,
            signal_dbm=device.signal_dbm,
            firmware_version=device.firmware_version,
            monitoring_enabled=link.monitoring_enabled if link else None,
            suspended_until=link.suspended_until if link else None,
            schedule_start_hour=link.schedule_start_hour if link else None,
            schedule_end_hour=link.schedule_end_hour if link else None,
            created_at=device.created_at,
        ))
    return results


@router.get("/devices/{device_id}", response_model=DeviceResponse)
def get_device(
    device_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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

    return DeviceResponse(
        id=device.id,
        device_uid=device.device_uid,
        farm_id=device.farm_id,
        status=device.status,
        last_heartbeat=device.last_heartbeat,
        battery_pct=device.battery_pct,
        cpu_temp=device.cpu_temp,
        signal_dbm=device.signal_dbm,
        firmware_version=device.firmware_version,
        monitoring_enabled=link.monitoring_enabled,
        suspended_until=link.suspended_until,
        schedule_start_hour=link.schedule_start_hour,
        schedule_end_hour=link.schedule_end_hour,
        created_at=device.created_at,
    )


# --- Schedule and Monitoring ---

@router.put("/devices/{device_id}/schedule", response_model=DeviceLinkResponse)
def set_monitoring_schedule(
    device_id: int,
    body: MonitoringSchedule,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set daily monitoring schedule (start_hour, end_hour) per device."""
    link = (
        db.query(DeviceFarmer)
        .filter(DeviceFarmer.device_id == device_id, DeviceFarmer.user_id == user.id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Device link not found")

    link.schedule_start_hour = body.start_hour
    link.schedule_end_hour = body.end_hour
    link.monitoring_enabled = body.enabled
    db.commit()
    db.refresh(link)

    device = db.query(Device).filter(Device.id == device_id).first()

    return DeviceLinkResponse(
        id=link.id,
        device_id=device.id,
        device_uid=device.device_uid,
        status=device.status,
        monitoring_enabled=link.monitoring_enabled,
        suspended_until=link.suspended_until,
        schedule_start_hour=link.schedule_start_hour,
        schedule_end_hour=link.schedule_end_hour,
        created_at=link.created_at,
    )


@router.put("/devices/{device_id}/monitoring", response_model=DeviceLinkResponse)
def toggle_monitoring(
    device_id: int,
    body: AdHocToggle,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ad-hoc toggle monitoring on/off for a device."""
    link = (
        db.query(DeviceFarmer)
        .filter(DeviceFarmer.device_id == device_id, DeviceFarmer.user_id == user.id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Device link not found")

    link.monitoring_enabled = body.monitoring_enabled
    if body.monitoring_enabled:
        link.suspended_until = None
    db.commit()
    db.refresh(link)

    device = db.query(Device).filter(Device.id == device_id).first()

    return DeviceLinkResponse(
        id=link.id,
        device_id=device.id,
        device_uid=device.device_uid,
        status=device.status,
        monitoring_enabled=link.monitoring_enabled,
        suspended_until=link.suspended_until,
        schedule_start_hour=link.schedule_start_hour,
        schedule_end_hour=link.schedule_end_hour,
        created_at=link.created_at,
    )


@router.put("/devices/{device_id}/suspend", response_model=DeviceLinkResponse)
def suspend_monitoring(
    device_id: int,
    body: SuspendRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Suspend alerts for a device for a specified duration.

    duration_minutes=0 means resume immediately (clear suspension).
    """
    link = (
        db.query(DeviceFarmer)
        .filter(DeviceFarmer.device_id == device_id, DeviceFarmer.user_id == user.id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Device link not found")

    if body.duration_minutes == 0:
        link.suspended_until = None
    else:
        link.suspended_until = datetime.now(timezone.utc) + timedelta(minutes=body.duration_minutes)

    db.commit()
    db.refresh(link)

    device = db.query(Device).filter(Device.id == device_id).first()

    return DeviceLinkResponse(
        id=link.id,
        device_id=device.id,
        device_uid=device.device_uid,
        status=device.status,
        monitoring_enabled=link.monitoring_enabled,
        suspended_until=link.suspended_until,
        schedule_start_hour=link.schedule_start_hour,
        schedule_end_hour=link.schedule_end_hour,
        created_at=link.created_at,
    )
