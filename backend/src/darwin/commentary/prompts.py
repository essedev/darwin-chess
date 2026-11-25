"""The commentary prompts, built from facts only (pure functions, no I/O).

Everything the model may say is in the prompt: moves, Stockfish's evaluations, match
numbers. It is asked to stay on them, so a visitor never reads an invented tactic.
"""

import io
import statistics
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import chess
import chess.pgn

MATE_CP = 10000  # how the referee's analysis encodes a forced mate
DECIDED_CP = 600  # past six pawns the game is decided: larger swings say nothing more
EARLY_PLIES = 40
KEY_MOMENTS = 3

SYSTEM = (
    "You write short commentary for the public website of darwin-chess, an experiment in "
    "which an AI agent writes a chess engine from scratch and keeps improving it on its own, "
    "while a trusted referee keeps only the versions that win real games. The readers are "
    "curious visitors, mostly neither chess players nor programmers.\n"
    "Rules:\n"
    "- Use only the facts in the message. Never invent moves, tactics, threats, plans, "
    "openings, players or numbers that are not there.\n"
    "- Plain prose: no headings, no lists, no Markdown, no emoji, no quotation of these "
    "instructions.\n"
    "- Write the same commentary twice, in Italian (field it) and in English (field en). "
    "Each must read naturally in its own language, not as a word-for-word translation.\n"
    "- Refer to our engine as the engine or the agent's engine, and to chess moves with their "
    "move number, as written in the facts.\n"
    "- Italian terms: the referee is l'arbitro, the champion il campione, the candidate il "
    "candidato, a draw una patta, checkmate scacco matto, stalemate stallo. Never use the "
    "English words in the Italian text."
)

IT_EN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"it": {"type": "string"}, "en": {"type": "string"}},
    "required": ["it", "en"],
    "additionalProperties": False,
}

TRANSLATION_SYSTEM = (
    "You translate into Italian the notes an AI agent writes in English while it develops a "
    "chess engine. Translate faithfully: same meaning, same numbers, nothing added or left "
    "out, no comments of yours. Keep technical terms and names as they are (for example "
    "alpha-beta, perft, NNUE, UCI, SPRT, bitboard, Elo, code identifiers). Plain text, no "
    "Markdown."
)

TITLE_SYSTEM = (
    "You write the headline of a change an AI agent made to the chess engine it develops, for "
    "the public website of the project. The readers are curious visitors, mostly neither chess "
    "players nor programmers.\n"
    "Rules:\n"
    "- At most 8 words; 3 to 5 is best. Sentence case, no final period, no quotes.\n"
    "- Name what changed in the engine's play or thinking, in plain words: for example "
    "'Search three moves deep', 'Bonus for the bishop pair', 'Stop hanging pieces'.\n"
    "- No jargon or code names (eval, movegen, perft, go mover, cp, negamax, startpos), no "
    "numbers unless they are the point, nothing that is not in the agent's text.\n"
    "- Write it in Italian (field it) and in English (field en); each must read naturally in "
    "its own language."
)

MEMORY_TRANSLATION_SYSTEM = (
    "You translate into Italian a Markdown file an AI agent keeps while it develops a chess "
    "engine (its strategy or its notes), or the instructions it receives. Translate the prose "
    "faithfully: same meaning, same numbers, nothing added or left out, no comments of yours. "
    "Keep the Markdown exactly as it is (headings, lists, emphasis, links, line breaks) and "
    "leave untouched code, commands, file names, identifiers and technical terms (for example "
    "alpha-beta, perft, NNUE, UCI, SPRT, bitboard, Elo)."
)

STATUS = {
    "mate": "checkmate",
    "resign": "resignation",
    "outoftime": "time running out",
    "timeout": "a player leaving the game",
    "stalemate": "stalemate",
    "draw": "a draw by agreement or by rule",
}
OUTCOME = {"win": "our engine won", "loss": "our engine lost", "draw": "the game was drawn"}


@dataclass(frozen=True)
class GameFacts:
    generation: int
    color: str  # ours
    opponent: str
    opponent_rating: int | None
    opponent_title: str | None
    rated: bool
    time_control: str  # seconds+increment
    result: str  # win, loss, draw
    status: str  # Lichess status
    moves: list[str]  # UCI, from the standard start
    evals: list[int]  # centipawns from our side, one per position (len(moves) + 1)


def pawns(cp: int) -> str:
    if cp >= MATE_CP:
        return "M+"
    if cp <= -MATE_CP:
        return "M-"
    return f"{cp / 100:+.1f}"


