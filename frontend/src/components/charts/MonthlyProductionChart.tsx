import { useId } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Card } from '@/components/ui/Card';
import { KnowMoreButton } from '@/components/ui/KnowMoreButton';

const MONTH_LABELS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
] as const;

type MonthlyProductionChartProps = {
  /** 12 calendar-month AC totals (kWh) from the pvlib simulation. */
  pvlibMonthlyKwh: number[];
  /** 12 calendar-month AC totals (kWh) from the manual physics simulation. */
  manualMonthlyKwh: number[];
};

type Row = {
  month: (typeof MONTH_LABELS)[number];
  pvlib: number;
  manual: number;
  difference_kwh: number;
  difference_pct: number;
};

function buildRows(
  pvlib: number[],
  manual: number[],
): Row[] {
  return MONTH_LABELS.map((month, idx) => {
    const p = Number(pvlib[idx] ?? 0);
    const m = Number(manual[idx] ?? 0);
    const diff = m - p;
    const pct = p > 0 ? (diff / p) * 100 : 0;
    return {
      month,
      pvlib: Math.round(p),
      manual: Math.round(m),
      difference_kwh: Math.round(diff),
      difference_pct: pct,
    };
  });
}

function formatNumber(value: number): string {
  return Math.round(value).toLocaleString('en-US');
}

/**
 * Day-15: monthly AC-energy production chart.
 *
 * Renders the 12 monthly totals from both energy models (pvlib + manual)
 * as grouped bars so a reader can read the seasonal Cairo summer peak
 * directly off the axis. A semantically labelled fallback ``<table>`` is
 * always rendered (visually hidden via ``sr-only``) so screen-reader
 * users see the same numbers a sighted reader sees on the chart — the
 * brief's "All charts have a fallback ``<table>`` for screen readers"
 * accessibility rule.
 */
export function MonthlyProductionChart({
  pvlibMonthlyKwh,
  manualMonthlyKwh,
}: MonthlyProductionChartProps) {
  const rows = buildRows(pvlibMonthlyKwh, manualMonthlyKwh);
  const captionId = useId();

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-2xl font-semibold">Monthly production</h3>
          <p className="mt-2 text-sm text-ink-soft">
            Calendar-month AC energy delivered to the grid, January through
            December. Cairo's summer peak (June–August) is the seasonal
            shape every reasonable Egyptian PV simulation must reproduce.
          </p>
        </div>
        <KnowMoreButton id="monthly-production" />
      </div>

      <div
        role="img"
        aria-label="Monthly production bar chart comparing pvlib and the manual physics model"
        className="mt-6 h-72 w-full"
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E5EA" vertical={false} />
            <XAxis
              dataKey="month"
              tickLine={false}
              axisLine={{ stroke: '#191A23' }}
              fontSize={12}
            />
            <YAxis
              tickLine={false}
              axisLine={{ stroke: '#191A23' }}
              fontSize={12}
              tickFormatter={(value: number) => `${formatNumber(value)}`}
              label={{
                value: 'kWh',
                angle: -90,
                position: 'insideLeft',
                style: { textAnchor: 'middle', fontSize: 12 },
              }}
            />
            <Tooltip
              cursor={{ fill: '#F3F3F3' }}
              formatter={(value, name) => [
                `${formatNumber(Number(value))} kWh`,
                String(name) === 'pvlib' ? 'pvlib' : 'manual',
              ]}
            />
            <Legend />
            <Bar dataKey="pvlib" name="pvlib" fill="#191A23" radius={[6, 6, 0, 0]} />
            <Bar
              dataKey="manual"
              name="manual"
              fill="#B9FF66"
              stroke="#191A23"
              strokeWidth={1}
              radius={[6, 6, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <table className="sr-only" aria-describedby={captionId}>
        <caption id={captionId}>
          Monthly AC production (kWh) — pvlib vs. manual physics model
        </caption>
        <thead>
          <tr>
            <th scope="col">Month</th>
            <th scope="col">pvlib (kWh)</th>
            <th scope="col">manual (kWh)</th>
            <th scope="col">Δ (manual − pvlib, kWh)</th>
            <th scope="col">Δ (%)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.month}>
              <th scope="row">{row.month}</th>
              <td>{formatNumber(row.pvlib)}</td>
              <td>{formatNumber(row.manual)}</td>
              <td>{formatNumber(row.difference_kwh)}</td>
              <td>{row.difference_pct.toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
