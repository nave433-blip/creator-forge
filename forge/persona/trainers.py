"""Persona trainers registry.

Realistic AI video of a real person needs a trained persona/LoRA model.
This registry lists the real ways to get one, each entry honest about
what it needs: her data, GPU time or API money, and setup effort.

No entry here trains anything by itself -- each one either generates a
config/command you run yourself, or calls a real paid API with YOUR key.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class TrainerInfo:
    name: str
    kind: str  # "local-gpu" | "paid-api"
    docs_url: str
    setup_steps: list[str]
    cost_notes: str
    gpu_notes: str
    needs: list[str] = field(default_factory=list)
    # Optional callable that generates a config/command. Signature varies
    # per trainer; see each generator's docstring.
    config_generator: Callable[..., Any] | None = None


def kohya_lora_generator(**kwargs: Any):
    """Generate a kohya_sd LoRA TOML (see forge/video/training.py)."""
    from forge.video.training import write_kohya_config
    return write_kohya_config(**kwargs)


def diffusers_lora_command(
    *,
    train_data_dir: str,
    output_dir: str,
    pretrained_model: str,
    resolution: int = 1024,
    max_train_steps: int = 1500,
    learning_rate: float = 1e-4,
    rank: int = 16,
) -> str:
    """Build a HuggingFace diffusers LoRA training command (SDXL).

    You run this yourself with `accelerate` on a CUDA GPU. Honest cost:
    same GPU/time as kohya (~30-90 min on a 4090-class card).
    """
    return (
        "accelerate launch "
        "diffusers/examples/text_to_image/train_text_to_image_lora_sdxl.py "
        f"--pretrained_model_name_or_path={pretrained_model!r} "
        f"--train_data_dir={train_data_dir!r} "
        f"--output_dir={output_dir!r} "
        f"--resolution={resolution} "
        f"--max_train_steps={max_train_steps} "
        f"--learning_rate={learning_rate} "
        f"--rank={rank} "
        "--mixed_precision=bf16 "
        "--checkpointing_steps=250"
    )


def replicate_training_adapter(api_token: str, **kwargs: Any) -> dict[str, Any]:
    """Start a fine-tune training on Replicate (real API call, costs money).

    You must pick the training model (e.g. a LoRA trainer) yourself --
    pass its ``model`` owner/name and ``input`` dict. Needs
    REPLICATE_API_TOKEN or an explicit token.
    """
    import json
    import os
    import urllib.request

    token = api_token or os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise RuntimeError(
            "Replicate training needs an API token: pass api_token or set "
            "REPLICATE_API_TOKEN. Get one at "
            "https://replicate.com/account/api-tokens"
        )
    payload = {"model": kwargs["model"], "input": kwargs.get("input", {}),
               "destination": kwargs.get("destination", "")}
    req = urllib.request.Request(
        "https://api.replicate.com/v1/trainings",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Token {token}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fal_training_adapter(api_key: str, endpoint: str,
                         payload: dict[str, Any]) -> dict[str, Any]:
    """Submit a training job to fal.ai (real API call, costs money).

    fal.ai's training endpoints change; you supply the exact queue
    ``endpoint`` (e.g. "https://queue.fal.run/fal-ai/<trainer-model>")
    from their docs. Needs a FAL_KEY.
    """
    import json
    import os
    import urllib.request

    key = api_key or os.environ.get("FAL_KEY")
    if not key:
        raise RuntimeError(
            "fal.ai training needs an API key: pass api_key or set FAL_KEY. "
            "See https://fal.ai for pricing."
        )
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Key {key}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def comfy_training_checklist(out_md: str | Path) -> Path:
    """Write a checklist for LoRA training inside ComfyUI (local GPU).

    ComfyUI training uses community custom nodes; there is no single
    official trainer, so this generates an honest step-by-step checklist
    instead of pretending a one-click path exists.
    """
    from pathlib import Path as _P
    out = _P(out_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "# LoRA training inside ComfyUI -- checklist\n\n"
        "ComfyUI has no built-in LoRA trainer. Community custom nodes add\n"
        "training workflows; they all need a CUDA GPU and your dataset.\n\n"
        "- [ ] Install ComfyUI and confirm it runs on your GPU\n"
        "- [ ] Install a training custom node (e.g. search ComfyUI-Manager\n"
        "      for 'lora train' / 'kohya' nodes; check the node's own docs)\n"
        "- [ ] Prepare dataset: images + .txt captions "
        "(`forge video prep-dataset`)\n"
        "- [ ] Load YOUR base checkpoint in the training workflow\n"
        "- [ ] Set trigger word, steps, LR per the node's docs\n"
        "- [ ] Queue the workflow and wait (30-90 min on 4090-class GPU)\n"
        "- [ ] Copy the output .safetensors to your inference workflow\n",
        encoding="utf-8",
    )
    return out


TRAINERS: list[TrainerInfo] = [
    TrainerInfo(
        name="kohya_sd LoRA",
        kind="local-gpu",
        docs_url="https://github.com/kohya-ss/sd-scripts",
        setup_steps=[
            "Install sd-scripts + CUDA PyTorch in a venv",
            "Prepare dataset: images + .txt captions (forge video prep-dataset)",
            "Generate config: forge video write-kohya-config --base-model <ckpt>",
            "Run: bash scripts/train_lora.sh training/kohya-lora.toml",
        ],
        cost_notes="Free software; you pay for the GPU (own card or ~$0.50-2/hr rented).",
        gpu_notes="24GB+ VRAM recommended for 1024px SDXL LoRA; 30-90 min.",
        needs=["her consented dataset", "CUDA GPU", "base checkpoint you may fine-tune"],
        config_generator=kohya_lora_generator,
    ),
    TrainerInfo(
        name="diffusers LoRA (HuggingFace)",
        kind="local-gpu",
        docs_url="https://huggingface.co/docs/diffusers/main/en/training/lora",
        setup_steps=[
            "pip install diffusers accelerate transformers",
            "Prepare dataset as an imagefolder with captions",
            "Run the generated accelerate command on a CUDA GPU",
        ],
        cost_notes="Free software; you pay for the GPU (own card or rented).",
        gpu_notes="24GB+ VRAM for SDXL; 30-90 min typical.",
        needs=["her consented dataset", "CUDA GPU", "base checkpoint"],
        config_generator=diffusers_lora_command,
    ),
    TrainerInfo(
        name="Replicate fine-tunes",
        kind="paid-api",
        docs_url="https://replicate.com/docs/fine-tuning",
        setup_steps=[
            "Create a Replicate API token",
            "Upload training data (zip of images) somewhere URL-reachable",
            "Pick a trainer model on Replicate and call it via the adapter",
            "Download the resulting weights version",
        ],
        cost_notes="Pay per training run + per prediction; see replicate.com/pricing.",
        gpu_notes="None locally -- training runs on Replicate's GPUs.",
        needs=["her consented dataset", "REPLICATE_API_TOKEN", "trainer model of your choice"],
        config_generator=replicate_training_adapter,
    ),
    TrainerInfo(
        name="fal.ai training",
        kind="paid-api",
        docs_url="https://fal.ai",
        setup_steps=[
            "Create a fal.ai API key (FAL_KEY)",
            "Pick a LoRA/persona training endpoint from fal.ai docs",
            "Submit the job via the adapter with your data URLs",
            "Download the resulting LoRA file",
        ],
        cost_notes="Pay per job; see fal.ai pricing. Endpoint names change -- check docs.",
        gpu_notes="None locally.",
        needs=["her consented dataset", "FAL_KEY", "training endpoint URL from fal.ai docs"],
        config_generator=fal_training_adapter,
    ),
    TrainerInfo(
        name="ComfyUI training workflows",
        kind="local-gpu",
        docs_url="https://docs.comfy.org",
        setup_steps=[
            "Install ComfyUI + a training custom node via ComfyUI-Manager",
            "Prepare dataset (forge video prep-dataset)",
            "Follow the generated checklist for the node's workflow",
        ],
        cost_notes="Free software; you pay for the GPU.",
        gpu_notes="24GB+ VRAM recommended; time varies by node.",
        needs=["her consented dataset", "CUDA GPU", "training custom node"],
        config_generator=comfy_training_checklist,
    ),
]


def list_trainers(kind: str | None = None) -> list[TrainerInfo]:
    """List trainers, optionally filtered to 'local-gpu' or 'paid-api'."""
    if kind is None:
        return list(TRAINERS)
    return [t for t in TRAINERS if t.kind == kind]


def get_trainer(name: str) -> TrainerInfo:
    for t in TRAINERS:
        if t.name.lower() == name.lower():
            return t
    raise KeyError(f"Unknown trainer {name!r}. "
                   f"Available: {[t.name for t in TRAINERS]}")
