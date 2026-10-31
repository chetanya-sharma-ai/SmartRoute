"""Apply transparent, local demo incident scenarios to predicted road costs."""

import json
import os
import tempfile

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SCENARIOS_PATH = os.path.join(DATA_DIR, "demo_scenarios.json")
BLOCKING_CONDITIONS = {"blocked", "flooded", "inaccessible"}


def load_scenarios() -> dict:
    with open(SCENARIOS_PATH, encoding="utf-8") as scenario_file:
        return json.load(scenario_file)["scenarios"]


def get_scenario_overlay_data(graph_path: str, scenario: str) -> dict:
    """Extract GeoJSON features for edges affected by the given simulated scenario."""
    scenarios = load_scenarios()
    if scenario not in scenarios:
        valid = ", ".join(sorted(scenarios.keys()))
        raise ValueError(f"Unknown scenario '{scenario}'. Valid values: {valid}")

    definition = scenarios[scenario]
    if scenario == "normal" or not definition.get("road_names"):
        return {
            "type": "FeatureCollection",
            "scenario": "normal",
            "label": definition.get("label", "Normal conditions"),
            "condition": None,
            "multiplier": 1.0,
            "road_names": [],
            "data_source": "simulated demo scenario; not a live incident feed",
            "affected_segments": 0,
            "features": []
        }

    with open(graph_path, encoding="utf-8") as gf:
        graph = json.load(gf)

    nodes_map = {int(n["id"]): n for n in graph.get("nodes", [])}
    road_names = {name.casefold() for name in definition.get("road_names", [])}
    condition = definition.get("condition")
    multiplier = float(definition.get("multiplier", 1.0))
    label = definition.get("label", scenario)

    features = []
    for edge in graph.get("edges", []):
        if "from" not in edge or "to" not in edge:
            continue
        edge_name = str(edge.get("name", "")).strip()
        if edge_name.casefold() in road_names:
            u_id = int(edge["from"])
            v_id = int(edge["to"])
            u = nodes_map.get(u_id)
            v = nodes_map.get(v_id)
            if u and v:
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [float(u["lon"]), float(u["lat"])],
                            [float(v["lon"]), float(v["lat"])]
                        ]
                    },
                    "properties": {
                        "from": u_id,
                        "to": v_id,
                        "name": edge_name,
                        "length_m": float(edge.get("length", 0.0)),
                        "speed_kph": float(edge.get("speed_kph", 40.0)),
                        "condition": condition,
                        "multiplier": multiplier,
                        "scenario": scenario,
                        "label": label,
                        "data_source": "simulated demo scenario; not a live incident feed"
                    }
                })

    return {
        "type": "FeatureCollection",
        "scenario": scenario,
        "label": label,
        "condition": condition,
        "multiplier": multiplier,
        "road_names": definition.get("road_names", []),
        "data_source": "simulated demo scenario; not a live incident feed",
        "affected_segments": len(features),
        "features": features
    }


def create_route_weights(graph_path: str, base_weights_path: str | None,
                         scenario: str, priority: str) -> tuple[str, dict]:
    """Create a temporary C++-compatible weight file with demo incidents applied.

    Args:
        graph_path:        Path to graph_data.json
        base_weights_path: Path to ML-computed edge_weights JSON, or None
        scenario:          One of the keys in demo_scenarios.json
        priority:          "standard" or "emergency"

    Returns:
        (tmp_weights_path, incident_context_dict)

    Raises:
        ValueError: if scenario is not a known key in demo_scenarios.json
        FileNotFoundError: if graph_path does not exist
    """
    with open(graph_path, encoding="utf-8") as graph_file:
        graph = json.load(graph_file)

    # Build edge-name lookup; skip malformed edges
    edge_names: dict[tuple[int, int], str] = {}
    for edge in graph.get("edges", []):
        if "from" not in edge or "to" not in edge:
            continue
        edge_names[(int(edge["from"]), int(edge["to"]))] = str(
            edge.get("name", "")
        ).strip()

    if base_weights_path and os.path.isfile(base_weights_path):
        with open(base_weights_path, encoding="utf-8") as weight_file:
            weights = json.load(weight_file)
    else:
        weights = []
        for edge in graph.get("edges", []):
            # Skip malformed edges silently
            if "from" not in edge or "to" not in edge or "length" not in edge:
                continue
            try:
                speed = float(edge.get("speed_kph") or 40.0)
                if speed <= 0:
                    speed = 40.0
                length = float(edge["length"])
                if length < 0:
                    length = 0.0
            except (TypeError, ValueError):
                continue
            weights.append({
                "from": int(edge["from"]),
                "to": int(edge["to"]),
                "time_weight": length / (speed * 1000 / 3600),
                "congestion": "Low",
            })

    scenarios = load_scenarios()

    # Validate scenario name — explicit error instead of a silent KeyError
    if scenario not in scenarios:
        valid = ", ".join(sorted(scenarios.keys()))
        raise ValueError(
            f"Unknown scenario '{scenario}'. Valid values: {valid}"
        )

    definition = scenarios[scenario]
    road_names = {name.casefold() for name in definition.get("road_names", [])}
    condition = definition.get("condition")
    multiplier = float(definition.get("multiplier", 1.0))
    affected = 0

    for weight in weights:
        try:
            from_id = int(weight["from"])
            to_id = int(weight["to"])
        except (KeyError, TypeError, ValueError):
            continue
        road_name = edge_names.get((from_id, to_id), "")
        if road_name.casefold() not in road_names:
            continue
        affected += 1
        if condition in BLOCKING_CONDITIONS:
            weight["time_weight"] = -1.0          # sentinel: skip this edge
        elif condition == "congested":
            current = float(weight["time_weight"])
            if current > 0:
                weight["time_weight"] = current * multiplier

    emergency_high_cost_segments = 0
    if priority == "emergency":
        for weight in weights:
            if weight.get("congestion") == "High" and float(weight["time_weight"]) > 0:
                weight["time_weight"] = float(weight["time_weight"]) * 1.25
                emergency_high_cost_segments += 1

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".json", prefix="smartroute-",
        delete=False,
    ) as handle:
        json.dump(weights, handle)

    return handle.name, {
        "scenario": scenario,
        "label": definition["label"],
        "priority": priority,
        "data_source": "simulated demo scenario; no live incident feed",
        "affected_segments": affected,
        "condition": condition or "clear",
        "emergency_high_congestion_segments": emergency_high_cost_segments,
    }
