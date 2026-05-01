import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ModelComparisonView } from './ModelComparisonView';
import type { EnergyManualResult, EnergyPvlibResult } from '@/types/api';

function makePvlib(annual: number, overrides: Partial<EnergyPvlibResult> = {}): EnergyPvlibResult {
  return {
    annual_kwh: annual,
    monthly_kwh: Array.from({ length: 12 }, () => annual / 12),
    specific_yield_kwh_per_kwp: annual / 25,
    capacity_factor: 0.21,
    performance_ratio: 0.81,
    poa_annual_kwh_per_m2: 2200,
    mean_cell_temp_c: 38,
    system_kw: 25,
    tilt_deg: 26,
    azimuth_deg: 180,
    inverter_efficiency: 0.96,
    system_losses_fraction: 0.14,
    ...overrides,
  };
}

function makeManual(annual: number, overrides: Partial<EnergyManualResult> = {}): EnergyManualResult {
  return {
    model: 'manual',
    annual_kwh: annual,
    monthly_kwh: Array.from({ length: 12 }, () => annual / 12),
    specific_yield_kwh_per_kwp: annual / 25,
    capacity_factor: 0.20,
    performance_ratio: 0.80,
    poa_annual_kwh_per_m2: 2210,
    mean_cell_temp_c: 39,
    system_kw: 25,
    tilt_deg: 26,
    azimuth_deg: 180,
    inverter_efficiency: 0.96,
    system_losses_fraction: 0.14,
    ...overrides,
  };
}

describe('ModelComparisonView', () => {
  it('renders both annual totals and a signed residual', () => {
    render(<ModelComparisonView pvlib={makePvlib(45000)} manual={makeManual(44100)} />);
    expect(screen.getByText('45,000')).toBeInTheDocument();
    expect(screen.getByText('44,100')).toBeInTheDocument();
    // residual = -900, displayed with explicit minus sign.
    expect(screen.getByText('-900')).toBeInTheDocument();
    // residual_pct = -900 / 45000 = -2.0%
    expect(screen.getByText(/\(-2\.0%\)/)).toBeInTheDocument();
  });

  it('classifies < 5% disagreement as strong agreement', () => {
    render(<ModelComparisonView pvlib={makePvlib(45000)} manual={makeManual(44100)} />);
    expect(screen.getByText(/strong agreement/i)).toBeInTheDocument();
  });

  it('classifies 5–10% disagreement as reasonable', () => {
    // 45000 * 0.93 = 41850 → -7%
    render(<ModelComparisonView pvlib={makePvlib(45000)} manual={makeManual(41850)} />);
    expect(screen.getByText(/reasonable agreement/i)).toBeInTheDocument();
  });

  it('flags > 10% disagreement as material divergence', () => {
    // 45000 * 0.85 = 38250 → -15%
    render(<ModelComparisonView pvlib={makePvlib(45000)} manual={makeManual(38250)} />);
    expect(screen.getByText(/material divergence/i)).toBeInTheDocument();
  });

  it('exposes a model-comparison KnowMore button', () => {
    render(<ModelComparisonView pvlib={makePvlib(45000)} manual={makeManual(44100)} />);
    expect(screen.getByRole('button', { name: /know more/i })).toBeInTheDocument();
  });

  it('renders a positive residual with an explicit plus sign', () => {
    render(<ModelComparisonView pvlib={makePvlib(40000)} manual={makeManual(40500)} />);
    expect(screen.getByText('+500')).toBeInTheDocument();
  });
});
