# BDF Analysis Algorithms

This document explains the algorithms currently implemented in:

- `battery_bdf_collector.py`
- `battery_bdf_analyzer.py`
- `battery_bdf_analyzer_console.py`
- `generate_test_bdf_data.py`

## 1) Data collection (`battery_bdf_collector.py`)

### Sampling model

Each sample row stores:

- `Test Time / s` = elapsed wall time since process start
- `Unix Time / s` = UNIX timestamp
- voltage/current/temperature from platform APIs when available
- computed power as:

$$
P = V \cdot I
$$

### Sign convention

- Charging: current is forced non-negative.
- Discharging: current is forced non-positive.

### Platform data sources

- Linux: `/sys/class/power_supply/BAT0/*`
- Windows: WMI (`Win32_Battery` for voltage when available)
- macOS: best-effort parse of `pmset -g batt`

## 2) Header normalization (GUI + console analyzers)

Analyzers accept BDF preferred-label headers and normalize them to internal names.
Example mappings:

- `Test Time / s` -> `test_time_second`
- `Voltage / V` -> `voltage_volt`
- `Current / A` -> `current_ampere`
- `Capacity / %` -> `capacity_percent`

This keeps compatibility with official BDF files and project-generated datasets.

## 3) SOH computation

Implemented in both analyzers.

### Primary mode

If `capacity_percent` exists and has values:

$$
SOH_t = capacity\_percent_t
$$

### Fallback mode

If capacity is missing, SOH is estimated from cumulative absolute current throughput:

$$
\Delta t_i = t_i - t_{i-1}
$$

$$
Q_i = \sum_{k=1}^{i} \frac{|I_k|\Delta t_k}{3600}
$$

$$
SOH_i = 100 \cdot \left(1 - \frac{Q_i}{\max(Q)}\right)
$$

Then values are clipped to `[0, 100]`.

## 4) Linear degradation model

Both analyzers fit linear regression:

$$
SOH(t) = a + bt
$$

Where:

- $t$ = `test_time_second`
- $b$ = degradation slope (% per second)

Displayed daily slope:

$$
b_{day} = b \cdot 86400
$$

### RUL estimation

Given EOL threshold $SOH_{eol}$ (default 70):

$$
t_{eol} = \frac{SOH_{eol}-a}{b}
$$

$$
RUL = \max(0, t_{eol} - t_{current})
$$

Special cases:

- if $b \ge 0$: RUL = infinity (no trend toward EOL)
- if current SOH already <= EOL: RUL = 0

## 5) SVR model

Feature vector:

- `test_time_second`
- `voltage_volt`
- `current_ampere`
- `temperature_celsius` (fallback 25.0)

Processing:

1. Standardize features (`StandardScaler`)
2. Train `SVR(kernel='rbf', C=10.0, epsilon=0.01)`
3. Report:
   - $R^2$
   - MAE

## 6) Synthetic dataset generation

`generate_test_bdf_data.py` creates physically plausible test data with:

- monotonic long-term SOH decline from `start_soh` to `end_soh`
- sinusoidal local variation + Gaussian noise
- bounded voltage/current/temperature ranges
- cycle count progression

Default configuration keeps `end_soh > 70`, so tests do not start in end-of-life.

## 7) Practical interpretation

- Linear model: stable trend and interpretable RUL baseline.
- SVR: captures non-linear local behavior and can improve fit diagnostics.
- Use both metrics together (trend + fit quality) for robust monitoring.
