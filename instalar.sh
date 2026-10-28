#!/usr/bin/env bash
# instalar.sh: instala lo que necesita AssetCrisol (ComfyUI + nodos, TRELLIS.2, Blender y los modelos) y escribe
# config.json. Nativo, sin Docker, sin sudo: lo que necesita del sistema (driver, toolkit de CUDA, git) lo revisa y
# dice cómo instalarlo. Se puede volver a correr: lo que ya está se saltea. Repos en commits fijos (los probados).
#
#   ./instalar.sh                        nivel completo en ~/assetcrisol-herramientas
#   ./instalar.sh --nivel minimo         Qwen + Z-Image + TRELLIS.2 + Blender (sin Pixal3D, UltraTex ni escenarios)
#   ./instalar.sh --destino /disco/grande --flux2 --solo modelos
#   ./instalar.sh --kimodo               también Kimodo (crisol movimiento, en CPU; +~19 GB)
#   ./instalar.sh --plan                 muestra qué haría, sin hacer nada
#
# Si config.json ya apunta a un ComfyUI, TRELLIS.2 o Blender existentes, los usa: no toca su código ni su venv,
# solo suma los nodos y modelos que falten. Al final corre `crisol doctor`.
set -euo pipefail

RAIZ=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
CONFIG=${ASSETCRISOL_CONFIG:-$RAIZ/config.json}

# --- versiones fijadas (las de la placa de referencia, RTX 4080 Super, 2026-10) --------------------------------
COMFYUI_REPO=https://github.com/comfyanonymous/ComfyUI.git
COMFYUI_COMMIT=6338e4bd428247a4a8843496aa98fb7f2a9d3632      # v0.35.0+10: trae los nodos nativos de Pixal3D
COMFYUI_PY=3.12
TORCH_COMFY="torch==2.14.0 torchvision==0.29.0 torchaudio==2.11.0"
# nodo -> "repo commit nivel": nivel completo, o flux2 (solo con --flux2)
declare -A NODOS=(
  [ComfyUI-UltraTex]="https://github.com/visualbruno/ComfyUI-UltraTex 8137da52ed8352305cb7825b39c36a250bf2507a completo"
  [comfyui_controlnet_aux]="https://github.com/Fannovel16/comfyui_controlnet_aux 59b1fc411ede8623b2997855b8018f0b3b6cf49f completo"
  [comfyui_ipadapter_plus]="https://github.com/cubiq/ComfyUI_IPAdapter_plus a0f451a5113cf9becb0847b92884cb10cbdec0ef completo"
  [ComfyUI-GGUF]="https://github.com/city96/ComfyUI-GGUF 6ea2651e7df66d7585f6ffee804b20e92fb38b8a flux2"
)
TRELLIS_REPO=https://github.com/microsoft/TRELLIS.2.git
TRELLIS_COMMIT=75fbf0183001ed9876c8dbb35de6b68552ee08bd
TRELLIS_TORCH="torch==2.6.0 torchvision==0.21.0"                # el repo lo pide así (cu124)
FLASH_ATTN=https://github.com/Dao-AILab/flash-attention/releases/download/v2.7.3/flash_attn-2.7.3+cu12torch2.6cxx11abiFALSE-cp310-cp310-linux_x86_64.whl
UTILS3D=git+https://github.com/EasternJournalist/utils3d.git@9a4eb15e4021b67b12c460c7057d642626897ec8
# extensiones de TRELLIS.2 que se compilan: nombre -> "repo commit"
declare -A EXT_TRELLIS=(
  [nvdiffrast]="https://github.com/NVlabs/nvdiffrast.git 253ac4fcea7de5f396371124af597e6cc957bfae"   # v0.4.0
  [nvdiffrec]="https://github.com/JeffreyXiang/nvdiffrec.git b296927cc7fd01c2ac1087c8065c4d7248f72da4" # renderutils
  [CuMesh]="https://github.com/JeffreyXiang/CuMesh.git 12289e1062f0603f2f0d0771b02e1395d247f26f"
  [FlexGEMM]="https://github.com/JeffreyXiang/FlexGEMM.git 6dd94a859c26ee8246888502eada3dd8ad85532e"
)
BLENDER_VERSION=5.1.2
BLENDER_URL=https://download.blender.org/release/Blender5.1/blender-$BLENDER_VERSION-linux-x64.tar.xz
HF_HUB="huggingface_hub[hf_xet]==0.36.2"
KIMODO_REPO=https://github.com/nv-tlabs/kimodo.git
KIMODO_COMMIT=e1c219c99b4b94ba48be1fb6a1cbc64ecee4c954
KIMODO_TORCH="torch==2.11.0"                                    # de CPU: crisol movimiento no usa la GPU
KIMODO_MODELO=nvidia/Kimodo-SOMA-RP-v1.2                        # a la caché de Hugging Face (HF_HOME)
# codificador de texto (LLM2Vec sobre Llama 3 8B Instruct) en <kimodo>/text_encoders: el espejo de NousResearch
# tiene los mismos pesos que meta-llama (gated) y la misma licencia
KIMODO_LLAMA=NousResearch/Meta-Llama-3-8B-Instruct
KIMODO_LLM2VEC="McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp-supervised"

