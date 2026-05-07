import { useRef, useState } from 'react';
import { request } from '@/lib/api';
import type { ObstacleAnnotationResult } from '@/types/api';
import { PolygonCanvas } from './PolygonCanvas';
import type { DrawnPolygon, PolygonKind } from './PolygonCanvas';

type Mode =
  /** OSM area is known — user only marks obstacles. */
  | 'obstacles-only'
  /** No OSM — user draws the roof boundary first, then marks obstacles. */
  | 'roof-and-obstacles';

type Props = {
  mode: Mode;
  /** Pre-known area (from OSM). Required when mode === 'obstacles-only'. */
  knownAreaM2?: number;
  /** Called when the backend returns the computed usable area. */
  onAreaComputed: (netAreaM2: number) => void;
};

type ImageMeta = {
  url: string;
  naturalWidth: number;
  naturalHeight: number;
};

export function ObstacleAnnotationPanel({ mode, knownAreaM2, onAreaComputed }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [image, setImage] = useState<ImageMeta | null>(null);
  const [polygons, setPolygons] = useState<DrawnPolygon[]>([]);
  const [drawingKind, setDrawingKind] = useState<PolygonKind>(
    mode === 'roof-and-obstacles' ? 'roof' : 'obstacle',
  );
  const [manualAreaInput, setManualAreaInput] = useState('');
  const [result, setResult] = useState<ObstacleAnnotationResult | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const roofPolygon = polygons.find((p) => p.kind === 'roof');
  const obstacles = polygons.filter((p) => p.kind === 'obstacle');

  const effectiveArea =
    mode === 'obstacles-only' ? (knownAreaM2 ?? 0) : parseFloat(manualAreaInput);

  const canSubmit =
    image !== null &&
    effectiveArea > 0 &&
    (mode === 'obstacles-only' || roofPolygon !== undefined);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      setImage({ url, naturalWidth: img.naturalWidth, naturalHeight: img.naturalHeight });
      setPolygons([]);
      setResult(null);
      setError(null);
    };
    img.src = url;
  }

  function handlePolygonComplete(poly: DrawnPolygon) {
    if (poly.kind === 'roof') {
      // Only one roof polygon allowed — replace any existing one.
      setPolygons((prev) => [...prev.filter((p) => p.kind !== 'roof'), poly]);
      setDrawingKind('obstacle');
    } else {
      setPolygons((prev) => [...prev, poly]);
    }
  }

  function handlePolygonDelete(id: string) {
    setPolygons((prev) => prev.filter((p) => p.id !== id));
  }

  async function handleSubmit() {
    if (!canSubmit || !image) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const w = image.naturalWidth;
      const h = image.naturalHeight;

      // When mode is obstacles-only, the roof polygon is the full image rectangle.
      const roofPx: Array<[number, number]> =
        roofPolygon?.points ??
        ([
          [0, 0],
          [w, 0],
          [w, h],
          [0, h],
        ] as Array<[number, number]>);

      const obstaclePx = obstacles.map((o) => o.points as Array<[number, number]>);

      const data = await request<ObstacleAnnotationResult>('/api/roof/annotate', {
        method: 'POST',
        body: {
          roof_polygon_px: roofPx,
          obstacle_polygons_px: obstaclePx,
          known_area_m2: effectiveArea,
        },
      });
      setResult(data);
      onAreaComputed(data.net_area_m2);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Annotation failed.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Image upload */}
      <div>
        <label className="block font-display text-sm font-semibold text-ink">
          Satellite image of your rooftop
        </label>
        <div
          className="mt-2 flex cursor-pointer items-center justify-center rounded-card border-2 border-dashed border-border bg-bg py-6 text-sm text-ink-soft transition hover:border-ink-soft"
          onClick={() => fileInputRef.current?.click()}
        >
          {image ? (
            <span className="text-ink">Image loaded — click to replace</span>
          ) : (
            <span>Click to upload a PNG or JPEG satellite image</span>
          )}
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
          onChange={handleFileChange}
        />
      </div>

      {/* Manual area input (Case B only) */}
      {mode === 'roof-and-obstacles' && (
        <div>
          <label className="block font-display text-sm font-semibold text-ink">
            Estimated roof area (m²)
          </label>
          <input
            type="number"
            min={1}
            step="any"
            value={manualAreaInput}
            onChange={(e) => setManualAreaInput(e.target.value)}
            placeholder="Enter your roof area in m²"
            className="mt-2 block w-full rounded-card border-2 border-border bg-bg px-4 py-3 font-display text-lg focus:outline-none"
          />
        </div>
      )}

      {/* Canvas + drawing controls */}
      {image && (
        <div className="space-y-3">
          {/* Mode selector */}
          <div className="flex flex-wrap gap-2">
            {mode === 'roof-and-obstacles' && (
              <button
                type="button"
                onClick={() => setDrawingKind('roof')}
                className={`rounded-card border-2 px-3 py-1.5 text-sm font-semibold transition ${
                  drawingKind === 'roof'
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-border text-ink-soft hover:border-ink-soft'
                }`}
              >
                Draw roof boundary
              </button>
            )}
            <button
              type="button"
              onClick={() => setDrawingKind('obstacle')}
              className={`rounded-card border-2 px-3 py-1.5 text-sm font-semibold transition ${
                drawingKind === 'obstacle'
                  ? 'border-red-500 bg-red-50 text-red-700'
                  : 'border-border text-ink-soft hover:border-ink-soft'
              }`}
            >
              Mark obstacle
            </button>
          </div>

          <p className="text-xs text-ink-soft">
            {drawingKind === 'roof'
              ? 'Click to place vertices around your roof. Double-click or click the first vertex to close.'
              : 'Click to place vertices around each obstacle (tank, AC unit, dish…). Double-click or click the first vertex to close. Press Esc to cancel.'}
          </p>

          {/* Drawing canvas */}
          <div className="relative overflow-hidden rounded-card border border-border">
            <img
              src={image.url}
              alt="Rooftop satellite view"
              className="block w-full"
              draggable={false}
            />
            <PolygonCanvas
              imageWidth={image.naturalWidth}
              imageHeight={image.naturalHeight}
              polygons={polygons}
              drawingKind={drawingKind}
              onPolygonComplete={handlePolygonComplete}
              onPolygonDelete={handlePolygonDelete}
            />
          </div>

          {/* Summary */}
          <p className="text-xs text-ink-soft">
            {mode === 'roof-and-obstacles' && (
              <>
                {roofPolygon ? (
                  <span className="text-blue-600">Roof boundary drawn. </span>
                ) : (
                  <span className="text-amber-600">No roof boundary yet. </span>
                )}
              </>
            )}
            {obstacles.length === 0
              ? 'No obstacles marked yet.'
              : `${obstacles.length} obstacle${obstacles.length > 1 ? 's' : ''} marked.`}
          </p>
        </div>
      )}

      {/* Submit */}
      <button
        type="button"
        disabled={!canSubmit || isSubmitting}
        onClick={handleSubmit}
        className="rounded-card bg-ink px-5 py-2.5 font-display text-sm font-semibold text-bg transition hover:opacity-80 disabled:opacity-40"
      >
        {isSubmitting ? 'Calculating…' : 'Calculate usable area'}
      </button>

      {/* Result */}
      {result && (
        <div className="rounded-card border border-border bg-bg p-4 text-sm">
          <p className="font-semibold text-ink">Usable area computed</p>
          <ul className="mt-2 space-y-1 text-ink-soft">
            <li>
              Roof area: <span className="text-ink">{result.roof_area_m2.toFixed(1)} m²</span>
            </li>
            <li>
              Obstacle area:{' '}
              <span className="text-ink">
                {result.obstacle_area_m2.toFixed(1)} m² ({(result.obstacle_fraction * 100).toFixed(1)}%)
              </span>
            </li>
            <li>
              Net usable area:{' '}
              <span className="font-semibold text-ink">{result.net_area_m2.toFixed(1)} m²</span>
            </li>
          </ul>
          <p className="mt-2 text-xs text-ink-soft">
            The estimate form has been updated with {result.net_area_m2.toFixed(1)} m².
          </p>
        </div>
      )}

      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
