"""SQLAlchemy ORM models."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text,
    Index, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), default="")
    address = Column(Text, default="")
    selfie_path = Column(String(500), default="")
    fcm_token = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    farms = relationship("Farm", back_populates="owner", cascade="all, delete-orphan")
    device_links = relationship("DeviceFarmer", back_populates="user", cascade="all, delete-orphan")


class Farm(Base):
    __tablename__ = "farms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    location = Column(String(500), default="")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    owner = relationship("User", back_populates="farms")
    devices = relationship("Device", back_populates="farm", cascade="all, delete-orphan")


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_uid = Column(String(100), unique=True, nullable=False)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=True)
    status = Column(String(50), default="offline")  # armed / disarmed / offline
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)
    battery_pct = Column(Integer, default=-1)
    cpu_temp = Column(Float, default=0.0)
    signal_dbm = Column(Integer, default=0)
    firmware_version = Column(String(50), default="")
    config_json = Column(Text, default="{}")  # schedule, threshold, zones
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    farm = relationship("Farm", back_populates="devices")
    alerts = relationship("Alert", back_populates="device", cascade="all, delete-orphan")
    command_logs = relationship("CommandLog", back_populates="device", cascade="all, delete-orphan")
    farmer_links = relationship("DeviceFarmer", back_populates="device", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_devices_farm", "farm_id"),
        Index("idx_devices_heartbeat", "last_heartbeat"),
    )


class DeviceFarmer(Base):
    """Many-to-many link between devices and farmers (users)."""
    __tablename__ = "device_farmers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    monitoring_enabled = Column(Boolean, default=True)
    schedule_start_hour = Column(Integer, nullable=True)
    schedule_end_hour = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    device = relationship("Device", back_populates="farmer_links")
    user = relationship("User", back_populates="device_links")

    __table_args__ = (
        UniqueConstraint("device_id", "user_id", name="uq_device_farmer"),
        Index("idx_device_farmer_device", "device_id"),
        Index("idx_device_farmer_user", "user_id"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    event_type = Column(String(50), nullable=False)  # intrusion_detected / tamper_detected
    camera_id = Column(String(50), default="")
    confidence = Column(Float, default=0.0)
    person_count = Column(Integer, default=0)
    bbox_json = Column(Text, default="[]")
    direction = Column(String(50), default="")
    image_path = Column(String(500), default="")  # MinIO object key
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    device = relationship("Device", back_populates="alerts")

    __table_args__ = (
        Index("idx_alerts_device_created", "device_id", "created_at"),
        Index("idx_alerts_created", "created_at"),
    )


class CommandLog(Base):
    __tablename__ = "command_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    command = Column(String(50), nullable=False)
    payload_json = Column(Text, default="{}")
    status = Column(String(50), default="sent")  # sent / acked / failed
    created_at = Column(DateTime(timezone=True), default=utcnow)

    device = relationship("Device", back_populates="command_logs")

    __table_args__ = (
        Index("idx_cmdlog_device_created", "device_id", "created_at"),
    )
