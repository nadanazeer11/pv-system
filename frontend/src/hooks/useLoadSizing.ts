import { useMutation, useQuery } from '@tanstack/react-query';
import { request } from '@/lib/api';
import { APPLIANCE_LIBRARY_FALLBACK } from '@/content/applianceLibrary';
import type {
  ApplianceLibraryEntry,
  LoadSizingRequest,
  LoadSizingResult,
} from '@/types/api';

/**
 * Fetch the seeded Egyptian residential appliance library so the UI
 * can offer a "pick from list" entry point. Cached for the session —
 * the library is config-static.
 *
 * `initialData` seeds the cache with the static frontend mirror so the
 * dropdown is populated on first render and remains usable when the
 * backend is unreachable; the API call refreshes the list silently
 * once it resolves.
 */
export function useApplianceLibrary() {
  return useQuery<ApplianceLibraryEntry[], Error>({
    queryKey: ['appliance-library'],
    queryFn: () => request<ApplianceLibraryEntry[]>('/api/load-sizing/library'),
    initialData: APPLIANCE_LIBRARY_FALLBACK,
    staleTime: Infinity,
  });
}

/**
 * Run the load-driven sizing recommendation. Mutation rather than a
 * query because the user explicitly clicks "compute" — we don't want
 * to fire requests on every keystroke into the appliance editor.
 */
export function useLoadSizing() {
  return useMutation<LoadSizingResult, Error, LoadSizingRequest>({
    mutationKey: ['load-sizing'],
    mutationFn: (input) =>
      request<LoadSizingResult>('/api/load-sizing', {
        method: 'POST',
        body: input,
      }),
  });
}
