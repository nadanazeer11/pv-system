import { useId, useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Card } from '@/components/ui/Card';
import { KnowMoreButton } from '@/components/ui/KnowMoreButton';
import type { HistogramBins, MonteCarloPercentiles } from '@/types/api';

type MonteCarloHistogramProps = {
  histogram: HistogramBins;
  percentiles: MonteCarloPercentiles;
  /** Probability the project pays back within the analysis horizon. */
  paybackProbability: number;
  /** Total simulations the underlying ensemble was drawn from. */
  nSimulations: number;
};

type Row = {
  bin_label: string;
  bin_center: number;
  bin_lo: number;
  bin_hi: number;
  count: number;
};

function formatYear(value: number, fractionDigits = 1): string {
  return value.toFixed(fractionDigits);
}

function buildRows(histogram: HistogramBins): Row[] {
  const { bin_edges, counts } = histogram;
  return counts.map((count, i) => {
    const lo = Number(bin_edges[i] ?? 0);
    const hi = Number(bin_edges[i + 1] ?? lo);
    const center = (lo + hi) / 2;
    return {
      bin_label: `${formatYear(lo)}–${formatYear(hi)}`,
      bin_center: center,
      bin_lo: lo,
      bin_hi: hi,
      count,
    };
  });
}

/**
 * Day-16: histogram of payback-year outcomes from the Monte Carlo run.
 *
 * The histogram is the most direct visualisation of the simulation's
 * shape — the dashboard's headline payback card already shows the
 * median plus a 90 % band, but a single ± hides whether the
 * distribution is symmetric, fat-tailed, or bimodal. The histogram
 * exposes that shape; reference lines at p05, p50, and p95 anchor the
 * eye so a reader can map the headline number back onto the cloud.
 *
 * A semantically labelled fallback ``<table>`` is rendered (visually
 * hidden via ``sr-only``) so the same numbers reach screen-reader
 * users — the brief's "All charts have a fallback table" rule.
 */
export function MonteCarloHistogram({
  histogram,
  percentiles,
  paybackProbability,
  nSimulations,
}: MonteCarloHistogramProps) {
  const captionId = useId();
  const rows = useMemo(() => buildRows(histogram), [histogram]);
  const totalInHistogram = useMemo(
    () => rows.reduce((acc, row) => acc + row.count, 0),
    [rows],
  );
  const paybackPct = (paybackProbability * 100).toFixed(0);

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-2xl font-semibold">
            Payback distribution
          </h3>
          <p className="mt-2 max-w-2xl text-sm text-ink-soft">
            Each bar is the count of simulated futures whose payback year
            fell into that bracket. The median (p50) is the headline
            number; the bracket from p05 to p95 is the 90% band shown on
            the payback card. {paybackPct}% of simulations recover capex
            within the analysis horizon.
          </p>
        </div>
        <KnowMoreButton id="monte-carlo" />
      </div>

      <div
        role="img"
        aria-label="Monte Carlo payback histogram with p05, p50 and p95 reference lines"
        className="mt-6 h-72 w-full"
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E5EA" vertical={false} />
            <XAxis
              dataKey="bin_center"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickLine={false}
              axisLine={{ stroke: '#191A23' }}
              fontSize={12}
              tickFormatter={(value: number) => formatYear(value, 1)}
              label={{
                value: 'Payback year',
                position: 'insideBottom',
                offset: -2,
                style: { textAnchor: 'middle', fontSize: 12 },
              }}
            />
            <YAxis
              tickLine={false}
              axisLine={{ stroke: '#191A23' }}
              fontSize={12}
              allowDecimals={false}
              label={{
                value: 'Simulations',
                angle: -90,
                position: 'insideLeft',
                style: { textAnchor: 'middle', fontSize: 12 },
              }}
            />
            <Tooltip
              cursor={{ fill: '#F3F3F3' }}
              formatter={(value, _name, payload) => {
                const lo = payload?.payload?.bin_lo;
                const hi = payload?.payload?.bin_hi;
                const range =
                  typeof lo === 'number' && typeof hi === 'number'
                    ? `${formatYear(lo)}–${formatYear(hi)} yr`
                    : '';
                return [`${Number(value)} sims`, range];
              }}
            />
            <ReferenceLine
              x={percentiles.p05}
              stroke="#F59E0B"
              strokeDasharray="4 4"
              label={{ value: 'p05', position: 'top', fontSize: 11 }}
            />
            <ReferenceLine
              x={percentiles.p50}
              stroke="#191A23"
              strokeWidth={2}
              label={{ value: 'p50', position: 'top', fontSize: 11 }}
            />
            <ReferenceLine
              x={percentiles.p95}
              stroke="#F59E0B"
              strokeDasharray="4 4"
              label={{ value: 'p95', position: 'top', fontSize: 11 }}
            />
            <Bar dataKey="count" fill="#B9FF66" stroke="#191A23" strokeWidth={1} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-y-1 text-xs text-ink-soft sm:grid-cols-4">
        <dt>Median (p50)</dt>
        <dd className="text-right text-ink">{formatYear(percentiles.p50)} yr</dd>
        <dt>5th percentile</dt>
        <dd className="text-right text-ink">{formatYear(percentiles.p05)} yr</dd>
        <dt>95th percentile</dt>
        <dd className="text-right text-ink">{formatYear(percentiles.p95)} yr</dd>
        <dt>Simulations</dt>
        <dd className="text-right text-ink">
          {totalInHistogram.toLocaleString('en-US')} / {nSimulations.toLocaleString('en-US')}
        </dd>
      </dl>

      <table className="sr-only" aria-describedby={captionId}>
        <caption id={captionId}>
          Monte Carlo payback histogram — counts of simulations per payback-year bracket
        </caption>
        <thead>
          <tr>
            <th scope="col">Bracket (years)</th>
            <th scope="col">Simulations</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.bin_label}>
              <th scope="row">{row.bin_label}</th>
              <td>{row.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
