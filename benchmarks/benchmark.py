"""
benchmark.py
──────────────────────────────────────────────────────────────────────────────
Benchmarks Dijkstra vs A* on random synthetic graphs of increasing sizes.
Outputs results/benchmark_results.json and prints a formatted table.

Usage:
    python benchmarks/benchmark.py
    python benchmarks/benchmark.py --sizes 100 500 1000 5000
"""

import argparse
import heapq
import json
import math
import os
import random
import time
from dataclasses import dataclass, asdict
from typing import Optional

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


# ── Pure-Python graph for benchmarking (no C++ dep needed) ───────────────────
@dataclass
class BenchNode:
    id: int
    lat: float
    lon: float


def generate_random_graph(n_nodes: int, avg_degree: int = 4, seed: int = 42):
    """Generate a random geographic graph with n_nodes nodes."""
    random.seed(seed)
    # Nodes spread across Bangalore-like bounding box
    nodes = {
        i: BenchNode(
            id=i,
            lat=12.85 + random.uniform(0, 0.25),
            lon=77.50 + random.uniform(0, 0.25)
        )
        for i in range(n_nodes)
    }

    adj = {i: [] for i in range(n_nodes)}
    n_edges = 0

    for i in range(n_nodes):
        # Connect to nearby nodes by distance
        others = random.sample(range(n_nodes), min(avg_degree * 3, n_nodes - 1))
        added = 0
        for j in others:
            if j == i:
                continue
            dist = haversine(nodes[i].lat, nodes[i].lon,
                             nodes[j].lat, nodes[j].lon)
            speed = random.uniform(20, 80)  # km/h
            time_w = dist / (speed * 1000 / 3600)
            adj[i].append((j, dist, time_w))
            n_edges += 1
            added += 1
            if added >= avg_degree:
                break

    return nodes, adj, n_edges


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Dijkstra ─────────────────────────────────────────────────────────────────
def dijkstra(nodes, adj, src, dst):
    dist = {src: 0.0}
    prev = {}
    pq = [(0.0, src)]
    nodes_expanded = 0

    while pq:
        cost, u = heapq.heappop(pq)
        nodes_expanded += 1
        if u == dst:
            path = _reconstruct(prev, src, dst)
            return cost, len(path), nodes_expanded
        if cost > dist.get(u, math.inf):
            continue
        for v, dist_m, time_w in adj.get(u, []):
            nc = dist[u] + time_w
            if nc < dist.get(v, math.inf):
                dist[v] = nc
                prev[v] = u
                heapq.heappush(pq, (nc, v))

    return math.inf, 0, nodes_expanded  # no path


# ── A* ───────────────────────────────────────────────────────────────────────
def astar(nodes, adj, src, dst):
    def h(u):
        n1, n2 = nodes[u], nodes[dst]
        return haversine(n1.lat, n1.lon, n2.lat, n2.lon) / 22.22  # time at 80km/h

    g = {src: 0.0}
    prev = {}
    pq = [(h(src), src)]
    nodes_expanded = 0

    while pq:
        f, u = heapq.heappop(pq)
        nodes_expanded += 1
        if u == dst:
            path = _reconstruct(prev, src, dst)
            return g[dst], len(path), nodes_expanded
        for v, dist_m, time_w in adj.get(u, []):
            tg = g[u] + time_w
            if tg < g.get(v, math.inf):
                g[v] = tg
                prev[v] = u
                heapq.heappush(pq, (tg + h(v), v))

    return math.inf, 0, nodes_expanded


def _reconstruct(prev, src, dst):
    path = []
    at = dst
    while at != src and at in prev:
        path.append(at)
        at = prev[at]
    path.append(src)
    return path


