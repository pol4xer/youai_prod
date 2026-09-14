"""Environment-backed application settings."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


def _path(value: str, root: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def _boolean(value: str) -> bool:
    return value.casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    """All process configuration, resolved once at the composition root."""

    openai_api_key: str = field(repr=False)
    openai_model: str
    video_provider: str
    email_provider: str
    email_address: str
    database_path: Path
    output_dir: Path
    download_dir: Path
    reddit_user_agent: str
    headless: bool
    runtime_root: Path

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        values = os.environ if env is None else env
        runtime_root = Path(values.get("YOUAI_ROOT", Path.cwd())).expanduser().resolve()

        return cls(
            openai_api_key=values["OPENAI_API_KEY"],
            openai_model=values.get("OPENAI_MODEL", "gpt-5.6-luna"),
            video_provider=values.get("YOUAI_VIDEO_PROVIDER", "kapwing"),
            email_provider=values.get("YOUAI_EMAIL_PROVIDER", "console"),
            email_address=values.get("YOUAI_EMAIL_ADDRESS", ""),
            database_path=_path(
                values.get("YOUAI_DB_PATH", "var/youai.db"), runtime_root
            ),
            output_dir=_path(values.get("YOUAI_OUTPUT_DIR", "var/media"), runtime_root),
            download_dir=_path(
                values.get("YOUAI_DOWNLOAD_DIR", "var/downloads"), runtime_root
            ),
            reddit_user_agent=values.get(
                "YOUAI_REDDIT_USER_AGENT", "youai/0.1 (contact: local-operator)"
            ),
            headless=_boolean(values.get("YOUAI_HEADLESS", "false")),
            runtime_root=runtime_root,
        )
