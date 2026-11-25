from pathlib import Path

import pytest

from darwin.config import Settings


def test_defaults_point_to_haiku_on_anthropic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)  # no .env here: only code defaults apply
    settings = Settings(llm_api_key="k")
    assert (settings.llm_provider, settings.llm_model) == ("anthropic", "claude-haiku-5-5")
    assert settings.llm_key_env() == {"ANTHROPIC_API_KEY": "k"}
    assert settings.daily_budget_usd == 2.0


def test_openrouter_gets_its_own_model_id_and_key_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings(llm_provider="openrouter", llm_api_key="k")
    assert settings.llm_model == "anthropic/claude-haiku-5.5"
    assert settings.llm_key_env() == {"OPENROUTER_API_KEY": "k"}


def test_an_unknown_provider_needs_an_explicit_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="no default model"):
        Settings(llm_provider="fake")
    assert Settings(llm_provider="fake", llm_model="scripted").llm_key_env() == {}


def test_paths_are_made_absolute(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings()
    assert settings.data_dir == (tmp_path / "data").resolve()
    assert settings.mirror_dir.is_absolute() and settings.genome_dir.is_absolute()
