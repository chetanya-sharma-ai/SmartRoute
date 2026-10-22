# SmartRoute — Emergency-Aware Route Optimization · Hackathon Demo

## Judge Q&A and 5-minute demo walkthrough

---

## The problem

Normal navigation finds the shortest route. During an emergency that route might be
**blocked** (road closure), **flooded** (flash flood), **inaccessible** (restricted access),
or too slow due to **congestion**. SmartRoute demonstrates how a routing engine can account
for all four conditions at the same time.

---

## 5-minute walkthrough (verified steps)

### Before you start
```
# Windows
.venv\Scripts\python.exe -m uvicorn api.main:app --port 8000
# Then open: http://localhost:8000/app
```

### Step 1 — Normal conditions (baseline)
1. Click the **🟢 Normal conditions** preset. Source and destination are pre-filled.
2. Click **Find Safe Route**.
3. **Expected:** Route appears — ~17 waypoints, ~0.95 km, ~4.3 min ETA.
4. Result panel shows **"Normal conditions"**, 0 affected segments.

### Step 2 — Road closure (blocked road)
1. Click **🔴 Road closure** preset.
2. Click **Find Safe Route**.
3. **Expected:** Longer route (~1.47 km, ~6.6 min). The route avoids 100 Feet Road.
4. Result panel: condition = **blocked**, 15 affected segments, route took detour.

### Step 3 — Flash flood (flooded road unavailable)
1. Click **🌊 Flash flood** preset.
2. Click **Find Safe Route**.
3. **Expected:** Route avoids Swamy Vivekananda Road; 10 affected segments.

### Step 4 — Emergency access restriction
1. Click **🚧 Access restriction** preset (emergency profile pre-selected).
2. Click **Find Safe Route**.
3. **Expected:** Route avoids 11th Main Road; 22 affected segments.

### Step 5 — Congestion spike (cost penalty, not blocking)
1. Click **🟠 Congestion spike** preset (emergency profile).
2. Click **Find Safe Route**.
3. **Expected:** Route prefers a less-congested alternative; 34 penalised segments.

### Optional — Traffic heatmap
- Enable **🔥 Traffic Heatmap** toggle.
- Change the hour slider or weather. The heatmap updates with simulated predictions.
- All popups say "(simulated)" — there is no live feed.

---

## Honest judge Q&A

### Q: What problem does this solve?
Normal shortest-path routing ignores road availability. This prototype shows how a graph
router can exclude blocked, flooded, or inaccessible edges (weight = −1, skipped by the
pathfinding algorithm), and prefer lower-cost alternatives when congestion is modelled.

### Q: Where does the traffic/flood/incident data come from?
**There is no live data.** The road graph is a bundled 322-node/838-edge Indiranagar
snapshot exported via OSMnx (OpenStreetMap). Congestion is predicted from a Random Forest
classifier trained on ~108 k generated synthetic records. Road closures, flooding, and
access restrictions are explicitly labelled demo scenarios defined in
`data/demo_scenarios.json`. Every API response includes `"data_source": "simulated demo
scenario; no live incident feed"`. The frontend shows a persistent **⚠️ SIMULATED DATA**
banner on every screen.

### Q: How are blocked roads handled technically?
Blocked edges get `time_weight = -1.0` in the edge-weight JSON. The C++ engine (and
Python fallback) skip any edge with `time_weight ≤ 0` during graph traversal. The
routing algorithm never visits, relaxes, or includes such an edge in any returned path.
This is verified by the `test_blocked_road_never_appears_in_result_path` test.

### Q: What if there is no alternate route?
The engine returns `{"error": "No path found…"}`. The API converts that to HTTP 404
with a `tip` field: "The selected scenario may have blocked all paths between these nodes.
Try a different node pair or scenario." The frontend displays this message in the status
bar. The `test_no_route_when_all_edges_blocked` test verifies this.

