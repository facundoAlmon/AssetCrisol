# Paso 4: frames renderizados -> hoja de sprites para el juego + meta + GIF de preview + retratos.
# Orden fijo (contrato con el script del jugador en el juego): 0 quieto, 1-8 caminata, 9 despegue, 10 subida, 11 cima,
# 12 caída; las animaciones nuevas van SIEMPRE después (ver ANIMACIONES). La hoja es una grilla de COLUMNAS
# columnas (índice = fila * COLUMNAS + columna, como Sprite2D con hframes/vframes): la fila 0 es la tira original.
# Todas las celdas comparten ancla: centro horizontal = eje del personaje, piso = mismo renglón.
import json, os
from PIL import Image, ImageDraw

import aseprite, posproceso

COLUMNAS = 13
# nombre en Godot, carpeta de frames, índices dentro de la carpeta, fps, loop, nombres de cada frame
ANIMACIONES = [
    ('idle', 'idle', [0], 1, False, ['idle']),
    ('walk', 'caminar', range(8), 12, True, None),
    ('jump', 'saltar', [2, 3, 4, 5], 8, False, ['jump_takeoff', 'jump_rise', 'jump_apex', 'jump_fall']),
    # --- desde acá, agregadas después del contrato original (índices 13+) ---
    ('idle_loop', 'respirar', range(8), 6, True, None),
    ('run', 'correr', range(12), 24, True, None),
    ('roll', 'rodar', range(8), 16, False, None),
    ('punch', 'golpe', range(7), 14, False, None),
    ('kick', 'patada', range(8), 14, False, None),
    ('crouch', 'agacharse', [0], 1, False, ['crouch']),
    ('block', 'defender', [0], 1, False, ['block']),
    ('land', 'saltar', [6], 1, False, ['jump_land']),
    ('hurt', 'herido', range(3), 10, False, None),
    ('die', 'morir', range(6), 10, False, None),
    # poderes (lanzar algo, brazos arriba, cargar energía)
    ('throw', 'lanzar', range(6), 14, False, None),
    ('arms_up', 'brazos_arriba', range(6), 10, False, None),
    ('charge', 'cargar', range(6), 10, True, None),
]


def orden():
    """[(carpeta, índice)], [nombre de cada frame], {animación: {frames, fps, loop}}"""
    celdas, nombres, anims = [], [], {}
    for n, carpeta, idx, fps, loop, nfr in ANIMACIONES:
        idx = list(idx)
        anims[n] = {'frames': list(range(len(celdas), len(celdas) + len(idx))), 'fps': fps, 'loop': loop}
        celdas += [(carpeta, i) for i in idx]
        nombres += nfr or [f'{n}{i}' for i in range(len(idx))]
    return celdas, nombres, anims


ORDEN, NOMBRES, ANIMS = orden()


def recortar_alfa(im, margen=4):
    b = im.getchannel('A').point(lambda v: 255 if v > 8 else 0).getbbox()
    return im.crop((b[0] - margen, b[1] - margen, b[2] + margen, b[3] + margen))


def recorte_imagen(pdir, caja):
    """El encuadre del retrato (caja en unidades del modelo, de retrato.json) recortado de la imagen que
    generó la malla (trabajo/malla/sin_fondo.png). Blender normaliza la malla a lo que se ve en la imagen:
    pies en z=0, arriba en z=altura, centrada en x; así que el bbox del alfa es esa misma caja."""
    im = Image.open(os.path.join(pdir, 'trabajo', 'malla', 'sin_fondo.png')).convert('RGBA')
    bx0, by0, bx1, by1 = im.getchannel('A').point(lambda v: 255 if v > 128 else 0).getbbox()
    s = (by1 - by0) / caja['altura']                       # píxeles por unidad
    cx = (bx0 + bx1) / 2
    box = [round(cx + caja['x'][0] * s), round(by1 - caja['z'][1] * s),
           round(cx + caja['x'][1] * s), round(by1 - caja['z'][0] * s)]
    # crop fuera de la imagen deja transparente (con RGBA)
    return im.crop(box).resize((caja['ancho_px'], caja['alto_px']), Image.LANCZOS)


def retratos(pdir, nombre, pj, dir_godot, meta):
    """Selector de personajes y diálogos: retrato (cabeza y hombros) y cuerpo entero de frente.
    retrato.fuente = "imagen" (por defecto): recorte de la imagen que generó la malla, con el encuadre que
    calcula Blender; "modelo": el render del modelo 3D (también si falta la imagen o retrato.json)."""
    P, sr = pj['_estilo']['posproceso'], pj['sprites']['superresolucion']
    rdir = os.path.join(pdir, 'trabajo', 'retrato')
    if not os.path.exists(os.path.join(rdir, 'retrato.png')):
        return
    caja = os.path.join(rdir, 'retrato.json')
    img = os.path.join(pdir, 'trabajo', 'malla', 'sin_fondo.png')
    if pj.get('retrato', {}).get('fuente', 'imagen') == 'imagen' and os.path.exists(caja) and os.path.exists(img):
        with open(caja) as f:
            retrato = recorte_imagen(pdir, json.load(f))
        print('[sprites] retrato recortado de trabajo/malla/sin_fondo.png')
    else:
        retrato = Image.open(os.path.join(rdir, 'retrato.png')).convert('RGBA')
    # el retrato se ve grande en la selección: contorno a escala ~2x (512 px vs ~180 en el juego)
    posproceso.aplicar(retrato, P, 2).save(os.path.join(dir_godot, f'{nombre}_retrato.png'))
    recortar_alfa(posproceso.aplicar(Image.open(os.path.join(rdir, 'frente.png')).convert('RGBA'), P, sr)).save(
        os.path.join(dir_godot, f'{nombre}_frente.png'))
    meta['retrato'], meta['frente'] = f'{nombre}_retrato.png', f'{nombre}_frente.png'


