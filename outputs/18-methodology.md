# Output 18 — Methodology Section (Academic, LaTeX-ready)

> **Date:** 2026-05-02
> **Plan day:** Day 19
> **Branch:** `docs/methodology`
> **Status:** ✅ Complete

---

## Plain English

A bachelor's thesis needs a chapter that explains, in academic prose, exactly how every number on the dashboard was calculated — what data went in, what equation was applied, where the constants came from, and why those choices were made instead of the alternatives.
Today we wrote that chapter.
The result is a single document with ten sections that walks a reader from the raw weather record all the way to the carbon-dioxide headline, with each section pinned to one piece of the codebase so an examiner can audit the math against the working program.
Alongside the chapter we also expanded the running list of academic sources the thesis will cite — every claim in the new chapter now has a paper or report behind it, recorded in the format the final manuscript will use.
The page on the website did not change today; everything the user sees on screen is unchanged. What changed is the body of writing that turns a working tool into a defensible piece of academic work.

---

## What I built

A 696-line, ten-section methodology chapter at `research/methodology.md`, written in academic prose with LaTeX equations rendered inline so the file drops directly into the thesis manuscript. The chapter maps one-to-one to the seven backend services that ship the math, so an examiner can read top-to-bottom and audit each step against the corresponding Python module. A 214-line `research/references.bib` carries every citation the chapter uses, in BibTeX form.

```
research/
├── methodology.md   (rewritten — 696 lines, academic, LaTeX-ready)
├── references.bib   (expanded — 214 lines, ~25 entries)
├── validation.md    (untouched — Day 20)
└── limitations.md   (untouched — Day 21)
```

Concretely, the new methodology chapter has the following structure:

1. **Data sources** — PVGIS TMY (§1.1), OSM + Google Maps Static (§1.2), Egypt-specific operating constants table (§1.3) with one row per published figure and its source.
2. **PV modelling** — sizing kernel (§2.1), pvlib industry-standard chain (§2.2), manual physics-based independent twin (§2.3), loss decomposition with the published 14 % breakdown (§2.4).
3. **Roof detection (Contribution A)** — OSM footprint retrieval and selection (§3.1), CV regularisation, confidence and orientation (§3.2), with the equirectangular projection equation, the perimeter-band Sobol-gradient confidence formula, and the rationale for choosing classical CV over a deep segmenter.
4. **Tiered-tariff billing and PV-size optimisation (Contribution B)** — the EgyptERA progressive-marginal block tariff (§4.1) with the upper-bound table and the marginal-vs-inclusive justification, the self-consumption-first PV netting equations (§4.2), and the PV-size optimiser (§4.3).
5. **Financial modelling** — year-by-year cash-flow chain (§5.1) with NPV, LCOE, simple-payback and discounted-payback equations; Egypt-specific economic constants (§5.2).
6. **Uncertainty quantification — Monte Carlo (Contribution C)** — parametric distributions and priors (§6.1) with a per-parameter source table, sampling and aggregation strategy (§6.2), cumulative-cash-flow trajectory bands for the Day-16 fan chart (§6.3).
7. **Sensitivity tornado** — the OAT method, the seven swung parameters, and the OAT-vs-Sobol justification.
8. **CO₂ avoidance** — the year-by-year displacement equation, the marginal-vs-grid-average emission factor justification, the homeowner-friendly equivalences.
9. **Reproducibility** — pure-function kernel contract, mock-vs-live test split, pinned runtime environment, single-command thesis re-derivation recipe.
10. **Summary** — claim-to-section traceability table, restating the four academic claims and where each is derived.

The expanded `references.bib` adds 18 new entries on top of the four that were in the skeleton: NREL PVWatts manual (Dobos 2014), NREL Solar Position Algorithm (Reda & Andreas 2008), Duffie & Beckman (2013), Liu & Jordan (1960), NREL SAM, IEA-PVPS Task 7, Jordan & Kurtz (NREL 2013) on degradation, IEA-PVPS Task 13 on inverter service life, IRENA 2023 on residential rooftop costs, EEHC 2022/2023 grid-emission factor, Mahmoud & El-Nokali 2023, Esmail & Negm 2021, El-Sayed 2017 on Egyptian soiling, IEA-PVPS Task 12 on LCA, US EPA equivalencies calculator, EEA passenger-car emissions, IPCC AR6 WG-III, Saltelli et al. 2008 on sensitivity analysis, OSM Overpass, Vargas-Muñoz et al. 2021, Haklay 2010 on OSM positional accuracy, Wang et al. 2018 on building extraction.

---

## Why this matters (academic logic)

Day 19 is the first of three documentation deliverables (methodology, validation, limitations) that turn the working software into a defensible piece of academic work. The methodology chapter is the single most important of the three — it is the chapter an external examiner reads first, the chapter the introduction's "the system computes X" claims redirect to, and the chapter against which the validation chapter (Day 20) measures error.

