#!/usr/bin/env python3
"""Vitrina de los ejemplos para la web: gifs y pngs en docs/vitrina/img/ a partir de lo que dejan `blender`, `sprites`,
`iso` y `tema` de los ejemplos en datos_dir (Cris, sus objetos y los escenarios). python3 + Pillow, no genera nada con IA.

uso: python3 herramientas/4_sprites/vitrina.py [--salida carpeta]

Antes: copiar los ejemplos a datos_dir y correr `blender` + `sprites` (+ `iso` de cris) de cada uno y `tema` de los
escenarios (`tests/humo.py --dejar` deja todo hecho en una carpeta temporal: ASSETCRISOL_CONFIG=<esa>/config.json).

Salida: cris_acciones.gif (acciones mirando al sudoeste), cris_paseo.gif (camina por el piso), cris_direcciones.gif
(las 8 direcciones), taller.gif (Cris entre sus objetos, a la misma escala), <objeto>.gif (gira en sus 4 direcciones) y
<escenario>.png (las texturas elegidas, repetidas).
"""
import json, math, os, sys
from PIL import Image, ImageDraw, ImageFilter

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OBJETOS = ('horno', 'yunque', 'crisol', 'caja_herramientas', 'martillo')   # orden en taller.gif (de izquierda a derecha)
ESCENARIOS = ('taller', 'bosque')
FONDO = (46, 52, 60)
S = 0.5                     # escala de salida: la de los sprites en el juego (render a 2×)


def datos_dir():
    cfg = os.environ.get('ASSETCRISOL_CONFIG') or os.path.join(RAIZ, 'config.json')
    with open(cfg) as f:
        d = json.load(f).get('datos_dir') or RAIZ
    return os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(cfg)), d))


def guardar_gif(cuadros, ruta, ms):
    q = [c.convert('RGB').quantize(colors=255, method=Image.MEDIANCUT, dither=Image.NONE) for c in cuadros]
    q[0].save(ruta, save_all=True, append_images=q[1:], duration=ms, loop=0, disposal=2)
    print(f'[vitrina] {os.path.basename(ruta)}: {len(cuadros)} cuadros, {os.path.getsize(ruta) // 1024} KB')


class Cris:
    """Cuadros iso de un personaje (hojas de `iso`: filas = direcciones, columnas = cuadros)."""

    def __init__(self, d):
        self.dir = os.path.join(d, 'personajes', 'cris', 'godot', 'personajes', 'cris', 'iso')
        with open(os.path.join(self.dir, 'cris_iso_meta.json')) as f:
            self.m = json.load(f)
        self.W, self.H = self.m['frame_width'], self.m['frame_height']
        self.pies = (-self.m['offset'][0], -self.m['offset'][1])
        self.ppm = self.m['baldosa_px'] / math.sqrt(2) * 2          # px de la hoja por metro de piso
        self.hojas = {}

    def anim(self, a):
        return self.m['animaciones'][a]

    def cuadro(self, a, d, f):
        if a not in self.hojas:
            self.hojas[a] = Image.open(os.path.join(self.dir, self.anim(a)['imagen'])).convert('RGBA')
        f %= self.anim(a)['frames']
        i = self.m['direcciones'].index(d)
        c = self.hojas[a].crop((f * self.W, i * self.H, (f + 1) * self.W, (i + 1) * self.H))
        return c.resize((round(self.W * S), round(self.H * S)), Image.LANCZOS)

    def pegar(self, im, a, d, f, x, y):
        sombra(im, x, y, 34, 11)
        im.alpha_composite(self.cuadro(a, d, f), (round(x - self.pies[0] * S), round(y - self.pies[1] * S)))


def sombra(im, x, y, rx, ry):
    m = Image.new('L', im.size, 0)
    ImageDraw.Draw(m).ellipse((x - rx, y - ry, x + rx, y + ry), fill=110)
    im.paste(Image.new('RGBA', im.size, (20, 24, 28, 255)), (0, 0), m.filter(ImageFilter.GaussianBlur(4)))