def armar(pdir, nombre, pj, dir_godot):
    fdir = os.path.join(pdir, 'trabajo', 'frames')
    P, sr = pj['_estilo']['posproceso'], pj['sprites']['superresolucion']
    frames = [posproceso.aplicar(Image.open(os.path.join(fdir, a, f'{i:02d}.png')).convert('RGBA'), P, sr)
              for a, i in ORDEN]
    W, H = frames[0].size
    boxes = [f.getchannel('A').point(lambda v: 255 if v > 8 else 0).getbbox() for f in frames]
    x0 = min(b[0] for b in boxes) - 2; y0 = min(b[1] for b in boxes) - 2
    x1 = max(b[2] for b in boxes) + 2; y1 = max(b[3] for b in boxes) + 2
    half = max(W // 2 - x0, x1 - W // 2)          # simétrico respecto al eje (el centro del render)
    x0, x1 = W // 2 - half, W // 2 + half
    cw, ch = x1 - x0, y1 - y0
    filas = -(-len(frames) // COLUMNAS)
    tira = Image.new('RGBA', (cw * COLUMNAS, ch * filas), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        tira.paste(f.crop((x0, y0, x1, y1)), (i % COLUMNAS * cw, i // COLUMNAS * ch))

    # línea de los pies: último renglón bien opaco del frame quieto
    a = frames[0].getchannel('A').crop((x0, y0, x1, y1))
    pie = max(y for y in range(ch) if max(a.crop((0, y, cw, y + 1)).getdata()) >= 128) + 1
    esc = 1.0 / sr
    alto = pj['sprites']['alto_en_pantalla_px']
    meta = {
        'imagen': f'{nombre}_sheet.png', 'frame_width': cw, 'frame_height': ch, 'frames': len(frames),
        'hframes': COLUMNAS, 'vframes': filas, 'orden': NOMBRES, 'animaciones': ANIMS, 'escala': round(esc, 5),
        'offset': [round(-cw / 2 * esc, 3), round(-pie * esc, 3)],
        'pie_y_px': pie, 'alto_en_pantalla_px': alto,
        'colision_sugerida': {'size': [round(alto * 0.24), round(alto * 0.77)], 'position': [0, -round(alto * 0.385)]},
    }
    os.makedirs(dir_godot, exist_ok=True)
    tira.save(os.path.join(dir_godot, meta['imagen']))
    retratos(pdir, nombre, pj, dir_godot, meta)
    with open(os.path.join(dir_godot, f'{nombre}_meta.json'), 'w') as f:
        json.dump(meta, f, indent=1)
    aseprite.personaje(meta, dir_godot)
    preview(frames, (x0, y0, x1, y1), meta, os.path.join(pdir, 'preview.gif'))
    print(f'[sprites] hoja {tira.size[0]}x{tira.size[1]} ({len(frames)} frames de {cw}x{ch}, '
          f'{COLUMNAS}x{filas}), en pantalla ~{round(ch * esc)} px')
    return meta


def preview(frames, caja, meta, out, escala=0.4, columnas=5):
    """GIF con todas las animaciones en loop (con sombra de referencia en el piso)."""
    cells = [f.crop(caja) for f in frames]
    cells = [c.resize((int(c.width * escala), int(c.height * escala)), Image.LANCZOS) for c in cells]
    cw, ch = cells[0].size
    lift = int(ch * 0.3)
    pie = int(meta['pie_y_px'] * escala)
    anims = list(meta['animaciones'].items())
    filas = -(-len(anims) // columnas)
    rh = ch + lift + 24
    W, H = cw * columnas, rh * filas
    subida = {'jump': [0.35, 0.8, 1.0, 0.55]}
    out_frames = []
    for t in range(24):
        im = Image.new('RGBA', (W, H), (78, 78, 78, 255))
        d = ImageDraw.Draw(im)
        capa = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        dc = ImageDraw.Draw(capa)
        for k, (n, A) in enumerate(anims):
            x, y = k % columnas * cw, k // columnas * rh
            floor = y + rh - 8
            d.rectangle((x, floor, x + cw - 2, floor + 8), fill=(70, 140, 60, 255))
            d.text((x + 4, y + 2), n, fill=(230, 230, 230))
            fr = A['frames']
            # a ~12 fps; las que no hacen loop se quedan en el último frame hasta reiniciar
            j = t % len(fr) if A['loop'] else min(t // 2, len(fr) + 3) % (len(fr) + 4)
            j = min(j, len(fr) - 1)
            h = subida.get(n, [0] * len(fr))[j]
            kk = max(0.0, 1 - h * 0.7)
            rx, ry = cw * 0.2 * (0.55 + 0.45 * kk), cw * 0.045 * (0.55 + 0.45 * kk)
            for i in range(6):
                r = 1 - i / 6 * 0.6
                dc.ellipse((x + cw / 2 - rx * r, floor - ry * r, x + cw / 2 + rx * r, floor + ry * r),
                           fill=(0, 0, 0, int(255 * 0.4 * kk / 6 * 1.6)))
            capa.alpha_composite(cells[fr[j]], (x, int(floor - pie - h * lift)))
        im.alpha_composite(capa)
        out_frames.append(im.convert('RGB').quantize(colors=255, method=Image.MEDIANCUT, dither=Image.NONE))
    out_frames[0].save(out, save_all=True, append_images=out_frames[1:], duration=85, loop=0, disposal=2)
