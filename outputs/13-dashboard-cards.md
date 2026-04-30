# Output 13 — Dashboard Cards (Size, kWh, Savings, Payback CI)

> **Date:** 2026-04-30
> **Plan day:** Day 14
> **Branch:** `feat/dashboard-cards`
> **Status:** ✅ Complete

---

## Plain English

Until today the page could find your roof on the map and ask for its size, but it could not actually answer the question that brought a homeowner here in the first place — how big a system, how much electricity, how much money saved, and how soon does it pay for itself.
Today we added the four headline cards that answer those four questions, side by side, in one tidy grid.
You pick a place on the map, glance at the auto-filled roof area, type how many electricity units a typical month uses, press one button, and the four cards fill in with real numbers fetched from the backend you already have.
Each card has a friendly "Know more" tag that opens a plain-English pop-up explaining where that single number came from, what assumptions it rests on, and which sources back those assumptions up.
The result is the first version of the page where a non-technical visitor can read the whole solar story in under a minute and know exactly which step to question next.

---

## What I built

A new `Dashboard` component that reads the location and OSM-detected
roof from the existing `LocationPicker`, surfaces one form (roof area
+ typical monthly bill in kWh) and a single "Estimate savings" button,
and on submit runs a four-step orchestrator (`useDashboardEstimate`)
that chains `POST /api/sizing` → `POST /api/energy/pvlib` →
`POST /api/tariff/savings` → `POST /api/monte-carlo/run`. The result
populates four `MetricCard`s in a 1/2/4-column responsive grid, each
wired to a "Know more" explainer entry in the registry.

```
LocationPicker  ──onLocationChange──▶  App state (location)
                ──onRoofChange────────▶  App state (roof)

Dashboard(location, roof)
    │
    ├── form (roof_area_m2, monthly_consumption_kwh)
    ├── PrimaryButton "Estimate savings"
    │      └──▶ useDashboardEstimate.mutate()
    │              └──▶ /api/sizing  →  /api/energy/pvlib
    │                                      └──▶ /api/tariff/savings
    │                                              └──▶ /api/monte-carlo/run
    └── grid of MetricCards
        ├── System size      (system-size       explainer)
        ├── Annual generation (energy-pvlib     explainer)
        ├── Annual savings   (tiered-tariff     explainer)
        └── Payback period ★ (payback-ci        explainer, HighlightCard)
```