def san_moves(moves: Sequence[str]) -> list[str]:
    """The moves in SAN, played from the standard start; UCI from the first one that is not
    legal there (a game the bot did not start from the standard position)."""
    board = chess.Board()
    out: list[str] = []
    for i, uci_move in enumerate(moves):
        try:
            move = chess.Move.from_uci(uci_move)
            if move not in board.legal_moves:
                raise ValueError(uci_move)
        except ValueError:
            return out + list(moves[i:])
        out.append(board.san(move))
        board.push(move)
    return out


def _clamp(cp: int) -> int:
    return max(-DECIDED_CP, min(DECIDED_CP, cp))


def key_moments(
    sans: Sequence[str], evals: Sequence[int], our_color: str, limit: int = KEY_MOMENTS
) -> list[str]:
    """The moves that swung the evaluation the most (on values clamped to +-DECIDED_CP),
    in game order, each as a line of facts."""
    swings: list[tuple[int, int]] = []
    for ply in range(min(len(sans), len(evals) - 1)):
        delta = _clamp(evals[ply + 1]) - _clamp(evals[ply])
        if abs(delta) >= 100:  # a pawn or more
            swings.append((abs(delta), ply))
    top = sorted(swings, key=lambda item: (-item[0], item[1]))[:limit]
    lines = []
    ours_first = our_color == "white"
    for _, ply in sorted(top, key=lambda item: item[1]):
        white_moved = ply % 2 == 0
        mover = "our engine" if white_moved == ours_first else "the opponent"
        side = "white" if white_moved else "black"
        lines.append(
            f"move {ply // 2 + 1}, {side} ({mover}) played {sans[ply]}: the evaluation went "
            f"from {pawns(evals[ply])} to {pawns(evals[ply + 1])}"
        )
    return lines


def annotated_moves(sans: Sequence[str], evals: Sequence[int]) -> str:
    parts = []
    for ply, san in enumerate(sans):
        number = f"{ply // 2 + 1}. " if ply % 2 == 0 else ""
        note = f" ({pawns(evals[ply + 1])})" if ply + 1 < len(evals) else ""
        parts.append(f"{number}{san}{note}")
    return " ".join(parts)


def game_prompt(facts: GameFacts) -> str:
    sans = san_moves(facts.moves)
    opponent = " ".join(p for p in (facts.opponent_title, facts.opponent) if p)
    if facts.opponent_rating:
        opponent += f", rated {facts.opponent_rating}"
    ending = STATUS.get(facts.status, facts.status)
    moments = key_moments(sans, facts.evals, facts.color)
    lines = [
        "A game our engine played on Lichess against another chess bot.",
        f"Our engine: generation {facts.generation}, playing {facts.color}.",
        f"Opponent: {opponent}.",
        f"Time control: {facts.time_control} (seconds on the clock, plus seconds added per "
        f"move), {'rated' if facts.rated else 'casual'}.",
        f"Result: {OUTCOME.get(facts.result, facts.result)}, by {ending}, after "
        f"{(len(facts.moves) + 1) // 2} moves.",
        "",
        "Moves, each followed by Stockfish's evaluation of the position after it, in pawns "
        "from our engine's side (positive is good for us; M+ is a forced mate for us, M- "
        "against us):",
        annotated_moves(sans, facts.evals),
        "",
        "Largest swings in the evaluation:",
        *(f"- {line}" for line in moments),
    ]
    if not moments:
        lines.append("- none: the evaluation never moved by a pawn or more in one move.")
    lines += [
        "",
        "Write 2 or 3 sentences for a visitor who does not play chess: how the game went and "
        "its key moment, named by move number (for example: at move 14). Base every claim on "
        "the moves and evaluations above. Do not describe tactics, threats or plans they do "
        "not show; if the evaluation stayed level for long, say the game was balanced.",
    ]
    return "\n".join(lines)


@dataclass(frozen=True)
class MatchGame:
    white: str
    black: str
    result: str  # 1-0, 0-1, 1/2-1/2
    termination: str
    plies: int


@dataclass(frozen=True)
class MatchFacts:
    hypothesis: str | None
    opponent: str  # random, champion, or an engine name
    time_control: str
    wins: int
    draws: int
    losses: int
    pentanomial: list[int] | None
    elo: float | None
    elo_error: float | None
    sprt_verdict: str | None  # h1, h0, continue
    accepted: bool | None  # the experiment's outcome, when known
    games: list[MatchGame]


