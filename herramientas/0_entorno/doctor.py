# `crisol doctor`: revisa la instalación (config, rutas, venvs, Blender, ComfyUI y sus nodos, modelos, GPU) y dice qué
# falta, cómo arreglarlo y qué pasos quedan deshabilitados. Solo lee: no genera, no carga modelos ni toca la GPU (lee
# nvidia-smi y, si ComfyUI está corriendo, su /queue). Python del sistema, sin dependencias: anda aunque falte Pillow
# o config.json. `--json` para agentes; sale con 1 si algún paso quedó deshabilitado por algo obligatorio.
import json, os, re, shutil, subprocess, sys, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OK, AVISO, FALTA = 'ok', 'aviso', 'falta'
MARCA = {OK: '✔', AVISO: '!', FALTA: '✘'}

# Modelos de ComfyUI por grupo: (carpetas dentro de models/ donde puede estar, nombre o clave de modelos_imagen).
# Las carpetas van de a pares porque ComfyUI trata como una sola unet/diffusion_models y clip/text_encoders.
DM, TE = ('diffusion_models', 'unet'), ('text_encoders', 'clip')
MODELOS = {
    'qwen': [(DM, '@qwen_unet'), (('loras',), '@qwen_lora'), (TE, 'qwen_2.5_vl_7b_fp8_scaled.safetensors'),
             (('vae',), 'qwen_image_vae.safetensors')],
    'zimage': [(DM, '@zimage_unet'), (TE, '@zimage_clip'), (('vae',), '@zimage_vae')],
    'flux2': [(DM, '@flux_unet'), (TE, '@flux_clip'), (('vae',), '@flux_vae')],
    'pixal3d': [(DM, 'pixal3d_int8_convrot.safetensors'), (DM, 'pixal3d_multiview_int8_convrot.safetensors'),
                (('vae',), 'trellis_2_shape_vae_bf16.safetensors'), (('vae',), 'trellis_2_texture_vae_bf16.safetensors'),
                (('clip_vision',), 'dino_v3_L_naf_fp32.safetensors'),
                (('geometry_estimation',), 'moge_2_vitl_normal_fp16.safetensors'),
                (('background_removal',), 'birefnet.safetensors')],
    'ultratex': [(DM, 'flux-2-klein-base-9b-fp8.safetensors'), (('loras',), 'ultratex_flux2.safetensors'),
                 (('ultratex',), 'ultratex_flux2_decoder.pt'), (TE, 'qwen_3_8b_fp8mixed.safetensors'),
                 (('vae',), 'flux2-vae.safetensors')],
    'sdxl': [(('checkpoints',), 'dreamshaperXL_v21TurboDPMSDE.safetensors')],
    'ipadapter': [(('ipadapter',), 'ip-adapter-plus_sdxl_vit-h.safetensors'),
                  (('clip_vision',), 'CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors')],
}
# nodos extra de ComfyUI: grupo -> (nombres posibles de la carpeta en custom_nodes, repo)
NODOS = {
    'gguf': (('comfyui-gguf',), 'https://github.com/city96/ComfyUI-GGUF'),
    'ultratex': (('comfyui-ultratex',), 'https://github.com/visualbruno/ComfyUI-UltraTex'),
    'dwpose': (('comfyui_controlnet_aux',), 'https://github.com/Fannovel16/comfyui_controlnet_aux'),
    'ipadapter': (('comfyui_ipadapter_plus',), 'https://github.com/cubiq/ComfyUI_IPAdapter_plus'),
}
# pesos de TRELLIS.2 en la caché de Hugging Face (HF_HOME de env_modelos)
HF_TRELLIS = ('microsoft/TRELLIS.2-4B', 'microsoft/TRELLIS-image-large', 'facebook/dinov3-vitl16-pretrain-lvd1689m')


class Revision:
    def __init__(self):
        self.items = []     # {grupo, nombre, estado, detalle, arreglo}
        self.tiene = {}     # capacidad -> bool (lo que usan los pasos)

    def anotar(self, grupo, nombre, estado, detalle='', arreglo=''):
        self.items.append({'grupo': grupo, 'nombre': nombre, 'estado': estado, 'detalle': detalle, 'arreglo': arreglo})
        return estado == OK


