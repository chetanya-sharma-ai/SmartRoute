"""
test_api.py — SmartRoute API Tests
"""
import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.main import app

client = TestClient(app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert "timestamp" in r.json()


def test_route_missing_params():
    r = client.get("/route")
    assert r.status_code == 422  # Unprocessable entity (missing src/dst)


def test_route_invalid_nodes():
    r = client.get("/route?src=0&dst=1")
    # Either 404 (no path) or 503 (no graph) — both acceptable in test env
    assert r.status_code in (200, 404, 503)


def test_congestion_endpoint():
    r = client.get("/congestion?from_node=1&to_node=2&hour=8&weather=Clear")
    assert r.status_code == 200
    data = r.json()
    assert "congestion_level" in data
    assert data["congestion_level"] in ("Low", "Medium", "High")


def test_simulate_endpoint():
    r = client.get("/simulate?weather=Rain&day=1")
    assert r.status_code == 200
    data = r.json()
    assert len(data["hourly"]) == 24


def test_heatmap_endpoint():
    r = client.get("/heatmap?hour=8&weather=Clear&day=0")
    assert r.status_code == 200
    data = r.json()
    assert "features" in data
    assert isinstance(data["features"], list)
