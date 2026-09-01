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

from .base import ModelSpec

QUEUE_ROOT = "https://queue.fal.run"
POLL_INTERVAL_S = 3.0
DEFAULT_TIMEOUT_S = 900.0


class FalError(RuntimeError):
    pass


def build_payload(
    spec: ModelSpec,
    prompt: str,
    duration_s: float,
    start_image: str | None = None,
) -> dict[str, object]:
    """Per-family request body. These endpoints agree on almost nothing.

    Every take renders at 720p so that resolution differences cannot bias the
    ranking, and with audio off wherever the field exists - we have a song, and
    audio roughly doubles the rate on several models.
    """
    payload: dict[str, object] = {"prompt": prompt, "resolution": "720p"}

    if spec.accepts_duration:
        payload["duration"] = int(round(min(duration_s, spec.max_duration_s)))

    if spec.family == "wan":
        # Wan expands prompts by default, rewriting them before generation.
        # That would silently undo the staging language the whole experiment
        # is testing, so it is off.
        payload["enable_prompt_expansion"] = False
        payload["negative_prompt"] = (
            "glowing, glow, lens flare, neon, saturated colour, dreamlike, "
            "ethereal, particles, sparks, smoke effects, slow motion, "
            "dramatic lighting, cinematic colour grade"
        )
    elif spec.family == "kling":
        payload["generate_audio"] = False
    elif spec.family == "veo":
        # Veo names the field `audio` and exposes no duration - 8s per call.
        payload["audio"] = False

    if start_image and spec.accepts_start_image:
        key = "start_image_url" if spec.family == "kling" else "image_url"
        payload[key] = start_image

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

    def generate(
        self,
        *,
        spec: ModelSpec,
        prompt: str,
        duration_s: float,
        out_path: str,
        start_image: str | None = None,
    ) -> float:
        payload = build_payload(spec, prompt, duration_s, start_image)

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
