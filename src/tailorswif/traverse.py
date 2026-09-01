"""The traverse: one figure, twelve spaces, twelve unrelated wrongnesses.

A different structural template from `sequence.py`, and the one the reference
work in this genre actually uses.

    sequence  one altered law, one location, escalating.
    traverse  a figure walks through connected spaces. Each has its own
              anomaly. Nothing escalates. The unifying principle is not a
              physical rule at all - it is *tone*.

Two things make it worth building.

**Threshold transitions are free.** The signature move is a door opening onto
somewhere it could not open onto. In live action that is a built set and a
compositing job; here it is two clips cut together. The traverse plays to what
generation is good at - impossible cuts - instead of what it is bad at, which is
sustained coherence inside one shot.

**Backs-only solves two problems at once.** A traverse needs the same person in
every shot and there is no identity layer yet, so a face would drift into a
different person by shot twelve. Never showing the face fixes that for free, and
it is also the deadpan register: no face means no reaction to read.

The anomalies deliberately span intensity 1 to 3. Crossed with staging that
never emphasises them, this asks the sharper question: **can a loud anomaly
survive being shot quietly, or does it demand emphasis?** If the loud ones only
work at PRIMARY, the deadpan register has a ceiling and we need to know where.

Grammar taken from the genre; content is our own. No location, character or gag
is lifted from any existing video, and no director or work is ever named in a
prompt - both a provenance problem and, on most providers, a filtered request.
"""

from __future__ import annotations

from .banned import check_concept, check_prompt
from .experiment import GRAVITY_RULE
from .schemas import ShotSpec, ShotType
from .staging import BY_KEY

TRAVERSE_NAME = "overcoat-01"

# The figure itself is described in the FOLLOW / THRESHOLD staging notes, so it
# is worded identically in every shot - the cheapest identity mechanism there is,
# and the reason the figure might survive twelve separate generations.

# Tone, not plot. This is what the twelve spaces have in common.
REGISTER = (
    "Low winter sun raking in through windows at a steep angle, strong "
    "directional light and deep shadow, worn municipal surfaces catching "
    "specular highlight, a restrained palette with one warm accent"
)

# Invariants, phrased for the frame. At least one holds in every shot.
NOBODY_LOOKS = "Nobody present pays the slightest attention"
ORDINARY_PACE = "Everyone moves at an ordinary unhurried pace"
NORMAL_LIGHT = "The light is ordinary for the place and time, shadows falling consistently from one direction"


def _shot(
    n: int,
    staging_key: str,
    duration: float,
    environment: str,
    anomaly: str | None,
    invariant: str,
    *,
    intensity: int = 1,
    risk: int = 1,
    lens: int = 35,
) -> ShotSpec:
    return ShotSpec(
        shot_id=f"{TRAVERSE_NAME}.{n:02d}",
        shot_type=ShotType.GENERATED,
        duration_s=duration,
        environment=f"{environment}. {REGISTER}",
        anomaly=anomaly,
        rule_id=GRAVITY_RULE.id,  # placeholder: a traverse is tonal, not ruled
        invariant_shown=invariant,
        staging=BY_KEY[staging_key],
        lens_mm=lens,
        handles_s=0.5,
        order=n,
        stage=0,
        intensity=intensity,
        render_risk=risk,
    )


