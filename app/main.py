import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from . import models as m
from .auth import current, roles, secret, token, verify
from .database import get_db
from .rate_limit import check_login


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@asynccontextmanager
async def lifespan(app):
    secret()
    yield


app = FastAPI(title="HealthOps", version="2.0.0", lifespan=lifespan)
instrumentator = Instrumentator().instrument(app)
if os.getenv("EXPOSE_METRICS", "false").lower() == "true":
    instrumentator.expose(app, include_in_schema=False)
manager = roles("admin", "manager")


def audit(db, user, action, detail):
    db.add(m.Audit(actor=user.username, action=action, detail=detail))


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Duplicate record or conflicting update")


class Login(BaseModel):
    username: str = Field(max_length=80)
    password: str = Field(max_length=128)


@app.post("/api/auth/login")
def login(body: Login, db=Depends(get_db)):
    check_login(body.username)
    user = db.scalar(select(m.User).where(m.User.username == body.username))
    if not user or not verify(body.password, user.password_hash):
        raise HTTPException(401, "Invalid username or password")
    return {"access_token": token(user), "username": user.username, "role": user.role}


@app.get("/api/me")
def me(user=Depends(current)):
    return {"username": user.username, "role": user.role}


@app.get("/health")
def health(db=Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "mode": "fictional-data demo"}


@app.get("/api/overview")
def overview(db=Depends(get_db), user=Depends(current)):
    return {
        "facilities": db.scalar(select(func.count(m.Facility.id))),
        "available_doses": db.scalar(select(func.sum(m.Batch.doses)).where(m.Batch.expires > now())) or 0,
        "appointments": db.scalar(
            select(func.count(m.Appointment.id)).where(m.Appointment.status == "booked")
        ),
        "low_stock": db.scalar(
            select(func.count(m.Batch.id)).where(m.Batch.doses < 30, m.Batch.expires > now())
        ),
        "notifications": db.scalar(select(func.count(m.Notification.id))),
    }


class FacilityIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    district: str = Field(min_length=2, max_length=80)


@app.get("/api/facilities")
def facilities(db=Depends(get_db), user=Depends(current)):
    return db.scalars(select(m.Facility).order_by(m.Facility.id)).all()


@app.post("/api/facilities", status_code=201)
def create_facility(body: FacilityIn, db=Depends(get_db), user=Depends(roles("admin"))):
    row = m.Facility(**body.model_dump())
    db.add(row)
    audit(db, user, "facility.created", body.name)
    commit(db)
    return row


class BatchIn(BaseModel):
    facility_id: int
    code: str = Field(min_length=2, max_length=60)
    vaccine: str = Field(min_length=2, max_length=60)
    doses: int = Field(ge=1, le=100000)
    expires: datetime

    @field_validator("expires")
    @classmethod
    def expiry(cls, value):
        value = value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
        if value <= now():
            raise ValueError("Expiry must be in the future")
        return value


@app.get("/api/batches")
def batches(db=Depends(get_db), user=Depends(current)):
    return db.scalars(select(m.Batch).order_by(m.Batch.expires)).all()


@app.post("/api/batches", status_code=201)
def create_batch(body: BatchIn, db=Depends(get_db), user=Depends(manager)):
    if not db.get(m.Facility, body.facility_id):
        raise HTTPException(404, "Clinic not found")
    row = m.Batch(**body.model_dump())
    db.add(row)
    audit(db, user, "stock.received", f"{body.code}: {body.doses} doses")
    commit(db)
    return row


class Booking(BaseModel):
    facility_id: int
    patient_ref: str = Field(pattern=r"^DEMO-[A-Z0-9-]{3,40}$")
    vaccine: str = Field(min_length=2, max_length=60)
    slot: datetime

    @field_validator("slot")
    @classmethod
    def future(cls, value):
        value = value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
        if value <= now() or value > now() + timedelta(days=180):
            raise ValueError("Choose a future appointment within 180 days")
        return value


def reserve(db, facility, vaccine, slot):
    candidates = db.scalars(
        select(m.Batch.id)
        .where(
            m.Batch.facility_id == facility,
            m.Batch.vaccine == vaccine,
            m.Batch.expires > slot,
            m.Batch.doses > 0,
        )
        .order_by(m.Batch.expires, m.Batch.id)
    ).all()
    for bid in candidates:
        result = db.execute(
            update(m.Batch).where(m.Batch.id == bid, m.Batch.doses > 0).values(doses=m.Batch.doses - 1)
        )
        if result.rowcount:
            return bid
    raise HTTPException(409, "No unexpired doses available for this appointment")


