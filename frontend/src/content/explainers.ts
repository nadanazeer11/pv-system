/**
 * Single source of truth for "Know more" modal content.
 *
 * Every dashboard concept gets one entry. Adding a new explainer is a
 * one-file change: append an entry here, reference its id from the
 * surface (e.g. `<KnowMoreButton id="system-size" />`). Days 13–17 will
 * fill in the remaining required ids defined in PLAN.md's Frontend
 * Design Brief — Day 12 ships only the `system-size` entry as a
 * working end-to-end demo of the pattern.
 */

export type ExplainerSource = {
  label: string;
  href?: string;
};

export type ExplainerVariable = {
  label: string;
  value: string;
};

export type Explainer = {
  id: string;
  title: string;
  /** 1–2 short paragraphs in plain English. No code, no jargon. */
  plainEnglish: string[];
  /** Optional formula block(s); rendered monospaced, no LaTeX runtime. */
  math?: string[];
  /**
   * Variables filled in from the user's request, used to make the
   * explanation concrete rather than abstract. Optional — the modal
   * still renders cleanly without them.
   */
  variables?: ExplainerVariable[];
  sources: ExplainerSource[];
};

export const explainers: Record<string, Explainer> = {
  'roof-detection': {
    id: 'roof-detection',
    title: 'How does the AI detect the roof?',
    plainEnglish: [
      "When you type an address we ask OpenStreetMap — a free, community-maintained map of the world — to translate it into a latitude and longitude. The pin you see on the map is that point.",
      "Once we know the point, we look up every nearby building outline that the OpenStreetMap community has already drawn around real rooftops, pick the one most likely to be yours, and draw it back on top of the map so you can confirm it before we run any numbers.",
      "If the outline does not match your roof you can click the map to drop the pin somewhere else, or override the area on the next step — the system never guesses without giving you a way to correct it.",
    ],
    math: [
      'address  ──Nominatim──▶  (latitude, longitude)',
      '(latitude, longitude)  ──Overpass──▶  nearby OSM building polygons',
      'primary_roof = polygon containing the pin (else nearest centroid)',
    ],
    variables: [
      { label: 'Geocoder', value: 'OpenStreetMap Nominatim' },
      { label: 'Footprint source', value: 'OpenStreetMap Overpass API' },
      { label: 'Default search radius (Egypt-tuned)', value: '50 m' },
      { label: 'Country bias', value: 'Egypt (configurable)' },
    ],
    sources: [
      { label: 'OpenStreetMap Nominatim Usage Policy', href: 'https://operations.osmfoundation.org/policies/nominatim/' },
      { label: 'OpenStreetMap Overpass API', href: 'https://wiki.openstreetmap.org/wiki/Overpass_API' },
      { label: 'Methodology — Roof detection (research/methodology.md)' },
    ],
  },
  'system-size': {
    id: 'system-size',
    title: 'How is the panel count calculated?',
    plainEnglish: [
      "We start with how much roof you have, then keep only the part that's actually usable for solar — walkways, edges, and shaded zones near the roof's edge or chimneys can't hold panels.",
      'We then divide that usable area by the size of one modern solar panel, round down to a whole number, and multiply by the panel rating to get the total system capacity in kilowatts.',
    ],
    math: [
      'usable_area = roof_area × utilization_factor',
      'panel_count = floor(usable_area ÷ panel_area)',
      'system_kW = panel_count × panel_rating ÷ 1000',
    ],
    variables: [
      { label: 'Default panel rating (Egypt 2024)', value: '450 W' },
      { label: 'Default panel area', value: '1.8 m²' },
      { label: 'Default roof utilization factor', value: '0.7' },
    ],
    sources: [
      {
        label: 'Methodology — System sizing (research/methodology.md)',
      },
      {
        label: 'PLAN.md — Egypt-Specific Assumptions (Hardware)',
      },
    ],
  },
};

export function getExplainer(id: string): Explainer | undefined {
  return explainers[id];
}