1. **Why a separate document and not docstrings?** The codebase already has rich module-level docstrings — every backend service has one and the comments reference the academic sources. But a thesis examiner reads a chapter, not a Python module. The methodology document is the *narrative reorganisation* of those docstrings: it traces the data flow end-to-end (raw TMY → AC kWh → financial cash flow → CO₂ + sensitivity), pulls the key equations into LaTeX, and assembles the citations into a single per-service table. The codebase remains the single source of truth for the math; the document is the single source of truth for the *narrative* about the math.

2. **Why ten sections and not a flat list of services?** The four academic claims (dual energy, AI roof detection, tiered tariff, Monte Carlo) decompose along a natural data-flow axis: data sources → physics modelling → roof geometry → tariff billing → financial cash flow → uncertainty. Each chapter section corresponds to one stage of that flow, not to one service module — so a service that touches more than one stage (e.g. the financial kernel feeds both §5 and §6 and §7) appears once per stage rather than being arbitrarily attributed to one. The §10 summary then collapses the chapter back to the four-claim view for cross-reference.

3. **Why LaTeX equations inline?** A reader reading on GitHub renders the file as Markdown; a reader reading in the thesis manuscript needs LaTeX. Modern Markdown renderers (GitHub, Pandoc, MkDocs Material) parse `$…$` and `$$…$$` blocks, so the same file serves both audiences without duplication. When the chapter is converted to the thesis's LaTeX template (Day 21) the Markdown-to-LaTeX conversion is mechanical because every formula is already in the target syntax.

4. **Why a per-section "why this and not the alternative" paragraph?** The methodology chapter is also where the *rejected alternatives* live. A defensible thesis is not "we used method X" but "we used method X *and not method Y* because…". The chapter therefore carries an explicit justification for every non-trivial choice: marginal vs inclusive tier billing (§4.1), Hay-Davies vs Perez sky-diffuse model (§2.2), pvlib SAPM vs NOCT (§2.3 cross-reference), classical CV vs deep segmentation (§3.2), parametric vs bootstrap Monte Carlo (§6.1), per-(sim, year) yield vs per-sim yield (§6.1), one inverter replacement vs two (§6.1), grid-average vs marginal emission factor (§8), trees + km equivalences vs tonnes-only (§8), OAT vs Sobol sensitivity (§7).

5. **Why a per-parameter source table for the Monte Carlo priors (§6.1)?** The single most important figure in Contribution C is the *uncertainty interval* on payback. That interval is only as defensible as the priors that produced it. The §6.1 table makes the priors auditable — every distribution carries its parameters and the published source those parameters came from. A reviewer who disagrees with one prior can re-run the engine with their own override (the API exposes every distribution as a request-level field) and read off the new interval; the table tells them which prior to override.

6. **Why a "Reproducibility" section (§9) at all?** The thesis must be reproducible end-to-end from a fresh checkout, including the Monte Carlo numbers cited in the headline payback claim. §9 documents the contract that makes that possible: pure-function kernels, a thread-able random seed on the only stochastic engine, mocked external APIs in the test suite plus a live-network validation pass in Day 20's chapter. A future reader who wants to update Egypt's grid emission factor or the EgyptERA tier schedule sees, in one place, exactly which knob to turn and how to verify the new headline numbers.

7. **Why the §10 claim-to-section traceability table?** The methodology chapter is long; an examiner who has read the introduction wants to confirm that each of the four academic claims is actually substantiated by a specific section. The traceability table does that mapping in one read. It is also the table the thesis introduction can cite directly when listing the contributions.

8. **Why expand `references.bib` now and not in Day 21?** Every citation in the new chapter must resolve. Adding the BibTeX entries today, in the same commit as the prose that cites them, prevents the citation graph from drifting. Day 21 will add a few last entries (deployment-tool references, demo script readme) but the substantive academic citations all land here so the methodology chapter is self-contained from this commit onwards.

---

## How the code is organised

```
research/
├── methodology.md            REWRITTEN — 696 lines, 10 sections, LaTeX-ready
└── references.bib            EXPANDED — 214 lines, ~25 BibTeX entries

# Code untouched. The methodology document is a narrative reorganisation
# of the existing kernel docstrings; the kernels themselves are the
# single source of truth for the math.
```

Backend service modules (`backend/app/services/*.py`) are unchanged. Frontend components are unchanged. The only files touched on Day 19 are the two research-folder markdown / BibTeX documents.

---

## How I verified it works

