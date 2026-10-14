import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_full_booking_flow():
    fid = client.post("/facilities", json={"name": "Rural Clinic A", "district": "North"}).json()["id"]
    client.put("/stock", json={"facility_id": fid, "vaccine": "MMR", "doses": 1})

    body = {"facility_id": fid, "patient_ref": "p-10001", "vaccine": "MMR", "slot": "2026-11-01T09:00:00"}
    assert client.post("/appointments", json=body).status_code == 201
    assert client.post("/appointments", json=body).status_code == 409  # stock exhausted
    assert len(client.get("/stock/low?threshold=5").json()) == 1


def test_duplicate_facility():
    client.post("/facilities", json={"name": "Dup", "district": "East"})
    assert client.post("/facilities", json={"name": "Dup", "district": "East"}).status_code == 409
