In Ubuntu Linux, detailed battery charge and discharge data can be obtained through two main methods: the direct system interface `/sys/class/power_supply/` and the `upower` command-line tool.

### Method 1: Directly from the system via `/sys/class/power_supply/`

This is the most direct and low-level data source, because the kernel exposes battery information in this directory.

1.  **Find your battery**: First, identify your battery name. It is usually `BAT0` or `BAT1`.
    ```bash
    ls /sys/class/power_supply/
    ```

2.  **View all data at once**: The `uevent` file shows all information in an easy-to-read format.
    ```bash
    cat /sys/class/power_supply/BAT0/uevent
    ```
    The command above will show several lines, including:
    *   `POWER_SUPPLY_ENERGY_NOW` or `POWER_SUPPLY_CHARGE_NOW`: Current charge.
    *   `POWER_SUPPLY_ENERGY_FULL`: Charge when the battery is currently full.
    *   `POWER_SUPPLY_ENERGY_FULL_DESIGN`: Original factory charge.
    *   `POWER_SUPPLY_CAPACITY`: Current charge percentage.
    *   `POWER_SUPPLY_CYCLE_COUNT`: Number of full charge cycles.

3.  **Access individual files**: For scripts or monitoring, you can read specific files.
    *   **Current capacity (Wh or mAh)**: `cat /sys/class/power_supply/BAT0/energy_now`
    *   **Current total capacity (Wh or mAh)**: `cat /sys/class/power_supply/BAT0/energy_full`
    *   **Factory capacity (Wh or mAh)**: `cat /sys/class/power_supply/BAT0/energy_full_design`
    *   **Charge cycles**: `cat /sys/class/power_supply/BAT0/cycle_count`
    *   **Current voltage (microvolts)**: `cat /sys/class/power_supply/BAT0/voltage_now`

### Method 2: `upower` tool

`upower` is a service and command-line tool that abstracts power information, offering a more user-friendly and standardized view. It is the recommended method for quick checks.

1.  **Install it (usually already installed)**:
    ```bash
    sudo apt update
    sudo apt install upower
    ```

2.  **View full battery details**: Replace `BAT0` with your device name, found with `upower -e | grep BAT`.
    ```bash
    upower -i /org/freedesktop/UPower/devices/battery_BAT0
    ```
    The output will include:
    *   `energy-full`: Current full charge.
    *   `energy-full-design`: Factory charge.
    *   `energy-rate`: Energy consumption rate.
    *   `percentage`: Charge percentage.
    *   `capacity`: A battery health measure (`energy-full / energy-full-design`).

3.  **Monitor in real time**:
    To observe changes over time, use the command:
    ```bash
    upower --monitor-detail
    ```
    This command keeps running and shows updates whenever battery status changes (e.g., plugging/unplugging the charger, percentage changes).

### How to use this data to calculate Battery Health (SOH)

With the collected data, you can apply the formulas discussed earlier:

1.  **SOH by Capacity**: This is the most common metric.
    ```
    SOH (%) = (energy-full value / energy-full-design value) * 100
    ```
    *   `energy-full`: The maximum capacity the battery can store now.
    *   `energy-full-design`: The capacity the battery had when it left the factory.

    **Practical example**: If `energy-full-design` is 44000 mWh (44 Wh) and the current `energy-full` is 35000 mWh (35 Wh), then SOH is (35000/44000) * 100 = **79.5%**. A battery is generally considered near end-of-life when it reaches 70-80% SOH.

2.  **SOH by Charge Cycles**: Battery lifespan is also tied to cycle count.
    *   The `cycle_count` file in `/sys/class/power_supply/BAT0/` shows the total number of full cycles completed by the battery. Manufacturers often specify lifespan, for example, "500 cycles to 70% capacity."

### Creating a dataset for analysis

To estimate degradation over time, you need to collect data periodically. A simple script can do this:

```bash
#!/bin/bash
# script: collect_battery.sh
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
BAT_PATH="/sys/class/power_supply/BAT0"

ENERGY_NOW=$(cat $BAT_PATH/energy_now 2>/dev/null)
ENERGY_FULL=$(cat $BAT_PATH/energy_full 2>/dev/null)
ENERGY_FULL_DESIGN=$(cat $BAT_PATH/energy_full_design 2>/dev/null)
VOLTAGE_NOW=$(cat $BAT_PATH/voltage_now 2>/dev/null)
CYCLE_COUNT=$(cat $BAT_PATH/cycle_count 2>/dev/null)

# Converts micro/energy values to more readable units (optional)
ENERGY_NOW_WH=$(echo "scale=2; $ENERGY_NOW / 1000000" | bc)
ENERGY_FULL_WH=$(echo "scale=2; $ENERGY_FULL / 1000000" | bc)
ENERGY_FULL_DESIGN_WH=$(echo "scale=2; $ENERGY_FULL_DESIGN / 1000000" | bc)

# Calculates SOH
SOH=$(echo "scale=2; ($ENERGY_FULL / $ENERGY_FULL_DESIGN) * 100" | bc)

echo "$TIMESTAMP, $ENERGY_NOW_WH, $ENERGY_FULL_WH, $ENERGY_FULL_DESIGN_WH, $SOH%, $CYCLE_COUNT"
```

**To use the script**:
1.  Save the content above as `collect_battery.sh`.
2.  Make it executable: `chmod +x collect_battery.sh`
3.  Run it manually or add it to `cron` to run every hour/day and store output in a CSV file that can be analyzed in a spreadsheet or with Python.

```bash
# Example of adding to crontab (runs every hour)
# crontab -e
# 0 * * * * /path/to/collect_battery.sh >> /path/to/logs/battery.csv
```
