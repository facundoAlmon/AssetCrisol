# Re-texturizar una malla con UltraTex (nodos visualbruno/ComfyUI-UltraTex: FLUX.2 Klein base 9B + LoRA, 6 vistas
# horneadas al UV). Corre con el python3 del sistema; ComfyUI hace todo (README > Instalación > UltraTex).
# uso: python3 retexturizar_ultratex.py <malla.glb> <imagen con alfa> <salida.glb> [seed] [resolucion] [textura_px]
#   malla: la de `blender_main.py limpia` (soldada, sin el interior: si no, las capas internas reciben color)
#   imagen: sin_fondo.png (el alfa es la máscara); resolucion: por vista (1024 | 2048)
# Salida: GLB con UV nuevas y solo color base, en la escala y posición de la malla de entrada; trabajo/malla/
# ultratex_vistas.png = las 6 vistas generadas (mirarlas). Desde el pipeline: malla.ultratex / `pipeline.py ultratex`.
# Con `espalda` (la vista_back.png de Qwen de Pixal3D 4 vistas): UltraTex solo mira la imagen de frente y la espalda la
# inventa (copiaba lo del pecho); una primera pasada da las 6 vistas, la de atrás se reemplaza por la de Qwen encajada
# en la silueta y una segunda pasada (denoise parcial) las repinta coherentes -> ultratex_espalda.png para mirarla.
# Con `costados` (vista_left/right.png de Qwen), ídem con las cámaras 1 y 3 (ver COSTADOS) -> ultratex_costados.png.
import glob, json, os, shutil, subprocess, sys
from PIL import Image, ImageChops, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '1_imagen'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generar_imagen  # noqa: E402
import generar_malla_pixal3d  # noqa: E402


ORDEN_ATLAS = [[0, 1, 3], [2, 4, 5]]   # render.GRID_ORDER de UltraTex: vistas front, left, back, right, top, bottom
ATRAS = 2
# Cámaras de los costados (verificado con un muñeco de juguete con alas y POSES de render.py: la vista 1 está del
# lado -X de Blender, donde queda la mano derecha de un modelo de frente -Y, y lo ve mirando al borde derecho de la
# imagen = vista_right de Qwen; la 3, el izquierdo mirando al borde izquierdo = vista_left). Sin espejar si Qwen la
# hizo bien.
COSTADOS = {1: 'right', 3: 'left'}


def workflow(malla, imagen, seed, reso, tex_px, prefijo, giro=0.0, inicio=None, denoise=1.0, hornear=True):
    """giro > 0: segunda pasada con el rig de cámaras girado `giro` grados (vistas a 45/135/225/315 con 45): parte de
    lo ya pintado (denoise 0.6, conserva lo visto de frente) y pinta los costados que la primera no vio.
    inicio: 6 imágenes (en input/ de ComfyUI, en el orden de las vistas) de las que parte el muestreo con `denoise`.
    hornear=False: solo las vistas y los normales de la malla (`normales_*`, la silueta de cada cámara)."""
    n = lambda c, **i: {'class_type': c, 'inputs': i}  # noqa: E731
    w = {
        'img': n('LoadImage', image=imagen),
        'unet': n('UNETLoader', unet_name='flux-2-klein-base-9b-fp8.safetensors', weight_dtype='default'),
        'clip': n('CLIPLoader', clip_name='qwen_3_8b_fp8mixed.safetensors', type='flux2', device='default'),
        'vae': n('VAELoader', vae_name='flux2-vae.safetensors'),
        'decoder': n('UltraTexForegroundDecoder', vae=['vae', 0], decoder_name='ultratex_flux2_decoder.pt'),
        'lora': n('UltraTexLoraLoader', model=['unet', 0], lora_name='ultratex_flux2.safetensors', strength=1.0),
        'pos': n('CLIPTextEncode', clip=['clip', 0], text=''),
        'neg': n('CLIPTextEncode', clip=['clip', 0], text=''),
        'prep': n('UltraTexPrep', reference_image=['img', 0], reference_mask=['img', 1], mesh_path=malla,
                  render_size=4096, atlas_size=tex_px, uv_mode='comfy_gpu', reference_alignment='fit_front_silhouette',
                  mask_meaning='background (LoadImage)'),
        # valores del workflow de ejemplo a 1024 (PBR Flux2Klein9B)
        'muestreo': n('UltraTexSampler', model=['lora', 0], vae=['decoder', 0], positive=['pos', 0],
                      negative=['neg', 0], prep=['prep', 0], resolution=reso, steps=25, seed=seed, guidance=4.0,
                      drop_background_tokens=True, memory_factor=0.0, attention='ultratex_sparse', sparse_topk=0.2,
                      token_chunk=8192, denoise=1.0),
        'vistas': n('SaveImage', images=['muestreo', 2], filename_prefix=prefijo + '_vistas'),
        'horneado': n('UltraTexBake', prep=['prep', 0], albedo_views=['muestreo', 0], texture_size=tex_px,
                      filename_prefix=f'UltraTex/{prefijo}', view_weight_power=4.0, best_view_mix=0.5,
                      edge_feather_px=6.0),
    }
    if inicio:
        for i, f in enumerate(inicio):
            w[f'ini_{i}'] = n('LoadImage', image=f)
        previo = 'ini_0'
        for i in range(1, len(inicio)):
            w[f'lote_{i}'] = n('ImageBatch', image1=[previo, 0], image2=[f'ini_{i}', 0])
            previo = f'lote_{i}'
        w['muestreo']['inputs'].update(init_views=[previo, 0], denoise=denoise)
    if not hornear:
        del w['horneado']
        w['normales'] = n('SaveImage', images=['prep', 1], filename_prefix=prefijo + '_normales')
        w['crudas'] = n('SaveImage', images=['muestreo', 0], filename_prefix=prefijo + '_crudas')
        return w
    if giro:
        muestreo = w['muestreo']['inputs']
        w['rig_2'] = n('UltraTexRotateRig', prep=['prep', 0], azimuth=float(giro), elevation=0.0,
                       elevation_mode='per view')
        w['inicio_2'] = n('UltraTexRenderViews', prep=['rig_2', 0], source_prep=['prep', 0],
                          source_views=['muestreo', 0], resolution=reso, keep_above=0.75, keep_feather=0.1)
        w['muestreo_2'] = n('UltraTexSampler', **dict(muestreo, prep=['rig_2', 0], denoise=0.6,
                                                    init_views=['inicio_2', 0], keep_mask=['inicio_2', 1]))
        w['vistas_2'] = n('SaveImage', images=['muestreo_2', 2], filename_prefix=prefijo + '_vistas_2')
        w['horneado']['inputs'].update(prep_2=['rig_2', 0], albedo_views_2=['muestreo_2', 0], views_2_use='all')
    return w


