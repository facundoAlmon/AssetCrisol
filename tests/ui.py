#!/usr/bin/env python3
"""Test de la UI web (`crisol ui`) sin GPU: levanta el servidor sobre una copia de los ejemplos en una carpeta temporal
y prueba la página, la API, la seguridad (Host, Origin, rutas fuera del asset), elegir/ajustar, crear un asset con
una imagen subida y la cola (un paso que sale enseguida, el SSE y cancelar uno que corre). No corre Blender ni nada
que use la GPU (~10 s).

uso: python3 tests/ui.py [--dejar]
  --dejar   no borrar la carpeta temporal
"""
import glob, json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.error, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEJAR = '--dejar' in sys.argv
fallas = []


def chequear(ok, que, detalle=''):
    print(f"  {'✔' if ok else '✘'} {que}" + (f': {detalle}' if detalle and not ok else ''), flush=True)
    if not ok:
        fallas.append(que)
    return ok


def pedir(base, ruta, metodo='GET', cuerpo=None, tipo='application/json', host=None, origen=True, crudo=False):
    """(código, cuerpo: dict/str/bytes)."""
    datos = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo).encode() if cuerpo is not None else None
    r = urllib.request.Request(base + ruta, data=datos, method=metodo)
    if datos is not None:
        r.add_header('Content-Type', tipo)
    if origen and metodo != 'GET':
        r.add_header('Origin', base.rstrip('/'))
    if host:
        r.add_header('Host', host)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            codigo, b = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        codigo, b = e.code, e.read()
    if crudo:
        return codigo, b
    try:
        return codigo, json.loads(b)
    except ValueError:
        return codigo, b.decode(errors='replace')


def puerto_libre():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def probar_cancelar(tmp):
    """La cola en el proceso, con un 'pipeline' falso que tarda: cancelar el que corre y quitar uno pendiente."""
    sys.path[:0] = [os.path.join(RAIZ, 'herramientas', '0_entorno'), os.path.join(RAIZ, 'herramientas', 'ui')]
    import operaciones as op
    from cola import Cola
    os.makedirs(os.path.join(tmp, 'falso'))
    falso = os.path.join(tmp, 'falso', 'pipeline.py')   # se llama como el de verdad: la cola reconoce su PID por eso
    with open(falso, 'w') as f:
        f.write('import time, sys\nprint("[falso] empiezo", file=sys.stderr, flush=True)\ntime.sleep(60)\n')
    op.PY, op.PIPELINE = sys.executable, falso
    c = Cola(os.path.join(tmp, 'cola_prueba'))
    a, b = c.agregar(['imagen', 'x'], 'x', 'personaje'), c.agregar(['malla', 'x'], 'x', 'personaje')
    for _ in range(50):
        if a['estado'] == 'corriendo':
            break
        time.sleep(0.1)
    chequear(a['estado'] == 'corriendo' and b['estado'] == 'pendiente', 'cola: uno corre y el otro espera')
    c.quitar(b['id'])
    chequear(b['estado'] == 'cancelado', 'cola: quitar un pendiente')
    c.quitar(a['id'])
    for _ in range(100):
        if a['estado'] != 'corriendo':
            break
        time.sleep(0.1)
    chequear(a['estado'] == 'cancelado', 'cola: cancelar el que corre (killpg)', a['estado'])
    import re
    chequear(re.search(r'^\d\d:\d\d:\d\d \[falso\] empiezo', c.log(a['id']), re.M), 'cola: log con la hora', c.log(a['id']))
    c2 = Cola(os.path.join(tmp, 'cola_prueba'))   # el historial sobrevive a un reinicio
    chequear([t['estado'] for t in c2.trabajos] == ['cancelado', 'cancelado'], 'cola: historial en cola.json')
    # la UI se cierra con un paso corriendo: al volver a abrirla se lo sigue esperando (no arranca otro encima)
    d, e = c2.agregar(['iso', 'y'], 'y', 'personaje'), c2.agregar(['anclas', 'y'], 'y', 'personaje')
    for _ in range(50):
        if d['estado'] == 'corriendo':
            break
        time.sleep(0.1)
    c3 = Cola(os.path.join(tmp, 'cola_prueba'))   # c2 sigue viva, como el proceso huérfano de una UI cerrada
    d3, e3 = c3.buscar(d['id']), c3.buscar(e['id'])
    time.sleep(1.5)
    chequear(d3['estado'] == 'corriendo' and e3['estado'] == 'pendiente', 'cola: reabrir espera al paso que sigue corriendo',
             f'{d3["estado"]} {e3["estado"]}')
    c2.quitar(e['id'])
    c3.trabajos.remove(e3)   # que c3 no lo lance: lo maneja c2
    c3.quitar(d3['id'])
    for _ in range(100):
        if d3['estado'] != 'corriendo':
            break
        time.sleep(0.1)
    chequear(d3['estado'] in ('cancelado', 'fallo'), 'cola: cancelar un paso que quedó de antes', d3['estado'])


