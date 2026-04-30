import { useMutation } from '@tanstack/react-query';
import { searchAddress, type GeocodeHit } from '@/lib/nominatim';

export type GeocodeInput = {
  query: string;
  countryCodes?: string;
};

/**
 * Forward-geocode a free-text address via OpenStreetMap Nominatim.
 *
 * Modelled as a mutation rather than a query because the call is
 * user-triggered (search button submit), and we want fine-grained
 * control over the loading / success / error / empty-result states the
 * UI surfaces. The country-code bias is left optional so the same hook
 * powers both the Egypt-focused estimator and any future broader use.
 */
export function useGeocode() {
  return useMutation<GeocodeHit[], Error, GeocodeInput>({
    mutationKey: ['geocode'],
    mutationFn: ({ query, countryCodes }) =>
      searchAddress(query, { countryCodes }),
  });
}
