import pytest

from darwin.api import hub as hub_module
from darwin.api.hub import Full, Hub
from darwin.ledger.store import Ledger
from darwin.referee.judge import Phase


async def test_one_poller_feeds_every_viewer_and_new_ones_get_the_snapshot(
    ledger: Ledger,
) -> None:
    await ledger.seed("0" * 40)
    state = {"value": 1}
    hub = Hub(ledger, {"game": lambda: state})
    first = hub.subscribe()
    exp = await ledger.start_experiment(kind="iteration", phase=Phase.GENESIS,
                                        base_commit="0" * 40, base_generation_id=0,
                                        trigger="t")  # fmt: skip
    await ledger.add_event(exp, "thought", {"text": "hello"})
    await hub._tick()
    messages = [first.get_nowait() for _ in range(first.qsize())]
    assert any(m.startswith("event: agent") and "hello" in m for m in messages)
    assert any(m.startswith("event: game") for m in messages)
    late = hub.subscribe()
    assert late.get_nowait().startswith("event: game")  # the current game, at once
    await hub._tick()
    assert late.empty()  # nothing changed: nothing sent


async def test_the_number_of_viewers_is_capped(
    ledger: Ledger, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hub_module, "MAX_SUBSCRIBERS", 2)
    hub = Hub(ledger, {})
    hub.subscribe()
    hub.subscribe()
    with pytest.raises(Full):
        hub.subscribe()
