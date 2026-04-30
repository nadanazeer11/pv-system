import { useEffect, useMemo, useState } from 'react';
import { PrimaryButton } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { MetricCard } from '@/components/ui/MetricCard';
import { useDashboardEstimate } from '@/hooks/useDashboardEstimate';
import type { Location, RoofPolygon } from '@/types/api';

type DashboardProps = {
  /** Latest location chosen via the upstream LocationPicker. */
  location: Location | null;
  /**
   * Latest OSM-detected roof for the chosen pin (null when none was
   * found, or no pin is set). Used to pre-fill the roof area input.
   * The user can still override the value before pressing Estimate.
   */
  roof: RoofPolygon | null;
};

const DEFAULT_MONTHLY_KWH = 350;
const DEFAULT_FALLBACK_AREA_M2 = 100;

function formatNumber(value: number, fractionDigits = 0): string {
  return value.toLocaleString('en-US', {
    maximumFractionDigits: fractionDigits,
    minimumFractionDigits: fractionDigits,
  });
}

/**
 * Day-14 results dashboard.
 *
 * Reads ``location`` + the OSM-detected ``roof`` from the upstream
 * LocationPicker, asks the user for two more numbers (roof area, typical
 * monthly bill in kWh), and runs the four-call orchestrator on submit.
 * Renders the four headline metric cards — System Size, Annual
 * Generation, Annual Savings, and Payback Period (highlight) — each
 * with its own KnowMore explainer.
 *
 * Three states are visible to the user:
 *   - idle: every card shows a placeholder dash and "Run an estimate"
 *     subtitle so the dashboard scaffold is itself self-explanatory.
 *   - pending: each card shows "Estimating…" without re-using the
 *     button's spinner, matching the design brief's "no blocking
 *     spinners" rule.
 *   - settled: cards either render the value or surface the error
 *     inline below the form.
 */
