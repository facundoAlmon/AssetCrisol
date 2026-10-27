# Articulaciones desde la pose 2D (paso `articulaciones`): DWPose (comfyui_controlnet_aux, en ComfyUI) sobre los renders
# ortográficos de `guia` (frente y costado; la escala sale de guia.json) -> modelo.articulaciones en metros. Corre con el
# python3 del sistema. La estimación por rebanadas de rig_lib falla en cuerpos de torso ancho o cabezones (hubo que
# cargarlas a mano en casi todos); en dos humanoides de prueba DWPose cayó a < 5 cm de las cargadas a mano. En muñecos
# (un muñeco de juguete con alas) el detector de personas no los encuentra y sin él los puntos salen corridos:
# la validación anatómica los descarta y quedan las de antes.
import glob, json, os, shutil, sys
from PIL import Image, ImageChops

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '2_malla'))
import generar_malla_pixal3d  # noqa: E402  (correr: encola en ComfyUI y espera)

# índices del formato OpenPose de 18 puntos (R = derecha del personaje = -X en el render de frente)
NARIZ, CUELLO = 0, 1
LADO = {'R': dict(hombro=2, codo=3, muneca=4, cadera=8, rodilla=9, tobillo=10),
        'L': dict(hombro=5, codo=6, muneca=7, cadera=11, rodilla=12, tobillo=13)}


def detectar(cfg, nombre, png, detector):
    """[(u, v, confianza)] x 18 en píxeles del render, o None si no encontró a nadie."""
    vista = os.path.splitext(os.path.basename(png))[0]
    entrada = f'{nombre}_guia_{vista}.png'
    shutil.copy(png, os.path.join(cfg['comfyui_dir'], 'input', entrada))
    pre = f'gp_{nombre}_pose_{vista}'
    w = {'img': {'class_type': 'LoadImage', 'inputs': {'image': entrada}},
         'dw': {'class_type': 'DWPreprocessor', 'inputs': {
             'image': ['img', 0], 'detect_hand': 'disable', 'detect_body': 'enable', 'detect_face': 'disable',
             'resolution': 1024, 'bbox_detector': detector, 'pose_estimator': 'dw-ll_ucoco_384_bs5.torchscript.pt'}},
         'json': {'class_type': 'SavePoseKpsAsJsonFile', 'inputs': {'pose_kps': ['dw', 1], 'filename_prefix': pre}},
         'ver': {'class_type': 'SaveImage', 'inputs': {'images': ['dw', 0], 'filename_prefix': pre}}}
    salidas = generar_malla_pixal3d.correr(cfg, w)
    f = max(glob.glob(os.path.join(cfg['comfyui_dir'], 'output', pre + '*.json')), key=os.path.getmtime)
    d = json.load(open(f))
    if not d or not d[0]['people']:
        return None
    im = salidas['ver']['images'][0]
    shutil.copy(os.path.join(cfg['comfyui_dir'], 'output', im['subfolder'], im['filename']),
                os.path.join(os.path.dirname(png), f'pose_{vista}.png'))
    k = d[0]['people'][0]['pose_keypoints_2d']
    return [tuple(k[i:i + 3]) for i in range(0, len(k), 3)]


def _arriba(png):
    """z (en píxeles) del punto más alto de la figura: el fondo del render es liso."""
    im = Image.open(png).convert('RGB')
    fondo = Image.new('RGB', im.size, im.getpixel((2, 2)))
    caja = ImageChops.difference(im, fondo).convert('L').point(lambda v: 255 if v > 30 else 0).getbbox()
    return caja[1] if caja else None


def _validar(P):
    """Motivo si la pose no es la de un humanoide en pose A (o None si está bien)."""
    for s in 'LR':
        h, c, m = (P[f'{p}_{s}'][1] for p in ('hombro', 'codo', 'muneca'))
        ca, r, t = (P[f'{p}_{s}'][1] for p in ('cadera', 'rodilla', 'tobillo'))
        if not h > c > m:
            return f'brazo {s}: hombro, codo y muñeca no van de arriba a abajo'
        if not ca > r > t:
            return f'pierna {s}: cadera, rodilla y tobillo no van de arriba a abajo'
        if not 0.35 < (ca - r) / (ca - t) < 0.65:
            return f'pierna {s}: la rodilla no está cerca de la mitad ({(ca - r) / (ca - t):.2f})'
        if not 0.3 < (h - c) / (h - m) < 0.7:
            return f'brazo {s}: el codo no está cerca de la mitad ({(h - c) / (h - m):.2f})'
    if not P['nariz'][1] > P['cuello'][1] > max(P['cadera_L'][1], P['cadera_R'][1]):
        return 'nariz, cuello y caderas no van de arriba a abajo'
    return None


