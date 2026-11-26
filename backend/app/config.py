from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    tt_api_base_url: str = "https://app-tpl.tndigit.it/gtlservice"
    tt_api_username: str = ""
    tt_api_password: str = ""
    tt_api_requested_with: str = "it.tndigit.mit"
    tt_trips_cache_ttl_seconds: int = 30
    database_path: str = "/data/trento-transit.db"
    cache_stale_fallback: bool = True