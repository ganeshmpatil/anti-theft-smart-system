"""Pydantic schemas for API request/response validation."""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# --- Auth ---

class UserRegister(BaseModel):
    phone: str = Field(..., min_length=5, max_length=20)
    full_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=72)
    address: str = ""
    email: Optional[EmailStr] = None

class UserLogin(BaseModel):
    phone: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class UserProfileResponse(BaseModel):
    id: int
    full_name: str
    phone: str
    address: str
    email: Optional[str] = None
    selfie_url: str = ""

    model_config = {"from_attributes": True}

class FcmTokenUpdate(BaseModel):
    fcm_token: str


# --- Farm ---

class FarmCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    location: str = ""

class FarmResponse(BaseModel):
    id: int
    name: str
    location: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Device ---

_DEVICE_UID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')

class DeviceLinkRequest(BaseModel):
    device_uid: str = Field(..., min_length=1, max_length=100)

    @field_validator('device_uid')
    @classmethod
    def validate_device_uid(cls, v: str) -> str:
        if not _DEVICE_UID_PATTERN.match(v):
            raise ValueError('device_uid must contain only letters, digits, hyphens, and underscores')
        return v

class DeviceLinkResponse(BaseModel):
    id: int
    device_id: int
    device_uid: str
    status: str
    monitoring_enabled: bool
    schedule_start_hour: Optional[int] = None
    schedule_end_hour: Optional[int] = None
    created_at: datetime

class DeviceResponse(BaseModel):
    id: int
    device_uid: str
    farm_id: Optional[int] = None
    status: str
    last_heartbeat: Optional[datetime] = None
    battery_pct: int
    cpu_temp: float
    signal_dbm: int
    firmware_version: str
    monitoring_enabled: Optional[bool] = None
    schedule_start_hour: Optional[int] = None
    schedule_end_hour: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class MonitoringSchedule(BaseModel):
    start_hour: int = Field(..., ge=0, le=23)
    end_hour: int = Field(..., ge=0, le=23)
    enabled: bool = True

class AdHocToggle(BaseModel):
    monitoring_enabled: bool

# Keep old schema for backwards compatibility
class DeviceRegister(BaseModel):
    device_uid: str = Field(..., min_length=1, max_length=100)
    farm_id: int

    @field_validator('device_uid')
    @classmethod
    def validate_device_uid(cls, v: str) -> str:
        if not _DEVICE_UID_PATTERN.match(v):
            raise ValueError('device_uid must contain only letters, digits, hyphens, and underscores')
        return v


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