def _mascara(img, umbral):
    """'L' 255 donde algún canal es menor que `umbral` (contenido sobre fondo blanco/marcado)."""
    r, g, b = img.convert('RGB').split()
    return ImageChops.darker(ImageChops.darker(r, g), b).point(lambda v: 255 if v < umbral else 0)


def _sin_fondo(cfg, ruta):
    """RGB y alfa ('L') de una vista de Qwen: rembg (birefnet-general) en el venv de TRELLIS.2; el fondo de Qwen tiene
    degradé y viñeta y una inundación desde los bordes se lo comía. Queda en <vista>_alfa.png."""
    dst = os.path.splitext(ruta)[0] + '_alfa.png'
    if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(ruta):
        cod = ('import sys; from PIL import Image; from rembg import remove, new_session; '
               'remove(Image.open(sys.argv[1]).convert("RGB"), session=new_session("birefnet-general")).save(sys.argv[2])')
        subprocess.run([os.path.join(cfg['trellis2_dir'], 'venv', 'bin', 'python'), '-c', cod, ruta, dst], check=True,
                       env=dict(os.environ, **cfg['env_modelos']))
    img = Image.open(dst)
    return img.convert('RGB'), img.getchannel('A').point(lambda v: 255 if v > 127 else 0)


def _encajar(cfg, cruda, normal, ruta, reso, auto_espejo=False):
    """La vista de Qwen `ruta` encajada en la silueta de la cámara (`normal`: su render de normales): misma altura y
    centro (los brazos de Qwen no caen justo donde los de la malla); afuera de la silueta, blanco; donde la silueta
    no tiene a Qwen, lo de `cruda`. auto_espejo (costados): si la de Qwen espejada calza mejor con la silueta (mira al
    lado contrario: pasa), la espeja. Devuelve la vista y si la espejó."""
    sil = _mascara(normal.resize((reso, reso), Image.NEAREST), 250)
    rgb, alfa = _sin_fondo(cfg, ruta)
    caja_q, caja_s = alfa.getbbox(), sil.getbbox()
    k = (caja_s[3] - caja_s[1]) / (caja_q[3] - caja_q[1])
    tam = (round((caja_q[2] - caja_q[0]) * k), caja_s[3] - caja_s[1])
    x0 = round((caja_s[0] + caja_s[2]) / 2 - tam[0] / 2)
    rgb_r = rgb.crop(caja_q).resize(tam, Image.LANCZOS)
    alfa_r = alfa.crop(caja_q).resize(tam, Image.BILINEAR).point(lambda v: 255 if v > 127 else 0)

    def iou(a):
        qa = Image.new('L', (reso, reso), 0); qa.paste(a, (x0, caja_s[1]))
        inter = ImageChops.multiply(qa, sil).histogram()[255]
        return inter / max(1, ImageChops.lighter(qa, sil).histogram()[255])
    espejada = False
    if auto_espejo:
        espejo = alfa_r.transpose(Image.FLIP_LEFT_RIGHT)
        directa, invertida = iou(alfa_r), iou(espejo)
        print(f'[ultratex] {os.path.basename(ruta)}: calce con la silueta {directa:.2f}, espejada {invertida:.2f}',
              flush=True)
        if invertida > directa + 0.02:
            espejada = True
            rgb_r, alfa_r = rgb_r.transpose(Image.FLIP_LEFT_RIGHT), espejo
            print(f'[ultratex] {os.path.basename(ruta)} mira al lado contrario: se espeja', flush=True)
    q = Image.new('RGB', (reso, reso), 'white'); qa = Image.new('L', (reso, reso), 0)
    q.paste(rgb_r, (x0, caja_s[1])); qa.paste(alfa_r, (x0, caja_s[1]))
    vista = cruda.convert('RGB').resize((reso, reso))
    vista.paste(q, (0, 0), ImageChops.multiply(qa, sil))
    return Image.composite(vista, Image.new('RGB', vista.size, 'white'), sil), espejada


