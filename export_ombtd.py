#!/usr/bin/env python3
"""
OMBTD v1.0 Exporter
====================
Reads analysis jobs from runtime/analyses/ and produces the four OMBTD CSV
tables without modifying any collector or analysis code:

  devices.csv   – anonymized device metadata
  sessions.csv  – one row per job / session
  telemetry.csv – raw battery telemetry (relative timestamps only)
  labels.csv    – derived metrics from Battery Health Analyzer

Usage:
  python3 export_ombtd.py [--analyses-dir PATH] [--out-dir PATH] [--salt TEXT]

Environment variables override defaults:
  OMBTD_ANALYSES_DIR   path to runtime/analyses  (default: runtime/analyses)
  OMBTD_OUT_DIR        output directory           (default: ombtd_export)
  DATASET_SALT / OMBTD_DATASET_SALT  hashing salt (required in production)
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.0"

DEVICES_COLS = [
    "device_id",
    "manufacturer",
    "brand",
    "model",
    "hardware",
    "android_version",
    "android_api_level",
    "first_seen",
    "last_seen",
]

SESSIONS_COLS = [
    "session_id",
    "device_id",
    "start_time_relative",
    "duration_seconds",
    "sample_count",
    "cycle_count_min",
    "cycle_count_max",
]

TELEMETRY_COLS = [
    "session_id",
    "time_s",
    "voltage_v",
    "current_a",
    "power_w",
    "temperature_c",
    "soc_percent",
    "cycle_count",
    "charging_status",
    "plugged_state",
]

LABELS_COLS = [
    "session_id",
    "soh_current_percent",
    "soh_min_percent",
    "soh_mean_percent",
    "linear_r2",
    "linear_slope_percent_per_day",
    "svr_r2",
    "svr_mae_percent",
    "estimated_rul_days",
    "eol_threshold_percent",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_SALT = "change-this-dataset-salt"


def _make_public_device_id(telemetry_device_id: str, salt: str) -> str:
    """Return dev_<12-hex> derived from (telemetry_device_id, salt)."""
    h = hashlib.sha256(f"{telemetry_device_id}:{salt}".encode()).hexdigest()
    return f"dev_{h[:12]}"


def _make_session_id(job_dir_name: str, salt: str) -> str:
    """Return sess_<12-hex> derived from job directory name."""
    h = hashlib.sha256(f"{job_dir_name}:{salt}".encode()).hexdigest()
    return f"sess_{h[:12]}"


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Column detection – BDF collector CSV vs Microsoft test-bench CSV
# ---------------------------------------------------------------------------

# BDF collector columns (from battery_bdf_collector.py)
_BDF_REQUIRED = {"Test Time / s", "Voltage / V", "Current / A", "Capacity / %"}
# Microsoft test-bench columns
_MSFT_REQUIRED = {"Test Time / s", "Voltage / V", "Current / A", "Cycle Count / 1"}
# Extra BDF columns present in Android collector output
_BDF_ANDROID_EXTRAS = {"Unix Time / s", "Ambient Temperature / degC"}


def _detect_csv_format(headers: list[str]) -> str:
    header_set = set(headers)
    if "Capacity / %" in header_set:
        return "bdf_android"
    if "Cycle Count / 1" in header_set:
        return "msft_testbench"
    return "unknown"


def _col(row: dict, *keys: str, default=""):
    for k in keys:
        if k in row and row[k] not in ("", None):
            return row[k]
    return default


# ---------------------------------------------------------------------------
# BDF-specific: infer charging_status and plugged_state from available columns
# ---------------------------------------------------------------------------

def _infer_charging_status(row: dict, fmt: str) -> str:
    """Best-effort charging status from available data."""
    current = _safe_float(_col(row, "Current / A", default="0"))
    if fmt == "bdf_android":
        # Positive current = charging on Android BDF convention
        if current > 0.01:
            return "CHARGING"
        if current < -0.01:
            return "DISCHARGING"
        return "FULL"
    # MSFT test bench: rely on sign convention as well
    if current > 0.01:
        return "CHARGING"
    if current < -0.01:
        return "DISCHARGING"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# CSV reader that handles a single telemetry CSV file
# ---------------------------------------------------------------------------

def _read_telemetry_csv(csv_path: Path):
    """Return (rows, fmt) where rows is list[dict] with raw column values."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        fmt = _detect_csv_format(headers)
        for row in reader:
            rows.append(dict(row))
    return rows, fmt


