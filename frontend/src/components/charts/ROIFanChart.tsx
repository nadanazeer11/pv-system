import { useId, useMemo } from 'react';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Card } from '@/components/ui/Card';
import { KnowMoreButton } from '@/components/ui/KnowMoreButton';
import type { CumulativeCashFlowTrajectory } from '@/types/api';

type ROIFanChartProps = {
  trajectory: CumulativeCashFlowTrajectory;
  /** Median payback year (years). Drawn as a vertical reference line. */
  medianPaybackYear: number | null;
};

type Row = {
  year: number;
  /** Lower bound of the 90% band (p05). */
  p05: number;
  /** Lower bound of the IQR (p25). */
  p25: number;
  /** Median trajectory (p50). */
  p50: number;
  /** Upper bound of the IQR (p75). */
  p75: number;
  /** Upper bound of the 90% band (p95). */
  p95: number;
  /**
   * Width contributions for stacked-area rendering. Recharts'
   * <Area /> is naturally a positive-from-zero ribbon, so to draw
   * percentile ribbons we stack invisible-then-visible bands with
   * a ``stackId`` and let Recharts compose them. Each ``*_band``
   * field is the *width* of one ribbon segment.
   */
  band_p05: number;
  band_p25_minus_p05: number;
  band_p50_minus_p25: number;
  band_p75_minus_p50: number;
  band_p95_minus_p75: number;
};

function buildRows(traj: CumulativeCashFlowTrajectory): Row[] {
  return traj.year_index.map((year, i) => {
    const p05 = Number(traj.p05[i] ?? 0);
    const p25 = Number(traj.p25[i] ?? 0);
    const p50 = Number(traj.p50[i] ?? 0);
    const p75 = Number(traj.p75[i] ?? 0);
    const p95 = Number(traj.p95[i] ?? 0);
    return {
      year,
      p05,
      p25,
      p50,
      p75,
      p95,
      band_p05: p05,
      band_p25_minus_p05: p25 - p05,
      band_p50_minus_p25: p50 - p25,
      band_p75_minus_p50: p75 - p50,
      band_p95_minus_p75: p95 - p75,
    };
  });
}

const EGP_FORMATTER = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });

