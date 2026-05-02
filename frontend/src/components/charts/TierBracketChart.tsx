import { useId, useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Card } from '@/components/ui/Card';
import { KnowMoreButton } from '@/components/ui/KnowMoreButton';
import type { MonthlyBillBreakdown } from '@/types/api';

type TierBracketChartProps = {
  /**
   * Twelve monthly bill breakdowns produced by the kernel for the
   * household *without* PV — each entry carries the per-tier kWh and
   * EGP decomposition.
   */
  monthlyBillBefore: MonthlyBillBreakdown[];
  /**
   * Twelve monthly bill breakdowns *after* the PV system has netted
   * down each month's consumption.
   */
  monthlyBillAfter: MonthlyBillBreakdown[];
  /**
   * Optional override of the tier upper-bound labels rendered in the
   * stacked-bar tooltip and the screen-reader table. When absent the
   * chart falls back to "Tier 1, Tier 2, …" labels — sufficient for
   * the visual story even before the schedule is plumbed through from
   * the backend.
   */
  tierLabels?: string[];
};

type StackRow = {
  /** "Without solar" or "With solar" — the x-axis category. */
  scenario: string;
  /** Annual EGP charged in each tier, indexed by tier order. */
  tier_egp: number[];
  /** Annual kWh consumed in each tier (used by the sr-only fallback). */
  tier_kwh: number[];
  /** Total EGP charged across all tiers in this scenario. */
  total_egp: number;
  /** Total kWh consumed across all tiers in this scenario. */
  total_kwh: number;
};

const EGP_FORMATTER = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });

function formatEgp(value: number): string {
  return EGP_FORMATTER.format(Math.round(value));
}

function formatKwh(value: number): string {
  return EGP_FORMATTER.format(Math.round(value));
}

function aggregateByTier(months: MonthlyBillBreakdown[]): {
  tier_egp: number[];
  tier_kwh: number[];
} {
  if (months.length === 0) {
    return { tier_egp: [], tier_kwh: [] };
  }
  const tierCount = Math.max(
    ...months.map((m) => Math.max(m.per_tier_egp.length, m.per_tier_kwh.length)),
  );
  const egp = Array.from({ length: tierCount }, () => 0);
  const kwh = Array.from({ length: tierCount }, () => 0);
  for (const month of months) {
    for (let i = 0; i < tierCount; i += 1) {
      egp[i] += Number(month.per_tier_egp[i] ?? 0);
      kwh[i] += Number(month.per_tier_kwh[i] ?? 0);
    }
  }
  return { tier_egp: egp, tier_kwh: kwh };
}

/**
 * Lime-on-dark seven-step palette that walks from the cheapest to the
 * priciest tier as the eye moves up the stack. The darkest band sits at
 * the top so the "saved EGP comes off the top tier first" story is
 * legible at a glance — the dark band is exactly what the PV system is
 * shaving off in the "With solar" bar.
 *
 * Falls back to the last colour for any extra tier the schedule may
 * gain in future EgyptERA reforms.
 */
const TIER_PALETTE = [
  '#E8FFD4',
  '#D4FF9E',
  '#B9FF66',
  '#7DC83D',
  '#4A8B1A',
  '#2D5410',
  '#191A23',
];

function tierColor(idx: number): string {
  return TIER_PALETTE[Math.min(idx, TIER_PALETTE.length - 1)] ?? '#191A23';
}

/**
 * Day-17: tier-bracket "before vs after" visualisation for Egypt's
 * progressive marginal tariff (Contribution B).
 *
 * Two stacked bars sit side by side. The left bar is the household's
 * annual bill *without* PV, decomposed by EgyptERA tier; the right bar
 * is the same bill *with* PV, after each month's generation has netted
 * down consumption. Both bars are stacked from cheapest tier (bottom)
 * to most expensive (top), so the visual story — that PV erases the
 * top tier first, before chipping away at the cheap tiers — is exactly
 * the story Contribution B is making.
 *
 * A semantically labelled fallback ``<table>`` is rendered (visually
 * hidden via ``sr-only``) so the same per-tier numbers reach screen-
 * reader users — the brief's "All charts have a fallback table"
 * accessibility rule.
 */
