# PV Estimator — Frontend

React 18 + Vite + TypeScript + TailwindCSS scaffold for the rooftop solar
estimator. The visual language follows the **Positivus** mood (bold,
high-contrast, lime accent on white) defined in
[`PLAN.md`](../PLAN.md#-frontend-design-brief-read-before-day-12).

## Status — Day 12 (scaffold)

- ✅ Vite + React 18 + TypeScript
- ✅ TailwindCSS configured with the design tokens from the brief
- ✅ Google Fonts (Space Grotesk + Inter) loaded via `<link>`
- ✅ Header, Footer, Hero, Section layout components
- ✅ Core UI primitives — `<Card>`, `<HighlightCard>`, `<PrimaryButton>`, `<AccentButton>`, `<MetricCard>`
- ✅ `<KnowMoreButton>` + `<KnowMoreModal>` reading from a typed
  registry (`src/content/explainers.ts`) — only the `system-size`
  entry is filled in today; the remaining ten ids land on Days 13–18.
- ✅ TanStack Query provider in `main.tsx`
- ✅ Typed `lib/api.ts` fetch client
- ✅ `useSizing()` hook calling `POST /api/sizing` end-to-end
- ✅ One working form field (roof area) → one MetricCard with a
  Know-more trigger that opens the system-size modal.

Days 13–17 layer on top of this scaffold without changing it.

## Running it

The backend must be running on `http://localhost:8000` (or the URL
configured by `VITE_API_BASE_URL`) before the form can be submitted.

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

In another terminal:

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload
```

## Other commands

```bash
npm run build        # type-check + production bundle
npm run typecheck    # type-check only
npm run test         # vitest run (KnowMoreModal pattern test)
```

## Configuration

| Variable             | Default                  | Purpose                       |
| -------------------- | ------------------------ | ----------------------------- |
| `VITE_API_BASE_URL`  | `http://localhost:8000`  | Where the backend is hosted.  |

Copy `.env.example` to `.env.local` to override locally. Vite reloads
automatically.

## Folder layout

```
frontend/
├── index.html
├── package.json
├── tailwind.config.ts
├── vite.config.ts
└── src/
    ├── main.tsx                     QueryClientProvider + entry
    ├── App.tsx                      Header + Hero + Estimator + Footer
    ├── components/
    │   ├── ui/                      Card, HighlightCard, Button, MetricCard,
    │   │                            KnowMoreButton, KnowMoreModal (+ test)
    │   ├── layout/                  Header, Footer, Hero, Section
    │   ├── estimator/               SizingEstimator (Day 13 expands)
    │   ├── dashboard/               (Day 14)
    │   └── charts/                  (Days 15–17)
    ├── content/
    │   └── explainers.ts            Know-more registry — single source of truth
    ├── hooks/
    │   └── useSizing.ts             POST /api/sizing
    ├── lib/
    │   └── api.ts                   typed fetch + ApiError
    ├── types/
    │   └── api.ts                   mirror of backend Pydantic schemas
    └── styles/
        ├── tokens.css               CSS custom properties (Tailwind mirrors these)
        └── index.css                Tailwind layers + base styles
```

## Adding a new "Know more" explainer

1. Append an entry to `src/content/explainers.ts` keyed by the new id.
2. Reference it from any surface: `<KnowMoreButton id="..." />` or
   `<MetricCard knowMoreId="..." ... />`.

That's the whole pattern. No component changes required.
