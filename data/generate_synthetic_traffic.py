"""
generate_synthetic_traffic.py
──────────────────────────────────────────────────────────────────────────────
Generates realistic synthetic traffic data for each road segment,
simulating time-of-day, weather, and day-of-week patterns.

This gives us training data for the ML models without needing a
paid traffic API subscription.

Output: data/traffic_data.csv
"""

import os
import random
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "traffic_data.csv")
EDGES_CSV   = os.path.join(os.path.dirname(__file__), "graph_edges.csv")

WEATHER_TYPES = ["Clear", "Clouds", "Rain", "Drizzle", "Fog", "Mist", "Haze"]
WEATHER_WEIGHTS = [0.40, 0.25, 0.15, 0.08, 0.05, 0.04, 0.03]

# Peak hour multipliers (hour → congestion factor)
HOUR_PROFILE = {
    0: 0.10, 1: 0.08, 2: 0.07, 3: 0.07, 4: 0.10, 5: 0.20,
    6: 0.50, 7: 0.85, 8: 1.00, 9: 0.90, 10: 0.70, 11: 0.65,
    12: 0.80, 13: 0.75, 14: 0.70, 15: 0.75, 16: 0.85, 17: 1.00,
    18: 0.95, 19: 0.80, 20: 0.65, 21: 0.50, 22: 0.35, 23: 0.20
}

WEATHER_FACTOR = {
    "Clear": 1.0, "Clouds": 1.05, "Drizzle": 1.15,
    "Rain": 1.30, "Fog": 1.40, "Mist": 1.20, "Haze": 1.10
}

def congestion_label(volume_pct: float) -> str:
    if volume_pct < 0.35:  return "Low"
    if volume_pct < 0.70:  return "Medium"
    return "High"


def generate_records(num_days: int = 90, edges_df: pd.DataFrame = None) -> pd.DataFrame:
    records = []
    start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)

    # Use a sample of edge IDs or fallback to synthetic ones
    if edges_df is not None and len(edges_df) > 0:
        sample_edges = edges_df.sample(min(200, len(edges_df)))[["from","to","length"]].values.tolist()
    else:
        sample_edges = [(i, i+1, random.uniform(100, 2000)) for i in range(200)]

    for day in range(num_days):
        current = start + timedelta(days=day)
        day_of_week = current.weekday()           # 0=Mon, 6=Sun
        is_weekend = int(day_of_week >= 5)
        is_holiday = int(day_of_week == 6 and random.random() < 0.1)
        weather = random.choices(WEATHER_TYPES, weights=WEATHER_WEIGHTS, k=1)[0]
        temp_c = np.random.normal(28, 4)          # Bangalore avg ~28°C

        for hour in range(24):
            base_factor = HOUR_PROFILE[hour]
            if is_weekend:
                base_factor *= 0.65              # lighter on weekends
            if is_holiday:
                base_factor *= 0.50

            w_factor = WEATHER_FACTOR.get(weather, 1.0)

            # Sample a subset of edges each hour
            for from_id, to_id, length in random.sample(sample_edges,
                                                         min(50, len(sample_edges))):
                noise = np.random.normal(0, 0.08)
                volume_pct = np.clip(base_factor * w_factor + noise, 0.0, 1.0)
                max_capacity = max(1, int(length / 10))     # cars per segment
                traffic_volume = int(volume_pct * max_capacity)

                records.append({
                    "timestamp":        current + timedelta(hours=hour),
                    "date":             current.date(),
                    "hour":             hour,
                    "day_of_week":      day_of_week,
                    "is_weekend":       is_weekend,
                    "is_holiday":       is_holiday,
                    "month":            current.month,
                    "weather_main":     weather,
                    "temp_c":           round(temp_c, 1),
                    "from_node":        int(from_id),
                    "to_node":          int(to_id),
                    "road_length_m":    round(length, 1),
                    "traffic_volume":   traffic_volume,
                    "volume_pct":       round(volume_pct, 4),
                    "congestion_level": congestion_label(volume_pct)
                })

    return pd.DataFrame(records)


def main():
    print("[Traffic Gen] Loading edges...")
    edges_df = None
    if os.path.exists(EDGES_CSV):
        edges_df = pd.read_csv(EDGES_CSV)
        print(f"  -> Loaded {len(edges_df)} edges from {EDGES_CSV}")
    else:
        print("  -> Edges CSV not found; using synthetic edge IDs")

    print("[Traffic Gen] Generating 90-day synthetic traffic data...")
    df = generate_records(num_days=90, edges_df=edges_df)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"\n[OK] Generated {len(df):,} records -> {OUTPUT_PATH}")
    print(df["congestion_level"].value_counts(normalize=True).round(3))


if __name__ == "__main__":
    main()