# ── Benchmark runner ──────────────────────────────────────────────────────────
def run_benchmark(n_nodes: int, n_trials: int = 20) -> dict:
    nodes, adj, n_edges = generate_random_graph(n_nodes)
    node_ids = list(nodes.keys())

    dijkstra_times = []
    astar_times    = []
    dijkstra_expanded = []
    astar_expanded    = []
    paths_match = True

    for trial in range(n_trials):
        src = random.choice(node_ids)
        dst = random.choice(node_ids)
        while dst == src:
            dst = random.choice(node_ids)

        # Dijkstra
        t0 = time.perf_counter()
        d_cost, d_len, d_exp = dijkstra(nodes, adj, src, dst)
        dijkstra_times.append((time.perf_counter() - t0) * 1000)
        dijkstra_expanded.append(d_exp)

        # A*
        t0 = time.perf_counter()
        a_cost, a_len, a_exp = astar(nodes, adj, src, dst)
        astar_times.append((time.perf_counter() - t0) * 1000)
        astar_expanded.append(a_exp)

        # Check both find same cost (within float tolerance)
        if d_cost != math.inf and a_cost != math.inf:
            if abs(d_cost - a_cost) > 1e-6:
                paths_match = False

    def avg(lst): return round(sum(lst) / len(lst), 4) if lst else 0
    def median(lst):
        s = sorted(lst)
        return round(s[len(s)//2], 4)

    speedup = avg(dijkstra_times) / avg(astar_times) if avg(astar_times) > 0 else 1.0
    node_reduction = (1 - avg(astar_expanded) / max(avg(dijkstra_expanded), 1)) * 100

    result = {
        "n_nodes": n_nodes,
        "n_edges": n_edges,
        "n_trials": n_trials,
        "dijkstra": {
            "avg_ms": avg(dijkstra_times),
            "median_ms": median(dijkstra_times),
            "avg_nodes_expanded": round(avg(dijkstra_expanded), 1)
        },
        "astar": {
            "avg_ms": avg(astar_times),
            "median_ms": median(astar_times),
            "avg_nodes_expanded": round(avg(astar_expanded), 1)
        },
        "astar_speedup_x": round(speedup, 2),
        "node_reduction_pct": round(node_reduction, 1),
        "optimal_paths_match": paths_match
    }
    return result


def print_table(results: list):
    print("\n" + "=" * 80)
    print("  SMARTROUTE BENCHMARK: Dijkstra vs A*")
    print("=" * 80)
    print(f"  {'Nodes':>7}  {'Edges':>7}  "
          f"{'Dijkstra(ms)':>14}  {'A*(ms)':>10}  "
          f"{'Speedup':>9}  {'Node Reduction':>15}  {'Match':>6}")
    print("-" * 80)
    for r in results:
        print(f"  {r['n_nodes']:>7,}  {r['n_edges']:>7,}  "
              f"  {r['dijkstra']['avg_ms']:>10.3f}ms  "
              f"  {r['astar']['avg_ms']:>8.3f}ms  "
              f"  {r['astar_speedup_x']:>6.2f}x  "
              f"  {r['node_reduction_pct']:>11.1f}%  "
              f"  {'YES' if r['optimal_paths_match'] else 'NO':>6}")
    print("=" * 80)
    print("\n  Key insight: A* explores fewer nodes by using Haversine heuristic")
    print("  → Optimal path guaranteed when heuristic is admissible (never overestimates)\n")


def main():
    parser = argparse.ArgumentParser(description="Benchmark Dijkstra vs A*")
    parser.add_argument("--sizes", nargs="+", type=int,
                        default=[100, 500, 1000, 2000, 5000])
    parser.add_argument("--trials", type=int, default=20)
    args = parser.parse_args()

    os.makedirs(RESULTS_DIR, exist_ok=True)
    results = []

    for n in args.sizes:
        print(f"  Benchmarking n={n:,} nodes ({args.trials} trials)...", end=" ", flush=True)
        r = run_benchmark(n, args.trials)
        results.append(r)
        print(f"Dijkstra={r['dijkstra']['avg_ms']:.2f}ms, "
              f"A*={r['astar']['avg_ms']:.2f}ms, "
              f"Speedup={r['astar_speedup_x']:.2f}x")

    print_table(results)

    out_path = os.path.join(RESULTS_DIR, "benchmark_results.json")
    with open(out_path, "w") as f:
        json.dump({"benchmarks": results}, f, indent=2)
    print(f"  Results saved -> {out_path}")


if __name__ == "__main__":
    main()
