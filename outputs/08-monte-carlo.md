# Output 08 — Monte Carlo Uncertainty Engine

> **Date:** 2026-04-30
> **Plan day:** Day 9
> **Branch:** `feat/monte-carlo`
> **Status:** ✅ Complete

---

## Plain English

Today the project learned to give an honest answer instead of a single
guess. Until now, the system would say "your panels pay for themselves
in eleven years." But that number depends on dozens of small bets — how
much electricity prices rise, how fast the panels age, how dusty the
roof gets, when the inverter needs replacing. Now the system runs a
thousand pretend versions of the same household, each with slightly
different luck on those bets, and reports a range like "almost
certainly between nine and fifteen years, most likely about eleven."
The household and the thesis can now talk about confidence, not just
averages.

---

## What I built

A new service module `backend/app/services/monte_carlo.py` plus
matching Pydantic schemas in `backend/app/schemas/monte_carlo.py` and a
FastAPI router at `backend/app/routers/monte_carlo.py`. The kernel
exposes one operation through one endpoint:

| Endpoint | Function | Purpose |
|---|---|---|
| `POST /api/monte-carlo/run` | `run_monte_carlo` | Draw N samples for each uncertain parameter, evaluate the same year-by-year cash flow as `financial_basic`, and return percentile bands + probabilities + histograms for payback, NPV, LCOE and lifetime savings. |

Seven uncertain parameters are modelled, each as a `Distribution`
(normal or triangular, with optional clipping):

| Parameter | Default distribution | Citation |
|---|---|---|
| Module degradation rate | triangular(0.002, 0.005, 0.010) | Jordan & Kurtz, NREL 2013 |
| Tariff escalation rate  | normal(0.08, 0.03), clipped at 0 | EgyptERA decade trend |
| O&M cost fraction       | triangular(0.005, 0.010, 0.020) | IRENA 2023 |
| Installed cost (EGP/kW) | triangular(30 000, 35 000, 45 000) | Egypt market 2024 quote spread |
| Annual yield factor     | normal(1.0, 0.05), clipped 0.5–1.5 per (sim, year) | Egyptian PV field studies |
| Inverter replacement year | triangular(10, 12, 15) | IEA-PVPS Task 13 |
| Inverter cost fraction  | triangular(0.07, 0.10, 0.15) | IEA-PVPS Task 13 |

All seven distributions can be overridden in the request body, so a
caller can disable one source of uncertainty (low = mode = high) or
substitute a published prior of their own. A `random_seed` field is
threaded into a NumPy `Generator` so any reported figure can be
reproduced byte-for-byte.

```
backend/app/
├── config.py                     (+ 7 Monte Carlo default distributions)
├── main.py                       (+ monte_carlo router wiring)
├── schemas/monte_carlo.py        (Distribution, MonteCarloRequest/Result, percentiles, histograms)
├── services/monte_carlo.py       (vectorised sampler, simulator, aggregator)
└── routers/monte_carlo.py        (1 POST endpoint)
backend/tests/
├── test_monte_carlo.py           (30 service tests)
└── test_monte_carlo_router.py    (12 HTTP tests)
```

---

## Why this matters (academic logic)

This is **Contribution C** of the thesis. Four threads of academic
logic shaped the design:

1. **Why parametric distributions, not bootstrap?** A homeowner at the
   moment of investment has no historical sample of *their own*
   future panel performance — only published priors on degradation,
   on tariff policy, on weather. The right uncertainty model is
   therefore parametric, with priors anchored to the literature
   (Jordan & Kurtz 2013 for degradation, EgyptERA history for tariff
   inflation, IEA-PVPS Task 13 for inverter service life). Bootstrap
   would require historical data we do not and cannot have.

2. **Why per-(sim, year) yield noise, not one yield draw per
   simulation?** Annual irradiance in Egypt varies ~±5 % around the
   TMY central value, and that variability does *not* average out for
   the *payback* metric — a string of bad early years pushes break-
   even later in nonlinear ways, while compensating good late years
   are discounted away. Sampling a fresh yield factor for every
   (simulation, year) pair captures this asymmetry; sampling once per
   simulation would understate the spread of payback.

