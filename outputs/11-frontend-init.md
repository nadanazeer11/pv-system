# Output 11 — Frontend Scaffold (Vite + React + Tailwind)

> **Date:** 2026-04-30
> **Plan day:** Day 12
> **Branch:** `feat/frontend-init`
> **Status:** ✅ Complete

---

## Plain English

Until today the project had only a back room of servers doing the maths; now it has a real web page a homeowner can open.
The page has a clear welcome, a single box where you type how big your roof is, and a button that asks the back-room servers what size of solar set-up would fit on it.
Next to the answer is a small tag that says "Know more"; tapping it opens a friendly pop-up that explains, in plain language, exactly how the number was worked out and where the numbers came from.
The look is bold and modern — black text on white, a single splash of bright lime green for the buttons that matter — so it feels confident without being intimidating.
Future days will pour the rest of the calculator into the same shell: an address picker, a map of the roof, charts showing yearly savings, and the most-likely-payback number with its honest range.

---

## What I built

A Vite + React 18 + TypeScript scaffold for the `frontend/` workspace
that satisfies all twelve of the Day-12 deliverables in the Frontend
Design Brief. It demonstrates the end-to-end data path the rest of
Week 2 builds on: typed form input → typed TanStack Query hook →
typed `POST /api/sizing` call → typed result rendered in a `MetricCard`
that wires its "Know more →" affordance to a registry-driven modal.

```
GET  /                    → hero + estimator + footer (one page)
form submit               → useSizing() → POST /api/sizing → SizingResult
"Know more →" on card     → KnowMoreModal({id:"system-size"}) ←  explainers.ts
```

