#!/usr/bin/env python3
"""
Console Battery Data Format (BDF) analyzer.

This script loads a BDF-style CSV file, normalizes known header variants,
estimates state-of-health (SOH), fits linear and SVR degradation models,
prints a textual report, and saves diagnostic plots.
"""

from __future__ import annotations

import argparse
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
    x = time_sec.reshape(-1, 1)
    model.fit(x, soh)
    pred = model.predict(x)
    metrics = {
        "r2": float(r2_score(soh, pred)),
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
    if "temperature_celsius" in df.columns:
        features["temperature_celsius"] = df["temperature_celsius"].fillna(25.0)
    else:
        features["temperature_celsius"] = 25.0

    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(features)

    model = SVR(kernel="rbf", C=10.0, epsilon=0.01)
    model.fit(x_scaled, soh)
    pred = model.predict(x_scaled)

    metrics = {
        "r2": float(r2_score(soh, pred)),
        "mae": float(mean_absolute_error(soh, pred)),
    }
    return model, scaler, metrics, pred


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


def run_analysis(input_file: Path, output_dir: Path, eol_soh: float) -> None:
    """Run complete BDF analysis pipeline and print a console report."""
    df = load_bdf(input_file)
    soh = compute_soh(df)

    linear_model, linear_metrics = fit_linear(df["test_time_second"].values, soh)
    rul_seconds = estimate_rul_seconds(
        linear_model=linear_model,
        current_time=float(df["test_time_second"].iloc[-1]),
        current_soh=float(soh[-1]),
        eol_soh=eol_soh,
    )

    _, _, svr_metrics, svr_pred = fit_svr(df, soh)
    saved_plots = save_plots(df, soh, linear_model, svr_pred, output_dir, eol_soh)

    print("=" * 60)
    print("BATTERY BDF CONSOLE ANALYSIS REPORT")
    print("=" * 60)
    print(f"Input file: {input_file}")
    print(f"Samples: {len(df)}")
    print(f"Time range: {df['test_time_second'].min():.1f} s -> {df['test_time_second'].max():.1f} s")
    if df["cycle_count"].notna().any():
        print(f"Cycle count range: {df['cycle_count'].min():.0f} -> {df['cycle_count'].max():.0f}")
    print()
    print("Current health")
    print(f"- Current SOH: {soh[-1]:.2f}%")
    print(f"- Minimum SOH: {np.min(soh):.2f}%")
    print(f"- Average SOH: {np.mean(soh):.2f}%")
    print()
    print("Linear degradation model")
    print(f"- R²: {linear_metrics['r2']:.4f}")
    print(f"- Slope: {linear_metrics['slope'] * 86400:.6f}% per day")
    print(f"- Estimated RUL to SOH {eol_soh:.0f}%: {format_duration(rul_seconds)}")
    print()
    print("SVR model")
    print(f"- R²: {svr_metrics['r2']:.4f}")
    print(f"- MAE: {svr_metrics['mae']:.4f}%")
    print()
    print("Saved plots")
    for path in saved_plots:
        print(f"- {path}")
    print("=" * 60)


def parse_args() -> argparse.Namespace:
    """Build and parse command-line arguments for console analysis."""
    parser = argparse.ArgumentParser(description="Console BDF battery analyzer")
    parser.add_argument("input_file", type=Path, help="Path to .csv or .bdf.csv file")
    parser.add_argument("--outdir", type=Path, default=Path("plots_bdf"), help="Directory to save PNG charts")
    parser.add_argument("--eol", type=float, default=70.0, help="End-of-life SOH threshold (default: 70)")
    return parser.parse_args()


def main() -> int:
    """Program entry point; handles SIGINT gracefully and returns exit code."""
    signal.signal(signal.SIGINT, signal.default_int_handler)
    args = parse_args()
    try:
        run_analysis(args.input_file, args.outdir, args.eol)
    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl+C).")
        return 130
    except BrokenPipeError:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
