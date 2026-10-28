# Hojas para otros motores: un .json estilo Aseprite (json-array) junto a cada hoja PNG, que leen Phaser
# (`load.aseprite` + `anims.createFromAseprite`), Defold, Unity (importadores de Aseprite/TexturePacker) y casi todo lo
# que lee TexturePacker. Cuadros con nombre y duración, una etiqueta (frameTag) por animación y un slice `pie` con el
# pivote (los pies del personaje, el centro de la base del objeto) en cada cuadro. Las claves que no son de Aseprite
# van en `meta.assetcrisol`.
import json, os
from PIL import Image


def _hoja(ruta_png, celdas, etiquetas, pivote, extra):
    """celdas: [(nombre, x, y, w, h, ms)]; etiquetas: [(nombre, desde, hasta, loop)]; pivote: (x, y) en la celda."""
    W, H = Image.open(ruta_png).size
    w, h = celdas[0][3], celdas[0][4]
    d = {
        'frames': [{'filename': n, 'frame': {'x': x, 'y': y, 'w': cw, 'h': ch}, 'rotated': False, 'trimmed': False,
                    'spriteSourceSize': {'x': 0, 'y': 0, 'w': cw, 'h': ch}, 'sourceSize': {'w': cw, 'h': ch},
                    'duration': ms} for n, x, y, cw, ch, ms in celdas],
        'meta': {
            'app': 'AssetCrisol', 'version': '1', 'image': os.path.basename(ruta_png), 'format': 'RGBA8888',
            'size': {'w': W, 'h': H}, 'scale': '1',
            'frameTags': [dict({'name': n, 'from': a, 'to': b, 'direction': 'forward'}, **({} if loop else {'repeat': '1'}))
                          for n, a, b, loop in etiquetas],
            'slices': [{'name': 'pie', 'color': '#0000ffff',
                        'keys': [{'frame': 0, 'bounds': {'x': 0, 'y': 0, 'w': w, 'h': h},
                                  'pivot': {'x': round(pivote[0]), 'y': round(pivote[1])}}]}],
            'assetcrisol': extra,
        },
    }
    ruta = os.path.splitext(ruta_png)[0] + '.json'
    with open(ruta, 'w') as f:
        json.dump(d, f, indent=1)
    return ruta


def _ms(fps):
    return round(1000 / max(fps, 1))


def personaje(meta, dir_godot):
    """<n>_sheet.json: la hoja de costado (grilla de hframes columnas, `orden` da el nombre de cada cuadro)."""
    cw, ch, cols = meta['frame_width'], meta['frame_height'], meta['hframes']
    dur = {}
    for a in meta['animaciones'].values():
        for i in a['frames']:
            dur.setdefault(i, _ms(a['fps']))
    celdas = [(n, i % cols * cw, i // cols * ch, cw, ch, dur.get(i, 100)) for i, n in enumerate(meta['orden'])]
    etiquetas = []
    for n, a in meta['animaciones'].items():
        f = a['frames']
        if f == list(range(f[0], f[0] + len(f))):   # Aseprite solo tiene rangos; todas las de la hoja lo son
            etiquetas.append((n, f[0], f[-1], a['loop']))
    return _hoja(os.path.join(dir_godot, meta['imagen']), celdas, etiquetas, (cw / 2, meta['pie_y_px']),
                 {'escala': meta['escala'], 'alto_en_pantalla_px': meta['alto_en_pantalla_px']})


def iso(meta, dir_iso):
    """<n>_iso_<anim>.json por hoja: filas = direcciones, columnas = cuadros; una etiqueta <anim>_<dir> por fila."""
    cw, ch = meta['frame_width'], meta['frame_height']
    pivote = (-meta['offset'][0], -meta['offset'][1])
    rutas = []
    for n, a in meta['animaciones'].items():
        k, ms = a['frames'], _ms(a['fps'])
        celdas = [(f'{n}_{d}_{i}', i * cw, r * ch, cw, ch, ms) for r, d in enumerate(meta['direcciones']) for i in range(k)]
        etiquetas = [(f'{n}_{d}', r * k, r * k + k - 1, a['loop']) for r, d in enumerate(meta['direcciones'])]
        rutas.append(_hoja(os.path.join(dir_iso, a['imagen']), celdas, etiquetas, pivote,
                           {'escala': meta['escala'], 'baldosa_px': meta['baldosa_px'], 'direcciones': meta['direcciones']}))
    return rutas


def objeto(meta, dir_godot):
    """<n>_iso.json: una celda por dirección (etiqueta = la dirección)."""
    I = meta['iso']
    ruta = os.path.join(dir_godot, I['imagen'])
    W, H = Image.open(ruta).size
    cw = W // I['hframes']
    celdas = [(d, k * cw, 0, cw, H, 100) for k, d in enumerate(I['direcciones'])]
    etiquetas = [(d, k, k, False) for k, d in enumerate(I['direcciones'])]
    return _hoja(ruta, celdas, etiquetas, (-I['offset'][0], -I['offset'][1]),
                 {'escala': I['escala'], 'baldosa_px': I['baldosa_px'], 'huellas': I['huellas']})
