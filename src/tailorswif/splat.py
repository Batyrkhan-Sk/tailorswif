"""Strip floaters out of a Gaussian splat.

Every reconstruction is surrounded by junk: huge, faint, badly-placed gaussians
in the region the photographer never actually covered. In a viewer you orbit
around them. In a *render* they sit in front of the camera as white fog, and
they are indistinguishable from exactly the AI artefacts we are trying to avoid.

Lassoing 300,000 points by hand is miserable, so this filters them numerically.
Three cuts, in order of how much they remove:

  distance   - keep what is near the scene's robust centre, using median
               absolute deviation rather than mean and standard deviation,
               because the floaters are precisely the outliers that would
               drag a mean around
  size       - drop the enormous smeared gaussians; real surface detail is
               small, fog is not
  opacity    - drop the nearly-transparent ones that only add haze

Everything is quantile-based, so it adapts to a scene's own scale instead of
carrying magic numbers tuned on one capture.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True, slots=True)
class PlyData:
    header: bytes
    names: list[str]
    array: np.ndarray  # structured, one record per gaussian

    @property
    def count(self) -> int:
        return len(self.array)


def _parse_header(raw: bytes) -> tuple[int, int, list[tuple[str, str]]]:
    end = raw.find(b"end_header\n")
    if end == -1:
        raise ValueError("not a ply file, or header is not newline-terminated")
    body_at = end + len(b"end_header\n")
    text = raw[:end].decode("ascii", errors="replace")

    if "binary_little_endian" not in text:
        raise ValueError("only binary_little_endian ply is supported")

    count = 0
    props: list[tuple[str, str]] = []
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "element" and parts[1] == "vertex":
            count = int(parts[2])
        elif parts[0] == "property":
            if parts[1] == "list":
                raise ValueError("list properties are not supported")
            props.append((parts[1], parts[2]))
    return body_at, count, props


_NP = {
    "float": "<f4", "float32": "<f4", "double": "<f8", "float64": "<f8",
    "uchar": "u1", "uint8": "u1", "char": "i1", "int8": "i1",
    "ushort": "<u2", "uint16": "<u2", "short": "<i2", "int16": "<i2",
    "uint": "<u4", "uint32": "<u4", "int": "<i4", "int32": "<i4",
}


def read_ply(path: str | Path) -> PlyData:
    raw = Path(path).read_bytes()
    body_at, count, props = _parse_header(raw)
    dtype = np.dtype([(name, _NP[kind]) for kind, name in props])
    array = np.frombuffer(raw, dtype=dtype, count=count, offset=body_at)
    return PlyData(raw[:body_at], [n for _, n in props], array)


def write_ply(data: PlyData, keep: np.ndarray, path: str | Path) -> int:
    """Write only the kept gaussians, patching the vertex count in the header."""
    kept = data.array[keep]
    header = data.header.decode("ascii")
    out_lines = []
    for line in header.splitlines(keepends=True):
        if line.startswith("element vertex"):
            out_lines.append(f"element vertex {len(kept)}\n")
        else:
            out_lines.append(line)
    Path(path).write_bytes("".join(out_lines).encode("ascii") + kept.tobytes())
    return len(kept)


def clean(
    data: PlyData,
    *,
    distance_q: float = 0.92,
    distance_slack: float = 1.25,
    size_q: float = 0.98,
    min_opacity: float | None = -2.0,
) -> tuple[np.ndarray, dict[str, int]]:
    """Return a boolean keep-mask and a report of what each cut removed.

    `distance_q` is the fraction of gaussians assumed to be real scene rather
    than floater - lower it if fog survives, raise it if the scene loses edges.
    """
    xyz = np.stack([data.array["x"], data.array["y"], data.array["z"]], axis=1)
    xyz = xyz.astype(np.float64)

    # Robust centre. The median is unmoved by the outliers we are hunting.
    centre = np.median(xyz, axis=0)
    radius = np.linalg.norm(xyz - centre, axis=1)
    cutoff = np.quantile(radius, distance_q) * distance_slack
    near = radius <= cutoff

    keep = near.copy()
    report = {"total": len(data.array), "far": int((~near).sum())}

    # Scale is stored logarithmically; the largest gaussians are the fog.
    scale_cols = [n for n in data.names if n.startswith("scale_")]
    if scale_cols:
        scale = np.stack([data.array[c] for c in scale_cols], axis=1).astype(np.float64)
        biggest = scale.max(axis=1)
        # Judge size against the gaussians we are already keeping, so a scene
        # full of floaters does not set its own threshold.
        huge = biggest > np.quantile(biggest[near], size_q)
        keep &= ~huge
        report["huge"] = int((huge & near).sum())

    # Opacity is a logit; very negative is nearly invisible haze.
    if min_opacity is not None and "opacity" in data.names:
        faint = data.array["opacity"].astype(np.float64) < min_opacity
        before = keep.sum()
        keep &= ~faint
        report["faint"] = int(before - keep.sum())

    report["kept"] = int(keep.sum())
    return keep, report
