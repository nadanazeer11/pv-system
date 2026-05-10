import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Dashboard } from './Dashboard';
import type { Location, RoofPolygon } from '@/types/api';

const CAIRO_LOCATION: Location = { latitude: 30.0444, longitude: 31.2357 };

const ROOF_POLYGON: RoofPolygon = {
  osm_way_id: 12345,
  coordinates_lat_lng: [
    [30.0444, 31.2357],
    [30.0445, 31.2358],
    [30.0444, 31.2359],
    [30.0444, 31.2357],
  ],
  area_m2: 142.6,
  perimeter_m: 50,
  centroid: { latitude: 30.0444, longitude: 31.2358 },
  contains_query_point: true,
  distance_to_query_point_m: 0,
  tags: { building: 'residential' },
};

const SIZING_RESULT = {
  roof_area_m2: 143,
  usable_roof_area_m2: 100.1,
  panel_count: 55,
  system_kw: 24.75,
  panel_rated_watts: 450,
  panel_area_m2: 1.8,
  roof_utilization_factor: 0.7,
  panel_density_w_per_m2: 250,
};

const ENERGY_RESULT = {
  annual_kwh: 45000,
  monthly_kwh: [3500, 3300, 3800, 4000, 4200, 4300, 4400, 4300, 4000, 3700, 3300, 3200],
  specific_yield_kwh_per_kwp: 1818,
  capacity_factor: 0.207,
  performance_ratio: 0.81,
  poa_annual_kwh_per_m2: 2200,
  mean_cell_temp_c: 38,
  system_kw: 24.75,
  tilt_deg: 26,
  azimuth_deg: 180,
  inverter_efficiency: 0.96,
  system_losses_fraction: 0.14,
};

const ENERGY_MANUAL_RESULT = {
  model: 'manual' as const,
  annual_kwh: 44100, // ~2% lower than pvlib — strong agreement
  monthly_kwh: [3450, 3250, 3700, 3950, 4150, 4200, 4300, 4200, 3950, 3650, 3250, 3150],
  specific_yield_kwh_per_kwp: 1782,
  capacity_factor: 0.203,
  performance_ratio: 0.80,
  poa_annual_kwh_per_m2: 2210,
  mean_cell_temp_c: 39,
  system_kw: 24.75,
  tilt_deg: 26,
  azimuth_deg: 180,
  inverter_efficiency: 0.96,
  system_losses_fraction: 0.14,
};

function billMonth(consumption: number) {
  // Mirror of the EgyptERA marginal-tier kernel so the dashboard test
  // exercises the tier-bracket chart with realistic per-tier numbers
  // without round-tripping through the backend.
  const uppers = [50, 100, 200, 350, 650, 1000, 1.0e9];
  const prices = [0.58, 0.68, 0.83, 1.25, 1.40, 1.45, 1.55];
  const per_tier_kwh = prices.map(() => 0);
  const per_tier_egp = prices.map(() => 0);
  let remaining = consumption;
  let prev = 0;
  let highest = 0;
  prices.forEach((price, i) => {
    if (remaining <= 0) return;
    const cap = uppers[i] - prev;
    const inBand = Math.min(remaining, cap);
    per_tier_kwh[i] = inBand;
    per_tier_egp[i] = inBand * price;
    remaining -= inBand;
    prev = uppers[i];
    if (inBand > 0) highest = i;
  });
  const bill_egp = per_tier_egp.reduce((acc, v) => acc + v, 0);
  return {
    consumption_kwh: consumption,
    bill_egp,
    per_tier_kwh,
    per_tier_egp,
    marginal_tariff_egp_per_kwh: consumption === 0 ? prices[0] : prices[highest],
  };
}

const TARIFF_RESULT = {
  bill_before_egp: 12 * billMonth(500).bill_egp,
  bill_after_egp: 12 * billMonth(150).bill_egp,
  annual_savings_egp: 12 * (billMonth(500).bill_egp - billMonth(150).bill_egp),
  self_consumed_kwh: 4200,
  exported_kwh: 40800,
  export_credit_egp: 0,
  average_savings_egp_per_kwh: 0.81,
  monthly_bill_before: Array.from({ length: 12 }, (_, m) => ({
    month_index: m + 1,
    ...billMonth(500),
  })),
  monthly_bill_after: Array.from({ length: 12 }, (_, m) => ({
    month_index: m + 1,
    ...billMonth(150),
  })),
};