@app.get("/api/appointments")
def appointments(db=Depends(get_db), user=Depends(current)):
    return db.scalars(select(m.Appointment).order_by(m.Appointment.slot).limit(500)).all()


@app.post("/api/appointments", status_code=201)
def book(body: Booking, db=Depends(get_db), user=Depends(current)):
    bid = reserve(db, body.facility_id, body.vaccine, body.slot)
    row = m.Appointment(**body.model_dump(), batch_id=bid)
    db.add(row)
    audit(db, user, "appointment.booked", body.patient_ref)
    commit(db)
    return row


@app.post("/api/appointments/{aid}/cancel")
def cancel(aid: int, db=Depends(get_db), user=Depends(current)):
    row = db.scalar(select(m.Appointment).where(m.Appointment.id == aid).with_for_update())
    if not row:
        raise HTTPException(404, "Appointment not found")
    changed = db.execute(
        update(m.Appointment)
        .where(m.Appointment.id == aid, m.Appointment.status == "booked")
        .values(status="cancelled")
    )
    if changed.rowcount:
        db.execute(update(m.Batch).where(m.Batch.id == row.batch_id).values(doses=m.Batch.doses + 1))
        audit(db, user, "appointment.cancelled", str(aid))
        commit(db)
    return {"status": "cancelled"}


class Reschedule(BaseModel):
    slot: datetime
    _future = field_validator("slot")(Booking.future.__func__)


@app.post("/api/appointments/{aid}/reschedule")
def reschedule(aid: int, body: Reschedule, db=Depends(get_db), user=Depends(current)):
    row = db.scalar(select(m.Appointment).where(m.Appointment.id == aid).with_for_update())
    if not row or row.status != "booked":
        raise HTTPException(409, "Only booked appointments can be rescheduled")
    db.execute(update(m.Batch).where(m.Batch.id == row.batch_id).values(doses=m.Batch.doses + 1))
    bid = reserve(db, row.facility_id, row.vaccine, body.slot)
    row.batch_id, row.slot = bid, body.slot
    audit(db, user, "appointment.rescheduled", str(aid))
    commit(db)
    return row


class TransferIn(BaseModel):
    batch_id: int
    destination_id: int
    doses: int = Field(ge=1, le=100000)


@app.get("/api/transfers")
def transfers(db=Depends(get_db), user=Depends(current)):
    return db.scalars(select(m.Transfer).order_by(m.Transfer.id.desc())).all()


@app.post("/api/transfers", status_code=201)
def request_transfer(body: TransferIn, db=Depends(get_db), user=Depends(manager)):
    batch = db.get(m.Batch, body.batch_id)
    if not batch or not db.get(m.Facility, body.destination_id):
        raise HTTPException(404, "Batch or destination not found")
    if batch.facility_id == body.destination_id:
        raise HTTPException(422, "Choose a different destination")
    row = m.Transfer(**body.model_dump(), requested_by=user.username)
    db.add(row)
    audit(db, user, "transfer.requested", str(body.batch_id))
    commit(db)
    return row


@app.post("/api/transfers/{tid}/approve")
def approve_transfer(tid: int, db=Depends(get_db), user=Depends(roles("admin"))):
    row = db.get(m.Transfer, tid)
    if not row:
        raise HTTPException(404, "Transfer not found")
    claim = db.execute(
        update(m.Transfer)
        .where(m.Transfer.id == tid, m.Transfer.status == "pending")
        .values(status="approved")
    )
    if not claim.rowcount:
        raise HTTPException(409, "Transfer already processed")
    source = db.get(m.Batch, row.batch_id)
    changed = db.execute(
        update(m.Batch)
        .where(m.Batch.id == source.id, m.Batch.doses >= row.doses, m.Batch.expires > now())
        .values(doses=m.Batch.doses - row.doses)
    )
    if not changed.rowcount:
        db.rollback()
        raise HTTPException(409, "Insufficient unexpired stock")
    db.add(
        m.Batch(
            facility_id=row.destination_id,
            code=f"TRF-{tid}-{source.id}",
            vaccine=source.vaccine,
            doses=row.doses,
            expires=source.expires,
        )
    )
    audit(db, user, "transfer.approved", f"{tid}: {row.doses} doses")
    commit(db)
    return {"status": "approved"}


