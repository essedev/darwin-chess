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
