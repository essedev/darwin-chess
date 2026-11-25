"""One agent session: sandbox up, pi started with the session prompt, events consumed into
the ledger until pi settles or a ceiling is hit, everything torn down."""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from darwin.config import Settings
from darwin.ledger import lichess
from darwin.ledger.commentary import THOUGHT
from darwin.ledger.store import LabState, Ledger
from darwin.orchestrator import prompts
from darwin.orchestrator.jobs import Jobs
from darwin.orchestrator.pi import PiError, PiProcess
from darwin.orchestrator.sandbox import Sandbox
from darwin.orchestrator.tools import SessionTools, ToolRouter

log = logging.getLogger(__name__)

TEXT_LIMIT = 2000
LOSSES_COUNTED = 1000  # a cap on the count, far above what one session's gap can hold


@dataclass(frozen=True)
class Outcome:
    experiment_id: int
    submitted: str | None
    status: str  # "judging", "reflected", "abandoned", "budget_stop", "error"
    cost_usd: float


class Ceiling(Exception):
    """A per-session limit was hit; the message says which."""


def _text_of(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content or [] if b.get("type") == "text")


def _short(value: Any) -> Any:
    text = str(value)
    return text if len(text) <= TEXT_LIMIT else text[:TEXT_LIMIT] + "..."


