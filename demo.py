"""
demo.py — SmartRoute End-to-End Demo
──────────────────────────────────────────────────────────────────────────────
Demonstrates the full SmartRoute pipeline WITHOUT needing a running server
or compiled C++ binary. Uses the Python A* fallback and trained ML models.

Run:
    python demo.py
    python demo.py --nodes 300 --trials 5
"""

import argparse
import heapq
import json
import math
import os
import random
import sys
import time

# Windows console (cp1252) cannot encode Unicode box-drawing characters.
# Force UTF-8 output so the banner prints correctly.
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                   errors="replace", line_buffering=True)

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
DATA_DIR   = os.path.join(os.path.dirname(__file__), "data")

CONGESTION_MULTIPLIER = {"Low": 1.0, "Medium": 1.6, "High": 3.0}
CONGESTION_COLOR_ASCII = {"Low": "\033[92m", "Medium": "\033[93m", "High": "\033[91m"}
RESET = "\033[0m"


def banner():
    print("""
\033[1;34m╔══════════════════════════════════════════════════════════════╗
║       SmartRoute — AI-Powered Traffic & Route Optimization    ║
║       C++ Graph Engine + ML Congestion Prediction Demo        ║
╚══════════════════════════════════════════════════════════════╝\033[0m
""")


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def generate_demo_graph(n_nodes=200, seed=42):
    """Generate a small Bangalore-like demo road network."""
    random.seed(seed)
    nodes = {}
    for i in range(n_nodes):
        nodes[i] = {
            "id": i,
            "lat": 12.92 + random.uniform(-0.05, 0.05),
            "lon": 77.60 + random.uniform(-0.05, 0.05),
            "name": f"Junction_{i}"
        }
    adj = {i: [] for i in range(n_nodes)}
    for i in range(n_nodes):
        candidates = random.sample(range(n_nodes), min(8, n_nodes-1))
        connected = 0
        for j in candidates:
            if j == i: continue
            dist = haversine(nodes[i]["lat"], nodes[i]["lon"],
                             nodes[j]["lat"], nodes[j]["lon"])
            speed = random.uniform(25, 60)
            base_time = dist / (speed * 1000 / 3600)
            adj[i].append({"to": j, "length": dist, "time": base_time,
                           "speed_kph": speed})
            connected += 1
            if connected >= 4: break
    return nodes, adj


def load_ml_model():
    """Load the trained congestion classifier if available."""
    clf_path  = os.path.join(MODELS_DIR, "rf_congestion.pkl")
    feat_path = os.path.join(MODELS_DIR, "features.json")
    if not os.path.exists(clf_path):
        return None, None, None
    try:
        import joblib
        clf = joblib.load(clf_path)
        with open(feat_path) as f:
            meta = json.load(f)
        label_inv = {int(k): v for k, v in meta["label_map"].items()}
        return clf, meta["features"], label_inv
    except Exception as e:
        print(f"  [Warning] Could not load model: {e}")
        return None, None, None


def predict_congestion(clf, features, label_inv, hour, weather):
    """Predict congestion level using ML model or rule-based fallback."""
    if clf is None:
        # Rule-based fallback
        peak = hour in (7, 8, 9, 17, 18, 19)
        if peak and weather in ("Rain", "Fog"):    return "High"
        if peak:                                    return "Medium"
        if weather in ("Rain", "Fog", "Mist"):     return "Medium"
        return "Low"

    WEATHER_COLS = ["weather_Clear","weather_Clouds","weather_Rain",
                    "weather_Drizzle","weather_Fog","weather_Mist","weather_Haze"]
    import numpy as np
    row = {
        "hour": hour, "day_of_week": 0, "is_weekend": 0,
        "is_holiday": 0, "month": 9, "temp_c": 28.0, "road_length_m": 500.0
    }
    for col in WEATHER_COLS:
        row[col] = 1 if col == f"weather_{weather}" else 0
    x = np.array([row.get(f, 0) for f in features], dtype=float)
    pred = int(clf.predict([x])[0])
    return label_inv.get(pred, "Low")