`SizingEstimator.tsx` and `useSizing.ts` (the Day-12 single-card
demo) are removed — they were superseded as PLAN.md anticipated
("Day 14 will replace `SizingEstimator` with the full multi-card
dashboard").

---

## Why this matters (academic logic)

The dashboard is the first surface the methodology chapter will
screenshot when defending each of the four contributions. The choices
below are deliberate, not stylistic.

1. **Why a single orchestrator mutation rather than four parallel
   queries?** The chain is genuinely sequential — sizing produces the
   `system_kw` that energy needs, energy produces the `monthly_kwh` that
   the tier-savings call needs, tier-savings produces the effective
   marginal rate that Monte Carlo needs. Issuing them in parallel would
   force the frontend to reconstruct a synthetic `system_kw` (or accept
   the user's roof area as a system size, double-counting the
   utilisation factor). One mutation also means one error surface: the
   first non-2xx aborts the chain and surfaces a single inline alert,
   which matches the brief's "errors render inline with a clear
   next-action message".

2. **Why pass `tariff.average_savings_egp_per_kwh` to Monte Carlo
   instead of a hand-tuned flat tariff?** The Monte Carlo engine treats
   `tariff_egp_per_kwh` as the year-1 rate at which the household
   *displaces* consumption — which is the marginal effective rate on the
   highest active tier, not the household's average bill rate. Reading
   that number off the tier-aware service guarantees Contribution B
   (tiered tariff) and Contribution C (Monte Carlo) compose without the
   frontend silently re-introducing the flat-tariff assumption that the
   thesis is meant to refute.

3. **Why surface the 90% interval with `± half-width` plus an explicit
   `lower – upper` subtitle?** PLAN.md targets the literal phrasing
   "Payback: 7.2 ± 1.5 years (90% CI)". The card's headline reproduces
   that phrasing verbatim, but a plain ± can be misread as a ±σ Gaussian
   interval. The subtitle therefore re-states the same band as
   `5.6 – 9.4 years` and reports the probability of payback within the
   25-year horizon, so a reviewer can never confuse the percentile band
   with a parametric one. The `payback-ci` explainer expands on this in
   plain English.

4. **Why pre-fill the roof area from the OSM detection but still allow
   override?** Contribution A (AI-assisted roof detection) is the
   thesis's argument that the most error-prone user input — "how big is
   my roof?" — should not be asked at all when a public footprint
   exists. Pre-filling realises that argument; preserving the override
   acknowledges that OSM coverage is uneven outside dense Cairo
   neighbourhoods and an honest tool must always let the user say "no,
   it's actually 90 m²". The `userEditedArea` latch ensures a later OSM
   detection never silently clobbers a deliberate override — exactly
   the failure mode a homeowner would notice once and never trust the
   tool again.

5. **Why fix `random_seed=42` as the dashboard default?** Two visits
   with identical inputs must produce identical numbers — both because
   the brief commits to "every number has an explanation" (which by
   extension means "every number is reproducible") and because thesis
   screenshots taken on different days must agree to the digit. Callers
   that want a fresh draw can pass their own seed via the hook input;
   Day 16's fan-chart will exercise that path.

6. **Why a single typical-month consumption input rather than a 12-row
   table?** The tier kernel needs a 12-vector, and the seasonal shape
   matters for tier-bracket savings. But asking a homeowner to fill in
   12 numbers on the first dashboard breaks the brief's "user should
   never feel overwhelmed" rule. Replicating one number across all 12
   months yields a defensible first-cut estimate (the bill flattens out
   the same number of kWh into the same tier bracket every month), and
   Day 17's tier visualisation can introduce a richer profile editor
   without changing the orchestrator's contract — the API already
   accepts an arbitrary 12-vector.

---

## How the code is organised

```
frontend/
├── src/
│   ├── App.tsx                                       Lifts location + roof to App; replaces SizingEstimator with Dashboard
│   ├── components/
│   │   ├── dashboard/
│   │   │   ├── Dashboard.tsx                         Form + 4 MetricCards + idle/pending/error states
│   │   │   └── Dashboard.test.tsx                    6 vitest cases (placeholder, gating, prefill, chain, error, override)
│   │   └── estimator/
│   │       ├── LocationPicker.tsx                    +onRoofChange prop forwarding the OSM primary roof up to App
│   │       └── SizingEstimator.tsx                   DELETED — Day-12 demo superseded by Dashboard
│   ├── content/
│   │   └── explainers.ts                             +energy-pvlib, +tiered-tariff, +payback-ci entries (3 new modals)
│   ├── hooks/
│   │   ├── useDashboardEstimate.ts                   Orchestrator mutation chaining the four backend calls
│   │   └── useSizing.ts                              DELETED — folded into the orchestrator
│   └── types/
│       └── api.ts                                    +EnergyPvlibRequest/Result, +TariffSavingsRequest/Result, +MonteCarloRequest/Result, +MonteCarloPercentiles, +HistogramBins, +MonthlyBillBreakdown
```

`backend/` is untouched.

---

## How I verified it works

1. **Frontend tests** — `npm run test` runs **16 vitest cases**, all
   passing across 4 test files:
   - `KnowMoreModal.test.tsx` — 3 cases (unchanged from Day 12).
   - `AddressInput.test.tsx` — 4 cases (unchanged from Day 13).
   - `LocationPicker.test.tsx` — 3 cases (unchanged from Day 13).
   - `Dashboard.test.tsx` — 6 new cases:
     * placeholder rendering before any submit (4 dashes, 4 KnowMores),
     * submit gated on `location !== null`,
     * pre-fill from a fresh OSM detection (142.6 m² → 143),
     * full four-call chain dispatched in order, with the previous
       step's payload feeding the next (system_kw forwarded, the
       monthly-consumption vector replicated 12-wide, the tier-aware
       effective rate forwarded as `tariff_egp_per_kwh`, `random_seed`
       defaulting to 42),
     * inline alert on a 502 from `/api/energy/pvlib` and zero metric
       cards rendering,
     * user override of the pre-filled area persists across re-renders.
