# Maia Battery Health Analyzer

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
  - JSON report output support.
  - Batch processing with wildcard input patterns.
  - Graceful `Ctrl+C` handling.
- `generate_test_bdf_data.py`
  - Generates realistic degradation data that stays above EOL by default.

## BDF Format and Documentation

- Project BDF reference: [docs/BDF_FORMAT_REFERENCE.md](docs/BDF_FORMAT_REFERENCE.md)
- Algorithm documentation: [docs/BDF_ANALYSIS_ALGORITHMS.md](docs/BDF_ANALYSIS_ALGORITHMS.md)

## Quick Start

### 0) Start the REST service + web UI

Install Node dependencies and start the service:

```bash
npm install
npm start
```

Then open:

- `http://localhost:8000` (web interface for upload, predictions, and plots)
- `http://localhost:8000/api/health` (service health check)

Main REST endpoints:

- `POST /api/analyze` (multipart field: `batteryFile`; optional: `eol`, `svrDays`)
- `POST /api/generate-dataset` (JSON body with generator parameters)
- `GET /api/analysis/:jobId/report`
- `GET /api/analysis/:jobId/plots/:plotName`
- `GET /api/datasets/:fileName`

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

Generate JSON output for a single file:

```bash
python3 battery_bdf_analyzer_console.py battery_data.bdf.csv --json
```

Batch process using wildcards (one JSON per input file):

```bash
python3 battery_bdf_analyzer_console.py dataset/*.csv
```

In batch mode, the analyzer automatically writes `file_name.json` for each input
next to its source file. You can override JSON destination directory with:

```bash
python3 battery_bdf_analyzer_console.py dataset/*.csv --json-dir reports_json
```

### 4) Generate synthetic test data

```bash
python3 generate_test_bdf_data.py --output battery_test_degradation.bdf.csv
```

## CLI JSON Regression Tests

The project includes a dedicated regression suite under `test/`:

- `test/case_*.bdf.csv`: input datasets (10 generated test cases)
- `test/case_*.test`: expected JSON baselines
- `test/run_cli_json_tests.py`: automation runner

Run all JSON regression tests:

```bash
python3 test/run_cli_json_tests.py
```

The runner executes `battery_bdf_analyzer_console.py` for each case, compares
the generated `*.json` with `*.test`, and prints a consolidated pass/fail report.

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

### Optional web server service installers (server environments)

These are optional and intended for server deployments where `server.js` should start automatically as a system service:

- Linux (systemd): `scripts/install_server_service_linux.sh`
- macOS (LaunchDaemon): `scripts/install_server_service_macos.sh`
- Windows (Scheduled Task as SYSTEM): `scripts/install_server_service_windows.ps1`

Common wrapper used by Linux/macOS installer:

- `scripts/run_battery_web_service.sh`

Examples:

```bash
# Linux
sudo ./scripts/install_server_service_linux.sh --port 8000

# macOS
sudo ./scripts/install_server_service_macos.sh --port 8000
```

```powershell
# Windows PowerShell (Run as Administrator)
./scripts/install_server_service_windows.ps1 -Port 8000
```

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
