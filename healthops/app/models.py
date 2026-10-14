from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class Facility(Base):
    __tablename__ = "facilities"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    district: Mapped[str] = mapped_column(String(80), index=True)


class VaccineStock(Base):
    __tablename__ = "vaccine_stock"
    __table_args__ = (UniqueConstraint("facility_id", "vaccine"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    vaccine: Mapped[str] = mapped_column(String(60))
    doses: Mapped[int] = mapped_column(Integer, default=0)


class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    # Pseudonymous reference only - NO names, national IDs or other PII stored.
    patient_ref: Mapped[str] = mapped_column(String(64), index=True)
    vaccine: Mapped[str] = mapped_column(String(60))
    slot: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="booked")
