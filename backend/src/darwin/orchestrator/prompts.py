"""What the agent reads. Prompts are in English: they go to the model.

The system prompt is fixed (and so cached by the provider); everything that changes goes in
the session prompt, kept short because every token of it is paid on every call.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from darwin.ledger import models as m
from darwin.referee.judge import Phase

NOTES_TAIL_CHARS = 4000
STRATEGY_CHARS = 3000

SYSTEM = """\
# darwin

You are the only author of a chess engine written in Rust, in /genome. You improve it one
experiment at a time; an independent referee you cannot see or influence decides whether each
candidate survives. Nobody will answer questions: decide and act.

## Environment
- /genome: the engine's git repository (your working tree). `cargo` works offline only: use
  the standard library or crates vendored in the repository. No network.
- /memory/NOTES.md and /memory/STRATEGY.md: your memory across sessions. They are not part of
  the engine and survive rejected experiments. Keep both short: they are in your prompt.
- /jobs/<id>/out: output of jobs you started with run_job.
- Read /genome/CONTRACT.md for what the referee requires (UCI, `perft <depth>` divide output).

## How a session works
1. Read the state below, your notes and strategy; look at the code you need.
2. Make one focused change. Build with `cargo build --release` and check it (perft_check,
   your own tests, a few games against the previous version if useful).
3. Call submit with a clear hypothesis. The session ends there.
Each session starts from a clean working tree at the base commit: unsubmitted work is lost.

## How you are judged
Gates in order, stopping at the first failure: build, perft on random positions, smoke games
(an illegal move, crash or timeout fails), then a match decided by SPRT. Genesis: build and
perft only. First steps: beat a random mover. Evolution: beat the current champion. Each
engine process gets one CPU core and its own clock.

## Verdicts
accepted: it passed; it is now your base (and, after a match, the new champion).
rejected: a gate failed; its details say which and why.
stale: not your fault. A new champion arrived while it waited and your change conflicted
with it, so it was never judged. Redo the idea on top of the new base if it still matters.
abandoned: the session ended without a submission. budget_stop: a session limit stopped it.
Work is only kept if you submit it: commits alone do not survive the session.

## Tools
read, write, edit, bash run in the sandbox. perft_check asks the referee about your move
generator. experiments searches past experiments. run_job starts long CPU-only work
(self-play, training) that outlives the session. submit hands in the candidate.
"""


@dataclass(frozen=True)
class SessionContext:
    kind: str  # "iteration" or "reflection"
    trigger: str
    phase: Phase
    champion: m.Generation
    base_commit: str
    recent: Sequence[m.Experiment]
    gates_of_last: Sequence[m.GateResult]
    jobs: Sequence[m.Job]
    notes: str
    strategy: str
    max_tool_calls: int


def _experiment_line(row: m.Experiment) -> str:
    verdict = row.status
    if row.rejected_at_gate:
        verdict += f" at {row.rejected_at_gate}"
    line = f"- #{row.id} [{row.phase}] {verdict}: {row.hypothesis or '(no submission)'}"
    if row.lesson:
        line += f" | lesson: {row.lesson}"
    return line


def _gate_line(gate: m.GateResult) -> str:
    detail = {k: v for k, v in gate.detail.items() if k != "pgn"}
    return f"- {gate.gate}: {'passed' if gate.passed else 'FAILED'} {detail}"


def session_prompt(ctx: SessionContext) -> str:
    parts = [
        f"# Session ({ctx.kind}, woken by: {ctx.trigger})",
        f"Phase: {ctx.phase.value}. Champion: gen-{ctx.champion.id} "
        f"({ctx.champion.commit_sha[:12]}). Your working tree starts at {ctx.base_commit[:12]}.",
        f"Tool calls available this session: {ctx.max_tool_calls}.",
    ]
    if ctx.recent:
        last = ctx.recent[0]
        parts.append(f"\n## Last verdict (#{last.id}: {last.status})")
        parts += [_gate_line(gate) for gate in ctx.gates_of_last] or ["- no gates ran"]
        failed_game = next((g for g in ctx.gates_of_last if "pgn" in g.detail), None)
        if failed_game is not None:
            parts.append(f"Failing game:\n{str(failed_game.detail['pgn'])[:1500]}")
        if last.lesson is None and last.status in {"accepted", "rejected"}:
            parts.append("Pass a one-line lesson about it as lesson_for_previous when you submit.")
        parts.append("\n## Recent experiments (newest first)")
        parts += [_experiment_line(row) for row in ctx.recent]
    if ctx.jobs:
        parts.append("\n## Jobs")
        parts += [f"- job {j.id}: {j.status} `{j.command[:80]}`" for j in ctx.jobs[:5]]
    parts.append(f"\n## /memory/STRATEGY.md\n{ctx.strategy[:STRATEGY_CHARS]}")
    parts.append(f"\n## /memory/NOTES.md (tail)\n{ctx.notes[-NOTES_TAIL_CHARS:]}")
    if ctx.kind == "reflection":
        parts.append(
            "\n## Task: reflect\nDo not change the engine and do not submit. Review the "
            "experiments (use the experiments tool for more), then rewrite "
            "/memory/STRATEGY.md: what works, what to try next and in which order, what to "
            "stop doing. Keep it under 40 lines. Compact /memory/NOTES.md if it grew long."
        )
    else:
        parts.append(
            "\n## Task\nRun one experiment and submit it. Add a line to /memory/NOTES.md "
            "when you learn something worth keeping."
        )
    return "\n".join(parts)
