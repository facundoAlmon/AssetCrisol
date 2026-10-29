# Genera clips candidatos con Kimodo (corre con el venv de Kimodo; lo lanza `pipeline.py movimiento`). Deja
# movimientos/candidatos/<anim>_s<seed>_<i>.npz (lo que usa kimodo_clip.py: posiciones, rotaciones globales,
# contactos, raíz, nombres de somaskel77, fps) y <anim>_s<seed>.png: esqueletos de costado, una fila por muestra y
# un cuadro cada 5, con el número de cuadro (30 fps), para elegir muestra y ventana (desde/hasta).
#   generar_movimiento.py <anim> "<prompt>" --duracion 4 --seed 1 --muestras 3
import argparse, os, subprocess, sys, tempfile

import numpy as np
from PIL import Image, ImageDraw
from kimodo.skeleton.definitions import SOMASkeleton77

CLAVES = ('posed_joints', 'global_rot_mats', 'foot_contacts', 'smooth_root_pos', 'root_positions')
CANDIDATOS = os.environ.get('MOVIMIENTOS_CANDIDATOS') or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                   'movimientos', 'candidatos')
PALITOS = [('Hips', 'Spine1'), ('Spine1', 'Chest'), ('Chest', 'Neck1'), ('Neck1', 'Head'), ('Head', 'HeadEnd')]
for _l in ('Left', 'Right'):
    PALITOS += [('Chest', _l + 'Shoulder'), (_l + 'Shoulder', _l + 'Arm'), (_l + 'Arm', _l + 'ForeArm'),
                (_l + 'ForeArm', _l + 'Hand'), ('Hips', _l + 'Leg'), (_l + 'Leg', _l + 'Shin'),
                (_l + 'Shin', _l + 'Foot'), (_l + 'Foot', _l + 'ToeBase')]


def hoja_palitos(rutas, salida, paso=5, celda=120, escala=60):
    """Vista lateral (adelante = derecha), en el lugar; izquierda en rojo, derecha en azul. Filas de 2 × celda
    = 240 px de alto: crisol ui recorta con ese alto la de cada muestra."""
    filas = []
    for r in rutas:
        d = np.load(r)
        J = {n: i for i, n in enumerate(d['nombres'])}
        P, raiz = d['posed_joints'], d['smooth_root_pos']
        filas.append((J, [(t, P[t] - [raiz[t, 0], 0, raiz[t, 2]]) for t in range(0, len(P), paso)]))
    img = Image.new('RGB', (max(len(f) for _, f in filas) * celda, len(filas) * celda * 2), 'white')
    dr = ImageDraw.Draw(img)
    for fi, (J, fila) in enumerate(filas):
        for ci, (t, p) in enumerate(fila):
            ox, oy = ci * celda + celda // 2, (fi + 1) * celda * 2 - 20
            for a, b in PALITOS:
                col = (200, 40, 40) if 'Left' in a + b else (40, 40, 200)
                pa, pb = p[J[a]], p[J[b]]
                dr.line([(ox + pa[2] * escala, oy - pa[1] * escala * 1.4),
                         (ox + pb[2] * escala, oy - pb[1] * escala * 1.4)], fill=col, width=2)
            dr.text((ci * celda + 4, fi * celda * 2 + 4), f'{fi}: {t}' if ci == 0 else str(t), fill='black')
    img.save(salida)


ap = argparse.ArgumentParser()
ap.add_argument('nombre')
ap.add_argument('prompt')
ap.add_argument('--duracion', type=float, default=4.0)
ap.add_argument('--seed', type=int, default=1)
ap.add_argument('--muestras', type=int, default=3)
ap.add_argument('--modelo', default='Kimodo-SOMA-RP-v1.2')
args = ap.parse_args()

os.makedirs(CANDIDATOS, exist_ok=True)
nombres = np.array([n for n, _ in SOMASkeleton77.bone_order_names_with_parents])
kimodo_gen = os.path.join(os.path.dirname(sys.executable), 'kimodo_gen')
destinos = []
# una sola llamada (cargar el modelo y el codificador lleva más que generar): --muestras variantes de la semilla
with tempfile.TemporaryDirectory() as tmp:
    stem = os.path.join(tmp, 'clip')
    subprocess.run([kimodo_gen, args.prompt, '--model', args.modelo, '--duration', str(args.duracion),
                    '--seed', str(args.seed), '--num_samples', str(args.muestras), '--output', stem], check=True)
    archivos = [stem + '.npz'] if args.muestras == 1 else [os.path.join(stem, f'clip_{i:02d}.npz')
                                                          for i in range(args.muestras)]
    for i, ruta in enumerate(archivos):
        d = np.load(ruta)
        assert d['posed_joints'].shape[1] == len(nombres), d['posed_joints'].shape
        destino = os.path.join(CANDIDATOS, f'{args.nombre}_s{args.seed}_{i}.npz')
        np.savez_compressed(destino, nombres=nombres, fps=30.0, prompt=args.prompt,
                            **{k: d[k].astype(np.float32) for k in CLAVES})
        destinos.append(destino)
        print('[movimiento]', destino, f'{len(d["posed_joints"])} cuadros')
hoja = os.path.join(CANDIDATOS, f'{args.nombre}_s{args.seed}.png')
hoja_palitos(destinos, hoja)
print('[movimiento] esqueletos:', hoja)
