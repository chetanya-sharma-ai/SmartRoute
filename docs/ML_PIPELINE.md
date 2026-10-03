# SmartRoute — ML Pipeline Reference

> This document explains every ML component: features, models, evaluation, and prediction pipeline.
> Be ready to explain any of this in an interview.

---

## 🎯 Problem Framing

Traffic routing has two ML sub-problems:

| Problem | Type | Target | Model |
|---------|------|--------|-------|
| "How busy is this road?" | Regression | `volume_pct` (0.0–1.0) | XGBoost |
| "Can I drive normally?" | Classification | `congestion_level` (Low/Medium/High) | Random Forest |

The classification output directly feeds the **Dynamic Edge Weight Updater** — which is the bridge between ML and the C++ routing engine.

---

## 🧮 Feature Engineering

### Input Features

| Feature | Type | Description |
|---------|------|-------------|
| `hour` | int 0-23 | Hour of day — strongest predictor |
| `day_of_week` | int 0-6 | 0=Monday, 6=Sunday |
| `is_weekend` | bool | 1 if Sat/Sun |
| `is_holiday` | bool | 1 if public holiday |
| `month` | int 1-12 | Seasonal patterns |
| `temp_c` | float | Temperature (Bangalore avg 28°C) |
| `road_length_m` | float | Road segment length |
| `weather_*` | one-hot | 7 binary columns (Clear/Rain/Fog/...) |

### Target Variables

```python
# Regression target (continuous)
volume_pct = traffic_volume / max_capacity   # 0.0 to 1.0

# Classification target (categorical)
def congestion_label(volume_pct):
    if volume_pct < 0.35:  return "Low"     # green
    if volume_pct < 0.70:  return "Medium"  # yellow
    return "High"                            # red
```

### Feature Importance (Trained Model)

| Rank | Feature | Importance |
|------|---------|-----------|
| 1 | `hour` | **81.1%** |
| 2 | `day_of_week` | 6.9% |
| 3 | `is_weekend` | 6.2% |
| 4 | `road_length_m` | 1.9% |
| 5 | `weather_Clear` | 0.9% |

> The `hour` feature dominates because Bangalore has very sharp peak-hour patterns (7-9 AM, 5-7 PM).

---

## 🤖 Model 1: XGBoost Regressor

### Architecture
```python
xgb.XGBRegressor(
    n_estimators=200,     # 200 decision trees
    learning_rate=0.05,   # conservative learning rate
    max_depth=6,          # tree depth
    subsample=0.8,        # row sampling
    colsample_bytree=0.8  # feature sampling
)
```

### Why XGBoost?
- Handles mixed feature types (integers + floats + one-hots)
- Built-in regularization prevents overfitting
- Faster training than neural networks on tabular data
- Interpretable (feature importances)

### Results on Test Set (80/20 split)
| Metric | Value | Meaning |
|--------|-------|---------|
| R² | **0.9524** | 95.2% variance explained |
| RMSE | **0.0721** | ±7.2% volume error |
| MAE | **0.0568** | ±5.7% mean absolute error |

---

## 🌲 Model 2: Random Forest Classifier

### Architecture
```python
RandomForestClassifier(
    n_estimators=150,     # 150 decision trees (bagging ensemble)
    max_depth=12,
    min_samples_leaf=5,
    class_weight="balanced"  # handles class imbalance
)
```

### Why Random Forest?
- Ensemble of 150 trees → reduced variance via bagging
- `class_weight="balanced"` automatically handles unequal class distribution
- Highly interpretable feature importances
- Fast inference (< 1ms per prediction)

### Results on Test Set
| Class | Precision | Recall | F1-score | Support |
|-------|-----------|--------|----------|---------|
| Low | 0.97 | 0.93 | 0.95 | 7,080 |
| Medium | 0.79 | 0.80 | 0.80 | 6,046 |
| High | 0.88 | 0.91 | 0.90 | 8,474 |
| **Weighted Avg** | **0.89** | **0.89** | **0.89** | 21,600 |

**Overall Accuracy: 88.52%**

---

## 🔗 Prediction Pipeline

```
                    INPUT
          hour=8, weather=Rain, day=Monday
                        │
              ┌─────────▼──────────┐
              │   Feature Vector   │
              │ [8, 0, 0, 0, 9,    │
              │  28.0, 500.0,      │
              │  0, 0, 1, ...]     │
              └─────────┬──────────┘
                        │
              ┌─────────▼──────────┐
              │  Random Forest     │
              │  Classifier        │
              │  (150 trees)       │
              └─────────┬──────────┘
                        │
              Prediction: "High"
                        │
              ┌─────────▼──────────┐
              │  Congestion        │
              │  Multiplier Map    │
              │  High → 3.0×       │
              │  Medium → 1.6×     │
              │  Low → 1.0×        │
              └─────────┬──────────┘
                        │
              base_time × 3.0 = adjusted_time_weight
                        │
              ┌─────────▼──────────┐
              │  C++ A* Engine     │
              │  routes on         │
              │  adjusted weights  │
              └────────────────────┘
                        │
                   OPTIMAL ROUTE
```

---

## 📊 Why This Matters for Routing

Without ML-adjusted weights, A* finds the geometrically shortest path.
With ML weights, A* avoids congested roads even if they are shorter:

```
Without ML (peak hour, rainy day):
  Route: A → B → C → D  (shortest distance: 2.3 km, 4.2 min)
  But road B→C is highly congested → actual time: 12 min

With ML weights:
  Route: A → E → F → D  (longer distance: 3.1 km, 7.1 min)
  Roads are clear → actual time: 7.1 min  ← FASTER!
```

This is the core value proposition of SmartRoute.

---

## 🔮 Future ML Improvements

- **Real-time data:** Replace synthetic data with Google Maps Traffic API / TomTom
- **LSTM/Transformer:** Sequence model for time-series traffic forecasting
- **Reinforcement Learning:** Agent that learns optimal routing policy
- **Graph Neural Network:** Node-level congestion prediction using road network topology
- **Transfer Learning:** Pre-train on one city, fine-tune on another
