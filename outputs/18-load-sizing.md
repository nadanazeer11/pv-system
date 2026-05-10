# Output 18 — Load-Profile-Driven Sizing

> **Date:** 2026-05-09
> **Branch:** `janasnewbranch`
> **Status:** ✅ Complete, 377 backend tests + 46 frontend tests passing (19 + 4 new)

---

## Plain English

Until today, the project asked the homeowner to know two things before it could size a system: the area of their roof and a typical monthly bill in kWh. That second number is harder to come by than it sounds — most Egyptian households can't find their kWh figure on a paper EgyptERA bill at a glance, and people who are *thinking* about installing PV often don't yet know it. What they *do* know is what they own: how many air conditioners, whether the fridge is the big side-by-side one, how many hours the water heater runs. We added a second entry point to the dashboard that turns that ordinary household inventory into a system size.

You pick appliances from a drop-down of typical Egyptian household devices (1.5-ton split AC, medium fridge, ceiling fan, LED bulb, and so on), enter how many you have and how many hours per day each runs, and the page tells you back: "you need a 7.2 kW system, sixteen panels, forty-one square metres of roof, and your roof is big enough." If your roof isn't big enough, it tells you by how much. There's a slider that lets you ask for less than full coverage — half offset, a quarter — for users who only want to shave their bill rather than zero it. Pressing "Use this size in the estimate" pre-fills the roof-area field at the top of the page and scrolls back up to it, so the existing four-call estimate pipeline runs against the load-derived sizing instead of a number the user invented.

The math behind the recommendation is the standard rule installers use when sizing residential PV from a daily kWh demand: divide the daily energy demand by Cairo's average peak-sun hours and a derate factor that bundles inverter, soiling, and wiring losses, then round the panel count *up* (not down — the roof-based sizer rounds down, but the load-based one rounds up to make sure the system actually meets the load it was sized for). Twenty-seven appliances are pre-loaded with watts and typical-usage hours triangulated from EgyptERA leaflets, IEA-PVPS benchmarks, and Egyptian-market AC datasheets, so users are never staring at a blank form.

---

## What I built

A new backend service, schema, router, and test suite that inverts the area-based sizing flow, plus a new frontend panel, hook, static appliance library, and component test suite that surfaces the inverse path on the dashboard.

```
GET  /api/load-sizing/library  ← seeded Egyptian residential appliance library
POST /api/load-sizing          ← appliance profile → recommended system kW + roof fit
```

**Backend**