# Modelos de ComfyUI: nivel | carpeta en models/ | nombre final | repo (hf: Hugging Face, ms: ModelScope) | archivo.
# Los nombres finales son los que esperan doctor.py y config.ejemplo.json (modelos_imagen).
MODELOS_COMFY='
minimo   diffusion_models    qwen_image_edit_2511_int8_convrot.safetensors              hf:Comfy-Org/Qwen-Image-Edit_ComfyUI      split_files/diffusion_models/qwen_image_edit_2511_int8_convrot.safetensors
minimo   loras               Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors hf:lightx2v/Qwen-Image-Edit-2511-Lightning Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors
minimo   text_encoders       qwen_2.5_vl_7b_fp8_scaled.safetensors                      hf:Comfy-Org/Qwen-Image_ComfyUI           split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors
minimo   vae                 qwen_image_vae.safetensors                                 hf:Comfy-Org/Qwen-Image_ComfyUI           split_files/vae/qwen_image_vae.safetensors
minimo   diffusion_models    z_image_turbo_bf16.safetensors                             hf:Comfy-Org/z_image_turbo                split_files/diffusion_models/z_image_turbo_bf16.safetensors
minimo   text_encoders       qwen_3_4b.safetensors                                      hf:Comfy-Org/z_image_turbo                split_files/text_encoders/qwen_3_4b.safetensors
minimo   vae                 z_image_ae.safetensors                                     hf:Comfy-Org/z_image_turbo                split_files/vae/ae.safetensors
completo diffusion_models    pixal3d_int8_convrot.safetensors                           hf:Comfy-Org/Pixal3D                      diffusion_models/pixal3d_int8_convrot.safetensors
completo diffusion_models    pixal3d_multiview_int8_convrot.safetensors                 hf:Comfy-Org/Pixal3D                      diffusion_models/pixal3d_multiview_int8_convrot.safetensors
completo vae                 trellis_2_shape_vae_bf16.safetensors                       hf:Comfy-Org/Pixal3D                      vae/trellis_2_shape_vae_bf16.safetensors
completo vae                 trellis_2_texture_vae_bf16.safetensors                     hf:Comfy-Org/Pixal3D                      vae/trellis_2_texture_vae_bf16.safetensors
completo clip_vision         dino_v3_L_naf_fp32.safetensors                             hf:Comfy-Org/Pixal3D                      clip_vision/dino_v3_L_naf_fp32.safetensors
completo geometry_estimation moge_2_vitl_normal_fp16.safetensors                        hf:Comfy-Org/MoGe                         geometry_estimation/moge_2_vitl_normal_fp16.safetensors
completo background_removal  birefnet.safetensors                                       hf:Comfy-Org/BiRefNet                     background_removal/birefnet.safetensors
completo diffusion_models    flux-2-klein-base-9b-fp8.safetensors                       hf:black-forest-labs/FLUX.2-klein-base-9b-fp8 flux-2-klein-base-9b-fp8.safetensors
completo text_encoders       qwen_3_8b_fp8mixed.safetensors                             hf:Comfy-Org/flux2-klein-9B               split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors
completo vae                 flux2-vae.safetensors                                      hf:Comfy-Org/flux2-klein-9B               split_files/vae/flux2-vae.safetensors
completo loras               ultratex_flux2.safetensors                                 ms:Yibo-Zhang/UltraTex                    flux2/lora/dit_lora.safetensors
completo ultratex            ultratex_flux2_decoder.pt                                  ms:Yibo-Zhang/UltraTex                    flux2/decoder.pt
completo checkpoints         dreamshaperXL_v21TurboDPMSDE.safetensors                   hf:Lykon/dreamshaper-xl-v2-turbo          DreamShaperXL_Turbo_v2_1.safetensors
completo ipadapter           ip-adapter-plus_sdxl_vit-h.safetensors                     hf:h94/IP-Adapter                         sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors
completo clip_vision         CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors                hf:h94/IP-Adapter                         models/image_encoder/model.safetensors
flux2    unet                flux2-dev-Q5_K_M.gguf                                      hf:city96/FLUX.2-dev-gguf                 flux2-dev-Q5_K_M.gguf
flux2    text_encoders       mistral_3_small_flux2_fp8.safetensors                      hf:Comfy-Org/flux2-dev                    split_files/text_encoders/mistral_3_small_flux2_fp8.safetensors
flux2    vae                 flux2-vae.safetensors                                      hf:Comfy-Org/flux2-klein-9B               split_files/vae/flux2-vae.safetensors
'
# pesos de TRELLIS.2 (en la caché de Hugging Face, HF_HOME): repo | archivos (vacío = el repo entero)
PESOS_TRELLIS='
microsoft/TRELLIS.2-4B
microsoft/TRELLIS-image-large            ckpts/ss_dec_conv3d_16l8_fp16.json ckpts/ss_dec_conv3d_16l8_fp16.safetensors
facebook/dinov3-vitl16-pretrain-lvd1689m
'
GATED_MINIMO="facebook/dinov3-vitl16-pretrain-lvd1689m"
GATED_COMPLETO="black-forest-labs/FLUX.2-klein-base-9b-fp8"

