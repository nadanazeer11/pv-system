"""Roof detection endpoints (Days 10–11).

Three endpoints sit behind ``/api/roof``:

* ``POST /api/roof/detect`` — vector-side detection only (OpenStreetMap
  Overpass + selection logic). Day 10.
* ``POST /api/roof/satellite-tile`` — helper for the frontend to obtain
  a Google Maps Static URL with the ground-resolution metadata needed
  to draw the OSM polygon over the imagery. Day 10.
* ``POST /api/roof/analyze`` — full pipeline: detect + satellite-tile
  fetch + CV polygon refinement + tilt and azimuth estimation. Day 11.

The split is deliberate: ``/detect`` is cheap (one Overpass call), while
``/analyze`` issues one Overpass call *and* one Google Maps Static
download, then runs CPU-bound CV. Frontends that only need the polygon
(e.g. a quick-preview map) use ``/detect``; the full estimator pipeline
uses ``/analyze``.
"""
from fastapi import APIRouter, HTTPException

from app.schemas.roof import (
    RoofAnalysisRequest,
    RoofDetectionRequest,
    RoofDetectionResult,
    SatelliteTileRequest,
    SatelliteTileResult,
)
from app.services import gmaps_static, roof_detection

router = APIRouter(prefix="/api/roof", tags=["roof"])


@router.post("/detect", response_model=RoofDetectionResult)
async def detect(request: RoofDetectionRequest) -> RoofDetectionResult:
    """Run vector-side roof detection for a geographic pin.

    The endpoint always returns 200 with a populated payload when the
    upstream Overpass call succeeds — the absence of buildings is
    surfaced through ``primary_roof = None`` and the ``notes`` field,
    not as an error. This keeps the frontend's UX flow uniform.

    Status codes
    ------------
    * 200 — successful detection (including the empty-result case).
    * 422 — invalid input (e.g. non-positive radius), surfaced by the
      orchestrator before any upstream call.
    * 502 — the OSM Overpass upstream failed.
    """
    try:
        return await roof_detection.detect_roof(
            request.location,
            search_radius_m=request.search_radius_m,
        )
    except roof_detection.RoofDetectionError as exc:
        message = str(exc)
        if "OSM Overpass fetch failed" in message:
            raise HTTPException(status_code=502, detail=message) from exc
        raise HTTPException(status_code=422, detail=message) from exc


@router.post("/satellite-tile", response_model=SatelliteTileResult)
async def satellite_tile(request: SatelliteTileRequest) -> SatelliteTileResult:
    """Build the Google Maps Static URL + ground-resolution for a tile.

    The endpoint does **not** fetch the image itself — it only assembles
    the URL and the geometric metadata. Returning the URL keeps the
    payload tiny and lets the browser load the image directly from
    Google's CDN.

    Status codes
    ------------
    * 200 — URL successfully built.
    * 503 — Google Maps API key not configured server-side.
    """
    try:
        url = gmaps_static.build_static_map_url(
            request.location.latitude,
            request.location.longitude,
            zoom=request.zoom,
            size_px=request.size_px,
            scale=request.scale,
        )
    except gmaps_static.GoogleMapsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    metadata = gmaps_static.describe_tile(
        request.location.latitude,
        zoom=request.zoom,
        size_px=request.size_px,
        scale=request.scale,
    )
    return SatelliteTileResult(
        url=url,
        zoom=int(metadata["zoom"]),
        size_px=int(metadata["size_px"]),
        scale=int(metadata["scale"]),
        meters_per_pixel=float(metadata["meters_per_pixel"]),
        tile_width_m=float(metadata["tile_width_m"]),
        tile_height_m=float(metadata["tile_height_m"]),
    )


@router.post("/analyze", response_model=RoofDetectionResult)
async def analyze(request: RoofAnalysisRequest) -> RoofDetectionResult:
    """Run the full Day-11 pipeline (detect + CV refinement + tilt/azimuth).

    The endpoint *never* surfaces a CV failure as an HTTP error: a
    transport-level Google Maps failure, a non-image response, or a
    decoding failure all degrade gracefully to "OSM-only" with a
    populated note. This matches the conservative philosophy used by
    ``/detect`` (an empty Overpass result also returns 200) and lets
    the frontend show one rendering path for both states.

    Status codes
    ------------
    * 200 — analysis completed (with or without CV evidence).
    * 422 — invalid input (e.g. non-positive radius).
    * 502 — the OSM Overpass upstream failed (the same condition that
      makes ``/detect`` return 502, since without a vector polygon the
      CV pass has nothing to refine).
    """
    try:
        return await roof_detection.analyze_roof(
            request.location,
            search_radius_m=request.search_radius_m,
            enable_cv=request.enable_cv,
        )
    except roof_detection.RoofDetectionError as exc:
        message = str(exc)
        if "OSM Overpass fetch failed" in message:
            raise HTTPException(status_code=502, detail=message) from exc
        raise HTTPException(status_code=422, detail=message) from exc
