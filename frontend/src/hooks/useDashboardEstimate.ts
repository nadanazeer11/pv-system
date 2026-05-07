import { useMutation } from '@tanstack/react-query';
import { request } from '@/lib/api';
import type {
  EnergyManualResult,
  EnergyPvlibResult,
  Location,
  MonteCarloResult,
  SizingResult,
  TariffSavingsResult,
} from '@/types/api';

export type DashboardEstimateInput = {
  location: Location;
  roof_area_m2: number;
  /**
   * Single typical-month consumption figure replicated across all 12
   * months. Egypt residential billing is monthly, so the tier kernel
   * needs a 12-vector; we keep the dashboard form to one number on
   * Day 14 and leave seasonal profile editing for a later day.
   */
  monthly_consumption_kwh: number;
  /** Random seed forwarded to the Monte Carlo engine for reproducibility. */
  random_seed?: number;
  /**
   * Override the backend's default roof utilization factor. Set to 0.85
   * when the user has explicitly marked obstacles via the annotation tool
   * (obstacles are already subtracted from roof_area_m2, so the factor
   * only needs to cover setbacks and inter-row spacing).
   */
  roof_utilization_factor?: number;
};

export type DashboardEstimateResult = {
  sizing: SizingResult;
  energy: EnergyPvlibResult;
  /**
   * Day-15 addition: the manual physics-based simulation result.
   *
   * pvlib remains the canonical input to downstream tariff and Monte
   * Carlo calculations, so the dashboard's headline numbers do not
   * change with the dual-model rollout. ``energy_manual`` is consumed
   * exclusively by the comparison view to validate the pvlib chain
   * against an independent reference implementation — the thesis's
   * model-uncertainty quantification.
   */
  energy_manual: EnergyManualResult;
  tariff: TariffSavingsResult;
  monte_carlo: MonteCarloResult;
};

/**
 * Day-14 orchestrator: fans the dashboard inputs out across the four
 * backend endpoints required to populate the headline metric grid.
 *
 * The chain is intentionally sequential, not parallel: each call
 * depends on the previous one's output (sizing → system_kw → energy →
 * monthly_kwh → tariff → effective tariff → monte carlo). Running them
 * in series also makes the failure surface easy to reason about — the
 * first non-2xx aborts the chain and surfaces in the mutation's error
 * state with the full ``ApiError`` so the dashboard can render an
 * inline banner.
 *
 * The seed defaults to 42 so two clicks on the same inputs return
 * byte-identical Monte Carlo numbers — the brief's "every number has
 * an explanation" rule extends to "every number is reproducible".
 */
export function useDashboardEstimate() {
  return useMutation<DashboardEstimateResult, Error, DashboardEstimateInput>({
    mutationKey: ['dashboard-estimate'],
    mutationFn: async (input) => {
      const sizing = await request<SizingResult>('/api/sizing', {
        method: 'POST',
        body: {
          roof_area_m2: input.roof_area_m2,
          ...(input.roof_utilization_factor !== undefined && {
            roof_utilization_factor: input.roof_utilization_factor,
          }),
        },
      });

      // The two energy models share inputs (location + system_kw) and do
      // not depend on one another, so we issue them in parallel — the
      // dashboard's wall-clock time is the slower of the two PVGIS
      // round-trips, not their sum. pvlib is canonical for downstream
      // tariff / Monte Carlo; manual feeds Day-15's comparison view.
      const [energy, energy_manual] = await Promise.all([
        request<EnergyPvlibResult>('/api/energy/pvlib', {
          method: 'POST',
          body: {
            location: input.location,
            system_kw: sizing.system_kw,
          },
        }),
        request<EnergyManualResult>('/api/energy/manual', {
          method: 'POST',
          body: {
            location: input.location,
            system_kw: sizing.system_kw,
          },
        }),
      ]);

      const monthly_consumption_kwh = Array.from(
        { length: 12 },
        () => input.monthly_consumption_kwh,
      );
      const tariff = await request<TariffSavingsResult>('/api/tariff/savings', {
        method: 'POST',
        body: {
          monthly_consumption_kwh,
          monthly_generation_kwh: energy.monthly_kwh,
        },
      });

      const tariff_egp_per_kwh =
        tariff.average_savings_egp_per_kwh > 0
          ? tariff.average_savings_egp_per_kwh
          : tariff.bill_before_egp /
            Math.max(
              1,
              monthly_consumption_kwh.reduce((acc, v) => acc + v, 0),
            );

      const monte_carlo = await request<MonteCarloResult>('/api/monte-carlo/run', {
        method: 'POST',
        body: {
          system_kw: sizing.system_kw,
          annual_kwh: energy.annual_kwh,
          tariff_egp_per_kwh,
          random_seed: input.random_seed ?? 42,
        },
      });

      return { sizing, energy, energy_manual, tariff, monte_carlo };
    },
  });
}
