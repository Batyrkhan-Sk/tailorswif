"""The four staging strategies under test in the Deadpan Test.

The experiment varies two binary factors that the architecture review argues
are the real levers on the deadpan register:

  faces_visible  - can the audience read a reaction on anyone in frame?
  emphasis       - does the composition privilege the anomaly, or ignore it?

The hypothesis is that `BACKS_SUPPRESSED` wins and `FACES_PRIMARY` looks like
every other AI video. That hypothesis is cheap to be wrong about, which is the
whole point of running this before writing a pipeline.
"""

from __future__ import annotations

from .schemas import Emphasis, Staging

FACES_PRIMARY = Staging(
    key="faces_primary",
    label="Faces visible, anomaly foregrounded",
    emphasis=Emphasis.PRIMARY,
    faces_visible=True,
    camera_note=(
        "Medium shot at eye level, the subject centred and sharp, "
        "shallow depth of field"
    ),
    blocking_note=(
        "Two people face camera in the mid-ground, their expressions clearly legible"
    ),
)

FACES_SUPPRESSED = Staging(
    key="faces_suppressed",
    label="Faces visible, anomaly in the background",
    emphasis=Emphasis.SUPPRESSED,
    faces_visible=True,
    camera_note=(
        "Medium-wide shot at eye level, deep focus, the frame composed around "
        "the street rather than around any single event"
    ),
    blocking_note=(
        "Two people face camera in the mid-ground continuing a conversation, "
        "their expressions unchanged and their attention on each other"
    ),
)

BACKS_PRIMARY = Staging(
    key="backs_primary",
    label="No faces, anomaly foregrounded",
    emphasis=Emphasis.PRIMARY,
    faces_visible=False,
    camera_note=(
        "Medium shot at eye level, the subject centred and sharp, "
        "shallow depth of field"
    ),
    blocking_note=(
        "Pedestrians walk away from camera through the frame, seen from behind, "
        "no face turned toward the lens"
    ),
)

BACKS_SUPPRESSED = Staging(
    key="backs_suppressed",
    label="No faces, anomaly in the background",
    emphasis=Emphasis.SUPPRESSED,
    faces_visible=False,
    camera_note=(
        "Wide static shot at chest height, deep focus throughout, the composition "
        "weighted toward the architecture with the event placed off-centre and small"
    ),
    blocking_note=(
        "Pedestrians walk steadily through the frame seen from behind and in "
        "profile, nobody stopping, nobody turning, nobody looking"
    ),
)

# --- traverse grammar -------------------------------------------------------
# A traverse needs a protagonist in every shot, and we have no identity layer
# yet - faces would drift into a different person by shot twelve. Seeing the
# figure only from behind solves that for free, and it *is* the deadpan
# register: no face means no reaction to read.

FOLLOW = Staging(
    key="follow",
    label="Following the figure from behind",
    emphasis=Emphasis.SECONDARY,
    faces_visible=False,
    camera_note=(
        "Handheld medium-wide shot following a walking figure from directly "
        "behind at shoulder height, deep focus, the figure kept small in frame"
    ),
    blocking_note=(
        "A figure in a dark wool overcoat walks steadily away from camera, "
        "never turning, never stopping, face never visible"
    ),
)

THRESHOLD = Staging(
    key="threshold",
    label="The figure passing through a doorway",
    emphasis=Emphasis.SECONDARY,
    faces_visible=False,
    camera_note=(
        "Static wide shot square onto a doorway, deep focus, the room beyond "
        "clearly readable through the opening"
    ),
    blocking_note=(
        "A figure in a dark wool overcoat pushes through the door and walks on "
        "without pausing, seen from behind, face never visible"
    ),
)

# The still-life register: shoot the impossible thing exactly as you would shoot
# an ordinary one. This is what lets a loud anomaly stay deadpan - the wow is in
# the content, never in the camera.
DOMESTIC = Staging(
    key="domestic",
    label="Ordinary coverage of an extraordinary thing",
    emphasis=Emphasis.SECONDARY,
    faces_visible=False,
    camera_note=(
        "Static close shot from slightly above, the way a cookery programme "
        "covers a hob, unremarkable framing, no camera movement at all"
    ),
    blocking_note=(
        "A pair of hands works at ordinary speed, unhurried, out of frame "
        "above the wrist"
    ),
)

STRATEGIES: tuple[Staging, ...] = (
    FACES_PRIMARY,
    FACES_SUPPRESSED,
    BACKS_PRIMARY,
    BACKS_SUPPRESSED,
)

TRAVERSE_STRATEGIES: tuple[Staging, ...] = (FOLLOW, THRESHOLD, DOMESTIC)

BY_KEY: dict[str, Staging] = {
    s.key: s for s in STRATEGIES + TRAVERSE_STRATEGIES
}
