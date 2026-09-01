"""The Deadpan Test.

One surreal beat, rendered across three models and four staging strategies.
Twelve takes, sixty-six pairwise comparisons, roughly $40.

It answers three questions no amount of architecture can:
  1. Which model can hold a restrained, photographic register at all?
  2. Is deadpan reachable through blocking, or does it collapse either way?
  3. What does a frame in this register actually look like when we get one?

And it produces the first sixty-six preference labels, which is the seed of the
only asset here that compounds.

If none of the twelve is good, that is the most valuable thing you can learn
this month, and it cost $40.
"""

from __future__ import annotations

from .banned import check_concept, check_prompt
from .schemas import RealityRule, ShotSpec, ShotType
from .staging import STRATEGIES

# One rule, narrow domain, three invariants. The invariants are the point:
# the strangeness reads as designed because of what refuses to change.
GRAVITY_RULE = RealityRule(
    id="rule.gravity_release",
    statement="Objects heavier than a car have stopped being held down.",
    domain="vehicles and large street furniture in one city district",
    invariants=[
        "people walk and stand normally, entirely unaffected",
        "light, weather and shadow behave exactly as they should",
        "small objects - litter, bags, birds - obey gravity as usual",
    ],
    manifestations=[
        "a parked sedan resting a metre above its parking space, level and still",
        "a municipal bus drifting slowly at second-floor height",
        "a skip hanging motionless above the pavement it was left on",
    ],
    escalation=[
        "a parked sedan resting a metre above its parking space, level and still",
        "a municipal bus drifting slowly at second-floor height",
    ],
    forbidden=[
        "debris swirling",
        "anything glowing or trailing light",
        "people floating",
        "visible energy or force effects",
        "damage, panic or spectacle of any kind",
    ],
    why=(
        "Weightlessness treated as a municipal inconvenience is funnier and "
        "sadder than weightlessness treated as an event."
    ),
)

# Deliberately mundane, over-specified, and photographic. Specificity is what
# buys perceived production value; 'a cool city' buys nothing.
ENVIRONMENT = (
    "A residential street in a post-war concrete housing district on an overcast "
    "weekday morning, wet pavement, faded shopfront signage, parked hatchbacks, "
    "a bus shelter with a cracked panel, bare plane trees"
)

ANOMALY = (
    "a parked silver sedan resting level and completely still about one metre "
    "above its parking space, as though the space had simply been raised"
)

INVARIANT_SHOWN = (
    "Litter and fallen leaves lie on the ground normally and the light is flat "
    "and even, exactly as on any ordinary morning"
)

MODELS: tuple[str, ...] = ("wan-2.7", "kling-3.0", "veo-3.1-fast")

EXPERIMENT_NAME = "deadpan-test-01"


def build_shots(
    *,
    environment: str = ENVIRONMENT,
    anomaly: str = ANOMALY,
    invariant_shown: str = INVARIANT_SHOWN,
    duration_s: float = 6.0,
) -> list[ShotSpec]:
    """The four staging variants of one shot. Concept-gated before anything renders."""
    check_concept(f"{environment} {anomaly}")

    shots = []
    for staging in STRATEGIES:
        shot = ShotSpec(
            shot_id=f"deadpan.{staging.key}",
            shot_type=ShotType.GENERATED,
            duration_s=duration_s,
            environment=environment,
            anomaly=anomaly,
            rule_id=GRAVITY_RULE.id,
            invariant_shown=invariant_shown,
            staging=staging,
            lens_mm=35,
            handles_s=1.0,
        )
        if leaked := check_prompt(shot.prompt()):
            raise ValueError(
                f"{shot.shot_id}: dreamlike style words leaked into the prompt: "
                f"{leaked}. The register must come from staging, not adjectives."
            )
        shots.append(shot)
    return shots


def matrix(models: tuple[str, ...] = MODELS) -> list[tuple[str, ShotSpec]]:
    """Every (model, shot) pair - the full run."""
    return [(model, shot) for model in models for shot in build_shots()]


def pair_count(n_takes: int) -> int:
    """Comparisons needed to rank n takes exhaustively."""
    return n_takes * (n_takes - 1) // 2
