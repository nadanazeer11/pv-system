# Methodology

> Draft skeleton — to be expanded throughout development. Final version delivered Day 19.

## 1. Data Sources

### 1.1 Solar irradiance (PVGIS)
- API: `https://re.jrc.ec.europa.eu/api/v5_2/`
- Product: Typical Meteorological Year (TMY) hourly data
- Variables: GHI (global horizontal), DNI (direct normal), DHI (diffuse horizontal), ambient temperature, wind speed
- Spatial resolution: ~5 km grid

### 1.2 Roof geometry
- OpenStreetMap building footprints (Overpass API) for area
- Google Maps Static API for satellite imagery
- Computer vision pipeline for tilt and azimuth estimation

### 1.3 Egypt-specific assumptions
- Tariff structure: EgyptERA published residential tiers (2024)
- Grid emission factor: 0.46 kg CO₂/kWh (EEHC 2023 annual report)
- Installed cost: 35,000 EGP/kW (Egyptian solar market survey 2024)

## 2. PV Modeling Approach

### 2.1 System sizing
*To be filled — Day 3.*

### 2.2 Energy generation — pvlib model
*To be filled — Day 4.*

### 2.3 Energy generation — manual physics model
*To be filled — Day 5.*

### 2.4 Loss modeling
*To be filled — Day 8.*

## 3. Financial Modeling

### 3.1 Tiered tariff model
*To be filled — Day 8.*

### 3.2 Optimization formulation
*To be filled — Day 8.*

### 3.3 NPV/IRR with inflation
*To be filled — Day 9.*

## 4. Uncertainty Quantification (Monte Carlo)

### 4.1 Stochastic input distributions
*To be filled — Day 9.*

### 4.2 Confidence intervals
*To be filled — Day 9.*

## 5. AI Roof Detection

### 5.1 Footprint retrieval
*To be filled — Day 10.*

### 5.2 Segmentation pipeline
*To be filled — Day 11.*

### 5.3 Tilt and azimuth inference
*To be filled — Day 11.*
