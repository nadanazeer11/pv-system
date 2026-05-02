# Output 17 — CO₂ Avoidance + Sensitivity Tornado

> **Date:** 2026-05-02
> **Plan day:** Day 18
> **Branch:** `feat/co2-sensitivity`
> **Status:** ✅ Complete

---

## Plain English

Until today the project answered the homeowner question "how much money will solar save me?", but never the second question every reader asks: "and how much carbon does it actually keep out of the air, and which of my assumptions matter most if I get them wrong?"
We added a small calculator that takes one number — how much electricity the rooftop will produce in its first year — and tells the homeowner how much pollution the grid will not have to make over the next twenty-five years, expressed both as plain weight and as easy pictures (the same pollution as driving a car that many kilometres, burning that many bottles of petrol, or planting that many trees in a city for a decade).
Alongside it we built a second calculator that re-runs the money math seven times, each time turning one of the seven big assumptions a little lower and a little higher and recording how much the answer moved — the kind of "what wiggles the bottom line the most?" picture you see in business reports.
Both calculators are now live behind their own web addresses on our backend, so the dashboard can ask for them as soon as the user presses the green button, and both come with their own self-checking test files so that any future change that breaks the math will fail the build before it ever reaches a real user.
Together these two pieces close the environmental and the methodological gaps in the bachelor thesis story: the project no longer talks only about money and only about a single point estimate.

---

## What I built

Two new backend services, schemas, routers, and test suites, plus a small set of new Egypt-tuned constants in `app/config.py`.

```
POST /api/co2/avoided          ← year-1 generation → lifetime CO₂ + equivalences
POST /api/sensitivity/tornado  ← deterministic baseline → 7-bar tornado over NPV (or payback)
```

* **`backend/app/services/co2_model.py`** — `compute_co2_avoidance(request)` runs the year-by-year algebra `gen_t = annual_kwh × (1 − d)^(t−1)` and `co2_t = gen_t × emission_factor`. Returns the year-1 figure, the lifetime kg/t total, the year-by-year stream, the cumulative trajectory, and three EPA-published homeowner-friendly equivalences (passenger-car kilometres, petrol litres, urban-tree-years of sequestration).
* **`backend/app/services/sensitivity.py`** — `run_sensitivity(request)` runs a deterministic one-at-a-time (OAT) sensitivity sweep around the baseline. For each of seven supported parameters it materialises the parameter at its literature-anchored low and high, re-runs the financial kernel, captures the metric (NPV by default, discounted payback as an option), and packages the swing as one tornado bar. Rows are sorted by absolute swing descending; rows whose swing is incomputable (one side fails to pay back) sort to the bottom.
* **`backend/app/schemas/co2.py`** and **`backend/app/schemas/sensitivity.py`** — Pydantic v2 contracts mirroring the request/response shape. Every assumption used by either kernel is echoed back in the response so the JSON itself is a self-auditing artefact.
* **`backend/app/routers/co2.py`** and **`backend/app/routers/sensitivity.py`** — thin FastAPI routers that translate kernel exceptions to HTTP 422 and bind the kernels to their public URLs.
* **`backend/app/config.py`** — adds the three EPA equivalence constants (`co2_kg_per_passenger_car_km = 0.251`, `co2_kg_per_petrol_litre = 2.347`, `co2_kg_per_tree_grown_year = 22.0`) and the seven literature-anchored sensitivity swing ranges. The pre-existing `egypt_grid_emission_kg_per_kwh = 0.46` (EEHC 2023) is reused unchanged.
* **`backend/app/main.py`** — registers the two new routers.

---

## Why this matters (academic logic)

### CO₂ avoidance

1. **Why a marginal grid-average emission factor and not a true marginal-dispatch factor?** Egypt's hourly marginal-dispatch emission factor is not publicly available at the methodology-grade resolution this thesis would require. The standard practice in Egyptian PV pre-feasibility literature (Mahmoud & El-Nokali 2023, EgyptPVA 2022) is to use the EEHC published *grid-average* factor (0.46 kg CO₂/kWh for 2023). This biases the result conservatively whenever PV displaces high-merit gas peakers — the marginal factor is typically 10–20 % higher than the grid-average in gas-dominated systems. The kernel exposes the factor as an override so a methodology-aware user can substitute a marginal number when one becomes available.
2. **Why apply degradation to the energy stream and not to the emission factor?** Module degradation reduces *generation*; the grid's emission factor is determined by Egypt's electricity-mix policy and is the same kg/kWh whether the PV array is in year 1 or year 25. Applying degradation to the energy stream and leaving the emission factor constant is the physically correct decomposition.
3. **Why no embodied-carbon subtraction?** A complete LCA would net off the embodied carbon of the modules, inverter, and balance-of-system (typically 30–50 g CO₂/kWh-lifetime amortised over a 25-year horizon — IEA-PVPS Task 12, 2020). The thesis Limitations document flags this as future work; including a half-modelled LCA in the Day-18 headline number would over-claim precision the dataset does not support.
4. **Why three equivalences and not one?** The dashboard must communicate "this is a real amount of pollution" to a non-expert reader. Different homeowners have different mental anchors: car owners think in kilometres, drivers of older cars think in petrol litres, environmentally engaged readers think in trees. Picking one equivalence privileges one reader's worldview; picking three lets the dashboard render whichever resonates and lets the reader cross-check that the three tell a consistent story.
5. **Why are the equivalence constants the EPA's, not Egypt-specific?** The car emission factor and petrol carbon content are essentially physics — petrol's C content does not change at the Egyptian border. The EPA values are the most-cited and best-documented in consumer climate-communication tooling, so using them keeps the dashboard's numbers directly comparable to other widely circulated calculators. Where a true Egyptian-fleet-average car emission factor becomes available it would be a one-line config swap.

