"""
Statistical Anomaly Detection Engine for Industrial Sensor Telemetry.

Implements 4 industry-standard methods using pure Python stdlib:
  1. Rolling Z-Score        (ISO 7870 / Six Sigma SPC)
  2. Modified Z-Score / MAD (NIST / ASTM E178)
  3. EWMA & Linear Drift    (ISO 11462 / Western Electric Rules)
  4. ISO Vibration RMS      (ISO 10816-1 / ISO 20816)

All functions are pure (no side effects, no I/O, no logging).
Inputs: plain Python list[float]. Outputs: plain Python dict.
"""

import math
import statistics
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants & Thresholds
# ---------------------------------------------------------------------------

# Z-Score severity thresholds (ISO 7870 / Six Sigma 3-Sigma Rule)
_ZSCORE_WARNING = 2.0
_ZSCORE_CRITICAL = 3.0

# Modified Z-Score severity thresholds (NIST / ASTM E178)
_MAD_WARNING = 2.5
_MAD_CRITICAL = 3.5
_MAD_CONSISTENCY_CONSTANT = 0.6745  # Phi^-1(0.75) for normal distribution

# EWMA parameters (ISO 11462 / Western Electric)
_EWMA_DEFAULT_ALPHA = 0.2  # 80% history, 20% latest
_EWMA_CONTROL_MULTIPLIER = 3.0  # L = 3.0 for control limits

# ISO 10816-1 Vibration Severity Zones (Class II: 15kW – 75kW machines, mm/s)
_ISO_ZONE_A_LIMIT = 1.8   # Good (newly commissioned)
_ISO_ZONE_B_LIMIT = 4.5   # Acceptable (unrestricted long-term)
_ISO_ZONE_C_LIMIT = 11.2  # Warning (restricted operation)
# >= 11.2 = Zone D (Danger / Immediate shutdown)

_CREST_FACTOR_BEARING_THRESHOLD = 3.5  # Bearing spalling early warning

# Minimum sample sizes for meaningful computation
_MIN_SAMPLES_ZSCORE = 5
_MIN_SAMPLES_EWMA = 10
_MIN_SAMPLES_VIBRATION = 3
_MIN_EWMA_SPAN_SECONDS = 3600  # 1 hour minimum timespan for drift


# ---------------------------------------------------------------------------
# Method 1: Rolling Z-Score (ISO 7870 / Six Sigma SPC)
# ---------------------------------------------------------------------------

def compute_rolling_zscore(
    values: List[float],
    current_value: float,
) -> Dict[str, Any]:
    """Compute the Rolling Z-Score of current_value against a baseline window.

    Formula:
        μ = (1/N) Σ xᵢ
        σ = sqrt((1/(N-1)) Σ (xᵢ - μ)²)
        Z = (x_current - μ) / σ

    :param values: Historical baseline readings (list of floats).
    :param current_value: The latest sensor reading to evaluate.
    :return: Dict with mean, std_dev, z_score, severity.
    """
    if len(values) < _MIN_SAMPLES_ZSCORE:
        return {
            "method": "rolling_zscore",
            "severity": "INSUFFICIENT_DATA",
            "detail": f"Need at least {_MIN_SAMPLES_ZSCORE} baseline samples, got {len(values)}.",
        }

    mean = statistics.mean(values)
    std_dev = statistics.stdev(values)  # Uses N-1 (sample std dev)

    if std_dev == 0.0:
        return {
            "method": "rolling_zscore",
            "mean": mean,
            "std_dev": 0.0,
            "z_score": 0.0,
            "severity": "FLAT_SIGNAL",
            "detail": "All baseline readings are identical (σ=0). Cannot compute Z-score.",
        }

    z_score = (current_value - mean) / std_dev

    if abs(z_score) > _ZSCORE_CRITICAL:
        severity = "CRITICAL"
    elif abs(z_score) > _ZSCORE_WARNING:
        severity = "WARNING"
    else:
        severity = "NORMAL"

    return {
        "method": "rolling_zscore",
        "mean": round(mean, 4),
        "std_dev": round(std_dev, 4),
        "z_score": round(z_score, 4),
        "severity": severity,
    }


# ---------------------------------------------------------------------------
# Method 2: Modified Z-Score via MAD (NIST / ASTM E178)
# ---------------------------------------------------------------------------