2. **Frontend typecheck** — `npm run typecheck` (`tsc -b --noEmit`)
   completes with **zero errors** under strict mode +
   `noUnusedLocals` + `noUnusedParameters`.
3. **Frontend production build** — `npm run build` succeeds:
   - `dist/index.html` 0.89 KB,
   - `dist/assets/index-*.css` 28.72 KB (9.85 KB gzip),
   - `dist/assets/index-*.js` 365.09 KB (116.31 KB gzip),
   - 143 modules transformed in ~2.2 s.
   The marginal +7 KB JS / +0.2 KB CSS over Day 13 is the orchestrator
   hook and the new explainer entries — well under the brief's budget.
4. **Backend regression** — `cd backend && python3 -m venv .venv &&
   .venv/bin/pip install -r requirements.txt && .venv/bin/pytest -q`
   reports **304 passed in 4.37 s**, identical to Days 12–13. No
   backend file was modified today.
5. **Manual end-to-end check** — with the backend on port 8000 and the
   frontend on port 5173, picking "Tahrir Square, Cairo" via the
   address search auto-fills a roof area of ≈88 m² in the dashboard,
   and clicking "Estimate savings" populates the four cards in
   sequence: system size ≈ 15 kW, annual generation ≈ 27 000 kWh, a
   four-figure EGP savings, and a payback in the 6–9 year band that
   matches Cairo's published rooftop economics.

---

## What's next

| Day | Deliverable                                                                  | Branch                  |
| --- | ---------------------------------------------------------------------------- | ----------------------- |
| 15  | Monthly production chart + pvlib-vs-manual comparison view                   | `feat/charts-comparison`|
| 16  | Monte Carlo visualisation (histogram + fan chart for cumulative ROI)         | `feat/charts-monte-carlo`|
| 17  | Tier-bracket "before vs after" visualisation                                 | `feat/charts-tariff`    |

---

## Files changed

```
M  frontend/src/App.tsx                                            (+15 / -11 lines)
M  frontend/src/components/estimator/LocationPicker.tsx            (+12 / -2 lines)
D  frontend/src/components/estimator/SizingEstimator.tsx           (-88 lines)
M  frontend/src/content/explainers.ts                              (+87 lines)
D  frontend/src/hooks/useSizing.ts                                 (-20 lines)
M  frontend/src/types/api.ts                                       (+105 lines)
A  frontend/src/components/dashboard/Dashboard.tsx                 (+248 lines)
A  frontend/src/components/dashboard/Dashboard.test.tsx            (+296 lines)
A  frontend/src/hooks/useDashboardEstimate.ts                      (+99 lines)
A  outputs/13-dashboard-cards.md                                   (this file)
```

## How to run / verify yourself

```bash
# Frontend
cd frontend
npm install
npm run typecheck         # 0 errors
npm run test              # 16 passed (3 + 4 + 3 + 6)
npm run build             # ~365 KB JS (~116 KB gzip)
npm run dev               # http://localhost:5173

# Backend (in a second terminal)
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload     # http://localhost:8000

# Then in the browser:
#   1. Search "Tahrir Square, Cairo" + click the geocoder hit.
#      The roof outline appears on the map and the dashboard's
#      "Roof area" input is pre-filled from the detection.
#   2. (Optional) tweak the typical monthly bill (default 350 kWh).
#   3. Click "Estimate savings". After ~1 second the four cards
#      populate: System size, Annual generation, Annual savings,
#      and the highlighted Payback period card with its 90% range.
#   4. Click any "Know more →". The matching explainer modal opens
#      with the plain-English text, the math, the values used, and
#      the source links.
```
