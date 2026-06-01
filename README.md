# Battery Health Analyzer (BDF Workflow)

Battery telemetry collection and analysis toolkit using the Battery Data Format (BDF).

This repository now uses the **BDF collector/analyzer stack**:

- `battery_bdf_collector.py`: collects local battery telemetry and writes `.bdf.csv` files with BDF preferred-label headers.
- `battery_bdf_analyzer.py`: Tkinter GUI analyzer for BDF datasets (linear + SVR models).
- `battery_bdf_analyzer_console.py`: console analyzer that prints a report and saves plots.
- `generate_test_bdf_data.py`: synthetic BDF dataset generator for test/validation.

## Core Files

- `battery_bdf_collector.py`
  - One-shot and loop collection modes.
  - Default output: `battery_data.bdf.csv`.
- `battery_bdf_analyzer.py`
  - GUI plots and RUL estimates.
  - If started without arguments, it auto-loads `battery_data.bdf.csv` when that file exists.
- `battery_bdf_analyzer_console.py`
  - CLI report + PNG plots.
  - Graceful `Ctrl+C` handling.
- `generate_test_bdf_data.py`
  - Generates realistic degradation data that stays above EOL by default.

## BDF Format and Documentation

- Project BDF reference: [docs/BDF_FORMAT_REFERENCE.md](docs/BDF_FORMAT_REFERENCE.md)
- Algorithm documentation: [docs/BDF_ANALYSIS_ALGORITHMS.md](docs/BDF_ANALYSIS_ALGORITHMS.md)

## Quick Start

### 1) Collect one sample

```bash
python3 battery_bdf_collector.py --once --output battery_data.bdf.csv
```

### 2) Run GUI analyzer

```bash
python3 battery_bdf_analyzer.py battery_data.bdf.csv
```

Or simply:

```bash
python3 battery_bdf_analyzer.py
```

If `battery_data.bdf.csv` exists in the project root, it is loaded automatically.

### 3) Run console analyzer

```bash
python3 battery_bdf_analyzer_console.py battery_data.bdf.csv --outdir plots_bdf --eol 70
```

### 4) Generate synthetic test data

```bash
python3 generate_test_bdf_data.py --output battery_test_degradation.bdf.csv
```

## Automation Scripts (`scripts/`)

### Launchers

- `scripts/open_battery_health_analyzer.sh`
- `scripts/open_battery_health_analyzer.command`
- `scripts/open_battery_health_analyzer.cmd`

All launchers target `battery_bdf_analyzer.py` and default to `battery_data.bdf.csv`.
If the file does not exist, they still open the analyzer without preloaded data.

### Background collector wrappers

- `scripts/run_battery_logger.sh`
- `scripts/run_battery_logger.cmd`

Both wrappers run `battery_bdf_collector.py --loop` and write to `battery_data.bdf.csv` by default.

### Installers

- Linux: `scripts/install_automation_linux.sh`
- macOS: `scripts/install_automation_macos.sh`
- Windows: `scripts/install_automation_windows.ps1`

Installers configure startup/background collection and desktop launchers to the BDF workflow.

## BDF Header Notes

Collector output uses preferred-label style headers, for example:

- `Test Time / s`
- `Voltage / V`
- `Current / A`
- `Unix Time / s`
- `Cycle Count / 1`
- `Ambient Temperature / degC`
- `Power / W`
- `Capacity / %`

Analyzers normalize these headers to internal aliases automatically.

## Notes

- GUI and console analyzers support both preferred-label headers and legacy aliases.
- EOL default threshold in analyzers is `70%` SOH.
- Synthetic data generator keeps SOH above EOL unless configured otherwise.

## License

See `LICENSE`.
