#!/usr/bin/env python3
"""
Console Battery Data Format (BDF) analyzer.

This script loads a BDF-style CSV file, normalizes known header variants,
estimates state-of-health (SOH), fits linear and SVR degradation models,
prints a textual report, and saves diagnostic plots.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import signal
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map known BDF and legacy header labels to canonical machine names."""
    column_map = {
        "Test Time / s": "test_time_second",
        "Voltage / V": "voltage_volt",
        "Current / A": "current_ampere",
        "Cycle Count / 1": "cycle_count",
        "Power / W": "power_watt",
        "Ambient Temperature / degC": "ambient_temperature_celsius",
        "Capacity / %": "capacity_percent",
        "Temperature / degC": "temperature_celsius",
        "Temperature / °C": "temperature_celsius",
        "Unix Time / s": "unix_time_second",
        "Step Capacity / Ah": "step_capacity_ah",
        "Step Energy / Wh": "step_energy_wh",
        "Step Index / 1": "step_index",
    }
    available_map = {src: dst for src, dst in column_map.items() if src in df.columns}
    return df.rename(columns=available_map) if available_map else df


def load_bdf(file_path: Path) -> pd.DataFrame:
    """
    Load, normalize, validate, and clean a BDF-like CSV file.

    Args:
        file_path: Path to the input CSV file.

    Returns:
        A validated DataFrame sorted by `test_time_second`.

    Raises:
        ValueError: If required BDF quantities are missing or no valid rows
        remain after numeric normalization.
    """
    df = pd.read_csv(file_path)
    df = normalize_columns(df)

    required = ["test_time_second", "voltage_volt", "current_ampere"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing BDF columns: {missing}")

    for col in ["unix_time_second", "cycle_count", "capacity_percent", "power_watt", "temperature_celsius"]:
        if col not in df.columns:
            df[col] = np.nan

    if "temperature_celsius" not in df.columns and "ambient_temperature_celsius" in df.columns:
        df["temperature_celsius"] = df["ambient_temperature_celsius"]

    df["test_time_second"] = pd.to_numeric(df["test_time_second"], errors="coerce")
    df["voltage_volt"] = pd.to_numeric(df["voltage_volt"], errors="coerce")
    df["current_ampere"] = pd.to_numeric(df["current_ampere"], errors="coerce")
    df["cycle_count"] = pd.to_numeric(df["cycle_count"], errors="coerce")
    df["capacity_percent"] = pd.to_numeric(df["capacity_percent"], errors="coerce")
    df["temperature_celsius"] = pd.to_numeric(df["temperature_celsius"], errors="coerce")

    # Treat non-finite values as missing before filtering rows.
    df = df.replace([np.inf, -np.inf], np.nan)

    df = df.dropna(subset=["test_time_second", "voltage_volt", "current_ampere"]).copy()
    if df.empty:
        raise ValueError("No valid rows after numeric normalization")

    return df.sort_values("test_time_second").reset_index(drop=True)


def compute_soh(df: pd.DataFrame) -> np.ndarray:
    """
    Compute a SOH time series.

    Preferred behavior uses `capacity_percent` directly when present. If not
    available, a fallback estimate is produced from absolute current throughput.
    """
    if df["capacity_percent"].notna().any():
        return df["capacity_percent"].ffill().fillna(100.0).values

    times = df["test_time_second"].values
    currents = df["current_ampere"].values

    dt = np.diff(times, prepend=times[0])
    dt = np.clip(dt, 0.0, None)
    ah_throughput = np.cumsum(np.abs(currents) * dt) / 3600.0

    max_ah = float(np.max(ah_throughput)) if len(ah_throughput) else 0.0
    if max_ah <= 0:
        return np.full(len(df), 100.0)

    soh = (max_ah - ah_throughput) / max_ah * 100.0
    return np.clip(soh, 0.0, 100.0)


def fit_linear(time_sec: np.ndarray, soh: np.ndarray) -> tuple[LinearRegression, dict]:
    """Fit a linear SOH-vs-time model and return model plus quality metrics."""
    model = LinearRegression()
    x = pd.to_numeric(pd.Series(time_sec), errors="coerce").replace([np.inf, -np.inf], np.nan)
    y = pd.to_numeric(pd.Series(soh), errors="coerce").replace([np.inf, -np.inf], np.nan)
    valid = x.notna() & y.notna()
    if int(valid.sum()) < 2:
        raise ValueError("Insufficient finite samples for linear fit")

    x_fit = x[valid].to_numpy().reshape(-1, 1)
    y_fit = y[valid].to_numpy()
    model.fit(x_fit, y_fit)
    pred = model.predict(x_fit)
    metrics = {
        "r2": float(r2_score(y_fit, pred)),
        "slope": float(model.coef_[0]),
        "intercept": float(model.intercept_),
    }
    return model, metrics


def estimate_rul_seconds(linear_model: LinearRegression, current_time: float, current_soh: float, eol_soh: float) -> float:
    """Estimate remaining time (seconds) to reach the SOH end-of-life threshold."""
    if current_soh <= eol_soh:
        return 0.0

    slope = float(linear_model.coef_[0])
    intercept = float(linear_model.intercept_)
    if slope >= 0:
        return float("inf")

    t_eol = (eol_soh - intercept) / slope
    return max(0.0, t_eol - current_time)


def fit_svr(df: pd.DataFrame, soh: np.ndarray) -> tuple[SVR, StandardScaler, dict, np.ndarray]:
    """Train an SVR model for SOH and return fitted artifacts and metrics."""
    features = df[["test_time_second", "voltage_volt", "current_ampere"]].copy()
    features["test_time_second"] = pd.to_numeric(features["test_time_second"], errors="coerce")
    features["voltage_volt"] = pd.to_numeric(features["voltage_volt"], errors="coerce")
    features["current_ampere"] = pd.to_numeric(features["current_ampere"], errors="coerce")

    if "temperature_celsius" in df.columns:
        features["temperature_celsius"] = pd.to_numeric(df["temperature_celsius"], errors="coerce")
    else:
        features["temperature_celsius"] = 25.0

    features = features.replace([np.inf, -np.inf], np.nan)
    features["test_time_second"] = features["test_time_second"].interpolate(limit_direction="both").fillna(0.0)
    features["voltage_volt"] = features["voltage_volt"].ffill().bfill().fillna(3.7)
    features["current_ampere"] = features["current_ampere"].ffill().bfill().fillna(0.0)
    features["temperature_celsius"] = features["temperature_celsius"].ffill().bfill().fillna(25.0)

    y = pd.to_numeric(pd.Series(soh), errors="coerce").replace([np.inf, -np.inf], np.nan)
    y = y.ffill().bfill().fillna(100.0).to_numpy()

    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(features)

    model = SVR(kernel="rbf", C=10.0, epsilon=0.01)
    model.fit(x_scaled, y)
    pred = model.predict(x_scaled)

    metrics = {
        "r2": float(r2_score(y, pred)),
        "mae": float(mean_absolute_error(y, pred)),
    }
    return model, scaler, metrics, pred


def predict_future_svr(
    df: pd.DataFrame,
    model: SVR,
    scaler: StandardScaler,
    future_days: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Project future SOH using last known operating conditions and time progression."""
    horizon_seconds = max(0.0, future_days * 86400.0)

    features = df[["test_time_second", "voltage_volt", "current_ampere"]].copy()
    features["test_time_second"] = pd.to_numeric(features["test_time_second"], errors="coerce")
    features["voltage_volt"] = pd.to_numeric(features["voltage_volt"], errors="coerce")
    features["current_ampere"] = pd.to_numeric(features["current_ampere"], errors="coerce")

    if "temperature_celsius" in df.columns:
        features["temperature_celsius"] = pd.to_numeric(df["temperature_celsius"], errors="coerce")
    else:
        features["temperature_celsius"] = 25.0

    features = features.replace([np.inf, -np.inf], np.nan)
    features["test_time_second"] = features["test_time_second"].interpolate(limit_direction="both").fillna(0.0)
    features["voltage_volt"] = features["voltage_volt"].ffill().bfill().fillna(3.7)
    features["current_ampere"] = features["current_ampere"].ffill().bfill().fillna(0.0)
    features["temperature_celsius"] = features["temperature_celsius"].ffill().bfill().fillna(25.0)

    last = features.iloc[-1]
    last_time = float(last["test_time_second"])
    future_times = np.linspace(last_time, last_time + horizon_seconds, num=100)

    x_future = pd.DataFrame(
        {
            "test_time_second": future_times,
            "voltage_volt": float(last["voltage_volt"]),
            "current_ampere": float(last["current_ampere"]),
            "temperature_celsius": float(last["temperature_celsius"]),
        }
    )

    x_future_scaled = scaler.transform(x_future)
    soh_future = model.predict(x_future_scaled)
    return future_times, soh_future


def estimate_svr_rul_seconds(
    df: pd.DataFrame,
    model: SVR,
    scaler: StandardScaler,
    eol_soh: float,
    future_days: float,
) -> float | None:
    """Estimate SVR-based RUL by finding first forecast time crossing EOL SOH."""
    future_times, soh_future = predict_future_svr(df, model, scaler, future_days)
    if len(future_times) == 0:
        return None

    current_time = float(df["test_time_second"].iloc[-1])
    below = np.where(soh_future <= eol_soh)[0]
    if len(below) == 0:
        return None

    t_eol = float(future_times[below[0]])
    return max(0.0, t_eol - current_time)


def save_plots(df: pd.DataFrame, soh: np.ndarray, linear_model: LinearRegression, svr_pred: np.ndarray, output_dir: Path, eol_soh: float) -> list[Path]:
    """Render and save analysis plots to `output_dir`, returning created paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    time_sec = df["test_time_second"].values
    linear_pred = linear_model.predict(time_sec.reshape(-1, 1))

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(time_sec, soh, "b.", markersize=3, label="Observed SOH")
    ax.plot(time_sec, linear_pred, "r-", linewidth=1.5, label="Linear fit")
    ax.axhline(y=eol_soh, color="g", linestyle="--", label=f"EOL ({eol_soh:.0f}%)")
    ax.set_xlabel("Test Time (s)")
    ax.set_ylabel("SOH (%)")
    ax.set_title("SOH and Linear Degradation Trend")
    ax.grid(True, alpha=0.3)
    ax.legend()
    p1 = output_dir / "soh_linear.png"
    fig.tight_layout()
    fig.savefig(p1, dpi=150)
    plt.close(fig)
    saved.append(p1)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(time_sec, soh, "b.", markersize=3, label="Observed SOH")
    ax.plot(time_sec, svr_pred, "m-", linewidth=1.5, label="SVR fit")
    ax.axhline(y=eol_soh, color="g", linestyle="--", label=f"EOL ({eol_soh:.0f}%)")
    ax.set_xlabel("Test Time (s)")
    ax.set_ylabel("SOH (%)")
    ax.set_title("SOH and SVR Fit")
    ax.grid(True, alpha=0.3)
    ax.legend()
    p2 = output_dir / "soh_svr.png"
    fig.tight_layout()
    fig.savefig(p2, dpi=150)
    plt.close(fig)
    saved.append(p2)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(soh, bins=25, color="#4c78a8", edgecolor="black", alpha=0.8)
    ax.axvline(np.mean(soh), color="red", linestyle="--", label=f"Mean {np.mean(soh):.2f}%")
    ax.axvline(soh[-1], color="green", linestyle="--", label=f"Current {soh[-1]:.2f}%")
    ax.set_xlabel("SOH (%)")
    ax.set_ylabel("Count")
    ax.set_title("SOH Distribution")
    ax.grid(True, alpha=0.25)
    ax.legend()
    p3 = output_dir / "soh_distribution.png"
    fig.tight_layout()
    fig.savefig(p3, dpi=150)
    plt.close(fig)
    saved.append(p3)

    return saved


def format_duration(seconds: float) -> str:
    """Format seconds into a compact human-readable duration string."""
    if math.isinf(seconds):
        return "∞ (no degradation trend toward EOL)"
    days = seconds / 86400.0
    years = days / 365.0
    if years >= 1:
        return f"{days:.1f} days ({years:.2f} years)"
    return f"{days:.1f} days"


def _json_safe(value):
    """Convert NumPy/Pandas/path values into JSON-safe primitives."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        if math.isinf(float(value)):
            return "inf" if float(value) > 0 else "-inf"
        if math.isnan(float(value)):
            return None
        return float(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def build_report(
    input_file: Path,
    df: pd.DataFrame,
    soh: np.ndarray,
    linear_metrics: dict,
    rul_seconds: float,
    svr_metrics: dict,
    svr_rul_seconds: float | None,
    svr_days: float,
    eol_soh: float,
    saved_plots: list[Path],
) -> dict:
    """Build a structured report dictionary for text and JSON output."""
    report = {
        "input_file": str(input_file),
        "samples": int(len(df)),
        "time_range_seconds": {
            "start": float(df["test_time_second"].min()),
            "end": float(df["test_time_second"].max()),
        },
        "cycle_count_range": None,
        "current_health": {
            "current_soh_percent": float(soh[-1]),
            "minimum_soh_percent": float(np.min(soh)),
            "average_soh_percent": float(np.mean(soh)),
        },
        "linear_model": {
            "r2": float(linear_metrics["r2"]),
            "slope_percent_per_day": float(linear_metrics["slope"] * 86400),
            "eol_threshold_percent": float(eol_soh),
            "rul_seconds": _json_safe(rul_seconds),
            "rul_human": format_duration(rul_seconds),
        },
        "svr_model": {
            "r2": float(svr_metrics["r2"]),
            "mae_percent": float(svr_metrics["mae"]),
            "forecast_horizon_days": float(svr_days),
            "eol_threshold_percent": float(eol_soh),
            "rul_seconds": _json_safe(svr_rul_seconds) if svr_rul_seconds is not None else None,
            "rul_human": format_duration(svr_rul_seconds) if svr_rul_seconds is not None else f"> {svr_days:.1f} days (within forecast horizon)",
        },
        "saved_plots": [str(path) for path in saved_plots],
    }

    if df["cycle_count"].notna().any():
        report["cycle_count_range"] = {
            "min": int(df["cycle_count"].min()),
            "max": int(df["cycle_count"].max()),
        }

    return _json_safe(report)


def print_text_report(report: dict) -> None:
    """Render the report dictionary in the original human-readable text format."""
    print("=" * 60)
    print("BATTERY BDF CONSOLE ANALYSIS REPORT")
    print("=" * 60)
    print(f"Input file: {report['input_file']}")
    print(f"Samples: {report['samples']}")
    tr = report["time_range_seconds"]
    print(f"Time range: {tr['start']:.1f} s -> {tr['end']:.1f} s")
    cc = report.get("cycle_count_range")
    if cc is not None:
        print(f"Cycle count range: {cc['min']} -> {cc['max']}")
    print()
    print("Current health")
    ch = report["current_health"]
    print(f"- Current SOH: {ch['current_soh_percent']:.2f}%")
    print(f"- Minimum SOH: {ch['minimum_soh_percent']:.2f}%")
    print(f"- Average SOH: {ch['average_soh_percent']:.2f}%")
    print()
    print("Linear degradation model")
    lm = report["linear_model"]
    print(f"- R²: {lm['r2']:.4f}")
    print(f"- Slope: {lm['slope_percent_per_day']:.6f}% per day")
    print(f"- Estimated RUL to SOH {lm['eol_threshold_percent']:.0f}%: {lm['rul_human']}")
    print()
    print("SVR model")
    sm = report["svr_model"]
    print(f"- R²: {sm['r2']:.4f}")
    print(f"- MAE: {sm['mae_percent']:.4f}%")
    print(f"- Estimated RUL to SOH {sm['eol_threshold_percent']:.0f}%: {sm['rul_human']}")
    print()
    print("Saved plots")
    for path in report["saved_plots"]:
        print(f"- {path}")
    print("=" * 60)


def run_analysis(input_file: Path, output_dir: Path, eol_soh: float, svr_days: float) -> dict:
    """Run complete BDF analysis pipeline and return a structured report."""
    df = load_bdf(input_file)
    soh = compute_soh(df)

    linear_model, linear_metrics = fit_linear(df["test_time_second"].values, soh)
    rul_seconds = estimate_rul_seconds(
        linear_model=linear_model,
        current_time=float(df["test_time_second"].iloc[-1]),
        current_soh=float(soh[-1]),
        eol_soh=eol_soh,
    )

    svr_model, svr_scaler, svr_metrics, svr_pred = fit_svr(df, soh)
    svr_rul_seconds = estimate_svr_rul_seconds(df, svr_model, svr_scaler, eol_soh=eol_soh, future_days=svr_days)
    saved_plots = save_plots(df, soh, linear_model, svr_pred, output_dir, eol_soh)
    return build_report(
        input_file=input_file,
        df=df,
        soh=soh,
        linear_metrics=linear_metrics,
        rul_seconds=rul_seconds,
        svr_metrics=svr_metrics,
        svr_rul_seconds=svr_rul_seconds,
        svr_days=svr_days,
        eol_soh=eol_soh,
        saved_plots=saved_plots,
    )


def expand_input_files(patterns: list[str]) -> list[Path]:
    """Expand file patterns (including wildcards) into a sorted unique file list."""
    resolved: list[Path] = []
    seen: set[str] = set()

    for pattern in patterns:
        matches: list[str] = []
        if any(ch in pattern for ch in "*?[]"):
            matches = glob.glob(pattern)
            if not matches and pattern.startswith("/"):
                root = Path("/")
                rel_pattern = pattern.lstrip("/")
                matches = [str(path) for path in root.glob(rel_pattern)]
        else:
            path = Path(pattern)
            if path.exists() and path.is_file():
                matches = [str(path)]
            else:
                matches = glob.glob(pattern)

        for match in matches:
            path = str(Path(match).resolve())
            if path not in seen and Path(path).is_file():
                seen.add(path)
                resolved.append(Path(path))

    return sorted(resolved)


def json_output_path(input_file: Path, json_dir: Path | None) -> Path:
    """Return output JSON path for an input file."""
    if json_dir is None:
        return input_file.with_suffix("").with_suffix(".json")
    json_dir.mkdir(parents=True, exist_ok=True)
    return json_dir / f"{input_file.stem}.json"


def save_json_report(report: dict, output_file: Path) -> None:
    """Persist report dictionary as UTF-8 JSON."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)


def parse_args() -> argparse.Namespace:
    """Build and parse command-line arguments for console analysis."""
    parser = argparse.ArgumentParser(description="Console BDF battery analyzer")
    parser.add_argument("input_files", nargs="+", help="Input file(s) or wildcard pattern(s), e.g. dataset/*.csv")
    parser.add_argument("--outdir", type=Path, default=Path("plots_bdf"), help="Directory to save PNG charts")
    parser.add_argument("--json", action="store_true", help="Write JSON report file(s) in addition to text output")
    parser.add_argument("--json-dir", type=Path, default=None, help="Optional directory for JSON report files")
    parser.add_argument("--eol", type=float, default=70.0, help="End-of-life SOH threshold (default: 70)")
    parser.add_argument("--svr-days", type=float, default=30.0, help="Future horizon in days for SVR EOL estimate (default: 30)")
    return parser.parse_args()


def main() -> int:
    """Program entry point; handles SIGINT gracefully and returns exit code."""
    signal.signal(signal.SIGINT, signal.default_int_handler)
    args = parse_args()
    try:
        input_files = expand_input_files(args.input_files)
        if not input_files:
            print("ERROR: No input files matched the provided pattern(s).", file=sys.stderr)
            return 2

        wildcard_mode = any(any(ch in pattern for ch in "*?[]") for pattern in args.input_files)
        is_batch = len(input_files) > 1
        for input_file in input_files:
            effective_outdir = args.outdir / input_file.stem if is_batch else args.outdir
            report = run_analysis(input_file, effective_outdir, args.eol, args.svr_days)
            print_text_report(report)

            if args.json or is_batch or wildcard_mode:
                out_json = json_output_path(input_file, args.json_dir)
                save_json_report(report, out_json)
                print(f"Saved JSON report: {out_json}")
    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl+C).")
        return 130
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
