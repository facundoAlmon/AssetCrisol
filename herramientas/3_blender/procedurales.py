#!/usr/bin/env python3
# El esqueleto de costado de cada animación procedural (las de metodos.CUADROS), para compararlas con los clips de
# Kimodo en crisol ui > Movimientos: corre Blender (modo `esqueletos`) sobre una copia de Cris y deja
# movimientos/procedurales.json (versionado). Volver a correrlo al cambiar anim.py o el rig.
# uso: python3 herramientas/3_blender/procedurales.py   (python3 del sistema; ~1 min, Blender con la GPU)
import json, os, shutil, sys, tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, RAIZ)
import pipeline  # noqa: E402

with tempfile.TemporaryDirectory() as tmp:
    pipeline.DATOS = tmp
    shutil.copytree(os.path.join(RAIZ, 'ejemplos', 'personajes', 'cris'), os.path.join(tmp, 'personajes', 'cris'))
    pdir, pj = pipeline.cargar('cris')
    pj['tiempo_real'] = False
    pipeline.blender('esqueletos', pdir, pj)
    with open(os.path.join(pdir, 'trabajo', 'esqueletos.json')) as f:
        d = json.load(f)
destino = os.path.join(AQUI, 'movimientos', 'procedurales.json')
with open(destino, 'w') as f:
    json.dump(d, f, separators=(',', ':'))
    f.write('\n')
print(f'{destino}: {", ".join(d["animaciones"])} ({os.path.getsize(destino) / 1e3:.0f} kB)')