# --- argumentos --------------------------------------------------------------------------------------------------
NIVEL=completo; DESTINO=$HOME/assetcrisol-herramientas; FLUX2=0; KIMODO=0; PLAN=0; SOLO=""
ayuda() { sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; cat <<EOF

Opciones:
  --nivel minimo|completo   completo (por defecto) suma Pixal3D, UltraTex, DWPose y escenarios (~135 GB en total;
                            mínimo ~90 GB)
  --destino DIR             dónde van ComfyUI, TRELLIS.2, Blender y la caché de modelos (default $DESTINO)
  --flux2                   también FLUX.2 Dev (+ ComfyUI-GGUF, ~42 GB; licencia no comercial; opcional)
  --kimodo                  también Kimodo, para clips de movimiento nuevos (crisol movimiento, en CPU; ~19 GB;
                            opcional: los clips incluidos se leen sin él)
  --solo a,b                solo esos componentes: comfyui, modelos (también los pesos de TRELLIS.2), trellis,
                            blender, kimodo, config
  --plan                    mostrar qué se haría, sin instalar ni bajar nada
EOF
}
while [ $# -gt 0 ]; do
  case $1 in
    --nivel) NIVEL=$2; shift 2 ;;
    --destino) DESTINO=$2; shift 2 ;;
    --flux2) FLUX2=1; shift ;;
    --kimodo) KIMODO=1; shift ;;
    --solo) SOLO=",$2,"; shift 2 ;;
    --plan) PLAN=1; shift ;;
    -h|--help) ayuda; exit 0 ;;
    *) echo "opción desconocida: $1 (ver --help)" >&2; exit 2 ;;
  esac
done
case $NIVEL in minimo|completo) ;; *) echo "--nivel minimo o completo" >&2; exit 2 ;; esac
[ $PLAN = 1 ] || mkdir -p "$DESTINO"
DESTINO=$(cd "$DESTINO" 2>/dev/null && pwd || echo "$DESTINO")

# --- utilidades --------------------------------------------------------------------------------------------------
titulo() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
ok() { printf '  \033[32m✔\033[0m %s\n' "$*"; }
aviso() { printf '  \033[33m!\033[0m %s\n' "$*"; }
error() { printf '  \033[31m✘\033[0m %s\n' "$*" >&2; }
morir() { error "$*"; exit 1; }
hacer() { if [ $PLAN = 1 ]; then info "[plan] $*"; else "$@"; fi; }
toca() { [ -z "$SOLO" ] || [[ $SOLO == *",$1,"* ]]; }
[[ $SOLO == *",kimodo,"* ]] && KIMODO=1   # Kimodo es opcional: solo con --kimodo o --solo kimodo
incluye() {   # incluye <nivel de un ítem>: si entra en lo pedido
  case $1 in minimo) return 0 ;; completo) [ $NIVEL = completo ] ;; flux2) [ $FLUX2 = 1 ] ;; *) return 1 ;; esac
}
cfg() {   # cfg <clave>: valor de config.json (vacío si no hay o es un placeholder /ruta/a...)
  [ -f "$CONFIG" ] || return 0
  python3 - "$CONFIG" "$1" <<'EOF'
import json, sys
v = json.load(open(sys.argv[1]))
for k in sys.argv[2].split('.'):
    v = v.get(k) if isinstance(v, dict) else None
print(v if isinstance(v, str) and not v.startswith('/ruta/a') else '')
EOF
}
clonar() {   # clonar <repo> <commit> <dir>: clon nuevo en un commit fijo
  hacer git clone --quiet --filter=blob:none "$1" "$3"
  hacer git -C "$3" -c advice.detachedHead=false checkout --quiet "$2"
}
hf() { HF_HOME=$HF_HOME_DIR uvx --quiet --from "$HF_HUB" hf "$@"; }
hfpy() { HF_HOME=$HF_HOME_DIR uv run --quiet --no-project --with "$HF_HUB" python3 -c "$@"; }

