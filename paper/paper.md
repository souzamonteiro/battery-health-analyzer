---
title: 'Maia Battery Health Analyzer: Open‑Source Toolkit for BDF‑Compliant Telemetry Collection and Degradation Modelling'

tags:
  - Python
  - Node.js
  - battery
  - forecast
  - regression
  - soh
  - svr
  
authors:
  - name: Roberto Luiz Souza Monteiro
    orcid: 0000-0002-3931-5953
    equal-contrib: true
    affiliation: "1, 2" # (Multiple affiliations must be quoted)
  - name: Marcos Toranosuke Morita
    orcid: 0009-0009-1530-0106
    equal-contrib: true
    affiliation: "2" # (Multiple affiliations must be quoted)
  - name: Andréia Rita da Silva
    orcid: 0009-0009-0587-1263
    equal-contrib: true
    affiliation: "2" # (Multiple affiliations must be quoted)
  - name: Thiago	Barros Murari
    orcid: 0000-0001-5598-2679
    equal-contrib: true
    affiliation: "2" # (Multiple affiliations must be quoted)
  - name: Marcos Batista Figueredo
    orcid: 0000-0002-8193-5419
    equal-contrib: true
    affiliation: "1" # (Multiple affiliations must be quoted)
  - name: Hernane Barros de Borges Pereira
    orcid: 0000-0001-7476-9267
    equal-contrib: true
    affiliation: "1, 2" # (Multiple affiliations must be quoted)
    
affiliations:
 - name: State University of Bahia, UBrazil
   index: 1
 - name: SENAI CIMATEC University
   index: 2
date: 2 June 2026
bibliography: paper.bib

# Optional fields if submitting to a AAS journal too, see this blog post:
# https://blog.joss.theoj.org/2018/12/a-new-collaboration-with-aas-publishing
# aas-doi: 10.3847/xxxxx
# aas-journal: Astrophysical Journal
---

# Summary

Maia Battery Health Analyzer is a toolkit for real-time data collection from mobile, Windows, Linux, and macOS device batteries, analysis and estimation of state of health (SOH), and prediction of remaining battery life, compatible with the Battery Data Format (BDF). The toolkit includes a program for real-time data capture, a command-line tool with automation capabilities for analyzing and diagnosing multiple BDF files, including graph generation, a graphical user interface, and a web service that allows battery data analysis from the internet. The tools are distributed under the Apache 2.0 license and can be obtained from GitHub.

# Statement of need

Despite the growing interest in and adoption of Battery Data Format (BDF) for storing data collected from various types of batteries, there are no kits that provide cross-platform, real-time data acquisition and real-time analysis of battery health and remaining lifespan for mobile devices, are easy to install and use by both researchers and end users of mobile devices, and offer an integrated web interface allowing online data analysis, as well as the generation of synthetic data for research and training of predictive models.

Maia Battery Health Analyzer fills this gap by offering industry standardization, using the BDF format, two different analysis methods, linear regression and Support Vector Regression (SVR), with graph generation and human-readable results, generation of synthetic data in BDF format, and automation for data capture on Windows, Linux, and macOS mobile devices, in addition to allowing batch processing of BDF files.

# State of the field                                                                                               
Solutions for data capture, health analysis, and prediction of remaining battery life exist, but not in an integrated way that conforms to industry standards.

Continue...

# Software design

**Maia Battery Health Analyzer** consists of four Python applications ('battery_bdf_analyzer_console.py', 'battery_bdf_analyzer.py', 'battery_bdf_collector.py', 'generate_test_bdf_data.py') and one Node.js application ('server.js'). All data processing and analysis is performed by the Python applications, but they are not interdependent. The Node.js application, on the other hand, uses the programs 'battery_bdf_analyzer_console.py', for analysis and prediction, and 'generate_test_bdf_data.py' for creating synthetic battery data in BDF format.

Continued...

# Research impact statement

The **Maia Battery Health Analyzer** tool kit has been of great importance for battery research in master's theses at the State University of Bahia and SENAI CIMATEC University.

Continued...

# Mathematics

### 1. Data collector – `battery_bdf_collector.py`

