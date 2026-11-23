"""Configurare centralizată (variabile de mediu, vezi .env.example)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://tro:tro@localhost:5432/tro"

    # Județele țintă ale ETL-ului (coduri auto: SB, CJ, B...). "*" = toată țara.
    target_counties: str = "SB"
    # Județul implicit folosit de API/frontend când nu se trimite parametrul ?county=
    default_county: str = "SB"

    # SEAP: anii și trimestrele importate implicit
    seap_years: str = "2025,2026"
    seap_quarters: str = "1,2,3,4"
    seap_kinds: str = "ad,dan,contracte,atribuire_fara,initiere,modificari"
    data_dir: str = "/data"

    # Politețe față de serviciile publice
    user_agent: str = "TransparentRO-ETL/0.1 (civic transparency project, Romania)"
    anaf_min_interval_s: float = 1.1
    nominatim_min_interval_s: float = 1.1
    http_timeout_s: float = 120.0

    # Bilanțuri ANAF doar pentru firme cu încasări publice peste prag (reduce numărul de cereri)
    bilant_min_public_ron: float = 50_000
    bilant_max_companies: int = 400

    # API
    cors_origins: str = "http://localhost:3000"
    cache_ttl_s: int = 300
    public_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"

    # Faza 3
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    mail_provider: str = "console"  # console | smtp
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "TransparentRO <alerte@localhost>"
    smtp_starttls: bool = True

    risk_thresholds_path: str = Field(default="")

    @property
    def target_county_list(self) -> list[str]:
        return [c.strip().upper() for c in self.target_counties.split(",") if c.strip()]

    @property
    def all_counties(self) -> bool:
        return "*" in self.target_county_list


@lru_cache
def get_settings() -> Settings:
    return Settings()
