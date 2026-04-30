/**
 * Hand-written mirror of the backend Pydantic schemas the frontend
 * actually consumes today. Day 12 wires only `/api/sizing` end-to-end;
 * Day 13+ either expand this file or replace it with `openapi-typescript`
 * generation against the FastAPI OpenAPI schema (the latter is the
 * design-brief target — but only after the backend stabilises and the
 * generation step is reproducible in CI).
 *
 * Keep these names, types, and units in lockstep with
 * `backend/app/schemas/sizing.py`.
 */

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
