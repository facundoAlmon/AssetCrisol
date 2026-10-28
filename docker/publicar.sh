#!/usr/bin/env bash
# Construye la imagen acá y la sube a un registro (la imagen pesa ~23 GB: no entra en los runners gratis de GitHub).
#   docker/publicar.sh 0.1.0                          -> ghcr.io/facundoalmon/assetcrisol:0.1.0 y :latest
#   REGISTRO=docker.io/usuario docker/publicar.sh 0.1.0
#   REGISTRO=registry.gitlab.com/usuario/assetcrisol docker/publicar.sh 0.1.0
# Antes, una vez: docker login <registro> (en GHCR, con un token de GitHub con permiso write:packages).
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=${1:?uso: docker/publicar.sh <versión> (p. ej. 0.1.0)}
REGISTRO=${REGISTRO:-ghcr.io/facundoalmon}
IMAGEN=$REGISTRO/assetcrisol
[[ $REGISTRO == registry.gitlab.com/*/* ]] && IMAGEN=$REGISTRO   # GitLab: la imagen va con la ruta del proyecto

[ -z "$(git status --porcelain)" ] || { echo "hay cambios sin commitear: la imagen tiene que salir de un commit"; exit 1; }
COMMIT=$(git rev-parse --short HEAD)

docker build -t "$IMAGEN:$VERSION" -t "$IMAGEN:latest" \
  --label org.opencontainers.image.version="$VERSION" --label org.opencontainers.image.revision="$COMMIT" .
docker push "$IMAGEN:$VERSION"
docker push "$IMAGEN:latest"
echo "publicada: $IMAGEN:$VERSION ($COMMIT)"
