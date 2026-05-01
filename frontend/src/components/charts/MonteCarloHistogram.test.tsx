import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MonteCarloHistogram } from './MonteCarloHistogram';
import type { HistogramBins, MonteCarloPercentiles } from '@/types/api';

const HISTOGRAM: HistogramBins = {
  bin_edges: [4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
  counts: [12, 41, 113, 207, 87, 40],
};

const PERCENTILES: MonteCarloPercentiles = {
  mean: 7.1,
  std: 1.0,
  p05: 5.4,
  p10: 5.7,
  p25: 6.4,
  p50: 7.0,
  p75: 7.8,
  p90: 8.4,
  p95: 8.7,
  minimum: 4.2,
  maximum: 9.8,
};

describe('MonteCarloHistogram', () => {
  it('renders an sr-only fallback table with one row per bin', () => {
    render(
      <MonteCarloHistogram
        histogram={HISTOGRAM}
        percentiles={PERCENTILES}
        paybackProbability={0.97}
        nSimulations={1000}
      />,
    );
    const caption = screen.getByText(/monte carlo payback histogram/i);
    const table = caption.closest('table');
    expect(table).not.toBeNull();
    if (!table) return;
    const utils = within(table);
    // 6 bins → 6 body rows + 1 header row.
    expect(utils.getAllByRole('row')).toHaveLength(7);
    expect(utils.getByText('4.0–5.0')).toBeInTheDocument();
    expect(utils.getByText('9.0–10.0')).toBeInTheDocument();
    // Bin counts.
    expect(utils.getByText('207')).toBeInTheDocument();
  });

  it('exposes the chart container with a descriptive aria-label', () => {
    render(
      <MonteCarloHistogram
        histogram={HISTOGRAM}
        percentiles={PERCENTILES}
        paybackProbability={0.97}
        nSimulations={1000}
      />,
    );
    expect(
      screen.getByRole('img', { name: /monte carlo payback histogram/i }),
    ).toBeInTheDocument();
  });

  it('renders a KnowMore button wired to the monte-carlo explainer', () => {
    render(
      <MonteCarloHistogram
        histogram={HISTOGRAM}
        percentiles={PERCENTILES}
        paybackProbability={0.97}
        nSimulations={1000}
      />,
    );
    expect(screen.getByRole('button', { name: /know more/i })).toBeInTheDocument();
  });

  it('shows the payback probability as a percentage in the description', () => {
    render(
      <MonteCarloHistogram
        histogram={HISTOGRAM}
        percentiles={PERCENTILES}
        paybackProbability={0.973}
        nSimulations={1000}
      />,
    );
    expect(screen.getByText(/97% of simulations recover capex/i)).toBeInTheDocument();
  });

  it('summarises the median, p05, p95, and total simulations in the caption strip', () => {
    render(
      <MonteCarloHistogram
        histogram={HISTOGRAM}
        percentiles={PERCENTILES}
        paybackProbability={0.97}
        nSimulations={1000}
      />,
    );
    // The bins sum to 500; the ensemble was drawn from 1,000 sims —
    // both numbers must be readable.
    expect(screen.getByText(/500 \/ 1,000/)).toBeInTheDocument();
    expect(screen.getByText('7.0 yr')).toBeInTheDocument();
    expect(screen.getByText('5.4 yr')).toBeInTheDocument();
    expect(screen.getByText('8.7 yr')).toBeInTheDocument();
  });
});
