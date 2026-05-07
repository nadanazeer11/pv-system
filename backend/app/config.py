from pydantic_settings import BaseSettings, SettingsConfigDict

# ─────────────────────────────────────────────────────────────────────────
# EgyptERA residential electricity tariff (post-July 2023 reform schedule).
#
# Egypt's residential bill is a *progressive marginal block tariff*: each
# successive monthly-kWh band is billed at its own price, and the cheaper
# bands are still applied to the kWh that fall within them. A household
# consuming 250 kWh in a month therefore pays the first-band rate on the
# first 50 kWh, the second-band rate on the next 50 kWh, the third-band
# rate on the next 100 kWh, and the fourth-band rate on the remaining 50
# kWh — *not* the fourth-band rate on all 250 kWh.
#
# This shape is the analytical core of Contribution B in the thesis: PV
# generation displaces consumption from the *top* of the household's
# active band first, so each kWh saved is valued at that household's
# *marginal* rate, which can be 2–3× the average bill rate. A flat-tariff
# model systematically under-rates the savings and overstates payback.
#
# Source: EgyptERA published residential schedule effective from August
# 2023 (the most recent reform step at PLAN.md's 2024 reference point).
# Bands are upper bounds in kWh/month; the final band has no upper bound.
# Prices are in EGP per kWh and exclude the small fixed monthly service
# charge, which is negligible for our payback comparisons.
# ─────────────────────────────────────────────────────────────────────────
# 1e9 kWh/month is the JSON-safe sentinel for the "and above" tail —
# four orders of magnitude beyond any plausible residential consumption,
# but representable as a finite IEEE-754 double so the schedule survives
# JSON round-tripping in the API surface.
TARIFF_TOP_BAND_SENTINEL_KWH: float = 1.0e9

