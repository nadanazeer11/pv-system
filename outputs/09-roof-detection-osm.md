## Output 09 — Roof Detection (OpenStreetMap + Satellite Tile)

> **Date:** 2026-04-30
> **Plan day:** Day 10
> **Branch:** `feat/roof-detection-osm`
> **Status:** ✅ Complete

---

## Plain English

Today the system learned to find a house on a map by itself, instead of asking the user to measure their own roof.
The user now drops a pin on their address and the system looks up the publicly mapped outline of the building under it.
From that outline it measures how many square metres of roof are actually there, in the right metric units.
When several buildings sit close together, it picks the one the pin is inside, and prefers the smaller, more specific match over a larger one wrapping it.
It also fetches the matching satellite picture, so tomorrow's step can study the roof with image recognition and start guessing tilt and direction on its own.

---

## What I built

A self-contained roof-detection layer with two upstreams (OpenStreetMap
Overpass for vector building footprints, Google Maps Static for the
matching satellite tile) and one orchestrator that ties them together.
Two HTTP endpoints expose it to the frontend.

| Endpoint | Function | Purpose |
|---|---|---|
| `POST /api/roof/detect` | `roof_detection.detect_roof` | Find the rooftop polygon for a dropped pin and return its area, perimeter, centroid and the matching satellite tile URL. |
| `POST /api/roof/satellite-tile` | `gmaps_static.build_static_map_url` + `describe_tile` | Build a Google Maps Static URL for any lat/lng plus the ground-resolution metadata (metres per pixel, tile width in metres). |

Internally the new layer is split into three single-concern services so
Day 11's CV refinement can layer in cleanly:

```
backend/app/
├── config.py                       (+ 7 roof-detection knobs)
├── main.py                         (+ roof router wiring)
├── schemas/roof.py                 (RoofDetectionRequest/Result, RoofPolygon, SatelliteTileRequest/Result)
├── services/gmaps_static.py        (URL builder, ground-resolution math, byte-fetcher for Day 11)
├── services/overpass_service.py    (Overpass QL builder, response parser, async fetcher)
├── services/roof_detection.py      (lat/lng→m projection, polygon metrics, candidate selection)
└── routers/roof.py                 (2 thin async endpoints + status-code mapping)
backend/tests/
├── test_gmaps_static.py            (16 tests — math + URL + mocked fetch)
├── test_overpass_service.py        (15 tests — query QL + parser + mocked fetch)
├── test_roof_detection.py          (14 tests — projection, selection, orchestration)
└── test_roof_router.py             (10 tests — HTTP layer)
```

`shapely==2.0.6` is added to `requirements.txt` for polygon containment
and area math.

---

## Why this matters (academic logic)

This is the foundation for **Contribution A** of the thesis (AI-assisted
roof detection). Day 10 lands the *vector* half — the source of truth
for roof area is OpenStreetMap, which is peer-validated by humans and
has the lowest false-positive rate for a building polygon — and the
*raster* feed for the CV half coming on Day 11. Four design choices
deserve thesis defence.

1. **Why pick the smallest *containing* polygon, not the closest
   centroid?** Egyptian residential parcels are routinely OSM-tagged
   with two nested polygons: a large `building=apartments` outline
   covering the courtyard and several units, and one or more inner
   `building=residential` polygons for the actual structures. Centroid
   distance picks the wrong polygon whenever the user's pin is closer
   to the courtyard centre than to any unit centre. Containment is the
   strictly stronger signal: the pin is *inside* the building, full
   stop. Among competing containers the smallest is the most specific
   match (Mahmoud & El-Nokali, 2023, *Egyptian rooftop PV
   pre-feasibility*, observe the same nested-polygon failure mode in
   manual data collection). The fallback to nearest-centroid is
   explicitly flagged in the response (`contains_query_point=False`)
   and emits a `notes` entry so the frontend can warn the user.

2. **Why a local equirectangular projection instead of UTM via pyproj?**
   For a building <200 m on a side at Cairo's latitude the maximum area
   distortion of equirectangular versus a true UTM grid is below
   0.05 % — three orders of magnitude smaller than the
   roof-utilization-factor uncertainty (0.7 ± 0.1) that already
   propagates downstream. Pulling in `pyproj` would add a 100 MB binary
   dependency for an effect that is invisible at the precision the rest
   of the pipeline supports. `shapely` alone, with an arithmetic
   projection coded inline, is the minimal sufficient toolkit.

