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

// ── /api/energy/pvlib — backend/app/schemas/energy.py ───────────────────

export type EnergyPvlibRequest = {
  location: Location;
  system_kw: number;
  tilt_deg?: number;
  azimuth_deg?: number;
  inverter_efficiency?: number;
  system_losses_fraction?: number;
};

export type EnergyPvlibResult = {
  annual_kwh: number;
  /** 12 calendar-month AC totals, January..December (kWh). */
  monthly_kwh: number[];
  specific_yield_kwh_per_kwp: number;
  capacity_factor: number;
  performance_ratio: number;
  poa_annual_kwh_per_m2: number;
  mean_cell_temp_c: number;
  system_kw: number;
  tilt_deg: number;
  azimuth_deg: number;
  inverter_efficiency: number;
  system_losses_fraction: number;
};

// ── /api/energy/manual — backend/app/schemas/energy.py ──────────────────

export type EnergyManualRequest = EnergyPvlibRequest;

export type EnergyManualResult = {
  /** Discriminator emitted by the backend (always "manual"). */
  model: 'manual';
  annual_kwh: number;
  /** 12 calendar-month AC totals, January..December (kWh). */
  monthly_kwh: number[];
  specific_yield_kwh_per_kwp: number;
  capacity_factor: number;
  performance_ratio: number;
  poa_annual_kwh_per_m2: number;
  mean_cell_temp_c: number;
  system_kw: number;
  tilt_deg: number;
  azimuth_deg: number;
  inverter_efficiency: number;
  system_losses_fraction: number;
};

// ── /api/tariff/savings — backend/app/schemas/tariff.py ─────────────────

export type MonthlyBillBreakdown = {
  month_index: number;
  consumption_kwh: number;
  bill_egp: number;
  per_tier_kwh: number[];
  per_tier_egp: number[];
  marginal_tariff_egp_per_kwh: number;
};

export type TariffSavingsRequest = {
  monthly_consumption_kwh: number[];
  monthly_generation_kwh: number[];
  export_credit_egp_per_kwh?: number;
};

export type TariffSavingsResult = {
  bill_before_egp: number;
  bill_after_egp: number;
  annual_savings_egp: number;
  self_consumed_kwh: number;
  exported_kwh: number;
  export_credit_egp: number;
  average_savings_egp_per_kwh: number;
  monthly_bill_before: MonthlyBillBreakdown[];
  monthly_bill_after: MonthlyBillBreakdown[];
};

// ── /api/monte-carlo/run — backend/app/schemas/monte_carlo.py ───────────

export type MonteCarloPercentiles = {
  mean: number;
  std: number;
  p05: number;
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
  p95: number;
  minimum: number;
  maximum: number;
};

export type HistogramBins = {
  bin_edges: number[];
  counts: number[];
};

export type MonteCarloRequest = {
  system_kw: number;
  annual_kwh: number;
  tariff_egp_per_kwh: number;
  analysis_period_years?: number;
  discount_rate?: number;
  n_simulations?: number;
  random_seed?: number;
};

export type MonteCarloResult = {
  n_simulations: number;
  payback_years: MonteCarloPercentiles;
  npv_egp: MonteCarloPercentiles;
  lcoe_egp_per_kwh: MonteCarloPercentiles;
  lifetime_savings_egp: MonteCarloPercentiles;
  payback_probability: number;
  positive_npv_probability: number;
  payback_histogram: HistogramBins;
  npv_histogram: HistogramBins;
  system_kw: number;
  annual_kwh: number;
  tariff_egp_per_kwh: number;
  analysis_period_years: number;
  discount_rate: number;
  random_seed: number | null;
};
