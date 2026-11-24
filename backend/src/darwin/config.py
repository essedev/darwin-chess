from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from the environment (prefix DARWIN_) and .env."""

    model_config = SettingsConfigDict(env_prefix="DARWIN_", env_file=".env", extra="ignore")

    ledger_url: str = "sqlite+aiosqlite:///./data/ledger.sqlite"
    genome_dir: Path = Path("../genome")

    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = "anthropic/claude-haiku-5.5"
    daily_budget_usd: float = 2.0

    api_port: int = 4730


@lru_cache
def get_settings() -> Settings:
    return Settings()
