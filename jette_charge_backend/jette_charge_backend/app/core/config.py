from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "JETTE_CHARGE_BACKEND"
    app_env: str = "local"
    api_prefix: str = "/api/v2"

    keco_service_key: str = ""
    energy_service_key: str = ""

    database_url: str = "sqlite+aiosqlite:///./jette_charge.db"
    redis_url: str = "redis://localhost:6379/0"

    supported_zcode: str = "47"
    supported_zscodes: str = "47190,47150,47850"
    cache_fresh_seconds: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def supported_zscode_list(self) -> List[str]:
        return [x.strip() for x in self.supported_zscodes.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
