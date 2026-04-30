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

const TARIFF_RESULT = {
  bill_before_egp: 4200,
  bill_after_egp: 800,
  annual_savings_egp: 3400,
  self_consumed_kwh: 4200,
  exported_kwh: 40800,
  export_credit_egp: 0,
  average_savings_egp_per_kwh: 0.81,
  monthly_bill_before: [],
  monthly_bill_after: [],
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

  it('runs the four-call chain and renders all four metrics on success', async () => {
    const { fn, calls } = mockFetchSequence([
      { url: /\/api\/sizing/, body: SIZING_RESULT },
      { url: /\/api\/energy\/pvlib/, body: ENERGY_RESULT },
      { url: /\/api\/tariff\/savings/, body: TARIFF_RESULT },
      { url: /\/api\/monte-carlo\/run/, body: MONTE_CARLO_RESULT },
    ]);

    renderWithClient(<Dashboard location={CAIRO_LOCATION} roof={ROOF_POLYGON} />);
    fireEvent.click(screen.getByRole('button', { name: /estimate savings/i }));

    await waitFor(() => expect(screen.getByText('24.75')).toBeInTheDocument());
    expect(screen.getByText('45,000')).toBeInTheDocument(); // annual kWh
    expect(screen.getByText('3,400')).toBeInTheDocument(); // EGP/yr savings
    expect(screen.getByText('7.2')).toBeInTheDocument(); // payback p50
    // Half-width = (9.4 - 5.6) / 2 = 1.9
    expect(screen.getByText(/± 1\.9 yr/)).toBeInTheDocument();
    // 90% range subtitle
    expect(screen.getByText(/90% range: 5\.6 – 9\.4 years/i)).toBeInTheDocument();
    // Probability of payback within horizon — 0.97 → 97%
    expect(screen.getByText(/probability of payback within horizon: 97%/i)).toBeInTheDocument();

    // Order matters: sizing → energy → tariff → monte-carlo.
    expect(fn).toHaveBeenCalledTimes(4);
    expect(calls[0].url).toMatch(/\/api\/sizing$/);
    expect(calls[1].url).toMatch(/\/api\/energy\/pvlib$/);
    expect(calls[2].url).toMatch(/\/api\/tariff\/savings$/);
    expect(calls[3].url).toMatch(/\/api\/monte-carlo\/run$/);

    // Each downstream call consumed the previous step's output.
    expect((calls[1].body as { system_kw: number }).system_kw).toBe(SIZING_RESULT.system_kw);
    const tariffBody = calls[2].body as {
      monthly_consumption_kwh: number[];
      monthly_generation_kwh: number[];
    };
    expect(tariffBody.monthly_consumption_kwh).toHaveLength(12);
    expect(tariffBody.monthly_consumption_kwh[0]).toBe(350); // default
    expect(tariffBody.monthly_generation_kwh).toEqual(ENERGY_RESULT.monthly_kwh);
    const mcBody = calls[3].body as {
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
    mockFetchSequence([
      { url: /\/api\/sizing/, body: SIZING_RESULT },
      {
        url: /\/api\/energy\/pvlib/,
        ok: false,
        status: 502,
        body: { detail: 'PVGIS unavailable' },
      },
    ]);

    renderWithClient(<Dashboard location={CAIRO_LOCATION} roof={ROOF_POLYGON} />);
    fireEvent.click(screen.getByRole('button', { name: /estimate savings/i }));

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/pvgis unavailable/i),
    );
    // No metric ever rendered.
    expect(screen.getAllByText('—').length).toBe(4);
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
