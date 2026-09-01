"""Dry-run provider: costs nothing, dispatches nothing.

Lets the whole experiment - matrix, ledger, budget guard, ranking UI - be
exercised before an API key exists. Writes a small text sidecar per take so the
ranking tool has something to enumerate.
"""

from __future__ import annotations

from pathlib import Path

from .base import ModelSpec


class DryRunProvider:
    name = "dryrun"

    def generate(
        self,
        *,
        spec: ModelSpec,
        prompt: str,
        duration_s: float,
        out_path: str,
        start_image: str | None = None,
    ) -> float:
        path = Path(out_path).with_suffix(".txt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(
                [
                    f"model:      {spec.key} ({spec.model_id})",
                    f"duration:   {duration_s:.1f}s",
                    f"would cost: ${spec.price(duration_s):.3f}",
                    f"start_image:{start_image or '-'}",
                    "",
                    "prompt:",
                    prompt,
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return 0.0