def apply_ml_weights(adj, clf, features, label_inv, hour, weather):
    """Apply ML-predicted congestion multipliers to all edges."""
    for from_id, edges in adj.items():
        for edge in edges:
            cong = predict_congestion(clf, features, label_inv, hour, weather)
            mult = CONGESTION_MULTIPLIER[cong]
            edge["time_adjusted"] = edge["time"] * mult
            edge["congestion"] = cong
    return adj


def astar_route(nodes, adj, src, dst):
    """A* pathfinding using Haversine heuristic and ML-adjusted time weights."""
    def h(u):
        n1, n2 = nodes[u], nodes[dst]
        return haversine(n1["lat"], n1["lon"], n2["lat"], n2["lon"]) / 22.22

    g = {src: 0.0}
    dist_m = {src: 0.0}
    came_from = {}
    open_set = [(h(src), src)]
    expanded = 0

    while open_set:
        f, u = heapq.heappop(open_set)
        expanded += 1
        if u == dst:
            path = []
            at = dst
            while at != src:
                path.append(at)
                at = came_from[at]
            path.append(src)
            path.reverse()
            return {
                "path": path,
                "total_time_s": g[dst],
                "total_distance_m": dist_m[dst],
                "eta_minutes": g[dst] / 60,
                "nodes_expanded": expanded
            }
        for edge in adj.get(u, []):
            v = edge["to"]
            tw = edge.get("time_adjusted", edge["time"])
            tg = g[u] + tw
            if tg < g.get(v, math.inf):
                g[v] = tg
                dist_m[v] = dist_m.get(u, 0) + edge["length"]
                came_from[v] = u
                heapq.heappush(open_set, (tg + h(v), v))

    return None


def dijkstra_route(nodes, adj, src, dst):
    """Dijkstra pathfinding with ML-adjusted time weights."""
    dist = {src: 0.0}
    dist_m = {src: 0.0}
    came_from = {}
    pq = [(0.0, src)]
    expanded = 0

    while pq:
        cost, u = heapq.heappop(pq)
        expanded += 1
        if u == dst:
            path = []
            at = dst
            while at != src:
                path.append(at)
                at = came_from[at]
            path.append(src)
            path.reverse()
            return {
                "path": path,
                "total_time_s": dist[dst],
                "total_distance_m": dist_m[dst],
                "eta_minutes": dist[dst] / 60,
                "nodes_expanded": expanded
            }
        if cost > dist.get(u, math.inf):
            continue
        for edge in adj.get(u, []):
            v = edge["to"]
            tw = edge.get("time_adjusted", edge["time"])
            nc = dist[u] + tw
            if nc < dist.get(v, math.inf):
                dist[v] = nc
                dist_m[v] = dist_m.get(u, 0) + edge["length"]
                came_from[v] = u
                heapq.heappush(pq, (nc, v))

    return None


def print_result(result, algo, congestion, weather, hour):
    if not result:
        print("  [!] No path found between selected nodes.\n")
        return

    color = CONGESTION_COLOR_ASCII.get(congestion, "")
    path_preview = " -> ".join(str(n) for n in result["path"][:5])
    if len(result["path"]) > 5:
        path_preview += f" ... -> {result['path'][-1]}"

    print(f"  Algorithm     : {algo.upper()}")
    print(f"  Weather       : {weather} (Hour {hour:02d}:00)")
    print(f"  Congestion    : {color}{congestion}{RESET}")
    print(f"  Distance      : {result['total_distance_m']/1000:.2f} km")
    print(f"  ETA           : {result['eta_minutes']:.1f} min")
    print(f"  Waypoints     : {len(result['path'])} nodes")
    print(f"  Nodes expanded: {result['nodes_expanded']}")
    print(f"  Path preview  : {path_preview}")
    print()


