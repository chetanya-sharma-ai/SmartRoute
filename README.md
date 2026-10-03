<p align="center">
  <h1 align="center">🚦 SmartRoute</h1>
  <h3 align="center">AI-Powered Smart Traffic &amp; Route Optimization · Bangalore, India</h3>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/C%2B%2B-17-orange?logo=cplusplus&logoColor=white" alt="C++">
  <img src="https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/XGBoost-R²%3D0.95-red?logo=python" alt="XGBoost">
  <img src="https://img.shields.io/badge/RandomForest-88.5%25-green" alt="RandomForest">
  <img src="https://img.shields.io/badge/Leaflet.js-Map-4CAF50?logo=leaflet" alt="Leaflet">
  <img src="https://img.shields.io/badge/Tests-13%20passed-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="MIT">
</p>

<p align="center">
  <a href="#-quick-start"><strong>Quick Start</strong></a> ·
  <a href="#-architecture"><strong>Architecture</strong></a> ·
  <a href="#-ml-results"><strong>ML Results</strong></a> ·
  <a href="#-benchmarks"><strong>Benchmarks</strong></a> ·
  <a href="#-api-reference"><strong>API</strong></a>
</p>

---

> **SmartRoute** is a full-stack intelligent routing system combining a **C++17 graph engine** (A\* / Dijkstra), **Machine Learning** (XGBoost + Random Forest), and an **interactive Leaflet.js map** to find the fastest route through Bangalore's real road network — dynamically adjusted for time-of-day, weather, and predicted congestion.
>
> Built as a portfolio project by a 2nd year B.Tech AI & ML student.

---

## ✨ Features

| Feature | Detail |
|---|---|
| 🗺 **Real City Graph** | Bangalore road network from OpenStreetMap (OSMnx) |
| ⚡ **C++ Engine** | A\* and Dijkstra implemented in C++17 with STL |
| 🤖 **ML Congestion** | XGBoost regressor + Random Forest classifier |
| 🔗 **Dynamic Weights** | ML predictions fed into C++ graph before routing |
| 🔥 **Traffic Heatmap** | Color-coded overlay: 🟢 Low · 🟡 Medium · 🔴 High |
| ⏰ **Time Simulation** | Hour slider — simulate any time of day |
| 🌧 **Weather Aware** | Routes adapt for Rain, Fog, Mist conditions |
| 🐳 **Docker Ready** | Multi-stage Docker + Compose for one-command deploy |
| ✅ **Tested** | 13 pytest tests across API + ML layers |

---

## 🏗 Architecture

```
                    ┌─────────────────────────────────┐
                    │          Leaflet.js Frontend     │
                    │  Map · Route · Heatmap · Slider  │
                    └────────────────┬────────────────┘
                                     │ HTTP REST
                    ┌────────────────▼────────────────┐
                    │         FastAPI Backend          │
                    │  /route  /congestion  /heatmap   │
                    └──────┬──────────────┬───────────┘
                           │              │
          ┌────────────────▼──┐    ┌──────▼─────────────────┐
          │  C++ Graph Engine │    │   Python ML Pipeline    │
          │  A* / Dijkstra    │◄───┤  XGBoost  RandomForest  │
          │  (subprocess)     │    │  edge_weight_updater    │
          └───────────────────┘    └─────────────────────────┘
                                            │
                              ┌─────────────▼─────────────┐
                              │  OpenStreetMap (OSMnx)     │
                              │  graph_data.json            │
                              │  edge_weights_*.json        │
                              └─────────────────────────────┘
```

### Data Flow
```
User clicks map
  → /nodes/nearest?lat=12.97&lon=77.59    (find nearest graph node)
  → /route?src=X&dst=Y&hour=8&weather=Rain
      → ML predicts congestion per edge    (Random Forest)
      → Write edge_weights_08h_rain.json
      → C++ engine: A*(graph, ML_weights)
      → JSON path response
  → Leaflet.js draws animated route + ETA
```

