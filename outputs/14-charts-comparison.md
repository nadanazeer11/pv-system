# Output 14 — Monthly Production Chart + pvlib-vs-Manual Comparison

> **Date:** 2026-05-01
> **Plan day:** Day 15
> **Branch:** `feat/charts-comparison`
> **Status:** ✅ Complete

---

## Plain English

Until today the page printed four headline numbers — system size, yearly electricity, yearly savings, and how soon the system pays for itself — but said nothing about how those numbers were checked.
Today we added a second view, right under the four cards, that compares two completely separate ways of guessing how much electricity the panels will actually produce.
A simple bar chart shows month by month, January through December, what each method expects, so a homeowner can see the summer peak that any honest Cairo simulation has to reproduce.
A side-by-side panel above the chart shows the two yearly totals and the gap between them, and tells the reader in plain words whether the two methods agree well, agree roughly, or disagree enough to be worth a closer look.
The result is the first version of the dashboard where every headline number visibly stands on more than one source.

---

## What I built

A new `charts/` family of components and a small extension to the dashboard's data orchestrator.

```
LocationPicker  ──onLocationChange──▶  App state
                ──onRoofChange────────▶  App state

Dashboard(location, roof)
  ├── form (roof_area_m2, monthly_consumption_kwh)
  ├── PrimaryButton "Estimate savings"
  │     └──▶ useDashboardEstimate.mutate()
  │            ├──▶ /api/sizing
  │            ├──▶ /api/energy/pvlib   ─┐ Promise.all (parallel)
  │            ├──▶ /api/energy/manual  ─┘
  │            ├──▶ /api/tariff/savings
  │            └──▶ /api/monte-carlo/run
  ├── grid of 4 MetricCards (unchanged from Day 14)
  └── new <section data-testid="model-comparison-section">  ← Day-15
        ├── <ModelComparisonView pvlib manual />            ← annual residual + verdict
        └── <MonthlyProductionChart pvlib manual />         ← 12 grouped bars + sr-only table
```

Concretely:

- `frontend/src/components/charts/ModelComparisonView.tsx` — three-column grid (pvlib annual, manual annual, residual highlight). Classifies the residual into "strong / reasonable / divergent" agreement bands. Owns the `model-comparison` Know-more button.
- `frontend/src/components/charts/MonthlyProductionChart.tsx` — Recharts grouped bar chart with 12 months × 2 series, plus an `sr-only` `<table>` with the same numbers (per-row pvlib, manual, Δ kWh, Δ %). Owns the `monthly-production` Know-more button.
- `frontend/src/hooks/useDashboardEstimate.ts` — fans the two energy calls out in parallel via `Promise.all`. pvlib remains the canonical input to tariff and Monte Carlo; manual is consumed only by the comparison surface.
- `frontend/src/types/api.ts` — new `EnergyManualRequest` / `EnergyManualResult` types mirroring `backend/app/schemas/energy.py::EnergyManualResult`.
- `frontend/src/content/explainers.ts` — three new entries: `energy-manual` (Day-12 placeholder slot, finally filled), `model-comparison` (the brief's required modal for the comparison view), and `monthly-production` (the brief's pattern of one explainer per chart).

The backend is untouched — `/api/energy/manual` is the same endpoint the manual physics service shipped on Day 5.

---

## Why this matters (academic logic)

The dual-energy backbone is the thesis's first contribution and the one
the methodology chapter leans on hardest. The choices below are
deliberate.

1. **Why surface a second simulation as a *first-class* dashboard
   surface, not a hidden tab?** Most published rooftop calculators run
   one chain and report one number. The thesis argues that a single
   number with no agreement check is methodologically weaker than two
   numbers that agree to within a stated band. Promoting the residual
   to a dedicated panel — visible without an extra click — makes the
   cross-validation argument legible to a homeowner *and* to a
   reviewer. The fact that the user sees the residual at all is the
   methodological claim.

2. **Why three classification bands (`< 5%`, `5–10%`, `> 10%`) rather
   than a continuous number?** Continuous residuals invite over-reading
   ("3.4% means the manual model is wrong"). Agreement bands match how
   the pvlib documentation itself reports against PVSyst — a single-digit
   percent gap is the noise floor of any TMY-driven simulation, not a
   bug. The thresholds are written into the explainer so a reviewer can
   challenge or re-tune them without code changes.

