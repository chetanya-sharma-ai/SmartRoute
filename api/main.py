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
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .engine_runner import run_cpp_engine
from .ml_inference import MLInference
from .route_scenarios import create_route_weights

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
    incident_context: dict


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


# Node ID cache for fast existence checks
_VALID_NODE_IDS: set[int] | None = None


def get_valid_nodes() -> set[int]:
    global _VALID_NODE_IDS
    if _VALID_NODE_IDS is None:
        if os.path.exists(GRAPH_JSON):
            try:
                with open(GRAPH_JSON, encoding="utf-8") as f:
                    data = json.load(f)
                _VALID_NODE_IDS = {int(n["id"]) for n in data.get("nodes", [])}
            except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
                _VALID_NODE_IDS = set()
        else:
            _VALID_NODE_IDS = set()
    return _VALID_NODE_IDS


@app.get("/graph/summary", tags=["Graph"])
def graph_summary():
    """Return graph metadata (node count, bounds, center)."""
    if not os.path.exists(SUMMARY_JSON):
        raise HTTPException(404, "Graph summary not found. Run export_city_graph.py")
    with open(SUMMARY_JSON, encoding="utf-8") as f:
        return json.load(f)


@app.get("/route", tags=["Routing"], response_model=RouteResponse)
def get_route(
    src: int = Query(..., gt=0, description="Source node ID (positive integer)"),
    dst: int = Query(..., gt=0, description="Destination node ID (positive integer)"),
    hour: int = Query(default=None, ge=0, le=23,
                      description="Hour of day (0-23). Defaults to current hour."),
    weather: Literal["Clear", "Clouds", "Rain", "Drizzle", "Fog", "Mist", "Haze"] = Query(
        default="Clear", description="Weather: Clear/Clouds/Rain/Drizzle/Fog/Mist/Haze"
    ),
    day: int = Query(default=None, ge=0, le=6,
                     description="Day of week (0=Mon). Defaults to today."),
    algo: Literal["astar", "dijkstra"] = Query(
        default="astar", description="Algorithm: astar or dijkstra"
    ),
    scenario: Literal[
        "normal", "road_closure", "flash_flood", "access_restriction", "congestion_spike"
    ] = Query(
        default="normal", description="Simulated demo incident scenario"
    ),
    priority: Literal["standard", "emergency"] = Query(
        default="standard", description="Emergency profile adds extra cost to high-congestion edges"
    ),
):
    """
    Find the fastest route between two nodes using ML-adjusted edge weights.
    """
    if not os.path.exists(GRAPH_JSON):
        raise HTTPException(503, "Graph data not found. Run export_city_graph.py")

    if src == dst:
        raise HTTPException(
            422,
            "Source and destination must be different nodes (src == dst)"
        )

    valid_nodes = get_valid_nodes()
    if valid_nodes and (src not in valid_nodes or dst not in valid_nodes):
        missing_node = src if src not in valid_nodes else dst
        raise HTTPException(
            404,
            {
                "message": f"Node {missing_node} not found in graph",
                "scenario": scenario,
                "priority": priority,
                "data_source": "simulated demo scenario; no live incident feed",
                "tip": "Please select valid nodes from the Indiranagar graph or click on the map."
            }
        )

    # Default to current time
    now = datetime.now().astimezone()
    hour = hour if hour is not None else now.hour
    day  = day  if day  is not None else now.weekday()

    # Apply local, explicitly simulated incidents after the traffic prediction.
    base_weights_path = ml.get_or_compute_weights(hour, day, weather)
    weights_path = None
    try:
        weights_path, incident_context = create_route_weights(
            GRAPH_JSON, base_weights_path, scenario, priority
        )
        result = run_cpp_engine(
            graph_json=GRAPH_JSON,
            src=src,
            dst=dst,
            weights_json=weights_path,
            algo=algo,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        if weights_path and os.path.exists(weights_path):
            try:
                os.remove(weights_path)
            except OSError:
                pass

    if "error" in result:
        detail = result["error"]
        # Distinguish "no path" / "not found" from engine crash errors
        if "No path" in detail or "not found" in detail.lower():
            raise HTTPException(
                404,
                {
                    "message": f"No safe route found: {detail}",
                    "scenario": scenario,
                    "priority": priority,
                    "data_source": "simulated demo scenario; no live incident feed",
                    "tip": "The selected scenario may have blocked all paths between these nodes. Try a different node pair or scenario."
                }
            )
        raise HTTPException(503, f"Routing engine error: {detail}")

    # Add congestion context
    congestion_ctx = ml.predict_congestion_single(hour, day, weather)
    result["congestion_context"] = congestion_ctx
    result["incident_context"] = incident_context
    result["src"] = src
    result["dst"] = dst

    return result


@app.get("/congestion", tags=["ML"], response_model=CongestionResponse)
def predict_congestion(
    from_node: int = Query(..., gt=0, description="From node ID"),
    to_node: int = Query(..., gt=0, description="To node ID"),
    hour: int = Query(default=8, ge=0, le=23, description="Hour of day (0-23)"),
    weather: Literal["Clear", "Clouds", "Rain", "Drizzle", "Fog", "Mist", "Haze"] = Query(
        default="Clear", description="Weather condition"
    ),
    road_length: float = Query(default=500.0, gt=0, description="Road segment length in meters")
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
    hour: int = Query(default=None, ge=0, le=23, description="Hour of day (0-23)"),
    weather: Literal["Clear", "Clouds", "Rain", "Drizzle", "Fog", "Mist", "Haze"] = Query(
        default="Clear", description="Weather condition"
    ),
    day: int = Query(default=None, ge=0, le=6, description="Day of week (0=Mon)")
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
    weather: Literal["Clear", "Clouds", "Rain", "Drizzle", "Fog", "Mist", "Haze"] = Query(
        default="Clear", description="Weather condition"
    ),
    day: int = Query(default=0, ge=0, le=6, description="Day of week (0=Mon)")
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
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude (-90 to 90)"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude (-180 to 180)")
):
    """Find the nearest graph node to given coordinates."""
    result = ml.find_nearest_node(lat, lon)
    if result is None:
        raise HTTPException(503, "No graph data loaded")
    if result.get("distance_m", 0) > 10000.0:
        raise HTTPException(
            400,
            {
                "message": f"Coordinates ({lat}, {lon}) are outside the supported graph area (Indiranagar, Bangalore).",
                "distance_m": result.get("distance_m"),
                "tip": "Please click within the Indiranagar map bounds."
            }
        )
    return result
