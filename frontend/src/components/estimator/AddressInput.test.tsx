import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AddressInput } from './AddressInput';

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const FAKE_HITS = [
  {
    osm_type: 'way',
    osm_id: 12345,
    place_id: 1,
    lat: '30.0444',
    lon: '31.2357',
    display_name: 'Tahrir Square, Cairo, Egypt',
  },
];

describe('AddressInput', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('searches Nominatim and renders the returned hits', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => FAKE_HITS,
    });

    const onSelect = vi.fn();
    renderWithClient(<AddressInput onSelect={onSelect} />);

    fireEvent.change(screen.getByLabelText(/address or place name/i), {
      target: { value: 'Tahrir Square' },
    });
    fireEvent.click(screen.getByRole('button', { name: /find on map/i }));

    const hit = await screen.findByRole('button', {
      name: /tahrir square, cairo/i,
    });
    fireEvent.click(hit);

    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({
        latitude: 30.0444,
        longitude: 31.2357,
        displayName: 'Tahrir Square, Cairo, Egypt',
      }),
    );
  });

  it('shows a no-results message when the geocoder returns nothing', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => [],
    });

    renderWithClient(<AddressInput onSelect={() => {}} />);

    fireEvent.change(screen.getByLabelText(/address or place name/i), {
      target: { value: 'somewhere' },
    });
    fireEvent.click(screen.getByRole('button', { name: /find on map/i }));

    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent(/no matches found/i),
    );
  });

  it('renders an alert when the geocoder errors out', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({}),
    });

    renderWithClient(<AddressInput onSelect={() => {}} />);

    fireEvent.change(screen.getByLabelText(/address or place name/i), {
      target: { value: 'somewhere' },
    });
    fireEvent.click(screen.getByRole('button', { name: /find on map/i }));

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/could not search the map/i),
    );
  });

  it('does nothing when the query is empty whitespace', () => {
    renderWithClient(<AddressInput onSelect={() => {}} />);

    fireEvent.change(screen.getByLabelText(/address or place name/i), {
      target: { value: '   ' },
    });
    fireEvent.click(screen.getByRole('button', { name: /find on map/i }));

    expect(globalThis.fetch).not.toHaveBeenCalled();
  });
});
