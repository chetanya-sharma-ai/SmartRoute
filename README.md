<p align="center">
  <h1 align="center">🚦 SmartRoute</h1>
  <h3 align="center">Emergency-Aware Route Optimization · Indiranagar, Bangalore</h3>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/C%2B%2B-17-orange?logo=cplusplus&logoColor=white" alt="C++">
  <img src="https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/RandomForest-88.5%25_synthetic-green" alt="RandomForest">
  <img src="https://img.shields.io/badge/Leaflet.js-Map-4CAF50?logo=leaflet" alt="Leaflet">
  <img src="https://img.shields.io/badge/Tests-33_passed-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/Docker-Multi--stage-2496ED?logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/Data-Simulated-yellow" alt="Simulated">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="MIT">
</p>

---

> **SmartRoute** is an intelligent navigation engine designed for emergency response and disaster resilience. While standard navigation systems focus solely on static shortest paths, SmartRoute dynamically accounts for **road closures, flash floods, vehicle access restrictions, and sudden congestion spikes**.
>
> It combines a high-performance **C++17 graph traversal engine** (A* and Dijkstra), a **scikit-learn Random Forest congestion classifier**, and a modern **Leaflet.js interactive map** over real-world road geometry from Indiranagar, Bangalore (322 nodes).
>
> **⚠️ Simulation Notice:** All incident, traffic, and weather data is simulated for reproducible hackathon evaluation. No live municipal feeds are connected. Every API response and UI view explicitly flags this simulated context.

---