def correr(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, str(e)


def placeholder(v):
    return isinstance(v, str) and v.startswith('/ruta/a')


def libre_gb(ruta):
    while ruta and not os.path.exists(ruta):
        ruta = os.path.dirname(ruta)
    try:
        return shutil.disk_usage(ruta or '/').free / 1e9
    except OSError:
        return None


def version_paquete(py, paquete):
    """Versión de un paquete en otro intérprete, sin importarlo (importlib.metadata: no carga torch ni nada)."""
    cod, out = correr([py, '-c', f'import importlib.metadata as m; print(m.version("{paquete}"))'])
    return out.splitlines()[-1] if cod == 0 and out else None


def sistema(R):
    G = 'Sistema'
    v = sys.version_info
    R.anotar(G, 'python3', OK if v >= (3, 10) else AVISO, f'{v.major}.{v.minor}.{v.micro}',
             '' if v >= (3, 10) else 'probado con 3.10+')
    try:
        import PIL
        R.tiene['pillow'] = R.anotar(G, 'Pillow', OK, PIL.__version__)
    except ImportError:
        R.tiene['pillow'] = R.anotar(G, 'Pillow', FALTA, 'el python3 del sistema no lo tiene',
                                     'sudo apt install python3-pil (o pip install --user pillow)')
    try:
        import numpy
        R.tiene['numpy'] = R.anotar(G, 'numpy', OK, numpy.__version__)
    except ImportError:   # texturas y tema se relanzan con el python de ComfyUI (ver comfyui())
        R.anotar(G, 'numpy', OK, 'no está: texturas y tema usan el python de ComfyUI')
    cod, out = correr(['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader,nounits'])
    if cod:
        R.tiene['gpu'] = R.anotar(G, 'GPU NVIDIA', FALTA, 'nvidia-smi no responde',
                                  'driver de NVIDIA (sin GPU solo andan los pasos de Blender, sprites y Godot)')
    else:
        nombre, mem, driver = [x.strip() for x in out.splitlines()[0].split(',')]
        gb = int(mem) / 1024
        R.tiene['gpu'] = R.anotar(G, 'GPU NVIDIA', OK if gb >= 15.5 else AVISO, f'{nombre}, {gb:.0f} GB, driver {driver}',
                                  '' if gb >= 15.5 else 'con menos de 16 GB la malla puede no entrar')
    try:
        with open('/proc/meminfo') as f:
            kb = int(re.search(r'MemTotal:\s+(\d+)', f.read()).group(1))
        gb = kb / 1024 ** 2
        R.anotar(G, 'RAM', OK if gb >= 30 else AVISO, f'{gb:.0f} GB', '' if gb >= 30 else 'Kimodo usa ~16 GB en CPU')
    except (OSError, AttributeError):
        pass


def config(R, ruta):
    G = 'Config'
    if not os.path.exists(ruta):
        R.anotar(G, 'config.json', FALTA, ruta, './instalar.sh (o cp config.ejemplo.json config.json y completar las rutas)')
        return None
    try:
        with open(ruta) as f:
            cfg = json.load(f)
    except ValueError as e:
        R.anotar(G, 'config.json', FALTA, f'json inválido: {e}', 'corregir el archivo')
        return None
    R.tiene['config'] = R.anotar(G, 'config.json', OK, ruta)
    sin = [k for k in ('comfyui_dir', 'comfyui_url', 'trellis2_dir', 'blender', 'env_modelos', 'modelos_imagen')
           if k not in cfg]
    if sin:
        R.anotar(G, 'claves', AVISO, 'faltan: ' + ', '.join(sin), 'copiarlas de config.ejemplo.json')
    datos = os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(ruta)), cfg.get('datos_dir') or RAIZ))
    if os.path.isdir(datos) and os.access(datos, os.W_OK):
        g = libre_gb(datos)
        R.anotar(G, 'datos_dir', OK if g is None or g > 20 else AVISO, f'{datos} ({g:.0f} GB libres)' if g else datos,
                 '' if g is None or g > 20 else 'cada personaje con malla ocupa ~0,5-1 GB')
    else:
        R.anotar(G, 'datos_dir', FALTA, f'{datos} no existe o no se puede escribir', 'crear la carpeta o corregir datos_dir')
    est = cfg.get('estilo', 'moderno')
    R.anotar(G, 'estilo', OK if os.path.exists(os.path.join(RAIZ, 'estilos', f'{est}.json')) else FALTA, est,
             f'no hay estilos/{est}.json: usar uno de ' + ', '.join(sorted(f[:-5] for f in os.listdir(
                 os.path.join(RAIZ, 'estilos')) if f.endswith('.json'))))
    return cfg


