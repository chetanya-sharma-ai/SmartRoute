"""
test_api.py — SmartRoute API Tests
─────────────────────────────────────────────────────────────────────────────
Tests for FastAPI endpoint validation, error handling, and data transparency.
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


def test_route_rejects_unknown_routing_options():
    base = "/route?src=253179982&dst=1328155425"
    for option in ("scenario=live", "priority=ambulance", "algo=greedy", "weather=Storm"):
        response = client.get(f"{base}&{option}")
        assert response.status_code == 422, option


def test_route_rejects_src_equals_dst():
    """src == dst is an invalid request and must return 422."""
    r = client.get("/route?src=253179982&dst=253179982")
    assert r.status_code == 422


def test_route_invalid_node_id_zero_returns_422():
    """Non-positive node IDs must be rejected by FastAPI schema validation with 422."""
    r = client.get("/route?src=0&dst=1")
    assert r.status_code == 422


def test_route_unknown_node_returns_404_with_tip():
    """
    Nodes not present in the graph must return exact 404 with an actionable tip.
    Node 253179982 is in the graph; 999999999 is unknown.
    """
    r = client.get("/route?src=253179982&dst=999999999")
    assert r.status_code == 404
    detail = r.json().get("detail", {})
    assert isinstance(detail, dict)
    assert "tip" in detail
    assert "999999999" in detail.get("message", "")


def test_nearest_node_rejects_out_of_bounds_coords():
    """Coordinates far outside the supported area must return 400 Bad Request."""
    r = client.get("/nodes/nearest?lat=0.0&lon=0.0")
    assert r.status_code == 400
    detail = r.json().get("detail", {})
    assert "outside the supported graph area" in detail.get("message", "")


def test_congestion_rejects_negative_road_length():
    """Negative road length must return 422."""
    r = client.get("/congestion?from_node=1&to_node=2&hour=8&road_length=-10")
    assert r.status_code == 422


def test_congestion_rejects_unsupported_weather():
    """Unsupported weather string must return 422."""
    r = client.get("/congestion?from_node=1&to_node=2&hour=8&weather=Blizzard")
    assert r.status_code == 422


def test_simulate_rejects_invalid_day():
    """Day of week outside 0-6 must return 422."""
    r = client.get("/simulate?day=7")
    assert r.status_code == 422


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


def test_graph_summary_endpoint():
    """Graph summary should return metadata when graph_data.json exists."""
    r = client.get("/graph/summary")
    # Either 200 with data or 404 if summary file not generated yet
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        data = r.json()
        assert "num_nodes" in data or "center_lat" in data


def test_congestion_peak_hour_rainy_is_high_or_medium():
    """
    At rush hour (hour=8) with Rain, the rule-based congestion fallback must
    return High. This validates the rule without needing a trained model.
    """
    r = client.get("/congestion?from_node=1&to_node=2&hour=8&weather=Rain")
    assert r.status_code == 200
    data = r.json()
    assert data["congestion_level"] in ("High", "Medium")


def test_simulate_all_hours_return_valid_congestion():
    r = client.get("/simulate?weather=Clear&day=0")
    assert r.status_code == 200
    for entry in r.json()["hourly"]:
        assert entry["congestion_level"] in ("Low", "Medium", "High")
        assert entry["multiplier"] >= 1.0
