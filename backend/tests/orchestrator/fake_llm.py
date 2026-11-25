"""A scripted OpenAI-compatible chat endpoint, so pi can run a whole session for free.

Each request answers with the next step of the script, chosen by how many tool results the
conversation already holds.
"""

import json
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

Step = dict[str, Any]  # {"tool": name, "args": {...}} or {"text": "..."}


def make_app(script: list[Step], seen: list[dict[str, Any]]) -> FastAPI:
    app = FastAPI()

    @app.post("/v1/chat/completions")
    async def complete(request: Request) -> Any:
        body = await request.json()
        seen.append(body)
        done = sum(1 for message in body["messages"] if message.get("role") == "tool")
        step = script[min(done, len(script) - 1)]
        if "tool" in step:
            delta: dict[str, Any] = {
                "role": "assistant",
                "content": f"Calling {step['tool']}.",
                "tool_calls": [
                    {
                        "index": 0,
                        "id": f"call_{uuid.uuid4().hex[:8]}",
                        "type": "function",
                        "function": {"name": step["tool"], "arguments": json.dumps(step["args"])},
                    }
                ],
            }
            finish = "tool_calls"
        else:
            delta, finish = {"role": "assistant", "content": step["text"]}, "stop"
        usage = {"prompt_tokens": 1000, "completion_tokens": 50, "total_tokens": 1050}
        if not body.get("stream"):
            message = {k: v for k, v in delta.items() if k != "tool_calls"}
            if "tool_calls" in delta:
                message["tool_calls"] = [
                    {k: v for k, v in c.items() if k != "index"} for c in delta["tool_calls"]
                ]
            return JSONResponse(
                {
                    "id": "x",
                    "object": "chat.completion",
                    "model": body["model"],
                    "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                    "usage": usage,
                }
            )

        def chunk(payload: dict[str, Any]) -> str:
            return (
                "data: "
                + json.dumps(
                    {
                        "id": "x",
                        "object": "chat.completion.chunk",
                        "model": body["model"],
                        **payload,
                    }
                )
                + "\n\n"
            )

        async def stream() -> Any:
            yield chunk({"choices": [{"index": 0, "delta": delta, "finish_reason": None}]})
            yield chunk({"choices": [{"index": 0, "delta": {}, "finish_reason": finish}]})
            yield chunk({"choices": [], "usage": usage})
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app
