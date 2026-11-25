import chess

from darwin.referee.analysis import worst_drop

# 1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6?? 4. Qxf7#: black's real mistake is 3...Nf6.
MOVES = ["e2e4", "e7e5", "d1h5", "b8c6", "f1c4", "g8f6", "h5f7"]


def test_the_first_real_mistake_beats_the_slide_into_mate() -> None:
    # Black's view, one value per position: fine, fine, ..., lost after Nf6, mated at the end.
    evals = [0, 0, 0, -20, -20, -40, -10000, -10000]
    worst = worst_drop(MOVES, evals, chess.BLACK)
    assert (worst["move_number"], worst["move"]) == (3, "Nf6")


def test_a_lost_position_getting_worse_is_not_the_mistake() -> None:
    evals = [0, 0, -900, -900, -900, -1500, -10000, -10000]  # already decided after move 2
    worst = worst_drop(MOVES, evals, chess.BLACK)
    assert worst["move_number"] == 1  # the drop to -900 came from black's first move
