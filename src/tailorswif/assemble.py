"""Cut the sequence together.

Two things happen here, and the second matters more than it sounds.

**Trim.** Every shot is rendered with handles, so the cut discards the first and
last half-second of each. Generated clips are least stable at their ends - that
is where morphing and drift show - and trimming them is free quality.

**Grade to match.** Twelve separately generated clips come back with different
colour and contrast, and that inconsistency is the single loudest signal that a
video was assembled rather than shot. A shared grade is the cheapest thing that
makes them read as one place. This is not a finishing flourish: a large share of
what audiences read as continuity in AI work was never generated consistently,
it was graded into consistency afterwards.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# A restrained, cool, slightly desaturated pass. Deliberately not a look - it
# exists to pull twelve clips toward each other, not to add character.
GRADE = (
    "eq=saturation=0.88:contrast=1.04:brightness=-0.012,"
    "colorbalance=rs=-0.03:bs=0.04:rm=-0.02:bm=0.02,"
    "unsharp=5:5:0.4"
)

TARGET_W, TARGET_H, FPS = 1280, 720, 24


class FFmpegMissing(RuntimeError):
    pass


def _require_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise FFmpegMissing("ffmpeg is not installed. Try: brew install ffmpeg")
    return path


def probe_duration(path: Path) -> float | None:
    probe = shutil.which("ffprobe")
    if not probe:
        return None
    result = subprocess.run(
        [probe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def _xfade_chain(
    usable: list[tuple[Path, float]], xfade_s: float
) -> list[str]:
    """Fold the clips together with crossfades.

    Each xfade eats `xfade_s` of overlap, so every offset is computed against
    the running length of what has already been folded, not against the raw
    clip durations.
    """
    steps: list[str] = []
    prev = "v0"
    running = usable[0][1]
    for i in range(1, len(usable)):
        offset = max(0.0, running - xfade_s)
        out = "out" if i == len(usable) - 1 else f"x{i}"
        steps.append(
            f"[{prev}][v{i}]xfade=transition=fade:"
            f"duration={xfade_s:.2f}:offset={offset:.2f}[{out}]"
        )
        running = running + usable[i][1] - xfade_s
        prev = out
    return steps


def build(
    clips: list[tuple[Path, float]],
    out_path: Path,
    *,
    handles_s: float = 0.5,
    grade: bool = True,
    audio: Path | None = None,
    transition: str = "cut",
    xfade_s: float = 0.5,
) -> Path:
    """Trim handles off each clip, normalise, grade, concatenate.

    `clips` is (path, intended_duration) in cut order. Filters run in one graph
    rather than as intermediate files so nothing is re-encoded twice.

    `transition` is "cut" or "dissolve". A threshold transition - a door opening
    onto somewhere it could not open onto - wants a hard cut: the dissolve
    announces the trick and softens exactly the abruptness the joke depends on.
    Dissolve is here to be compared against, not because it is right.
    """
    ffmpeg = _require_ffmpeg()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    usable = [(p, d) for p, d in clips if p.exists() and p.suffix == ".mp4"]
    if not usable:
        raise FileNotFoundError(
            "no rendered .mp4 clips found - run with --provider fal first "
            "(a dry run writes prompt sidecars, not video)"
        )

    inputs: list[str] = []
    chains: list[str] = []
    for i, (path, intended) in enumerate(usable):
        inputs += ["-i", str(path)]
        actual = probe_duration(path)
        # Trim the handles when the render is long enough to spare them;
        # otherwise take what is there rather than producing an empty segment.
        start = handles_s if actual and actual > intended else 0.0
        chain = (
            f"[{i}:v]trim=start={start:.2f}:duration={intended:.2f},"
            f"setpts=PTS-STARTPTS,"
            f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
            f"crop={TARGET_W}:{TARGET_H},fps={FPS},setsar=1"
        )
        if grade:
            chain += f",{GRADE}"
        chains.append(f"{chain}[v{i}]")

    if transition == "cut" or len(usable) == 1:
        concat = "".join(f"[v{i}]" for i in range(len(usable)))
        graph = ";".join(chains) + f";{concat}concat=n={len(usable)}:v=1:a=0[out]"
    else:
        graph = ";".join(chains + _xfade_chain(usable, xfade_s))

    cmd = [ffmpeg, "-y", *inputs]
    if audio and audio.exists():
        cmd += ["-i", str(audio)]
    cmd += ["-filter_complex", graph, "-map", "[out]"]
    if audio and audio.exists():
        cmd += ["-map", f"{len(usable)}:a", "-shortest", "-c:a", "aac", "-b:a", "192k"]
    cmd += [
        "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(out_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-12:])
        raise RuntimeError(f"ffmpeg failed:\n{tail}")
    return out_path
