# Output 01 — PVGIS Integration

> **Date:** 2026-04-30
> **Plan day:** Day 2
> **Branch:** `feat/pvgis-integration`
> **Status:** ✅ Complete, 10/10 tests passing, live API call verified

---

## Plain English

Today we connected the project to PVGIS, a free European weather database that tells us how much sun any spot on Earth gets in a typical year. We built a small piece of the backend that takes a latitude and longitude (for example, Cairo) and downloads the full year of hourly weather — sunlight, temperature, and wind. We then wrote a feature that summarises this data into a few easy numbers, like the total yearly sunshine and the average temperature. We tested everything with both fake data (to make sure the code is correct) and real data (to make sure Cairo's numbers match what published Egyptian solar studies report). This is the foundation everything else stands on, because every solar calculation we do later starts from this weather data.

---

## What I built

A backend service that fetches **Typical Meteorological Year (TMY)** weather data from the **PVGIS** API for any latitude/longitude, plus a FastAPI endpoint (`POST /api/weather/tmy`) that returns annual summary statistics for the location.

When you give the system "Cairo (30.04°N, 31.24°E)", the service downloads ~8,760 hourly weather records covering a representative year and tells you:

- Annual global, direct, and diffuse solar energy per square metre
- Mean and maximum ambient temperature
- Mean wind speed at 10 m

These five variables (`ghi`, `dni`, `dhi`, `temp_air`, `wind_speed`) are the **inputs** to the energy generation models that get built on Days 4 and 5.

---

## Why this matters (academic logic)

### Why PVGIS?

A solar PV model is only as accurate as its weather data. We need a credible, **peer-reviewed** source of irradiance and temperature for the project location. There are three realistic options:

| Source | Pros | Cons |
|---|---|---|
| **PVGIS** (EU JRC) | Free, peer-reviewed, ~5 km grid, covers Egypt | TMY only — no real-time / forecast |
| NASA POWER | Free, global | Coarser resolution, less validated for PV |
| Local weather station | Most accurate | Doesn't exist for most rooftops |

PVGIS is the de-facto standard in academic PV literature for sites without on-site measurement, and it covers all of Egypt with good fidelity. It's the right choice for a thesis.

### Why "Typical Meteorological Year"?

A TMY is a **statistically constructed** 12-month dataset assembled by picking the most "representative" month from each calendar month over a multi-year history. For Cairo, our PVGIS response covers 2005–2018 and stitches together the typical January from one year, the typical February from another, etc.

This means our model answers: **"What would a typical year produce?"** — not "What did 2024 produce?"

This is a deliberate design choice for two reasons:
1. PV system financing is a multi-decade decision; a single real year would be misleading (it could be unusually sunny or cloudy).
2. Inter-annual variability is captured later by the **Monte Carlo uncertainty model** (Day 9), which treats annual irradiance as a random variable around the TMY mean.

### Why use pvlib instead of calling the HTTP API directly?

`pvlib` is the industry-standard Python library for PV simulation. Its `iotools.get_pvgis_tmy()` function:
1. Handles version negotiation across PVGIS API formats.
2. **Renames raw PVGIS columns** (e.g. `G(h)`, `Gb(n)`) into pvlib's internal canonical names (`ghi`, `dni`, `dhi`). Our energy models on Day 4 expect these canonical names — so using pvlib here saves a translation step.
3. Is the same data path used in the published peer-reviewed pvlib literature, which strengthens reproducibility for the thesis defence.

---

## How the code is organised

```
backend/
├── app/
│   ├── services/
│   │   └── pvgis_service.py     ← the work happens here
│   ├── routers/
│   │   └── weather.py           ← thin HTTP layer
│   └── main.py                  ← wired the new router in
└── tests/
    ├── conftest.py              ← shared fake_tmy fixture
    ├── test_pvgis_service.py    ← unit tests (5)
    └── test_weather_router.py   ← endpoint tests (3)
```

### `pvgis_service.py` — three things

1. **`fetch_tmy(lat, lon)`** — async wrapper around `pvlib.iotools.get_pvgis_tmy`. Async because pvlib's HTTP client is synchronous and would otherwise block the FastAPI event loop. We run it in a worker thread with `asyncio.to_thread`.
2. **`summarize_irradiance(df)`** — turns 8,760 rows into 7 summary numbers.
3. **`PVGISError`** — a domain-specific exception so the router can return a clean `502 Bad Gateway` when the upstream API is unreachable, rather than leaking a low-level network exception.

### `weather.py` — the endpoint

`POST /api/weather/tmy` takes a `Location` (lat, lon) and returns the summary. We **deliberately do not return the full hourly DataFrame** over HTTP — 8,760 rows is heavy and the frontend has no use for raw irradiance. The summary is enough for "is this location reasonable?" sanity checks.

---

## How I verified it works

### 1. Unit tests (offline, mocked)
```bash
cd backend
.venv/bin/pytest tests/ -v
```
Result: **10 passed** in 0.48 s. The PVGIS HTTP layer is mocked — tests don't hit the real network.

### 2. Live integration check (real PVGIS call for Cairo)
```bash
.venv/bin/python -c "
import asyncio
from app.services import pvgis_service
df = asyncio.run(pvgis_service.fetch_tmy(30.0444, 31.2357))
print(pvgis_service.summarize_irradiance(df))
"
```
Result for Cairo:

| Metric | Value | Sanity check |
|---|---|---|
| Annual GHI | **2,207 kWh/m²/year** | Egyptian Solar Atlas reports ~6 kWh/m²/day = 2,190 — ✅ matches |
| Annual DNI | 2,470 kWh/m²/year | Cairo is high-DNI, plausible |
| Mean ambient temp | 21.8 °C | Cairo annual average ~22 °C — ✅ |
| Max temp | 44.5 °C | Cairo summer extreme — ✅ |

The live numbers fall squarely within published ranges for Cairo, which gives us confidence the data path is wired up correctly.

### 3. API endpoint
```bash
.venv/bin/uvicorn app.main:app --reload
# In another terminal:
curl -X POST http://localhost:8000/api/weather/tmy \
  -H "Content-Type: application/json" \
  -d '{"latitude":30.0444,"longitude":31.2357}'
```

---

## What's next

| Day | Branch | Goal |
|---|---|---|
| 3 | `feat/pv-sizing` | Convert roof area → number of panels → system kW |
| 4 | `feat/energy-pvlib` | First energy model: feed TMY into pvlib's PVWatts to get hourly kWh |
| 5 | `feat/energy-manual` | Manual physics model with the same signature for cross-validation |

The TMY DataFrame we return today is exactly the shape Days 4 and 5 will consume — no further translation needed.

---

## Files changed

```
A  backend/app/services/pvgis_service.py    (+106 lines)
A  backend/app/routers/weather.py           (+33 lines)
A  backend/tests/conftest.py                (+24 lines)
A  backend/tests/test_pvgis_service.py      (+58 lines)
A  backend/tests/test_weather_router.py     (+44 lines)
A  backend/pyproject.toml                   (+5 lines)
M  backend/app/main.py                      (+2 lines)
```

## How to run / verify yourself

```bash
cd ~/pv-solar-estimator/backend
.venv/bin/pytest tests/ -v          # 10 tests, all pass
.venv/bin/uvicorn app.main:app --reload
# Open http://localhost:8000/docs and try POST /api/weather/tmy
```