def probar_movimientos(base, datos):
    """La biblioteca de movimientos (`crisol clip`) sin correr Kimodo: candidatos copiados de los clips del repo."""
    print('movimientos')
    from PIL import Image
    repo = os.path.join(RAIZ, 'herramientas', '3_blender', 'movimientos')
    bib_repo = open(os.path.join(repo, 'biblioteca.json')).read()
    cand = os.path.join(datos, 'movimientos', 'candidatos')
    os.makedirs(cand, exist_ok=True)
    for i in range(2):
        shutil.copy(os.path.join(repo, 'correr.npz'), os.path.join(cand, f'correr_s3_{i}.npz'))
    Image.new('RGB', (600, 480), 'white').save(os.path.join(cand, 'correr_s3.png'))   # 2 filas de 240 px
    c, d = pedir(base, 'api/movimientos')
    cs = {x['id']: x for x in d.get('candidatos', [])} if c == 200 else {}
    chequear(set(cs) == {'correr_s3_0', 'correr_s3_1'} and cs['correr_s3_1'].get('duracion') == 3.0 and
             'jogging' in cs['correr_s3_1'].get('prompt', '') and cs['correr_s3_1']['hoja'] == 'correr_s3.png',
             'candidatos con duración y prompt (leídos sin numpy)', json.dumps(d)[:300])
    chequear({x['animacion']: x['origen'] for x in d.get('biblioteca', [])}.get('caminar') == 'repo', 'biblioteca del repo')
    c, b = pedir(base, 'movimientos/correr_s3.png?fila=1', crudo=True)
    chequear(c == 200 and Image.open(__import__('io').BytesIO(b)).size == (600, 240), 'fila de la hoja de una muestra')
    c, _ = pedir(base, 'movimientos/correr_s3.png?fila=2', crudo=True)
    chequear(c == 404, 'fila que no está: 404')
    c, _ = pedir(base, 'api/movimientos/clip', 'POST', {'animacion': 'correr', 'candidato': 'correr_s3_1'}, origen=False)
    chequear(c == 403, 'pasar un clip sin Origin: 403')
    for malo in ({'animacion': 'idle', 'candidato': 'correr_s3_1'}, {'animacion': 'correr', 'candidato': '../x_s1_0'},
                 {'animacion': 'correr', 'candidato': 'correr_s9_0'}, {'animacion': 'correr'},
                 {'animacion': 'correr', 'candidato': 'correr_s3_1', 'hasta': 99}):
        c, _ = pedir(base, 'api/movimientos/clip', 'POST', malo)
        chequear(c == 400, f'clip rechazado: {json.dumps(malo)}', str(c))
    propia = os.path.join(datos, 'movimientos')
    chequear(not os.path.exists(os.path.join(propia, 'correr.npz')), 'un clip rechazado no copia nada')
    c, d = pedir(base, 'api/movimientos/clip', 'POST', {'animacion': 'correr', 'candidato': 'correr_s3_1', 'desde': 0.5,
                                                         'hasta': '', 'recomendado': True})
    e = {x['animacion']: x for x in d.get('biblioteca', [])}.get('correr', {}) if c == 200 else {}
    chequear(e.get('origen') == 'propia' and e.get('recomendado') and e.get('desde') == 0.5 and e.get('hasta') is None and
             e.get('candidato') == 'correr_s3_1' and os.path.isfile(os.path.join(propia, 'correr.npz')),
             'pasar un candidato a la biblioteca propia', json.dumps(d)[:300])
    chequear(open(os.path.join(repo, 'biblioteca.json')).read() == bib_repo, 'la biblioteca del repo no cambia')
    c, d = pedir(base, 'api/movimientos/clip', 'POST', {'animacion': 'golpe', 'recomendado': True, 'desde': ''})
    e = {x['animacion']: x for x in d.get('biblioteca', [])}.get('golpe', {}) if c == 200 else {}
    chequear(e.get('origen') == 'repo+propia' and e.get('recomendado') and e.get('desde') is None and e.get('hasta') == 1.3,
             'cambiar una entrada del repo desde la propia', json.dumps(e))
    c, d = pedir(base, 'api/movimientos/clip', 'POST', {'animacion': 'patada', 'candidato': 'correr_s3_0'})
    chequear(c == 200, 'clip para una animación sin clip en el repo')
    c, d = pedir(base, 'api/assets/cris/metodos')
    pat = next((a for a in d if a['animacion'] == 'patada'), {}) if c == 200 else {}
    chequear(pat.get('metodo') == 'procedural' and pat.get('nota', '').startswith('kimodo'), 'Ajustes ofrece el clip propio',
             json.dumps(pat))
    c, d = pedir(base, 'api/assets/cris/metodos', 'POST', {'cambios': {'patada': 'kimodo'}})
    json_cris = os.path.join(datos, 'personajes', 'cris', 'personaje.json')
    chequear(c == 200 and json.load(open(json_cris))['animacion']['metodos'].get('patada') == 'kimodo',
             'usar el clip propio en un personaje')
    for anim in ('correr', 'golpe'):
        c, d = pedir(base, 'api/movimientos/clip', 'POST', {'animacion': anim, 'quitar': True})
        e = {x['animacion']: x for x in d.get('biblioteca', [])}.get(anim, {}) if c == 200 else {}
        chequear(e.get('origen') == 'repo', f'quitar {anim}: vuelve el del repo', json.dumps(e))
    chequear(not os.path.exists(os.path.join(propia, 'correr.npz')), 'quitar borra el .npz propio')