export function TierBracketChart({
  monthlyBillBefore,
  monthlyBillAfter,
  tierLabels,
}: TierBracketChartProps) {
  const captionId = useId();

  const before = useMemo(
    () => aggregateByTier(monthlyBillBefore),
    [monthlyBillBefore],
  );
  const after = useMemo(
    () => aggregateByTier(monthlyBillAfter),
    [monthlyBillAfter],
  );

  const tierCount = Math.max(before.tier_egp.length, after.tier_egp.length);

  const labels = useMemo(() => {
    if (tierLabels && tierLabels.length >= tierCount) {
      return tierLabels.slice(0, tierCount);
    }
    return Array.from({ length: tierCount }, (_, i) => `Tier ${i + 1}`);
  }, [tierLabels, tierCount]);

  const rows: StackRow[] = useMemo(() => {
    const padded = (arr: number[]): number[] => {
      const out = arr.slice(0, tierCount);
      while (out.length < tierCount) out.push(0);
      return out;
    };
    const beforeRow: StackRow = {
      scenario: 'Without solar',
      tier_egp: padded(before.tier_egp),
      tier_kwh: padded(before.tier_kwh),
      total_egp: before.tier_egp.reduce((acc, v) => acc + v, 0),
      total_kwh: before.tier_kwh.reduce((acc, v) => acc + v, 0),
    };
    const afterRow: StackRow = {
      scenario: 'With solar',
      tier_egp: padded(after.tier_egp),
      tier_kwh: padded(after.tier_kwh),
      total_egp: after.tier_egp.reduce((acc, v) => acc + v, 0),
      total_kwh: after.tier_kwh.reduce((acc, v) => acc + v, 0),
    };
    return [beforeRow, afterRow];
  }, [before, after, tierCount]);

  // Recharts stacks series whose ``stackId`` matches; flatten the per-
  // tier arrays into one named field per tier so each can be its own
  // <Bar /> in the chart and its own column in the sr-only table.
  const chartData = useMemo(() => {
    return rows.map((row) => {
      const flat: Record<string, string | number> = { scenario: row.scenario };
      labels.forEach((_label, i) => {
        flat[`tier_${i}_egp`] = row.tier_egp[i] ?? 0;
      });
      return flat;
    });
  }, [rows, labels]);

  const totalSavings = rows[0].total_egp - rows[1].total_egp;
  // The highest tier that the *household actually uses* without PV.
  // That tier — not the schedule's absolute "and above" tail — is the
  // one a homeowner thinks of as their "top tier", and it is the tier
  // PV erodes first under marginal billing. Falls back to the schedule
  // top if no tier has positive consumption (zero-bill household).
  const topTierIdx = useMemo(() => {
    for (let i = tierCount - 1; i >= 0; i -= 1) {
      if ((rows[0].tier_kwh[i] ?? 0) > 0) return i;
    }
    return tierCount - 1;
  }, [rows, tierCount]);
  const topTierBefore = rows[0].tier_egp[topTierIdx] ?? 0;
  const topTierAfter = rows[1].tier_egp[topTierIdx] ?? 0;
  const topTierShaveEgp = Math.max(0, topTierBefore - topTierAfter);
  const topTierShareOfSavingsPct =
    totalSavings > 0
      ? Math.min(100, Math.round((topTierShaveEgp / totalSavings) * 100))
      : 0;

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-2xl font-semibold">
            Tier-bracket savings — before vs after
          </h3>
          <p className="mt-2 max-w-2xl text-sm text-ink-soft">
            Egypt's residential bill is split into progressive price
            steps. The left bar is your annual bill split by step
            without solar; the right bar is the same bill once solar
            has netted each month down. Each layer of the stack is one
            step, with the cheapest at the bottom and the priciest at
            the top — which is where solar takes its biggest bite.
          </p>
          {totalSavings > 0 && (
            <p className="mt-2 text-sm text-ink">
              <span className="font-semibold">
                Annual savings ≈ {formatEgp(totalSavings)} EGP
              </span>
              {topTierShareOfSavingsPct > 0 && (
                <>
                  {' '}— roughly {topTierShareOfSavingsPct}% of that comes off the
                  top tier (the priciest step).
                </>
              )}
            </p>
          )}
        </div>
        <KnowMoreButton id="tier-bracket-savings" />
      </div>

      <div
        role="img"
        aria-label="Annual bill stacked by EgyptERA tier — without solar versus with solar"
        className="mt-6 h-80 w-full"
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            margin={{ top: 8, right: 16, bottom: 8, left: 0 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#E5E5EA"
              vertical={false}
            />
            <XAxis
              dataKey="scenario"
              tickLine={false}
              axisLine={{ stroke: '#191A23' }}
              fontSize={12}
            />
            <YAxis
              tickLine={false}
              axisLine={{ stroke: '#191A23' }}
              fontSize={12}
              tickFormatter={(value: number) => formatEgp(value)}
              label={{
                value: 'EGP / year',
                angle: -90,
                position: 'insideLeft',
                style: { textAnchor: 'middle', fontSize: 12 },
              }}
            />
            <Tooltip
              cursor={{ fill: '#F3F3F3' }}
              labelFormatter={(label) => String(label)}
              formatter={(value, name) => {
                const numeric = Number(value);
                const key = String(name);
                const match = key.match(/^tier_(\d+)_egp$/);
                if (!match) return [`${formatEgp(numeric)} EGP`, key];
                const idx = Number(match[1]);
                return [`${formatEgp(numeric)} EGP`, labels[idx] ?? key];
              }}
            />
            {labels.map((_label, i) => (
              <Bar
                key={i}
                dataKey={`tier_${i}_egp`}
                stackId="bill"
                fill={tierColor(i)}
                stroke="#191A23"
                strokeWidth={1}
                name={labels[i]}
                isAnimationActive={false}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>

      <ul
        className="mt-4 flex flex-wrap items-center gap-3 text-xs text-ink-soft"
        aria-label="Tier legend"
      >
        {labels.map((label, i) => (
          <li key={label} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className="inline-block h-3 w-6 rounded border border-border"
              style={{ backgroundColor: tierColor(i) }}
            />
            {label}
          </li>
        ))}
      </ul>

      <table className="sr-only" aria-describedby={captionId}>
        <caption id={captionId}>
          Annual bill decomposition by EgyptERA tier — without solar vs.
          with solar (EGP and kWh per tier)
        </caption>
        <thead>
          <tr>
            <th scope="col">Tier</th>
            <th scope="col">Without solar — kWh / year</th>
            <th scope="col">Without solar — EGP / year</th>
            <th scope="col">With solar — kWh / year</th>
            <th scope="col">With solar — EGP / year</th>
            <th scope="col">EGP saved in tier</th>
          </tr>
        </thead>
        <tbody>
          {labels.map((label, i) => {
            const beforeKwh = rows[0].tier_kwh[i] ?? 0;
            const beforeEgp = rows[0].tier_egp[i] ?? 0;
            const afterKwh = rows[1].tier_kwh[i] ?? 0;
            const afterEgp = rows[1].tier_egp[i] ?? 0;
            const saved = beforeEgp - afterEgp;
            return (
              <tr key={label}>
                <th scope="row">{label}</th>
                <td>{formatKwh(beforeKwh)}</td>
                <td>{formatEgp(beforeEgp)}</td>
                <td>{formatKwh(afterKwh)}</td>
                <td>{formatEgp(afterEgp)}</td>
                <td>{formatEgp(saved)}</td>
              </tr>
            );
          })}
          <tr>
            <th scope="row">Total</th>
            <td>{formatKwh(rows[0].total_kwh)}</td>
            <td>{formatEgp(rows[0].total_egp)}</td>
            <td>{formatKwh(rows[1].total_kwh)}</td>
            <td>{formatEgp(rows[1].total_egp)}</td>
            <td>{formatEgp(totalSavings)}</td>
          </tr>
        </tbody>
      </table>
    </Card>
  );
}
