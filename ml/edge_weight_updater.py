"""
edge_weight_updater.py
──────────────────────────────────────────────────────────────────────────────
Uses the trained ML models to predict congestion for each road segment
at a given hour/weather and updates the C++ engine's edge weights accordingly.

Congestion multipliers:
  Low    → 1.0× (free flow)
  Medium → 1.6× (moderate slowdown)
  High   → 3.0× (heavy congestion)

Output: data/edge_weights_<hour>_<weather>.json
Usage:
    python edge_weight_updater.py --hour 8 --weather Rain --day 0
"""

import argparse
import json
import os

import joblib
import numpy as np
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────
MODELS_DIR  = os.path.join(os.path.dirname(__file__), "..", "models")
DATA_DIR    = os.path.join(os.path.dirname(__file__), "..", "data")
EDGES_CSV   = os.path.join(DATA_DIR, "graph_edges.csv")

CONGESTION_MULTIPLIER = {"Low": 1.0, "Medium": 1.6, "High": 3.0}
WEATHER_COLS = ["weather_Clear", "weather_Clouds", "weather_Rain",
                "weather_Drizzle", "weather_Fog", "weather_Mist", "weather_Haze"]
LABEL_INV = {"0": "Low", "1": "Medium", "2": "High"}


def load_models():
    """Load trained ML models from disk."""
    clf_path = os.path.join(MODELS_DIR, "rf_congestion.pkl")
    feat_path = os.path.join(MODELS_DIR, "features.json")

    if not os.path.exists(clf_path):
        raise FileNotFoundError(
            f"Model not found: {clf_path}\n"
            "Run: python ml/train_models.py"
        )

    clf = joblib.load(clf_path)
    with open(feat_path) as f:
        meta = json.load(f)

    label_inv = {int(k): v for k, v in meta["label_map"].items()}
    return clf, meta["features"], label_inv


def build_feature_row(hour: int, day_of_week: int, weather: str,
                      road_length_m: float, month: int,
                      feature_names: list) -> np.ndarray:
    """Build a single feature vector for ML inference."""
    row = {
        "hour": hour,
        "day_of_week": day_of_week,
        "is_weekend": int(day_of_week >= 5),
        "is_holiday": 0,
        "month": month,
        "temp_c": 28.0,   # Bangalore average
        "road_length_m": road_length_m,
    }
    # One-hot weather
    for col in WEATHER_COLS:
        row[col] = 1 if col == f"weather_{weather}" else 0

    return np.array([row.get(f, 0) for f in feature_names], dtype=float)


def compute_edge_weights(hour: int, day_of_week: int, weather: str,
                          month: int = 9) -> list:
    """
    Predict congestion for all road segments and compute updated time weights.

    Returns list of {"from": X, "to": Y, "time_weight": Z} dicts.
    """
    clf, features, label_inv = load_models()

    if not os.path.exists(EDGES_CSV):
        raise FileNotFoundError(
            f"Edges CSV not found: {EDGES_CSV}\n"
            "Run: python data/export_city_graph.py"
        )

    edges = pd.read_csv(EDGES_CSV)
    results = []

    for _, row in edges.iterrows():
        length  = float(row.get("length", 500))
        speed   = float(row.get("speed_kph", 40)) if "speed_kph" in row else 40.0
        x = build_feature_row(hour, day_of_week, weather, length, month, features)
        pred_class = int(clf.predict([x])[0])
        congestion = label_inv.get(pred_class, "Low")
        multiplier = CONGESTION_MULTIPLIER[congestion]

        base_time = length / (speed * 1000 / 3600)  # seconds at free flow
        adjusted_time = base_time * multiplier

        results.append({
            "from":        int(row["from"]),
            "to":          int(row["to"]),
            "time_weight": round(adjusted_time, 4),
            "congestion":  congestion,
            "multiplier":  multiplier
        })

    return results


def save_weights(results: list, hour: int, weather: str) -> str:
    """Save edge weights to JSON file."""
    filename = f"edge_weights_{hour:02d}h_{weather.lower()}.json"
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w") as f:
        json.dump(results, f)
    print(f"[Weights] Saved {len(results)} edges -> {path}")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hour",    type=int, default=8,
                        help="Hour of day (0-23)")
    parser.add_argument("--day",     type=int, default=0,
                        help="Day of week (0=Mon, 6=Sun)")
    parser.add_argument("--weather", default="Clear",
                        choices=["Clear","Clouds","Rain","Drizzle","Fog","Mist","Haze"])
    parser.add_argument("--month",   type=int, default=9)
    args = parser.parse_args()

    print(f"[EdgeUpdater] hour={args.hour}, day={args.day}, "
          f"weather={args.weather}")
    results = compute_edge_weights(args.hour, args.day, args.weather, args.month)

    # Print congestion distribution
    from collections import Counter
    counts = Counter(r["congestion"] for r in results)
    print(f"  Congestion: {dict(counts)}")

    save_weights(results, args.hour, args.weather)


if __name__ == "__main__":
    main()
