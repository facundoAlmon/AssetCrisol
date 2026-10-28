# Paso iso: frames isométricos (trabajo/iso/<anim>/<dir>/NN.png) -> una hoja por animación (filas = 8
# direcciones, columnas = frames) + <n>_iso_meta.json + preview_iso.gif. Todas las celdas de todas las hojas
# comparten tamaño y ancla (el origen = los pies, proyectado), así un solo offset sirve para todo.
import json, os
from PIL import Image, ImageDraw

import armar_tira
import aseprite, posproceso

# carpeta de Blender -> nombre en Godot (el salto isométrico usa las 8 poses: incluye el aterrizaje)
NOMBRES = {'idle': 'idle', 'caminar': 'walk', 'saltar': 'jump', 'respirar': 'idle_loop', 'correr': 'run',
           'rodar': 'roll', 'golpe': 'punch', 'patada': 'kick', 'agacharse': 'crouch', 'defender': 'block',
           'herido': 'hurt', 'morir': 'die', 'lanzar': 'throw', 'brazos_arriba': 'arms_up', 'cargar': 'charge'}


def _ritmo(carpeta):
    for n, c, _, fps, loop, _ in armar_tira.ANIMACIONES:
        if c == carpeta:
            return fps, loop
    return 10, False


def armar(pdir, nombre, pj, dir_iso):
    idir = os.path.join(pdir, 'trabajo', 'iso')
    with open(os.path.join(idir, 'iso.json')) as f:
        info = json.load(f)
    dirs = info['direcciones']
    P, sri = pj['_estilo']['posproceso'], pj.get('isometrico', {}).get('superresolucion', 2)
    ims = {c: [[posproceso.aplicar(Image.open(os.path.join(idir, c, dn, f'{i:02d}.png')).convert('RGBA'), P, sri)
                for i in range(n)]
               for dn in dirs] for c, n in info['frames'].items()}
    todas = [im for filas in ims.values() for fila in filas for im in fila]
    boxes = [im.getchannel('A').point(lambda v: 255 if v > 8 else 0).getbbox() for im in todas]
    boxes = [b for b in boxes if b]
    x0 = min(b[0] for b in boxes) - 2; y0 = min(b[1] for b in boxes) - 2
    x1 = max(b[2] for b in boxes) + 2; y1 = max(b[3] for b in boxes) + 2
    cw, ch = x1 - x0, y1 - y0
    ox, oy = info['origen_px']
    sr = pj.get('isometrico', {}).get('superresolucion', 2)
    os.makedirs(dir_iso, exist_ok=True)
    meta = {'frame_width': cw, 'frame_height': ch, 'direcciones': dirs, 'escala': round(1 / sr, 5),
            'offset': [round(x0 - ox, 2), round(y0 - oy, 2)],   # en píxeles de la hoja (antes de escalar)
            'baldosa_px': pj.get('isometrico', {}).get('baldosa_px', 128), 'animaciones': {}}
    for c, filas in ims.items():
        n = NOMBRES.get(c, c)
        hoja = Image.new('RGBA', (cw * len(filas[0]), ch * len(dirs)), (0, 0, 0, 0))
        for r, fila in enumerate(filas):
            for i, im in enumerate(fila):
                hoja.paste(im.crop((x0, y0, x1, y1)), (i * cw, r * ch))
        archivo = f'{nombre}_iso_{n}.png'
        hoja.save(os.path.join(dir_iso, archivo))
        fps, loop = _ritmo(c)
        meta['animaciones'][n] = {'imagen': archivo, 'frames': len(filas[0]), 'fps': fps, 'loop': loop}
    with open(os.path.join(dir_iso, f'{nombre}_iso_meta.json'), 'w') as f:
        json.dump(meta, f, indent=1)
    aseprite.iso(meta, dir_iso)
    preview(ims, (x0, y0, x1, y1), (ox - x0, oy - y0), os.path.join(pdir, 'preview_iso.gif'))
    print(f'[iso] {len(ims)} hojas de {len(dirs)} direcciones, celdas de {cw}x{ch} '
          f'(en pantalla ~{round(ch / sr)} px de alto) -> {dir_iso}')
    return meta


def preview(ims, caja, origen, out, escala=0.3):
    """GIF: caminata en las 8 direcciones sobre un rombo de baldosas + todas las demás animaciones hacia el
    sureste (fila 1 = 'se'), cada una con su nombre; las cortas se repiten hasta completar el GIF."""
    filas_walk = ims.get('caminar') or next(iter(ims.values()))
    celdas = [(d, f) for d, f in zip(('e', 'se', 's', 'sw', 'w', 'nw', 'n', 'ne'), filas_walk)]
    celdas += [(NOMBRES.get(c, c), ims[c][1]) for c in ims if c != 'caminar']
    cw, ch = int((caja[2] - caja[0]) * escala), int((caja[3] - caja[1]) * escala)
    ox, oy = origen[0] * escala, origen[1] * escala
    cols = 5
    rows = -(-len(celdas) // cols)
    W, H = cw * cols, ch * rows
    frames = []
    for t in range(24):
        im = Image.new('RGBA', (W, H), (60, 66, 72, 255))
        d = ImageDraw.Draw(im)
        for k, (nombre, fila) in enumerate(celdas):
            x, y = k % cols * cw, k // cols * ch
            cx, cy = x + ox, y + oy
            r = cw * 0.3
            d.polygon([(cx - r, cy), (cx, cy - r / 2), (cx + r, cy), (cx, cy + r / 2)], fill=(90, 130, 80, 255),
                      outline=(120, 160, 100, 255))
            d.ellipse((cx - r * 0.35, cy - r * 0.12, cx + r * 0.35, cy + r * 0.12), fill=(40, 60, 40, 255))
            f = fila[t % len(fila)].crop(caja).resize((cw, ch), Image.LANCZOS)
            im.alpha_composite(f, (x, y))
            d.text((x + 4, y + 3), nombre, fill=(230, 230, 230, 255))
        frames.append(im.convert('RGB').quantize(colors=255, method=Image.MEDIANCUT, dither=Image.NONE))
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=90, loop=0, disposal=2)
