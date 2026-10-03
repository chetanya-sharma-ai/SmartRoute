"""
main.py — SmartRoute FastAPI Backend
──────────────────────────────────────────────────────────────────────────────
REST API that connects:
  • Python ML models (congestion prediction)
  • C++ graph engine (pathfinding)
  • Frontend (route + heatmap data)

Run:
    uvicorn api.main:app --reload --port 8000
"""

import json
import os
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .engine_runner import run_cpp_engine
from .ml_inference import MLInference

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="SmartRoute API",
    description="AI-Powered Smart Traffic & Route Optimization for Bangalore",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

# Load ML inference engine once at startup
ml = MLInference()

DATA_DIR   = os.path.join(os.path.dirname(__file__), "..", "data")
GRAPH_JSON = os.path.join(DATA_DIR, "graph_data.json")
SUMMARY_JSON = os.path.join(DATA_DIR, "graph_summary.json")


# ── Pydantic models ───────────────────────────────────────────────────────────
class RouteResponse(BaseModel):
    algorithm: str
    src: int
    dst: int
    total_distance_m: float
    total_time_s: float
    eta_minutes: float
    num_nodes: int
    path: list
    congestion_context: dict


class CongestionResponse(BaseModel):
    from_node: int
    to_node: int
    congestion_level: str
    volume_pct: float
    time_weight: float


class HeatmapResponse(BaseModel):
    type: str
    features: list


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {
        "status": "ok",
        "service": "SmartRoute API",
        "docs": "/docs",
        "frontend": "/app"
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy", "timestamp": datetime.now().astimezone().isoformat()}


@app.get("/graph/summary", tags=["Graph"])
def graph_summary():
    """Return graph metadata (node count, bounds, center)."""
    if not os.path.exists(SUMMARY_JSON):
        raise HTTPException(404, "Graph summary not found. Run export_city_graph.py")
    with open(SUMMARY_JSON) as f:
        return json.load(f)


@app.get("/route", tags=["Routing"], response_model=RouteResponse)
def get_route(
    src: int = Query(..., description="Source node ID"),
    dst: int = Query(..., description="Destination node ID"),
    hour: int = Query(default=None, ge=0, le=23,
                      description="Hour of day (0-23). Defaults to current hour."),
    weather: str = Query(default="Clear",
                         description="Weather: Clear/Clouds/Rain/Drizzle/Fog/Mist/Haze"),
    day: int = Query(default=None, ge=0, le=6,
                     description="Day of week (0=Mon). Defaults to today."),
    algo: str = Query(default="astar", description="Algorithm: astar or dijkstra")
):
    """
    Find the fastest route between two nodes using ML-adjusted edge weights.
    """
    if not os.path.exists(GRAPH_JSON):
        raise HTTPException(503, "Graph data not found. Run export_city_graph.py")

    # Default to current time
    now = datetime.now().astimezone()
    hour = hour if hour is not None else now.hour
    day  = day  if day  is not None else now.weekday()

    # Get ML-adjusted weights for this time/weather
    weights_path = ml.get_or_compute_weights(hour, day, weather)

    # Run C++ engine
    result = run_cpp_engine(
        graph_json=GRAPH_JSON,
        src=src,
        dst=dst,
        weights_json=weights_path,
        algo=algo
    )

    if "error" in result:
        raise HTTPException(404, f"No route found: {result['error']}")

    # Add congestion context
    congestion_ctx = ml.predict_congestion_single(hour, day, weather)
    result["congestion_context"] = congestion_ctx
    result["src"] = src
    result["dst"] = dst

    return result


@app.get("/congestion", tags=["ML"], response_model=CongestionResponse)
def predict_congestion(
    from_node: int = Query(...),
    to_node: int = Query(...),
    hour: int = Query(default=8, ge=0, le=23),
    weather: str = Query(default="Clear"),
    road_length: float = Query(default=500.0, description="Road segment length in meters")
):
    """Predict congestion level for a specific road segment."""
    result = ml.predict_single_edge(
        from_node=from_node,
        to_node=to_node,
        hour=hour,
        weather=weather,
        road_length_m=road_length
    )
    return result


@app.get("/heatmap", tags=["ML"])
def get_heatmap(
    hour: int = Query(default=None, ge=0, le=23),
    weather: str = Query(default="Clear"),
    day: int = Query(default=None, ge=0, le=6)
):
    """
    Return GeoJSON FeatureCollection of all road segments colored by
    predicted congestion level (for map heatmap overlay).
    """
    now = datetime.now().astimezone()
    hour = hour if hour is not None else now.hour
    day  = day  if day  is not None else now.weekday()

    features = ml.get_heatmap_geojson(hour, day, weather)
    return {"type": "FeatureCollection", "features": features}


@app.get("/simulate", tags=["Simulation"])
def simulate_day(
    weather: str = Query(default="Clear"),
    day: int = Query(default=0)
):
    """
    Return congestion predictions for all 24 hours of a given day.
    Useful for animating a day-in-the-life visualization.
    """
    results = []
    for hour in range(24):
        ctx = ml.predict_congestion_single(hour, day, weather)
        results.append({"hour": hour, **ctx})
    return {"weather": weather, "day_of_week": day, "hourly": results}


@app.get("/nodes/nearest", tags=["Graph"])
def nearest_node(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude")
):
    """Find the nearest graph node to given coordinates."""
    result = ml.find_nearest_node(lat, lon)
    if result is None:
        raise HTTPException(404, "No graph data loaded")
    return result
