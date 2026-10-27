# Paso sprites de un objeto: renders de trabajo/render/ -> <n>_lateral.png (vista de costado), <n>_iso.png
# (tira con una celda por dirección, ancla común = centro de la base) + <n>_meta.json + preview.png.
import json, math, os
from PIL import Image, ImageDraw

import posproceso

DIRECCIONES = ['e', 'se', 's', 'sw', 'w', 'nw', 'n', 'ne']


def _caja(ims, margen=2, umbral=4):
    bs = [im.getchannel('A').point(lambda v: 255 if v > umbral else 0).getbbox() for im in ims]
    bs = [b for b in bs if b]
    return (min(b[0] for b in bs) - margen, min(b[1] for b in bs) - margen,
            max(b[2] for b in bs) + margen, max(b[3] for b in bs) + margen)


def armar(pdir, nombre, pj, dir_godot):
    rdir = os.path.join(pdir, 'trabajo', 'render')
    with open(os.path.join(rdir, 'render.json')) as f:
        info = json.load(f)
    os.makedirs(dir_godot, exist_ok=True)
    dx, dy, dz = info['dimensiones']
    meta = {'dimensiones': info['dimensiones'], 'colision': pj.get('colision', True)}

    # lateral: origen = centro de la base; colisión = caja de la malla
    L = info['lateral']
    sr = pj.get('lateral', {}).get('superresolucion', 3)
    P = pj['_estilo']['posproceso']
    im = posproceso.aplicar(Image.open(os.path.join(rdir, 'lateral.png')).convert('RGBA'), P, sr)
    x0, y0, x1, y1 = _caja([im])
    im.crop((x0, y0, x1, y1)).save(os.path.join(dir_godot, f'{nombre}_lateral.png'))
    tam_lateral = f'{x1 - x0}x{y1 - y0}'
    ox, oy = L['origen_px']
    ppu = L['ppu'] / sr
    meta['lateral'] = {'imagen': f'{nombre}_lateral.png', 'escala': round(1 / sr, 5),
                       'offset': [round(x0 - ox, 2), round(y0 - oy, 2)],
                       'colision_size': [round(dx * ppu, 1), round(dz * ppu, 1)]}

    # iso: una celda por dirección; huella (polígono en el piso) por dirección para la colisión
    I = info['iso']
    sri = pj.get('isometrico', {}).get('superresolucion', 2)
    n = I['direcciones']
    ims = [Image.open(os.path.join(rdir, f'iso_{k}.png')).convert('RGBA') for k in range(n)]
    for im in ims:  # la cola de la sombra suave (Cycles) deja alfa casi nulo en todo el cuadro: limpiarla
        im.putalpha(im.getchannel('A').point(lambda v: 0 if v < 10 else v))
    ims = [posproceso.aplicar(im, P, sri) for im in ims]
    x0, y0, x1, y1 = _caja(ims, umbral=10)
    cw, ch = x1 - x0, y1 - y0
    tira = Image.new('RGBA', (cw * n, ch), (0, 0, 0, 0))
    for k, im in enumerate(ims):
        tira.paste(im.crop((x0, y0, x1, y1)), (k * cw, 0))
    tira.save(os.path.join(dir_godot, f'{nombre}_iso.png'))
    ox, oy = I['origen_px']
    P = I['ppu'] / sri
    se = math.sin(math.radians(I['elevacion_grados']))
    nombres, huellas = [], []
    for k in range(n):
        r = math.pi / 4 + 2 * math.pi * k / n
        c, s = math.cos(r), math.sin(r)
        fx, fy = s, -c                                  # hacia dónde mira el frente (-Y girado)
        nombres.append(DIRECCIONES[round(math.degrees(math.atan2(-fy, fx)) / 45) % 8])
        esq = [(-dx / 2, -dy / 2), (dx / 2, -dy / 2), (dx / 2, dy / 2), (-dx / 2, dy / 2)]
        huellas.append([[round((x * c - y * s) * P, 1), round(-(x * s + y * c) * se * P, 1)] for x, y in esq])
    meta['iso'] = {'imagen': f'{nombre}_iso.png', 'hframes': n, 'escala': round(1 / sri, 5),
                   'offset': [round(x0 - ox, 2), round(y0 - oy, 2)], 'direcciones': nombres, 'huellas': huellas,
                   'baldosa_px': pj.get('isometrico', {}).get('baldosa_px', 128)}
    with open(os.path.join(dir_godot, f'{nombre}_meta.json'), 'w') as f:
        json.dump(meta, f, indent=1)
    preview(dir_godot, nombre, meta, os.path.join(pdir, 'preview.png'))
    print(f'[sprites] {nombre}: lateral {tam_lateral}, iso {n} direcciones de {cw}x{ch} -> {dir_godot}')
    return meta


def preview(d, nombre, meta, out, e=0.5):
    """lateral sobre una línea de piso + cada dirección iso con su huella (colisión) dibujada"""
    L, I = meta['lateral'], meta['iso']
    lat = Image.open(os.path.join(d, L['imagen']))
    lat = lat.resize((int(lat.width * e), int(lat.height * e)), Image.LANCZOS)
    tira = Image.open(os.path.join(d, I['imagen']))
    cw, ch = tira.width // I['hframes'], tira.height
    pw, ph = int(cw * e), int(ch * e)
    W = 10 + lat.width + 20 + (pw + 10) * I['hframes']
    H = max(lat.height, ph) + 30
    im = Image.new('RGBA', (W, H), (60, 66, 72, 255))
    dr = ImageDraw.Draw(im)
    piso = H - 12
    dr.line((0, piso, lat.width + 20, piso), fill=(70, 140, 60), width=3)
    im.alpha_composite(lat, (10, int(piso + L['offset'][1] * e)))
    for k in range(I['hframes']):
        x, y = 10 + lat.width + 20 + k * (pw + 10), 20
        ox, oy = x - I['offset'][0] * e, y - I['offset'][1] * e      # origen (centro de la base)
        k_px = e / I['escala']                                     # px de pantalla -> px del preview
        dr.polygon([(ox + px * k_px, oy + py * k_px) for px, py in I['huellas'][k]], fill=(90, 130, 80),
                   outline=(200, 200, 90))
        im.alpha_composite(tira.crop((k * cw, 0, (k + 1) * cw, ch)).resize((pw, ph), Image.LANCZOS), (x, y))
        dr.polygon([(ox + px * k_px, oy + py * k_px) for px, py in I['huellas'][k]], outline=(230, 230, 90))
        dr.text((x + 4, 4), I['direcciones'][k], fill=(230, 230, 230))
    im.convert('RGB').save(out)