# --- rutas: las de config.json si existen, si no las de --destino ----------------------------------------------
COMFY=$(cfg comfyui_dir); TRELLIS=$(cfg trellis2_dir); BLENDER=$(cfg blender); HF_HOME_DIR=$(cfg env_modelos.HF_HOME)
KIMODO_DIR=$(cfg kimodo_dir)
U2NET_DIR=$(cfg env_modelos.U2NET_HOME)
COMFY_AJENO=0; TRELLIS_AJENO=0; KIMODO_AJENO=0
if [ -n "$COMFY" ] && [ -d "$COMFY" ] && [ ! -f "$COMFY/.assetcrisol" ]; then COMFY_AJENO=1; fi
if [ -n "$TRELLIS" ] && [ -d "$TRELLIS" ] && [ ! -f "$TRELLIS/.assetcrisol" ]; then TRELLIS_AJENO=1; fi
if [ -n "$KIMODO_DIR" ] && [ -d "$KIMODO_DIR" ] && [ ! -f "$KIMODO_DIR/.assetcrisol" ]; then KIMODO_AJENO=1; fi
[ -n "$COMFY" ] || COMFY=$DESTINO/ComfyUI
[ -n "$TRELLIS" ] || TRELLIS=$DESTINO/TRELLIS.2
[ -n "$BLENDER" ] || BLENDER=$DESTINO/blender-$BLENDER_VERSION-linux-x64/blender
[ -n "$KIMODO_DIR" ] || KIMODO_DIR=$DESTINO/kimodo
[ -n "$HF_HOME_DIR" ] || HF_HOME_DIR=$DESTINO/hf-cache
[ -n "$U2NET_DIR" ] || U2NET_DIR=$DESTINO/u2net

# la caché de uv (~15 GB de ruedas de torch y CUDA) va al disco de --destino, no a ~/.cache del disco del sistema;
# entre discos distintos uv copia en vez de enlazar
export UV_CACHE_DIR=${UV_CACHE_DIR:-$DESTINO/.uv-cache} UV_LINK_MODE=${UV_LINK_MODE:-copy}

# --- 1. requisitos del sistema -----------------------------------------------------------------------------------
titulo "Requisitos"
[ "$(uname -s)-$(uname -m)" = Linux-x86_64 ] || morir "solo Linux x86_64 (ver README > Requisitos)"
for c in git curl tar xz python3; do command -v $c >/dev/null || morir "falta $c: sudo apt install $c"; done
python3 -c 'import PIL' 2>/dev/null && ok "python3 con Pillow" || aviso "el python3 del sistema no tiene Pillow (pipeline.py lo necesita): sudo apt install python3-pil"
if [ -n "${CRISOL_CUDA_ARCH:-}" ]; then
  # sin GPU a la vista (docker build): arquitecturas y CUDA de torch fijados por variables
  CC=$CRISOL_CUDA_ARCH; TORCH_INDEX=https://download.pytorch.org/whl/${CRISOL_TORCH_CUDA:-cu126}
  ok "sin detectar GPU: compilar para $CC, torch de ComfyUI ${CRISOL_TORCH_CUDA:-cu126}"
