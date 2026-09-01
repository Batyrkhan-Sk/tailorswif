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

STRATEGIES: tuple[Staging, ...] = (
    FACES_PRIMARY,
    FACES_SUPPRESSED,
    BACKS_PRIMARY,
    BACKS_SUPPRESSED,
)

BY_KEY: dict[str, Staging] = {s.key: s for s in STRATEGIES}
