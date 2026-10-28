#!/usr/bin/env python3
"""AssetCrisol: imagen -> modelo 3D -> rig/animación -> sprites -> Godot, todo con IA local. Ver README.md.

uso: crisol <paso> <personaje> [opciones]   (o python3 pipeline.py ...)

configuración: config.json junto a este archivo (copiar config.ejemplo.json) o la ruta en ASSETCRISOL_CONFIG.
Los personajes, objetos y escenarios viven en `datos_dir` de la config (por defecto, esta carpeta).

  nuevo    <n> [--referencia img] [--objeto]  crea personajes/<n>/ (u objetos/<n>/) desde la plantilla
  imagen   <n>                      candidatas con ComfyUI (una por seed) -> elegir en personaje.json
  vistas   <n>                      (Pixal3D 4 vistas) espalda y costados con Qwen -> trabajo/imagen/vistas.png,
                                    para revisarlas antes de la malla (la malla las reusa; borrar una para rehacerla)
  malla    <n>                      imagen elegida -> modelo.glb texturizado (Pixal3D / TRELLIS.2)
                                    con malla.candidatos: uno por candidato -> trabajo/candidatos.png (comparar)
  comparar <n>                      rehace trabajo/candidatos.png (una fila por candidato de malla, cámara iso)
  ultratex <n>                      vuelve a pintar la malla del motor con UltraTex (ComfyUI, FLUX.2 Klein)
  guia     <n>                      renders con grilla + articulaciones para revisarlas
  articulaciones <n>                (humanoides) estima modelo.articulaciones con DWPose sobre los renders de guia
                                    (ComfyUI) y rehace guia.png para revisarlas; las anteriores quedan en
                                    modelo._articulaciones_previas
  blender  <n>                      rig + animaciones + frames + retrato (Blender headless)
                                    objetos: vista lateral + vistas isométricas
  sprites  <n>                      hoja + meta + preview.gif + retrato/frente
  retrato  <n>                      solo el retrato/frente (Blender + recorte de la imagen), sin rehacer frames
  iso      <n>                      personajes: animaciones en 8 direcciones isométricas (Blender + hojas)
  metodo   <n> [anim=kimodo|procedural ...]  método de cada animación (lista; con cambios, los guarda en
                                    personaje.json > animacion.metodos); después rehacer blender/iso/anclas
  movimiento <anim> --prompt "..." [--duracion s] [--seed n] [--muestras k]  clips candidatos con Kimodo
                                    (CPU, ~2,5 min) -> <datos_dir>/movimientos/candidatos/
  rehacer  <n1,n2,...|todos>        blender -> sprites -> iso -> anclas -> revisar de cada uno (para pasarles un
                                    cambio del rig o las animaciones); todos = personajes con malla (sin tmp_*);
                                    sigue si uno falla y al final lista los que fallaron
  revisar  <n>                      hoja de control (cabeza, codos, caminata iso de frente y de espalda, poses)
                                    -> trabajo/revision.png; después de sprites + iso
  godot    <n> [--instalar proyecto] exporta a <carpeta>/<n>/godot/ (y copia a un proyecto Godot)
  todo     <n> [--instalar proyecto] malla -> blender -> sprites -> godot (requiere imagen elegida)

  estado   [<n>] [--json]           qué pasos están hechos, cuáles quedaron viejos y qué falta elegir (sin <n>: todos)
  doctor   [--json]                 revisa la instalación: qué falta, cómo arreglarlo y qué pasos quedan deshabilitados

escenarios (nuevo <n> --escenario -> escenarios/<n>/):
  texturas <n> [--solo piso,pared]  candidatas de cada textura (piso, camino, pared) -> elegir en escenario.json
  tema     <n>                      texturas elegidas -> repetibles + colores (trabajo/tema/, preview.png)

<n> se busca en personajes/, objetos/ y escenarios/ de datos_dir.
"""
import argparse, json, os, shutil, subprocess, sys, time, urllib.request

RAIZ = os.path.dirname(os.path.abspath(__file__))
H = os.path.join(RAIZ, 'herramientas')
for sub in ('0_entorno', '1_imagen', '2_malla', '3_blender', '4_sprites', '5_godot', '6_escenario'):
    sys.path.insert(0, os.path.join(H, sub))

CONFIG = os.environ.get('ASSETCRISOL_CONFIG') or os.path.join(RAIZ, 'config.json')
if __name__ in ('__main__', 'pipeline') and sys.argv[1:2] == ['doctor']:   # antes de leer la config: la revisa él
    import doctor
    sys.exit(doctor.main(CONFIG, sys.argv[2:]))
if not os.path.exists(CONFIG):
    sys.exit(f'falta {CONFIG}: copiar config.ejemplo.json a config.json y completar las rutas (README > Instalación)')
with open(CONFIG) as f:
    CFG = json.load(f)
# dónde viven personajes/, objetos/, escenarios/ y movimientos/candidatos/ (relativo a la config)
DATOS = os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(CONFIG)), CFG.get('datos_dir') or RAIZ))


def _fusionar(base, encima):
    """dicts anidados: `encima` pisa a `base` clave por clave"""
    r = dict(base)
    for k, v in encima.items():
        r[k] = _fusionar(r[k], v) if isinstance(v, dict) and isinstance(r.get(k), dict) else v
    return r


def cargar_estilo(nombre):
    """estilos/<nombre>.json sobre estilos/animacion3d.json (el completo, con todos los valores por defecto)"""
    with open(os.path.join(RAIZ, 'estilos', 'animacion3d.json')) as f:
        est = json.load(f)
    ruta = os.path.join(RAIZ, 'estilos', f'{nombre}.json')
    if not os.path.exists(ruta):
        sys.exit(f'no existe estilos/{nombre}.json (hay: {", ".join(sorted(x[:-5] for x in os.listdir(os.path.join(RAIZ, "estilos"))))})')
    with open(ruta) as f:
        est = _fusionar(est, json.load(f))
    est['nombre'] = nombre
    return est


