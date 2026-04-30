"""OpenStreetMap Overpass API integration.

Queries the OSM Overpass instance for *building* footprints near a
geographic point and returns them as plain Python dictionaries ready to
be projected and area-computed by the roof-detection orchestrator.

Why Overpass and not the OSM main API?
--------------------------------------
The main OSM API (api.openstreetmap.org) is a *write-oriented* edit
endpoint: it returns the entire bounding-box tile, including every
amenity, road, and tree, and is rate-limited toward editors rather than
read-only consumers. Overpass is the *read-oriented* endpoint operated by
the OSM community for analytical workloads. It supports tag-filtered
queries (``["building"]``), spatial filters (``around:R,lat,lng``), and
geometry inlining (``out body geom``) — the exact three primitives we
need to retrieve a building footprint with one round-trip.

Overpass QL contract used here
------------------------------
The ``around:R,lat,lng`` filter selects every way whose *centroid* lies
within ``R`` metres of the point. ``out geom`` instructs Overpass to
inline each node's lat/lng inside the way response, so we do not need
a follow-up node-resolution query.

Egypt-specific reliability notes
--------------------------------
* OSM building coverage in Cairo is patchy: well-mapped in central
  districts, sparse in informal areas. The orchestrator treats "no
  buildings found" as a graceful degradation, not an error.
* The public Overpass instance (``overpass-api.de``) imposes
  per-IP rate limits. The 50 m default radius and 30 s timeout in
  ``app.config`` are tuned to stay comfortably inside its fair-use
  policy for academic use.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class OverpassError(Exception):
    """Raised when the Overpass request or response cannot be processed.

    Wraps both transport-layer failures and structural parse errors so
    the router can map every Overpass-side failure mode to a single
    well-defined HTTP status (502).
    """


def build_overpass_query(
    latitude: float,
    longitude: float,
    radius_m: float,
    timeout_s: float | None = None,
) -> str:
    """Build the Overpass QL query string for buildings near a point.

    Returns
    -------
    str
        A complete Overpass QL program. ``out body geom`` is required so
        the response inlines node coordinates — without it we would only
        receive node IDs and need a second round-trip to resolve them.
    """
    if radius_m <= 0:
        raise OverpassError(f"Search radius must be positive, got {radius_m}")
    timeout = int(timeout_s if timeout_s is not None else settings.overpass_timeout_s)
    return (
        f"[out:json][timeout:{timeout}];"
        f'(way["building"](around:{radius_m},{latitude},{longitude});'
        f' relation["building"](around:{radius_m},{latitude},{longitude}););'
        f"out body geom;"
    )


def _parse_way(element: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a single Overpass `way` element into our internal shape.

    Returns ``None`` when the element is not a usable closed building
    polygon (too few nodes, no geometry, or open linestring). We tolerate
    open rings by closing them ourselves — OSM occasionally serves a
    way without an explicit closure, and the geometric area function
    closes the ring implicitly anyway.
    """
    if element.get("type") != "way":
        return None
    geometry = element.get("geometry") or []
    if len(geometry) < 3:
        return None

    coordinates_lat_lng: list[tuple[float, float]] = [
        (float(point["lat"]), float(point["lon"]))
        for point in geometry
        if "lat" in point and "lon" in point
    ]
    if len(coordinates_lat_lng) < 3:
        return None

    if coordinates_lat_lng[0] != coordinates_lat_lng[-1]:
        coordinates_lat_lng.append(coordinates_lat_lng[0])

    raw_tags = element.get("tags") or {}
    tags = {str(k): str(v) for k, v in raw_tags.items()}

    return {
        "osm_way_id": int(element["id"]),
        "coordinates_lat_lng": coordinates_lat_lng,
        "tags": tags,
    }


def parse_overpass_response(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a raw Overpass JSON payload into a list of building dicts.

    Skips relation elements (multi-polygon buildings with holes) for
    Day 10. They are rare in Egyptian residential OSM data and are
    cleanly handled by Day 11's CV path; surfacing them here would
    require a multi-polygon area calculator that is out of scope.
    """
    if not isinstance(payload, dict):
        raise OverpassError("Overpass response is not a JSON object")
    elements = payload.get("elements")
    if not isinstance(elements, list):
        raise OverpassError("Overpass response missing 'elements' array")

    buildings: list[dict[str, Any]] = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        parsed = _parse_way(element)
        if parsed is not None:
            buildings.append(parsed)
    return buildings


# Overpass's fair-use policy asks every consumer to identify itself with
# a meaningful User-Agent; in practice ``overpass-api.de`` returns HTTP
# 406 to httpx's default ``python-httpx/X.Y`` UA, so this is also the
# concrete fix for that error mode (verified empirically: any non-default
# UA gets HTTP 200 for the same request).
_USER_AGENT = "pv-solar-estimator/0.1 (thesis; https://github.com/nadanazeer11/pv-solar-estimator)"


async def fetch_buildings(
    latitude: float,
    longitude: float,
    radius_m: float,
) -> list[dict[str, Any]]:
    """Fetch building footprints near a point from the Overpass API.

    Returns
    -------
    list[dict]
        Each dict contains ``osm_way_id``, ``coordinates_lat_lng``
        (closed lat/lng ring), and ``tags``. Empty list when no buildings
        are mapped within the radius — *not* an error.

    Raises
    ------
    OverpassError
        On transport failure, non-2xx response, malformed JSON, or
        structural parse failure. The router maps this to HTTP 502.
    """
    query = build_overpass_query(latitude, longitude, radius_m)
    try:
        async with httpx.AsyncClient(timeout=settings.overpass_timeout_s) as client:
            # Overpass accepts the query in the request body as
            # ``data=<QL>`` form-encoded. POST is the documented form for
            # any non-trivial query — GET URLs hit length limits quickly.
            response = await client.post(
                settings.overpass_url,
                data={"data": query},
                headers={
                    "Accept": "application/json",
                    "User-Agent": _USER_AGENT,
                },
            )
    except httpx.HTTPError as exc:
        raise OverpassError(f"Overpass transport error: {exc}") from exc

    if response.status_code != 200:
        raise OverpassError(f"Overpass returned HTTP {response.status_code}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise OverpassError(f"Overpass returned non-JSON: {exc}") from exc

    return parse_overpass_response(payload)
