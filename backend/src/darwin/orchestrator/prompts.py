"""What the agent reads. Prompts are in English: they go to the model.

The system prompt is fixed (and so cached by the provider); everything that changes goes in
the session prompt, kept short because every token of it is paid on every call.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

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
- /genome: the engine's git repository (your working tree). No network. `cargo` works offline
  with the standard library and a vendored set: rand 0.9, rayon 1.12, bytemuck 1.25 (add
  them to Cargo.toml as usual; nothing else resolves).
- Your past work is in the same git repository: every candidate you submitted, rejected ones
  included, as refs/darwin/exp-<id> (exp-<id>-rebased when the referee replayed it on a newer
  champion), and every champion as refs/darwin/gen-<n>. For example
  `git diff HEAD refs/darwin/exp-11` or `git show refs/darwin/exp-11:src/main.rs` shows
  attempt #11, so a failed idea can be fixed instead of rewritten.
- Python 3 with PyTorch 2.15 (CPU) and numpy is available, for training and tooling. The
  engine itself stays in Rust.
- The referee runs target/release/genome alone, with no other file: embed whatever it needs
  (network weights, tables) in the binary, for example with include_bytes!.
- Jobs (run_job) get 2 CPUs, 4 GB of RAM, up to 12 hours and a disk quota (10 GB each, 40 GB
  in total); delete outputs you no longer need. A job runs on a copy of your working tree as
  it is when you start it, uncommitted changes included: /job/src, its working directory
  (/jobs/<id>/src from a session), with its output in /job/out (/jobs/<id>/out). /memory is
  not mounted in jobs: copy into /genome what a job needs before starting it. When a job
  ends, a new session starts, woken by job_done:<id>.
- /memory/NOTES.md and /memory/STRATEGY.md: your memory across sessions. They are not part of
  the engine and survive rejected experiments. Keep both short: they are in your prompt.
- /jobs/<id>/out: output of jobs you started with run_job.
- Read /genome/CONTRACT.md for what the referee requires (UCI, `perft <depth>` divide output).

## How a session works
1. Read the state below, your notes and strategy; look at the code you need.
2. Work on what you think matters most. Often that is one change, built with
   `cargo build --release`, checked (perft_check, your own tests, games against the previous
   version) and submitted with a clear hypothesis; the session ends there.

Be curious, and do not feel limited: nothing ties you to small edits, to one file or to the
way you have worked so far. When understanding something is worth more than a quick change,
spend the session on it and write what you found in your notes; not every session has to end
with a submission. /memory persists across sessions: keep there the small tools and scripts
you want to reuse (large data belongs in job outputs).

Text you write between tool calls is shown live on a dashboard: one short plain
sentence each time, no Markdown. Details belong in the hypothesis and in your notes.
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
abandoned: the session ended without a submission (fine when you wrote down what you
learned). budget_stop: a session limit stopped it.
Changes to the engine are judged only if you submit them. When a session ends without a
submission, whatever changed in /genome is kept, never judged, as refs/darwin/wip-<id>.

## Tools
read, write, edit, bash run in the sandbox. perft_check asks the referee about your move
generator. experiments searches past experiments. run_job starts long CPU-only work
(self-play, training) that outlives the session. submit hands in the candidate.
lichess_losses shows recent games the champion lost on Lichess and where each went wrong.
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
    new_lichess_losses: int  # since the previous session started
    started_at: datetime | None = None
    max_minutes: float = 40.0
    max_usd: float = 0.25


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


def _limits_line(ctx: SessionContext) -> str:
    start = f"started at {ctx.started_at:%H:%M} UTC and " if ctx.started_at else ""
    return (
        f"This session {start}ends at the first of: {ctx.max_minutes:g} minutes, "
        f"{ctx.max_tool_calls} tool calls, {ctx.max_usd:g} $ of model cost (`date` gives the "
        "time). While it is open no other session starts and the referee waits for your "
        "submission."
    )


def session_prompt(ctx: SessionContext) -> str:
    parts = [
        f"# Session ({ctx.kind}, woken by: {ctx.trigger})",
        f"Phase: {ctx.phase.value}. Champion: gen-{ctx.champion.id} "
        f"({ctx.champion.commit_sha[:12]}). Your working tree starts at {ctx.base_commit[:12]}.",
        _limits_line(ctx),
    ]
    if ctx.new_lichess_losses:
        parts.append(
            f"Lichess: {ctx.new_lichess_losses} new "
            f"{'loss' if ctx.new_lichess_losses == 1 else 'losses'} since your last session "
            "(lichess_losses shows where each went wrong)."
        )
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
            "\n## Task: reflect\nDo not change the engine and do not submit. Review the whole "
            "history, not only the last tries: every experiment (the experiments tool, with a "
            "high limit), the code of each champion and attempt (git, refs/darwin/*), the "
            "Lichess losses (lichess_losses). Ask which kinds of change gained Elo and which "
            "did not, what you abandoned and why, what you have never tried, and whether the "
            "way you choose changes still fits. Then rewrite /memory/STRATEGY.md: what works, "
            "what to try next and in which order, what to stop doing. Keep it under 40 lines. "
            "Compact /memory/NOTES.md if it grew long."
        )
    else:
        parts.append(
            "\n## Task\nRun one experiment and submit it. Add a line to /memory/NOTES.md "
            "when you learn something worth keeping."
        )
    return "\n".join(parts)
