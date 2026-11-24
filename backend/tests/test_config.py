from pathlib import Path

import pytest

from darwin.config import Settings


def test_defaults_point_to_openrouter_haiku(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)  # no .env here: only code defaults apply
    settings = Settings()
    assert settings.llm_base_url.startswith("https://openrouter.ai")
    assert settings.daily_budget_usd == 2.0