def estimar(cfg, nombre, gdir, altura):
    """(articulaciones, None) o (None, motivo)."""
    g = json.load(open(os.path.join(gdir, 'guia.json')))
    px, cz = g['px'], g['centro_z']
    ppu = px / g['ortho']
    a_xz = lambda u, v: ((u - px / 2) / ppu, cz - (v - px / 2) / ppu)  # noqa: E731
    frente = os.path.join(gdir, 'frente.png')
    k = motivo = None
    for detector in ('yolox_l.onnx', 'None'):
        k = detectar(cfg, nombre, frente, detector)
        if not k:
            motivo = 'DWPose no encontró a nadie en el render de frente'
            continue
        if any(k[i][2] < 0.3 for i in [NARIZ, CUELLO] + [j for s in LADO.values() for j in s.values()]):
            motivo, k = 'DWPose no vio todos los puntos del cuerpo', None
            continue
        P = {'nariz': a_xz(*k[NARIZ][:2]), 'cuello': a_xz(*k[CUELLO][:2])}
        for s, idx in LADO.items():
            P.update({f'{p}_{s}': a_xz(*k[i][:2]) for p, i in idx.items()})
        motivo = _validar(P)
        if not motivo:
            break
        k = None
    if not k:
        return None, motivo
    # profundidad: de la pose de costado (frente a la izquierda: y = horizontal); sin ella, la de la plantilla
    kc = detectar(cfg, nombre, os.path.join(gdir, 'costado.png'), 'yolox_l.onnx')
    s = altura / 1.85

    def y(punto, defecto):
        if not kc:
            return defecto * s
        ys = [(kc[i][0] - px / 2) / ppu for i in ([LADO['L'][punto], LADO['R'][punto]] if punto in LADO['L'] else [punto])
              if kc[i][2] >= 0.3]
        return sum(ys) / len(ys) if ys else defecto * s

    X = lambda p: (abs(P[f'{p}_L'][0]) + abs(P[f'{p}_R'][0])) / 2  # noqa: E731  (simétrico, lado +X)
    Z = lambda p: (P[f'{p}_L'][1] + P[f'{p}_R'][1]) / 2  # noqa: E731
    zc, zn, zcad = P['cuello'][1], P['nariz'][1], Z('cadera')
    arriba = _arriba(frente)
    ztop = cz - (arriba - px / 2) / ppu if arriba is not None else altura
    yt, yb = y(CUELLO, 0.02), y('codo', 0.02)
    r = lambda *v: [round(x, 3) for x in v]  # noqa: E731
    zh = Z('hombro') - 0.045 * s     # el punto de DWPose es el borde de arriba del hombro; la articulación va más abajo
    xh = X('hombro') + 0.025 * s
    codo = r(X('codo'), yb, Z('codo'))
    muneca = r(X('muneca'), y('muneca', 0.02), Z('muneca'))
    d = [muneca[0] - codo[0], muneca[2] - codo[2]]
    n = (d[0] ** 2 + d[1] ** 2) ** 0.5 or 1
    mano = r(muneca[0] + d[0] / n * 0.14 * s, muneca[1] - 0.01 * s, muneca[2] + d[1] / n * 0.14 * s)
    rodilla = r(X('rodilla'), y('rodilla', 0.0), Z('rodilla'))
    # DWPose marca el tobillo en el hueso de atrás: la articulación del rig va más adelante (como mucho 3 cm)
    tobillo = r(X('tobillo'), min(y('tobillo', 0.02), 0.03 * s), Z('tobillo'))
    punta = r(tobillo[0] + 0.015 * s, tobillo[1] - 0.2 * s, 0.03 * s)
    J = {
        'root': [[0, 0, 0], [0, 0.4, 0]],
        'hips': [r(0, yt, zcad), r(0, yt, zcad + 0.2 * (zc - zcad))],
        'spine': [r(0, yt, zcad + 0.2 * (zc - zcad)), r(0, yt, zcad + 0.5 * (zc - zcad))],
        'chest': [r(0, yt, zcad + 0.5 * (zc - zcad)), r(0, yt, zc)],
        'neck': [r(0, yt, zc), r(0, yt, zc + 0.5 * (zn - zc))],
        'head': [r(0, yt, zc + 0.5 * (zn - zc)), r(0, yt, ztop)],
        'shoulder.S': [r(0.05 * s, yt, zc - 0.03 * s), r(xh - 0.02 * s, yt, zh)],
        'upper_arm.S': [r(xh, y('hombro', 0.0), zh), codo],
        'forearm.S': [codo, muneca],
        'hand.S': [muneca, mano],
        'thigh.S': [r(X('cadera'), y('cadera', 0.02), zcad), rodilla],
        'shin.S': [rodilla, tobillo],
        'foot.S': [tobillo, punta],
        'foot_ik.S': [tobillo, punta],
        'knee_pole.S': [r(rodilla[0], -0.7 * s, rodilla[2]), r(rodilla[0], -0.8 * s, rodilla[2])],
    }
    return J, None