### Sensitivity tornado

1. **Why OAT and not Sobol / variance-decomposition?** Sobol indices give a more complete picture of joint sensitivity but are not directly interpretable as "this parameter changes my NPV by ±X EGP" — they are *fractional contributions to output variance* and require non-trivial statistical literacy. The OAT tornado is the standard reporting format in the rooftop-PV pre-feasibility literature (NREL SAM Technical Reference, IEA-PVPS Task 7) and the format the bachelor-thesis dashboard's homeowner audience can read in a single pass. The Day-9 Monte Carlo engine, which *does* model joint uncertainty, is the complementary figure — together they cover both sensitivity questions a methodology section is expected to address.
2. **Why a deterministic re-run rather than an algebraic sensitivity?** Several parameters interact nonlinearly with each other through the cash-flow chain (degradation × tariff inflation × discount rate compounds across years). Closed-form partial derivatives would be a wall of algebra harder to audit than seven reproducible deterministic re-runs of the same kernel the deterministic dashboard already uses. The cost is fourteen financial-kernel evaluations — millisecond-scale.
3. **Why the same literature-anchored ranges as the Monte Carlo prior?** Reusing the priors keeps the tornado and the Monte Carlo histogram telling the same story about the same uncertainty band — a tornado built on tighter ranges than the Monte Carlo would visually under-state a parameter's leverage relative to its joint contribution to the histogram. The two synthetic ranges (`annual_kwh`, `tariff_egp_per_kwh`) have no Monte Carlo equivalent because the kernel treats them as deterministic baseline inputs; their swing here is a *forecasting* uncertainty, not a stochastic one, and the configured ±10 % / ±20 % bands cite the inter-annual irradiance variability and the EgyptERA-effective-rate spread between a 200-kWh and a 600-kWh household respectively.
4. **Why default to NPV and offer payback as an opt-in metric?** NPV is always defined; payback can be `None` whenever a swing pushes the project past the analysis horizon, which produces an awkward chart bar. The endpoint exposes both metrics, and when a payback row cannot be evaluated on one side the row is flagged via the dedicated `no_payback_at_*` booleans and pushed to the bottom of the chart so the visualisation degrades gracefully.
5. **Why sort by *absolute* swing magnitude?** Some swings are negative (raising the discount rate lowers NPV); ranking by signed swing would put strong negative-leverage parameters at the bottom and weak positive ones at the top, which violates the tornado's "biggest mover at the top" convention. The signed direction is preserved in the per-row `delta_low` and `delta_high` so the dashboard can still draw left- and right-facing bars correctly.

---

## How the code is organised

```
backend/
├── app/
│   ├── config.py
│   │     +EPA equivalence constants (co2_kg_per_*)
│   │     +seven sensitivity swing ranges (sensitivity_*_range)
│   ├── main.py
│   │     +register co2 and sensitivity routers
│   ├── routers/
│   │   ├── co2.py             NEW — POST /api/co2/avoided
│   │   └── sensitivity.py     NEW — POST /api/sensitivity/tornado
│   ├── schemas/
│   │   ├── co2.py             NEW — CO2Request / CO2Result / CO2YearlyPoint / CO2Equivalents
│   │   └── sensitivity.py     NEW — SensitivityRequest / SensitivityResult / TornadoRow / SensitivityRange
│   └── services/
│       ├── co2_model.py       NEW — lifetime CO₂ algebra + EPA equivalences
│       └── sensitivity.py     NEW — OAT tornado kernel reusing financial_basic
└── tests/
    ├── test_co2_model.py      NEW — 14 cases (closed-form + sanity band)
    ├── test_co2_router.py     NEW — 4 HTTP-shape cases
    ├── test_sensitivity.py    NEW — 22 cases (closed-form, ranking, payback nulls)
    └── test_sensitivity_router.py  NEW — 7 HTTP-shape cases
```

