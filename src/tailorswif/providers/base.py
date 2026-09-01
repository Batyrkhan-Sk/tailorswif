"""Provider abstraction and the budget guard.

Two rules the architecture review insists on, enforced here rather than by
convention:

  1. Every request is priced *before* dispatch and checked against a ceiling.
     Video inference has no checkpointing and no salvage value when a render is
     rejected, so the guard has to sit in front of the call.
  2. Nothing renders with native audio. We already have a song, and audio
     roughly doubles the per-second rate on several models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class BudgetExceeded(RuntimeError):
    """Raised before dispatch when a request would break the ceiling."""


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """What a model costs, what it accepts, and how to talk to it.

    Rates are USD per second of generated video, audio off, verified Sep 2026.
    Re-check before committing to a provider - this category reprices monthly.

    `family` selects the payload shape: these endpoints disagree about almost
    every field name, and one of them silently rewrites your prompt unless told
    not to. See `providers/fal.py`.
    """

    key: str
    provider: str
    model_id: str
    usd_per_second: float
    max_duration_s: float
    family: str = "generic"
    accepts_duration: bool = True
    accepts_start_image: bool = False
    accepts_end_image: bool = False
    accepts_image_refs: bool = False

    def price(self, duration_s: float) -> float:
        return round(self.usd_per_second * duration_s, 4)


# Endpoint ids verified against fal model pages, Sep 2026. Getting one of these
# wrong costs a failed run and a confusing afternoon, so they are checked rather
# than guessed. Veo has the best camera language and the weakest conditioning -
# a hero-shot model, not a continuity model - and does not expose duration at
# all, capping at 8s per call.
CATALOG: dict[str, ModelSpec] = {
    "wan-2.7": ModelSpec(
        "wan-2.7", "fal", "fal-ai/wan/v2.7/text-to-video", 0.10, 15,
        family="wan",
        accepts_start_image=True, accepts_end_image=True, accepts_image_refs=True,
    ),
    "kling-3.0": ModelSpec(
        "kling-3.0", "fal", "fal-ai/kling-video/v3/standard/text-to-video", 0.112, 15,
        family="kling",
        accepts_start_image=True, accepts_end_image=True, accepts_image_refs=True,
    ),
    "veo-3.1-fast": ModelSpec(
        "veo-3.1-fast", "fal", "fal-ai/veo3.1/fast", 0.10, 8,
        family="veo", accepts_duration=False, accepts_start_image=True,
    ),
    "veo-3.1": ModelSpec(
        "veo-3.1", "fal", "fal-ai/veo3.1", 0.20, 8,
        family="veo", accepts_duration=False, accepts_start_image=True,
    ),
}


@dataclass
class Budget:
    """A spend ceiling with a running total. Checked before every dispatch."""

    ceiling_usd: float
    spent_usd: float = 0.0
    _reserved: float = field(default=0.0, repr=False)

    @property
    def remaining_usd(self) -> float:
        return self.ceiling_usd - self.spent_usd - self._reserved

    def reserve(self, amount: float) -> None:
        if amount > self.remaining_usd:
            raise BudgetExceeded(
                f"request costs ${amount:.2f} but only ${self.remaining_usd:.2f} "
                f"remains of a ${self.ceiling_usd:.2f} ceiling"
            )
        self._reserved += amount

    def settle(self, reserved: float, actual: float) -> None:
        self._reserved = max(0.0, self._reserved - reserved)
        self.spent_usd += actual

    def release(self, reserved: float) -> None:
        """Give back a reservation for a request that never dispatched."""
        self._reserved = max(0.0, self._reserved - reserved)


@runtime_checkable
class VideoProvider(Protocol):
    """Swap-in point for any generation backend."""

    name: str

    def generate(
        self,
        *,
        spec: ModelSpec,
        prompt: str,
        duration_s: float,
        out_path: str,
        start_image: str | None = None,
    ) -> float:
        """Render to `out_path`. Return actual USD spent."""
        ...