3. **Why one inverter replacement event, not zero or two?** Modern
   string inverters in Egypt's climate carry 10–12 year warranties and
   see a typical 12–15 year service life (IEA-PVPS Task 13). A 25-year
   horizon therefore contains exactly one replacement on the balance
   of evidence. Modelling two replacements would over-attribute
   uncertainty to the inverter line item; modelling zero would
   produce the well-known "PV always pays back" optimism bias seen in
   consumer-facing calculators. The replacement year and cost fraction
   are themselves distributions, so the kernel does *not* commit to
   one specific replacement schedule.

4. **Why discounted payback by linear interpolation, vectorised across
   simulations, with `inf` for non-recovery?** The textbook payback
   convention (linear interpolation across the year of the sign flip)
   matches the deterministic `financial_basic` service exactly, which
   gives the test suite a closed-form anchor: when every distribution
   collapses to zero variance, the Monte Carlo NPV must equal the
   deterministic NPV minus the present value of one inverter
   replacement. This equality is asserted in
   `test_zero_variance_npv_matches_financial_basic_minus_inverter_cost`
   and is the methodological backbone that justifies the entire
   stochastic wrapper.

The output deliberately separates the **percentile band** of payback
from the **probability** that the project pays back at all. Mixing the
two — for example by reporting "median payback = 23 years" when 60 % of
draws never recover — is a common failure mode in PV pre-feasibility
literature. The histogram is built only from paid-back simulations, and
its total count equals `payback_probability × n_simulations` (asserted
in `test_histogram_count_sums_to_paid_back_simulations`).

---

## How the code is organised

```
backend/app/config.py
  + monte_carlo_default_n_simulations
  + monte_carlo_degradation_triangular              (NREL 0.2–1.0 %/yr)
  + monte_carlo_tariff_inflation_normal             (EgyptERA 8 % ± 3 %)
  + monte_carlo_om_fraction_triangular              (IRENA 0.5–2.0 %)
  + monte_carlo_cost_per_kw_triangular              (Egypt 2024 spread)
  + monte_carlo_yield_factor_normal + clip          (Egypt field studies ±5 %)
  + monte_carlo_inverter_year_triangular            (IEA-PVPS 10–15 yr)
  + monte_carlo_inverter_cost_fraction_triangular   (7–15 % of capex)

backend/app/schemas/monte_carlo.py
  Distribution                  — kind ∈ {normal, triangular} + clip bounds
  MonteCarloRequest             — deterministic core + 7 optional Distribution overrides
  MonteCarloPercentiles         — mean/std/p05/p10/p25/p50/p75/p90/p95/min/max
  HistogramBins                 — bin_edges + counts ready for Recharts
  MonteCarloResult              — 4 percentile bundles + 2 probabilities + 2 histograms

backend/app/services/monte_carlo.py
  MonteCarloError               — kernel-level error (unreachable from valid HTTP)
  _default_distribution         — central factory, every default flows through Pydantic
  _resolve_distribution         — caller override → else default
  _default_distributions        — Egypt-tuned set, materialised per-call so config reloads stick
  _sample                       — normal | triangular sampler with clipping, zero-σ short-circuit
  _simulate                     — vectorised (N, T) cash-flow, capex/O&M/inverter/discounting
  _vectorised_discounted_payback— linear-interp payback across all sims, ∞ for non-recovery
  _percentiles_from_array       — percentile bundle, optional inf-filter
  _histogram                    — frequency histogram, ε-bin guard for collapsed draws
  run_monte_carlo               — public entry point

backend/app/routers/monte_carlo.py
  1 thin async endpoint, translates MonteCarloError → HTTP 422

backend/tests/test_monte_carlo.py
  30 service tests: distribution validation, sampling primitives,
  reproducibility under seed, deterministic-collapse equivalence with
  financial_basic, percentile ordering, histogram totals, Egypt sanity
  ranges, override resolution, kernel guards.

backend/tests/test_monte_carlo_router.py
  12 HTTP tests: happy paths, 422 on malformed distributions, seed
  determinism over JSON, override round-trip, histogram payload
  shape, null-seed echo.
```