def cargar(nombre):
    """personajes/<n>/personaje.json u objetos/<n>/objeto.json + su estilo -> configuración efectiva.
    pj['_objeto'] / pj['_escenario'] dicen cuál es, pj['_estilo'] trae el estilo; las escalas que el json deja en
    null salen del estilo."""
    for carpeta, archivo in CARPETAS:
        pdir = os.path.join(DATOS, carpeta, nombre)
        if os.path.exists(os.path.join(pdir, archivo)):
            with open(os.path.join(pdir, archivo)) as f:
                pj = json.load(f)
            pj['_dir'], pj['_objeto'], pj['_escenario'] = pdir, carpeta == 'objetos', carpeta == 'escenarios'
            est = pj['_estilo'] = cargar_estilo(pj.get('estilo') or CFG.get('estilo', 'animacion3d'))
            if pj.get('render'):   # retoques del render solo para este personaje u objeto (metal, rugosidad...)
                est['render'] = _fusionar(est['render'], pj['render'])
            if pj['_escenario']:
                return pdir, pj
            ppu, baldosa = est['escala']['px_por_unidad'], est['escala']['baldosa_px']
            iso = pj.setdefault('isometrico', {})
            if iso.get('baldosa_px') is None:
                iso['baldosa_px'] = baldosa
            if pj['_objeto']:
                lat = pj.setdefault('lateral', {})
                if lat.get('px_por_unidad') is None:
                    lat['px_por_unidad'] = ppu
            elif pj['sprites'].get('alto_en_pantalla_px') is None:
                pj['sprites']['alto_en_pantalla_px'] = round(pj['modelo']['altura'] * ppu)
            return pdir, pj
    sys.exit(f'no existe personajes/{nombre}/, objetos/{nombre}/ ni escenarios/{nombre}/ '
             f'(crear con: crisol nuevo {nombre} [--objeto | --escenario])')


CARPETAS = (('personajes', 'personaje.json'), ('objetos', 'objeto.json'), ('escenarios', 'escenario.json'))
PASOS_ESCENARIO = ('nuevo', 'texturas', 'tema')


def paso_estado(nombre, como_json=False):
    import estado
    if nombre:
        pdir, pj = cargar(nombre)
        e = estado.estado(pdir, pj, nombre)
        print(json.dumps(e, indent=1, ensure_ascii=False) if como_json else estado.texto(e))
        return e
    todos = []
    for carpeta, archivo in CARPETAS:
        d = os.path.join(DATOS, carpeta)
        for n in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if os.path.exists(os.path.join(d, n, archivo)):
                pdir, pj = cargar(n)
                todos.append(estado.estado(pdir, pj, n))
    if como_json:
        print(json.dumps(todos, indent=1, ensure_ascii=False))
    for e in [] if como_json else todos:
        hechos = [p['paso'] for p in e['pasos'] if p['estado'] == 'hecho']
        pend = ', '.join(d['clave'] for d in e['decidir'])
        print(f'{e["nombre"]:24s} {e["tipo"]:9s} hasta {hechos[-1] if hechos else "-":9s} ' +
              (f'decidir {pend}' if pend else f'siguiente: {e["siguiente"]}' if e['siguiente'] else 'listo'))
    return todos


def paso_nuevo(nombre, referencia=None, objeto=False, escenario=False, vehiculo=False):
    carpeta, archivo = CARPETAS[2 if escenario else 1 if objeto else 0]
    pdir = os.path.join(DATOS, carpeta, nombre)
    if any(os.path.exists(os.path.join(DATOS, c, nombre)) for c, _ in CARPETAS):
        sys.exit(f'ya existe un personaje, objeto o escenario llamado {nombre}')
    os.makedirs(os.path.join(pdir, 'trabajo'))
    shutil.copy(os.path.join(RAIZ, 'plantilla', archivo), pdir)
    cfg_path = os.path.join(pdir, archivo)
    with open(cfg_path) as f:
        cfg = json.load(f)
    if vehiculo:   # objeto + la receta de autos (plantilla/vehiculo.json)
        with open(os.path.join(RAIZ, 'plantilla', 'vehiculo.json')) as f:
            cfg = _fusionar(cfg, json.load(f))
    if escenario:
        if referencia:  # estilo y colores de las texturas (IP-Adapter); mejor con `recorte` por textura
            shutil.copy(referencia, os.path.join(pdir, 'referencia.png'))
            cfg['referencia'] = 'referencia.png'
    elif referencia:
        shutil.copy(referencia, os.path.join(pdir, 'referencia.png'))
        cfg['imagen']['referencia'] = 'referencia.png'
    else:
        # sin referencia: el prompt describe al personaje/objeto desde cero (Flux.2)
        cfg['imagen']['referencia'] = None
    with open(cfg_path, 'w') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    if escenario:
        print(f'creado {carpeta}/{nombre}/ -> editar {archivo} (texturas.<clave>.descripcion) y correr: '
              f'crisol texturas {nombre}')
        return
    print(f'creado {carpeta}/{nombre}/ (estilo {CFG.get("estilo", "animacion3d")}) -> editar {archivo} '
          f'(imagen.descripcion) y correr: crisol imagen {nombre}')


def con_numpy():
    """Los pasos de escenarios usan numpy, que el python3 del sistema puede no tener: se relanza el mismo comando con
    el python del venv de ComfyUI (trae numpy y Pillow)."""
    try:
        import numpy  # noqa: F401
    except ImportError:
        py = os.path.join(CFG['comfyui_dir'], 'venv', 'bin', 'python')
        os.execv(py, [py, os.path.abspath(__file__)] + sys.argv[1:])


