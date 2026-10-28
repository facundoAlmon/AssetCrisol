#!/usr/bin/env bash
# Entrada de la imagen Docker. Corre los pasos como el dueño de /datos (los archivos generados quedan a su nombre).
#   modelos [opciones de instalar.sh]   baja los modelos al volumen /modelos (--nivel minimo, --flux2...)
#   bash                                una terminal adentro
#   <paso> <n> ...                      crisol <paso> <n> (doctor, nuevo, imagen, malla, blender...)
set -euo pipefail

if [ "$(id -u)" = 0 ]; then
  uid=$(stat -c %u /datos) gid=$(stat -c %g /datos)
  if [ "$uid" != 0 ]; then
    # los modelos los escribe y lee el mismo usuario (HF deja candados en la caché, DWPose y rembg bajan pesos)
    for d in /modelos /modelos/.home; do
      [ ! -e "$d" ] || [ "$(stat -c %u "$d")" = "$uid" ] || chown -R "$uid:$gid" "$d"
    done
    exec setpriv --reuid="$uid" --regid="$gid" --clear-groups env HOME=/modelos/.home "$0" "$@"
  fi
fi
# ya como el usuario final: lo que se crea acá es suyo
mkdir -p /modelos/comfyui /modelos/dwpose /modelos/hf /modelos/u2net /modelos/.home
cp -rn /opt/crisol/ComfyUI/models.vacio/. /modelos/comfyui/ 2>/dev/null || true   # las carpetas que espera ComfyUI
export HOME=${HOME:-/modelos/.home}
[ -w "$HOME" ] || export HOME=/modelos/.home
# numba (lo usa rembg) cachea junto a su código, que en la imagen no se puede escribir
export NUMBA_CACHE_DIR=$HOME/.cache/numba

case ${1:-doctor} in
  modelos) shift; exec /app/instalar.sh --solo modelos --destino /modelos "$@" ;;
  bash|sh) exec "$@" ;;
  *) exec python3 /app/pipeline.py "$@" ;;
esac
