# Hoja de control de un personaje terminado (paso `revisar`): lo que hay que mirar antes de darlo por bueno, en una
# sola imagen -> trabajo/revision.png. Filas: cabeza de costado (idle, caminata, correr: ¿mira al frente o al
# cielo?), brazos (codos doblados en caminata, correr, golpe y bloqueo: ¿plastilina?), caminata iso de frente (¿pies
# muy separados, rodillas juntas, puntas adentro?), espalda iso (lo que inventó UltraTex), poses clave y revés (el
# interior de la malla a la vista, en magenta: lo renderiza `blender` en trabajo/reves/).
import json, os
from PIL import Image, ImageChops, ImageDraw, ImageFont

FONDO = (120, 120, 120, 255)
ALTO = 260


def _fuente():
    for f in ('DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(f, 16)
        except OSError:
            pass
    return ImageFont.load_default()


def _union(celdas):
    """Recorta todas las celdas al mismo recuadro (el que contiene a todas): misma escala en la fila."""
    bbs = [c.getbbox() for c in celdas if c.getbbox()]
    if not bbs:
        return celdas
    caja = (min(b[0] for b in bbs), min(b[1] for b in bbs), max(b[2] for b in bbs), max(b[3] for b in bbs))
    return [c.crop(caja) for c in celdas]


def _celda(hoja, f, fw, fh, columnas=13):
    r, c = divmod(f, columnas)
    return hoja.crop((c * fw, r * fh, (c + 1) * fw, (r + 1) * fh))


def _recorte(cel, desde, hasta):
    """Franja vertical [desde, hasta] (fracción del alto de la figura) de una celda."""
    bb = cel.getbbox()
    if not bb:
        return cel
    h = bb[3] - bb[1]
    return cel.crop((max(0, bb[0] - 8), bb[1] + int(h * desde), min(cel.width, bb[2] + 8), bb[1] + int(h * hasta)))


def _fila(titulo, imgs, alto=ALTO):
    imgs = [i.resize((max(1, int(i.width * alto / i.height)), alto)) for i in imgs if i.height]
    ancho = max(400, sum(i.width for i in imgs))
    fila = Image.new('RGBA', (ancho, alto + 26), FONDO)
    ImageDraw.Draw(fila).text((6, 4), titulo, fill=(255, 255, 255, 255), font=_fuente())
    x = 0
    for i in imgs:
        fila.alpha_composite(i, (x, 26))
        x += i.width
    return fila


# % de la figura en magenta a partir del cual avisar, sin contar rodar (de abajo se ve siempre el interior de sombreros
# y cascos). Escaneo de los 40 personajes (2026-10-22): la mayoría < 2 %; con defectos a la vista, 3-28 % (un chibi y
# un lobo con pantalón ancho: el pantalón al agacharse; otro chibi: la suela; un pájaro chibi: cabeza y pecho
# borrados, ver modelo.normales)
UMBRAL_REVES = 3.0


def porcentaje_reves(img):
    """% de los píxeles opacos de un render de trabajo/reves/ que son magenta (caras de atrás)."""
    r, g, b, a = img.split()
    opaco = a.point(lambda v: 255 if v > 128 else 0)
    mag = ImageChops.multiply(ImageChops.multiply(r.point(lambda v: 255 if v > 200 else 0),
                                                  g.point(lambda v: 255 if v < 70 else 0)),
                              ImageChops.multiply(b.point(lambda v: 255 if v > 200 else 0), opaco))
    return 100 * mag.histogram()[255] / max(1, opaco.histogram()[255])


def revisar(pdir, nombre):
    d = os.path.join(pdir, 'godot', 'personajes', nombre)
    meta = json.load(open(os.path.join(d, f'{nombre}_meta.json')))
    hoja = Image.open(os.path.join(d, f'{nombre}_sheet.png')).convert('RGBA')
    fw, fh, A = meta['frame_width'], meta['frame_height'], meta['animaciones']

    def cuadros(nombres, desde=0.0, hasta=1.0, recortar=True):
        out = []
        for anim, i in nombres:
            if anim in A and i < len(A[anim]['frames']):
                cel = _celda(hoja, A[anim]['frames'][i], fw, fh)
                out.append(_recorte(cel, desde, hasta) if recortar else cel)
        return out if recortar else _union(out)

    filas = [
        _fila('cabeza: idle | caminata | correr (mirar al frente, igual que en el idle)',
              cuadros([('idle', 0), ('walk', 0), ('walk', 3), ('walk', 6), ('run', 3)], 0.0, 0.3)),
        _fila('brazos: caminata | correr | golpe | bloqueo (codo marcado, sin plastilina)',
              cuadros([('walk', 1), ('walk', 5), ('run', 3), ('punch', 2), ('punch', 3), ('block', 0)], 0.15, 0.6)),
    ]
    iso = os.path.join(d, 'iso')
    walk = os.path.join(iso, f'{nombre}_iso_walk.png')
    if os.path.exists(walk):
        mi = json.load(open(os.path.join(iso, f'{nombre}_iso_meta.json')))
        hw = Image.open(walk).convert('RGBA')
        iw, ih = mi['frame_width'], mi['frame_height']
        dirs = mi.get('direcciones', ['e', 'se', 's', 'sw', 'w', 'nw', 'n', 'ne'])
        cols = hw.width // iw

        def fila_iso(d_):
            r = dirs.index(d_)
            return _union([hw.crop((c * iw, r * ih, (c + 1) * iw, (r + 1) * ih)) for c in range(cols)])
        filas.append(_fila('caminata iso de frente (s): pies bajo el cuerpo, piernas casi paralelas', fila_iso('s')))
        filas.append(_fila('caminata iso de espalda (n): lo que inventó UltraTex atrás', fila_iso('n')))
    filas.append(_fila('poses: patada | rodar | morir | lanzar | brazos arriba',
                       cuadros([('kick', 3), ('roll', 3), ('die', 5), ('throw', 3), ('arms_up', 3)], recortar=False)))
    reves = os.path.join(pdir, 'trabajo', 'reves')
    if os.path.isdir(reves):
        fs = sorted(f for f in os.listdir(reves) if f.endswith('.png'))
        ims = [Image.open(os.path.join(reves, f)).convert('RGBA') for f in fs]
        peor = max((porcentaje_reves(i) for f, i in zip(fs, ims) if not f.startswith('rodar')), default=0)
        filas.append(_fila(f'revés: magenta = se ve el interior de la malla (agujeros, capas cruzadas); peor pose sin rodar {peor:.1f} %'
                           + ('  << REVISAR' if peor > UMBRAL_REVES else ''), _union(ims)))
        if peor > UMBRAL_REVES:
            print(f'[revisar] AVISO: interior a la vista en {peor:.1f} % de la figura (más de {UMBRAL_REVES} %): '
                  'mirar la fila de revés')
    ancho = max(f.width for f in filas)
    img = Image.new('RGBA', (ancho, sum(f.height for f in filas)), FONDO)
    y = 0
    for f in filas:
        img.alpha_composite(f, (0, y))
        y += f.height
    dst = os.path.join(pdir, 'trabajo', 'revision.png')
    img.convert('RGB').save(dst)
    return dst