3. **Why parallelise the two energy calls instead of running them
   sequentially?** The manual chain and the pvlib chain are
   functionally independent — they share inputs (location, system_kw)
   but neither consumes the other's output. Running them sequentially
   would double the dashboard's wall-clock time for no gain, because
   PVGIS itself is the per-call latency floor (~1 s round-trip from
   Egypt). `Promise.all` collapses them onto a single network round-trip
   window. The trade-off is that on the error path the rejection comes
   from whichever chain fails first; the dashboard's existing inline
   alert handles either, and the test suite explicitly covers a pvlib
   502 with manual returning 200.

4. **Why keep pvlib (not manual) as the canonical input to tariff and
   Monte Carlo?** A reviewer could argue we should average the two, or
   pick the more conservative. The thesis defence is the opposite: the
   downstream financial chain must be reproducible against a single,
   citeable model — pvlib's PVWatts implementation is the most widely
   cited rooftop-PV reference in the literature and is the model the
   methodology chapter will reference for tariff and payback maths.
   The manual chain's role is to *audit* pvlib, not to replace it.
   Mixing the two would muddy that audit relationship.

5. **Why grouped bars instead of overlaid lines?** The reader's primary
   question is "do the two simulations agree this month?", not "how
   does this month compare to last month?" Grouped bars put the two
   numbers physically next to each other for every month, so a reader
   can read the gap directly off the chart without having to mentally
   subtract two line points. The seasonal shape (Cairo summer peak)
   remains legible because the bars are still time-ordered along the
   x-axis.

6. **Why a screen-reader-only `<table>`?** The Frontend Design Brief
   makes it non-negotiable: "All charts have a fallback `<table>` for
   screen readers." The `sr-only` table also doubles as the primary
   testable surface — happy-dom does not honour Recharts'
   `ResponsiveContainer` measurements (the SVG renders at 0×0), so
   asserting on the SVG would yield brittle tests. Asserting on the
   semantic table tests the data, which is what a reviewer cares about.

7. **Why give every chart its own `Know more` button rather than reuse
   the cards' explainers?** The brief lists `model-comparison` and
   `monthly-production` as required explainer ids. A homeowner who
   clicks a chart should be told *what they are looking at right now*,
   not redirected back to a card. The single registry pattern (one
   `explainers.ts` source of truth) means each new explainer is a
   one-file change.

---

## How the code is organised

```
frontend/
├── src/
│   ├── components/
│   │   ├── charts/                          NEW directory (Day 15)
│   │   │   ├── ModelComparisonView.tsx        Annual residual panel + agreement band
│   │   │   ├── ModelComparisonView.test.tsx   6 vitest cases (totals, residuals, bands, ±, KnowMore)
│   │   │   ├── MonthlyProductionChart.tsx     Recharts grouped bars + sr-only fallback table
│   │   │   └── MonthlyProductionChart.test.tsx 4 vitest cases (table, aria-label, KnowMore, defensive)
│   │   └── dashboard/
│   │       ├── Dashboard.tsx                  Mounts the comparison <section> when data is ready
│   │       └── Dashboard.test.tsx             Updated for the 5-call chain + section visibility
│   ├── content/
│   │   └── explainers.ts                      +energy-manual, +model-comparison, +monthly-production
│   ├── hooks/
│   │   └── useDashboardEstimate.ts            +Promise.all over /api/energy/{pvlib,manual}
│   └── types/
│       └── api.ts                             +EnergyManualRequest / +EnergyManualResult
├── package.json                               +recharts dependency
└── package-lock.json
```

`backend/` is untouched.

---

## How I verified it works

1. **Frontend tests** — `npm run test` runs **26 vitest cases** across
   **6 test files**, all green:
   - `KnowMoreModal.test.tsx` — 3 cases (unchanged from Day 12).
   - `AddressInput.test.tsx` — 4 cases (unchanged from Day 13).
   - `LocationPicker.test.tsx` — 3 cases (unchanged from Day 13).
   - `Dashboard.test.tsx` — 6 cases (Day 14, three of them rewritten):
     placeholder + comparison-hidden, submit-gating, OSM pre-fill, the
     **five-call chain** (sizing → pvlib + manual in parallel → tariff
     → monte-carlo) with all five payloads asserted, error-path with
     comparison section never mounted, and override persistence.
   - `ModelComparisonView.test.tsx` — 6 new cases: both annuals
     rendered, residual sign + percentage, < 5% → "strong agreement",
     5–10% → "reasonable agreement", > 10% → "material divergence",
     positive residual prefixes a `+`, KnowMore present.
   - `MonthlyProductionChart.test.tsx` — 4 new cases: 12-row sr-only
     fallback table with January numbers, accessible chart container
     `aria-label`, KnowMore present, defensive zero-fill of short input
     arrays still produces 12 rows.
