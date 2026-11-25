from pathlib import Path

import pytest

from darwin.config import Settings


def test_defaults_point_to_openrouter_haiku(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)  # no .env here: only code defaults apply
    settings = Settings()
    assert settings.llm_provider == "openrouter"
    assert "haiku" in settings.llm_model
    assert settings.daily_budget_usd == 2.0


def test_paths_are_made_absolute(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings()
    assert settings.data_dir == (tmp_path / "data").resolve()
    assert settings.mirror_dir.is_absolute() and settings.genome_dir.is_absolute()
