import { Card, HighlightCard } from '@/components/ui/Card';
import { KnowMoreButton } from '@/components/ui/KnowMoreButton';
import type { EnergyManualResult, EnergyPvlibResult } from '@/types/api';

type ModelComparisonViewProps = {
  pvlib: EnergyPvlibResult;
  manual: EnergyManualResult;
};

function formatInteger(value: number): string {
  return Math.round(value).toLocaleString('en-US');
}

function formatPercent(value: number, fractionDigits = 1): string {
  return `${(value * 100).toFixed(fractionDigits)}%`;
}

/**
 * Day-15 cross-validation panel for the dual-energy backbone.
 *
 * The panel surfaces — side by side — the annual headline numbers from
 * both energy chains and the residual between them. The thesis argues
 * that running two independent simulations on the same TMY is a model
 * uncertainty quantification: the residual's magnitude is itself a
 * reportable result. The brief target is single-digit-percent agreement,
 * which is the same convergence band the pvlib documentation reports
 * against PVSyst.
 */
export function ModelComparisonView({ pvlib, manual }: ModelComparisonViewProps) {
  const annualDiff = manual.annual_kwh - pvlib.annual_kwh;
  const annualDiffPct =
    pvlib.annual_kwh > 0 ? annualDiff / pvlib.annual_kwh : 0;
  const absAnnualDiffPct = Math.abs(annualDiffPct);
  const yieldDiff =
    manual.specific_yield_kwh_per_kwp - pvlib.specific_yield_kwh_per_kwp;
  const prDiff = manual.performance_ratio - pvlib.performance_ratio;

  const agreementLabel =
    absAnnualDiffPct < 0.05
      ? 'Strong agreement (< 5%)'
      : absAnnualDiffPct < 0.10
        ? 'Reasonable agreement (5–10%)'
        : 'Material divergence (> 10%) — investigate before reporting';

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-2xl font-semibold">
            Why two energy models?
          </h3>
          <p className="mt-2 max-w-2xl text-sm text-ink-soft">
            Every dashboard number rests on one simulation. Running the same
            inputs through a second, independently coded simulation is the
            cheapest sanity check we have on that single number — and the
            residual is the headline of the thesis's model-uncertainty
            chapter.
          </p>
        </div>
        <KnowMoreButton id="model-comparison" />
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-3" role="group" aria-label="Annual totals">
        <div className="rounded-card border-2 border-border bg-bg p-5">
          <p className="font-display text-xs font-semibold uppercase tracking-wide text-ink-soft">
            pvlib (industry-standard)
          </p>
          <p className="mt-3 font-display text-4xl font-semibold leading-none">
            {formatInteger(pvlib.annual_kwh)}
          </p>
          <p className="mt-1 text-sm text-ink-soft">kWh / yr</p>
          <dl className="mt-4 grid grid-cols-2 gap-y-1 text-xs text-ink-soft">
            <dt>Specific yield</dt>
            <dd className="text-right text-ink">
              {formatInteger(pvlib.specific_yield_kwh_per_kwp)} kWh/kWp
            </dd>
            <dt>Performance ratio</dt>
            <dd className="text-right text-ink">{pvlib.performance_ratio.toFixed(2)}</dd>
            <dt>Capacity factor</dt>
            <dd className="text-right text-ink">{formatPercent(pvlib.capacity_factor, 1)}</dd>
          </dl>
        </div>

        <div className="rounded-card border-2 border-border bg-surface p-5">
          <p className="font-display text-xs font-semibold uppercase tracking-wide text-ink-soft">
            Manual physics model
          </p>
          <p className="mt-3 font-display text-4xl font-semibold leading-none">
            {formatInteger(manual.annual_kwh)}
          </p>
          <p className="mt-1 text-sm text-ink-soft">kWh / yr</p>
          <dl className="mt-4 grid grid-cols-2 gap-y-1 text-xs text-ink-soft">
            <dt>Specific yield</dt>
            <dd className="text-right text-ink">
              {formatInteger(manual.specific_yield_kwh_per_kwp)} kWh/kWp
            </dd>
            <dt>Performance ratio</dt>
            <dd className="text-right text-ink">{manual.performance_ratio.toFixed(2)}</dd>
            <dt>Capacity factor</dt>
            <dd className="text-right text-ink">{formatPercent(manual.capacity_factor, 1)}</dd>
          </dl>
        </div>

        <HighlightCard className="!p-5">
          <p className="font-display text-xs font-semibold uppercase tracking-wide text-ink">
            Residual (manual − pvlib)
          </p>
          <p className="mt-3 font-display text-4xl font-semibold leading-none">
            {annualDiff >= 0 ? '+' : ''}
            {formatInteger(annualDiff)}
          </p>
          <p className="mt-1 text-sm text-ink">
            kWh / yr ({(annualDiffPct * 100).toFixed(1)}%)
          </p>
          <dl className="mt-4 grid grid-cols-2 gap-y-1 text-xs text-ink">
            <dt>Yield Δ</dt>
            <dd className="text-right">
              {yieldDiff >= 0 ? '+' : ''}
              {formatInteger(yieldDiff)} kWh/kWp
            </dd>
            <dt>PR Δ</dt>
            <dd className="text-right">
              {prDiff >= 0 ? '+' : ''}
              {prDiff.toFixed(2)}
            </dd>
            <dt>Verdict</dt>
            <dd className="text-right font-semibold">{agreementLabel}</dd>
          </dl>
        </HighlightCard>
      </div>
    </Card>
  );
}