### Q: Why is the emergency route safer?
It is not guaranteed "safer" — it is *differently weighted*. The emergency profile adds a
25% cost multiplier to edges the ML model labels "High congestion". This makes the
path-finder prefer those edges only when a lower-cost alternative exists. It does not
control traffic signals, grant right-of-way, or guarantee emergency access. The profile is
a routing-cost demonstration documented in `api/route_scenarios.py` and in the UI tip text.

### Q: What if the incident report is stale or wrong?
The system has no incident expiry or confidence scoring. A stale or incorrect report
would cause the router to block a road that is actually passable, or leave an unpassable
road open. Production would require timestamps, confidence scores, and operator
confirmation before acting on a report. The bundled scenarios are never stale because
they are static demo definitions, not live data.

### Q: How does the ML model work?
A Random Forest classifier predicts Low/Medium/High congestion from:
`hour`, `day_of_week`, `is_weekend`, `month`, `weather`, `road_length_m`.
It was trained on synthetic records (rule-based ground truth). **The reported 88.5%
accuracy is on the synthetic holdout, not real traffic.** When the model is not loaded,
a documented rule-based fallback applies the same three levels using peak-hour and
weather rules. The congestion level becomes a travel-time multiplier (Low=1×, Medium=1.6×,
High=3×) fed into the C++ pathfinder.

### Q: How large is the map?
322 nodes, 838 directed edges, Indiranagar neighbourhood only (~2.5 km²). This is
sufficient for a demo showing route changes across 3–5 road segments, not for city-wide
routing. The graph summary is available at `/graph/summary`.

### Q: What is the pathfinding algorithm?
A* (default) and Dijkstra (selectable), both implemented in C++17 with an STL priority
queue. A* uses a Haversine distance lower bound as its admissible heuristic. Both use
the same ML-adjusted and incident-adjusted edge costs. The C++ binary is called via
subprocess; a pure-Python fallback runs if the binary is not compiled.

### Q: How does the system scale to a real city?
The current architecture uses a single in-process graph loaded at startup. A city-scale
graph (millions of nodes) would require: tile-based graph partitioning, contraction
hierarchies or similar preprocessing, a proper graph database (e.g., Neo4j, PostGIS +
pgRouting), and async worker pools for ML inference. None of that is implemented here.

### Q: How would live feeds be added?
`api/route_scenarios.py::create_route_weights` is the adapter boundary. Replace
`load_scenarios()` with a call to a live incident API. The rest of the pipeline —
weight merging, engine call, response format — stays the same. A real provider would
need: authenticated REST/WebSocket feed, incident schema with coordinates + type + expiry,
confidence threshold before marking an edge, and a cache with TTL.

### Q: Privacy?
The bundled prototype collects no user data. A production system routing real users would
need: no logging of origin-destination pairs, on-device route computation where feasible,
data minimisation for any server-side routing, and compliance with applicable regulations.

---

## API examples (verified against the bundled graph)

```
# Normal
GET /route?src=253179982&dst=736207607&hour=8&weather=Clear&algo=astar&scenario=normal&priority=standard

# Road closure → longer alternate route (~24 nodes vs 17)
GET /route?src=253179982&dst=736207607&hour=8&weather=Rain&algo=astar&scenario=road_closure&priority=standard

# Flash flood → avoids Swamy Vivekananda Road
GET /route?src=253179982&dst=12692472176&hour=8&weather=Rain&algo=astar&scenario=flash_flood&priority=standard

# Access restriction + emergency profile
GET /route?src=253179991&dst=4202336813&hour=8&weather=Clear&algo=astar&scenario=access_restriction&priority=emergency

# Congestion spike + emergency profile
GET /route?src=253179982&dst=1563306444&hour=8&weather=Clear&algo=astar&scenario=congestion_spike&priority=emergency

# Validation — these return 422
GET /route?src=253179982&dst=253179982        # src == dst
GET /route?src=253179982&dst=736207607&scenario=live   # unknown scenario
```

Interactive docs: **http://localhost:8000/docs**
