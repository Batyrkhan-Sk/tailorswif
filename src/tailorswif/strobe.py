"""The strobe cut: a first-person nightclub, and faces you only half-see.

This is the same bet as `sequence.py` - one world, one rule, an escalation - but
it inverts the deadpan hypothesis instead of testing it. There, faces were
suppressed so no reaction could be read. Here the faces *are* the anomaly.

What replaces suppression is **intermittency**. The room's base state is
near-darkness; a strobe flash is the only moment a face fully resolves. The
viewer is never given long enough to check what they saw, and there is no second
look. That single property does three jobs at once:

  - it is the horror, which is about recognition you cannot confirm;
  - it hides the model's weakest frames, since anatomy only has to survive the
    lit ones, which is why this is cheaper to render than it looks;
  - it makes the cut possible at all (see TWINS below).

The anomalies are written as **observations, not emotions**. "Quiet
disappointment" is not a renderable instruction and, worse, a face that reads as
one clean legible emotion stops being frightening - six of those in a row is a
checklist of traumas rather than a mounting suspicion. So the prompts say
`unblinking, mouth closed and slightly downturned` and leave the reading to the
viewer. Intent lives in `note`, which is never sent.

**Twins.** The load-bearing trick. An anomaly is not rendered as an event inside
one clip - the model cannot be asked to hold an expression "a fraction of a
second too long". Instead a shot is rendered twice from the same start frame,
once clean and once wrong, and the two are cut together in the dark: face,
darkness, different face. The audience never witnesses the change, only the
before and the after, with no way to be sure the two were the same person.

Cutting on a *lit* frame shows them the swap and turns the film into an effect.
Every cut point in this piece lands on a dark frame.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .assemble import _require_ffmpeg
from .banned import check_concept, check_prompt
from .providers.base import CATALOG, TIER_RESOLUTION, Budget, BudgetExceeded
from .schemas import ShotSpec
from .staging import BY_KEY

STROBE_NAME = "strobe-club-01"
STROBE_MODEL = "seedance-2.5"

# Seedance is the pick for length and conditioning volume - 30s in one pass, up
# to 50 references - not for the end frame, which wan and kling also take. If
# this cut ever needs to be cheaper, kling-3.0 is the honest alternative: it is
# a third of the rate, it holds character consistency well, and the twin
# technique works there too. What it costs is Act IV, where the turn spreading
# across the room wants a single long take.
SMOKE_MODEL = "seedance-2.5-t2v-480"
SMOKE_TWIN_MODEL = "seedance-2.5-480"

# One room, described once, inherited by every shot - the same consistency
# mechanism the street sequence runs on, and the reason the cut might hold.
WORLD = (
    "An underground nightclub at night, very dark: low concrete ceiling, narrow "
    "dance floor, a lit bar at the back left, a small raised DJ booth at the "
    "back right, dense atmospheric haze, red, blue and violet LED beams cutting "
    "through the smoke"
)

# The governing light rule. Not atmosphere - it is the mechanism, so it rides on
# every generation rather than appearing in the shots that happen to need it.
FLICKER = (
    "Between intermittent white strobe flashes the faces fall into "
    "near-darkness; a face is fully lit only during a flash"
)

# What stays conspicuously normal. The bodies never stop being bodies: that is
# what keeps this psychological rather than a monster film, and it is the
# treatment's own instruction. At least one is visible in every shot.
DANCING = "The crowd keeps dancing at an ordinary human tempo, nobody reacting"
BODIES = "Bodies and hands stay anatomically ordinary and in proportion"
ROOM = "The ceiling, the bar and the DJ booth stay exactly where they were"


class StrobeShot(ShotSpec):
    """A shot whose prompt is a locked style block plus one line of action.

    `ShotSpec.prompt()` composes a street in flat daylight and ends on a fixed
    "one dominant light source ... shot on 35mm film" clause. Both are wrong for
    a room lit by a strobe, so the composition is overridden rather than the
    lighting fought with. Everything else on ShotSpec - pricing, handles,
    validation, the ledger fields - is inherited unchanged.

    The order matters: world, then light rule, then action. Video models weight
    early tokens, and the world has to survive twenty-five separate calls.
    """

    slate: str = ""
    note: str = ""

    def prompt(self) -> str:
        parts = [
            "First-person point of view, the camera is the character's eyes.",
            f"{self.lens_mm}mm wide angle, eye level 1.7m, handheld "
            "micro-motion, natural motion blur.",
            f"{WORLD.rstrip('. ')}.",
            f"{FLICKER.rstrip('. ')}.",
        ]
        if self.anomaly:
            parts.append(f"{self.anomaly.rstrip('. ')}.")
        parts.append(f"{self.invariant_shown.rstrip('. ')}.")
        parts.append(
            "Photorealistic, skin pores and sweat, deep blacks with preserved "
            "shadow detail, controlled highlights, cinematic colour grade."
        )
        return " ".join(parts)


def _shot(
    n: int,
    slate: str,
    stage: int,
    duration: float,
    anomaly: str | None,
    *,
    note: str = "",
    invariant: str = DANCING,
    staging: str = "pov_crowd",
    intensity: int = 1,
    risk: int = 2,
    lens: int = 26,
) -> StrobeShot:
    return StrobeShot(
        shot_id=f"{STROBE_NAME}.{slate}",
        slate=slate,
        note=note,
        duration_s=duration,
        environment=WORLD,
        anomaly=anomaly,
        rule_id="strobe-faces",
        invariant_shown=invariant,
        staging=BY_KEY[staging],
        lens_mm=lens,
        handles_s=0.5,
        order=n,
        stage=stage,
        intensity=intensity,
        render_risk=risk,
    )


# Twenty-five renders for twenty slates: five of them are twins or variants of a
# shot already in the list, rendered from the same start frame so they can be cut
# against it. `order` is render order; `slate` is what the shot is called.
SHOTS: list[StrobeShot] = [
    # --- act I: the real club ------------------------------------------------
    # Nothing is wrong, and the audience has to believe that completely or there
    # is nothing to take away later. Cheapest material in the film - shoot it
    # first, at 480p, to find out whether the room holds before spending.
    _shot(
        1, "S01", 0, 6.0,
        "Slow walk forward into the packed dance floor, people dancing close on "
        "both sides, laughing, arms raised, sweat on their skin, bodies brushing "
        "past the lens",
        note="Establish euphoria.", invariant=DANCING, intensity=0, risk=2,
    ),
    _shot(
        2, "S02", 0, 6.0,
        "Continuing forward, deeper into the crowd, a woman with dark hair "
        "pinned up dancing on the left and a man in a black t-shirt on the "
        "right, the DJ booth beyond them",
        note="Plant the two faces that will break. Do not emphasise them.",
        invariant=ROOM, intensity=0, risk=2,
    ),
    _shot(
        3, "S03", 0, 5.0,
        "The head turning slowly right, taking in the lit bar at the back left "
        "and the raised DJ booth beyond the dancers",
        note="Geography. Own the room before breaking it.",
        invariant=ROOM, intensity=0, risk=1, lens=24,
    ),

    # --- act II: the first wrongness ----------------------------------------
    # Twin pairs. S04/S04X is also the smoke test: if that cut works, the film
    # works, and it costs about $2.65 to find out.
    #
    # Every recurring figure carries a re-identification handle - pinned-up hair,
    # a black t-shirt, grey stubble, height. Without one the model recasts the
    # person between the clean take and its twin, and the cut then reads as a
    # jump between two different people rather than as one person changing.
    #
    # The handles are deliberately dull. An earlier draft used "a woman in a red
    # top", which works on the model and fails on the audience: in a dark room
    # lit red she is the most conspicuous thing in frame, so the composition
    # announces her as important before anything has happened to her. That is
    # the opposite of Emphasis.SUPPRESSED, and it telegraphs the anomaly. A
    # handle has to be legible to the model without being legible as emphasis.
    #
    # The better fix, once there is a face to reference: hold identity with a
    # portrait on seedance-2.5/reference-to-video (addressed as [Image1] in the
    # prompt) and drop the costume handle entirely.
    _shot(
        4, "S04", 0, 5.0,
        "A woman with dark hair pinned up dancing directly ahead in a plain "
        "dark top, close to the lens, smiling, glancing at the camera, looking "
        "away, still dancing",
        note="Twin A. Keep its first frame.",
        staging="pov_held", intensity=0, risk=2,
    ),
    _shot(
        5, "S04X", 1, 5.0,
        "The same woman with dark hair pinned up, same position, still dancing, "
        "smiling at the lens and not stopping, not blinking, her eyes fixed on "
        "the camera while her body keeps dancing to the beat",
        note="Twin B. The smile held too long - built as a cut, not a duration.",
        staging="pov_held", invariant=BODIES, intensity=1, risk=3,
    ),
    _shot(
        6, "S05", 0, 5.0,
        "A man in a black t-shirt dancing just right of centre, head down, "
        "absorbed in the music, blue beams moving across his shoulders",
        note="Twin A.", staging="pov_held", intensity=0, risk=2,
    ),
    _shot(
        7, "S05X", 1, 5.0,
        "The same man, same position, same dance, his eyes entirely dark with no "
        "whites and no catchlight, his expression otherwise neutral, still dancing",
        note="Twin B. Dark eyes, body language untouched.",
        staging="pov_held", invariant=BODIES, intensity=2, risk=3,
    ),
    _shot(
        8, "S06", 2, 5.0,
        "A woman in her forties caught mid-crowd by a single strobe flash, "
        "looking directly at the lens, lips parted as if about to speak, her "
        "face lost in the dark between flashes",
        note="Half-recognition. A face almost placed.",
        staging="pov_held", intensity=2, risk=3,
    ),
    _shot(
        9, "S07", 2, 5.0,
        "A man in his sixties with grey stubble standing motionless among the "
        "dancers, facing the lens, unblinking, mouth closed and slightly "
        "downturned, everyone around him still dancing",
        note="The disappointed familiar face.",
        staging="pov_held", intensity=2, risk=3,
    ),
    _shot(
        10, "S08", 2, 5.0,
        "A tall man directly ahead lit from below by red LED, his head tilted "
        "down toward the lens, standing a head above everyone near him and not "
        "moving, dancers passing between him and the camera",
        note="The intimidating adult. Height and low light do the work.",
        staging="pov_held", intensity=2, risk=3,
    ),
    _shot(
        11, "S09", 2, 5.0,
        "A woman near the bar who has stopped dancing and is looking down at "
        "something out of frame below the camera, eyebrows raised, mouth "
        "slightly open, not looking at the lens",
        note="Watching a frightened child. She never looks at the lens.",
        intensity=2, risk=3,
    ),
    _shot(
        12, "S10", 2, 5.0,
        "A young man dancing directly ahead close to the lens, his face slack "
        "and still, eyes open, mouth loose, while his body moves in time with "
        "the beat",
        note="Abandonment. Absence of expression, not an expression of horror.",
        staging="pov_held", invariant=BODIES, intensity=2, risk=3,
    ),
    _shot(
        13, "S11", 2, 5.0,
        "A woman dancing close on the right, her mouth stretched wide in a smile "
        "while the muscles around her eyes stay completely still",
        note="The emotionally inappropriate smile.",
        staging="pov_held", intensity=2, risk=3,
    ),

    # --- act III: destabilise -------------------------------------------------
    # Panic in the camera, not in the crowd. No anomaly in these three: the room
    # is behaving, and that is what makes it worse.
    _shot(
        14, "S12", 2, 5.0,
        "A fast look left, then right, then back over the shoulder, the crowd "
        "smearing, the focus hunting and settling late, dancers pressing in on "
        "every side",
        note="The looking-around begins.", invariant=DANCING, intensity=1, risk=2,
    ),
    _shot(
        15, "S13", 2, 5.0,
        "The camera backing away and bumping into a dancer's shoulder, lurching, "
        "recovering, bodies close on all sides with no gap in the crowd, the low "
        "concrete ceiling overhead",
        note="Contact. The collision the treatment asks for.",
        invariant=ROOM, intensity=1, risk=3,
    ),
    _shot(
        16, "S14", 2, 5.0,
        "Pushing between two dancers, their faces very close to the lens, haze "
        "thick, rapid white strobe flashes, high contrast with controlled "
        "highlights",
        note="Peak strobe. Last shot before the room notices.",
        invariant=BODIES, intensity=1, risk=3,
    ),

    # --- act IV: the turn -----------------------------------------------------
    # The spread has to be gradual or the climax has nowhere to go. Worth
    # considering as one 20s take instead of three: it is a single continuous
    # action, and Seedance does 30s in one pass.
    _shot(
        17, "S15", 3, 5.0,
        "Far across the dance floor a woman stopping dancing and turning to face "
        "the lens, standing completely still while everyone else keeps dancing "
        "around her",
        note="One. Distance is essential - she must be almost missable.",
        invariant=DANCING, intensity=2, risk=2,
    ),
    _shot(
        18, "S16", 3, 6.0,
        "The woman still facing the lens, two dancers beside her slowing and "
        "turning toward the camera as well, the rest of the room still dancing",
        note="Three. The spread begins, unhurried.",
        invariant=DANCING, intensity=2, risk=3,
    ),
    _shot(
        19, "S17", 3, 6.0,
        "Half the dance floor stopped, rows of people standing facing the lens "
        "with their arms at their sides while the others still dance around "
        "them, red and blue beams cutting across the motionless bodies",
        note="Half. Dancers and statues in one frame - the film's best image.",
        invariant=BODIES, intensity=3, risk=3,
    ),

    # --- act V: climax, blackout, return --------------------------------------
    _shot(
        20, "S18", 4, 6.0,
        "Every person on the dance floor standing motionless facing the lens, "
        "arms at their sides, nobody dancing, blank attentive faces, the camera "
        "trembling slightly",
        note="All of them. Base bed for the variants - keep its first frame.",
        staging="pov_held", invariant=BODIES, intensity=3, risk=3,
    ),
    _shot(
        21, "S18Xa", 4, 4.0,
        "Every person standing motionless facing the lens, the front row's faces "
        "subtly familiar, mouths closed and slightly downturned",
        note="Flash variant. 6-10 frames, cut in the dark.",
        staging="pov_held", invariant=BODIES, intensity=3, risk=3,
    ),
    _shot(
        22, "S18Xb", 4, 4.0,
        "Every person standing motionless facing the lens, the front row smiling "
        "widely, the muscles around their eyes unmoving",
        note="Flash variant.",
        staging="pov_held", invariant=BODIES, intensity=3, risk=3,
    ),
    _shot(
        23, "S18Xc", 4, 4.0,
        "Every person standing motionless facing the lens, the front row's eyes "
        "dark with pupils fully blown, fixed on the camera",
        note="Flash variant.",
        staging="pov_held", invariant=BODIES, intensity=3, risk=3,
    ),
    _shot(
        24, "S19", 4, 4.0,
        "The white strobe firing and holding, filling the frame, the faces "
        "washing out to pure white, rising overexposure",
        note="Into white. The cut to black is made in the edit, not here.",
        invariant=ROOM, intensity=3, risk=1,
    ),
    _shot(
        25, "S20", 0, 8.0,
        "The crowd dancing normally with ordinary faces, nobody looking at the "
        "lens, the camera holding still and then looking slowly left and right "
        "in small nervous movements",
        note="The return. Identical to Act I, so nothing can be confirmed.",
        invariant=DANCING, intensity=0, risk=2,
    ),
]

BY_SLATE: dict[str, StrobeShot] = {s.slate: s for s in SHOTS}

# (clean, wrong) pairs rendered from one start frame and cut against each other.
# The first is the smoke test.
TWINS: tuple[tuple[str, str], ...] = (
    ("S04", "S04X"),
    ("S05", "S05X"),
    ("S18", "S18Xa"),
    ("S18", "S18Xb"),
    ("S18", "S18Xc"),
)

# Nothing is probed on another model. Seedance is load-bearing here rather than
# one option among several - see SMOKE_TWIN_MODEL above - so a probe would only
# tell us what we already know, which is that the others cannot take an end frame.
PROBE_ORDERS: tuple[int, ...] = ()
PROBE_MODELS: tuple[str, ...] = ()


def validate() -> None:
    """Gate the whole cut before a cent is spent."""
    check_concept(f"{WORLD} " + " ".join(s.anomaly or "" for s in SHOTS))
    for shot in SHOTS:
        if leaked := check_prompt(shot.prompt()):
            raise ValueError(f"{shot.shot_id}: dreamlike words leaked: {leaked}")
    for clean, wrong in TWINS:
        for slate in (clean, wrong):
            if slate not in BY_SLATE:
                raise ValueError(f"twin references unknown slate: {slate}")


def plan() -> list[tuple[str, StrobeShot]]:
    validate()
    return [(STROBE_MODEL, shot) for shot in SHOTS]


def runtime_s() -> float:
    """Cut length, counting each twin as an insert into its clean take."""
    inserts = {wrong for _, wrong in TWINS}
    return sum(s.duration_s for s in SHOTS if s.slate not in inserts)


# --------------------------------------------------------------------------- #
# The smoke test
#
# The S04/S04X pair is a complete miniature of the film, which is why it is the
# thing to run first. It exercises four assumptions *together* - and the risk is
# in their interaction, not in any one of them:
#
#   1. the room's base state goes dark and faces resolve only in flashes
#   2. the point of view stays clean, with no body entering frame
#   3. anatomy survives the lit frames
#   4. two takes from one start frame match closely enough to cut invisibly
#
# Any cheaper test proves something already known. A single handsome club shot
# only establishes that the model can render a nightclub, which was never the
# question.


def first_frame(video: Path, out: Path) -> Path:
    """Lift frame zero out of a clip, to seed the next generation from it."""
    ffmpeg = _require_ffmpeg()
    out.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [ffmpeg, "-y", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(out)],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not out.exists():
        raise RuntimeError(f"frame extract failed:\n{result.stderr[-800:]}")
    return out


def twin_cut(
    clean: Path, wrong: Path, out: Path, at_s: float = 2.0, hold_s: float = 0.5
) -> Path:
    """Cut the anomaly into the clean take and back out again.

    A first look, not a finish. `hold_s` defaults to twelve frames at 24fps,
    which is the middle of the 8-14 frame window where the anomaly registers
    without being readable. Tune it in an editor afterwards - that single dial
    is what gets tuned across the whole film.

    Both cut points want to land on a dark frame. This picks them by time rather
    than by looking at the picture, so expect to nudge `at_s` by a few frames
    once you can see where the flashes actually fell.
    """
    ffmpeg = _require_ffmpeg()
    out.parent.mkdir(parents=True, exist_ok=True)
    chain = (
        f"[0:v]trim=0:{at_s},setpts=PTS-STARTPTS[a];"
        f"[1:v]trim={at_s}:{at_s + hold_s},setpts=PTS-STARTPTS[b];"
        f"[0:v]trim={at_s + hold_s},setpts=PTS-STARTPTS[c];"
        f"[a][b][c]concat=n=3:v=1[v]"
    )
    result = subprocess.run(
        [ffmpeg, "-y", "-i", str(clean), "-i", str(wrong),
         "-filter_complex", chain, "-map", "[v]",
         "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(out)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"twin cut failed:\n{result.stderr[-800:]}")
    return out


CHECKLIST = """
  Check these in order - the first is the one most likely to fail, and the
  only one whose failure means a redesign rather than a retake.

  1  Does the room go dark?      Between flashes the faces should be
     unreadable: silhouettes, beams, haze. A continuously lit club means the
     mechanic did not survive the prompt - move the flicker to post, generate
     under even light and build the strobe with a luma curve in the grade.

  2  Is the point of view clean? No hands, arms or shoulders entering at the
     bottom of frame. One intrusion in five seconds is a framing problem, not
     bad luck - fix it by reframing ("seen from chest height upward"), never
     by naming the body part.

  3  Does anatomy hold in the flashes? Failures in the dark frames do not
     count. Nobody will ever see them. If lit frames break, thin the crowd in
     the plate - density is the cost driver, and a slightly emptier floor in a
     very dark room reads as identical.

  4  Do the twins match?         Flick between clean and wrong. Framing, crowd
     and lighting should sit close enough that a cut made in darkness does not
     jump. If they drift, pin both ends with end_image_url.

  5  Watch twin-cut.mp4 once, at speed. You should feel that something was
     wrong without being able to say what. If you can name it, the anomaly is
     too legible. If you notice nothing at all, hold two frames longer.
