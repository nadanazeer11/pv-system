import { useMutation } from '@tanstack/react-query';
import { request } from '@/lib/api';
import type { SizingRequest, SizingResult } from '@/types/api';

/**
 * `POST /api/sizing` — translate a roof area into a panel count and
 * system capacity. Modelled as a mutation rather than a query because
 * the call is user-triggered (form submit) and we want explicit control
 * over the loading/success/error states the UI surfaces.
 */
export function useSizing() {
  return useMutation<SizingResult, Error, SizingRequest>({
    mutationKey: ['sizing'],
    mutationFn: (input) =>
      request<SizingResult>('/api/sizing', {
        method: 'POST',
        body: input,
      }),
  });
}