def _build_telemetry_rows(session_id: str, csv_path: Path):
    """Convert raw CSV rows to OMBTD telemetry dicts."""
    raw_rows, fmt = _read_telemetry_csv(csv_path)
    out = []
    for raw in raw_rows:
        time_s = _safe_float(_col(raw, "Test Time / s"))
        voltage_v = _safe_float(_col(raw, "Voltage / V"))
        current_a = _safe_float(_col(raw, "Current / A"))
        power_w = _safe_float(_col(raw, "Power / W"))
        temperature_c = _safe_float(_col(raw, "Ambient Temperature / degC", default="0"))
        soc_percent = _safe_int(_col(raw, "Capacity / %", default="0"))
        cycle_count = _safe_int(_col(raw, "Cycle Count / 1", default="0"))
        charging_status = _infer_charging_status(raw, fmt)
        plugged_state = 0  # not available in CSV; default to unplugged

        out.append({
            "session_id": session_id,
            "time_s": round(time_s, 6),
            "voltage_v": round(voltage_v, 6),
            "current_a": round(current_a, 6),
            "power_w": round(power_w, 6),
            "temperature_c": round(temperature_c, 4),
            "soc_percent": soc_percent,
            "cycle_count": cycle_count,
            "charging_status": charging_status,
            "plugged_state": plugged_state,
        })
    return out


# ---------------------------------------------------------------------------
# Session + labels from report JSON
# ---------------------------------------------------------------------------

def _build_session_and_labels(session_id: str, device_id: str, report: dict, telemetry_rows: list):
    n = len(telemetry_rows)
    duration = round(telemetry_rows[-1]["time_s"] - telemetry_rows[0]["time_s"], 3) if n > 1 else 0.0
    cycle_counts = [r["cycle_count"] for r in telemetry_rows]

    session = {
        "session_id": session_id,
        "device_id": device_id,
        "start_time_relative": 0.0,
        "duration_seconds": duration,
        "sample_count": n,
        "cycle_count_min": min(cycle_counts) if cycle_counts else 0,
        "cycle_count_max": max(cycle_counts) if cycle_counts else 0,
    }

    current_health = report.get("current_health", {})
    linear = report.get("linear_model", {})
    svr = report.get("svr_model", {})

    rul_s = _safe_float(linear.get("rul_seconds", 0))
    rul_days = round(rul_s / 86400.0, 4) if rul_s > 0 else 0.0

    labels = {
        "session_id": session_id,
        "soh_current_percent": round(_safe_float(current_health.get("current_soh_percent", 0.0)), 6),
        "soh_min_percent": round(_safe_float(current_health.get("minimum_soh_percent", 0.0)), 6),
        "soh_mean_percent": round(_safe_float(current_health.get("average_soh_percent", 0.0)), 6),
        "linear_r2": round(_safe_float(linear.get("r2", 0.0)), 8),
        "linear_slope_percent_per_day": round(_safe_float(linear.get("slope_percent_per_day", 0.0)), 8),
        "svr_r2": round(_safe_float(svr.get("r2", 0.0)), 8),
        "svr_mae_percent": round(_safe_float(svr.get("mae_percent", 0.0)), 8),
        "estimated_rul_days": rul_days,
        "eol_threshold_percent": round(_safe_float(linear.get("eol_threshold_percent", 70.0)), 2),
    }

    return session, labels