def paso_texturas(nombre, solo=None):
    con_numpy()
    import texturas
    pdir, pj = cargar(nombre)
    texturas.main(CFG, nombre, pj, solo.split(',') if solo else None)


def paso_tema(nombre):
    con_numpy()
    import tema
    pdir, pj = cargar(nombre)
    tema.main(pj)


def paso_imagen(nombre):
    import generar_imagen
    pdir, pj = cargar(nombre)
    generar_imagen.main(CFG, nombre, pj)


def imagen_elegida(pdir, pj):
    seed = pj['imagen'].get('elegida')
    if seed is None:
        sys.exit('falta elegir la imagen: poné la seed en personaje.json > imagen.elegida '
                 '(o el nombre de un archivo de la carpeta del personaje)')
    for p in (os.path.join(pdir, 'trabajo', 'imagen', f'cand_{seed}.png'), os.path.join(pdir, str(seed))):
        if os.path.isfile(p):
            return p
    sys.exit(f'no encuentro la imagen elegida ({seed})')


def liberar_vram_comfyui():
    try:  # descarga los modelos de ComfyUI sin cerrarlo (TRELLIS.2 necesita la VRAM)
        req = urllib.request.Request(CFG['comfyui_url'] + '/free', method='POST',
                                     data=json.dumps({'unload_models': True, 'free_memory': True}).encode(),
                                     headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=10)
        time.sleep(3)
        print('[malla] VRAM de ComfyUI liberada')
    except Exception:
        pass


def paso_vistas(nombre):
    """Solo las vistas de Qwen de Pixal3D 4 vistas + hoja frente/espalda/costados para revisarlas."""
    pdir, pj = cargar(nombre)
    m = pj['malla']
    if not pj.get('vehiculo') and (m.get('motor') != 'pixal3d' or not m.get('vistas')):
        sys.exit('vistas: solo con malla.motor = "pixal3d" y malla.vistas = true, o en un vehículo')
    img = imagen_elegida(pdir, pj)
    import generar_malla_pixal3d
    from PIL import Image, ImageDraw
    dir_img = os.path.join(pdir, 'trabajo', 'imagen')
    rutas = generar_malla_pixal3d.generar_vistas(CFG, nombre, pj, img, dir_img)
    pares = [('elegida' if 'front' in rutas or pj.get('vehiculo') else 'front', img)] + \
        [(v, rutas[v]) for v in ('front', 'back', 'left', 'right', 'atras') if v in rutas]
    ims = [(v, Image.open(r).convert('RGB')) for v, r in pares]
    ims = [(v, i.resize((int(i.width * 600 / i.height), 600))) for v, i in ims]
    hoja = Image.new('RGB', (sum(i.width for _, i in ims), 600), 'white')
    x = 0
    for v, i in ims:
        hoja.paste(i, (x, 0)); ImageDraw.Draw(hoja).text((x + 8, 8), v, fill='black'); x += i.width
    hoja.save(os.path.join(dir_img, 'vistas.png'))
    if pj.get('vehiculo'):
        print(f'[vistas] {os.path.join(dir_img, "vistas.png")}: el mismo auto, entero y con la cola bien dibujada '
              f'(si no, borrar la vista y rehacer, o cambiar malla.seed_vistas)')
        return
    print(f'[vistas] {os.path.join(dir_img, "vistas.png")}: la espalda no debe repetir lo del pecho; left mira al '
          f'borde izquierdo y right al derecho (si no, espejar o borrar y rehacer)')


def paso_revisar(nombre):
    pdir, pj = cargar(nombre)
    if pj['_objeto']:
        sys.exit('revisar: es para personajes')
    import revisar
    blender('reves', pdir, pj)   # poses con el interior de la malla en magenta -> trabajo/reves/
    print(f'[revisar] {revisar.revisar(pdir, nombre)}')


def paso_rehacer(lista):
    if lista == 'todos':
        d = os.path.join(DATOS, 'personajes')
        nombres = sorted(n for n in os.listdir(d) if not n.startswith(('tmp_', 'Old'))
                         and os.path.exists(os.path.join(d, n, 'trabajo', 'malla', 'modelo.glb')))
    else:
        nombres = [n for n in lista.split(',') if n]
    fallas = []
    for i, n in enumerate(nombres, 1):
        print(f'[rehacer] {i}/{len(nombres)} {n}', flush=True)
        t = time.time()
        try:
            for paso in (paso_blender, paso_sprites, paso_iso, paso_anclas, paso_revisar):
                paso(n)
        except (SystemExit, Exception) as e:
            fallas.append((n, paso.__name__, str(e)[-300:]))
            print(f'[rehacer] {n}: falló en {paso.__name__}: {str(e)[-300:]}', flush=True)
            continue
        print(f'[rehacer] {n} listo ({time.time() - t:.0f} s): trabajo/revision.png', flush=True)
    print(f'[rehacer] {len(nombres) - len(fallas)}/{len(nombres)} bien' +
          ''.join(f'\n  {n}: {p} ({e})' for n, p, e in fallas))


def candidatos_malla(pj):
    """malla.candidatos (personaje, objeto o vehículo): [(nombre, pj del candidato)], el principal (nombre = su motor)
    primero y el elegido (malla.elegida) al final. Cada candidato pisa claves de malla; `desde: <otro>` reusa la malla
    de ese otro candidato (sin volver a generarla) y solo le aplica lo suyo (p. ej. ultratex). None si no hay
    candidatos."""
    m = pj['malla']
    if not m.get('candidatos'):
        return None
    base = {k: v for k, v in m.items() if k not in ('candidatos', 'elegida')}
    lista = [(m.get('motor', 'trellis2'), base)] + [(n, dict(base, **c)) for n, c in m['candidatos'].items()]
    elegida = m.get('elegida', lista[0][0])
    if elegida not in dict(lista):
        sys.exit(f'[malla] malla.elegida = {elegida!r} no es ningún candidato ({", ".join(n for n, _ in lista)})')
    salida = []
    for n, mc in sorted(lista, key=lambda x: x[0] == elegida):
        pjc = json.loads(json.dumps(pj))
        pjc['malla'] = mc
        salida.append((n, pjc))
    return salida


