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

Despite the growing interest in and adoption of Battery Data Format (BDF) [@BatteryDataAlliance2025BDFGitHub] for storing data collected from various types of batteries, there are no kits that provide cross-platform, real-time data acquisition and real-time analysis of battery health and remaining lifespan for mobile devices, are easy to install and use by both researchers and end users of mobile devices, and offer an integrated web interface allowing online data analysis, as well as the generation of synthetic data for research and training of predictive models.

Maia Battery Health Analyzer fills this gap by offering industry standardization [@Hassini2023LithiumIonBD], using the BDF format, two different analysis methods, linear regression and Support Vector Regression (SVR), with graph generation and human-readable results, generation of synthetic data in BDF format, and automation for data capture on Windows, Linux, and macOS mobile devices, in addition to allowing batch processing of BDF files.

# State of the field                                                                                               

Batteries are present in all mobile devices, whether rechargeable or not. Cell phones, smartwatches, laptops, automobiles, and smart home devices require portable electrical power sources to function. These power sources, however, degrade over time, whether through normal use, charging and discharging, or through the degradation of their constituent elements due to chemical reactions that take place even when these devices are at rest. The study of this degradation and its prediction has stimulated the development of several tools. @Sulzer2021PyBaMM offers an extensive framework for electrochemical battery modeling and simulation, but does not focus on real-time data capture nor adopt an industry standard like BDF. @Zhang2024BatteryML presents a unified platform with machine learning (ML) capabilities for prediction, however it does not offer real-time data capture capabilities nor user-friendly results. @BatteryHistorian continues to offer an Android tool for device battery analysis, but it is not cross-platform, does not offer SOH/ROL data, and does not adopt industry standards such as BDF.

Maia Battery Health Analyzer complements these efforts by offering an integrated tool for collecting battery data from multiple devices, real-time Battery Health Status (SOH) analysis, prediction models using Linear Degradation Model (RUL) and Support-Vector Regression (SVR), as well as an online tool for analyzing battery data from devices not supported by the Maia ecosystem, compatible with the Battery Data Format (BDF) for standardization [@Hassini2023LithiumIonBD].

# Research impact statement

The **Maia Battery Health Analyzer** toolkit has been of great importance for battery research in master's theses at the State University of Bahia and SENAI CIMATEC University. Through the tool, we have collected data from volunteers and are creating a public database on battery charging and discharging, in addition to using the programs in related research, including vehicle battery degradation.

# Software architecture and functionality

**Maia Battery Health Analyzer** consists of four Python applications ('battery_bdf_analyzer_console.py', 'battery_bdf_analyzer.py', 'battery_bdf_collector.py', 'generate_test_bdf_data.py') and one Node.js application ('server.js'). All data processing and analysis is performed by the Python applications, but they are not interdependent. The Node.js application, on the other hand, uses the programs 'battery_bdf_analyzer_console.py', for analysis and prediction, and 'generate_test_bdf_data.py' for creating synthetic battery data in BDF format [@BatteryDataAlliance2025BDFGitHub].

## Data collection

### 1. The collector

The data collection is performed locally using the `battery_bdf_collector.py` script. The script typically runs in the background and utilizes the API most appropriate for the underlying operating system, namely:

- **Linux**: `energy_now`, `voltage_now`, `current_now`, `cycle_count`, `temperature` from `/sys/class/power_supply/BAT*`.
- **Windows**: `Voltage` from `Win32_Battery` and estimated charge rate.
- **macOS**: `voltage` from `pmset -g batt` and estimated charge rate.

For each sample we computes:
- The elapsed wall time since collector start, `Test Time / s`.
- The  POSIX timestamp, `Unix Time / s`.
- The power rate, `Power / W = Voltage × Current`, with sign convention: charging → current ≥ 0, discharging → current ≤ 0.

The output is a CSV file in BDF format with the following header: `Test Time / s,Unix Time / s,Voltage / V,Current / A,Cycle Count / 1,Capacity / %,Power / W,Ambient Temperature / degC`. However, due to limitations of each system, some of these values ​​may be estimates or even zeros.