---

## 🤖 ML Results

### Trained on 108,000 generated synthetic records (90 days × 24h × road segments)

#### XGBoost Regressor — Traffic Volume Prediction
| Metric | Value | Interpretation |
|--------|-------|----------------|
| **R²** | **0.9524** | 95.2% of variance explained |
| **RMSE** | **0.0721** | ±7.2% volume prediction error |
| **MAE** | **0.0568** | ±5.7% mean absolute error |

#### Random Forest Classifier — Congestion Level (Low/Medium/High)

**Accuracy: 88.52% · Weighted F1: 88.59%** (reported in models/metrics.json; evaluated on the synthetic dataset holdout).

#### Feature Importances
```
hour            ████████████████████████████████████ 81.1%  ← strongest signal
day_of_week     ███                                   6.9%
is_weekend      ██                                    6.2%
road_length_m   █                                     1.9%
weather_*       █                                     0.9%
```

---

## 📊 Benchmarks

**Dijkstra vs A\* — Python implementation (30 trials each)**

| Graph Size | Dijkstra (avg ms) | A\* (avg ms) | Nodes Explored ↓ | Optimal? |
|-----------|-------------------|--------------|------------------|----------|
| 100 nodes | 0.042 ms | 0.070 ms | **47.1% fewer** | ✅ |
| 500 nodes | 0.496 ms | 0.510 ms | **30.6% fewer** | ✅ |
| 1,000 nodes | 0.687 ms | 1.158 ms | **33.5% fewer** | ✅ |
| 2,000 nodes | 1.357 ms | 2.725 ms | **40.4% fewer** | ✅ |
| 5,000 nodes | 6.310 ms | 9.787 ms | **33.9% fewer** | ✅ |

> **Key insight:** In the saved Python benchmark, A* explored fewer nodes but was slower in wall-clock time at each tested graph size. The benchmark does not measure the C++ engine, so no C++ speedup is claimed.
>
> Run: `python benchmarks/benchmark.py`

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- C++ compiler (MinGW on Windows, GCC on Linux)
- CMake ≥ 3.15

### 1 — Clone & Install
```bash
git clone https://github.com/chetanya-sharma-ai/SmartRoute.git
cd SmartRoute
pip install -r requirements.txt
```

### 2 — Run Demo (no OSMnx needed)
```bash
python demo.py
```

### 3 — Download Real City Map
```bash
# Downloads Indiranagar neighbourhood of Bangalore (~5k nodes)
python data/export_city_graph.py --place "Indiranagar, Bangalore, India" --simplify
```

### 4 — Generate Data & Train Models
```bash
python data/generate_synthetic_traffic.py   # 108k records, ~10min
python ml/train_models.py                    # XGBoost + RandomForest, ~2min
```

### 5 — Build C++ Engine
```bash
cd core && mkdir build && cd build
cmake .. -G "MinGW Makefiles"     # Windows
cmake --build . --config Release
# Binary: core/build/smartroute_engine.exe
```

### 6 — Start API + Open Frontend
```bash
uvicorn api.main:app --reload --port 8000
# Open frontend/index.html in browser
# Or: http://localhost:8000/app
```

---

