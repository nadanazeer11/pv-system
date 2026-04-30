# Output 02 — PV Sizing

> **Date:** 2026-04-30
> **Plan day:** Day 3
> **Branch:** `feat/pv-sizing`
> **Status:** ✅ Complete, 22/22 tests passing (12 new, 10 existing)

---

## Plain English

Today we taught the system how to translate a roof into a solar setup. If you tell it "my roof is one hundred square metres", it now answers back: "you can fit thirty-eight panels, which adds up to a seventeen-kilowatt system." It does this by first deciding how much of the roof is actually usable once you account for things like walkways, the water tank, and the spacing the panels need between rows so they don't shade each other. Then it works out how many full panels fit in that usable space and adds up their power. We were careful to always round the panel count down, because promising more panels than can physically fit would inflate every later number — the savings, the payback time, the carbon savings — and that would mislead the homeowner.

---

## What I built

A backend service that turns a flat roof area into a discrete PV system specification, plus a `POST /api/sizing` endpoint that exposes it independently of the full estimate flow so the frontend can show a live "panels you can fit" preview as the user adjusts the roof area.

Inputs: roof area (m²) and optional per-request overrides for panel rating, panel area, and roof utilization factor (defaults pulled from `app.config.settings`).

Outputs: panel count (integer), system DC capacity (kW), usable roof area, and an echo of every assumption used so the response is self-documenting.

---

## Why this matters (academic logic)

### Why a roof utilization factor (and why 0.7)?

A naïve calculation would simply do `roof_area / panel_area`, but that ignores four physical realities:

1. **Edge setbacks** required by Egyptian fire and maintenance codes.
2. **Walkways** between panel rows for cleaning — non-negotiable in Cairo's high-soiling environment, where un-cleaned panels can lose 15–25 % of yield over a summer.
3. **Inter-row shading spacing.** At Cairo's optimum tilt of 26°, a panel casts a morning/afternoon shadow that would steal yield from any panel packed immediately behind it. The standard mitigation is row spacing of roughly 1.5 × panel chord length.
4. **Roof obstructions.** Egyptian residential rooftops are busy: water tanks, satellite dishes, parapet walls, HVAC condensers, and laundry lines all eat usable area.

The 0.7 factor (i.e. 70 % of roof area is actually usable) is the published rule-of-thumb in Egyptian rooftop PV pre-feasibility studies. It's a deliberate **bulk approximation** — Days 10–11 will replace it with a polygon-clipping geometric model that subtracts obstructions detected from satellite imagery. Until then, 0.7 gives the right order of magnitude.

### Why floor, not round?

A fractional panel is physically meaningless. Rounding **down** is the conservative, installer-realistic choice. Rounding up would be worse than wrong: a system spec that promises capacity the roof cannot actually hold would propagate an upward bias through every downstream financial metric (annual generation → savings → payback → CO₂ avoided). For a thesis defending its own conservatism, this is the right default.

### Why an explicit error for tiny roofs?

If the usable area is smaller than a single panel, the math gives `panel_count = 0` and `system_kw = 0` — technically valid but operationally a footgun: the energy and financial models would happily compute "0 kWh / year" and an undefined payback, and the user would see a confusing zero-everything dashboard. We raise `SizingError` instead, which the router translates to HTTP 422 with a human-readable message. Failing loudly here saves debugging time later.

### Why echo the assumptions in the response?

Reproducibility is a thesis-grade requirement. By returning `panel_rated_watts`, `panel_area_m2`, and `roof_utilization_factor` alongside the result, anyone reading the JSON (a reviewer, a future me, an auditor) can re-derive the math without consulting the server config. It also makes per-request overrides visible — useful for the sensitivity analysis in Week 3.

---

## How the code is organised

```
backend/
├── app/
│   ├── services/
│   │   └── pv_sizing.py        ← compute_system_size + SizingError
│   ├── routers/
│   │   └── sizing.py           ← POST /api/sizing, maps SizingError → 422
│   ├── schemas/
│   │   └── sizing.py           ← SizingRequest, SizingResult (echoes assumptions)
│   └── main.py                 ← wired in the new router
└── tests/
    ├── test_pv_sizing.py       ← 8 service tests (math, floor rule, boundaries, errors)
    └── test_sizing_router.py   ← 4 endpoint tests (happy path, overrides, validation, error mapping)
```

The Egypt-specific defaults (450 W panel, 1.8 m² panel area, 0.7 utilization) live in `app.config.settings` exactly as the project conventions require — no hardcoding inside the service.

---

## How I verified it works

### 1. Unit + router tests
```bash
cd backend
.venv/bin/pytest -q
```
Result: **22 passed** in 0.67 s (12 new, 10 existing). The PVGIS suite still green — no regressions.

### 2. Hand-checked the math against the defaults

| Roof area | Usable (× 0.7) | Panels (floor / 1.8 m²) | System kW (× 450 W) |
|---|---|---|---|
| 100 m² | 70 m² | 38 | 17.1 kW |
| 50 m²  | 35 m² | 19 | 8.55 kW |
| 200 m² | 140 m² | 77 | 34.65 kW |

A 17 kW system on a 100 m² Egyptian rooftop matches the system-size range reported in Egyptian residential PV pre-feasibility literature for similar roof footprints, which gives us confidence the model is calibrated correctly.

### 3. Edge cases covered by tests
- Floor rule (50 m² → 19 panels, not 19.44).
- Boundary at exactly one panel (`roof = panel_area / utilization` → 1 panel).
- Sub-panel roofs raise `SizingError` and surface as HTTP 422.
- Pydantic rejects `roof_area_m2 ≤ 0` and `roof_utilization_factor > 1`.
- Per-request overrides shadow config defaults (verified with 600 W / 2.4 m² / 0.5 case).

### 4. Manual API call (after `uvicorn`)
```bash
curl -X POST http://localhost:8000/api/sizing \
  -H "Content-Type: application/json" \
  -d '{"roof_area_m2": 100}'
# {"roof_area_m2":100.0,"usable_roof_area_m2":70.0,"panel_count":38,
#  "system_kw":17.1,"panel_rated_watts":450.0,"panel_area_m2":1.8,
#  "roof_utilization_factor":0.7,"panel_density_w_per_m2":244.28...}
```

---

## What's next

| Day | Branch | Goal |
|---|---|---|
| 4 | `feat/energy-pvlib` | Feed TMY + system kW into pvlib's PVWatts to get hourly kWh |
| 5 | `feat/energy-manual` | Manual physics model (POA, cell temp, DC→AC) with the same signature for cross-validation |
| 6 | `feat/financial-basic` | Cost, flat-tariff savings, simple payback |

The `SizingResult.system_kw` produced today is exactly the input the Day 4 energy model expects — no further translation needed.

---

## Files changed

```
A  backend/app/services/pv_sizing.py     (+97 lines)
A  backend/app/routers/sizing.py         (+22 lines)
A  backend/app/schemas/sizing.py         (+62 lines)
A  backend/tests/test_pv_sizing.py       (+91 lines)
A  backend/tests/test_sizing_router.py   (+47 lines)
M  backend/app/main.py                   (+2 lines)
A  outputs/02-pv-sizing.md               (this file)
```

## How to run / verify yourself

```bash
cd ~/pv-system/backend
.venv/bin/pytest -q                # 22 tests, all pass
.venv/bin/uvicorn app.main:app --reload
# Open http://localhost:8000/docs and try POST /api/sizing
```
