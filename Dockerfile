# syntax=docker/dockerfile:1.7
# Imagen de AssetCrisol: ComfyUI (+ nodos), TRELLIS.2 y Blender instalados con instalar.sh, sin modelos. Los modelos
# van en el volumen /modelos (lo llena `docker run ... modelos`) y los assets en /datos. Ver docs/docker.md.
#   docker build -t assetcrisol .
ARG CUDA=12.8.1

# --- construir: el toolkit de CUDA hace falta solo para compilar las extensiones de TRELLIS.2 ----------------------
FROM nvidia/cuda:${CUDA}-devel-ubuntu24.04 AS construir
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates xz-utils python3 \
      build-essential && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.12.10 /uv /uvx /usr/local/bin/
# los Python de uv en una ruta fija, para copiarlos con los venvs que los usan
ENV UV_PYTHON_INSTALL_DIR=/opt/python UV_PYTHON_PREFERENCE=only-managed UV_LINK_MODE=copy
COPY instalar.sh config.ejemplo.json /app/
# sin GPU en el build: extensiones para Ampere, Ada y Hopper (las placas de 16 GB+ que andan con flash-attn 2);
# torch cu126 para ComfyUI (driver 560+). Después: modelos y pesos de DWPose al volumen, y las carpetas donde ComfyUI
# escribe abiertas a cualquier usuario (el contenedor corre como el dueño de /datos)
RUN CRISOL_CUDA_ARCH="8.0;8.6;8.9;9.0" CRISOL_TORCH_CUDA=cu126 ASSETCRISOL_CONFIG=/nada.json \
      /app/instalar.sh --destino /opt/crisol --solo comfyui,trellis,blender --flux2 \
 && rm -rf /opt/crisol/.uv-cache /opt/crisol/.tmp /opt/crisol/TRELLIS.2/_ext/*/build /root/.cache \
 && cd /opt/crisol/ComfyUI \
 && mv models models.vacio && ln -s /modelos/comfyui models \
 && rm -rf custom_nodes/comfyui_controlnet_aux/ckpts && ln -s /modelos/dwpose custom_nodes/comfyui_controlnet_aux/ckpts \
 && mkdir -p input output temp user && chmod -R a+rwX input output temp user

# --- imagen final: runtime de CUDA (sin el toolkit) + librerías de Blender y OpenGL/EGL ---------------------------
FROM nvidia/cuda:${CUDA}-runtime-ubuntu24.04
ENV DEBIAN_FRONTEND=noninteractive
# gcc: Triton (TRELLIS.2, UltraTex) compila su módulo de CUDA en el primer uso
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pil python3-numpy git curl gcc \
      libc6-dev ca-certificates xz-utils libegl1 libgl1 libglu1-mesa libglib2.0-0 libx11-6 libxrender1 libxi6 libxkbcommon0 \
      libxxf86vm1 libxfixes3 libxext6 libsm6 libice6 libgomp1 && rm -rf /var/lib/apt/lists/*
COPY --from=construir /usr/local/bin/uv /usr/local/bin/uvx /usr/local/bin/
COPY --from=construir /opt/python /opt/python
COPY --from=construir /opt/crisol /opt/crisol
COPY . /app
# graphics: EGL para Blender (EEVEE) y el horneado de UltraTex
ENV NVIDIA_DRIVER_CAPABILITIES=all UV_PYTHON_INSTALL_DIR=/opt/python UV_LINK_MODE=copy \
    ASSETCRISOL_CONFIG=/app/docker/config.json PATH=/app:$PATH
VOLUME ["/modelos", "/datos"]
WORKDIR /datos
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["doctor"]
