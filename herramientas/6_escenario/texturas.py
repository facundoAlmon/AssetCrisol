# Paso `texturas` de un escenario: candidatas de cada textura (piso, camino, pared) con ComfyUI.
#  - motor sdxl (por defecto): DreamShaper XL Turbo, ~5 s; con `referencia`, IP-Adapter (style transfer)
#    copia estilo y colores de la imagen (o de su `recorte`) sin copiar la composición.
#  - motor zimage: Z-Image Turbo (Apache-2.0), segundos, sin referencia ni negativo.
#  - motor flux: Flux.2 (receta de 1_imagen), más prolijo pero ~4 min por imagen, sin referencia y no comercial.
#  `texturas.<clave>.motor` pisa el `motor` del escenario para esa textura.
# Qwen-Edit no sirve para esto: con una imagen de un escenario conserva la composición y solo la recolorea.
# Salida: trabajo/texturas/<clave>/cand_<seed>.png (crudas) + trabajo/texturas/candidatos.png (cada una
# ya repetible, en mosaico de 2×2: así se ve si se nota la repetición). Python del sistema (Pillow + numpy).
import glob, json, os, shutil, sys, time, urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), '1_imagen'))
import generar_imagen  # noqa: E402  (servidor, CLI de comfy, receta de Flux)
from repetible import repetible  # noqa: E402

CHECKPOINT = 'dreamshaperXL_v21TurboDPMSDE.safetensors'
IPADAPTER = 'ip-adapter-plus_sdxl_vit-h.safetensors'
CLIP_VISION = 'CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors'
NEGATIVO = ('text, watermark, perspective, horizon, sky, objects, furniture, characters, frame, border, '
            'vignette, shadows, room, scene, gradient')
NEGATIVO_FONDO = ('text, watermark, characters, people, animals, frame, border, vignette, foreground objects, '
                  'close-up, top-down view, buildings in the foreground')
VISTA = {'arriba': 'top-down view', 'frente': 'flat front view'}
# vista "fondo": telón pintado detrás del mapa (horizonte abajo, cielo arriba), repetible solo a lo ancho
TAMANO = {'fondo': (1344, 768)}


def componer_prompt(esc, t):
    E = esc['_estilo']['prompt']
    render = E.get('render_textura') or 'hand-painted stylized toy-like 3D game texture'
    # sin la paleta del estilo: es de personajes ("primarios saturados" vuelve multicolor al follaje);
    # el color va en la descripción de cada textura
    desc = t['descripcion'].strip().rstrip('.')
    if t.get('vista') == 'fondo':
        return (f'Wide side view painted backdrop of {desc} seen from far away, horizon line in the lower third, '
                f'{render}, large simple shapes, soft even lighting, plain clear sky filling the upper half, '
                'horizontally seamless panorama')
    partes = [f"Seamless tileable {VISTA[t.get('vista', 'arriba')]} texture of {desc}", render]
    # formas grandes: con detalle fino, de lejos (cámara iso, mipmaps) el piso se ve como ruido
    partes.append('large simple shapes, low detail, flat even lighting, uniform pattern filling the whole image')
    return ', '.join(partes)


def api(cfg, ruta, datos=None):
    req = urllib.request.Request(cfg['comfyui_url'] + ruta, data=json.dumps(datos).encode() if datos is not None else None,
                                 headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=60).read() or b'{}')


