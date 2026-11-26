"""Joint maximum-likelihood Elo of the generations, from every series of games that ties them.

A series is a generation against a Stockfish anchor, fixed at its nominal Elo, or against
another generation. The model is the logistic Elo curve with a draw as half a point, every game
independent; the 95% margins come from the observed information, the inverse of the negative
Hessian at the maximum.

A finite maximum exists only for the generations in the same strongly connected component as
the anchors, in the graph where an edge goes from whoever took points to whoever gave them:
generations that, directly or through others, have both scored against the anchors and
conceded to them. The others get no estimate. One with no path to an anchor has nothing to be
measured by; one that only ever won (or only ever lost) would sit at infinity, and its games
tell nothing about the rest.

Pure Python: the Hessian is a weighted graph Laplacian whose band, with generations in order,
is as wide as the longest match between them (1 when each plays only its parent), so a banded
Cholesky keeps the fit linear in the number of generations.
"""

import math
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

K = math.log(10) / 400  # slope of the logistic curve per Elo point
Z95 = 1.959963984540054
MAX_STEP = 400.0  # Elo: a Newton step from far away is cut to this before the line search
TOLERANCE = 1e-7  # Elo
MAX_ITERATIONS = 200


class FitError(RuntimeError):
    """The Newton iteration did not converge: never expected on a concave likelihood."""


@dataclass(frozen=True)
class Anchor:
    """An opponent of known strength: a Stockfish rung at its nominal Elo."""

    elo: float


@dataclass(frozen=True)
class Series:
    """Games of `player` against `opponent`, scored from the player's side."""

    player: int
    opponent: int | Anchor
    games: int
    points: float  # a win counts 1, a draw 0.5


@dataclass(frozen=True)
class Estimate:
    elo: float
    error: float  # 95% half-width


def fit(series: Sequence[Series]) -> dict[int, Estimate]:
    """The joint estimate of every generation the anchors can measure."""
    usable = [s for s in series if s.games > 0 and s.player != s.opponent]
    measured = _anchored(usable)
    if not measured:
        return {}
    kept = [
        s
        for s in usable
        if s.player in measured and (isinstance(s.opponent, Anchor) or s.opponent in measured)
    ]
    order = sorted(measured)
    index = {player: i for i, player in enumerate(order)}
    anchors = [s.opponent.elo for s in kept if isinstance(s.opponent, Anchor)]
    x = [sum(anchors) / len(anchors)] * len(order)
    likelihood = _log_likelihood(x, kept, index)
    for _ in range(MAX_ITERATIONS):
        gradient, information = _derivatives(x, kept, index)
        step = _solve(_cholesky(information, _band(kept, index)), gradient)
        largest = max(abs(v) for v in step)
        if largest < TOLERANCE:
            break
        scale = min(1.0, MAX_STEP / largest)
        slope = sum(g * d for g, d in zip(gradient, step, strict=True)) * scale
        while True:  # backtracking: the likelihood is concave, a short enough step improves it
            trial = [v + scale * d for v, d in zip(x, step, strict=True)]
            value = _log_likelihood(trial, kept, index)
            if value >= likelihood + 1e-4 * slope or scale < 1e-12:
                break
            scale, slope = scale / 2, slope / 2
        x, likelihood = trial, value
    else:
        raise FitError(f"no convergence in {MAX_ITERATIONS} iterations")
    _, information = _derivatives(x, kept, index)
    variances = _inverse_diagonal(_cholesky(information, _band(kept, index)))
    return {player: Estimate(x[i], Z95 * math.sqrt(variances[i])) for player, i in index.items()}


def _anchored(series: Iterable[Series]) -> set[int]:
    """Generations in the strongly connected component of the anchors (all one node, None)."""
    took: dict[int | None, set[int | None]] = defaultdict(set)  # u -> v: u scored against v
    gave: dict[int | None, set[int | None]] = defaultdict(set)
    for s in series:
        a, b = s.player, None if isinstance(s.opponent, Anchor) else s.opponent
        if s.points > 0:
            took[a].add(b)
            gave[b].add(a)
        if s.points < s.games:
            took[b].add(a)
            gave[a].add(b)
    both = _reach(took) & _reach(gave)
    return {node for node in both if node is not None}


