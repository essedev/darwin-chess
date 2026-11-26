"""What a session writes to agent_events from pi's events: reasoning, thoughts, tool calls
with their arguments as JSON and the call id that ties a result to its call."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select

from darwin.config import Settings
from darwin.ledger import models as m
from darwin.ledger.store import Ledger
from darwin.orchestrator import events
from darwin.orchestrator.jobs import Jobs
from darwin.orchestrator.pi import PiProcess
from darwin.orchestrator.session import SessionRunner
from darwin.orchestrator.tools import ToolRouter
from darwin.referee.judge import Phase

LONG = "x" * (events.TEXT_LIMIT + 500)


def assistant(*content: dict[str, Any]) -> dict[str, Any]:
    usage = {"input": 10, "output": 5, "cacheRead": 0, "cost": {"total": 0.001}}
    return {"type": "message_end",
            "message": {"role": "assistant", "content": list(content), "usage": usage}}  # fmt: skip


# One model turn as pi 1.5.2 reports it in RPC mode: the message with its thinking, text and
# tool call, then the call's execution, then a final message and the end.
PI_EVENTS: list[dict[str, Any]] = [
    assistant(
        {"type": "thinking", "thinking": "The eval ignores mobility.", "thinkingSignature": "s"},
        {
            "type": "thinking",
            "thinking": "[Reasoning redacted]",
            "thinkingSignature": "e",
            "redacted": True,
        },
        {"type": "text", "text": "Let me read the evaluation."},
        {"type": "toolCall", "id": "toolu_1", "name": "edit", "arguments": {}},
    ),  # fmt: skip
    {
        "type": "tool_execution_start",
        "toolCallId": "toolu_1",
        "toolName": "edit",
        "args": {"path": "src/main.rs", "edits": [{"oldText": "a", "newText": LONG}]},
    },
    {
        "type": "tool_execution_end",
        "toolCallId": "toolu_1",
        "toolName": "edit",
        "result": {"content": [{"type": "text", "text": "Successfully replaced 1 block"}]},
        "isError": False,
    },
    assistant({"type": "text", "text": "Done."}),
    {"type": "agent_settled"},
]


class FakePi:
    def __init__(self, script: list[dict[str, Any]]) -> None:
        self.script = script

    async def prompt(self, message: str) -> None:
        return None

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        for event in self.script:
            yield event


async def test_a_turn_lands_as_reasoning_thought_call_and_result(
    tmp_path: Path, ledger: Ledger
) -> None:
    await ledger.seed("0" * 40)
    experiment = await ledger.start_experiment(
        kind="iteration", phase=Phase.GENESIS, base_commit="0" * 40,
        base_generation_id=0, trigger="start",
    )  # fmt: skip
    runner = SessionRunner(Settings(data_dir=tmp_path), ledger, ToolRouter(), cast(Jobs, None))
    cost = await runner._drive(cast(PiProcess, FakePi(PI_EVENTS)), experiment, "go")
    assert cost == 0.002
    async with ledger.session() as s:
        rows = (await s.scalars(select(m.AgentEvent).order_by(m.AgentEvent.id))).all()
    assert [r.kind for r in rows] == ["reasoning", "thought", "tool_call", "tool_result", "thought"]
    reasoning, thought, call, result, _ = (r.payload for r in rows)
    assert reasoning == {"text": "The eval ignores mobility.", "cut": False}
    assert thought == {"text": "Let me read the evaluation.", "cut": False}
    assert call["tool"] == "edit" and call["call_id"] == "toolu_1" and call["cut"] is True
    (edit,) = call["args"]["edits"]
    assert call["args"]["path"] == "src/main.rs" and edit["oldText"] == "a"
    assert edit["newText"] == "x" * events.TEXT_LIMIT + "..."
    assert result == {"tool": "edit", "call_id": "toolu_1", "error": False,
                      "text": "Successfully replaced 1 block", "cut": False}  # fmt: skip


def test_arguments_stay_an_object_with_every_string_cut_on_its_own() -> None:
    payload = events.tool_call(
        {"toolCallId": "c", "toolName": "bash", "args": {"command": LONG, "timeout": 30}}
    )
    assert payload["args"] == {"command": "x" * events.TEXT_LIMIT + "...", "timeout": 30}
    assert payload["cut"] is True
    small = events.tool_call({"toolCallId": "c", "toolName": "experiments", "args": None})
    assert (small["args"], small["cut"]) == ({}, False)


def test_long_lists_and_deep_nesting_are_bounded() -> None:
    value, cut = events.bounded({"edits": [{"oldText": "a"}] * (events.LIST_LIMIT + 5)})
    assert cut and len(value["edits"]) == events.LIST_LIMIT
    deep, cut = events.bounded({"a": {"b": {"c": {"d": {"e": 1}}}}})
    assert cut and deep == {"a": {"b": {"c": {"d": "{'e': 1}"}}}}


def test_a_long_result_is_flagged_as_cut() -> None:
    payload = events.tool_result(
        {"toolCallId": "c", "toolName": "bash", "isError": True,
         "result": {"content": [{"type": "text", "text": LONG}]}}
    )  # fmt: skip
    assert payload["error"] and payload["cut"] and payload["text"].endswith("...")


def test_no_reasoning_without_readable_thinking() -> None:
    redacted = {"type": "thinking", "thinking": "[Reasoning redacted]", "redacted": True}
    omitted = {"type": "thinking", "thinking": "", "thinkingSignature": "s"}
    assert events.reasoning_of({"content": [redacted, omitted]}) == ""
    assert events.reasoning_of({"content": "plain text"}) == ""