def ejecutable(R, G, nombre, ruta, obligatorio, arreglo, version_args=None, version_re=None, minima=None):
    if not ruta or placeholder(ruta):
        R.anotar(G, nombre, FALTA if obligatorio else AVISO, 'sin configurar', arreglo)
        return False
    if not (os.path.isfile(ruta) and os.access(ruta, os.X_OK)):
        R.anotar(G, nombre, FALTA if obligatorio else AVISO, f'no existe o no es ejecutable: {ruta}', arreglo)
        return False
    if not version_args:
        return R.anotar(G, nombre, OK, ruta)
    cod, out = correr([ruta] + version_args)
    m = re.search(version_re, out) if cod == 0 else None
    if not m:
        return R.anotar(G, nombre, FALTA if obligatorio else AVISO, f'{ruta} no responde a {" ".join(version_args)}',
                        arreglo)
    v = m.group(1)
    vieja = minima and tuple(int(x) for x in v.split('.')[:2]) < minima
    R.anotar(G, nombre, AVISO if vieja else OK, f'{v} ({ruta})',
             f'probado con {".".join(map(str, minima))}' if vieja else '')
    return True


def herramientas(R, cfg):
    G = 'Herramientas'
    R.tiene['blender'] = ejecutable(R, G, 'Blender', cfg.get('blender'), True,
                                    './instalar.sh --solo blender,config (o bajar Blender 5.1 de blender.org y poner el ejecutable en `blender`)',
                                    ['-b', '--factory-startup', '--version'], r'Blender (\d+\.\d+(?:\.\d+)?)', (5, 1))
    R.tiene['godot'] = ejecutable(R, G, 'Godot (opcional)', cfg.get('godot'), False,
                                  'solo para `godot --instalar`: Godot 4.x en `godot`',
                                  ['--headless', '--version'], r'(\d+\.\d+(?:\.\d+)?)')
    kd = cfg.get('kimodo_dir')
    py = os.path.join(kd, 'venv', 'bin', 'python') if kd and not placeholder(kd) else None
    R.tiene['kimodo'] = bool(py and os.path.exists(py))
    R.anotar(G, 'Kimodo (opcional)', OK if R.tiene['kimodo'] else AVISO, kd if R.tiene['kimodo'] else 'sin instalar',
             '' if R.tiene['kimodo'] else 'solo para `crisol movimiento` (README > Kimodo)')


def comfyui(R, cfg):
    G = 'ComfyUI'
    cd = cfg.get('comfyui_dir')
    R.tiene['comfyui'] = False
    if not cd or placeholder(cd) or not os.path.isdir(cd):
        R.anotar(G, 'carpeta', FALTA, cd or 'sin configurar', './instalar.sh (o instalar ComfyUI a mano y poner la carpeta en `comfyui_dir`)')
        return
    py, comfy = os.path.join(cd, 'venv', 'bin', 'python'), os.path.join(cd, 'venv', 'bin', 'comfy')
    if not os.path.exists(py):
        R.anotar(G, 'venv', FALTA, f'no hay {py}', 'crear el venv en <comfyui_dir>/venv e instalar los requirements')
        return
    R.anotar(G, 'carpeta', OK, cd)
    R.tiene['numpy'] = R.tiene.get('numpy') or bool(version_paquete(py, 'numpy'))
    R.tiene['comfyui'] = R.anotar(G, 'comfy-cli', OK if os.path.exists(comfy) else FALTA,
                                  comfy if os.path.exists(comfy) else 'no está en el venv',
                                  f'{os.path.join(cd, "venv", "bin", "pip")} install comfy-cli')
    url = cfg.get('comfyui_url', 'http://127.0.0.1:8188')
    try:
        q = json.loads(urllib.request.urlopen(url + '/queue', timeout=3).read())
        ocupada = len(q.get('queue_running', [])) + len(q.get('queue_pending', []))
        R.anotar(G, 'servidor', OK, f'{url} corriendo' + (f', {ocupada} trabajo(s) en la cola' if ocupada else ''))
    except (OSError, ValueError):
        R.anotar(G, 'servidor', OK, f'{url} apagado (el pipeline lo arranca cuando hace falta)')
    # Pixal3D: nodos nativos de ComfyUI (versión reciente)
    nativo = any('Pixal3DConditioning' in open(os.path.join(d, f), errors='ignore').read()
                 for d, _, fs in os.walk(os.path.join(cd, 'comfy_extras')) for f in fs if f.endswith('.py'))
    R.tiene['pixal3d_nodos'] = R.anotar(G, 'nodos de Pixal3D', OK if nativo else FALTA,
                                        'nativos' if nativo else 'esta versión de ComfyUI no los trae',
                                        'actualizar ComfyUI (git pull + requirements)')
    hay = {n.lower() for n in os.listdir(os.path.join(cd, 'custom_nodes'))} if os.path.isdir(
        os.path.join(cd, 'custom_nodes')) else set()
    for clave, (nombres, repo) in NODOS.items():
        R.tiene[f'nodo_{clave}'] = any(n in hay for n in nombres)
        R.anotar(G, f'nodo {repo.rsplit("/", 1)[1]}', OK if R.tiene[f'nodo_{clave}'] else AVISO,
                 'instalado' if R.tiene[f'nodo_{clave}'] else 'no está',
                 f'./instalar.sh --solo comfyui (o git clone {repo} en custom_nodes/ + sus requirements en el venv de ComfyUI)')
    if R.tiene['nodo_ultratex']:
        sin = [p for p in ('moderngl', 'xatlas') if not version_paquete(py, p)]
        if sin:
            R.tiene['nodo_ultratex'] = R.anotar(G, 'UltraTex: paquetes', FALTA, 'faltan ' + ', '.join(sin),
                                                f'{os.path.join(cd, "venv", "bin", "pip")} install moderngl xatlas')
    modelos(R, cfg, cd)


