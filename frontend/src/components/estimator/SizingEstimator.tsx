import { useState } from 'react';
import { PrimaryButton } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { MetricCard } from '@/components/ui/MetricCard';
import { useSizing } from '@/hooks/useSizing';

/**
 * Day-12 end-to-end demo: one form field (roof area) → POST /api/sizing
 * → one MetricCard with the resulting system size and a Know-more
 * trigger that opens the `system-size` explainer.
 *
 * Subsequent days replace the single field with the full address /
 * Leaflet input form (Day 13) and layer additional metric cards on top
 * (Day 14). The data flow established here — form state → typed hook →
 * Card with KnowMore — is the template for every later screen.
 */
export function SizingEstimator() {
  const [roofArea, setRoofArea] = useState<string>('100');
  const sizing = useSizing();

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsed = Number.parseFloat(roofArea);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      return;
    }
    sizing.mutate({ roof_area_m2: parsed });
  };

  return (
    <div className="grid gap-8 md:grid-cols-2">
      <Card>
        <h3 className="font-display text-2xl font-semibold">Tell us about your roof</h3>
        <p className="mt-2 text-sm text-ink-soft">
          A flat concrete roof is most common in Egypt — measure the usable rectangle and
          enter the area below.
        </p>
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label
              htmlFor="roof-area"
              className="block font-display text-sm font-semibold text-ink"
            >
              Roof area (m²)
            </label>
            <input
              id="roof-area"
              type="number"
              min={1}
              step="any"
              required
              value={roofArea}
              onChange={(event) => setRoofArea(event.target.value)}
              className="mt-2 block w-full rounded-card border-2 border-border bg-bg px-4 py-3 font-display text-lg focus:outline-none"
            />
          </div>
          <PrimaryButton type="submit" disabled={sizing.isPending}>
            {sizing.isPending ? 'Estimating…' : 'Estimate system size'}
          </PrimaryButton>
          {sizing.isError && (
            <p role="alert" className="text-sm text-danger">
              Could not reach the API ({sizing.error.message}). Make sure the backend is
              running on {import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'}.
            </p>
          )}
        </form>
      </Card>

      {sizing.data ? (
        <MetricCard
          title="System size"
          number={sizing.data.system_kw.toFixed(2)}
          unit="kW"
          subtitle={`${sizing.data.panel_count} panels at ${sizing.data.panel_rated_watts.toFixed(0)} W each`}
          knowMoreId="system-size"
        />
      ) : (
        <MetricCard
          title="System size"
          number="—"
          unit="kW"
          subtitle="Submit the form to see your estimated system capacity."
          knowMoreId="system-size"
        />
      )}
    </div>
  );
}
