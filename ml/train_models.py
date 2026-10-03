"""
train_models.py
──────────────────────────────────────────────────────────────────────────────
Trains two ML models on traffic_data.csv:
  1. XGBoost Regressor  → predicts traffic_volume (continuous)
  2. Random Forest       → predicts congestion_level (Low/Medium/High)

Saves trained models to models/ directory.
Prints evaluation metrics to console.

Usage:
    python train_models.py
    python train_models.py --data ../data/traffic_data.csv
"""

import argparse
import json
import os

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import train_test_split

# ── Config ────────────────────────────────────────────────────────────────────
DATA_PATH   = os.path.join(os.path.dirname(__file__), "..", "data", "traffic_data.csv")
MODELS_DIR  = os.path.join(os.path.dirname(__file__), "..", "models")
METRICS_JSON = os.path.join(MODELS_DIR, "metrics.json")

FEATURES = [
    "hour", "day_of_week", "is_weekend", "is_holiday",
    "month", "temp_c", "road_length_m",
    "weather_Clear", "weather_Clouds", "weather_Rain",
    "weather_Drizzle", "weather_Fog", "weather_Mist", "weather_Haze"
]

LABEL_MAP = {"Low": 0, "Medium": 1, "High": 2}
LABEL_INV = {v: k for k, v in LABEL_MAP.items()}


def load_and_prepare(data_path: str) -> pd.DataFrame:
    """Load CSV and engineer features."""
    print(f"[Data] Loading {data_path}")
    df = pd.read_csv(data_path)
    print(f"[Data] {len(df):,} records loaded")

    # One-hot encode weather
    weather_dummies = pd.get_dummies(df["weather_main"], prefix="weather")
    df = pd.concat([df, weather_dummies], axis=1)

    # Ensure all weather columns exist (in case some are missing)
    for col in [c for c in FEATURES if c.startswith("weather_")]:
        if col not in df.columns:
            df[col] = 0

    # Encode congestion label
    df["congestion_encoded"] = df["congestion_level"].map(LABEL_MAP)

    return df


def train_xgb_regressor(X_train, X_test, y_train, y_test) -> dict:
    """Train XGBoost traffic volume regressor."""
    print("\n[XGBoost] Training traffic volume regressor...")
    model = xgb.XGBRegressor(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )
    y_pred = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae  = mean_absolute_error(y_test, y_pred)
    r2   = r2_score(y_test, y_pred)

    print(f"  RMSE : {rmse:.4f}")
    print(f"  MAE  : {mae:.4f}")
    print(f"  R2   : {r2:.4f}")

    # Save model
    model_path = os.path.join(MODELS_DIR, "xgb_traffic.pkl")
    joblib.dump(model, model_path)
    print(f"  Saved -> {model_path}")

    return {"rmse": round(rmse, 4), "mae": round(mae, 4), "r2": round(r2, 4)}


def train_rf_classifier(X_train, X_test, y_train, y_test) -> dict:
    """Train Random Forest congestion classifier."""
    print("\n[RandomForest] Training congestion classifier...")
    model = RandomForestClassifier(
        n_estimators=150,
        max_depth=12,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    f1  = f1_score(y_test, y_pred, average="weighted")

    print(f"  Accuracy : {acc:.4f}")
    print(f"  F1 Score : {f1:.4f}")
    print("\n  Classification Report:")
    print(classification_report(y_test, y_pred,
                                 target_names=["Low","Medium","High"]))

    # Feature importances
    importances = dict(sorted(
        zip(FEATURES, model.feature_importances_),
        key=lambda x: x[1], reverse=True
    )[:5])
    print(f"  Top features: {importances}")

    # Save model + label encoder
    model_path = os.path.join(MODELS_DIR, "rf_congestion.pkl")
    joblib.dump(model, model_path)
    print(f"  Saved -> {model_path}")

    return {
        "accuracy": round(acc, 4),
        "f1_weighted": round(f1, 4),
        "top_features": {k: round(float(v), 4) for k, v in importances.items()}
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=DATA_PATH)
    args = parser.parse_args()

    os.makedirs(MODELS_DIR, exist_ok=True)

    df = load_and_prepare(args.data)

    # Available features
    avail_features = [f for f in FEATURES if f in df.columns]
    X = df[avail_features].fillna(0).values
    y_reg = df["volume_pct"].values     # regression target (0-1 normalized)
    y_clf = df["congestion_encoded"].values  # classification target (0/1/2)

    # Split
    X_tr, X_te, yr_tr, yr_te = train_test_split(X, y_reg, test_size=0.2,
                                                  random_state=42)
    _, _, yc_tr, yc_te = train_test_split(X, y_clf, test_size=0.2,
                                            random_state=42)

    # Train
    xgb_metrics = train_xgb_regressor(X_tr, X_te, yr_tr, yr_te)
    rf_metrics  = train_rf_classifier(X_tr, X_te, yc_tr, yc_te)

    # Save feature list for inference
    features_path = os.path.join(MODELS_DIR, "features.json")
    with open(features_path, "w") as f:
        json.dump({"features": avail_features, "label_map": LABEL_INV}, f, indent=2)

    # Save combined metrics
    metrics = {
        "xgboost_regressor": xgb_metrics,
        "random_forest_classifier": rf_metrics
    }
    with open(METRICS_JSON, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\n[OK] Training complete. Metrics -> {METRICS_JSON}")


if __name__ == "__main__":
    main()