"""


def run_smoke(
    provider,
    *,
    root: Path,
    budget: Budget,
    at_s: float = 2.0,
    hold_s: float = 0.5,
) -> int:
    """Render the S04/S04X twin pair, cut them together, print the checklist."""
    validate()
    clean_shot, wrong_shot = BY_SLATE["S04"], BY_SLATE["S04X"]
    clean_spec, wrong_spec = CATALOG[SMOKE_MODEL], CATALOG[SMOKE_TWIN_MODEL]
    root.mkdir(parents=True, exist_ok=True)

    jobs = [(clean_shot, clean_spec), (wrong_shot, wrong_spec)]
    quote = sum(s.price(sh.render_duration_s) for sh, s in jobs)
    print(f"\n\033[1mstrobe smoke test\033[0m  S04 / S04X, "
          f"{clean_spec.model_id.rsplit('/', 1)[-1]}, ${quote:.2f}\n")

    paths: dict[str, Path] = {}
    start_image: str | None = None

    for shot, spec in jobs:
        out = root / f"{shot.slate}.mp4"
        resolution = TIER_RESOLUTION.get(spec.key, "480p")
        price = spec.price(shot.render_duration_s)
        try:
            budget.reserve(price)
        except BudgetExceeded as exc:
            print(f"stopped: {exc}")
            return 1

        print(f"gen   {shot.slate:<6} {shot.render_duration_s:.1f}s "
              f"{resolution}  ${price:.2f} ... ", end="", flush=True)
        try:
            actual = provider.generate(
                spec=spec,
                prompt=shot.prompt(),
                duration_s=shot.render_duration_s,
                out_path=str(out),
                start_image=start_image,
                resolution=resolution,
            )
        except Exception as exc:
            budget.release(price)
            print(f"failed: {exc}")
            return 1
        budget.settle(price, actual)
        paths[shot.slate] = out
        print(f"ok  (${actual:.2f})")

        # The anomaly starts from the clean take's own first frame, so the two
        # begin identically. That is the twin condition, and it means the test
        # needs no separate plate and no image model.
        if shot.slate == "S04":
            if provider.name == "dryrun":
                print("      (dryrun: no video to lift a frame from)")
                break
            plate = first_frame(out, root / "S04.frame0.png")
            print(f"frame {plate.name}  -> uploading ... ", end="", flush=True)
            start_image = provider.upload(str(plate))
            print("ok")

    if provider.name == "dryrun":
        print(f"\ndryrun: ${budget.spent_usd:.2f} spent, "
              f"${quote:.2f} is what this would cost on fal.")
        print("next: rerun with --provider fal")
        return 0

    cut = twin_cut(paths["S04"], paths["S04X"], root / "twin-cut.mp4",
                   at_s=at_s, hold_s=hold_s)
    print(f"\n{cut}  ({cut.stat().st_size / 1e6:.1f} MB)   "
          f"${budget.spent_usd:.2f} spent")
    print(CHECKLIST)
    return 0