SHOTS: list[ShotSpec] = [
    # 1 - establish the figure and the register. Nothing wrong.
    _shot(
        1, "follow", 4.0,
        "A tiled municipal stairwell with a metal handrail and a small dirty "
        "window on the half-landing",
        None, NORMAL_LIGHT, intensity=0, lens=28,
    ),
    # 2 - first threshold, first wrongness. Quiet.
    _shot(
        2, "threshold", 4.5,
        "A launderette with a row of front-loading machines and a folding table",
        "in one machine a full-grown sheep turns slowly with the drum, calm and "
        "unbothered, while a woman folds towels at the table without looking up",
        NOBODY_LOOKS, intensity=2, lens=35,
    ),
    # 3 - a corridor beat. Small, throwaway, keeps the density up.
    _shot(
        3, "follow", 3.0,
        "A long corridor with woodchip wallpaper and a worn carpet runner",
        "a man walks past in the opposite direction carrying a full-sized "
        "interior door under one arm",
        ORDINARY_PACE, intensity=1, lens=35,
    ),
    # 4 - the user's grenades. The strongest idea here, and the easiest render:
    # small scale, static, no human anatomy. Shot exactly like a cookery
    # programme - the wow is in the content, never in the camera.
    _shot(
        4, "domestic", 4.5,
        "A small domestic kitchen, a gas hob, a scratched steel frying pan, "
        "a tea towel over the oven rail",
        "a dozen hand grenades frying in shallow oil in the pan, being turned "
        "and shaken exactly like a pan of chips, oil bubbling around them",
        ORDINARY_PACE, intensity=3, lens=50,
    ),
    # 5 - threshold onto a bus.
    _shot(
        5, "threshold", 4.0,
        "The interior of a single-decker city bus, plaid moquette seats, "
        "condensation on the windows",
        "every other passenger is asleep bolt upright in exactly the same "
        "posture, hands flat on their knees, heads level",
        NORMAL_LIGHT, intensity=2, lens=28,
    ),
    # 6 - a window beat. Pure background anomaly, no emphasis at all.
    _shot(
        6, "follow", 3.5,
        "Through the bus window, flat wet farmland going past",
        "a full brass marching band in uniform stands in the middle of an empty "
        "field, playing, with no audience and no stage",
        NOBODY_LOOKS, intensity=2, lens=50,
    ),
    # 7 - the user's head-in-sand. Highest risk in the run: human anatomy in an
    # unusual configuration is exactly where models produce limb garbage. Shot
    # wide, with the sand hiding the join, to give it the best chance.
    _shot(
        7, "follow", 5.0,
        "A municipal sandpit in a small urban park, railings, a bin, "
        "flat grey daylight",
        "a person planted head-down in the sand up to the shoulders, their legs "
        "and torso upright above the surface performing a slow controlled "
        "breakdance, unhurried and precise, while two people on a bench nearby "
        "continue reading",
        NOBODY_LOOKS, intensity=3, risk=3, lens=28,
    ),
    # 8 - the puddle. Our own, not the reference's: same joke family - water,
    # scale, urban misplacement - and far easier to render than an animal.
    _shot(
        8, "follow", 4.0,
        "A cracked pavement outside a shuttered shop, a shallow puddle "
        "the size of a doormat",
        "a man in waterproofs sits on a folding chair beside the puddle with a "
        "full fishing rod, line in three inches of water, a keep net beside him",
        ORDINARY_PACE, intensity=2, lens=35,
    ),
    # 9 - a walk-past beat. Deliberately unremarked.
    _shot(
        9, "follow", 3.0,
        "A pedestrian underpass with tiled walls and strip lighting",
        "a large dog walks past upright on its hind legs at a normal walking "
        "pace, wearing nothing, entirely matter-of-fact",
        NOBODY_LOOKS, intensity=2, risk=2, lens=35,
    ),
    # 10 - threshold into a shop. Quiet again, to let the loud ones land.
    _shot(
        10, "threshold", 4.0,
        "A small high-street bakery, wire shelves, a glass counter, "
        "a till with a handwritten sign",
        "the baker is asleep standing bolt upright behind the counter, and "
        "every loaf and roll on every shelf is uniformly grey",
        NORMAL_LIGHT, intensity=2, lens=35,
    ),
    # 11 - the biggest space, still no emphasis.
    _shot(
        11, "follow", 5.0,
        "A municipal football pitch with worn goalmouths and a low fence",
        "twenty-two players in full kit and a referee are playing a committed, "
        "physical match with no ball anywhere on the pitch",
        ORDINARY_PACE, intensity=3, lens=24,
    ),
    # 12 - the loop closes. Same stairwell, empty. The recovery shot.
    _shot(
        12, "threshold", 4.0,
        "The same tiled municipal stairwell, metal handrail, dirty half-landing "
        "window, now empty",
        "a dark wool overcoat hangs over the handrail",
        NORMAL_LIGHT, intensity=1, lens=28,
    ),
]

# Chosen to span intensity: one quiet, one loud-and-safe, one loud-and-risky.
PROBE_ORDERS: tuple[int, ...] = (3, 4, 7)

TRAVERSE_MODEL = "wan-2.7"
PROBE_MODELS: tuple[str, ...] = ("kling-3.0", "veo-3.1-fast")


def validate() -> None:
    check_concept(" ".join(s.anomaly or "" for s in SHOTS))
    for shot in SHOTS:
        if leaked := check_prompt(shot.prompt()):
            raise ValueError(f"{shot.shot_id}: dreamlike words leaked: {leaked}")


def plan() -> list[tuple[str, ShotSpec]]:
    validate()
    jobs = [(TRAVERSE_MODEL, shot) for shot in SHOTS]
    jobs += [
        (model, shot)
        for shot in SHOTS
        if shot.order in PROBE_ORDERS
        for model in PROBE_MODELS
    ]
    return jobs


def runtime_s() -> float:
    return sum(s.duration_s for s in SHOTS)
