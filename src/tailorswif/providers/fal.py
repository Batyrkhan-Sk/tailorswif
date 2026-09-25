"""fal.ai adapter.

fal is the right first backend: pay-as-you-go with no subscription, it carries
every model in the catalog, and it is what a real pipeline would be built
against rather than an interactive credit surface.

Needs FAL_KEY in the environment. Audio is off on every call - we have a song,
and audio roughly doubles the rate on several of these models.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import httpx

from .base import MAX_RESOLUTION, RESOLUTION_ORDER, ModelSpec

QUEUE_ROOT = "https://queue.fal.run"
POLL_INTERVAL_S = 3.0
DEFAULT_TIMEOUT_S = 900.0


class FalError(RuntimeError):
    pass


def clamp_resolution(family: str, resolution: str) -> str:
    """Lower a request to the highest tier this family actually accepts.

    Seedance tops out at 720p while the default here is 1080p, and the endpoint
    answers an out-of-range value with a 422 rather than rounding down. Clamping
    keeps a run alive instead of failing every shot identically.
    """
    ceiling = MAX_RESOLUTION.get(family)
    if not ceiling or resolution not in RESOLUTION_ORDER:
        return resolution
    if RESOLUTION_ORDER.index(resolution) <= RESOLUTION_ORDER.index(ceiling):
        return resolution
    return ceiling


def build_payload(
    spec: ModelSpec,
    prompt: str,
    duration_s: float,
    start_image: str | None = None,
    resolution: str = "1080p",
    end_image: str | None = None,
) -> dict[str, object]:
    """Per-family request body. These endpoints agree on almost nothing.

    Renders at 1080p by default. An earlier version pinned 720p so resolution
    could not bias a ranking, which was correct for the comparison and wrong for
    everything else - 720p reads as cheap on any modern screen, and that alone
    can sink a shot. Audio is off wherever the field exists: we have a song.
    """
    resolution = clamp_resolution(spec.family, resolution)
    payload: dict[str, object] = {"prompt": prompt, "resolution": resolution}

    if spec.accepts_duration:
        payload["duration"] = int(round(min(duration_s, spec.max_duration_s)))

    if spec.family == "wan":
        # Wan expands prompts by default, rewriting them before generation.
        # That would silently undo the staging language the whole experiment
        # is testing, so it is off.
        payload["enable_prompt_expansion"] = False
        # Bans the dreamlike register, not the craft. An earlier version also
        # banned "dramatic lighting" and "cinematic colour grade", which threw
        # out the lighting along with the slop and produced flat, cheap footage.
        payload["negative_prompt"] = (
            "glowing, glow, lens flare, neon, oversaturated, dreamlike, "
            "ethereal, particles, sparks, magic, slow motion, "
            "teal and orange grade, plastic skin, smooth CGI"
        )
    elif spec.family == "kling":
        payload["generate_audio"] = False
    elif spec.family == "veo":
        # Veo names the field `audio` and exposes no duration - 8s per call.
        payload["audio"] = False
    elif spec.family == "seedance":
        # Seedance generates audio by default, and it is the only model here
        # that does. Twenty independently generated soundtracks do not cut
        # together, and the rate is per token of output either way.
        payload["generate_audio"] = False
        payload["duration"] = str(payload["duration"])  # this one wants a string
        payload["aspect_ratio"] = "16:9"

    if start_image and spec.accepts_start_image:
        key = "start_image_url" if spec.family == "kling" else "image_url"
        payload[key] = start_image

    if end_image and spec.accepts_end_image:
        key = "tail_image_url" if spec.family == "kling" else "end_image_url"
        payload[key] = end_image

    return payload


class FalProvider:
    name = "fal"

    def __init__(self, api_key: str | None = None, timeout_s: float = DEFAULT_TIMEOUT_S):
        self.api_key = api_key or os.environ.get("FAL_KEY")
        if not self.api_key:
            raise FalError(
                "FAL_KEY is not set. Get a key at fal.ai and export it, or run "
                "with --provider dryrun to exercise everything except the render."
            )
        self.timeout_s = timeout_s

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Key {self.api_key}"}

    def upload(self, path: str) -> str:
        """Put a local file in fal storage and return its URL.

        Used to feed a frame lifted out of one clip back in as the start image
        of the next, which is how continuity is actually held across shots.
        """
        import fal_client

        os.environ.setdefault("FAL_KEY", self.api_key or "")
        return str(fal_client.upload_file(path))

    def generate(
        self,
        *,
        spec: ModelSpec,
        prompt: str,
        duration_s: float,
        out_path: str,
        start_image: str | None = None,
        end_image: str | None = None,
        resolution: str = "1080p",
    ) -> float:
        payload = build_payload(
            spec, prompt, duration_s, start_image,
            resolution=resolution, end_image=end_image,
        )

        with httpx.Client(timeout=60.0) as client:
            submit = client.post(
                f"{QUEUE_ROOT}/{spec.model_id}",
                headers=self._headers,
                json=payload,
            )
            if submit.status_code >= 400:
                raise FalError(f"submit failed [{submit.status_code}]: {submit.text}")
            queued = submit.json()
            status_url = queued.get("status_url")
            response_url = queued.get("response_url")
            if not status_url or not response_url:
                raise FalError(f"unexpected submit response: {queued}")

            result = self._await_result(client, status_url, response_url)

        url = _first_video_url(result)
        if not url:
            raise FalError(f"no video url in result: {result}")
        _download(url, out_path)
        return spec.price(duration_s)

    def _await_result(
        self, client: httpx.Client, status_url: str, response_url: str
    ) -> dict:
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            status = client.get(status_url, headers=self._headers)
            if status.status_code >= 400:
                raise FalError(f"status failed [{status.status_code}]: {status.text}")
            state = status.json().get("status")
            if state == "COMPLETED":
                final = client.get(response_url, headers=self._headers)
                if final.status_code >= 400:
                    raise FalError(f"fetch failed [{final.status_code}]: {final.text}")
                return final.json()
            if state in {"FAILED", "CANCELLED"}:
                raise FalError(f"job {state.lower()}: {status.text}")
            time.sleep(POLL_INTERVAL_S)
        raise FalError(f"timed out after {self.timeout_s:.0f}s")


def _first_video_url(result: dict) -> str | None:
    """Pull the video URL out of whichever shape this model returned."""
    video = result.get("video")
    if isinstance(video, dict) and video.get("url"):
        return str(video["url"])
    if isinstance(video, str):
        return video
    videos = result.get("videos")
    if isinstance(videos, list) and videos:
        head = videos[0]
        if isinstance(head, dict) and head.get("url"):
            return str(head["url"])
        if isinstance(head, str):
            return head
    return None


def _download(url: str, out_path: str) -> None:
    dest = Path(out_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, timeout=300.0, follow_redirects=True) as response:
        response.raise_for_status()
        with dest.open("wb") as handle:
            for chunk in response.iter_bytes(chunk_size=1 << 16):
                handle.write(chunk)
