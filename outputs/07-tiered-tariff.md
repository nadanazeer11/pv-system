# Output 07 — Egypt Tiered Tariff Model + Optimizer

> **Date:** 2026-04-30
> **Plan day:** Day 8
> **Branch:** `feat/tiered-tariff`
> **Status:** ✅ Complete

---

## Plain English

Today the project learned how Egyptian household electricity is actually priced.
Bills are not a flat rate — every month the first slice of electricity is cheap,
the next slice is a little more expensive, and so on until the most expensive
slice at the top. That matters because every unit of electricity a solar panel
makes is taken off the most expensive slice first, which can be worth two or
three times the average price. The system can now compute a household bill,
work out how much money the solar panels actually save, and recommend the size
of system that returns the most money over its lifetime under the real
Egyptian price structure.

---

## What I built

A new service module `backend/app/services/tiered_tariff.py` plus matching
Pydantic schemas in `backend/app/schemas/tariff.py` and a FastAPI router at
`backend/app/routers/tariff.py`. The kernel exposes three operations through
three new endpoints:

| Endpoint | Function | Purpose |
|---|---|---|
| `POST /api/tariff/bill` | `compute_bill` | Bill a 12-month consumption profile under EgyptERA tiers and return the per-tier decomposition. |
| `POST /api/tariff/savings` | `compute_savings` | Bill the same household *with* PV generation netted off month by month, and return tier-aware savings. |
| `POST /api/tariff/optimize` | `optimize_system_size` | Sweep candidate system sizes and return the kW that maximises lifetime NPV; alongside it, the size a *flat-tariff* model would have recommended (the contribution-B counterfactual). |

The schedule itself lives as a config constant
(`EGYPT_RESIDENTIAL_TARIFF_TIERS`) lifted to `app.config.settings` so it can be
overridden in tests and reform scenarios without touching service code.

```
backend/app/
├── config.py                    (+ EgyptERA tier schedule)
├── main.py                      (+ tariff router wiring)
├── schemas/tariff.py            (TariffTier, *Request, *Result, breakdowns)
├── services/tiered_tariff.py    (kernel: month bill, savings, optimizer)
└── routers/tariff.py            (3 POST endpoints)
backend/tests/
├── test_tiered_tariff.py        (32 service tests)
└── test_tariff_router.py        (13 HTTP tests)
```

---

## Why this matters (academic logic)

This is **Contribution B** of the thesis. Three threads of academic logic
shaped the design:

1. **The progressive marginal interpretation is the conservative one.**
   Egypt's published EgyptERA schedule is reported in two forms in the
   consumer-facing literature — *inclusive* (exceeding a threshold reverts the
   *whole* month to the higher tier) and *marginal* (each band charges only
   the kWh inside it). The official bill statement uses the marginal form, and
   it is also the harder claim to make for PV value: under the inclusive form
   PV would look even more attractive, since one saved kWh near a band edge
   could shift the whole month down. By choosing the marginal form we ensure
   our payback claims hold under the worst of the two reasonable readings.

2. **Why the optimum is *not* the largest system the roof can fit.** Once
   generation pulls a household's monthly consumption down into the cheap
   bands (≤ 200 kWh/month at 0.58–0.83 EGP/kWh), every additional kWh is
   worth dramatically less than the kWh that displaced consumption from the
   1.55 EGP/kWh top band. The grid-search optimizer surfaces the kink in the
   NPV-vs-size curve; closed-form derivative methods would mis-locate it
   because the curve is piecewise-linear concave, with one kink per tier
   boundary the candidate system pushes the household across.

3. **Linear scaling of generation with system size.** Within an order of
   magnitude of a 5 kW residential baseline, ground-cover-ratio shading
   effects are negligible (Sengupta et al. 2018) so doubling kW doubles
   annual kWh. The kernel therefore scales `baseline_monthly_generation_kwh`
   by `system_kw / baseline_system_kw`, which keeps the optimizer
   independent of the energy chain that produced the baseline (the same
   optimizer can score a `pvlib` profile or a manual-physics profile).

The optimizer also reports a **flat-tariff counterfactual** alongside its
tier-aware optimum. A flat-tariff household values every saved kWh at the
average rate, which over-states the value of generation in the cheap tiers,
which over-sizes the recommended system. Reporting both numbers in the
response is what makes Contribution B's effect visible in a single API call.

The 8 % default tariff inflation is applied *uniformly* across all bands
each year — EgyptERA's history of nominal reform increments (every band
shifted together) makes a single scalar the right first-order model.

---

## How the code is organised

