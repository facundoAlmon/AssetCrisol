# AssetCrisol en Docker

[English](docker.en.md)

La imagen trae ComfyUI (con sus nodos), TRELLIS.2 (con sus extensiones compiladas) y Blender 5.1, instalados con
`instalar.sh`. **No trae modelos**: van en un volumen que se llena una vez. Los assets que generás quedan en una
carpeta tuya.

## Requisitos

- Linux con una NVIDIA de 16 GB (Ampere, Ada o Hopper: RTX 30/40, A-series; las RTX 50 no están probadas) y driver
  560 o más nuevo.
- Docker con [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
  (`docker run --rm --gpus all ubuntu nvidia-smi` tiene que mostrar la placa).
- Disco: ~23 GB la imagen y ~90-135 GB los modelos (ver README > Requisitos en detalle). Si `/var/lib/docker` está
  en un disco chico, mover el almacenamiento de Docker (`data-root` en `/etc/docker/daemon.json`).

## Uso

```bash
docker pull ghcr.io/facundoalmon/assetcrisol   # ~23 GB; o construirla: docker build -t ghcr.io/facundoalmon/assetcrisol . (~20 min)

# un alias para no repetir: GPU, modelos en un volumen, assets en ./assets
mkdir -p assets
alias crisol='docker run --rm -it --gpus all -v crisol-modelos:/modelos -v "$PWD/assets":/datos ghcr.io/facundoalmon/assetcrisol'

crisol modelos                  # baja los modelos al volumen (nivel completo; --nivel minimo, --flux2)
crisol doctor                   # revisa todo
crisol nuevo bandido            # y el resto de los pasos igual que sin Docker
crisol todo bandido
```

- **Modelos gated** (DINOv3 y FLUX.2 Klein): aceptar sus condiciones en Hugging Face con tu cuenta. `crisol modelos`
  pide un token de lectura (o pasarlo con `-e HF_TOKEN=hf_...`); queda guardado en el volumen.
- Los archivos generados quedan a nombre del dueño de la carpeta montada en `/datos`.
- Para probar sin generar: `cp -r ejemplos/* assets/` y `crisol blender cris && crisol sprites cris`.
- Una terminal adentro: `crisol bash`.

## Publicar (mantenedores)

`docker/publicar.sh <versión>` la construye acá y la sube (23 GB: no entra en los runners gratis de GitHub). Por
defecto a GHCR (`ghcr.io/facundoalmon/assetcrisol`, que es pública; la primera fue `0.1.0-alpha.1`); para otro registro,
`REGISTRO=docker.io/<usuario>` o `registry.gitlab.com/<usuario>/<proyecto>`. Antes, `docker login`. En GHCR el
paquete nace privado: la primera vez, hacerlo público en su página de GitHub.

## Notas

- Cada `docker run` arranca su propio ComfyUI cuando un paso lo necesita: el primer paso de imagen tarda más (carga
  los modelos).
- **Una generación por vez en la GPU**: no correr un paso de imagen o malla mientras otro programa la usa (otro
  ComfyUI, un juego). Con 16 GB, dos a la vez se quedan sin memoria.
- Kimodo y Godot no están en la imagen (opcionales; ver README).
- Blender y el horneado de UltraTex usan EGL (OpenGL sin pantalla): la imagen ya pide las capacidades gráficas del
  driver (`NVIDIA_DRIVER_CAPABILITIES=all`).
