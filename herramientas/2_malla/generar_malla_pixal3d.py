# Paso 2 con Pixal3D (malla.motor = "pixal3d"): imagen -> malla 3D texturizada con los nodos nativos de ComfyUI
# (Pixal3D sobre TRELLIS.2, alineado a píxel: la cara y los estampados salen de la imagen). Corre con el python3 del
# sistema; ComfyUI hace todo. Modelos en ComfyUI/models (README > Instalación > Pixal3D).
# Con malla.vistas = true usa el modelo de 4 vistas: espalda y costados salen de la imagen elegida con Qwen Edit
# (trabajo/imagen/vista_<v>.png; borrar una para rehacerla).
# Salida: trabajo/malla/sin_fondo.png (BiRefNet) y modelo.glb (solo color base).
import glob, json, os, shutil, struct, sys, time, urllib.request, uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '1_imagen'))
import generar_imagen  # noqa: E402

VISTAS = {  # nombre del nodo -> pedido a Qwen Edit (left/right: los costados del personaje, no de la imagen)
    'back': 'directly from behind: an exact back view rotated 180 degrees, we see the back of the head and the back '
            'of the body, the face is not visible. Emblems, lights, buttons and prints that are on the front (chest emblem, '
            'glowing chest light, logo) do not appear on the back: the back has only the plain back of the same outfit',
    'left': "exactly from its left side: an exact side profile view rotated 90 degrees, the character's left arm "
            'is closest to the camera and it faces the left edge of the image, not three-quarter',
    'right': "exactly from its right side: an exact side profile view rotated 90 degrees, the character's right arm "
             'is closest to the camera and it faces the right edge of the image, not three-quarter',
}


# vehículos (objeto.json con bloque `vehiculo`): la elegida es de tres cuartos, así que también el frente sale de Qwen.
# Mismas convenciones que el personaje: la trompa es la cara (front = trompa a la cámara; left = costado izquierdo
# del auto adelante y la trompa al borde izquierdo de la imagen)
VISTAS_VEHICULO = {
    'front': 'exactly from the front: an exact front view, the nose of the car points straight at the camera, '
             'we see the headlights, the front bumper and the windshield, perfectly symmetric, not three-quarter',
    'back': 'exactly from behind: an exact rear view rotated 180 degrees, we see the tail lights, the rear bumper '
            'and the rear wing, the headlights are not visible, perfectly symmetric, not three-quarter',
    'left': "exactly from its left side: an exact side profile view, the car's left side (driver side) is closest to "
            'the camera and the nose of the car points to the left edge of the image, both left wheels fully visible, '
            'not three-quarter',
    'right': "exactly from its right side: an exact side profile view, the car's right side is closest to the camera "
             'and the nose of the car points to the right edge of the image, both right wheels fully visible, '
             'not three-quarter',
}


# vehículo con malla.vista = "atras" (TRELLIS.2 o Pixal3D de una vista): una sola imagen, la cola en tres cuartos
# desde arriba. En la carrera los autos se ven casi siempre de atrás (el propio y los rivales de adelante): de la
# elegida (tres cuartos de frente) el motor inventaba la cola; así inventa adelante, que casi no se ve
# (un auto de prueba)
PROMPT_ATRAS = ('Show this exact same toy car from behind: a three-quarter rear view from above, we see the rear of the '
                'car, the tail lights, the rear wing, the roof and the engine cover, and the left side of the car. Keep '
                'exactly the same design, colors, materials, proportions and wheels, the whole car visible, plain light '
                'grey background, no shadow on the floor.')


def vistas_de(pj):
    if pj.get('vehiculo'):
        return {'atras': PROMPT_ATRAS} if pj['malla'].get('vista') == 'atras' else VISTAS_VEHICULO
    return VISTAS