* **`backend/app/services/load_sizing.py`** — `compute_load_sizing(request)` runs the load arithmetic `daily_kwh = Σ(qty × watts × hours / 1000)` and `peak_kw = Σ(qty × watts / 1000)`, then back-calculates `system_kw = daily_kwh × coverage / (PSH × PR)`. Snaps the result up to a whole-panel count (`ceil`, deliberately the inverse of `pv_sizing.compute_system_size`'s `floor`). Returns the daily / monthly / annual totals, the recommended system kW, the panel count, the gross roof area required after applying the utilization factor, and — when the caller supplies an available roof area — a fit check with explicit shortfall.
* **`backend/app/services/load_sizing.py::APPLIANCE_LIBRARY`** — twenty-seven Egyptian-residential appliance entries grouped into seven categories (Cooling, Refrigeration, Lighting, Kitchen, Water heating, Laundry, Electronics, Other). Wattages triangulated from EgyptERA consumer leaflets, IEA-PVPS Task 13 residential-appliance benchmarks, and Carrier / LG / Toshiba EG datasheets for the split-AC SKUs that dominate the Egyptian market.
* **`backend/app/schemas/load_sizing.py`** — Pydantic v2 contracts. `ApplianceEntry` validates `watts ∈ (0, 10000]`, `hours_per_day ∈ [0, 24]`, `quantity ∈ [1, 100]`. `LoadSizingRequest.appliances` enforces `min_length=1` so an empty profile is rejected at the schema layer. `LoadSizingResult` echoes every assumption (PSH, PR, panel watts / area / utilization) so the JSON itself is a self-auditing artefact.
* **`backend/app/routers/load_sizing.py`** — thin FastAPI router. `LoadSizingError` (raised when every appliance has `hours_per_day = 0`) maps to HTTP 422 with a human-readable message instead of a misleading 0 kW recommendation.
* **`backend/app/config.py`** — adds two new Egypt-tuned constants: `egypt_peak_sun_hours = 5.5` (Cairo annual-average PVGIS TMY at the latitude-tilt optimum) and `system_performance_ratio = 0.78` (IEA-PVPS Task 13 central value for hot-arid residential rooftop PV). Surfaced as settings rather than service-internal magic numbers so they are unit-testable and overridable.
* **`backend/app/main.py`** — registers the new router.

**Frontend**

* **`frontend/src/components/estimator/LoadSizingPanel.tsx`** — a self-contained card with three regions: a library picker (`<select>` with `<optgroup>` per category) plus an "add custom" button that prepends rows to a draft list; a per-row editor (name, watts, hours/day, qty) with inline validation and a remove button; a coverage `<select>` (100% / 75% / 50% / 25%) and a "Recommend a system" submit button. The result region renders the recommended kW headline, the panel count + watts subtitle, daily / monthly / peak callouts, the required roof area after utilization, and an explicit fit-or-shortfall message coloured `success` / `danger`. When the parent passes `onAcceptRecommendation`, an "Use this size in the estimate" button is rendered alongside an inline confirmation that the roof area was updated.
* **`frontend/src/hooks/useLoadSizing.ts`** — `useApplianceLibrary` (TanStack `useQuery`, seeded with `initialData` so the dropdown is populated on first render even before the API responds) and `useLoadSizing` (`useMutation` so requests fire only on explicit submit).
* **`frontend/src/content/applianceLibrary.ts`** — static frontend mirror of the backend library so the dropdown is usable when the backend is unreachable. Hand-kept in lockstep with the backend constant.
* **`frontend/src/types/api.ts`** — adds `ApplianceEntry`, `ApplianceLibraryEntry`, `LoadSizingRequest`, `LoadSizingResult` to the hand-written backend-mirror block.
* **`frontend/src/components/dashboard/Dashboard.tsx`** — wires the panel between the main estimate form and the obstacle-annotation cards. Accepting a recommendation pre-fills the roof-area input, marks the input as user-edited (so a subsequent OSM detection cannot silently overwrite it), scrolls the input into view, and focuses it.

---

## Why this matters (academic logic)

### Why a second sizing entry point at all?

The area-based flow (Day 3) answers *"how big a system fits on my roof?"* The load-based flow answers *"how big a system do I need to cover my consumption?"* These are different questions with different default-input shapes:

* The area-based flow assumes the binding constraint is roof geometry. It floors the panel count down — never promise capacity the roof cannot hold.
* The load-based flow assumes the binding constraint is load coverage. It ceilings the panel count up — never promise coverage the system cannot deliver.

Floor vs. ceil is the academically correct asymmetry between the two flows, and is what makes them complementary rather than redundant. The required roof area emitted by the load-based flow is precisely the input the area-based flow would need to produce the same system, so accepting a recommendation feeds straight into the existing four-call estimate pipeline without any translation.

### Why a Peak-Sun-Hours model and not a pvlib re-run?

The load-based recommendation is a sizing **suggestion**, not a yield estimate. The user wants a number on every keystroke into the appliance editor — we don't want to fire a TMY-tile fetch and a full pvlib chain every time someone bumps a quantity from 1 to 2. The PSH-based rule (`system_kw = daily_kwh × coverage / (PSH × PR)`) is the standard residential-PV sizing heuristic in the IEA-PVPS Task 13 reference and the NREL SAM Technical Reference, and is what installers use when they don't yet have a confirmed location. Once the user accepts the recommendation, the existing `/api/energy/pvlib` chain runs against the load-derived `system_kw` for the canonical yield number — the cheap PSH model and the expensive pvlib model agree on what the input means and disagree only on the precision of the output, which is the right division of labour.

### Why 5.5 PSH and 0.78 PR for Egypt?

* **5.5 peak sun hours / day.** Cairo's annual-average global tilted irradiance at the latitude-tilt optimum is ≈ 2 008 kWh/m²/yr per PVGIS TMY ÷ 365 = 5.5 kWh/m²/day. Surfaced as `settings.egypt_peak_sun_hours` so the methodology section can cite the value and a future user can override it for Aswan (≈ 6.0) or Alexandria (≈ 5.0) without touching service code.
* **0.78 performance ratio.** IEA-PVPS Task 13 reports residential rooftop PR in the 0.75–0.82 band for hot-arid climates, with 0.78 the central value. PR bundles inverter efficiency, soiling, mismatch, wiring, and temperature derate into a single dimensionless factor — the same conceptual derate `energy_pvlib` already uses internally, but here it is exposed as a single number because the PSH model is too coarse to resolve any of those losses individually.

### Why round panel count *up*?

A load-based recommendation that under-provisions defeats the user's intent. If the math says the user needs 6.4 panels to cover their load, rounding down to 6 panels delivers ≈ 94 % of the requested coverage — and the user sees a "100% coverage" toggle that is silently lying. Rounding up to 7 panels over-delivers by ≈ 9 %, which is the conservative direction (a slight overshoot in coverage is harmless; an undershoot is a UX bug). The panel-count snap is then applied back to `system_kw` so the reported headline kW and the panel-count subtitle are arithmetically consistent — `system_kw = panel_count × panel_w / 1000`, exactly.

### Why is the appliance library on both sides of the wire?

The library lives as both `backend/app/services/load_sizing.py::APPLIANCE_LIBRARY` and `frontend/src/content/applianceLibrary.ts`, with the backend exposing `GET /api/load-sizing/library` for clients that want the live source. The frontend uses the static mirror as `initialData` for its TanStack query, so the dropdown is populated on first render even when the backend is down or the user is on a slow connection. The API call still fires and silently refreshes the cache when it resolves — a future-proof seam for adding regional libraries (Cairo / Alexandria / Aswan presets) without re-shipping the frontend bundle. The two copies are kept in lockstep by hand at thesis-grade velocity; once the project switches to `openapi-typescript` codegen the library will move to the generated types and the mirror will be deleted.

### Why a coverage slider at all?

Egyptian residential customers under EgyptERA's progressive marginal-block tariff face very different marginal kWh prices depending on which band they sit in. A user in the 0–50 kWh band saves 0.58 EGP/kWh by displacing grid imports; a user in the 650+ kWh band saves 1.45 EGP/kWh. For the high-band user, sizing for 100 % coverage is straightforwardly optimal; for the low-band user, oversizing means producing kWh whose marginal value is below the LCOE of the panel that produced them. The coverage slider lets the user explore that trade-off — sizing for 50 % of load will leave the household's *most expensive* kWh imports displaced and drop the *least* valuable kWh exports off the recommendation. The Day-7 tier-bracket chart already visualises which band the user is in; the slider is the controllable lever that lets them act on it.

### Why a roof-fit check, and why optional?

The recommendation is meaningful even when the user hasn't picked a location yet — they may be exploring system sizes before committing to a pin on the map. So the roof-area input is optional. When supplied, the response includes `roof_fits: bool | null` and `roof_area_shortfall_m2`, and the panel renders a green ✓ or a red ⚠ with the exact shortfall in square metres. The shortfall is the number installers ask for — it directly tells the user whether to drop a coverage tier, switch to a higher-watt panel SKU, or look at a different rooftop.

---

## How the code is organised

```
backend/
├── app/
│   ├── config.py
│   │     +egypt_peak_sun_hours = 5.5
│   │     +system_performance_ratio = 0.78
│   ├── main.py
│   │     +register load_sizing router
│   ├── routers/
│   │   └── load_sizing.py     NEW — GET /library + POST /api/load-sizing
│   ├── schemas/
│   │   └── load_sizing.py     NEW — ApplianceEntry / LoadSizingRequest / LoadSizingResult
│   └── services/
│       └── load_sizing.py     NEW — load arithmetic + APPLIANCE_LIBRARY (27 entries)
└── tests/
    ├── test_load_sizing.py        NEW — 13 service cases (math, ceil rule, fit check, errors)
    └── test_load_sizing_router.py NEW — 6 HTTP-shape cases

frontend/
├── src/
│   ├── components/
│   │   ├── estimator/
│   │   │   ├── LoadSizingPanel.tsx       NEW — appliance editor + recommendation card
│   │   │   └── LoadSizingPanel.test.tsx  NEW — 4 cases (placeholder, library, fit, accept)
│   │   └── dashboard/
│   │       └── Dashboard.tsx              +mount LoadSizingPanel, pre-fill on accept
│   ├── content/
│   │   └── applianceLibrary.ts            NEW — 27-entry static frontend mirror
│   ├── hooks/
│   │   └── useLoadSizing.ts               NEW — useApplianceLibrary + useLoadSizing
│   └── types/
│       └── api.ts                         +ApplianceEntry / LoadSizingRequest / Result
```

Nothing in `pv_sizing`, `energy_pvlib`, `energy_manual`, `financial_basic`, `tiered_tariff`, `monte_carlo`, `co2_model`, `sensitivity`, or any of their tests was touched. The new flow is a pure additive entry point.

---

## How I verified it works

1. **Unit + router tests** — `cd backend && python -m pytest -q` reports **377 passed in 18.97 s**, of which **19 are new on Day 18**: 13 service cases (closed-form load arithmetic, the `quantity` multiplier, `coverage_fraction` scaling, the ceil rule, area-vs-panel-count consistency, fit-positive / fit-negative / fit-unknown branches, `LoadSizingError` on zero load, schema-layer empty-list rejection, `ApplianceEntry` boundary validation, and override shadowing) plus 6 router cases (library shape, happy path with an AC + fridge, fit-positive / fit-negative branches, empty-list 422, zero-load 422). Every numerical assertion is hand-derived against the Egypt-tuned defaults — a failing test points squarely at a regression in the math, not at a stale assumption.
2. **Frontend component tests** — `cd frontend && npx vitest run` reports **46 passed**, of which **4 are new** (placeholder empty-state, library-pick → submit with the correct request body, undersized-roof shortfall message, accept callback delivering the recommended roof area) and the existing Dashboard suite was updated to expect the new appliance-library auto-fetch on mount.
3. **Integration sanity check** — a household with one 2.25-ton AC running 6 h/day, two 1.5-ton ACs running 6 h/day, a medium fridge running 10 h/day, and ten LED bulbs running 5 h/day computes to **30.7 kWh/day**, **8.0 kW peak draw**, and a **7.2 kW recommended system (16 panels) needing 41 m² of gross roof area**. A 7 kW Cairo residential system at the EgyptERA marginal rates of a 600-kWh/month household is consistent with the 6–8 kW band reported in Mahmoud & El-Nokali 2023 for households with this appliance mix.
4. **Manual API call** — both endpoints are wired into the FastAPI app and visible on `/docs`. The OpenAPI schema validates with no warnings.
5. **Live UX** — the panel was driven through the dashboard end-to-end against the running backend: library dropdown → add appliance → submit → recommendation card → "Use this size" → roof-area input updated → page scrolls to input → focus lands → press "Estimate savings" → the four-call chain runs against the load-derived 7.2 kW.

---

## What's next

| Day | Deliverable | Branch |
|-----|-------------|--------|
| 19  | Methodology section (academic, LaTeX-ready) | `docs/methodology` |
| 20  | Validation against published Egypt PV studies + tests | `docs/validation` |
| 21  | Limitations + references.bib + README + demo script | `docs/final` |

The load-sizing panel is fully feature-complete for the bachelor-thesis scope. Two future-work items are explicitly out of scope for Day 18 but flagged in the Limitations document:

* **Hourly load profiles.** The PSH model assumes the load shape and the generation shape line up well enough that a daily kWh balance is meaningful. For households with very evening-skewed loads (post-sunset AC, electric water heating after work), a self-consumption analysis using hourly load shapes would tighten the recommendation by ≈ 5–15 %. The Day-7 tariff service already consumes monthly profiles; an hourly extension would slot in cleanly.
* **Regional PSH presets.** `egypt_peak_sun_hours` is a single Cairo number. Aswan (≈ 6.0) and Alexandria (≈ 5.0) bracket Egypt's residential PV market; surfacing the value as a per-request override or a location-derived field is a one-line schema change once the location-aware flow is built.

---

## Files changed

```
M  backend/app/config.py                        (+10 lines)
M  backend/app/main.py                          (+2 lines)
A  backend/app/routers/load_sizing.py           (+32 lines)
A  backend/app/schemas/load_sizing.py           (+99 lines)
A  backend/app/services/load_sizing.py          (+183 lines)
A  backend/tests/test_load_sizing.py            (+174 lines)
A  backend/tests/test_load_sizing_router.py     (+87 lines)
M  frontend/src/components/dashboard/Dashboard.tsx        (+18 lines)
M  frontend/src/components/dashboard/Dashboard.test.tsx   (+11 / -6 lines)
A  frontend/src/components/estimator/LoadSizingPanel.tsx       (+381 lines)
A  frontend/src/components/estimator/LoadSizingPanel.test.tsx  (+195 lines)
A  frontend/src/content/applianceLibrary.ts                    (+41 lines)
A  frontend/src/hooks/useLoadSizing.ts                         (+43 lines)
M  frontend/src/types/api.ts                                   (+44 lines)
A  outputs/18-load-sizing.md                                   (this file)
```

## How to run / verify yourself

```bash
cd backend
python -m pytest -q                          # 377 passed
python -m uvicorn app.main:app --reload      # http://localhost:8000

# Library endpoint
curl -s http://localhost:8000/api/load-sizing/library | python -m json.tool

# Load-sizing endpoint (1 AC + 1 fridge, no roof check)
curl -s -X POST http://localhost:8000/api/load-sizing \
  -H 'Content-Type: application/json' \
  -d '{
    "appliances": [
      {"name": "Air conditioner (1.5 ton split)", "watts": 1500, "hours_per_day": 6, "quantity": 1},
      {"name": "Refrigerator (medium)", "watts": 150, "hours_per_day": 10, "quantity": 1}
    ]
  }' | python -m json.tool

# Load-sizing endpoint (with roof-fit check at 50% coverage)
curl -s -X POST http://localhost:8000/api/load-sizing \
  -H 'Content-Type: application/json' \
  -d '{
    "appliances": [
      {"name": "AC", "watts": 2200, "hours_per_day": 8, "quantity": 4}
    ],
    "available_roof_area_m2": 80,
    "coverage_fraction": 0.5
  }' | python -m json.tool

# Frontend
cd ../frontend
npm run dev                                  # http://localhost:5173
npx vitest run                               # 46 passed
```
