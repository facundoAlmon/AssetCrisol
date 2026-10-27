# Dibuja la grilla (cada 0.1 unidades) y las articulaciones sobre los renders de `guia`
# -> trabajo/guia/guia.png. Corre con el python3 del sistema (PIL), lo llama pipeline.py.
import json, os
from PIL import Image, ImageDraw


def dibujar(gdir):
    with open(os.path.join(gdir, 'guia.json')) as f:
        g = json.load(f)
    px, ortho, cz = g['px'], g['ortho'], g['centro_z']
    ppu = px / ortho

    def P(h, z):  # (coordenada horizontal, z) -> pixel
        return (px / 2 + h * ppu, px / 2 - (z - cz) * ppu)

    J = g['articulaciones']
    lienzo = Image.new('RGB', (px * 2, px), 'white')
    for k, (vista, eje) in enumerate((('frente', 0), ('costado', 1))):
        im = Image.open(os.path.join(gdir, f'{vista}.png')).convert('RGB')
        d = ImageDraw.Draw(im)
        for i in range(-12, 13):
            x = P(i / 10, 0)[0]
            d.line([(x, 0), (x, px)], fill=(255, 0, 0) if i == 0 else (200, 140, 140))
            d.text((x + 2, 2), f'{i / 10:.1f}', fill=(150, 0, 0))
        for i in range(0, 30):
            y = P(0, i / 10)[1]
            d.line([(0, y), (px, y)], fill=(140, 140, 220))
            d.text((2, y + 2), f'{i / 10:.1f}', fill=(0, 0, 150))
        for n, (h, t) in J.items():
            lados = (1, -1) if n.endswith('.S') and eje == 0 else (1,)
            lados = [s for s in lados if not n.endswith('.S') or n[:-2] + ('.L' if s > 0 else '.R') not in J]
            for s in lados:
                a = P(h[eje] * (s if eje == 0 else 1), h[2]); b = P(t[eje] * (s if eje == 0 else 1), t[2])
                ctrl = n.startswith(('foot_ik', 'knee_pole', 'root'))
                d.line([a, b], fill=(255, 150, 0) if ctrl else (0, 170, 0), width=3)
                d.ellipse((a[0] - 5, a[1] - 5, a[0] + 5, a[1] + 5), fill=(255, 220, 0), outline=(0, 0, 0))
        d.text((10, px - 20), f'{vista}  (ejes: {"X" if eje == 0 else "Y, frente a la izquierda"} / Z)  '
                              f'articulaciones: {g["origen"]}', fill=(0, 0, 0))
        lienzo.paste(im, (k * px, 0))
    lienzo.save(os.path.join(gdir, 'guia.png'))
    return os.path.join(gdir, 'guia.png')
