# tests/test_health.py
from fastapi.testclient import TestClient
from app.api.server import app

def test_health():
    with TestClient(app) as c:
        r = c.get("/health")
        assert r.status_code == 200
        assert r.json().get("status") in {"ok","OK","healthy","up"}
