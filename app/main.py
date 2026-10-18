import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pathlib import Path
from prometheus_client import Gauge
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text, update
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
    vaccine: str = Field(min_length=2, max_length=60)
    doses: int = Field(ge=0, le=1000000)


class AppointmentIn(BaseModel):
    facility_id: int
    patient_ref: str = Field(min_length=4, max_length=64, description="Pseudonymous ID, not PII")
    vaccine: str = Field(min_length=2, max_length=60)
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
    db.add(models.Activity(action="Facility created", detail=body.name))
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
    db.add(models.Activity(action="Stock set", detail=f"Facility {body.facility_id}: {body.vaccine} set to {body.doses}"))
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
    changed = db.execute(update(models.VaccineStock).where(
        models.VaccineStock.facility_id == body.facility_id,
        models.VaccineStock.vaccine == body.vaccine,
        models.VaccineStock.doses > 0,
    ).values(doses=models.VaccineStock.doses - 1))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "No doses available at this facility")
    appt = models.Appointment(**body.model_dump())
    db.add(appt)
    db.add(models.Activity(action="Appointment booked", detail=f"Facility {body.facility_id}: one {body.vaccine} dose reserved"))
    db.commit()
    _refresh_metrics(db)
    log.info("appointment booked facility=%s vaccine=%s", body.facility_id, body.vaccine)
    return appt


@app.get("/appointments", tags=["appointments"])
def list_appointments(facility_id: int | None = None, db: Session = Depends(get_db)):
    q = select(models.Appointment)
    if facility_id:
        q = q.where(models.Appointment.facility_id == facility_id)
    return db.scalars(q.order_by(models.Appointment.id.desc()).limit(100)).all()


def _refresh_metrics(db: Session):
    rows = db.execute(
        select(models.VaccineStock.vaccine, func.sum(models.VaccineStock.doses)).group_by(
            models.VaccineStock.vaccine
        )
    )
    for vaccine, total in rows:
        TOTAL_DOSES.labels(vaccine=vaccine).set(total or 0)


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(Path(__file__).parent / "static" / "index.html")

@app.get("/stock", tags=["stock"])
def all_stock(db: Session = Depends(get_db)):
    return db.scalars(select(models.VaccineStock)).all()


class RestockIn(BaseModel):
    facility_id: int
    vaccine: str = Field(min_length=2, max_length=60)
    doses: int = Field(gt=0, le=10000)

@app.post('/stock/restock', tags=['stock'])
def restock(body:RestockIn, db:Session=Depends(get_db)):
    row=db.scalar(select(models.VaccineStock).where(models.VaccineStock.facility_id==body.facility_id, models.VaccineStock.vaccine==body.vaccine))
    if not row: raise HTTPException(404,'Set up this stock item first')
    db.execute(update(models.VaccineStock).where(models.VaccineStock.id==row.id).values(doses=models.VaccineStock.doses+body.doses))
    db.add(models.Activity(action='Stock replenished',detail=f'Facility {body.facility_id}: added {body.doses} {body.vaccine} doses'))
    db.commit();db.refresh(row);_refresh_metrics(db)
    return row

@app.post('/appointments/{appointment_id}/cancel',tags=['appointments'])
def cancel(appointment_id:int,db:Session=Depends(get_db)):
    row=db.get(models.Appointment,appointment_id)
    if not row: raise HTTPException(404,'Appointment not found')
    changed=db.execute(update(models.Appointment).where(models.Appointment.id==appointment_id,models.Appointment.status=='booked').values(status='cancelled'))
    if changed.rowcount!=1:
        db.rollback();raise HTTPException(409,'Only a booked appointment can be cancelled')
    db.execute(update(models.VaccineStock).where(models.VaccineStock.facility_id==row.facility_id,models.VaccineStock.vaccine==row.vaccine).values(doses=models.VaccineStock.doses+1))
    db.add(models.Activity(action='Appointment cancelled',detail=f'Booking {appointment_id}: reserved dose returned to stock'))
    db.commit();db.refresh(row);_refresh_metrics(db)
    return row

@app.post('/appointments/{appointment_id}/complete',tags=['appointments'])
def complete(appointment_id:int,db:Session=Depends(get_db)):
    changed=db.execute(update(models.Appointment).where(models.Appointment.id==appointment_id,models.Appointment.status=='booked').values(status='completed'))
    if changed.rowcount!=1: db.rollback();raise HTTPException(409,'Only a booked appointment can be completed')
    db.add(models.Activity(action='Appointment completed',detail=f'Booking {appointment_id}: administered dose recorded'))
    db.commit();return {'id':appointment_id,'status':'completed'}

@app.post('/demo/seed',tags=['demo'])
def seed_demo(db:Session=Depends(get_db)):
    for name,district,mmr,polio in [('Demo North Clinic','Demo North',1,80),('Demo Central Clinic','Demo Central',25,120),('Demo East Clinic','Demo East',60,30)]:
        f=db.scalar(select(models.Facility).where(models.Facility.name==name))
        if f: continue
        f=models.Facility(name=name,district=district);db.add(f);db.flush()
        db.add_all([models.VaccineStock(facility_id=f.id,vaccine='MMR',doses=mmr),models.VaccineStock(facility_id=f.id,vaccine='Polio',doses=polio)])
    db.add(models.Activity(action='Demo data loaded',detail='Fictional clinics and stock; existing records preserved'))
    db.commit();return {'status':'ready','message':'Demo clinics loaded; existing data preserved'}

@app.get('/overview',tags=['dashboard'])
def overview(db:Session=Depends(get_db)):
    stocks=db.scalars(select(models.VaccineStock)).all()
    return {'facilities':db.scalar(select(func.count()).select_from(models.Facility)), 'doses':sum(x.doses for x in stocks),'low_stock':sum(x.doses<50 for x in stocks),'booked':db.scalar(select(func.count()).select_from(models.Appointment).where(models.Appointment.status=='booked')), 'activity':db.scalars(select(models.Activity).order_by(models.Activity.id.desc()).limit(20)).all()}

@app.get('/report.csv',tags=['reports'])
def stock_report(db:Session=Depends(get_db)):
    import csv,io
    out=io.StringIO();w=csv.writer(out);w.writerow(['facility','district','vaccine','available_doses'])
    for row,facility in db.execute(select(models.VaccineStock,models.Facility).join(models.Facility)):
        w.writerow([safe_csv(facility.name),safe_csv(facility.district),safe_csv(row.vaccine),row.doses])
    return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="healthops-stock.csv"'})


def safe_csv(value):
    value=str(value)
    return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value