# ---------------------------------------------------------------------------
# Load device metadata from *.device.json in a job directory
# ---------------------------------------------------------------------------

def _load_device_metadata(job_dir: Path) -> dict:
    """Find and return the public device metadata JSON in a job directory."""
    # Prefer .device.json (public) over .device.private.json
    for candidate in sorted(job_dir.glob("*.device.json")):
        if not candidate.name.endswith(".device.private.json"):
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def _build_device_record(public_device_id: str, meta: dict, seen_date: str) -> dict:
    """Build a single devices.csv row from public metadata."""
    return {
        "device_id": public_device_id,
        "manufacturer": meta.get("manufacturer", "unknown"),
        "brand": meta.get("brand", "unknown"),
        "model": meta.get("model", "unknown"),
        "hardware": meta.get("hardware", "unknown"),
        "android_version": meta.get("osVersion", "unknown"),
        "android_api_level": meta.get("osApiLevel", 0),
        "first_seen": seen_date,
        "last_seen": seen_date,
    }


# ---------------------------------------------------------------------------
# Derive a device_id for jobs that have no metadata
# ---------------------------------------------------------------------------

def _fallback_device_id(job_dir_name: str, salt: str) -> str:
    h = hashlib.sha256(f"anon:{job_dir_name}:{salt}".encode()).hexdigest()
    return f"dev_{h[:12]}"


# ---------------------------------------------------------------------------
# Infer a "seen_date" from metadata timestamps or fallback to file mtime
# ---------------------------------------------------------------------------

def _infer_date(meta: dict, job_dir: Path) -> str:
    received_at = meta.get("receivedAt") or meta.get("capturedAt")
    if received_at:
        s = str(received_at)
        # ISO string e.g. 2026-06-06T21:32:12.684Z
        m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
        if m:
            return m.group(1)
        # Unix ms int
        try:
            ts = int(s) / 1000.0
            from datetime import datetime, timezone
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        except ValueError:
            pass
    # Fallback: directory mtime
    try:
        mtime = job_dir.stat().st_mtime
        from datetime import datetime, timezone
        return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return "1970-01-01"


# ---------------------------------------------------------------------------
# Main export function
# ---------------------------------------------------------------------------

