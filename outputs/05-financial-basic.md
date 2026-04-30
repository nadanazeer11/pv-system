# Output 05 — Basic Financial Feasibility Model

> **Date:** 2026-04-30
> **Plan day:** Day 6
> **Branch:** `feat/financial-basic`
> **Status:** Complete, 84/84 tests passing (32 new, 52 existing)

---

## Plain English

Today we taught the project to answer the question every homeowner actually cares about: "If I install solar panels, how much does it cost, how much do I save each year, and how long until the savings have paid for the panels?". Yesterday's work could already estimate how much electricity a rooftop would produce; now we turn that electricity into Egyptian pounds and compare it against the up-front purchase price. The new piece also looks ahead twenty-five years and accounts for the fact that panels age slightly each year, electricity prices in Egypt keep rising, and money in your pocket today is worth a little more than money in your pocket a decade from now. Two break-even numbers are reported side by side: the simple one quoted in brochures, and a more honest one that respects the time value of money. With this in place the project can finally produce the headline payback figure that the dashboard and the thesis abstract will both lead with.

---

## What I built

A backend service and HTTP endpoint that take a system size, a year-1 generation figure (from either the pvlib or manual energy chain), and a flat residential tariff, and return a complete financial picture: capex, year-1 savings, simple and discounted payback, net present value, levelised cost of electricity, lifetime ROI, and the full year-by-year cash-flow series for charting. Five economic parameters (installed cost, analysis horizon, discount rate, tariff inflation, module degradation, O&M fraction) are optional inputs with Egypt-tuned defaults from `app.config.settings`, so the minimal call is just three fields and the full call lets the future Monte Carlo engine perturb every knob.

```
backend/
├── app/
│   ├── services/
│   │   └── financial_basic.py        ← compute_financials() + dataclass + payback interp
│   ├── routers/
│   │   └── financial.py              ← POST /api/financial/basic
│   ├── schemas/
│   │   └── financial.py              ← FinancialBasicRequest / FinancialBasicResult
│   ├── config.py                     ← + 5 financial defaults (horizon/rates/degradation/O&M)
│   └── main.py                       ← register financial router
└── tests/
    ├── test_financial_basic.py       ← 27 service tests (closed-form, behaviour, edges)
    └── test_financial_router.py      ← 5 endpoint tests (200, 422, null serialisation)
```

---

## Why this matters (academic logic)

### Why a *flat* tariff in the basic model?
Egypt's residential bills are billed on a progressive **tier** structure (EgyptERA): the unit price jumps as monthly consumption crosses 50, 100, 200, 350, 650, and 1 000 kWh. A flat-tariff model is therefore deliberately a **first-order approximation** — every published Egyptian PV pre-feasibility study available to me (Mahmoud & El-Nokali 2023; Khalil & Asheibi 2021) uses a single weighted-average tariff. Reproducing that baseline first lets the thesis quantify exactly what Day 8's tiered model adds, which is the second academic contribution. Without a flat baseline to compare against, the tier-aware result has no reference point.

### Why both simple *and* discounted payback?
Simple payback (capex divided by year-1 savings) is criticised throughout the energy-finance literature (Short, Packey & Holt 1995; IRENA 2024) for ignoring the time value of money, tariff escalation, and post-payback cash flow. Yet it remains the single number every PV brochure quotes, and Egyptian consumer-facing solar calculators report nothing else. A defensible thesis must report it (so results are comparable to industry tools) **and** report a discounted payback alongside (so the reader can see the gap the naïve metric hides). The basic model returns both:

* `simple_payback_years` — capex / year-1 net savings (savings − O&M). No inflation, no degradation, no discounting.
* `discounted_payback_years` — first year at which the **discounted** cumulative cash-flow series turns non-negative, with linear interpolation. Honours degradation, tariff inflation, O&M, and the discount rate.

In the default Egypt scenario these two diverge in an unexpected direction (discounted < simple) — see the validation table below — because Egypt's 8 % real tariff escalation is high enough that the inflation gain on future cash flows outweighs the 4 % real discount rate. That structural asymmetry is itself a finding worth reporting in the methodology chapter.

### Why NPV and LCOE if "basic" only required payback?
NPV is the single metric the international project-finance literature treats as canonical — payback is a screening tool, NPV is the decision rule. LCOE (levelised cost of electricity) is the figure published by IRENA and the IEA for cross-country PV comparisons; it has the desirable property of being directly comparable against a tariff. Reporting both lets the dashboard show the same project from three vantage points (when do I break even? what is the project worth today? what does each kWh cost me to produce?) without re-running the kernel, and lets the validation chapter cross-reference Egyptian results against international benchmarks.

### Why a 25-year analysis period?
Matches the standard module performance warranty (the manufacturer guarantees ≥ 80 % of nameplate at 25 years). Going longer requires assumptions about inverter replacement cost (typically year 12) and end-of-life decommissioning that the basic model intentionally does not yet make — they enter at Day 9 in the Monte Carlo as separate stochastic inputs.

