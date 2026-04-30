from pydantic_settings import BaseSettings, SettingsConfigDict


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


settings = Settings()