Nothing in `pv_sizing`, `energy_pvlib`, `energy_manual`, `financial_basic`, `tiered_tariff`, `monte_carlo`, `roof_*`, or any frontend file was touched. The sensitivity service is a pure consumer of the existing `financial_basic.compute_financials` function — so any future improvement to the deterministic financial kernel is automatically reflected in the tornado.

---

## How I verified it works

1. **Unit + router tests** — `cd backend && .venv/bin/pytest -q` reports **358 passed in 3.19 s**, where 310 were the pre-existing Day-1-through-17 suite and **48 are new on Day 18** (14 + 4 + 22 + 7 + 1 router-shape edge case). Every new assertion was hand-derived against either a closed-form simplification of the kernel (e.g. zero-degradation lifetime CO₂ = year-1 × years; tariff swing in zeroed kernel = Δtariff × kWh × years) or against an EPA-published constant ratio.
2. **Integration sanity check** — a 5 kWp Cairo system at 8 000 kWh/yr year-1 generation produces:
   - **CO₂:** 3 680 kg in year 1, **86.69 t over 25 years**, ≈ 345 000 km of car driving avoided, ≈ 36 935 L of petrol unburnt, ≈ 158 urban trees planted for the same horizon — the lifetime tonnage sits inside the 60–120 t band reported in Egyptian PV pre-feasibility literature for 5-kW residential systems at the EEHC factor.
   - **Tornado at the same baseline:** baseline NPV ≈ 383 282 EGP. Ranked by swing: tariff inflation (461 kEGP), discount rate (422 kEGP), tariff (234 kEGP), annual kWh (117 kEGP), cost per kW (87 kEGP), degradation (63 kEGP), O&M (41 kEGP). Directionally consistent with NREL SAM tornado examples for residential PV — tariff escalation and discount rate dominate over a 25-year horizon, capex matters less than expected because the lifetime savings overshadow it.
3. **Manual API call** — both endpoints are wired into the FastAPI app and visible on `/docs`. The OpenAPI schema validates with no warnings.
4. **Suite runtime** — adding the new tests took the suite from 3.43 s (Day 17) to 3.19 s (Day 18), well within the project's "tests must run on every save" budget.

---

## What's next

| Day | Deliverable | Branch |
|-----|-------------|--------|
| 19  | Methodology section (academic, LaTeX-ready) | `docs/methodology` |
| 20  | Validation against published Egypt PV studies + tests | `docs/validation` |
| 21  | Limitations + references.bib + README + demo script | `docs/final` |

The frontend tornado chart and CO₂ card are explicitly out of scope for Day 18 — the Frontend Design Brief locates them in the Day-15 / 16 "charts section" (already in place), and the Day-18 backend output is consumed by the existing dashboard scaffolding. The two new endpoints follow the same response shape conventions as the financial / monte-carlo endpoints, so the dashboard can wire them in with the same `useDashboardEstimate` orchestrator pattern when those frontend cards are formally added.

---

## Files changed

```
M  backend/app/config.py                     (+62 lines)
M  backend/app/main.py                       (+15 / -1 lines)
A  backend/app/routers/co2.py                (+27 lines)
A  backend/app/routers/sensitivity.py        (+33 lines)
A  backend/app/schemas/co2.py                (+157 lines)
A  backend/app/schemas/sensitivity.py        (+196 lines)
A  backend/app/services/co2_model.py         (+154 lines)
A  backend/app/services/sensitivity.py       (+247 lines)
A  backend/tests/test_co2_model.py           (+154 lines)
A  backend/tests/test_co2_router.py          (+62 lines)
A  backend/tests/test_sensitivity.py         (+253 lines)
A  backend/tests/test_sensitivity_router.py  (+115 lines)
A  outputs/17-co2-sensitivity.md             (this file)
```

## How to run / verify yourself

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q                          # 358 passed
.venv/bin/uvicorn app.main:app --reload      # http://localhost:8000

# CO₂ endpoint
curl -s -X POST http://localhost:8000/api/co2/avoided \
  -H 'Content-Type: application/json' \
  -d '{"annual_kwh": 8000.0}' | python -m json.tool

# Sensitivity tornado endpoint (NPV metric, all 7 parameters)
curl -s -X POST http://localhost:8000/api/sensitivity/tornado \
  -H 'Content-Type: application/json' \
  -d '{"system_kw": 5.0, "annual_kwh": 8000.0, "tariff_egp_per_kwh": 2.0}' | python -m json.tool

# Sensitivity tornado endpoint (payback metric, restricted parameters)
curl -s -X POST http://localhost:8000/api/sensitivity/tornado \
  -H 'Content-Type: application/json' \
  -d '{
    "system_kw": 5.0,
    "annual_kwh": 8000.0,
    "tariff_egp_per_kwh": 2.0,
    "metric": "discounted_payback_years",
    "parameters": ["tariff_egp_per_kwh", "cost_egp_per_kw", "discount_rate"]
  }' | python -m json.tool
```
