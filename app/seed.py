"""Explicit fictional demo bootstrap. Never run against real patient data."""

import os
from datetime import timezone, datetime, timedelta
from sqlalchemy import select
from .database import SessionLocal
from .models import User, Facility, Batch, Appointment
from .auth import hash_password


def seed():
    password = os.environ.get("DEMO_PASSWORD", "")
    if len(password) < 12:
        raise RuntimeError("Set DEMO_PASSWORD to at least 12 characters")
    with SessionLocal() as db:
        if db.scalar(select(User.id)):
            print("Already initialized; no records changed.")
            return
        for role in ["admin", "manager", "nurse"]:
            db.add(User(username=f"demo.{role}", role=role, password_hash=hash_password(password)))
        for name, district in [
            ("Cedar Community Clinic", "North District"),
            ("Willow Health Centre", "Central District"),
            ("Maple Family Clinic", "South District"),
        ]:
            db.add(Facility(name=name, district=district))
        db.flush()
        clinics = db.scalars(select(Facility)).all()
        batches = []
        for i, clinic in enumerate(clinics):
            for j, vaccine in enumerate(["MMR", "Hepatitis B", "Polio"]):
                b = Batch(
                    facility_id=clinic.id,
                    code=f"DEMO-{i+1}{j+1}",
                    vaccine=vaccine,
                    doses=[18, 126, 84][j] + i * 12,
                    expires=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=18 + j * 70),
                )
                db.add(b)
                batches.append(b)
        db.flush()
        for i in range(12):
            b = batches[i % len(batches)]
            b.doses -= 1
            db.add(
                Appointment(
                    facility_id=b.facility_id,
                    batch_id=b.id,
                    patient_ref=f"DEMO-{1001+i}",
                    vaccine=b.vaccine,
                    slot=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=3 + i * 2),
                )
            )
        db.commit()
        print("Fictional demo clinics and three role accounts created.")


if __name__ == "__main__":
    seed()
