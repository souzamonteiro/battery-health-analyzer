# Battery Data Format (BDF) Reference for this Project

This project follows the official Battery Data Format (BDF) convention from the Battery Data Alliance (`battery-data-format` repository).

## Key rule used here

For CSV files, the **header must use Preferred Labels** (human-readable labels with units), not only machine-readable names.

## Canonical columns used in this project

### Required

- `Test Time / s`
- `Voltage / V`
- `Current / A`

### Recommended

- `Unix Time / s`
- `Cycle Count / 1`
- `Ambient Temperature / degC`

### Optional used by this project

- `Power / W`
- `Capacity / %` (project-specific analytical helper, not an official BDF core quantity)

## Internal normalization strategy

To remain compatible with existing files, analyzers normalize these variants:

- Preferred Label -> machine-readable alias:
  - `Test Time / s` -> `test_time_second`
  - `Voltage / V` -> `voltage_volt`
  - `Current / A` -> `current_ampere`
  - `Unix Time / s` -> `unix_time_second`
  - `Cycle Count / 1` -> `cycle_count`
  - `Ambient Temperature / degC` -> `ambient_temperature_celsius`
  - `Power / W` -> `power_watt`

- Legacy aliases also accepted:
  - `temperature_celsius`
  - `capacity_percent`

## File naming

Recommended style from BDF docs:

`InstitutionCode__CellName__YYYYMMDD_XXX.bdf.csv`

## Validation checklist

A file is considered valid for this project if:

1. It has at least the three required BDF quantities.
2. `Test Time / s`, `Voltage / V`, `Current / A` are numeric after parsing.
3. Rows are sorted by `Test Time / s` for analysis.

## Notes

- The synthetic test dataset generated in this repository intentionally keeps SOH above EOL (70%) so model behavior can be verified before end-of-life.
- GUI and console analyzers both apply the same normalization rules.
- Algorithm details are documented in `docs/BDF_ANALYSIS_ALGORITHMS.md`.
