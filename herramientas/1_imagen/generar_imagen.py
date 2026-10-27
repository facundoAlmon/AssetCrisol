# Paso 1: imagen limpia del personaje (frente, pose A, fondo liso) con ComfyUI local.
#  - Con referencia (personajes/<n>/referencia.png): Qwen-Image-Edit 2511 la "re-renderiza" en estilo 3D.
#  - Sin referencia: Z-Image Turbo (por defecto: segundos, Apache-2.0) o FLUX.2 Dev (`imagen.motor: "flux2"`: ~3 min,
#    licencia no comercial) generan desde el prompt.
# Una imagen por seed -> personajes/<n>/trabajo/imagen/cand_<seed>.png + candidatos.png (hoja de contacto).
# Se llama desde pipeline.py (python3 del sistema; usa el CLI `comfy` del venv de ComfyUI).
import glob, json, os, shutil, subprocess, sys, time, urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))


def comfy_cli(cfg):
    return os.path.join(cfg['comfyui_dir'], 'venv', 'bin', 'comfy')


def servidor_vivo(cfg):
    try:
        urllib.request.urlopen(cfg['comfyui_url'] + '/system_stats', timeout=2)
        return True
    except Exception:
        return False


def asegurar_servidor(cfg, log_dir):
    if servidor_vivo(cfg):
        return
    print('[imagen] iniciando ComfyUI...')
    log = open(os.path.join(log_dir, 'comfyui.log'), 'w')
    subprocess.Popen([os.path.join(cfg['comfyui_dir'], 'venv', 'bin', 'python'), 'main.py',
                      '--listen', '127.0.0.1', '--port', cfg['comfyui_url'].rsplit(':', 1)[1]],
                     cwd=cfg['comfyui_dir'], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(120):
        if servidor_vivo(cfg):
            return
        time.sleep(2)
    sys.exit('[imagen] ComfyUI no arrancó; ver trabajo/imagen/comfyui.log')


def run_json(cmd):
    out = subprocess.run(cmd, capture_output=True, text=True)
    try:
        env = json.loads(out.stdout)
    except json.JSONDecodeError:
        sys.exit(f'[imagen] salida inesperada de {cmd[:4]}:\n{out.stdout}\n{out.stderr}')
    if not env.get('ok'):
        sys.exit(f'[imagen] error en {cmd[:4]}: {env.get("error")}')
    return env['data']


# Requisitos técnicos de la malla 3D/rig (no son estilo: no dependen de estilos/*.json)
# pose A relajada con aire entre brazos y torso y entre las piernas: si se tocan, TRELLIS.2 los funde en una sola
# superficie y el rig no los separa; muy abiertos, al cerrarlos en las animaciones se deforma el hombro
ENCUADRE_PERSONAJE = ('Full body, front view, symmetrical, standing straight in a relaxed A-pose: arms straight down '
                      'and angled about 25 degrees away from the body, a clear gap between the arms and the torso, '
                      'hands relaxed with palms facing the thighs, not touching the body, legs slightly apart with a '
                      'visible gap between them, feet pointing forward')
ENCUADRE_OBJETO = 'Single object, three-quarter view from slightly above, whole object visible, centered, no text'


def componer_prompt(pj):
    """imagen.descripcion + estilo (render, tema, paleta, extra) + encuadre técnico. Si el json no tiene
    descripcion, se usa imagen.prompt tal cual (personajes viejos; el estilo no entra en el prompt)."""
    img, E = pj['imagen'], pj['_estilo']['prompt']
    desc = (img.get('descripcion') or '').strip().rstrip('.')
    if not desc:
        return img['prompt']
    obj = pj.get('_objeto')
    render = E['render_objeto' if obj else 'render_personaje']
    if img.get('referencia'):
        partes = [f"Transform this {'object' if obj else 'character'} into {render}. Keep the same design: {desc}."]
    else:
        partes = [f'{render[0].upper()}{render[1:]}: {desc}.']
    partes += [f'{x.strip()[0].upper()}{x.strip()[1:].rstrip(".")}.' for x in (E.get('tema'), E.get('paleta')) if x]
    partes.append(f"{ENCUADRE_OBJETO if obj else ENCUADRE_PERSONAJE}, {E['extra']}.")
    return ' '.join(partes)


def motor_texto(cfg, pj):
    """Motor de imagen sin referencia: imagen.motor, o Z-Image Turbo si la config tiene sus modelos (si no, FLUX.2 Dev)."""
    return pj['imagen'].get('motor') or ('zimage' if cfg['modelos_imagen'].get('zimage_unet') else 'flux2')


def workflow_zimage(cfg, prompt, seed, prefijo, lado=1024):
    """Z-Image Turbo en formato API: 8 pasos, cfg 1, negativo vacío (ConditioningZeroOut)."""
    M = cfg['modelos_imagen']
    return {
        '1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': M['zimage_unet'], 'weight_dtype': 'default'}},
        '2': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': M['zimage_clip'], 'type': 'lumina2'}},
        '3': {'class_type': 'VAELoader', 'inputs': {'vae_name': M['zimage_vae']}},
        '4': {'class_type': 'ModelSamplingAuraFlow', 'inputs': {'model': ['1', 0], 'shift': 3.0}},
        '5': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['2', 0], 'text': prompt}},
        '6': {'class_type': 'ConditioningZeroOut', 'inputs': {'conditioning': ['5', 0]}},
        '7': {'class_type': 'EmptySD3LatentImage', 'inputs': {'width': lado, 'height': lado, 'batch_size': 1}},
        '8': {'class_type': 'KSampler', 'inputs': {'model': ['4', 0], 'positive': ['5', 0], 'negative': ['6', 0],
              'latent_image': ['7', 0], 'seed': seed, 'steps': 8, 'cfg': 1.0, 'sampler_name': 'res_multistep',
              'scheduler': 'simple', 'denoise': 1.0}},
        '9': {'class_type': 'VAEDecode', 'inputs': {'samples': ['8', 0], 'vae': ['3', 0]}},
        '10': {'class_type': 'SaveImage', 'inputs': {'images': ['9', 0], 'filename_prefix': prefijo}},
    }


