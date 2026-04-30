# Output 12 — Address Input + Map Preview (Leaflet)

> **Date:** 2026-04-30
> **Plan day:** Day 13
> **Branch:** `feat/input-form`
> **Status:** ✅ Complete

---

## Plain English

Yesterday the page asked for a number — how many square metres of roof you have — but had no idea where the roof actually was.
Today it asks for an address instead, then shows you a real map with a pin sitting on top of your house and the building's outline traced over it.
If the pin lands in the wrong spot you can simply click anywhere else on the map and the pin moves there, and the system looks up that new spot's building outline straight away.
A small "Know more" tag next to the address box opens a friendly pop-up explaining, in plain language, where the address lookup and the building outline come from and what to do if the outline does not match your roof.
This means the next steps in the project — measuring how much sun the roof gets, sizing the panels, working out the savings — can all start from a real place on a map instead of a number the user guessed.

---

## What I built

A new `LocationPicker` section that sits above the existing sizing form
inside the `Estimator` `Section`. It composes three smaller pieces — an
`AddressInput` that geocodes free text via OpenStreetMap Nominatim, a
`RoofMapPreview` that renders a Leaflet map with a draggable pin and an
overlaid building polygon, and a `useRoofDetect` mutation that calls the
existing backend `POST /api/roof/detect` endpoint to retrieve the OSM
footprint for whichever pin is currently selected.

```
type address  ──useGeocode──▶  Nominatim  ──hits──▶  list of buttons
click hit / click map  ───────▶  setLocation()  ───────▶  RoofMapPreview pin
                                       │
                                       └──▶ useRoofDetect()  ──POST /api/roof/detect──▶
                                                                       primary_roof  ──▶  <Polygon> on map + status text
```

The `KnowMoreButton id="roof-detection"` next to the section heading
opens a registry-driven explainer that describes the geocoder, the
footprint source, and the user's escape hatch (click the map to
override). One of the eleven required explainers from the Frontend
Design Brief is now wired; the remaining ten remain stubbed for Days
14–18.

---

## Why this matters (academic logic)

The thesis's headline contribution **A — AI-assisted roof detection**
is moot without an interface that lets a non-expert pick *where* the
roof is in the first place. Day 13's choices below are the ones the
methodology chapter will cite when defending why this surface is
trustworthy in spite of being simple.

1. **Why geocode in the browser via Nominatim, not behind our own
   server?** Routing forward-geocoding through FastAPI would add a hop
   without adding value: the OSMF Nominatim Usage Policy explicitly
   permits direct browser calls when a meaningful Referer is set
   (which the browser does automatically), and TanStack Query's
   user-triggered mutation pattern already enforces the policy's
   1 req/s ceiling. Centralising the call server-side would also
   require us to either share one User-Agent across all users (not
   permitted) or proxy every request individually (no caching benefit).
   For production deployment a dedicated server-side geocoder remains
   the correct path; for a thesis prototype, direct calls keep the
   demo runnable from a single laptop.
2. **Why use the cheap `/api/roof/detect` here, not `/api/roof/analyze`?**
   The `/analyze` endpoint runs a CV refinement pass and tilt/azimuth
   estimation that costs one Google Maps Static fetch and a CPU-bound
   image step *per* pin drop. The Day-13 surface has to be responsive
   to every map click (the user fine-tunes the pin manually because
   geocoders point at street centroids, not roofs), so we use the
   vector-only endpoint and reserve `/analyze` for the explicit
   "Estimate" trigger that lands in Day 14's dashboard. This split
   was already encoded in the backend by the Day 10–11 routers; today
   simply consumes it.
3. **Why does the parent `LocationPicker` own the location state and
   not `RoofMapPreview`?** The Frontend Brief commits to lifted state
   ("No global state library on Day 12. Lift state, pass props.") and
   to swappable map renderers (the brief is Leaflet-specific, but the
   research output may demand MapLibre or a satellite-tile layer in
   Week 3). A presentational `RoofMapPreview` whose entire input is
   `{location, roof, onLocationChange}` lets us replace Leaflet
   without touching the data path or the test suite. The mock used in
   `LocationPicker.test.tsx` is *itself* such a swap, demonstrating
   the seam works.
