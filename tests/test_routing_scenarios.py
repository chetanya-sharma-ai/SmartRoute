"""
test_routing_scenarios.py
─────────────────────────────────────────────────────────────────────────────
Tests for route safety, alternate-route selection, validation, and error cases.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.engine_runner import run_cpp_engine
from api.route_scenarios import create_route_weights


# ── Helper ────────────────────────────────────────────────────────────────────

def _write_scenarios(tmp_path, scenarios_dict: dict) -> str:
    path = tmp_path / "scenarios.json"
    path.write_text(json.dumps({"scenarios": scenarios_dict}), encoding="utf-8")
    return str(path)


# ── Core safety: blocked/flooded/inaccessible roads are excluded ──────────────

@pytest.mark.parametrize("condition", ["blocked", "flooded", "inaccessible"])
def test_hazardous_road_is_excluded_and_cpp_finds_alternative(tmp_path, monkeypatch, condition):
    """
    Graph: direct 1→4 (Main Road, 8 s), alternate 1→2→4 (Side Road, 24 s).
    When Main Road is blocked/flooded/inaccessible the route MUST use 1→2→4.
    """
    from api import route_scenarios

    graph = {
        "nodes": [
            {"id": 1, "lat": 12.0, "lon": 77.0, "name": "Start"},
            {"id": 2, "lat": 12.001, "lon": 77.0, "name": "Via"},
            {"id": 4, "lat": 12.002, "lon": 77.0, "name": "Destination"},
        ],
        "edges": [
            {"from": 1, "to": 4, "length": 250, "speed_kph": 40, "name": "Main Road"},
            {"from": 1, "to": 2, "length": 120, "speed_kph": 40, "name": "Side Road"},
            {"from": 2, "to": 4, "length": 120, "speed_kph": 40, "name": "Side Road"},
        ],
    }
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    base_path = tmp_path / "weights.json"
    base_path.write_text(json.dumps([
        {"from": 1, "to": 4, "time_weight": 8,  "congestion": "Low"},
        {"from": 1, "to": 2, "time_weight": 12, "congestion": "Low"},
        {"from": 2, "to": 4, "time_weight": 12, "congestion": "Low"},
    ]), encoding="utf-8")
    scenario_path = _write_scenarios(tmp_path, {
        "normal":       {"label": "Normal",  "condition": None, "road_names": []},
        "road_closure": {"label": "Hazard",  "condition": condition, "road_names": ["Main Road"]},
    })
    monkeypatch.setattr(route_scenarios, "SCENARIOS_PATH", scenario_path)

    normal_weights, _ = create_route_weights(str(graph_path), str(base_path), "normal", "standard")
    closure_weights, context = create_route_weights(
        str(graph_path), str(base_path), "road_closure", "standard"
    )
    try:
        normal = run_cpp_engine(str(graph_path), 1, 4, normal_weights, "dijkstra")
        closed = run_cpp_engine(str(graph_path), 1, 4, closure_weights, "dijkstra")
    finally:
        os.remove(normal_weights)
        os.remove(closure_weights)

    # Normal route takes the direct edge
    assert [node["id"] for node in normal["path"]] == [1, 4], \
        f"Normal should use direct path, got {[n['id'] for n in normal['path']]}"
    # Blocked route must avoid Main Road and go via node 2
    assert [node["id"] for node in closed["path"]] == [1, 2, 4], \
        f"Blocked route should use alternate path, got {[n['id'] for n in closed['path']]}"
    assert context["affected_segments"] == 1
    assert context["data_source"].startswith("simulated")


def test_blocked_road_never_appears_in_result_path(tmp_path, monkeypatch):
    """
    The path returned for a blocked scenario must not include the blocked edge (1→4).
    Verifies the safety invariant explicitly.
    """
    from api import route_scenarios

    graph = {
        "nodes": [
            {"id": 1, "lat": 12.0, "lon": 77.0, "name": "A"},
            {"id": 2, "lat": 12.001, "lon": 77.0, "name": "B"},
            {"id": 4, "lat": 12.002, "lon": 77.0, "name": "C"},
        ],
        "edges": [
            {"from": 1, "to": 4, "length": 100, "speed_kph": 60, "name": "Blocked Rd"},
            {"from": 1, "to": 2, "length": 150, "speed_kph": 40, "name": "Safe Rd"},
            {"from": 2, "to": 4, "length": 150, "speed_kph": 40, "name": "Safe Rd"},
        ],
    }
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    scenario_path = _write_scenarios(tmp_path, {
        "road_closure": {"label": "Closure", "condition": "blocked", "road_names": ["Blocked Rd"]},
    })
    monkeypatch.setattr(route_scenarios, "SCENARIOS_PATH", scenario_path)

    weights_path, _ = create_route_weights(
        str(graph_path), None, "road_closure", "standard"
    )
    try:
        result = run_cpp_engine(str(graph_path), 1, 4, weights_path, "astar")
    finally:
        os.remove(weights_path)

    assert "path" in result, f"Expected a path but got: {result}"
    path_ids = [n["id"] for n in result["path"]]
    # The edge 1→4 (Blocked Rd) must not appear as a direct hop
    assert 1 in path_ids and 4 in path_ids
    # If there's a direct edge 1→4 in the path, node 2 should not be absent
    # (i.e., the path must go through 2 since the direct edge is blocked)
    assert 2 in path_ids, \
        f"Blocked direct edge should force route through node 2; got path {path_ids}"


def test_no_route_when_all_edges_blocked(tmp_path, monkeypatch):
    """
    When both direct and alternate paths are blocked the engine must return an error,
    not a partial or empty route.
    """
    from api import route_scenarios

    graph = {
        "nodes": [
            {"id": 1, "lat": 12.0, "lon": 77.0, "name": "Start"},
            {"id": 2, "lat": 12.002, "lon": 77.0, "name": "End"},
        ],
        "edges": [
            {"from": 1, "to": 2, "length": 200, "speed_kph": 40, "name": "Only Road"},
        ],
    }
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    scenario_path = _write_scenarios(tmp_path, {
        "road_closure": {"label": "Block all", "condition": "blocked", "road_names": ["Only Road"]},
    })
    monkeypatch.setattr(route_scenarios, "SCENARIOS_PATH", scenario_path)

    weights_path, context = create_route_weights(
        str(graph_path), None, "road_closure", "standard"
    )
    try:
        result = run_cpp_engine(str(graph_path), 1, 2, weights_path, "astar")
    finally:
        os.remove(weights_path)

    assert "error" in result, \
        f"Expected an error response when no route exists, got: {result}"
    assert context["affected_segments"] == 1


def test_disconnected_graph_returns_error(tmp_path, monkeypatch):
    """
    Nodes that are not connected at all must produce a clear error, not crash or
    silently return an empty path.
    """
    graph = {
        "nodes": [
            {"id": 10, "lat": 12.0,  "lon": 77.0, "name": "Island A"},
            {"id": 20, "lat": 12.05, "lon": 77.1, "name": "Island B"},
        ],
        "edges": [],   # no edges at all — disconnected graph
    }
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")

    result = run_cpp_engine(str(graph_path), 10, 20, None, "astar")
    assert "error" in result, f"Expected error for disconnected graph, got: {result}"


def test_invalid_node_id_returns_error(tmp_path):
    """
    Requesting a route from/to a node ID that does not exist in the graph must
    produce a clear error, not crash.
    """
    graph = {
        "nodes": [{"id": 1, "lat": 12.0, "lon": 77.0, "name": "X"}],
        "edges": [],
    }
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")

    result = run_cpp_engine(str(graph_path), 1, 99999, None, "astar")
    assert "error" in result, f"Expected error for missing node, got: {result}"


# ── Validation ────────────────────────────────────────────────────────────────

def test_unknown_scenario_raises_value_error(tmp_path, monkeypatch):
    """
    Requesting an unknown scenario name must raise ValueError with a helpful message
    listing valid names, not a silent KeyError.
    """
    from api import route_scenarios

    graph = {"nodes": [], "edges": []}
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    scenario_path = _write_scenarios(tmp_path, {
        "normal": {"label": "Normal", "condition": None, "road_names": []},
    })
    monkeypatch.setattr(route_scenarios, "SCENARIOS_PATH", scenario_path)

    with pytest.raises(ValueError, match="Unknown scenario"):
        create_route_weights(str(graph_path), None, "not_a_real_scenario", "standard")


def test_malformed_edges_are_skipped_gracefully(tmp_path, monkeypatch):
    """
    Edges missing required fields (from, to, length) must be silently skipped,
    not cause a crash. The remaining valid edge(s) must still be processed.
    """
    from api import route_scenarios

    graph = {
        "nodes": [
            {"id": 1, "lat": 12.0, "lon": 77.0, "name": "A"},
            {"id": 2, "lat": 12.001, "lon": 77.0, "name": "B"},
        ],
        "edges": [
            {"from": 1, "to": 2, "length": 200, "speed_kph": 40, "name": "Good Road"},
            {"length": 100, "speed_kph": 40, "name": "Missing from/to"},   # malformed
            {"from": 3, "speed_kph": 40, "name": "Missing to and length"}, # malformed
        ],
    }
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    scenario_path = _write_scenarios(tmp_path, {
        "normal": {"label": "Normal", "condition": None, "road_names": []},
    })
    monkeypatch.setattr(route_scenarios, "SCENARIOS_PATH", scenario_path)

    weights_path, ctx = create_route_weights(str(graph_path), None, "normal", "standard")
    try:
        weights = json.loads(open(weights_path, encoding="utf-8").read())
    finally:
        os.remove(weights_path)

    # Only the valid edge should appear
    assert len(weights) == 1
    assert weights[0]["from"] == 1
    assert weights[0]["to"] == 2
    assert ctx["affected_segments"] == 0


# ── Emergency profile ─────────────────────────────────────────────────────────

def test_emergency_profile_increases_high_congestion_cost(tmp_path, monkeypatch):
    from api import route_scenarios

    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps({"nodes": [], "edges": [
        {"from": 1, "to": 2, "length": 100, "speed_kph": 40, "name": "Road"}
    ]}), encoding="utf-8")
    base_path = tmp_path / "weights.json"
    base_path.write_text(json.dumps([
        {"from": 1, "to": 2, "time_weight": 10, "congestion": "High"}
    ]), encoding="utf-8")
    scenario_path = _write_scenarios(tmp_path, {
        "normal": {"label": "Normal", "condition": None, "road_names": []},
    })
    monkeypatch.setattr(route_scenarios, "SCENARIOS_PATH", scenario_path)

    weights_path, context = create_route_weights(
        str(graph_path), str(base_path), "normal", "emergency"
    )
    try:
        weights = json.loads(open(weights_path, encoding="utf-8").read())
    finally:
        os.remove(weights_path)

    assert weights[0]["time_weight"] == pytest.approx(12.5)
    assert context["emergency_high_congestion_segments"] == 1


def test_emergency_does_not_affect_low_congestion_edges(tmp_path, monkeypatch):
    """Emergency profile must only increase cost of High-congestion edges."""
    from api import route_scenarios

    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps({"nodes": [], "edges": [
        {"from": 1, "to": 2, "length": 100, "speed_kph": 40, "name": "Road"}
    ]}), encoding="utf-8")
    base_path = tmp_path / "weights.json"
    base_path.write_text(json.dumps([
        {"from": 1, "to": 2, "time_weight": 10, "congestion": "Low"}
    ]), encoding="utf-8")
    scenario_path = _write_scenarios(tmp_path, {
        "normal": {"label": "Normal", "condition": None, "road_names": []},
    })
    monkeypatch.setattr(route_scenarios, "SCENARIOS_PATH", scenario_path)

    weights_path, context = create_route_weights(
        str(graph_path), str(base_path), "normal", "emergency"
    )
    try:
        weights = json.loads(open(weights_path, encoding="utf-8").read())
    finally:
        os.remove(weights_path)

    assert weights[0]["time_weight"] == pytest.approx(10.0)   # unchanged
    assert context["emergency_high_congestion_segments"] == 0


# ── Congestion spike ──────────────────────────────────────────────────────────

def test_simulated_congestion_spike_increases_named_road_cost(tmp_path, monkeypatch):
    from api import route_scenarios

    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps({"nodes": [], "edges": [
        {"from": 1, "to": 2, "length": 100, "speed_kph": 40, "name": "Main Road"},
        {"from": 2, "to": 3, "length": 100, "speed_kph": 40, "name": "Side Road"},
    ]}), encoding="utf-8")
    base_path = tmp_path / "weights.json"
    base_path.write_text(json.dumps([
        {"from": 1, "to": 2, "time_weight": 10, "congestion": "Low"},
        {"from": 2, "to": 3, "time_weight": 10, "congestion": "Low"},
    ]), encoding="utf-8")
    scenario_path = _write_scenarios(tmp_path, {
        "congestion_spike": {"label": "Spike", "condition": "congested",
                             "multiplier": 2.5, "road_names": ["Main Road"]},
    })
    monkeypatch.setattr(route_scenarios, "SCENARIOS_PATH", scenario_path)

    weights_path, context = create_route_weights(
        str(graph_path), str(base_path), "congestion_spike", "standard"
    )
    try:
        weights = json.loads(open(weights_path, encoding="utf-8").read())
    finally:
        os.remove(weights_path)

    assert [item["time_weight"] for item in weights] == [25, 10]
    assert context["affected_segments"] == 1


def test_congestion_prefers_alternate_when_named_road_spiked(tmp_path, monkeypatch):
    """
    With a 2.5× spike on Main Road, a route of equal base distance must
    prefer Side Road when it becomes faster after the multiplier.
    """
    from api import route_scenarios

    graph = {
        "nodes": [
            {"id": 1, "lat": 12.0,   "lon": 77.0, "name": "Start"},
            {"id": 2, "lat": 12.001, "lon": 77.0, "name": "Via"},
            {"id": 3, "lat": 12.002, "lon": 77.0, "name": "End"},
        ],
        "edges": [
            {"from": 1, "to": 3, "length": 200, "speed_kph": 40, "name": "Main Road"},
            {"from": 1, "to": 2, "length": 110, "speed_kph": 40, "name": "Side Road"},
            {"from": 2, "to": 3, "length": 110, "speed_kph": 40, "name": "Side Road"},
        ],
    }
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    base_path = tmp_path / "weights.json"
    base_path.write_text(json.dumps([
        {"from": 1, "to": 3, "time_weight": 18, "congestion": "Low"},
        {"from": 1, "to": 2, "time_weight": 10, "congestion": "Low"},
        {"from": 2, "to": 3, "time_weight": 10, "congestion": "Low"},
    ]), encoding="utf-8")
    scenario_path = _write_scenarios(tmp_path, {
        "congestion_spike": {"label": "Spike", "condition": "congested",
                             "multiplier": 2.5, "road_names": ["Main Road"]},
    })
    monkeypatch.setattr(route_scenarios, "SCENARIOS_PATH", scenario_path)

    weights_path, _ = create_route_weights(
        str(graph_path), str(base_path), "congestion_spike", "standard"
    )
    try:
        result = run_cpp_engine(str(graph_path), 1, 3, weights_path, "dijkstra")
    finally:
        os.remove(weights_path)

    path_ids = [n["id"] for n in result["path"]]
    # Spiked Main Road cost = 45s, Side Road total = 20s → must prefer 1→2→3
    assert path_ids == [1, 2, 3], \
        f"Should prefer alternate route after congestion spike, got {path_ids}"


# ── Data-source transparency ──────────────────────────────────────────────────

def test_incident_context_always_reports_simulated_source(tmp_path, monkeypatch):
    """incident_context.data_source must always declare simulated data."""
    from api import route_scenarios

    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps({"nodes": [], "edges": []}), encoding="utf-8")
    scenario_path = _write_scenarios(tmp_path, {
        "normal": {"label": "Normal", "condition": None, "road_names": []},
    })
    monkeypatch.setattr(route_scenarios, "SCENARIOS_PATH", scenario_path)

    for scenario in ["normal"]:
        weights_path, ctx = create_route_weights(
            str(graph_path), None, scenario, "standard"
        )
        os.remove(weights_path)
        assert "simulated" in ctx["data_source"].lower(), \
            f"data_source must mention 'simulated', got: {ctx['data_source']}"
