"""The bot's lobby against a fake Lichess: which challenges it takes and whom it challenges.
No game is played here, so no container runs."""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from darwin.ledger.store import Ledger
from darwin.lichess import rules
from darwin.referee.models import EngineSpec

from .conftest import bot_settings, running_bot, until
from .fake_lichess import FakeLichess, blitz_user

UNUSED_ENGINE = EngineSpec(name="gen-1", image="none", command=("none",))


async def champion() -> tuple[int, EngineSpec] | None:
    return 1, UNUSED_ENGINE


async def no_champion() -> tuple[int, EngineSpec] | None:
    return None


def offer(challenge_id: str, by: str, variant: str = "standard") -> dict[str, Any]:
    return {"type": "challenge", "challenge": {
        "id": challenge_id, "challenger": {"id": by.lower(), "name": by},
        "variant": {"key": variant}, "rated": True, "speed": "blitz",
        "timeControl": {"type": "clock", "limit": 180, "increment": 2},
    }}  # fmt: skip


async def test_takes_one_fitting_challenge_at_a_time(
    tmp_path: Path, fake: FakeLichess, lichess_url: str, ledger: Ledger
) -> None:
    for event in (
        offer("mine", "DarwinBot"),  # our own challenge, echoed back: not ours to answer
        offer("c960", "Odd", variant="chess960"),
        offer("good", "Fine"),
        offer("next", "Late"),  # the accepted one has not started yet
    ):
        fake.events.put_nowait(event)
    async with running_bot(bot_settings(tmp_path, lichess_url), ledger, champion) as bot:
        await until(lambda: len(fake.declined) == 2, 10)
        assert fake.declined == [("c960", "variant"), ("next", "later")]
        assert fake.accepted == ["good"]
        assert bot.pending_id == "good" and bot.busy()

        fake.events.put_nowait({"type": "challengeCanceled", "challenge": {"id": "good"}})
        await until(lambda: not bot.busy(), 10)


async def test_declines_while_there_is_no_champion(
    tmp_path: Path, fake: FakeLichess, lichess_url: str, ledger: Ledger
) -> None:
    fake.events.put_nowait(offer("early", "Eager"))
    async with running_bot(bot_settings(tmp_path, lichess_url), ledger, no_champion):
        await until(lambda: bool(fake.declined), 10)
    assert fake.declined == [("early", "later")]
    assert fake.accepted == []


async def test_challenges_a_bot_near_its_rating_once(
    tmp_path: Path, fake: FakeLichess, lichess_url: str, ledger: Ledger
) -> None:
    fake.bots += [blitz_user("Near", 1700), blitz_user("Far", 2400)]
    settings = bot_settings(tmp_path, lichess_url, challenge_every_s=0.1)
    async with running_bot(settings, ledger, champion):
        await until(lambda: bool(fake.challenged), 10)
        await asyncio.sleep(0.5)  # pending: no second challenge meanwhile
    assert len(fake.challenged) == 1
    name, form = fake.challenged[0]
    assert name == "Near"
    assert form["rated"] == "true"
    assert (form["clock.limit"], form["clock.increment"]) == ("180", "2")
    assert form["variant"] == "standard"


async def test_a_refused_challenge_moves_on_to_another_bot_at_once(
    tmp_path: Path,
    fake: FakeLichess,
    lichess_url: str,
    ledger: Ledger,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def first_listed(bots: list[dict[str, Any]], *, me: str, **_: Any) -> str | None:
        names = [str(b["username"]) for b in bots if str(b["username"]).lower() != me]
        return names[0] if names else None

    monkeypatch.setattr(rules, "pick_opponent", first_listed)  # Busy first, then Free
    fake.bots += [blitz_user("Busy", 1600), blitz_user("Free", 1600)]
    fake.refusing.add("Busy")
    settings = bot_settings(tmp_path, lichess_url, challenge_every_s=3)
    async with running_bot(settings, ledger, champion):
        await until(lambda: any(name == "Free" for name, _ in fake.challenged), 10)
    assert [name for name, _ in fake.challenged] == ["Busy", "Free"]
    # Same matchmaking round: the retry did not wait for the next one, 3 s later.
    assert fake.challenged_at[1] - fake.challenged_at[0] < 1.0
