#!/usr/bin/env python3
"""
Collect battery telemetry and write Battery Data Format (BDF) CSV files.

This utility samples local system battery information (when available via `psutil`
and OS-specific sources) and stores rows using BDF preferred-label headers,
including required quantities:

- Test Time / s
- Voltage / V
- Current / A

and commonly useful recommended/optional quantities such as Unix Time, cycle
count, ambient temperature, power, and capacity percentage.

Supported platforms:
- Linux (best coverage via `/sys/class/power_supply/BAT0/...`)
- Windows (limited voltage support via WMI)
- macOS (best-effort voltage parsing via `pmset`)
"""

import time
import csv
from pathlib import Path
import platform
import sys
from datetime import datetime

try:
    import psutil
except ImportError:
    print("ERROR: psutil not installed. Run: pip install psutil")
    sys.exit(1)

class BDFBatteryCollector:
    """Real-time battery collector that emits rows in BDF-compatible CSV format."""

    # BDF preferred-label headers (human-readable canonical CSV headings).
    BDF_FIELDS = [
        "Test Time / s",
        "Unix Time / s",
        "Voltage / V",
        "Current / A",
        "Cycle Count / 1",
        "Ambient Temperature / degC",
        "Power / W",
        "Capacity / %"
    ]

    def __init__(self):
        """Initialize internal timers and state used during collection."""
        self.start_time = time.time()
        self.last_cycle = 0

    def get_battery_data(self):
        """
        Collect one battery snapshot and return it as a BDF-header dictionary.

        Returns:
            dict | None: A single normalized telemetry row, or `None` if battery
            data cannot be obtained from the current system.
        """
        data = {
            "Test Time / s": time.time() - self.start_time,
            "Unix Time / s": int(time.time())
        }

        try:
            battery = psutil.sensors_battery()
            if battery:
                data["Capacity / %"] = battery.percent
                data["Current / A"] = 0.0
                data["Power / W"] = 0.0

                # Attempt to get voltage, current, cycle count using platform-specific APIs
                data = self._add_platform_specific_data(data)

                # For BDF, current is positive during charge, negative during discharge
                if battery.power_plugged:
                    data["Current / A"] = abs(data.get("Current / A", 0.0))
                else:
                    data["Current / A"] = -abs(data.get("Current / A", 0.0))

                data["Voltage / V"] = max(3.0, data.get("Voltage / V", 3.7))
                data["Ambient Temperature / degC"] = data.get("Ambient Temperature / degC", 25.0)

                # Keep power aligned with measured voltage/current.
                data["Power / W"] = data["Voltage / V"] * data["Current / A"]

                # Simple cycle count heuristic
                if battery.percent < 20 and self.last_cycle != battery.percent:
                    self.last_cycle = battery.percent
                data["Cycle Count / 1"] = max(0, getattr(self, "cycle_counter", 0))

                return data
        except Exception:
            pass
        return None

    def _add_platform_specific_data(self, data):
        """
        Enrich a telemetry row with OS-specific battery signals when possible.

        Args:
            data (dict): Partially filled row dictionary.

        Returns:
            dict: The same dictionary updated with any successfully collected
            platform-specific fields.
        """
        system = platform.system()

        if system == "Linux":
            try:
                with open("/sys/class/power_supply/BAT0/voltage_now", "r") as f:
                    data["Voltage / V"] = int(f.read().strip()) / 1_000_000
                with open("/sys/class/power_supply/BAT0/current_now", "r") as f:
                    data["Current / A"] = abs(int(f.read().strip())) / 1_000_000
                with open("/sys/class/power_supply/BAT0/temp", "r") as f:
                    data["Ambient Temperature / degC"] = int(f.read().strip()) / 1000
            except:
                pass
        elif system == "Windows":
            try:
                import wmi
                c = wmi.WMI()
                for battery in c.Win32_Battery():
                    if hasattr(battery, 'Voltage'):
                        data["Voltage / V"] = battery.Voltage / 1000
                    break
            except:
                pass
        elif system == "Darwin":  # macOS
            try:
                output = __import__('subprocess').run(
                    ['pmset', '-g', 'batt'], capture_output=True, text=True).stdout
                for line in output.split('\n'):
                    if 'voltage' in line.lower():
                        import re
                        numbers = re.findall(r'\d+', line)
                        if numbers:
                            data["Voltage / V"] = int(numbers[0]) / 1000
            except:
                pass
        return data

    def save_to_bdf(self, data, output_file):
        """
        Append one telemetry row to a BDF CSV file.

        The header is written automatically if the target file does not yet
        exist.
        """
        file_path = Path(output_file)
        write_header = not file_path.exists()

        with open(file_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.BDF_FIELDS)
            if write_header:
                writer.writeheader()
            if data:
                # Fill missing fields with None
                row = {f: data.get(f, None) for f in self.BDF_FIELDS}
                writer.writerow(row)

    def run_once(self, output_file):
        """Collect a single snapshot and persist it to `output_file`."""
        data = self.get_battery_data()
        if data:
            self.save_to_bdf(data, output_file)
            print(f"✅ BDF data saved to {output_file}")
            for k in self.BDF_FIELDS:
                if k in data:
                    print(f"   {k}: {data[k]}")
        else:
            print("❌ No battery data available.")

    def run_loop(self, interval, output_file):
        """Continuously collect snapshots at a fixed interval until interrupted."""
        print(f"🔄 Collecting BDF data every {interval} seconds. Press Ctrl+C to stop.")
        try:
            while True:
                data = self.get_battery_data()
                if data:
                    self.save_to_bdf(data, output_file)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopped.")

def main():
    """CLI entry point for one-shot or continuous BDF collection."""
    import argparse
    p = argparse.ArgumentParser(
        description="Collect local battery telemetry and write BDF CSV output."
    )
    p.add_argument("--once", action="store_true", help="Collect one sample and exit.")
    p.add_argument("--loop", action="store_true", help="Collect continuously until Ctrl+C.")
    p.add_argument("--interval", type=int, default=60, help="Sampling interval in seconds for --loop mode.")
    p.add_argument("--output", "-o", default="battery_data.bdf.csv", help="Destination BDF CSV path.")
    args = p.parse_args()

    collector = BDFBatteryCollector()
    if args.once:
        collector.run_once(args.output)
    elif args.loop:
        collector.run_loop(args.interval, args.output)
    else:
        # Default to one-shot
        collector.run_once(args.output)

if __name__ == "__main__":
    main()