2. **Frontend typecheck** — `npm run typecheck` (`tsc -b --noEmit`)
   completes with **zero errors** under strict mode. The `Tooltip`
   formatter is untyped at the call site (`(value, name)`) because
   Recharts' v2 `Formatter<ValueType, NameType>` declares its arguments
   as a union; we coerce via `Number(value)` and `String(name)` rather
   than locally pinning the generics.
3. **Frontend production build** — `npm run build` succeeds:
   - `dist/index.html` 0.89 KB,
   - `dist/assets/index-*.css` 29.31 KB (9.95 KB gzip),
   - `dist/assets/index-*.js` 743.30 KB (229.48 KB gzip),
   - 851 modules transformed in ~4.3 s.
   The +378 KB JS / +0.6 KB CSS over Day 14 is Recharts and its
   d3-shape / d3-scale dependencies. Day 18+ will revisit code-splitting
   the chart bundle once Days 16 and 17 finish loading additional chart
   primitives — the Vite warning about chunks > 500 KB is the canonical
   trigger to do that.
4. **Backend regression** — `cd backend && python3 -m venv .venv &&
   .venv/bin/pip install -r requirements.txt && .venv/bin/pytest -q`
   reports **304 passed in 3.62 s**, identical to Days 12–14. No
   backend file was modified today.
5. **Manual end-to-end check (mental)** — picking a Cairo address and
   pressing "Estimate savings" now triggers the five-call chain. Both
   energy results land within the same network window because they're
   issued in parallel, the dashboard's four headline cards populate as
   before, and below them the comparison panel renders the two annuals
   and the residual classified into one of the three agreement bands.
   The monthly chart below shows 12 grouped bars in Jan→Dec order with
   pvlib (dark) and manual (lime). Both surfaces expose a Know-more
   pill that opens the matching explainer modal.

---

## What's next

| Day | Deliverable                                                              | Branch                    |
| --- | ------------------------------------------------------------------------ | ------------------------- |
| 16  | Monte Carlo visualisation (histogram + fan chart for cumulative ROI)     | `feat/charts-monte-carlo` |
| 17  | Tier-bracket "before vs after" visualisation                             | `feat/charts-tariff`      |
| 18  | CO₂ savings + Egypt grid emission factor + sensitivity tornado           | `feat/co2-sensitivity`    |

---

## Files changed

```
M  frontend/package.json                                               (+1 line)
M  frontend/package-lock.json                                          (+409 lines)
A  frontend/src/components/charts/ModelComparisonView.tsx              (+133 lines)
A  frontend/src/components/charts/ModelComparisonView.test.tsx         (+80 lines)
A  frontend/src/components/charts/MonthlyProductionChart.tsx           (+174 lines)
A  frontend/src/components/charts/MonthlyProductionChart.test.tsx      (+71 lines)
M  frontend/src/components/dashboard/Dashboard.tsx                     (+16 lines)
M  frontend/src/components/dashboard/Dashboard.test.tsx                (+67 / -16 lines)
M  frontend/src/content/explainers.ts                                  (+91 lines)
M  frontend/src/hooks/useDashboardEstimate.ts                          (+42 / -8 lines)
M  frontend/src/types/api.ts                                           (+22 lines)
A  outputs/14-charts-comparison.md                                     (this file)
```

## How to run / verify yourself

```bash
# Frontend
cd frontend
npm install
npm run typecheck         # 0 errors
npm run test              # 26 passed (3 + 4 + 3 + 6 + 6 + 4)
npm run build             # ~743 KB JS (~229 KB gzip)
npm run dev               # http://localhost:5173

# Backend (in a second terminal)
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload     # http://localhost:8000

# Then in the browser:
#   1. Search "Tahrir Square, Cairo" + click the geocoder hit. The
#      roof outline appears on the map and the dashboard's "Roof area"
#      input is pre-filled from the OSM detection.
#   2. Click "Estimate savings". After ~1 second the four cards
#      populate, and immediately below them a new "Why two energy
#      models?" panel and "Monthly production" chart appear.
#   3. Read the "Residual" highlight card — it shows the kWh and %
#      gap between the two simulations and labels the agreement band.
#   4. Hover any monthly bar to see the kWh tooltip; tab through the
#      page with a screen reader and the same data is read off the
#      sr-only table.
#   5. Click any "Know more →" — model-comparison and monthly-production
#      open the matching explainer modals.
```