EGYPT_RESIDENTIAL_TARIFF_TIERS: list[tuple[float, float]] = [
    (50.0, 0.58),
    (100.0, 0.68),
    (200.0, 0.83),
    (350.0, 1.25),
    (650.0, 1.40),
    (1000.0, 1.45),
    (TARIFF_TOP_BAND_SENTINEL_KWH, 1.55),
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # API
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # External APIs
    pvgis_base_url: str = "https://re.jrc.ec.europa.eu/api/v5_2"
    google_maps_api_key: str = ""
    google_maps_static_url: str = "https://maps.googleapis.com/maps/api/staticmap"
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    # Network timeouts for the two roof-detection upstreams (seconds).
    # Overpass is slow under load; Google Maps Static is fast but we
    # still want a hard ceiling so the API surface fails fast.
    overpass_timeout_s: float = 30.0
    gmaps_static_timeout_s: float = 15.0

    # Roof detection (Day 10) ─────────────────────────────────────────
    # Search radius for OSM Overpass building queries. 50 m is a
    # deliberately conservative choice for the Egyptian residential
    # context: typical Cairo plot frontage is 10–25 m, and 50 m comfortably
    # captures the building containing the dropped pin plus a couple of
    # neighbours, without inflating the response with city-block-scale
    # results. Capped at 500 m to prevent accidental abuse of the public
    # Overpass instance.
    roof_search_radius_m: float = 50.0
    roof_search_radius_max_m: float = 500.0
    # Google Maps Static tile defaults — zoom 20 is the highest free tier
    # and gives ~14 cm/pixel at Cairo latitude (with scale=2), enough for
    # roof-edge detection. 640×640 is the maximum non-premium image size.
    gmaps_static_default_zoom: int = 20
    gmaps_static_default_size_px: int = 640
    gmaps_static_default_scale: int = 2
    # Web Mercator equatorial pixel size at zoom 0 (a Google constant
    # derived from the Earth's circumference). Documented so the
    # ground-resolution formula is auditable.
    web_mercator_zoom0_meters_per_pixel: float = 156543.03392

    # Roof CV segmentation (Day 11) ───────────────────────────────────
    # Width (in metres) of the band drawn either side of an OSM polygon
    # edge when scoring image-gradient alignment. 1.0 m ≈ 7 px at the
    # zoom-20/scale-2 default, which is wide enough to absorb GPS jitter
    # and OSM digitisation noise (typical 0.5–1.5 m positional error per
    # OSMF accuracy studies) without bleeding into neighbouring rooftops.
    cv_edge_band_width_m: float = 1.0
    # Confidence floor for the OSM-only fallback when the satellite tile
    # cannot be loaded (e.g. transport failure, missing API key). 0.0
    # signals "no CV evidence", but the OSM polygon is still surfaced
    # because the vector source is independently authoritative.
    cv_no_image_confidence: float = 0.0
    # When the OSM polygon is poorly axis-aligned (long-edge azimuth
    # within this many degrees of a cardinal heading) we *snap* the
    # estimated panel azimuth to the nearest cardinal — installers
    # almost always orient panels along the building's primary edges,
    # and OSM digitisation jitter can rotate a square footprint by 1–2°.
    cv_azimuth_snap_tolerance_deg: float = 8.0
    # Default tilt assumptions when OSM tags are missing — Egyptian
    # residential rooftops are overwhelmingly flat concrete slabs, so
    # the prior on "no tag" is "flat", and panels on a flat slab are
    # tilted to the latitude optimum. Pitched-roof shapes default to
    # the published Egyptian residential pitch median (≈30°).
    cv_default_pitched_roof_tilt_deg: float = 30.0
    cv_default_shed_roof_tilt_deg: float = 15.0
    # Bound checks for OSM-supplied roof:angle tag — anything outside
    # this band is treated as a tagging error and ignored.
    cv_min_roof_angle_deg: float = 0.0
    cv_max_roof_angle_deg: float = 60.0

    # PV hardware defaults
    panel_rated_watts: float = 450.0
    panel_area_m2: float = 1.8
    roof_utilization_factor: float = 0.7
    # Reduced utilization factor used when the user has explicitly marked
    # obstacles via the annotation tool — obstacles are already subtracted,
    # so only setbacks, walkways, and inter-row spacing remain (~15 %).
    roof_utilization_factor_annotated: float = 0.85
    inverter_efficiency: float = 0.96

    # Egypt-specific defaults
    default_tilt_deg: float = 26.0
    default_azimuth_deg: float = 180.0
    egypt_grid_emission_kg_per_kwh: float = 0.46
    installed_cost_egp_per_kw: float = 35000.0

    # CO₂ user-friendly equivalences (Day 18) ─────────────────────────
    # The thesis dashboard reports lifetime CO₂ avoided in raw kg, but a
    # homeowner cannot picture 50 000 kg of CO₂. The three equivalents
    # below are the ones the US EPA Greenhouse Gas Equivalencies
    # Calculator publishes as the "translate kg-CO₂ into something the
    # public can picture" defaults; using them makes the dashboard's
    # CO₂ card directly comparable to other consumer-facing climate
    # tools and to the figures cited in popular Egyptian press
    # coverage of rooftop PV.
    #
    # All three values are deliberately *factors* rather than per-year
    # rates so the CO₂ service can apply them to a *lifetime* CO₂ total
    # without coupling to the analysis horizon. The "trees" equivalent
    # is the EPA's "carbon sequestered annually by 1 acre of average
    # US forest" ÷ "trees/acre" derivation, expressed per-tree-per-year;
    # the CO₂ service multiplies by the analysis-period years to give
    # a horizon-matched headline ("the lifetime CO₂ this system avoids
    # equals what N trees would absorb over the same horizon").
    #
    # Sources (US EPA Greenhouse Gas Equivalencies Calculator,
    # "Calculations and References" page, 2024 edition):
    #   * Passenger car: 0.404 kg CO₂/mi ≈ 0.251 kg/km (US LDV fleet
    #     average, EPA 2022 MOVES3 model).
    #   * Petrol (gasoline): 8.887 × 10⁻³ tCO₂/gal ≈ 2.347 kg/L
    #     (EPA emission factor, combustion only — well-to-wheel would
    #     add ~25 % from upstream fuel production but is excluded for
    #     comparability with EPA's equivalency calculator).
    #   * Urban tree, 10-year average sequestration ≈ 21.77 kg CO₂/yr/tree
    #     (EPA derivation from McPherson urban-forest carbon-sequestration
    #     studies; rounded to 22 kg/yr in the calculator's headline).
    co2_kg_per_passenger_car_km: float = 0.251
    co2_kg_per_petrol_litre: float = 2.347
    co2_kg_per_tree_grown_year: float = 22.0

    # Sensitivity tornado (Day 18) ────────────────────────────────────
    # Default low / high swing ranges for the one-at-a-time tornado.
    # Each pair is the published (or literature-anchored) reasonable
    # range over which the parameter is plausibly uncertain — typically
    # the 10th / 90th percentile of the corresponding Monte Carlo prior.
    # Surfacing them here keeps the tornado deterministic and lets a
    # methodology-aware user reproduce or override any single range
    # without rebuilding the whole engine. The two synthetic ranges
    # (annual_kwh, tariff_egp_per_kwh) have no Monte Carlo equivalent
    # because the kernel treats them as deterministic *baseline* inputs;
    # their swing here is a *forecasting* uncertainty, not a stochastic
    # one. Cited:
    #   * yield: ±10 % spans the inter-annual irradiance + soiling band
    #     reported in Egyptian PV field studies (Mahmoud & El-Nokali 2023);
    #   * tariff: ±20 % spans the EgyptERA-effective-rate spread between
    #     a 200-kWh/mo and 600-kWh/mo household under the 2023 schedule;
    #   * cost / discount / inflation / degradation / O&M ranges mirror
    #     the corresponding monte_carlo_* ranges so the tornado and the
    #     Monte Carlo engine cite the same priors.
    sensitivity_yield_factor_range: tuple[float, float] = (0.90, 1.10)
    sensitivity_tariff_factor_range: tuple[float, float] = (0.80, 1.20)
    sensitivity_cost_egp_per_kw_range: tuple[float, float] = (30000.0, 45000.0)
    sensitivity_discount_rate_range: tuple[float, float] = (0.02, 0.08)
    sensitivity_tariff_inflation_range: tuple[float, float] = (0.05, 0.11)
    sensitivity_degradation_rate_range: tuple[float, float] = (0.002, 0.010)
    sensitivity_om_cost_fraction_range: tuple[float, float] = (0.005, 0.020)

    # Financial defaults
    # Analysis horizon: matches the standard PV module performance warranty
    # (25 years) and the analysis period adopted in most Egyptian PV
    # pre-feasibility studies.
    analysis_period_years: int = 25
    # Real discount rate for project finance — see PLAN.md: 4% real,
    # consistent with the cost-of-capital range typical for Egyptian
    # residential infrastructure investment under recent macro conditions.
    discount_rate: float = 0.04
    # Tariff escalation: EgyptERA residential rates have risen ~8 % per
    # year in real terms over the last decade as subsidies have been
    # rolled back. PLAN.md: 8 % ± 3 % (Day 9 Monte Carlo treats this as a
    # distribution; the basic model uses the central value).
    tariff_inflation_rate: float = 0.08
    # PV module performance degradation — industry consensus for
    # mono-crystalline silicon under guarantee terms. NREL median: ~0.5 %/yr.
    annual_degradation_rate: float = 0.005
    # Annual operations & maintenance cost as a fraction of capex —
    # cleaning, monitoring, minor electrical repairs. IRENA / IEA-PVPS
    # benchmark for residential rooftop PV: ~1 %/yr.
    om_cost_fraction: float = 0.01

    # Egypt residential tariff tiers — progressive marginal blocks, each
    # ``(upper_kwh_per_month, egp_per_kwh)`` pair. Lifted to settings so
    # the optimizer can be unit-tested with synthetic schedules and so a
    # future reform update only changes config, not the service code.
    egypt_residential_tariff_tiers: list[tuple[float, float]] = EGYPT_RESIDENTIAL_TARIFF_TIERS

    # Monte Carlo (Day 9, Contribution C) ─ default ensemble size and
    # default distribution shapes for each uncertain parameter. The
    # service applies these only when the request omits an override, so
    # tests can collapse any distribution to a deterministic constant.
    monte_carlo_default_n_simulations: int = 1000
    # NREL median module degradation is ~0.5 %/yr; bounds 0.2–1.0 %/yr
    # span the published warranty range for mono-Si under guarantee.
    monte_carlo_degradation_triangular: tuple[float, float, float] = (0.002, 0.005, 0.010)
    # EgyptERA decade trend: 8 % ± 3 %. Clipped at zero so a left-tail
    # draw cannot represent a tariff *cut* that the policy regime makes
    # implausible at the analysis horizon.
    monte_carlo_tariff_inflation_normal: tuple[float, float] = (0.08, 0.03)
    # IRENA residential rooftop O&M benchmark: 0.5–2.0 %/yr of capex.
    monte_carlo_om_fraction_triangular: tuple[float, float, float] = (0.005, 0.010, 0.020)
    # Egyptian market 2024 installer-quote spread; mode at the PLAN.md
    # central value of 35 000 EGP/kW.
    monte_carlo_cost_per_kw_triangular: tuple[float, float, float] = (30000.0, 35000.0, 45000.0)
    # Per-year yield multiplier for weather + soiling. Egyptian PV field
    # studies cluster within ±5 % of TMY-modelled output.
    monte_carlo_yield_factor_normal: tuple[float, float] = (1.0, 0.05)
    monte_carlo_yield_factor_clip: tuple[float, float] = (0.5, 1.5)
    # Inverter replacement event: most installers warranty 10–12 years;
    # 15 years is the upper bound of typical service life.
    monte_carlo_inverter_year_triangular: tuple[float, float, float] = (10.0, 12.0, 15.0)
    monte_carlo_inverter_cost_fraction_triangular: tuple[float, float, float] = (0.07, 0.10, 0.15)


settings = Settings()
