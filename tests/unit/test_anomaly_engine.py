"""
Unit tests for backend.analytics.anomaly_engine.

All tests use plain Python lists — no OPC UA, no mocking required.
"""

import math
import time
import pytest

from backend.analytics.anomaly_engine import (
    compute_rolling_zscore,
    compute_modified_zscore_mad,
    compute_ewma_drift,
    compute_iso_vibration,
    run_full_anomaly_analysis,
)


# ---------------------------------------------------------------------------
# Method 1: Rolling Z-Score
# ---------------------------------------------------------------------------

class TestRollingZScore:
    def test_normal_reading(self):
        baseline = [70.0, 71.0, 69.5, 70.5, 71.0, 70.0, 69.0, 70.2]
        result = compute_rolling_zscore(baseline, 70.8)
        assert result["severity"] == "NORMAL"
        assert abs(result["z_score"]) < 2.0

    def test_critical_spike(self):
        baseline = [70.0, 71.0, 69.5, 70.5, 71.0, 70.0, 69.0, 70.2]
        result = compute_rolling_zscore(baseline, 120.0)  # Massive spike
        assert result["severity"] == "CRITICAL"
        assert abs(result["z_score"]) > 3.0

    def test_warning_threshold(self):
        baseline = [70.0, 71.0, 69.5, 70.5, 71.0, 70.0, 69.0, 70.2]
        mean = sum(baseline) / len(baseline)
        std = (sum((x - mean) ** 2 for x in baseline) / (len(baseline) - 1)) ** 0.5
        warning_value = mean + 2.5 * std  # Between 2.0 and 3.0
        result = compute_rolling_zscore(baseline, warning_value)
        assert result["severity"] == "WARNING"

    def test_insufficient_data(self):
        result = compute_rolling_zscore([1.0, 2.0], 3.0)
        assert result["severity"] == "INSUFFICIENT_DATA"

    def test_flat_signal(self):
        baseline = [50.0, 50.0, 50.0, 50.0, 50.0]
        result = compute_rolling_zscore(baseline, 50.0)
        assert result["severity"] == "FLAT_SIGNAL"


# ---------------------------------------------------------------------------
# Method 2: Modified Z-Score / MAD
# ---------------------------------------------------------------------------

class TestModifiedZScoreMAD:
    def test_normal_reading(self):
        baseline = [70.0, 71.0, 69.5, 70.5, 71.0, 70.0, 69.0, 70.2]
        result = compute_modified_zscore_mad(baseline, 70.5)
        assert result["severity"] == "NORMAL"

    def test_critical_outlier(self):
        baseline = [70.0, 71.0, 69.5, 70.5, 71.0, 70.0, 69.0, 70.2]
        result = compute_modified_zscore_mad(baseline, 150.0)  # Massive outlier
        assert result["severity"] == "CRITICAL"

    def test_noise_rejection(self):
        """A single-point glitch in baseline should NOT break the calculation."""
        baseline = [70.0, 71.0, 999.0, 70.5, 71.0, 70.0, 69.0, 70.2]  # 999 = glitch
        result = compute_modified_zscore_mad(baseline, 70.5)
        # MAD-based method should still report NORMAL for a valid current value
        assert result["severity"] in ("NORMAL", "WARNING")

    def test_flat_signal(self):
        baseline = [50.0, 50.0, 50.0, 50.0, 50.0]
        result = compute_modified_zscore_mad(baseline, 50.0)
        assert result["severity"] == "FLAT_SIGNAL"


# ---------------------------------------------------------------------------
# Method 3: EWMA & Drift
# ---------------------------------------------------------------------------

