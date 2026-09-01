"""Typed artifacts for the pipeline.

The load-bearing idea is `RealityRule.invariants`: a surreal world reads as
designed largely because of what it refuses to change. A rule is defined as
much by its boundary as by its effect, so invariants are required and a shot
must show at least one of them holding.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Unit = Annotated[float, Field(ge=0.0, le=1.0)]


class Emphasis(StrEnum):
    """Where the anomaly sits in the frame's attention hierarchy.

    `SUPPRESSED` is the deadpan register: the composition gives the anomaly no
    more weight than anything else, which is why it lands.
    """

    PRIMARY = "primary"
    SECONDARY = "secondary"
    SUPPRESSED = "suppressed"


class ShotType(StrEnum):
    GENERATED = "generated"  # text/image -> video, whole frame from the model
    COMP = "comp"  # plate + element placed into it
    SPLAT = "splat"  # virtual camera through captured 3D geometry


class RealityRule(BaseModel):
    """One altered rule of physics, biology or society, plus its boundary."""

    id: str
    statement: str = Field(min_length=12)
    domain: str = Field(description="What the rule acts on. Keep it narrow.")

    invariants: list[str] = Field(
        min_length=3,
        description="What stays conspicuously normal. This is what makes the "
        "strangeness read as intentional rather than random.",
    )
    manifestations: list[str] = Field(min_length=2)
    escalation: list[str] = Field(
        min_length=1,
        description="Ordered subtle -> overt. Each entry should be a manifestation.",
    )
    forbidden: list[str] = Field(
        default_factory=list,
        description="What would make this generic if it crept in.",
    )
    why: str = Field(
        min_length=8,
        description="The 'why is this here' answer. Narrative, emotional, "
        "thematic, comedic, aesthetic, symbolic or musical.",
    )

    @field_validator("statement")
    @classmethod
    def _not_a_list_of_things(cls, v: str) -> str:
        if v.count(",") >= 3:
            raise ValueError(
                "A reality rule is one altered rule, not an inventory of effects. "
                "Split this into separate rules or narrow the domain."
            )
        return v

    @model_validator(mode="after")
    def _escalation_draws_from_manifestations(self) -> RealityRule:
        unknown = [e for e in self.escalation if e not in self.manifestations]
        if unknown:
            raise ValueError(
                f"escalation entries must appear in manifestations; unknown: {unknown}"
            )
        return self


class Staging(BaseModel):
    """How the camera and blocking treat the anomaly.

    Deadpan is achieved here, not in an adjective. The absence of reaction comes
    from never showing a face legible enough to react.
    """

    key: str
    label: str
    emphasis: Emphasis
    faces_visible: bool
    camera_note: str
    blocking_note: str

    def prompt_fragment(self) -> str:
        parts = [self.camera_note.rstrip(". "), self.blocking_note.rstrip(". ")]
        return ". ".join(p for p in parts if p) + "."


class ShotSpec(BaseModel):
    """Everything needed to render one shot, and to explain it later."""

    shot_id: str
    shot_type: ShotType = ShotType.GENERATED
    duration_s: float = Field(default=6.0, ge=2.0, le=30.0)

    environment: str = Field(min_length=20, description="Specific, not 'a cool city'.")
    anomaly: str = Field(min_length=6)
    rule_id: str
    invariant_shown: str = Field(
        description="Which invariant is visibly holding in this frame."
    )
    staging: Staging

    lens_mm: int = Field(default=35, ge=14, le=200)
    handles_s: float = Field(
        default=1.0,
        ge=0.0,
        description="Extra time generated at each end so the edit can cut to a downbeat.",
    )

    @property
    def render_duration_s(self) -> float:
        return self.duration_s + 2 * self.handles_s

    def prompt(self) -> str:
        """The text handed to the generator.

        Deliberately does not name any director, artist or existing work, and
        does not use the word 'surreal' - both push models toward the dreamlike
        register we are trying to avoid.
        """
        return " ".join(
            [
                f"{self.environment.rstrip('. ')}.",
                f"{self.lens_mm}mm lens.",
                self.staging.prompt_fragment(),
                f"In the frame: {self.anomaly}.",
                f"{self.invariant_shown}.",
                "Naturalistic available light, restrained colour, "
                "no visual effects, no glow, photographic.",
            ]
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(self.prompt().encode()).hexdigest()[:12]


class Take(BaseModel):
    """One generation attempt against one ShotSpec."""

    take_id: str
    shot_id: str
    provider: str
    model: str
    prompt: str
    path: str | None = None
    cost_usd: float = 0.0
    status: Literal["pending", "ok", "failed", "rejected"] = "pending"
    reject_reason: str | None = None