class Waste(BaseModel):
    doses: int = Field(ge=1)
    reason: str = Field(min_length=4, max_length=200)


@app.post("/api/batches/{bid}/waste")
def waste(bid: int, body: Waste, db=Depends(get_db), user=Depends(manager)):
    result = db.execute(
        update(m.Batch)
        .where(m.Batch.id == bid, m.Batch.doses >= body.doses)
        .values(doses=m.Batch.doses - body.doses)
    )
    if not result.rowcount:
        raise HTTPException(409, "Insufficient stock")
    audit(db, user, "stock.wasted", f"Batch {bid}, {body.doses}: {body.reason}")
    commit(db)
    return {"status": "recorded"}


@app.get("/api/audit")
def history(db=Depends(get_db), user=Depends(manager)):
    return db.scalars(select(m.Audit).order_by(m.Audit.id.desc()).limit(200)).all()


@app.get("/api/notifications")
def notifications(db=Depends(get_db), user=Depends(current)):
    return db.scalars(select(m.Notification).order_by(m.Notification.id.desc()).limit(200)).all()


def automation_auth(authorization: str = Header(default="")):
    expected = os.getenv("AUTOMATION_TOKEN", "")
    if len(expected) < 32 or not secrets.compare_digest(authorization, "Bearer " + expected):
        raise HTTPException(401, "Invalid automation credential")


def run_workflow(kind, db):
    today = now().date().isoformat()
    items = []
    if kind == "low-stock":
        for b in db.scalars(select(m.Batch).where(m.Batch.doses < 30, m.Batch.expires > now())):
            items.append(
                (
                    f"low:{b.id}:{today}",
                    f"Clinic {b.facility_id}: {b.vaccine} batch {b.code} has {b.doses} doses. Review a transfer or replenish.",
                )
            )
    elif kind == "expiry":
        for b in db.scalars(
            select(m.Batch).where(m.Batch.expires < now() + timedelta(days=30), m.Batch.doses > 0)
        ):
            items.append(
                (
                    f"expiry:{b.id}:{today}",
                    f"Batch {b.code}: {b.doses} doses, expiry {b.expires.date()}. Review inventory.",
                )
            )
    elif kind == "reminders":
        for a in db.scalars(
            select(m.Appointment).where(
                m.Appointment.status == "booked",
                m.Appointment.slot > now(),
                m.Appointment.slot < now() + timedelta(days=1),
            )
        ):
            items.append(
                (
                    f"reminder:{a.id}:{a.slot.isoformat()}",
                    f"{a.patient_ref}: {a.vaccine} appointment at clinic {a.facility_id}, {a.slot} UTC.",
                )
            )
    elif kind == "daily-report":
        count = db.scalar(select(func.count(m.Appointment.id)).where(m.Appointment.status == "booked"))
        doses = db.scalar(select(func.sum(m.Batch.doses)).where(m.Batch.expires > now())) or 0
        items.append(
            (
                f"report:{today}",
                f"Operations report: {count} booked appointments; {doses} available unexpired doses. Fictional demo data only.",
            )
        )
    else:
        raise HTTPException(404, "Unknown workflow")
    created = 0
    for key, message in items:
        try:
            with db.begin_nested():
                db.add(m.Notification(event_key=key, kind=kind, message=message))
                db.flush()
            created += 1
        except IntegrityError:
            pass
    db.commit()
    return {
        "workflow": kind,
        "created": created,
        "duplicates_skipped": len(items) - created,
        "delivery": "demo_inbox_only",
    }


@app.post("/api/automation/{kind}", dependencies=[Depends(automation_auth)])
def automation(kind: str, db=Depends(get_db)):
    return run_workflow(kind, db)


@app.post("/api/demo/workflows/{kind}")
def manual_workflow(kind: str, db=Depends(get_db), user=Depends(manager)):
    audit(db, user, "workflow.preview", kind)
    return run_workflow(kind, db)


static = Path(__file__).parent / "static"
if static.exists():
    app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(static / "index.html")
