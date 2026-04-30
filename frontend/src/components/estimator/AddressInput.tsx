import { useId, useState } from 'react';
import { PrimaryButton } from '@/components/ui/Button';
import { useGeocode } from '@/hooks/useGeocode';
import { NOMINATIM_ATTRIBUTION, type GeocodeHit } from '@/lib/nominatim';

type AddressInputProps = {
  /** Called when the user picks one of the geocoder hits. */
  onSelect: (hit: GeocodeHit) => void;
  /**
   * Optional ISO 3166-1 alpha-2 country bias (e.g. "eg"). The estimator
   * passes "eg" because the thesis is Egypt-focused; tests omit it to
   * exercise the generic path.
   */
  countryCodes?: string;
  initialQuery?: string;
};

/**
 * Free-text address field with an OpenStreetMap-Nominatim search.
 *
 * The component owns:
 * - the current text the user has typed,
 * - the most recent search results (rendered as a keyboard-navigable
 *   list of buttons),
 * - the search request lifecycle (idle / loading / error / no-results).
 *
 * It does **not** own the selected location — that lives in the parent
 * (LocationPicker) so the same selection can drive both the map preview
 * and any downstream sizing/dashboard cards.
 */
export function AddressInput({
  onSelect,
  countryCodes,
  initialQuery = '',
}: AddressInputProps) {
  const inputId = useId();
  const listId = useId();
  const [query, setQuery] = useState(initialQuery);
  const geocode = useGeocode();

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = query.trim();
    if (trimmed.length === 0) {
      return;
    }
    geocode.mutate({ query: trimmed, countryCodes });
  };

  const hits = geocode.data ?? [];
  const showEmptyResults = geocode.isSuccess && hits.length === 0;

  return (
    <div>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label
            htmlFor={inputId}
            className="block font-display text-sm font-semibold text-ink"
          >
            Address or place name
          </label>
          <p id={`${inputId}-hint`} className="mt-1 text-xs text-ink-soft">
            Try a full street address or a landmark — e.g. "Tahrir Square, Cairo".
          </p>
          <input
            id={inputId}
            type="search"
            autoComplete="off"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-describedby={`${inputId}-hint`}
            aria-controls={listId}
            className="mt-2 block w-full rounded-card border-2 border-border bg-bg px-4 py-3 font-body text-base focus:outline-none"
          />
        </div>
        <PrimaryButton type="submit" disabled={geocode.isPending}>
          {geocode.isPending ? 'Searching…' : 'Find on map'}
        </PrimaryButton>
        {geocode.isError && (
          <p role="alert" className="text-sm text-danger">
            Could not search the map ({geocode.error.message}). Try again in a moment.
          </p>
        )}
        {showEmptyResults && (
          <p role="status" className="text-sm text-ink-soft">
            No matches found. Try adding the city name, or drop a pin on the map below.
          </p>
        )}
      </form>

      {hits.length > 0 && (
        <div className="mt-4">
          <p className="font-display text-sm font-semibold uppercase tracking-wide text-ink-soft">
            Pick a match
          </p>
          <ul
            id={listId}
            role="list"
            className="mt-2 divide-y-2 divide-border rounded-card border-2 border-border bg-bg"
          >
            {hits.map((hit) => (
              <li key={hit.id}>
                <button
                  type="button"
                  onClick={() => onSelect(hit)}
                  className="block w-full px-4 py-3 text-left text-sm hover:bg-surface focus-visible:bg-surface"
                >
                  <span className="font-display font-semibold text-ink">
                    {hit.displayName}
                  </span>
                  <span className="mt-1 block text-xs text-ink-soft">
                    {hit.latitude.toFixed(5)}°, {hit.longitude.toFixed(5)}°
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-ink-soft">{NOMINATIM_ATTRIBUTION}</p>
        </div>
      )}
    </div>
  );
}
