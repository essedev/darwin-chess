import pytest

from darwin.referee.rating import AnchorResult, climb, combine, first_rungs


def test_informative_anchors_are_combined_by_precision() -> None:
    rating = combine(
        [
            AnchorResult(1320, 0.95, 500, 200, 40),
            AnchorResult(1600, 0.6, 70, 50, 40),
            AnchorResult(2000, 0.2, -240, 100, 40),
        ]
    )
    assert rating.elo is not None and rating.error is not None
    # 1670 +- 50 weighs four times 1760 +- 100; the whitewash at 1320 says nothing
    assert rating.elo == pytest.approx((4 * 1670 + 1760) / 5)
    assert rating.error < 50


def test_a_champion_crushed_by_the_weakest_anchor_is_below_scale() -> None:
    rating = combine([AnchorResult(1320, 0.02, -600, 300, 40)])
    assert rating.elo is None and rating.below_scale


def test_rating_detail_lists_every_anchor_played_with_its_games() -> None:
    detail = combine([AnchorResult(1320, 0.5, 0, 80, 40)]).detail()
    assert detail["anchors"] == [
        {"elo": 1320, "score": 0.5, "elo_diff": 0, "error": 80, "games": 40}
    ]


@pytest.mark.parametrize(
    ("expected", "rungs"),
    [(None, [1320]), (1200, [1320]), (1320, [1320, 1600]), (2090, [2000, 2400]), (3000, [2800])],
)
def test_the_ladder_starts_around_the_expected_elo(
    expected: float | None, rungs: list[int]
) -> None:
    assert first_rungs(expected) == rungs


async def ladder(expected: float | None, scores: dict[int, float]) -> list[tuple[int, float]]:
    """The rungs the ladder plays, lowest first, against a champion scoring `scores`."""

    async def play(anchor: int) -> AnchorResult:
        return AnchorResult(anchor, scores[anchor], 0.0, 100.0, 40)

    return [(r.anchor_elo, r.score) for r in await climb(expected, play)]


async def test_without_an_expectation_the_ladder_climbs_from_the_bottom_as_before() -> None:
    gen15 = {1320: 1.0, 1600: 0.863, 2000: 0.4}
    assert await ladder(None, gen15) == [(1320, 1.0), (1600, 0.863)]
    gen14 = {1320: 0.912, 1600: 0.95, 2000: 0.65}
    assert await ladder(None, gen14) == [(1320, 0.912), (1600, 0.95), (2000, 0.65)]


async def test_gen15_expected_at_2105_plays_both_rungs_around_it() -> None:
    # gen-14's joint Elo at the time (2020) plus the +84 that promoted gen-15: no more 1600
    assert await ladder(2105, {1600: 0.863, 2000: 0.55, 2400: 0.2}) == [
        (2000, 0.55),
        (2400, 0.2),
    ]


async def test_a_whitewash_at_the_top_climbs_and_a_rout_at_the_bottom_steps_down() -> None:
    stronger = {2000: 0.95, 2400: 0.92, 2800: 0.6}
    assert await ladder(2100, stronger) == [(2000, 0.95), (2400, 0.92), (2800, 0.6)]
    weaker = {1320: 0.3, 1600: 0.05, 2000: 0.0}
    assert await ladder(1700, weaker) == [(1320, 0.3), (1600, 0.05), (2000, 0.0)]
    beyond = {2400: 1.0, 2800: 0.95}  # the top of the ladder: nowhere left to climb
    assert await ladder(2900, beyond) == [(2800, 0.95)]