1. **Backend test suite (regression).** `cd backend && .venv/bin/pytest -q` reports **358 passed in 3.50 s** — identical to the Day 18 baseline (which is what we'd expect, since no Python changed). The methodology chapter is a documentation deliverable; the runtime contract that the chapter describes is exercised by the existing test suite.
2. **Markdown renders.** `research/methodology.md` parses cleanly as GitHub-flavoured Markdown. Every `$…$` and `$$…$$` block is balanced (verified by grep-counted parity), every internal cross-reference (`§N.M`) corresponds to a real section heading, and every BibTeX `@key` referenced in the prose (e.g. `[@pvgis]`, `[@jordan2013]`) has a matching entry in `references.bib`.
3. **Citation closure.** `references.bib` contains 23 entries; the methodology prose references 21 unique keys. The two unused entries (`esmail-negm-2021`, `wang2018`) are forward-references for the validation and limitations chapters and are documented in `_TEMPLATE.md`-style header comments inside the bib file.
4. **Numerical fidelity.** Every equation in the chapter was hand-verified against the corresponding Python source:
   - The sizing equations (§2.1) match `backend/app/services/pv_sizing.py` line-for-line (`compute_system_size`).
   - The pvlib chain steps (§2.2) match `backend/app/services/energy_pvlib.py::simulate` step-by-step (solar position → POA → cell temperature → DC PVWatts → DC losses → AC).
   - The manual chain table (§2.3) matches `backend/app/services/energy_manual.py` — same six steps with Liu–Jordan replacing Hay–Davies and NOCT replacing SAPM, exactly as the kernel docstring states.
   - The marginal billing equation (§4.1) matches `backend/app/services/tiered_tariff.py::_bill_one_month` — both walk the tiers in order and bill `min(U_i − U_{i−1}, max(0, C − U_{i−1}))` per band.
   - The financial cash-flow chain (§5.1) matches `backend/app/services/financial_basic.py::compute_financials` line-for-line.
   - The CO₂ chain (§8) matches `backend/app/services/co2_model.py::compute_co2_avoidance`.
   - The OAT swing definition (§7) matches `backend/app/services/sensitivity.py::compute_tornado`.
5. **Constants table (§1.3) ↔ `backend/app/config.py`.** Every value in the §1.3 Egypt-specific operating constants table was cross-checked against `backend/app/config.py::Settings`: panel rating 450 W, panel area 1.8 m², roof utilisation 0.7, inverter efficiency 0.96, default tilt 26°, default azimuth 180°, grid emission factor 0.46 kg CO₂/kWh, installed cost 35 000 EGP/kW, discount rate 0.04, tariff inflation 0.08, degradation 0.005, O&M 0.01. All match.
6. **Monte Carlo prior table (§6.1) ↔ `backend/app/config.py`.** Every distribution in §6.1 was cross-checked against the seven `monte_carlo_*` settings: degradation `triangular(0.002, 0.005, 0.010)`, inflation `normal(0.08, 0.03)` clipped at 0, O&M `triangular(0.005, 0.010, 0.020)`, capex `triangular(30 000, 35 000, 45 000)`, yield factor `normal(1.0, 0.05)` clipped to `[0.5, 1.5]`, inverter year `triangular(10, 12, 15)`, inverter cost fraction `triangular(0.07, 0.10, 0.15)`. All match.
7. **EgyptERA tier table (§4.1) ↔ `backend/app/config.py::EGYPT_RESIDENTIAL_TARIFF_TIERS`.** Seven rows, byte-identical to the configured schedule: `(50, 0.58), (100, 0.68), (200, 0.83), (350, 1.25), (650, 1.40), (1000, 1.45), (∞, 1.55)`.

---

## What's next

| Day | Deliverable                                                              | Branch                    |
| --- | ------------------------------------------------------------------------ | ------------------------- |
| 20  | Validation against published Egypt PV studies + tests                    | `docs/validation`         |
| 21  | Limitations + references.bib + README + demo script                      | `docs/final`              |

The Day 20 validation chapter consumes the methodology chapter directly: every numerical claim Day 20 makes ("our model produces X for Cairo, published study Y reports Z, residual is …") cross-references one of the methodology chapter's §-numbered sections so the reader can audit which method produced which validated number.

---

## Files changed

```
M  research/methodology.md          (+635 / -49 lines)  rewritten end-to-end
M  research/references.bib          (+184 / -4 lines)   expanded with ~20 new entries
A  outputs/18-methodology.md        (this file)
```

## How to run / verify yourself

```bash
# Pull and review the chapter
git pull origin docs/methodology
less research/methodology.md          # 696 lines, 10 sections
less research/references.bib          # 214 lines, ~25 BibTeX entries

# Confirm the regression suite still passes (no code changed; this is a
# documentation deliverable, but the chapter must accurately describe a
# kernel that still works).
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q                   # 358 passed

# Render the methodology chapter the way the thesis will see it. GitHub
# renders LaTeX in $…$ blocks natively; for a local preview that mirrors
# the thesis rendering use Pandoc:
pandoc research/methodology.md \
       --citeproc \
       --bibliography research/references.bib \
       -o /tmp/methodology.pdf

# Cross-check the constants table (§1.3) against the runtime config:
python3 -c "from app.config import settings; \
  print('grid', settings.egypt_grid_emission_kg_per_kwh); \
  print('cost', settings.installed_cost_egp_per_kw); \
  print('disc', settings.discount_rate); \
  print('infl', settings.tariff_inflation_rate); \
  print('degr', settings.annual_degradation_rate); \
  print('om',   settings.om_cost_fraction)"
# Each printed value must match the §1.3 row in research/methodology.md.
```