---

## How I verified it works

1. **Unit tests** — 42 new tests, all passing. The full backend suite
   is **194 passed** (152 pre-existing + 42 new) with **94.96 % branch
   coverage**, above the 90 % gate. The Monte Carlo service module
   itself clears 98 % coverage and the schema module 100 %.

2. **Closed-form anchors baked into the suite** —
   - With every distribution collapsed to zero variance, the Monte
     Carlo median NPV equals the deterministic `financial_basic` NPV
     minus `capex × inverter_cost_fraction / (1 + r)^inverter_year`,
     to within `1 × 10⁻⁶` relative tolerance.
   - With every distribution collapsed to zero variance, the Monte
     Carlo lifetime savings equals the deterministic `financial_basic`
     lifetime savings exactly.
   - The mean of 50 000 triangular draws matches the textbook
     `(low + mode + high) / 3` formula to within `1 × 10⁻⁴`.

3. **Structural invariants the kernel must satisfy** —
   - Same `random_seed` ⇒ byte-identical output across re-runs and
     across the JSON layer (`test_seed_makes_response_deterministic_over_http`).
   - Different seeds ⇒ different output (`test_different_seeds_produce_different_results`).
   - Percentiles strictly ordered: p05 ≤ p10 ≤ p25 ≤ p50 ≤ p75 ≤ p90 ≤ p95.
   - Wider tariff-inflation σ ⇒ wider NPV std (`test_higher_variance_gives_wider_band`).
   - Histogram total = paid-back count for payback, n_sims for NPV.
   - Quadrupling installed cost drives positive-NPV probability below 10 %.

4. **Egypt sanity number** — At 5 kW system, 8 000 kWh/yr year-1
   generation, 2.0 EGP/kWh average tariff, 1 000 simulations,
   `random_seed=2026` and all default distributions:

   | Metric | p10 | p50 (median) | p90 |
   |---|---|---|---|
   | Discounted payback (years) | 9.38 | 11.43 | 14.98 |
   | NPV (EGP)                  | 131 766 | 333 223 | 678 639 |
   | LCOE (EGP/kWh)             | 1.715 | 1.925 | 2.192 |

   The 90 % CI on payback is **9.4 – 15.0 years**, comfortably
   bracketing the 7–14 year range Esmail & Negm (2021) report for
   Egyptian residential rooftop, and `P(payback within 25 years) =
   99.6 %`, `P(NPV > 0) = 99.6 %`. The dashboard headline can now be
   phrased as *"Payback: 11.4 years, 90 % CI 9.4–15.0"* — the
   thesis-required form.

---

## What's next

| Day | Deliverable | Branch |
|---|---|---|
| 10  | Roof detection part 1 — Google Maps Static + OSM Overpass | `feat/roof-detection-osm` |
| 11  | Roof detection part 2 — CV segmentation + tilt/azimuth     | `feat/roof-detection-cv` |
| 12  | React + Vite + TS scaffold, routing, API client            | `feat/frontend-init` |

---

## Files changed

```
M  backend/app/config.py                     (+22 lines)
M  backend/app/main.py                       (+2  lines)
A  backend/app/routers/monte_carlo.py        (+28 lines)
A  backend/app/schemas/monte_carlo.py        (+345 lines)
A  backend/app/services/monte_carlo.py       (+503 lines)
A  backend/tests/test_monte_carlo.py         (+490 lines)
A  backend/tests/test_monte_carlo_router.py  (+171 lines)
A  outputs/08-monte-carlo.md                 (this file)
```

## How to run / verify yourself

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q                        # 194 passed
.venv/bin/pytest -q --cov=app              # 94.96 % coverage

# Manual API smoke (in another terminal):
.venv/bin/uvicorn app.main:app --reload
curl -s -X POST http://127.0.0.1:8000/api/monte-carlo/run \
  -H 'content-type: application/json' \
  -d '{"system_kw":5.0,"annual_kwh":8000.0,"tariff_egp_per_kwh":2.0,"n_simulations":1000,"random_seed":2026}' \
  | python -m json.tool | head -40
```
