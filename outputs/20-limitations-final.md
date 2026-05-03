# Output 20 — Limitations chapter, final README, demo script

> **Date:** 2026-05-03
> **Plan day:** Day 21
> **Branch:** `docs/final`
> **Status:** ✅ Complete

---

## Plain English

This is the closing day of the project, the day a thesis manuscript stops adding new calculations and starts being honest about what the calculator does not do.
We wrote a long structured chapter that walks a reader through every assumption we made — from "the year is a typical year, not a measured year" to "we use one panel type" to "we don't subtract the carbon footprint of making the panels themselves" — and pairs each assumption with a citation, an estimate of what fixing it would cost, and a future-work tag a follow-up student can quote.
We rewrote the project's front page so a stranger arriving at the source code sees, in one read, what the project does, why anyone should care that it exists for Egypt specifically, where every number on the dashboard comes from, and how to run the whole thing on their own laptop.
We added a small command that, when typed into the terminal, walks the calculator through every calculation it knows how to make, with a sample household in Cairo, and prints the numbers as they would appear on the dashboard, so a thesis examiner can see the entire system work end-to-end without learning to navigate a web interface.
And we extended the project's reading list with the few remaining sources the limitations chapter cites, so every name dropped anywhere in the project — methodology, validation, limitations — resolves to a full bibliography entry the manuscript can paste straight into a thesis.

---

## What I built

Day-21 is the closing-out day. Three artefacts get rewritten and one
gets created:

```
research/
├── limitations.md          REWRITTEN — 11-section limitations chapter + 21-item future-work register
└── references.bib          EXTENDED — 5 new BibTeX entries for the limitations citations
README.md                   REWRITTEN — project orientation; doubles as the thesis-defence quickstart
scripts/
└── demo.sh                 NEW — end-to-end deterministic pipeline demo
outputs/
└── 20-limitations-final.md NEW — this file
```

Specifically:

* **`research/limitations.md`** is now an academic-grade Limitations
  chapter with:
  * 11 numbered sections covering solar resource (§1), PV modelling
    (§2), financial modelling (§3), uncertainty quantification (§4),
    AI roof detection (§5), CO₂ avoidance (§6), tariff schedule (§7),
    hardware generalisation (§8), validation harness (§9), and a
    consolidated future-work register (§10) of 21 stable
    `F-1`…`F-21` tags so a follow-up paper can cite individual items.
  * Every limitation paired with (a) the source-code location, (b)
    the academic citation it is anchored against, and (c) a concrete
    future-work statement with an effort estimate.
* **`research/references.bib`** gains five new entries covering keys
  introduced by the limitations chapter: `capmas2023`,
  `egyptian_pv_market_2024`, `nrea_atlas`, `gueymard_ruizarias_2014`,
  `ema_sandstorms`. The bibliography is now closed-set: every key
  cited inline in any of the three research documents has a matching
  entry.
* **`README.md`** is rewritten to be the project's actual orientation
  document — a "Why this exists" section explaining the EgyptERA tier
  problem, a Quickstart for backend / frontend / demo / tests, a
  table of academic contributions linked to source files, an
  Egypt-tuned constants table linked to `config.py`, and a
  documentation map pointing at every other research document.
* **`scripts/demo.sh`** is a 200-line end-to-end demo that walks
  every backend kernel in dashboard order against a hard-coded Cairo
  scenario:

  ```
  health → sizing → energy(pvlib) → energy(manual) →
    financial(flat) → tariff(bill) → tariff(savings) →
    tariff(optimize) → monte-carlo → co2 → sensitivity-tornado →
    roof-detection
  ```

  Each step prints its headline numbers (parsed with a small inline
  Python helper to avoid jq as a hard dependency). The script is
  network-tolerant: PVGIS-dependent and Overpass-dependent steps
  fall through with a warning instead of aborting, so a thesis
  examiner running the demo on a flight or in a sandbox sees the
  full pipeline shape rather than a half-finished output.

---

## Why this matters (academic logic)

A bachelor thesis closes on three artefacts, and Day 21 produces all
three:

### 1. The Limitations chapter is what makes the thesis defensible