### 2. Data normalisation

Since some systems only provide battery voltage or charge percentage, although the synthetic data generator creates a complete BDF file, the data collector only displays complete and real data in a Linux environment. In other environments, only `Test Time / s,Unix Time / s,Voltage` shows real values, with the remaining columns filled with zeros.

If `Capacity / %` is missing, SOH is estimated via Coulomb counting (see below).

## The estimator

There are two programs for estimating battery degradation:

- The command-line tool, `battery_bdf_analyzer_console.py`.
- The graphical tool, `battery_bdf_analyzer.py`.
  
Both use the same algorithms described below.
 
 ### 1. Calculating the State‑of‑health (SOH)

If the BDF file contains the `Capacity / %` column the the SOH is just equals to that percentage directly. This is the **Primary method**.

However, when capacity is omitted in the BDF file, the SOH is derived from cumulative absolute current throughput. This the **Fallback method** [@Yang2023BatterySO]. These calculations are described in the following formula:

$$
\Delta t_i = t_i - t_{i-1}, \quad
Q_i = \sum_{k=1}^{i} \frac{|I_k|\,\Delta t_k}{3600}, \quad
\mathrm{SOH}_i = 100 \left(1 - \frac{Q_i}{\max(Q)}\right)
$$

The results are are clipped to $[0, 100]$. This method works if the BDF file contains `current` and `time`.

### 2. Linear degradation model (RUL)

The **linear degradation model** fits to an ordinary least squares [@Vilsen2021BatterySM]: $\mathrm{SOH}(t) = a + bt$, where $t$ = `test_time_second`. The `degradation` slope is reported in % per day: $b_{\mathrm{day}} = b \cdot 86400$.

The **remaining useful life** (RUL) to end‑of‑life threshold $\mathrm{SOH}_{\mathrm{eol}}$ and the default value is 70%:

$$
t_{\mathrm{eol}} = \frac{\mathrm{SOH}_{\mathrm{eol}} - a}{b}, \quad
\mathrm{RUL} = \max\left(0,\, t_{\mathrm{eol}} - t_{\mathrm{current}}\right)
$$

The special case occurs if $b \ge 0$ → infinite RUL (no degradation trend). So if current $SOH ≤ EOL → RUL = 0$.

### 3. Support‑vector regression (SVR) model

The **Support‑vector Regression** [@Yang2024ARL; @Li2024ResearchOS] uses `sklearn.svm.SVR` Python library with RBF kernel ($C=10.0$, $\epsilon=0.01$). The features are:
- `test_time_second`
- `voltage_volt`
- `current_ampere`
- `ambient_temperature_celsius`, with default to 25.0, if it is missed.

The features are standardised using `StandardScaler`. The model is trained on all available data and reports the $R^2$ and the MAE. This method captures non-local and non-linear behaviors that a simple least squares fit would not capture.

## Synthetic data generator

The synthetic data generator is the program `generate_test_bdf_data.py`. It creates physically plausible BDF datasets containing:

- Monotonic long‑term SOH decline (linear from `start_soh` to `end_soh`).
- Sinusoidal local variation + Gaussian noise.
- Bounded voltage, current, and temperature ranges.
- Cycle count progression.

By default, `end_soh > 70%` so that models can be tested before reaching EOL, but this can be adjusted.

# AI usage disclosure

We used artificial intelligence (**DeepSeek-V3** and **GPT-5.3-Codex**) to create the project prototypes, and these prototypes are preserved for study and reference in the *prototypes* folder in the GitHub repository. In addition to these prototypes, the Android app was entirely built using AI (**GPT-5.3-Codex**). No part of this paper's manuscript, however, was written using AI; it was constructed entirely by the researchers.

# Acknowledgements

We acknowledge and appreciate the support of our students and colleagues who dedicated their time and effort to testing and reviewing the code and text developed for this project.

# References