# PV Rooftop Solar Estimator

**AI-Assisted Rooftop Solar Potential Estimation and Financial Analysis System**

Bachelor's thesis project. Estimates residential PV system performance and financial feasibility for Egyptian rooftops using PVGIS irradiance data, dual energy models (`pvlib` + custom physics), AI-assisted roof detection, Egypt-specific tiered-tariff optimization, and Monte Carlo uncertainty analysis.

> See [`PLAN.md`](./PLAN.md) for the full 3-week development plan and academic contributions.

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

API docs available at: `http://localhost:8000/docs`

### Frontend

*(Scaffolded on Day 10 — see PLAN.md.)*

---

## Project Structure

```
pv-solar-estimator/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI entry point
│   │   ├── config.py            Settings + assumptions
│   │   ├── routers/             API endpoints
│   │   ├── services/            Domain logic (sizing, energy, financial, ...)
│   │   └── schemas/             Pydantic request/response models
│   ├── tests/
│   └── requirements.txt
├── frontend/                     React + Vite + TS (later)
├── research/                     Methodology, validation, limitations
├── docs/                         Diagrams, screenshots
├── PLAN.md                       Living development plan
└── README.md
```

---

## Academic Contributions

1. **Dual energy model** — `pvlib` baseline cross-validated against a manual physics model.
2. **AI roof detection** — automatic roof area + tilt + azimuth from satellite imagery.
3. **Egypt tiered tariff optimization** — first PV calculator that models EgyptERA progressive tariffs.
4. **Monte Carlo uncertainty** — payback expressed as a confidence interval, not a point estimate.

---

## License

Educational / academic use.
