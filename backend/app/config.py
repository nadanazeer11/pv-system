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
    overpass_url: str = "https://overpass-api.de/api/interpreter"

    # PV hardware defaults
    panel_rated_watts: float = 450.0
    panel_area_m2: float = 1.8
    roof_utilization_factor: float = 0.7
    inverter_efficiency: float = 0.96

    # Egypt-specific defaults
    default_tilt_deg: float = 26.0
    default_azimuth_deg: float = 180.0
    egypt_grid_emission_kg_per_kwh: float = 0.46
    installed_cost_egp_per_kw: float = 35000.0

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