def export(analyses_dir: Path, out_dir: Path, salt: str):
    if not analyses_dir.is_dir():
        print(f"ERROR: analyses_dir not found: {analyses_dir}", file=sys.stderr)
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)

    # Accumulate across all jobs
    devices: dict[str, dict] = {}   # device_id -> device row
    sessions: list[dict] = []
    telemetry_rows: list[dict] = []
    labels_rows: list[dict] = []

    job_dirs = sorted(d for d in analyses_dir.iterdir() if d.is_dir())
    if not job_dirs:
        print("No analysis jobs found.", file=sys.stderr)
        sys.exit(0)

    skipped = 0
    exported = 0

    for job_dir in job_dirs:
        # Find the report JSON (not *.device*.json)
        report_jsons = [
            f for f in job_dir.glob("*.json")
            if not f.name.endswith(".device.json")
            and not f.name.endswith(".device.private.json")
        ]
        if not report_jsons:
            skipped += 1
            continue

        # Find the telemetry CSV (first non-device json → same stem)
        report_path = report_jsons[0]
        csv_stem = report_path.stem  # e.g. battery_data.bdf
        csv_candidates = list(job_dir.glob(f"{csv_stem}.csv")) + list(job_dir.glob(f"{csv_stem}"))
        # Also accept .bdf.csv
        if not csv_candidates:
            csv_candidates = list(job_dir.glob("*.bdf.csv")) + list(job_dir.glob("*.csv"))
        csv_candidates = [c for c in csv_candidates if not c.name.endswith(".device.json")]
        if not csv_candidates:
            skipped += 1
            continue

        csv_path = csv_candidates[0]

        # Load report
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"WARN: cannot read report {report_path}: {e}", file=sys.stderr)
            skipped += 1
            continue

        # Load device metadata (may be empty dict if no metadata file)
        meta = _load_device_metadata(job_dir)
        seen_date = _infer_date(meta, job_dir)

        # Derive identifiers
        if meta.get("publicDeviceId"):
            device_id = meta["publicDeviceId"]
        elif meta.get("telemetryDeviceId"):
            device_id = _make_public_device_id(meta["telemetryDeviceId"], salt)
        else:
            device_id = _fallback_device_id(job_dir.name, salt)

        session_id = _make_session_id(job_dir.name, salt)

        # Build telemetry rows
        try:
            t_rows = _build_telemetry_rows(session_id, csv_path)
        except Exception as e:
            print(f"WARN: cannot read telemetry {csv_path}: {e}", file=sys.stderr)
            skipped += 1
            continue

        if not t_rows:
            skipped += 1
            continue

        # Build session and labels
        session, labels = _build_session_and_labels(session_id, device_id, report, t_rows)

        # Accumulate device record (merge first_seen / last_seen)
        if device_id in devices:
            existing = devices[device_id]
            existing["first_seen"] = min(existing["first_seen"], seen_date)
            existing["last_seen"] = max(existing["last_seen"], seen_date)
        else:
            devices[device_id] = _build_device_record(device_id, meta, seen_date)

        sessions.append(session)
        telemetry_rows.extend(t_rows)
        labels_rows.append(labels)
        exported += 1

    # Write devices.csv
    _write_csv(out_dir / "devices.csv", DEVICES_COLS, sorted(devices.values(), key=lambda r: r["device_id"]))
    # Write sessions.csv
    _write_csv(out_dir / "sessions.csv", SESSIONS_COLS, sessions)
    # Write telemetry.csv
    _write_csv(out_dir / "telemetry.csv", TELEMETRY_COLS, telemetry_rows)
    # Write labels.csv
    _write_csv(out_dir / "labels.csv", LABELS_COLS, labels_rows)

    # Write schema-version marker
    (out_dir / "OMBTD_VERSION").write_text(f"OMBTD_SCHEMA_VERSION={SCHEMA_VERSION}\n")

    print(f"Exported {exported} job(s) to {out_dir}/")
    print(f"  devices.csv   : {len(devices)} device(s)")
    print(f"  sessions.csv  : {len(sessions)} session(s)")
    print(f"  telemetry.csv : {len(telemetry_rows)} row(s)")
    print(f"  labels.csv    : {len(labels_rows)} label(s)")
    if skipped:
        print(f"  Skipped       : {skipped} incomplete job(s)")
    if salt == _DEFAULT_SALT:
        print(
            "\nWARNING: using default DATASET_SALT. "
            "Set DATASET_SALT env var or --salt before publishing.",
            file=sys.stderr,
        )


def _write_csv(path: Path, columns: list, rows: list):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Export OMBTD v1.0 dataset from Battery Health Analyzer runtime/analyses/"
    )
    parser.add_argument(
        "--analyses-dir",
        default=os.environ.get("OMBTD_ANALYSES_DIR", "runtime/analyses"),
        help="Path to runtime/analyses directory (default: runtime/analyses)",
    )
    parser.add_argument(
        "--out-dir",
        default=os.environ.get("OMBTD_OUT_DIR", "ombtd_export"),
        help="Output directory (default: ombtd_export)",
    )
    parser.add_argument(
        "--salt",
        default=os.environ.get("DATASET_SALT") or os.environ.get("OMBTD_DATASET_SALT") or _DEFAULT_SALT,
        help="Dataset salt for device ID hashing (override via DATASET_SALT env var)",
    )
    args = parser.parse_args()

    export(
        analyses_dir=Path(args.analyses_dir),
        out_dir=Path(args.out_dir),
        salt=args.salt,
    )


if __name__ == "__main__":
    main()