def _reach(edges: dict[int | None, set[int | None]]) -> set[int | None]:
    seen: set[int | None] = {None}
    stack: list[int | None] = [None]
    while stack:
        for nxt in edges[stack.pop()]:
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def _expected(diff: float) -> float:
    z = K * diff
    if z >= 0:
        return 1 / (1 + math.exp(-z))
    e = math.exp(z)
    return e / (1 + e)


def _softplus(t: float) -> float:
    return max(t, 0.0) + math.log1p(math.exp(-abs(t)))


def _diff(x: list[float], s: Series, index: dict[int, int]) -> float:
    opponent = s.opponent.elo if isinstance(s.opponent, Anchor) else x[index[s.opponent]]
    return x[index[s.player]] - opponent


def _log_likelihood(x: list[float], series: list[Series], index: dict[int, int]) -> float:
    total = 0.0
    for s in series:
        z = K * _diff(x, s, index)
        total -= s.points * _softplus(-z) + (s.games - s.points) * _softplus(z)
    return total


Matrix = list[dict[int, float]]  # row i holds the lower triangle, columns j <= i


def _derivatives(
    x: list[float], series: list[Series], index: dict[int, int]
) -> tuple[list[float], Matrix]:
    """Gradient of the log-likelihood and the information matrix (minus its Hessian)."""
    gradient = [0.0] * len(x)
    information: Matrix = [defaultdict(float) for _ in x]
    for s in series:
        q = _expected(_diff(x, s, index))
        g = K * (s.points - s.games * q)
        w = s.games * K * K * q * (1 - q)
        p = index[s.player]
        gradient[p] += g
        information[p][p] += w
        if not isinstance(s.opponent, Anchor):
            o = index[s.opponent]
            gradient[o] -= g
            information[o][o] += w
            information[max(p, o)][min(p, o)] -= w
    return gradient, information


def _band(series: list[Series], index: dict[int, int]) -> int:
    return max(
        (
            abs(index[s.player] - index[s.opponent])
            for s in series
            if not isinstance(s.opponent, Anchor)
        ),
        default=0,
    )


def _cholesky(a: Matrix, band: int) -> tuple[Matrix, int]:
    """Lower factor L of a banded symmetric positive definite matrix, A = L L^T."""
    low: Matrix = [{} for _ in a]
    for i in range(len(a)):
        for j in range(max(0, i - band), i + 1):
            total = a[i].get(j, 0.0) - sum(
                low[i][k] * low[j][k] for k in range(max(0, i - band), j)
            )
            if i == j:
                if total <= 0:
                    raise FitError("information matrix not positive definite")
                low[i][i] = math.sqrt(total)
            else:
                low[i][j] = total / low[j][j]
    return low, band


def _solve(factor: tuple[Matrix, int], rhs: list[float]) -> list[float]:
    low, band = factor
    n = len(rhs)
    y = [0.0] * n
    for i in range(n):
        y[i] = (rhs[i] - sum(low[i][k] * y[k] for k in range(max(0, i - band), i))) / low[i][i]
    out = [0.0] * n
    for i in reversed(range(n)):
        out[i] = (y[i] - sum(low[k][i] * out[k] for k in range(i + 1, min(n, i + band + 1)))) / low[
            i
        ][i]
    return out


def _inverse_diagonal(factor: tuple[Matrix, int]) -> list[float]:
    """diag(A^-1) = squared norms of the columns of L^-1, each solved from its own row on."""
    low, band = factor
    n = len(low)
    out = []
    for col in range(n):
        z = [0.0] * n
        z[col] = 1 / low[col][col]
        for i in range(col + 1, n):
            z[i] = -sum(low[i][k] * z[k] for k in range(max(col, i - band), i)) / low[i][i]
        out.append(sum(v * v for v in z))
    return out
