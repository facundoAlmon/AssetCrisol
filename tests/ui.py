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
    falso = os.path.join(tmp, 'falso.py')
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
    chequear('[falso] empiezo' in c.log(a['id']), 'cola: log del trabajo')
    c2 = Cola(os.path.join(tmp, 'cola_prueba'))   # el historial sobrevive a un reinicio
    chequear([t['estado'] for t in c2.trabajos] == ['cancelado', 'cancelado'], 'cola: historial en cola.json')


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
