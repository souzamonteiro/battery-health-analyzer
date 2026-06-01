#!/usr/bin/env python3
"""Battery data collector for Linux systems using the sysfs power interface.

This script reads battery information exposed by the Linux kernel in
`/sys/class/power_supply/` and exports snapshots to CSV, JSON, or both.

Main features:
- Automatic battery detection when the default `BAT0` path is unavailable.
- Collection of common battery metrics such as energy, charge, voltage,
  current, cycle count, status, and technology.
- Derived health metrics including `SOH` (State of Health) and remaining
  energy percentage when enough source data is available.
- Single-shot execution or continuous monitoring in a timed loop.

Typical usage:
    python3 collects_battery_data.py --once
    python3 collects_battery_data.py --loop --interval 60 --format both
"""

import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class BatteryDataCollector:
    """Collect battery metrics from Linux sysfs.

    Parameters
    ----------
    battery_path:
        Path to the battery device directory in sysfs. On most laptops,
        this is `/sys/class/power_supply/BAT0` or `/sys/class/power_supply/BAT1`.
    """

    STRING_FIELDS = {
        "status",
        "capacity_level",
        "health",
        "technology",
        "manufacturer",
        "model_name",
        "serial_number",
    }

    FILES_TO_READ = {
        "energy_now": "current_energy_wh",
        "energy_full": "current_full_energy_wh",
        "energy_full_design": "design_energy_wh",
        "charge_now": "current_charge_ah",
        "charge_full": "current_full_charge_ah",
        "charge_full_design": "design_charge_ah",
        "voltage_now": "current_voltage_v",
        "voltage_min_design": "design_min_voltage_v",
        "current_now": "current_a",
        "power_now": "power_w",
        "cycle_count": "cycle_count",
        "capacity": "capacity_percent",
        "capacity_level": "capacity_level",
        "status": "status",
        "health": "health",
        "technology": "technology",
        "manufacturer": "manufacturer",
        "model_name": "model_name",
        "serial_number": "serial_number",
    }

    def __init__(self, battery_path: str = "/sys/class/power_supply/BAT0") -> None:
        self.battery_path = Path(battery_path)
        self.valid = self._check_battery_exists()

    def _check_battery_exists(self) -> bool:
        """Validate the battery path and try automatic discovery if needed.

        Returns
        -------
        bool
            `True` if a battery device is available, otherwise `False`.
        """
        if self.battery_path.exists():
            return True

        print(f"ERROR: Battery not found at {self.battery_path}")
        power_supply_path = Path("/sys/class/power_supply/")

        if not power_supply_path.exists():
            return False

        batteries = [
            device
            for device in power_supply_path.iterdir()
            if (device / "type").exists()
            and (device / "type").read_text(encoding="utf-8").strip() == "Battery"
        ]

        if batteries:
            self.battery_path = batteries[0]
            print(f"Using auto-detected battery: {self.battery_path}")
            return True

        return False

    def _read_sysfs_file(self, filename: str, convert_to_float: bool = True) -> Optional[Any]:
        """Read a sysfs file from the battery directory.

        Parameters
        ----------
        filename:
            File name inside the battery sysfs directory.
        convert_to_float:
            When `True`, convert numeric values to `float`. String-like fields
            such as status or manufacturer should use `False`.

        Returns
        -------
        Optional[Any]
            Parsed value, or `None` if the file does not exist or cannot be read.

        Notes
        -----
        Several sysfs battery values are exposed in micro-units, such as:
        - micro-watt-hours
        - micro-ampere-hours
        - microvolts
        - microwatts

        For fields containing `now` or `full`, this function converts them to
        base units by dividing by 1,000,000.
        """
        filepath = self.battery_path / filename
        if not filepath.exists():
            return None

        try:
            content = filepath.read_text(encoding="utf-8").strip()
            if not convert_to_float:
                return content

            return (
                float(content) / 1_000_000.0
                if "now" in filename or "full" in filename
                else float(content)
            )
        except (ValueError, OSError) as error:
            print(f"Error reading {filename}: {error}")
            return None

    def get_battery_info(self) -> Dict[str, Any]:
        """Collect available battery information from sysfs.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing raw and derived battery metrics.
        """
        info: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "unix_timestamp": time.time(),
        }

        for sysfs_file, output_name in self.FILES_TO_READ.items():
            value = self._read_sysfs_file(
                sysfs_file,
                convert_to_float=sysfs_file not in self.STRING_FIELDS,
            )

            if value is not None:
                info[output_name] = value

        if "design_energy_wh" in info and "current_full_energy_wh" in info:
            soh = (info["current_full_energy_wh"] / info["design_energy_wh"]) * 100
            info["soh_percent"] = round(soh, 2)
        elif "design_charge_ah" in info and "current_full_charge_ah" in info:
            soh = (info["current_full_charge_ah"] / info["design_charge_ah"]) * 100
            info["soh_percent"] = round(soh, 2)
        else:
            info["soh_percent"] = None

        if "current_energy_wh" in info and "current_full_energy_wh" in info:
            remaining_energy_percent = (
                info["current_energy_wh"] / info["current_full_energy_wh"]
            ) * 100
            info["remaining_energy_percent"] = round(remaining_energy_percent, 2)

        return info

    def save_to_csv(self, data: Dict[str, Any], filename: str, is_first_write: bool = False) -> None:
        """Save a battery snapshot to a CSV file.

        Parameters
        ----------
        data:
            Dictionary containing the collected battery data.
        filename:
            Destination CSV file path.
        is_first_write:
            When `True`, overwrite the file and write a fresh header.
        """
        file_exists = Path(filename).exists()
        mode = "w" if is_first_write else "a"

        with open(filename, mode, newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=data.keys())
            if is_first_write or not file_exists:
                writer.writeheader()
            writer.writerow(data)

    def save_to_json(self, data: Dict[str, Any], filename: str, append: bool = False) -> None:
        """Save a battery snapshot to a JSON file.

        Parameters
        ----------
        data:
            Dictionary containing the collected battery data.
        filename:
            Destination JSON file path.
        append:
            When `True`, append the snapshot to an existing JSON array or convert
            an existing single object into a list before appending.
        """
        if append and Path(filename).exists():
            with open(filename, "r", encoding="utf-8") as file:
                existing_data = json.load(file)

            if isinstance(existing_data, list):
                existing_data.append(data)
            else:
                existing_data = [existing_data, data]

            with open(filename, "w", encoding="utf-8") as file:
                json.dump(existing_data, file, indent=2, ensure_ascii=False)
            return

        with open(filename, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)