class SessionRunner:
    def __init__(self, settings: Settings, ledger: Ledger, router: ToolRouter, jobs: Jobs) -> None:
        self.settings = settings
        self.ledger = ledger
        self.router = router
        self.jobs = jobs

    async def run(self, *, kind: str, trigger: str, state: LabState) -> Outcome:
        s = self.settings
        experiment_id = await self.ledger.start_experiment(
            kind=kind,
            phase=state.phase,
            base_commit=state.base_commit,
            base_generation_id=state.champion.id,
            trigger=trigger,
        )
        # Past experiments only: this session's own row is already in the ledger, and taking
        # it for the previous one showed an empty verdict and filed lessons one off.
        recent = [r for r in await self.ledger.recent_experiments(9) if r.id != experiment_id][:8]
        previous = recent[0] if recent else None
        # Lichess losses the agent has not been told about: since the previous session started.
        since = previous.created_at if previous else None
        new_losses = len(await lichess.losses(self.ledger, since=since, limit=LOSSES_COUNTED))
        box = Sandbox(s, experiment_id)
        tools = SessionTools(
            s,
            self.ledger,
            self.jobs,
            box,
            experiment_id,
            state.base_commit,
            previous.id if previous else None,
        )
        token = self.router.register(tools)
        pi: PiProcess | None = None
        cost = 0.0
        try:
            await box.start()
            await box.reset_to(state.base_commit)
            ctx = prompts.SessionContext(
                kind=kind,
                trigger=trigger,
                phase=state.phase,
                champion=state.champion,
                base_commit=state.base_commit,
                recent=recent,
                gates_of_last=await self.ledger.gates_of(previous.id) if previous else [],
                jobs=await self.ledger.jobs(),
                notes=await self._memory(box, "NOTES.md"),
                strategy=await self._memory(box, "STRATEGY.md"),
                max_tool_calls=s.session_max_tool_calls,
                new_lichess_losses=new_losses,
            )
            system = s.data_dir / "agent" / "system-prompt.md"
            system.parent.mkdir(parents=True, exist_ok=True)
            system.write_text(prompts.SYSTEM)
            pi = PiProcess(
                s,
                system_prompt=system,
                workdir=s.data_dir / "agent" / "cwd",
                extra_env={
                    "DARWIN_SANDBOX": box.name,
                    "DARWIN_DOCKER": s.docker_bin,
                    "DARWIN_TOOLS_URL": f"http://127.0.0.1:{s.tools_port}",
                    "DARWIN_TOOLS_TOKEN": token,
                },
            )
            await pi.start()
            await self.ledger.add_event(
                experiment_id, "status", {"state": "started", "kind": kind, "trigger": trigger}
            )
            try:
                cost = await asyncio.wait_for(
                    self._drive(pi, experiment_id, prompts.session_prompt(ctx)),
                    s.session_max_minutes * 60,
                )
            except TimeoutError as exc:
                raise Ceiling(f"session exceeded {s.session_max_minutes:g} minutes") from exc
        except Ceiling as limit:
            if pi is not None:
                await pi.abort()
            await self.ledger.add_event(
                experiment_id, "status", {"state": "stopped", "reason": str(limit)}
            )
            cost = await self.ledger.spend_of(experiment_id)
            if tools.submitted is None:
                await self.ledger.finish_experiment(experiment_id, "budget_stop", error=str(limit))
                return Outcome(experiment_id, None, "budget_stop", cost)
        except Exception as exc:
            log.exception("session %s failed", experiment_id)
            detail = f"{exc}\n{pi.stderr_tail() if pi else ''}"[-4000:]
            await self.ledger.finish_experiment(experiment_id, "error", error=detail)
            return Outcome(experiment_id, None, "error", await self.ledger.spend_of(experiment_id))
        finally:
            self.router.unregister(token)
            if pi is not None:
                await pi.close()
            await box.stop()
        if tools.submitted is not None:
            return Outcome(experiment_id, tools.submitted, "judging", cost)
        status = "reflected" if kind == "reflection" else "abandoned"
        await self.ledger.finish_experiment(experiment_id, status)
        return Outcome(experiment_id, None, status, cost)

    async def _memory(self, box: Sandbox, name: str) -> str:
        """Read through the sandbox: the file is the agent's, it could be a link to anywhere."""
        done = await box.exec(f"cat /memory/{name} 2>/dev/null || true")
        return done.output

    async def _drive(self, pi: PiProcess, experiment_id: int, prompt: str) -> float:
        s = self.settings
        cost, tool_calls = 0.0, 0
        started = time.monotonic()
        await pi.prompt(prompt)
        async for event in pi.events():
            kind = event.get("type")
            if kind == "message_end" and event["message"].get("role") == "assistant":
                message = event["message"]
                usage = message.get("usage") or {}
                call_cost = float((usage.get("cost") or {}).get("total") or 0.0)
                cost += call_cost
                await self.ledger.add_llm_call(
                    experiment_id,
                    s.llm_model,
                    input_tokens=int(usage.get("input") or 0),
                    cached_tokens=int(usage.get("cacheRead") or 0),
                    output_tokens=int(usage.get("output") or 0),
                    cost_usd=call_cost,
                )
                if text := _text_of(message).strip():
                    event_id = await self.ledger.add_event(
                        experiment_id, "thought", {"text": _short(text)}
                    )
                    if self.router.notify is not None:  # its Italian, for the live page
                        self.router.notify(THOUGHT, event_id)
                if message.get("stopReason") == "error":
                    await self.ledger.add_event(
                        experiment_id,
                        "status",
                        {"state": "provider_error", "error": _short(message.get("errorMessage"))},
                    )
                if cost > s.session_max_usd:
                    raise Ceiling(f"session cost {cost:.3f} $ over {s.session_max_usd} $")
            elif kind == "tool_execution_start":
                tool_calls += 1
                await self.ledger.add_event(
                    experiment_id,
                    "tool_call",
                    {"tool": event.get("toolName"), "args": _short(event.get("args"))},
                )
                if tool_calls > s.session_max_tool_calls:
                    raise Ceiling(f"more than {s.session_max_tool_calls} tool calls")
            elif kind == "tool_execution_end":
                result = event.get("result") or {}
                await self.ledger.add_event(
                    experiment_id,
                    "tool_result",
                    {
                        "tool": event.get("toolName"),
                        "error": bool(event.get("isError")),
                        "text": _short(_text_of(result)),
                    },
                )
            elif kind == "agent_settled":
                log.info(
                    "session %s settled after %.0fs, %.4f $",
                    experiment_id,
                    time.monotonic() - started,
                    cost,
                )
                return cost
        raise PiError(f"pi exited before settling: {pi.stderr_tail()[-500:]}")
