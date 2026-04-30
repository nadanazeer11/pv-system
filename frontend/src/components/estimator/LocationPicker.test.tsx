import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Replace the real Leaflet preview with a tiny presentational stub so
// the LocationPicker test stays focused on the state-orchestration
// logic. The stub exposes the props as data-attributes and a button so
// we can assert that a click on the map updates the picker's state.
vi.mock('./RoofMapPreview', () => ({
  RoofMapPreview: ({
    location,
    roof,
    onLocationChange,
  }: {
    location: { latitude: number; longitude: number } | null;
    roof: { area_m2: number } | null;
    onLocationChange?: (loc: { latitude: number; longitude: number }) => void;
  }) => (
    <div
      data-testid="roof-map-preview"
      data-lat={location?.latitude ?? ''}
      data-lng={location?.longitude ?? ''}
      data-roof-area={roof?.area_m2 ?? ''}
    >
      <button
        type="button"
        onClick={() => onLocationChange?.({ latitude: 31.0, longitude: 32.0 })}
      >
        click-map
      </button>
    </div>
  ),
}));

import { LocationPicker } from './LocationPicker';

const NOMINATIM_HIT = {
  osm_type: 'way',
  osm_id: 99,
  place_id: 1,
  lat: '30.0444',
  lon: '31.2357',
  display_name: 'Tahrir Square, Cairo, Egypt',
};

const ROOF_RESULT = {
  query: { latitude: 30.0444, longitude: 31.2357 },
  primary_roof: {
    osm_way_id: 12345,
    coordinates_lat_lng: [
      [30.0444, 31.2357],
      [30.0445, 31.2358],
      [30.0444, 31.2359],
      [30.0444, 31.2357],
    ],
    area_m2: 87.5,
    perimeter_m: 36,
    centroid: { latitude: 30.0444, longitude: 31.2358 },
    contains_query_point: true,
    distance_to_query_point_m: 0,
    tags: { building: 'residential' },
  },
  candidates: [],
  search_radius_m: 50,
  satellite_tile_url: null,
  meters_per_pixel: null,
  detection_source: 'osm-overpass',
  notes: [],
  segmentation_polygon_lat_lng: null,
  segmentation_area_m2: null,
  segmentation_confidence: null,
  estimated_tilt_deg: null,
  estimated_tilt_source: null,
  estimated_azimuth_deg: null,
  estimated_azimuth_source: null,
};

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function mockFetchSequence(
  responses: Array<{ url: RegExp; body: unknown; ok?: boolean; status?: number }>,
) {
  const fn = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input.toString();
    const match = responses.find((r) => r.url.test(url));
    if (!match) {
      throw new Error(`Unexpected fetch URL: ${url}`);
    }
    return {
      ok: match.ok ?? true,
      status: match.status ?? 200,
      json: async () => match.body,
    } as Response;
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}

describe('LocationPicker', () => {
  beforeEach(() => {
    vi.useRealTimers();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('selecting a geocoder hit fires /api/roof/detect and surfaces the result', async () => {
    mockFetchSequence([
      { url: /nominatim\.openstreetmap\.org\/search/, body: [NOMINATIM_HIT] },
      { url: /\/api\/roof\/detect/, body: ROOF_RESULT },
    ]);

    const onLocationChange = vi.fn();
    renderWithClient(<LocationPicker onLocationChange={onLocationChange} />);

    fireEvent.change(screen.getByLabelText(/address or place name/i), {
      target: { value: 'Tahrir Square' },
    });
    fireEvent.click(screen.getByRole('button', { name: /find on map/i }));

    const hit = await screen.findByRole('button', {
      name: /tahrir square, cairo/i,
    });
    fireEvent.click(hit);

    await waitFor(() =>
      expect(screen.getByText(/detected building: 88 m²/i)).toBeInTheDocument(),
    );
    // The selected lat/lng appears both in the hit-list and in the
    // dl summary card — assert at least one of each is rendered.
    expect(screen.getAllByText(/30\.04440°/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/31\.23570°/).length).toBeGreaterThan(0);
    // The parent receives the latest selected location.
    expect(onLocationChange).toHaveBeenCalledWith({
      latitude: 30.0444,
      longitude: 31.2357,
    });
  });

  it('clicking the map updates the selected pin and triggers a detect call', async () => {
    const fetchMock = mockFetchSequence([
      { url: /\/api\/roof\/detect/, body: { ...ROOF_RESULT, primary_roof: null, notes: ['no buildings'] } },
    ]);

    renderWithClient(<LocationPicker />);

    fireEvent.click(screen.getByRole('button', { name: /click-map/i }));

    await waitFor(() =>
      expect(screen.getByText(/no building outline found/i)).toBeInTheDocument(),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/roof/detect'),
      expect.objectContaining({ method: 'POST' }),
    );
    expect(screen.getByText(/31\.00000°/)).toBeInTheDocument();
    expect(screen.getByText(/32\.00000°/)).toBeInTheDocument();
  });

  it('renders an inline error when /api/roof/detect fails', async () => {
    mockFetchSequence([
      {
        url: /\/api\/roof\/detect/,
        ok: false,
        status: 502,
        body: { detail: 'OSM Overpass fetch failed' },
      },
    ]);

    renderWithClient(<LocationPicker />);
    fireEvent.click(screen.getByRole('button', { name: /click-map/i }));

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/roof lookup failed/i),
    );
  });
});
