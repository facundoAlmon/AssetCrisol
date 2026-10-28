# Licencias de terceros

[English](licenses.md) · [README](../README.md)

AssetCrisol (el código) es **GPL-3.0**, pero no incluye pesos de modelos: cada uno se baja aparte y tiene su propia
licencia, y algunas **no permiten uso comercial**. Esta página es una guía para saber qué modelos tocan cada asset,
no asesoramiento legal: **verificá la licencia vigente de cada modelo antes de vender algo hecho con él.** Revisado el
2026-10-27.

## ¿Puedo usar lo que genero en un juego comercial?

Depende de la receta. Lo que decide es **qué modelos generaron el asset**:

| Paso | Comercial | No comercial |
|---|---|---|
| Imagen con referencia, vistas | Qwen Image Edit 2511 + LoRA Lightning | — |
| Imagen sin referencia | Z-Image Turbo (`imagen.motor: "zimage"`, el valor por defecto) | FLUX.2 Dev (`imagen.motor: "flux2"`) |
| Malla | TRELLIS.2, Pixal3D | — |
| Textura de la malla | la del motor (TRELLIS.2 o Pixal3D) | **UltraTex** (FLUX.2 Klein) |
| Articulaciones | DWPose | — |
| Animación | procedural, Kimodo | — |
| Escenarios | `sdxl` (DreamShaper XL Turbo), `zimage` (Z-Image Turbo) | `flux` (FLUX.2 Dev) |

> [!CAUTION]
> **La receta recomendada para humanoides (Pixal3D 4 vistas + UltraTex) es no comercial**, porque UltraTex pinta la
> textura con FLUX.2 Klein base 9B. Para un juego comercial: TRELLIS.2 o Pixal3D sin `malla.ultratex`, y la imagen con
> Qwen o Z-Image. Los sprites, retratos y escenas de Godot heredan la condición de la malla y la textura de las que
> salen.

Blender, Godot y ComfyUI son programas: no le ponen condiciones a lo que hacés con ellos (la GPL de Blender alcanza a
los scripts que importan `bpy`, no a los renders).

## En cada asset

`sprites` e `iso` suman al meta (`<n>_meta.json`, `<n>_iso_meta.json`) un bloque `licencias`: los modelos que
hicieron el asset, la licencia de cada uno y `comercial` (`true` solo si todos lo permiten). Los escenarios lo dejan
en `trabajo/tema/licencias.json` y los vehículos en `trabajo/licencias.json`. Sale de la configuración actual del json
(`imagen.referencia`/`imagen.motor`, `malla.motor`/`vistas`/`ultratex` del candidato elegido, `animacion.metodos`,
`motor` de cada textura): si cambiaste un motor después de generar, rehacé ese paso para que el aviso sea cierto. Con
referencia, la imagen de referencia es tuya o de quien la hizo: sus derechos también cuentan.

## Componentes

| Componente | Para qué | Licencia | Uso comercial |
|---|---|---|---|
| Qwen Image Edit 2511 | imagen con referencia, vistas | Apache-2.0 | sí |
| LoRA Lightning de Qwen Image Edit 2511 (lightx2v) | imagen en 4 pasos | Apache-2.0 | sí |
| Z-Image Turbo | imagen sin referencia, escenarios `zimage` | Apache-2.0 | sí |
| FLUX.2 Dev | imagen con `imagen.motor: "flux2"`, escenarios `flux` | FLUX.2 [dev] Non-Commercial License | **no** |
| TRELLIS.2 (código y pesos) | malla (`trellis2`) | MIT | sí |
| TRELLIS-image-large (un decoder) | malla (`trellis2`) | MIT | sí |
| DINOv3 | codificador de imagen de TRELLIS.2 y Pixal3D | DINOv3 License (Meta, acceso gated) | no lo prohíbe; al distribuir el modelo o derivados pide "Built with DINOv3" y prohíbe usos militares, nucleares, de espionaje y armas |
| Pixal3D | malla (`pixal3d`) | MIT | sí |
| MoGe-2 | campo visual de Pixal3D | MIT | sí |
| BiRefNet | sacar el fondo (Pixal3D, `malla.fondo`) | MIT | sí |
| rembg (U-2-Net) | sacar el fondo (TRELLIS.2) | MIT (rembg), Apache-2.0 (U-2-Net) | sí |
| FLUX.2 Klein base 9B | UltraTex | licencia no comercial de Black Forest Labs (el Klein 4B es Apache-2.0, pero UltraTex usa el 9B) | **no** |
| ComfyUI-UltraTex (nodos) | UltraTex | MIT | sí |
| LoRA y decoder de UltraTex | UltraTex | sin licencia publicada en ModelScope | (no comercial igual, por FLUX.2 Klein) |
| DWPose (comfyui_controlnet_aux) | articulaciones | Apache-2.0 | sí |
| DreamShaper XL Turbo | escenarios `sdxl` | CreativeML Open RAIL++-M | sí, con las restricciones de uso de la licencia |
| IP-Adapter Plus SDXL + CLIP ViT-H | escenarios con referencia | Apache-2.0 (IP-Adapter), MIT (OpenCLIP) | sí |
| Kimodo (código) | clips de movimiento | Apache-2.0 | sí |
| Kimodo-SOMA-RP (pesos) | clips de movimiento | NVIDIA Open Model License | sí |
| Llama 3 8B Instruct + LLM2Vec | codificador de texto de Kimodo | Llama 3 Community License (+ MIT de LLM2Vec) | sí, con sus condiciones (atribución, límite de 700 M usuarios) |
| ComfyUI | servidor de generación | GPL-3.0 | programa: no alcanza a lo generado |
| Blender | rig, animación y render | GPL-3.0 | programa: no alcanza a los renders |
| Godot | motor de destino (opcional) | MIT | sí |
| Preact + htm (en `herramientas/ui/web/vendor/`) | la UI (`crisol ui`) | MIT | sí |
| Bricolage Grotesque (en `herramientas/ui/web/vendor/`) | tipografía de la UI | SIL Open Font License 1.1 | sí |

## Los ejemplos del repo

| Ejemplo | Modelos | Uso comercial |
|---|---|---|
| `personajes/cris` | Z-Image Turbo + Qwen Image Edit → Pixal3D 4 vistas + **UltraTex** | **no** (por UltraTex) |
| `personajes/cris/demo_*.gif`, `preview_iso.gif` | renders de Cris | **no** (ídem) |
| `objetos/crisol`, `yunque`, `caja_herramientas` | Z-Image Turbo → TRELLIS.2 + **UltraTex** | **no** (por UltraTex) |
| `objetos/martillo`, `horno` | Z-Image Turbo → Pixal3D | sí |
| `objetos/camioneta` | Z-Image Turbo + Qwen Image Edit → TRELLIS.2 + **UltraTex** | **no** (por UltraTex) |
| `objetos/caja` | malla del motor anterior (Hunyuan3D-2), pendiente de rehacer con TRELLIS.2 | a revisar |
| `escenarios/bosque` | Z-Image Turbo (piso), DreamShaper XL Turbo (camino, pared, fondo) | sí |
| `escenarios/taller` | Z-Image Turbo | sí |
| `herramientas/3_blender/movimientos/*.npz` | Kimodo-SOMA-RP | sí |

Para usar a Cris en algo comercial habría que rehacer su textura sin UltraTex (`malla.ultratex` fuera, o TRELLIS.2).
