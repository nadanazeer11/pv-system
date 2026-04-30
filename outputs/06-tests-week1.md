# Output 06 — Week-1 Test Tightening + v0.1 Backend Core

> **Date:** 2026-04-30
> **Plan day:** Day 7
> **Branch:** `chore/tests-week1`
> **Status:** Complete, 107/107 tests passing (23 new, 84 existing); 94 % line coverage; coverage gate enforced at 90 %.

---

## Plain English

Today we did not add a new feature — we hardened the foundation we have been building all week. Until today, every part of the project (the part that turns a roof into panel count, the two parts that turn weather into electricity, and the part that turns electricity into pounds and a payback year) was tested only on its own, in isolation. Today we added a second layer of tests that pin the contract *between* those parts: the things that must always be true no matter what the inputs are, the things that have to line up when the parts are wired together end to end, and the rules that prevent a future change from quietly breaking one part while another part keeps showing green. We also turned on automatic coverage measurement, so anyone running the suite immediately sees how much of the code is exercised. The whole foundation is now ready to be frozen as the first stable backend release before next week's work on tiered tariffs and uncertainty.

---

## What I built

A new `tests/test_invariants_week1.py` file (23 tests) that pins the cross-service contract of the four week-1 kernels (`pv_sizing`, `energy_pvlib`, `energy_manual`, `financial_basic`), plus a coverage configuration in `pyproject.toml` that fails the suite if total coverage drops below 90 %. The new tests are organised into four bands:

```
tests/test_invariants_week1.py
    pipeline integration       sizing → energy → financial → positive NPV
                               pvlib vs manual ⇒ same payback ordering
    energy structural          Σ monthly == annual (both chains)
                               ac_hourly ≥ 0 (both chains)
                               ac_hourly ≤ inverter nameplate (both chains)
                               determinism: two runs identical (both chains)
                               inverter_efficiency monotone (both chains)
    manual geometry            zenith ∈ [0°, 180°], azimuth ∈ [0°, 360°)
                               cell-temp ≥ air-temp under sunlight
                               naive-datetime fallback parity with tz-aware
    sizing × hardware          panel count monotone in roof area
                               density uses overridden W, not config default
                               pydantic rejects 0 / negative utilization
    financial identities       ROI = 100 × NPV / capex when r=0
                               year-3 savings hand-derivation
                               cumulative cashflow strictly increases
                               LCOE break-even: NPV(τ=LCOE) = 0 at i=0
                               service-layer guard against horizon=0
```

Coverage is now measured automatically on every `pytest` run (94.08 % total, 100 % for sizing / energy_pvlib / energy_manual, 97 % for financial). The threshold is set to 90 % via `tool.coverage.report.fail_under` in `pyproject.toml`.

---

## Why this matters (academic logic)

### Why "tightening" rather than "more tests"?

Day 7 in PLAN.md asks for "Unit tests for energy + sizing + financial". The per-service files (`test_pv_sizing.py`, `test_energy_pvlib.py`, `test_energy_manual.py`, `test_financial_basic.py`) already cover each kernel in isolation with 84 tests. What they cannot cover is the *contract between the kernels* — the properties that depend on more than one service holding together. A schema rename, a unit error, or a sign flip in any single kernel can pass every per-service test and still break the pipeline. The 23 new tests pin those cross-service properties so that **tagging `v0.1-backend-core`** is the moment that contract is frozen for Week-2 work. Without that freeze, every Week-2 commit risks silently breaking a Day-1..6 invariant.

### Why parametrised invariants over both chains?

Six of the new invariants run *parametrised* over `(energy_pvlib, energy_manual)`. The dual-energy backbone is the methodological centrepiece of the thesis — the two chains must remain symmetric in shape, in numerical sanity, and in determinism, even though they disagree on numbers (that disagreement is the cross-validation finding). Asserting structural symmetry separately from numerical symmetry catches the easiest class of regression: one chain quietly drifts in its output convention while the other does not. Day 15's "comparison view" is built on these symmetric outputs.

### Why pin determinism explicitly?

Day 9's Monte Carlo engine will call the energy + financial kernels 1 000 times per request. Its only source of randomness must be the *parameter sampler*; the kernels themselves must be deterministic. A non-deterministic kernel would silently widen the resulting confidence interval — a result that would still look plausible in the final dashboard but would be an artefact of the implementation, not a property of the model. The two `test_simulation_is_deterministic[...]` tests pin that contract before Day 9 starts to depend on it.

