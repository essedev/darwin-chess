import math

import pytest

from darwin.ledger.elo_fit import Z95, Anchor, K, Series, fit


def test_two_anchors_and_one_engine() -> None:
    # 26/40 against 1600 and 14/40 against 2000: at 1800 the expected scores are q and 1 - q,
    # so 40 points are expected in all, exactly the 40 scored.
    estimates = fit([Series(1, Anchor(1600), 40, 26), Series(1, Anchor(2000), 40, 14)])
    q = 1 / (1 + 10 ** (-200 / 400))
    assert estimates[1].elo == pytest.approx(1800, abs=1e-6)
    information = 2 * 40 * K**2 * q * (1 - q)
    assert estimates[1].error == pytest.approx(Z95 / math.sqrt(information))


def test_a_chain_carries_the_anchor_to_a_generation_that_never_met_it() -> None:
    # gen-2 scores half against 1600; gen-1 beats gen-2 30/40, +400*log10(3) Elo.
    estimates = fit([Series(2, Anchor(1600), 40, 20), Series(1, 2, 40, 30)])
    assert estimates[2].elo == pytest.approx(1600, abs=1e-6)
    assert estimates[1].elo == pytest.approx(1600 + 400 * math.log10(3), abs=1e-6)
    variance = 1 / (40 * K**2 * 0.25) + 1 / (40 * K**2 * 0.75 * 0.25)
    assert estimates[1].error == pytest.approx(Z95 * math.sqrt(variance))


def test_gen15_lands_above_gen14_once_their_match_counts() -> None:
    # Production: the ladder rated gen-14 from its 2000 rung and gen-15 from its 1600 rung,
    # with gen-15 104/168 against gen-14 in the SPRT that promoted it (+84 +- 34).
    gen14 = [(1320, 36.5), (1600, 38), (2000, 26)]  # alone: 2108 +- 130, from the 2000 rung
    gen15 = [(1320, 40), (1600, 34.5)]  # alone: 1919 +- 166, from the 1600 rung

    series = [Series(14, Anchor(a), 40, p) for a, p in gen14]
    series += [Series(15, Anchor(a), 40, p) for a, p in gen15]
    series.append(Series(15, 14, 168, 71 + 66 / 2))
    estimates = fit(series)
    assert estimates[15].elo > estimates[14].elo
    assert estimates[14].elo < 2108 and estimates[15].elo > 1919
    # Both borrow from each other's games: each margin is narrower than its own ladder's.
    assert estimates[14].error < 130 and estimates[15].error < 166


def test_generations_out_of_reach_of_the_anchors_get_no_estimate() -> None:
    estimates = fit(
        [
            Series(1, Anchor(1600), 40, 20),
            Series(2, 1, 40, 40),  # gen-2 only ever won: it would sit at infinity
            Series(3, Anchor(1320), 40, 40),  # a whitewash of the weakest rung, nothing else
            Series(5, 4, 40, 25),  # a pair of generations no anchor ever met
        ]
    )
    assert set(estimates) == {1}
    assert estimates[1].elo == pytest.approx(1600, abs=1e-6)  # gen-2's games add nothing


def test_the_estimate_does_not_depend_on_how_generations_are_numbered() -> None:
    # The same chain in two numberings: band 1 (neighbours) and band 2 (1 plays 3).
    def chain(a: int, b: int, c: int) -> list[Series]:
        return [
            Series(a, Anchor(1320), 40, 30),
            Series(b, a, 100, 62),
            Series(c, b, 100, 58.5),
            Series(c, Anchor(2000), 40, 9),
        ]

    plain, shuffled = fit(chain(1, 2, 3)), fit(chain(1, 3, 2))
    for p, s in ((1, 1), (2, 3), (3, 2)):
        assert shuffled[s].elo == pytest.approx(plain[p].elo, abs=1e-6)
        assert shuffled[s].error == pytest.approx(plain[p].error, rel=1e-9)
