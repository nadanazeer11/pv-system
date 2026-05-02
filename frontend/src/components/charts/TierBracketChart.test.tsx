import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { TierBracketChart } from './TierBracketChart';
import type { MonthlyBillBreakdown } from '@/types/api';

const TIER_PRICES = [0.58, 0.68, 0.83, 1.25, 1.40, 1.45, 1.55] as const;
const TIER_LABELS = [
  '0–50 kWh @ 0.58',
  '50–100 kWh @ 0.68',
  '100–200 kWh @ 0.83',
  '200–350 kWh @ 1.25',
  '350–650 kWh @ 1.40',
  '650–1,000 kWh @ 1.45',
  '> 1,000 kWh @ 1.55',
];

/**
 * Bill a single month under the EgyptERA marginal-tier schedule used
 * elsewhere in the project. Mirrors the backend kernel's logic so the
 * synthetic fixtures are economically realistic without going through
 * a network call.
 */
function billMonth(consumption: number, tierUppers: number[]): MonthlyBillBreakdown {
  const per_tier_kwh = TIER_PRICES.map(() => 0);
  const per_tier_egp = TIER_PRICES.map(() => 0);
  let remaining = consumption;
  let prev = 0;
  let highest = 0;
  TIER_PRICES.forEach((price, i) => {
    if (remaining <= 0) return;
    const capacity = tierUppers[i] - prev;
    const inBand = Math.min(remaining, capacity);
    per_tier_kwh[i] = inBand;
    per_tier_egp[i] = inBand * price;
    remaining -= inBand;
    prev = tierUppers[i];
    if (inBand > 0) highest = i;
  });
  const bill_egp = per_tier_egp.reduce((acc, v) => acc + v, 0);
  const marginal = consumption === 0 ? TIER_PRICES[0] : TIER_PRICES[highest];
  return {
    month_index: 1,
    consumption_kwh: consumption,
    bill_egp,
    per_tier_kwh,
    per_tier_egp,
    marginal_tariff_egp_per_kwh: marginal,
  };
}

const TIER_UPPERS = [50, 100, 200, 350, 650, 1000, 1.0e9];

function buildMonthly(consumption: number): MonthlyBillBreakdown[] {
  return Array.from({ length: 12 }, (_, m) => ({
    ...billMonth(consumption, TIER_UPPERS),
    month_index: m + 1,
  }));
}

const BEFORE = buildMonthly(500); // mid-Egyptian household, reaches tier 5
const AFTER = buildMonthly(150); // post-PV: lives in tier 3 most of the year

describe('TierBracketChart', () => {
  it('renders an sr-only fallback table with one row per tier plus a total', () => {
    render(
      <TierBracketChart
        monthlyBillBefore={BEFORE}
        monthlyBillAfter={AFTER}
        tierLabels={TIER_LABELS}
      />,
    );
    const caption = screen.getByText(/annual bill decomposition by egyptera tier/i);
    const table = caption.closest('table');
    expect(table).not.toBeNull();
    if (!table) return;
    const utils = within(table);
    // 7 tiers + 1 total row + 1 header row.
    expect(utils.getAllByRole('row')).toHaveLength(9);
    // Every tier label is rendered as a row header.
    for (const label of TIER_LABELS) {
      expect(utils.getByRole('rowheader', { name: label })).toBeInTheDocument();
    }
    // 500 kWh/month × 12 = 6,000 kWh annual without solar (total row).
    expect(utils.getByText('6,000')).toBeInTheDocument();
    // Annual savings 5,268 EGP appears in the totals row's saved column.
    expect(utils.getAllByText('5,268').length).toBeGreaterThanOrEqual(1);
    // Total before-EGP: 12 × 543.5 = 6,522.
    expect(utils.getByText('6,522')).toBeInTheDocument();
    // Total after-EGP: 12 × 104.5 = 1,254.
    expect(utils.getByText('1,254')).toBeInTheDocument();
  });

  it('exposes the chart container with a descriptive aria-label', () => {
    render(
      <TierBracketChart
        monthlyBillBefore={BEFORE}
        monthlyBillAfter={AFTER}
        tierLabels={TIER_LABELS}
      />,
    );
    expect(
      screen.getByRole('img', {
        name: /annual bill stacked by egyptera tier/i,
      }),
    ).toBeInTheDocument();
  });

  it('renders a KnowMore button wired to the tier-bracket-savings explainer', () => {
    render(
      <TierBracketChart
        monthlyBillBefore={BEFORE}
        monthlyBillAfter={AFTER}
        tierLabels={TIER_LABELS}
      />,
    );
    expect(
      screen.getByRole('button', { name: /know more/i }),
    ).toBeInTheDocument();
  });

  it('summarises annual savings and the share that comes off the top tier', () => {
    render(
      <TierBracketChart
        monthlyBillBefore={BEFORE}
        monthlyBillAfter={AFTER}
        tierLabels={TIER_LABELS}
      />,
    );
    // Annual savings = before-bill − after-bill.
    // 500 kWh under EgyptERA marginal: 50·0.58 + 50·0.68 + 100·0.83 +
    //   150·1.25 + 150·1.40 = 29 + 34 + 83 + 187.5 + 210 = 543.5/month.
    // 150 kWh: 50·0.58 + 50·0.68 + 50·0.83 = 29 + 34 + 41.5 = 104.5/month.
    // Annual delta = (543.5 − 104.5) × 12 = 5,268 EGP.
    expect(screen.getByText(/annual savings ≈ 5,268 egp/i)).toBeInTheDocument();
    // No tier-5 consumption survives in the "with solar" scenario, so
    // 100% of tier 5's annual EGP is saved. Tier 5 contributed
    // 150 kWh × 1.40 EGP × 12 = 2,520 EGP/yr. Share of total savings:
    // 2,520 / 5,268 ≈ 48%.
    expect(
      screen.getByText(/roughly 48% of that comes off the top tier/i),
    ).toBeInTheDocument();
  });

  it('falls back to "Tier N" labels when no schedule labels are passed', () => {
    render(
      <TierBracketChart
        monthlyBillBefore={BEFORE}
        monthlyBillAfter={AFTER}
      />,
    );
    const caption = screen.getByText(/annual bill decomposition by egyptera tier/i);
    const table = caption.closest('table');
    expect(table).not.toBeNull();
    if (!table) return;
    const utils = within(table);
    expect(utils.getByRole('rowheader', { name: 'Tier 1' })).toBeInTheDocument();
    expect(utils.getByRole('rowheader', { name: 'Tier 7' })).toBeInTheDocument();
  });

  it('hides the savings caption when before and after are identical (no PV)', () => {
    render(
      <TierBracketChart
        monthlyBillBefore={BEFORE}
        monthlyBillAfter={BEFORE}
        tierLabels={TIER_LABELS}
      />,
    );
    expect(screen.queryByText(/annual savings ≈/i)).not.toBeInTheDocument();
  });
});
