"""The sequence: twelve shots, one world, one escalation.

Where `experiment.py` renders the same moment twelve ways - clean science, no
artifact - this renders twelve moments of one story that cut together into
roughly forty seconds you can send to someone.

The trade is deliberate. The staging signal gets noisier (three shots per
strategy instead of a clean grid) and in exchange you learn the thing the grid
cannot tell you at all: whether twelve separately generated shots hold together
as one place. And you end the week with a thing rather than a finding.

Escalation, five stages across the cut:

    0  the world behaving normally
    1  one thing slightly wrong, easy to miss
    2  it is unmistakable, and nobody reacts
    3  it is everywhere
    4  the rule has fully taken the street
"""

from __future__ import annotations

from .banned import check_concept, check_prompt
from .experiment import GRAVITY_RULE
from .schemas import ShotSpec, ShotType
from .staging import BY_KEY

SEQUENCE_NAME = "gravity-street-01"

# One location, described once. Every shot inherits it, which is the cheapest
# possible consistency mechanism and the reason the cut might hold together.
WORLD = (
    "A residential street in a post-war concrete housing district on an overcast "
    "weekday morning, wet pavement, faded shopfront signage, parked hatchbacks, "
    "a bus shelter with a cracked panel, bare plane trees, sodium streetlights "
    "still on"
)

# Invariants from the rule, phrased for the frame. At least one is visible in
# every shot - that is what makes the strangeness read as designed.
LITTER = "Litter and wet leaves lie flat on the pavement, the light dull and even"
PEOPLE = "People walk at an ordinary pace, unhurried and uninterested"
WEATHER = "The overcast light is flat and unchanged, shadows soft and consistent"


def _shot(
    n: int,
    stage: int,
    staging_key: str,
    duration: float,
    anomaly: str | None,
    invariant: str,
    lens: int = 35,
) -> ShotSpec:
    return ShotSpec(
        shot_id=f"{SEQUENCE_NAME}.{n:02d}",
        shot_type=ShotType.GENERATED,
        duration_s=duration,
        environment=WORLD,
        anomaly=anomaly,
        rule_id=GRAVITY_RULE.id,
        invariant_shown=invariant,
        staging=BY_KEY[staging_key],
        lens_mm=lens,
        handles_s=0.5,
        order=n,
        stage=stage,
    )


# Durations vary so the cut has rhythm rather than twelve equal blocks. Staging
# is spread roughly three per strategy so the comparison still carries signal.
SHOTS: list[ShotSpec] = [
    # --- stage 0: nothing is wrong -------------------------------------
    _shot(1, 0, "backs_suppressed", 4.0, None, LITTER, lens=28),
    _shot(2, 0, "faces_suppressed", 3.5, None, PEOPLE, lens=50),
    _shot(
        3, 0, "backs_suppressed", 3.5,
        "a municipal bus pulling away from the stop, entirely normal",
        WEATHER,
    ),
    # --- stage 1: one thing, easy to miss ------------------------------
    _shot(
        4, 1, "backs_suppressed", 4.5,
        "far down the row of parked cars, one silver sedan sits a hand's width "
        "higher than the others, level and still",
        LITTER, lens=28,
    ),
    _shot(
        5, 1, "faces_suppressed", 3.5,
        "behind the two figures, the same sedan hangs slightly above its space",
        PEOPLE, lens=50,
    ),
    # --- stage 2: unmistakable, and ignored -----------------------------
    _shot(
        6, 2, "backs_primary", 5.0,
        "the silver sedan resting level and completely still a full metre above "
        "its parking space, as though the space itself had been raised",
        PEOPLE,
    ),
    _shot(
        7, 2, "faces_primary", 3.5,
        "the floating sedan in the background, unremarked",
        PEOPLE, lens=50,
    ),
    # --- stage 3: everywhere --------------------------------------------
    _shot(
        8, 3, "backs_suppressed", 5.0,
        "four cars along the row now hanging at different heights above the "
        "kerb, all perfectly level, none of them moving",
        LITTER, lens=24,
    ),
    _shot(
        9, 3, "faces_suppressed", 3.5,
        "a municipal bus drifting slowly upward past a second-floor window",
        PEOPLE, lens=50,
    ),
    _shot(
        10, 3, "backs_primary", 4.0,
        "a skip hanging motionless above the pavement it was left on",
        LITTER,
    ),
    # --- stage 4: the street belongs to the rule -------------------------
    _shot(
        11, 4, "backs_suppressed", 5.5,
        "the whole row of parked cars risen to roof height, hanging level and "
        "still above the empty street",
        WEATHER, lens=24,
    ),
    # --- recovery: the world, after ---------------------------------------
    _shot(12, 0, "backs_suppressed", 4.0, None, LITTER, lens=50),
]

# Shots rendered on every model, not just the sequence model, so the cut still
# yields a model comparison. Chosen to span the ladder.
PROBE_ORDERS: tuple[int, ...] = (1, 6, 11)

SEQUENCE_MODEL = "wan-2.7"
PROBE_MODELS: tuple[str, ...] = ("kling-3.0", "veo-3.1-fast")


def validate() -> None:
    """Gate the whole sequence before a cent is spent."""
    check_concept(f"{WORLD} " + " ".join(s.anomaly or "" for s in SHOTS))
    for shot in SHOTS:
        if leaked := check_prompt(shot.prompt()):
            raise ValueError(f"{shot.shot_id}: dreamlike words leaked: {leaked}")


def plan() -> list[tuple[str, ShotSpec]]:
    """Every (model, shot) pair: the full sequence, plus probes."""
    validate()
    jobs = [(SEQUENCE_MODEL, shot) for shot in SHOTS]
    jobs += [
        (model, shot)
        for shot in SHOTS
        if shot.order in PROBE_ORDERS
        for model in PROBE_MODELS
    ]
    return jobs


def runtime_s() -> float:
    return sum(s.duration_s for s in SHOTS)
