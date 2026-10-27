# Texturas repetibles sin depender del modelo (Flux y SDXL no generan "seamless" de verdad).
import numpy as np
from PIL import Image


def repetible(im, parche=0.25, candidatos=40, seed=0, solo_x=False):
    """Textura -> repetible: se corre media vuelta (los bordes, que no calzan, quedan en una cruz en el medio
    y los bordes nuevos sí calzan entre sí) y la cruz se tapa con parches del interior de bordes suaves,
    eligiendo entre `candidatos` el que mejor calza con lo que tapa. Sirve para texturas de "ruido"
    (pasto, tierra, piedras, hojas); en dibujos regulares (tablas, ladrillos) los parches pueden notarse.
    `solo_x`: repetible solo a lo ancho (telón de fondo: abajo el horizonte, arriba el cielo)."""
    a = np.asarray(im.convert('RGB'), dtype=np.float32)
    H, W = a.shape[:2]
    if solo_x:  # el cielo suele aclararse hacia un costado: sin eso, cada parche deja una franja
        a = a - _suave_x(a, W // 4) + a.mean(1, keepdims=True)
    r = np.roll(a, (0 if solo_x else H // 2, W // 2), (0, 1))
    P = int(min(H, W) * parche) // 2 * 2
    t = np.linspace(-1, 1, P)
    d = np.maximum(np.abs(t)[None, :], np.abs(t)[:, None])
    m = np.clip((1 - d) / 0.45, 0, 1)
    m = (m * m * (3 - 2 * m))[..., None]  # 1 en el centro del parche, 0 en su borde
    rng = np.random.default_rng(seed)
    if solo_x:  # sin vuelta de arriba abajo: parches enteros dentro de la imagen
        centros = [(y, W // 2) for y in list(range(P // 2, H - P // 2, P // 2)) + [H - P // 2]]
    else:
        centros = [(y, W // 2) for y in range(0, H, P // 2)]
    if not solo_x:
        centros += [(H // 2, x) for x in range(0, W, P // 2)]
    for cy, cx in centros:
        ys = (np.arange(P) + cy - P // 2) % H  # con vuelta: el parche del borde sigue del otro lado
        xs = (np.arange(P) + cx - P // 2) % W
        dest = r[np.ix_(ys, xs)]
        mejor, err = None, None
        for _ in range(candidatos):  # fuente: el original lejos de sus bordes (que son la costura)
            # solo_x: a la misma altura (el telón cambia de abajo arriba: horizonte, cielo)
            y0 = int(np.clip(cy - P // 2, 0, H - P)) if solo_x else rng.integers(0, H - P)
            x0 = rng.integers(0, W - P)
            src = a[y0:y0 + P, x0:x0 + P]
            e = (((src - dest) ** 2) * (1 - m) * (m > 0.02)).sum()  # calce en la franja de mezcla
            if err is None or e < err:
                mejor, err = src, e
        r[np.ix_(ys, xs)] = mejor * m + dest * (1 - m)
    return Image.fromarray(np.clip(r, 0, 255).astype(np.uint8))


def _suave_x(a, r):
    """Promedio móvil a lo ancho (3 pasadas de caja de radio r/3 ≈ gaussiano), bordes reflejados."""
    k = max(1, r // 3)
    for _ in range(3):
        p = np.pad(a, ((0, 0), (k, k), (0, 0)), mode='reflect')
        c = np.cumsum(p, axis=1, dtype=np.float64)
        c = np.concatenate([np.zeros_like(c[:, :1]), c], axis=1)
        a = ((c[:, 2 * k + 1:] - c[:, :-2 * k - 1]) / (2 * k + 1)).astype(np.float32)
    return a
