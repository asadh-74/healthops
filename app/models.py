from datetime import timezone, datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class Facility(Base):
    __tablename__ = "facilities"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    district: Mapped[str] = mapped_column(String(80))


class Batch(Base):
    __tablename__ = "batches"
    __table_args__ = (CheckConstraint("doses >= 0"), UniqueConstraint("facility_id", "code"))
    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    code: Mapped[str] = mapped_column(String(60))
    vaccine: Mapped[str] = mapped_column(String(60))
    doses: Mapped[int]
    expires: Mapped[datetime] = mapped_column(DateTime)


class Appointment(Base):
    __tablename__ = "appointments_v2"
    __table_args__ = (UniqueConstraint("patient_ref", "slot"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"))
    patient_ref: Mapped[str] = mapped_column(String(64))
    vaccine: Mapped[str] = mapped_column(String(60))
    slot: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="booked")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20))


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(String(500))
    created: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_key: Mapped[str] = mapped_column(String(160), unique=True)
    kind: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(default="demo_only")
    created: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class Transfer(Base):
    __tablename__ = "transfers"
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"))
    destination_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    doses: Mapped[int]
    status: Mapped[str] = mapped_column(default="pending")
    requested_by: Mapped[str]
