"""Device management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.database import Device, Farm, User
from app.models.schemas import DeviceRegister, DeviceResponse, FarmCreate, FarmResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/v1", tags=["devices"])


# --- Farms ---

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


# --- Devices ---

@router.get("/devices", response_model=list[DeviceResponse])
def list_devices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm_ids = [f.id for f in db.query(Farm).filter(Farm.owner_id == user.id).all()]
    if not farm_ids:
        return []
    return db.query(Device).filter(Device.farm_id.in_(farm_ids)).all()


@router.post("/devices", response_model=DeviceResponse, status_code=201)
def register_device(
    body: DeviceRegister,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    farm = db.query(Farm).filter(Farm.id == body.farm_id, Farm.owner_id == user.id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    existing = db.query(Device).filter(Device.device_uid == body.device_uid).first()
    if existing:
        raise HTTPException(status_code=400, detail="Device UID already registered")

    device = Device(device_uid=body.device_uid, farm_id=body.farm_id)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.get("/devices/{device_id}", response_model=DeviceResponse)
def get_device(
    device_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    farm = db.query(Farm).filter(Farm.id == device.farm_id, Farm.owner_id == user.id).first()
    if not farm:
        raise HTTPException(status_code=403, detail="Access denied")

    return device


@router.delete("/devices/{device_id}", status_code=204)
def delete_device(
    device_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    farm = db.query(Farm).filter(Farm.id == device.farm_id, Farm.owner_id == user.id).first()
    if not farm:
        raise HTTPException(status_code=403, detail="Access denied")

    db.delete(device)
    db.commit()
