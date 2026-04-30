import { useEffect, useMemo, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { KnowMoreButton } from '@/components/ui/KnowMoreButton';
import { useRoofDetect } from '@/hooks/useRoofDetect';
import type { Location } from '@/types/api';
import { AddressInput } from './AddressInput';
import { RoofMapPreview } from './RoofMapPreview';

type LocationPickerProps = {
  /**
   * Forwarded up to the parent estimator on every change so Day-14's
   * dashboard wiring can read the latest location without reaching into
   * this component's internals. Optional so the component is also
   * usable in isolation (and in tests) without forcing a callback.
   */
  onLocationChange?: (location: Location | null) => void;
  /**
   * ISO 3166-1 alpha-2 country bias for the address search. Defaults to
   * "eg" because the thesis is Egypt-focused; pass an empty string to
   * disable the bias.
   */
  geocoderCountryCodes?: string;
};

/**
 * Top-level location-input section combining:
 *
 *   1. ``AddressInput``     — free-text + Nominatim geocoder.
 *   2. ``RoofMapPreview``   — Leaflet map with a draggable pin.
 *   3. ``useRoofDetect``    — auto-fetch the OSM building footprint for
 *                             the chosen pin and overlay it on the map.
 *
 * The hierarchy intentionally keeps the *selected* location in a single
 * piece of state owned here. Both sub-components are presentational:
 * AddressInput emits a hit on click; the map emits a click on user
 * pin-drop. Either source updates the same state and triggers a roof-
 * detection refetch on the next debounce.
 */
export function LocationPicker({
  onLocationChange,
  geocoderCountryCodes = 'eg',
}: LocationPickerProps) {
  const [location, setLocation] = useState<Location | null>(null);
  const [pickedLabel, setPickedLabel] = useState<string | null>(null);
  const roofDetect = useRoofDetect();

  useEffect(() => {
    onLocationChange?.(location);
  }, [location, onLocationChange]);

  // Whenever a *new* location lands, ask the backend for the building
  // footprint at that pin. We don't gate this on user action because
  // the explicit affordance is the address search itself; once the user
  // has chosen a place, the polygon overlay is what they expect to see.
  useEffect(() => {
    if (!location) return;
    roofDetect.mutate({ location });
    // We intentionally exclude `roofDetect` from the deps: the mutation
    // object identity changes after each settle, which would re-fire
    // the request and produce a refetch loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location?.latitude, location?.longitude]);

  const primaryRoof = roofDetect.data?.primary_roof ?? null;

  const detectionStatus = useMemo(() => {
    if (!location) return null;
    if (roofDetect.isPending) return 'Looking up the building outline…';
    if (roofDetect.isError) {
      return `Roof lookup failed (${roofDetect.error.message}). The location is still selected — you can enter the area manually.`;
    }
    if (roofDetect.isSuccess) {
      if (primaryRoof) {
        return `Detected building: ${primaryRoof.area_m2.toFixed(0)} m² footprint (OpenStreetMap).`;
      }
      const note = roofDetect.data?.notes?.[0];
      return note
        ? `No building outline found at this pin. ${note}`
        : 'No building outline found at this pin. Drop a pin on the roof you want to estimate.';
    }
    return null;
  }, [location, roofDetect, primaryRoof]);

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-display text-2xl font-semibold">
              Where is your roof?
            </h3>
            <p className="mt-2 text-sm text-ink-soft">
              Type an address or click anywhere on the map to drop a pin. We use
              the pin to look up your roof on OpenStreetMap.
            </p>
          </div>
          <KnowMoreButton id="roof-detection" />
        </div>
        <div className="mt-6">
          <AddressInput
            countryCodes={geocoderCountryCodes || undefined}
            onSelect={(hit) => {
              setLocation({ latitude: hit.latitude, longitude: hit.longitude });
              setPickedLabel(hit.displayName);
            }}
          />
        </div>

        {location && (
          <dl className="mt-6 grid grid-cols-2 gap-3 rounded-card border-2 border-border bg-surface p-4 text-sm">
            <div>
              <dt className="font-display font-semibold uppercase tracking-wide text-ink-soft">
                Latitude
              </dt>
              <dd className="font-display text-base">
                {location.latitude.toFixed(5)}°
              </dd>
            </div>
            <div>
              <dt className="font-display font-semibold uppercase tracking-wide text-ink-soft">
                Longitude
              </dt>
              <dd className="font-display text-base">
                {location.longitude.toFixed(5)}°
              </dd>
            </div>
            {pickedLabel && (
              <div className="col-span-2">
                <dt className="font-display font-semibold uppercase tracking-wide text-ink-soft">
                  Address
                </dt>
                <dd className="text-ink">{pickedLabel}</dd>
              </div>
            )}
          </dl>
        )}

        {detectionStatus && (
          <p
            role={roofDetect.isError ? 'alert' : 'status'}
            className="mt-4 text-sm text-ink-soft"
          >
            {detectionStatus}
          </p>
        )}
      </Card>

      <div>
        <RoofMapPreview
          location={location}
          roof={primaryRoof}
          onLocationChange={(next) => {
            setLocation(next);
            setPickedLabel(null);
          }}
        />
        <p className="mt-2 text-xs text-ink-soft">
          Tip: the geocoder often points at a street, not a roof. Click the map to
          fine-tune.
        </p>
      </div>
    </div>
  );
}