def paso_malla(nombre):
    pdir, pj = cargar(nombre)
    lista = candidatos_malla(pj)
    if not lista:
        return generar_malla(pdir, pj, nombre)
    t = os.path.join(pdir, 'trabajo')
    actual = os.path.join(t, 'malla')
    for n, pjc in sorted(lista, key=lambda x: 'desde' in x[1]['malla']):   # los `desde` después de su base
        dst = os.path.join(t, f'malla_{n}')
        if os.path.exists(os.path.join(dst, 'modelo.glb')):
            print(f'[malla] candidato {n}: ya está (borrar trabajo/malla_{n} para rehacerlo)')
            continue
        print(f'[malla] candidato {n}', flush=True)
        shutil.rmtree(actual, ignore_errors=True)
        desde = pjc['malla'].get('desde')
        if desde:
            shutil.copytree(os.path.join(t, f'malla_{desde}'), actual)
            if os.path.exists(os.path.join(actual, 'modelo_motor.glb')):
                shutil.copy(os.path.join(actual, 'modelo_motor.glb'), os.path.join(actual, 'modelo.glb'))
            if pjc['malla'].get('ultratex'):
                liberar_vram_comfyui()
                retexturizar_ultratex(pdir, pjc, nombre)
        else:
            generar_malla(pdir, pjc, nombre)
        shutil.copytree(actual, dst)
    elegida = lista[-1][0]
    shutil.rmtree(actual, ignore_errors=True)
    shutil.copytree(os.path.join(t, f'malla_{elegida}'), actual)
    if pj.get('vehiculo'):
        print(f'[malla] candidatos listos; trabajo/malla = {elegida}. Correr `blender` para compararlos')
    else:
        print(f'[malla] candidatos listos; trabajo/malla = {elegida}')
        comparar_candidatos(pdir, lista)


VISTAS_COMPARAR = ('s', 'se', 'e', 'n', 'w')   # frente, tres cuartos, los dos costados y espalda, cámara iso (30°)


def paso_comparar(nombre):
    pdir, pj = cargar(nombre)
    lista = candidatos_malla(pj)
    if not lista or pj.get('vehiculo'):
        sys.exit('comparar: es para personajes y objetos con malla.candidatos (los vehículos comparan en `blender`)')
    comparar_candidatos(pdir, lista)


def comparar_candidatos(pdir, lista):
    """trabajo/candidatos.png: una fila por candidato de malla (el elegido, último, marcado) con la malla tal como la
    importa `blender` (soldada, sin interior, ojos) vista con la cámara iso desde VISTAS_COMPARAR. Elegir con
    malla.elegida y correr `malla` de nuevo (no regenera: copia el elegido a trabajo/malla)."""
    from PIL import Image, ImageDraw
    t = os.path.join(pdir, 'trabajo')
    lista = [(n, pjc) for n, pjc in lista if os.path.exists(os.path.join(t, f'malla_{n}', 'modelo.glb'))]
    filas = []
    for n, pjc in lista:
        pjc['_glb'] = os.path.join(t, f'malla_{n}', 'modelo.glb')
        pjc['_vistas_comparar'] = VISTAS_COMPARAR
        blender('comparar', pdir, pjc)
        filas.append((n, [Image.open(os.path.join(t, 'comparar', f'{v}.png')).convert('RGBA') for v in VISTAS_COMPARAR]))
    cajas = [im.getchannel('A').getbbox() for _, ims in filas for im in ims]
    caja = [f(c[k] for c in cajas if c) for k, f in enumerate((min, min, max, max))]   # la misma en todas: misma escala
    caja = (caja[0] - 12, caja[1] - 24, caja[2] + 12, caja[3] + 12)
    alto = 360
    ancho = round((caja[2] - caja[0]) * alto / (caja[3] - caja[1]))
    hoja = Image.new('RGB', (ancho * len(VISTAS_COMPARAR), alto * len(filas)), (120, 120, 120))
    for j, (n, ims) in enumerate(filas):
        for i, im in enumerate(ims):
            im = im.crop(caja).resize((ancho, alto), Image.LANCZOS)
            hoja.paste(im, (i * ancho, j * alto), im)
        ImageDraw.Draw(hoja).text((8, j * alto + 6), n + ('  (elegida)' if j == len(filas) - 1 else ''), fill='white')
    hoja.save(os.path.join(t, 'candidatos.png'))
    print(f'[comparar] mirar {os.path.join(t, "candidatos.png")} y elegir con malla.elegida')


