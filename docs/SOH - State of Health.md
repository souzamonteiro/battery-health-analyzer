# **Health (SOH - State of Health)**

To estimate the **Health (SOH - State of Health)** and **lifespan** of a battery from charge and discharge data, we need to process cycles and identify degradation trends. The basic process involves:

## 1. Main metrics to estimate SOH

- **Current Capacity / Nominal Capacity** → $SOH (\%) = (C_{current} / C_{nominal}) × 100$
   
  Current capacity is obtained by integrating current during a complete discharge (from 100% to voltage cutoff).

- **Internal Resistance (DCIR)** → SOH can also be estimated by the increase in internal resistance relative to the initial value.  
  Measured via voltage drop during current pulse: $R = \Delta V / I$

- **Coulomb counting** during complete cycles (full charge → full discharge) to obtain real energy/ampere-hours.

## 2. How to extract from data

Charge/discharge data should contain at least:
- Time (s)
- Current (A)
- Voltage (V)
- Temperature (important, as it affects kinetics)

Steps:
1. Identify complete cycles (beginning and end of charge/discharge by change in current or voltage limit).
2. Integrate current over time during discharge:  
   $C_{cycle} = \int I_{dischg}(t) \, dt$ (in Ah)
3. Compare with nominal capacity (e.g., 100 Ah → $SOH = C_{cycle}/100)$.
4. Track SOH across cycles → linear or exponential regression to project end of life (typically $SOH = 70-80\%$).

## 3. Lifespan estimation

- **Empirical model**:  
  $C(n) = C_0 - k \cdot n$ (linear degradation)  
  $n_{end} = \frac{C_0 - C_{end}}{k}$  
  where $n$ = number of cycles, $k$ = degradation rate per cycle.

- **Model based on processed energy (Ah throughput)**:  
  Lifespan (cycles) = (total capacity processed until failure) / (nominal capacity × 2) – adjusted for discharge depth (DoD).

- **Factors that need to be included in data** for better accuracy:
  - Average temperature per cycle (Arrhenius for accelerated degradation)
  - Charge/discharge rate (C-rate)
  - Voltage fluctuation (unbalanced cells)

## 4. Practical tool

Data can be processed with:
```python
# Basic example in Python (pandas + numpy)
import pandas as pd
import numpy as np

# Load data
df = pd.read_csv('battery_data.csv')
# Isolate a discharge cycle
discharge = df[(df['current'] < 0) & (df['time'] > t_start) & (df['time'] < t_end)]
capacity_Ah = np.trapz(abs(discharge['current']), discharge['time']) / 3600
SOH = (capacity_Ah / nominal_capacity) * 100
```

## 5. Important limitations

- Data from only a few cycles does not allow good prediction without a physical model or pre-trained machine learning.
- Effects of **capacity recovery** (if the battery rests) can mask degradation.
- For real lifespan, it is necessary to test until end of life or use aging models based on data from many cycles.
