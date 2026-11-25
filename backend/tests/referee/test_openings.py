import random

import chess

from darwin.referee.openings import _material, generate


def test_openings_are_distinct_balanced_and_reproducible() -> None:
    book = generate(random.Random(3), 50)
    assert book == generate(random.Random(3), 50)
    assert len(set(book)) == 50
    for epd in book:
        board = chess.Board()
        board.set_epd(epd)
        assert _material(board, chess.WHITE) == _material(board, chess.BLACK)
        assert not board.is_check()


class FoolsMateFirst(random.Random):
    """Plays fool's mate on the first line, then behaves like random.Random."""

    def __init__(self) -> None:
        super().__init__(0)
        self.script = ["f2f3", "e7e5", "g2g4", "d8h4"]

    def choice(self, seq):  # type: ignore[no-untyped-def]
        if self.script:
            wanted = self.script.pop(0)
            return next(move for move in seq if move.uci() == wanted)
        return super().choice(seq)


def test_a_random_line_that_ends_in_mate_is_discarded_not_a_crash() -> None:
    book = generate(FoolsMateFirst(), 3, plies=8)
    assert len(book) == 3
