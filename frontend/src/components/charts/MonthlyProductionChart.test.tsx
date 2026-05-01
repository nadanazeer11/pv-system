import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MonthlyProductionChart } from './MonthlyProductionChart';

const PVLIB_MONTHS = [3500, 3300, 3800, 4000, 4200, 4300, 4400, 4300, 4000, 3700, 3300, 3200];
const MANUAL_MONTHS = [3450, 3250, 3700, 3950, 4150, 4200, 4300, 4200, 3950, 3650, 3250, 3150];

describe('MonthlyProductionChart', () => {
  it('renders a screen-reader fallback table with all 12 months', () => {
    render(
      <MonthlyProductionChart
        pvlibMonthlyKwh={PVLIB_MONTHS}
        manualMonthlyKwh={MANUAL_MONTHS}
      />,
    );

    const caption = screen.getByText(
      /monthly ac production .* pvlib vs\. manual/i,
    );
    const table = caption.closest('table');
    expect(table).not.toBeNull();
    if (!table) return;
    const utils = within(table);
    expect(utils.getByText('Jan')).toBeInTheDocument();
    expect(utils.getByText('Dec')).toBeInTheDocument();
    // pvlib January value (3,500) is unique in the table.
    expect(utils.getByText('3,500')).toBeInTheDocument();
    // manual January value (3,450) is unique in the table.
    expect(utils.getByText('3,450')).toBeInTheDocument();
    // Differences repeat across months — assert at least one '-50' (Jan).
    expect(utils.getAllByText('-50').length).toBeGreaterThan(0);
  });

  it('exposes the chart container with a descriptive aria-label', () => {
    render(
      <MonthlyProductionChart
        pvlibMonthlyKwh={PVLIB_MONTHS}
        manualMonthlyKwh={MANUAL_MONTHS}
      />,
    );
    expect(
      screen.getByRole('img', { name: /monthly production bar chart comparing pvlib/i }),
    ).toBeInTheDocument();
  });

  it('shows a KnowMore button for the monthly-production explainer', () => {
    render(
      <MonthlyProductionChart
        pvlibMonthlyKwh={PVLIB_MONTHS}
        manualMonthlyKwh={MANUAL_MONTHS}
      />,
    );
    expect(screen.getByRole('button', { name: /know more/i })).toBeInTheDocument();
  });

  it('handles short input arrays defensively (zero-fills missing months)', () => {
    render(
      <MonthlyProductionChart
        pvlibMonthlyKwh={[3500]}
        manualMonthlyKwh={[3450]}
      />,
    );
    const caption = screen.getByText(/monthly ac production/i);
    const table = caption.closest('table');
    expect(table).not.toBeNull();
    if (!table) return;
    const utils = within(table);
    // 12 rows still rendered.
    expect(utils.getAllByRole('row')).toHaveLength(13); // 12 body + 1 header
  });
});