def workflow_sdxl(prompt, seed, prefijo, ref=None, peso=0.8, negativo=NEGATIVO, tam=(1024, 1024)):
    wf = {
        '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': CHECKPOINT}},
        '2': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['1', 1], 'text': prompt}},
        '3': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['1', 1], 'text': negativo}},
        '4': {'class_type': 'EmptyLatentImage', 'inputs': {'width': tam[0], 'height': tam[1], 'batch_size': 1}},
        '5': {'class_type': 'KSampler', 'inputs': {'model': ['13', 0] if ref else ['1', 0], 'positive': ['2', 0],
              'negative': ['3', 0], 'latent_image': ['4', 0], 'seed': seed, 'steps': 8, 'cfg': 2.0,
              'sampler_name': 'dpmpp_sde', 'scheduler': 'karras', 'denoise': 1.0}},
        '6': {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}},
        '7': {'class_type': 'SaveImage', 'inputs': {'images': ['6', 0], 'filename_prefix': prefijo}},
    }
    if ref:
        wf.update({
            '10': {'class_type': 'IPAdapterModelLoader', 'inputs': {'ipadapter_file': IPADAPTER}},
            '11': {'class_type': 'CLIPVisionLoader', 'inputs': {'clip_name': CLIP_VISION}},
            '12': {'class_type': 'LoadImage', 'inputs': {'image': ref}},
            '13': {'class_type': 'IPAdapterAdvanced', 'inputs': {
                'model': ['1', 0], 'ipadapter': ['10', 0], 'image': ['12', 0], 'clip_vision': ['11', 0],
                'weight': peso, 'weight_type': 'style transfer', 'combine_embeds': 'concat',
                'start_at': 0.0, 'end_at': 1.0, 'embeds_scaling': 'V only'}},
        })
    return wf


def correr_sdxl(cfg, wf):
    pid = api(cfg, '/prompt', {'prompt': wf})['prompt_id']
    while True:
        h = api(cfg, f'/history/{pid}')
        if pid in h:
            st = h[pid].get('status', {})
            if st.get('status_str') == 'error':
                sys.exit(f'[texturas] error en ComfyUI: {json.dumps(st)[:1500]}')
            if st.get('completed'):
                return
        time.sleep(1)


def correr_flux(cfg, prompt, seed, prefijo, wf_path, tam=(1024, 1024)):
    comfy, M = generar_imagen.comfy_cli(cfg), cfg['modelos_imagen']
    with open(wf_path, 'w') as f:
        json.dump({'nodes': [], 'links': [], 'last_node_id': 0, 'last_link_id': 0}, f)
    data = generar_imagen.run_json([comfy, '--json', '--where', 'local', 'workflow', 'apply', wf_path, '--ops',
                                    os.path.join(os.path.dirname(AQUI), '1_imagen', 'flux2_t2i.recipe.json'),
                                    '--param', f'prompt={prompt}', '--param', f'seed={seed}',
                                    '--param', f'width={tam[0]}', '--param', f'height={tam[1]}',
                                    '--param', f'filename_prefix={prefijo}'])
    alias = data.get('aliases', {})
    for addr, val in {'unetloadergguf.unet_name': M['flux_unet'], 'cliploader.clip_name': M['flux_clip'],
                      'vaeloader.vae_name': M['flux_vae']}.items():
        a, widget = addr.split('.')
        generar_imagen.run_json([comfy, '--json', '--where', 'local', 'workflow', 'set-widget', wf_path,
                                 f'{alias[a]}.{widget}', val])
    generar_imagen.run_json([comfy, '--json', '--where', 'local', 'run', '--workflow', wf_path, '--wait'])


def subir_referencia(cfg, edir, nombre, clave, t, esc):
    """Copia la referencia (recortada si hay `recorte`) al input de ComfyUI; None si no hay."""
    ref = t.get('referencia') or esc.get('referencia')
    if not ref:
        return None
    from PIL import Image
    ruta = ref if os.path.isabs(ref) else os.path.join(edir, ref)
    if not os.path.isfile(ruta):
        sys.exit(f'[texturas] no encuentro la referencia {ruta}')
    im = Image.open(ruta).convert('RGB')
    if t.get('recorte'):
        im = im.crop(tuple(t['recorte']))
    dst = f'esc_{nombre}_{clave}_ref.png'
    im.save(os.path.join(cfg['comfyui_dir'], 'input', dst))
    return dst


