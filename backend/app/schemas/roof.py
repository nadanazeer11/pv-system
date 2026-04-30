"""Schemas for the AI-assisted roof detection pipeline (Days 10–11).

Day 10 lands the OSM-Overpass + Google Maps Static halves: given a
geographic point, the system fetches every nearby OpenStreetMap building
footprint, picks the one most likely to be the user's roof, and reports
its polygon and area in metric units. Day 11 layers the computer-vision
refinement on top of the satellite tile and estimates roof tilt and
azimuth — the geometric inputs the energy models need.

The CV fields on :class:`RoofDetectionResult` are optional. The Day-10
``/api/roof/detect`` endpoint never populates them; Day-11's
``/api/roof/analyze`` endpoint does. Existing clients that only consume
the OSM half therefore see an unchanged response shape.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.inputs import Location


class RoofDetectionRequest(BaseModel):
    """Input for the OSM-based roof detection endpoint.

    Only the location is mandatory. ``search_radius_m`` is exposed so
    callers can widen the search on rural plots where the building of
    interest may be 50–100 m from the dropped pin, while still defaulting
    to the dense-Cairo-friendly 50 m.
    """

    location: Location = Field(
        ...,
        description="Geographic point inside (or near) the target rooftop.",
    )
    search_radius_m: float | None = Field(
        None,
        gt=0,
        description=(
            "Overpass search radius in metres. Defaults to the configured "
            "Egypt-tuned value if omitted; capped server-side to avoid "
            "abusing the free public Overpass instance."
        ),
    )


class RoofPolygon(BaseModel):
    """A single OSM building footprint candidate.

    Coordinates are returned as ``[lat, lng]`` pairs forming a closed
    ring (first point repeated at the end), matching OSM's native
    convention. The ring is *not* re-projected — clients that need
    drawing pixels should use the ``meters_per_pixel`` and tile centre
    returned alongside the satellite tile.
    """

    osm_way_id: int | None = Field(
        None,
        description="Overpass `way` ID — null only for synthetic test fixtures.",
    )
    coordinates_lat_lng: list[tuple[float, float]] = Field(
        ...,
        min_length=4,
        description=(
            "Closed ring of (latitude, longitude) pairs in degrees. "
            "Ring is closed (first==last) — at least 4 points for a triangle."
        ),
    )
    area_m2: float = Field(
        ...,
        ge=0,
        description="Footprint area in square metres (local equirectangular projection).",
    )
    perimeter_m: float = Field(
        ...,
        ge=0,
        description="Footprint perimeter in metres.",
    )
    centroid: Location = Field(
        ...,
        description="Geometric centroid of the footprint in lat/lng.",
    )
    contains_query_point: bool = Field(
        ...,
        description=(
            "True if the user's pin lies inside this polygon. The selected "
            "primary roof is always one with this flag set if any exists."
        ),
    )
    distance_to_query_point_m: float = Field(
        ...,
        ge=0,
        description="Distance from the user's pin to the polygon centroid (metres).",
    )
    tags: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "OSM tags on the way (e.g. building, building:levels, height, "
            "roof:shape). Used by Day 11 to seed tilt/azimuth priors."
        ),
    )


class RoofDetectionResult(BaseModel):
    """Output of the OSM-based roof detection.

    ``primary_roof`` is the algorithm's best guess; ``candidates`` is the
    full sorted list (containing first, then by ascending centroid
    distance) so a frontend can offer a manual override picker.
    """

    query: Location = Field(..., description="Echo of the user-supplied pin.")
    primary_roof: RoofPolygon | None = Field(
        None,
        description="Best-match footprint, or null if no buildings were found.",
    )
    candidates: list[RoofPolygon] = Field(
        default_factory=list,
        description="Every building returned by Overpass within the search radius, sorted.",
    )
    search_radius_m: float = Field(
        ...,
        gt=0,
        description="Search radius actually used (after applying the server-side cap).",
    )
    satellite_tile_url: str | None = Field(
        None,
        description=(
            "Google Maps Static URL pre-built for the primary roof's centroid "
            "(or the query point if no roof was detected). Null when no "
            "Google Maps API key is configured — OSM detection is unaffected."
        ),
    )
    meters_per_pixel: float | None = Field(
        None,
        description=(
            "Ground resolution of the satellite tile at the chosen zoom — "
            "needed by Day 11 to convert pixel measurements back to metres."
        ),
    )
    detection_source: str = Field(
        ...,
        description="Identifier for the data path used (e.g. 'osm-overpass').",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Human-readable notes — e.g. 'API key not configured', 'no buildings'.",
    )
    # ── Day 11 CV refinement (optional; populated by /api/roof/analyze) ─
    segmentation_polygon_lat_lng: list[tuple[float, float]] | None = Field(
        None,
        description=(
            "Closed lat/lng ring produced by the CV-aware refinement of "
            "the OSM polygon (typically the minimum-rotated-rectangle "
            "regularisation, optionally snapped to image gradients). "
            "Null when no satellite imagery was available."
        ),
    )
    segmentation_area_m2: float | None = Field(
        None,
        ge=0,
        description="Area of the refined polygon in square metres. Null when CV did not run.",
    )
    segmentation_confidence: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description=(
            "Normalised score in [0,1] describing how strongly the OSM "
            "polygon edges align with the satellite image's gradient "
            "structure. 0 means the imagery could not be evaluated; 1 "
            "means every polygon edge sits on a strong, contiguous "
            "intensity ridge in the satellite tile."
        ),
    )
    estimated_tilt_deg: float | None = Field(
        None,
        ge=0.0,
        le=90.0,
        description=(
            "Recommended PV panel tilt in degrees. For flat roofs this is "
            "the latitude-optimal panel tilt (panels tilted on racks); for "
            "pitched roofs this is the roof surface pitch (panels laid "
            "flush). Null when CV did not run."
        ),
    )
    estimated_tilt_source: str | None = Field(
        None,
        description=(
            "Provenance of the tilt estimate: 'osm:roof:angle', "
            "'osm:roof:shape', 'flat-roof-default-cairo-optimum', or "
            "'fallback-cairo-default'."
        ),
    )
    estimated_azimuth_deg: float | None = Field(
        None,
        ge=0.0,
        le=360.0,
        description=(
            "Recommended PV panel azimuth in degrees from north (180 = "
            "south). Derived from the polygon's principal axis with "
            "cardinal-snapping for axis-aligned footprints. Null when CV "
            "did not run."
        ),
    )
    estimated_azimuth_source: str | None = Field(
        None,
        description=(
            "Provenance of the azimuth estimate: 'polygon-long-edge', "
            "'polygon-long-edge-snapped-cardinal', or 'fallback-south'."
        ),
    )


class RoofAnalysisRequest(BaseModel):
    """Input for the full detect+CV-refine endpoint (Day 11)."""

    location: Location = Field(
        ...,
        description="Geographic point inside (or near) the target rooftop.",
    )
    search_radius_m: float | None = Field(
        None,
        gt=0,
        description="Overpass search radius (defaults to the configured Egypt-tuned value).",
    )
    enable_cv: bool = Field(
        True,
        description=(
            "Toggle for the CV refinement pass. Set False to skip the "
            "satellite-tile fetch entirely (useful for offline tests or "
            "bandwidth-limited deployments) — the response still carries "
            "the OSM polygon and Day-11 tilt/azimuth heuristics."
        ),
    )


class SatelliteTileRequest(BaseModel):
    """Input for the Google Maps Static helper endpoint."""

    location: Location = Field(..., description="Tile centre in lat/lng.")
    zoom: int | None = Field(
        None,
        ge=1,
        le=21,
        description="Web Mercator zoom level (default: configured Egypt-tuned value).",
    )
    size_px: int | None = Field(
        None,
        gt=0,
        le=640,
        description="Square tile edge in pixels (default: configured value, capped at 640).",
    )
    scale: int | None = Field(
        None,
        ge=1,
        le=2,
        description="Pixel density multiplier (1 or 2; default: 2 for HiDPI).",
    )


class SatelliteTileResult(BaseModel):
    """Output for the Google Maps Static helper endpoint.

    The endpoint deliberately returns the URL — *not* the bytes — so
    Day 10 can be smoke-tested without paying for a real image fetch.
    The Day 11 pipeline calls the lower-level service helper directly
    to retrieve bytes for CV processing.
    """

    url: str = Field(..., description="Signed Google Maps Static URL (includes API key).")
    zoom: int = Field(..., description="Zoom level used to build the URL.")
    size_px: int = Field(..., description="Edge length of the requested tile in pixels.")
    scale: int = Field(..., description="Pixel-density multiplier used.")
    meters_per_pixel: float = Field(
        ...,
        gt=0,
        description="Ground resolution in metres at the tile centre's latitude.",
    )
    tile_width_m: float = Field(..., gt=0, description="Tile edge in metres on the ground.")
    tile_height_m: float = Field(..., gt=0, description="Tile edge in metres on the ground.")