def buscar_modelo(cd, carpetas, nombre):
    for c in carpetas:
        base = os.path.join(cd, 'models', c)
        if os.path.isfile(os.path.join(base, nombre)):
            return True
        for d, _, fs in os.walk(base, followlinks=True):
            if nombre in fs:
                return True
    return False


def modelos(R, cfg, cd):
    G = 'Modelos de ComfyUI'
    mi = cfg.get('modelos_imagen', {})
    for grupo, lista in MODELOS.items():
        faltan = []
        for carpetas, nombre in lista:
            if nombre.startswith('@'):
                clave, nombre = nombre[1:], mi.get(nombre[1:])
                if not nombre:
                    faltan.append(f'modelos_imagen.{clave} (sin configurar)')
                    continue
            if not buscar_modelo(cd, carpetas, nombre):
                faltan.append(f'{carpetas[0]}/{nombre}')
        R.tiene[f'modelos_{grupo}'] = not faltan
        R.anotar(G, grupo, OK if not faltan else AVISO, f'{len(lista)} archivo(s)' if not faltan else
                 'faltan: ' + ', '.join(faltan), './instalar.sh --solo modelos (README > Lista de modelos de ComfyUI)' if faltan else '')


def trellis(R, cfg):
    G = 'TRELLIS.2'
    td = cfg.get('trellis2_dir')
    R.tiene['trellis2'] = R.tiene['rembg'] = False
    if not td or placeholder(td) or not os.path.isdir(td):
        R.anotar(G, 'carpeta', FALTA, td or 'sin configurar', './instalar.sh --solo trellis,config (o README > TRELLIS.2 y poner la carpeta en `trellis2_dir`)')
        return
    py = os.path.join(td, 'venv', 'bin', 'python')
    if not os.path.exists(py):
        R.anotar(G, 'venv', FALTA, f'no hay {py}', 'crear el venv (Python 3.10) en <trellis2_dir>/venv')
        return
    cod, out = correr([py, '--version'])
    R.anotar(G, 'venv', OK if '3.10' in out else AVISO, out, '' if '3.10' in out else 'el repo pide Python 3.10')
    tf = version_paquete(py, 'transformers')
    ok_tf = R.anotar(G, 'transformers', OK if tf == '4.57.1' else FALTA, tf or 'no está',
                     f'{os.path.join(td, "venv", "bin", "pip")} install transformers==4.57.1 (con 5.x falla DINOv3)')
    sin = [p for p in ('rembg', 'onnxruntime', 'trimesh') if not version_paquete(py, p)]
    R.tiene['rembg'] = R.anotar(G, 'rembg, onnxruntime, trimesh', OK if not sin else FALTA,
                                'instalados' if not sin else 'faltan ' + ', '.join(sin),
                                f'{os.path.join(td, "venv", "bin", "pip")} install rembg onnxruntime trimesh')
    hf = cfg.get('env_modelos', {}).get('HF_HOME') or os.path.expanduser('~/.cache/huggingface')
    faltan = [r for r in HF_TRELLIS if not os.path.isdir(os.path.join(hf, 'hub', 'models--' + r.replace('/', '--')))]
    ok_hf = R.anotar(G, 'pesos (Hugging Face)', OK if not faltan else FALTA,
                     hf if not faltan else 'faltan ' + ', '.join(faltan),
                     f'./instalar.sh --solo modelos (DINOv3 es gated: aceptar sus condiciones en Hugging Face)')
    R.tiene['trellis2'] = ok_tf and ok_hf and R.tiene['rembg']


