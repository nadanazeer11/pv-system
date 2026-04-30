# Limitations and Assumptions

> Draft skeleton — final report on Day 21.

## 1. TMY Data Limitations

- TMY represents a "typical" year and does not capture inter-annual variability.
- A real installation in a sunny year may produce 5–10% above prediction; a cloudier year may produce 5–10% below.
- Mitigation: Monte Carlo analysis treats annual irradiance as a random variable centred on TMY.

## 2. Shading Assumptions

- The system assumes **no obstacles** (neighboring buildings, palm trees, antennas) cast shade on the roof.
- A simple geometric horizon-shading model is included as a *coarse* correction; high-resolution shadow analysis is out of scope.
- Mitigation: explicit user disclaimer; future work item (LiDAR / 3D shadow simulation).

## 3. Roof Detection Accuracy

- Footprints depend on OSM coverage, which varies across Egypt (high in Cairo and Alexandria, sparse in remote governorates).
- CV-based tilt/azimuth estimation from satellite imagery is approximate.
- Mitigation: user can manually correct the detected polygon and override tilt/azimuth.

## 4. Tariff Model

- Reflects EgyptERA residential tiers as published at project start; tariffs change. The system parameterises tier breakpoints and rates so they can be updated.
- Net metering rules in Egypt cap surplus credits; the model treats surplus as fully credited at retail rates (best case). Real surplus economics may be worse.

## 5. Financial Assumptions

- Discount rate, tariff inflation, and panel degradation are all uncertain in the long term.
- Mitigation: Monte Carlo confidence intervals rather than point estimates.
- Egyptian inflation is volatile; the tariff inflation distribution is wide intentionally.

## 6. Hardware Generalisation

- Assumes a single representative panel (450 W, 1.8 m², monocrystalline).
- Inverter assumed to be a single string inverter at 96% efficiency.
- Mitigation: parameters are configurable.

## 7. Scope Boundaries

- Grid-tied only; no battery storage simulated.
- Residential only; commercial tariff structures (EgyptERA non-residential) out of scope.
- No structural roof analysis (load-bearing capacity is not assessed).
