# Output 15 — Monte Carlo Histogram + Cumulative-ROI Fan Chart

> **Date:** 2026-05-01
> **Plan day:** Day 16
> **Branch:** `feat/charts-monte-carlo`
> **Status:** ✅ Complete

---

## Plain English

Until today the page told a homeowner one number for how soon the panels pay for themselves and a small range around it, but never showed what was inside that range or how the savings actually pile up year by year.
Today we added two new pictures right under the existing comparison view that open up the uncertainty.
The first picture is a tall-bar chart that counts how many imagined futures finish paying off in each year — most of them clustered together, a few stragglers either side, with three small markers calling out the headline year and the edges of the most-likely band.
The second picture is a widening green ribbon that follows the project's running balance from day one all the way through year twenty-five, dipping deeply negative at the start, climbing back up, and crossing zero somewhere around the headline year — with a darker line in the middle to show the most likely path and the ribbon getting wider each year because surprises stack up over time.
Together they turn the single sentence "payback is about seven years, give or take" into something a reader can actually see and judge for themselves.

---

## What I built

A new "Monte Carlo uncertainty" dashboard section, plus the small backend extension that makes the fan chart possible.

```
Dashboard(location, roof)
  ├── form (unchanged)
  ├── 4 MetricCards (unchanged from Day 14)
  ├── <section data-testid="model-comparison-section">  ← Day-15
  │     ├── ModelComparisonView
  │     └── MonthlyProductionChart
  └── <section data-testid="monte-carlo-section">       ← Day-16 (new)
        ├── <MonteCarloHistogram histogram percentiles probability nSimulations />
        └── <ROIFanChart trajectory medianPaybackYear />
```

Concretely:

- `backend/app/schemas/monte_carlo.py` — new `CumulativeCashFlowTrajectory` model. Year-by-year (length T+1) percentile bands of the discounted cumulative cash flow.
- `backend/app/services/monte_carlo.py` — `_vectorised_discounted_payback` now returns the (N, T+1) cumulative matrix it already builds; `_trajectory_from_cumulative` aggregates that matrix into column-wise percentile bands; `run_monte_carlo` wires the new field onto the response. **No** new sampling, no new RNG draws — the trajectory is a free byproduct of the matrix the kernel already computed for payback.
- `backend/tests/test_monte_carlo.py` — six new structural tests covering: trajectory length, year-0 negative-capex invariant, percentile band ordering at every year, zero-variance collapse to the deterministic chain, end-of-horizon median ≡ NPV median (under zero variance), and uncertainty-widens-with-time monotonicity.
- `frontend/src/types/api.ts` — `CumulativeCashFlowTrajectory` type, plus the new field on `MonteCarloResult`.
- `frontend/src/components/charts/MonteCarloHistogram.tsx` — Recharts `BarChart` of the existing `payback_histogram` with vertical reference lines at p05, p50, and p95. Owns the brief-required `monte-carlo` Know-more button.
- `frontend/src/components/charts/ROIFanChart.tsx` — Recharts `ComposedChart` rendering the cumulative trajectory as five stacked-area bands (the lowest is invisible to lift the stack off the y-axis, then four visible ribbons p05–p25, p25–p50, p50–p75, p75–p95) plus a bold dashed median `Line`, a horizontal zero-line and a vertical "Median payback ≈ year N" reference line. Owns a new `roi-fan` Know-more button.
- Both charts ship the brief's mandatory `sr-only` `<table>` fallback so screen-reader users get the same numbers a sighted reader sees.
- `frontend/src/content/explainers.ts` — two new entries: `monte-carlo` (the brief-required modal for the histogram) and `roi-fan` (one explainer per chart, matching the pattern Day 15 established).
- `frontend/src/components/dashboard/Dashboard.tsx` — mounts the new `monte-carlo-section` once an estimate has succeeded.

The dashboard data orchestrator (`useDashboardEstimate`) is **untouched** — the trajectory rides on the same Monte Carlo response that the headline payback card has consumed since Day 14, so no extra round-trip was added.

---

## Why this matters (academic logic)

Contribution C of the thesis is "report distributions, not point estimates." The Day 14 dashboard showed the mean ± half-band on a single card; the present surface is what the contribution actually claims to deliver.

