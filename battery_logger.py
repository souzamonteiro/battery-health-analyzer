#!/usr/bin/env python3
"""Battery history logger for Linux, macOS, and Windows.

The script appends one record to a CSV file using this schema:
    date,capacity_percent,source

`capacity_percent` can represent either:
- Battery health (default mode `--metric health`, recommended for forecast)
- Current charge level (`--metric charge`)

When the selected metric is unavailable on the host, the script applies
cross-metric fallback and marks the data source accordingly.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import platform
import re
import time
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional, Tuple

CSV_COLUMNS = ["date", "capacity_percent", "source"]
DEFAULT_LOG_FILE = Path(__file__).resolve().parent / "battery_history.csv"
MetricMode = Literal["health", "charge"]


class BatteryReadError(RuntimeError):
    """Raised when battery values cannot be collected from the OS."""


def _run_command(command: list[str]) -> str:
    """Run command and return stdout, raising BatteryReadError on failure."""
    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise BatteryReadError(f"Command not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise BatteryReadError(
            f"Command failed ({' '.join(command)}): {exc.stderr.strip()}"
        ) from exc
    return result.stdout


def _linux_battery_path() -> str:
    """Return first Linux battery sysfs path."""
    battery_paths = glob.glob("/sys/class/power_supply/BAT*")
    if not battery_paths:
        raise BatteryReadError("No battery entries found under /sys/class/power_supply/BAT*")
    return battery_paths[0]


def _linux_charge_percent(bat_path: str) -> Tuple[float, str]:
    """Return current Linux battery charge percentage."""
    capacity_path = os.path.join(bat_path, "capacity")
    if not os.path.exists(capacity_path):
        raise BatteryReadError("Linux battery capacity file was not found")

    try:
        with open(capacity_path, "r", encoding="utf-8") as f:
            capacity = float(f.read().strip())
    except OSError as exc:
        raise BatteryReadError(f"Failed to read Linux battery capacity: {exc}") from exc

    if 0 <= capacity <= 100:
        return capacity, "linux_sysfs_charge"

    raise BatteryReadError("Invalid battery capacity value read from Linux sysfs")


def _linux_health_percent(bat_path: str) -> Tuple[float, str]:
    """Return Linux battery health percentage (full/design)."""

    energy_full_path = os.path.join(bat_path, "energy_full")
    energy_design_path = os.path.join(bat_path, "energy_full_design")

    # Some systems expose charge_* totals instead of energy_* totals.
    if not os.path.exists(energy_full_path) or not os.path.exists(energy_design_path):
        energy_full_path = os.path.join(bat_path, "charge_full")
        energy_design_path = os.path.join(bat_path, "charge_full_design")

    try:
        with open(energy_full_path, "r", encoding="utf-8") as f:
            full = float(f.read().strip())
        with open(energy_design_path, "r", encoding="utf-8") as f:
            design = float(f.read().strip())
    except OSError as exc:
        raise BatteryReadError(f"Failed to read Linux battery files: {exc}") from exc

    if design <= 0:
        raise BatteryReadError("Invalid design capacity reported by Linux battery interface")

    return (full / design) * 100.0, "linux_sysfs_health"


def _linux_capacity_percent(metric: MetricMode) -> Tuple[float, str]:
    """Return Linux battery metric according to selected mode."""
    bat_path = _linux_battery_path()

    if metric == "charge":
        try:
            return _linux_charge_percent(bat_path)
        except BatteryReadError:
            health_percent, _ = _linux_health_percent(bat_path)
            return health_percent, "linux_sysfs_health_fallback"

    try:
        return _linux_health_percent(bat_path)
    except BatteryReadError:
        charge_percent, _ = _linux_charge_percent(bat_path)
        return charge_percent, "linux_sysfs_charge_fallback"


def _parse_macos_capacity_from_system_profiler(raw: str) -> Optional[Tuple[float, str]]:
    """Parse macOS battery health from system_profiler output."""
    # Example lines:
    #   Full Charge Capacity (mAh): 4820
    #   Design Capacity (mAh): 5103
    full_match = re.search(r"Full Charge Capacity \(mAh\):\s*(\d+)", raw)
    design_match = re.search(r"Design Capacity \(mAh\):\s*(\d+)", raw)
    if not full_match or not design_match:
        return None

    full = float(full_match.group(1))
    design = float(design_match.group(1))
    if design <= 0:
        return None

    return (full / design) * 100.0, "macos_system_profiler_health"


def _macos_health_percent() -> Tuple[float, str]:
    """Return battery health on macOS from system_profiler."""
    profiler_raw = _run_command(["system_profiler", "SPPowerDataType"])
    parsed = _parse_macos_capacity_from_system_profiler(profiler_raw)
    if parsed is None:
        raise BatteryReadError("Unable to parse macOS battery health from system_profiler output")
    return parsed


def _macos_charge_percent() -> Tuple[float, str]:
    """Return current battery charge percentage on macOS."""
    # pmset returns current charge percentage (not battery health).
    pmset_raw = _run_command(["pmset", "-g", "batt"])
    charge_match = re.search(r"(\d+)%", pmset_raw)
    if not charge_match:
        raise BatteryReadError("Unable to parse battery percentage from pmset output")

    return float(charge_match.group(1)), "macos_pmset_charge"


def _macos_capacity_percent(metric: MetricMode) -> Tuple[float, str]:
    """Return macOS battery metric according to selected mode."""
    if metric == "charge":
        try:
            return _macos_charge_percent()
        except BatteryReadError:
            health_percent, _ = _macos_health_percent()
            return health_percent, "macos_system_profiler_health_fallback"

    try:
        return _macos_health_percent()
    except BatteryReadError:
        charge_percent, _ = _macos_charge_percent()
        return charge_percent, "macos_pmset_charge_fallback"


def _powershell_json(command: str) -> list[dict]:
    """Execute a PowerShell command that outputs JSON and return parsed objects."""
    raw = _run_command(["powershell", "-NoProfile", "-Command", command])
    if not raw.strip():
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BatteryReadError("Failed to parse PowerShell JSON output") from exc

    if isinstance(parsed, dict):
        return [parsed]
    if isinstance(parsed, list):
        return parsed
    return []


def _windows_health_percent() -> Tuple[float, str]:
    """Return battery health on Windows using CIM battery classes."""
    try:
        full_entries = _powershell_json(
            "Get-CimInstance -Namespace root\\wmi -ClassName BatteryFullChargedCapacity "
            "| Select-Object FullChargedCapacity | ConvertTo-Json"
        )
    except BatteryReadError:
        full_entries = []

    try:
        design_entries = _powershell_json(
            "Get-CimInstance -Namespace root\\wmi -ClassName BatteryStaticData "
            "| Select-Object DesignedCapacity | ConvertTo-Json"
        )
    except BatteryReadError:
        design_entries = []

    if full_entries and design_entries:
        full = float(full_entries[0].get("FullChargedCapacity", 0) or 0)
        design = float(design_entries[0].get("DesignedCapacity", 0) or 0)
        if design > 0:
            return (full / design) * 100.0, "windows_cim_health"

    raise BatteryReadError("Windows battery health classes are unavailable")


def _windows_charge_percent() -> Tuple[float, str]:
    """Return current battery charge percentage on Windows."""

    charge_entries = _powershell_json(
        "Get-CimInstance -ClassName Win32_Battery "
        "| Select-Object EstimatedChargeRemaining | ConvertTo-Json"
    )
    if not charge_entries:
        raise BatteryReadError("Win32_Battery did not return data")

    charge = float(charge_entries[0].get("EstimatedChargeRemaining", 0) or 0)
    if charge <= 0:
        raise BatteryReadError("Windows battery charge percentage is unavailable")

    return charge, "windows_win32_charge"


def _windows_capacity_percent(metric: MetricMode) -> Tuple[float, str]:
    """Return Windows battery metric according to selected mode."""
    if metric == "charge":
        try:
            return _windows_charge_percent()
        except BatteryReadError:
            health_percent, _ = _windows_health_percent()
            return health_percent, "windows_cim_health_fallback"

    try:
        return _windows_health_percent()
    except BatteryReadError:
        charge_percent, _ = _windows_charge_percent()
        return charge_percent, "windows_win32_charge_fallback"


def get_battery_capacity_percent(metric: MetricMode = "health") -> Tuple[float, str]:
    """Dispatch battery collection by OS and return (percent, source)."""
    system = platform.system().lower()

    if metric not in ("health", "charge"):
        raise BatteryReadError(f"Unsupported metric mode: {metric}")

    if system == "linux":
        return _linux_capacity_percent(metric)
    if system == "darwin":
        return _macos_capacity_percent(metric)
    if system == "windows":
        return _windows_capacity_percent(metric)

    raise BatteryReadError(f"Unsupported operating system: {platform.system()}")


def append_to_csv(log_file: Path, date_value: datetime, capacity_percent: float, source: str) -> None:
    """Append one sample to CSV, creating the file with header if needed."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_exists = log_file.exists()

    with open(log_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(CSV_COLUMNS)
        writer.writerow([date_value.strftime("%Y-%m-%d %H:%M:%S"), f"{capacity_percent:.2f}", source])


def parse_args(argv: list[str]) -> argparse.Namespace:
    default_metric = os.environ.get("BATTERY_LOGGER_METRIC", "health").strip().lower() or "health"
    if default_metric not in ("health", "charge"):
        default_metric = "health"

    parser = argparse.ArgumentParser(description="Append one battery sample to CSV history.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_LOG_FILE,
        help=f"Output CSV path (default: {DEFAULT_LOG_FILE})",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Keep collecting samples in a loop until interrupted (Ctrl+C).",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=60.0,
        help="Seconds between samples when --loop is enabled (default: 60).",
    )
    parser.add_argument(
        "--metric",
        choices=["health", "charge"],
        default=default_metric,
        help=(
            "Metric to log: health (best for lifetime forecast) or charge "
            "(current battery level). Can also be set by BATTERY_LOGGER_METRIC."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.interval_seconds <= 0:
        print("Invalid --interval-seconds: value must be greater than zero.", file=sys.stderr)
        return 2

    def log_sample() -> None:
        capacity_percent, source = get_battery_capacity_percent(metric=args.metric)
        timestamp = datetime.now()
        append_to_csv(args.output, timestamp, capacity_percent, source)
        print(
            "Logged battery sample: "
            f"date={timestamp.strftime('%Y-%m-%d %H:%M:%S')} "
            f"capacity_percent={capacity_percent:.2f} source={source} "
            f"output={args.output}"
        )

    try:
        if args.loop:
            print(
                "Loop mode enabled. "
                f"Collecting every {args.interval_seconds:g}s with metric={args.metric}. Press Ctrl+C to stop."
            )
            while True:
                log_sample()
                time.sleep(args.interval_seconds)
        else:
            log_sample()
    except BatteryReadError as exc:
        print(f"Battery read failed: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Failed to write CSV file: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Stopped by user.")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