def generar_malla(pdir, pj, nombre):
    img = imagen_elegida(pdir, pj)
    if pj.get('vehiculo') and pj['malla'].get('vista'):   # vehículo con TRELLIS.2: la malla sale de una vista de Qwen
        img = os.path.join(pdir, 'trabajo', 'imagen', f'vista_{pj["malla"]["vista"]}.png')
        if not os.path.exists(img):
            sys.exit(f'[malla] falta {img}: correr antes `crisol vistas {nombre}`')
    liberar_vram_comfyui()
    m = pj['malla']
    env = dict(os.environ, **CFG['env_modelos'])
    out = os.path.join(pdir, 'trabajo', 'malla')
    os.makedirs(out, exist_ok=True)
    if m.get('motor') == 'pixal3d':  # en ComfyUI (no hay log aparte: lo de ComfyUI queda en su consola)
        import generar_malla_pixal3d
        generar_malla_pixal3d.generar(CFG, nombre, pdir, pj, img, out)
        cmd = None
        if pj['_objeto'] and not pj.get('vehiculo') and not m.get('vistas') and pj['modelo'].get('alinear', True):
            # de una vista sale en el marco de la cámara (el cofre: 21° inclinado, 56° girado): se endereza el GLB
            # mismo, que es lo que copia el juego; el de la cámara queda en pixal3d_camara.glb
            shutil.copy(os.path.join(out, 'modelo.glb'), os.path.join(out, 'pixal3d_camara.glb'))
            blender('alinear', pdir, pj)
    elif m.get('motor', 'trellis2') == 'trellis2':
        cwd = CFG['trellis2_dir']
        log = os.path.join(out, 'trellis2.log')
        reso = m.get('resolucion', 512 if pj['_objeto'] else 1024)  # objetos macizos: 1024 no entra en 16 GB
        cmd = [os.path.join(cwd, 'venv', 'bin', 'python'), os.path.join(H, '2_malla', 'generar_malla_trellis.py'),
               img, out, str(m['caras']), str(reso), str(m['seed']), str(m.get('textura_px', 2048)),
               str(m.get('alfa_min', 0)), '1',
               '10' if pj['_objeto'] else '100']  # pedacitos sueltos a sacar: los objetos no llevan rig (hojas)
        env['PYTHONPATH'] = cwd
        env['TRELLIS_FONDO'] = m.get('fondo', 'u2net')  # modelo de rembg: birefnet-general recorta mejor follaje
        env['TRELLIS_MARGEN'] = str(m.get('margen') or '')  # recorte cuadrado a la máscara con margen (p. ej. 1.1)
        print(f'[malla] TRELLIS.2 (forma + textura, ~2-5 min; log: {log})')
    else:
        sys.exit(f'[malla] motor desconocido: {m.get("motor")} (pixal3d | trellis2)')
    if cmd:
        with open(log, 'w') as lf:
            r = subprocess.run(cmd, cwd=cwd, env=env, stdout=lf, stderr=subprocess.STDOUT)
        if r.returncode or not os.path.exists(os.path.join(out, 'modelo.glb')):
            sys.exit(f'[malla] falló, ver {log}')
    motor = os.path.join(out, 'modelo_motor.glb')
    if os.path.exists(motor):  # era la de la malla anterior
        os.remove(motor)
    if m.get('ultratex'):
        retexturizar_ultratex(pdir, pj, nombre)
    print('[malla] listo:', os.path.join(out, 'modelo.glb'))


def retexturizar_ultratex(pdir, pj, nombre):
    """Pinta de nuevo la malla del motor (modelo_motor.glb) con UltraTex: limpia (soldada, sin interior) ->
    6 vistas con FLUX.2 Klein -> modelo.glb. malla.ultratex: true o {"seed", "resolucion", "giro", "espalda",
    "costados", "denoise_espalda"} (giro: segunda pasada con las cámaras giradas, para los costados; espalda: la de atrás sale de
    trabajo/imagen/vista_back.png de Qwen en vez de inventarla; costados: ídem vista_left/right.png)."""
    import retexturizar_ultratex as ut
    out = os.path.join(pdir, 'trabajo', 'malla')
    motor, modelo = os.path.join(out, 'modelo_motor.glb'), os.path.join(out, 'modelo.glb')
    if os.path.exists(motor):
        shutil.copy(motor, modelo)
    else:
        shutil.copy(modelo, motor)
    blender('limpia', pdir, pj)
    op = pj['malla'].get('ultratex')
    op = op if isinstance(op, dict) else {}
    espalda = None
    if op.get('espalda'):
        espalda = os.path.join(pdir, 'trabajo', 'imagen', 'vista_back.png')
        if not os.path.exists(espalda):
            sys.exit('[ultratex] espalda: falta trabajo/imagen/vista_back.png (crisol vistas, con malla.vistas)')
    costados = None
    if op.get('costados'):
        costados = {v: os.path.join(pdir, 'trabajo', 'imagen', f'vista_{v}.png') for v in ('left', 'right')}
        for r in costados.values():
            if not os.path.exists(r):
                sys.exit(f'[ultratex] costados: falta trabajo/imagen/{os.path.basename(r)} (crisol vistas, con '
                         f'malla.vistas)')
    ut.retexturizar(CFG, nombre, os.path.join(out, 'limpia.glb'), os.path.join(out, 'sin_fondo.png'), modelo,
                    op.get('seed', 1), op.get('resolucion', 1024), pj['malla'].get('textura_px', 4096),
                    op.get('giro', 0), espalda, op.get('denoise_espalda', 0.6), costados)
    if espalda:
        print('[ultratex] mirar trabajo/malla/ultratex_espalda.png (inventada | la de Qwen encajada)')
    if costados:
        print('[ultratex] mirar trabajo/malla/ultratex_costados.png (inventados | los de Qwen encajados; arriba el '
              'costado derecho)')
    print('[ultratex] mirar trabajo/malla/ultratex_vistas.png; la malla del motor quedó en modelo_motor.glb')


def paso_ultratex(nombre):
    pdir, pj = cargar(nombre)
    if not os.path.exists(os.path.join(pdir, 'trabajo', 'malla', 'modelo.glb')):
        sys.exit('[ultratex] falta trabajo/malla/modelo.glb: correr antes `malla`')
    liberar_vram_comfyui()
    retexturizar_ultratex(pdir, pj, nombre)


def blender(modo, pdir, pj):
    # Blender lee la configuración efectiva (json del personaje/objeto + estilo), no el json crudo
    with open(os.path.join(pdir, 'trabajo', '_config.json'), 'w') as f:
        json.dump(pj, f, indent=1, ensure_ascii=False)
    r = subprocess.run([CFG['blender'], '-b', '--factory-startup', '--python',
                        os.path.join(H, '3_blender', 'blender_main.py'), '--', modo, pdir],
                       capture_output=True, text=True)
    salida = r.stdout + r.stderr
    with open(os.path.join(pdir, 'trabajo', f'blender_{modo}.log'), 'w') as f:
        f.write(salida)
    for l in salida.splitlines():
        if l.startswith('[blender]') or 'Error' in l or 'OK' in l:
            print(l)
    if r.returncode or f'{modo.upper()} OK' not in salida:
        sys.exit(f'[blender] falló, ver trabajo/blender_{modo}.log')


