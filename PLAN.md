# PV Rooftop Solar Estimation System — 3-Week Plan

> **Project:** AI-Assisted Rooftop Solar Potential Estimation and Financial Analysis System
> **Author:** Nada (Bachelor's Thesis)
> **Region:** Egypt (Cairo focus, generalizable)
> **Timeline:** 3 weeks (21 days)
> **Status:** Day 1 — scaffolding

---

## 🎯 Core Academic Contributions

This thesis goes beyond "API integration." Four defensible contributions:

### 1. Dual Energy Model (baseline)
Two independent energy generation models — `pvlib` (industry-standard) and a **manual physics-based model** built from first principles. Cross-validation between them is the methodological backbone.

### 2. AI-Assisted Roof Detection (Contribution A)
User enters an address. The system fetches a satellite image and uses computer vision (OpenStreetMap building footprints + segmentation model) to **automatically detect roof area, tilt, and orientation** — eliminating the most error-prone user input.

### 3. Egypt Tiered Tariff Optimization (Contribution B)
Egypt's residential electricity uses **progressive tier pricing** (EgyptERA). Most existing PV calculators assume flat tariffs and **systematically miscalculate Egyptian payback periods**. This system models the actual tier structure and optimizes system size for maximum household savings under tiered pricing — a domain-specific contribution unique to the Egyptian market.

### 4. Monte Carlo Uncertainty Analysis (Contribution C)
Treats uncertain inputs (panel degradation, tariff inflation, weather variability, soiling, inverter replacement) as probability distributions. Runs 1000 simulations to produce **confidence intervals** rather than point estimates. Outputs: "Payback: 7.2 ± 1.5 years (90% CI)."

---

## 🧍 User Flow

1. User enters address (or lat/lng) + electricity tariff + optional roof override.
2. Backend fetches satellite tile + OSM footprint → auto-detects roof polygon → computes area, tilt, azimuth.
3. PVGIS API returns Typical Meteorological Year (TMY) hourly weather for the location.
4. Two energy models run in parallel: `pvlib` and the manual physics model.
5. Tiered tariff optimizer finds the system size that maximizes annual savings.
6. Monte Carlo simulation runs 1000 scenarios with stochastic inputs.
7. Dashboard displays:
   - Detected roof + system size
   - Annual generation (pvlib vs manual comparison chart)
   - **Payback period with confidence interval**
   - Tier-bracket savings visualization
   - CO₂ savings
   - Sensitivity tornado chart

---

## 🏗️ Architecture

```
┌──────────────────┐     ┌──────────────────────────────────────────┐     ┌──────────────────┐
│  React + Vite    │────▶│   FastAPI Backend                        │────▶│   PVGIS API      │
│  Frontend        │     │                                          │     │  (TMY hourly)    │
│                  │◀────│   Services:                              │     └──────────────────┘
│  - Address input │     │     - roof_detection (GMaps + OSM + CV)  │     ┌──────────────────┐
│  - Map view      │     │     - pvgis_service                      │────▶│  Google Maps     │
│  - Dashboard     │     │     - pv_sizing                          │     │  Static API      │
│  - Charts        │     │     - energy_pvlib                       │     └──────────────────┘
└──────────────────┘     │     - energy_manual (physics)            │     ┌──────────────────┐
                         │     - loss_model                         │────▶│  OpenStreetMap   │
                         │     - tiered_tariff (Egypt)              │     │  Overpass API    │
                         │     - financial_model                    │     └──────────────────┘
                         │     - monte_carlo                        │
                         │     - co2_model                          │
                         └──────────────────────────────────────────┘
```

---

## 📅 Week 1 — Backend Foundation + Roof Detection

| Day | Deliverable | Branch |
|-----|-------------|--------|
| 1   | Repo, FastAPI skeleton, schemas, .gitignore, venv                   | `main` (this commit) |
| 2   | PVGIS API integration (TMY fetcher + parser)                        | `feat/pvgis-integration` |
| 3   | PV sizing module (panel count, system kW)                           | `feat/pv-sizing` |
| 4   | pvlib-based energy model (PVWatts approach)                         | `feat/energy-pvlib` |
| 5   | Manual physics-based model (POA, temp, DC→AC)                       | `feat/energy-manual` |
| 6   | Basic financial model (cost, flat-tariff savings, payback)          | `feat/financial-basic` |
| 7   | Unit tests for energy + sizing + financial; tag `v0.1-backend-core` | `chore/tests-week1` |

---

## 📅 Week 2 — Three Contributions + Frontend Start

| Day | Deliverable | Branch |
|-----|-------------|--------|
| 8   | **Egypt tiered tariff** model + optimizer (Contribution B)          | `feat/tiered-tariff` |
| 9   | **Monte Carlo** uncertainty engine (Contribution C)                 | `feat/monte-carlo` |
| 10  | **Roof detection** part 1: Google Maps Static + OSM Overpass        | `feat/roof-detection-osm` |
| 11  | **Roof detection** part 2: CV segmentation + tilt/azimuth estimate  | `feat/roof-detection-cv` |
| 12  | React + Vite + TS scaffold, routing, API client, design system — **read [Frontend Design Brief](#-frontend-design-brief-read-before-day-12) first** | `feat/frontend-init` |
| 13  | Address input + map preview component (Leaflet) — follow Frontend Brief    | `feat/input-form` |
| 14  | Dashboard layout: metric cards (size, kWh, savings, payback CI) + "Know more" modals — follow Frontend Brief | `feat/dashboard-cards` |

---

## 📅 Week 3 — Charts, Validation, Polish

| Day | Deliverable | Branch |
|-----|-------------|--------|
| 15  | Monthly production chart + pvlib-vs-manual comparison view — follow Frontend Brief  | `feat/charts-comparison` |
| 16  | Monte Carlo visualization (histogram + fan chart for cumulative ROI) — follow Frontend Brief | `feat/charts-monte-carlo` |
| 17  | Tier-bracket "before vs after" visualization — follow Frontend Brief                 | `feat/charts-tariff` |
| 18  | CO₂ savings + Egypt grid emission factor + sensitivity tornado      | `feat/co2-sensitivity` |
| 19  | **Methodology section** (academic, LaTeX-ready)                     | `docs/methodology` |
| 20  | **Validation** (compare against published Egypt PV studies + tests) | `docs/validation` |
| 21  | **Limitations** + references.bib + README + demo script             | `docs/final` |

---

## 🎨 Frontend Design Brief (READ before Day 12)

> **For the agent:** This section is the canonical specification for the entire frontend (Days 12–17). Read it in full **before** starting Day 12 and re-read the relevant subsection at the start of every frontend day. The Day-table rows above are intentionally short — the *real* spec lives here.

### Design mood — Positivus-inspired

The visual language follows the **Positivus Landing Page Design** (community Figma):
**https://www.figma.com/design/8sfwze4d2Oha9P3mVaP9dW/Positivus-Landing-Page-Design--Community-**

Mood and aesthetic:
- **Bold, modern, friendly.** This is a tool a homeowner uses to make a real-money decision — it should feel confident and professional but not corporate or intimidating.
- **High contrast, generous whitespace.** Large typography, clear visual hierarchy, lots of breathing room. The user should never feel overwhelmed by information density.
- **Geometric and rounded.** Cards have generously rounded corners (16–24 px). Buttons are rounded rectangles with strong dark fills. Large decorative shapes are welcome but never compete with data.
- **Black + white base, single accent.** Pure black text on white background is the spine. Lime-green (Positivus signature, ~`#B9FF66`) is the accent for primary actions, highlight cards, and decorative shapes. Use sparingly and consistently.
- **Illustrations where they help.** Small line illustrations or icons next to section headers make technical concepts feel approachable. Never use stock photos.

### Color tokens (configure in `tailwind.config.ts`)

| Token | Hex | Used for |
|---|---|---|
| `bg`            | `#FFFFFF` | Page background |
| `surface`       | `#F3F3F3` | Card backgrounds, subtle sections |
| `ink`           | `#191A23` | Primary text, primary buttons |
| `ink-soft`      | `#4A4B57` | Secondary text |
| `accent`        | `#B9FF66` | Primary CTAs, highlight cards, hero accents |
| `accent-soft`   | `#E8FFD4` | Soft accent backgrounds (e.g. info cards) |
| `border`        | `#191A23` | Card outlines (heavy, 2 px) |
| `success`       | `#22C55E` | Positive metrics (savings, CO₂ avoided) |
| `warning`       | `#F59E0B` | Confidence-interval edges |
| `danger`        | `#EF4444` | Errors, blocked-PR labels |

### Typography

- **Display / Hero:** "Space Grotesk" 700 weight, 56–80 px, very tight tracking.
- **Section headers:** "Space Grotesk" 600 weight, 32–40 px.
- **Body:** "Inter" or system stack, 16 px, 1.6 line-height.
- **Numbers (metrics):** "Space Grotesk" 600, 40–56 px — they are the protagonists.
- All Google Fonts; load via `<link>` in `index.html`, not via JS.

### Layout principles

1. **Single-column flow on mobile, max-width 1200 px on desktop.** The tool is fundamentally one journey: enter inputs → see results.
2. **Hero section.** Bold headline ("How much can solar save you?"), one-sentence subhead, primary CTA, optional decorative geometric accent.
3. **Estimator section.** Address + roof inputs, big primary "Estimate" button.
4. **Results dashboard.** Cards in a 2- or 3-column grid (1-column on mobile). Each card surfaces ONE number prominently with a small "Know more" trigger.
5. **Charts section.** Below the cards, full-width visualisations.
6. **Footer.** Sources + thesis disclaimer + GitHub link.

### Component patterns (build these once, use everywhere)

| Component | Notes |
|---|---|
| `<MetricCard title number unit subtitle knowMoreId />` | Used for every dashboard number. `knowMoreId` wires the "Know more" modal. |
| `<KnowMoreButton id="..." />` | Small pill button labelled "Know more →". Opens `<KnowMoreModal id="..." />` from a global registry. |
| `<KnowMoreModal id title body sources />` | Reusable modal. Body supports markdown + simple LaTeX-style formula blocks. |
| `<PrimaryButton />` | Dark fill, white text, 16 px rounded, 16 px vertical padding, hover lifts. |
| `<AccentButton />` | Lime fill, dark text — used only for the hero CTA. |
| `<Card />` | White surface, 2 px ink border, 16 px rounded, 24 px padding. |
| `<HighlightCard />` | Same as Card but lime fill — used for the "headline" metric (typically Payback CI). |
| `<Section title="..." />` | Section wrapper with title chip + spacing. |

### "Know more" modal pattern (CRITICAL — this is the user-friendliness backbone)

Every section that surfaces a calculation has a small `Know more →` button next to it. Clicking opens a modal with:

1. **Title** — plain English ("How is the panel count calculated?")
2. **Plain English body** — 1–2 short paragraphs explaining the concept without any code or jargon. Imagine a homeowner reading it.
3. **The math** — the formula(s) used, written out cleanly (LaTeX-like, no actual LaTeX dependency required).
4. **Variables used** — the actual values from this user's request (e.g. "Your roof: 100 m², Utilization factor: 0.7, Panel area: 1.8 m²").
5. **Sources** — links to `research/methodology.md` section anchors and any external references.

The modal content lives in a single TypeScript registry file (e.g. `frontend/src/content/explainers.ts`) — one entry per concept — so adding a new explainer is a one-file change. The modal component reads from the registry by `id`.

**Required explainers (one modal per row — agent must implement all of these):**

| Modal id | Where it appears | Title |
|---|---|---|
| `system-size`        | System Size card                  | How is the panel count calculated? |
| `energy-pvlib`       | Annual Generation card (pvlib tab)| How does the industry-standard model work? |
| `energy-manual`      | Annual Generation card (manual tab)| How does our physics model work? |
| `model-comparison`   | Comparison chart                  | Why two energy models? |
| `tiered-tariff`      | Annual Savings card               | How does Egypt's tiered tariff change the math? |
| `payback-ci`         | Payback Period card               | What does "± 1.5 years" actually mean? |
| `monte-carlo`        | Sensitivity / fan chart           | How does the Monte Carlo simulation work? |
| `co2-savings`        | CO₂ Avoided card                  | How is CO₂ avoidance calculated? |
| `roof-detection`     | Roof preview card                 | How does the AI detect the roof? |
| `losses`             | Generation card (secondary)       | What real-world losses are accounted for? |
| `sensitivity-tornado`| Tornado chart                     | Which inputs matter most? |

### Accessibility (non-negotiable)

- WCAG AA contrast ratios.
- Every interactive element keyboard-reachable (Tab order, visible focus rings).
- Modals trap focus while open and restore focus on close.
- All charts have a fallback `<table>` for screen readers.
- Form fields have proper `<label>` associations.

### State + data layer

- **TanStack Query** for all server calls. Each backend endpoint gets a typed hook (`useSizing()`, `useEstimate()`, etc.).
- **No global state library on Day 12.** Lift state, pass props. If complexity grows in Week 3, evaluate then.
- **Type safety end-to-end:** generate TypeScript types from the FastAPI OpenAPI schema (use `openapi-typescript`) — never hand-write request/response types.

### Folder structure (Day 12 sets this up)

```
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── components/
│   │   ├── ui/                  ← MetricCard, KnowMoreButton, KnowMoreModal, Card, etc.
│   │   ├── layout/              ← Header, Footer, Section
│   │   ├── estimator/           ← input form (Day 13)
│   │   ├── dashboard/           ← cards + grid (Day 14)
│   │   └── charts/              ← Recharts wrappers (Days 15–17)
│   ├── content/
│   │   └── explainers.ts        ← KnowMore registry — single source of truth
│   ├── hooks/                   ← TanStack Query hooks
│   ├── lib/
│   │   └── api.ts               ← typed fetch client
│   ├── types/                   ← generated from OpenAPI
│   └── styles/
│       └── tokens.css           ← CSS custom properties for color/typography tokens
├── index.html
├── tailwind.config.ts
├── tsconfig.json
├── vite.config.ts
└── package.json
```

### Day 12 specific deliverables (what "scaffold" actually means)

The agent on Day 12 must deliver **all** of:

1. `npm create vite@latest` with React + TypeScript template.
2. TailwindCSS installed and configured with the tokens table above.
3. Google Fonts loaded (Space Grotesk + Inter).
4. Header component with the project name + a stub link to GitHub.
5. Footer component with thesis disclaimer + sources link.
6. Hero section component (placeholder copy is fine; the visual structure must be in place).
7. The four core UI primitives: `<Card>`, `<HighlightCard>`, `<PrimaryButton>`, `<AccentButton>`.
8. **`<KnowMoreModal>` and `<KnowMoreButton>` components, fully working** — wired to a stub `explainers.ts` containing **at least the `system-size` entry** so the pattern is demonstrably end-to-end on Day 12. Subsequent days fill in the other entries.
9. TanStack Query provider wired into `main.tsx`.
10. `lib/api.ts` typed fetch client pointing at `http://localhost:8000` (env-configurable).
11. A working `useSizing()` hook calling `POST /api/sizing` and a placeholder page that demonstrates the end-to-end flow with one form field (roof area) and one card showing the result + a `Know more →` opening the system-size modal.
12. README in `frontend/` with `npm install` + `npm run dev` instructions.

After Day 12 lands, days 13–17 layer on top of this foundation without changing it.

### What "user-friendly" means concretely

- Every number has a unit (kWh, EGP, %, years).
- Every number has a tooltip OR a "Know more" trigger explaining where it came from.
- Loading states use skeleton cards, never blocking spinners.
- Errors render inline with a clear next-action message ("PVGIS unavailable — try again in a minute").
- The "Estimate" button has three states: idle, loading, success — never just disabled-with-no-feedback.
- All copy is plain English, free of acronyms unless explained on first use.

---

## 🛠️ Tech Stack

**Backend (Python 3.12)**
- FastAPI + Uvicorn (web framework)
- pvlib (PV modeling — industry standard)
- pandas, numpy (data + numerics)
- requests / httpx (external APIs)
- pydantic v2 (schemas)
- Pillow + OpenCV (image processing for roof detection)
- shapely (polygon math)
- scipy (Monte Carlo distributions, optimization)
- pytest (testing)

**Frontend**
- React 18 + Vite + TypeScript
- TailwindCSS (styling)
- Recharts (charts)
- Leaflet (maps)
- TanStack Query (API client)

**External APIs**
- PVGIS — `https://re.jrc.ec.europa.eu/api/v5_2/` (free, no key)
- Google Maps Static API — for satellite tiles (free tier with API key)
- OpenStreetMap Overpass — `https://overpass-api.de/` (free, building footprints)

---

## 📊 Egypt-Specific Assumptions (initial — refined in research/)

### Hardware
| Parameter | Value | Source |
|-----------|-------|--------|
| Panel rating | 450 W | Industry standard 2024 |
| Panel area | 1.8 m² | Industry standard 2024 |
| Roof utilization factor | 0.7 | Common rule-of-thumb |
| Inverter efficiency | 96% | Modern grid-tied inverters |

### Egypt environment
| Parameter | Value | Source |
|-----------|-------|--------|
| Soiling losses | 2–8% (varies by region) | Egyptian PV literature |
| Default tilt | 26° | Cairo latitude |
| Default azimuth | 180° (south) | Northern hemisphere optimum |
| Grid emission factor | 0.46 kg CO₂/kWh | EEHC 2023 |

### Egypt market
| Parameter | Value | Source |
|-----------|-------|--------|
| Installed system cost | ~35,000 EGP/kW | Egyptian market 2024 |
| Tariff inflation rate | 8% ± 3% (annual) | EgyptERA history |
| Discount rate (real) | 4% | Standard project finance |
| Tariff structure | EgyptERA residential tiers | EgyptERA published rates |

---

## 🎓 Deliverables

1. ✅ Backend (FastAPI + 9 services) with API documentation
2. ✅ Frontend (React) with map input + interactive dashboard
3. ✅ AI roof detection pipeline
4. ✅ Tiered tariff optimization model
5. ✅ Monte Carlo uncertainty analysis
6. ✅ Methodology section (academic style)
7. ✅ Validation report (vs published Egypt studies)
8. ✅ Limitations document
9. ✅ References (BibTeX)
10. ✅ Deployment-ready Docker + README

---

## 🤖 Daily Agent Workflow

A scheduled agent runs **every 8 hours**. Each run:
1. Picks the next item from this PLAN.
2. Opens the corresponding feature branch.
3. Implements the deliverable + commits with a dated, descriptive message.
4. **Writes a "professor brief" to `outputs/NN-<slug>.md`** — plain-English explanation of what was built and why. This is the day-by-day narrative you can read without diving into code.
5. Opens a PR for your review.

You: review → comment / merge. ~10–15 min per agent run.

**The `outputs/` folder is your source of truth for understanding the project's progress.** Each file maps 1-1 to an agent run.

---

## 📝 How This Plan Evolves

This is a **living document**. Edit freely as scope clarifies. If a day slips, push subsequent items back rather than skipping. Each contribution (A, B, C) is independent — if one becomes infeasible, the other two still stand.