## 🐳 Docker
```bash
docker compose up --build -d
# API docs: http://localhost:8000/docs
# Frontend: http://localhost:8000/app
```

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/route?src=X&dst=Y&hour=8&weather=Rain&algo=astar` | Find optimal ML-weighted route |
| `GET` | `/congestion?from_node=X&to_node=Y&hour=8&weather=Clear` | Predict single-segment congestion |
| `GET` | `/heatmap?hour=17&weather=Clear&day=0` | GeoJSON congestion heatmap |
| `GET` | `/simulate?weather=Rain&day=1` | 24h hourly congestion simulation |
| `GET` | `/nodes/nearest?lat=12.97&lon=77.59` | Nearest graph node to coordinates |
| `GET` | `/graph/summary` | Graph metadata (bounds, center) |

Full interactive docs: **http://localhost:8000/docs**

---

## 📁 Project Structure
```
SmartRoute/
├── core/                        # C++17 graph engine
│   ├── Graph.h / Graph.cpp      # Adjacency list, Haversine, JSON loader
│   ├── Dijkstra.h / .cpp        # Priority-queue Dijkstra
│   ├── AStar.h / .cpp           # Heuristic A* (admissible Haversine)
│   ├── main.cpp                 # CLI entry point → JSON output
│   └── CMakeLists.txt
├── ml/
│   ├── train_models.py          # XGBoost + RandomForest training pipeline
│   └── edge_weight_updater.py   # ML predictions → C++ edge weights
├── api/
│   ├── main.py                  # FastAPI application (8 endpoints)
│   ├── engine_runner.py         # C++ subprocess bridge + Python fallback
│   └── ml_inference.py          # Inference, heatmap generation, nearest-node
├── data/
│   ├── export_city_graph.py     # OSMnx → graph_data.json + CSVs
│   └── generate_synthetic_traffic.py  # 108k synthetic training records
├── frontend/
│   └── index.html               # Leaflet.js dark-themed interactive map
├── benchmarks/
│   ├── benchmark.py             # Dijkstra vs A* timing benchmark
│   └── results/benchmark_results.json  # Actual benchmark data
├── models/                      # Saved .pkl models + metrics.json
├── docs/
│   ├── ALGORITHMS.md            # DSA reference (Dijkstra, A*, Haversine)
│   ├── ML_PIPELINE.md           # ML reference (features, models, pipeline)
│   └── GIT_COMMIT_GUIDE.md      # Meaningful commit history guide
├── tests/
│   ├── test_api.py              # 7 FastAPI endpoint tests
│   └── test_ml.py               # 6 ML inference tests
├── demo.py                      # End-to-end demo (no server needed)
├── Dockerfile                   # Multi-stage C++ + Python build
├── docker-compose.yml
└── requirements.txt
```

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Pathfinding | **C++17**, STL, CMake |
| ML Models | **XGBoost**, **Scikit-learn** (Random Forest) |
| Data Processing | **Pandas**, **NumPy** |
| Backend API | **Python**, **FastAPI**, Uvicorn |
| City Map Data | **OSMnx**, OpenStreetMap |
| Frontend | **Leaflet.js**, OpenStreetMap tiles |
| Containerization | **Docker**, Docker Compose |
| CI/CD | **GitHub Actions** |
| Version Control | **Git/GitHub** |

---

## 🔮 Future Work

- [ ] Real-time traffic via Google Maps / TomTom API
- [ ] LSTM / Transformer for time-series traffic forecasting
- [ ] Reinforcement Learning agent for adaptive routing
- [ ] Graph Neural Network for topology-aware prediction
- [ ] Multi-modal routing (auto + metro + walking)
- [ ] Mobile app (React Native)

---

## 🧪 Tests
```bash
pytest tests/ -v
# Verified locally: 13 tests passed (7 API + 6 ML)
```

---

## 📖 Documentation

- [Algorithm Reference](docs/ALGORITHMS.md) — Dijkstra, A\*, Priority Queue, Haversine
- [ML Pipeline](docs/ML_PIPELINE.md) — Features, Models, Evaluation, Prediction pipeline
- [Git Commit Guide](docs/GIT_COMMIT_GUIDE.md) — Meaningful commit history

---

## 👤 Author

**Chetanya Sharma** — 2nd Year B.Tech AI & ML Student

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?logo=linkedin)](https://www.linkedin.com/in/chetanya-sharma-504615381/)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-black?logo=github)](https://github.com/chetanya-sharma-ai)

---

## 📄 License

MIT © 2026 — See [LICENSE](LICENSE)

---

<p align="center">⭐ If this helped you, please star the repo!</p>
