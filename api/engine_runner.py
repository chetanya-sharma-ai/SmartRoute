"""
engine_runner.py
──────────────────────────────────────────────────────────────────────────────
Calls the compiled C++ smartroute_engine binary via subprocess
and parses the JSON output.
"""

import json
import os
import subprocess

# Path to the compiled C++ binary
# After CMake build: core/build/smartroute_engine.exe (Windows)
BINARY_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "smartroute_engine.exe"),
    os.path.join(os.path.dirname(__file__), "smartroute_engine"),
    os.path.join(os.path.dirname(__file__), "..", "core", "build",
                 "Release", "smartroute_engine.exe"),
    os.path.join(os.path.dirname(__file__), "..", "core", "build",
                 "smartroute_engine"),
    os.path.join(os.path.dirname(__file__), "..", "core", "build",
                 "smartroute_engine.exe"),
]


def find_binary() -> str | None:
    """Find the compiled C++ engine binary."""
    for path in BINARY_CANDIDATES:
        if os.path.isfile(path):
            return os.path.abspath(path)
    return None


def run_cpp_engine(
    graph_json: str,
    src: int,
    dst: int,
    weights_json: str | None = None,
    algo: str = "astar",
    timeout: int = 30
) -> dict:
    """
    Run the C++ pathfinding engine and return parsed JSON result.

    Args:
        graph_json:   Path to graph_data.json
        src:          Source node ID
        dst:          Destination node ID
        weights_json: Path to ML-updated edge weights JSON (optional)
        algo:         "astar" or "dijkstra"
        timeout:      Max seconds to wait for C++ process

    Returns:
        dict with route result or {"error": "..."}
    """
    binary = find_binary()
    if binary is None:
        # Fallback: Python-based pathfinding (for dev without C++ build)
        return _python_fallback(graph_json, src, dst, weights_json, algo)

    cmd = [
        binary,
        graph_json,
        str(src),
        str(dst),
        weights_json or "none",
        algo
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if proc.returncode not in (0, 1):
            return {"error": f"Engine exited with code {proc.returncode}: "
                              f"{proc.stderr.strip()}"}

        output = proc.stdout.strip()
        if not output:
            return {"error": "Engine produced no output"}

        return json.loads(output)

    except subprocess.TimeoutExpired:
        return {"error": f"Engine timed out after {timeout}s"}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON from engine: {e}"}
    except OSError as e:
        return {"error": str(e)}


def _python_fallback(graph_json: str, src: int, dst: int,
                      weights_json: str | None, algo: str = "astar") -> dict:
    """
    Pure-Python A* / Dijkstra fallback when C++ binary isn't compiled.
    Used during development/demo. Slower but functionally identical.
    """
    import heapq
    import math

    if not os.path.exists(graph_json):
        return {"error": "Graph data not found"}

    algo_norm = (algo or "astar").lower()
    if algo_norm not in ("astar", "dijkstra"):
        return {"error": f"Unsupported algorithm '{algo}'"}

    algorithm_name = f"{algo_norm}_python_fallback"

    with open(graph_json, encoding="utf-8") as f:
        data = json.load(f)

    # Build adjacency map
    nodes = {int(n["id"]): n for n in data["nodes"]}
    adj: dict[int, list[dict]] = {n["id"]: [] for n in data["nodes"]}
    for e in data.get("edges", []):
        if "from" not in e or "to" not in e or "length" not in e:
            continue
        try:
            speed = float(e.get("speed_kph") or 40.0)
            if speed <= 0:
                speed = 40.0
            length = float(e["length"])
            if length < 0:
                length = 0.0
            base_time = length / (speed * 1000.0 / 3600.0)
            from_node = int(e["from"])
            to_node = int(e["to"])
            if from_node in adj:
                adj[from_node].append({
                    "to": to_node, "length": length, "time": base_time
                })
        except (TypeError, ValueError):
            continue

    # Apply ML weights if available
    if weights_json and os.path.exists(weights_json):
        with open(weights_json, encoding="utf-8") as f:
            weights = json.load(f)
        weight_map = {(int(w["from"]), int(w["to"])): float(w["time_weight"]) for w in weights}
        for from_id, edges in adj.items():
            for edge in edges:
                key = (from_id, edge["to"])
                if key in weight_map:
                    edge["time"] = weight_map[key]

    def haversine(n1, n2):
        R = 6371000.0
        lat1, lon1 = math.radians(n1["lat"]), math.radians(n1["lon"])
        lat2, lon2 = math.radians(n2["lat"]), math.radians(n2["lon"])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2.0)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0)**2
        return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    if src not in nodes or dst not in nodes:
        missing = src if src not in nodes else dst
        return {"error": f"Node {missing} not found in graph"}

    if src == dst:
        node = nodes[src]
        return {
            "algorithm": algorithm_name,
            "total_distance_m": 0.0,
            "total_time_s": 0.0,
            "eta_minutes": 0.0,
            "num_nodes": 1,
            "path": [{"id": src, "lat": node["lat"], "lon": node["lon"], "name": node.get("name", "")}]
        }

    # Priority queue: (priority, current_node)
    # For A*: priority = g_score + heuristic(current, dst)
    # For Dijkstra: priority = g_score (heuristic = 0.0)
    initial_h = (haversine(nodes[src], nodes[dst]) / 22.22) if algo_norm == "astar" else 0.0
    open_set = [(initial_h, src)]
    g_score = {src: 0.0}
    g_dist = {src: 0.0}
    came_from = {}
    visited = set()

    while open_set:
        priority, current = heapq.heappop(open_set)

        if current in visited:
            continue
        visited.add(current)

        if current == dst:
            path = []
            at = dst
            while at != src:
                path.append(at)
                at = came_from[at]
            path.append(src)
            path.reverse()
            path_nodes = [
                {"id": n, "lat": nodes[n]["lat"], "lon": nodes[n]["lon"], "name": nodes[n].get("name", "")}
                for n in path if n in nodes
            ]
            return {
                "algorithm": algorithm_name,
                "total_distance_m": round(g_dist.get(dst, 0.0), 2),
                "total_time_s": round(g_score[dst], 2),
                "eta_minutes": round(g_score[dst] / 60.0, 2),
                "num_nodes": len(path),
                "path": path_nodes
            }

        cur_g = g_score[current]
        for edge in adj.get(current, []):
            if edge["time"] <= 0.0 or not math.isfinite(edge["time"]):
                continue
            nb = edge["to"]
            if nb in visited:
                continue

            tentative = cur_g + edge["time"]
            if tentative < g_score.get(nb, float("inf")):
                came_from[nb] = current
                g_score[nb] = tentative
                g_dist[nb] = g_dist.get(current, 0.0) + edge["length"]
                h = (haversine(nodes[nb], nodes[dst]) / 22.22) if algo_norm == "astar" else 0.0
                heapq.heappush(open_set, (tentative + h, nb))

    return {"error": "No path found between the specified nodes"}