else
  command -v nvidia-smi >/dev/null || morir "no hay nvidia-smi: instalar el driver de NVIDIA"
  IFS=, read -r GPU VRAM DRIVER CC < <(nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap --format=csv,noheader,nounits | head -1)
  GPU=${GPU# }; VRAM=${VRAM// /}; DRIVER=${DRIVER// /}; CC=${CC// /}
  ok "GPU $GPU, $(((VRAM + 512) / 1024)) GB, driver $DRIVER, compute capability $CC"
  [ "$VRAM" -ge 15800 ] || aviso "con menos de 16 GB de VRAM la malla puede no entrar"
  if [ "${DRIVER%%.*}" -ge 580 ]; then TORCH_INDEX=https://download.pytorch.org/whl/cu130
  else TORCH_INDEX=https://download.pytorch.org/whl/cu126; fi
fi
if ! command -v uv >/dev/null; then
  aviso "falta uv (gestor de entornos de Python): se instala en ~/.local/bin"
  hacer sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
  export PATH=$HOME/.local/bin:$PATH
fi
command -v uv >/dev/null && ok "uv $(uv --version | cut -d' ' -f2)"
existe=$DESTINO; while [ ! -d "$existe" ]; do existe=$(dirname "$existe"); done   # con --plan puede no existir
LIBRE=$(df -BG --output=avail "$existe" | tail -1 | tr -dc 0-9)
NECESITA=$([ $NIVEL = completo ] && echo 135 || echo 90); [ $FLUX2 = 1 ] && NECESITA=$((NECESITA + 42))
[ $KIMODO = 1 ] && NECESITA=$((NECESITA + 20))
if [ -n "$LIBRE" ] && [ "$LIBRE" -lt "$NECESITA" ]; then
  aviso "$DESTINO tiene $LIBRE GB libres; una instalación nueva usa ~$NECESITA GB (otro disco: --destino)"
else ok "$DESTINO (${LIBRE:-?} GB libres)"; fi

# toolkit de CUDA 12 para compilar las extensiones de TRELLIS.2 (su torch es cu124)
CUDA_12=""
if toca trellis && [ ! -f "$TRELLIS/.assetcrisol" ] && [ $TRELLIS_AJENO = 0 ]; then
  for d in "${CUDA_HOME:-}" /usr/local/cuda-12.9 /usr/local/cuda-12.8 /usr/local/cuda-12.6 /usr/local/cuda-12.4 /usr/local/cuda-12 /usr/local/cuda /usr; do
    [ -n "$d" ] && [ -x "$d/bin/nvcc" ] && "$d/bin/nvcc" --version | grep -q 'release 12\.' && { CUDA_12=$d; break; }
  done
  [ -n "$CUDA_12" ] && ok "toolkit de CUDA 12: $CUDA_12" || morir "TRELLIS.2 se compila con un toolkit de CUDA 12.x (nvcc) y no hay ninguno.
      Instalarlo de https://developer.nvidia.com/cuda-downloads (p. ej. sudo apt install cuda-toolkit-12-8) o
      indicar CUDA_HOME=/ruta. Con 13.x no compila contra el torch de TRELLIS.2."
  [ "${CC%%.*}" -lt 12 ] || aviso "GPU de compute capability $CC (RTX 50): el torch 2.6 de TRELLIS.2 no la soporta; sin probar"
fi

# MotionCorrection (parte de Kimodo) es C++ con CMake
if [ $KIMODO = 1 ] && toca kimodo && [ ! -f "$KIMODO_DIR/.assetcrisol" ] && [ $KIMODO_AJENO = 0 ]; then
  command -v cmake >/dev/null || morir "Kimodo necesita cmake: sudo apt install cmake"
  command -v g++ >/dev/null || morir "Kimodo necesita g++: sudo apt install build-essential"
  ok "cmake y g++ (Kimodo)"
fi

# --- 2. acceso a Hugging Face (modelos gated) --------------------------------------------------------------------
# solo si falta bajar alguno gated (un token se pide recién ahí: el resto se baja sin cuenta)
sesion_hf() { ! hf auth whoami 2>&1 | grep -qiE 'not logged|invalid'; }
gated=""
if toca modelos && [ ! -d "$HF_HOME_DIR/hub/models--${GATED_MINIMO//\//--}/snapshots" ]; then gated=$GATED_MINIMO; fi
if toca modelos && [ $NIVEL = completo ] && [ ! -f "$COMFY/models/diffusion_models/flux-2-klein-base-9b-fp8.safetensors" ]; then
  gated="$gated $GATED_COMPLETO"
fi
if [ -n "$gated" ] && [ $PLAN = 0 ]; then
  titulo "Hugging Face (modelos gated:$gated)"
  mkdir -p "$HF_HOME_DIR"
  # un token ya guardado en la caché por defecto (otra instalación) sirve igual, si es válido
  if [ -z "${HF_TOKEN:-}" ] && [ ! -f "$HF_HOME_DIR/token" ] && [ -f "$HOME/.cache/huggingface/token" ]; then
    export HF_TOKEN=$(cat "$HOME/.cache/huggingface/token")
    sesion_hf || unset HF_TOKEN
  fi
  if ! sesion_hf; then
    info "Hace falta una cuenta de Hugging Face y un token de lectura (https://huggingface.co/settings/tokens);"
    info "se guarda en $HF_HOME_DIR."
    [ -t 0 ] || morir "sin terminal para pedir el token: correr  HF_HOME=$HF_HOME_DIR uvx --from huggingface_hub hf auth login"
    hf auth login
    sesion_hf || morir "el token no anda: probar con otro (hf auth login)"
  fi
  ok "sesión: $(hf auth whoami 2>/dev/null | head -1)"
  sin=""
  for r in $gated; do
    hfpy "from huggingface_hub import auth_check; auth_check('$r')" >/dev/null 2>&1 || sin="$sin $r"
  done
  if [ -n "$sin" ]; then
    for r in $sin; do error "sin acceso a $r: entrar a https://huggingface.co/$r y aceptar las condiciones"; done
    morir "volver a correr ./instalar.sh después de aceptar (lo ya instalado se saltea)"
  fi
  ok "acceso a los modelos gated"
fi

# --- 3. ComfyUI ----------------------------------------------------------------------------------------------------
if toca comfyui; then
  titulo "ComfyUI ($COMFY)"
  if [ $COMFY_AJENO = 1 ]; then
    info "ya instalado (no lo puso este script): no se toca su código ni su venv, solo se suman nodos"
  elif [ -f "$COMFY/.assetcrisol" ] && grep -qx "$COMFYUI_COMMIT" "$COMFY/.assetcrisol"; then
    ok "ya instalado ($COMFYUI_COMMIT)"
  else
    [ -d "$COMFY/.git" ] || clonar "$COMFYUI_REPO" "$COMFYUI_COMMIT" "$COMFY"
    hacer git -C "$COMFY" -c advice.detachedHead=false checkout --quiet "$COMFYUI_COMMIT"
    [ -x "$COMFY/venv/bin/python" ] || hacer uv venv --quiet -p $COMFYUI_PY --seed "$COMFY/venv"
    info "torch ($TORCH_INDEX)..."
    hacer uv pip install --quiet -p "$COMFY/venv/bin/python" $TORCH_COMFY --index-url "$TORCH_INDEX"
    hacer uv pip install --quiet -p "$COMFY/venv/bin/python" -r "$COMFY/requirements.txt" comfy-cli==1.20.0 "$HF_HUB"
    [ $PLAN = 1 ] || echo "$COMFYUI_COMMIT" > "$COMFY/.assetcrisol"
    ok "ComfyUI $COMFYUI_COMMIT"
  fi
  for nodo in "${!NODOS[@]}"; do
    read -r repo commit nivel <<< "${NODOS[$nodo]}"
    incluye "$nivel" || continue
    dir=$COMFY/custom_nodes/$nodo
    if ls "$COMFY/custom_nodes" 2>/dev/null | grep -qix "$nodo"; then ok "nodo $nodo"; continue; fi
    clonar "$repo" "$commit" "$dir"
    [ -f "$dir/requirements.txt" ] && hacer uv pip install --quiet -p "$COMFY/venv/bin/python" -r "$dir/requirements.txt"
    if [ "$nodo" = ComfyUI-UltraTex ]; then
      hacer uv pip install --quiet -p "$COMFY/venv/bin/python" moderngl xatlas
      # hornea con OpenGL por X11; sin pantalla (servidor, contenedor) tiene que ser EGL
      hacer sed -i "s/create_standalone_context(require=330)/create_standalone_context(require=330, **({} if __import__('os').environ.get('DISPLAY') else {'backend': 'egl'}))/" \
        "$dir/ultratex_core/render.py"
    fi
    ok "nodo $nodo ($commit)"
  done
fi

# --- 4. modelos de ComfyUI -----------------------------------------------------------------------------------------
bajar_modelo() {   # bajar_modelo <carpeta> <nombre> <origen> <archivo>
  local dest=$COMFY/models/$1/$2 tmp=$COMFY/models/.descargas
  if [ -f "$dest" ] || find -L "$COMFY/models/$1" -name "$2" -print -quit 2>/dev/null | grep -q .; then
    ok "$1/$2"; return
  fi
  if [ $PLAN = 1 ]; then info "[plan] bajar $1/$2 de ${3#*:}"; return; fi
  info "bajando $1/$2 (${3#*:})..."
  mkdir -p "$COMFY/models/$1" "$tmp"
  case $3 in
    hf:*) hf download "${3#hf:}" "$4" --local-dir "$tmp" >/dev/null && mv "$tmp/$4" "$dest" ;;
    ms:*) curl -fL --retry 3 -C - -o "$tmp/$2.parcial" "https://www.modelscope.ai/models/${3#ms:}/resolve/master/$4" \
            && mv "$tmp/$2.parcial" "$dest" ;;
  esac
  ok "$1/$2"
}
if toca modelos; then
  titulo "Modelos de ComfyUI ($COMFY/models)"
  [ -d "$COMFY" ] || [ $PLAN = 1 ] || morir "no hay ComfyUI en $COMFY: correr sin --solo o con --solo comfyui,modelos"
  while read -r nivel carpeta nombre origen archivo; do
    if [ -n "$nivel" ] && incluye "$nivel"; then bajar_modelo "$carpeta" "$nombre" "$origen" "$archivo"; fi
  done <<< "$MODELOS_COMFY"
  rm -rf "$COMFY/models/.descargas"
  titulo "Pesos de TRELLIS.2 ($HF_HOME_DIR)"
  while read -r repo archivos; do
    [ -n "$repo" ] || continue
    if [ -d "$HF_HOME_DIR/hub/models--${repo//\//--}/snapshots" ]; then ok "pesos $repo"; continue; fi
    if [ $PLAN = 1 ]; then info "[plan] bajar $repo a $HF_HOME_DIR"; continue; fi
    info "bajando $repo..."
    # shellcheck disable=SC2086
    hf download "$repo" $archivos >/dev/null
    ok "pesos $repo"
  done <<< "$PESOS_TRELLIS"