class TestEWMADrift:
    def test_stable_signal(self):
        values = [70.0 + (i % 3) * 0.2 for i in range(50)]
        base_epoch = time.time() - 3600 * 24
        timestamps = [base_epoch + i * 1800 for i in range(50)]  # 30-min intervals
        result = compute_ewma_drift(values, timestamps)
        assert result["severity"] == "STABLE"

    def test_rising_drift(self):
        """Simulate a linearly increasing temperature (thermal runaway)."""
        # +1.0°C per 30-min sample = +2.0°C/hr drift rate (exceeds default 1.5°C/hr threshold)
        values = [70.0 + i * 1.0 for i in range(50)]
        base_epoch = time.time() - 3600 * 24
        timestamps = [base_epoch + i * 1800 for i in range(50)]  # 30-min intervals
        result = compute_ewma_drift(values, timestamps)
        assert result["drift_direction"] == "RISING"
        assert result["drift_rate_per_hour"] > 1.5
        assert result["severity"] == "DRIFTING"

    def test_insufficient_samples(self):
        result = compute_ewma_drift([1.0, 2.0, 3.0], [100.0, 200.0, 300.0])
        assert result["severity"] == "INSUFFICIENT_DATA"

    def test_insufficient_timespan(self):
        values = [70.0] * 15
        timestamps = [100.0 + i * 10 for i in range(15)]  # Only 150 seconds
        result = compute_ewma_drift(values, timestamps)
        assert result["severity"] == "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# Method 4: ISO 10816 Vibration
# ---------------------------------------------------------------------------

class TestISOVibration:
    def test_zone_a_good(self):
        result = compute_iso_vibration([0.5, 0.8, 1.0, 0.7, 0.9])
        assert result["iso_zone"] == "A"
        assert result["severity"] == "NORMAL"

    def test_zone_c_warning(self):
        result = compute_iso_vibration([5.0, 6.0, 7.0, 5.5, 6.5])
        assert result["iso_zone"] == "C"
        assert result["severity"] == "WARNING"

    def test_zone_d_danger(self):
        result = compute_iso_vibration([12.0, 15.0, 13.0, 14.0, 11.5])
        assert result["iso_zone"] == "D"
        assert result["severity"] == "CRITICAL"

    def test_bearing_warning_crest_factor(self):
        """High crest factor with low RMS should trigger bearing_warning."""
        # Baseline smooth vibration (0.2 mm/s) with a sharp shock impulse (4.0 mm/s)
        # RMS ~ 0.91 mm/s (Zone A), Peak = 4.0 mm/s -> Crest Factor = 4.37 (> 3.5 threshold)
        values = [0.2] * 19 + [4.0]
        result = compute_iso_vibration(values)
        assert result["bearing_warning"] is True
        assert result["crest_factor"] > 3.5
        assert result["severity"] == "WARNING"

    def test_insufficient_data(self):
        result = compute_iso_vibration([1.0])
        assert result["severity"] == "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# Full Aggregate Analysis
# ---------------------------------------------------------------------------

class TestFullAnalysis:
    def test_vibration_runs_all_four_methods(self):
        values = [2.0, 2.1, 1.9, 2.0, 2.2, 1.8, 2.0, 2.1, 1.9, 2.0, 2.0]
        base_epoch = time.time() - 3600 * 12
        timestamps = [base_epoch + i * 3600 for i in range(11)]
        result = run_full_anomaly_analysis(values, timestamps, sensor_type="vibration")
        assert "rolling_zscore" in result["methods"]
        assert "modified_zscore_mad" in result["methods"]
        assert "ewma_drift" in result["methods"]
        assert "iso_vibration" in result["methods"]

    def test_temperature_skips_iso_vibration(self):
        values = [70.0, 71.0, 69.5, 70.5, 71.0, 70.0, 69.0, 70.2, 70.1, 70.3, 70.0]
        base_epoch = time.time() - 3600 * 12
        timestamps = [base_epoch + i * 3600 for i in range(11)]
        result = run_full_anomaly_analysis(values, timestamps, sensor_type="temperature")
        assert "rolling_zscore" in result["methods"]
        assert "modified_zscore_mad" in result["methods"]
        assert "ewma_drift" in result["methods"]
        assert "iso_vibration" not in result["methods"]

    def test_worst_severity_propagates(self):
        """If any method returns CRITICAL, overall severity should be CRITICAL."""
        values = [70.0, 71.0, 69.5, 70.5, 71.0, 70.0, 69.0, 70.2, 70.1, 70.3, 200.0]  # Last = spike
        base_epoch = time.time() - 3600 * 12
        timestamps = [base_epoch + i * 3600 for i in range(11)]
        result = run_full_anomaly_analysis(values, timestamps, sensor_type="temperature")
        assert result["overall_severity"] == "CRITICAL"

    def test_empty_data(self):
        result = run_full_anomaly_analysis([], [])
        assert result["overall_severity"] == "INSUFFICIENT_DATA"
