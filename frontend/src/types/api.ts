/**
 * Hand-written mirror of the backend Pydantic schemas the frontend
 * actually consumes. Each section maps 1-1 to a module under
 * ``backend/app/schemas/`` — keep names, types, and units in lockstep.
 *
 * Day 13+ extends this file ahead of replacing it with `openapi-typescript`
 * generation against the FastAPI OpenAPI schema (the design-brief
 * target — but only after the backend stabilises and the generation
 * step is reproducible in CI).
 */

// ── /api/sizing — backend/app/schemas/sizing.py ─────────────────────────

export type SizingRequest = {
  roof_area_m2: number;
  panel_rated_watts?: number;
  panel_area_m2?: number;
  roof_utilization_factor?: number;
};

export type SizingResult = {
  roof_area_m2: number;
  usable_roof_area_m2: number;
  panel_count: number;
  system_kw: number;
  panel_rated_watts: number;
  panel_area_m2: number;
  roof_utilization_factor: number;
  panel_density_w_per_m2: number;
};

// ── shared — backend/app/schemas/inputs.py ──────────────────────────────

export type Location = {
  latitude: number;
  longitude: number;
};

// ── /api/roof — backend/app/schemas/roof.py ─────────────────────────────

export type RoofDetectionRequest = {
  location: Location;
  search_radius_m?: number;
};

export type RoofPolygon = {
  osm_way_id: number | null;
  /** Closed ring of [lat, lng] pairs in degrees. */
  coordinates_lat_lng: Array<[number, number]>;
  area_m2: number;
  perimeter_m: number;
  centroid: Location;
  contains_query_point: boolean;
  distance_to_query_point_m: number;
  tags: Record<string, string>;
};

export type RoofDetectionResult = {
  query: Location;
  primary_roof: RoofPolygon | null;
  candidates: RoofPolygon[];
  search_radius_m: number;
  satellite_tile_url: string | null;
  meters_per_pixel: number | null;
  detection_source: string;
  notes: string[];
  segmentation_polygon_lat_lng: Array<[number, number]> | null;
  segmentation_area_m2: number | null;
  segmentation_confidence: number | null;
  estimated_tilt_deg: number | null;
  estimated_tilt_source: string | null;
  estimated_azimuth_deg: number | null;
  estimated_azimuth_source: string | null;
};
