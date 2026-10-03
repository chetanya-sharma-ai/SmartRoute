# SmartRoute — DSA & Algorithm Reference

> This document explains every data structure and algorithm implemented in the C++ engine.
> A recruiter or interviewer should be able to ask you about any of these — you should know them cold.

---

## 📐 Graph Representation — Adjacency List

### Why Adjacency List?

The Bangalore road network has ~50,000 nodes but is **sparse** — each intersection connects to only 2–5 roads on average. An adjacency **matrix** would waste `O(V²)` = 2.5 billion cells. An adjacency **list** uses only `O(V + E)`.

```
Node 1 → [Edge(to=2, w=120s), Edge(to=5, w=80s)]
Node 2 → [Edge(to=3, w=95s), Edge(to=1, w=120s)]
Node 3 → [Edge(to=4, w=200s)]
...
```

### Implementation

```cpp
// core/Graph.h
struct Edge {
    int to;
    double weight;        // distance (meters)
    double time_weight;   // travel time (seconds) — ML-adjusted
    std::string road_name;
};

std::unordered_map<int, std::vector<Edge>> adj_;
```

**Space complexity:** O(V + E) where V = nodes, E = edges<br>
**Access time:** O(degree(v)) per node — average O(1) for sparse graphs

---

## ⚡ Algorithm 1: Dijkstra's Shortest Path

### Core Idea
Greedy algorithm. Always expand the **cheapest unvisited node** first using a **min-heap priority queue**.

### Pseudocode
```
dist[src] = 0
PQ = MinHeap{(0, src)}

while PQ not empty:
    (cost, u) = PQ.pop_min()
    if u == dst: return path

    for each edge (u → v, weight):
        if dist[u] + weight < dist[v]:
            dist[v] = dist[u] + weight
            prev[v] = u
            PQ.push((dist[v], v))
```

### Why STL Priority Queue?
```cpp
using PQEntry = pair<double, int>;  // {cost, node}
priority_queue<PQEntry, vector<PQEntry>, greater<PQEntry>> pq;
// greater<> gives MIN-heap behavior (default is max-heap)
```

### Complexity
| Metric | With Binary Heap |
|--------|-----------------|
| Time   | O((V + E) log V) |
| Space  | O(V) |

### When to use
- When you need the **optimal path guaranteed**
- When there's no good heuristic available
- Handles all positive edge weights

---

## 🎯 Algorithm 2: A* (A-Star) Pathfinding

### Core Idea
A* improves on Dijkstra by adding a **heuristic function** h(n) — an estimate of the remaining cost to the goal. This guides the search toward the destination.

**f(n) = g(n) + h(n)**
- `g(n)` = actual cost from source to node n
- `h(n)` = estimated cost from n to destination (heuristic)
- `f(n)` = total estimated cost through n

### Our Heuristic: Haversine Distance

We use the **Haversine formula** to compute the great-circle distance between two lat/lon points — a perfect admissible heuristic for road networks.

```cpp
double Graph::heuristic(int from, int to) const {
    const auto& a = nodes_.at(from);
    const auto& b = nodes_.at(to);
    // Convert haversine distance → estimated time at free-flow speed
    return haversine(a.lat, a.lon, b.lat, b.lon) / 22.22; // 80 km/h
}
```

**Haversine formula:**
```
a = sin²(Δlat/2) + cos(lat1)·cos(lat2)·sin²(Δlon/2)
distance = 2R·atan2(√a, √(1−a))    where R = 6,371,000 m
```

### Why Haversine is Admissible
- It computes the **straight-line** (as-the-crow-flies) distance
- No road path can be shorter than the straight-line distance
- Therefore h(n) **never overestimates** → A* finds the optimal path

### A* vs Dijkstra on Real Maps

| Scenario | Dijkstra | A* |
|----------|----------|-----|
| Nodes explored | ~100% of reachable graph | ~15-30% |
| Time (small graph 1k nodes) | ~2ms | ~0.3ms |
| Time (large graph 50k nodes) | ~150ms | ~20ms |
| Optimal path guaranteed? | ✅ | ✅ (with admissible heuristic) |

### Benchmarks (our implementation)

See `benchmarks/results.json` for detailed timing data.

---

## 🏗 Data Structures Used

### 1. Min-Heap Priority Queue
```cpp
priority_queue<pair<double,int>, vector<pair<double,int>>, greater<>> pq;
```
- **Insert:** O(log n)
- **Extract-min:** O(log n)
- Used by: Dijkstra, A*

### 2. Hash Map (unordered_map)
```cpp
unordered_map<int, vector<Edge>> adj_;   // adjacency list
unordered_map<int, double> dist;          // distances
unordered_map<int, int> prev;             // path predecessor
```
- **Average lookup:** O(1)
- **Worst case:** O(n) (rare, due to hash collisions)

### 3. Path Reconstruction
After the search completes, we backtrack from `dst` to `src` using the `prev` map:

```cpp
vector<int> path;
for (int at = dst; at != src; at = prev.at(at))
    path.push_back(at);
path.push_back(src);
reverse(path.begin(), path.end());  // O(n)
```

---

## 🧮 Complexity Summary

| Algorithm | Time | Space | Optimal? | Complete? |
|-----------|------|-------|----------|-----------|
| Dijkstra  | O((V+E)logV) | O(V) | ✅ | ✅ |
| A*        | O(b^d) best case | O(b^d) | ✅* | ✅ |
| Bellman-Ford | O(VE) | O(V) | ✅ | ✅ |

*A* is optimal when heuristic is admissible (never overestimates)

---

## 🔄 ML Integration: Dynamic Edge Weights

The key innovation of SmartRoute is that edge weights are **not static** — they are updated by ML predictions before each routing query.

```
1. Input: hour=8, weather=Rain, day=Monday
       ↓
2. Random Forest predicts congestion for each edge:
   Edge(A→B): High  → multiply time_weight × 3.0
   Edge(B→C): Low   → multiply time_weight × 1.0
   Edge(C→D): Medium → multiply time_weight × 1.6
       ↓
3. Updated weights written to JSON
       ↓
4. C++ engine loads updated weights via Graph::loadWeightsFromJSON()
       ↓
5. Dijkstra/A* runs with ML-adjusted costs → finds fastest real-world path
```

This is what separates SmartRoute from a basic pathfinding demo — the routing is **contextually aware** of real traffic conditions.