def main():
    tmp = tempfile.mkdtemp(prefix='crisol_ui_')
    srv = None
    try:
        cfg_ruta = os.environ.get('ASSETCRISOL_CONFIG') or os.path.join(RAIZ, 'config.json')
        with open(cfg_ruta) as f:
            cfg = json.load(f)
        cfg['datos_dir'] = os.path.join(tmp, 'datos')
        with open(os.path.join(tmp, 'config.json'), 'w') as f:
            json.dump(cfg, f)
        shutil.copytree(os.path.join(RAIZ, 'ejemplos'), cfg['datos_dir'])
        env = dict(os.environ, ASSETCRISOL_CONFIG=os.path.join(tmp, 'config.json'))
        puerto = puerto_libre()
        base = f'http://127.0.0.1:{puerto}/'
        srv = subprocess.Popen([sys.executable, os.path.join(RAIZ, 'crisol'), 'ui', '--puerto', str(puerto), '--no-abrir'],
                               env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for _ in range(100):
            try:
                urllib.request.urlopen(base, timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        print(f'crisol ui en {base} (datos: {cfg["datos_dir"]})')

        print('página')
        web = os.path.join(RAIZ, 'herramientas', 'ui', 'web')
        estaticos = ['', 'app.mjs', 'estilos.css', 'favicon.svg'] + [os.path.relpath(p, web) for p in
                                                                   glob.glob(os.path.join(web, '*', '*.mjs'))]
        malos = [r for r in estaticos if pedir(base, r, crudo=True)[0] != 200]
        chequear(not malos, f'{len(estaticos)} archivos de la página', ', '.join(malos))
        if shutil.which('node'):
            mal = [p for p in glob.glob(os.path.join(web, '**', '*.mjs'), recursive=True)
                   if subprocess.run(['node', '--check', p], capture_output=True).returncode]
            chequear(not mal, 'sintaxis de los módulos (node --check)', ', '.join(mal))
        es, en = (open(os.path.join(web, 'i18n', f'{x}.mjs')).read() for x in ('es', 'en'))
        claves = lambda s: {l.split("'")[1] for l in s.splitlines() if l.startswith("  '")}   # noqa: E731
        chequear(claves(es) == claves(en), 'mismas claves en es y en', ', '.join(sorted(claves(es) ^ claves(en))))

        print('lectura')
        c, d = pedir(base, 'api/assets')
        nombres = {a['nombre']: a for a in d.get('assets', [])} if c == 200 else {}
        chequear({'cris', 'caja', 'bosque'} <= set(nombres), 'api/assets lista los ejemplos')
        chequear(all(a.get('miniatura') for a in nombres.values()), 'todos con miniatura')
        c, d = pedir(base, 'api/assets/cris')
        chequear(c == 200 and d['tipo'] == 'personaje' and d['pasos'], 'api/assets/cris')
        c, _ = pedir(base, 'api/assets/no_existe')
        chequear(c == 400, 'asset que no existe: 400')
        for r in ('recetas', 'estilos', 'animaciones', 'cola', 'movimientos'):
            c, _ = pedir(base, 'api/' + r)
            chequear(c == 200, f'api/{r}')
        c, d = pedir(base, 'api/animaciones')
        chequear(len(d) >= 15 and d[1] == {'id': 'caminar', 'godot': 'walk'}, 'animaciones sin importar bpy')
        mini = nombres.get('caja', {}).get('miniatura')
        c, b = pedir(base, f'mini/caja/{mini}?lado=100', crudo=True)
        chequear(c == 200 and b[:4] == b'\x89PNG', 'miniatura PNG')
        c, b = pedir(base, f'archivos/caja/{mini}', crudo=True)
        chequear(c == 200 and len(b) > 1000, 'archivo del asset')
        c, d = pedir(base, 'api/assets/caja')
        g3d = next((g for g in d.get('visuales', []) if g['id'] == '3d'), None)
        chequear(g3d is not None, 'grupo 3d en el visor de la caja')
        if g3d:
            r = urllib.request.urlopen(base + 'archivos/caja/' + g3d['archivos'][0], timeout=30)
            chequear(r.headers['Content-Type'] == 'model/gltf-binary' and r.read(4) == b'glTF', '.glb con su mimetype')
        malos = [r for r in ('three.module.min.js', 'GLTFLoader.js', 'OrbitControls.js', 'BufferGeometryUtils.js')
                 if pedir(base, 'vendor/three/' + r, crudo=True)[0] != 200]
        chequear(not malos, 'three.js vendorizado', ', '.join(malos))

        print('seguridad')
        c, _ = pedir(base, 'api/assets', host='evil.example:80')
        chequear(c == 403, 'Host ajeno: 403')
        c, _ = pedir(base, 'api/cola', 'POST', {'paso': 'godot', 'nombre': 'caja'}, origen=False)
        chequear(c == 403, 'POST sin Origin: 403')
        for r in ('archivos/caja/..%2F..%2F..%2Fconfig.json', 'archivos/caja/../../config.json', '..%2F..%2Fpipeline.py'):
            c, _ = pedir(base, r, crudo=True)
            chequear(c in (403, 404), f'{r}: fuera de la carpeta', str(c))
        c, _ = pedir(base, 'api/cola', 'POST', {'paso': 'rm', 'nombre': 'caja'})
        chequear(c == 400, 'paso desconocido: 400')

        print('elegir y ajustar')
        json_caja = os.path.join(cfg['datos_dir'], 'objetos', 'caja', 'objeto.json')
        c, _ = pedir(base, 'api/assets/caja/elegir', 'POST', {'clave': 'modelo.altura', 'valor': 3})
        chequear(c == 400, 'elegir con una clave que no es elección: 400')
        c, _ = pedir(base, 'api/assets/caja/json', 'PATCH', {'cambios': {'modelo.altura': 0.9}})
        chequear(c == 200 and json.load(open(json_caja))['modelo']['altura'] == 0.9, 'ajustar modelo.altura')
        c, _ = pedir(base, 'api/assets/caja/json', 'PATCH', {'cambios': {'imagen.elegida': 1}})
        chequear(c == 400, 'ajustar no elige: 400')
        nuevo = json.load(open(json_caja))
        nuevo.setdefault('imagen', {})['elegida'] = 'otra'
        c, _ = pedir(base, 'api/assets/caja/json', 'PUT', {'json': nuevo})
        chequear(c == 400, 'json completo no cambia elecciones: 400')

        print('candidatos de malla')
        cands = {'pixal3d': {'motor': 'pixal3d', 'resolucion': 1024, 'seed': 1, 'caras': 200000},
                 'ultratex': {'desde': 'trellis2', 'ultratex': {'seed': 2, 'giro': 45}}}
        c, _ = pedir(base, 'api/assets/caja/json', 'PATCH', {'cambios': {'malla.motor': 'trellis2', 'malla.candidatos': cands}})
        chequear(c == 200 and json.load(open(json_caja))['malla']['candidatos'] == cands, 'guardar malla.candidatos')
        trabajo_caja = os.path.join(cfg['datos_dir'], 'objetos', 'caja', 'trabajo')
        for n in ('pixal3d', 'ultratex'):   # como si `malla` los hubiera generado
            os.makedirs(os.path.join(trabajo_caja, f'malla_{n}'), exist_ok=True)
            open(os.path.join(trabajo_caja, f'malla_{n}', 'modelo.glb'), 'wb').close()
        c, d = pedir(base, 'api/assets/caja')
        chequear(c == 200 and set(d.get('mallas_hechas', {})) == {'pixal3d', 'ultratex'}, 'candidatos ya generados en el detalle')
        for malo in ('..', '..%2F..%2Fimagen', 'no_existe', 'Pixal3D'):
            c, _ = pedir(base, f'api/assets/caja/malla/{malo}/rehacer', 'POST', {})
            chequear(c in (400, 404), f'rehacer candidato {malo}: rechazado', str(c))
        chequear(os.path.isfile(os.path.join(trabajo_caja, 'malla', 'modelo.glb')) and
                 os.path.isdir(os.path.join(trabajo_caja, 'malla_pixal3d')), 'rehacer rechazado no borró nada')
        c, d = pedir(base, 'api/assets/caja/malla/trellis2/rehacer', 'POST', {})   # trellis2 no está hecho: el desde sí
        chequear(c == 200 and d['borrados'] == ['ultratex'] and os.path.isdir(os.path.join(trabajo_caja, 'malla_pixal3d')),
                 'rehacer borra el candidato y los que se hacen desde él', json.dumps(d))
        c, d = pedir(base, 'api/assets/caja/malla/pixal3d/rehacer', 'POST', {}, origen=False)
        chequear(c == 403, 'rehacer sin Origin: 403')
        c, d = pedir(base, 'api/assets/caja/malla/pixal3d/rehacer', 'POST', {})
        chequear(c == 200 and d['borrados'] == ['pixal3d'] and not os.path.exists(os.path.join(trabajo_caja, 'malla_pixal3d')),
                 'rehacer un candidato generado')

        print('crear')
        c, _ = pedir(base, 'api/subidas', 'POST', b'no es una imagen', tipo='image/png')
        chequear(c == 400, 'subida que no es imagen: 400')
        ref = os.path.join(RAIZ, 'ejemplos', 'objetos', 'caja', 'trabajo', 'malla', 'sin_fondo.png')
        c, d = pedir(base, 'api/subidas', 'POST', open(ref, 'rb').read(), tipo='image/png')
        chequear(c == 200 and 'id' in d, 'subir una imagen')
        c, d = pedir(base, 'api/assets', 'POST', {'nombre': 'prueba_ui', 'receta': 'objeto', 'subida': d.get('id'),
                                                  'estilo': 'moderno'})
        pdir = os.path.join(cfg['datos_dir'], 'objetos', 'prueba_ui')
        chequear(c == 200 and os.path.exists(os.path.join(pdir, 'referencia.png')), 'crear con referencia', str(d))
        chequear(json.load(open(os.path.join(pdir, 'objeto.json'))).get('estilo') == 'moderno', 'crear con estilo')
        c, _ = pedir(base, 'api/assets', 'POST', {'nombre': 'prueba_ui', 'receta': 'objeto', 'descripcion': 'a box'})
        chequear(c == 400, 'nombre repetido: 400')
        c, _ = pedir(base, 'api/assets', 'POST', {'nombre': 'Con Espacios', 'receta': 'objeto', 'descripcion': 'x'})
        chequear(c == 400, 'nombre inválido: 400')

        probar_movimientos(base, cfg['datos_dir'])

        print('cola')
        c, tr = pedir(base, 'api/cola', 'POST', {'paso': 'godot', 'nombre': 'caja'})   # sale enseguida: falta sprites
        chequear(c == 200 and tr['estado'] == 'pendiente', 'encolar godot caja')
        for _ in range(100):
            _, d = pedir(base, 'api/cola')
            t = next(x for x in d['trabajos'] if x['id'] == tr['id'])
            if t['estado'] not in ('pendiente', 'corriendo'):
                break
            time.sleep(0.2)
        chequear(t['estado'] == 'fallo' and t['codigo'] == 5 and 'sprites' in (t['resultado'] or {}).get('error', ''),
                 'godot sin sprites termina con código 5 y el error', json.dumps(t)[:300])
        c, b = pedir(base, f'api/trabajos/{tr["id"]}/log')
        chequear(c == 200 and 'sprites' in b, 'log del trabajo')
        with urllib.request.urlopen(base + 'api/eventos', timeout=10) as r:
            primera = r.readline().decode()
        chequear(primera.startswith('event: cola'), 'SSE: evento de la cola')
        probar_cancelar(tmp)
    finally:
        if srv:
            srv.terminate()
            srv.wait(10)
        if DEJAR:
            print(f'datos en {tmp}')
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    print('\nOK' if not fallas else f'\n{len(fallas)} falla(s): ' + '; '.join(fallas))
    sys.exit(1 if fallas else 0)


if __name__ == '__main__':
    main()