const MONTE_CARLO_RESULT = {
  n_simulations: 1000,
  payback_years: {
    mean: 7.4,
    std: 1.1,
    p05: 5.6,
    p10: 6.0,
    p25: 6.7,
    p50: 7.2,
    p75: 8.1,
    p90: 8.9,
    p95: 9.4,
    minimum: 5.0,
    maximum: 11.0,
  },
  npv_egp: {
    mean: 100000,
    std: 20000,
    p05: 60000,
    p10: 70000,
    p25: 85000,
    p50: 100000,
    p75: 115000,
    p90: 130000,
    p95: 140000,
    minimum: 40000,
    maximum: 160000,
  },
  lcoe_egp_per_kwh: {
    mean: 0.5,
    std: 0.05,
    p05: 0.4,
    p10: 0.42,
    p25: 0.46,
    p50: 0.5,
    p75: 0.54,
    p90: 0.58,
    p95: 0.6,
    minimum: 0.35,
    maximum: 0.65,
  },
  lifetime_savings_egp: {
    mean: 200000,
    std: 30000,
    p05: 150000,
    p10: 160000,
    p25: 180000,
    p50: 200000,
    p75: 220000,
    p90: 240000,
    p95: 250000,
    minimum: 130000,
    maximum: 270000,
  },
  payback_probability: 0.97,
  positive_npv_probability: 1.0,
  payback_histogram: { bin_edges: [5, 6, 7, 8, 9, 10], counts: [50, 200, 400, 250, 100] },
  npv_histogram: { bin_edges: [40000, 80000, 120000, 160000], counts: [100, 700, 200] },
  cumulative_cash_flow_trajectory: {
    year_index: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    p05: [-200000, -180000, -160000, -140000, -120000, -100000, -80000, -60000, -40000, -20000, 0],
    p25: [-180000, -160000, -140000, -120000, -100000, -80000, -60000, -40000, -20000, 0, 20000],
    p50: [-150000, -130000, -110000, -90000, -70000, -50000, -30000, -10000, 10000, 30000, 50000],
    p75: [-120000, -100000, -80000, -60000, -40000, -20000, 0, 20000, 40000, 60000, 80000],
    p95: [-100000, -80000, -60000, -40000, -20000, 0, 20000, 40000, 60000, 80000, 100000],
    mean: [-150000, -130000, -110000, -90000, -70000, -50000, -30000, -10000, 10000, 30000, 50000],
  },
  system_kw: 24.75,
  annual_kwh: 45000,
  tariff_egp_per_kwh: 0.81,
  analysis_period_years: 25,
  discount_rate: 0.04,
  random_seed: 42,
};

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

type FetchSpec = {
  url: RegExp;
  body: unknown;
  ok?: boolean;
  status?: number;
};

function mockFetchSequence(responses: FetchSpec[]) {
  const calls: Array<{ url: string; body: unknown }> = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString();
    const match = responses.find((r) => r.url.test(url));
    if (!match) {
      throw new Error(`Unexpected fetch URL: ${url}`);
    }
    let parsed: unknown = undefined;
    if (init?.body && typeof init.body === 'string') {
      try {
        parsed = JSON.parse(init.body);
      } catch {
        parsed = init.body;
      }
    }
    calls.push({ url, body: parsed });
    return {
      ok: match.ok ?? true,
      status: match.status ?? 200,
      json: async () => match.body,
    } as Response;
  });
  vi.stubGlobal('fetch', fn);
  return { fn, calls };
}