export function Dashboard({ location, roof }: DashboardProps) {
  const [roofAreaInput, setRoofAreaInput] = useState<string>(
    String(DEFAULT_FALLBACK_AREA_M2),
  );
  const [monthlyKwhInput, setMonthlyKwhInput] = useState<string>(
    String(DEFAULT_MONTHLY_KWH),
  );
  const [userEditedArea, setUserEditedArea] = useState<boolean>(false);

  // Auto-populate the area field whenever a fresh OSM detection lands —
  // but only if the user hasn't manually edited the input yet, so we
  // never silently clobber a deliberate override.
  useEffect(() => {
    if (userEditedArea) return;
    if (roof && Number.isFinite(roof.area_m2) && roof.area_m2 > 0) {
      setRoofAreaInput(String(Math.round(roof.area_m2)));
    }
  }, [roof, userEditedArea]);

  const estimate = useDashboardEstimate();

  const parsedRoofArea = Number.parseFloat(roofAreaInput);
  const parsedMonthlyKwh = Number.parseFloat(monthlyKwhInput);
  const formValid =
    Number.isFinite(parsedRoofArea) &&
    parsedRoofArea > 0 &&
    Number.isFinite(parsedMonthlyKwh) &&
    parsedMonthlyKwh > 0 &&
    location !== null;

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!formValid || !location) return;
    estimate.mutate({
      location,
      roof_area_m2: parsedRoofArea,
      monthly_consumption_kwh: parsedMonthlyKwh,
    });
  };

  const data = estimate.data;
  const isPending = estimate.isPending;

  const paybackSummary = useMemo(() => {
    if (!data) return null;
    const { p50, p05, p95 } = data.monte_carlo.payback_years;
    const halfWidth = (p95 - p05) / 2;
    return {
      median: p50,
      halfWidth,
      lower: p05,
      upper: p95,
      probability: data.monte_carlo.payback_probability,
    };
  }, [data]);

  const idleSubtitle = 'Run an estimate to see this number.';
  const pendingSubtitle = 'Estimating…';

  return (
    <div className="space-y-8">
      <Card>
        <h3 className="font-display text-2xl font-semibold">Run the estimate</h3>
        <p className="mt-2 text-sm text-ink-soft">
          {location
            ? roof
              ? `We pre-filled the roof area from the building outline (${formatNumber(roof.area_m2, 0)} m²). You can override it below.`
              : 'No building outline was detected at the selected pin — enter your roof area manually.'
            : 'Select a location on the map above to enable the estimate.'}
        </p>
        <form
          onSubmit={handleSubmit}
          className="mt-6 grid gap-4 md:grid-cols-2"
          aria-label="Estimate inputs"
        >
          <div>
            <label
              htmlFor="dashboard-roof-area"
              className="block font-display text-sm font-semibold text-ink"
            >
              Roof area (m²)
            </label>
            <input
              id="dashboard-roof-area"
              type="number"
              min={1}
              step="any"
              required
              value={roofAreaInput}
              onChange={(event) => {
                setRoofAreaInput(event.target.value);
                setUserEditedArea(true);
              }}
              className="mt-2 block w-full rounded-card border-2 border-border bg-bg px-4 py-3 font-display text-lg focus:outline-none"
            />
          </div>
          <div>
            <label
              htmlFor="dashboard-monthly-kwh"
              className="block font-display text-sm font-semibold text-ink"
            >
              Typical monthly bill (kWh)
            </label>
            <input
              id="dashboard-monthly-kwh"
              type="number"
              min={1}
              step="any"
              required
              value={monthlyKwhInput}
              onChange={(event) => setMonthlyKwhInput(event.target.value)}
              className="mt-2 block w-full rounded-card border-2 border-border bg-bg px-4 py-3 font-display text-lg focus:outline-none"
            />
            <p className="mt-2 text-xs text-ink-soft">
              Read off any recent EgyptERA bill — typical Egyptian households consume 200–600 kWh per month.
            </p>
          </div>
          <div className="md:col-span-2">
            <PrimaryButton type="submit" disabled={!formValid || isPending}>
              {isPending ? 'Running estimate…' : 'Estimate savings'}
            </PrimaryButton>
            {!location && (
              <p className="mt-3 text-sm text-ink-soft" role="status">
                Pick a place on the map first — then come back here.
              </p>
            )}
            {estimate.isError && (
              <p role="alert" className="mt-3 text-sm text-danger">
                Could not run the estimate ({estimate.error.message}). Make sure the backend is reachable.
              </p>
            )}
          </div>
        </form>
      </Card>

      <div
        className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4"
        role="region"
        aria-label="Estimate results"
      >
        <MetricCard
          title="System size"
          number={data ? formatNumber(data.sizing.system_kw, 2) : '—'}
          unit="kW"
          subtitle={
            data
              ? `${data.sizing.panel_count} panels at ${formatNumber(data.sizing.panel_rated_watts, 0)} W each`
              : isPending
                ? pendingSubtitle
                : idleSubtitle
          }
          knowMoreId="system-size"
        />
        <MetricCard
          title="Annual generation"
          number={data ? formatNumber(data.energy.annual_kwh, 0) : '—'}
          unit="kWh / yr"
          subtitle={
            data
              ? `${formatNumber(data.energy.specific_yield_kwh_per_kwp, 0)} kWh per kW installed`
              : isPending
                ? pendingSubtitle
                : idleSubtitle
          }
          knowMoreId="energy-pvlib"
        />
        <MetricCard
          title="Annual savings"
          number={data ? formatNumber(data.tariff.annual_savings_egp, 0) : '—'}
          unit="EGP / yr"
          subtitle={
            data
              ? `${formatNumber(data.tariff.average_savings_egp_per_kwh, 2)} EGP saved per kWh generated`
              : isPending
                ? pendingSubtitle
                : idleSubtitle
          }
          knowMoreId="tiered-tariff"
        />
        <MetricCard
          title="Payback period"
          number={paybackSummary ? formatNumber(paybackSummary.median, 1) : '—'}
          unit={
            paybackSummary
              ? `± ${formatNumber(paybackSummary.halfWidth, 1)} yr`
              : 'yr'
          }
          subtitle={
            paybackSummary
              ? `90% range: ${formatNumber(paybackSummary.lower, 1)} – ${formatNumber(paybackSummary.upper, 1)} years (probability of payback within horizon: ${(paybackSummary.probability * 100).toFixed(0)}%)`
              : isPending
                ? pendingSubtitle
                : idleSubtitle
          }
          knowMoreId="payback-ci"
          highlight
        />
      </div>
    </div>
  );
}
