import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Satoshi's Crystal Ball")
    cryptocompare_api_key: str | None = os.getenv("CRYPTOCOMPARE_API_KEY") or None
    cache_file: Path = Path(os.getenv("CACHE_FILE", "data/bitcoin_usd_daily.csv"))
    cache_ttl_minutes: int = int(os.getenv("CACHE_TTL_MINUTES", "60"))
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()

