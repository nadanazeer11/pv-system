"""Google Maps Static API integration.

Builds (and, when invoked, fetches) the satellite tiles consumed by the
roof-detection pipeline. Day 10 only needs the URL builder and the
ground-resolution math; the byte-fetching helper is added now so the
Day 11 computer-vision module can call it without further plumbing.

Why Google Maps Static and not Bing / Esri / Mapbox?
----------------------------------------------------
The Egypt rooftop dataset (informal additions, satellite dishes, water
tanks) is best resolved at sub-50 cm imagery. As of 2024:

  * Google Maps Static — sub-25 cm in greater Cairo, free up to 28 000
    requests / month, no commercial-use restriction for academic
    research, single API key.
  * Bing Maps Static — comparable resolution in Egypt but requires an
    Azure subscription and quota approval that is non-trivial for a
    student project.
  * Esri / Mapbox — billed per tile from request 0; impractical for the
    iterative thesis demo.

For the thesis prototype Google Maps Static is therefore the lowest-
friction choice with the resolution to support segmentation. The URL is
built deterministically — *no live request is made* by ``build_static_map_url``
— so unit tests can assert the URL contents without network access.

Ground-resolution formula
-------------------------
Google Maps tiles use Web Mercator at integer zoom levels. The standard
ground-resolution-per-pixel at the equator at zoom 0 is the Earth's
equatorial circumference / 256 ≈ 156 543.034 m/px (this constant is
documented in Google's developer guide). Because Web Mercator stretches
toward the poles, the true ground resolution at latitude φ is::

    m_per_px = 156543.034 × cos(φ) / (2^zoom × scale)

Cairo (φ ≈ 30°) at zoom 20, scale 2 ⇒ ≈ 14 cm/pixel — sufficient for the
Day 11 segmentation work.
"""
from __future__ import annotations

import math
from urllib.parse import urlencode

import httpx

from app.config import settings


class GoogleMapsError(Exception):
    """Raised when the Google Maps Static request cannot be built or fetched.

    Distinguished from a Pydantic validation error: those are 422 user
    errors at the HTTP boundary, this one is an upstream-or-config
    failure that becomes a 502 / 503.
    """


def _resolved_params(
    zoom: int | None,
    size_px: int | None,
    scale: int | None,
) -> tuple[int, int, int]:
    """Apply Egypt-tuned defaults from settings for any field left as None."""
    return (
        zoom if zoom is not None else settings.gmaps_static_default_zoom,
        size_px if size_px is not None else settings.gmaps_static_default_size_px,
        scale if scale is not None else settings.gmaps_static_default_scale,
    )


def meters_per_pixel(latitude: float, zoom: int, scale: int = 2) -> float:
    """Ground resolution of a Web Mercator tile at a given latitude.

    Parameters
    ----------
    latitude : float
        Tile centre latitude in degrees (positive north). Polar latitudes
        are mathematically valid but Web Mercator becomes unusable beyond
        ~85°; we do not clip explicitly because Egypt is comfortably
        inside the usable band.
    zoom : int
        Google Maps zoom level (1–21 in practice). Each step doubles the
        spatial resolution.
    scale : int, default 2
        Pixel-density multiplier — Google returns ``size×scale`` pixels
        for the same ground area, so ``scale=2`` halves the metres-per-pixel.

    Returns
    -------
    float
        Metres of ground covered by one image pixel.
    """
    if zoom < 0:
        raise GoogleMapsError(f"Invalid Google Maps zoom: {zoom} (must be >= 0)")
    if scale < 1:
        raise GoogleMapsError(f"Invalid Google Maps scale: {scale} (must be >= 1)")
    return (
        settings.web_mercator_zoom0_meters_per_pixel
        * math.cos(math.radians(latitude))
        / (2**zoom)
        / scale
    )


def build_static_map_url(
    latitude: float,
    longitude: float,
    *,
    zoom: int | None = None,
    size_px: int | None = None,
    scale: int | None = None,
    maptype: str = "satellite",
) -> str:
    """Construct a signed Google Maps Static URL for a satellite tile.

    The function does not perform a network request — it only assembles
    the URL. This keeps it pure and trivially testable.

    Raises
    ------
    GoogleMapsError
        If the API key is not configured. We fail loudly here because a
        silently-degraded URL (no key) returns a "for development only"
        watermarked image that is useless for downstream segmentation.
    """
    if not settings.google_maps_api_key:
        raise GoogleMapsError(
            "GOOGLE_MAPS_API_KEY not configured; cannot build a satellite tile URL."
        )

    z, s, sc = _resolved_params(zoom, size_px, scale)

    params = {
        "center": f"{latitude:.6f},{longitude:.6f}",
        "zoom": z,
        "size": f"{s}x{s}",
        "scale": sc,
        "maptype": maptype,
        "format": "png",
        "key": settings.google_maps_api_key,
    }
    return f"{settings.google_maps_static_url}?{urlencode(params)}"


def describe_tile(
    latitude: float,
    *,
    zoom: int | None = None,
    size_px: int | None = None,
    scale: int | None = None,
) -> dict[str, float | int]:
    """Return the geometric metadata for a tile centred at the given latitude.

    Used both internally (to populate ``RoofDetectionResult.meters_per_pixel``)
    and from the helper endpoint. The returned dict is intentionally JSON-
    serialisable so it can flow through Pydantic without conversion.
    """
    z, s, sc = _resolved_params(zoom, size_px, scale)
    mpp = meters_per_pixel(latitude, z, sc)
    edge_m = mpp * s * sc
    return {
        "zoom": z,
        "size_px": s,
        "scale": sc,
        "meters_per_pixel": mpp,
        "tile_width_m": edge_m,
        "tile_height_m": edge_m,
    }


async def fetch_static_map(
    latitude: float,
    longitude: float,
    *,
    zoom: int | None = None,
    size_px: int | None = None,
    scale: int | None = None,
) -> bytes:
    """Fetch the PNG bytes of a satellite tile.

    Day 10 does not call this from any router — Day 11's segmentation
    pipeline will. It lives here so the entire Google Maps Static
    surface is in one module and the test suite covers it once.

    Raises
    ------
    GoogleMapsError
        On any non-2xx response, non-image content type, or transport-
        level failure. The error message is sanitised so callers can
        surface it through HTTP without leaking the API key.
    """
    url = build_static_map_url(
        latitude,
        longitude,
        zoom=zoom,
        size_px=size_px,
        scale=scale,
    )
    try:
        async with httpx.AsyncClient(timeout=settings.gmaps_static_timeout_s) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        raise GoogleMapsError(f"Google Maps Static transport error: {exc}") from exc

    if response.status_code != 200:
        raise GoogleMapsError(
            f"Google Maps Static returned HTTP {response.status_code}"
        )

    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        raise GoogleMapsError(
            f"Google Maps Static returned non-image content-type: {content_type!r}"
        )

    return response.content
