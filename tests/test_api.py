import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "sqlite:///./test.db")
os.environ["JWT_SECRET"] = "test-only-signing-secret-not-for-deployment-123"
os.environ["AUTOMATION_TOKEN"] = "test-only-automation-secret-not-for-deployment"
os.environ["DEMO_PASSWORD"] = "test-only-password"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed()
    with TestClient(app) as c:
        yield c


def auth(c, role="admin"):
    r = c.post("/api/auth/login", json={"username": "demo." + role, "password": "test-only-password"})
    assert r.status_code == 200
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def future(days=2):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def batch(c, h, doses=1):
    return c.post(
        "/api/batches",
        headers=h,
        json={
            "facility_id": 1,
            "code": "TEST-ONE",
            "vaccine": "Test vaccine",
            "doses": doses,
            "expires": future(30),
        },
    ).json()


def booking(ref="DEMO-TEST"):
    return {"facility_id": 1, "patient_ref": ref, "vaccine": "Test vaccine", "slot": future()}


def test_auth_and_roles(client):
    assert client.get("/api/batches").status_code == 401
    nurse = auth(client, "nurse")
    assert client.get("/api/batches", headers=nurse).status_code == 200
    assert client.get("/api/audit", headers=nurse).status_code == 403
    assert (
        client.post(
            "/api/transfers", headers=nurse, json={"batch_id": 1, "destination_id": 2, "doses": 1}
        ).status_code
        == 403
    )
    assert (
        client.post("/api/auth/login", json={"username": "demo.admin", "password": "wrong"}).status_code
        == 401
    )


def test_stock_and_cancellation_idempotence(client):
    h = auth(client)
    b = batch(client, h)
    a = client.post("/api/appointments", headers=h, json=booking()).json()
    assert client.post("/api/appointments", headers=h, json=booking("DEMO-OTHER")).status_code == 409
    for _ in range(2):
        assert client.post(f"/api/appointments/{a['id']}/cancel", headers=h).status_code == 200
    stocks = client.get("/api/batches", headers=h).json()
    assert next(x["doses"] for x in stocks if x["id"] == b["id"]) == 1


def test_concurrent_last_dose(client):
    h = auth(client)
    batch(client, h)
    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = list(
            pool.map(
                lambda i: client.post(
                    "/api/appointments", headers=h, json=booking(f"DEMO-RACE-{i}")
                ).status_code,
                range(6),
            )
        )
    assert codes.count(201) == 1
    assert codes.count(409) == 5


def test_transfer_approval_and_balance(client):
    h = auth(client)
    b = batch(client, h, 10)
    t = client.post(
        "/api/transfers", headers=h, json={"batch_id": b["id"], "destination_id": 2, "doses": 4}
    ).json()
    assert (
        client.post(f"/api/transfers/{t['id']}/approve", headers=auth(client, "manager")).status_code == 403
    )
    assert client.post(f"/api/transfers/{t['id']}/approve", headers=h).status_code == 200
    assert client.post(f"/api/transfers/{t['id']}/approve", headers=h).status_code == 409
    rows = [b for b in client.get("/api/batches", headers=h).json() if b["vaccine"] == "Test vaccine"]
    assert sorted(b["doses"] for b in rows) == [4, 6]


def test_workflow_dedup_and_auth(client):
    assert client.post("/api/automation/daily-report").status_code == 401
    h = {"Authorization": "Bearer " + os.environ["AUTOMATION_TOKEN"]}
    assert client.post("/api/automation/daily-report", headers=h).json()["created"] == 1
    assert client.post("/api/automation/daily-report", headers=h).json()["created"] == 0
    rows = client.get("/api/notifications", headers=auth(client)).json()
    assert len(rows) == 1 and rows[0]["status"] == "demo_only"


def test_expiry_and_invalid_patient(client):
    h = auth(client)
    batch(client, h)
    body = booking("real-person")
    assert client.post("/api/appointments", headers=h, json=body).status_code == 422
    body = booking()
    body["slot"] = future(40)
    assert client.post("/api/appointments", headers=h, json=body).status_code == 409


def test_failed_duplicate_rolls_back_stock(client):
    h = auth(client)
    b = batch(client, h, 3)
    body = booking()
    assert client.post("/api/appointments", headers=h, json=body).status_code == 201
    assert client.post("/api/appointments", headers=h, json=body).status_code == 409
    rows = client.get("/api/batches", headers=h).json()
    assert next(x["doses"] for x in rows if x["id"] == b["id"]) == 2


def test_reschedule_and_waste(client):
    h = auth(client)
    b = batch(client, h, 3)
    a = client.post("/api/appointments", headers=h, json=booking()).json()
    assert (
        client.post(
            f"/api/appointments/{a['id']}/reschedule", headers=h, json={"slot": future(3)}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/batches/{b['id']}/waste", headers=h, json={"doses": 1, "reason": "Demo damaged vial"}
        ).status_code
        == 200
    )
    rows = client.get("/api/batches", headers=h).json()
    assert next(x["doses"] for x in rows if x["id"] == b["id"]) == 1


def test_reschedule_last_reserved_dose(client):
    h = auth(client)
    batch(client, h, 1)
    a = client.post("/api/appointments", headers=h, json=booking()).json()
    assert (
        client.post(
            f"/api/appointments/{a['id']}/reschedule", headers=h, json={"slot": future(3)}
        ).status_code
        == 200
    )


def test_failed_transfer_leaves_request_pending(client):
    h = auth(client)
    b = batch(client, h, 1)
    t = client.post(
        "/api/transfers", headers=h, json={"batch_id": b["id"], "destination_id": 2, "doses": 5}
    ).json()
    assert client.post(f"/api/transfers/{t['id']}/approve", headers=h).status_code == 409
    assert client.get("/api/transfers", headers=h).json()[0]["status"] == "pending"


def test_all_workflows_and_audit(client):
    h = auth(client)
    for kind in ["low-stock", "expiry", "reminders", "daily-report"]:
        response = client.post("/api/demo/workflows/" + kind, headers=h)
        assert response.status_code == 200
        assert response.json()["created"] > 0
    assert len(client.get("/api/audit", headers=h).json()) == 4
    assert all(n["status"] == "demo_only" for n in client.get("/api/notifications", headers=h).json())
