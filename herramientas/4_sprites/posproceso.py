# Posproceso de estilo (estilos/<n>.json > posproceso), igual para todo lo renderizado de un estilo:
# saturación / contraste / brillo, nitidez, tinte hacia un color y contorno opcional. Se aplica a cada render
# antes de recortar (el contorno agranda la silueta).
from PIL import Image, ImageChops, ImageEnhance, ImageFilter


def activo(P):
    return any((P.get('saturacion', 1) != 1, P.get('contraste', 1) != 1, P.get('brillo', 1) != 1,
                P.get('tinte') and P.get('tinte_fuerza', 0) > 0, P.get('contorno_px', 0) > 0, P.get('nitidez', 0) > 0))


def aplicar(im, P, superres=1):
    """im RGBA -> RGBA. contorno_px está en píxeles de pantalla (se multiplica por la superresolución).
    El contorno sale solo de la parte opaca (alfa > 50 %): la sombra suave de los objetos no se contornea."""
    if not activo(P):
        return im
    rgb, a = im.convert('RGB'), im.getchannel('A')
    for clave, enh in (('saturacion', ImageEnhance.Color), ('contraste', ImageEnhance.Contrast),
                       ('brillo', ImageEnhance.Brightness)):
        if P.get(clave, 1) != 1:
            rgb = enh(rgb).enhance(P[clave])
    if P.get('nitidez', 0) > 0:  # máscara de enfoque (% de fuerza), radio en píxeles de pantalla
        rgb = rgb.filter(ImageFilter.UnsharpMask(radius=1.2 * superres, percent=int(P['nitidez']), threshold=2))
    if P.get('tinte') and P.get('tinte_fuerza', 0) > 0:
        tinte = ImageChops.multiply(rgb, Image.new('RGB', rgb.size, tuple(P['tinte'])))
        rgb = Image.blend(rgb, tinte, P['tinte_fuerza'])
    out = Image.merge('RGBA', (*rgb.split(), a))
    n = round(P.get('contorno_px', 0) * superres)
    if n > 0:
        solido = a.point(lambda v: 255 if v > 128 else 0)
        borde = solido.filter(ImageFilter.MaxFilter(2 * n + 1)).filter(ImageFilter.GaussianBlur(0.6 * superres))
        fondo = Image.new('RGBA', im.size, (*P['contorno_color'], 0))
        fondo.putalpha(borde)
        fondo.alpha_composite(out)
        out = fondo
    return out
