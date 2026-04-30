"""Roof detection endpoints (Day 10 — OSM-Overpass + Google Maps Static).

Two endpoints sit behind ``/api/roof``:

* ``POST /api/roof/detect`` — vector-side detection (OpenStreetMap
  Overpass building footprints + selection logic).
* ``POST /api/roof/satellite-tile`` — helper for the frontend to fetch
  a Google Maps Static URL with the ground-resolution metadata needed
  to draw the OSM polygon over the imagery.

Day 11's CV-segmentation endpoint will compose these two — that's why
they are exposed as separate routes today rather than buried inside one.
"""
from fastapi import APIRouter, HTTPException

from app.schemas.roof import (
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
