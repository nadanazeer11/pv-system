"""Roof detection orchestrator (Day 10 — OSM half).

Combines :mod:`overpass_service` (vector building footprints) with
:mod:`gmaps_static` (raster satellite tiles) and produces a single
structured result describing the most likely rooftop for the user's
dropped pin. Day 11 layers a computer-vision refinement on top of the
satellite tile; the schema is designed so Day 11 only needs to fill
two additional optional fields.

Selection rule
--------------
Given a ranked list of nearby OSM building footprints we pick the
**smallest polygon that contains the user's pin**. The two clauses
matter independently:

1. *Containment first* — even a 1-cm offset from a building edge is far
   stronger evidence than centroid distance. A user who drops a pin on
   their roof is almost always inside the polygon.
2. *Smallest area among containers* — Egyptian residential parcels are
   sometimes nested inside a larger ``building=apartments`` polygon
   that wraps a courtyard plus several units. Picking the *innermost*
   container disambiguates correctly.

When **no** polygon contains the pin (rural plot, mis-mapped building,
or sparse OSM coverage), the orchestrator falls back to *the building
with the closest centroid*. The result schema flags
``contains_query_point`` so the frontend can warn the user that the
match is heuristic.

Projection
----------
For local distance and area we use a small-region equirectangular
projection centred on the user's pin::

    x_m = (lng - lng0) * cos(lat0) * R * π/180
    y_m = (lat  - lat0)            * R * π/180

with ``R = 6 378 137 m`` (WGS84 semi-major axis). At the building scale
(<200 m diagonal) the maximum area distortion versus a UTM-quality
projection is below 0.05 % at Cairo's latitude — well inside the
roof-utilization-factor uncertainty downstream. We avoid pulling in
``pyproj`` to keep the dependency surface small.
"""
from __future__ import annotations

import math
from typing import Any

from shapely.geometry import Point, Polygon

from app.config import settings
from app.schemas.inputs import Location
from app.schemas.roof import RoofDetectionResult, RoofPolygon
from app.services import gmaps_static, overpass_service


class RoofDetectionError(Exception):
    """Raised when the orchestrator cannot complete a detection.

    Distinct from ``OverpassError`` / ``GoogleMapsError`` so the router
    can return 422 for "your inputs are off" versus 502 for "an upstream
    failed". Day 10 raises this only for fatal validation failures —
    "no buildings found" is *not* an error, just a populated result with
    ``primary_roof = None``.
    """


# ────────────────────────────────────────────────────────────────────
# Geometry helpers
# ────────────────────────────────────────────────────────────────────
_EARTH_RADIUS_M = 6_378_137.0


