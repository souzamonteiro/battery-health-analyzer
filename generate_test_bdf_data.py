#!/usr/bin/env python3
"""
Generate synthetic Battery Data Format (BDF) test datasets.

The generated file uses BDF preferred-label headers and simulates realistic
degradation behavior while keeping SOH above end-of-life by default.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def generate_synthetic_bdf(
    output_file: Path,
    samples: int = 3000,
    step_seconds: float = 60.0,
    start_soh: float = 99.0,
    end_soh: float = 82.0,
    seed: int = 42,
) -> Path:
    """
    Create a synthetic BDF CSV with smooth long-term degradation.

    The output is intended for analyzer validation and debugging, not for
    representing specific electrochemical cell chemistry.
    """
    if end_soh <= 70.0:
        raise ValueError("end_soh must be > 70 to avoid end-of-life in this test dataset")

    rng = np.random.default_rng(seed)

    test_time = np.arange(samples, dtype=float) * step_seconds
    unix_start = 1760000000
    unix_time = unix_start + test_time

    progress = np.linspace(0.0, 1.0, samples)
    degradation_curve = start_soh - (start_soh - end_soh) * (progress ** 1.05)
    local_wobble = 0.15 * np.sin(progress * 20.0 * np.pi)
    noise = rng.normal(0.0, 0.08, size=samples)
    capacity_percent = np.clip(degradation_curve + local_wobble + noise, end_soh, start_soh)

    cycle_count = np.floor(progress * 420).astype(int)

    phase = progress * 16 * np.pi
    current_ampere = 0.9 * np.sin(phase) + rng.normal(0.0, 0.05, size=samples)
    current_ampere = np.clip(current_ampere, -1.6, 1.6)

    nominal_voltage = 3.9
    voltage_volt = nominal_voltage - (100.0 - capacity_percent) * 0.005 + 0.04 * np.cos(phase * 0.7)
    voltage_volt += rng.normal(0.0, 0.01, size=samples)
    voltage_volt = np.clip(voltage_volt, 3.3, 4.25)

    power_watt = voltage_volt * current_ampere

    temperature_celsius = 28.0 + 2.0 * np.sin(phase * 0.3) + 0.8 * np.abs(current_ampere)
    temperature_celsius += rng.normal(0.0, 0.2, size=samples)
    temperature_celsius = np.clip(temperature_celsius, 22.0, 42.0)

    df = pd.DataFrame(
        {
            "Test Time / s": test_time,
            "Unix Time / s": unix_time.astype(int),
            "Voltage / V": np.round(voltage_volt, 4),
            "Current / A": np.round(current_ampere, 4),
            "Cycle Count / 1": cycle_count,
            "Capacity / %": np.round(capacity_percent, 4),
            "Power / W": np.round(power_watt, 4),
            "Ambient Temperature / degC": np.round(temperature_celsius, 4),
        }
    )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False)
    return output_file


def parse_args() -> argparse.Namespace:
    """Parse command-line options for synthetic BDF generation."""
    parser = argparse.ArgumentParser(description="Generate synthetic BDF battery data")
    parser.add_argument("--output", type=Path, default=Path("battery_test_degradation.bdf.csv"), help="Output CSV path.")
    parser.add_argument("--samples", type=int, default=3000, help="Number of time-series samples.")
    parser.add_argument("--step-seconds", type=float, default=60.0, help="Sampling interval in seconds.")
    parser.add_argument("--start-soh", type=float, default=99.0, help="Initial SOH percentage.")
    parser.add_argument("--end-soh", type=float, default=82.0, help="Final SOH percentage (must be > 70).")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    return parser.parse_args()


def main() -> int:
    """Program entry point for synthetic BDF file generation."""
    args = parse_args()
    out = generate_synthetic_bdf(
        output_file=args.output,
        samples=args.samples,
        step_seconds=args.step_seconds,
        start_soh=args.start_soh,
        end_soh=args.end_soh,
        seed=args.seed,
    )
    print(f"Generated synthetic BDF dataset: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
