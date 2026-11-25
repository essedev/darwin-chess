from pathlib import Path

from pydantic import SecretStr

from darwin.config import Settings
from darwin.ledger.store import Ledger
from darwin.orchestrator.loop import Orchestrator


def settings(tmp_path: Path, **lichess: object) -> Settings:
    return Settings(data_dir=tmp_path / "data", genome_dir=tmp_path / "genome",
                    mirror_dir=tmp_path / "mirror.git", **lichess)  # type: ignore[arg-type]  # fmt: skip


async def test_the_bot_runs_only_when_enabled_with_a_token(tmp_path: Path, ledger: Ledger) -> None:
    off = Orchestrator(settings(tmp_path, lichess_token=SecretStr("t")), ledger)
    assert off.lichess_client() is None
    no_token = Orchestrator(
        settings(tmp_path, lichess_enabled=True, lichess_token=SecretStr("")), ledger
    )
    assert no_token.lichess_client() is None
    on = Orchestrator(
        settings(tmp_path, lichess_enabled=True, lichess_token=SecretStr("t")), ledger
    )
    client = on.lichess_client()
    assert client is not None
    await client.close()


async def test_no_engine_while_gen_0_is_the_champion(tmp_path: Path, ledger: Ledger) -> None:
    await ledger.seed("0" * 40)
    assert await Orchestrator(settings(tmp_path), ledger).champion_engine() is None
