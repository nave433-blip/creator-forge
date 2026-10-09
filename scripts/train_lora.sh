#!/usr/bin/env bash
# Train the creator's persona LoRA on a GPU machine.
#
# THIS SCRIPT NEEDS:
#   1. A CUDA GPU (24GB+ VRAM recommended for 1024px SDXL LoRA; cloud GPU
#      rentals like RunPod/Vast.ai work if you have no local GPU).
#   2. kohya_sd (sd-scripts) installed: https://github.com/kohya-ss/sd-scripts
#   3. Your dataset: images + .txt captions, prepared with
#      `forge video prep-dataset` (see docs/VIDEO.md).
#   4. A base checkpoint you have the right to fine-tune.
#
# Honest expectations: a usable likeness LoRA takes ~20-200 good images,
# captioned well, and 30-90 minutes on an A100/4090-class GPU. There is no
# shortcut that skips training -- anyone selling "instant AI you" without
# training is selling a face-swap, not your likeness.
set -euo pipefail

CONFIG="${1:-training/kohya-lora.toml}"
VENV="${KOHYA_VENV:-$HOME/sd-scripts/venv}"

if [ ! -f "$CONFIG" ]; then
  echo "Config not found: $CONFIG"
  echo "Generate one with: forge video write-kohya-config --base-model <path>"
  exit 1
fi
if [ ! -d "$VENV" ]; then
  echo "kohya venv not found at $VENV (set KOHYA_VENV to override)."
  echo "Install sd-scripts first: https://github.com/kohya-ss/sd-scripts"
  exit 1
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
accelerate launch --num_cpu_threads_per_process=4 \
  "$HOME/sd-scripts/sdxl_train_network.py" \
  --config_file="$CONFIG"

echo "Done. LoRA safetensors are in the output_dir from $CONFIG."
echo "Next: load the .safetensors into ComfyUI (forge video generate --adapter comfyui)"
echo "or upload it to your Replicate custom model."
