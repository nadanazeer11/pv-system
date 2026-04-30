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


settings = Settings()