def prompt_vista(v, pj=None):
    if v == 'atras':
        return PROMPT_ATRAS
    if pj and pj.get('vehiculo'):
        return (f'Show this exact same toy car {VISTAS_VEHICULO[v]}. Keep exactly the same design, colors, '
                'materials, proportions and wheels, the whole car visible, same scale. Low horizontal camera at the '
                'height of the headlights, not from above: the roof is barely visible. Plain light grey background, '
                'no shadow on the floor.')
    return (f'Show this exact same character {VISTAS[v]}. Keep exactly the same design, colors, materials, '
            'proportions, A-pose with arms slightly away from the body, full body from head to feet, same scale, '
            'orthographic camera at the same height, plain light grey background, no shadow on the floor.')


def generar_vistas(cfg, nombre, pj, img, dir_img):
    """Espalda y costados de la imagen elegida con Qwen Edit (si no están ya); en un vehículo, también el frente."""
    salida = os.path.join(cfg['comfyui_dir'], 'output')
    rutas = {}
    if not all(os.path.exists(os.path.join(dir_img, f'vista_{v}.png')) for v in vistas_de(pj)):
        generar_imagen.asegurar_servidor(cfg, dir_img)
    for v in vistas_de(pj):
        dst = os.path.join(dir_img, f'vista_{v}.png')
        if not os.path.exists(dst):
            prefijo = f'gp_{nombre}_vista_{v}'
            wf = os.path.join(dir_img, f'wf_vista_{v}.json')
            seed = pj['malla'].get('seed_vistas', pj['malla'].get('seed', 1))
            generar_imagen.armar_workflow(cfg, nombre, pj, seed, wf, prefijo, ref=img, prompt=prompt_vista(v, pj))
            print(f'[malla] vista {v} con Qwen Edit...', flush=True)
            generar_imagen.comfy_run(cfg, wf)
            ult = max(glob.glob(os.path.join(salida, prefijo + '_*.png')), key=os.path.getmtime)
            shutil.copy(ult, dst)
        rutas[v] = dst
    return rutas