def paso_guia(nombre):
    import dibujar_guia
    pdir, pj = cargar(nombre)
    if pj['_objeto']:
        sys.exit('[guia] los objetos no tienen esqueleto: correr `blender` y mirar trabajo/render/')
    blender('guia', pdir, pj)
    print('[guia]', dibujar_guia.dibujar(os.path.join(pdir, 'trabajo', 'guia')))
    if not pj['modelo'].get('articulaciones'):
        print('[guia] articulaciones ESTIMADAS. Si están bien, no hace falta nada. Para ajustarlas, copiá\n'
              '       trabajo/guia/guia.json > articulaciones a personaje.json > modelo.articulaciones y editalas.')


def paso_articulaciones(nombre):
    import articulaciones_pose, generar_imagen
    pdir, pj = cargar(nombre)
    if pj['_objeto']:
        sys.exit('[articulaciones] los objetos no tienen esqueleto')
    blender('guia', pdir, pj)
    generar_imagen.asegurar_servidor(CFG, os.path.join(pdir, 'trabajo'))
    J, motivo = articulaciones_pose.estimar(CFG, nombre, os.path.join(pdir, 'trabajo', 'guia'), pj['modelo']['altura'])
    if motivo:
        print(f'[articulaciones] no se pudieron estimar ({motivo}): quedan las de antes; cargarlas a mano mirando guia.png')
        paso_guia(nombre)
        return
    ruta = os.path.join(pdir, 'personaje.json')
    with open(ruta) as f:
        crudo = json.load(f)
    if crudo['modelo'].get('articulaciones'):
        crudo['modelo']['_articulaciones_previas'] = crudo['modelo']['articulaciones']
    crudo['modelo']['articulaciones'] = J
    with open(ruta, 'w') as f:
        json.dump(crudo, f, indent=2, ensure_ascii=False)
    print('[articulaciones] estimadas con DWPose (trabajo/guia/pose_frente.png): revisarlas en guia.png')
    paso_guia(nombre)


VISTAS_VEHICULO = ('juego', 'tres_cuartos', 'costado', 'arriba')


def paso_blender(nombre):
    pdir, pj = cargar(nombre)
    if pj.get('vehiculo'):
        return blender_vehiculo(pdir, pj)
    blender('objeto' if pj['_objeto'] else 'construir', pdir, pj)


def blender_vehiculo(pdir, pj):
    """Sin candidatos: vehiculo.glb + revision.png. Con candidatos: arma cada uno (vehiculo_<c>.glb,
    revision_<c>_<vista>.png) y deja vehiculo.glb / revision_<vista>.png del elegido (va último: el .blend es el suyo);
    revision.png = una fila por candidato."""
    t = os.path.join(pdir, 'trabajo')
    lista = candidatos_malla(pj)
    if not lista:
        blender('vehiculo', pdir, pj)
        recortar_tarjeta(t)
        return hoja_vehiculo(t, [None])
    lista = [(n, pjc) for n, pjc in lista if os.path.exists(os.path.join(t, f'malla_{n}', 'modelo.glb'))]
    for n, pjc in lista:
        print(f'[vehiculo] candidato {n}', flush=True)
        shutil.rmtree(os.path.join(t, 'malla'), ignore_errors=True)
        shutil.copytree(os.path.join(t, f'malla_{n}'), os.path.join(t, 'malla'))
        blender('vehiculo', pdir, pjc)
        recortar_tarjeta(t)
        shutil.copy(os.path.join(t, 'vehiculo.glb'), os.path.join(t, f'vehiculo_{n}.glb'))
        shutil.copy(os.path.join(t, 'tarjeta.png'), os.path.join(t, f'tarjeta_{n}.png'))
        for v in VISTAS_VEHICULO:
            shutil.copy(os.path.join(t, f'revision_{v}.png'), os.path.join(t, f'revision_{n}_{v}.png'))
    hoja_vehiculo(t, [n for n, _ in lista], elegida=lista[-1][0])


def recortar_tarjeta(t, ancho=512):
    """trabajo/tarjeta.png: el render de la tarjeta (vehiculo.tarjeta) recortado al auto, `ancho` px (tamaño de tarjeta
    para un selector)."""
    from PIL import Image
    im = Image.open(os.path.join(t, 'tarjeta_render.png')).convert('RGBA')
    im = im.crop(im.getchannel('A').point(lambda a: 255 if a > 8 else 0).getbbox())
    im.resize((ancho, round(im.height * ancho / im.width)), Image.LANCZOS).save(os.path.join(t, 'tarjeta.png'))