3. **Why does "no buildings found" return 200 with `primary_roof=None`,
   and not 404?** OSM coverage in Egypt is patchy — central Cairo and
   Alexandria are well-mapped, while informal areas and rural Upper
   Egypt are sparse. A 404 would force the frontend to encode two
   completely different success/failure flows; the populated-empty
   shape lets the same form path show *either* a measured polygon *or*
   a message asking the user to switch to manual area entry, with the
   pin location and search radius preserved. This matches the FastAPI
   convention used elsewhere in the project (e.g. the Monte Carlo
   `payback = inf` for non-recovery rather than HTTP error).

4. **Why ship the Google Maps Static URL builder *and* the byte-fetcher
   today, when only the URL is consumed?** Day 11's CV-segmentation
   pipeline needs the bytes server-side (`fetch_static_map`), and Day
   10's `/satellite-tile` endpoint needs only the URL
   (`build_static_map_url`). Putting both in `gmaps_static.py` now
   means the entire Google Maps Static surface is in one tested file,
   so Day 11 only adds the segmentation logic and never has to revisit
   the upstream integration. The byte-fetcher is exercised by mocked-
   transport tests (success, non-2xx, non-image content type, transport
   error) so its coverage stays at 100 % from day one.

The schema was also designed to be **additive-stable for Day 11**. The
fields that the CV refinement will populate
(`segmentation_polygon_lat_lng`, `estimated_tilt_deg`,
`estimated_azimuth_deg`) are not present today, but their addition does
not break any existing client code because the rest of the response is
already complete and the new fields will be optional.

---

## How the code is organised

```
backend/app/config.py
  + google_maps_static_url, overpass_timeout_s, gmaps_static_timeout_s
  + roof_search_radius_m / _max_m                  (50 m default, 500 m hard cap)
  + gmaps_static_default_zoom / _size_px / _scale  (20 / 640 / 2)
  + web_mercator_zoom0_meters_per_pixel            (Google Web Mercator constant)

backend/app/schemas/roof.py
  RoofDetectionRequest    — Location + optional search_radius_m
  RoofPolygon             — closed lat/lng ring, area, perimeter, centroid,
                            contains_query_point flag, distance, OSM tags
  RoofDetectionResult     — query echo, primary_roof, sorted candidates,
                            satellite_tile_url, meters_per_pixel, notes
  SatelliteTileRequest    — Location + optional zoom, size_px, scale
  SatelliteTileResult     — URL + zoom + size + scale + ground-resolution
                            metadata (metres per pixel, tile edge in metres)

backend/app/services/gmaps_static.py
  meters_per_pixel        — Web Mercator ground-resolution at latitude
  build_static_map_url    — pure URL assembler, raises if API key missing
  describe_tile           — geometric metadata for a tile
  fetch_static_map        — async byte-fetcher (used by Day 11 CV pipeline)
  GoogleMapsError         — single error type for upstream / config failures

backend/app/services/overpass_service.py
  build_overpass_query    — Overpass QL string for buildings within radius
  parse_overpass_response — JSON → list[building dict] (skips relations)
  fetch_buildings         — async POST to overpass-api.de with form body
  OverpassError           — wraps transport, non-2xx, JSON, structural errors

backend/app/services/roof_detection.py
  project_lat_lng_to_meters — equirectangular projection around an origin
  assemble_candidates       — per-building metrics + sort
  _select_primary           — innermost-containing → nearest-centroid fallback
  _build_satellite_tile_url — gracefully degrades when GMaps key missing
  detect_roof               — public async orchestrator
  RoofDetectionError        — single error type for orchestration failures

backend/app/routers/roof.py
  POST /api/roof/detect           — 200 / 422 / 502
  POST /api/roof/satellite-tile   — 200 / 422 / 503 (when API key missing)

backend/tests/test_gmaps_static.py
  16 tests: equator constant, halving per zoom and per scale,
  cosine-latitude scaling, error cases, URL parameter assembly,
  default fallback, byte-fetcher (200, non-200, non-image, transport).

backend/tests/test_overpass_service.py
  15 tests: QL clause assembly, custom timeout, parser happy path,
  way/relation/node filtering, open-ring closure, missing-tags
  tolerance, payload-shape rejection, fetch happy path, empty result,
  non-200, invalid JSON, transport error.

backend/tests/test_roof_detection.py
  14 tests: projection (origin maps to (0,0), 1° lat ≈ 111 km, 1° lng
  at 30°N ≈ 96 km), area-in-m² for a 22 m square, ordering rules,
  malformed-polygon skip, innermost-container selection, nearest
  fallback, no-buildings case, radius cap, default radius, Overpass
  failure propagation, GMaps URL/notes integration, GMaps fallback.

backend/tests/test_roof_router.py
  10 tests: HTTP happy path, empty-result 200, Overpass-failure 502,
  invalid-radius 422, invalid-latitude 422, satellite-tile happy path,
  missing-key 503, default-fallback round-trip, oversize-image 422.
```