Reads platform‑specific power supply interfaces:
- **Linux**: `energy_now`, `voltage_now`, `current_now`, `cycle_count`, `temperature` from `/sys/class/power_supply/BAT*`.
- **Windows**: `Win32_Battery` (voltage, estimated charge rate).
- **macOS**: `pmset -g batt` (best‑effort parsing).

Each sample computes:
- `Test Time / s` – elapsed wall time since collector start.
- `Unix Time / s` – POSIX timestamp.
- `Power / W = Voltage × Current` (with sign convention: charging → current ≥ 0, discharging → current ≤ 0).

Output is a CSV file with BDF preferred‑label headers (e.g. `Test Time / s, Voltage / V, Current / A, Cycle Count / 1, Ambient Temperature / degC`). Loop and one‑shot modes are supported.

### 2. Header normalisation (both analyzers)

The analyzers automatically map BDF preferred labels and legacy aliases to internal names:

| Preferred label | Internal alias |
|----------------|----------------|
| `Test Time / s` | `test_time_second` |
| `Voltage / V` | `voltage_volt` |
| `Current / A` | `current_ampere` |
| `Capacity / %` | `capacity_percent` |
| `Cycle Count / 1` | `cycle_count` |

If `Capacity / %` is missing, SOH is estimated via Coulomb counting (see below).

### 3. State‑of‑health (SOH) computation

**Primary method** – if the file contains a `Capacity / %` column (as written by synthetic generator or some BMS), SOH equals that percentage directly.

**Fallback (Coulomb counting)** – when capacity is absent, SOH is derived from cumulative absolute current throughput:

$$
\Delta t_i = t_i - t_{i-1}, \quad
Q_i = \sum_{k=1}^{i} \frac{|I_k|\,\Delta t_k}{3600}, \quad
\mathrm{SOH}_i = 100 \left(1 - \frac{Q_i}{\max(Q)}\right)
$$

Results are clipped to $[0, 100]$. This method works for any dataset containing current and time.

### 4. Linear degradation model (RUL)

Fits ordinary least squares: $\mathrm{SOH}(t) = a + bt$, where $t$ = `test_time_second`. Degradation slope is reported in % per day: $b_{\mathrm{day}} = b \cdot 86400$.

Remaining useful life (RUL) to end‑of‑life threshold $\mathrm{SOH}_{\mathrm{eol}}$ (default 70%):

$$
t_{\mathrm{eol}} = \frac{\mathrm{SOH}_{\mathrm{eol}} - a}{b}, \quad
\mathrm{RUL} = \max\left(0,\, t_{\mathrm{eol}} - t_{\mathrm{current}}\right)
$$

Special cases: if $b \ge 0$ → infinite RUL (no degradation trend); if current SOH ≤ EOL → RUL = 0.

### 5. Support‑vector regression (SVR) model

Uses `sklearn.svm.SVR` with RBF kernel ($C=10.0$, $\epsilon=0.01$). Features:
- `test_time_second`
- `voltage_volt`
- `current_ampere`
- `ambient_temperature_celsius` (default 25.0 if missing)

Features are standardised (`StandardScaler`). The model is trained on all available data and reports $R^2$ and MAE. This captures non‑local, non‑linear ageing behaviour that the linear model may miss.

### 6. Synthetic data generator – `generate_test_bdf_data.py`

Creates physically plausible BDF datasets with:
- Monotonic long‑term SOH decline (linear from `start_soh` to `end_soh`).
- Sinusoidal local variation + Gaussian noise.
- Bounded voltage, current, and temperature ranges.
- Cycle count progression.

By default, `end_soh > 70%` so that models can be tested before reaching EOL.

# AI usage disclosure

We used artificial intelligence (**DeepSeek-V3** and **GPT-5.3-Codex**) to create the project prototypes, and these prototypes are preserved for study and reference in the *prototypes* folder in the GitHub repository. No part of this paper's manuscript, however, was written using AI; it was constructed entirely by the researchers.

# Acknowledgements

We acknowledge and appreciate the support of our students and colleagues who dedicated their time and effort to testing and reviewing the code and text developed for this project.

# References