"""
ml_inference.py
──────────────────────────────────────────────────────────────────────────────
ML inference layer — loads trained models and provides:
  • Edge weight computation (for C++ engine input)
  • Single-edge congestion prediction
  • Heatmap GeoJSON generation
  • Nearest node lookup
"""

import json
import math
import os
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
DATA_DIR   = os.path.join(os.path.dirname(__file__), "..", "data")
EDGES_CSV  = os.path.join(DATA_DIR, "graph_edges.csv")
NODES_CSV  = os.path.join(DATA_DIR, "graph_nodes.csv")

CONGESTION_MULTIPLIER = {"Low": 1.0, "Medium": 1.6, "High": 3.0}
CONGESTION_COLOR = {"Low": "#22c55e", "Medium": "#f59e0b", "High": "#ef4444"}

WEATHER_COLS = [
    "weather_Clear", "weather_Clouds", "weather_Rain",
    "weather_Drizzle", "weather_Fog", "weather_Mist", "weather_Haze"
]


class MLInference:
    """Singleton-style ML inference engine loaded once at app startup."""

    def __init__(self):
        self._clf = None
        self._features = None
        self._label_inv = None
        self._edges_df = None
        self._nodes_df = None
        self._weights_cache: dict[str, str] = {}   # cache key → file path
        self._load()

    def _load(self):
        """Load models and data. Gracefully handles missing files (dev mode)."""
        clf_path  = os.path.join(MODELS_DIR, "rf_congestion.pkl")
        feat_path = os.path.join(MODELS_DIR, "features.json")

        if os.path.exists(clf_path) and os.path.exists(feat_path):
            self._clf = joblib.load(clf_path)
            # Avoid spawning all CPU cores for each API request.
            if hasattr(self._clf, "n_jobs"):
                self._clf.set_params(n_jobs=1)
            with open(feat_path) as f:
                meta = json.load(f)
            self._features = meta["features"]
            self._label_inv = {int(k): v for k, v in meta["label_map"].items()}
            print("[ML] Models loaded [OK]")
        else:
            print("[ML] WARNING: Models not trained yet. Using rule-based fallback.")

        if os.path.exists(EDGES_CSV):
            self._edges_df = pd.read_csv(EDGES_CSV)
            print(f"[ML] Edges loaded: {len(self._edges_df)} segments")
        if os.path.exists(NODES_CSV):
            self._nodes_df = pd.read_csv(NODES_CSV)
            print(f"[ML] Nodes loaded: {len(self._nodes_df)} nodes")

    def _build_feature(self, hour: int, day: int, weather: str,
                       road_length: float) -> np.ndarray:
        row = {
            "hour": hour, "day_of_week": day,
            "is_weekend": int(day >= 5), "is_holiday": 0,
            "month": datetime.now().astimezone().month, "temp_c": 28.0,
            "road_length_m": road_length
        }
        for col in WEATHER_COLS:
            row[col] = 1 if col == f"weather_{weather}" else 0
        features = self._features or (list(row.keys()))
        return np.array([row.get(f, 0) for f in features], dtype=float)

    def _rule_based_congestion(self, hour: int, weather: str) -> str:
        """Fallback congestion rule when ML model is not trained."""
        peak = hour in (7, 8, 9, 17, 18, 19)
        if peak and weather in ("Rain", "Fog"):  return "High"
        if peak:                                  return "Medium"
        if weather in ("Rain", "Fog"):            return "Medium"
        return "Low"

    def predict_congestion(self, hour: int, day: int, weather: str,
                           road_length: float = 500.0) -> str:
        """Predict congestion level (Low/Medium/High) for given conditions."""
        if self._clf is None:
            return self._rule_based_congestion(hour, weather)
        x = self._build_feature(hour, day, weather, road_length)
        pred = int(self._clf.predict([x])[0])
        return self._label_inv.get(pred, "Low")

    def predict_single_edge(self, from_node: int, to_node: int,
                             hour: int, weather: str,
                             road_length_m: float = 500.0) -> dict:
        """Predict congestion and compute time weight for one edge."""
        congestion = self.predict_congestion(hour, 0, weather, road_length_m)
        mult = CONGESTION_MULTIPLIER[congestion]
        speed = 40.0
        base_time = road_length_m / (speed * 1000 / 3600)
        vol_map = {"Low": 0.2, "Medium": 0.55, "High": 0.85}
        return {
            "from_node": from_node, "to_node": to_node,
            "congestion_level": congestion,
            "volume_pct": vol_map[congestion],
            "time_weight": round(base_time * mult, 4)
        }

    def predict_congestion_single(self, hour: int, day: int,
                                   weather: str) -> dict:
        """Return aggregate congestion context for a time/weather combo."""
        congestion = self.predict_congestion(hour, day, weather)
        descriptions = {
            "Low": "Roads are clear. Enjoy the drive!",
            "Medium": "Moderate traffic. Expect some slowdowns.",
            "High": "Heavy congestion. Consider an alternate route."
        }
        return {
            "congestion_level": congestion,
            "description": descriptions[congestion],
            "color": CONGESTION_COLOR[congestion],
            "multiplier": CONGESTION_MULTIPLIER[congestion]
        }

    def get_or_compute_weights(self, hour: int, day: int,
                                weather: str) -> str | None:
        """
        Get cached or freshly computed edge weights JSON path.
        Returns None if edges CSV not available.
        """
        if self._edges_df is None:
            return None

        cache_key = f"{hour}_{day}_{weather}"
        if cache_key in self._weights_cache:
            cached = self._weights_cache[cache_key]
            if os.path.exists(cached):
                return cached

        path = os.path.join(DATA_DIR, f"edge_weights_{cache_key}.json")
        if os.path.isfile(path):
            self._weights_cache[cache_key] = path
            return path

        edges = self._edges_df
        lengths = edges["length"].fillna(500.0).astype(float).to_numpy()
        speeds = (
            edges["speed_kph"]
            if "speed_kph" in edges
            else pd.Series(40.0, index=edges.index)
        ).fillna(40.0).astype(float).to_numpy()

        if self._clf is None:
            congestion_levels = [
                self._rule_based_congestion(hour, weather) for _ in lengths
            ]
        elif len(lengths):
            feature_rows = np.vstack([
                self._build_feature(hour, day, weather, length)
                for length in lengths
            ])
            predictions = self._clf.predict(feature_rows)
            congestion_levels = [
                self._label_inv.get(int(prediction), "Low")
                for prediction in predictions
            ]
        else:
            congestion_levels = []

        results = []
        for (_, row), length, speed, congestion in zip(
            edges.iterrows(), lengths, speeds, congestion_levels
        ):
            multiplier = CONGESTION_MULTIPLIER[congestion]
            base_time = length / (speed * 1000 / 3600)
            results.append({
                "from": int(row["from"]),
                "to": int(row["to"]),
                "time_weight": round(base_time * multiplier, 4),
                "congestion": congestion,
            })

        with open(path, "w") as f:
            json.dump(results, f)
        self._weights_cache[cache_key] = path
        return path

    def get_heatmap_geojson(self, hour: int, day: int,
                             weather: str) -> list:
        """
        Generate GeoJSON features for each road segment,
        colored by predicted congestion level.
        """
        if self._edges_df is None or self._nodes_df is None:
            return []

        node_map = {int(r["node_id"]): r
                    for _, r in self._nodes_df.iterrows()}

        features = []
        for _, row in self._edges_df.iterrows():
            fn = int(row["from"])
            tn = int(row["to"])
            if fn not in node_map or tn not in node_map:
                continue

            n1 = node_map[fn]
            n2 = node_map[tn]
            length = float(row.get("length", 500))
            cong   = self.predict_congestion(hour, day, weather, length)

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [float(n1["lon"]), float(n1["lat"])],
                        [float(n2["lon"]), float(n2["lat"])]
                    ]
                },
                "properties": {
                    "from": fn, "to": tn,
                    "congestion": cong,
                    "color": CONGESTION_COLOR[cong],
                    "length_m": round(length, 1)
                }
            })

        return features

    def find_nearest_node(self, lat: float, lon: float) -> dict | None:
        """Find the graph node nearest to given lat/lon coordinates."""
        if self._nodes_df is None:
            return None

        def haversine(lat1, lon1, lat2, lon2):
            R = 6371000
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dp = math.radians(lat2 - lat1)
            dl = math.radians(lon2 - lon1)
            a = math.sin(dp/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
            return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        best = None
        best_dist = float("inf")
        for _, row in self._nodes_df.iterrows():
            d = haversine(lat, lon, float(row["lat"]), float(row["lon"]))
            if d < best_dist:
                best_dist = d
                best = {
                    "node_id": int(row["node_id"]),
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                    "distance_m": round(d, 1)
                }
        return best
