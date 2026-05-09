import { useMemo, useState } from 'react';
import { AccentButton, PrimaryButton } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { useApplianceLibrary, useLoadSizing } from '@/hooks/useLoadSizing';
import type { ApplianceEntry, ApplianceLibraryEntry } from '@/types/api';

type LoadSizingPanelProps = {
  /**
   * Optional roof area from the upstream OSM detection / annotation.
   * When supplied the recommendation reports whether the system fits.
   */
  availableRoofAreaM2: number | null;
  /**
   * Called when the user accepts the recommendation. The dashboard
   * uses the suggested roof area to pre-fill its area input so the
   * downstream estimate runs against the load-derived sizing.
   */
  onAcceptRecommendation?: (suggestedRoofAreaM2: number) => void;
};

type DraftAppliance = ApplianceEntry & { id: string };

const COVERAGE_OPTIONS = [
  { value: 1.0, label: 'Full offset (100%)' },
  { value: 0.75, label: '75% of load' },
  { value: 0.5, label: 'Half (50%)' },
  { value: 0.25, label: 'A quarter (25%)' },
];

let draftIdCounter = 0;
function nextDraftId(): string {
  draftIdCounter += 1;
  return `draft-${draftIdCounter}`;
}

function fromLibrary(entry: ApplianceLibraryEntry): DraftAppliance {
  return {
    id: nextDraftId(),
    name: entry.name,
    watts: entry.watts,
    hours_per_day: entry.typical_hours_per_day,
    quantity: 1,
  };
}

function blankAppliance(): DraftAppliance {
  return {
    id: nextDraftId(),
    name: '',
    watts: 100,
    hours_per_day: 1,
    quantity: 1,
  };
}

function formatNumber(value: number, fractionDigits = 0): string {
  return value.toLocaleString('en-US', {
    maximumFractionDigits: fractionDigits,
    minimumFractionDigits: fractionDigits,
  });
}