describe('Dashboard', () => {
  beforeEach(() => {
    vi.useRealTimers();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('renders four placeholder cards with KnowMore buttons before any estimate', () => {
    renderWithClient(<Dashboard location={CAIRO_LOCATION} roof={null} />);

    expect(screen.getByText(/system size/i)).toBeInTheDocument();
    expect(screen.getByText(/annual generation/i)).toBeInTheDocument();
    expect(screen.getByText(/annual savings/i)).toBeInTheDocument();
    expect(screen.getByText(/payback period/i)).toBeInTheDocument();

    // One KnowMore per card.
    expect(screen.getAllByRole('button', { name: /know more/i }).length).toBe(4);
    // No real number rendered yet — every card shows the em-dash placeholder.
    expect(screen.getAllByText('—').length).toBe(4);
    // Day-15 model-comparison section is hidden until an estimate has run.
    expect(screen.queryByTestId('model-comparison-section')).not.toBeInTheDocument();
    // Day-16 monte-carlo section is also hidden in the placeholder state.
    expect(screen.queryByTestId('monte-carlo-section')).not.toBeInTheDocument();
    // Day-17 tier-bracket section is also hidden until an estimate runs.
    expect(screen.queryByTestId('tier-bracket-section')).not.toBeInTheDocument();
  });

  it('disables the submit button until a location is supplied', () => {
    renderWithClient(<Dashboard location={null} roof={null} />);

    const submit = screen.getByRole('button', { name: /estimate savings/i });
    expect(submit).toBeDisabled();
    expect(screen.getByText(/pick a place on the map first/i)).toBeInTheDocument();
  });

  it('pre-fills the roof area from a fresh OSM detection', () => {
    renderWithClient(<Dashboard location={CAIRO_LOCATION} roof={ROOF_POLYGON} />);
    const input = screen.getByLabelText(/roof area/i) as HTMLInputElement;
    // 142.6 → rounded to 143
    expect(input.value).toBe('143');
    expect(
      screen.getByText(/we pre-filled the roof area from the building outline \(143 m²\)/i),
    ).toBeInTheDocument();
  });

  it('runs the five-call chain and renders all four metrics on success', async () => {
    const { fn, calls } = mockFetchSequence([
      // The LoadSizingPanel auto-fetches the appliance library on mount.
      // It is independent of the estimate chain — we mock it so the
      // unmatched-URL guard does not fire, then filter library calls out
      // of the chain-order assertions below.
      { url: /\/api\/load-sizing\/library/, body: [] },
      { url: /\/api\/sizing/, body: SIZING_RESULT },
      { url: /\/api\/energy\/pvlib/, body: ENERGY_RESULT },
      { url: /\/api\/energy\/manual/, body: ENERGY_MANUAL_RESULT },
      { url: /\/api\/tariff\/savings/, body: TARIFF_RESULT },
      { url: /\/api\/monte-carlo\/run/, body: MONTE_CARLO_RESULT },
    ]);

    renderWithClient(<Dashboard location={CAIRO_LOCATION} roof={ROOF_POLYGON} />);
    fireEvent.click(screen.getByRole('button', { name: /estimate savings/i }));

    await waitFor(() => expect(screen.getByText('24.75')).toBeInTheDocument());
    // pvlib annual_kwh appears in both the MetricCard and the
    // comparison panel — the latter is Day 15's new surface, so we
    // assert on multiplicity rather than uniqueness.
    expect(screen.getAllByText('45,000').length).toBeGreaterThanOrEqual(1);
    // Annual savings: 12 × (543.5 − 104.5) = 5,268 EGP under the
    // EgyptERA marginal-tier schedule used in the test fixture. The
    // number appears both on the headline savings card and inside the
    // Day-17 tier-bracket chart caption, so we assert on multiplicity.
    expect(screen.getAllByText('5,268').length).toBeGreaterThanOrEqual(1); // EGP/yr savings
    expect(screen.getByText('7.2')).toBeInTheDocument(); // payback p50
    // Half-width = (9.4 - 5.6) / 2 = 1.9
    expect(screen.getByText(/± 1\.9 yr/)).toBeInTheDocument();
    // 90% range subtitle
    expect(screen.getByText(/90% range: 5\.6 – 9\.4 years/i)).toBeInTheDocument();
    // Probability of payback within horizon — 0.97 → 97%
    expect(screen.getByText(/probability of payback within horizon: 97%/i)).toBeInTheDocument();

    // Day-15 model-comparison section now visible with both annuals.
    expect(screen.getByTestId('model-comparison-section')).toBeInTheDocument();
    expect(screen.getByText(/why two energy models\?/i)).toBeInTheDocument();
    expect(screen.getByText('44,100')).toBeInTheDocument(); // manual annual_kwh
    // Residual = 44,100 − 45,000 = −900 (-2.0%) — strong agreement.
    expect(screen.getByText('-900')).toBeInTheDocument();
    expect(screen.getByText(/strong agreement/i)).toBeInTheDocument();
    // Monthly chart is mounted with its KnowMore button.
    expect(screen.getByText(/monthly production/i)).toBeInTheDocument();

    // Day-16 monte-carlo section is also visible — both the histogram
    // and the ROI fan chart, each with its own KnowMore explainer.
    expect(screen.getByTestId('monte-carlo-section')).toBeInTheDocument();
    expect(screen.getByText(/payback distribution/i)).toBeInTheDocument();
    expect(screen.getByText(/cumulative return — uncertainty fan/i)).toBeInTheDocument();
    // Reference label on the fan chart anchors the median payback year.
    expect(screen.getByText(/median payback ≈ year 7\.2/i)).toBeInTheDocument();

    // Day-17 tier-bracket section is mounted with its own card title
    // and KnowMore explainer. Annual-savings caption mirrors the
    // headline number computed from the EgyptERA-marginal fixture.
    expect(screen.getByTestId('tier-bracket-section')).toBeInTheDocument();
    expect(
      screen.getByText(/tier-bracket savings — before vs after/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/annual savings ≈ 5,268 egp/i),
    ).toBeInTheDocument();

    // Day-15: five calls in the estimate chain (sizing, then pvlib +
    // manual in parallel, then tariff, then monte-carlo). pvlib and
    // manual may arrive in either order on the wire, but both must
    // appear before tariff. The LoadSizingPanel's appliance-library
    // fetch is independent and is filtered out before chain-order
    // assertions.
    const chain = calls.filter((c) => !/\/api\/load-sizing\/library/.test(c.url));
    expect(chain.length).toBe(5);
    expect(fn).toHaveBeenCalledTimes(5 + (calls.length - chain.length));
    expect(chain[0].url).toMatch(/\/api\/sizing$/);
    const energyUrls = [chain[1].url, chain[2].url].sort();
    expect(energyUrls[0]).toMatch(/\/api\/energy\/manual$/);
    expect(energyUrls[1]).toMatch(/\/api\/energy\/pvlib$/);
    expect(chain[3].url).toMatch(/\/api\/tariff\/savings$/);
    expect(chain[4].url).toMatch(/\/api\/monte-carlo\/run$/);

    // Both energy calls inherited system_kw from sizing.
    expect((chain[1].body as { system_kw: number }).system_kw).toBe(SIZING_RESULT.system_kw);
    expect((chain[2].body as { system_kw: number }).system_kw).toBe(SIZING_RESULT.system_kw);

    const tariffBody = chain[3].body as {
      monthly_consumption_kwh: number[];
      monthly_generation_kwh: number[];
    };
    expect(tariffBody.monthly_consumption_kwh).toHaveLength(12);
    expect(tariffBody.monthly_consumption_kwh[0]).toBe(350); // default
    // Tariff still uses pvlib's monthly profile — pvlib remains canonical
    // for downstream tariff / Monte Carlo on Day 15.
    expect(tariffBody.monthly_generation_kwh).toEqual(ENERGY_RESULT.monthly_kwh);
    const mcBody = chain[4].body as {
      system_kw: number;
      annual_kwh: number;
      tariff_egp_per_kwh: number;
      random_seed: number;
    };
    expect(mcBody.annual_kwh).toBe(ENERGY_RESULT.annual_kwh);
    expect(mcBody.tariff_egp_per_kwh).toBe(TARIFF_RESULT.average_savings_egp_per_kwh);
    expect(mcBody.random_seed).toBe(42);
  });

  it('surfaces an inline error when the chain aborts', async () => {
    // pvlib fails; manual is configured to succeed but its result is
    // discarded because Promise.all rejects on the first failure. We
    // include the manual mock so the test does not depend on which of
    // the two parallel calls happens to reject first.
    mockFetchSequence([
      { url: /\/api\/load-sizing\/library/, body: [] },
      { url: /\/api\/sizing/, body: SIZING_RESULT },
      {
        url: /\/api\/energy\/pvlib/,
        ok: false,
        status: 502,
        body: { detail: 'PVGIS unavailable' },
      },
      { url: /\/api\/energy\/manual/, body: ENERGY_MANUAL_RESULT },
    ]);

    renderWithClient(<Dashboard location={CAIRO_LOCATION} roof={ROOF_POLYGON} />);
    fireEvent.click(screen.getByRole('button', { name: /estimate savings/i }));

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/pvgis unavailable/i),
    );
    // No metric ever rendered.
    expect(screen.getAllByText('—').length).toBe(4);
    // Day-15 comparison section never mounted.
    expect(screen.queryByTestId('model-comparison-section')).not.toBeInTheDocument();
    // Day-16 monte-carlo section is also gated on a successful chain.
    expect(screen.queryByTestId('monte-carlo-section')).not.toBeInTheDocument();
    // Day-17 tier-bracket section is also gated on a successful chain.
    expect(screen.queryByTestId('tier-bracket-section')).not.toBeInTheDocument();
  });

  it('lets the user override the pre-filled roof area', () => {
    renderWithClient(<Dashboard location={CAIRO_LOCATION} roof={ROOF_POLYGON} />);
    const input = screen.getByLabelText(/roof area/i) as HTMLInputElement;
    expect(input.value).toBe('143');
    fireEvent.change(input, { target: { value: '90' } });
    expect(input.value).toBe('90');
    // Even if a "newer" detection lands afterwards, the user override
    // wins — the auto-fill effect is gated on `userEditedArea`.
    // Re-render with the same roof prop to simulate that:
    renderWithClient(<Dashboard location={CAIRO_LOCATION} roof={ROOF_POLYGON} />);
    // The first instance still shows '90'; the second is a fresh tree at 143.
    const inputs = screen.getAllByLabelText(/roof area/i) as HTMLInputElement[];
    expect(inputs[0].value).toBe('90');
    expect(inputs[1].value).toBe('143');
  });
});