def main():
    banner()
    parser = argparse.ArgumentParser(description="SmartRoute Demo")
    parser.add_argument("--nodes",  type=int, default=300,
                        help="Graph size (number of nodes)")
    parser.add_argument("--trials", type=int, default=3,
                        help="Number of route queries to demo")
    args = parser.parse_args()

    # ── Step 1: Build graph ──────────────────────────────────────────────────
    print(f"[1/4] Building synthetic {args.nodes}-node Bangalore road network...")
    nodes, adj = generate_demo_graph(args.nodes)
    print(f"      -> {len(nodes)} nodes, "
          f"{sum(len(e) for e in adj.values())} directed edges")

    # ── Step 2: Load ML model ─────────────────────────────────────────────────
    print("[2/4] Loading ML congestion model...")
    clf, features, label_inv = load_ml_model()
    if clf is not None:
        print("      -> Trained Random Forest classifier loaded")
    else:
        print("      -> Models not found; using rule-based fallback")
        print("         Run: python ml/train_models.py  to train models first")

    # ── Step 3: Apply ML weights ───────────────────────────────────────────────
    scenarios = [
        (8,  "Rain",   "Monday 8AM — Peak hour + Rain"),
        (14, "Clear",  "Afternoon 2PM — Clear weather"),
        (18, "Clouds", "Evening 6PM — Evening rush"),
    ]

    node_ids = list(nodes.keys())

    for trial_i in range(args.trials):
        scenario = scenarios[trial_i % len(scenarios)]
        hour, weather, label = scenario
        print(f"\n{'='*60}")
        print(f"  ROUTE QUERY #{trial_i+1}: {label}")
        print(f"{'='*60}")

        # Apply ML weights for this scenario
        print(f"[3/4] Applying ML-predicted congestion weights (hour={hour}, weather={weather})...")
        adj_ml = apply_ml_weights(adj, clf, features, label_inv, hour, weather)
        congestion = predict_congestion(clf, features, label_inv, hour, weather)
        print(f"      -> Predicted city-wide congestion: {congestion}")

        # Pick source/destination
        src, dst = random.choice(node_ids), random.choice(node_ids)
        while dst == src:
            dst = random.choice(node_ids)
        print(f"      -> Source: Node {src} ({nodes[src]['lat']:.4f}, {nodes[src]['lon']:.4f})")
        print(f"      -> Dest:   Node {dst} ({nodes[dst]['lat']:.4f}, {nodes[dst]['lon']:.4f})")

        # ── Step 4: Route with both algorithms ─────────────────────────────
        print("[4/4] Finding optimal route...\n")

        t0 = time.perf_counter()
        result_astar = astar_route(nodes, adj_ml, src, dst)
        t_astar = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        result_dijk  = dijkstra_route(nodes, adj_ml, src, dst)
        t_dijk = (time.perf_counter() - t0) * 1000

        print("  --- A* (Recommended) ---")
        print_result(result_astar, "A*", congestion, weather, hour)

        print("  --- Dijkstra ---")
        print_result(result_dijk, "Dijkstra", congestion, weather, hour)

        if result_astar and result_dijk:
            print(f"  [Comparison]")
            print(f"    A*       : {t_astar:.3f}ms, {result_astar['nodes_expanded']} nodes expanded")
            print(f"    Dijkstra : {t_dijk:.3f}ms, {result_dijk['nodes_expanded']} nodes expanded")
            reduction = (1 - result_astar["nodes_expanded"] /
                         max(result_dijk["nodes_expanded"], 1)) * 100
            print(f"    A* explored {reduction:.1f}% fewer nodes")
            same = abs(result_astar["total_time_s"] - result_dijk["total_time_s"]) < 1e-6
            print(f"    Same optimal path cost: {'YES' if same else 'NO (BUG!)'}")

    print(f"\n{'='*60}")
    print("  Demo complete! Start the full API server:")
    print("  uvicorn api.main:app --reload --port 8000")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