def compute_modified_zscore_mad(
    values: List[float],
    current_value: float,
) -> Dict[str, Any]:
    """Compute the Modified Z-Score using Median Absolute Deviation (MAD).

    Formula:
        x̃ = median(X)
        MAD = median(|xᵢ - x̃|)
        Mᵢ = 0.6745 × (xᵢ - x̃) / MAD

    The constant 0.6745 = Φ⁻¹(0.75) makes MAD a consistent estimator for σ.

    :param values: Historical baseline readings.
    :param current_value: The latest sensor reading to evaluate.
    :return: Dict with median, mad, modified_z_score, severity.
    """
    if len(values) < _MIN_SAMPLES_ZSCORE:
        return {
            "method": "modified_zscore_mad",
            "severity": "INSUFFICIENT_DATA",
            "detail": f"Need at least {_MIN_SAMPLES_ZSCORE} baseline samples, got {len(values)}.",
        }

    median_val = statistics.median(values)
    abs_deviations = [abs(x - median_val) for x in values]
    mad = statistics.median(abs_deviations)

    if mad == 0.0:
        return {
            "method": "modified_zscore_mad",
            "median": median_val,
            "mad": 0.0,
            "modified_z_score": 0.0,
            "severity": "FLAT_SIGNAL",
            "detail": "MAD is zero (all values near median). Cannot compute Modified Z-score.",
        }

    modified_z = _MAD_CONSISTENCY_CONSTANT * (current_value - median_val) / mad

    if abs(modified_z) > _MAD_CRITICAL:
        severity = "CRITICAL"
    elif abs(modified_z) > _MAD_WARNING:
        severity = "WARNING"
    else:
        severity = "NORMAL"

    return {
        "method": "modified_zscore_mad",
        "median": round(median_val, 4),
        "mad": round(mad, 4),
        "modified_z_score": round(modified_z, 4),
        "severity": severity,
    }


# ---------------------------------------------------------------------------
# Method 3: EWMA & Linear Drift Rate (ISO 11462 / Western Electric)
# ---------------------------------------------------------------------------