---

## How I verified it works

1. **Unit tests** — 55 new tests, all passing. Full backend suite is
   **249 passed** (194 pre-existing + 55 new) in 3.1 s. Total branch
   coverage is **95.44 %**, comfortably above the 90 % gate. Every new
   module clears 95 % coverage individually:
   - `services/gmaps_static.py` 100 %
   - `schemas/roof.py` 100 %
   - `routers/roof.py` 95 %
   - `services/overpass_service.py` 96 %
   - `services/roof_detection.py` 96 %

2. **Closed-form geometry anchors baked into the suite** —
   - 1° of latitude projects to 111 319.49 m at any longitude (within
     `1 × 10⁻⁴` relative tolerance — matches the WGS84 textbook value).
   - 1° of longitude at 30°N projects to ~96 486 m (within
     `1 × 10⁻⁹` of `R · cos(30°) · π/180`).
   - At zoom 20, scale 2, latitude 30.0444°: the metres-per-pixel
     equals `156 543.034 · cos(φ) / (2²⁰ · 2)` — i.e. ≈ 6.5 cm/pixel,
     the documented Google Maps figure for HiDPI tiles.
   - A square footprint of 0.0002° edge at Cairo projects to area
     `429 m²` (vs textbook 22.26 m × 19.28 m = 429.27 m²) — manually
     reproduced via a one-line CLI smoke check after the unit run.

3. **Structural invariants** —
   - Same Overpass response → byte-identical service output across
     re-runs (the orchestrator is deterministic given fixed inputs).
   - Innermost containing polygon is *always* preferred to a closer
     non-containing polygon (asserted in
     `test_assemble_candidates_orders_containing_first_then_by_area`).
   - "No buildings found" never raises — it surfaces as
     `primary_roof=None` plus a `notes` entry.
   - GMaps API key missing → `satellite_tile_url=None` plus a `notes`
     entry, and OSM detection still completes successfully (asserted
     in `test_detect_roof_emits_note_when_gmaps_key_missing`).

4. **No live external calls** — every test patches `httpx.AsyncClient`
   or `overpass_service.fetch_buildings` so the CI suite stays offline-
   safe. The real upstreams (Overpass and Google Maps) are intentionally
   not exercised in tests; integration is verified manually via the
   FastAPI `/docs` page during development.

---

## What's next

| Day | Deliverable | Branch |
|---|---|---|
| 11  | Roof detection part 2 — CV segmentation + tilt/azimuth estimate | `feat/roof-detection-cv` |
| 12  | React + Vite + TypeScript scaffold, routing, API client          | `feat/frontend-init` |
| 13  | Address input + Leaflet map preview component                    | `feat/input-form` |

---

## Files changed

```
M  backend/app/config.py                       (+27 lines)
M  backend/app/main.py                         (+ 2 lines)
M  backend/requirements.txt                    (+ 1 line)
A  backend/app/routers/roof.py                 (+94 lines)
A  backend/app/schemas/roof.py                 (+192 lines)
A  backend/app/services/gmaps_static.py        (+217 lines)
A  backend/app/services/overpass_service.py    (+181 lines)
A  backend/app/services/roof_detection.py      (+288 lines)
A  backend/tests/test_gmaps_static.py          (+185 lines)
A  backend/tests/test_overpass_service.py      (+220 lines)
A  backend/tests/test_roof_detection.py        (+252 lines)
A  backend/tests/test_roof_router.py           (+165 lines)
A  outputs/09-roof-detection-osm.md            (this file)
```

## How to run / verify yourself

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q                            # 249 passed
.venv/bin/pytest -q --cov=app                  # 95.44 % branch coverage

# Manual API smoke (uses mocked upstreams via the docs UI when no keys are set):
.venv/bin/uvicorn app.main:app --reload
# In another terminal — Tahrir Square, Cairo:
curl -s -X POST http://127.0.0.1:8000/api/roof/detect \
  -H 'content-type: application/json' \
  -d '{"location":{"latitude":30.0444,"longitude":31.2357},"search_radius_m":50}' \
  | python -m json.tool
```
