"""Video generation adapters.

Honest design: CreatorForge does not ship a trained model and does not
fake generation. Each adapter calls a REAL backend that you configure
with your own key/endpoint:

- :class:`ReplicateAdapter` -- calls replicate.com's HTTP API with your
  ``REPLICATE_API_TOKEN`` (or config ``video.replicate_token``) and the
  model version you choose.
- :class:`ComfyUIAdapter` -- talks to a local ComfyUI server over its
  websocket/prompt HTTP API (default ``http://127.0.0.1:8188``).

If a backend is not configured, the adapter raises
:class:`NotConfiguredError` with setup instructions -- it never returns
fake output.
"""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from typing import Any

from forge.config import ForgeConfig


class NotConfiguredError(Exception):
    """Raised when a video backend has not been configured yet."""


class VideoResult:
    """A completed generation: local paths or remote URLs of outputs."""

    def __init__(self, outputs: list[str], meta: dict[str, Any] | None = None):
        self.outputs = outputs
        self.meta = meta or {}

    def __repr__(self) -> str:  # pragma: no cover
        return f"VideoResult(outputs={self.outputs!r})"


class BaseAdapter:
    name = "base"

    def __init__(self, config: ForgeConfig):
        self.config = config

    def check_configured(self) -> None:
        raise NotImplementedError

    def generate(
        self,
        *,
        prompt: str,
        negative_prompt: str = "",
        reference_images: list[str] | None = None,
        duration_s: int = 5,
        **kwargs: Any,
    ) -> VideoResult:
        raise NotImplementedError


class ReplicateAdapter(BaseAdapter):
    """Generate via a Replicate-hosted video model.

    You pick the model version (e.g. a LoRA/persona-tuned video model you
    trained or rented). Needs ``video.replicate_token`` in forge.yaml or
    the ``REPLICATE_API_TOKEN`` env var.
    """

    name = "replicate"
    API = "https://api.replicate.com/v1/predictions"

    def check_configured(self) -> None:
        token = (self.config.get_path("video.replicate_token")
                 or __import__("os").environ.get("REPLICATE_API_TOKEN"))
        version = self.config.get_path("video.replicate_model_version")
        missing = []
        if not token:
            missing.append("video.replicate_token (or REPLICATE_API_TOKEN env var)")
        if not version:
            missing.append("video.replicate_model_version (the model version to run)")
        if missing:
            raise NotConfiguredError(
                "Replicate backend not configured. Missing: "
                + ", ".join(missing) + ".\n"
                "1. Create a token at https://replicate.com/account/api-tokens\n"
                "2. Put it in forge.yaml under video.replicate_token (or set "
                "REPLICATE_API_TOKEN).\n"
                "3. Set video.replicate_model_version to the version of the "
                "video model you want to use."
            )
        self._token = token
        self._version = version

    def generate(self, *, prompt: str, negative_prompt: str = "",
                 reference_images: list[str] | None = None,
                 duration_s: int = 5, **kwargs: Any) -> VideoResult:
        self.check_configured()
        payload = {
            "version": self._version,
            "input": {
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "duration": duration_s,
                **({"image": reference_images[0]} if reference_images else {}),
                **kwargs,
            },
        }
        req = urllib.request.Request(
            self.API,
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Token {self._token}",
                     "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                pred = json.load(resp)
        except urllib.error.HTTPError as e:  # pragma: no cover
            raise RuntimeError(f"Replicate API error {e.code}: {e.read()[:500]}")
        # Poll until terminal state (honest: this costs real API money).
        get_url = pred["urls"]["get"]
        while True:
            with urllib.request.urlopen(
                urllib.request.Request(
                    get_url, headers={"Authorization": f"Token {self._token}"}),
                timeout=30,
            ) as resp:
                pred = json.load(resp)
            status = pred.get("status")
            if status in ("succeeded", "failed", "canceled"):
                break
            time.sleep(5)
        if status != "succeeded":  # pragma: no cover
            raise RuntimeError(f"Replicate prediction {status}: {pred.get('error')}")
        outputs = pred.get("output")
        if isinstance(outputs, str):
            outputs = [outputs]
        return VideoResult(outputs=list(outputs or []),
                           meta={"prediction_id": pred.get("id")})


class ComfyUIAdapter(BaseAdapter):
    """Generate via a local ComfyUI server (http://127.0.0.1:8188).

    You provide a workflow JSON (``video.comfy_workflow`` path in forge.yaml)
    that loads YOUR trained persona/LoRA checkpoint. ComfyUI does the heavy
    lifting on your GPU; this adapter just queues the prompt and waits.
    """

    name = "comfyui"

    def check_configured(self) -> None:
        import os
        self._base = (self.config.get_path("video.comfy_base_url")
                      or os.environ.get("COMFY_BASE_URL")
                      or "http://127.0.0.1:8188")
        wf_path = self.config.get_path("video.comfy_workflow")
        if not wf_path:
            raise NotConfiguredError(
                "ComfyUI backend not configured. Missing: video.comfy_workflow "
                "(path to a ComfyUI API workflow JSON that loads your trained "
                "persona checkpoint).\n"
                "1. Install ComfyUI locally and confirm it serves at "
                f"{self._base}.\n"
                "2. Build a workflow that loads YOUR trained LoRA/checkpoint "
                "and export it as API-format JSON.\n"
                "3. Set video.comfy_workflow to that JSON path in forge.yaml."
            )
        with open(wf_path, encoding="utf-8") as fh:
            self._workflow = json.load(fh)
        # Fail fast if the server is not reachable.
        try:
            urllib.request.urlopen(self._base + "/system_stats", timeout=5)
        except Exception as e:
            raise NotConfiguredError(
                f"ComfyUI server not reachable at {self._base} ({e}). "
                "Start ComfyUI first, then retry."
            )

    def generate(self, *, prompt: str, negative_prompt: str = "",
                 reference_images: list[str] | None = None,
                 duration_s: int = 5, **kwargs: Any) -> VideoResult:
        self.check_configured()
        import copy
        import uuid
        wf = copy.deepcopy(self._workflow)
        # Best-effort prompt injection: overwrite text-encode node inputs.
        for node in wf.values():
            if isinstance(node, dict):
                inputs = node.get("inputs", {})
                if node.get("class_type") in ("CLIPTextEncode",) and "text" in inputs:
                    inputs["text"] = prompt if not inputs.get("text") else inputs["text"]
        payload = {"prompt": wf, "client_id": str(uuid.uuid4())}
        req = urllib.request.Request(
            self._base + "/prompt",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            queued = json.load(resp)
        prompt_id = queued["prompt_id"]
        # Poll history until done.
        while True:
            with urllib.request.urlopen(
                self._base + f"/history/{prompt_id}", timeout=30) as resp:
                hist = json.load(resp)
            if prompt_id in hist:
                break
            time.sleep(5)
        outputs: list[str] = []
        for node_out in hist[prompt_id].get("outputs", {}).values():
            for item in node_out.get("gifs", []) + node_out.get("videos", []):
                outputs.append(
                    f"{self._base}/view?filename={item['filename']}"
                    f"&subfolder={item.get('subfolder', '')}"
                    f"&type={item.get('type', 'output')}"
                )
        return VideoResult(outputs=outputs, meta={"prompt_id": prompt_id})


def get_adapter(name: str, config: ForgeConfig) -> BaseAdapter:
    adapters = {"replicate": ReplicateAdapter, "comfyui": ComfyUIAdapter}
    if name not in adapters:
        raise ValueError(
            f"Unknown video adapter {name!r}. Choose from: {sorted(adapters)}")
    return adapters[name](config)
