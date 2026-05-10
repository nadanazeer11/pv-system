"""Obstacle-polygon area computation for user-annotated rooftop images.

The user draws a roof boundary and zero or more obstacle polygons (water
tanks, AC condensers, satellite dishes, parapet walls) over a satellite
image displayed in the browser. This service receives the polygon
coordinates in image-pixel space and a known real-world roof area
(from OSM or user entry), then returns the usable area after clipping
and subtracting the obstacles.

Why pixel-space and not geographic coordinates?
-----------------------------------------------
The user annotates a locally-displayed image whose pixel→meter scale may
not be known (they may have uploaded their own satellite photo). Working
in pixel fractions — obstacle_area_px / roof_area_px — keeps the
computation scale-free: the absolute pixel size cancels out, and the
result is a dimensionless fraction that we then apply to the known area.

This approach is exact when the obstacles are drawn relative to the same
roof polygon used to define 100 % of the area; small perspective
distortions in consumer satellite imagery are negligible compared with
the ±10 % uncertainty in the user's own roof-area estimate.
"""
from __future__ import annotations

from shapely.geometry import Polygon

from app.schemas.obstacle_annotation import (
    ObstacleAnnotationRequest,
    ObstacleAnnotationResult,
)


class AnnotationError(ValueError):
    """Raised when the annotation geometry is invalid."""


def compute_usable_area(request: ObstacleAnnotationRequest) -> ObstacleAnnotationResult:
    """Subtract obstacle polygons from the roof polygon and return usable area.

    Raises
    ------
    AnnotationError
        If the roof polygon has fewer than 3 vertices or zero area after
        Shapely's validity repair.
    """
    if len(request.roof_polygon_px) < 3:
        raise AnnotationError("Roof polygon must have at least 3 vertices.")

    roof_poly = Polygon([(p[0], p[1]) for p in request.roof_polygon_px])
    if not roof_poly.is_valid:
        roof_poly = roof_poly.buffer(0)
    if roof_poly.is_empty or roof_poly.area == 0:
        raise AnnotationError("Roof polygon has zero area after geometry repair.")

    roof_area_px = roof_poly.area
    total_obstacle_px = 0.0

    for obs_coords in request.obstacle_polygons_px:
        if len(obs_coords) < 3:
            continue
        obs_poly = Polygon([(p[0], p[1]) for p in obs_coords])
        if not obs_poly.is_valid:
            obs_poly = obs_poly.buffer(0)
        if obs_poly.is_empty:
            continue
        # Clip the obstacle to the roof boundary before measuring it.
        clipped = roof_poly.intersection(obs_poly)
        total_obstacle_px += clipped.area

    obstacle_fraction = min(total_obstacle_px / roof_area_px, 1.0)
    obstacle_area_m2 = request.known_area_m2 * obstacle_fraction
    net_area_m2 = request.known_area_m2 * (1.0 - obstacle_fraction)

    return ObstacleAnnotationResult(
        roof_area_m2=request.known_area_m2,
        obstacle_area_m2=round(obstacle_area_m2, 2),
        net_area_m2=round(net_area_m2, 2),
        obstacle_fraction=round(obstacle_fraction, 4),
        obstacle_count=len(request.obstacle_polygons_px),
    )
