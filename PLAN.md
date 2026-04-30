# PV Rooftop Solar Estimation System — 3-Week Plan

> **Project:** AI-Assisted Rooftop Solar Potential Estimation and Financial Analysis System
> **Author:** Nada (Bachelor's Thesis)
> **Region:** Egypt (Cairo focus, generalizable)
> **Timeline:** 3 weeks (21 days)
> **Status:** Day 1 — scaffolding

---

## 🎯 Core Academic Contributions

This thesis goes beyond "API integration." Four defensible contributions:

### 1. Dual Energy Model (baseline)
Two independent energy generation models — `pvlib` (industry-standard) and a **manual physics-based model** built from first principles. Cross-validation between them is the methodological backbone.

### 2. AI-Assisted Roof Detection (Contribution A)
User enters an address. The system fetches a satellite image and uses computer vision (OpenStreetMap building footprints + segmentation model) to **automatically detect roof area, tilt, and orientation** — eliminating the most error-prone user input.

### 3. Egypt Tiered Tariff Optimization (Contribution B)
Egypt's residential electricity uses **progressive tier pricing** (EgyptERA). Most existing PV calculators assume flat tariffs and **systematically miscalculate Egyptian payback periods**. This system models the actual tier structure and optimizes system size for maximum household savings under tiered pricing — a domain-specific contribution unique to the Egyptian market.

### 4. Monte Carlo Uncertainty Analysis (Contribution C)
Treats uncertain inputs (panel degradation, tariff inflation, weather variability, soiling, inverter replacement) as probability distributions. Runs 1000 simulations to produce **confidence intervals** rather than point estimates. Outputs: "Payback: 7.2 ± 1.5 years (90% CI)."

---

## 🧍 User Flow

1. User enters address (or lat/lng) + electricity tariff + optional roof override.
2. Backend fetches satellite tile + OSM footprint → auto-detects roof polygon → computes area, tilt, azimuth.
3. PVGIS API returns Typical Meteorological Year (TMY) hourly weather for the location.
4. Two energy models run in parallel: `pvlib` and the manual physics model.
5. Tiered tariff optimizer finds the system size that maximizes annual savings.
6. Monte Carlo simulation runs 1000 scenarios with stochastic inputs.
7. Dashboard displays:
   - Detected roof + system size
   - Annual generation (pvlib vs manual comparison chart)
   - **Payback period with confidence interval**
   - Tier-bracket savings visualization
   - CO₂ savings
   - Sensitivity tornado chart

---

## 🏗️ Architecture

```
┌──────────────────┐     ┌──────────────────────────────────────────┐     ┌──────────────────┐
│  React + Vite    │────▶│   FastAPI Backend                        │────▶│   PVGIS API      │
│  Frontend        │     │                                          │     │  (TMY hourly)    │
│                  │◀────│   Services:                              │     └──────────────────┘
│  - Address input │     │     - roof_detection (GMaps + OSM + CV)  │     ┌──────────────────┐
│  - Map view      │     │     - pvgis_service                      │────▶│  Google Maps     │
│  - Dashboard     │     │     - pv_sizing                          │     │  Static API      │
│  - Charts        │     │     - energy_pvlib                       │     └──────────────────┘
└──────────────────┘     │     - energy_manual (physics)            │     ┌──────────────────┐
                         │     - loss_model                         │────▶│  OpenStreetMap   │
                         │     - tiered_tariff (Egypt)              │     │  Overpass API    │
                         │     - financial_model                    │     └──────────────────┘
                         │     - monte_carlo                        │
                         │     - co2_model                          │
                         └──────────────────────────────────────────┘
```

---

## 📅 Week 1 — Backend Foundation + Roof Detection

| Day | Deliverable | Branch |
|-----|-------------|--------|
| 1   | Repo, FastAPI skeleton, schemas, .gitignore, venv                   | `main` (this commit) |
| 2   | PVGIS API integration (TMY fetcher + parser)                        | `feat/pvgis-integration` |
| 3   | PV sizing module (panel count, system kW)                           | `feat/pv-sizing` |
| 4   | pvlib-based energy model (PVWatts approach)                         | `feat/energy-pvlib` |
| 5   | Manual physics-based model (POA, temp, DC→AC)                       | `feat/energy-manual` |
| 6   | Basic financial model (cost, flat-tariff savings, payback)          | `feat/financial-basic` |
| 7   | Unit tests for energy + sizing + financial; tag `v0.1-backend-core` | `chore/tests-week1` |

---

## 📅 Week 2 — Three Contributions + Frontend Start

| Day | Deliverable | Branch |
|-----|-------------|--------|
| 8   | **Egypt tiered tariff** model + optimizer (Contribution B)          | `feat/tiered-tariff` |
| 9   | **Monte Carlo** uncertainty engine (Contribution C)                 | `feat/monte-carlo` |
| 10  | **Roof detection** part 1: Google Maps Static + OSM Overpass        | `feat/roof-detection-osm` |
| 11  | **Roof detection** part 2: CV segmentation + tilt/azimuth estimate  | `feat/roof-detection-cv` |
| 12  | React + Vite + TS scaffold, routing, API client (TanStack Query)    | `feat/frontend-init` |
| 13  | Address input + map preview component (Leaflet)                     | `feat/input-form` |
| 14  | Dashboard layout: metric cards (size, kWh, savings, payback CI)     | `feat/dashboard-cards` |

---

## 📅 Week 3 — Charts, Validation, Polish

| Day | Deliverable | Branch |
|-----|-------------|--------|
| 15  | Monthly production chart + pvlib-vs-manual comparison view          | `feat/charts-comparison` |
| 16  | Monte Carlo visualization (histogram + fan chart for cumulative ROI)| `feat/charts-monte-carlo` |
| 17  | Tier-bracket "before vs after" visualization                        | `feat/charts-tariff` |
| 18  | CO₂ savings + Egypt grid emission factor + sensitivity tornado      | `feat/co2-sensitivity` |
| 19  | **Methodology section** (academic, LaTeX-ready)                     | `docs/methodology` |
| 20  | **Validation** (compare against published Egypt PV studies + tests) | `docs/validation` |
| 21  | **Limitations** + references.bib + README + demo script             | `docs/final` |

---

## 🛠️ Tech Stack

**Backend (Python 3.12)**
- FastAPI + Uvicorn (web framework)
- pvlib (PV modeling — industry standard)
- pandas, numpy (data + numerics)
- requests / httpx (external APIs)
- pydantic v2 (schemas)
- Pillow + OpenCV (image processing for roof detection)
- shapely (polygon math)
- scipy (Monte Carlo distributions, optimization)
- pytest (testing)

**Frontend**
- React 18 + Vite + TypeScript
- TailwindCSS (styling)
- Recharts (charts)
- Leaflet (maps)
- TanStack Query (API client)

**External APIs**
- PVGIS — `https://re.jrc.ec.europa.eu/api/v5_2/` (free, no key)
- Google Maps Static API — for satellite tiles (free tier with API key)
- OpenStreetMap Overpass — `https://overpass-api.de/` (free, building footprints)

---

## 📊 Egypt-Specific Assumptions (initial — refined in research/)

### Hardware
| Parameter | Value | Source |
|-----------|-------|--------|
| Panel rating | 450 W | Industry standard 2024 |
| Panel area | 1.8 m² | Industry standard 2024 |
| Roof utilization factor | 0.7 | Common rule-of-thumb |
| Inverter efficiency | 96% | Modern grid-tied inverters |

### Egypt environment
| Parameter | Value | Source |
|-----------|-------|--------|
| Soiling losses | 2–8% (varies by region) | Egyptian PV literature |
| Default tilt | 26° | Cairo latitude |
| Default azimuth | 180° (south) | Northern hemisphere optimum |
| Grid emission factor | 0.46 kg CO₂/kWh | EEHC 2023 |

### Egypt market
| Parameter | Value | Source |
|-----------|-------|--------|
| Installed system cost | ~35,000 EGP/kW | Egyptian market 2024 |
| Tariff inflation rate | 8% ± 3% (annual) | EgyptERA history |
| Discount rate (real) | 4% | Standard project finance |
| Tariff structure | EgyptERA residential tiers | EgyptERA published rates |

---

## 🎓 Deliverables

1. ✅ Backend (FastAPI + 9 services) with API documentation
2. ✅ Frontend (React) with map input + interactive dashboard
3. ✅ AI roof detection pipeline
4. ✅ Tiered tariff optimization model
5. ✅ Monte Carlo uncertainty analysis
6. ✅ Methodology section (academic style)
7. ✅ Validation report (vs published Egypt studies)
8. ✅ Limitations document
9. ✅ References (BibTeX)
10. ✅ Deployment-ready Docker + README

---

## 🤖 Daily Agent Workflow

A scheduled agent runs **every 8 hours**. Each run:
1. Picks the next item from this PLAN.
2. Opens the corresponding feature branch.
3. Implements the deliverable + commits with a dated, descriptive message.
4. **Writes a "professor brief" to `outputs/NN-<slug>.md`** — plain-English explanation of what was built and why. This is the day-by-day narrative you can read without diving into code.
5. Opens a PR for your review.

You: review → comment / merge. ~10–15 min per agent run.

**The `outputs/` folder is your source of truth for understanding the project's progress.** Each file maps 1-1 to an agent run.

---

## 📝 How This Plan Evolves

This is a **living document**. Edit freely as scope clarifies. If a day slips, push subsequent items back rather than skipping. Each contribution (A, B, C) is independent — if one becomes infeasible, the other two still stand.
