"""Video generation pipeline: consent gate -> catalog select -> adapter.

This is the hard gate: generation is REFUSED unless a valid identity
pack (signed consent) is supplied. The adapter then calls the real
backend you configured (Replicate or local ComfyUI). Nothing is faked.
"""

from __future__ import annotations

from typing import Any

from forge.config import ForgeConfig
from forge.identity.pack import (
    InvalidConsentError,
    load_identity_pack,
    validate_identity_pack,
)
from forge.video.adapters import (
    BaseAdapter,
    NotConfiguredError,
    VideoResult,
    get_adapter,
)


class ConsentGateError(InvalidConsentError):
    """Raised by the pipeline when consent validation fails."""


class SceneRefused(Exception):
    """Raised when a scene is refused by the comfort boundary."""


def generate_scene_video(
    *,
    config: ForgeConfig,
    identity_pack_path: str,
    scene_path: str,
    catalog_items: list[dict[str, Any]] | None = None,
    adapter_name: str | None = None,
    negative_prompt: str = "",
    duration_s: int = 5,
    decision_log: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Resolve a scene against her comfort boundary, then act.

    Returns a dict describing what happened:
    - mode "ai": generation ran; includes the VideoResult outputs.
    - mode "real": no generation; includes matching real catalog items.
    - mode "refused": raises :class:`SceneRefused` with the reason.

    The decision is always logged (stdout + optional log file) so she can
    audit what the AI chose and why.
    """
    from forge.video.scenes import (
        SceneRefusedError,
        log_decision,
        resolve_scene_with_pack,
    )

    decision = resolve_scene_with_pack(scene_path, identity_pack_path,
                                       catalog_items)
    log_target = decision_log or config.get_path(
        "video.scene_log", "./forge-data/scene-decisions.log")
    log_decision(decision, log_target)
    print(f"[scene] {decision.scene}: {decision.mode} -- {decision.reason}")

    if decision.mode == "refused":
        raise SceneRefusedError(decision.reason)
    if decision.mode == "real":
        return {"mode": "real", "scene": decision.scene,
                "reason": decision.reason,
                "items": [i["path"] for i in decision.catalog_items]}
    # AI path goes through the normal consent-gated pipeline.
    from forge.video.scenes import load_scene
    scene = load_scene(scene_path)
    result = generate_video(
        config=config,
        identity_pack_path=identity_pack_path,
        prompt=scene.prompt(),
        negative_prompt=negative_prompt,
        adapter_name=adapter_name,
        duration_s=duration_s,
        catalog_items=catalog_items,
        **kwargs,
    )
    return {"mode": "ai", "scene": decision.scene,
            "reason": decision.reason, "outputs": result.outputs,
            "meta": result.meta}


def generate_video(
    *,
    config: ForgeConfig,
    identity_pack_path: str,
    prompt: str,
    negative_prompt: str = "",
    adapter_name: str | None = None,
    reference_images: list[str] | None = None,
    duration_s: int = 5,
    catalog_items: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> VideoResult:
    """Run the full pipeline.

    Steps:
      1. Load + validate the identity pack (consent). Raises
         :class:`ConsentGateError` on any problem -- generation stops here.
      2. Pick the adapter (config ``video.adapter`` or ``adapter_name``).
      3. Call the real backend via the adapter. Raises
         :class:`NotConfiguredError` if the backend isn't set up.

    ``reference_images`` may be explicit paths; if omitted and
    ``catalog_items`` (image rows) are given, the first image is used.
    """
    try:
        pack = validate_identity_pack(load_identity_pack(identity_pack_path))
    except InvalidConsentError as e:
        raise ConsentGateError(
            f"Video generation refused: {e} "
            "(see docs/CONSENT.md for the consent form)"
        ) from e
    except OSError as e:
        raise ConsentGateError(
            f"Video generation refused: identity pack not found or "
            f"unreadable at {identity_pack_path!r} ({e}). "
            "Create one with `forge identity create`."
        ) from e

    name = adapter_name or config.get_path("video.adapter", "replicate")
    adapter: BaseAdapter = get_adapter(name, config)

    refs = list(reference_images or [])
    if not refs and catalog_items:
        for item in catalog_items:
            if item.get("kind") == "image":
                refs.append(item["path"])
                break

    result = adapter.generate(
        prompt=prompt,
        negative_prompt=negative_prompt,
        reference_images=refs or None,
        duration_s=duration_s,
        **kwargs,
    )
    result.meta["identity"] = pack.get("name")
    result.meta["consent_signer"] = pack["consent"]["signer"]
    return result
