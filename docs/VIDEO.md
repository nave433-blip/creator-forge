# Making her AI videos: the honest path

Realistic AI video of a real, specific person is not a filter you turn
on. It requires **training a persona model** (a LoRA fine-tune) on her
own photos/videos, on a GPU. CreatorForge gives you the pipeline and the
adapters; the training itself happens on hardware you control, with data
she consented to (see docs/CONSENT.md -- the pipeline refuses to run
without a valid identity pack).

## The pipeline, step by step

### 1. Collect the dataset (her catalog)

```bash
forge catalog scan /path/to/her/content --tags original
```

Pick 20-200 good shots: clear face, varied angles/expressions/lighting,
minimal heavy filters. Tag the best ones (`forge catalog` + dashboard) --
quality beats quantity.

### 2. Build the training manifest + captions

```bash
forge video prep-dataset --out dataset/manifest.csv --trigger hername
forge video write-kohya-config --base-model /path/to/base.safetensors
```

`prep-dataset` writes `dataset/manifest.csv` (path, caption, split).
Copy the chosen images next to their captions and **hand-edit the
captions** -- good captions ("hername woman, smiling, studio lighting")
train far better than placeholders.

### 3. Train the LoRA (needs a GPU)

```bash
bash scripts/train_lora.sh training/kohya-lora.toml
```

Realistic expectations:
- **Hardware:** 24GB+ VRAM (RTX 4090 / A100-class). No local GPU? Rent
  one by the hour (RunPod, Vast.ai, etc.) -- roughly $0.50-$2/hr.
- **Time:** 30-90 minutes for a first usable LoRA at 1024px.
- **Data:** 20 images can work; 100+ well-captioned images work better.
- **Tooling:** kohya_sd (`sd-scripts`) or HuggingFace `diffusers`
  training scripts. Both are free and open source.

There is no legitimate shortcut. Anyone selling "instant AI you" with
no training step is selling a face-swap, not a likeness model.

### 4. Generate videos

Two adapters, both calling real backends you configure:

**Option A -- local ComfyUI (free after hardware):**
1. Install ComfyUI, load your trained `.safetensors` LoRA in a
   text-to-video / image-to-video workflow.
2. Export the workflow as API JSON, set `video.comfy_workflow` in
   forge.yaml.
3. `forge video generate --adapter comfyui --prompt "..."`

**Option B -- Replicate (pay per second, no GPU needed):**
1. Upload your LoRA as a custom Replicate model (or use a hosted
   persona-video model you have rights to).
2. Set `video.replicate_token` and `video.replicate_model_version`.
3. `forge video generate --adapter replicate --prompt "..."`

If a backend isn't configured, the adapter raises a clear error telling
you exactly what's missing -- it never fakes output.

## Labeling

Many platforms require AI-generated content to be labeled as such.
Check each platform's current synthetic-media policy before posting,
and keep records of what was AI-generated vs. real.
