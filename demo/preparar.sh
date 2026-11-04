#!/usr/bin/env bash
# Instala en esta demo los assets de los ejemplos de AssetCrisol: Cris (iso), sus objetos y el tema del taller.
# Usa tu config (o ASSETCRISOL_CONFIG): si en datos_dir no están los ejemplos, los copia de ejemplos/ (no pisa nada).
# Corre blender/sprites/iso de cada uno (unos 5 min, renderiza con Blender: no hace falta la IA ni descargar modelos
# de imagen o malla) y `godot --instalar` hacia esta carpeta. Después: abrir project.godot con Godot 4.4 o más nuevo.
set -euo pipefail
DEMO="$(cd "$(dirname "$0")" && pwd)"
RAIZ="$(dirname "$DEMO")"
crisol() { "$RAIZ/crisol" "$@"; }
DATOS="$(python3 - "$RAIZ" <<'PY'
import json, os, sys
raiz = sys.argv[1]
cfg = os.environ.get('ASSETCRISOL_CONFIG') or os.path.join(raiz, 'config.json')
d = json.load(open(cfg)).get('datos_dir') or raiz
print(os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(cfg)), d)))
PY
)"
OBJETOS="horno yunque crisol caja_herramientas martillo"

for tipo_n in personajes/cris escenarios/taller $(for o in $OBJETOS; do echo objetos/$o; done); do
    if [ ! -e "$DATOS/$tipo_n" ]; then
        echo "[demo] copio el ejemplo $tipo_n a $DATOS"
        mkdir -p "$DATOS/$(dirname "$tipo_n")"
        cp -r "$RAIZ/ejemplos/$tipo_n" "$DATOS/$tipo_n"
    fi
done

echo "[demo] Cris"
crisol blender cris && crisol sprites cris && crisol iso cris
crisol godot cris --instalar "$DEMO"
for o in $OBJETOS; do
    echo "[demo] $o"
    crisol blender "$o" && crisol sprites "$o"
    crisol godot "$o" --instalar "$DEMO"
done
echo "[demo] tema del taller"
crisol tema taller
mkdir -p "$DEMO/escenarios/taller"
cp "$DATOS/escenarios/taller/trabajo/tema/"{tema.json,piso.png,camino.png,pared.png} "$DEMO/escenarios/taller/"
echo "[demo] listo: abrí $DEMO/project.godot con Godot (o: godot --path $DEMO)"
