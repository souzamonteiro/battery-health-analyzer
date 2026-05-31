# Battery Health Analyzer

Desktop battery health analysis tool with historical logging and end-of-life forecasting.

This project provides:
- A GUI analyzer to visualize degradation and estimate battery replacement timing.
- A cross-platform logger to collect battery health snapshots on Linux, macOS, and Windows.
- A sample dataset for validation and exploratory testing.

## Key Features

- Historical CSV ingestion (`date`, `capacity_percent`).
- One-click capture of current battery data from the local machine.
- Forecast of the date when battery health is expected to drop below 80%.
- Robust trend model designed for noisy, real-world battery observations.
- Platform-aware dependency installation script.

## Project Architecture

- `battery_health_analyzer.py`
: Tkinter + Matplotlib GUI application. Responsible for loading data, training the forecast model, plotting, and reporting end-of-life estimation.
- `battery_logger.py`
: Command-line data collector that appends one battery sample to CSV. Includes OS-specific collectors and fallback strategies.
- `bateria_teste.csv`
: Sample historical dataset for testing and baseline validation.
- `install_deps.sh`
: Dependency installer with OS routing rules (Ubuntu apt, macOS Homebrew, Windows pip, other Linux venv + pip).

## Forecast and Analysis Model

The analyzer uses **Theil-Sen robust linear regression** to model long-term battery degradation trend over time.

Model form:

$$
\hat{H}(t) = a + b \cdot t
$$

Where:
- $\hat{H}(t)$ is predicted battery health (%).
- $t$ is elapsed days from first recorded sample.
- $a$ is estimated intercept.
- $b$ is estimated degradation slope (% per day).

### Why this model

- Better outlier resistance than ordinary least squares.
- Stable for extrapolating the threshold crossing date.
- Interpretable slope for maintenance planning.

### End-of-life definition

End-of-life is estimated as the first date where:

$$
\hat{H}(t) \leq 80\%
$$

The 80% threshold is a common operational recommendation for replacement planning.

## Battery Data Sources by OS

`battery_logger.py` prioritizes health-capacity sources and uses fallback charge-level sources when needed.

- Linux
: `/sys/class/power_supply/BAT*` (`energy_full`/`energy_full_design`, or `charge_*` fallback).
- macOS
: `system_profiler SPPowerDataType` for full/design capacity ratio.
Fallback: `pmset -g batt` charge percentage.
- Windows
: PowerShell CIM classes:
`BatteryFullChargedCapacity` + `BatteryStaticData` for health ratio.
Fallback: `Win32_Battery` charge percentage.

The `source` column in logger output indicates whether the measurement is true health or fallback charge data.

## Installation

Run:

```bash
./install_deps.sh
```

Behavior:
- Ubuntu Linux: installs packages with `apt` (same as previous behavior).
- macOS: installs Python runtime with Homebrew, then installs Python libraries globally with `sudo python3 -m pip`.
- Windows shell (`MINGW/MSYS/CYGWIN`): installs with `pip`.
- Other Linux distributions: creates `.venv` and installs with `pip` inside the virtual environment.

## Automation

This repository now includes per-OS automation scripts under [`scripts/`](scripts) to keep logging running while the machine is on and to open the analyzer with the default history file.

Logger service installers:
- Linux: [`scripts/install_automation_linux.sh`](scripts/install_automation_linux.sh)
- macOS: [`scripts/install_automation_macos.sh`](scripts/install_automation_macos.sh)
- Windows: [`scripts/install_automation_windows.ps1`](scripts/install_automation_windows.ps1)

These installers configure the logger to run continuously with `--loop` and write to the default CSV file next to the project.

Analyzer launchers that open the default history file:
- Linux/macOS shell launcher: [`scripts/open_battery_health_analyzer.sh`](scripts/open_battery_health_analyzer.sh)
- macOS double-click launcher: [`scripts/open_battery_health_analyzer.command`](scripts/open_battery_health_analyzer.command)
- Windows launcher: [`scripts/open_battery_health_analyzer.cmd`](scripts/open_battery_health_analyzer.cmd)

Icon asset:
- [`assets/battery-health-analyzer.svg`](assets/battery-health-analyzer.svg) is the shared source icon for the launchers and future packaging.

The analyzer also accepts a history CSV path directly:

```bash
python3 battery_health_analyzer.py battery_history.csv
```

If no file is passed, it behaves as before and opens the empty GUI.

## Usage

### 1) Launch GUI analyzer

```bash
python3 battery_health_analyzer.py
```

In the GUI, you can:
- Load a historical CSV.
- Capture current battery status.
- Generate synthetic sample data.
- Plot trend and forecast end-of-life.

### 2) Log one battery sample

```bash
python3 battery_logger.py
```

Optional custom output path:

```bash
python3 battery_logger.py --output ./my_battery_history.csv
```

Loop mode (collect continuously until process is stopped):

```bash
python3 battery_logger.py --loop --interval-seconds 60
```

Stop with `Ctrl+C`.

Logger CSV schema:
- `date`: ISO date/time (`YYYY-MM-DD HH:MM:SS`) or date (`YYYY-MM-DD`)
- `capacity_percent`: measured percentage value
- `source`: data origin (`*_health` or `*_charge_fallback`)

## Sample Dataset Validation (`bateria_teste.csv`)

The provided dataset is suitable for baseline forecasting tests because it:
- Uses consistent date formatting.
- Contains enough points (29 records) for trend fitting.
- Shows a plausible long-term degradation path from ~99% to ~76.5%.
- Crosses the 80% threshold, enabling end-of-life date estimation checks.

If you want stress testing, create additional datasets with outliers, gaps, and non-monotonic sections.

## Notes and Limitations

- Forecast quality depends on historical coverage and measurement quality.
- Fallback charge-level readings are less ideal than design/full-capacity health readings.
- Battery behavior can change due to usage pattern, temperature, and firmware updates.

## License

This project is distributed under the terms defined in `LICENSE`.