def main(cfg, nombre, esc, claves=None):
    from PIL import Image, ImageDraw
    edir = esc['_dir']
    raiz = os.path.join(edir, 'trabajo', 'texturas')
    os.makedirs(raiz, exist_ok=True)
    generar_imagen.asegurar_servidor(cfg, raiz)
    salida_comfy = os.path.join(cfg['comfyui_dir'], 'output')
    filas = []
    for clave, t in esc['texturas'].items():
        out = os.path.join(raiz, clave)
        os.makedirs(out, exist_ok=True)
        prompt = componer_prompt(esc, t)
        with open(os.path.join(out, 'prompt.txt'), 'w') as f:
            f.write(prompt + '\n')
        hacer = claves is None or clave in claves
        motor = t.get('motor') or esc.get('motor', 'sdxl')
        ref = subir_referencia(cfg, edir, nombre, clave, t, esc) if hacer else None
        if ref and motor != 'sdxl':
            sys.exit('[texturas] la referencia solo anda con motor sdxl (IP-Adapter)')
        hechas = []
        for seed in t['seeds']:
            dst = os.path.join(out, f'cand_{seed}.png')
            if hacer:
                prefijo = f'esc_{nombre}_{clave}_s{seed}'
                print(f'[texturas] {clave} seed {seed}{" (con referencia)" if ref else ""}...', flush=True)
                fondo = t.get('vista') == 'fondo'
                tam = TAMANO['fondo'] if fondo else (1024, 1024)
                if motor == 'flux':
                    correr_flux(cfg, prompt, seed, prefijo, os.path.join(out, f'wf_s{seed}.json'), tam)
                elif motor == 'zimage':
                    correr_sdxl(cfg, generar_imagen.workflow_zimage(cfg, prompt, seed, prefijo, *tam))
                else:
                    correr_sdxl(cfg, workflow_sdxl(prompt, seed, prefijo, ref, esc.get('ip_peso', 0.8),
                                                   NEGATIVO_FONDO if fondo else NEGATIVO, tam))
                shutil.copy(max(glob.glob(os.path.join(salida_comfy, prefijo + '_*.png')), key=os.path.getmtime), dst)
            if os.path.exists(dst):
                hechas.append((seed, dst))
        filas.append((clave, t.get('vista') == 'fondo', hechas))

    # hoja de contacto: una fila por textura, cada candidata ya repetible (2×2; el fondo, 2 a lo ancho)
    L = 256
    celdas = []  # (x, y, imagen, rótulo)
    y = 0
    for clave, fondo, hechas in filas:
        alto = 0
        for j, (seed, p) in enumerate(hechas):
            im = Image.open(p)
            if fondo:
                t = repetible(im, solo_x=True)
                t = t.resize((L, round(L * t.height / t.width)), Image.LANCZOS)
                celda = Image.new('RGB', (2 * L, t.height))
                celda.paste(t, (0, 0))
                celda.paste(t, (L, 0))
            else:
                t = repetible(im).resize((L // 2, L // 2), Image.LANCZOS)
                celda = Image.new('RGB', (L, L))
                for a in range(2):
                    for b in range(2):
                        celda.paste(t, (a * L // 2, b * L // 2))
            celdas.append((j * celda.width, y, celda, f'{clave} - seed {seed}'))
            alto = celda.height
        y += alto
    hoja = Image.new('RGB', (max(x + c.width for x, _, c, _ in celdas), y), 'white')
    d = ImageDraw.Draw(hoja)
    for x, yy, c, rotulo in celdas:
        hoja.paste(c, (x, yy))
        d.rectangle((x + 4, yy + 4, x + 130, yy + 20), fill='white')
        d.text((x + 8, yy + 6), rotulo, fill='black')
    hoja.save(os.path.join(raiz, 'candidatos.png'))
    print('[texturas] listo:', os.path.join(raiz, 'candidatos.png'))
    print('[texturas] elegí una por textura (escenario.json > texturas.<clave>.elegida) y corré `tema`')