fi

# --- 5. TRELLIS.2 --------------------------------------------------------------------------------------------------
if toca trellis; then
  titulo "TRELLIS.2 ($TRELLIS)"
  if [ $TRELLIS_AJENO = 1 ]; then
    info "ya instalado (no lo puso este script): no se toca su código ni su venv"
  elif [ -f "$TRELLIS/.assetcrisol" ] && grep -qx "$TRELLIS_COMMIT" "$TRELLIS/.assetcrisol"; then
    ok "ya instalado ($TRELLIS_COMMIT)"
  else
    [ -d "$TRELLIS/.git" ] || clonar "$TRELLIS_REPO" "$TRELLIS_COMMIT" "$TRELLIS"
    hacer git -C "$TRELLIS" -c advice.detachedHead=false checkout --quiet "$TRELLIS_COMMIT"
    hacer git -C "$TRELLIS" submodule update --quiet --init --recursive   # eigen, para o-voxel
    PY=$TRELLIS/venv/bin/python
    [ -x "$PY" ] || hacer uv venv --quiet -p 3.10 --python-preference only-managed --seed "$TRELLIS/venv"
    hacer uv pip install --quiet -p "$PY" $TRELLIS_TORCH --index-url https://download.pytorch.org/whl/cu124
    # dependencias de su setup.sh --basic (sin gradio ni pillow-simd: no las usa el pipeline) + las de AssetCrisol
    hacer uv pip install --quiet -p "$PY" imageio imageio-ffmpeg tqdm easydict opencv-python-headless ninja \
      trimesh transformers==4.57.1 tensorboard pandas lpips zstandard kornia timm setuptools wheel "$UTILS3D" \
      "$FLASH_ATTN" rembg onnxruntime "$HF_HUB"
    # extensiones CUDA: se compilan para la GPU de esta PC (TORCH_CUDA_ARCH_LIST)
    hacer mkdir -p "$TRELLIS/_ext"
    for ext in nvdiffrast nvdiffrec CuMesh FlexGEMM; do
      read -r repo commit <<< "${EXT_TRELLIS[$ext]}"
      [ -d "$TRELLIS/_ext/$ext" ] || { clonar "$repo" "$commit" "$TRELLIS/_ext/$ext"
                                        hacer git -C "$TRELLIS/_ext/$ext" submodule update --quiet --init --recursive; }
    done
    for ext in _ext/nvdiffrast _ext/nvdiffrec _ext/CuMesh _ext/FlexGEMM o-voxel; do
      info "compilando $ext (unos minutos)..."
      hacer mkdir -p "$DESTINO/.tmp"   # los temporales de nvcc tampoco van al disco del sistema
      hacer env CUDA_HOME="$CUDA_12" PATH="$CUDA_12/bin:$PATH" TORCH_CUDA_ARCH_LIST="$CC" MAX_JOBS="$(nproc)" TMPDIR="$DESTINO/.tmp" \
        uv pip install --quiet -p "$PY" "$TRELLIS/$ext" --no-build-isolation
    done
    hacer uv pip install --quiet -p "$PY" transformers==4.57.1   # alguna extensión puede haberlo movido
    [ $PLAN = 1 ] || echo "$TRELLIS_COMMIT" > "$TRELLIS/.assetcrisol"
    ok "TRELLIS.2 $TRELLIS_COMMIT"
  fi