def normalizar_vistas(cfg, rutas, dir_out, px=1024, pad=1.1):
    """Vehículos: las vistas recortadas con la misma escala para la altura del auto (sobre negro, como las deja
    ImageCropToMask). ImageCropToMask encuadra cada vista por su lado más largo: en un personaje manda la altura en
    las cuatro, pero en un auto el frente (angosto) quedaba tan grande como el costado (largo) y Pixal3D armaba un
    auto cuadrado y astillado (dos autos de prueba). Devuelve {vista: ruta}."""
    from PIL import Image
    import retexturizar_ultratex
    recortes = {}
    for v, r in rutas.items():
        rgb, alfa = retexturizar_ultratex._sin_fondo(cfg, r)
        caja = alfa.getbbox()
        recortes[v] = (rgb.crop(caja), alfa.crop(caja))
    prop = max(max(a.width, a.height) / a.height for _, a in recortes.values())
    alto = px / pad / prop
    salida = {}
    for v, (rgb, alfa) in recortes.items():
        k = alto / alfa.height
        tam = (max(1, round(rgb.width * k)), max(1, round(alto)))
        lienzo = Image.new('RGB', (px, px), 'black')
        lienzo.paste(rgb.resize(tam, Image.LANCZOS), ((px - tam[0]) // 2, (px - tam[1]) // 2),
                     alfa.resize(tam, Image.BILINEAR))
        salida[v] = os.path.join(dir_out, f'pixal3d_{v}.png')
        lienzo.save(salida[v])
    return salida


def workflow(entradas, seed, reso, caras, tex_px, prefijo, multi, seed_estructura=None, normalizadas=None):
    """API de ComfyUI: la plantilla oficial 3d_pixal3d_trellis2_image_to_model (o 3d_pixal3d_multi_views) sin
    previews ni mapas normal/AO, más el guardado de la imagen sin fondo (para el retrato).
    seed_estructura: seed solo de la estructura gruesa (la forma y la textura usan seed)."""
    n = lambda c, **i: {'class_type': c, 'inputs': i}  # noqa: E731
    w = {
        'clip': n('CLIPVisionLoader', clip_name='dino_v3_L_naf_fp32.safetensors'),
        'unet': n('UNETLoader', unet_name='pixal3d_multiview_int8_convrot.safetensors' if multi
                  else 'pixal3d_int8_convrot.safetensors', weight_dtype='default'),
        'vae_forma': n('VAELoader', vae_name='trellis_2_shape_vae_bf16.safetensors'),
        'vae_tex': n('VAELoader', vae_name='trellis_2_texture_vae_bf16.safetensors'),
        'fondo': n('LoadBackgroundRemovalModel', bg_removal_name='birefnet.safetensors'),
    }
    vistas = {}
    for v, archivo in entradas.items():
        w[f'img_{v}'] = n('LoadImage', image=archivo)
        w[f'mask_{v}'] = n('RemoveBackground', bg_removal_model=['fondo', 0], image=[f'img_{v}', 0])
        w[f'rec_{v}'] = n('ImageCropToMask', images=[f'img_{v}', 0], masks=[f'mask_{v}', 0], width=1024, height=1024,
                          pad_factor=1.1, grow_mask=0, background='#000000')
        if normalizadas:   # vehículo: ya recortadas con la misma escala (normalizar_vistas)
            w[f'rec_{v}'] = n('LoadImage', image=normalizadas[v])
        vistas[v] = [f'rec_{v}', 0]
    # sin_fondo.png: la elegida entera con el alfa de BiRefNet (JoinImageWithAlpha usa 1 - máscara)
    w['inv'] = n('InvertMask', mask=['mask_front', 0])
    w['rgba'] = n('JoinImageWithAlpha', image=['img_front', 0], alpha=['inv', 0])
    w['sin_fondo'] = n('SaveImage', images=['rgba', 0], filename_prefix=prefijo + '_sin_fondo')
    if multi:
        w['cond'] = n('Pixal3DMultiViewConditioning', clip_vision_model=['clip', 0], fov=20.0,
                      **{v: r for v, r in vistas.items()})
    else:
        w['moge'] = n('LoadMoGeModel', model_name='moge_2_vitl_normal_fp16.safetensors')
        w['moge_inf'] = n('MoGeInference', moge_model=['moge', 0], image=vistas['front'], resolution_level=9,
                          fov_x_degrees=0.0, batch_size=4, force_projection=True, apply_mask=True)
        w['fov'] = n('MoGeGeometryToFOV', moge_geometry=['moge_inf', 0], axis='horizontal', unit='degrees')
        w['cond'] = n('Pixal3DConditioning', clip_vision_model=['clip', 0], image=vistas['front'],
                      camera_angle_x=['fov', 0])
    pos, neg = ['cond', 0], ['cond', 1]
    w.update({
        'cfg_e': n('CFGOverride', model=['unet', 0], cfg=1.0, start_percent=0.667, end_percent=1.0),
        'resc_e': n('RescaleCFG', model=['cfg_e', 0], multiplier=0.7),
        'muestreo_e': n('ModelSamplingSD3', model=['resc_e', 0], shift=5.0),
        'cfg_f': n('CFGOverride', model=['unet', 0], cfg=1.0, start_percent=0.769, end_percent=1.0),
        'resc_f': n('RescaleCFG', model=['cfg_f', 0], multiplier=0.5),
        'vacio': n('EmptyTrellis2LatentStructure', batch_size=1),
        # estructura -> forma -> subida de resolución -> textura (pasos y cfg de la plantilla)
        'ks_estructura': n('KSampler', model=['muestreo_e', 0], positive=pos, negative=neg, latent_image=['vacio', 0],
                           seed=seed if seed_estructura is None else seed_estructura, steps=12, cfg=7.5,
                           sampler_name='euler', scheduler='normal', denoise=1.0),
        'estructura': n('VaeDecodeStructureTrellis2', samples=['ks_estructura', 0], vae=['vae_forma', 0],
                        resolution='32'),
        'etapa_forma': n('Trellis2ShapeStage', positive=pos, negative=neg, voxel=['estructura', 0]),
        'ks_forma': n('KSampler', model=['resc_f', 0], positive=['etapa_forma', 0], negative=['etapa_forma', 1],
                      latent_image=['etapa_forma', 2], seed=seed, steps=20, cfg=7.5, sampler_name='euler',
                      scheduler='normal', denoise=1.0),
        'subida': n('Trellis2UpsampleStage', positive=['etapa_forma', 0], negative=['etapa_forma', 1],
                    shape_latent=['ks_forma', 0], vae=['vae_forma', 0], target_resolution=reso),
        'ks_subida': n('KSampler', model=['resc_f', 0], positive=['subida', 0], negative=['subida', 1],
                       latent_image=['subida', 2], seed=seed, steps=12, cfg=7.5, sampler_name='euler',
                       scheduler='simple', denoise=1.0),
        'forma': n('VaeDecodeShapeTrellis', samples=['ks_subida', 0], vae=['vae_forma', 0]),
        'etapa_tex': n('Trellis2TextureStage', positive=['subida', 0], negative=['subida', 1],
                       shape_latent=['ks_subida', 0]),
        'ks_tex': n('KSampler', model=['unet', 0], positive=['etapa_tex', 0], negative=['etapa_tex', 1],
                    latent_image=['etapa_tex', 2], seed=seed, steps=12, cfg=1.0, sampler_name='euler',
                    scheduler='normal', denoise=1.0),
        'tex': n('VaeDecodeTextureTrellis', samples=['ks_tex', 0], vae=['vae_tex', 0],
                 shape_subdivides=['forma', 1]),
        # malla final: remesh, reducción, UV y horneado del color
        'remesh': n('RemeshMesh', mesh=['forma', 0], resolution=768, sign_mode='udf', band=1.0, project_back=0.0,
                    fix_poles=False, smooth_iters=20, drop_small_components=0.01, precluster_max_verts=20000000,
                    **{'sign_mode.qef': False, 'sign_mode.drop_inverted_components': False,
                       'sign_mode.drop_enclosed_components': False}),
        'reducida': n('DecimateMesh', mesh=['remesh', 0], target_face_count=caras, placement_mode='midpoint'),
        'normales': n('MeshSmoothNormals', mesh=['reducida', 0], crease_angle=180.0),
        'uv': n('UnwrapMesh', mesh=['normales', 0], resolution=tex_px, segmenter='pec', padding=1,
                weld_distance=0.0002),
        'horneado': n('BakeTextureFromVoxel', mesh=['uv', 0], voxel_colors=['tex', 0], reference_mesh=['forma', 0],
                      texture_size=tex_px),
        'texturizada': n('ApplyTextureToMesh', mesh=['uv', 0], base_color=['horneado', 0]),
        'archivo': n('MeshToFile3D', mesh=['texturizada', 0]),
        'guardar': n('Save3DAdvanced', model_3d=['archivo', 0], filename_prefix=f'3d/{prefijo}', viewport_state='',
                     width=1024, height=1024),
    })
    return w


def correr(cfg, w):
    """Encola el workflow y espera; devuelve las salidas del historial."""
    url = cfg['comfyui_url']
    req = urllib.request.Request(url + '/prompt', method='POST', headers={'Content-Type': 'application/json'},
                                 data=json.dumps({'prompt': w, 'client_id': uuid.uuid4().hex}).encode())
    try:
        pid = json.load(urllib.request.urlopen(req))['prompt_id']
    except urllib.error.HTTPError as e:
        sys.exit('[malla] ComfyUI rechazó el workflow:\n' + e.read().decode()[:3000])
    while True:
        time.sleep(5)
        h = json.load(urllib.request.urlopen(f'{url}/history/{pid}'))
        if pid in h:
            st = h[pid]['status']
            if st.get('status_str') == 'error':
                msgs = [m for m in st.get('messages', []) if m[0] == 'execution_error']
                sys.exit(f'[malla] Pixal3D falló en ComfyUI: {json.dumps(msgs)[:3000]}')
            return h[pid]['outputs']


def solo_color_base(src, dst):
    """GLB con solo el color base: saca metal/rugosidad, normal, oclusión y emisión de los materiales (el resto del
    pipeline pone su rugosidad y metal 0; un mapa conectado haría que Blender ignore esos valores)."""
    with open(src, 'rb') as f:
        datos = f.read()
    largo_json = struct.unpack_from('<I', datos, 12)[0]
    gltf = json.loads(datos[20:20 + largo_json])
    resto = datos[20 + largo_json:]
    for m in gltf.get('materials', []):
        pbr = m.setdefault('pbrMetallicRoughness', {})
        pbr.pop('metallicRoughnessTexture', None)
        pbr['metallicFactor'], pbr['roughnessFactor'] = 0.0, 1.0
        for k in ('normalTexture', 'occlusionTexture', 'emissiveTexture', 'emissiveFactor'):
            m.pop(k, None)
    js = json.dumps(gltf, separators=(',', ':')).encode()
    js += b' ' * (-len(js) % 4)
    cuerpo = struct.pack('<II', len(js), 0x4E4F534A) + js + resto
    with open(dst, 'wb') as f:
        f.write(struct.pack('<III', 0x46546C67, 2, 12 + len(cuerpo)) + cuerpo)


def generar(cfg, nombre, pdir, pj, img, out):
    m = pj['malla']
    multi = bool(m.get('vistas'))
    generar_imagen.asegurar_servidor(cfg, out)
    rutas = {'front': img}
    if multi:  # en un vehículo el frente también es de Qwen (la elegida es de tres cuartos)
        rutas.update(generar_vistas(cfg, nombre, pj, img, os.path.join(pdir, 'trabajo', 'imagen')))
    entradas = {}
    for v, r in rutas.items():
        entradas[v] = f'{nombre}_pixal3d_{v}.png'
        shutil.copy(r, os.path.join(cfg['comfyui_dir'], 'input', entradas[v]))
    normalizadas = None
    if multi and pj.get('vehiculo'):
        normalizadas = {}
        for v, r in normalizar_vistas(cfg, rutas, out).items():
            normalizadas[v] = f'{nombre}_pixal3d_{v}_norm.png'
            shutil.copy(r, os.path.join(cfg['comfyui_dir'], 'input', normalizadas[v]))
    prefijo = f'gp_{nombre}_pixal3d'
    w = workflow(entradas, m['seed'], m.get('resolucion', 1536), m['caras'], m.get('textura_px', 4096), prefijo,
                 multi, m.get('seed_estructura'), normalizadas)
    with open(os.path.join(out, 'pixal3d_api.json'), 'w') as f:
        json.dump(w, f, indent=1)
    print(f'[malla] Pixal3D {"4 vistas" if multi else "1 vista"} a {m.get("resolucion", 1536)} '
          f'(seed {m["seed"]}, ~2-3 min)...', flush=True)
    t = time.time()
    salidas = correr(cfg, w)
    base = os.path.join(cfg['comfyui_dir'], 'output')
    im = salidas['sin_fondo']['images'][0]
    shutil.copy(os.path.join(base, im['subfolder'], im['filename']), os.path.join(out, 'sin_fondo.png'))
    glb = max(glob.glob(os.path.join(base, '3d', prefijo + '_*.glb')), key=os.path.getmtime)
    solo_color_base(glb, os.path.join(out, 'modelo.glb'))
    print(f'[malla] Pixal3D listo en {time.time() - t:.0f} s', flush=True)
