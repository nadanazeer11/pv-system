import { useMutation } from '@tanstack/react-query';
import { request } from '@/lib/api';
import type { RoofDetectionRequest, RoofDetectionResult } from '@/types/api';

/**
 * ``POST /api/roof/detect`` — given a lat/lng, ask the backend for the
 * nearest OSM building footprint plus a primary-roof selection.
 *
 * Day 13 only consumes the cheap vector-side ``/detect`` endpoint to
 * draw the polygon over the Leaflet preview. The richer ``/analyze``
 * endpoint (with CV refinement and tilt/azimuth heuristics) is reserved
 * for the dashboard wiring on Day 14+.
 */
export function useRoofDetect() {
  return useMutation<RoofDetectionResult, Error, RoofDetectionRequest>({
    mutationKey: ['roof-detect'],
    mutationFn: (input) =>
      request<RoofDetectionResult>('/api/roof/detect', {
        method: 'POST',
        body: input,
      }),
  });
}
