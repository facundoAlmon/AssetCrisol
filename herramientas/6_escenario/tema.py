# Paso `tema` de un escenario: de las texturas elegidas a lo que usa el juego (tema.json).
# Cada textura: repetible -> sin luz de fondo (degradés, viñeta) -> "detalle" normalizado: en lineal,
# píxel / promedio × 0.5 (gris medio = el color del tema). El color promedio va al tema; el juego
# multiplica color × detalle × 2 (core/fx/detail.gdshader), así cambiar el color en el tema la tiñe.
# El fondo (vista "fondo") es distinto: color de verdad (sRGB), repetible solo a lo ancho, y arriba se funde
# con el color del cielo, que pasa a `background_color` (así el telón no tiene borde contra el fondo liso).
# Salida: trabajo/tema/{piso,camino,pared,fondo}.png + tema.json + preview.png. Python del sistema.
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw
from repetible import repetible

# clave del escenario -> campo de tema.json (textura, color)
CAMPOS = {'piso': ('floor_detail', 'floor_color'), 'camino': ('path_detail', 'path_color'),
          'pared': ('wall_detail', 'wall_color')}


def a_lineal(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def a_srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)


def hexa(lin):
    return ''.join(f'{int(round(v * 255)):02X}' for v in a_srgb(np.asarray(lin)))


def desenfoque_periodico(a, sigma):
    """Gaussiano con vuelta (la textura es periódica), por FFT."""
    H, W = a.shape[:2]
    fy, fx = np.fft.fftfreq(H)[:, None], np.fft.fftfreq(W)[None, :]
    g = np.exp(-2 * (np.pi * sigma) ** 2 * (fx ** 2 + fy ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(a, axes=(0, 1)) * g[..., None], axes=(0, 1)))


def detalle(im, px, contraste):
    """-> (detalle 8 bits lineal con 0.5 = promedio, color promedio lineal)"""
    lin = a_lineal(np.asarray(repetible(im), dtype=np.float64) / 255)
    media = lin.reshape(-1, 3).mean(0)
    plano = lin / np.maximum(desenfoque_periodico(lin, lin.shape[0] / 6), 1e-4) * media  # sin degradés
    rel = np.clip(plano / np.maximum(media, 1e-4), 0, None) ** contraste
    # el exponente y el recorte bajan el promedio (en texturas muy contrastadas, brillo sobre negro, el
    # juego las veía más oscuras que el tema): volver a llevarlo a 1 por canal
    for _ in range(3):
        rel = np.clip(rel / np.maximum(rel.reshape(-1, 3).mean(0), 1e-4), 0, 2)
    det = rel * 0.5
    img = Image.fromarray((det * 255 + 0.5).astype(np.uint8)).resize((px, px), Image.LANCZOS)
    return img, media


def telon(im, ancho=1024):
    """Fondo pintado -> (imagen repetible a lo ancho con el tercio de arriba fundido al cielo, color del cielo,
    color del suelo: las últimas filas, para el faldón que sigue debajo del telón en el juego)"""
    a = np.asarray(repetible(im, solo_x=True), dtype=np.float64)
    H = a.shape[0]
    cielo = a[:max(1, H // 12)].reshape(-1, 3).mean(0)
    suelo = a[-max(1, H // 7):].reshape(-1, 3).mean(0)
    y = np.arange(H)[:, None, None] / H
    t = np.clip((0.4 - y) / 0.3, 0, 1)  # 1 arriba de todo, 0 desde el 40 % de la altura para abajo
    a = a * (1 - t * t * (3 - 2 * t)) + cielo * (t * t * (3 - 2 * t))
    t = np.clip((y - 0.9) / 0.1, 0, 1)  # el último 10 %, hacia el color del faldón (sin corte con el dibujo)
    a = a * (1 - t * t * (3 - 2 * t)) + suelo * (t * t * (3 - 2 * t))
    img = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8))
    return img.resize((ancho, round(ancho * img.height / img.width)), Image.LANCZOS), cielo, suelo


def main(esc):
    edir = esc['_dir']
    T = esc.get('tema', {})
    px, rep, k = int(T.get('px', 512)), float(T.get('repeticion_m', 4.0)), float(T.get('contraste', 1.0))
    out = os.path.join(edir, 'trabajo', 'tema')
    os.makedirs(out, exist_ok=True)
    tema = {'detail_scale': rep, 'texturas': {}}
    muestras = []
    fondo = None
    for clave, t in esc['texturas'].items():
        if clave not in CAMPOS and t.get('vista') != 'fondo':
            print(f'[tema] AVISO: textura "{clave}" sin campo en el juego (hay: {", ".join(CAMPOS)}); se saltea')
            continue
        seed = t.get('elegida')
        if seed is None:
            sys.exit(f'[tema] falta elegir {clave}: escenario.json > texturas.{clave}.elegida (mirar trabajo/texturas/candidatos.png)')
        src = os.path.join(edir, 'trabajo', 'texturas', clave, f'cand_{seed}.png')
        if not os.path.isfile(src):
            src = os.path.join(edir, str(seed))  # o un archivo propio de la carpeta del escenario
        if not os.path.isfile(src):
            sys.exit(f'[tema] no encuentro la textura elegida de {clave} ({seed})')
        if t.get('vista') == 'fondo':
            fondo, cielo, suelo = telon(Image.open(src), 2 * px)
            fondo.save(os.path.join(out, f'{clave}.png'))
            tema['texturas']['backdrop'] = f'{clave}.png'
            tema['background_color'] = ''.join(f'{int(round(v)):02X}' for v in cielo)
            tema['backdrop_ground'] = ''.join(f'{int(round(v)):02X}' for v in suelo)
            continue
        det, media = detalle(Image.open(src), px, k)
        det.save(os.path.join(out, f'{clave}.png'))
        campo_tex, campo_color = CAMPOS[clave]
        tema['texturas'][campo_tex] = f'{clave}.png'
        if T.get('colores', True):
            tema[campo_color] = hexa(media)
            if clave == 'piso':  # el damero del piso: la segunda baldosa apenas más oscura
                tema['floor_color_2'] = hexa(media * 0.9)
        muestras.append((clave, det, media))
    with open(os.path.join(out, 'tema.json'), 'w') as f:
        json.dump(tema, f, indent=1)

    # preview: lo que va a mostrar el juego (color × detalle × 2), 2×2 repeticiones por textura
    L = 384
    alto_fondo = round(L * len(muestras) * fondo.height / fondo.width / 2) if fondo else 0
    hoja = Image.new('RGB', (max(L * len(muestras), 1), L + 24 + alto_fondo), 'white')
    if fondo:  # dos repeticiones a lo ancho, abajo de las texturas
        f = fondo.resize((L * len(muestras) // 2, alto_fondo), Image.LANCZOS)
        hoja.paste(f, (0, L + 24))
        hoja.paste(f, (f.width, L + 24))
    for i, (clave, det, media) in enumerate(muestras):
        d = np.asarray(det.resize((L // 2, L // 2), Image.LANCZOS), dtype=np.float64) / 255
        rgb = Image.fromarray((a_srgb(d * 2 * media) * 255 + 0.5).astype(np.uint8))
        for a in range(2):
            for b in range(2):
                hoja.paste(rgb, (i * L + a * L // 2, 24 + b * L // 2))
        ImageDraw.Draw(hoja).text((i * L + 8, 6), f'{clave}  #{hexa(media)}', fill='black')
    hoja.save(os.path.join(edir, 'preview.png'))
    print('[tema]', json.dumps({k2: v for k2, v in tema.items() if k2 != 'texturas'}))
    print('[tema] listo:', out, '+ preview.png')
