# PV Rooftop Solar Estimator

**AI-Assisted Rooftop Solar Potential Estimation and Financial Analysis System for Egypt**

A bachelor-thesis web application that takes a rooftop address, fetches
satellite imagery and OSM building footprints, runs two independent
energy models against PVGIS hourly weather data, applies the Egyptian
EgyptERA tiered tariff, and reports system size, payback with a 90 %
confidence interval, lifetime CO₂ avoidance, and a sensitivity tornado.

---

## Why this exists

Existing rooftop-PV calculators consistently misprice payback in
Egypt because they assume a flat tariff. Egypt's residential
electricity is sold on a seven-tier *progressive marginal block*
schedule, which means the same kWh of solar generation is worth
2–3× more for a heavy consumer than for a light one. This project's
contribution is to model the actual schedule, optimise system size
under it, and surface the result with a Monte Carlo confidence
interval rather than a point estimate.

---

## Quickstart

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

* Interactive API docs: `http://localhost:8000/docs`
* Health check: `curl http://localhost:8000/health`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App runs at `http://localhost:5173` and expects the backend on
`http://localhost:8000` (override with `VITE_API_BASE_URL`).
See [`frontend/README.md`](./frontend/README.md) for the full
component map.

### Demo (deterministic end-to-end)

A curated end-to-end run that exercises every backend kernel with
hard-coded Cairo inputs:

```bash
./scripts/demo.sh
```

The script starts the backend, walks `sizing → energy → financial →
tariff → monte-carlo → co2 → sensitivity → roof-detection (offline)`
in order, and prints each kernel's headline numbers so a thesis
examiner can see the whole dashboard wire up in one terminal.

### Tests

```bash
cd backend
.venv/bin/pytest -q
```

The full suite includes a Day-20 validation panel that compares the
deterministic dashboard against published Egyptian rooftop-PV figures
across seven cities; see [`research/validation.md`](./research/validation.md).

---

## Academic contributions

Four contributions, all auditable in the source tree:

| # | Contribution | Source | Document |
|---|---|---|---|
| 1 | **Dual energy model** — pvlib (Hay-Davies + SAPM) cross-validated against a manual physics chain (Liu-Jordan + NOCT) | `backend/app/services/energy_pvlib.py`, `energy_manual.py` | methodology §2.2–2.3 |
| 2 | **AI-assisted roof detection** — Overpass + Google Maps Static + classical-CV regularisation | `backend/app/services/overpass_service.py`, `gmaps_static.py`, `roof_segmentation.py`, `roof_orientation.py` | methodology §5 |
| 3 | **EgyptERA tiered-tariff optimisation** — progressive marginal-block billing + NPV-maximising size grid search | `backend/app/services/tiered_tariff.py` | methodology §3.2 |
| 4 | **Monte Carlo uncertainty + OAT tornado** — 1000-simulation parametric ensemble + 7-parameter tornado | `backend/app/services/monte_carlo.py`, `sensitivity.py` | methodology §4 |

---

## Repository layout

```
pv-system/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI entry point
│   │   ├── config.py            Settings + Egypt-tuned constants
│   │   ├── routers/             API endpoints
│   │   ├── services/            Domain kernels (sizing, energy, financial, tariff, monte-carlo, sensitivity, co2, roof-detection)
│   │   └── schemas/             Pydantic v2 request/response schemas
│   ├── tests/                   Per-kernel suites + week-1 invariants + Day-20 Egypt validation
│   └── requirements.txt
├── frontend/                     React + Vite + TypeScript dashboard (Days 12–17)
├── research/
│   ├── methodology.md           Day-19 academic, LaTeX-ready specification
│   ├── validation.md            Day-20 Egypt validation report (21-case harness)
│   ├── limitations.md           Day-21 limitations + future-work register (F-1…F-21)
│   └── references.bib           BibTeX for all cited literature
├── outputs/                     One file per agent run (the day-by-day narrative)
├── scripts/
│   └── demo.sh                  End-to-end deterministic demo
├── docs/                        Setup notes, agent configuration
├── PLAN.md                      The 21-day plan this project delivered
└── README.md                    (this file)
```

---

## Egypt-specific assumptions

Every Egypt-tuned constant lives in `backend/app/config.py` as a
field on the `Settings` class so the project can be retargeted to
another country by editing one file.

| Parameter | Value | Source |
|---|---|---|
| Default tilt | 26° | Cairo latitude optimum |
| Default azimuth | 180° (south) | Northern-hemisphere optimum |
| Roof utilisation factor | 0.7 | Mahmoud & El-Nokali 2023 |
| Panel rated power | 450 W | Industry standard 2024 |
| Panel area | 1.8 m² | Industry standard 2024 |
| Inverter efficiency | 96 % | Modern grid-tied inverters |
| Installed cost | 35 000 EGP/kW | Egyptian PV market 2024 |
| Tariff escalation prior | $\mathcal N(0.08, 0.03)$ | EgyptERA decade history |
| Discount rate | 4 % real | Standard Egyptian residential infrastructure |
| Module degradation prior | Triangular(0.002, 0.005, 0.010) | NREL Jordan & Kurtz 2013 |
| Grid emission factor | 0.46 kg CO₂/kWh | EEHC 2023 annual report |
| EgyptERA tariff schedule | 7-tier post-July-2023 reform | EgyptERA published bill statement |

See [`research/methodology.md`](./research/methodology.md) §1.3 for the
full table with citations and
[`research/limitations.md`](./research/limitations.md) §1–§7 for the
documented simplifications around each constant.

---

## Documentation map

| Document | Audience | Purpose |
|---|---|---|
| [`PLAN.md`](./PLAN.md)                              | Author / agent | The 21-day plan and the frontend design brief |
| [`research/methodology.md`](./research/methodology.md) | Thesis examiner  | What the system does, equation-by-equation |
| [`research/validation.md`](./research/validation.md)   | Thesis examiner  | What the system's output bands are, vs published Egypt figures |
| [`research/limitations.md`](./research/limitations.md) | Thesis examiner / follow-up student | What the system does *not* do and why; future-work register (F-1…F-21) |
| [`research/references.bib`](./research/references.bib) | Thesis manuscript | Single-source BibTeX |
| [`outputs/`](./outputs/)                            | Author          | Day-by-day plain-English narrative of every agent run |
| [`frontend/README.md`](./frontend/README.md)        | Frontend developer | Component map and Day-12 scaffold notes |
| [`docs/agent-setup.md`](./docs/agent-setup.md)      | Operator        | Daily implementation agent configuration |

---

## Daily implementation agent

A scheduled remote agent picks up the next undone day from
[`PLAN.md`](./PLAN.md), creates the corresponding feature branch,
implements the deliverable, opens a pull request for review, and
writes a plain-English brief to `outputs/NN-<slug>.md`. Each output
file maps 1-to-1 to one agent run, so the project's progress is
readable without diving into code.

See [`docs/agent-setup.md`](./docs/agent-setup.md) for the prompt and
the cron configuration. The output template lives at
[`outputs/_TEMPLATE.md`](./outputs/_TEMPLATE.md).

---

## License

Educational / academic use.
