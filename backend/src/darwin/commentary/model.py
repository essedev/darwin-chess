"""The model call behind the commentary: one Messages API request with structured output.

Direct through the Anthropic SDK, never through pi: the agent never sees these calls, their
prompts or their texts. Any failure (API error, refusal, cut or malformed output) is logged
and returns None; nothing is stored and core goes on.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol

import anthropic
from anthropic.types import Message

from darwin.config import Settings

log = logging.getLogger(__name__)

MAX_TOKENS = 800
TIMEOUT_S = 60.0


@dataclass(frozen=True)
class Written:
    fields: dict[str, str]
    model: str
    input_tokens: int  # all of them: uncached, read from and written to the cache
    output_tokens: int
    cost_usd: float


class Writer(Protocol):
    """What the worker needs from a model; the tests give it a fake."""

    async def write(self, system: str, prompt: str, schema: dict[str, Any]) -> Written | None: ...


def cost_of(message: Message, settings: Settings) -> tuple[int, float]:
    """Input tokens (all kinds) and the cost in dollars, from the usage of a response."""
    usage = message.usage
    uncached = usage.input_tokens
    read = usage.cache_read_input_tokens or 0
    created = usage.cache_creation_input_tokens or 0
    cost = (
        uncached * settings.commentary_price_input
        + read * settings.commentary_price_cache_read
        + created * settings.commentary_price_cache_write
        + usage.output_tokens * settings.commentary_price_output
    ) / 1_000_000
    return uncached + read + created, cost


def parse(message: Message, schema: dict[str, Any]) -> dict[str, str] | None:
    """The fields of the structured output, or None (and a log line) when unusable."""
    if message.stop_reason == "refusal":
        details = message.stop_details
        log.warning("commentary: the model declined (%s)", details.category if details else "-")
        return None
    if message.stop_reason != "end_turn":
        log.warning("commentary: the model stopped on %s", message.stop_reason)
        return None
    text = next((block.text for block in message.content if block.type == "text"), None)
    if text is None:
        log.warning("commentary: no text in the response")
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        log.warning("commentary: the output is not JSON: %.200s", text)
        return None
    required = schema["required"]
    if not isinstance(data, dict) or any(
        not isinstance(data.get(name), str) or not data[name].strip() for name in required
    ):
        log.warning("commentary: the output misses a field: %.200s", text)
        return None
    return {name: data[name].strip() for name in required}


class AnthropicWriter:
    def __init__(self, client: anthropic.AsyncAnthropic, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    @classmethod
    def from_settings(cls, settings: Settings) -> "AnthropicWriter":
        # The key is passed explicitly: the SDK must not pick up other credentials found on
        # the machine (a profile, an environment variable meant for something else).
        client = anthropic.AsyncAnthropic(
            api_key=settings.llm_api_key.get_secret_value(), timeout=TIMEOUT_S, max_retries=2
        )
        return cls(client, settings)

    async def close(self) -> None:
        await self.client.close()

    async def write(self, system: str, prompt: str, schema: dict[str, Any]) -> Written | None:
        model = self.settings.commentary_model
        try:
            message = await self.client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config={
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": schema},
                },
            )
        except anthropic.RateLimitError:
            log.warning("commentary: rate limited, skipped")
            return None
        except anthropic.APIStatusError as error:
            log.error("commentary: API error %s: %s", error.status_code, error.message)
            return None
        except anthropic.APIConnectionError:
            log.warning("commentary: cannot reach the API", exc_info=True)
            return None
        input_tokens, cost = cost_of(message, self.settings)
        if message.stop_reason != "end_turn":
            log.info("commentary: unusable response cost %.5f $", cost)
        fields = parse(message, schema)
        if fields is None:
            return None
        return Written(fields, model, input_tokens, message.usage.output_tokens, cost)
