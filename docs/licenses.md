# Third-party licenses

[Español](licencias.md) · [README](../README.en.md)

AssetCrisol (the code) is **GPL-3.0**, but it ships no model weights: each one is downloaded separately and has its
own license, and some **do not allow commercial use**. This page is a guide to which models touch each asset, not
legal advice: **check each model's current license before selling something made with it.** Reviewed on 2026-10-27.

## Can I use what I generate in a commercial game?

It depends on the recipe. What matters is **which models generated the asset**:

| Step | Commercial | Non-commercial |
|---|---|---|
| Image with a reference, views | Qwen Image Edit 2511 + Lightning LoRA | — |
| Image without a reference | Z-Image Turbo (`imagen.motor: "zimage"`, the default) | FLUX.2 Dev (`imagen.motor: "flux2"`) |
| Mesh | TRELLIS.2, Pixal3D | — |
| Mesh texture | the engine's own (TRELLIS.2 or Pixal3D) | **UltraTex** (FLUX.2 Klein) |
| Joints | DWPose | — |
| Animation | procedural, Kimodo | — |
| Scenery | `sdxl` (DreamShaper XL Turbo), `zimage` (Z-Image Turbo) | `flux` (FLUX.2 Dev) |

> [!CAUTION]
> **The recommended humanoid recipe (Pixal3D 4 views + UltraTex) is non-commercial**, because UltraTex paints the
> texture with FLUX.2 Klein base 9B. For a commercial game: TRELLIS.2 or Pixal3D without `malla.ultratex`, and the
> image with Qwen or Z-Image. Sprites, portraits and Godot scenes inherit the terms of the mesh and texture they come
> from.

Blender, Godot and ComfyUI are programs: they put no conditions on what you make with them (Blender's GPL covers the
scripts that import `bpy`, not the renders).

## In each asset

`sprites` and `iso` add a `licencias` block to the meta (`<n>_meta.json`, `<n>_iso_meta.json`): the models that made
the asset, each one's license and `comercial` (`true` only if all of them allow it). Scenery leaves it in
`trabajo/tema/licencias.json` and vehicles in `trabajo/licencias.json`. It comes from the json's current settings
(`imagen.referencia`/`imagen.motor`, the chosen candidate's `malla.motor`/`vistas`/`ultratex`, `animacion.metodos`,
each texture's `motor`): if you changed an engine after generating, redo that step so the notice is accurate. With a
reference, the reference image belongs to you or whoever made it: its rights count too.

## Components

| Component | Used for | License | Commercial use |
|---|---|---|---|
| Qwen Image Edit 2511 | image with a reference, views | Apache-2.0 | yes |
| Qwen Image Edit 2511 Lightning LoRA (lightx2v) | 4-step image | Apache-2.0 | yes |
| Z-Image Turbo | image without a reference, `zimage` scenery | Apache-2.0 | yes |
| FLUX.2 Dev | image with `imagen.motor: "flux2"`, `flux` scenery | FLUX.2 [dev] Non-Commercial License | **no** |
| TRELLIS.2 (code and weights) | mesh (`trellis2`) | MIT | yes |
| TRELLIS-image-large (one decoder) | mesh (`trellis2`) | MIT | yes |
| DINOv3 | image encoder for TRELLIS.2 and Pixal3D | DINOv3 License (Meta, gated) | not forbidden; distributing the model or derivatives requires "Built with DINOv3" and bans military, nuclear, espionage and weapons uses |
| Pixal3D | mesh (`pixal3d`) | MIT | yes |
| MoGe-2 | Pixal3D's field of view | MIT | yes |
| BiRefNet | background removal (Pixal3D, `malla.fondo`) | MIT | yes |
| rembg (U-2-Net) | background removal (TRELLIS.2) | MIT (rembg), Apache-2.0 (U-2-Net) | yes |
| FLUX.2 Klein base 9B | UltraTex | Black Forest Labs non-commercial license (Klein 4B is Apache-2.0, but UltraTex uses the 9B) | **no** |
| ComfyUI-UltraTex (nodes) | UltraTex | MIT | yes |
| UltraTex LoRA and decoder | UltraTex | no license published on ModelScope | (non-commercial anyway, because of FLUX.2 Klein) |
| DWPose (comfyui_controlnet_aux) | joints | Apache-2.0 | yes |
| DreamShaper XL Turbo | `sdxl` scenery | CreativeML Open RAIL++-M | yes, with the license's use restrictions |
| IP-Adapter Plus SDXL + CLIP ViT-H | scenery with a reference | Apache-2.0 (IP-Adapter), MIT (OpenCLIP) | yes |
| Kimodo (code) | motion clips | Apache-2.0 | yes |
| Kimodo-SOMA-RP (weights) | motion clips | NVIDIA Open Model License | yes |
| Llama 3 8B Instruct + LLM2Vec | Kimodo's text encoder | Llama 3 Community License (+ LLM2Vec's MIT) | yes, with its conditions (attribution, 700 M user cap) |
| ComfyUI | generation server | GPL-3.0 | a program: doesn't reach what it generates |
| Blender | rig, animation and render | GPL-3.0 | a program: doesn't reach the renders |
| Godot | target engine (optional) | MIT | yes |

## The repo's examples

| Example | Models | Commercial use |
|---|---|---|
| `personajes/cris` | Z-Image Turbo + Qwen Image Edit → Pixal3D 4 views + **UltraTex** | **no** (because of UltraTex) |
| `personajes/cris/demo_*.gif`, `preview_iso.gif` | renders of Cris | **no** (same) |
| `objetos/crisol`, `yunque`, `caja_herramientas` | Z-Image Turbo → TRELLIS.2 + **UltraTex** | **no** (because of UltraTex) |
| `objetos/martillo`, `horno` | Z-Image Turbo → Pixal3D | yes |
| `objetos/camioneta` | Z-Image Turbo + Qwen Image Edit → TRELLIS.2 + **UltraTex** | **no** (because of UltraTex) |
| `objetos/caja` | mesh from the previous engine (Hunyuan3D-2), to be redone with TRELLIS.2 | to be checked |
| `escenarios/bosque` | Z-Image Turbo (floor), DreamShaper XL Turbo (path, wall, backdrop) | yes |
| `escenarios/taller` | Z-Image Turbo | yes |
| `herramientas/3_blender/movimientos/*.npz` | Kimodo-SOMA-RP | yes |

To use Cris in something commercial, her texture would have to be redone without UltraTex (drop `malla.ultratex`, or
use TRELLIS.2).