def armar_inicio(cfg, vistas, normales, reemplazos, reso):
    """6 vistas de la primera pasada con las de `reemplazos` ({índice de vista: vista de Qwen}) encajadas en su
    silueta (`_encajar`; los costados se espejan solos si miran al revés). Devuelve las 6 y {índice: encajada}."""
    out = [v.convert('RGB').resize((reso, reso)) for v in vistas]
    pegadas = {}
    for i, ruta in reemplazos.items():
        out[i], _ = _encajar(cfg, out[i], normales[i], ruta, reso, auto_espejo=i != ATRAS)
        pegadas[i] = out[i]
    return out, pegadas


def _imagenes(cfg, salidas, nodo):
    base = os.path.join(cfg['comfyui_dir'], 'output')
    return [Image.open(os.path.join(base, im['subfolder'], im['filename'])) for im in salidas[nodo]['images']]


def retexturizar(cfg, nombre, malla, imagen, salida, seed=1, reso=1024, tex_px=4096, giro=0.0, espalda=None,
                 denoise_espalda=0.6, costados=None):
    """espalda: vista_back.png de Qwen; costados: {'left': vista_left.png, 'right': vista_right.png} de Qwen. Con
    alguna, primera pasada sin hornear, esas vistas reemplazan a las inventadas y la segunda pasada parte de ahí."""
    out = os.path.dirname(salida)
    generar_imagen.asegurar_servidor(cfg, out)
    entrada = f'{nombre}_ultratex.png'
    shutil.copy(imagen, os.path.join(cfg['comfyui_dir'], 'input', entrada))
    prefijo = f'gp_{nombre}_ultratex'
    inicio = None
    reemplazos = {ATRAS: espalda} if espalda else {}
    for i, lado in COSTADOS.items():
        if costados and costados.get(lado):
            reemplazos[i] = costados[lado]
    if reemplazos:
        print(f'[ultratex] primera pasada (para {", ".join(os.path.basename(r) for r in reemplazos.values())})...',
              flush=True)
        s0 = generar_malla_pixal3d.correr(cfg, workflow(os.path.abspath(malla), entrada, seed, reso, tex_px,
                                                        prefijo + '_0', hornear=False))
        crudas = _imagenes(cfg, s0, 'crudas')
        vistas, pegadas = armar_inicio(cfg, crudas, _imagenes(cfg, s0, 'normales'), reemplazos, reso)
        inicio = []
        for i, v in enumerate(vistas):
            inicio.append(f'{nombre}_ultratex_ini_{i}.png')
            v.save(os.path.join(cfg['comfyui_dir'], 'input', inicio[-1]))
        # hojas de control: inventada | la de Qwen encajada (una fila por vista)
        for archivo, indices in (('ultratex_espalda.png', [ATRAS]), ('ultratex_costados.png', sorted(COSTADOS))):
            filas = [i for i in indices if i in pegadas]
            if not filas:
                continue
            par = Image.new('RGB', (2 * reso, reso * len(filas)), 'white')
            for f, i in enumerate(filas):
                par.paste(crudas[i].convert('RGB').resize((reso, reso)), (0, f * reso))
                par.paste(pegadas[i], (reso, f * reso))
            par.save(os.path.join(out, archivo))
    print(f'[ultratex] 6 vistas a {reso} (seed {seed}, ~1-5 min)...', flush=True)
    salidas = generar_malla_pixal3d.correr(cfg, workflow(os.path.abspath(malla), entrada, seed, reso, tex_px, prefijo, giro,
                                                         inicio, denoise_espalda if inicio else 1.0))
    base = os.path.join(cfg['comfyui_dir'], 'output')
    im = salidas['vistas']['images'][0]
    shutil.copy(os.path.join(base, im['subfolder'], im['filename']), os.path.join(out, 'ultratex_vistas.png'))
    if giro:
        im = salidas['vistas_2']['images'][0]
        shutil.copy(os.path.join(base, im['subfolder'], im['filename']), os.path.join(out, 'ultratex_vistas_2.png'))
    glb = max(glob.glob(os.path.join(base, 'UltraTex', prefijo + '_*.glb')), key=os.path.getmtime)
    generar_malla_pixal3d.solo_color_base(glb, salida)


if __name__ == '__main__':
    malla, imagen, salida = (os.path.abspath(a) for a in sys.argv[1:4])
    with open(os.environ.get('ASSETCRISOL_CONFIG')
              or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'config.json')) as f:
        cfg = json.load(f)
    retexturizar(cfg, os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(salida)))), malla, imagen,
                 salida, *(int(a) for a in sys.argv[4:7]))
    print(f'[ultratex] listo: {salida}')
