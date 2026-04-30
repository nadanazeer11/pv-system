# Validation Strategy

> Draft skeleton — final report on Day 20.

## 1. Cross-Model Validation

Compare `pvlib` PVWatts output vs. the manual physics model on:
- 10 representative Egyptian locations (Cairo, Alexandria, Aswan, Hurghada, Sharm El Sheikh, Luxor, Mansoura, Tanta, Asyut, Marsa Matruh)
- Identical PVGIS TMY input
- Identical system specs (5 kW, 26° tilt, south-facing)

Metric: annual kWh agreement (target: <5% MAPE).

## 2. Comparison vs. Published Egyptian PV Studies

References to be cited from `references.bib`:
- Sayed et al. — measured PV performance in Cairo
- Egyptian Solar Atlas (NREA) — typical specific yield by region

Approach: report deviation between this system's predicted specific yield (kWh/kWp) and published values for matching locations.

## 3. Tariff Model Validation

Cross-check tier breakpoints and rates against EgyptERA published residential schedules. Validate against 5 sample household bills (anonymized) provided by the author.

## 4. Roof Detection Validation

For 20 manually-labeled Cairo rooftops:
- Measure IoU (Intersection-over-Union) of predicted polygon vs. ground truth
- Measure absolute error in roof area (m²)
- Target: median IoU > 0.7, mean area error < 15%

## 5. Limitations Disclosure

All assumptions are clearly separated from measured data — see `limitations.md`.

## 6. Out of Scope

- Real-time generation forecasting (TMY only)
- Battery storage simulation (grid-tied, no battery, per spec)
- Commercial-scale systems
