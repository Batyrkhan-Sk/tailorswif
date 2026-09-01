"""The splat-conditioning spike.

One question, and the whole product thesis rests on it:

    Does a generative pass conditioned on a splat render actually respect that
    render's geometry?

If it does, you photograph a real place, place an impossible thing inside it,
and the strangeness lands where you put it with real light and real parallax
around it. If the model ignores the conditioning and paints whatever it likes,
there is no product and everything else is decoration.

The pipeline, following fal's own 3D-to-AI recipe but substituting a splat of a
real place for their untextured Blender blockout:

    plate.mp4  (splat render: geometry, camera, parallax)
        +
    keyframe   (one frame, edited to add the impossible thing)
        ↓
    fal-ai/ltx-2.3-quality/render-to-real   ("repaint surfaces, keep geometry")

The overlay check between steps is not optional. fal's warning is exact: give it
a perspective error and it will animate that error beautifully.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

# The instruction that does the work. Without the first sentence the editor
# recomposes the shot - it makes a *nicer* picture of a table, which is
# precisely the failure, because then the geometry no longer matches the plate.
GEOMETRY_LOCK = (
    "Image 1 is the ONLY source of truth for geometry, camera, perspective and "
    "composition. Do not reframe, do not move the camera, do not change the "
    "layout. Repaint surfaces only, keeping every edge exactly where it is."
)

PHOTOGRAPHIC = (
    "Photographic, shot on 35mm film with fine grain, one dominant light source "
    "with a clear direction and defined shadow falloff, deep shadows that still "
    "hold detail, no glow, no visual effects."
)

# Anchored to the LEGO bulldozer because it gives the model a known real object
# to judge scale against, and it must partially occlude the intervention - which
# is the property that actually proves geometry was respected.
EXCAVATION = (
    "The yellow toy digger has excavated a real hole straight through the wooden "
    "tabletop beneath it. A heap of dark damp earth is piled on the table beside "
    "the hole, spilling onto the woven runner. The torn edge of the placemat "
    "hangs into the hole. Splintered wood around the rim. The digger sits at the "
    "edge of the hole it made, partly covering it."
)


@dataclass(frozen=True, slots=True)
class SpikeResult:
    keyframe_path: Path
    overlay_path: Path
    video_path: Path | None
    cost_usd: float


def _upload(path: Path) -> str:
    import fal_client

    return fal_client.upload_file(str(path))


def _download(url: str, dest: Path) -> None:
    import httpx

    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, timeout=300.0, follow_redirects=True) as r:
        r.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in r.iter_bytes(1 << 16):
                fh.write(chunk)


def make_keyframe(
    frame: Path,
    out: Path,
    *,
    intervention: str = EXCAVATION,
    variants: int = 2,
) -> list[Path]:
    """Edit one plate frame to contain the impossible thing.

    Asks for more than one variant because this step is cheap and the next one
    is not - and because a keyframe with drifted perspective poisons everything
    downstream, so it is worth having a choice.
    """
    import fal_client

    prompt = f"{GEOMETRY_LOCK} {intervention} {PHOTOGRAPHIC}"
    result = fal_client.subscribe(
        "fal-ai/nano-banana-pro/edit",
        arguments={
            "prompt": prompt,
            "image_urls": [_upload(frame)],
            "num_images": variants,
        },
    )
    paths = []
    for i, image in enumerate(result.get("images", [])):
        dest = out if i == 0 else out.with_stem(f"{out.stem}_{i + 1}")
        _download(image["url"], dest)
        paths.append(dest)
    return paths


def overlay(plate_frame: Path, keyframe: Path, out: Path) -> Path:
    """Blend the keyframe over the plate at 50% so drift is visible.

    Anything that has moved shows as a doubled edge. Look at the table edges,
    the chair backs and the runner's stripes - if those ghost, the perspective
    has shifted and the render will animate that error.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(plate_frame), "-i", str(keyframe),
         "-filter_complex",
         "[1:v]scale=rw:rh[k];[0:v][k]blend=all_mode=normal:all_opacity=0.5",
         "-frames:v", "1", str(out)],
        check=True,
    )
    return out


def render_to_real(
    plate: Path,
    keyframe: Path,
    out: Path,
    *,
    width: int = 1280,
    height: int = 720,
    frames: int = 42,
) -> tuple[Path, float]:
    """Repaint the plate's surfaces, keeping its geometry, guided by the keyframe."""
    import fal_client

    cost = 0.0024075 * (width * height * frames) / 1_000_000
    result = fal_client.subscribe(
        "fal-ai/ltx-2.3-quality/render-to-real",
        arguments={
            "video_url": _upload(plate),
            "image_url": _upload(keyframe),
        },
    )
    url = (result.get("video") or {}).get("url")
    if not url:
        raise RuntimeError(f"no video in result: {result}")
    _download(url, out)
    return out, round(cost, 3)
