# AssetCrisol

> **Work in progress**: the code works, but docs, examples and installation are still being tidied up for the first
> public release (v0.1 coming). Configurations may break between versions.
>
> This is a short English overview. The full reference (every step, `personaje.json`, styles, objects, vehicles,
> scenery, the Godot guide and known issues) is the Spanish [README.md](README.md). The code, CLI and config keys
> are in Spanish too. What is done and what is next: [ROADMAP.md](ROADMAP.md) (Spanish).

**From one image to 2D and 3D game assets** (animated characters, props, vehicles and scenery kits) with **local,
open-source AI**: everything runs on your own machine, with no paid APIs or cloud services. *Crisol* is Spanish for
*crucible*: an image goes in, sprites, models and scenes come out.

```
reference.png ─(1 ComfyUI: Qwen-Image-Edit)→ clean front-facing A-pose image
              ─(2 Pixal3D 4 views + UltraTex in ComfyUI, or TRELLIS.2)→ textured model.glb
              ─(3 headless Blender)→ rig + weights + animations → side-view frames + portrait
              ─(4 PIL)→ sprite sheet + meta + preview.gif
              ─(iso)→ animations in 8 isometric directions → SpriteFrames
              ─(5)→ ready-to-use Godot scenes
```

It also makes **portraits** for a selection screen, static **props** (side and isometric views), **vehicles** as
`.glb` files with separate wheels for 3D games, and **scenery kits** (tileable floor/path/wall textures, a painted
backdrop and theme colors).

Code license: **GPL-3.0**. The AI models it uses have their own licenses, some of them **non-commercial**: see
[Third-party licenses](#third-party-licenses).

## Requirements

- **Linux** (tested on Linux Mint 22.3, based on Ubuntu 24.04).
- **NVIDIA GPU with 16 GB of VRAM** (tested on an RTX 4080 Super) and the CUDA toolkit (to build TRELLIS.2's
  extensions). Tested with 64 GB of RAM; 32 GB should be enough.
- Roughly **100-150 GB** of free disk for models, environments and caches (estimate).
- System `python3` with **Pillow**; **Blender 5.1**; a recent **ComfyUI** with `comfy-cli` in its venv;
  **TRELLIS.2** with its own venv (Python 3.10).
- Optional: **Kimodo** (NVIDIA, text-to-motion, runs on CPU) to generate new motion clips; **Godot 4.x** for
  `godot --instalar`.

## Installation

```bash
git clone https://github.com/facundoAlmon/AssetCrisol.git && cd AssetCrisol
cp config.ejemplo.json config.json      # fill in the paths
```

`config.json` (not versioned) holds the paths to ComfyUI, TRELLIS.2, Kimodo, Blender and Godot, the model cache
environment variables (`env_modelos`), the default style, and `datos_dir`: where `personajes/`, `objetos/`,
`escenarios/` and `movimientos/candidatos/` are created (relative to the config file). You can also point the
`ASSETCRISOL_CONFIG` environment variable at a config file stored elsewhere.

Then install ComfyUI (plus the ComfyUI-GGUF, ComfyUI-UltraTex, comfyui_controlnet_aux and ComfyUI_IPAdapter_plus
custom nodes), the models it needs (Qwen Image Edit 2511, FLUX.2 Dev, Pixal3D, FLUX.2 Klein base 9B + the UltraTex
LoRA, DreamShaper XL + IP-Adapter for scenery) and TRELLIS.2 (pin `transformers==4.57.1`; DINOv3 is gated on
Hugging Face). The exact file names and steps are in the Spanish README, section *Instalación*.

## First character

```bash
python3 pipeline.py nuevo bandit --referencia ~/bandit_sketch.png
#   edit <datos_dir>/personajes/bandit/personaje.json -> imagen.descripcion (in English: who it is)
python3 pipeline.py imagen bandit           # candidates -> trabajo/imagen/candidatos.png
#   pick one: personaje.json -> imagen.elegida = <seed>
python3 pipeline.py vistas bandit           # back and side views with Qwen -> look at trabajo/imagen/vistas.png
python3 pipeline.py malla bandit            # Pixal3D + UltraTex (~6 min) -> look at trabajo/malla/ultratex_vistas.png
python3 pipeline.py articulaciones bandit   # joints with DWPose -> check trabajo/guia/guia.png
python3 pipeline.py blender bandit          # rig + animations + frames (~1 min)
python3 pipeline.py sprites bandit          # sprite sheet + preview.gif + portrait
python3 pipeline.py iso bandit              # 8 isometric directions (~25 s)
python3 pipeline.py revisar bandit          # review sheet -> trabajo/revision.png
python3 pipeline.py godot bandit            # Godot scenes in personajes/bandit/godot/
```

Pick the **style before generating the image** (`estilo` in `personaje.json`): it shapes the image prompt, and
changing it later only changes the render. For people use `moderno` (3D cartoon with an outline, recommended) or
`semirealista`; `moderno_juguete` is for hard-plastic toys. If the eyes look off on the model (cross-eyed, heavy
outline), re-run `pipeline.py ultratex <n>` with another `malla.ultratex.seed`.

Each step reads `personaje.json` and writes to `trabajo/`, so any step can be re-run on its own. Run **one GPU job
at a time** (image, views, mesh, UltraTex, joints, textures): two at once slow down dramatically and the mesh step
can run out of VRAM. Always look at the review images before accepting a result.

## Third-party licenses

AssetCrisol does not ship model weights; each one is downloaded separately under its own license. This is guidance,
not legal advice: **check each model's current license before using the output commercially.**

| Component | License |
|---|---|
| TRELLIS.2, Pixal3D, rembg, BiRefNet | MIT |
| DINOv3 | Meta's own license, gated |
| Qwen Image Edit 2511 | Apache-2.0 |
| FLUX.2 Dev, FLUX.2 Klein base 9B (UltraTex) | **non-commercial** |
| UltraTex LoRA/decoder, Qwen Lightning LoRA, MoGe, DWPose weights, DreamShaper XL | to be verified |
| Kimodo code | Apache-2.0 |
| Kimodo weights | **to be verified** |
| Llama 3 (Kimodo's text encoder) | Llama 3 Community License |
| ComfyUI / Blender / Godot | GPL-3.0 / GPL / MIT |

Note: the default humanoid recipe uses UltraTex (FLUX.2 Klein 9B, non-commercial), and generating an image without
a reference uses FLUX.2 Dev (non-commercial).
