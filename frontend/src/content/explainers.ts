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
  'energy-manual': {
    id: 'energy-manual',
    title: 'How does our physics model work?',
    plainEnglish: [
      "Alongside the industry-standard tool, we wrote a second simulation from scratch — one that walks through the physics step by step rather than calling a black box.",
      "It uses the same hourly weather record, then for every hour figures out how the sun sits in the sky, how much of that sunlight hits a tilted panel facing south, how warm the panel runs in the Cairo heat (hot panels lose efficiency), and finally how much electricity comes out after the wiring and inverter take their cut.",
      "Building it ourselves is the academic point. If two simulations written from completely different starting points land on the same yearly number, the result is trustworthy — and any disagreement tells us exactly how much honest uncertainty sits behind the headline.",
    ],
    math: [
      'sun_position(latitude, longitude, hour)  →  zenith, azimuth',
      'POA = beam·cos(angle_of_incidence) + diffuse·sky_view + ground_reflected',
      'cell_temp = ambient_temp + (NOCT − 20)/800 · POA',
      'DC_power = system_kW · POA/1000 · (1 + γ·(cell_temp − 25)) · (1 − DC_losses)',
      'AC_power = DC_power · inverter_efficiency',
      'annual_kWh = Σ AC_power × 1 hour',
    ],
    variables: [
      { label: 'Sun-position model', value: 'NREL Solar Position Algorithm (SPA)' },
      { label: 'Diffuse / albedo split', value: 'Hay–Davies transposition' },
      { label: 'Temperature coefficient', value: '−0.4%/°C (mono-Si standard)' },
      { label: 'NOCT (default)', value: '45 °C' },
      { label: 'DC-side losses (default)', value: '14% (PVWatts canonical)' },
      { label: 'Inverter efficiency (default)', value: '96%' },
    ],
    sources: [
      {
        label: 'NREL Solar Position Algorithm (SPA) — Reda & Andreas 2008',
        href: 'https://www.nrel.gov/docs/fy08osti/34302.pdf',
      },
      {
        label: 'PVWatts Version 5 Manual — Dobos 2014 (NREL/TP-6A20-62641)',
        href: 'https://www.nrel.gov/docs/fy14osti/62641.pdf',
      },
      { label: 'Methodology — Manual physics model (research/methodology.md)' },
    ],
  },
  'model-comparison': {
    id: 'model-comparison',
    title: 'Why two energy models?',
    plainEnglish: [
      'Most solar calculators run a single black-box simulation, print one number, and move on. We run two: a widely used industry tool and a fresh-from-physics model we wrote ourselves. Both consume the same hourly weather record for your spot, and both are aimed at the same answer: how many kilowatt-hours per year will this system produce?',
      'When two simulations written from totally different starting points agree, the headline number is trustworthy. When they disagree, the size of the gap is itself a useful piece of information — it tells the homeowner (and a thesis examiner) how much honest model uncertainty sits behind the dashboard.',
      'A residual under 5% is "strong agreement", 5–10% is "reasonable", and anything above 10% is a flag to investigate the inputs before reporting any payback number to a homeowner.',
    ],
    math: [
      'residual_kWh   = annual_manual − annual_pvlib',
      'residual_pct   = residual_kWh ÷ annual_pvlib',
      'agreement = strong   if |residual_pct| < 5%',
      '            reasonable if 5% ≤ |residual_pct| < 10%',
      '            divergent  otherwise',
    ],
    variables: [
      { label: 'Reference model', value: 'pvlib PVWatts chain' },
      { label: 'Independent model', value: 'manual physics chain (POA + cell-temp + DC→AC)' },
      { label: 'Strong-agreement threshold', value: '|Δ| < 5% (matches pvlib-vs-PVSyst documented band)' },
    ],
    sources: [
      {
        label: 'pvlib-python validation against PVSyst',
        href: 'https://pvlib-python.readthedocs.io/en/stable/user_guide/index.html',
      },
      { label: 'Methodology — Dual-model cross-validation (research/methodology.md)' },
      { label: 'PLAN.md — Core Academic Contributions: Dual Energy Model' },
    ],
  },
  'monthly-production': {
    id: 'monthly-production',
    title: 'What does the monthly production chart show?',
    plainEnglish: [
      'Each pair of bars is one calendar month. The dark bar is what the industry-standard model expects your panels to deliver that month; the green bar is what our independent physics model expects. Both numbers are kilowatt-hours of usable AC electricity (post-inverter) — the same units that show up on your bill.',
      'Cairo gets its highest production in May–August, when the sun stays high in the sky for longer; December and January are the leanest months. Any reasonable simulation has to reproduce that seasonal hump, so the chart doubles as a sanity check.',
      'Reading the gap between bars in any given month gives a finer-grained version of the annual residual: if a single month disagrees by a lot, that points at a season-specific input (winter diffuse fraction, summer cell-temperature derate) rather than a systematic offset.',
    ],
    math: [
      'monthly_kWh[m]  = group_by_month(hourly_AC, m)        for m = 1 … 12',
      'monthly_residual[m]  = manual.monthly_kWh[m] − pvlib.monthly_kWh[m]',
    ],
    variables: [
      { label: 'Months in chart', value: 'Jan, Feb, …, Dec' },
      { label: 'Series 1 (dark)', value: 'pvlib (industry-standard PVWatts)' },
      { label: 'Series 2 (lime)', value: 'manual physics model' },
      { label: 'Units', value: 'kWh of AC energy delivered to the grid' },
    ],
    sources: [
      {
        label: 'PVGIS — Typical Meteorological Year (data source)',
        href: 'https://re.jrc.ec.europa.eu/pvg_tools/en/',
      },
      { label: 'Methodology — Energy modelling (research/methodology.md)' },
    ],
  },
  'monte-carlo': {
    id: 'monte-carlo',
    title: 'How does the Monte Carlo simulation work?',
    plainEnglish: [
      'Nobody can predict the future of electricity prices, weather, or how fast solar panels age. Instead of pretending we know any of those numbers exactly, we treat each one as a *range* of plausible values, then ask the computer to roll the dice 1,000 times — once for every set of plausible numbers — and re-calculate payback for each roll.',
      'The bars on this chart count those 1,000 outcomes by year. A tall bar means many simulations land in that year; a short tail on the right means a small minority of pessimistic futures. The middle marker (p50) is the median: half the simulations pay back faster, half slower. The two outer markers (p05, p95) bracket the middle 90% — that is the range you see on the headline payback card.',
      'The shape of the histogram matters: a tightly clustered cloud means the answer is robust, while a long tail means the project depends sensitively on parameters that could swing the wrong way (typically tariff inflation and capex).',
    ],
    math: [
      'for k = 1 … 1000:',
      '   draw degradation_k, tariff_inflation_k, capex_k, O&M_k,',
      '         weather_yield_k, inverter_year_k, inverter_cost_k',
      '   simulate 25 yr of cash flow at the kth draw',
      '   payback_k = year discounted cumulative cash flow ≥ 0',
      'p50 = median(payback_1, …, payback_1000)',
      'p05, p95 = percentiles bracketing the middle 90%',
    ],
    variables: [
      { label: 'Number of simulations', value: '1,000 (default)' },
      { label: 'Random seed', value: '42 (fixed for reproducibility)' },
      { label: 'Degradation distribution', value: 'triangular(0.2%, 0.5%, 1.0%) per year' },
      { label: 'Tariff inflation distribution', value: 'normal(8%, 3%) clipped at 0' },
      { label: 'Capex distribution', value: 'triangular(30k, 35k, 45k EGP/kW)' },
      { label: 'Weather-yield distribution', value: 'normal(1.0, 0.05) clipped to 0.5–1.5' },
      { label: 'Inverter replacement', value: 'triangular(year 10, 12, 15) at triangular(7%, 10%, 15%) of capex' },
    ],
    sources: [
      { label: 'Jordan & Kurtz (NREL 2013) — PV Degradation Rates: An Analytical Review' },
      { label: 'IRENA (2023) — Renewable Power Generation Costs' },
      { label: 'IEA-PVPS Task 13 (2021) — Service Life of PV Inverters' },
      { label: 'Methodology — Monte Carlo uncertainty (research/methodology.md)' },
      { label: 'PLAN.md — Contribution C (Monte Carlo Uncertainty Analysis)' },
    ],
  },
  'roi-fan': {
    id: 'roi-fan',
    title: 'How do I read the cumulative-return fan chart?',
    plainEnglish: [
      "The y-axis is the running balance of the project, in Egyptian pounds. It starts deeply negative on day one because you've just paid for the system — that is the deepest point on the chart. Each year afterwards, the savings from your panels chip away at the hole, and at some point the line crosses zero and keeps climbing — that crossing is your payback.",
      "The middle dark line is the most likely path. The dark green ribbon around it shows the middle 50% of simulated futures, and the lighter ribbon shows the broader 90% band. The fan widens with time because uncertainty compounds: a small annual surprise (a hotter summer, a faster price hike) accumulates over 25 years.",
      "Crossing zero is good news, but the *shape* of the fan tells you more than the headline number — a narrow fan means the project is robust, while a wide fan means there are plausible futures (the bottom edge) where break-even is uncomfortably late, and others (the top edge) where the system pays for itself two or three times over.",
    ],
    math: [
      'cumulative_k(t) = -capex_k + Σ_{i=1..t} discounted_net_cash_flow_k(i)',
      'p50(t) = median over k of cumulative_k(t)            ← the middle line',
      'p25(t), p75(t) = the inner ribbon (interquartile range)',
      'p05(t), p95(t) = the outer ribbon (90% band)',
      'payback year ≈ smallest t such that p50(t) ≥ 0',
    ],
    variables: [
      { label: 'Trajectory length', value: 'analysis_period_years + 1 (year 0 included)' },
      { label: 'Discount rate (real)', value: '4% (Egypt project finance)' },
      { label: 'Median line', value: 'column-wise median across all simulations' },
      { label: 'Bands', value: 'envelope percentiles, not single-simulation paths' },
    ],
    sources: [
      { label: 'Methodology — Cumulative-cash-flow uncertainty bands (research/methodology.md)' },
      { label: 'PLAN.md — Contribution C (Monte Carlo Uncertainty Analysis)' },
    ],
  },
  'tier-bracket-savings': {
    id: 'tier-bracket-savings',
    title: 'How do I read the tier-bracket chart?',
    plainEnglish: [
      "Egypt charges residential electricity in steps. The first 50 units of the month are the cheapest, the next 50 a little more, and the highest steps cost almost three times the lowest. The chart paints your annual bill as a stack of those steps — bottom is the cheapest step, top is the priciest.",
      "Solar power knocks down each month's consumption. Because the cheap steps are filled first, every unit your panels make subtracts from the *top* of the stack first. That is why the right-hand bar in the chart is so much shorter than the left: solar is shaving off the most expensive layers, even though it produces the same kilowatt-hour as one from the cheap layers.",
      "If your household barely reaches the top step, the right-hand bar will look almost as tall as the left and your savings will be modest. If your monthly bill regularly hits the top step, solar pays back faster than a flat-tariff calculator would tell you — sometimes by a lot.",
    ],
    math: [
      'monthly_bill = Σ_i (kWh_in_tier_i × price_i)',
      'annual_bill = Σ_{m=1..12} monthly_bill_m',
      'monthly_consumption_with_PV = max(0, consumption − generation)',
      'savings_per_tier = (annual_bill_before_per_tier − annual_bill_after_per_tier)',
      'top_tier_share = savings_per_tier[top] ÷ total_savings',
    ],
    variables: [
      { label: 'Tier schedule', value: 'EgyptERA residential, post-July 2023' },
      { label: 'Lowest tier', value: '0–50 kWh/month @ 0.58 EGP' },
      { label: 'Top tier', value: '> 1,000 kWh/month @ 1.55 EGP' },
      { label: 'Top-tier price ÷ lowest-tier price', value: '~2.7×' },
      { label: 'Self-consumption first', value: 'Surplus generation defaults to zero export credit' },
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