4. **Why pre-fire a roof-detect on every pin change rather than wait
   for an "Estimate" button?** Two reasons. First, the polygon overlay
   is the user's primary feedback loop ("did the system find *my*
   roof?"); deferring it would force a second-click discovery flow
   that the brief explicitly rules out ("Every number has a tooltip
   OR a 'Know more' trigger explaining where it came from"). Second,
   the mutation is idempotent and the call is cheap (one Overpass
   query, ~150 ms median); rate-limit guards still come from the
   user-driven click cadence, not the code.
5. **Why no debounce on the map-click → roof-detect path?** A
   pin-drop is a single explicit user action — the user does not
   "scrub" the map. A debounce would only hurt the perceived latency.
   Fast typing in the *address* field is already debounced by the
   "Find on map" button, so no rapid-fire events ever reach the
   detect call.
6. **Why hand-write the Nominatim client (`lib/nominatim.ts`) rather
   than pull a wrapper?** The dominant npm wrappers
   (`nominatim-browser`, `node-nominatim`) ship CommonJS-only builds
   that interact poorly with Vite's ESM-first module graph and bring
   in 30+ kB of polyfills the browser doesn't need. The native
   `fetch` call here is 30 lines, fully typed, and lets the file
   double as the policy-compliance documentation surface (the doc
   block enumerates each requirement and where it's satisfied).

---

## How the code is organised

```
frontend/
├── package.json                                     +leaflet ^1.9.4, react-leaflet ^4.2.1, @types/leaflet ^1.9.21
├── src/
│   ├── App.tsx                                      Adds <LocationPicker /> above <SizingEstimator /> inside Estimator section
│   ├── content/
│   │   └── explainers.ts                            +`roof-detection` entry (geocoder + footprint sources + escape hatch)
│   ├── types/
│   │   └── api.ts                                   +Location, +RoofDetectionRequest, +RoofPolygon, +RoofDetectionResult
│   ├── lib/
│   │   └── nominatim.ts                             Browser-side OSM Nominatim client + GeocodeError + attribution string
│   ├── hooks/
│   │   ├── useGeocode.ts                            useMutation wrapping searchAddress() — user-triggered, cancellable
│   │   └── useRoofDetect.ts                         useMutation wrapping POST /api/roof/detect
│   └── components/
│       └── estimator/
│           ├── AddressInput.tsx                     Search field + result list; emits GeocodeHit on click
│           ├── AddressInput.test.tsx                4 vitest cases — search, empty, error, whitespace guard
│           ├── RoofMapPreview.tsx                   Leaflet container + tile layer + marker + polygon + click handler
│           ├── LocationPicker.tsx                   Owns selected Location, wires AddressInput ↔ RoofMapPreview ↔ useRoofDetect
│           └── LocationPicker.test.tsx              3 vitest cases — geocode→select→detect, map-click→detect, error path
```

`backend/` is untouched. The Day-12 components (`SizingEstimator`,
`MetricCard`, `KnowMoreModal`, layout primitives) are imported as-is.

---

## How I verified it works

1. **Frontend tests** — `npm run test` runs **10 vitest cases**, all
   passing across 3 test files (3 modal + 4 AddressInput + 3
   LocationPicker). The new tests cover:
   - geocoder happy path → hit click → `onSelect` payload,
   - empty-result message,
   - upstream error → inline alert,
   - whitespace-only query is a no-op (no fetch),
   - end-to-end `LocationPicker` flow: hit selection drives the
     summary card *and* fires `POST /api/roof/detect` with the
     selected lat/lng,
   - direct map-click also fires `/api/roof/detect` and surfaces the
     "no buildings found" copy when the response has no primary roof,
   - 502 from the backend renders an inline alert and keeps the
     selected location in place.
2. **Frontend typecheck** — `npm run typecheck` (`tsc -b --noEmit`)
   completes with **zero errors** under strict mode +
   `noUnusedLocals` + `noUnusedParameters`.
3. **Frontend production build** — `npm run build` succeeds:
   - `dist/index.html` 0.89 KB,
   - `dist/assets/index-*.css` 28.48 KB (9.81 KB gzip),
   - `dist/assets/index-*.js` 357.53 KB (113.35 KB gzip),
   - 143 modules transformed in ~2.0 s.
   The +170 KB JS / +17 KB CSS over Day 12 is the Leaflet runtime
   plus react-leaflet bindings — within the brief's "under 200 KB
   gzipped" budget.
4. **Backend regression** — `cd backend && python3 -m venv .venv &&
   .venv/bin/pip install -r requirements.txt && .venv/bin/pytest -q`
   reports **304 passed in 3.57 s**, identical to Day 12. No backend
   file was touched today.
5. **Manual end-to-end check** — with the backend running on
   `http://localhost:8000` and the frontend on
   `http://localhost:5173/`, typing "Tahrir Square, Cairo" + clicking
   "Find on map" returns one Nominatim hit; clicking the hit moves
   the Leaflet pin to (30.04°, 31.24°) and overlays the building
   polygon returned by `/api/roof/detect`; clicking elsewhere on the
   map drops the pin there and re-issues the detect call; clicking
   "Know more →" opens the `roof-detection` explainer with the
   plain-English copy, the math block, the Egypt-tuned defaults, and
   the OSM source links.

---

## What's next

| Day | Deliverable                                                                  | Branch                  |
| --- | ---------------------------------------------------------------------------- | ----------------------- |
| 14  | Dashboard layout: metric cards (size, kWh, savings, payback CI) + "Know more" modals | `feat/dashboard-cards`  |
| 15  | Monthly production chart + pvlib-vs-manual comparison view                   | `feat/charts-comparison`|
| 16  | Monte Carlo visualisation (histogram + fan chart for cumulative ROI)         | `feat/charts-monte-carlo`|

---

## Files changed

```
M  frontend/package.json                                       (+ 3 lines)
M  frontend/package-lock.json                                  (auto)
M  frontend/src/App.tsx                                        (+12 / -2 lines)
M  frontend/src/content/explainers.ts                          (+25 lines)
M  frontend/src/types/api.ts                                   (+44 / -2 lines)
A  frontend/src/lib/nominatim.ts                               (+134 lines)
A  frontend/src/hooks/useGeocode.ts                            (+24 lines)
A  frontend/src/hooks/useRoofDetect.ts                         (+23 lines)
A  frontend/src/components/estimator/AddressInput.tsx          (+124 lines)
A  frontend/src/components/estimator/AddressInput.test.tsx     (+109 lines)
A  frontend/src/components/estimator/RoofMapPreview.tsx        (+172 lines)
A  frontend/src/components/estimator/LocationPicker.tsx        (+164 lines)
A  frontend/src/components/estimator/LocationPicker.test.tsx   (+183 lines)
A  outputs/12-input-form.md                                    (this file)
```

## How to run / verify yourself

```bash
# Frontend
cd frontend
npm install
npm run typecheck         # 0 errors
npm run test              # 10 passed (3 + 4 + 3)
npm run build             # ~358 KB JS (~113 KB gzip)
npm run dev               # http://localhost:5173

# Backend (in a second terminal)
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload     # http://localhost:8000

# Then in the browser:
#   1. Type "Tahrir Square, Cairo" + "Find on map".
#   2. Click the returned hit. The Leaflet pin re-centres on the
#      result and the OSM building polygon appears as a lime overlay.
#   3. Click anywhere on the map. The pin moves there and the
#      polygon refreshes for the new location.
#   4. Click "Know more →". The roof-detection explainer opens
#      with the plain-English text, formula, and source links.
```