def main() -> None:
    """Run the command-line battery collector."""
    parser = argparse.ArgumentParser(
        description="Collect battery data from Linux sysfs."
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously in a loop.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Interval between collections in seconds (default: 60).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="battery_data",
        help="Base name of the output file, without extension.",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json", "both"],
        default="both",
        help="Output format.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Collect data once and exit.",
    )

    args = parser.parse_args()
    collector = BatteryDataCollector()

    if not collector.valid:
        print("Error: No battery could be found on this system.")
        print(
            "Check whether the machine has a battery and whether you are running "
            "on real hardware rather than an unsupported environment such as WSL."
        )
        return

    print(f"Collecting battery data from: {collector.battery_path}")

    if args.once or not args.loop:
        data = collector.get_battery_info()

        print("\n=== BATTERY DATA ===")
        for key, value in data.items():
            if value is not None:
                print(f"{key}: {value}")

        if args.format in ["csv", "both"]:
            csv_file = f"{args.output}.csv"
            collector.save_to_csv(data, csv_file, is_first_write=True)
            print(f"\nData saved to: {csv_file}")

        if args.format in ["json", "both"]:
            json_file = f"{args.output}.json"
            collector.save_to_json(data, json_file, append=False)
            print(f"Data saved to: {json_file}")

        return

    print(f"Starting loop collection (interval: {args.interval} seconds)")
    print("Press Ctrl+C to stop")

    csv_file = f"{args.output}.csv"
    json_file = f"{args.output}.json"
    is_first_csv = True

    try:
        while True:
            data = collector.get_battery_info()

            soh_str = f"{data['soh_percent']}%" if data["soh_percent"] else "N/A"
            print(
                f"[{data['timestamp']}] SOH: {soh_str}, "
                f"Charge: {data.get('capacity_percent', 'N/A')}%, "
                f"Status: {data.get('status', 'N/A')}"
            )

            if args.format in ["csv", "both"]:
                collector.save_to_csv(data, csv_file, is_first_write=is_first_csv)
                is_first_csv = False

            if args.format in ["json", "both"]:
                collector.save_to_json(data, json_file, append=True)

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nCollection interrupted by user.")
        if args.format == "both":
            print(f"Data saved to: {csv_file} and {json_file}")
        elif args.format == "csv":
            print(f"Data saved to: {csv_file}")
        elif args.format == "json":
            print(f"Data saved to: {json_file}")


if __name__ == "__main__":
    main()