1. **Why surface a histogram even though the headline card already shows ± a number?** A `7.2 ± 1.5 yr` interval implicitly assumes the underlying distribution is roughly symmetric. Payback under Egyptian assumptions is *not* symmetric: the right tail of "very-bad-weather × very-aggressive-degradation" is fatter than the left tail because both factors are bounded below (degradation can't go negative, weather yield is clipped at 0.5). A homeowner reading "7.2 ± 1.5" should be able to verify that the cloud is well-behaved, and a thesis examiner should be able to point at the asymmetry directly. The histogram is the only visualisation that lets either reader do that.

2. **Why a cumulative-cash-flow fan rather than another distribution view (e.g. NPV histogram)?** A homeowner's mental model of "is this worth it?" is a running balance that starts deeply negative on day one and (hopefully) climbs into positive territory before the inverter dies. The fan chart matches that mental model directly: every reader can read the year-of-zero-crossing off the chart without having to internalise what NPV means. The NPV histogram remains useful as a thesis appendix figure but is not the primary surface a homeowner needs.

3. **Why column-wise percentile bands rather than a few representative simulation paths?** A "spaghetti plot" of 1,000 individual paths would be visually illegible *and* would over-state the chart's claim — Recharts cannot honestly draw 1,000 lines, and any subset of 5–10 sample paths would imply the user is looking at "typical futures" when they are looking at *whichever futures the sampler happened to pick*. Column-wise (envelope) percentiles are the correct framing: at every year, the band tells the reader where the middle 50/90 % of futures lie, regardless of which futures they are. The trade-off — that the bands do not correspond to single coherent simulation paths — is documented in the `roi-fan` explainer modal so a reviewer cannot mis-read the chart.

4. **Why compute the trajectory inside the kernel rather than re-running the simulation client-side?** Two reasons. First, the cumulative-cash-flow matrix is *already constructed* inside `_vectorised_discounted_payback` to find the year of zero-crossing — exposing it costs zero additional sampling and zero additional algebra. Second, recomputing the trajectory on the frontend would require shipping the entire cash-flow algebra (capex, discounting, inverter event, degradation, tariff inflation, O&M) twice — once in Python and once in TypeScript — which is exactly the model-drift problem the thesis spent Day 6 building cross-service invariants to prevent. The backend is and remains the single source of truth for the financial chain.

5. **Why one inverter replacement event in the trajectory rather than rolling that knob to two?** This was already a Day-9 decision, but it is worth re-stating in the context of the fan chart: a discrete event in year 12 ± 2 will show up as a noticeable downward kick in the median trajectory, and a reviewer who can see that kick can challenge it independently of the rest of the calculation. The methodology chapter (Day 19) will reference this exact figure to defend the single-replacement assumption.

6. **Why three reference markers (p05, p50, p95) on the histogram?** The histogram's purpose is to let the reader map the headline `± 1.5 yr` back onto the cloud. Drawing the same three percentile markers that the headline card consumes makes that mapping unambiguous. Drawing more markers (p25/p75 from the IQR) would add visual clutter without adding new information for a homeowner — the IQR is best read off the fan chart, where it is rendered as a darker ribbon.

7. **Why fall back to a `sr-only` `<table>` for both charts?** The Frontend Design Brief is non-negotiable: "All charts have a fallback `<table>` for screen readers." The fallback table also doubles as the primary testable surface, since happy-dom does not honour Recharts' `ResponsiveContainer` measurements (the SVG renders at 0×0). Asserting on the semantic table tests the data the chart is meant to communicate, which is what a reviewer cares about; asserting on the SVG would be brittle and would test the renderer rather than the model.

8. **Why a vertical reference line marking "Median payback ≈ year N" on the fan chart?** Without it, the reader has to triangulate between the median line crossing zero and the x-axis tick marks, which is a lot to ask of a single glance. The reference line links the headline card's number directly to its visual representation in the chart, which is the brief's "every number has an explanation" rule extended one step further: every number has a *visual* explanation as well.

---

## How the code is organised

```
backend/
├── app/
│   ├── schemas/
│   │   └── monte_carlo.py                  +CumulativeCashFlowTrajectory + field on MonteCarloResult
│   └── services/
│       └── monte_carlo.py                  +_trajectory_from_cumulative; _vectorised_… now returns cum matrix
└── tests/
    └── test_monte_carlo.py                 +6 trajectory tests (length, sign, ordering, collapse, NPV identity, widening)

frontend/
├── src/
│   ├── components/
│   │   ├── charts/                         (Day-15 directory, extended)
│   │   │   ├── MonteCarloHistogram.tsx       NEW — bar chart + p05/p50/p95 reference lines + sr-only table
│   │   │   ├── MonteCarloHistogram.test.tsx  NEW — 5 vitest cases (table, aria-label, KnowMore, prob-pct, summary)
│   │   │   ├── ROIFanChart.tsx               NEW — composed area+line + zero-line + payback marker + sr-only table
│   │   │   └── ROIFanChart.test.tsx          NEW — 5 vitest cases (table, aria-label, KnowMore, null-payback, finite-payback)
│   │   └── dashboard/
│   │       ├── Dashboard.tsx                 +monte-carlo-section block, mounts both new charts on success
│   │       └── Dashboard.test.tsx            +trajectory in mock; +monte-carlo-section visibility assertions
│   ├── content/
│   │   └── explainers.ts                     +monte-carlo (brief-required) + roi-fan (one-per-chart pattern)
│   └── types/
│       └── api.ts                            +CumulativeCashFlowTrajectory + field on MonteCarloResult
└── (no other files changed)
```

`useDashboardEstimate.ts`, `MetricCard`, `ModelComparisonView`, `MonthlyProductionChart`, the layout components and the Day-13 input surfaces are all untouched.

---

## How I verified it works

1. **Backend tests** — `cd backend && .venv/bin/pytest -q` reports **310 passed in 3.50 s** (304 from Day 15 + 6 new trajectory tests), no warnings, no skips. Test file: `backend/tests/test_monte_carlo.py`.
2. **Backend trajectory test invariants** — explicitly verified:
   - `year_index == range(T+1)` and every band has the same length (length test).
   - `year-0 cumulative < 0` for every band — the capex draw is unambiguously a hole.
   - `p05 ≤ p25 ≤ p50 ≤ p75 ≤ p95` at every year (no ribbon crossings).
   - Under zero variance, every percentile band collapses onto the deterministic median curve to within 1e-6, and the median curve crosses zero exactly at the deterministic payback year reported in the same response.
   - Under zero variance, `p50[-1]` of the trajectory is bit-identical to `npv_egp.p50` — algebra check.
   - Under default (non-zero) variance, the IQR at the analysis horizon is materially wider than at year 0, confirming uncertainty propagates and accumulates.
3. **Frontend tests** — `cd frontend && npm run test` reports **36 passed in 8 files**, all green:
   - `KnowMoreModal.test.tsx` (3) — unchanged.
   - `AddressInput.test.tsx` (4), `LocationPicker.test.tsx` (3) — unchanged.
   - `ModelComparisonView.test.tsx` (6), `MonthlyProductionChart.test.tsx` (4) — unchanged from Day 15.
   - `MonteCarloHistogram.test.tsx` (5 NEW) — sr-only fallback table with one row per bin (6 bins → 7 rows including header), aria-label on the chart container, KnowMore button present, payback-probability rendered as a percentage, percentile summary strip carries p50, p05, p95 plus the "500 / 1,000" total-vs-ensemble counter.
   - `ROIFanChart.test.tsx` (5 NEW) — sr-only fallback table with one row per year (26 rows + header for a 25-year horizon), aria-label, KnowMore, null-payback case omits the median-payback caption, finite-payback case renders "Median payback ≈ year 6.0".
   - `Dashboard.test.tsx` (6, three updated) — placeholder state hides both Day-15 and Day-16 sections; success path mounts `monte-carlo-section`, both chart titles and the median-payback marker are readable; error path keeps both sections hidden.
4. **Frontend typecheck** — `npm run typecheck` (`tsc -b --noEmit`) completes with **zero errors** under strict mode. Recharts v3's `Legend` no longer accepts a hand-built `payload` array, so the fan chart's legend is rendered as plain HTML below the chart instead — same information, type-safe, and bonus accessibility (it is a real `<ul>` with an `aria-label="Legend"`).
5. **Frontend production build** — `npm run build` succeeds:
   - `dist/index.html` 0.89 KB,
   - `dist/assets/index-*.css` 29.58 KB (9.99 KB gzip),
   - `dist/assets/index-*.js` 788.32 KB (239.75 KB gzip),
   - 853 modules transformed in ~4.4 s.
   - The +45 KB JS / +0.3 KB CSS over Day 15 is the additional Recharts primitives (`ComposedChart`, `Area`, `ReferenceLine`) plus the two new components themselves. The chunk-size warning has been raised since Day 14 and remains the canonical signal to revisit code-splitting once Day 17's tariff chart lands and the chart bundle is feature-complete.
6. **Manual end-to-end check (mental)** — picking a Cairo address and pressing "Estimate savings" runs the same five-call chain as Day 15 (sizing → pvlib + manual in parallel → tariff → monte-carlo). The Monte Carlo response now carries a `cumulative_cash_flow_trajectory` field, which the dashboard's new `monte-carlo-section` consumes end-to-end. The histogram shows the payback cloud with the headline percentiles called out; the fan chart shows the running balance climbing through zero around the median payback year. Both charts expose a Know-more pill that opens the matching explainer modal.

---

## What's next

| Day | Deliverable                                                              | Branch                    |
| --- | ------------------------------------------------------------------------ | ------------------------- |
| 17  | Tier-bracket "before vs after" visualisation                             | `feat/charts-tariff`      |
| 18  | CO₂ savings + Egypt grid emission factor + sensitivity tornado           | `feat/co2-sensitivity`    |
| 19  | Methodology section (academic, LaTeX-ready)                              | `docs/methodology`        |

---

## Files changed

```
M  backend/app/schemas/monte_carlo.py                                  (+44 lines)
M  backend/app/services/monte_carlo.py                                 (+45 / -7 lines)
M  backend/tests/test_monte_carlo.py                                   (+104 lines)
A  frontend/src/components/charts/MonteCarloHistogram.tsx              (+203 lines)
A  frontend/src/components/charts/MonteCarloHistogram.test.tsx         (+102 lines)
A  frontend/src/components/charts/ROIFanChart.tsx                      (+330 lines)
A  frontend/src/components/charts/ROIFanChart.test.tsx                 (+57 lines)
M  frontend/src/components/dashboard/Dashboard.tsx                     (+25 lines)
M  frontend/src/components/dashboard/Dashboard.test.tsx                (+21 lines)
M  frontend/src/content/explainers.ts                                  (+60 lines)
M  frontend/src/types/api.ts                                           (+21 lines)
A  outputs/15-charts-monte-carlo.md                                    (this file)
```

## How to run / verify yourself

```bash
# Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q                          # 310 passed
.venv/bin/uvicorn app.main:app --reload      # http://localhost:8000

# Frontend (in a second terminal)
cd frontend
npm install
npm run typecheck                            # 0 errors
npm run test                                 # 36 passed across 8 files
npm run build                                # ~788 KB JS (~240 KB gzip)
npm run dev                                  # http://localhost:5173

# Then in the browser:
#   1. Search "Tahrir Square, Cairo" + click the geocoder hit. The
#      roof outline appears on the map and the dashboard's "Roof
#      area" input is pre-filled from the OSM detection.
#   2. Click "Estimate savings". After ~1 second the four cards
#      populate, immediately below them the Day-15 model-comparison
#      and monthly-production charts appear, and below those the new
#      "Payback distribution" histogram and "Cumulative return —
#      uncertainty fan" chart appear.
#   3. On the histogram, locate the three vertical markers (p05, p50,
#      p95) and read off the headline payback year (the dark p50 line).
#      Hover any bar to see "<count> sims" in the bin's year range.
#   4. On the fan chart, follow the dark median line from its deeply
#      negative starting value at year 0 down to its zero-crossing
#      (marked by the green vertical "Median payback ≈ year N" line).
#      Note how the lighter ribbon widens with time — the visual
#      claim of Contribution C.
#   5. Click any "Know more →" — the new monte-carlo and roi-fan
#      modals each show a plain-English description, the formula
#      block, the actual user-facing distributions, and source links.
#   6. Tab through the page with a screen reader — every chart is
#      followed by an sr-only table that names every datum.
```
