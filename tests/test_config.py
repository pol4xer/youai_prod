from pathlib import Path

import pytest

from youai.config import Settings


def test_settings_resolve_relative_runtime_paths(tmp_path: Path) -> None:
    settings = Settings.from_env(
        {
            "OPENAI_API_KEY": "test-key",
            "YOUAI_EMAIL_ADDRESS": "creator@example.com",
            "YOUAI_ROOT": str(tmp_path),
            "YOUAI_DB_PATH": "state/test.db",
            "YOUAI_OUTPUT_DIR": "state/media",
            "YOUAI_DOWNLOAD_DIR": "state/downloads",
            "YOUAI_HEADLESS": "yes",
        }
    )

    assert settings.runtime_root == tmp_path
    assert settings.database_path == tmp_path / "state/test.db"
    assert settings.output_dir == tmp_path / "state/media"
    assert settings.download_dir == tmp_path / "state/downloads"
    assert settings.headless is True
    assert settings.openai_model == "gpt-5.6-luna"


def test_settings_keep_absolute_paths(tmp_path: Path) -> None:
    settings = Settings.from_env(
        {
            "OPENAI_API_KEY": "test-key",
            "YOUAI_EMAIL_PROVIDER": "temp-mail",
            "YOUAI_DB_PATH": str(tmp_path / "test.db"),
        }
    )

    assert settings.database_path == tmp_path / "test.db"
    assert settings.email_address == ""


def test_custom_video_provider_does_not_require_email() -> None:
    settings = Settings.from_env(
        {
            "OPENAI_API_KEY": "test-key",
            "YOUAI_VIDEO_PROVIDER": "my-video-service",
        }
    )

    assert settings.email_address == ""


def test_current_directory_is_the_default_runtime_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    settings = Settings.from_env(
        {
            "OPENAI_API_KEY": "test-key",
            "YOUAI_EMAIL_ADDRESS": "creator@example.com",
        }
    )

    assert settings.runtime_root == tmp_path
    assert settings.database_path == tmp_path / "var/youai.db"


def test_settings_repr_does_not_expose_the_api_key() -> None:
    settings = Settings.from_env({"OPENAI_API_KEY": "private-test-value"})

    assert "private-test-value" not in repr(settings)
    assert "openai_api_key" not in repr(settings)
