from __future__ import annotations

from pydantic import BaseModel, Field


class ObstacleAnnotationRequest(BaseModel):
    """Polygon-space obstacle annotation.

    All coordinates are in image pixels. The backend never receives the
    image itself — it only needs the polygon coordinates and the known
    real-world area of the roof to scale the pixel-fraction to m².
    """

    roof_polygon_px: list[list[float]] = Field(
        ...,
        description=(
            "Closed ring of [x, y] pixel coordinates defining the roof "
            "boundary. Must have at least 3 distinct vertices."
        ),
    )
    obstacle_polygons_px: list[list[list[float]]] = Field(
        default_factory=list,
        description=(
            "List of obstacle polygons. Each polygon is a closed ring of "
            "[x, y] pixel coordinates. Polygons that extend outside the roof "
            "boundary are automatically clipped."
        ),
    )
    known_area_m2: float = Field(
        ...,
        gt=0,
        description=(
            "Total roof area in m², taken from OSM or entered manually by the "
            "user. Used to scale the pixel-space obstacle fraction to real area."
        ),
    )


class ObstacleAnnotationResult(BaseModel):
    """Usable area after subtracting marked obstacles from the roof polygon."""

    roof_area_m2: float = Field(..., description="Input known roof area.")
    obstacle_area_m2: float = Field(..., description="Area attributed to obstacles (m²).")
    net_area_m2: float = Field(..., description="Roof area minus obstacles (m²).")
    obstacle_fraction: float = Field(..., description="Fraction of roof area occupied by obstacles [0, 1].")
    obstacle_count: int = Field(..., description="Number of obstacle polygons supplied.")
