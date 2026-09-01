"""Pairwise ranking.

Absolute scores from a VLM across many dimensions are correlated, uncalibrated
and drift between prompt versions - and the axis that matters here (does this
read as intentional or as random?) is the one with the least signal in any
public preference data. So: no thresholds on absolute numbers. Two takes, one
choice, Elo.

You are the reward model at MVP. This module exists to make that fast.
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass

K_FACTOR = 24.0
INITIAL_RATING = 1000.0

# What each comparison asks. Kept short because the judge answers hundreds of
# these and a long question invites rationalising rather than reacting.
CRITERIA: dict[str, str] = {
    "overall": "Which would you put in a real video?",
    "photographic": "Which looks more like it was photographed?",
    "restraint": "Which is less obviously trying to impress you?",
    "deadpan": "In which does the world care less about the strange thing?",
}


@dataclass(frozen=True, slots=True)
class Rated:
    take_id: str
    rating: float
    wins: int
    losses: int
    draws: int

    @property
    def played(self) -> int:
        return self.wins + self.losses + self.draws


def all_pairs(take_ids: list[str], *, seed: int | None = 7) -> list[tuple[str, str]]:
    """Every unordered pair, shuffled.

    Shuffling matters: judging all of one model's takes in a row lets an
    impression of that model carry across comparisons.
    """
    pairs = list(itertools.combinations(take_ids, 2))
    if seed is not None:
        rng = random.Random(seed)
        rng.shuffle(pairs)
        # Also randomise which side each take appears on, so position bias
        # does not attach to a particular take.
        pairs = [p if rng.random() < 0.5 else (p[1], p[0]) for p in pairs]
    return pairs


def _expected(a: float, b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((b - a) / 400.0))


def elo(
    comparisons: list[tuple[str, str, str | None]],
    *,
    take_ids: list[str] | None = None,
    k: float = K_FACTOR,
) -> list[Rated]:
    """Rate takes from (left, right, winner) triples. `winner` None is a draw.

    Returns ratings sorted best first. With a full round robin the ordering is
    stable; with a partial one, treat it as indicative.
    """
    seen = set(take_ids or [])
    for left, right, _ in comparisons:
        seen.update((left, right))

    ratings = {t: INITIAL_RATING for t in seen}
    tally = {t: [0, 0, 0] for t in seen}  # wins, losses, draws

    for left, right, winner in comparisons:
        if left not in ratings or right not in ratings:
            continue
        exp_left = _expected(ratings[left], ratings[right])
        if winner is None:
            score_left = 0.5
            tally[left][2] += 1
            tally[right][2] += 1
        elif winner == left:
            score_left = 1.0
            tally[left][0] += 1
            tally[right][1] += 1
        elif winner == right:
            score_left = 0.0
            tally[left][1] += 1
            tally[right][0] += 1
        else:
            continue
        delta = k * (score_left - exp_left)
        ratings[left] += delta
        ratings[right] -= delta

    return sorted(
        (
            Rated(t, round(ratings[t], 1), tally[t][0], tally[t][1], tally[t][2])
            for t in ratings
        ),
        key=lambda r: r.rating,
        reverse=True,
    )


def group_ratings(rated: list[Rated], by: str) -> dict[str, float]:
    """Average rating grouped by a component of the take id.

    Take ids are `<experiment>.<model>.<staging>`, so this answers the two
    questions the Deadpan Test exists to settle: which model, which staging.
    """
    index = {"model": 1, "staging": 2}[by]
    buckets: dict[str, list[float]] = {}
    for r in rated:
        parts = r.take_id.split(".")
        if len(parts) <= index:
            continue
        buckets.setdefault(parts[index], []).append(r.rating)
    return {
        key: round(sum(values) / len(values), 1)
        for key, values in sorted(
            buckets.items(), key=lambda kv: -sum(kv[1]) / len(kv[1])
        )
    }
