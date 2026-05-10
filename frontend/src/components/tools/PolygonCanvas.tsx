import { useCallback, useEffect, useRef, useState } from 'react';

export type PolygonKind = 'roof' | 'obstacle';

export type DrawnPolygon = {
  id: string;
  kind: PolygonKind;
  points: Array<[number, number]>;
};

type Props = {
  /** Natural pixel dimensions of the background image. */
  imageWidth: number;
  imageHeight: number;
  /** Completed polygons to display. */
  polygons: DrawnPolygon[];
  /** Which kind the next drawn polygon will be. */
  drawingKind: PolygonKind;
  onPolygonComplete: (polygon: DrawnPolygon) => void;
  onPolygonDelete: (id: string) => void;
};

const SNAP_RADIUS = 12; // pixels in SVG-space
const ROOF_FILL = 'rgba(59,130,246,0.15)';
const ROOF_STROKE = '#3b82f6';
const OBS_FILL = 'rgba(239,68,68,0.25)';
const OBS_STROKE = '#ef4444';

function polygonCentroid(pts: Array<[number, number]>): [number, number] {
  const x = pts.reduce((s, p) => s + p[0], 0) / pts.length;
  const y = pts.reduce((s, p) => s + p[1], 0) / pts.length;
  return [x, y];
}

export function PolygonCanvas({
  imageWidth,
  imageHeight,
  polygons,
  drawingKind,
  onPolygonComplete,
  onPolygonDelete,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [inProgress, setInProgress] = useState<Array<[number, number]>>([]);
  const [cursor, setCursor] = useState<[number, number] | null>(null);

  // Convert a mouse event to SVG-space coordinates.
  const toSvgCoords = useCallback(
    (e: React.MouseEvent | MouseEvent): [number, number] => {
      const svg = svgRef.current;
      if (!svg) return [0, 0];
      const rect = svg.getBoundingClientRect();
      const scaleX = imageWidth / rect.width;
      const scaleY = imageHeight / rect.height;
      return [
        (e.clientX - rect.left) * scaleX,
        (e.clientY - rect.top) * scaleY,
      ];
    },
    [imageWidth, imageHeight],
  );

  const isNearFirst = useCallback(
    (pt: [number, number]): boolean => {
      if (inProgress.length < 3) return false;
      const [fx, fy] = inProgress[0];
      return Math.hypot(pt[0] - fx, pt[1] - fy) < SNAP_RADIUS;
    },
    [inProgress],
  );

  const closePolygon = useCallback(() => {
    if (inProgress.length < 3) return;
    onPolygonComplete({
      id: crypto.randomUUID(),
      kind: drawingKind,
      points: inProgress,
    });
    setInProgress([]);
  }, [inProgress, drawingKind, onPolygonComplete]);

  const handleClick = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (e.detail === 2) return; // handled by dblclick
      const pt = toSvgCoords(e);
      if (isNearFirst(pt)) {
        closePolygon();
        return;
      }
      setInProgress((prev) => [...prev, pt]);
    },
    [toSvgCoords, isNearFirst, closePolygon],
  );

  const handleDoubleClick = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      e.preventDefault();
      closePolygon();
    },
    [closePolygon],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      setCursor(toSvgCoords(e));
    },
    [toSvgCoords],
  );

  const handleMouseLeave = useCallback(() => setCursor(null), []);

  // Esc cancels the current in-progress polygon.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setInProgress([]);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const snapActive = cursor !== null && isNearFirst(cursor);
  const previewPoints =
    cursor !== null && inProgress.length > 0
      ? [...inProgress, snapActive ? inProgress[0] : cursor]
      : inProgress;

  const toPointsAttr = (pts: Array<[number, number]>) =>
    pts.map((p) => p.join(',')).join(' ');

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${imageWidth} ${imageHeight}`}
      className="absolute inset-0 h-full w-full cursor-crosshair select-none"
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      {/* Completed polygons */}
      {polygons.map((poly) => {
        const fill = poly.kind === 'roof' ? ROOF_FILL : OBS_FILL;
        const stroke = poly.kind === 'roof' ? ROOF_STROKE : OBS_STROKE;
        const [cx, cy] = polygonCentroid(poly.points);
        return (
          <g key={poly.id}>
            <polygon
              points={toPointsAttr(poly.points)}
              fill={fill}
              stroke={stroke}
              strokeWidth={2}
            />
            {/* Delete button */}
            <g
              className="cursor-pointer"
              onClick={(e) => {
                e.stopPropagation();
                onPolygonDelete(poly.id);
              }}
            >
              <circle cx={cx} cy={cy} r={10} fill={stroke} opacity={0.9} />
              <text
                x={cx}
                y={cy}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={12}
                fill="white"
                style={{ userSelect: 'none', pointerEvents: 'none' }}
              >
                ×
              </text>
            </g>
          </g>
        );
      })}

      {/* In-progress polygon */}
      {previewPoints.length > 1 && (
        <polyline
          points={toPointsAttr(previewPoints)}
          fill="none"
          stroke={drawingKind === 'roof' ? ROOF_STROKE : OBS_STROKE}
          strokeWidth={2}
          strokeDasharray="6 4"
        />
      )}

      {/* Vertex dots for in-progress polygon */}
      {inProgress.map(([x, y], i) => (
        <circle
          key={i}
          cx={x}
          cy={y}
          r={i === 0 && snapActive ? 8 : 4}
          fill={drawingKind === 'roof' ? ROOF_STROKE : OBS_STROKE}
          opacity={i === 0 && snapActive ? 0.7 : 1}
        />
      ))}

      {/* Cursor dot */}
      {cursor && !snapActive && inProgress.length > 0 && (
        <circle
          cx={cursor[0]}
          cy={cursor[1]}
          r={3}
          fill={drawingKind === 'roof' ? ROOF_STROKE : OBS_STROKE}
          opacity={0.5}
          style={{ pointerEvents: 'none' }}
        />
      )}
    </svg>
  );
}
