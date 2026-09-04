"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


# --- Auth ---

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str = ""

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class FcmTokenUpdate(BaseModel):
    fcm_token: str


# --- Farm ---

class FarmCreate(BaseModel):
    name: str
    location: str = ""

class FarmResponse(BaseModel):
    id: int
    name: str
    location: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Device ---

class DeviceRegister(BaseModel):
    device_uid: str
    farm_id: int

class DeviceResponse(BaseModel):
    id: int
    device_uid: str
    farm_id: int
    status: str
    last_heartbeat: Optional[datetime] = None
    battery_pct: int
    cpu_temp: float
    signal_dbm: int
    firmware_version: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Alert ---

class AlertResponse(BaseModel):
    id: int
    device_id: int
    event_type: str
    camera_id: str
    confidence: float
    person_count: int
    bbox_json: str
    direction: str
    image_path: str
    acknowledged: bool
    created_at: datetime

    model_config = {"from_attributes": True}

class AlertAcknowledge(BaseModel):
    acknowledged: bool = True


# --- Command ---

class CommandRequest(BaseModel):
    device_id: int
    action: str  # arm / disarm / snapshot / reboot
    params: dict = {}

class CommandResponse(BaseModel):
    id: int
    command: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Settings ---

class DeviceSettings(BaseModel):
    schedule: Optional[dict] = None
    exclusion_zones: Optional[dict] = None
    confidence_threshold: Optional[float] = None
    cooldown_seconds: Optional[int] = None