export function LoadSizingPanel({
  availableRoofAreaM2,
  onAcceptRecommendation,
}: LoadSizingPanelProps) {
  const library = useApplianceLibrary();
  const sizing = useLoadSizing();

  const [draft, setDraft] = useState<DraftAppliance[]>([]);
  const [coverage, setCoverage] = useState<number>(1.0);
  const [librarySelection, setLibrarySelection] = useState<string>('');
  const [acceptedAreaM2, setAcceptedAreaM2] = useState<number | null>(null);

  const groupedLibrary = useMemo(() => {
    if (!library.data) return [];
    const buckets = new Map<string, ApplianceLibraryEntry[]>();
    for (const entry of library.data) {
      const list = buckets.get(entry.category) ?? [];
      list.push(entry);
      buckets.set(entry.category, list);
    }
    return Array.from(buckets.entries()).map(([category, entries]) => ({
      category,
      entries,
    }));
  }, [library.data]);

  const handleAddFromLibrary = () => {
    if (!library.data || !librarySelection) return;
    const entry = library.data.find((e) => e.name === librarySelection);
    if (!entry) return;
    setDraft((prev) => [...prev, fromLibrary(entry)]);
    setLibrarySelection('');
  };

  const handleAddBlank = () => {
    setDraft((prev) => [...prev, blankAppliance()]);
  };

  const handleRemove = (id: string) => {
    setDraft((prev) => prev.filter((entry) => entry.id !== id));
  };

  const handleChange = <K extends keyof ApplianceEntry>(
    id: string,
    field: K,
    value: ApplianceEntry[K],
  ) => {
    setDraft((prev) =>
      prev.map((entry) =>
        entry.id === id ? { ...entry, [field]: value } : entry,
      ),
    );
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (draft.length === 0) return;
    sizing.mutate({
      appliances: draft.map(({ id: _id, ...rest }) => rest),
      coverage_fraction: coverage,
      ...(availableRoofAreaM2 !== null && {
        available_roof_area_m2: availableRoofAreaM2,
      }),
    });
  };

  const result = sizing.data;
  const formValid = draft.every(
    (entry) =>
      entry.name.trim().length > 0 &&
      entry.watts > 0 &&
      entry.hours_per_day >= 0 &&
      entry.hours_per_day <= 24 &&
      entry.quantity >= 1,
  );

  return (
    <Card>
      <h3 className="font-display text-2xl font-semibold">
        Size from your appliances
      </h3>
      <p className="mt-2 text-sm text-ink-soft">
        Don&rsquo;t know your monthly bill? List the appliances you run and
        we&rsquo;ll recommend a PV capacity based on Cairo&rsquo;s solar
        conditions (~5.5 peak sun hours/day).
      </p>

      <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto_auto]">
        <select
          aria-label="Choose an appliance from the library"
          value={librarySelection}
          onChange={(event) => setLibrarySelection(event.target.value)}
          className="rounded-card border-2 border-border bg-bg px-3 py-2 font-display text-sm focus:outline-none"
        >
          <option value="">Pick a typical appliance…</option>
          {groupedLibrary.map((group) => (
            <optgroup key={group.category} label={group.category}>
              {group.entries.map((entry) => (
                <option key={entry.name} value={entry.name}>
                  {entry.name} ({entry.watts} W)
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <AccentButton
          type="button"
          onClick={handleAddFromLibrary}
          disabled={!librarySelection}
        >
          Add from list
        </AccentButton>
        <AccentButton type="button" onClick={handleAddBlank}>
          Add custom
        </AccentButton>
      </div>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        {draft.length === 0 ? (
          <p className="rounded-card border-2 border-dashed border-border p-4 text-sm text-ink-soft">
            Add at least one appliance to compute a recommendation. Try the
            library above for typical Egyptian household devices.
          </p>
        ) : (
          <div className="space-y-3">
            <div className="hidden grid-cols-[2fr_1fr_1fr_0.7fr_auto] gap-3 px-2 text-xs font-semibold uppercase text-ink-soft md:grid">
              <span>Appliance</span>
              <span>Watts</span>
              <span>Hours / day</span>
              <span>Qty</span>
              <span aria-hidden="true" />
            </div>
            {draft.map((entry) => (
              <div
                key={entry.id}
                className="grid gap-2 rounded-card border-2 border-border bg-bg p-3 md:grid-cols-[2fr_1fr_1fr_0.7fr_auto] md:items-center md:gap-3"
              >
                <input
                  aria-label="Appliance name"
                  type="text"
                  required
                  value={entry.name}
                  onChange={(event) =>
                    handleChange(entry.id, 'name', event.target.value)
                  }
                  placeholder="e.g. Living-room AC"
                  className="rounded-card border-2 border-border bg-bg px-3 py-2 font-display text-sm focus:outline-none"
                />
                <input
                  aria-label="Watts"
                  type="number"
                  min={1}
                  max={10000}
                  step="any"
                  required
                  value={entry.watts}
                  onChange={(event) =>
                    handleChange(
                      entry.id,
                      'watts',
                      Number.parseFloat(event.target.value) || 0,
                    )
                  }
                  className="rounded-card border-2 border-border bg-bg px-3 py-2 font-display text-sm focus:outline-none"
                />
                <input
                  aria-label="Hours per day"
                  type="number"
                  min={0}
                  max={24}
                  step="any"
                  required
                  value={entry.hours_per_day}
                  onChange={(event) =>
                    handleChange(
                      entry.id,
                      'hours_per_day',
                      Number.parseFloat(event.target.value) || 0,
                    )
                  }
                  className="rounded-card border-2 border-border bg-bg px-3 py-2 font-display text-sm focus:outline-none"
                />
                <input
                  aria-label="Quantity"
                  type="number"
                  min={1}
                  max={100}
                  step={1}
                  required
                  value={entry.quantity}
                  onChange={(event) =>
                    handleChange(
                      entry.id,
                      'quantity',
                      Math.max(1, Number.parseInt(event.target.value, 10) || 1),
                    )
                  }
                  className="rounded-card border-2 border-border bg-bg px-3 py-2 font-display text-sm focus:outline-none"
                />
                <button
                  type="button"
                  aria-label={`Remove ${entry.name || 'appliance'}`}
                  onClick={() => handleRemove(entry.id)}
                  className="rounded-card border-2 border-border bg-bg px-3 py-2 font-display text-sm hover:bg-accent"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
          <div>
            <label
              htmlFor="load-sizing-coverage"
              className="block font-display text-sm font-semibold text-ink"
            >
              How much should the PV system cover?
            </label>
            <select
              id="load-sizing-coverage"
              value={coverage}
              onChange={(event) =>
                setCoverage(Number.parseFloat(event.target.value))
              }
              className="mt-2 block w-full rounded-card border-2 border-border bg-bg px-4 py-3 font-display text-base focus:outline-none"
            >
              {COVERAGE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <PrimaryButton
            type="submit"
            disabled={draft.length === 0 || !formValid || sizing.isPending}
          >
            {sizing.isPending ? 'Sizing…' : 'Recommend a system'}
          </PrimaryButton>
        </div>

        {sizing.isError && (
          <p role="alert" className="text-sm text-danger">
            Could not size the system ({sizing.error.message}).
          </p>
        )}
      </form>

      {result && (
        <div
          role="region"
          aria-label="Load-driven sizing recommendation"
          data-testid="load-sizing-result"
          className="mt-6 rounded-card border-2 border-border bg-accent/40 p-5"
        >
          <h4 className="font-display text-lg font-semibold">
            Recommended system: {formatNumber(result.recommended_system_kw, 2)} kW
          </h4>
          <ul className="mt-3 space-y-1 text-sm text-ink">
            <li>
              <strong>{result.recommended_panel_count}</strong> panels at{' '}
              {formatNumber(result.panel_rated_watts, 0)} W each.
            </li>
            <li>
              Daily load: <strong>{formatNumber(result.daily_load_kwh, 1)} kWh</strong>
              {' · '}
              Monthly: <strong>{formatNumber(result.monthly_load_kwh, 0)} kWh</strong>
              {' · '}
              Peak draw: <strong>{formatNumber(result.peak_load_kw, 1)} kW</strong>
            </li>
            <li>
              Required roof area:{' '}
              <strong>{formatNumber(result.required_roof_area_m2, 0)} m²</strong>
              {' '}
              (after {Math.round(result.roof_utilization_factor * 100)}% utilization).
            </li>
            {result.roof_fits === true && (
              <li className="text-success">
                ✓ Fits your detected roof area
                {result.available_roof_area_m2 !== null
                  ? ` (${formatNumber(result.available_roof_area_m2, 0)} m² available).`
                  : '.'}
              </li>
            )}
            {result.roof_fits === false && result.roof_area_shortfall_m2 !== null && (
              <li className="text-danger">
                ⚠ Your roof is{' '}
                <strong>{formatNumber(result.roof_area_shortfall_m2, 0)} m²</strong>{' '}
                short for this size — consider a lower coverage target or a
                higher-density panel.
              </li>
            )}
          </ul>
          {onAcceptRecommendation && (
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <AccentButton
                type="button"
                onClick={() => {
                  onAcceptRecommendation(result.required_roof_area_m2);
                  setAcceptedAreaM2(result.required_roof_area_m2);
                }}
              >
                Use this size in the estimate
              </AccentButton>
              {acceptedAreaM2 !== null && (
                <span role="status" className="text-sm text-success">
                  ✓ Roof area updated to {formatNumber(acceptedAreaM2, 0)} m² —
                  scroll up to run the estimate.
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
