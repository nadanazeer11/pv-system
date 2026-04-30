/**
 * Nominatim (OpenStreetMap) forward-geocoding client.
 *
 * Why a dedicated module — and why client-side?
 * ---------------------------------------------
 * Nominatim is the *de facto* free forward-geocoder for OpenStreetMap
 * data and is already implicitly trusted elsewhere in the project (the
 * roof-detection backend pulls its building footprints from the same
 * dataset via Overpass). Going straight from the browser saves a hop
 * through our own server, keeps API keys out of the picture, and means
 * the thesis demo works with no extra deployment.
 *
 * Usage policy compliance
 * -----------------------
 * The OSMF Nominatim Usage Policy
 * (https://operations.osmfoundation.org/policies/nominatim/) requires:
 *   - ≤ 1 request / second per active user — enforced upstream by
 *     TanStack Query's ``staleTime`` + the user-driven submit pattern.
 *   - Meaningful Referer or User-Agent — the browser sets Referer
 *     automatically when called from this app.
 *   - Attribution displayed on the result — handled by the
 *     ``attribution`` string we return alongside each hit, surfaced in
 *     the AddressInput's result list.
 *
 * For production deployment the calls would move behind a server-side
 * proxy that adds a stable User-Agent and shares results across users;
 * doing so is out of scope for the thesis prototype.
 */

const NOMINATIM_BASE_URL = 'https://nominatim.openstreetmap.org';

const ATTRIBUTION_TEXT = '© OpenStreetMap contributors';

/** A single forward-geocoding hit, normalised to the shape we render. */
export type GeocodeHit = {
  /** Stable id ('osm_type:osm_id' if present, else display name). */
  id: string;
  /** Human-readable address line. */
  displayName: string;
  latitude: number;
  longitude: number;
  /** Always the OSMF attribution string — surfaced verbatim in the UI. */
  attribution: string;
};

export class GeocodeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'GeocodeError';
  }
}

type NominatimRecord = {
  place_id?: number;
  osm_type?: string;
  osm_id?: number;
  lat: string;
  lon: string;
  display_name: string;
};

/**
 * Forward-geocode a free-text address.
 *
 * @param query       Free-text address ("12 Tahrir Square, Cairo").
 * @param options.signal AbortSignal forwarded from the caller (TanStack
 *                    Query passes one when a query is cancelled).
 * @param options.countryCodes ISO 3166-1 alpha-2 codes to bias results,
 *                    e.g. "eg" — defaults to none, since the frontend
 *                    Brief calls out Egypt-focus but generalisability
 *                    is part of the academic contribution.
 * @param options.limit Max number of hits to return (Nominatim caps at 50).
 */
export async function searchAddress(
  query: string,
  options: { signal?: AbortSignal; countryCodes?: string; limit?: number } = {},
): Promise<GeocodeHit[]> {
  const trimmed = query.trim();
  if (trimmed.length === 0) {
    return [];
  }

  const params = new URLSearchParams({
    q: trimmed,
    format: 'jsonv2',
    addressdetails: '0',
    limit: String(options.limit ?? 5),
  });
  if (options.countryCodes && options.countryCodes.length > 0) {
    params.set('countrycodes', options.countryCodes);
  }

  const url = `${NOMINATIM_BASE_URL}/search?${params.toString()}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal: options.signal,
    });
  } catch (cause) {
    if ((cause as { name?: string }).name === 'AbortError') {
      throw cause;
    }
    throw new GeocodeError('Could not reach the OpenStreetMap geocoder.');
  }

  if (!response.ok) {
    throw new GeocodeError(
      `OpenStreetMap geocoder returned status ${response.status}.`,
    );
  }

  const records = (await response.json()) as NominatimRecord[];

  return records.map((record) => {
    const lat = Number.parseFloat(record.lat);
    const lon = Number.parseFloat(record.lon);
    const id =
      record.osm_type && record.osm_id
        ? `${record.osm_type}:${record.osm_id}`
        : `${record.place_id ?? record.display_name}`;
    return {
      id,
      displayName: record.display_name,
      latitude: lat,
      longitude: lon,
      attribution: ATTRIBUTION_TEXT,
    };
  });
}

export const NOMINATIM_ATTRIBUTION = ATTRIBUTION_TEXT;