def armar_workflow(cfg, nombre, pj, seed, wf_path, prefijo, ref=None, prompt=None):
    """`ref` y `prompt` pisan a los del personaje (las vistas de Pixal3D editan la imagen elegida)."""
    comfy = comfy_cli(cfg)
    M = cfg['modelos_imagen']
    img = pj['imagen']
    if ref is None:
        ref = os.path.join(pj['_dir'], img['referencia']) if img.get('referencia') else None
    prompt = prompt or componer_prompt(pj)
    with open(wf_path, 'w') as f:
        json.dump({'nodes': [], 'links': [], 'last_node_id': 0, 'last_link_id': 0}, f)
    if ref and os.path.exists(ref):
        dst = f'{nombre}_{os.path.splitext(os.path.basename(ref))[0]}_ref.png'
        shutil.copy(ref, os.path.join(cfg['comfyui_dir'], 'input', dst))
        data = run_json([comfy, '--json', '--where', 'local', 'workflow', 'apply', wf_path,
                         '--ops', os.path.join(AQUI, 'qwen_edit.recipe.json'),
                         '--param', f'ref_image={dst}', '--param', f'edit_prompt={prompt}',
                         '--param', f'seed={seed}', '--param', f'filename_prefix={prefijo}'])
        fijos = {'unetloader.unet_name': M['qwen_unet'], 'loraloadermodelonly.lora_name': M['qwen_lora']}
    else:
        if prompt.lower().startswith('transform'):
            print('[imagen] AVISO: no hay referencia pero el prompt parece de edición ("Transform this...").\n'
                  '         Flux genera desde cero: usá imagen.descripcion (el pipeline arma el prompt con el estilo).')
        data = run_json([comfy, '--json', '--where', 'local', 'workflow', 'apply', wf_path,
                         '--ops', os.path.join(AQUI, 'flux2_t2i.recipe.json'),
                         '--param', f'prompt={prompt}', '--param', f'seed={seed}',
                         '--param', f'filename_prefix={prefijo}'])
        fijos = {'unetloadergguf.unet_name': M['flux_unet'], 'cliploader.clip_name': M['flux_clip'],
                 'vaeloader.vae_name': M['flux_vae']}
    # las recetas dejan los modelos en el primer valor del combo: fijarlos explícitamente
    alias = data.get('aliases', {})
    for addr, val in fijos.items():
        a, widget = addr.split('.')
        run_json([comfy, '--json', '--where', 'local', 'workflow', 'set-widget', wf_path, f'{alias[a]}.{widget}', val])


def main(cfg, nombre, pj):
    out_dir = os.path.join(pj['_dir'], 'trabajo', 'imagen')
    os.makedirs(out_dir, exist_ok=True)
    prompt = componer_prompt(pj)
    with open(os.path.join(out_dir, 'prompt.txt'), 'w') as f:
        f.write(prompt + '\n')
    motor = 'qwen edit' if pj['imagen'].get('referencia') else motor_texto(cfg, pj)
    print(f'[imagen] estilo {pj["_estilo"]["nombre"]}, motor {motor}; prompt (en trabajo/imagen/prompt.txt):\n  {prompt}')
    asegurar_servidor(cfg, out_dir)
    comfy = comfy_cli(cfg)
    salida_comfy = os.path.join(cfg['comfyui_dir'], 'output')
    hechas = []
    for seed in pj['imagen']['seeds']:
        prefijo = f'gp_{nombre}_s{seed}'
        wf = os.path.join(out_dir, f'wf_s{seed}.json')
        print(f'[imagen] seed {seed}...')
        if not pj['imagen'].get('referencia') and motor_texto(cfg, pj) == 'zimage':
            import generar_malla_pixal3d   # su `correr` encola un workflow API y espera
            w = workflow_zimage(cfg, prompt, seed, prefijo)
            with open(wf, 'w') as f:
                json.dump(w, f, indent=1)
            generar_malla_pixal3d.correr(cfg, w)
        else:
            armar_workflow(cfg, nombre, pj, seed, wf, prefijo)
            run_json([comfy, '--json', '--where', 'local', 'run', '--workflow', wf, '--wait'])
        ult = max(glob.glob(os.path.join(salida_comfy, prefijo + '_*.png')), key=os.path.getmtime)
        dst = os.path.join(out_dir, f'cand_{seed}.png')
        shutil.copy(ult, dst)
        hechas.append((seed, dst))

    from PIL import Image, ImageDraw
    h = 600
    ims = [Image.open(p).convert('RGB') for _, p in hechas]
    ims = [i.resize((int(i.width * h / i.height), h)) for i in ims]
    hoja = Image.new('RGB', (sum(i.width for i in ims), h), 'white')
    x = 0
    for (seed, _), im in zip(hechas, ims):
        hoja.paste(im, (x, 0))
        ImageDraw.Draw(hoja).text((x + 10, 10), f'seed {seed}', fill=(0, 0, 0))
        x += im.width
    hoja.save(os.path.join(out_dir, 'candidatos.png'))
    print('[imagen] listo:', os.path.join(out_dir, 'candidatos.png'))
    print('[imagen] elegí una y poné su seed en personaje.json > imagen.elegida')