### Why a sizing → energy → financial integration test?

Every per-service test consumes a hand-crafted input (a roof area, a TMY, a system size). The integration test consumes only one input — a 100 m² Cairo roof — and chains all three kernels end to end. A schema rename, a unit-of-measure error, or a sign flip in any one of them surfaces here, even if every per-service file still passes. This is the "headline" test of the week: when it fails, the failure is meaningful at the level of the architecture, not at the level of an individual function.

### Why is the LCOE break-even test conditional on `i = 0`?

LCOE is *defined* as the constant tariff at which discounted cost equals discounted revenue. So at `tariff = LCOE` and `tariff_inflation = 0`, `NPV` must be zero — that is the structural identity. With `i > 0`, the tariff escalates over time, and at the (constant) LCOE the future revenue grows faster than the future cost, so NPV becomes positive. That asymmetry is itself a finding worth surfacing in the methodology chapter (Short, Packey & Holt 1995, §3.2): in inflationary regimes, LCOE is a conservative lower bound on the break-even tariff, not the break-even tariff itself. Pinning the constant-tariff identity catches a regression where LCOE and NPV drift onto different cash-flow conventions; the inflationary regime is then validated by behavioural tests already in `test_financial_basic.py`.

### Why a coverage gate at 90 %, not 100 %?

The week-1 services hit 100 % per-service coverage, but the routers have ≈ 86 % because the schema-validated `422 ↔ EnergyModelError` paths are unreachable through normal HTTP traffic (Pydantic catches the same conditions before the service runs). Forcing 100 % would force monkeypatched tests that exercise unreachable code, which is theatre, not safety. Setting the threshold at 90 % leaves a 4-point headroom for Week-2 refactoring without immediately turning red, while still ensuring no whole module slips below the line.

### Why test the cell-temperature ≥ air-temperature invariant?

The NOCT thermal model in `energy_manual` *adds* a non-negative term proportional to plane-of-array irradiance. Negative cell temperatures relative to air would imply the array is actively cooling itself, which is unphysical for a passive radiator. The same monotonicity also matters for the temperature derate in the PVWatts equation: a sign flip in NOCT would *increase* output as the day got hotter, the opposite of every physical c-Si module. Pinning the invariant in three samples (zero, mid, full sun) is a 30-second hand-check a thesis reviewer can redo with a calculator.

### Why test the naive-datetime fallback?

PVGIS TMYs are always tz-aware, so the `index.tz is None` branch in `_solar_position` is dead code in production. But Day 9's Monte Carlo synthesis and Day 11's roof-detection-driven TMY-stub builder may both construct TMY-shaped frames in tests using the obvious `pd.date_range(...)` form — which is naive by default. The defensive fallback exists for that reason; pinning it now means a future contributor cannot delete it without a failing test pointing at the consequence.

---

## How the code is organised

```
backend/
├── pyproject.toml              ← + [tool.coverage.run] & [tool.coverage.report]
├── requirements.txt            ← + pytest-cov==5.0.0
└── tests/
    └── test_invariants_week1.py    ← 23 cross-service invariants
```

The new file deliberately does **not** duplicate per-service tests. It only asserts properties that span at least two services or that pin a structural identity (Σ monthly == annual; ROI = 100·NPV/capex at r=0; LCOE break-even at i=0). Per-service edge cases stay in their per-service files where they are easiest to trace.

---

## How I verified it works

### 1. Test suite

```bash
cd backend
.venv/bin/pytest -q
```

Result: **107 passed** in 2.32 s (23 new, 84 existing). No regressions.

### 2. Coverage

```bash
.venv/bin/pytest --cov=app -q
```

Total line coverage **94.08 %** with the gate at **90 %**. Per-module:

| Module | Cover | Notes |
|---|---|---|
| `services/pv_sizing.py` | 100 % | All branches reachable from the schema. |
| `services/energy_pvlib.py` | 100 % | All chain steps + all error branches. |
| `services/energy_manual.py` | 100 % | Naive-datetime fallback now covered. |
| `services/financial_basic.py` | 97 % | `inf` LCOE / `inf` ROI degenerate paths unreachable: pydantic forbids `annual_kwh = 0` and `system_kw = 0`. |
| `services/pvgis_service.py` | 96 % | Unexpected response-shape guard unreachable through pvlib mocks. |
| `routers/sizing.py` | 100 % | |
| `routers/energy.py` | 86 % | `EnergyModelError → 422` is dead code: pydantic catches the same preconditions earlier. |
| `routers/financial.py` | 82 % | Same: `analysis_period_years >= 1` enforced by the schema, so the service never raises. |
| `schemas/outputs.py` | 0 % | Legacy scaffolding from Day 1, not imported anywhere. Removal is post-Day 7 cleanup. |