function formatEgp(value: number): string {
  if (Math.abs(value) >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(2)} M`;
  }
  if (Math.abs(value) >= 1_000) {
    return `${(value / 1_000).toFixed(0)} k`;
  }
  return EGP_FORMATTER.format(value);
}

/**
 * Day-16: cumulative-ROI fan chart.
 *
 * The fan chart is the visual answer to the homeowner's question
 * "when does this stop being a hole in my pocket?". The y-axis is the
 * running discounted balance of the project (negative immediately
 * after capex, ideally crossing zero somewhere in years 5–12, and
 * climbing into positive territory afterwards). The percentile
 * ribbons widen with time because uncertainty in degradation, weather
 * yield, tariff inflation and inverter cost compounds — that
 * widening *is* the contribution.
 *
 * The chart uses Recharts' stacked-area pattern: each ribbon is one
 * <Area /> with a width equal to the percentile gap. The lowest band
 * (p05) is drawn invisibly to lift the stack off the y-axis baseline.
 * A bold dashed median line and a vertical reference line at the
 * median payback year give the eye two anchors.
 *
 * A semantically labelled fallback ``<table>`` mirrors every datum
 * for screen readers — the brief's chart-accessibility rule.
 */
export function ROIFanChart({ trajectory, medianPaybackYear }: ROIFanChartProps) {
  const captionId = useId();
  const rows = useMemo(() => buildRows(trajectory), [trajectory]);

  const yMin = useMemo(
    () => Math.min(...rows.map((r) => r.p05)),
    [rows],
  );
  const yMax = useMemo(
    () => Math.max(...rows.map((r) => r.p95)),
    [rows],
  );

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-2xl font-semibold">
            Cumulative return — uncertainty fan
          </h3>
          <p className="mt-2 max-w-2xl text-sm text-ink-soft">
            How does the project's running net worth evolve, given the
            full ensemble of plausible futures? The dark line is the
            median trajectory; the dark ribbon is the middle 50% of
            simulations; the lighter ribbon is the 90% band. The fan
            widens with time because uncertainty compounds.
          </p>
          {medianPaybackYear !== null && Number.isFinite(medianPaybackYear) && (
            <p className="mt-2 text-sm text-ink">
              <span className="font-semibold">
                Median payback ≈ year {medianPaybackYear.toFixed(1)}
              </span>{' '}
              — the green line on the chart marks where the median
              trajectory crosses zero.
            </p>
          )}
        </div>
        <KnowMoreButton id="roi-fan" />
      </div>

      <div
        role="img"
        aria-label="Cumulative discounted cash-flow fan chart with median trajectory, IQR and 90% band"
        className="mt-6 h-80 w-full"
      >
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E5EA" vertical={false} />
            <XAxis
              dataKey="year"
              tickLine={false}
              axisLine={{ stroke: '#191A23' }}
              fontSize={12}
              label={{
                value: 'Year',
                position: 'insideBottom',
                offset: -2,
                style: { textAnchor: 'middle', fontSize: 12 },
              }}
            />
            <YAxis
              domain={[yMin, yMax]}
              tickLine={false}
              axisLine={{ stroke: '#191A23' }}
              fontSize={12}
              tickFormatter={(value: number) => formatEgp(value)}
              label={{
                value: 'EGP',
                angle: -90,
                position: 'insideLeft',
                style: { textAnchor: 'middle', fontSize: 12 },
              }}
            />
            <Tooltip
              cursor={{ stroke: '#191A23', strokeDasharray: '3 3' }}
              labelFormatter={(label) => `Year ${label}`}
              formatter={(value, name) => {
                const numeric = Number(value);
                const label = String(name);
                if (label.startsWith('band_')) return [null, null];
                return [`${formatEgp(numeric)} EGP`, label];
              }}
            />
            <ReferenceLine y={0} stroke="#191A23" strokeDasharray="4 4" />
            {medianPaybackYear !== null && Number.isFinite(medianPaybackYear) && (
              <ReferenceLine
                x={medianPaybackYear}
                stroke="#22C55E"
                strokeWidth={2}
                label={{
                  value: `Median payback ≈ year ${medianPaybackYear.toFixed(1)}`,
                  position: 'top',
                  fontSize: 11,
                  fill: '#22C55E',
                }}
              />
            )}
            <Area
              type="monotone"
              dataKey="band_p05"
              stackId="fan"
              stroke="transparent"
              fill="transparent"
              activeDot={false}
              isAnimationActive={false}
              legendType="none"
              name="band_p05"
            />
            <Area
              type="monotone"
              dataKey="band_p25_minus_p05"
              stackId="fan"
              stroke="transparent"
              fill="#E8FFD4"
              fillOpacity={0.9}
              activeDot={false}
              isAnimationActive={false}
              legendType="none"
              name="band_p25_minus_p05"
            />
            <Area
              type="monotone"
              dataKey="band_p50_minus_p25"
              stackId="fan"
              stroke="transparent"
              fill="#B9FF66"
              fillOpacity={0.9}
              activeDot={false}
              isAnimationActive={false}
              legendType="none"
              name="band_p50_minus_p25"
            />
            <Area
              type="monotone"
              dataKey="band_p75_minus_p50"
              stackId="fan"
              stroke="transparent"
              fill="#B9FF66"
              fillOpacity={0.9}
              activeDot={false}
              isAnimationActive={false}
              legendType="none"
              name="band_p75_minus_p50"
            />
            <Area
              type="monotone"
              dataKey="band_p95_minus_p75"
              stackId="fan"
              stroke="transparent"
              fill="#E8FFD4"
              fillOpacity={0.9}
              activeDot={false}
              isAnimationActive={false}
              legendType="none"
              name="band_p95_minus_p75"
            />
            <Line
              type="monotone"
              dataKey="p50"
              stroke="#191A23"
              strokeWidth={2.5}
              dot={false}
              isAnimationActive={false}
              name="Median (p50)"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <ul
        className="mt-4 flex flex-wrap items-center gap-4 text-xs text-ink-soft"
        aria-label="Legend"
      >
        <li className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="inline-block h-1.5 w-6 rounded bg-ink"
          />
          Median trajectory (p50)
        </li>
        <li className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="inline-block h-3 w-6 rounded border border-border bg-accent"
          />
          Interquartile band (p25–p75)
        </li>
        <li className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="inline-block h-3 w-6 rounded border border-border bg-accent-soft"
          />
          90% band (p05–p95)
        </li>
      </ul>

      <table className="sr-only" aria-describedby={captionId}>
        <caption id={captionId}>
          Cumulative discounted cash-flow trajectory percentiles, year by year (EGP)
        </caption>
        <thead>
          <tr>
            <th scope="col">Year</th>
            <th scope="col">p05</th>
            <th scope="col">p25</th>
            <th scope="col">p50 (median)</th>
            <th scope="col">p75</th>
            <th scope="col">p95</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.year}>
              <th scope="row">{row.year}</th>
              <td>{Math.round(row.p05).toLocaleString('en-US')}</td>
              <td>{Math.round(row.p25).toLocaleString('en-US')}</td>
              <td>{Math.round(row.p50).toLocaleString('en-US')}</td>
              <td>{Math.round(row.p75).toLocaleString('en-US')}</td>
              <td>{Math.round(row.p95).toLocaleString('en-US')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