### Why are degradation, inflation, discount rate, and O&M optional request-level fields?
Because Day 9's Monte Carlo engine will perturb each one as a probability distribution. Treating them as request parameters (with config defaults) means the deterministic kernel and the probabilistic engine share **one** code path — the Monte Carlo wrapper just calls `compute_financials` 1 000 times with sampled inputs. No duplicated math, no risk of the two chains drifting. This is the same structural decision that made the dual energy model maintainable: design the kernel so all uncertain inputs are first-class parameters.

### Why does year-0 cash flow equal `−capex` and not `−capex − year-0 OM`?
The convention here is that capex is paid at the moment of installation (year 0) and the system *immediately starts* producing for year 1. O&M is incurred *during* operation, so year-1 O&M lands with year-1 savings. This is the convention used in IEA-PVPS Task 12 and in pvlib's own `analysis.lcoe` example notebook. Mixing the conventions (e.g. crediting year-1 generation but debiting year-0 O&M) introduces a half-year offset that biases payback by ~6 months — small but pointless when the convention is free.

### Why linear interpolation for the payback year?
The cumulative cash-flow array is sampled at integer years, but a homeowner reading "8.4 years" expects months, not days. Linear interpolation between the last negative and first non-negative cumulative point gives a fractional year of the form `(t-1) + |C_{t-1}| / (C_t - C_{t-1})`. Higher-order interpolation (cubic, splines) would imply intra-year cash-flow shape that the model does not actually have.

### Why does payback return `None` when the system never recovers?
A well-formed answer to "how many years until I break even?" must distinguish "not within the horizon" from "very long". Returning `None` (which serialises as JSON `null`) lets the frontend render "does not pay back within 25 years" instead of a misleading "25.0 years" or, worse, a NaN that crashes the chart. Tested explicitly by `test_financial_basic_endpoint_payback_can_be_null_in_json`.

---

## How the code is organised

```
backend/app/services/financial_basic.py
    compute_financials(request) → FinancialBasic
        capex = system_kw × cost_egp_per_kw
        for t in 1..N:
            gen(t)     = annual_kwh × (1−d)^(t−1)
            tariff(t)  = tariff × (1+i)^(t−1)
            savings(t) = gen(t) × tariff(t)
            net(t)     = savings(t) − capex × om_fraction
        npv  = −capex + Σ net(t) / (1+r)^t
        lcoe = (capex + Σ om(t) / (1+r)^t) / Σ gen(t) / (1+r)^t
        simple_payback     = capex / net(1)               # textbook
        discounted_payback = interp_zero( cumulative discounted cash flow )

backend/app/routers/financial.py
    POST /api/financial/basic → FinancialBasicResult
    422 ↔ FinancialError
```

Egypt-specific constants (`installed_cost_egp_per_kw`, `analysis_period_years`, `discount_rate`, `tariff_inflation_rate`, `annual_degradation_rate`, `om_cost_fraction`) live in `app.config.settings` per project conventions. The dataclass `FinancialBasic` mirrors `FinancialBasicResult` so the service can be unit-tested without going through Pydantic validation.

---

## How I verified it works

### 1. Unit + router tests

```bash
cd backend
.venv/bin/pytest -q
```

Result: **84 passed** in 2.71 s (32 new, 52 existing). PVGIS, sizing, pvlib, and manual chains all still green — no regressions.

### 2. Closed-form sanity (zero-friction baseline)

Most service tests run with discount rate, inflation, degradation and O&M all zeroed, so every metric reduces to a textbook closed form a reader can verify with a calculator:

| Identity | Formula | Test |
|---|---|---|
| capex | `system_kw × cost_per_kw` | `test_capex_is_system_kw_times_cost_per_kw` |
| year-1 savings | `annual_kwh × tariff` | `test_year1_savings_is_generation_times_tariff` |
| simple payback | `capex / year1_savings` | `test_simple_payback_zero_friction_is_capex_over_savings` |
| simple == discounted (zero-friction) | invariant | `test_discounted_payback_equals_simple_when_friction_zero` |
| NPV | `savings × N − capex` | `test_npv_zero_friction_closed_form` |
| LCOE | `capex / (annual_kwh × N)` | `test_lcoe_zero_friction_closed_form` |
| cumulative[0] | `−capex` | `test_cumulative_cashflow_starts_at_minus_capex` |
| cumulative[N] | `npv` (zero discount) | `test_cumulative_cashflow_ends_at_npv_when_zero_discount` |

### 3. Behavioural / monotonicity invariants