def project_lat_lng_to_meters(
    origin_lat: float,
    origin_lng: float,
    coordinates_lat_lng: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Project lat/lng coordinates to local metres around an origin.

    Equirectangular projection — first-order accurate for ``<10 km``
    extents at any latitude away from the poles. The y-axis is north,
    the x-axis is east, and the origin lat/lng maps to ``(0, 0)``.
    """
    cos_origin = math.cos(math.radians(origin_lat))
    deg_to_m = math.radians(1.0) * _EARTH_RADIUS_M
    return [
        ((lng - origin_lng) * cos_origin * deg_to_m, (lat - origin_lat) * deg_to_m)
        for lat, lng in coordinates_lat_lng
    ]


def _polygon_metrics(
    coordinates_lat_lng: list[tuple[float, float]],
    pin_lat: float,
    pin_lng: float,
) -> dict[str, Any]:
    """Compute the geometric metrics of a single building footprint.

    Centroid is computed in lat/lng directly (mean of vertices, dropping
    the closure repeat) — this is exact for triangles and within
    centimetres of the true area-weighted centroid for the convex,
    axis-aligned shapes typical of Egyptian residential buildings.
    """
    ring = list(coordinates_lat_lng)
    if len(ring) >= 2 and ring[0] == ring[-1]:
        unique_vertices = ring[:-1]
    else:
        unique_vertices = ring
    if len(unique_vertices) < 3:
        raise RoofDetectionError(
            f"Footprint has only {len(unique_vertices)} unique vertices; "
            "need at least 3 to form a polygon."
        )

    centroid_lat = sum(v[0] for v in unique_vertices) / len(unique_vertices)
    centroid_lng = sum(v[1] for v in unique_vertices) / len(unique_vertices)

    coords_m_pin = project_lat_lng_to_meters(pin_lat, pin_lng, ring)
    polygon = Polygon(coords_m_pin)
    if not polygon.is_valid:
        # Buffer-by-zero is the canonical shapely fix for a self-touching
        # ring; OSM occasionally serves these for buildings with a
        # courtyard tagged as a single way.
        polygon = polygon.buffer(0)
    if polygon.is_empty:
        raise RoofDetectionError("Footprint collapsed to an empty polygon after cleaning.")

    contains_pin = bool(polygon.contains(Point(0.0, 0.0)))

    centroid_x_m, centroid_y_m = (
        ((centroid_lng - pin_lng) * math.cos(math.radians(pin_lat)) * math.radians(1.0) * _EARTH_RADIUS_M),
        (centroid_lat - pin_lat) * math.radians(1.0) * _EARTH_RADIUS_M,
    )
    distance_m = math.hypot(centroid_x_m, centroid_y_m)

    return {
        "area_m2": float(polygon.area),
        "perimeter_m": float(polygon.length),
        "centroid_lat": centroid_lat,
        "centroid_lng": centroid_lng,
        "contains_query_point": contains_pin,
        "distance_to_query_point_m": distance_m,
    }


# ────────────────────────────────────────────────────────────────────
# Selection logic
# ────────────────────────────────────────────────────────────────────
def _to_roof_polygon(building: dict[str, Any], metrics: dict[str, Any]) -> RoofPolygon:
    return RoofPolygon(
        osm_way_id=building.get("osm_way_id"),
        coordinates_lat_lng=building["coordinates_lat_lng"],
        area_m2=metrics["area_m2"],
        perimeter_m=metrics["perimeter_m"],
        centroid=Location(
            latitude=metrics["centroid_lat"],
            longitude=metrics["centroid_lng"],
        ),
        contains_query_point=metrics["contains_query_point"],
        distance_to_query_point_m=metrics["distance_to_query_point_m"],
        tags=building.get("tags", {}),
    )


def _sort_key(polygon: RoofPolygon) -> tuple[int, float, float]:
    # Containing roofs first (False > True under default sort, so negate).
    # Then ascending area for the inner-most match. Then ascending
    # centroid distance as a tiebreaker.
    return (0 if polygon.contains_query_point else 1, polygon.area_m2, polygon.distance_to_query_point_m)


def _select_primary(candidates: list[RoofPolygon]) -> RoofPolygon | None:
    if not candidates:
        return None
    containing = [c for c in candidates if c.contains_query_point]
    if containing:
        # Innermost (smallest-area) container wins.
        return min(containing, key=lambda c: c.area_m2)
    # Closest-centroid fallback — explicitly flagged via
    # ``contains_query_point=False`` on the chosen polygon.
    return min(candidates, key=lambda c: c.distance_to_query_point_m)


# ────────────────────────────────────────────────────────────────────
# Public orchestrator
# ────────────────────────────────────────────────────────────────────
def _resolve_radius(requested: float | None) -> float:
    base = requested if requested is not None else settings.roof_search_radius_m
    if base <= 0:
        raise RoofDetectionError("Search radius must be positive.")
    return min(base, settings.roof_search_radius_max_m)


def _build_satellite_tile_url(
    primary_roof: RoofPolygon | None,
    pin: Location,
) -> tuple[str | None, float | None, list[str]]:
    """Build a satellite tile URL centred on the chosen roof.

    Returns ``(url, meters_per_pixel, notes)`` so the orchestrator can
    surface a human-readable note when the URL cannot be built (e.g.
    because the API key is not configured). The OSM detection is *not*
    affected by GMaps configuration — this is a graceful degradation.
    """
    centre = primary_roof.centroid if primary_roof is not None else pin
    notes: list[str] = []
    try:
        url = gmaps_static.build_static_map_url(
            centre.latitude,
            centre.longitude,
        )
    except gmaps_static.GoogleMapsError as exc:
        notes.append(f"Satellite tile unavailable: {exc}")
        return None, None, notes
    description = gmaps_static.describe_tile(centre.latitude)
    return url, float(description["meters_per_pixel"]), notes


def assemble_candidates(
    buildings: list[dict[str, Any]],
    pin_lat: float,
    pin_lng: float,
) -> list[RoofPolygon]:
    """Convert raw Overpass dicts into the sorted RoofPolygon list."""
    polygons: list[RoofPolygon] = []
    for building in buildings:
        try:
            metrics = _polygon_metrics(
                building["coordinates_lat_lng"], pin_lat, pin_lng
            )
        except RoofDetectionError:
            # A single malformed footprint should not poison the whole
            # response — skip and let the rest through.
            continue
        polygons.append(_to_roof_polygon(building, metrics))
    polygons.sort(key=_sort_key)
    return polygons


async def detect_roof(
    pin: Location,
    *,
    search_radius_m: float | None = None,
) -> RoofDetectionResult:
    """End-to-end roof detection for a user-dropped geographic pin.

    The function never raises ``OverpassError`` / ``GoogleMapsError`` to
    its caller — they are converted to ``RoofDetectionError`` (for the
    Overpass case, since the rest of the pipeline cannot proceed) or
    folded into a non-fatal ``notes`` entry (for the GMaps case).
    """
    radius = _resolve_radius(search_radius_m)
    notes: list[str] = []

    try:
        raw_buildings = await overpass_service.fetch_buildings(
            pin.latitude, pin.longitude, radius
        )
    except overpass_service.OverpassError as exc:
        raise RoofDetectionError(f"OSM Overpass fetch failed: {exc}") from exc

    candidates = assemble_candidates(raw_buildings, pin.latitude, pin.longitude)
    primary = _select_primary(candidates)

    if not candidates:
        notes.append(
            f"No OSM building footprints found within {radius:.0f} m of the pin."
        )
    elif primary is not None and not primary.contains_query_point:
        notes.append(
            "No polygon contains the dropped pin; falling back to the closest "
            "building centroid. Consider a manual override."
        )

    tile_url, mpp, gmaps_notes = _build_satellite_tile_url(primary, pin)
    notes.extend(gmaps_notes)

    return RoofDetectionResult(
        query=pin,
        primary_roof=primary,
        candidates=candidates,
        search_radius_m=radius,
        satellite_tile_url=tile_url,
        meters_per_pixel=mpp,
        detection_source="osm-overpass",
        notes=notes,
    )