fi

# --- 6. Blender ----------------------------------------------------------------------------------------------------
if toca blender; then
  titulo "Blender"
  if [ -x "$BLENDER" ]; then ok "$BLENDER"
  else
    BLENDER=$DESTINO/blender-$BLENDER_VERSION-linux-x64/blender
    if [ ! -x "$BLENDER" ]; then
      info "bajando Blender $BLENDER_VERSION..."
      hacer sh -c "curl -fL --retry 3 '$BLENDER_URL' | tar -xJ -C '$DESTINO'"
    fi
    ok "$BLENDER"
  fi
fi

# --- 7. Kimodo (opcional) ------------------------------------------------------------------------------------------
if [ $KIMODO = 1 ] && toca kimodo; then
  titulo "Kimodo ($KIMODO_DIR)"
  if [ $KIMODO_AJENO = 1 ]; then
    info "ya instalado (no lo puso este script): no se toca"
  elif [ -f "$KIMODO_DIR/.assetcrisol" ] && grep -qx "$KIMODO_COMMIT" "$KIMODO_DIR/.assetcrisol"; then
    ok "ya instalado ($KIMODO_COMMIT)"
  else
    [ -d "$KIMODO_DIR/.git" ] || clonar "$KIMODO_REPO" "$KIMODO_COMMIT" "$KIMODO_DIR"
    hacer git -C "$KIMODO_DIR" -c advice.detachedHead=false checkout --quiet "$KIMODO_COMMIT"
    PY=$KIMODO_DIR/venv/bin/python
    # un Python con headers: MotionCorrection se compila contra él
    [ -x "$PY" ] || hacer uv venv --quiet -p 3.11 --python-preference only-managed --seed "$KIMODO_DIR/venv"
    hacer uv pip install --quiet -p "$PY" $KIMODO_TORCH --index-url https://download.pytorch.org/whl/cpu
    info "kimodo y MotionCorrection (compila unos minutos)..."
    hacer mkdir -p "$DESTINO/.tmp"
    hacer env TMPDIR="$DESTINO/.tmp" uv pip install --quiet -p "$PY" -e "$KIMODO_DIR"
    for r in $KIMODO_LLAMA $KIMODO_LLM2VEC; do
      d=$KIMODO_DIR/text_encoders/$r
      if [ -f "$d/.completo" ]; then ok "codificador $r"; continue; fi
      if [ $PLAN = 1 ]; then info "[plan] bajar $r a $d"; continue; fi
      info "bajando $r..."
      hf download "$r" --local-dir "$d" >/dev/null && touch "$d/.completo"
      ok "codificador $r"
    done
    # los adaptadores de LLM2Vec apuntan a meta-llama/... (gated): al espejo local
    [ $PLAN = 1 ] || python3 - "$KIMODO_DIR/text_encoders" "$KIMODO_LLAMA" $KIMODO_LLM2VEC <<'EOF'