def hoja_vehiculo(t, candidatos, elegida=None):
    """trabajo/revision.png: sin candidatos ([None]) las cuatro vistas en 2x2; con candidatos una fila por cada uno
    (el nombre arriba a la izquierda, el elegido marcado)."""
    from PIL import Image, ImageDraw
    if candidatos == [None]:
        ims = [Image.open(os.path.join(t, f'revision_{v}.png')).convert('RGB') for v in VISTAS_VEHICULO]
        w, h = ims[0].size
        hoja = Image.new('RGB', (2 * w, 2 * h))
        for i, (v, im) in enumerate(zip(VISTAS_VEHICULO, ims)):
            hoja.paste(im, ((i % 2) * w, (i // 2) * h))
            ImageDraw.Draw(hoja).text(((i % 2) * w + 8, (i // 2) * h + 8), v, fill='black')
    else:
        w, h = 480, 270
        hoja = Image.new('RGB', (4 * w, len(candidatos) * h))
        for j, n in enumerate(candidatos):
            for i, v in enumerate(VISTAS_VEHICULO):
                im = Image.open(os.path.join(t, f'revision_{n}_{v}.png')).convert('RGB')
                if v in ('juego', 'tres_cuartos'):   # el auto ocupa el centro: recortar para verlo grande
                    W, H = im.size
                    im = im.crop((W // 4, H // 5, W * 3 // 4, H * 4 // 5))
                hoja.paste(im.resize((w, h)), (i * w, j * h))
            ImageDraw.Draw(hoja).text((8, j * h + 8), n + ('  (elegida)' if n == elegida else ''), fill='black')
    hoja.save(os.path.join(t, 'revision.png'))
    print(f'[vehiculo] {os.path.join(t, "vehiculo.glb")}; mirar {os.path.join(t, "revision.png")}')


def paso_iso(nombre):
    import armar_iso
    pdir, pj = cargar(nombre)
    if pj['_objeto']:
        sys.exit('[iso] los objetos ya salen en isométrico con `blender` + `sprites`')
    blender('iso', pdir, pj)
    armar_iso.armar(pdir, nombre, pj, os.path.join(dir_godot(pdir), 'personajes', nombre, 'iso'))


def paso_anclas(nombre):
    """Huesos por cuadro de las animaciones iso (sin renderizar) -> trabajo/iso/anclas.json."""
    pdir, pj = cargar(nombre)
    if pj['_objeto']:
        sys.exit('[anclas] los objetos no tienen esqueleto')
    blender('anclas', pdir, pj)
    print('[anclas]', os.path.join(pdir, 'trabajo', 'iso', 'anclas.json'))


def paso_metodo(nombre, cambios):
    """Lista con qué método sale cada animación (y el recomendado); `anim=metodo` lo cambia en personaje.json."""
    import armar_iso, metodos
    pdir, pj = cargar(nombre)
    if pj['_objeto']:
        sys.exit('[metodo] los objetos no tienen animaciones')
    bib = metodos.biblioteca()
    if cambios:
        ruta = os.path.join(pdir, 'personaje.json')
        with open(ruta) as f:
            crudo = json.load(f)
        elegidos = crudo.setdefault('animacion', {}).setdefault('metodos', {})
        for c in cambios:
            anim_, _, m = c.partition('=')
            if anim_ not in armar_iso.NOMBRES:
                sys.exit(f'[metodo] {anim_}: no es una animación ({", ".join(armar_iso.NOMBRES)})')
            elegidos[anim_] = m
            if m == metodos.recomendado(anim_, bib):
                del elegidos[anim_]          # el recomendado es el de por defecto: no hace falta guardarlo
            try:
                metodos.metodo(anim_, {'metodos': {anim_: m}}, bib)   # valida (método y clip)
            except ValueError as e:
                sys.exit(f'[metodo] {e}')
        if not elegidos:
            del crudo['animacion']['metodos']
        with open(ruta, 'w') as f:
            json.dump(crudo, f, indent=2, ensure_ascii=False)
            f.write('\n')
        pj['animacion'] = crudo['animacion']
    for anim_ in armar_iso.NOMBRES:
        m, rec = metodos.metodo(anim_, pj['animacion'], bib), metodos.recomendado(anim_, bib)
        nota = bib.get(anim_, {}).get('_nota', '')
        print(f'  {anim_:14s} {m:10s}' + ('' if m == rec else f' (recomendado: {rec})') +
              (f'  kimodo: {nota}' if nota else ''))
    if cambios:
        print(f'[metodo] guardado en personaje.json; rehacer: blender, sprites, iso, anclas {nombre}')


def paso_movimiento(anim_, prompt, duracion, seed, muestras):
    """Clips candidatos con Kimodo (en la CPU: no compite con la GPU). Elegir una muestra mirando la hoja de
    esqueletos, copiarla a movimientos/<anim>.npz y cargarla en movimientos/biblioteca.json."""
    import armar_iso
    if anim_ not in armar_iso.NOMBRES:
        sys.exit(f'[movimiento] {anim_}: no es una animación ({", ".join(armar_iso.NOMBRES)})')
    if not prompt:
        sys.exit('[movimiento] falta --prompt (en inglés, p. ej. "A person walks forward at a normal pace.")')
    kd = CFG['kimodo_dir']
    env = dict(os.environ, **CFG['env_modelos'], CUDA_VISIBLE_DEVICES='', TEXT_ENCODER_DEVICE='cpu',
               MOVIMIENTOS_CANDIDATOS=os.path.join(DATOS, 'movimientos', 'candidatos'),
               TEXT_ENCODER_MODE='local', TEXT_ENCODERS_DIR=os.path.join(kd, 'text_encoders'))
    subprocess.run([os.path.join(kd, 'venv', 'bin', 'python'), os.path.join(H, '3_blender', 'generar_movimiento.py'),
                    anim_, prompt, '--duracion', str(duracion), '--seed', str(seed), '--muestras', str(muestras)],
                   env=env, check=True)


def dir_godot(pdir):
    return os.path.join(pdir, 'godot')


def paso_sprites(nombre):
    import armar_tira
    pdir, pj = cargar(nombre)
    if pj['_objeto']:
        import armar_objeto
        return armar_objeto.armar(pdir, nombre, pj, os.path.join(dir_godot(pdir), 'objetos', nombre))
    meta = armar_tira.armar(pdir, nombre, pj, os.path.join(dir_godot(pdir), 'personajes', nombre))
    print('[sprites] preview:', os.path.join(pdir, 'preview.gif'))
    return meta


def paso_retrato(nombre):
    import armar_tira
    pdir, pj = cargar(nombre)
    if pj['_objeto']:
        sys.exit('[retrato] los objetos no tienen retrato')
    blender('retrato', pdir, pj)
    dg = os.path.join(dir_godot(pdir), 'personajes', nombre)
    os.makedirs(dg, exist_ok=True)
    mp = os.path.join(dg, f'{nombre}_meta.json')
    meta = json.load(open(mp)) if os.path.exists(mp) else None
    armar_tira.retratos(pdir, nombre, pj, dg, meta if meta is not None else {})
    if meta is not None:
        with open(mp, 'w') as f:
            json.dump(meta, f, indent=1)
    print('[retrato]', os.path.join(dg, f'{nombre}_retrato.png'))


def paso_godot(nombre, instalar=None):
    import exportar_godot
    pdir, pj = cargar(nombre)
    if pj['_objeto']:
        import exportar_objeto
        exportar_objeto.exportar(nombre, dir_godot(pdir))
        if instalar:
            exportar_godot.instalar(nombre, dir_godot(pdir), os.path.abspath(instalar), CFG.get('godot'), 'objetos')
        return
    with open(os.path.join(dir_godot(pdir), 'personajes', nombre, f'{nombre}_meta.json')) as f:
        meta = json.load(f)
    exportar_godot.exportar(nombre, dir_godot(pdir), meta)
    if os.path.exists(os.path.join(dir_godot(pdir), 'personajes', nombre, 'iso', f'{nombre}_iso_meta.json')):
        exportar_godot.exportar_iso(nombre, dir_godot(pdir))
    if instalar:
        exportar_godot.instalar(nombre, dir_godot(pdir), os.path.abspath(instalar), CFG.get('godot'))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('paso', choices=['nuevo', 'imagen', 'vistas', 'revisar', 'rehacer', 'malla', 'ultratex', 'guia', 'articulaciones', 'blender', 'sprites', 'retrato',
                                     'iso', 'anclas', 'godot', 'todo', 'comparar', 'texturas', 'tema', 'metodo', 'movimiento', 'estado'])
    ap.add_argument('personaje', nargs='?', help='personaje, objeto o escenario (en `movimiento`, la animación)')
    ap.add_argument('cambios', nargs='*', help='paso metodo: anim=kimodo|procedural')
    ap.add_argument('--prompt', help='paso movimiento: descripción del movimiento (en inglés)')
    ap.add_argument('--duracion', type=float, default=4.0, help='paso movimiento: segundos (máx. 10)')
    ap.add_argument('--seed', type=int, default=1, help='paso movimiento')
    ap.add_argument('--muestras', type=int, default=3, help='paso movimiento: variantes de la semilla')
    ap.add_argument('--referencia', help='imagen de referencia (paso nuevo)')
    ap.add_argument('--objeto', action='store_true', help='paso nuevo: crear un objeto (objetos/<n>/) en vez de un personaje')
    ap.add_argument('--vehiculo', action='store_true', help='paso nuevo: un objeto con la receta de autos (README > Vehículos)')
    ap.add_argument('--escenario', action='store_true', help='paso nuevo: crear un escenario (escenarios/<n>/)')
    ap.add_argument('--solo', metavar='CLAVES', help='paso texturas: solo estas (p. ej. piso,pared); las demás quedan')
    ap.add_argument('--instalar', metavar='PROYECTO_GODOT', help='copiar el resultado a este proyecto Godot')
    ap.add_argument('--json', action='store_true', help='paso estado: salida en JSON')
    a = ap.parse_args()
    if a.paso == 'estado':
        return paso_estado(a.personaje, a.json)
    if not a.personaje:
        ap.error(f'{a.paso}: falta el nombre')
    es_escenario = os.path.exists(os.path.join(DATOS, 'escenarios', a.personaje, 'escenario.json'))
    if a.cambios and a.paso != 'metodo':
        sys.exit(f'{a.paso}: argumentos de más: {" ".join(a.cambios)}')
    if a.paso not in ('nuevo', 'movimiento') and es_escenario != (a.paso in PASOS_ESCENARIO):
        sys.exit(f'{a.paso}: es un paso de {"personajes y objetos" if es_escenario else "escenarios"}')
    if a.paso == 'nuevo':
        paso_nuevo(a.personaje, a.referencia, a.objeto or a.vehiculo, a.escenario, a.vehiculo)
    elif a.paso == 'texturas':
        paso_texturas(a.personaje, a.solo)
    elif a.paso == 'tema':
        paso_tema(a.personaje)
    elif a.paso == 'imagen':
        paso_imagen(a.personaje)
    elif a.paso == 'vistas':
        paso_vistas(a.personaje)
    elif a.paso == 'rehacer':
        paso_rehacer(a.personaje)
    elif a.paso == 'revisar':
        paso_revisar(a.personaje)
    elif a.paso == 'malla':
        paso_malla(a.personaje)
    elif a.paso == 'comparar':
        paso_comparar(a.personaje)
    elif a.paso == 'ultratex':
        paso_ultratex(a.personaje)
    elif a.paso == 'guia':
        paso_guia(a.personaje)
    elif a.paso == 'articulaciones':
        paso_articulaciones(a.personaje)
    elif a.paso == 'blender':
        paso_blender(a.personaje)
    elif a.paso == 'sprites':
        paso_sprites(a.personaje)
    elif a.paso == 'retrato':
        paso_retrato(a.personaje)
    elif a.paso == 'iso':
        paso_iso(a.personaje)
    elif a.paso == 'anclas':
        paso_anclas(a.personaje)
    elif a.paso == 'metodo':
        paso_metodo(a.personaje, a.cambios)
    elif a.paso == 'movimiento':
        paso_movimiento(a.personaje, a.prompt, a.duracion, a.seed, a.muestras)
    elif a.paso == 'godot':
        paso_godot(a.personaje, a.instalar)
    elif a.paso == 'todo':
        paso_malla(a.personaje); paso_blender(a.personaje); paso_sprites(a.personaje)
        paso_godot(a.personaje, a.instalar)


if __name__ == '__main__':
    main()