# pasos -> lo que necesitan: listas de alternativas (basta una) de capacidades que tienen que estar todas
PASOS = [
    ('nuevo, metodo', [['pillow']], ''),
    ('imagen (con referencia)', [['comfyui', 'modelos_qwen']], 'Qwen Image Edit'),
    ('imagen (sin referencia)', [['comfyui', 'modelos_zimage'], ['comfyui', 'modelos_flux2', 'nodo_gguf']],
     'Z-Image Turbo, o FLUX.2 Dev + ComfyUI-GGUF'),
    ('vistas', [['comfyui', 'modelos_qwen']], 'Qwen Image Edit'),
    ('malla (TRELLIS.2)', [['trellis2', 'blender']], 'TRELLIS.2 con sus pesos'),
    ('malla (Pixal3D)', [['comfyui', 'pixal3d_nodos', 'modelos_pixal3d', 'blender']], 'nodos y modelos de Pixal3D'),
    ('ultratex', [['comfyui', 'nodo_ultratex', 'modelos_ultratex', 'blender']], 'ComfyUI-UltraTex + FLUX.2 Klein'),
    ('articulaciones', [['comfyui', 'nodo_dwpose', 'blender']], 'comfyui_controlnet_aux (DWPose)'),
    ('guia, blender, retrato, iso, anclas, revisar, comparar, rehacer', [['blender', 'pillow']], 'Blender 5.1'),
    ('sprites, godot', [['pillow']], 'Pillow'),
    ('godot --instalar', [['godot']], 'Godot 4.x'),
    ('texturas (sdxl)', [['comfyui', 'modelos_sdxl']], 'DreamShaper XL Turbo'),
    ('texturas (sdxl con referencia)', [['comfyui', 'modelos_sdxl', 'modelos_ipadapter', 'nodo_ipadapter']],
     'IP-Adapter + ComfyUI_IPAdapter_plus'),
    ('texturas (zimage)', [['comfyui', 'modelos_zimage']], 'Z-Image Turbo'),
    ('tema', [['pillow', 'numpy']], 'numpy (en el python3 del sistema o en el venv de ComfyUI)'),
    ('movimiento', [['kimodo']], 'Kimodo'),
]
# sin estos, la receta recomendada no anda: el resto son opcionales (avisan pero no hacen fallar a doctor)
OBLIGATORIOS = {'nuevo, metodo', 'imagen (con referencia)', 'vistas', 'malla (TRELLIS.2)',
                'guia, blender, retrato, iso, anclas, revisar, comparar, rehacer', 'sprites, godot'}


def pasos(R):
    res = []
    base = {'config': 'config.json', 'comfyui': 'ComfyUI', 'blender': 'Blender 5.1'}   # se nombran aparte
    for paso, alternativas, que in PASOS:
        alternativas = [['config'] + alt for alt in alternativas]
        ok = any(all(R.tiene.get(c) for c in alt) for alt in alternativas)
        falta = [] if ok else sorted({c for alt in alternativas for c in alt if not R.tiene.get(c)})
        previos = [n for c, n in base.items() if c in falta and n != que]
        que = ' + '.join(previos + ([que] if que else []))
        res.append({'paso': paso, 'disponible': ok, 'obligatorio': paso in OBLIGATORIOS, 'necesita': que,
                    'falta': falta})
    return res


def main(ruta_config, args):
    R = Revision()
    sistema(R)
    cfg = config(R, ruta_config)
    if cfg:
        herramientas(R, cfg)
        comfyui(R, cfg)
        trellis(R, cfg)
    ps = pasos(R)
    fallo = any(p['obligatorio'] and not p['disponible'] for p in ps)
    if '--json' in args:
        print(json.dumps({'ok': not fallo, 'revisiones': R.items, 'pasos': ps}, ensure_ascii=False, indent=1))
        return 1 if fallo else 0
    grupo = None
    for it in R.items:
        if it['grupo'] != grupo:
            grupo = it['grupo']
            print(f'\n{grupo}')
        print(f"  {MARCA[it['estado']]} {it['nombre']}: {it['detalle']}")
        if it['estado'] != OK and it['arreglo']:
            print(f"      → {it['arreglo']}")
    print('\nPasos')
    for p in ps:
        m = '✔' if p['disponible'] else ('✘' if p['obligatorio'] else '!')
        print(f"  {m} {p['paso']}" + ('' if p['disponible'] else f"  (necesita {p['necesita']})"))
    print('\n' + ('Falta algo obligatorio (✘): ver arriba cómo arreglarlo.' if fallo else
                  'Todo lo obligatorio está. Los ! son opcionales o avisos.'))
    return 1 if fallo else 0
