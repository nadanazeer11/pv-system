"""Tilt and azimuth estimators for the AI-assisted roof detection pipeline.

These two numbers — surface tilt and surface azimuth — are the
geometric inputs the energy models (``energy_pvlib``, ``energy_manual``)
need to convert plane-of-array irradiance into AC output. Day 11 derives
them from two independent sources:

* OSM tags on the building way (``roof:angle``, ``roof:shape``,
  ``building:levels``).
* The polygon's principal axis (long-edge bearing) — for azimuth only.

Why these two sources?
----------------------
OSM `roof:*` tags are sparse but high-precision when present: a tagged
``roof:angle=27`` is a community-validated measurement, not a guess.
Polygon orientation is always available because the polygon is always
available, but the bearing of a building's long edge is only weak
evidence about *panel* orientation. We therefore prefer the OSM tag
when it exists and fall back to the polygon-geometric heuristic.

Egypt-specific defaults
-----------------------
1. **Flat is the prior.** Egyptian residential construction is
   dominated by reinforced-concrete flat slabs (Khalil & Fath, 2024,
   *Egyptian residential PV deployment review*, J. Build. Eng.). When
   ``roof:shape`` is absent we therefore *do not* default to "pitched
   at latitude angle"; we default to **flat**, with the panel tilt set
   to the latitude-optimal tilt for Cairo (≈26°).
2. **South is the panel azimuth.** For all flat roofs in the Northern
   hemisphere the optimum panel azimuth is true south (180°) because
   the sun's noon position is south year-round. The polygon-derived
   azimuth is only used for **pitched** roofs, where the panels lay
   flush on the south-facing face.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from shapely.geometry import Polygon

from app.config import settings


@dataclass(frozen=True)
class TiltEstimate:
    """Recommended PV panel tilt with provenance."""

    tilt_deg: float
    source: str


@dataclass(frozen=True)
class AzimuthEstimate:
    """Recommended PV panel azimuth (deg from north) with provenance."""

    azimuth_deg: float
    source: str


# ────────────────────────────────────────────────────────────────────
# Tilt
# ────────────────────────────────────────────────────────────────────
_FLAT_SHAPES = {"flat"}
_PITCHED_SHAPES = {
    "gabled",
    "hipped",
    "pyramidal",
    "mansard",
    "gambrel",
    "round",
    "dome",
    "onion",
    "skillion",
    "pitched",
}
_SHED_SHAPES = {"shed", "half-hipped"}


def _parse_roof_angle(raw: str) -> float | None:
    """Parse an OSM ``roof:angle`` string (typically a bare number).

    OSM convention: integer or float degrees. Anything outside the
    ``[cv_min_roof_angle_deg, cv_max_roof_angle_deg]`` band is
    discarded — both 90° and 0.001° appear in the wild as digitisation
    errors.
    """
    try:
        angle = float(raw.strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(angle):
        return None
    if angle < settings.cv_min_roof_angle_deg or angle > settings.cv_max_roof_angle_deg:
        return None
    return angle


def estimate_tilt(
    osm_tags: dict[str, str] | None,
    *,
    latitude: float,
) -> TiltEstimate:
    """Recommend a PV panel tilt for a single roof.

    Selection order (highest evidence first):

    1. ``roof:angle`` tag — a community-validated measurement of the
       roof surface pitch. Used directly because panels lie flush.
    2. ``roof:shape`` tag — a categorical hint:
       * ``flat`` → latitude-optimal panel tilt (panels tilted on racks).
       * pitched-family shape → published Egyptian residential pitch
         median (~30°).
       * shed-family shape → ~15° (typical garage / outbuilding).
    3. No relevant tag → assume flat (Egyptian residential prior),
       use latitude-optimal panel tilt.

    The latitude-optimal tilt is approximated as ``|latitude|`` — the
    classic rule-of-thumb that maximises annual yield for fixed-tilt
    PV at moderate latitudes. For Cairo this is 26°, which matches the
    PLAN.md ``default_tilt_deg`` value.
    """
    tags = osm_tags or {}

    raw_angle = tags.get("roof:angle")
    if raw_angle is not None:
        parsed = _parse_roof_angle(raw_angle)
        if parsed is not None:
            return TiltEstimate(tilt_deg=parsed, source="osm:roof:angle")

    shape = tags.get("roof:shape", "").strip().lower()
    if shape in _FLAT_SHAPES:
        return TiltEstimate(
            tilt_deg=abs(latitude),
            source="flat-roof-default-cairo-optimum",
        )
    if shape in _PITCHED_SHAPES:
        return TiltEstimate(
            tilt_deg=settings.cv_default_pitched_roof_tilt_deg,
            source="osm:roof:shape",
        )
    if shape in _SHED_SHAPES:
        return TiltEstimate(
            tilt_deg=settings.cv_default_shed_roof_tilt_deg,
            source="osm:roof:shape",
        )

    return TiltEstimate(
        tilt_deg=abs(latitude),
        source="fallback-cairo-default",
    )


# ────────────────────────────────────────────────────────────────────
# Azimuth
# ────────────────────────────────────────────────────────────────────
_EARTH_RADIUS_M = 6_378_137.0


def _bearing_from_segment(
    lat1: float,
    lng1: float,
    lat2: float,
    lng2: float,
) -> float:
    """Initial bearing (degrees from north, clockwise) of a great-circle segment.

    Uses the standard spherical-trig formula. For the building-scale
    distances we care about (<200 m) this is indistinguishable from a
    rhumb-line bearing.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlng = math.radians(lng2 - lng1)
    x = math.sin(dlng) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlng)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def _longest_edge(
    polygon_lat_lng: Sequence[tuple[float, float]],
    origin_lat: float,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Return the two endpoints of the polygon's longest edge.

    Edge length is measured in projected metres so the comparison is
    geographically meaningful (a degree of longitude is shorter than a
    degree of latitude at non-equatorial latitudes).
    """
    if len(polygon_lat_lng) < 2:
        return None
    cos_origin = math.cos(math.radians(origin_lat))
    deg_to_m = math.radians(1.0) * _EARTH_RADIUS_M
    longest_length_m = -1.0
    longest_edge: tuple[tuple[float, float], tuple[float, float]] | None = None
    for (lat0, lng0), (lat1, lng1) in zip(polygon_lat_lng, polygon_lat_lng[1:]):
        dx = (lng1 - lng0) * cos_origin * deg_to_m
        dy = (lat1 - lat0) * deg_to_m
        length_m = math.hypot(dx, dy)
        if length_m > longest_length_m:
            longest_length_m = length_m
            longest_edge = ((lat0, lng0), (lat1, lng1))
    return longest_edge


def _south_facing_perpendicular(long_edge_bearing_deg: float) -> float:
    """Pick the perpendicular direction closest to true south (180°).

    A roof's long edge has two perpendicular directions, 180° apart.
    For the Northern hemisphere the optimum panel azimuth is the one
    closer to south. We always return a value in ``[0, 360)``.
    """
    candidate_a = (long_edge_bearing_deg + 90.0) % 360.0
    candidate_b = (long_edge_bearing_deg + 270.0) % 360.0
    distance_a = min(abs(candidate_a - 180.0), 360.0 - abs(candidate_a - 180.0))
    distance_b = min(abs(candidate_b - 180.0), 360.0 - abs(candidate_b - 180.0))
    return candidate_a if distance_a <= distance_b else candidate_b


def _snap_to_cardinal(azimuth_deg: float, tolerance_deg: float) -> tuple[float, bool]:
    """Snap to the nearest of {0, 90, 180, 270} if within tolerance.

    Returns ``(azimuth, snapped)``. The cardinal-snap is conservative:
    only snaps when the angle is *unambiguously* near a cardinal,
    avoiding silent rotation of polygons that genuinely sit at 45°.
    """
    cardinals = (0.0, 90.0, 180.0, 270.0, 360.0)
    distances = [
        (abs(((azimuth_deg - cardinal + 540.0) % 360.0) - 180.0) - 0.0, cardinal)
        for cardinal in cardinals
    ]
    closest_dist, closest_cardinal = min(distances, key=lambda x: abs(x[0]))
    # The above expression measures the *circular* distance to each
    # cardinal in degrees; closest_dist is in [0, 180].
    if abs(closest_dist) <= tolerance_deg:
        return (closest_cardinal % 360.0), True
    return azimuth_deg, False


def estimate_azimuth(
    polygon_lat_lng: Sequence[tuple[float, float]] | None,
    *,
    is_flat_roof: bool,
    fallback_deg: float = 180.0,
) -> AzimuthEstimate:
    """Recommend a PV panel azimuth for the roof.

    For **flat roofs** we always recommend the fallback (true south
    180°) — panels are tilt-mounted on racks and their azimuth is a
    free parameter, optimised to south by every textbook.

    For **pitched roofs** we compute the long-edge bearing (which
    typically aligns with the building's ridge), then take the
    perpendicular direction closest to south as the panel azimuth.
    Optionally snap to a cardinal heading when the long edge is within
    ``settings.cv_azimuth_snap_tolerance_deg`` of axis-aligned —
    OSM digitisation jitter routinely rotates a square footprint by
    1–2°, which we want to absorb.
    """
    if is_flat_roof:
        return AzimuthEstimate(
            azimuth_deg=fallback_deg % 360.0,
            source="fallback-south",
        )

    if polygon_lat_lng is None or len(polygon_lat_lng) < 2:
        return AzimuthEstimate(
            azimuth_deg=fallback_deg % 360.0,
            source="fallback-south",
        )

    edge = _longest_edge(polygon_lat_lng, polygon_lat_lng[0][0])
    if edge is None:
        return AzimuthEstimate(
            azimuth_deg=fallback_deg % 360.0,
            source="fallback-south",
        )

    (lat0, lng0), (lat1, lng1) = edge
    bearing = _bearing_from_segment(lat0, lng0, lat1, lng1)
    panel_azimuth = _south_facing_perpendicular(bearing)
    snapped, was_snapped = _snap_to_cardinal(
        panel_azimuth, settings.cv_azimuth_snap_tolerance_deg
    )
    return AzimuthEstimate(
        azimuth_deg=snapped,
        source=(
            "polygon-long-edge-snapped-cardinal"
            if was_snapped
            else "polygon-long-edge"
        ),
    )


# ────────────────────────────────────────────────────────────────────
# Convenience: classify roof shape from OSM tags
# ────────────────────────────────────────────────────────────────────
def is_flat_roof(osm_tags: dict[str, str] | None) -> bool:
    """Return True if the OSM tags indicate a flat roof.

    The Egyptian residential prior (no tag → flat) is encoded here so
    every caller (orchestrator, tests) gets a single source of truth.
    """
    if not osm_tags:
        return True
    shape = osm_tags.get("roof:shape", "").strip().lower()
    if shape in _FLAT_SHAPES:
        return True
    if shape in _PITCHED_SHAPES or shape in _SHED_SHAPES:
        return False
    angle = osm_tags.get("roof:angle")
    if angle is not None:
        parsed = _parse_roof_angle(angle)
        if parsed is not None and parsed > 5.0:
            return False
    return True


# Convenience polygon area (used by tests + orchestrator sanity checks).
def polygon_area_m2(
    polygon_lat_lng: Sequence[tuple[float, float]],
    origin_lat: float,
    origin_lng: float,
) -> float:
    cos_origin = math.cos(math.radians(origin_lat))
    deg_to_m = math.radians(1.0) * _EARTH_RADIUS_M
    coords = [
        ((lng - origin_lng) * cos_origin * deg_to_m, (lat - origin_lat) * deg_to_m)
        for lat, lng in polygon_lat_lng
    ]
    polygon = Polygon(coords)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    return float(polygon.area)