## 📑 Table of Contents
- [✨ Key Capabilities](#-key-capabilities)
- [🛠 Detailed Tech Stack & Technical Justifications](#-detailed-tech-stack--technical-justifications)
- [🏗 Architecture & Data Flow](#-architecture--data-flow)
- [💻 Step-by-Step: How to Run Locally](#-step-by-step-how-to-run-locally)
- [🌐 Step-by-Step: How to Deploy Live](#-step-by-step-how-to-deploy-live)
- [🎮 5-Minute Demo Walkthrough](#-5-minute-demo-walkthrough)
- [🧪 Test Suite & Invariants](#-test-suite--invariants)
- [📡 REST API Reference](#-rest-api-reference)
- [🗣 Judge Q&A Defense Guide](#-judge-qa-defense-guide)
- [⚠️ Limitations & Production Roadmap](#-limitations--production-roadmap)

---

## ✨ Key Capabilities

| Capability | Technical Mechanism | Emergency Impact |
|---|---|---|
| 🔴 **Blocked Roads** | Marked edges receive `time_weight = -1`; strictly pruned before graph traversal | Guarantees emergency vehicles never encounter closed construction or disaster zones |
| 🌊 **Flooded Corridors** | Dynamically marks submerged streets impassable based on weather & flood warnings | Prevents vehicle stall in low-lying waterlogged roads |
| 🚧 **Access Restrictions** | Excludes narrow or vehicle-incompatible road classes | Ensures heavy emergency vehicles stick to cleared, wide arterials |
| 🟠 **Congestion Avoidance** | Applies a dynamic cost penalty (2.5×–3.5× multiplier) to spiked corridors | A* automatically redirects around bottlenecks via clearer side streets |
| 🚑 **Emergency Priority Mode** | Applies additional 2.0× penalty to High-congestion links; prioritizes flow stability | Avoids gridlock even if the alternate route is slightly longer in meters |
| 🤖 **Predictive ML Congestion** | Random Forest predicts Low/Medium/High traffic from hour, weather, and road length | Anticipates bottlenecks before vehicles arrive at intersections |
| 🔥 **Dynamic Traffic Heatmap** | Computes network-wide edge delays and visualizes via GeoJSON polylines | Real-time situational awareness for dispatchers |

---

## 🛠 Detailed Tech Stack & Technical Justifications

This project purposefully uses a hybrid architecture designed to balance **raw algorithmic performance**, **machine learning intelligence**, and **developer velocity**. Here is how to explain every technology used:

### 1. Core Pathfinding: C++17 (with CMake)
* **What it does:** Implements Dijkstra's algorithm with priority queues (`std::priority_queue`) and the A* search algorithm using the admissible Haversine distance heuristic.
* **Why it was chosen:**
  * **Zero Overhead & Speed:** Microsecond-level graph traversal over complex road topologies.
  * **Memory Efficiency:** Contiguous cache-friendly adjacency lists.
  * **Deterministic Execution:** No garbage-collection pauses during time-critical emergency route calculation.
* **Judge Talking Point:** *"While Python is ideal for AI and web APIs, pathfinding across city graphs under high request volumes belongs in native C++. We compiled our pathfinder into an independent C++17 engine that receives dynamic edge weights and returns the optimal route via structured JSON."*

### 2. Backend Framework: Python 3.11 + FastAPI + Uvicorn
* **What it does:** Orchestrates the API layer, input validation, scenario filtering, ML model inference, and coordinates subprocess calls to the C++ engine (with an automatic Python fallback).
* **Why it was chosen:**
  * **Asynchronous Concurrency:** Built on ASGI (`uvicorn`) for high-throughput, non-blocking I/O.
  * **Strict Data Validation:** Utilizes Pydantic schemas to validate query parameters (e.g., rejecting `src == dst`, unknown scenarios, or out-of-range hours with HTTP 422).
  * **Automated Documentation:** Instant OpenAPI interactive documentation available at `/docs`.
* **Judge Talking Point:** *"FastAPI gives us strict schema safety and asynchronous throughput. It acts as the intelligent orchestration layer—transforming environmental signals and ML predictions into dynamic edge weights before dispatching to the C++ core."*

### 3. Machine Learning: Scikit-learn (Random Forest) + XGBoost
* **What it does:** Classifies traffic congestion levels (`Low`, `Medium`, `High`) based on contextual features: hour of the day, weather conditions, day of week, temperature, and segment length.
* **Why it was chosen:**
  * **Ensemble Robustness:** Random Forest captures non-linear feature interactions (e.g., rush hour + heavy rain compounding into gridlock) without overfitting.
  * **Graceful Degradation:** The system includes a deterministic rule-based fallback if serialized model artifacts (`.pkl`) are missing or unreadable.
* **Judge Talking Point:** *"Instead of assuming static travel speeds, we predict congestion dynamically. Our Random Forest classifier converts time and weather into speed multipliers (1.0× to 3.0×), accurately reflecting urban slowdowns."*

### 4. Geospatial Data: OSMnx & OpenStreetMap
* **What it does:** Extracts real-world road networks, node coordinates (latitude/longitude), one-way constraints, and road classifications from OpenStreetMap for Indiranagar, Bangalore.
* **Why it was chosen:**
  * **Authentic Topography:** Avoids synthetic grid graphs by using real Bengaluru streets (100 Feet Road, CMH Road, 12th Main).
  * **Standard Geodetic Distance:** Enables precise Haversine distance calculations in meters.
* **Judge Talking Point:** *"We grounded our prototype in authentic urban topography. OSMnx allowed us to extract the real street geometry of Indiranagar into a 322-node directional graph."*

### 5. Frontend: Vanilla HTML5 / Modern CSS3 / ES6 JavaScript + Leaflet.js
* **What it does:** Delivers an interactive, dark-themed command center featuring route visualization, scenario preset toggles, traffic heatmaps, and live metrics.
* **Why it was chosen:**
  * **Zero Build Step:** Runs instantly without requiring Node.js, npm installs, or webpack bundles.
  * **Lightweight & Fast:** Sub-second browser rendering with native responsive CSS and glassmorphism styling.
  * **Mobile-Friendly Mapping:** Leaflet.js provides smooth pan/zoom tile rendering powered by OpenStreetMap.
* **Judge Talking Point:** *"We chose zero-dependency Vanilla JS and Leaflet to ensure instant load times and zero client-side build complexity. It provides an immediate, responsive UI that works across desktop and mobile browsers."*

### 6. Testing & Quality Assurance: pytest + pytest-asyncio
* **What it does:** Provides 33 automated tests covering API validation, routing invariants (proving blocked edges never appear in returned paths), disconnected graph handling, and ML prediction consistency.
* **Judge Talking Point:** *"Reliability in an emergency system is non-negotiable. We built a 33-test automated regression suite that proves safety invariants—specifically that blocked roads are never traversed under any scenario."*

### 7. Containerization: Docker (Multi-Stage Build)
* **What it does:** Stage 1 uses `ubuntu:22.04` with CMake and `g++` to compile the C++ binary. Stage 2 copies the compiled binary into a slim `python:3.11-slim` runtime environment.
* **Judge Talking Point:** *"Our multi-stage Dockerfile ensures complete reproducibility across any Linux, macOS, or Windows environment without requiring host C++ compilers."*

---

## 🏗 Architecture & Data Flow

```
                     ┌────────────────────────────────────────┐
                     │          Leaflet.js Frontend           │
                     │  Interactive Map · Presets · Heatmap   │
                     └───────────────────┬────────────────────┘
                                         │ HTTP REST
                     ┌───────────────────▼────────────────────┐
                     │            FastAPI Backend             │
                     │   /route  /congestion  /heatmap /health │
                     └─────────┬───────────────────┬──────────┘
                               │                   │
              ┌────────────────▼───┐       ┌───────▼────────────────┐
              │  C++ Graph Engine  │       │   Python ML Pipeline   │
              │  A* / Dijkstra     │◄──────┤   Random Forest Clf    │
              │  (Subprocess CLI)  │       │   Rule-based Fallback  │
              │  Python Fallback   │       └────────────────────────┘
              └────────────────────┘                    │
                                            ┌───────────▼───────────┐
                                            │ Real OSMnx Graph Data │
                                            │ graph_data.json (322n)│
                                            │ demo_scenarios.json   │
                                            └───────────────────────┘
```

### Request Lifecycle (`/route`)
1. **User Interaction:** User picks origin, destination, scenario (e.g., `flash_flood`), and priority (`emergency`).
2. **Input Validation:** FastAPI checks node existence, ensures `src != dst`, and verifies scenario validity.
3. **ML Congestion Prediction:** Model evaluates contextual delay for each graph edge.
4. **Scenario Edge Pruning:** `route_scenarios.py` identifies affected street segments (e.g., flooded roads) and sets their traversal weight to `-1` (impassable).
5. **C++ Pathfinding:** The C++ binary executes A* search, completely skipping edges where `weight <= 0`.
6. **Transparent Response:** API responds with geo-coordinates, distance, ETA, and incident context explicitly marked as `simulated demo scenario`.
7. **Map Rendering:** Frontend draws the safe path in bright blue (or displays clear warnings if no route exists).

---

## 💻 Step-by-Step: How to Run Locally

### Prerequisites
* **Python:** 3.10, 3.11, or 3.12 installed.
* **Git:** Installed on your system.
* *(Optional)* **CMake & C++ Compiler:** (MSVC on Windows, GCC/Clang on Linux/macOS). If not present, the system automatically uses the verified Python fallback.

---

### Step 1: Clone the Repository
```bash
git clone https://github.com/chetanya-sharma-ai/SmartRoute.git
cd SmartRoute
```

### Step 2: Set Up Python Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**On macOS / Linux (Bash):**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: (Optional) Build the C++ Engine
> *Note: Windows precompiled binary is included at `api/smartroute_engine.exe`. If you are on Linux or macOS, you can build it in 2 commands:*

```bash
cd core
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build . --config Release
cd ../..
```
*If you skip this step, SmartRoute automatically falls back to its built-in Python routing engine with zero configuration.*

### Step 5: Start the FastAPI Server
```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```
You should see:
```text
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

### Step 6: Access the Application
* **Interactive Frontend:** Open [http://localhost:8000/app](http://localhost:8000/app) in any browser.
* **Interactive API Docs (Swagger):** Open [http://localhost:8000/docs](http://localhost:8000/docs).
* **System Health Check:** Open [http://localhost:8000/health](http://localhost:8000/health).

### Step 7: Run the Test Suite
In a separate terminal (with `.venv` active):
```bash
pytest tests/ -v
```
Expected output: **`33 passed in ~7s`** (100% pass rate).

### Step 8: Run Algorithmic Benchmarks
```bash
python benchmarks/benchmark.py
```
Outputs comparative exploration node counts and execution time between Dijkstra and A*.

---

## 🌐 Step-by-Step: How to Deploy Live

You can deploy SmartRoute live to the web for free in under 5 minutes using any of the following methods:

---

### Method A: Deploy on Render.com (Recommended Free Cloud Hosting)

[Render](https://render.com) is the easiest platform to deploy FastAPI + Docker apps with zero credit card required.

1. **Push your code to GitHub:**
   Ensure your latest code is pushed to your GitHub repository.
2. **Sign in to Render:**
   Go to [dashboard.render.com](https://dashboard.render.com/) and link your GitHub account.
3. **Create a New Web Service:**
   * Click **New +** → **Web Service**.
   * Select your `SmartRoute` GitHub repository.
4. **Configure Settings:**
   * **Name:** `smartroute-emergency` (or your choice).
   * **Region:** Singapore / Frankfurt / Oregon (choose closest).
   * **Language / Environment:** Select **Docker**.
     *(Render will automatically detect `Dockerfile` and run the multi-stage build).*
   * **Branch:** `main`
   * **Instance Type:** **Free** ($0/month).
5. **Environment Variables:**
   * Add key: `PORT`, value: `8000`
6. **Health Check Path:**
   * Set health check path to `/health`.
7. **Deploy:**
   * Click **Deploy Web Service**.
   * Once built (~2 minutes), your app is live at:
     **`https://smartroute-emergency.onrender.com/app`**

---

### Method B: Deploy on Railway.app

1. Go to [railway.app](https://railway.app/) and login with GitHub.
2. Click **New Project** → **Deploy from GitHub repo**.
3. Select `SmartRoute`.
4. Railway automatically detects the `Dockerfile` and provisions the container.
5. In **Settings** → **Networking**, click **Generate Domain**.
6. Access your live app at `https://<your-domain>.up.railway.app/app`.

---

### Method C: Run Live via Docker (Local or Cloud VPS)

If you have Docker Desktop or an AWS EC2 / DigitalOcean Ubuntu droplet:

```bash
# 1. Build and run in background
docker compose up --build -d

# 2. Check logs
docker compose logs -f

# 3. Access locally or via your server IP:
# Frontend: http://<SERVER_IP>:8000/app
# API Docs: http://<SERVER_IP>:8000/docs
```

To stop:
```bash
docker compose down
```

---

## 🎮 5-Minute Demo Walkthrough

Follow this sequence during your hackathon presentation:

```
Step 1: Open http://localhost:8000/app
        Show the prominent "SIMULATED DATA · For Demonstration Only" top banner.
        Point out the clean Indiranagar, Bangalore map loaded via Leaflet.js.

Step 2: Click "🟢 Normal conditions" preset → Click "Find Safe Route"
        → Baseline path: ~0.95 km, ~4.3 min ETA across 17 nodes.
        → Explain: "Under normal conditions, A* finds the direct arterial route along 100 Feet Road."

Step 3: Click "🔴 Road closure" preset → Click "Find Safe Route"
        → Rerouted path: ~1.47 km, ~6.6 min ETA across 24 nodes.
        → Explain: "100 Feet Road is marked closed. SmartRoute completely pruned those segments.
                    The C++ engine traversed side avenues, guaranteeing the blocked road is never entered."

Step 4: Click "🌊 Flash flood" preset → Click "Find Safe Route"
        → Path shifts north/south, avoiding flooded low-lying corridors on Swamy Vivekananda Road.
        → Incident panel clearly displays: Condition: Flooded, Affected Segments: 16.

Step 5: Click "🟠 Congestion spike" preset → Click "Find Safe Route"
        → Notice how the route diverts around the 80 Feet Road arterial bottleneck.
        → Explain: "Rather than forcing drivers through a 3.5× delay, the router takes a slightly longer
                    geographic distance that saves significant travel time."

Step 6: Toggle "🔥 Traffic Heatmap" checkbox & drag the Hour Slider
        → The whole city grid updates color codes (Green = Low, Yellow = Medium, Red = High).
        → Demonstrates 24-hour predictive ML capability.
```

---

## 🧪 Test Suite & Invariants

The project includes **33 automated tests** verified with `pytest`:

```text
======================== 33 passed in 6.97s ========================
```

| Category | Verified Behavior | Test Count |
|---|---|:---:|
| **API Parameter Validation** | Rejects missing inputs, validates types, enforces `src != dst` (422) | 5 |
| **Path Failure Handling** | Returns 404 with actionable recovery tips when all corridors are blocked | 1 |
| **Endpoint Smoke Tests** | Verifies `/health`, `/congestion`, `/heatmap`, `/simulate`, `/graph/summary` | 5 |
| **ML Inference Correctness** | Validates Random Forest output labels, 24h simulation, and nearest node | 6 |
| **Hazard Road Exclusion** | Proves blocked, flooded, and restricted roads are completely bypassed | 3 |
| **Safety Invariant** | Asserts that 0% of blocked edges ever appear in the returned path | 1 |
| **Topology Resilience** | Disconnected graph detection, invalid node ID handling, malformed edge skipping | 3 |
| **Emergency Priority Tuning**| Proves high-congestion edge costs double under emergency vehicle profile | 2 |
| **Congestion Routing** | Proves pathfinder picks alternates when named roads suffer traffic spikes | 2 |
| **Data Attribution** | Verifies every response includes simulated data disclaimer | 1 |

Run tests anytime with:
```bash
pytest tests/ -v
```

---

## 📡 REST API Reference

### Key Endpoints

#### 1. Route Optimization
```http
GET /route?src={node_id}&dst={node_id}&hour={0-23}&weather={Clear|Rain|Fog}&algo={astar|dijkstra}&scenario={scenario}&priority={standard|emergency}
```
**Example Response:**
```json
{
  "algorithm": "astar",
  "src": 253179982,
  "dst": 736207607,
  "total_distance_m": 1466.2,
  "total_time_s": 395.87,
  "eta_minutes": 6.6,
  "num_nodes": 24,
  "path": [
    {"id": 253179982, "lat": 12.9812, "lon": 77.6460, "name": ""},
    {"id": 10182013933, "lat": 12.9812, "lon": 77.6452, "name": ""}
  ],
  "congestion_context": {
    "congestion_level": "High",
    "multiplier": 3.0
  },
  "incident_context": {
    "scenario": "road_closure",
    "label": "Simulated road closure",
    "condition": "blocked",
    "affected_segments": 15,
    "data_source": "simulated demo scenario; no live incident feed"
  }
}
```

#### 2. Single Edge Congestion Prediction
```http
GET /congestion?from_node=253179982&to_node=736207607&hour=8&weather=Rain
```

#### 3. Network Heatmap
```http
GET /heatmap?hour=18&weather=Clear&day=0
```

#### 4. Nearest Node Finder
```http
GET /nodes/nearest?lat=12.9784&lon=77.6408
```

---

## 🗣 Judge Q&A Defense Guide

Be prepared to answer these questions with confidence:

#### Q1: "Why did you use C++ instead of doing everything in Python?"
> **Answer:** *"In emergency dispatch and autonomous fleet routing, pathfinding latency across large road networks is critical. Python's dynamic typing and GIL introduce variance. We chose C++17 with strict STL priority queues and A* heuristics for microsecond traversal speed, while using Python and FastAPI for what they do best: API orchestration and ML inference."*

#### Q2: "Is this real-time Google Maps or live traffic data?"
> **Answer:** *"No, and we are completely transparent about that. All traffic conditions, flood alerts, and closures are simulated. Connecting live municipal APIs requires government agreements and data cleaning beyond a hackathon scope. Instead, we built a fully verifiable simulation engine that proves how an emergency routing platform handles dynamic disruptions when those feeds are integrated."*

#### Q3: "What happens if every road leading to the hospital is blocked?"
> **Answer:** *"SmartRoute enforces an absolute safety guarantee: it will never route a vehicle onto a closed or submerged road. If no safe route exists, the API returns HTTP 404 with an actionable diagnostic tip explaining that all corridors are blocked, alerting dispatchers to deploy alternative evacuation methods rather than leading drivers into danger."*

#### Q4: "How does the Emergency Priority Profile differ from Standard routing?"
> **Answer:** *"Standard navigation balances distance and average speed. In Emergency mode, our algorithm doubles the penalty on roads with predicted High congestion. Even if a side street is geographically longer, an ambulance avoids congested bottlenecks where getting stuck behind stopped traffic is catastrophic."*

#### Q5: "How does this scale to a full metropolitan city like Bangalore?"
> **Answer:** *"Our prototype runs on a 322-node network of Indiranagar. For city-scale deployment (100,000+ nodes), we would implement Contraction Hierarchies (CH) or Customisable Contraction Hierarchies (CCH) in C++, which precompute shortcuts to enable sub-millisecond queries across entire countries."*

---

## ⚠️ Limitations & Production Roadmap

### Current Scope & Assumptions
* **Coverage:** 322 nodes covering Indiranagar, Bangalore.
* **Incidents:** Predefined scenario profiles applied to named road segments.
* **ML Model:** Trained on synthetic historical data; captures realistic traffic patterns but is not calibrated against on-the-ground loop detectors.
* **Signals:** Does not grant traffic signal priority or interface with traffic light hardware.

### Production Next Steps
1. **Live Feed Ingestion:** Connect GTFS-RT, TomTom Traffic API, and Bengaluru Traffic Police alerts.
2. **Contraction Hierarchies:** Precompute multi-level graph shortcuts in C++ for city-wide routing.
3. **Turn Restrictions:** Incorporate junction turn costs and U-turn penalties into the graph model.
4. **Driver Re-routing:** WebSocket push notifications to re-route in-transit vehicles if an incident occurs ahead.

---

## 👤 Author & Project Info

* **Developer:** **Chetanya Sharma** — 2nd Year B.Tech Student (Artificial Intelligence & Machine Learning)
* **GitHub:** [@chetanya-sharma-ai](https://github.com/chetanya-sharma-ai)
* **LinkedIn:** [Chetanya Sharma](https://www.linkedin.com/in/chetanya-sharma-504615381/)
* **License:** [MIT License](LICENSE)