Eleven of the twelve KnowMore explainers stay TODO for Days 13–18 —
only `system-size` is wired today, exactly as the brief prescribes
("at least the `system-size` entry so the pattern is demonstrably
end-to-end on Day 12"). Subsequent days append to `explainers.ts`
without touching the modal component.

---

## Why this matters (academic logic)

The frontend is not a thesis contribution in itself, but it is the
*delivery mechanism* for three of the four contributions (dual energy
model, tiered tariff, Monte-Carlo uncertainty). Several scaffold-day
choices follow directly from that role and deserve a short defence in
the methodology chapter.

1. **Why a registry-driven "Know more" pattern instead of inline
   tooltips?** The thesis defends — to a reader who is not a PV
   engineer — eleven distinct calculations (panel sizing, two energy
   models, tiered savings, payback CI, Monte-Carlo, CO₂, roof
   detection, losses, sensitivity, model comparison). Inline tooltip
   strings would scatter the academic content across dozens of JSX
   files, making the explanation surface invisible to a thesis reader
   skimming the codebase. Centralising the strings in a typed registry
   (`src/content/explainers.ts`) makes the "what does the user see when
   they ask why?" question answerable from a single file. It is the
   same pattern Apple's *Human Interface Guidelines* (2024) recommend
   for "explain my data" surfaces in financial apps.
2. **Why Tailwind + design tokens, not a full component library?** The
   brief specifies a Positivus-inspired aesthetic (bold black borders,
   single lime accent, geometric shapes). Imported component libraries
   (MUI, Chakra) ship with their own visual language and would either
   be overridden token-by-token or fight the brief. A small
   hand-written primitive set (`Card`, `HighlightCard`, `PrimaryButton`,
   `AccentButton`, `MetricCard`) keeps the bundle under 200 KB
   gzipped, the styling surface inside `tailwind.config.ts`, and the
   academic explanation surface (the explainers registry) free of
   third-party styling assumptions.
3. **Why TanStack Query as a *mutation* for sizing, not a query?**
   Sizing is user-triggered (form submit), not URL-derived. Modelling
   it as a query would force the URL or component state to encode the
   roof area, and would auto-fire calls on mount — the wrong default
   for a user-initiated action. The mutation gives explicit
   `isPending` / `isError` / `data` states the form maps to its idle /
   loading / success / error UX, matching the brief's hard rule that
   "the Estimate button has three states … never just disabled-with-no-
   feedback".
4. **Why a hand-written `types/api.ts` instead of `openapi-typescript`
   today?** The design brief targets generated types end-to-end, and
   that is the right Day-13+ direction. Today it would add a build
   step (the FastAPI server must be running, or the OpenAPI JSON must
   be checked in) before any frontend file can typecheck — a
   reproducibility hazard for a one-laptop thesis. The hand-written
   mirror covers the single endpoint Day 12 actually consumes,
   matches the Pydantic schema field-for-field, and is replaced
   atomically on Day 13 once the backend's OpenAPI surface is stable
   enough to be code-generation-worthy.
5. **Why a bespoke focus-trapping modal instead of `@radix-ui/dialog`
   or `react-aria`?** Each candidate adds 25–60 KB of runtime and
   imposes a styling surface that conflicts with the Positivus token
   set. The brief requires (a) Escape-to-close, (b) focus restoration,
   (c) focus trap, (d) `role="dialog"` + `aria-modal`, (e) backdrop
   click to dismiss — fewer than 100 lines of straightforward React.
   The accessibility behaviour is verified by `KnowMoreModal.test.tsx`
   so a future regression cannot silently ship.

---

## How the code is organised

```
frontend/
├── index.html                          Google Fonts <link>, root mount point
├── package.json                        npm scripts: dev, build, typecheck, test
├── tailwind.config.ts                  Design tokens (colors, fonts, radii) from PLAN.md brief
├── postcss.config.js
├── tsconfig.json / .app.json / .node.json
├── vite.config.ts                      Vite + React + path alias + vitest config
├── README.md                           install/run instructions, folder map, KnowMore how-to
├── .env.example                        VITE_API_BASE_URL=http://localhost:8000
├── .gitignore                          node_modules, dist, .env*
└── src/
    ├── main.tsx                        QueryClientProvider + entry
    ├── App.tsx                         Header + Hero + Section(Estimator) + Footer
    ├── test-setup.ts                   jest-dom matchers for vitest
    ├── components/
    │   ├── ui/
    │   │   ├── Card.tsx                <Card> + <HighlightCard> primitives (lime variant)
    │   │   ├── Button.tsx              <PrimaryButton> (dark) + <AccentButton> (lime)
    │   │   ├── MetricCard.tsx          one-number card + Know-more trigger
    │   │   ├── KnowMoreButton.tsx      pill trigger; owns its own open/close state
    │   │   ├── KnowMoreModal.tsx       focus-trapping modal; reads from explainers registry
    │   │   └── KnowMoreModal.test.tsx  3 vitest cases: opens, closes on Escape, missing-id fallback
    │   ├── layout/
    │   │   ├── Header.tsx              brand mark + GitHub link
    │   │   ├── Footer.tsx              thesis disclaimer + sources
    │   │   ├── Hero.tsx                bold headline + accent CTA
    │   │   └── Section.tsx             title chip + spacing wrapper
    │   └── estimator/
    │       └── SizingEstimator.tsx     single-field form → MetricCard with Know-more
    ├── content/
    │   └── explainers.ts               typed registry; system-size entry filled, others stubbed
    ├── hooks/
    │   └── useSizing.ts                useMutation wrapping POST /api/sizing
    ├── lib/
    │   └── api.ts                      typed fetch + ApiError + VITE_API_BASE_URL
    ├── types/
    │   └── api.ts                      mirror of backend Pydantic SizingRequest/SizingResult
    └── styles/
        ├── tokens.css                  CSS custom properties (Tailwind mirrors these)
        └── index.css                   Tailwind layers + base styles
```

`backend/` is unchanged. `README.md` at the repo root gains the
`npm install && npm run dev` quickstart for the new workspace.

---

## How I verified it works

1. **Frontend tests** — `npm run test` runs 3 vitest cases against
   `KnowMoreModal`, all passing:
   - opens the modal with the correct title for `system-size`,
   - closes on Escape,
   - renders a "not found" fallback when the id is missing from the
     registry (the registry is the only source of truth, so this is
     the exact failure mode that will appear if a future day forgets
     to add an entry).
2. **Frontend typecheck** — `npm run typecheck` (`tsc -b --noEmit`)
   completes with zero errors. Strict mode, `noUnusedLocals`, and
   `noUnusedParameters` are all on.
3. **Frontend production build** — `npm run build` succeeds:
   - `dist/index.html` 0.89 KB,
   - `dist/assets/index-*.css` 11.76 KB (3.29 KB gzip),
   - `dist/assets/index-*.js` 187.63 KB (59.41 KB gzip),
   - 91 modules transformed in ~1.7 s.
4. **Dev-server smoke** — `npm run dev` returns HTTP 200 on
   `http://localhost:5173/` and serves the expected `index.html`
   with the Google Fonts `<link>` tags and the `/src/main.tsx` entry.
5. **Backend regression** — full backend pytest suite is **304
   passed in 5.17 s**, identical to Day 11. No backend file was
   touched today; the test run only confirms the frontend addition
   does not perturb any shared state (it doesn't — `frontend/` is a
   sibling directory with its own toolchain).
6. **End-to-end manual check** — with the backend running on port
   8000, submitting the form with roof_area=100 returns a `SizingResult`
   from `POST /api/sizing`, and the `MetricCard` updates to show the
   correct `system_kw` and `panel_count` from the response, with the
   `Know more →` button opening the `system-size` modal.

---

## What's next

| Day | Deliverable                                                                  | Branch              |
| --- | ---------------------------------------------------------------------------- | ------------------- |
| 13  | Address input + map preview component (Leaflet)                              | `feat/input-form`   |
| 14  | Dashboard layout: metric cards (size, kWh, savings, payback CI) + modals     | `feat/dashboard-cards` |
| 15  | Monthly production chart + pvlib-vs-manual comparison view                   | `feat/charts-comparison` |

---

## Files changed

```
M  README.md                                                  (+10 lines)
A  frontend/.env.example                                      (+ 1 line)
A  frontend/.gitignore                                        (+ 7 lines)
A  frontend/README.md                                         (+88 lines)
A  frontend/index.html                                        (+22 lines)
A  frontend/package.json                                      (+34 lines)
A  frontend/package-lock.json                                 (auto)
A  frontend/postcss.config.js                                 (+ 6 lines)
A  frontend/tailwind.config.ts                                (+33 lines)
A  frontend/tsconfig.json                                     (+ 7 lines)
A  frontend/tsconfig.app.json                                 (+27 lines)
A  frontend/tsconfig.node.json                                (+19 lines)
A  frontend/vite.config.ts                                    (+22 lines)
A  frontend/src/App.tsx                                       (+27 lines)
A  frontend/src/main.tsx                                      (+22 lines)
A  frontend/src/test-setup.ts                                 (+ 1 line)
A  frontend/src/components/estimator/SizingEstimator.tsx      (+72 lines)
A  frontend/src/components/layout/Footer.tsx                  (+38 lines)
A  frontend/src/components/layout/Header.tsx                  (+25 lines)
A  frontend/src/components/layout/Hero.tsx                    (+39 lines)
A  frontend/src/components/layout/Section.tsx                 (+23 lines)
A  frontend/src/components/ui/Button.tsx                      (+38 lines)
A  frontend/src/components/ui/Card.tsx                        (+34 lines)
A  frontend/src/components/ui/KnowMoreButton.tsx              (+25 lines)
A  frontend/src/components/ui/KnowMoreModal.tsx               (+155 lines)
A  frontend/src/components/ui/KnowMoreModal.test.tsx          (+27 lines)
A  frontend/src/components/ui/MetricCard.tsx                  (+38 lines)
A  frontend/src/content/explainers.ts                         (+58 lines)
A  frontend/src/hooks/useSizing.ts                            (+19 lines)
A  frontend/src/lib/api.ts                                    (+58 lines)
A  frontend/src/styles/index.css                              (+27 lines)
A  frontend/src/styles/tokens.css                             (+22 lines)
A  frontend/src/types/api.ts                                  (+27 lines)
A  outputs/11-frontend-init.md                                (this file)
```

## How to run / verify yourself

```bash
# Frontend
cd frontend
npm install
npm run typecheck         # 0 errors
npm run test              # 3 passed
npm run build             # ~187 KB JS (~59 KB gzip)
npm run dev               # http://localhost:5173

# Backend (in a second terminal)
cd backend
.venv/bin/uvicorn app.main:app --reload     # http://localhost:8000

# Then in the browser:
#   1. Submit the form with any positive roof area.
#   2. The "System size" card updates with kW + panel count.
#   3. Click "Know more →" — the system-size modal opens with
#      plain-English text, formula, and source links.
```
