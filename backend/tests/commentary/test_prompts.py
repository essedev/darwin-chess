import chess
import chess.pgn

from darwin.commentary import prompts
from darwin.commentary.prompts import GameFacts, MatchFacts, MatchGame

# 1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. d3 Bc5 5. c3 d6 6. Nbd2 a6
MOVES = [
    "e2e4",
    "e7e5",
    "g1f3",
    "b8c6",
    "f1c4",
    "g8f6",
    "d2d3",
    "f8c5",
    "c2c3",
    "d7d6",
    "b1d2",
    "a7a6",
]


def facts(evals: list[int], **overrides: object) -> GameFacts:
    fields: dict[str, object] = {
        "generation": 3,
        "color": "white",
        "opponent": "maia1",
        "opponent_rating": 1500,
        "opponent_title": "BOT",
        "rated": True,
        "time_control": "180+2",
        "result": "loss",
        "status": "resign",
        "moves": MOVES,
        "evals": evals,
    }
    return GameFacts(**(fields | overrides))  # type: ignore[arg-type]


def test_san_moves_and_a_fallback_to_uci_when_not_legal() -> None:
    assert prompts.san_moves(MOVES[:4]) == ["e4", "e5", "Nf3", "Nc6"]
    assert prompts.san_moves(["e2e4", "e2e4", "g1f3"]) == ["e4", "e2e4", "g1f3"]


def test_key_moments_name_the_biggest_swings_in_game_order() -> None:
    sans = prompts.san_moves(MOVES)
    # Level, then black's 4...Bc5 swings +2.5 for us, then our 6.Nbd2 drops to -4.
    evals = [20, 20, 20, 20, 20, 20, 20, 20, 270, 270, 270, -400, -400]
    lines = prompts.key_moments(sans, evals, "white", limit=2)
    assert lines == [
        "move 4, black (the opponent) played Bc5: the evaluation went from +0.2 to +2.7",
        "move 6, white (our engine) played Nbd2: the evaluation went from +2.7 to -4.0",
    ]


def test_key_moments_clamp_a_decided_game_and_ignore_small_moves() -> None:
    sans = prompts.san_moves(MOVES[:4])
    # From -9 pawns to mate is no swing once clamped; tiny moves are not moments either.
    assert prompts.key_moments(sans, [0, 10, -900, -10000, -10000], "black") == [
        "move 1, black (our engine) played e5: the evaluation went from +0.1 to -9.0"
    ]
    assert prompts.key_moments(sans, [0, 10, 20, 30, 40], "white") == []


def test_the_game_prompt_carries_every_fact_and_marks_mates() -> None:
    evals = [20] * 12 + [-10000]
    text = prompts.game_prompt(facts(evals))
    assert "generation 3, playing white" in text
    assert "BOT maia1, rated 1500" in text
    assert "180+2" in text and "rated." in text
    assert "our engine lost, by resignation, after 6 moves" in text
    assert "1. e4 (+0.2) e5 (+0.2) 2. Nf3" in text
    assert "6. Nbd2 (+0.2) a6 (M-)" in text
    assert "move 6, black (the opponent) played a6" in text
    assert "2 or 3 sentences" in text


def test_a_level_game_says_there_was_no_swing() -> None:
    text = prompts.game_prompt(facts([15] * 13, result="draw", status="draw"))
    assert "the game was drawn, by a draw by agreement or by rule" in text
    assert "never moved by a pawn or more" in text


def pgn_of(moves: list[str]) -> str:
    game = chess.pgn.Game()
    node: chess.pgn.GameNode = game
    for move in moves:
        node = node.add_variation(chess.Move.from_uci(move))
    return str(game)


def test_plies_are_read_from_the_pgn() -> None:
    assert prompts.plies_of(pgn_of(MOVES)) == 12
    assert prompts.plies_of("") == 0


def test_game_stats_split_endings_by_who_won() -> None:
    games = [
        MatchGame("candidate", "champion", "1-0", "checkmate", 30),
        MatchGame("champion", "candidate", "1-0", "checkmate", 50),
        MatchGame("champion", "candidate", "0-1", "timeout", 90),
        MatchGame("candidate", "champion", "1/2-1/2", "repetition", 120),
    ]
    assert prompts.game_stats(games) == [
        "how the games ended: checkmate 2 (new version won 1, new version lost 1); "
        "timeout 1 (new version won 1); repetition 1 (1 drawn).",
        "median length: 70 plies (about 35 moves).",
        "decided with a win within the first 40 plies (20 moves): 1 of 4 games (25%).",
    ]
    assert prompts.game_stats([]) == ["no game records are available."]


def test_the_match_prompt_carries_the_numbers_and_the_verdict() -> None:
    text = prompts.match_prompt(
        MatchFacts(
            hypothesis="Add alpha-beta pruning to the search",
            opponent="champion",
            time_control="10+0.1",
            wins=30,
            draws=10,
            losses=20,
            pentanomial=[2, 5, 10, 8, 5],
            elo=58.4,
            elo_error=31.2,
            sprt_verdict="h1",
            accepted=True,
            games=[MatchGame("candidate", "champion", "1-0", "checkmate", 30)],
        )
    )
    assert "in its own words: Add alpha-beta pruning to the search" in text
    assert "the current champion" in text
    assert "30 wins, 10 draws, 20 losses in 60 games" in text
    assert "2 points out of 2: 2, 5, 10, 8, 5." in text
    assert "Elo difference against the opponent: +58 +- 31." in text
    assert "concluded the new version is stronger; accepted" in text
    assert "checkmate 1 (new version won 1)" in text


def test_translation_asks_for_exactly_the_fields_given() -> None:
    texts = {"hypothesis": "Use perft to check move generation", "lesson": "NNUE needs data."}
    schema = prompts.translation_schema(list(texts))
    assert schema["required"] == ["hypothesis", "lesson"]
    assert schema["additionalProperties"] is False
    prompt = prompts.translation_prompt(texts)
    assert "hypothesis:\nUse perft to check move generation" in prompt
    assert "lesson:\nNNUE needs data." in prompt


def test_no_prompt_has_an_em_dash() -> None:
    texts = [
        prompts.SYSTEM,
        prompts.TRANSLATION_SYSTEM,
        prompts.game_prompt(facts([0] * 13)),
        prompts.match_prompt(
            MatchFacts(None, "random", "1+0", 1, 0, 0, None, None, None, None, None, [])
        ),
    ]
    assert not any(chr(0x2014) in text for text in texts)
