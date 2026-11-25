"""The commentary worker: one task in core consuming a queue, so writing commentary never
holds up judging, the agent or the Lichess bot.

Subjects arrive from the orchestrator (a finished Lichess game, a verdict, a submission)
and, at startup and every new day, from a backfill of what is still missing. Each call
first checks the commentary's own daily budget; when it is spent the queue is dropped and
the worker sleeps until the next UTC day, when the backfill picks the rest up again.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from darwin.api.mind import read_mind
from darwin.commentary import prompts
from darwin.commentary.model import AnthropicWriter, Writer, Written
from darwin.config import Settings
from darwin.ledger import commentary as records
from darwin.ledger import lichess
from darwin.ledger import models as m
from darwin.ledger.commentary import Subject
from darwin.ledger.store import Ledger
from darwin.orchestrator.budget import day_start
from darwin.orchestrator.prompts import SYSTEM as AGENT_SYSTEM
from darwin.referee import analysis

log = logging.getLogger(__name__)

CALL_RESERVE_USD = 0.002  # a generous ceiling for one call, checked before making it

# The memory files are looked at every few minutes; one that changes often (the notes, after
# most sessions) is translated at most once an hour, the latest version. Past this size a
# file stays in English: its translation would be a long, costly call at every change.
MEMORY_CHECK_S = 600.0
MEMORY_EVERY = timedelta(hours=1)
MEMORY_MAX_CHARS = 16_000
MEMORY_MAX_TOKENS = 8000

# Stockfish over a game, from our side (the referee's analysis; the tests pass a fake).
Evaluate = Callable[[Settings, list[str], str], Awaitable[list[int]]]


class BudgetSpent(Exception):
    pass


def budget_allows(spent_today: float, daily_usd: float) -> bool:
    return spent_today + CALL_RESERVE_USD <= daily_usd


def split(total: int, parts: int) -> list[int]:
    """Spreads a token count over the rows one call produced, keeping the sum exact."""
    base, extra = divmod(total, parts)
    return [base + (1 if i < extra else 0) for i in range(parts)]


class CommentaryWorker:
    def __init__(
        self,
        settings: Settings,
        ledger: Ledger,
        writer: Writer | None,
        *,
        evaluate: Evaluate = analysis.evaluate,
    ) -> None:
        self.settings = settings
        self.ledger = ledger
        self.writer = writer
        self.evaluate = evaluate
        self.queue: asyncio.Queue[Subject] = asyncio.Queue()
        self.pending: set[Subject] = set()

    @classmethod
    def from_settings(cls, settings: Settings, ledger: Ledger) -> "CommentaryWorker":
        """On only with the anthropic provider and a key; otherwise off, said once."""
        writer = None
        if settings.llm_provider != "anthropic":
            log.info("commentary off: provider %s is not anthropic", settings.llm_provider)
        elif not settings.llm_api_key.get_secret_value():
            log.info("commentary off: no API key")
        else:
            writer = AnthropicWriter.from_settings(settings)
        return cls(settings, ledger, writer)

    @property
    def enabled(self) -> bool:
        return self.writer is not None

    async def close(self) -> None:
        if isinstance(self.writer, AnthropicWriter):
            await self.writer.close()

    # Intake

    def enqueue(self, kind: str, subject_id: int) -> None:
        """Never blocks, never raises: a no-op when commentary is off."""
        subject = Subject(kind, subject_id)
        if not self.enabled or subject in self.pending:
            return
        self.pending.add(subject)
        self.queue.put_nowait(subject)

    async def after_verdict(self, experiment_id: int) -> None:
        """The match (when there was one) and the hypothesis of a judged experiment."""
        if not self.enabled:
            return
        try:
            for match_id in await records.match_ids_of(self.ledger, experiment_id):
                self.enqueue(records.MATCH, match_id)
        except Exception:
            log.exception("commentary: cannot read the matches of %s", experiment_id)
        self.enqueue(records.HYPOTHESIS, experiment_id)

    def after_submit(self, experiment_id: int) -> None:
        """The title and the Italian of a hypothesis, as soon as it is submitted."""
        self.enqueue(records.TITLE, experiment_id)
        self.enqueue(records.HYPOTHESIS, experiment_id)

    async def backfill(self) -> int:
        missing = await records.missing(self.ledger)
        for subject in missing:
            self.enqueue(subject.kind, subject.subject_id)
        if missing:
            log.info("commentary: %d subjects without commentary queued", len(missing))
        return len(missing)

    # Work

    async def run(self) -> None:
        if not self.enabled:
            return
        while True:
            try:
                await self.backfill()
            except Exception:
                log.exception("commentary: backfill failed")
            await self.work()  # returns only when today's budget is spent
            await self._until_tomorrow()

    async def run_memory(self) -> None:
        """Its own task in core: the memory files are checked every few minutes."""
        if not self.enabled:
            return
        while True:
            try:
                await self.queue_memory()
            except Exception:
                log.exception("commentary: cannot check the memory files")
            await asyncio.sleep(MEMORY_CHECK_S)

    def memory_texts(self) -> dict[str, str]:
        """The agent's strategy, notes and instructions as the site shows them now."""
        mind = read_mind(self.settings.data_dir, AGENT_SYSTEM)
        return {
            records.STRATEGY: mind["strategy"],
            records.NOTES: mind["notes"],
            records.PROMPT: mind["system_prompt"],
        }

    async def queue_memory(self) -> None:
        """Queues the translation of each memory text whose current version has none."""
        texts = await asyncio.to_thread(self.memory_texts)
        for kind, text in texts.items():
            if not text.strip() or len(text) > MEMORY_MAX_CHARS:
                continue
            subject = Subject(kind, records.content_id(text))
            if await records.exists(self.ledger, subject):
                continue
            last = await records.latest_of(self.ledger, kind)
            if kind != records.PROMPT and last and datetime.now(UTC) - last < MEMORY_EVERY:
                continue
            self.enqueue(kind, subject.subject_id)

    async def _until_tomorrow(self) -> None:
        now = datetime.now(UTC)
        await asyncio.sleep((day_start(now) + timedelta(days=1) - now).total_seconds())

    async def work(self, *, until_idle: bool = False) -> None:
        """Comments the queue in order. Returns when the budget is spent (dropping what is
        left, the backfill finds it again) or, with `until_idle`, when the queue is empty."""
        while not (until_idle and self.queue.empty()):
            subject = await self.queue.get()
            self.pending.discard(subject)
            try:
                await self.comment(subject)
            except BudgetSpent:
                log.info("commentary: today's budget is spent, resuming tomorrow")
                self._drop_queue()
                return
            except Exception:
                log.exception("commentary: %s %d failed", subject.kind, subject.subject_id)

    def _drop_queue(self) -> None:
        while not self.queue.empty():
            self.queue.get_nowait()
        self.pending.clear()

    async def comment(self, subject: Subject) -> bool:
        """Writes and stores the commentary of one subject; False when there is nothing to
        do (already commented, not eligible, the model gave nothing usable)."""
        if subject.kind == records.LICHESS_GAME:
            return await self._lichess_game(subject)
        if subject.kind == records.MATCH:
            return await self._match(subject)
        if subject.kind in {records.HYPOTHESIS, records.LESSON}:
            return await self._translations(subject.subject_id)
        if subject.kind == records.TITLE:
            return await self._title(subject)
        if subject.kind == records.THOUGHT:
            return await self._thought(subject)
        if subject.kind in records.MEMORY:
            return await self._memory(subject)
        log.error("commentary: unknown kind %s", subject.kind)
        return False

    async def _write(
        self, system: str, prompt: str, schema: dict[str, Any], *, max_tokens: int | None = None
    ) -> Written | None:
        assert self.writer is not None
        since = day_start(datetime.now(UTC))
        spent = await records.spend_since(self.ledger, since)
        if not budget_allows(spent, self.settings.commentary_daily_usd):
            raise BudgetSpent
        if max_tokens is None:
            return await self.writer.write(system, prompt, schema)
        return await self.writer.write(system, prompt, schema, max_tokens=max_tokens)

    async def _store(self, subject: Subject, written: Written, text_it: str, text_en: str) -> bool:
        return await records.add(
            self.ledger,
            subject,
            text_it=text_it,
            text_en=text_en,
            model=written.model,
            input_tokens=written.input_tokens,
            output_tokens=written.output_tokens,
            cost_usd=written.cost_usd,
        )

    async def _lichess_game(self, subject: Subject) -> bool:
        row = await records.lichess_game(self.ledger, subject.subject_id)
        if row is None or not records.game_is_commented(row):
            return False
        if await records.exists(self.ledger, subject):
            return False
        evals = row.evals or await self._evaluate(row)
        if evals is None:
            return False
        facts = prompts.GameFacts(
            generation=row.generation_id,
            color=row.color,
            opponent=row.opponent,
            opponent_rating=row.opponent_rating,
            opponent_title=row.opponent_title,
            rated=row.rated,
            time_control=row.time_control,
            result=row.result or "",
            status=row.status,
            moves=row.moves.split(),
            evals=evals,
        )
        return await self._it_en(subject, prompts.game_prompt(facts))

    async def _evaluate(self, row: m.LichessGame) -> list[int] | None:
        """Evaluations for a game finished before they were recorded (backfill)."""
        try:
            evals = await self.evaluate(self.settings, row.moves.split(), row.color)
        except Exception:
            log.exception("commentary: cannot evaluate Lichess game %s", row.lichess_id)
            return None
        await lichess.set_evals(self.ledger, row.id, evals)
        return evals

    async def _match(self, subject: Subject) -> bool:
        found = await records.match_inputs(self.ledger, subject.subject_id)
        if found is None or await records.exists(self.ledger, subject):
            return False
        match, games, experiment = found
        accepted = None
        if experiment is not None and experiment.status in {"accepted", "rejected"}:
            accepted = experiment.status == "accepted"
        facts = prompts.MatchFacts(
            hypothesis=experiment.hypothesis if experiment else None,
            opponent=match.engine_b,
            time_control=match.time_control,
            wins=match.wins,
            draws=match.draws,
            losses=match.losses,
            pentanomial=match.pentanomial,
            elo=match.elo_diff,
            elo_error=match.elo_error,
            sprt_verdict=match.verdict,
            accepted=accepted,
            games=[
                prompts.MatchGame(
                    g.white, g.black, g.result, g.termination, prompts.plies_of(g.pgn)
                )
                for g in games
            ],
        )
        return await self._it_en(subject, prompts.match_prompt(facts))

    async def _title(self, subject: Subject) -> bool:
        row = await records.experiment(self.ledger, subject.subject_id)
        if row is None or not row.hypothesis or await records.exists(self.ledger, subject):
            return False
        return await self._it_en(
            subject, prompts.title_prompt(row.hypothesis), system=prompts.TITLE_SYSTEM
        )

    async def _thought(self, subject: Subject) -> bool:
        """The agent's thought on the live page, in Italian."""
        row = await records.event(self.ledger, subject.subject_id)
        if row is None or row.kind != "thought" or await records.exists(self.ledger, subject):
            return False
        text = str(row.payload.get("text") or "").strip()
        if not text:
            return False
        written = await self._write(
            prompts.TRANSLATION_SYSTEM,
            prompts.translation_prompt({"thought": text}),
            prompts.translation_schema(["thought"]),
        )
        if written is None:
            return False
        return await self._store(subject, written, written.fields["thought"], text)

    async def _memory(self, subject: Subject) -> bool:
        """A memory file or the instructions in Italian, if the text has not changed since."""
        text = (await asyncio.to_thread(self.memory_texts))[subject.kind]
        if records.content_id(text) != subject.subject_id:
            return False  # a newer version: the next check queues it
        if await records.exists(self.ledger, subject):
            return False
        written = await self._write(
            prompts.MEMORY_TRANSLATION_SYSTEM,
            prompts.memory_prompt(text),
            prompts.translation_schema(["text"]),
            max_tokens=MEMORY_MAX_TOKENS,
        )
        if written is None:
            return False
        return await self._store(subject, written, written.fields["text"], text)

    async def _it_en(self, subject: Subject, prompt: str, *, system: str = prompts.SYSTEM) -> bool:
        written = await self._write(system, prompt, prompts.IT_EN_SCHEMA)
        if written is None:
            return False
        return await self._store(subject, written, written.fields["it"], written.fields["en"])

    async def _translations(self, experiment_id: int) -> bool:
        """The agent's hypothesis and lesson in Italian: one call for whichever lack it."""
        row = await records.experiment(self.ledger, experiment_id)
        if row is None:
            return False
        texts: dict[str, str] = {}
        for kind, text in ((records.HYPOTHESIS, row.hypothesis), (records.LESSON, row.lesson)):
            if text and not await records.exists(self.ledger, Subject(kind, experiment_id)):
                texts[kind] = text
        if not texts:
            return False
        schema = prompts.translation_schema(list(texts))
        written = await self._write(
            prompts.TRANSLATION_SYSTEM, prompts.translation_prompt(texts), schema
        )
        if written is None:
            return False
        parts = len(texts)
        inputs = split(written.input_tokens, parts)
        outputs = split(written.output_tokens, parts)
        stored = False
        for i, (kind, original) in enumerate(texts.items()):
            share = Written(
                written.fields, written.model, inputs[i], outputs[i], written.cost_usd / parts
            )
            subject = Subject(kind, experiment_id)
            stored |= await self._store(subject, share, written.fields[kind], original)
        return stored
