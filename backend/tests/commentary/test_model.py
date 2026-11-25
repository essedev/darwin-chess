"""The real writer against a fake SDK client: no network, no spend."""

import json
from typing import Any, cast

import anthropic
import httpx2
import pytest
from anthropic.types import Message

from darwin.commentary import model
from darwin.commentary.model import MAX_TOKENS, AnthropicWriter
from darwin.commentary.prompts import IT_EN_SCHEMA
from darwin.config import Settings


def message(text: str = '{"it": "Ciao.", "en": "Hello."}', **fields: Any) -> Message:
    data: dict[str, Any] = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-5-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 200,
            "cache_read_input_tokens": 500,
            "cache_creation_input_tokens": 100,
        },
    }
    return Message.model_validate(data | fields)


class FakeMessages:
    def __init__(self, outcome: Message | Exception) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    async def create(self, **params: Any) -> Message:
        self.calls.append(params)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class FakeClient:
    def __init__(self, outcome: Message | Exception) -> None:
        self.messages = FakeMessages(outcome)


def writer(outcome: Message | Exception) -> tuple[AnthropicWriter, FakeMessages]:
    fake = FakeClient(outcome)
    return AnthropicWriter(cast(anthropic.AsyncAnthropic, fake), Settings()), fake.messages


async def test_one_structured_call_and_its_cost() -> None:
    write, calls = writer(message())
    written = await write.write("system", "prompt", IT_EN_SCHEMA)
    assert written is not None
    assert written.fields == {"it": "Ciao.", "en": "Hello."}
    assert (written.model, written.input_tokens, written.output_tokens) == (
        "claude-haiku-5-5", 1600, 200,
    )  # fmt: skip
    # 1000 x 0.10 + 500 x 0.01 + 100 x 0.125 + 200 x 0.50, per million.
    assert written.cost_usd == pytest.approx(217.5 / 1_000_000)
    (params,) = calls.calls
    assert params["model"] == "claude-haiku-5-5"
    assert params["max_tokens"] == MAX_TOKENS
    assert params["system"] == "system"
    assert params["messages"] == [{"role": "user", "content": "prompt"}]
    assert params["output_config"] == {
        "effort": "low",
        "format": {"type": "json_schema", "schema": IT_EN_SCHEMA},
    }


async def test_a_refusal_gives_nothing() -> None:
    refused = message(
        content=[],
        stop_reason="refusal",
        stop_details={"type": "refusal", "category": None, "explanation": None},
    )
    write, _ = writer(refused)
    assert await write.write("system", "prompt", IT_EN_SCHEMA) is None


@pytest.mark.parametrize(
    "response",
    [
        message(stop_reason="max_tokens", content=[{"type": "text", "text": '{"it": "Ci'}]),
        message(text="not json"),
        message(text=json.dumps({"it": "Ciao."})),
        message(text=json.dumps({"it": "  ", "en": "Hello."})),
    ],
)
async def test_cut_or_malformed_output_gives_nothing(response: Message) -> None:
    write, _ = writer(response)
    assert await write.write("system", "prompt", IT_EN_SCHEMA) is None


async def test_api_errors_are_swallowed() -> None:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    for error in (
        anthropic.InternalServerError(
            "boom", response=httpx2.Response(500, request=request), body=None
        ),
        anthropic.RateLimitError("slow", response=httpx2.Response(429, request=request), body=None),
        anthropic.APIConnectionError(request=request),
    ):
        write, _ = writer(error)
        assert await write.write("system", "prompt", IT_EN_SCHEMA) is None


def test_fields_are_trimmed() -> None:
    parsed = model.parse(message(text='{"it": " Ciao. ", "en": "Hello.\\n"}'), IT_EN_SCHEMA)
    assert parsed == {"it": "Ciao.", "en": "Hello."}