The methodology chapter (Day 19) tells an examiner what the system
*does*; the validation chapter (Day 20) tells them what the system's
output bands *are*. Without a Limitations chapter, the examiner can
ask "what about X?" — embodied carbon, marginal-dispatch emission
factors, joint-uncertainty Sobol indices, autocorrelated yield noise,
inverter-replacement multiplicity, sandstorm-frequency derate,
Mediterranean-coast cloud cover, etc. — and the student has to answer
in real time. The Limitations chapter pre-empts every one of those
questions: each is named, anchored to a citation, and given an
effort estimate. A defence is not made by claiming the system is
complete; it is made by showing the student knows *exactly* where it
is incomplete.

The 21-item future-work register (`F-1`…`F-21`) is a deliberate
design choice: stable identifiers mean a follow-up paper or a
follow-up student can cite "the F-7 net-metering rule" unambiguously
even after future reorganisations of the document.

### 2. The README is the project's first impression

A bachelor thesis's source code is read by three audiences: the
examiner reproducing the headline numbers, a follow-up student
extending the work, and a future Nada looking at her own project a
year later. All three need the same thing: a single page that says
*why this exists*, *how to run it*, and *where to find the rest*.

The "Why this exists" section is a deliberate methodology-narrative:
it foregrounds the EgyptERA tiered-tariff insight that motivates
Contribution B and explains in two paragraphs why the project's
existence is non-trivial, which is the question every thesis
examiner asks first.

### 3. The demo script makes the dashboard reproducible without the dashboard

The deterministic backend pipeline is the load-bearing layer of the
project. The frontend is the layer that *sells* it, but a thesis
examiner needs to inspect the *kernels* and `pytest -q` returning
green is not the same as seeing the kernels run end-to-end on a
specific input. The demo bridges that: a single shell command walks
every kernel in dashboard order on hard-coded Cairo inputs and
prints each headline so the whole pipeline is auditable from one
terminal session.