| Behaviour | Direction | Test |
|---|---|---|
| Higher discount rate | NPV ↓ | `test_npv_drops_when_discount_rate_increases` |
| Discounting (zero inflation) | discounted payback ≥ simple | `test_discounted_payback_longer_than_simple_with_positive_discount` |
| Tariff inflation | lifetime savings ↑ | `test_tariff_inflation_increases_lifetime_savings` |
| Module degradation | lifetime kWh ↓ | `test_degradation_reduces_lifetime_generation` |
| O&M | NPV ↓ | `test_om_cost_lowers_npv` |
| Year-2 savings | `year1 × (1−d)(1+i)` | `test_annual_savings_series_grows_with_inflation_and_decays_with_degradation` |
| LCOE > tariff ⇔ NPV < 0 | structural | `test_npv_positive_when_lcoe_below_tariff` |

### 4. Edge cases

* Tariff so low payback never lands (year-1 savings = 80 EGP) → both paybacks are `None`.
* O&M exceeds year-1 savings (10 % O&M, capex 175 000) → simple payback is `None`.
* Analysis period of 1 year → series of length 1 + capex row of length 2; service does not crash.
* Pydantic rejects `system_kw ≤ 0`, `tariff ≤ 0`, `discount_rate ≥ 1` at the schema layer.

### 5. Sanity check against published Egyptian PV literature

For the canonical reference project (5 kW, 8 000 kWh/yr year-1 generation, 2 EGP/kWh flat tariff, all five economic parameters at config defaults):

| Metric | Computed | Reference / Verdict |
|---|---|---|
| Capex | 175 000 EGP | 5 × 35 000 = 175 000 — by definition |
| Year-1 savings | 16 000 EGP | 8 000 × 2 — by definition |
| Simple payback | 12.28 yrs | High because year-1 ignores 8 %/yr tariff escalation |
| Discounted payback | 10.50 yrs | Inside Egyptian residential PV literature window (5–13 yrs at current tariffs) — the 8 % tariff inflation outweighs the 4 % discount rate, so the "honest" payback is *shorter* than the textbook one |
| NPV | 383 282 EGP | Strongly positive — investment is worthwhile |
| LCOE | 1.70 EGP/kWh | Below the 2.00 EGP/kWh tariff, consistent with NPV > 0 |
| ROI (lifetime) | 493 % | Cumulative un-discounted return, large because tariff escalation compounds over 25 yrs |
| Lifetime kWh | 188 448 | 8 000 × Σ (1−0.005)^(t−1), t=1..25 ≈ 8 000 × 23.56 ✓ |

The structural invariant `LCOE < tariff ⇒ NPV > 0` holds, confirming the discounted-cost / discounted-revenue accounting is internally consistent.

### 6. Manual API call (after `uvicorn`)

```bash
curl -X POST http://localhost:8000/api/financial/basic \
  -H "Content-Type: application/json" \
  -d '{"system_kw":5.0,"annual_kwh":8000.0,"tariff_egp_per_kwh":2.0}'
# {
#   "capex_egp": 175000.0,
#   "annual_savings_year1_egp": 16000.0,
#   "simple_payback_years": 12.28,
#   "discounted_payback_years": 10.50,
#   "npv_egp": 383282.0,
#   "lcoe_egp_per_kwh": 1.70,
#   "roi_percent": 492.9,
#   "annual_savings_series_egp": [...25 entries...],
#   "cumulative_cashflow_series_egp": [...26 entries starting at -175000...],
#   ...
# }
```

---

## What's next

| Day | Branch | Goal |
|---|---|---|
| 7 | `chore/tests-week1` | Tighten unit tests across week 1 + tag `v0.1-backend-core` |
| 8 | `feat/tiered-tariff` | EgyptERA tiered tariff + system-size optimiser (Contribution B) |
| 9 | `feat/monte-carlo` | Wrap `compute_financials` in a 1 000-sample MC loop (Contribution C) |

Day 8 will replace the flat `tariff_egp_per_kwh` with a marginal-tier savings calculation: each kWh of self-consumption displaces the household's *highest-tier* unit price first, dramatically improving payback for high-consumption households crossing into the punitive upper brackets. Day 9 will sample tariff inflation, degradation, discount rate, capex, and weather variability from documented distributions and run `compute_financials` 1 000 times to produce a 90 % confidence interval around payback — turning the deterministic point estimate above into "10.5 ± 1.5 years (90 % CI)".

---

## Files changed

```
A  backend/app/services/financial_basic.py        (+255 lines)
A  backend/app/schemas/financial.py               (+150 lines)
A  backend/app/routers/financial.py               (+30 lines)
A  backend/tests/test_financial_basic.py          (+260 lines)
A  backend/tests/test_financial_router.py         (+95 lines)
M  backend/app/main.py                            (+2 / -1 lines)
M  backend/app/config.py                          (+24 lines)
A  outputs/05-financial-basic.md                  (this file)
```

## How to run / verify yourself

```bash
cd ~/pv-system/backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q                              # 84 tests, all pass
.venv/bin/uvicorn app.main:app --reload
# Open http://localhost:8000/docs and try POST /api/financial/basic.
# Pipe the annual_kwh out of /api/energy/pvlib or /api/energy/manual
# into this endpoint to get a complete energy-to-EGP picture.
```