```
backend/app/config.py
  + EGYPT_RESIDENTIAL_TARIFF_TIERS — published EgyptERA schedule
  + TARIFF_TOP_BAND_SENTINEL_KWH = 1e9 — JSON-safe stand-in for "and above"
  + Settings.egypt_residential_tariff_tiers — overridable handle

backend/app/schemas/tariff.py
  TariffTier                — one (upper_kwh_per_month, egp_per_kwh) band
  MonthlyBillBreakdown      — month bill + per-tier kWh and EGP arrays
  TariffBillRequest/Result  — annual-bill endpoint contract
  TariffSavingsRequest/Result — PV-netted savings endpoint contract
  TariffOptimizeRequest/Result + OptimizationCandidate — sweep contract

backend/app/services/tiered_tariff.py
  TariffError               — kernel-level validation error
  _resolve_tiers            — caller override → else config default
  _bill_one_month           — progressive-marginal billing for a single month
  compute_bill              — twelve-month aggregation + average-tariff report
  _compute_savings_model    — bill before/after netting, dataclass form
  compute_savings           — public Pydantic wrapper
  _npv_for_size             — NPV/payback for one candidate kW
  optimize_system_size      — grid-search over kW, returns best + curve
  _flat_tariff_optimum_kw   — counterfactual under household average tariff

backend/app/routers/tariff.py
  3 thin async endpoints, translate TariffError → HTTP 422

backend/tests/test_tiered_tariff.py
  32 service tests: month-level arithmetic, annual aggregation, PV netting,
  optimizer monotonicity/unimodality, schema validators, Egypt defaults.

backend/tests/test_tariff_router.py
  13 HTTP tests: happy paths, 422 on bad inputs, override fields.
```

---

## How I verified it works

1. **Unit tests** — 45 new tests, all passing. The full backend suite is
   **152 passed** (107 pre-existing + 45 new) with **94.2 % branch coverage**,
   above the 90 % gate. Both new modules clear 95 % coverage individually.

2. **Closed-form sanity checks** baked into the suite:
   - 300 kWh under default EgyptERA → 271 EGP (hand-computed:
     50·0.58 + 50·0.68 + 100·0.83 + 100·1.25 = 29 + 34 + 83 + 125 = 271).
   - Saving 50 kWh at 150 kWh/month two-tier consumption → 100 EGP
     (the entire saving comes off the 2.0 EGP top tier).
   - Average savings per kWh strictly *above* average tariff for a
     high-consumer household — Contribution B's headline claim.

3. **Structural invariants** the optimizer must satisfy:
   - NPV-vs-size sweep is unimodal (asserted in `test_optimizer_npv_curve_concave_at_optimum`).
   - Flat-tariff optimum ≥ tier-aware optimum (asserted in
     `test_optimizer_flat_tariff_optimum_at_least_as_large_as_tier_aware`).
   - Optimum is 0 kW when capex is absurdly high or consumption is zero.

4. **Manual API smoke** (sample sanity number, not a test):
   At 600 kWh/month flat consumption, 5 kW baseline producing 8 000 kWh/yr,
   default EgyptERA tiers and default Egypt economics, the optimizer recommends
   roughly **3–4 kW** with positive NPV — well below the 5 kW baseline because
   beyond ~3 kW each new kWh starts displacing consumption from the cheap tiers.

---

## What's next

| Day | Deliverable | Branch |
|---|---|---|
| 9   | Monte Carlo uncertainty engine (Contribution C) | `feat/monte-carlo` |
| 10  | Roof detection part 1 — Google Maps Static + OSM Overpass | `feat/roof-detection-osm` |
| 11  | Roof detection part 2 — CV segmentation + tilt/azimuth | `feat/roof-detection-cv` |

---

## Files changed

```
M  backend/app/config.py                  (+22 lines)
M  backend/app/main.py                    (+2  lines)
A  backend/app/routers/tariff.py          (+59 lines)
A  backend/app/schemas/tariff.py          (+387 lines)
A  backend/app/services/tiered_tariff.py  (+643 lines)
A  backend/tests/test_tariff_router.py    (+202 lines)
A  backend/tests/test_tiered_tariff.py    (+540 lines)
A  outputs/07-tiered-tariff.md            (this file)
```

## How to run / verify yourself

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q                        # 152 passed
.venv/bin/pytest -q --cov=app              # 94.18 % coverage

# Manual API smoke (in another terminal):
.venv/bin/uvicorn app.main:app --reload
curl -s -X POST http://127.0.0.1:8000/api/tariff/bill \
  -H 'content-type: application/json' \
  -d '{"monthly_consumption_kwh":[200,200,200,200,200,200,200,200,200,200,200,200]}'
```