### 3. Cross-validation invariants in numbers

For the canonical Cairo clear-sky scenario (5 kW, lat = 30.04°, lon = 31.24°, default tilt/azimuth):

| Invariant | Observed | Expected |
|---|---|---|
| `pvlib.annual_kwh` | ~ 9 100 kWh | within published Cairo specific-yield band |
| `manual.annual_kwh` | ~ 9 050 kWh | within 15 % of pvlib (asserted) |
| `Σ monthly_kwh − annual_kwh` | < 1e-9 | float-precision identity (asserted at 1e-6) |
| `ac_hourly.min()` | 0.0 | non-negativity (asserted) |
| `ac_hourly.max()` | ≤ 5 000 W | inverter nameplate (asserted) |
| `simulation(t1) == simulation(t2)` | True | determinism (asserted bit-identical) |

For the financial kernel at zero friction (r = i = d = OM = 0):

| Identity | Asserted form |
|---|---|
| `roi_percent` = 100 × `npv_egp` / `capex_egp` | direct equality |
| `cumulative_cashflow_series_egp[0]` = `−capex_egp` | direct equality |
| `cumulative_cashflow_series_egp[-1]` = `npv_egp` | direct equality |
| Strictly monotone increasing after year 0 | per-step assertion |

For the constant-tariff LCOE identity (i = 0):

```
NPV(tariff = LCOE) = 0   (asserted within capex × 1e-4)
```

### 4. Manual API call (smoke check)

```bash
.venv/bin/uvicorn app.main:app --reload
curl -X POST http://localhost:8000/api/sizing -H 'Content-Type: application/json' \
     -d '{"roof_area_m2": 100}'
# → 38 panels, 17.1 kW   (unchanged from Day 3)
```

The full suite still finishes in under 3 s on a stock laptop, so the integration tests do not slow CI noticeably.

### 5. v0.1-backend-core tag

The plan calls for tagging `v0.1-backend-core` after this commit. **No tag is created on this branch by the agent** — tagging is reserved for the human reviewer so the tag points at the merge commit on `main`, not at a feature-branch commit that may be rebased away during review. After merging this PR, the human can tag with:

```bash
git checkout main && git pull
git tag -a v0.1-backend-core -m "Week 1 backend core: PVGIS, sizing, dual energy, basic financial"
git push origin v0.1-backend-core
```

That tag freezes the API surface that Week-2 services (`tiered_tariff`, `monte_carlo`) will build on.

---

## What's next

| Day | Branch | Goal |
|---|---|---|
| 8 | `feat/tiered-tariff` | EgyptERA progressive-tier model + system-size optimiser (Contribution B) |
| 9 | `feat/monte-carlo` | Wrap `compute_financials` in a 1 000-sample MC loop (Contribution C) |
| 10 | `feat/roof-detection-osm` | Google Maps Static + OSM Overpass (Contribution A, part 1) |

Day 8 is the first thesis contribution: it replaces the flat tariff in `financial_basic` with a marginal-tier savings calculation against the published EgyptERA tier breakpoints. The Day-7 invariants pinned today guarantee that `compute_financials` keeps the same input shape and the same output series structure as Day 8 builds the tiered version on top of it — which is exactly the kind of contract a `v0.1-backend-core` tag is supposed to protect.

---

## Files changed

```
A  backend/tests/test_invariants_week1.py    (+ ~360 lines, 23 tests)
M  backend/pyproject.toml                    (+22 lines, [tool.coverage] config)
M  backend/requirements.txt                  (+1 line, pytest-cov==5.0.0)
A  outputs/06-tests-week1.md                 (this file)
```

## How to run / verify yourself

```bash
cd ~/pv-system/backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# Full suite
.venv/bin/pytest -q                         # → 107 passed

# With coverage report (gate at 90 %)
.venv/bin/pytest --cov=app -q               # → 94 % total, gate passes

# Just the new invariants
.venv/bin/pytest tests/test_invariants_week1.py -v
```
