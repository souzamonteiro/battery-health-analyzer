#!/usr/bin/env python3
"""Simple battery data collector that appends snapshots to a CSV file.

This script reads a small set of battery metrics from Linux sysfs and stores
them periodically in a CSV file for later analysis.

Collected fields:
- timestamp
- soh
- capacity
- cycle_count
- voltage
- status

The script runs continuously until interrupted with `Ctrl+C`.
"""

import csv
import time
from datetime import datetime

BAT_PATH = "/sys/class/power_supply/BAT0"
CSV_FILE = "battery_data.csv"
COLLECTION_INTERVAL_SECONDS = 60  # Collect data every 60 seconds


def read_sysfs(filename):
    """Read a single sysfs file from the battery directory.

    Parameters
    ----------
    filename:
        Name of the file inside the battery sysfs directory.

    Returns
    -------
    str | None
        File content without surrounding whitespace, or `None` on failure.
    """
    try:
        with open(f"{BAT_PATH}/{filename}", "r", encoding="utf-8") as file:
            return file.read().strip()
    except OSError:
        return None


def collect_data():
    """Collect a single battery data snapshot.

    Returns
    -------
    dict
        Dictionary containing timestamp, SOH estimate, and selected battery
        values read from sysfs.
    """
    energy_full = read_sysfs("energy_full")
    energy_design = read_sysfs("energy_full_design")

    soh = None
    if energy_full and energy_design:
        soh = (float(energy_full) / float(energy_design)) * 100

    return {
        "timestamp": datetime.now().isoformat(),
        "soh": soh,
        "capacity": read_sysfs("capacity"),
        "cycle_count": read_sysfs("cycle_count"),
        "voltage": read_sysfs("voltage_now"),
        "status": read_sysfs("status"),
    }


def main():
    """Start continuous battery data collection and append results to CSV."""
    print("Collecting battery data... Press Ctrl+C to stop.")

    header_written = False

    while True:
        data = collect_data()

        with open(CSV_FILE, "a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=data.keys())
            if not header_written:
                writer.writeheader()
                header_written = True
            writer.writerow(data)

        print(
            f"[{data['timestamp']}] SOH: {data['soh']:.1f}%"
            if data["soh"]
            else f"[{data['timestamp']}] SOH: N/A"
        )
        time.sleep(COLLECTION_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()