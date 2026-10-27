<div align="center">

# AssetCrisol

**De una imagen a assets de juego 2D y 3D, con IA local y open source.**

Personajes animados · objetos · vehículos · kits de escenario → sprites, `.glb` y escenas de Godot

[![Licencia: GPL-3.0](https://img.shields.io/badge/licencia-GPL--3.0-blue)](LICENSE)
[![Plataforma: Linux](https://img.shields.io/badge/plataforma-Linux-FCC624?logo=linux&logoColor=black)](#requisitos)
[![GPU: NVIDIA 16 GB](https://img.shields.io/badge/GPU-NVIDIA%2016%20GB-76B900?logo=nvidia&logoColor=white)](#requisitos)
[![Godot 4](https://img.shields.io/badge/Godot-4-478CBF?logo=godotengine&logoColor=white)](#guía-de-godot)
[![Blender 5.1](https://img.shields.io/badge/Blender-5.1-F5792A?logo=blender&logoColor=white)](#4-blender)

<img src="ejemplos/personajes/cris/demo_acciones.gif" alt="Cris, la mascota del proyecto, en vista isométrica: reposo, caminar, correr, golpe, patada, salto, rodar y brazos arriba" width="300">

*Cris, la mascota del proyecto: sprites isométricos generados de punta a punta con AssetCrisol.*

[English](README.en.md) · [Roadmap](ROADMAP.md) · [Empezá acá](#empezá-acá) · [Para agentes de IA](#para-agentes-de-ia)

</div>

> [!WARNING]
> **En construcción.** El código funciona, pero la documentación, los ejemplos y la instalación todavía se están
> ordenando para la primera versión pública (v0.1 en camino). Puede haber cambios que rompan configuraciones. Qué
> está hecho y qué falta: [ROADMAP.md](ROADMAP.md).

Todo corre en tu PC: sin APIs pagas ni servicios en la nube. *Crisol* (en inglés, *crucible*) es el recipiente donde
se funde el material para darle forma: acá entra una imagen y salen sprites, modelos y escenas.

> [!CAUTION]
> El código es **GPL-3.0**, pero los modelos de IA tienen sus propias licencias y **algunos no son comerciales**: la
> receta por defecto de los humanoides usa UltraTex (FLUX.2 Klein 9B), y FLUX.2 Dev si lo elegís para la imagen sin
> referencia (por defecto es Z-Image Turbo, Apache-2.0).
> Leé [Licencias de terceros](#licencias-de-terceros) antes de usar lo generado en un juego que vayas a vender.

---

## Qué podés hacer

| | Asset | De una imagen sale... | Pasos clave |
|---|---|---|---|
| 🧍 | **Personaje animado** | rig + 15 animaciones (caminar, correr, saltar, golpe, patada, morir...) como hoja de sprites lateral, hojas **isométricas en 8 direcciones**, retrato y cuerpo de frente para una pantalla de selección, anclas por cuadro para colgarle equipo | `imagen` → `malla` → `blender` → `sprites` → `iso` |
| 📦 | **Objeto** | cajas, mesas, cofres, barriles: vista lateral + vistas isométricas con sombra de contacto, escenas `StaticBody2D` con colisión, o el `.glb` para un juego 3D | `imagen` → `malla` → `blender` → `sprites` |
| 🚗 | **Vehículo** | `.glb` con las 4 ruedas separadas en su nodo (origen en el eje), carrocería con materiales `pintura`/`oscuro` y una tarjeta para un selector | `imagen` → `vistas` → `malla` → `blender` |
| 🌲 | **Kit de escenario** | texturas repetibles de piso, camino y pared (detalle normalizado para teñir con los colores del tema), telón de fondo pintado y `tema.json` con los colores | `texturas` → `tema` |

## Cómo funciona

```mermaid
flowchart LR
    REF["Referencia<br/>boceto, foto, sprite<br/>o solo texto"] --> IMG["1 · Imagen<br/>ComfyUI: Qwen-Image-Edit<br/>o Z-Image / FLUX.2 Dev"]
    IMG -->|"elegís la seed"| VIS["Vistas<br/>espalda y costados<br/>con Qwen"]
    VIS --> MALLA["2 · Malla<br/>Pixal3D 4 vistas + UltraTex<br/>o TRELLIS.2"]
    MALLA --> BL["3 · Blender headless<br/>rig, pesos, animaciones"]
    BL --> SPR["4 · Sprites<br/>hoja, meta, preview.gif,<br/>retrato"]
    BL --> ISO["Iso<br/>8 direcciones<br/>+ anclas"]
    SPR --> REV["Revisar<br/>revision.png"]
    ISO --> REV
    REV --> GD["5 · Godot<br/>.tscn, SpriteFrames"]
    MALLA --> GLB["Objeto o vehículo<br/>.glb para 3D"]
    TEX["Escenario<br/>texturas → tema"] --> GD
```

Los pasos 1 y 2 usan la GPU (minutos); de Blender en adelante son segundos. Cada paso lee el json del asset y escribe
en su carpeta `trabajo/`, así que **cualquier paso se puede repetir por separado**. Las decisiones (qué imagen, qué
malla, qué textura) las toma siempre la persona mirando una hoja de candidatos.

---

## Empezá acá

### Requisitos

| | |
|---|---|
| Sistema | **Linux** (probado en Linux Mint 22.3, base Ubuntu 24.04). Windows y macOS no están probados. |
| GPU | **NVIDIA con 16 GB de VRAM** (probado en una RTX 4080 Super) + toolkit de CUDA |
| RAM | probado con 64 GB; 32 GB debería alcanzar |
| Disco | ~100-150 GB libres para modelos, entornos y cachés |
| Software | `python3` con Pillow, **Blender 5.1**, ComfyUI con `comfy-cli`, TRELLIS.2; opcionales: Kimodo y **Godot 4** |

<details>
<summary><b>Requisitos en detalle</b></summary>

| | |
|---|---|
| GPU | Con menos de 16 GB la malla no entra; TRELLIS.2 pide 24 GB oficialmente y entra en 16 con `low_vram`. El toolkit de CUDA hace falta para compilar las extensiones de TRELLIS.2. |
| RAM | Kimodo usa ~16 GB en CPU. |
| Disco | Estimado: TRELLIS.2 ~24 GB, Pixal3D ~15 GB, UltraTex ~11 GB, Z-Image Turbo ~21 GB, Qwen Image Edit y FLUX.2 Dev (opcional), más el codificador de texto de Kimodo si lo usás. Conviene que las cachés de modelos vayan a un disco con lugar (`env_modelos` en la config). |
| Python | `python3` del sistema con **Pillow** (para `pipeline.py`). Cada herramienta trae su propio entorno. |
| Blender | **5.1** (headless; el pipeline nunca toca un Blender abierto). |
| ComfyUI | reciente (con los nodos nativos de Pixal3D, TRELLIS.2 y BiRefNet) y el CLI `comfy` (`comfy-cli`) en su venv. |
| TRELLIS.2 | repo de Microsoft con su venv (Python 3.10). |
| Kimodo | **opcional**: solo para generar clips de movimiento nuevos (los incluidos se leen sin Kimodo). |
| Godot | **opcional**: 4.x, solo para `godot --instalar` (importación headless). |

</details>

### Instalación en 5 pasos

```bash
# 1. Clonar y configurar
git clone https://github.com/facundoAlmon/AssetCrisol.git && cd AssetCrisol
cp config.ejemplo.json config.json      # y completar las rutas
python3 -c "import PIL"                 # pipeline.py necesita Pillow (apt install python3-pil)
```

2. **ComfyUI** con su venv, `comfy-cli`, 4 nodos extra y los modelos → [ComfyUI](#2-comfyui-imagen-pixal3d-ultratex-dwpose-escenarios)
3. **TRELLIS.2** con su venv (Python 3.10, `transformers==4.57.1`) → [TRELLIS.2](#3-trellis2-motor-alternativo-su-venv-también-se-usa-para-rembg)
4. **Blender 5.1** → [Blender](#4-blender)
5. *(opcional)* **Kimodo** para clips de movimiento nuevos → [Kimodo](#5-kimodo-opcional)

Después: `python3 pipeline.py --help`.

<details>
<summary><b>1. config.json</b></summary>

`config.json` (no se versiona) tiene:

| clave | qué es |
|---|---|
| `datos_dir` | dónde se crean `personajes/`, `objetos/`, `escenarios/` y `movimientos/candidatos/`; relativo al archivo de config. Por defecto `.` (la carpeta del repo, ignorada por git). Conviene apuntarlo a una carpeta propia fuera del repo. |
| `estilo` | estilo por defecto (`estilos/<nombre>.json`; el ejemplo trae `moderno`), ver [Estilos](#estilos) |
| `comfyui_dir`, `comfyui_url` | carpeta de ComfyUI (con `venv/bin/python` y `venv/bin/comfy`) y su URL |
| `trellis2_dir` | carpeta de TRELLIS.2 (con `venv/bin/python`) |
| `kimodo_dir` | carpeta de Kimodo (con `venv/bin/python`); solo para `pipeline.py movimiento` |
| `env_modelos` | variables de entorno para las cachés de modelos (`HF_HOME`, `U2NET_HOME`...) |
| `blender`, `godot` | ejecutables |
| `modelos_imagen` | nombres de archivo de los modelos de imagen dentro de `ComfyUI/models`: Qwen Image Edit (`qwen_*`), Z-Image Turbo (`zimage_unet`, `zimage_clip`, `zimage_vae`; si están, es el motor sin referencia por defecto) y FLUX.2 Dev (`flux_*`). Ver `config.ejemplo.json` |

En vez de `config.json` en el repo se puede usar otro archivo con la variable `ASSETCRISOL_CONFIG=/ruta/config.json`
(útil para tener la config y los datos en una carpeta privada aparte).

</details>

#### 2. ComfyUI (imagen, Pixal3D, UltraTex, DWPose, escenarios)

Instalar [ComfyUI](https://github.com/comfyanonymous/ComfyUI) con un venv en `<comfyui_dir>/venv` y el CLI:
`<comfyui_dir>/venv/bin/pip install comfy-cli`. `pipeline.py` arranca ComfyUI solo si no está corriendo.

Nodos extra (en `custom_nodes/`):
- [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) (FLUX.2 Dev en GGUF; no hace falta si usás solo Z-Image);
- [ComfyUI-UltraTex](https://github.com/visualbruno/ComfyUI-UltraTex) (probado en el commit `8137da5`; además
  `pip install moderngl xatlas` en el venv de ComfyUI). El horneado usa moderngl con GLX: arrancar ComfyUI con un
  `DISPLAY` (sin X habría que pasarle `backend='egl'`);
- [comfyui_controlnet_aux](https://github.com/Fannovel16/comfyui_controlnet_aux) (DWPose, paso `articulaciones`);
- [ComfyUI_IPAdapter_plus](https://github.com/cubiq/ComfyUI_IPAdapter_plus) (escenarios con referencia).

Pixal3D no necesita nodos extra: ComfyUI trae `Pixal3DConditioning`, `Pixal3DMultiViewConditioning` y el
remesh/UV/horneado. El workflow lo arma `generar_malla_pixal3d.py` en Python (la plantilla oficial no valida tal
cual).

<details>
<summary><b>Lista de modelos de ComfyUI</b> (rutas dentro de <code>ComfyUI/models/</code>)</summary>

Los nombres de Qwen, Z-Image Turbo y FLUX.2 Dev se configuran en `modelos_imagen`.

```
# Paso 1: imagen
diffusion_models/qwen_image_edit_2511_int8_convrot.safetensors        Qwen-Image-Edit 2511
loras/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors     LoRA de 4 pasos
text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors, vae/qwen_image_vae.safetensors
diffusion_models/z_image_turbo_bf16.safetensors       Z-Image Turbo (sin referencia, por defecto; repo
                                                      Comfy-Org/Z-Image-Turbo en Hugging Face, split_files/)
text_encoders/qwen_3_4b.safetensors                   ídem
vae/z_image_ae.safetensors                            ídem split_files/vae/ae.safetensors, renombrado
unet/flux2DevFP8GGUF_ggufQ5KM.gguf (+ clip/ y vae/ de la misma versión)   FLUX.2 Dev (sin referencia, opcional:
                                                                         imagen.motor "flux2")

# Paso 2: Pixal3D (repos Comfy-Org/Pixal3D, Comfy-Org/MoGe y Comfy-Org/BiRefNet en Hugging Face)
diffusion_models/pixal3d_int8_convrot.safetensors              1 vista
diffusion_models/pixal3d_multiview_int8_convrot.safetensors    4 vistas
vae/trellis_2_shape_vae_bf16.safetensors, vae/trellis_2_texture_vae_bf16.safetensors
clip_vision/dino_v3_L_naf_fp32.safetensors
geometry_estimation/moge_2_vitl_normal_fp16.safetensors
background_removal/birefnet.safetensors

# UltraTex (re-texturizado)
diffusion_models/flux-2-klein-base-9b-fp8.safetensors    black-forest-labs/FLUX.2-klein-base-9b-fp8 (gated; el
                                                         flux-2-klein-9b destilado NO sirve)
loras/ultratex_flux2.safetensors                         ModelScope Yibo-Zhang/UltraTex: flux2/lora/dit_lora.safetensors
ultratex/ultratex_flux2_decoder.pt                       ídem flux2/decoder.pt
text_encoders/qwen_3_8b_fp8mixed.safetensors, vae/flux2-vae.safetensors

# Escenarios (motor sdxl)
checkpoints/dreamshaperXL_v21TurboDPMSDE.safetensors
ipadapter/ip-adapter-plus_sdxl_vit-h.safetensors
clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors
```

</details>

#### 3. TRELLIS.2 (motor alternativo; su venv también se usa para rembg)

Seguir la instalación de [microsoft/TRELLIS.2](https://github.com/microsoft/TRELLIS.2) con el venv en
`<trellis2_dir>/venv` (Python 3.10). Puntos que importan:

- **`transformers==4.57.1`**: con 5.x falla con `DINOv3ViTModel has no attribute 'layer'`.
- Además: `rembg onnxruntime trimesh` (el fondo lo saca rembg, no el RMBG-2.0 de TRELLIS, que también es gated).
- Las extensiones (nvdiffrast, nvdiffrec, CuMesh, FlexGEMM, o-voxel) se compilan con el `setup.sh` del repo; sin
  conda anda igual con el toolkit de CUDA del sistema y `TORCH_CUDA_ARCH_LIST` de tu GPU.
- Pesos (~24 GB): `microsoft/TRELLIS.2-4B`, un decoder de `microsoft/TRELLIS-image-large` y
  **`facebook/dinov3-vitl16-pretrain-lvd1689m`, que es gated**: pedir acceso en su página de Hugging Face y hacer
  `hf auth login` con el mismo `HF_HOME` que `env_modelos`.

#### 4. Blender

Bajar [Blender 5.1](https://www.blender.org/download/) y poner el ejecutable en `blender`. Se usa siempre
`-b --factory-startup`, sin addons.

#### 5. Kimodo (opcional)

<details>
<summary>Solo para <b>generar clips de movimiento nuevos</b> con <code>pipeline.py movimiento</code></summary>

[Kimodo](https://github.com/nv-tlabs/kimodo) (NVIDIA) genera movimiento humano a partir de texto. Los clips elegidos
ya vienen en `herramientas/3_blender/movimientos/` y Blender los lee sin Kimodo.

```bash
git clone https://github.com/nv-tlabs/kimodo.git && cd kimodo
uv venv -p 3.11 --python-preference only-managed venv   # un Python con headers (compila MotionCorrection)
uv pip install -p venv/bin/python torch --index-url https://download.pytorch.org/whl/cu128
uv pip install -p venv/bin/python -e .
```

El codificador de texto es LLM2Vec sobre Llama-3-8B-Instruct. El repo de meta-llama es gated; una alternativa es un
espejo con los mismos pesos (p. ej. `NousResearch/Meta-Llama-3-8B-Instruct`, misma licencia de Llama 3) con los
`adapter_config.json` de `McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp` y `...-mntp-supervised` apuntados a esa
carpeta. `pipeline.py movimiento` corre **todo en CPU** (~2,5 min, ~16 GB de RAM): no compite por la GPU. Los
avisos `MISSING`/`UNEXPECTED` del LoRA al cargar son normales.

</details>

### Probar con los ejemplos (sin generar nada)

`ejemplos/` trae a **Cris**, la mascota del proyecto (una herrera joven de pelo cobrizo con antiparras), un objeto
(`caja`) y un escenario (`bosque`), cada uno con su json. Cris y la caja traen ya su `trabajo/malla/modelo.glb`, así
que se puede correr todo **de Blender en adelante** sin ComfyUI ni TRELLIS.2 (solo Blender y Pillow):

```bash
cp -r ejemplos/* <datos_dir>/        # personajes/cris, objetos/caja, escenarios/bosque
python3 pipeline.py blender cris     # rig + animaciones + frames (≈1 min)
python3 pipeline.py sprites cris     # hoja + preview.gif + retrato
python3 pipeline.py iso cris         # 8 direcciones isométricas (≈25 s) -> preview_iso.gif
python3 pipeline.py revisar cris     # hoja de control -> trabajo/revision.png
python3 pipeline.py blender caja && python3 pipeline.py sprites caja   # -> objetos/caja/preview.png
python3 pipeline.py tema bosque      # texturas repetibles + colores del tema (trae las texturas elegidas)
```

El bosque trae solo las 4 texturas elegidas; la del piso se generó con FLUX.2 Klein (licencia no comercial): es un
ejemplo para probar, no un asset para un juego comercial.

En `ejemplos/personajes/cris/` también están los gifs de demo, armados con sus sprites iso:
[`demo_acciones.gif`](ejemplos/personajes/cris/demo_acciones.gif) (el de arriba),
[`demo_paseo.gif`](ejemplos/personajes/cris/demo_paseo.gif) (camina por un piso iso) y
[`demo_direcciones.gif`](ejemplos/personajes/cris/demo_direcciones.gif) (las 8 direcciones a la vez).

### Primer personaje en 10 comandos

```bash
python3 pipeline.py nuevo bandido --referencia ~/boceto_bandido.png
#   editar <datos_dir>/personajes/bandido/personaje.json -> estilo e imagen.descripcion (en inglés: quién es)
python3 pipeline.py imagen bandido          # candidatas (≈20 s c/u con referencia) -> trabajo/imagen/candidatos.png
#   elegir: personaje.json -> imagen.elegida = <seed>
python3 pipeline.py vistas bandido          # espalda y costados con Qwen -> trabajo/imagen/vistas.png (mirarlas)
python3 pipeline.py malla bandido           # Pixal3D 4 vistas + UltraTex (≈6 min) -> mirar trabajo/malla/ultratex_vistas.png
python3 pipeline.py articulaciones bandido  # articulaciones con DWPose -> trabajo/guia/guia.png (revisarlas)
python3 pipeline.py blender bandido         # rig + animaciones + frames (≈1 min)
python3 pipeline.py sprites bandido         # hoja + preview.gif + retrato
python3 pipeline.py iso bandido             # 8 direcciones isométricas (≈25 s)
python3 pipeline.py revisar bandido         # hoja de control -> trabajo/revision.png
python3 pipeline.py godot bandido           # escenas de Godot en personajes/bandido/godot/
```

Para colgarle cosas en el juego (espada, casco), sumar `python3 pipeline.py anclas bandido` después de `iso`. Para
pasar un cambio puntual (p. ej. una animación) alcanza con `blender` → `sprites` → `iso`.

> [!IMPORTANT]
> **El prompt del estilo se elige antes de generar la imagen; el render, cuando quieras.** El prompt lo arma el estilo
> con `imagen.descripcion` y define la textura: `moderno` y `moderno_juguete` comparten el mismo prompt, `semirealista`
> (proporciones y materiales reales), `animacion3d`, `medieval` y `futurista` tienen cada uno el suyo. Pasar a un
> estilo con **otro prompt** pide regenerar la imagen; entre estilos con el **mismo prompt** solo cambia el render de
> Blender (luces, rugosidad, oclusión, posproceso) y alcanza con rehacer `blender` → `sprites` → `iso`. Para
> personas, `moderno` (cartoon 3D con contorno, el recomendado) o `semirealista`. `moderno_juguete` es **solo para
> muñecos de plástico duro**: en una persona la ropa se ve lustrada como vinilo (se arregla pasando a `moderno` y
> rehaciendo el render, sin tocar la imagen).

> [!WARNING]
> **Una generación por vez en la GPU.** `imagen`, `vistas`, `malla`, `ultratex`, `articulaciones` y `texturas` usan la
> GPU (ComfyUI o TRELLIS.2). Con dos a la vez cada una tarda muchísimo más y la malla se puede quedar sin VRAM. Antes
> de lanzar uno, mirar que ComfyUI no esté generando (`curl -s 127.0.0.1:8188/queue`: `queue_running` y
> `queue_pending` vacías) y que no haya otra malla en curso (`nvidia-smi`). ComfyUI cargado con la cola vacía no
> molesta: `malla` le pide que libere la VRAM.

> [!TIP]
> **Mirá la cara de cerca** en `ultratex_vistas.png`: los ojos dependen mucho de `malla.ultratex.seed` (pueden salir
> estrábicos o con delineado grueso). Si no convencen, `pipeline.py ultratex <n>` con otra seed rehace solo la
> textura (≈6 min, sin rehacer la forma).

### Qué mirar en cada paso (receta para humanoides)

La plantilla ya trae estos valores; acá está qué mirar y qué tocar si sale mal.

1. **Referencia**: recortar al personaje solo (sin cajas, logos ni texto: Qwen los mete en la imagen), entero y con
   aire alrededor. Fondo liso.
2. **Imagen** (4 seeds; con referencia Qwen Edit, ≈20 s cada una; sin referencia Z-Image Turbo, ≈20 s cada una):
   elegir el prompt del estilo antes (ver arriba). **Sin referencia**, Z-Image da la primera idea rápido pero suele
   agregar piezas sueltas (cartucheras, correas, bolsillos) y ropa menos ajustada: elegir una, copiarla como
   `base_<seed>.png`, ponerla de `referencia` y pasarla por Qwen con un `imagen.prompt` de edición ("Keep this exact
   character unchanged ... Only make these changes: remove ..., make the trousers fitted ..., symmetrical A-pose
   ..."). Para eso el json tiene que tener solo `prompt`: si queda `imagen.descripcion`, el prompt lo arma el estilo y
   `prompt` se ignora (moverla, p. ej., a `_descripcion`). En la `descripcion`, sacar lo que cambie la pose de la referencia ("arms
   down, not on the hips"). Elegir la de **proporciones** correctas (a veces salen cabezonas). **Ojos achinados** por
   la sonrisa: no cambiar de seed, editar la elegida: copiarla como `base_<seed>.png`, ponerla de `referencia` y
   escribir un `prompt` "Keep this exact image unchanged ... Only change the eyes: open the eyes wider ...".
3. **Vistas** (`pipeline.py vistas`): la espalda no debe repetir lo del pecho y `left`/`right` miran a su borde de la
   imagen. Una mala se borra (`trabajo/imagen/vista_<v>.png`) y se rehace.
4. **Malla**: mirar `ultratex_vistas.png` y `ultratex_espalda.png`. Sin `malla.ultratex.espalda`, UltraTex inventa la
   espalda y suele copiar lo del pecho (un logo, un emblema); con `espalda` la de atrás sale de la vista de Qwen.
   Mirar la **cara de cerca** (ver el consejo de arriba).
5. **Articulaciones** (`pipeline.py articulaciones`): revisar `guia.png` (y `pose_frente.png`, lo que vio DWPose).
   Con muñecos y juguetes DWPose suele no detectar a nadie: ahí cargarlas a mano (ver
   [3a](#3a-guía-de-articulaciones-pipelinepy-guia)).
6. **Animación**: los valores por defecto andan; ver [3b](#3b-blender-pipelinepy-blender) si la cara no mira al
   frente o los codos doblan raro.
7. **Revisar** (`pipeline.py revisar`, después de `sprites` + `iso`): `trabajo/revision.png` junta la cabeza de
   costado (idle, caminata, correr), los codos doblados, la caminata iso de frente y de espalda, las poses clave y el
   **revés**: 7 poses donde lo que se ve del interior de la malla sale en magenta (agujeros, normales al revés, el
   interior del pantalón al agacharse). Avisa si alguna pose (sin contar rodar) pasa del 3 % de la figura; la boca
   abierta marca siempre y no es un problema. Es lo último que hay que mirar antes de usar el personaje.
8. **Cambios del rig o las animaciones**: `pipeline.py rehacer a,b,c` (o `todos`) corre `blender` → `sprites` →
   `iso` → `anclas` → `revisar` en cada uno, sigue si uno falla y al final lista las fallas.

---

## Referencia

### Comandos

```bash
python3 pipeline.py <nuevo|imagen|vistas|malla|ultratex|guia|articulaciones|blender|sprites|retrato|iso|anclas|revisar|godot|todo> <n>
python3 pipeline.py nuevo <n> [--referencia img] [--objeto | --vehiculo | --escenario]
python3 pipeline.py comparar <n>                    # rehace trabajo/candidatos.png de malla.candidatos
python3 pipeline.py rehacer <n1,n2,...|todos>       # blender..revisar en lote
python3 pipeline.py metodo <n> [anim=kimodo|procedural ...]
python3 pipeline.py movimiento <anim> --prompt "..." [--duracion s] [--seed n] [--muestras k]
python3 pipeline.py <texturas|tema> <n> [--solo piso,pared]   # escenarios
python3 pipeline.py godot <n> [--instalar <proyecto>]
python3 pipeline.py todo <n> [--instalar <proyecto>]   # malla -> blender -> sprites -> godot (requiere imagen elegida)
```

`<n>` se busca en `personajes/`, `objetos/` y `escenarios/` de `datos_dir`. `python3 pipeline.py --help` describe
cada paso.

<details>
<summary><b>Estructura del repo y de <code>datos_dir</code></b></summary>

```
AssetCrisol/
├── pipeline.py               orquestador (python3 del sistema; necesita Pillow)
├── config.ejemplo.json       modelo de config.json (no versionado)
├── estilos/                  animacion3d.json (base) y los demás (ver Estilos)
├── plantilla/                personaje.json, objeto.json, vehiculo.json, escenario.json: valores por defecto
├── ejemplos/                 Cris, caja y bosque, listos para copiar a datos_dir
└── herramientas/
    ├── 1_imagen/     generar_imagen.py + recetas de ComfyUI (qwen_edit, flux2_t2i); Z-Image en Python
    ├── 2_malla/      generar_malla_pixal3d.py (ComfyUI), generar_malla_trellis.py (venv TRELLIS.2),
    │                 retexturizar_ultratex.py (ComfyUI)
    ├── 3_blender/    blender_main.py (headless), rig_lib.py, anim.py, vehiculo.py, dibujar_guia.py,
    │                 articulaciones_pose.py (DWPose), metodos.py + kimodo_clip.py (clips -> rig),
    │                 generar_movimiento.py (venv Kimodo), movimientos/ (biblioteca.json + clips)
    ├── 4_sprites/    armar_tira.py, armar_iso.py, armar_objeto.py, revisar.py, posproceso.py
    ├── 5_godot/      sprite_personaje.gd, sprite_personaje_iso.gd, objeto_iso.gd, exportar_godot.py, exportar_objeto.py
    └── 6_escenario/  texturas.py, repetible.py, tema.py

<datos_dir>/
├── personajes/<n>/
│   ├── personaje.json        configuración
│   ├── referencia.png        (opcional) boceto, sprite, foto de un muñeco...
│   ├── preview.gif           animaciones laterales en loop
│   ├── preview_iso.gif       (con `iso`) caminata en 8 direcciones + el resto
│   ├── trabajo/              intermedios (se pueden borrar y regenerar)
│   │   ├── imagen/           cand_<seed>.png, candidatos.png, vista_*.png, prompt.txt, comfyui.log
│   │   ├── malla/            sin_fondo.png, modelo.glb, modelo_motor.glb, ultratex_*.png, logs
│   │   ├── guia/             frente.png, costado.png, guia.png, guia.json
│   │   ├── frames/           <animación>/NN.png (vista lateral)
│   │   ├── retrato/          retrato.png, frente.png, retrato.json
│   │   ├── iso/              <animación>/<dirección>/NN.png, anclas.json
│   │   ├── revision.png
│   │   └── <n>.blend         escena con malla + rig + una Action por animación
│   └── godot/personajes/     ← resultado para Godot (ver Guía de Godot)
├── objetos/<n>/              objeto.json, preview.png, trabajo/, godot/objetos/<n>/
├── escenarios/<n>/           escenario.json, preview.png, trabajo/texturas/, trabajo/tema/
└── movimientos/candidatos/   clips candidatos de Kimodo
```

</details>

### 1. Imagen (`pipeline.py imagen`)

Genera una imagen por cada seed de `imagen.seeds`:
- **Con referencia** → Qwen-Image-Edit la redibuja según el prompt y conserva el diseño. Sirve cualquier cosa:
  sprite pixel art, boceto, foto de un muñeco.
- **Sin referencia** (`imagen.referencia: null`) → la genera solo desde el prompt el motor de `imagen.motor`:
  - `"zimage"` (por defecto si la config tiene `modelos_imagen.zimage_unet`): Z-Image Turbo, 8 pasos, ≈20 s por
    seed, Apache-2.0;
  - `"flux2"`: FLUX.2 Dev, ≈3,5 min por seed y llena los 16 GB; licencia no comercial.

  Z-Image es ideal para la primera idea, pero suele sumar piezas sueltas (cartucheras, correas, bolsillos) y ropa
  menos ajustada, que después complican la malla y el rig. Receta para un personaje nuevo sin referencia: elegir una
  candidata, copiarla como `base_<seed>.png`, ponerla de `imagen.referencia` y regenerar con Qwen y un `imagen.prompt`
  de edición ("Keep this exact character unchanged ... Only make these changes: remove ..., make the trousers fitted
  ..., symmetrical A-pose ..."). Ojo: si el json tiene `imagen.descripcion`, el prompt lo arma el estilo e
  `imagen.prompt` se ignora; para la edición dejar solo `prompt` (p. ej., mover la descripción a `_descripcion`).

Mirá `trabajo/imagen/candidatos.png` y poné la seed ganadora en `imagen.elegida`. También se puede poner el nombre
de un archivo propio dentro de la carpeta del personaje (`"elegida": "mi_render.png"`) y saltear este paso.

<details>
<summary><b>Cómo se arma el prompt</b></summary>

El prompt **se arma solo** (`generar_imagen.componer_prompt`) y queda en `trabajo/imagen/prompt.txt`: render del
estilo + `imagen.descripcion` + tema y paleta del estilo + encuadre técnico + extra del estilo. El encuadre es fijo
porque lo necesita el paso 2:
- personajes: **cuerpo entero, de frente, simétrico, pose A relajada**: brazos a ~25° con aire hasta la axila,
  manos que no tocan el cuerpo, piernas un poco separadas (si se tocan, el modelo 3D las funde y el rig no las
  puede separar; muy abiertas, al cerrarlas en las animaciones se deforma el hombro);
- objetos: objeto solo, tres cuartos un poco desde arriba, entero y centrado;
- el `extra` de todos los estilos pide **fondo liso claro** y luz suave (no sacarlo al crear un estilo).

En `descripcion` va solo *quién es* (en inglés): ropa, pelo, colores, accesorios, expresión; aunque estén en la
referencia, describirlos ayuda a que no los cambie. Para escribir el prompt entero a mano, usar `imagen.prompt` en
vez de `descripcion` (el estilo entonces no entra en el prompt, solo en luces y posproceso). Con una foto de
referencia y un estilo de dibujo, pedir "3D ... no outlines, not a 2D drawing": si no, Qwen devuelve una
ilustración plana con contorno, mala para la malla.

</details>

### Vistas (`pipeline.py vistas`)

Con `malla.vistas: true` (Pixal3D de 4 vistas, el defecto de los humanoides) genera con Qwen Edit la espalda y los
costados de la imagen elegida → `trabajo/imagen/vista_{back,left,right}.png` y `vistas.png`, para revisarlas
**antes** de la malla (que las reusa). Qwen puede copiar a la espalda lo del pecho (una luz, un emblema) o dibujar un
costado mirando para el lado equivocado (`left` mira al borde izquierdo de la imagen, `right` al derecho; si sale al
revés, espejarla). Borrar una para rehacerla. En vehículos, `vistas` hace la cola en tres cuartos (ver
[Vehículos](#vehículos)).

### 2. Malla (`pipeline.py malla`)

Antes de empezar le pide a ComfyUI que libere la VRAM (`POST /free`) sin cerrarlo. Hay dos motores y un repintado:

| | motor | tiempo | cuándo |
|---|---|---|---|
| **Pixal3D** | `"motor": "pixal3d"` (defecto de personajes) | ≈2 min con 1 vista, ≈3 min + 1 de vistas con 4 | caras finas, ojos de verdad, estampados nítidos |
| **TRELLIS.2** | `"motor": "trellis2"` | ≈3 min | objetos (a 512), vehículos (a 1024), alternativa general |
| **UltraTex** | `"ultratex": true` o un dict | ≈1-6 min | repinta la malla del motor; la mejor textura para humanoides |

> [!TIP]
> **La seed pesa mucho**: si algo sale mal (una cara que desaparece adentro de un casco de vidrio, colores muy
> oscuros, un objeto acostado), probá 2-3 seeds de malla antes de tocar nada más.

<details>
<summary><b>Pixal3D</b>: cómo funciona y parámetros</summary>

La base de TRELLIS.2 pero **alineada a píxel** (proyecta los rasgos de la imagen al 3D). Corre en ComfyUI
(`generar_malla_pixal3d.py`; el workflow queda en `trabajo/malla/pixal3d_api.json`): BiRefNet saca el fondo
(`sin_fondo.png`), MoGe estima el campo visual, Pixal3D genera forma y color, y ComfyUI hace el remesh, la reducción
a `caras`, el UV y el horneado. Del GLB se deja solo el color base (los mapas de normal/AO/metal harían que Blender
ignore la rugosidad del estilo).

Parámetros: `seed`, `seed_estructura` (opcional, solo la estructura gruesa: para huecos en la malla), `resolucion`
(1024 | 1536; con 512 ComfyUI no corre la malla), `caras`, `textura_px` y **`vistas`** (`true` = modelo de 4 vistas
con las de Qwen). Con 1 vista la espalda se inventa; con 4 la forma es mejor pero el **color es menos fiel** (por eso
se repinta con UltraTex). El remesh arma cáscaras de dos caras: que `blender` saque ~3/4 de las caras como
interior es normal.

</details>

<details>
<summary><b>TRELLIS.2</b>: cómo funciona y parámetros</summary>

Log en `trellis2.log`. rembg saca el fondo, TRELLIS.2 genera forma y color juntos y o-voxel arma la malla, el UV y
hornea la textura (`forma.glb` = sin textura). Se sacan los pedacitos sueltos de menos de 100 caras en personajes (en
objetos solo migas de menos de 10, hasta el 10 % de las caras; la pieza más grande nunca); las piezas separadas que
quedan (ojos, cartucheras) las pega al cuerpo el rig.

Parámetros: `caras`, `seed`, `resolucion` (512 | 1024 | 1536; 1024 probado en 16 GB con personajes) y `textura_px`.
Si se queda sin VRAM se relanza solo con la resolución de abajo, o sin remesh si la malla es muy densa (`AVISO` en
la salida). Los objetos macizos no entran a 1024: por eso los objetos van a 512 por defecto.
- `malla.alfa_min` (0-255): lo que rembg deja semitransparente (la sombra entre las cadenas de una hamaca) TRELLIS
  lo vuelve una tela; con 192-240 esos píxeles pasan a transparentes.
- `malla.fondo`: modelo de rembg (`u2net` por defecto; `birefnet-general` recorta más limpio el follaje).
- `malla.margen` (apagado): recorta un cuadrado con ese margen (1.1) alrededor del objeto antes de llevarlo a 1024
  (sin margen, el objeto toca los bordes). Es otro punto de partida, no una mejora segura: probarlo como otra seed.

</details>

<details>
<summary><b>UltraTex</b>: cómo funciona y opciones</summary>

`"ultratex": true` o un dict en `malla`; o `pipeline.py ultratex <n>` para rehacer solo la textura. Vuelve a pintar
la malla del motor desde cero. `blender limpia` la suelda y le saca el interior (`limpia.glb`), FLUX.2 Klein + la
LoRA de UltraTex pintan 6 vistas guiadas por `sin_fondo.png` (`trabajo/malla/ultratex_vistas.png`: **mirarlas**) y
se hornean a UV nuevas → `modelo.glb`. La malla del motor queda en `modelo_motor.glb` (de ahí parte cada
`ultratex`). Es la mejor textura para humanoides sobre la forma de Pixal3D 4 vistas. Opciones:
- `seed`: cambia detalles (sobre todo la cara); con la misma seed sale idéntico.
- `giro: 45`: segunda pasada con cámaras a 45° (más superficie vista).
- `espalda: true`: dos pasadas; la vista de atrás se reemplaza por `vista_back.png` de Qwen (sin fondo con rembg,
  encajada en la silueta) y la segunda pasada (`denoise_espalda`, 0.6) repinta todo coherente. Sin esto UltraTex
  **inventa la espalda** y suele copiar lo del pecho.
- `costados: true`: lo mismo con `vista_left/right.png` (→ `ultratex_costados.png`). Si una vista mira al lado
  contrario se espeja sola (compara el calce de la silueta). Apagado por defecto: trae los brillos del render de
  Qwen; probarlo por personaje.

Mientras corre `ultratex`, `modelo.glb` es la malla del motor: no sacar conclusiones de una `guia` hecha en ese
momento.

</details>

<details>
<summary><b>Candidatos de malla</b> (<code>malla.candidatos</code> + <code>malla.elegida</code>)</summary>

Como las seeds de la imagen: la elección es del usuario. La principal es el resto de `malla` (su nombre es el motor);
cada candidato pisa claves de `malla`, y `desde: "<otro>"` reusa la malla de ese otro y solo le aplica lo suyo
(típico: `{"desde": "trellis2", "ultratex": {"giro": 45}}`). `malla` genera cada uno en `trabajo/malla_<c>/` (el que
ya tiene `modelo.glb` no se rehace) y deja el elegido en `trabajo/malla`; en personajes y objetos arma
`trabajo/candidatos.png` (`pipeline.py comparar <n>` la rehace): una fila por candidato, vista con la cámara iso
desde cinco ángulos. Para cambiar de elegida, editar `malla.elegida` y correr `malla` de nuevo (copia, no genera).
Los candidatos heredan `caras`: Pixal3D con 5000 sale astillado.

</details>

### 3a. Guía de articulaciones (`pipeline.py guia`)

Renderiza la malla de frente y de costado (ortográfico) con una grilla cada 0.1 unidades y dibuja el esqueleto →
`trabajo/guia/guia.png`. Verde = huesos que deforman, naranja = controles (IK del pie, polo de rodilla, root),
amarillo = cabezas de hueso.

`pipeline.py articulaciones` (humanoides) estima las articulaciones con **DWPose** (en ComfyUI) sobre los renders de
`guia` (ortográficos, escala conocida): hombros, codos, muñecas, caderas, rodillas y tobillos en metros; columna y
cuello se reparten entre cadera, cuello y nariz, y la profundidad sale de la vista de costado. En humanoides de
prueba cayó a menos de 5 cm de las cargadas a mano. Si no detecta a nadie o la pose no pasa la validación
anatómica (orden de arriba a abajo, rodilla y codo cerca de la mitad), avisa y quedan las de antes (en
`modelo._articulaciones_previas`). Pasa con muñecos y juguetes.

<details>
<summary><b>Articulaciones estimadas o a mano</b></summary>

Si `modelo.articulaciones` es `null`, se **estiman** por rebanadas de la malla (anda en cuerpos de proporciones
normales; falla en chibis, cabezones o torsos anchos). **A mano**: copiar el bloque `articulaciones` de
`trabajo/guia/guia.json` a `modelo.articulaciones`, editar mirando la grilla (`"hueso": [[x,y,z cabeza], [x,y,z
cola]]`; lado izquierdo del personaje = +X con sufijo `.S`, se espeja solo; frente = -Y; pies en z=0) y volver a
correr `guia`. Codo ≈ a la altura de la cintura, rodilla en la rótula, tobillo arriba del empeine.

Reglas que importan:
- cada hueso tiene que quedar **dentro** de su parte del cuerpo (si no, el bone heat falla);
- rodillas levemente adelante y codos levemente atrás (define hacia dónde doblan);
- `head` va desde el cuello hasta arriba del pelo o el sombrero: todo lo que esté arriba del cuello sigue a la cabeza.

Modelos asimétricos: además de `<hueso>.S` se puede poner un lado suelto de los brazos (`shoulder.R`, `upper_arm.R`,
`forearm.R`, `hand.R` o `.L`, coordenadas tal cual) que reemplaza a ese lado (un robot con un cañón en un solo brazo:
espejado, el hueso pasaba por el cañón y el brazo de verdad quedaba sin hueso).

</details>

### 3b. Blender (`pipeline.py blender`)

Blender headless (`-b --factory-startup`) arma la escena, importa y limpia la malla, la riggea, la anima y renderiza
los frames laterales y el retrato. Todas las animaciones son **en el lugar** (el juego mueve el cuerpo):

| carpeta | en Godot | frames | qué es |
|---|---|---|---|
| `idle` | `idle` | 1 | pose de reposo |
| `caminar` | `walk` | 8 | ciclo con doble apoyo, vaivén de cadera, braceo opuesto |
| `saltar` | `jump`, `land` | 4 + 1 | despegue, subida, cima, caída y aterrizaje |
| `respirar` | `idle_loop` | 8 | quieto en loop |
| `correr` | `run` | 12 | fase de vuelo, braceo con puños, torso inclinado |
| `rodar` | `roll` | 8 | voltereta hacia adelante |
| `golpe` | `punch` | 7 | uno-dos desde la guardia |
| `patada` | `kick` | 8 | patada frontal |
| `agacharse` | `crouch` | 1 | |
| `defender` | `block` | 1 | antebrazos verticales delante de la cara |
| `herido` | `hurt` | 3 | recibe un golpe, paso atrás |
| `morir` | `die` | 6 | cae de espaldas; el último cuadro queda acostado |
| `lanzar` | `throw` | 6 | lanza algo adelante con la mano de atrás |
| `brazos_arriba` | `arms_up` | 6 | los dos brazos arriba en V (festejo, conjuro) |
| `cargar` | `charge` | 6 | carga energía en loop, agachado |

<details>
<summary><b>Qué hace Blender, paso por paso</b></summary>

1. arma una escena limpia: cámara ortográfica **a nivel**, sol principal + relleno, EEVEE, fondo transparente,
   color *Standard*;
2. importa `modelo.glb`, lo normaliza (altura `modelo.altura`, pies en z=0, centrado) y **suelda los vértices**
   partidos por las costuras UV (sin esto el bone heat falla; el UV no se pierde). Después **saca las capas
   escondidas**: los generadores dejan el cuerpo entero debajo de la ropa y la cara interior de la ropa pegada a él
   (hasta 3/4 de las caras). No se ven, pero al animar atraviesan la capa de afuera (manchas oscuras, "volados",
   "agujeros"). Una cara es escondida si ningún rayo hacia donde mira sale de la malla (`malla.sacar_interior: false`
   lo apaga). Si la malla trae caras de afuera con la normal al revés, esa regla las borra (un pájaro perdía la
   cabeza y el pico): `modelo.normales: true` recalcula las normales por pieza y mira los rayos por los dos lados
   (apagado por defecto: en otros suma manchas). Lo detecta la fila de revés de `revisar`.
   `modelo.simetria` (`"izquierda"` = +X, o `"derecha"`) espeja un lado sobre el otro: solo para poses simétricas sin
   detalles de un lado que haya que conservar;
3. esqueleto (`rig_lib.py`) + pesos automáticos (bone heat) + suavizado **espacial** de pesos (promedio con los
   vértices a menos de `modelo.suavizar_pesos`, 0.03 para 1.85 de alto); aborta si queda más del 1 % sin peso. Las
   **piezas sueltas** (ojos, cartucheras, colas) copian los pesos del vértice más cercano del cuerpo, salvo que eso
   no cuadre con los huesos que tienen cerca (ahí van por distancia a los huesos). **Caras puente**
   (`modelo.cortar_puentes`, activo): se cortan y tapan las caras que unen partes lejanas del esqueleto (los dos
   zapatos, mano-cadera), que si no se estiran como una lámina. Ver [Cuando los pesos fallan](#cuando-los-pesos-fallan);
4. animaciones (`anim.py`, lista `TODAS`) con los parámetros de `animacion`, el personaje mirando a la derecha.
   `rodar` y `morir` se apoyan solas en el piso midiendo la malla deformada en cada pose;
5. **retrato** de frente (cabeza y hombros, y cuerpo entero) + `trabajo/retrato/retrato.json` con la caja del retrato
   en unidades del modelo (la usa `sprites` para recortar la imagen original);
6. guarda `trabajo/<n>.blend` y los PNG en `trabajo/frames/` y `trabajo/retrato/`. Lo que se toque a mano en el
   `.blend` se pierde: todos los modos rearman desde `modelo.glb`.

</details>

<details>
<summary><b>Ajustes del cuerpo</b>: codos, piernas cortas, cabeza, ojos</summary>

**Codos y rodillas**: el Armature usa cuaterniones duales (`modelo.preservar_volumen`, activo): con la mezcla lineal
el codo doblado 110-135° se aplastaba como plastilina. Si un traje liso sigue doblando como goma,
`modelo.afinar_pesos` 2.5. El ángulo del polo del IK de la pierna se calibra solo al armar el rig, y la rodilla se
lleva al plano cadera-tobillo (con la rodilla a un costado, al doblarse se abría hacia afuera).

**Piernas cortas (chibis)**: en personajes con la pierna más corta que 0,9 de la plantilla, la bajada de cadera y la
inclinación de pecho y cabeza de las poses se achican en proporción (si no, el agachado desgarra la ropa).

**`animacion.cabeza_arriba_grados`** inclina la cabeza en todas las poses. **Negativo = levantar la cara.** Con
Pixal3D la cara sale derecha (0, el valor de la plantilla); con TRELLIS.2 suele quedar gacha y anda entre 0 y -15.
Probar 2-3 valores renderizando el idle.

**Ojos agujereados** (`modelo.ojos`): a veces el generador deja cada ojo como un cráter que `sacar_interior` borra y
queda un agujero al interior gris de la cabeza (pintar no sirve). `blender` pone por ojo un disco con un ojo dibujado
y tapa con piel lo que en las cajas `tapar` es agujero. En el modelo normalizado (frente = -y), medido de frente:
```json
"ojos": {"centros": [[-0.046, 1.6795], [0.057, 1.68]], "radio": [0.0155, 0.0075],
         "tapar": [[-0.09, 1.684, -0.02, 1.72], [0.02, 1.684, 0.09, 1.72]]}
```
Opcionales: `bulto`, `iris` (RGB), `iris_radio`, `iris_alto`, `pupila_radio`, `esclerotica`, `tapar_min`.

</details>

#### Cuando los pesos fallan

Diagnóstico: render coloreado por hueso dominante, en reposo y en poses (`throw`, `arms_up`, `kick`), no solo en la
caminata.

<details>
<summary><b>Opciones de pesos</b></summary>

- `modelo.pesos: "distancia"`: pesos por distancia a cada hueso dividida por el grosor del miembro, sin bone heat.
  Para chibis de cuerpo redondo donde el bone heat da basura. En humanoides normales es peor.
  `modelo.pesos_exponente` (6) = qué tan corta es la mezcla.
- `modelo.pesos_rigidos: true`: cada vértice entero en su hueso dominante. Robots de bloques (antebrazo que se dobla
  en C).
- `modelo.pesos_zonas`: `[{"min": [x,y,z], "max": [x,y,z], "hueso": "hips"}]`, cajas (coordenadas de `guia.png`)
  cuyos vértices van enteros a un hueso: piezas rígidas cerca de la mano que el bone heat le da al antebrazo.
- `modelo.piezas_por_distancia: true`: todas las piezas menos la más grande toman pesos por distancia aunque tengan un
  hueso adentro (una cola en la misma pieza que el pantalón).
- `modelo.pesos_estanca` (lado del vóxel, p. ej. 0.008): bone heat sobre una copia estanca por vóxeles.
- `modelo.girar_manos_grados`: gira antebrazo y mano en reposo (+ = palmas hacia el cuerpo) cuando las manos quedan
  giradas hacia afuera al balancear los brazos.
- Chibis con los brazos fundidos al costado del cuerpo no tienen arreglo de pesos: al levantar los brazos se llevan la
  ropa. Regenerar la imagen con "both arms held clearly away from the body, a visible gap between each arm and the
  torso" (con la imagen anterior de referencia para conservar el diseño).

</details>

#### Animaciones: dos métodos (`procedural` y `kimodo`)

- **`procedural`**: las poses de `anim.py`. Exageran a propósito (golpes, saltos), con puños y la apertura de brazos
  medida por personaje.
- **`kimodo`**: un clip de captura de movimiento generado con Kimodo y traducido al rig (`kimodo_clip.py`). Más
  natural en movimientos de cuerpo entero; no tiene puños (mano abierta) ni exageración de dibujo animado. Se toman
  los mismos cuadros que la procedural (no corre índices de la hoja).

El método por defecto de cada animación es el **recomendado** en `herramientas/3_blender/movimientos/biblioteca.json`.
Hoy `caminar` y `morir` son de Kimodo (paso largo, pies que apoyan bien; caída creíble) y el resto procedural (el
directo de boxeo de Kimodo dura ~2 cuadros y casi no se ve).

```bash
python3 pipeline.py metodo bandido                                   # método de cada animación (y el recomendado)
python3 pipeline.py metodo bandido golpe=kimodo caminar=procedural   # lo guarda en animacion.metodos
python3 pipeline.py blender bandido && python3 pipeline.py sprites bandido   # + iso y anclas
```

<details>
<summary><b>Clip nuevo con Kimodo</b></summary>

```bash
python3 pipeline.py movimiento correr --prompt "A person runs forward at a steady jogging pace." --duracion 3
#   -> <datos_dir>/movimientos/candidatos/correr_s1_{0,1,2}.npz + correr_s1.png (esqueletos de costado, una fila
#      por muestra; rojo = izquierda). Otra --seed da otras 3.
#   elegir: copiar el .npz a herramientas/3_blender/movimientos/correr.npz y agregarlo a biblioteca.json
#           (con desde/hasta si sobra el principio o el final)
```
Prompts en inglés y concretos. Animaciones con clip posible: las de `kimodo_clip.CUADROS` (todas menos `idle`,
`saltar`, `agacharse` y `defender`).

</details>

### 4. Sprites (`pipeline.py sprites`)

Junta los frames en una hoja en grilla de **13 columnas** (celdas iguales, eje del personaje centrado, piso en el
mismo renglón), escribe `<n>_meta.json` (con `animaciones`: frames, fps y loop de cada una), `preview.gif` y copia el
retrato y el cuerpo de frente. Aplica el posproceso del estilo (color, nitidez, contorno).

El retrato sale por defecto de `trabajo/malla/sin_fondo.png` (la imagen elegida sin fondo) recortada con la caja de
`retrato.json`: se ve igual que el diseño, sin los defectos de la textura 3D. `retrato.fuente = "modelo"` usa el
render. `pipeline.py retrato <n>` rehace solo el retrato y el frente.

Resolución: `sprites.alto_en_pantalla_px × sprites.superresolucion` píxeles para `modelo.altura`.

### Iso (`pipeline.py iso`)

El mismo rig y las mismas animaciones con cámara **isométrica 2:1** (ortográfica, 30° de elevación) y el personaje
girado de a 45°: 8 direcciones `e, se, s, sw, w, nw, n, ne` (sentido horario desde la derecha). ≈25 s. Después correr
`godot`. Opciones en `personaje.json > isometrico` (todas opcionales): `baldosa_px` (128), `superresolucion` (2),
`elevacion_grados` (30), `animaciones` (por defecto todas), `cabeza_arriba_grados`.

### Anclas (`pipeline.py anclas`)

Mismas animaciones y direcciones que `iso`, **sin renderizar** (≈3 s): por cada cuadro guarda la posición y el giro
de algunos huesos (`hips, chest, neck, head, hand.R/L, foot.R/L`) en el mundo de Blender (origen = pies) y su píxel
en el render iso. Sirve para colgarle al personaje una espada, un casco o zapatillas en el juego sin renderizar una
hoja por combinación. Resultado: `trabajo/iso/anclas.json` con `size`, `ppu`, `origen_px`, `altura`, `largos`,
`cabeza` (`ancho`, `fondo`, `alto`) y `cuadros[<carpeta>][<dir>] = [{hueso: [x, y, z, qw, qx, qy, qz, px, py]}, ...]`.
Correrlo con el mismo `personaje.json` que la hoja iso.

### Revisar (`pipeline.py revisar`)

Ver [Qué mirar en cada paso](#qué-mirar-en-cada-paso-receta-para-humanoides), punto 7.

### 5. Godot (`pipeline.py godot`)

Ver [Guía de Godot](#guía-de-godot).

---

## personaje.json

Las claves más usadas: `estilo`, `imagen.descripcion`, `imagen.elegida`, `malla.motor`, `malla.ultratex`,
`modelo.altura`, `modelo.articulaciones` y `animacion.cabeza_arriba_grados`. La plantilla
(`plantilla/personaje.json`) trae valores que andan para humanoides.

<details>
<summary><b>Todas las claves</b></summary>

| clave | qué es |
|---|---|
| `estilo` | `null` = el de la config; o el nombre de un archivo de `estilos/` |
| `render` | (opcional) pisa claves del bloque `render` del estilo solo para este personaje (metal, rugosidad...) |
| `imagen.referencia` | archivo en la carpeta del personaje, o `null` para generar solo desde el prompt |
| `imagen.descripcion` | quién es (en inglés); el prompt se arma con el estilo |
| `imagen.prompt` | (alternativa) prompt completo escrito a mano, sin el estilo |
| `imagen.seeds` | una candidata por seed |
| `imagen.elegida` | seed elegida (o nombre de un archivo propio) |
| `malla.motor` | `"pixal3d"` (plantilla de personajes) o `"trellis2"` |
| `malla.caras / resolucion / textura_px / seed` | calidad del motor (ver paso 2) |
| `malla.vistas` | (`pixal3d`) `true` = modelo de 4 vistas con espalda y costados de Qwen |
| `malla.seed_estructura` | (`pixal3d`, opcional) seed de la estructura gruesa |
| `malla.ultratex` | `true` o `{"seed", "resolucion", "giro", "espalda", "costados", "denoise_espalda"}` |
| `malla.fondo` | (opcional) modelo de rembg: `u2net` o `birefnet-general` |
| `malla.alfa_min` | (opcional) alfa mínimo de la imagen para TRELLIS.2 |
| `malla.margen` | (opcional) margen del recorte para TRELLIS.2 (1.1) |
| `malla.sacar_interior` | (opcional, `true`) sacar las capas escondidas al importar en Blender |
| `malla.candidatos`, `malla.elegida` | (opcional) candidatos de malla a comparar |
| `modelo.altura` | alto en unidades de Blender (1.85 = escala de la plantilla del rig) |
| `modelo.articulaciones` | `null` = estimadas; o el bloque editado desde `guia.json` |
| `modelo.normales` | (opcional) normales recalculadas por pieza (ver 3b) |
| `modelo.simetria` | (opcional) `"izquierda"` o `"derecha"` |
| `modelo.ojos` | (opcional) discos de ojo y tapado de agujeros (ver 3b) |
| `modelo.suavizar_pesos` | (0.03) radio del suavizado espacial de pesos; 0 = sin suavizar |
| `modelo.preservar_volumen` | (`true`) cuaterniones duales en el Armature |
| `modelo.afinar_pesos` | (opcional) exponente (2.5) que achica la mezcla entre huesos de brazos y piernas |
| `modelo.pesos`, `pesos_exponente`, `pesos_rigidos`, `pesos_zonas`, `piezas_por_distancia`, `pesos_estanca`, `girar_manos_grados`, `cortar_puentes` | ver [Cuando los pesos fallan](#cuando-los-pesos-fallan) |
| `animacion.zancada` | medio paso del pie (unidades del modelo de 1,85; caminar usa 1,3×, correr 2,2×) |
| `animacion.levantar_pie` | altura del pie en el vuelo |
| `animacion.balanceo_brazos_grados` | amplitud del braceo al caminar |
| `animacion.cabeza_arriba_grados` | inclina la cabeza en todas las poses (negativo = levanta la cara) |
| `animacion.cabeza_kimodo_grados` | (opcional) retoque extra solo en los clips de Kimodo (+ = baja la cara); normalmente 0 |
| `animacion.cerrar_piernas` | (opcional) metros que se acerca cada pie al centro al caminar y correr; `null` = automático |
| `animacion.cerrar_brazos_grados` | (opcional) cuánto se cierran los brazos hacia el cuerpo; `null` = se mide el hueco brazo-torso |
| `animacion.metodos` | (opcional) `{"<anim>": "procedural" \| "kimodo"}` (se edita con `pipeline.py metodo`) |
| `sprites.alto_en_pantalla_px` | alto del personaje en el juego; `null` = `modelo.altura × estilo.escala.px_por_unidad` |
| `sprites.superresolucion` | la hoja se renderiza N veces más grande y Godot la reduce |
| `retrato.cabeza_grados` | (-5) inclinación de la cabeza en el retrato |
| `retrato.hombros` | (0.55) cuánto se ve debajo del cuello, relativo al alto de la cabeza |
| `retrato.ancho_px` | (512) ancho del retrato (alto = 1.25 × ancho) |
| `retrato.fuente` | (`"imagen"`) recorte de `sin_fondo.png`; `"modelo"` = render |
| `isometrico.*` | (opcional) ver [Iso](#iso-pipelinepy-iso) |

</details>

---

## Estilos

Para que todo lo que se genera para un juego combine, las pautas visuales viven en un **estilo** compartido
(`estilos/<nombre>.json`). `config.json > estilo` elige el de por defecto y cada personaje u objeto puede pisarlo con
`"estilo": "<nombre>"`. Un estilo parcial se completa con `animacion3d.json` (la base): alcanza con escribir lo que
cambia.

| estilo | para qué |
|---|---|
| `animacion3d` | la base: animación 3D estilizada |
| `moderno` | cartoon contemporáneo con contorno oscuro de 2 px; **el recomendado para personas** |
| `semirealista` | render de `moderno` con prompt de proporciones y materiales reales |
| `moderno_juguete` | `moderno` de plástico duro, mismo prompt (oclusión, más contraste y nitidez): **solo para muñecos y juguetes** |
| `medieval` | fantasía pintada a mano, luz cálida |
| `futurista` | sci-fi, luz fría, acentos neón |

Qué pesa más: el **prompt** define cómo se ve el modelo 3D (la textura sale de esa imagen); luces y posproceso
emparejan lo que queda. `moderno` y `moderno_juguete` tienen **exactamente el mismo prompt** (solo cambian rugosidad,
oclusión, contraste y nitidez del render): pasar de uno a otro no cambia la imagen, alcanza con rehacer `blender` →
`sprites` → `iso`. `semirealista` comparte el render de `moderno` pero cambia el prompt. En general, cambiar el estilo
de un personaje ya hecho sin regenerar la imagen solo cambia el render (`blender` + `sprites` + `iso`). Para un juego nuevo: copiar un estilo, ajustarlo, ponerlo en la config y generar
un personaje y un objeto de prueba para ver que combinen antes de producir el resto.

**Plastilina**: con luz suave, material mate y sin oclusión, un muñeco se ve de plastilina. `moderno_juguete` +
`malla.caras: 200000` + `malla.textura_px: 4096` lo pasan a plástico duro.

<details>
<summary><b>Secciones de un estilo</b></summary>

| sección | qué controla | dónde actúa |
|---|---|---|
| `prompt.render_personaje` / `render_objeto` | la técnica: "stylized 3D animated film CGI", "hand-painted", "low poly"... | paso 1 |
| `prompt.tema` | la época o el mundo y sus materiales, y qué **no** debe aparecer | paso 1 |
| `prompt.paleta` | los colores dominantes | paso 1 |
| `prompt.extra` | luz y fondo de la imagen (mantener el fondo liso claro) | paso 1 |
| `render.luz_principal` / `luz_relleno` | `energia`, `elevacion_grados`, `azimut_grados`, `color` | Blender |
| `render.ambiente`, `render.rugosidad` | color del ambiente, brillo de los materiales | Blender |
| `render.metal`, `render.entorno` | (opcionales) Metallic y ambiente en degradé `[[altura 0-1, gris], ...]`: el metal refleja el entorno, y una franja clara en el horizonte hace los brillos | Blender |
| `render.metal_gris`, `render.rugosidad_metal` | (opcionales) `[sat_metal, sat_no_metal]`: metal solo en lo gris/blanco de la textura (armadura metálica sobre piel) | Blender |
| `render.oscuro_brillante` | (opcional) `{valor, saturacion, rugosidad}`: lo oscuro y sin color con otra rugosidad (cuero, plástico negro) | Blender |
| `render.oclusion` | (opcional) `{distancia, fuerza}`: oscurece ranuras y uniones (nodo Ambient Occlusion sobre el color base) | Blender |
| `posproceso` | `saturacion`, `contraste`, `brillo`, `nitidez` (opcional), `tinte` + `tinte_fuerza`, `contorno_px` + `contorno_color` | sprites |
| `escala.px_por_unidad`, `escala.baldosa_px` | mismo tamaño en pantalla para todos los assets | Blender, sprites |

</details>

---

## Objetos

Cajas, mesas, cofres, barriles... Mismos pasos 1 y 2; cambia lo que hace Blender (sin esqueleto) y lo que se exporta.

```bash
python3 pipeline.py nuevo barril --objeto   # [--referencia img] -> objetos/barril/objeto.json
python3 pipeline.py imagen barril           # elegir seed -> objeto.json > imagen.elegida
python3 pipeline.py malla barril            # candidatos -> trabajo/candidatos.png; elegir malla.elegida y repetir
python3 pipeline.py blender barril && python3 pipeline.py sprites barril && python3 pipeline.py godot barril
```

<details>
<summary><b>Detalle de objetos</b></summary>

- **Prompt**: objeto solo, **tres cuartos un poco desde arriba** (el modelo 3D saca más forma que de frente), entero,
  centrado, fondo liso claro.
- `modelo.altura`: alto real en unidades (el personaje de referencia mide 1.85; una caja ≈0.7). `modelo.giro_grados`
  gira la malla sobre Z si sale girada.
- **Candidatos** (plantilla): TRELLIS.2 a 512 (la principal), `ultratex` (la misma repintada, ~1 min) y `pixal3d`
  (una vista a 1536, ~3-4 min). Según el objeto gana uno u otro; sacar los que no se quieran para ahorrar GPU.
- **Pixal3D de una vista** deja el objeto en el marco de la cámara (inclinado y girado): `malla` lo endereza en el
  GLB mismo (apoya la base, huella paralela a los ejes, frente = -Y, origen en el centro de la base). El de la cámara
  queda en `pixal3d_camara.glb`; `modelo.alinear: false` lo apaga. TRELLIS.2 los entrega derechos.
- `blender` renderiza `trabajo/render/lateral.png` (misma escala que los personajes) e `iso_<k>.png`
  (`isometrico.direcciones`, 4 por defecto, de a 90° + 45° para que las caras queden paralelas a las baldosas). Con
  `isometrico.sombra` (por defecto sí) las vistas iso llevan sombra de contacto horneada (Cycles + *shadow catcher*;
  un objeto quieto no salta, así que acá sirve).
- `sprites` → `godot/objetos/<n>/`: `<n>_lateral.png`, `<n>_iso.png` (una celda por dirección), `<n>_meta.json`, y
  `preview.png` con la huella dibujada.
- `godot` → `<n>_lateral.tscn` (`StaticBody2D` + `Sprite2D` + colisión rectangular; origen = centro de la base) y
  `<n>_iso.tscn` (`StaticBody2D` con `objeto_iso.gd`: `direccion` cambia la celda y la huella como
  `CollisionPolygon2D`, también en el editor). `colision: false` las omite.
- Para un juego 3D, `trabajo/malla/modelo.glb` se puede usar directo.

**Vegetación**: las hojitas sueltas dan cáscaras con agujeros (a 512 cada hoja es menos de un vóxel). Pedir masas
lisas: "big smooth puffy rounded green foliage clumps, no individual leaves, solid silhouette, toy-like", negativo
"many leaves, moss, fuzzy texture", `malla.fondo: "birefnet-general"`, TRELLIS.2 a 512. Pixal3D no entra en 16 GB con
follaje. Aun así, la malla reducida para un juego queda facetada: para árboles de fondo suele andar mejor un sprite
dibujado a partir de la imagen elegida.

</details>

---

## Vehículos

Un objeto con un bloque `vehiculo` en su `objeto.json`: autos para un juego 3D que usa el `.glb` (sin sprites).

```bash
python3 pipeline.py nuevo <n> --vehiculo   # [--referencia foto] objeto + plantilla/vehiculo.json
python3 pipeline.py imagen <n>     # tres cuartos de frente, como cualquier objeto; elegir seed
python3 pipeline.py vistas <n>     # la cola en tres cuartos desde arriba con Qwen -> trabajo/imagen/vista_atras.png
python3 pipeline.py malla <n>      # los candidatos (~10 min): trabajo/malla_<candidato>/
python3 pipeline.py blender <n>    # -> trabajo/revision.png (una fila por candidato) + vehiculo.glb del elegido
# elegir malla.elegida mirando revision.png y volver a correr blender (segundos)
```

**Salida** `trabajo/vehiculo.glb` (y `vehiculo_<candidato>.glb`): nodos `carroceria` (materiales `pintura`, `oscuro`,
`pasarrueda`), `rueda_di`, `rueda_dd`, `rueda_ti`, `rueda_td` (d/t = delantera/trasera, i/d = izquierda/derecha), cada
rueda con el origen en su eje; trompa en +Z del glTF.

<details>
<summary><b>Detalle de vehículos</b></summary>

- **Por qué de atrás** (`malla.vista: "atras"`): en una carrera los autos se ven casi siempre desde atrás y arriba, y
  el modelo 3D inventa lo que la imagen no muestra. Desde la cola, lo inventado es la trompa, que casi no se ve.
  `seed_vistas` cambia la imagen de Qwen (borrar `vista_atras.png` para rehacerla).
- **Candidatos**: TRELLIS.2 a 1024 (la principal, la más pareja; a veces erra el color), `pixal3d` (una vista a 1536:
  copia mejor colores y dibujos, abolla alerones) y `ultratex` (la de TRELLIS.2 repintada: arregla colores errados,
  ondula un poco las chapas). TRELLIS.2 a 1536 simplifica la cruda a 4 M de caras y hace el remesh a 1280
  (`TRELLIS_RES_REMESH`): limpio, pero no mejor que 1024. Pixal3D con dos vistas en tres cuartos da fantasmas
  (necesita cámaras consistentes): descartado.
- **`blender`** (modo `vehiculo`, `vehiculo.py`): normales consistentes y limpieza de capas de los dos lados; Pixal3D
  se endereza y se nivela apoyando las cuatro ruedas; escala a `largo_m`; `simetria` (`izquierda` = +X, o `derecha`)
  espeja un costado (malla y UV); detecta las 4 ruedas con rayos desde abajo (`radio_m` y `ancho_rueda_m` las fijan
  a mano). `ruedas`:
  - `"originales"` (por defecto): las caras dentro del cilindro de cada rueda pasan a un objeto propio con el origen
    en el eje, con un disco oscuro adentro (gira con ella) y el pasarrueda cerrado (si no, se ve a través del auto);
  - `"armadas"`: borra la rueda y pone un cilindro con la llanta fotografiada (suele salir más borrosa);
  - `false`: la malla entera.

  `materiales` (por defecto sí) separa la carrocería en `pintura` y `oscuro` (vidrios, tomas, bajos). Todo se
  exporta con doble cara (quedan cavidades abiertas).
- **Tarjeta** `trabajo/tarjeta.png`: el auto en tres cuartos de frente desde arriba, fondo transparente, 512 px de
  ancho (para un selector).
- **Revisión** `trabajo/revision.png`: vista de juego, tres cuartos, costado y arriba; una fila por candidato. Para
  buscar agujeros: render Workbench con `show_backface_culling` y fondo verde (con magenta el violeta no se distingue).

</details>

---

## Escenarios

El recorrido de un nivel lo arma el juego (desde su mapa, con su colisión), así que no se genera una malla del
escenario entero: un generador de imagen a 3D es para un objeto. Lo que se genera es el **kit** del mundo: texturas
repetibles de piso, camino y pared que el juego multiplica por los colores del tema, y un telón de fondo pintado.
Los objetos grandes (casas, árboles) siguen siendo `objetos/`.

```bash
python3 pipeline.py nuevo bosque --escenario    # [--referencia img] -> escenarios/bosque/escenario.json
python3 pipeline.py texturas bosque             # 4 candidatas por textura (~5 s c/u) -> trabajo/texturas/candidatos.png
#   elegir: escenario.json > texturas.<clave>.elegida   (--solo piso,pared rehace solo esas)
python3 pipeline.py tema bosque                 # -> trabajo/tema/{piso,camino,pared}.png + tema.json, preview.png
```

<details>
<summary><b>Detalle de escenarios</b></summary>

- **Prompt**: `texturas.<clave>.descripcion` (en inglés) + "seamless tileable top-down/front view texture" +
  `render_textura` del estilo + "large simple shapes, low detail". Sin la `paleta` del estilo (es de personajes);
  el color va en la descripción. Con detalle fino, de lejos el piso se ve como ruido.
- **Motor**: `sdxl` = DreamShaper XL Turbo (~5 s, admite referencia) o `flux` = FLUX.2 (más prolijo, ~4 min por
  imagen, sin referencia).
- **Desde una imagen**: `referencia` (global o por textura) + `recorte` `[x0, y0, x1, y1]` → IP-Adapter (*style
  transfer*, `ip_peso`) copia estilo y colores sin la composición. Mejor con el recorte de ese material. Qwen Image
  Edit no sirve acá: conserva la composición y solo recolorea.
- **Repetibles**: ningún modelo las da sin costura; `repetible.py` corre la imagen media vuelta y tapa la cruz de
  costuras con parches del interior. Bien para pasto, tierra, hojas, piedras; en dibujos regulares (tablas,
  ladrillos) los parches pueden notarse. La hoja de candidatas las muestra repetidas 2×2.
- **`tema`**: saca la luz de fondo (degradés, viñeta) y guarda el **detalle** en lineal: píxel / promedio × 0,5 (gris
  medio = el color del tema). El juego hace color × detalle × 2 en un shader (piso desde arriba, paredes
  triplanar). `tema.contraste` 0,5, `repeticion_m` 6 (metros por repetición), `px` 512. `tema.colores`: los promedios
  de cada textura van al tema (`floor_color`, `path_color`, `wall_color`).
- **Fondo** (`vista: "fondo"`): telón pintado 1344×768, repetible solo a lo ancho. `tema` funde el 40 % de arriba con
  el color del cielo (`background_color`) y el 10 % de abajo con el del suelo (`backdrop_ground`), en color de verdad
  (no es detalle).

</details>

---

## Guía de Godot

### Personaje de costado (`pipeline.py godot <n>`)

Genera en `personajes/<n>/godot/personajes/` (replica `res://personajes/...`):
- `<n>/<n>_visual.tscn`: Node2D con `sprite_personaje.gd` + Sprite2D (13 `hframes`, escalado 1/superresolución,
  filtro lineal con mipmaps: `texture_filter = 4`, `mipmaps/generate=true`), desplazado para que **el origen del nodo
  quede en los pies**;
- `<n>/<n>_sheet.png` (+ `.import`), `<n>_meta.json` (tamaños, offset, orden de frames, animaciones,
  `colision_sugerida`), `<n>_retrato.png` (512×640), `<n>_frente.png`;
- `_comun/sprite_personaje.gd`.

`--instalar <proyecto>` copia eso a `res://personajes/` del proyecto (conserva los `.import` existentes, así el uid
no cambia) y corre `godot --headless --import`. Lo instalado no se edita a mano: se regenera.

**Uso**: instanciar `<n>_visual.tscn` como **hijo directo** del `CharacterBody2D` (el rayo de la sombra excluye al
padre) y llamar `visual.set_frame(frame, mirando_izquierda)`. Colisión recomendada en `colision_sugerida` (≈ 24 % ×
77 % del alto en pantalla).

**Contrato del visual** (`sprite_personaje.gd`):
- `set_frame(frame: int, flip_h: bool)`;
- `frame_de(animacion, tiempo)` y `duracion(animacion)`: por nombre, con los datos de `animaciones` del meta (así un
  juego no depende de los índices);
- `retrato` y `frente`: las texturas, para una pantalla de selección;
- la **sombra** se dibuja en runtime pegada al piso (rayo hacia abajo desde los pies: se achica y aclara al saltar,
  desaparece sobre pozos). Nunca va en los sprites (subiría con el salto). Parámetros: `shadow_radius`,
  `shadow_alpha`, `shadow_fade_height`.

<details>
<summary><b>Orden de la hoja</b> (índices de frame)</summary>

Índice = fila × 13 + columna, igual que `Sprite2D.frame` con `hframes`/`vframes`; fila 0 = la tira original. Las
animaciones nuevas se agregan **siempre al final** (`armar_tira.ANIMACIONES`); las celdas van seguidas, así que
cambiar los cuadros de una corre los índices de las siguientes (buscar por nombre con `frame_de` o el meta):

| frame | 0 | 1-8 | 9 | 10 | 11 | 12 | 13-20 | 21-32 | 33-40 | 41-47 | 48-55 | 56 | 57 | 58 | 59-61 | 62-67 | 68-73 | 74-79 | 80-85 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| anim | idle | walk | despegue | subida | cima | caída | idle_loop | run | roll | punch | kick | crouch | block | land | hurt | die | throw | arms_up | charge |

</details>

### Personaje isométrico (`iso` + `godot`)

En `godot/personajes/<n>/iso/`:
- `<n>_iso_<anim>.png`: una hoja por animación (filas = direcciones `e,se,s,sw,w,nw,n,ne`, columnas = frames); todas
  comparten tamaño de celda y ancla (los pies);
- `<n>_iso_frames.tres`: `SpriteFrames` con una animación por acción y dirección (`walk_se`, `idle_n`...);
- `<n>_iso.tscn`: Node2D con `sprite_personaje_iso.gd` + `AnimatedSprite2D`; origen = pies (apto `y_sort`);
- API: `set_animacion("run", velocidad)` elige la dirección más cercana al vector (en pantalla; deshace el
  aplastamiento 2:1) y con `Vector2.ZERO` conserva la anterior. La sombra es una elipse dibujada en runtime.

Cámara 30°, `isometrico.baldosa_px` = ancho en pantalla de una baldosa de 1×1 unidad (128 → baldosas de 128×64 como
las de un `TileMapLayer` isométrico; el personaje de 1.85 mide ≈145 px). Para colgarle cosas, ver
[Anclas](#anclas-pipelinepy-anclas).

### Objetos

`<n>_lateral.tscn` y `<n>_iso.tscn` (ver [Objetos](#objetos)); `--instalar` copia a `res://objetos/`.

---

## Problemas conocidos

<details>
<summary><b>Síntomas frecuentes y su solución</b></summary>

| Síntoma | Causa / solución |
|---|---|
| `Bone Heat Weighting: failed to find solution` / todo sin peso | malla no soldada o un hueso fuera del cuerpo → revisar con `guia`; muchas piezas sueltas también lo rompen |
| Codos o rodillas "de goma" (trajes lisos) | revisar en `guia` que el codo esté a la altura de la cintura y probar `modelo.afinar_pesos` 2.5 |
| Al animar, manchas oscuras, "volados" o "agujeros" en la ropa (en reposo se ve bien) | capas escondidas que atraviesan la de afuera → `blender` ya las saca; si quedan, subir `modelo.suavizar_pesos`. Diagnóstico: render con `show_backface_culling` (las manchas son revés). Probar poses (golpe, patada), no solo la caminata |
| Le falta la cabeza o el pecho después de `blender` | caras de afuera con la normal al revés que `sacar_interior` borra → `modelo.normales: true` |
| La malla se queda sin VRAM | otro proceso en la GPU (ComfyUI generando, otra malla, un juego) → una generación por vez; `malla` ya libera ComfyUI. Tras un OOM, TRELLIS.2 se relanza solo a menor resolución |
| `DINOv3ViTModel has no attribute 'layer'` | `transformers` 5.x en el venv de TRELLIS.2 → `transformers==4.57.1` |
| Pixal3D falla buscando el GLB | `resolucion` 512: usar 1024 o 1536 |
| `resolucion: 1536` en TRELLIS.2 y la malla sale con agujeros | el remesh a 1536 no entra en 16 GB y sin remesh `sacar_interior` borra caras de afuera → 1024 |
| Se llena el disco del sistema | las cachés de Hugging Face y uv van por defecto a `~/.cache` → `env_modelos` en la config |
| La cara mira hacia abajo (o al cielo) en los sprites | `animacion.cabeza_arriba_grados` (negativo = levantar la cara) |
| Ojos como agujeros grises | ver `modelo.ojos` (3b) |
| Ojos estrábicos o con delineado grueso | `pipeline.py ultratex <n>` con otra `malla.ultratex.seed` |
| El personaje "flota" o se hunde en Godot | el offset sale de la última fila opaca del frame quieto; si hay algo debajo de los pies (capa, cola), ajustar `position.y` del Sprite en el `.tscn` |
| Personaje muy oscuro | TRELLIS.2 pinta la textura más oscura que la imagen; con colores oscuros de por sí no alcanza la compensación del render → aclarar la textura de `modelo.glb` (curva gamma ~0,6) antes de `blender`, o repintar con UltraTex |
| La espalda repite lo del pecho | UltraTex o Qwen copiaron el frente → `malla.ultratex.espalda: true` y revisar `vista_back.png` |
| La cara sale cachetona, con ojos y boca como manchas | en una imagen de cuerpo entero con proporciones reales la cara ocupa ~50 px → Pixal3D + UltraTex la resuelven mejor que TRELLIS.2 |
| Personaje sin referencia sale raro | con `referencia: null` y un `imagen.prompt` a mano, no empezar con "Transform this...": usar `imagen.descripcion` |
| La ropa sale lustrada como vinilo | estilo `moderno_juguete` en una persona → `moderno` (mismo prompt) y rehacer `blender` → `sprites` → `iso`; la imagen no hace falta regenerarla |

</details>

## Limitaciones

- La topología de la malla es automática (triángulos): sirve para sprites y deformaciones simples, no para
  animación facial ni para usar el personaje 3D en un juego sin retopología.
- El costado y la espalda se inventan a partir de la vista frontal (las vistas de Qwen ayudan, pero hay que mirarlas).
- Los dedos no tienen huesos (mano entera = un hueso).
- Los clips de Kimodo son de un cuerpo humano adulto: en chibis y cabezones las manos pueden no llegar o cruzar la
  cara.
- Las animaciones procedurales son las mismas poses para todos: en proporciones raras la piña puede no llegar o la
  guardia tapar la cara. Se ajustan en `anim.py` (afecta a todos) mirando `preview.gif`.
- Solo probado en Linux + NVIDIA de 16 GB.
- Los personajes parecidos a propiedad intelectual ajena (franquicias, marcas) son responsabilidad de quien los
  genera: hacerlos para uso personal no da derecho a publicarlos.

---

## Para agentes de IA

AssetCrisol está pensado para dos tipos de usuario: personas y **agentes de IA** (Claude Code u otro) que lo instalan,
corren los pasos y le muestran a la persona lo que tiene que decidir. Las instrucciones para agentes (cómo correr
cada paso, mapa del código, contratos que no hay que romper y problemas ya resueltos) están en
[CLAUDE.md](CLAUDE.md); [AGENTS.md](AGENTS.md) remite ahí para cualquier agente. Lo esencial:

- una generación por vez en la GPU (revisar la cola de ComfyUI y `nvidia-smi` antes de cada paso de GPU);
- **no elegir por la persona** `imagen.elegida`, `malla.elegida` ni las texturas elegidas: mostrarle la hoja de
  candidatos y preguntar;
- mirar los resultados visuales (`candidatos.png`, `preview.gif`, `revision.png`) antes de darlos por buenos.

---

## Licencia

AssetCrisol (este código) es **GPL-3.0**: ver [LICENSE](LICENSE). Los scripts que importan `bpy` se consideran GPL,
coherente con Blender.

## Licencias de terceros

AssetCrisol no incluye pesos de modelos: cada uno se baja aparte y tiene su licencia. Lo que sigue es una guía, no
asesoramiento legal: **verificá la licencia vigente de cada modelo antes de usar los resultados con fines
comerciales.**

> [!CAUTION]
> **La receta por defecto de los humanoides usa UltraTex (FLUX.2 Klein 9B, no comercial).** La imagen sin
> referencia usa por defecto Z-Image Turbo (Apache-2.0); FLUX.2 Dev (no comercial) solo si lo elegís con
> `imagen.motor: "flux2"`. Para un proyecto comercial, revisá estas licencias o usá una receta sin esos modelos (p.
> ej. TRELLIS.2 o Pixal3D sin `ultratex`, e imagen con Qwen o Z-Image).

| Componente | Para qué | Licencia |
|---|---|---|
| TRELLIS.2 (código y pesos) | malla (motor `trellis2`) | MIT |
| DINOv3 | codificador de imagen de TRELLIS.2 y Pixal3D | licencia propia de Meta, acceso gated |
| Pixal3D | malla (motor `pixal3d`) | MIT |
| rembg | quitar el fondo | MIT (los modelos u2net, la suya) |
| BiRefNet | quitar el fondo | MIT |
| MoGe | campo visual para Pixal3D | MIT (a verificar) |
| Qwen Image Edit 2511 | paso 1 con referencia, vistas | Apache-2.0 |
| LoRA Lightning de Qwen Image Edit | paso 1 en 4 pasos | a verificar |
| Z-Image Turbo | paso 1 sin referencia (por defecto) | Apache-2.0 |
| FLUX.2 Dev | paso 1 sin referencia (`imagen.motor: "flux2"`), escenarios `flux` | **no comercial** (FLUX.2 [dev] Non-Commercial License) |
| FLUX.2 Klein base 9B | UltraTex | **no comercial** (licencia de Black Forest Labs) |
| ComfyUI-UltraTex (nodos) | UltraTex | MIT |
| LoRA y decoder de UltraTex | UltraTex | a verificar |
| DWPose (comfyui_controlnet_aux) | paso `articulaciones` | Apache-2.0 (a verificar los pesos) |
| DreamShaper XL Turbo | escenarios `sdxl` | CreativeML Open RAIL++-M (a verificar) |
| IP-Adapter | escenarios con referencia | Apache-2.0 |
| Kimodo (código) | clips de movimiento | Apache-2.0 |
| Kimodo (pesos) | clips de movimiento | **a verificar** |
| Llama 3 8B Instruct + LLM2Vec | codificador de texto de Kimodo | Llama 3 Community License (y la de LLM2Vec) |
| ComfyUI | servidor de generación | GPL-3.0 |
| Blender | rig, animación y render | GPL |
| Godot | motor de destino (opcional) | MIT |
