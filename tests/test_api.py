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


def test_dashboard_and_stock_listing():
    assert client.get('/').status_code == 200
    assert isinstance(client.get('/stock').json(), list)
    assert isinstance(client.get('/appointments').json(), list)


def test_last_dose_concurrent_reservation():
    from concurrent.futures import ThreadPoolExecutor
    fid = client.post('/facilities', json={'name': 'Concurrent demo clinic', 'district': 'Demo'}).json()['id']
    client.put('/stock', json={'facility_id': fid, 'vaccine': 'MMR', 'doses': 1})
    payload = {'facility_id': fid, 'patient_ref': 'demo-race', 'vaccine': 'MMR', 'slot': '2026-11-01T09:00:00'}
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(lambda _: client.post('/appointments', json=payload).status_code, range(2)))
    assert sorted(codes) == [201, 409]
    stock = [r for r in client.get('/stock').json() if r['facility_id'] == fid]
    assert stock[0]['doses'] == 0