The demo is *deliberately* not a thin re-skin of the test suite.
Tests assert invariants; demo prints kernel-realistic outputs
(payback ≈ 17.7 yr, NPV ≈ 114 kEGP, lifetime CO₂ ≈ 92.4 t,
optimal tier-aware system ≈ 2.5 kW, flat-tariff optimum ≈ 15 kW —
the exact numbers the validation report's §5.1 baseline produces).
The two artefacts are complementary: tests *check*, demo *shows*.

---

## How the code is organised

```
research/
├── methodology.md      (unchanged on Day 21)
├── validation.md       (unchanged on Day 21)
├── limitations.md      REWRITTEN — 11 sections, 21 future-work tags
└── references.bib      EXTENDED  — 25 → 30 BibTeX entries
README.md               REWRITTEN — orientation + quickstart + Egypt constants table
scripts/
└── demo.sh             NEW — end-to-end deterministic demo
outputs/
└── 20-limitations-final.md  this file
```

Two design notes:

* **Limitations document tone.** Section 11 of the chapter explicitly
  draws the line between *limitations* (deliberate scope or
  methodology choices, paired with cost-of-fixing) and *bugs*
  (defects that belong in the test suite). This boundary matters —
  conflating the two is the most common mistake a bachelor thesis
  makes in its closing chapter, and it dilutes both.
* **Demo script error model.** The script uses
  `set -uo pipefail` (no `-e`) and a custom `post()` helper that
  surfaces non-2xx HTTP codes inline but does not abort the run.
  This is the right error model for a demo that *includes* steps
  requiring third-party APIs: the goal is to show every kernel that
  *can* run, not to abort on the first network hop. The PVGIS-
  dependent steps (`/api/energy/pvlib`, `/api/energy/manual`) fall
  through to a fixture annual-kWh that is consistent with the
  Day-20 Cairo validation result, so the financial and Monte Carlo
  numbers downstream remain consistent across offline and online
  runs of the demo.

---

## How I verified it works

1. **Backend test suite** — `cd backend && .venv/bin/pytest -q` reports
   **382 passed in 4.69 s**, identical to the post-Day-20 baseline.
   No source kernel was touched on Day 21 (this is a documentation +
   demo-script day), so a green suite confirms no accidental
   regression.
2. **Demo end-to-end run** — booted the backend on a local port and
   ran `API_BASE=http://127.0.0.1:8769 ./scripts/demo.sh`. The full
   walk produces:
   * Sizing: 30 m² Cairo roof → 4.95 kW (11 panels at 450 W).
   * Financial baseline at the EgyptERA-effective average tariff
     (≈ 1.009 EGP/kWh): NPV ≈ 114 367 EGP, discounted payback
     ≈ 17.7 yr, LCOE ≈ 1.58 EGP/kWh.
   * EgyptERA bill at 400 kWh/mo: 403.50 EGP, marginal 1.40
     EGP/kWh — matches the Day-20 hand computation byte-identically.
   * Tariff savings under PV: bill goes from 4842 to 0 EGP/yr; 4800
     kWh self-consumed, 3723 kWh exported (zero credit at default).
   * NPV-maximising tier-aware size: 2.5 kW (vs 15 kW under the
     flat-tariff counterfactual); the gap is the precise expression
     of Contribution B.
   * Monte Carlo (1000 sims, seed 42): payback probability 0.786,
     positive NPV probability 0.786.
   * CO₂: 3920 kg/yr year-1; 92.4 t over 25 yr; 367 940 km of car
     driving avoided.
   * Sensitivity tornado: tariff escalation dominates (Δ ≈ 248 kEGP),
     followed by discount rate (Δ ≈ 220 kEGP), tariff (Δ ≈ 126 kEGP),
     installed cost (Δ ≈ 86 kEGP), generation (Δ ≈ 63 kEGP), O&M
     (Δ ≈ 41 kEGP), degradation (Δ ≈ 34 kEGP) — directionally
     consistent with the Day-18 ranking on the same baseline.
3. **Bibliography integrity** — every BibTeX key cited inline in
   `limitations.md` (`capmas2023`, `egyptian_pv_market_2024`,
   `nrea_atlas`, `gueymard_ruizarias_2014`, `ema_sandstorms`) and in
   the methodology / validation chapters resolves to a `@type{key,…}`
   entry in `references.bib`. Spot-checked by `grep`-ing each cited
   identifier.
4. **README cross-references** — every link on the README
   (`PLAN.md`, `methodology.md`, `validation.md`, `limitations.md`,
   `references.bib`, `frontend/README.md`, `docs/agent-setup.md`,
   `outputs/`) points at a real file in the repo.
5. **Demo script syntax** — `bash -n scripts/demo.sh` returns no
   errors; the script handles both the live-PVGIS path and the
   offline fall-through path. Verified end-to-end in both states.

---

## What's next

`PLAN.md` ends at Day 21. The day-by-day implementation phase of the
project is therefore complete. The remaining tasks are *not* on the
day-table:

* **Thesis manuscript.** The three research documents (methodology,
  validation, limitations) plus the bibliography (`references.bib`)
  and the day-by-day narrative (`outputs/`) provide every paragraph
  the manuscript needs. The demo script's transcript is a useful
  appendix figure for the manuscript.
* **Defence preparation.** The 21-item future-work register
  (limitations §10) is the structured set of "what would you do
  next?" questions to anticipate.
* **Frontend polishing.** Discretionary; not on `PLAN.md`. The
  Day-12-through-17 frontend already supports the full deterministic
  dashboard.

A future agent run will, by `PLAN.md` design, find no undone day to
ship — and that is the correct end-state. The next genuinely-undone
work belongs to the manuscript itself, not to this repository.

---

## Files changed

```
M  README.md                        (+135 / -49  lines)
M  research/limitations.md          (+466 / -41  lines)
M  research/references.bib          (+47        lines)
A  scripts/demo.sh                  (+222 lines, executable)
A  outputs/20-limitations-final.md  (this file)
```

## How to run / verify yourself

```bash
# 1. Read the three research documents end-to-end:
less research/methodology.md
less research/validation.md
less research/limitations.md

# 2. Confirm no code regressions:
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q                          # 382 passed

# 3. Run the end-to-end deterministic demo:
.venv/bin/uvicorn app.main:app --reload &    # in another terminal, or backgrounded
cd ..
./scripts/demo.sh

# 4. Spot-check that every cited BibTeX key has a matching entry:
grep -oE '`[a-z0-9_]+`' research/limitations.md research/methodology.md research/validation.md \
  | sort -u \
  | sed 's/`//g' \
  | while read key; do
      grep -q "^@.*{$key," research/references.bib \
        && echo "  ok   $key" \
        || echo "  miss $key"
    done | head -50
```
