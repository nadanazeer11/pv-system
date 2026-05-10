import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LoadSizingPanel } from './LoadSizingPanel';

const LIBRARY = [
  {
    name: 'Air conditioner (1.5 ton split)',
    watts: 1500,
    typical_hours_per_day: 6,
    category: 'Cooling',
  },
  {
    name: 'Refrigerator (medium)',
    watts: 150,
    typical_hours_per_day: 10,
    category: 'Refrigeration',
  },
];

const RESULT_FITS = {
  daily_load_kwh: 9.0,
  monthly_load_kwh: 273.6,
  annual_load_kwh: 3285,
  peak_load_kw: 1.5,
  recommended_system_kw: 2.7,
  recommended_panel_count: 6,
  required_roof_area_m2: 16,
  coverage_fraction: 1.0,
  peak_sun_hours: 5.5,
  performance_ratio: 0.78,
  panel_rated_watts: 450,
  panel_area_m2: 1.8,
  roof_utilization_factor: 0.7,
  roof_fits: true,
  available_roof_area_m2: 100,
  roof_area_shortfall_m2: null,
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

describe('LoadSizingPanel', () => {
  beforeEach(() => {
    vi.useRealTimers();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('renders the empty-state placeholder when no appliance has been added', () => {
    mockFetchSequence([{ url: /\/api\/load-sizing\/library/, body: LIBRARY }]);
    renderWithClient(
      <LoadSizingPanel availableRoofAreaM2={null} />,
    );

    expect(
      screen.getByText(/add at least one appliance to compute a recommendation/i),
    ).toBeInTheDocument();
  });

  it('adds an appliance from the library and submits with the load profile', async () => {
    const { calls } = mockFetchSequence([
      { url: /\/api\/load-sizing\/library/, body: LIBRARY },
      { url: /\/api\/load-sizing$/, body: RESULT_FITS },
    ]);

    renderWithClient(<LoadSizingPanel availableRoofAreaM2={100} />);

    // Library loads asynchronously — the AC option appears after fetch.
    await waitFor(() =>
      expect(
        screen.getByRole('option', {
          name: /air conditioner \(1\.5 ton split\) \(1500 w\)/i,
        }),
      ).toBeInTheDocument(),
    );

    fireEvent.change(
      screen.getByLabelText(/choose an appliance from the library/i),
      { target: { value: 'Air conditioner (1.5 ton split)' } },
    );
    fireEvent.click(screen.getByRole('button', { name: /add from list/i }));

    fireEvent.click(screen.getByRole('button', { name: /recommend a system/i }));

    await waitFor(() =>
      expect(screen.getByTestId('load-sizing-result')).toBeInTheDocument(),
    );
    expect(screen.getByText(/recommended system: 2\.70 kw/i)).toBeInTheDocument();
    expect(screen.getByText(/fits your detected roof area/i)).toBeInTheDocument();

    const sizingCall = calls.find((c) => /\/api\/load-sizing$/.test(c.url));
    expect(sizingCall).toBeDefined();
    const body = sizingCall!.body as {
      appliances: Array<{ name: string; watts: number; hours_per_day: number; quantity: number }>;
      coverage_fraction: number;
      available_roof_area_m2: number;
    };
    expect(body.appliances).toHaveLength(1);
    expect(body.appliances[0].name).toBe('Air conditioner (1.5 ton split)');
    expect(body.appliances[0].watts).toBe(1500);
    expect(body.appliances[0].hours_per_day).toBe(6);
    expect(body.appliances[0].quantity).toBe(1);
    expect(body.coverage_fraction).toBe(1);
    expect(body.available_roof_area_m2).toBe(100);
  });

  it('warns when the recommended system is too big for the roof', async () => {
    mockFetchSequence([
      { url: /\/api\/load-sizing\/library/, body: LIBRARY },
      {
        url: /\/api\/load-sizing$/,
        body: { ...RESULT_FITS, roof_fits: false, roof_area_shortfall_m2: 25 },
      },
    ]);

    renderWithClient(<LoadSizingPanel availableRoofAreaM2={5} />);

    fireEvent.click(screen.getByRole('button', { name: /add custom/i }));
    fireEvent.change(screen.getByLabelText(/appliance name/i), {
      target: { value: 'Big AC' },
    });
    fireEvent.click(screen.getByRole('button', { name: /recommend a system/i }));

    await waitFor(() =>
      expect(screen.getByText(/your roof is/i)).toBeInTheDocument(),
    );
    expect(screen.getByText(/25 m²/)).toBeInTheDocument();
  });

  it('emits the recommended roof area when the user accepts the recommendation', async () => {
    mockFetchSequence([
      { url: /\/api\/load-sizing\/library/, body: LIBRARY },
      { url: /\/api\/load-sizing$/, body: RESULT_FITS },
    ]);

    const onAccept = vi.fn();
    renderWithClient(
      <LoadSizingPanel availableRoofAreaM2={null} onAcceptRecommendation={onAccept} />,
    );

    fireEvent.click(screen.getByRole('button', { name: /add custom/i }));
    fireEvent.change(screen.getByLabelText(/appliance name/i), {
      target: { value: 'My device' },
    });
    fireEvent.click(screen.getByRole('button', { name: /recommend a system/i }));

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /use this size in the estimate/i })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole('button', { name: /use this size in the estimate/i }));

    expect(onAccept).toHaveBeenCalledWith(RESULT_FITS.required_roof_area_m2);
  });
});
