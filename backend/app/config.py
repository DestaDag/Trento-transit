from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SPOTS_PATH = str(
    Path(__file__).resolve().parents[1] / "data" / "trento_study_spots.json"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    tt_api_base_url: str = "https://app-tpl.tndigit.it/gtlservice"
    tt_api_username: str = "mittmobile"
    tt_api_password: str = "ecGsp.RHB3"
    tt_api_requested_with: str = "it.tndigit.mit"
    tt_trento_areas: str = "23,7,8"
    tt_trips_cache_ttl_seconds: int = 30
    database_path: str = "./data/radar.db"
    cache_stale_fallback: bool = True
    checkin_rate_limit_seconds: int = 900
    checkin_salt: str = "trento-radar-v1-salt"
    study_spots_path: str = _DEFAULT_SPOTS_PATH
    enable_scheduler: bool = True