def piso(im, cx, cy, ancho, textura=None, color=(88, 100, 92)):
    """Rombo iso (2:1) centrado en (cx, cy); con textura, la textura del piso girada 45° y aplastada a la mitad."""
    alto = ancho / 2
    rombo = [(cx - ancho / 2, cy), (cx, cy - alto / 2), (cx + ancho / 2, cy), (cx, cy + alto / 2)]
    m = Image.new('L', im.size, 0)
    ImageDraw.Draw(m).polygon(rombo, fill=255)
    if textura:
        lado = round(ancho / math.sqrt(2))
        t = textura.resize((lado // 3, lado // 3), Image.LANCZOS)        # tres repeticiones por lado
        mosaico = Image.new('RGB', (lado, lado))
        for i in range(3):
            for j in range(3):
                mosaico.paste(t, (i * t.width, j * t.height))
        g = mosaico.rotate(45, expand=True, resample=Image.BICUBIC)
        g = g.resize((round(ancho), round(alto)), Image.LANCZOS)
        capa = Image.new('RGBA', im.size)
        capa.paste(g, (round(cx - ancho / 2), round(cy - alto / 2)))
        im.paste(capa, (0, 0), m)
    else:
        im.paste(Image.new('RGBA', im.size, color + (255,)), (0, 0), m)
    ImageDraw.Draw(im).line(rombo + rombo[:1], fill=(255, 255, 255, 40), width=1)


def baldosas(im, cris, cx, cy, n, lado_m):
    """Grilla iso de n×n baldosas de lado_m metros (para el paseo)."""
    d = ImageDraw.Draw(im)
    for i in range(-n, n):
        for j in range(-n, n):
            pts = []
            for a, b in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                wx, wy = (a - b) * lado_m / math.sqrt(2), (a + b) * lado_m / math.sqrt(2)
                pts.append((cx + wx * cris.ppm * S, cy - wy * cris.ppm * S / 2))
            d.polygon(pts, fill=(92, 104, 96) if (i + j) % 2 else (82, 94, 86), outline=(110, 124, 112))


def acciones(cris, out):
    seq = [('idle_loop', 1), ('walk', 2), ('run', 2), ('punch', 1), ('kick', 1), ('jump', 1), ('roll', 1),
           ('arms_up', 1), ('idle_loop', 1)]
    W, H = 300, 300
    cx, cy = W / 2, H * 0.78
    cuadros, dur = [], []
    for a, veces in seq:
        for f in range(cris.anim(a)['frames'] * veces):
            im = Image.new('RGBA', (W, H), FONDO + (255,))
            baldosas(im, cris, cx, cy, 1, 1.0)
            cris.pegar(im, a, 'sw', f, cx, cy)
            ImageDraw.Draw(im).text((10, H - 18), a, fill=(200, 205, 210))
            cuadros.append(im)
            dur.append(round(1000 / cris.anim(a)['fps']))
        if a == 'arms_up':   # que se vea el final
            cuadros += [cuadros[-1]] * 4
            dur += [100] * 4
    q = [c.convert('RGB').quantize(colors=255, method=Image.MEDIANCUT, dither=Image.NONE) for c in cuadros]
    q[0].save(out, save_all=True, append_images=q[1:], duration=dur, loop=0, disposal=2)
    print(f'[vitrina] {os.path.basename(out)}: {len(cuadros)} cuadros, {os.path.getsize(out) // 1024} KB')


def paseo(cris, out, vel=0.19):
    """Recorre un rombo del piso (se -> ne -> nw -> sw), dos ciclos de caminata por lado. vel: metros por cuadro,
    medida en la hoja (el pie apoyado no patina)."""
    W, H = 600, 400
    cx, cy = W / 2, H * 0.6
    lado = 2 * cris.anim('walk')['frames'] * vel
    wx, wy = -lado / math.sqrt(2), 0.0
    cuadros = []
    for d, ang in (('se', 45), ('ne', 135), ('nw', -135), ('sw', -45)):
        dx, dy = math.sin(math.radians(ang)), -math.cos(math.radians(ang))
        for f in range(2 * cris.anim('walk')['frames']):
            im = Image.new('RGBA', (W, H), FONDO + (255,))
            baldosas(im, cris, cx, cy, 5, 0.68)
            cris.pegar(im, 'walk', d, f, cx + wx * cris.ppm * S, cy - wy * cris.ppm * S / 2)
            cuadros.append(im)
            wx, wy = wx + dx * vel, wy + dy * vel
    guardar_gif(cuadros, out, round(1000 / cris.anim('walk')['fps']))


def direcciones(cris, out):
    orden = ['n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw']
    cw, ch = 150, 190
    cuadros = []
    for f in range(2 * cris.anim('walk')['frames']):
        im = Image.new('RGBA', (cw * 4, ch * 2), FONDO + (255,))
        for k, d in enumerate(orden):
            baldosas(im, cris, k % 4 * cw + cw / 2, k // 4 * ch + ch * 0.86, 1, 0.55)
        for k, d in enumerate(orden):
            cris.pegar(im, 'walk', d, f, k % 4 * cw + cw / 2, k // 4 * ch + ch * 0.86)
        cuadros.append(im)
    guardar_gif(cuadros, out, round(1000 / cris.anim('walk')['fps']))


class Objeto:
    """Hoja iso de un objeto (`sprites`): una fila, una columna por dirección (se, ne, nw, sw), sombra incluida."""

    def __init__(self, d, n, alto_px=None):
        """alto_px: agrandarlo hasta ese alto (máx. 2×, la resolución del render); None = escala del juego."""
        base = os.path.join(d, 'objetos', n, 'godot', 'objetos', n)
        with open(os.path.join(base, f'{n}_meta.json')) as f:
            self.m = json.load(f)['iso']
        hoja = Image.open(os.path.join(base, self.m['imagen'])).convert('RGBA')
        w = hoja.width // self.m['hframes']
        e = min(1.0, max(S, alto_px / hoja.height)) if alto_px else S
        self.pies = (-self.m['offset'][0] * e, -self.m['offset'][1] * e)
        self.cuadros = {d: hoja.crop((i * w, 0, (i + 1) * w, hoja.height)).resize(
            (round(w * e), round(hoja.height * e)), Image.LANCZOS) for i, d in enumerate(self.m['direcciones'])}

    def pegar(self, im, d, x, y):
        im.alpha_composite(self.cuadros[d], (round(x - self.pies[0]), round(y - self.pies[1])))


def giro(obj, out, textura):
    """El objeto en sus 4 direcciones, medio segundo cada una, sobre una baldosa del taller."""
    w = max(c.width for c in obj.cuadros.values())
    h = max(c.height for c in obj.cuadros.values())
    W, H = max(220, w + 60), max(200, h + 70)
    cuadros = []
    for d in obj.m['direcciones']:
        im = Image.new('RGBA', (W, H), FONDO + (255,))
        piso(im, W / 2, H - 45, W * 0.8, textura)
        obj.pegar(im, d, W / 2, H - 45)
        cuadros.append(im)
    guardar_gif(cuadros, out, 600)


def taller(cris, objs, out, textura):
    """Cris (reposo animado) entre sus objetos, todos a la misma escala del juego, sobre el piso del taller."""
    anchos = [max(c.width for c in o.cuadros.values()) for o in objs]
    alto = max([round(cris.H * S)] + [max(c.height for c in o.cuadros.values()) for o in objs])
    sep = 14
    W = sum(anchos) + round(cris.W * S * 0.55) + sep * (len(objs) + 2)
    H = alto + 90
    base = H - 60
    cuadros = []
    for f in range(cris.anim('idle_loop')['frames']):
        im = Image.new('RGBA', (W, H), FONDO + (255,))
        piso(im, W / 2, base, W * 1.05, textura)
        x = sep
        for k, (o, a) in enumerate(zip(objs, anchos)):
            if k == 2:   # Cris en el medio
                cx = x + round(cris.W * S * 0.55) / 2
                cris.pegar(im, 'idle_loop', 'sw', f, cx, base)
                x += round(cris.W * S * 0.55) + sep
            o.pegar(im, 'sw', x + a / 2, base)
            x += a + sep
        cuadros.append(im)
    guardar_gif(cuadros, out, round(1000 / cris.anim('idle_loop')['fps']))


def escenario(d, n, out):
    """Las texturas elegidas tal como las arma `tema` (preview.png), sin la franja blanca de rótulos de arriba."""
    im = Image.open(os.path.join(d, 'escenarios', n, 'preview.png')).convert('RGB')
    gris = im.convert('L')
    y = 0
    while y < im.height and sum(gris.getpixel((x, y)) > 235 for x in range(0, im.width, 4)) > im.width / 4 * 0.8:
        y += 1   # filas casi todas blancas (el texto de los rótulos ocupa poco)
    im = im.crop((0, y, im.width, im.height))
    im.save(out, optimize=True)
    print(f'[vitrina] {os.path.basename(out)}: {im.size}, {os.path.getsize(out) // 1024} KB')


def main():
    salida = sys.argv[sys.argv.index('--salida') + 1] if '--salida' in sys.argv else os.path.join(RAIZ, 'docs', 'vitrina',
                                                                                                    'img')
    os.makedirs(salida, exist_ok=True)
    d = datos_dir()
    cris = Cris(d)
    acciones(cris, os.path.join(salida, 'cris_acciones.gif'))
    paseo(cris, os.path.join(salida, 'cris_paseo.gif'))
    direcciones(cris, os.path.join(salida, 'cris_direcciones.gif'))
    tex = os.path.join(d, 'escenarios', 'taller', 'trabajo', 'texturas', 'piso')
    elegida = json.load(open(os.path.join(d, 'escenarios', 'taller', 'escenario.json')))['texturas']['piso']['elegida']
    textura = Image.open(os.path.join(tex, f'cand_{elegida}.png')).convert('RGB')
    objs = [Objeto(d, n) for n in OBJETOS]
    for n in OBJETOS:
        giro(Objeto(d, n, alto_px=170), os.path.join(salida, f'{n}.gif'), textura)
    taller(cris, objs, os.path.join(salida, 'taller.gif'), textura)
    for n in ESCENARIOS:
        escenario(d, n, os.path.join(salida, f'{n}.png'))


if __name__ == '__main__':
    main()
