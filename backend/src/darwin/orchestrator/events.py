"""The payloads a session writes to `agent_events`, shaped from pi's RPC events.

Every text is capped at `TEXT_LIMIT` characters, cut with a trailing "..." and flagged with
`cut`. Tool arguments stay a JSON object: each string inside is cut on its own, so a long
edit keeps its path and the start of every change instead of ending halfway through a repr.
The formats are in docs/DATABASE_SCHEMA.md (agent_events).
"""

from typing import Any

TEXT_LIMIT = 2000
LIST_LIMIT = 20  # items kept of a list argument (an edit's changes): the rest is dropped
DEPTH_LIMIT = 4  # nesting kept in arguments; deeper values become their text


def clip(text: str) -> tuple[str, bool]:
    """The text within the cap, and whether it was cut."""
    if len(text) <= TEXT_LIMIT:
        return text, False
    return text[:TEXT_LIMIT] + "...", True


def short(value: Any) -> str:
    return clip(str(value))[0]


def text_of(message: dict[str, Any]) -> str:
    """The visible text of a message or a tool result: its text blocks, joined."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content or [] if b.get("type") == "text")


def reasoning_of(message: dict[str, Any]) -> str:
    """The model's reasoning in an assistant message: the text of its thinking blocks.

    pi asks Anthropic for summarized thinking and keeps it as `{"type": "thinking",
    "thinking": ...}`; a redacted block carries only an opaque payload and is skipped.
    """
    content = message.get("content")
    if not isinstance(content, list):
        return ""
    texts = [
        str(b.get("thinking") or "").strip()
        for b in content
        if isinstance(b, dict) and b.get("type") == "thinking" and not b.get("redacted")
    ]
    return "\n\n".join(t for t in texts if t)


def bounded(value: Any, depth: int = 0) -> tuple[Any, bool]:
    """A JSON value with every string clipped, lists capped and nesting limited; and whether
    anything was cut."""
    if value is None or isinstance(value, bool | int | float):
        return value, False
    if isinstance(value, str):
        return clip(value)
    if depth >= DEPTH_LIMIT:
        return clip(str(value))[0], True
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        cut = False
        for key, item in value.items():
            out[str(key)], item_cut = bounded(item, depth + 1)
            cut = cut or item_cut
        return out, cut
    if isinstance(value, list | tuple):
        items = [bounded(item, depth + 1) for item in list(value)[:LIST_LIMIT]]
        return [item for item, _ in items], len(value) > LIST_LIMIT or any(c for _, c in items)
    return clip(str(value))


def message_text(text: str) -> dict[str, Any]:
    """A `thought` (what the agent writes between calls) or its `reasoning`."""
    clipped, cut = clip(text)
    return {"text": clipped, "cut": cut}


def tool_call(event: dict[str, Any]) -> dict[str, Any]:
    args, cut = bounded(event.get("args") if event.get("args") is not None else {})
    return {"tool": event.get("toolName"), "call_id": event.get("toolCallId"), "args": args,
            "cut": cut}  # fmt: skip


def tool_result(event: dict[str, Any]) -> dict[str, Any]:
    text, cut = clip(text_of(event.get("result") or {}))
    return {
        "tool": event.get("toolName"),
        "call_id": event.get("toolCallId"),
        "error": bool(event.get("isError")),
        "text": text,
        "cut": cut,
    }