import json, os, sys
raiz, llama, *adaptadores = sys.argv[1:]
for a in adaptadores:
    ruta = os.path.join(raiz, a, 'adapter_config.json')
    c = json.load(open(ruta))
    c['base_model_name_or_path'] = os.path.join(raiz, llama)
    json.dump(c, open(ruta, 'w'), indent=2)
EOF
    [ $PLAN = 1 ] || echo "$KIMODO_COMMIT" > "$KIMODO_DIR/.assetcrisol"
    ok "Kimodo $KIMODO_COMMIT"
  fi
  if [ -d "$HF_HOME_DIR/hub/models--${KIMODO_MODELO//\//--}/snapshots" ]; then ok "pesos $KIMODO_MODELO"
  elif [ $PLAN = 1 ]; then info "[plan] bajar $KIMODO_MODELO a $HF_HOME_DIR"
  else info "bajando $KIMODO_MODELO..."; hf download "$KIMODO_MODELO" >/dev/null; ok "pesos $KIMODO_MODELO"; fi
fi

# --- 8. config.json ------------------------------------------------------------------------------------------------
if toca config; then
  titulo "Config ($CONFIG)"
  if [ $PLAN = 1 ]; then info "[plan] completar en config.json las rutas vacías o de ejemplo"
  else
    # completa solo lo que falta o sigue con /ruta/a...: lo que el usuario ya puso no se pisa
    python3 - "$CONFIG" "$RAIZ/config.ejemplo.json" "$COMFY" "$TRELLIS" "$BLENDER" "$HF_HOME_DIR" "$U2NET_DIR" "$FLUX2" \
      "$([ -x "$KIMODO_DIR/venv/bin/python" ] && echo "$KIMODO_DIR")" <<'EOF'
import json, os, sys
ruta, ejemplo, comfy, trellis, blender, hf, u2net, flux2, kimodo = sys.argv[1:]
cfg = json.load(open(ruta if os.path.exists(ruta) else ejemplo))
vacio = lambda v: not v or (isinstance(v, str) and v.startswith('/ruta/a'))
cambios = []
def poner(d, k, v, nombre):
    if vacio(d.get(k)):
        d[k] = v
        cambios.append(f'{nombre} = {v}')
poner(cfg, 'comfyui_dir', comfy, 'comfyui_dir')
poner(cfg, 'trellis2_dir', trellis, 'trellis2_dir')
poner(cfg, 'blender', blender, 'blender')
for k, v in json.load(open(ejemplo)).get('modelos_imagen', {}).items():   # los que baja este script
    if vacio(cfg.setdefault('modelos_imagen', {}).get(k)):
        cfg['modelos_imagen'][k] = v
        cambios.append(f'modelos_imagen.{k} = {v}')
env = cfg.setdefault('env_modelos', {})
poner(env, 'HF_HOME', hf, 'env_modelos.HF_HOME')
poner(env, 'U2NET_HOME', u2net, 'env_modelos.U2NET_HOME')
if kimodo:
    poner(cfg, 'kimodo_dir', kimodo, 'kimodo_dir')
for k in ('kimodo_dir', 'godot'):   # opcionales que este script no instala: sin el placeholder, doctor avisa
    if vacio(cfg.get(k)) and k in cfg:
        cfg.pop(k)
        cambios.append(f'{k}: sin instalar (opcional)')
if flux2 == '1':   # los nombres de los archivos que baja este script (el ejemplo trae los de otra descarga)
    mi = cfg.setdefault('modelos_imagen', {})
    for k, v in (('flux_unet', 'flux2-dev-Q5_K_M.gguf'), ('flux_clip', 'mistral_3_small_flux2_fp8.safetensors'),
                 ('flux_vae', 'flux2-vae.safetensors')):
        if not os.path.exists(os.path.join(comfy, 'models', 'unet' if k == 'flux_unet' else
                                           'text_encoders' if k == 'flux_clip' else 'vae', mi.get(k, ''))):
            mi[k] = v
            cambios.append(f'modelos_imagen.{k} = {v}')
json.dump(cfg, open(ruta, 'w'), ensure_ascii=False, indent=2)
open(ruta, 'a').write('\n')
print('\n'.join('  ✔ ' + c for c in cambios) or '  ✔ sin cambios')
EOF
  fi
fi

# --- 9. doctor ------------------------------------------------------------------------------------------------------
titulo "crisol doctor"
if [ $PLAN = 1 ]; then info "[plan] ./crisol doctor"; exit 0; fi
ASSETCRISOL_CONFIG=$CONFIG python3 "$RAIZ/pipeline.py" doctor || true
cat <<EOF

La caché de paquetes se puede borrar: UV_CACHE_DIR=$UV_CACHE_DIR uv cache clean
Listo. Probar sin generar nada:  cp -r ejemplos/* <datos_dir>/ && crisol blender cris && crisol sprites cris
Comando corto: ln -s "$RAIZ/crisol" ~/.local/bin/crisol   (README > Instalación)
Opcional: Kimodo con ./instalar.sh --kimodo (crisol movimiento); Godot 4 a mano (godot --instalar): ver README.
EOF
