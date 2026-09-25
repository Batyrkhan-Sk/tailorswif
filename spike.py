"""Run the splat-conditioning spike. Two stages so the cheap one can be checked
before the expensive one runs.

    uv run python spike.py keyframe    # ~$0.30, makes 2 variants + overlays
    uv run python spike.py render      # ~$0.09, uses assets/spike/keyframe.png
"""
import sys
from pathlib import Path

from tailorswif.spike import (
    EXCAVATION, make_keyframe, match_to_plate, overlay, render_to_real,
)

PLATES = Path("assets/plates")
OUT = Path("assets/spike")
FRAME = PLATES / "plate_frame0.png"
PLATE = PLATES / "plate.mp4"


def keyframe() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    paths = make_keyframe(FRAME, OUT / "keyframe.png", intervention=EXCAVATION)
    print(f"\n{len(paths)} variant(s):")
    for p in paths:
        ov = overlay(FRAME, p, OUT / f"overlay_{p.stem}.png")
        print(f"  {p}\n    overlay -> {ov}")
    print("\nLook at the overlays before rendering. Doubled edges on the table,")
    print("the chair backs or the runner stripes mean the perspective drifted.")
    print("Pick the best variant, make sure it is named keyframe.png, then:")
    print("  uv run python spike.py render")


def render() -> None:
    kf = OUT / "keyframe.png"
    if not kf.exists():
        sys.exit(f"missing {kf} - run `uv run python spike.py keyframe` first")
    matched = match_to_plate(kf, FRAME, OUT / "keyframe_matched.png")
    print(f"keyframe matched to plate -> {matched}")
    video, cost = render_to_real(PLATE, matched, OUT / "result.mp4")
    print(f"\n{video}  (~${cost})")
    print("Now the actual test: does the hole stay in the table as the camera moves?")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "keyframe"
    {"keyframe": keyframe, "render": render}.get(cmd, keyframe)()
