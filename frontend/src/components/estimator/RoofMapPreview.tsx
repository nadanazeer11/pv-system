import { useEffect, useRef } from 'react';
import L from 'leaflet';
import {
  MapContainer,
  Marker,
  Polygon,
  TileLayer,
  useMap,
  useMapEvents,
} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import iconUrl from 'leaflet/dist/images/marker-icon.png';
import shadowUrl from 'leaflet/dist/images/marker-shadow.png';

import type { Location, RoofPolygon } from '@/types/api';

// Bundlers can't infer Leaflet's default icon paths from its CSS, so we
// rebuild the prototype here once. Without this, the marker renders as a
// broken-image placeholder in production builds.
const defaultIcon = L.icon({
  iconRetinaUrl,
  iconUrl,
  shadowUrl,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  tooltipAnchor: [16, -28],
  shadowSize: [41, 41],
});
L.Marker.prototype.options.icon = defaultIcon;

type RoofMapPreviewProps = {
  /** Currently-selected location; null while the user has not chosen one. */
  location: Location | null;
  /** Optional roof footprint to overlay (returned by /api/roof/detect). */
  roof?: RoofPolygon | null;
  /** Called when the user clicks the map to (re-)drop the pin. */
  onLocationChange?: (location: Location) => void;
  /** Map zoom level — 18 is the default close-up view used by the estimator. */
  zoom?: number;
  /** Center the map should fall back to when no location is selected. */
  fallbackCenter?: Location;
};

/**
 * Leaflet-based map preview for the address picker.
 *
 * The component is responsible for:
 *   - rendering an OpenStreetMap raster tile layer,
 *   - showing a marker at the currently-selected location,
 *   - emitting click events so the parent can update the location when
 *     the geocoder result is approximate (typical for Egyptian rural
 *     addresses where the dropped pin lands at the *village* centroid),
 *   - drawing the OSM building polygon when the parent has fetched it.
 *
 * The component is presentational — all state lives one level up in
 * LocationPicker. This makes the map cheap to swap out (e.g. for
 * MapLibre) and keeps the test surface for the parent free of Leaflet.
 */
export function RoofMapPreview({
  location,
  roof,
  onLocationChange,
  zoom = 18,
  fallbackCenter,
}: RoofMapPreviewProps) {
  // Cairo coords if the parent did not supply a fallback. We pick the
  // city centre rather than the country centroid because every other
  // Egypt-specific default in the project (tilt, soiling, pricing)
  // also targets Cairo unless explicitly overridden.
  const center: Location = location ?? fallbackCenter ?? {
    latitude: 30.0444,
    longitude: 31.2357,
  };

  return (
    <div
      className="overflow-hidden rounded-card border-2 border-border"
      data-testid="roof-map-preview"
    >
      <MapContainer
        center={[center.latitude, center.longitude]}
        zoom={location ? zoom : 12}
        className="h-72 w-full md:h-80"
        scrollWheelZoom={false}
        aria-label="Map preview of the selected roof location"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
        />
        <RecenterOnLocation location={location} zoom={zoom} />
        <ClickHandler onLocationChange={onLocationChange} />
        {location && (
          <Marker
            position={[location.latitude, location.longitude]}
            keyboard
            alt="Selected location"
          />
        )}
        {roof && roof.coordinates_lat_lng.length >= 3 && (
          <Polygon
            positions={roof.coordinates_lat_lng.map(([lat, lng]) => [lat, lng])}
            pathOptions={{
              color: '#191A23',
              weight: 2,
              fillColor: '#B9FF66',
              fillOpacity: 0.45,
            }}
          />
        )}
      </MapContainer>
    </div>
  );
}

/**
 * Invalidate Leaflet's internal sizing cache when the container first
 * mounts inside a flex/grid layout, then re-pan when the location prop
 * changes (the geocoder might shift the pin many kilometres). Keeping
 * this in a child of <MapContainer> lets us call ``useMap`` cleanly.
 */
function RecenterOnLocation({
  location,
  zoom,
}: {
  location: Location | null;
  zoom: number;
}) {
  const map = useMap();
  const hasInvalidatedSize = useRef(false);

  useEffect(() => {
    if (!hasInvalidatedSize.current) {
      // Defer one tick so the parent layout has its final dimensions.
      const handle = window.setTimeout(() => map.invalidateSize(), 0);
      hasInvalidatedSize.current = true;
      return () => window.clearTimeout(handle);
    }
    return undefined;
  }, [map]);

  useEffect(() => {
    if (location) {
      map.setView([location.latitude, location.longitude], zoom, {
        animate: true,
      });
    }
  }, [location, map, zoom]);

  return null;
}

function ClickHandler({
  onLocationChange,
}: {
  onLocationChange?: (location: Location) => void;
}) {
  useMapEvents({
    click(event) {
      if (!onLocationChange) return;
      onLocationChange({
        latitude: event.latlng.lat,
        longitude: event.latlng.lng,
      });
    },
  });
  return null;
}
