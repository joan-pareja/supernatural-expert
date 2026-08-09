"""Settings loaded from a `.env` file.

The process environment is never read or written. `dotenv_values` parses the file
into a plain mapping, and every client receives its credentials explicitly, so no
library can pick a secret up from `os.environ` behind our back.
"""

from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

# src/supernatural_expert/config.py -> supernatural_expert -> src -> repository root.
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = REPOSITORY_ROOT / ".env"


class MissingSettingError(RuntimeError):
    """Raised when `.env` does not define a setting the pipeline needs."""


@dataclass(frozen=True, slots=True)
class PostgresSettings:
    """Connection details for the local Docker Compose database."""

    host: str
    port: int
    database: str
    username: str
    password: str


@dataclass(frozen=True, slots=True)
class Settings:
    """Every setting the project needs, whether or not this run needs all of them."""

    postgres: PostgresSettings
    wikipedia_user_agent: str
    env_file: Path
    # Absent until someone answers a question. Ingestion, indexing, and lexical
    # search never call a model, so requiring a key here would stop a reviewer
    # loading the corpus before they have one.
    openai_api_key: str | None
    # Absent means telemetry is off, which is a supported way to run the project
    # rather than a misconfiguration. See docs/monitoring.md.
    logfire_write_token: str | None

    def require_openai_api_key(self) -> str:
        """Return the key, failing where it is needed rather than where it is read."""
        if self.openai_api_key is None:
            raise MissingSettingError(
                f"OPENAI_API_KEY is missing or empty in {self.env_file}. "
                "Answering questions needs it; loading and indexing the corpus does not."
            )
        return self.openai_api_key


def _clean(values: dict[str, str | None], key: str) -> str | None:
    value = values.get(key)
    return value.strip() if value and value.strip() else None


def _require(values: dict[str, str | None], key: str, env_file: Path) -> str:
    value = _clean(values, key)
    if value is None:
        raise MissingSettingError(f"{key} is missing or empty in {env_file}.")
    return value


def load_settings(env_file: Path = DEFAULT_ENV_FILE) -> Settings:
    """Read `.env` and return the settings, failing loudly on anything missing."""
    if not env_file.is_file():
        raise MissingSettingError(
            f"{env_file} does not exist. Copy .env.example to .env, or run scripts/setup-dev.ps1."
        )

    values = dotenv_values(env_file)
    port = _require(values, "POSTGRES_HOST_PORT", env_file)
    if not port.isdigit():
        raise MissingSettingError(f"POSTGRES_HOST_PORT must be a number, got {port!r}.")

    return Settings(
        postgres=PostgresSettings(
            host=_require(values, "POSTGRES_HOST", env_file),
            # The container always listens on 5432; this is the published host port.
            port=int(port),
            database=_require(values, "POSTGRES_DB", env_file),
            username=_require(values, "POSTGRES_USER", env_file),
            password=_require(values, "POSTGRES_PASSWORD", env_file),
        ),
        wikipedia_user_agent=_require(values, "WIKIPEDIA_USER_AGENT", env_file),
        env_file=env_file,
        openai_api_key=_clean(values, "OPENAI_API_KEY"),
        logfire_write_token=_clean(values, "LOGFIRE_WRITE_TOKEN"),
    )
