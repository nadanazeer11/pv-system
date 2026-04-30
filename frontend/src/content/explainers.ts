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
  'energy-pvlib': {
    id: 'energy-pvlib',
    title: 'How does the industry-standard model work?',
    plainEnglish: [
      "We use a free weather record from the European Commission's PVGIS service — a typical year of hourly sun, temperature, and wind for your exact spot. That record is the same one most professional solar reports rely on.",
      'For each of the 8,760 hours we work out how much sunlight actually reaches a tilted panel facing south, how hot the panel runs, and how much electricity it produces after the inverter — then add it all up to get one yearly number and twelve monthly numbers.',
      'Cairo rooftops typically yield around 1,700–1,900 kWh per kilowatt of panels each year. Anything inside that band is a sanity check that the model and your inputs agree.',
    ],
    math: [
      'hourly_AC = pvlib_chain(POA, cell_temp, system_kW, inverter_eff, losses)',
      'annual_kWh   = Σ hourly_AC',
      'monthly_kWh  = group_by_month(hourly_AC)',
      'specific_yield = annual_kWh ÷ system_kW',
    ],
    variables: [
      { label: 'Weather source', value: 'PVGIS Typical Meteorological Year' },
      { label: 'Default tilt (Cairo)', value: '26°' },
      { label: 'Default azimuth', value: '180° (south)' },
      { label: 'Default inverter efficiency', value: '96%' },
      { label: 'Default DC-side losses', value: '14% (PVWatts canonical)' },
    ],
    sources: [
      {
        label: 'PVGIS — Photovoltaic Geographical Information System',
        href: 'https://re.jrc.ec.europa.eu/pvg_tools/en/',
      },
      {
        label: 'pvlib-python documentation',
        href: 'https://pvlib-python.readthedocs.io/',
      },
      { label: 'Methodology — Energy modelling (research/methodology.md)' },
    ],
  },
  'tiered-tariff': {
    id: 'tiered-tariff',
    title: "How does Egypt's tiered tariff change the math?",
    plainEnglish: [
      'Most calculators assume the electricity price is one flat number. In Egypt the price grows in steps as you use more — the first 50 units of the month are cheap, the next 50 cost a bit more, and so on, with the highest steps costing roughly three times the lowest.',
      "Solar power displaces consumption from the most expensive step first. So a household whose bill reaches the top step saves money at the top-step price — not the household's average price — for every kWh the panels produce.",
      'That difference between the top-step price and the average price is exactly why a flat-tariff model under-estimates Egyptian payback. Our calculation uses the published step schedule, month by month.',
    ],
    math: [
      'monthly_bill = Σ (kWh_in_tier_i × price_i)   over all tiers',
      'savings = bill_without_PV − bill_after_PV',
      'effective_savings_rate = savings ÷ generation',
    ],
    variables: [
      { label: 'Tier schedule source', value: 'EgyptERA residential, post-July 2023' },
      { label: 'Lowest tier', value: '0–50 kWh/month @ 0.58 EGP' },
      { label: 'Top tier', value: '> 1000 kWh/month @ 1.55 EGP' },
      { label: 'Default monthly export credit', value: '0 EGP/kWh (self-consumption only)' },
    ],
    sources: [
      {
        label: 'EgyptERA published residential tariff schedule',
        href: 'https://egyptera.org/',
      },
      { label: 'Methodology — Tiered tariff optimisation (research/methodology.md)' },
      { label: 'PLAN.md — Contribution B (Egypt Tiered Tariff)' },
    ],
  },
  'payback-ci': {
    id: 'payback-ci',
    title: 'What does "± 1.5 years" actually mean?',
    plainEnglish: [
      'The payback period is the year in which your accumulated solar savings first cover the upfront cost. It depends on numbers nobody can know exactly — how fast electricity prices rise, how fast panels age, how much the weather cooperates, when the inverter needs replacing.',
      'Instead of guessing one value for each, we sample plausible values 1,000 times and run the math 1,000 times. The headline year is the middle of those answers, and the range you see captures the middle 90% of them.',
      'A range of "7.2 ± 1.5 years" therefore means: under realistic Egyptian conditions, payback is most likely around seven years, very rarely faster than five, and very rarely slower than nine.',
    ],
    math: [
      'for k = 1 … 1000:',
      '   draw degradation, tariff inflation, capex, O&M, weather yield',
      '   payback_k = year discounted cash-flow turns positive',
      'payback_p50 = median(payback_k)',
      '90% interval = (payback_p05, payback_p95)',
    ],
    variables: [
      { label: 'Number of simulations', value: '1,000' },
      { label: 'Degradation distribution', value: 'triangular(0.2%, 0.5%, 1.0%)' },
      { label: 'Tariff inflation distribution', value: 'normal(8%, 3%) clipped at 0' },
      { label: 'Capex distribution', value: 'triangular(30k, 35k, 45k EGP/kW)' },
    ],
    sources: [
      { label: 'Methodology — Monte Carlo uncertainty (research/methodology.md)' },
      { label: 'PLAN.md — Contribution C (Monte Carlo Uncertainty Analysis)' },
    ],
  },
};

export function getExplainer(id: string): Explainer | undefined {
  return explainers[id];
}