def plies_of(pgn: str) -> int:
    game = chess.pgn.read_game(io.StringIO(pgn))
    return 0 if game is None else sum(1 for _ in game.mainline_moves())


OPPONENTS = {
    "champion": "the current champion, the best version of the engine so far",
    "random": "a player that picks random legal moves",
}
SPRT = {
    "h1": "the statistical test (SPRT) concluded the new version is stronger",
    "h0": "the statistical test (SPRT) concluded the new version is not stronger",
    "continue": "the games ran out before the statistical test could conclude",
}


def game_stats(games: Sequence[MatchGame], candidate: str = "candidate") -> list[str]:
    """Aggregate facts: how games ended (and for whom), length, early decisions."""
    if not games:
        return ["no game records are available."]
    endings: Counter[str] = Counter()
    won: Counter[str] = Counter()
    lost: Counter[str] = Counter()
    for game in games:
        endings[game.termination] += 1
        if game.result in {"1-0", "0-1"}:
            candidate_won = (game.result == "1-0") == (game.white == candidate)
            (won if candidate_won else lost)[game.termination] += 1
    parts = []
    for termination, count in endings.most_common():
        detail = []
        if won[termination]:
            detail.append(f"new version won {won[termination]}")
        if lost[termination]:
            detail.append(f"new version lost {lost[termination]}")
        draws = count - won[termination] - lost[termination]
        if draws:
            detail.append(f"{draws} drawn")
        parts.append(f"{termination.replace('_', ' ')} {count} ({', '.join(detail)})")
    lengths = [game.plies for game in games]
    early = sum(1 for game in games if game.result in {"1-0", "0-1"} and game.plies <= EARLY_PLIES)
    median = statistics.median(lengths)
    return [
        "how the games ended: " + "; ".join(parts) + ".",
        f"median length: {median:g} plies (about {median / 2:g} moves).",
        f"decided with a win within the first {EARLY_PLIES} plies ({EARLY_PLIES // 2} moves): "
        f"{early} of {len(games)} games ({100 * early / len(games):.0f}%).",
    ]


def match_prompt(facts: MatchFacts) -> str:
    played = facts.wins + facts.draws + facts.losses
    opponent = OPPONENTS.get(facts.opponent, f"the engine {facts.opponent}")
    lines = [
        "A match the referee played to judge a change the agent made to its chess engine.",
        f"The agent's hypothesis, in its own words: {facts.hypothesis or '(not recorded)'}",
        f"Opponent: {opponent}.",
        f"Time control per game: {facts.time_control} (seconds, plus seconds per move).",
        f"Result for the new version: {facts.wins} wins, {facts.draws} draws, "
        f"{facts.losses} losses in {played} games, played in pairs with the same opening and "
        "colours swapped.",
    ]
    if facts.pentanomial:
        counts = ", ".join(str(n) for n in facts.pentanomial)
        lines.append(f"Pairs scoring 0, 0.5, 1, 1.5 and 2 points out of 2: {counts}.")
    if facts.elo is not None:
        error = f" +- {facts.elo_error:.0f}" if facts.elo_error is not None else ""
        lines.append(f"Elo difference against the opponent: {facts.elo:+.0f}{error}.")
    verdict = SPRT.get(facts.sprt_verdict or "", "no statistical verdict")
    if facts.accepted is not None:
        outcome = (
            "accepted: the new version becomes the champion"
            if facts.accepted
            else "rejected: the champion stays"
        )
        verdict = f"{verdict}; {outcome}"
    lines += [
        f"Verdict: {verdict}.",
        "",
        "Facts from the games:",
        *(f"- {line}" for line in game_stats(facts.games)),
        "",
        "Write 2 or 3 sentences for a visitor: did the change work, and how does it show in "
        "the games? Use only these facts; do not guess what the change did beyond the "
        "hypothesis.",
    ]
    return "\n".join(lines)


def title_prompt(hypothesis: str) -> str:
    return f"The agent's description of its change:\n\n{hypothesis}"


def memory_prompt(text: str) -> str:
    return f"Translate this text into Italian (field text):\n\n{text}"


def translation_schema(fields: Sequence[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {name: {"type": "string"} for name in fields},
        "required": list(fields),
        "additionalProperties": False,
    }


def translation_prompt(texts: dict[str, str]) -> str:
    """One call for the hypothesis, the lesson or both: each field gets its translation."""
    lines = ["Translate each field into Italian, keeping the field names."]
    for name, text in texts.items():
        lines += ["", f"{name}:", text]
    return "\n".join(lines)
