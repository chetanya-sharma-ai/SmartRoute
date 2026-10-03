"""
test_ml.py — ML Model Tests
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.ml_inference import MLInference


@pytest.fixture(scope="module")
def ml():
    return MLInference()


def test_rule_based_congestion_peak(ml):
    """Peak hour + Rain should return High congestion."""
    result = ml._rule_based_congestion(hour=8, weather="Rain")
    assert result == "High"


def test_rule_based_congestion_night(ml):
    """Night time + Clear should be Low."""
    result = ml._rule_based_congestion(hour=3, weather="Clear")
    assert result == "Low"


def test_predict_congestion_returns_valid_label(ml):
    cong = ml.predict_congestion(hour=8, day=0, weather="Clear")
    assert cong in ("Low", "Medium", "High")


def test_predict_single_edge(ml):
    result = ml.predict_single_edge(
        from_node=1, to_node=2, hour=8,
        weather="Rain", road_length_m=800.0
    )
    assert "congestion_level" in result
    assert "time_weight" in result
    assert result["time_weight"] > 0


def test_simulate_24h(ml):
    """predict_congestion_single should work for all 24 hours."""
    for hour in range(24):
        ctx = ml.predict_congestion_single(hour=hour, day=0, weather="Clear")
        assert "congestion_level" in ctx
        assert "multiplier" in ctx
        assert ctx["multiplier"] >= 1.0


def test_find_nearest_node_no_data(ml):
    """Returns None gracefully when nodes CSV not loaded."""
    if ml._nodes_df is None:
        result = ml.find_nearest_node(12.97, 77.59)
        assert result is None
    else:
        result = ml.find_nearest_node(12.97, 77.59)
        assert result is not None
        assert "node_id" in result
        assert "distance_m" in result
