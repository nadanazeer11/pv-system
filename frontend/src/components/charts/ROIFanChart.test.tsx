import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { ROIFanChart } from './ROIFanChart';
import type { CumulativeCashFlowTrajectory } from '@/types/api';

function buildTrajectory(years: number): CumulativeCashFlowTrajectory {
  const year_index = Array.from({ length: years + 1 }, (_, i) => i);
  // Synthetic monotonic trajectory: a plausible 25-year ROI fan.
  const p50 = year_index.map((y) => -150_000 + y * 25_000);
  const p25 = p50.map((v) => v - 10_000);
  const p05 = p50.map((v) => v - 30_000);
  const p75 = p50.map((v) => v + 10_000);
  const p95 = p50.map((v) => v + 30_000);
  const mean = p50;
  return { year_index, p05, p25, p50, p75, p95, mean };
}

const TRAJECTORY = buildTrajectory(25);

describe('ROIFanChart', () => {
  it('renders an sr-only fallback table with one row per year in year_index', () => {
    render(<ROIFanChart trajectory={TRAJECTORY} medianPaybackYear={6.0} />);
    const caption = screen.getByText(/cumulative discounted cash-flow trajectory/i);
    const table = caption.closest('table');
    expect(table).not.toBeNull();
    if (!table) return;
    const utils = within(table);
    // 26 body rows (years 0..25) + 1 header row.
    expect(utils.getAllByRole('row')).toHaveLength(27);
    // Year-0 capex value: p50 = -150,000.
    expect(utils.getByText('-150,000')).toBeInTheDocument();
    // Year-25 horizon median: p50 = -150,000 + 25 * 25,000 = 475,000.
    expect(utils.getByText('475,000')).toBeInTheDocument();
  });

  it('exposes the chart container with a descriptive aria-label', () => {
    render(<ROIFanChart trajectory={TRAJECTORY} medianPaybackYear={6.0} />);
    expect(
      screen.getByRole('img', { name: /cumulative discounted cash-flow fan chart/i }),
    ).toBeInTheDocument();
  });

  it('renders a KnowMore button wired to the roi-fan explainer', () => {
    render(<ROIFanChart trajectory={TRAJECTORY} medianPaybackYear={6.0} />);
    expect(screen.getByRole('button', { name: /know more/i })).toBeInTheDocument();
  });

  it('omits the payback reference line label when median payback is null', () => {
    render(<ROIFanChart trajectory={TRAJECTORY} medianPaybackYear={null} />);
    expect(screen.queryByText(/Median payback ≈/)).not.toBeInTheDocument();
  });

  it('includes the payback reference label when a finite median payback is given', () => {
    render(<ROIFanChart trajectory={TRAJECTORY} medianPaybackYear={6.0} />);
    expect(screen.getByText(/Median payback ≈ year 6\.0/)).toBeInTheDocument();
  });
});
