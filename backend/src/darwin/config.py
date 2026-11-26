"""Runtime settings of the whole backend, read from DARWIN_* variables and the root .env."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Providers pi knows natively: the environment variable it reads the key from, and the id of
# Haiku 5.5 there. Prices come from pi's own model data, identical on both.
PROVIDERS = {
    "anthropic": ("ANTHROPIC_API_KEY", "claude-haiku-5-5"),
    "openrouter": ("OPENROUTER_API_KEY", "anthropic/claude-haiku-5.5"),
}


class Settings(BaseSettings):
    """Runtime configuration, read from the environment (prefix DARWIN_) and .env."""

    # One .env at the repository root (Compose reads it too); a local one may override it.
    model_config = SettingsConfigDict(
        env_prefix="DARWIN_", env_file=("../.env", ".env"), extra="ignore"
    )

    # Defaults are relative to backend/, where the code runs in development; the data lives
    # at the repository root, where Compose mounts it.
    ledger_url: str = "sqlite+aiosqlite:///../data/ledger.sqlite"
    genome_dir: Path = Path("../genome")
    # Binaries, matches and artifacts. Containers spawned by the referee mount it at the same
    # path it has on the host, so it must be absolute (relative values are resolved here).
    data_dir: Path = Path("../data")
    # Trusted bare copy of every commit that matters; the agent never writes it.
    mirror_dir: Path = Path("../data/mirror.git")
    # The platform's own changelog, shown on the dashboard (the image copies it to /app).
    changelog_path: Path = Path("../CHANGELOG.md")
    changelog_en_path: Path = Path("../CHANGELOG.en.md")

    # "anthropic" or "openrouter" (any other provider must be configured in pi's models.json,
    # as the tests do). The key goes to pi in the variable that provider expects.
    llm_provider: str = "anthropic"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""  # empty: Haiku 5.5 under the provider's own id
    # pi's reasoning level, sent to Anthropic as the effort of adaptive thinking. High: at
    # "low" the agent kept to small safe tweaks; sessions still cost a few cents (DECISIONS #25).
    llm_thinking: str = "high"
    daily_budget_usd: float = 2.0
    # Per agent session: the orchestrator aborts pi past any of these.
    session_max_usd: float = 0.25
    session_max_tool_calls: int = 80
    session_max_minutes: float = 40.0
    reflection_every: int = 10  # iterations between two reflections

    # Commentary for the public site (Italian and English), written by the model directly
    # through the Anthropic SDK, never through pi: only with the anthropic provider and a key.
    # Its own daily budget, separate from the agent's. Prices in $ per million tokens.
    commentary_model: str = "claude-haiku-5-5"
    commentary_daily_usd: float = 0.20
    commentary_price_input: float = 0.10
    commentary_price_output: float = 0.50
    commentary_price_cache_read: float = 0.01
    commentary_price_cache_write: float = 0.125

    # pi, pinned, and the extension (repo folder `agent/`).
    agent_dir: Path = Path("../agent")
    tools_port: int = 4732

    # Tags every container this process starts; at startup it removes its leftovers.
    instance: str = "dev"
    docker_bin: str = "docker"
    docker_socket: str = "/var/run/docker.sock"
    lab_image: str = "darwin-lab"
    arena_image: str = "darwin-arena"
    anchors_image: str = "darwin-anchors"
    engine_cpus: float = 1.0
    engine_memory: str = "1g"
    build_cpus: float = 2.0
    build_memory: str = "4g"
    build_timeout_s: float = 900.0
    match_concurrency: int = 3

    # Lichess bot (account converted to BOT). Off unless enabled: it plays rated games.
    lichess_enabled: bool = False
    lichess_token: SecretStr = SecretStr("")
    lichess_url: str = "https://lichess.org"
    lichess_clock_s: int = 180
    lichess_increment_s: int = 2
    lichess_challenge_every_s: float = 120.0
    # Below Lichess's own caps (lila: 200 challenges sent a day per account, 100 games a day
    # against other bots), so the bot never runs into them and stays blocked for hours.
    lichess_challenges_per_day: int = 150
    lichess_bot_games_per_day: int = 90
    # Opponents are sought around this rating until ours settles (Lichess starts bots at
    # 3000). A first guess for a young engine; the anchors' Elo is a better one later.
    lichess_start_rating: int = 1200
    # The bot's public account: the site links to its games there. The API never holds the
    # token, so it does not learn the name from Lichess.
    lichess_account: str = "darwin-chess-bot"

    # Disk for job outputs (data/jobs): a ceiling per job and for all of them.
    job_disk_gb: float = 10.0
    jobs_disk_gb: float = 40.0

    api_port: int = 4730
    # Built dashboard served by the API in production; in development Vite serves it.
    frontend_dist: Path | None = None

    @model_validator(mode="after")
    def _default_model(self) -> "Settings":
        if not self.llm_model:
            if self.llm_provider not in PROVIDERS:
                raise ValueError(f"no default model for provider {self.llm_provider!r}")
            self.llm_model = PROVIDERS[self.llm_provider][1]
        return self

    def llm_key_env(self) -> dict[str, str]:
        """The API key as pi reads it for the configured provider."""
        if self.llm_provider not in PROVIDERS:
            return {}
        return {PROVIDERS[self.llm_provider][0]: self.llm_api_key.get_secret_value()}

    @field_validator(
        "genome_dir", "data_dir", "mirror_dir", "agent_dir", "changelog_path", "changelog_en_path"
    )
    @classmethod
    def _absolute(cls, value: Path) -> Path:
        return value.expanduser().resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
