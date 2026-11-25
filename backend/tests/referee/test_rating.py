import pytest

from darwin.referee.rating import AnchorResult, combine


def test_informative_anchors_are_combined_by_precision() -> None:
    rating = combine(
        [
            AnchorResult(1320, 0.95, 500, 200),
            AnchorResult(1600, 0.6, 70, 50),
            AnchorResult(2000, 0.2, -240, 100),
        ]
    )
    assert rating.elo is not None and rating.error is not None
    # 1670 +- 50 weighs four times 1760 +- 100; the whitewash at 1320 says nothing
    assert rating.elo == pytest.approx((4 * 1670 + 1760) / 5)
    assert rating.error < 50


def test_a_champion_crushed_by_the_weakest_anchor_is_below_scale() -> None:
    rating = combine([AnchorResult(1320, 0.02, -600, 300)])
    assert rating.elo is None and rating.below_scale


def test_rating_detail_lists_every_anchor_played() -> None:
    detail = combine([AnchorResult(1320, 0.5, 0, 80)]).detail()
    assert detail["anchors"] == [{"elo": 1320, "score": 0.5, "elo_diff": 0, "error": 80}]
