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
                      weights_json: str | None, algo: str) -> dict:
    """
    Pure-Python A* fallback when C++ binary isn't compiled.
    Used during development/demo. Slower but functionally identical.
    """
    import heapq
    import math

    if not os.path.exists(graph_json):
        return {"error": "Graph data not found"}

    with open(graph_json) as f:
        data = json.load(f)

    # Build adjacency map
    nodes = {n["id"]: n for n in data["nodes"]}
    adj = {}
    for node in data["nodes"]:
        adj[node["id"]] = []
    for e in data["edges"]:
        speed = e.get("speed_kph", 40)
        base_time = e["length"] / (speed * 1000 / 3600)
        adj[e["from"]].append({
            "to": e["to"], "length": e["length"], "time": base_time
        })

    # Apply ML weights if available
    if weights_json and os.path.exists(weights_json):
        with open(weights_json) as f:
            weights = json.load(f)
        weight_map = {(w["from"], w["to"]): w["time_weight"] for w in weights}
        for from_id, edges in adj.items():
            for edge in edges:
                key = (from_id, edge["to"])
                if key in weight_map:
                    edge["time"] = weight_map[key]

    def haversine(n1, n2):
        R = 6371000
        lat1, lon1 = math.radians(n1["lat"]), math.radians(n1["lon"])
        lat2, lon2 = math.radians(n2["lat"]), math.radians(n2["lon"])
        dlat = lat2 - lat1; dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    if src not in nodes or dst not in nodes:
        return {"error": f"Node {src} or {dst} not found in graph"}

    # A* search
    open_set = [(0.0, src)]
    g_score = {src: 0.0}
    g_dist  = {src: 0.0}
    came_from = {}

    while open_set:
        f, current = heapq.heappop(open_set)
        if current == dst:
            # Reconstruct
            path = []
            at = dst
            while at != src:
                path.append(at)
                at = came_from[at]
            path.append(src)
            path.reverse()
            path_nodes = [{"id": n, "lat": nodes[n]["lat"],
                           "lon": nodes[n]["lon"], "name": nodes[n].get("name","")}
                          for n in path if n in nodes]
            return {
                "algorithm": "astar_python_fallback",
                "total_distance_m": round(g_dist.get(dst, 0), 2),
                "total_time_s": round(g_score[dst], 2),
                "eta_minutes": round(g_score[dst] / 60, 2),
                "num_nodes": len(path),
                "path": path_nodes
            }

        for edge in adj.get(current, []):
            nb = edge["to"]
            tentative = g_score[current] + edge["time"]
            if tentative < g_score.get(nb, float("inf")):
                came_from[nb] = current
                g_score[nb] = tentative
                g_dist[nb] = g_dist.get(current, 0) + edge["length"]
                h = haversine(nodes[current], nodes[nb]) / 22.22 \
                    if current in nodes and nb in nodes else 0
                heapq.heappush(open_set, (tentative + h, nb))

    return {"error": "No path found between the specified nodes"}