def compute_ewma_drift(
    values: List[float],
    timestamps_epoch: List[float],
    alpha: float = _EWMA_DEFAULT_ALPHA,
    drift_threshold_per_hour: float = 1.5,
) -> Dict[str, Any]:
    """Compute EWMA smoothed value and linear drift rate (slope per hour).

    EWMA Formula:
        S_t = α × x_t + (1 - α) × S_{t-1},  S_0 = x_0

    Drift Rate via OLS:
        β = (N Σ(tᵢxᵢ) - Σtᵢ Σxᵢ) / (N Σ(tᵢ²) - (Σtᵢ)²)
        Drift per hour = β × 3600

    :param values: Historical sensor readings (chronological order).
    :param timestamps_epoch: Corresponding Unix epoch timestamps (seconds).
    :param alpha: EWMA smoothing factor (default 0.2).
    :param drift_threshold_per_hour: Drift rate that triggers DRIFTING severity.
    :return: Dict with ewma_current, drift_rate_per_hour, drift_direction, severity.
    """
    n = len(values)

    if n < _MIN_SAMPLES_EWMA:
        return {
            "method": "ewma_drift",
            "severity": "INSUFFICIENT_DATA",
            "detail": f"Need at least {_MIN_SAMPLES_EWMA} samples, got {n}.",
        }

    # Check time span
    time_span = timestamps_epoch[-1] - timestamps_epoch[0]
    if time_span < _MIN_EWMA_SPAN_SECONDS:
        return {
            "method": "ewma_drift",
            "severity": "INSUFFICIENT_DATA",
            "detail": f"Time span too short ({time_span:.0f}s). Need at least {_MIN_EWMA_SPAN_SECONDS}s (1 hour).",
        }

    # --- Compute EWMA ---
    ewma = values[0]
    for i in range(1, n):
        ewma = alpha * values[i] + (1.0 - alpha) * ewma
    ewma_current = ewma
    ewma_baseline = statistics.mean(values[:max(n // 4, 1)])  # First 25% as baseline

    # --- Compute Linear Drift Rate (OLS Slope with Relative Timestamps for numerical stability) ---
    t0 = timestamps_epoch[0]
    t_rel = [t - t0 for t in timestamps_epoch]

    sum_t = sum(t_rel)
    sum_x = sum(values)
    sum_tx = sum(t * x for t, x in zip(t_rel, values))
    sum_t2 = sum(t * t for t in t_rel)

    denominator = n * sum_t2 - sum_t * sum_t
    if denominator == 0.0:
        slope = 0.0
    else:
        slope = (n * sum_tx - sum_t * sum_x) / denominator

    drift_per_hour = slope * 3600.0  # Convert from per-second to per-hour

    # Determine drift direction
    if drift_per_hour > 0.1:
        drift_direction = "RISING"
    elif drift_per_hour < -0.1:
        drift_direction = "FALLING"
    else:
        drift_direction = "STABLE"

    # Severity: DRIFTING if the absolute drift exceeds threshold
    if abs(drift_per_hour) > drift_threshold_per_hour:
        severity = "DRIFTING"
    else:
        severity = "STABLE"

    return {
        "method": "ewma_drift",
        "ewma_current": round(ewma_current, 4),
        "ewma_baseline": round(ewma_baseline, 4),
        "drift_rate_per_hour": round(drift_per_hour, 4),
        "drift_direction": drift_direction,
        "severity": severity,
    }


# ---------------------------------------------------------------------------
# Method 4: ISO 10816 Vibration RMS & Crest Factor
# ---------------------------------------------------------------------------

def compute_iso_vibration(
    values: List[float],
) -> Dict[str, Any]:
    """Evaluate vibration severity per ISO 10816-1 (Class II: 15kW–75kW machines).

    RMS Formula:
        v_RMS = sqrt((1/N) Σ vᵢ²)

    Crest Factor:
        CF = |v_peak| / v_RMS

    ISO 10816-1 Zones (mm/s):
        Zone A (Good):       v_RMS < 1.8
        Zone B (Acceptable): 1.8 ≤ v_RMS < 4.5
        Zone C (Warning):    4.5 ≤ v_RMS < 11.2
        Zone D (Danger):     v_RMS ≥ 11.2

    Crest Factor > 3.5 indicates bearing spalling even if RMS is normal.

    :param values: Vibration velocity readings in mm/s.
    :return: Dict with rms, peak, crest_factor, iso_zone, bearing_warning.
    """
    if len(values) < _MIN_SAMPLES_VIBRATION:
        return {
            "method": "iso_vibration",
            "severity": "INSUFFICIENT_DATA",
            "detail": f"Need at least {_MIN_SAMPLES_VIBRATION} vibration samples, got {len(values)}.",
        }

    # RMS velocity
    sum_squares = sum(v * v for v in values)
    rms = math.sqrt(sum_squares / len(values))

    # Peak and Crest Factor
    peak = max(abs(v) for v in values)
    crest_factor = peak / rms if rms > 0.0 else 0.0

    # ISO 10816-1 Zone classification
    if rms < _ISO_ZONE_A_LIMIT:
        iso_zone = "A"
        iso_zone_label = "Good"
        severity = "NORMAL"
    elif rms < _ISO_ZONE_B_LIMIT:
        iso_zone = "B"
        iso_zone_label = "Acceptable"
        severity = "NORMAL"
    elif rms < _ISO_ZONE_C_LIMIT:
        iso_zone = "C"
        iso_zone_label = "Warning - Restricted Operation"
        severity = "WARNING"
    else:
        iso_zone = "D"
        iso_zone_label = "Danger - Immediate Shutdown Required"
        severity = "CRITICAL"

    # Bearing spalling early warning (high crest factor with normal/acceptable RMS)
    bearing_warning = crest_factor > _CREST_FACTOR_BEARING_THRESHOLD

    # Upgrade severity if bearing warning is active
    if bearing_warning and severity == "NORMAL":
        severity = "WARNING"

    return {
        "method": "iso_vibration",
        "rms_mm_s": round(rms, 4),
        "peak_mm_s": round(peak, 4),
        "crest_factor": round(crest_factor, 4),
        "iso_zone": iso_zone,
        "iso_zone_label": iso_zone_label,
        "bearing_warning": bearing_warning,
        "severity": severity,
    }


# ---------------------------------------------------------------------------
# Aggregate: Full Multi-Method Analysis
# ---------------------------------------------------------------------------

# Severity ranking for determining "worst" severity across methods
_SEVERITY_RANK = {
    "NORMAL": 0,
    "STABLE": 0,
    "FLAT_SIGNAL": 0,
    "INSUFFICIENT_DATA": 0,
    "WARNING": 1,
    "DRIFTING": 2,
    "CRITICAL": 3,
}


def run_full_anomaly_analysis(
    values: List[float],
    timestamps_epoch: List[float],
    sensor_type: str = "general",
) -> Dict[str, Any]:
    """Run all applicable statistical methods and return a merged result.

    :param values: Historical sensor readings (chronological order).
    :param timestamps_epoch: Corresponding Unix epoch timestamps.
    :param sensor_type: One of 'temperature', 'pressure', 'vibration',
                        'speed', 'current', 'flow', 'general'.
    :return: Dict with per-method results and an overall severity.
    """
    if not values or len(values) < 2:
        return {
            "node_id": None,
            "sensor_type": sensor_type,
            "sample_count": len(values) if values else 0,
            "overall_severity": "INSUFFICIENT_DATA",
            "methods": {},
        }

    current_value = values[-1]
    baseline = values[:-1]  # All except the latest reading

    results: Dict[str, Any] = {}

    # Method 1: Rolling Z-Score (all sensor types)
    results["rolling_zscore"] = compute_rolling_zscore(baseline, current_value)

    # Method 2: Modified Z-Score / MAD (all sensor types)
    results["modified_zscore_mad"] = compute_modified_zscore_mad(baseline, current_value)

    # Method 3: EWMA & Drift (all sensor types)
    results["ewma_drift"] = compute_ewma_drift(values, timestamps_epoch)

    # Method 4: ISO Vibration (only for vibration sensors)
    if sensor_type == "vibration":
        results["iso_vibration"] = compute_iso_vibration(values)

    # Determine overall severity (worst across all methods)
    worst_severity = "NORMAL"
    worst_rank = 0
    for method_result in results.values():
        sev = method_result.get("severity", "NORMAL")
        rank = _SEVERITY_RANK.get(sev, 0)
        if rank > worst_rank:
            worst_rank = rank
            worst_severity = sev

    return {
        "sensor_type": sensor_type,
        "sample_count": len(values),
        "current_value": current_value,
        "overall_severity": worst_severity,
        "methods": results,
    }
