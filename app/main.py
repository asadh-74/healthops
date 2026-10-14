import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from prometheus_client import Gauge
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from . import models
from .database import Base, engine, get_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("healthops")

TOTAL_DOSES = Gauge("healthops_total_doses", "Total vaccine doses in stock", ["vaccine"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # In production, replace with Alembic migrations.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="HealthOps API",
    version="1.0.0",
    description="Vaccination appointments & clinic stock tracking for public health departments.",
    lifespan=lifespan,
)
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


class FacilityIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    district: str = Field(min_length=2, max_length=80)


class StockIn(BaseModel):
    facility_id: int
    vaccine: str
    doses: int = Field(ge=0)


class AppointmentIn(BaseModel):
    facility_id: int
    patient_ref: str = Field(min_length=4, max_length=64, description="Pseudonymous ID, not PII")
    vaccine: str
    slot: datetime


@app.get("/health", tags=["ops"])
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.post("/facilities", status_code=201, tags=["facilities"])
def create_facility(body: FacilityIn, db: Session = Depends(get_db)):
    if db.scalar(select(models.Facility).where(models.Facility.name == body.name)):
        raise HTTPException(409, "Facility already exists")
    f = models.Facility(**body.model_dump())
    db.add(f)
    db.commit()
    return f


@app.get("/facilities", tags=["facilities"])
def list_facilities(district: str | None = None, db: Session = Depends(get_db)):
    q = select(models.Facility)
    if district:
        q = q.where(models.Facility.district == district)
    return db.scalars(q).all()


@app.put("/stock", tags=["stock"])
def set_stock(body: StockIn, db: Session = Depends(get_db)):
    if not db.get(models.Facility, body.facility_id):
        raise HTTPException(404, "Facility not found")
    row = db.scalar(
        select(models.VaccineStock).where(
            models.VaccineStock.facility_id == body.facility_id,
            models.VaccineStock.vaccine == body.vaccine,
        )
    )
    if row:
        row.doses = body.doses
    else:
        row = models.VaccineStock(**body.model_dump())
        db.add(row)
    db.commit()
    _refresh_metrics(db)
    return row


@app.get("/stock/low", tags=["stock"])
def low_stock(threshold: int = 50, db: Session = Depends(get_db)):
    """Facilities that need urgent resupply."""
    q = select(models.VaccineStock).where(models.VaccineStock.doses < threshold)
    return db.scalars(q).all()


@app.post("/appointments", status_code=201, tags=["appointments"])
def book(body: AppointmentIn, db: Session = Depends(get_db)):
    stock = db.scalar(
        select(models.VaccineStock).where(
            models.VaccineStock.facility_id == body.facility_id,
            models.VaccineStock.vaccine == body.vaccine,
        )
    )
    if not stock or stock.doses < 1:
        raise HTTPException(409, "No doses available at this facility")
    stock.doses -= 1
    appt = models.Appointment(**body.model_dump())
    db.add(appt)
    db.commit()
    _refresh_metrics(db)
    log.info("appointment booked facility=%s vaccine=%s", body.facility_id, body.vaccine)
    return appt


@app.get("/appointments", tags=["appointments"])
def list_appointments(facility_id: int | None = None, db: Session = Depends(get_db)):
    q = select(models.Appointment)
    if facility_id:
        q = q.where(models.Appointment.facility_id == facility_id)
    return db.scalars(q.limit(500)).all()


def _refresh_metrics(db: Session):
    rows = db.execute(
        select(models.VaccineStock.vaccine, func.sum(models.VaccineStock.doses)).group_by(
            models.VaccineStock.vaccine
        )
    )
    for vaccine, total in rows:
        TOTAL_DOSES.labels(vaccine=vaccine).set(total or 0)
