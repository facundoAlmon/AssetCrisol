#!/usr/bin/env python3
"""Test de la UI web (`crisol ui`) sin GPU: levanta el servidor sobre una copia de los ejemplos en una carpeta temporal
y prueba la página, la API, la seguridad (Host, Origin, rutas fuera del asset), elegir/ajustar, crear un asset con
una imagen subida, la cola (un paso que sale enseguida, el SSE y cancelar uno que corre) y el token de --host 0.0.0.0.
No corre Blender ni nada que use la GPU (~10 s).

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


def pedir(base, ruta, metodo='GET', cuerpo=None, tipo='application/json', host=None, origen=True, crudo=False,
          cookie=None, cabeceras=None):
    """(código, cuerpo: dict/str/bytes); con cabeceras (un dict), ahí quedan las de la respuesta."""
    datos = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo).encode() if cuerpo is not None else None
    r = urllib.request.Request(base + ruta, data=datos, method=metodo)
    if cookie:
        r.add_header('Cookie', cookie)
    if datos is not None:
        r.add_header('Content-Type', tipo)
    if origen and metodo != 'GET':
        r.add_header('Origin', base.rstrip('/'))
    if host:
        r.add_header('Host', host)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            codigo, b, h = resp.status, resp.read(), resp.headers
    except urllib.error.HTTPError as e:
        codigo, b, h = e.code, e.read(), e.headers
    if cabeceras is not None:
        cabeceras.update(h.items())
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


def ip_de_la_red():
    """Una IP de esta PC que no sea loopback (para hablarle a la UI como si fuera otra PC), o None."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sk:
            sk.connect(('10.255.255.255', 1))
            ip = sk.getsockname()[0]
        return None if ip.startswith('127.') else ip
    except OSError:
        return None


def probar_token(env):
    """`crisol ui --host 0.0.0.0`: desde otra PC (la IP de la red de esta) pide el token; desde 127.0.0.1, no."""
    print('token (--host 0.0.0.0)')
    ip = ip_de_la_red()
    if not ip:
        print('  - sin IP de red en esta PC: no se prueba el token')
        return
    puerto = puerto_libre()
    srv = subprocess.Popen([sys.executable, os.path.join(RAIZ, 'crisol'), 'ui', '--puerto', str(puerto), '--no-abrir',
                            '--host', '0.0.0.0'], env=dict(env, CRISOL_UI_TOKEN='prueba-123'),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        local, red = f'http://127.0.0.1:{puerto}/', f'http://{ip}:{puerto}/'
        for _ in range(100):
            try:
                urllib.request.urlopen(local, timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        lineas = [srv.stdout.readline() for _ in range(2)]
        chequear(any(f'{red}?token=prueba-123' in x for x in lineas), 'imprime la URL con el token', ''.join(lineas))
        chequear(pedir(local, 'api/assets')[0] == 200, 'desde esta PC, sin token')
        c, b = pedir(red, '', crudo=True)
        chequear(c == 401 and b'name="token"' in b, 'sin token: 401 con la página que lo pide', str(c))
        c, _ = pedir(red, 'api/assets')
        chequear(c == 401, 'API sin token: 401')
        for r in ('app.mjs', 'i18n/es.mjs', 'mini/caja/x.png', 'archivos/caja/objeto.json', 'api/eventos'):
            c, _ = pedir(red, r, crudo=True)
            chequear(c == 401, f'{r} sin token: 401', str(c))
        c, _ = pedir(red, 'api/cola', 'POST', {'paso': 'godot', 'nombre': 'caja'})
        chequear(c == 401, 'POST sin token: 401')
        c, b = pedir(red, '?token=malo', crudo=True)
        chequear(c == 401 and b'incorrecto' in b, 'token malo: 401', str(c))
        c, _ = pedir(red, 'api/assets', cookie=f'crisol_ui_{puerto}=malo')
        chequear(c == 401, 'cookie mala: 401')
        h = {}
        c, b = pedir(red, '?token=prueba-123&x=1', crudo=True, cabeceras=h)
        galleta = h.get('Set-Cookie', '')
        chequear(c == 200 and galleta.startswith(f'crisol_ui_{puerto}=prueba-123;') and 'HttpOnly' in galleta
                 and 'SameSite=Strict' in galleta, 'token bueno: cookie HttpOnly y SameSite=Strict', galleta)
        chequear(b'url=/?x=1"' in b and b'prueba-123' not in b, 'vuelve a la página sin el token en la URL', b[:300])
        cookie = galleta.split(';')[0]
        chequear(pedir(red, 'api/assets', cookie=cookie)[0] == 200, 'con la cookie: la API')
        chequear(pedir(red, '', crudo=True, cookie=cookie)[0] == 200, 'con la cookie: la página')
        chequear(pedir(red, 'api/cola', 'POST', {'paso': 'rm', 'nombre': 'caja'}, cookie=cookie)[0] == 400,
                 'con la cookie: POST con Origin llega a la API')
        chequear(pedir(red, 'api/cola', 'POST', {'paso': 'rm'}, cookie=cookie, origen=False)[0] == 403,
                 'con la cookie: POST sin Origin sigue en 403')
        chequear(pedir(red, 'api/assets', host='evil.example:80', cookie=cookie)[0] == 403,
                 'con la cookie: Host ajeno sigue en 403')
    finally:
        srv.terminate()
        srv.wait(10)


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
    # estimado por unidad: 3 seeds de qwen a 40 s cada una no dicen nada de zimage ni de 1 seed
    c3.duraciones = {'imagen|objeto': [120], 'imagen|objeto|qwen': [40, 44, 36]}
    chequear(c3.estimado('imagen', 'objeto', 'qwen', 1) == 40 and c3.estimado('imagen', 'objeto', 'qwen', 3) == 120
             and c3.estimado('imagen', 'objeto', 'zimage', 2) == 120 and c3.estimado('malla', 'objeto', 'trellis2', 0) == 5,
             'cola: estimado por unidad y variante')
    terminados = [x['id'] for x in c3.trabajos if x['estado'] not in ('pendiente', 'corriendo')]
    borrados = c3.borrar_historial(terminados[:1])
    chequear(borrados == terminados[:1] and not c3.buscar(borrados[0]) and not os.path.exists(c3.ruta(borrados[0], 'log'))
             and len(c3.borrar_historial()) == len(terminados) - 1, 'cola: borrar historial (uno y el resto, con sus logs)')


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
    c, e = pedir(base, 'api/movimientos/esqueleto?candidato=correr_s3_1')
    chequear(c == 200 and e.get('cuadros') == 90 and len(e.get('cuadros_xy', [])) == 90 and len(e.get('huesos', [])) == 21
             and len(e['cuadros_xy'][0]) == 2 * (1 + max(max(h[0], h[1]) for h in e['huesos'])), 'esqueleto animable de un candidato',
             {k: v for k, v in e.items() if k != 'cuadros_xy'} if c == 200 else e)
    chequear(d.get('animaciones', [])[:3] == ['caminar', 'respirar', 'correr'] and d.get('godot', {}).get('caminar') == 'walk',
             'animaciones en el orden de la hoja, con su nombre en Godot', d.get('animaciones'))
    c, e = pedir(base, 'api/movimientos/esqueleto?procedural=golpe')
    chequear(c == 200 and e.get('cuadros') == 7 and e.get('fps') == 14 and len(e['cuadros_xy'][0]) == 4 * len(e['huesos'])
             and 'golpe' in d.get('procedurales', []), 'esqueleto de una procedural (cuadros y fps de la hoja)',
             {k: v for k, v in e.items() if k != 'cuadros_xy'} if c == 200 else e)
    c, _ = pedir(base, 'api/movimientos/esqueleto?procedural=nada')
    chequear(c == 404, 'procedural que no está: 404')
    c, e = pedir(base, 'api/movimientos/esqueleto?animacion=caminar')
    chequear(c == 200 and e.get('cuadros', 0) > 0, 'esqueleto del clip de la biblioteca')
    c, _ = pedir(base, 'api/movimientos/esqueleto?candidato=../../x')
    chequear(c == 400, 'esqueleto con un nombre inválido: 400')
    chequear(all(isinstance(x.get('usan'), list) for x in d.get('biblioteca', [])), 'la biblioteca dice qué personajes usan cada clip')
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
    shutil.copy(os.path.join(repo, 'correr.npz'), os.path.join(cand, 'correr_s3_2.npz'))
    c, d = pedir(base, 'api/movimientos/borrar', 'POST', {'candidato': 'correr_s3_0'})
    chequear(c == 200 and {x['id'] for x in d['candidatos']} == {'correr_s3_1', 'correr_s3_2'} and
             os.path.isfile(os.path.join(cand, 'correr_s3.png')), 'borrar una muestra: la hoja queda')
    for malo in ('../x_s1_0', 'correr_s9', 'correr'):
        c, _ = pedir(base, 'api/movimientos/borrar', 'POST', {'candidato': malo})
        chequear(c == 400, f'borrar candidato rechazado: {malo}')
    c, d = pedir(base, 'api/movimientos/borrar', 'POST', {'candidato': 'correr_s3'})
    chequear(c == 200 and d['candidatos'] == [] and not os.listdir(cand), 'borrar la generación entera, con la hoja',
             os.listdir(cand))


def probar_articulaciones(base, datos):
    """El editor sobre una guía armada a mano (sin Blender): leer, guardar (previas, guia.png, marca) y rechazos."""
    from PIL import Image
    pdir = os.path.join(datos, 'personajes', 'cris')
    gdir = os.path.join(pdir, 'trabajo', 'guia')
    c, _ = pedir(base, 'api/assets/cris/articulaciones')
    chequear(c == 400, 'sin renders de la guía: 400')
    os.makedirs(gdir, exist_ok=True)
    with open(os.path.join(pdir, 'personaje.json')) as f:
        J = json.load(f)['modelo']['articulaciones']
    with open(os.path.join(gdir, 'guia.json'), 'w') as f:
        json.dump({'ortho': 2.0, 'centro_z': 0.9, 'px': 200, 'articulaciones': J, 'origen': 'personaje.json'}, f)
    for v in ('frente', 'costado'):
        Image.new('RGB', (200, 200), 'white').save(os.path.join(gdir, f'{v}.png'))
    c, g = pedir(base, 'api/assets/cris/articulaciones')
    chequear(c == 200 and g['px'] == 200 and g['articulaciones'] == J and g['origen'] == 'personaje.json',
             'leer las articulaciones de la guía', f'{c} {g}')
    nuevas = json.loads(json.dumps(J))
    rodilla = [nuevas['thigh.S'][1][0] + 0.01, nuevas['thigh.S'][1][1], nuevas['thigh.S'][1][2] - 0.02]
    nuevas['thigh.S'][1] = nuevas['shin.S'][0] = rodilla
    c, g = pedir(base, 'api/assets/cris/articulaciones', 'PUT', {'articulaciones': nuevas})
    with open(os.path.join(pdir, 'personaje.json')) as f:
        m = json.load(f)['modelo']
    with open(os.path.join(gdir, 'articulaciones.json')) as f:
        marca = json.load(f)
    chequear(c == 200 and m['articulaciones']['shin.S'][0] == rodilla and m['_articulaciones_previas'] == J
             and g['fuente'] == 'a mano', 'guardar: modelo.articulaciones y las de antes en _articulaciones_previas', f'{c} {g}')
    chequear(os.path.isfile(os.path.join(gdir, 'guia.png')) and marca['fuente'] == 'a mano', 'guia.png redibujada y la marca')
    c, d = pedir(base, 'api/assets/cris')
    art = next((p for p in d.get('pasos', []) if p['paso'] == 'articulaciones'), {})
    chequear(art.get('estado') == 'hecho' and 'a mano' in (art.get('nota') or ''), 'estado: articulaciones a mano', art)
    c, _ = pedir(base, 'api/assets/cris/articulaciones', 'PUT', {'articulaciones': {'cola': [[0, 0, 0], [0, 0, 1]]}})
    chequear(c == 400, 'un hueso que no está: 400')
    c, _ = pedir(base, 'api/assets/cris/articulaciones', 'PUT', {'articulaciones': {'hips': [[0, 0, 'x'], [0, 0, 1]]}})
    chequear(c == 400, 'una coordenada que no es número: 400')
    c, _ = pedir(base, 'api/assets/caja/articulaciones')
    chequear(c == 400, 'un objeto no tiene editor: 400')
    c, r = pedir(base, 'api/assets/cris/deshacer', 'POST', {'paso': 'articulaciones'})
    with open(os.path.join(pdir, 'personaje.json')) as f:
        m = json.load(f)['modelo']
    chequear(c == 200 and m['articulaciones'] == J, 'deshacer articulaciones vuelve a las de antes', f'{c} {r}')
    shutil.rmtree(gdir)


def probar_ocupado(tmp):
    """deshacer.ocupado: un `crisol` con otra config (otro datos_dir) no ocupa un asset del mismo nombre."""
    print('ocupado')
    sys.path.insert(0, os.path.join(RAIZ, 'herramientas', '0_entorno'))
    import deshacer
    falso = os.path.join(tmp, 'falso_ocupado')
    os.makedirs(falso, exist_ok=True)
    with open(os.path.join(falso, 'pipeline.py'), 'w') as f:
        f.write('import time\ntime.sleep(30)\n')
    propia = os.environ.get('ASSETCRISOL_CONFIG') or os.path.join(RAIZ, 'config.json')
    for config, espera in ((os.path.join(tmp, 'otra_config.json'), False), (propia, True)):
        p = subprocess.Popen([sys.executable, os.path.join(falso, 'pipeline.py'), 'blender', 'zz_ocupado'],
                             env=dict(os.environ, ASSETCRISOL_CONFIG=config))
        try:
            time.sleep(0.3)
            pid = deshacer.ocupado('zz_ocupado')
            chequear((pid == p.pid) == espera, f'ocupado con {"la misma" if espera else "otra"} config: {"sí" if espera else "no"}', pid)
        finally:
            p.kill(); p.wait()


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
        chequear(g3d is not None and g3d['paso'] == 'malla', 'grupo 3d en el visor de la caja, con su paso')
        if g3d:
            r = urllib.request.urlopen(base + 'archivos/caja/' + g3d['archivos'][0], timeout=30)
            chequear(r.headers['Content-Type'] == 'model/gltf-binary' and r.read(4) == b'glTF', '.glb con su mimetype')
        malos = [r for r in ('three.module.min.js', 'GLTFLoader.js', 'OrbitControls.js', 'BufferGeometryUtils.js')
                 if pedir(base, 'vendor/three/' + r, crudo=True)[0] != 200]
        chequear(not malos, 'three.js vendorizado', ', '.join(malos))

        print('deshacer y renombrar')
        c, v = pedir(base, 'api/assets/caja/deshacer?paso=sprites')
        rutas = [r for r, _ in v.get('borraria', [])] if c == 200 else []
        chequear('preview.png' in rutas, 'deshacer: lista lo que borraría', rutas)
        c, r = pedir(base, 'api/assets/caja/deshacer', 'POST', {'paso': 'sprites'})
        c2, d = pedir(base, 'api/assets/caja')
        sprites = next((p['estado'] for p in d.get('pasos', []) if p['paso'] == 'sprites'), None)
        chequear(c == 200 and sorted(r['borrados']) == sorted(rutas) and sprites == 'falta', 'deshacer sprites: borrado y falta',
                 f'{c} {r} {sprites}')
        c, r = pedir(base, 'api/assets/caja/renombrar', 'POST', {'nuevo': 'caja_dos'})
        c2, _ = pedir(base, 'api/assets/caja_dos')
        c3, _ = pedir(base, 'api/assets/caja')
        chequear(c == 200 and c2 == 200 and c3 == 400, 'renombrar caja -> caja_dos', f'{c} {r} {c2} {c3}')
        c, r = pedir(base, 'api/assets/caja_dos/renombrar', 'POST', {'nuevo': 'Caja Mal'})
        chequear(c == 400, 'renombrar con un nombre inválido: 400', r)
        c, _ = pedir(base, 'api/assets/caja_dos/renombrar', 'POST', {'nuevo': 'caja'})
        chequear(c == 200, 'renombrar de vuelta a caja')

        print('corregir imagen')
        img_dir = os.path.join(cfg['datos_dir'], 'personajes', 'cris', 'trabajo', 'imagen')
        for malo in ({'desde': '999', 'pedido': 'green eyes'}, {'desde': '104', 'pedido': '  '},
                     {'desde': '../x', 'pedido': 'x'}, {'desde': '104', 'pedido': 'x' * 601}):
            c, _ = pedir(base, 'api/cola', 'POST', {'paso': 'corregir', 'nombre': 'cris', **malo})
            chequear(c == 400, f'corregir rechazado: {json.dumps(malo)[:60]}', str(c))
        shutil.copy(os.path.join(img_dir, 'cand_104.png'), os.path.join(img_dir, 'cand_edit_2.png'))
        shutil.copy(os.path.join(img_dir, 'cand_104.png'), os.path.join(img_dir, 'cand_edit_10.png'))
        with open(os.path.join(img_dir, 'correcciones.json'), 'w') as f:
            json.dump({'edit_2': {'desde': 104, 'pedido': 'green eyes'}, 'edit_10': {'desde': 'edit_2', 'pedido': 'a scarf'}}, f)
        c, d = pedir(base, 'api/assets/cris')
        ops = next((e['opciones'] for e in d.get('elecciones', []) if e['clave'] == 'imagen.elegida'), [])
        chequear([o['valor'] for o in ops] == ['104', 'edit_2', 'edit_10'] and ops[2].get('correccion') ==
                 {'desde': 'edit_2', 'pedido': 'a scarf'} and 'correccion' not in ops[0],
                 'las correcciones son opciones de la imagen, en orden y con su pedido', ops)
        c, r = pedir(base, 'api/assets/cris/elegir', 'POST', {'clave': 'imagen.elegida', 'valor': 'edit_2'})
        c2, d = pedir(base, 'api/assets/cris')
        chequear(c == 200 and r['valor'] == 'edit_2' and d['json']['imagen']['elegida'] == 'edit_2', 'elegir una corrección')
        pedir(base, 'api/assets/cris/elegir', 'POST', {'clave': 'imagen.elegida', 'valor': '104'})
        c, v = pedir(base, 'api/assets/cris/deshacer?paso=corregir')
        rutas = sorted(r for r, _ in v.get('borraria', [])) if c == 200 else []
        chequear(rutas == ['trabajo/imagen/cand_edit_10.png', 'trabajo/imagen/cand_edit_2.png', 'trabajo/imagen/correcciones.json'],
                 'deshacer corregir: solo las correcciones', rutas)
        pedir(base, 'api/assets/cris/deshacer', 'POST', {'paso': 'corregir'})

        print('candidatos de cara de UltraTex')
        jcris = os.path.join(cfg['datos_dir'], 'personajes', 'cris', 'personaje.json')
        mdir = os.path.join(cfg['datos_dir'], 'personajes', 'cris', 'trabajo', 'malla')
        crudo = json.load(open(jcris))
        crudo['malla']['ultratex']['seeds'] = [1, 2]
        json.dump(crudo, open(jcris, 'w'), indent=2)
        from PIL import Image
        for sd in (1, 2):
            with open(os.path.join(mdir, f'ultratex_s{sd}.glb'), 'wb') as f:
                f.write(b'glTF' + bytes([sd]))
            Image.new('RGB', (64, 64), 'white').save(os.path.join(mdir, f'cara_s{sd}.png'))
        c, d = pedir(base, 'api/assets/cris')
        dec = next((x for x in d.get('decidir', []) if x['clave'] == 'malla.ultratex.elegida'), None)
        chequear(dec and [o['valor'] for o in dec['opciones']] == ['1', '2'] and dec['opciones'][1]['imagen'] == 'trabajo/malla/cara_s2.png',
                 'te toca elegir la cara, con la foto de cada seed', dec)
        glb_antes = open(os.path.join(mdir, 'modelo.glb'), 'rb').read()
        c, r = pedir(base, 'api/assets/cris/elegir', 'POST', {'clave': 'malla.ultratex.elegida', 'valor': '2'})
        c2, d = pedir(base, 'api/assets/cris')
        chequear(c == 200 and r['valor'] == 2 and open(os.path.join(mdir, 'modelo.glb'), 'rb').read() == b'glTF\x02' and
                 not any(x['clave'] == 'malla.ultratex.elegida' for x in d.get('decidir', [])),
                 'elegir la cara copia ese repintado a modelo.glb', r)
        c, v = pedir(base, 'api/assets/cris/deshacer?paso=ultratex')
        rutas = sorted(r for r, _ in v.get('borraria', [])) if c == 200 else []
        chequear({'trabajo/malla/ultratex_s1.glb', 'trabajo/malla/cara_s2.png'} <= set(rutas), 'deshacer ultratex borra los candidatos de cara', rutas)
        with open(os.path.join(mdir, 'modelo.glb'), 'wb') as f:
            f.write(glb_antes)
        for sd in (1, 2):
            os.remove(os.path.join(mdir, f'ultratex_s{sd}.glb')); os.remove(os.path.join(mdir, f'cara_s{sd}.png'))
        crudo = json.load(open(jcris)); crudo['malla']['ultratex'].pop('seeds'); crudo['malla']['ultratex'].pop('elegida')
        json.dump(crudo, open(jcris, 'w'), indent=2)

        print('editor del retrato')
        rdir = os.path.join(cfg['datos_dir'], 'personajes', 'cris', 'trabajo', 'retrato')
        os.makedirs(rdir, exist_ok=True)
        from PIL import Image
        Image.new('RGBA', (400, 400)).save(os.path.join(rdir, 'frente.png'))
        with open(os.path.join(rdir, 'retrato.json'), 'w') as f:
            json.dump({'altura': 1.85, 'x': [-0.25, 0.25], 'z': [1.2, 1.825], 'ancho_px': 512, 'alto_px': 640,
                       'frente': {'ortho': 2.5, 'centro_z': 1.0}}, f)
        c, r = pedir(base, 'api/assets/cris/retrato')
        mod = (r.get('fuentes') or {}).get('modelo') or {}
        chequear(c == 200 and r['fuente'] == 'imagen' and r['fuentes']['imagen'] and mod.get('auto') == [0.4, 0.17, 0.6, 0.42],
                 'retrato: fuentes con su caja automática', r)
        for malo in ({'fuente': 'x', 'caja': None}, {'fuente': 'imagen', 'caja': [0, 0, 1]},
                     {'fuente': 'imagen', 'caja': [0.5, 0.5, 0.5, 0.9]}, {'fuente': 'modelo', 'caja': ['a', 0, 1, 1]}):
            c, _ = pedir(base, 'api/assets/cris/retrato', 'PUT', malo)
            chequear(c == 400, f'retrato rechazado: {json.dumps(malo)}', str(c))
        jcris = os.path.join(cfg['datos_dir'], 'personajes', 'cris', 'personaje.json')
        c, r = pedir(base, 'api/assets/cris/retrato', 'PUT', {'fuente': 'imagen', 'caja': [0.3, 0.05, 0.6, 0.425]})
        rt = json.load(open(jcris)).get('retrato', {})
        chequear(c == 200 and rt['fuente'] == 'imagen' and rt['caja'] == {'imagen': [0.3, 0.05, 0.6, 0.425], 'de_imagen': 104}
                 and r['caja']['imagen'] and not r['vieja'], 'guardar la caja de la imagen (y de qué imagen es)', rt)
        pedir(base, 'api/assets/cris/elegir', 'POST', {'clave': 'imagen.elegida', 'valor': 'otra.png'})
        c, d = pedir(base, 'api/assets/cris')
        sp = next((p for p in d['pasos'] if p['paso'] == 'sprites'), {})
        c2, r = pedir(base, 'api/assets/cris/retrato')
        chequear(r.get('vieja') and (sp.get('aviso') or {}).get('id') in ('retrato_caja_vieja', None), 'la caja quedó vieja al cambiar la elegida', sp)
        pedir(base, 'api/assets/cris/elegir', 'POST', {'clave': 'imagen.elegida', 'valor': '104'})
        c, r = pedir(base, 'api/assets/cris/retrato', 'PUT', {'fuente': 'modelo', 'caja': [0.4, 0.05, 0.6, 0.3]})
        c2, r = pedir(base, 'api/assets/cris/retrato', 'PUT', {'fuente': 'imagen', 'caja': None})
        rt = json.load(open(jcris)).get('retrato', {})
        chequear(c == 200 and c2 == 200 and rt['caja'] == {'modelo': [0.4, 0.05, 0.6, 0.3]} and rt['fuente'] == 'imagen',
                 'automático borra solo la caja de esa fuente', rt)
        c, r = pedir(base, 'api/assets/cris/retrato', 'PUT', {'fuente': 'modelo', 'caja': None})
        chequear('caja' not in json.load(open(jcris))['retrato'], 'sin cajas, sin retrato.caja')
        op = json.load(open(jcris)); op['retrato'].pop('fuente'); json.dump(op, open(jcris, 'w'), indent=2)

        probar_ocupado(tmp)

        print('papelera')
        datos = cfg['datos_dir']
        c, t = pedir(base, 'api/assets/martillo/tamano')
        chequear(c == 200 and t.get('bytes', 0) > 0, 'tamaño del asset para confirmar', t)
        c, _ = pedir(base, 'api/assets/martillo', 'DELETE', origen=False)
        chequear(c == 403, 'borrar sin Origin: 403')
        c, r = pedir(base, 'api/assets/martillo', 'DELETE')
        c2, _ = pedir(base, 'api/assets/martillo')
        c3, pap = pedir(base, 'api/papelera')
        chequear(c == 200 and c2 == 400 and not os.path.exists(os.path.join(datos, 'objetos', 'martillo')) and
                 [e['nombre'] for e in pap] == ['martillo'] and pap[0]['id'] == r.get('id') and pap[0]['bytes'] == t['bytes'],
                 'borrar: a la papelera', f'{c} {r} {c2} {pap}')
        c, _ = pedir(base, 'api/papelera/restaurar', 'POST', {'id': '../../personajes/cris'})
        chequear(c == 400, 'restaurar algo que no está en la papelera: 400')
        c, _ = pedir(base, 'api/papelera', 'DELETE', {'ids': ['objetos/../../personajes/cris_20260101-000000']})
        chequear(c == 400 and os.path.isdir(os.path.join(datos, 'personajes', 'cris')), 'vaciar con un id raro: 400')
        c, r = pedir(base, 'api/papelera/restaurar', 'POST', {'id': pap[0]['id']})
        chequear(c == 200 and r.get('nombre') == 'martillo' and os.path.isfile(os.path.join(datos, 'objetos', 'martillo', 'objeto.json')),
                 'restaurar', r)
        pedir(base, 'api/assets/martillo', 'DELETE')
        shutil.copytree(os.path.join(RAIZ, 'ejemplos', 'objetos', 'martillo'), os.path.join(datos, 'objetos', 'martillo'))
        c, pap = pedir(base, 'api/papelera')
        c, r = pedir(base, 'api/papelera/restaurar', 'POST', {'id': pap[0]['id']})
        chequear(c == 400 and 'ya existe' in str(r), 'restaurar sobre un asset con el mismo nombre: no', r)
        c, r = pedir(base, 'api/papelera', 'DELETE', {})
        c2, pap = pedir(base, 'api/papelera')
        chequear(c == 200 and len(r['borrados']) == 1 and pap == [], 'vaciar la papelera', r)

        print('editor de articulaciones')
        probar_articulaciones(base, cfg['datos_dir'])

        print('3D animado')
        t = os.path.join(cfg['datos_dir'], 'personajes', 'cris', 'trabajo')
        shutil.copy(os.path.join(t, 'malla', 'modelo.glb'), os.path.join(t, 'animado.glb'))   # el visor solo lo sirve
        with open(os.path.join(t, 'animado.json'), 'w') as f:
            json.dump({'caminar': {'clip': 'Walk', 'tiempos': [0, 0.1667], 'fin': 0.3333, 'ciclo': True},
                       'golpe': {'clip': 'Punch', 'tiempos': [0, 0.1667], 'fin': 0.1667, 'ciclo': False}}, f)
        c, d = pedir(base, 'api/assets/cris')
        an = d.get('animado') or {}
        chequear(any(g['id'] == 'animado' and g['paso'] == 'blender' for g in d.get('visuales', [])),
                 'grupo 3D animado en el visor, del paso blender')
        chequear(list(an) == ['walk', 'punch'] and an['walk']['fps'] == 12 and an['walk']['loop']
                 and an['punch']['fps'] == 14 and not an['punch']['loop'], 'animaciones con su nombre, fps y loop de las hojas', an)
        c, g = pedir(base, 'api/assets/cris/exportar')
        modelo = next((x['archivos'] for x in g if x['id'] == 'modelo'), []) if c == 200 else []
        chequear('trabajo/animado.glb' in modelo, 'animado.glb en exportar > modelo', modelo)
        c, v = pedir(base, 'api/assets/cris/deshacer?paso=blender')
        rutas = [r for r, _ in v.get('borraria', [])] if c == 200 else []
        chequear({'trabajo/animado.glb', 'trabajo/animado.json'} <= set(rutas), 'deshacer blender borra el 3D animado', rutas)

        print('juego 3D')
        tr = os.path.join(t, 'tiempo_real'); os.makedirs(tr, exist_ok=True)
        for n in ('cris.glb', 'cris_lods.glb'):
            shutil.copy(os.path.join(t, 'malla', 'modelo.glb'), os.path.join(tr, n))
        with open(os.path.join(tr, 'lods.json'), 'w') as f:
            json.dump({'original': {'caras': 80000, 'vertices': 40000}, 'textura_px': 2048, 'mapas': ['normal'],
                       'archivos': {'cris.glb': 'LOD0 solo (Godot)', 'cris_lods.glb': 'todos los LOD'}, 'huesos': 'mixamo',
                       'lods': [{'nombre': f'cris_LOD{i}', 'caras': 20000 >> i, 'vertices': 10000 >> i} for i in range(3)]}, f)
        c, d = pedir(base, 'api/assets/cris')
        j3 = d.get('tiempo_real') or {}
        chequear(any(g['id'] == 'juego3d' and g['paso'] == 'blender' and g['archivos'] == ['trabajo/tiempo_real/cris_lods.glb']
                     for g in d.get('visuales', [])), 'grupo Juego 3D en el visor, del paso blender')
        chequear(len(j3.get('lods', [])) == 3 and j3.get('pesos', {}).get('cris_lods.glb', 0) > 0, 'lods.json y pesos para el visor', j3)
        chequear(d.get('tiempo_real_general') == cfg.get('tiempo_real'), 'tiempo_real de config.json para Ajustes',
                 d.get('tiempo_real_general'))
        c, g = pedir(base, 'api/assets/cris/exportar')
        tre = next((x['archivos'] for x in g if x['id'] == 'tiempo_real'), []) if c == 200 else []
        chequear('trabajo/tiempo_real/cris_lods.glb' in tre and 'trabajo/tiempo_real/lods.json' in tre, 'exportar > juego 3D', tre)
        c, v = pedir(base, 'api/assets/cris/deshacer?paso=blender')
        rutas = [r for r, _ in v.get('borraria', [])] if c == 200 else []
        chequear(any(r.startswith('trabajo/tiempo_real') for r in rutas), 'deshacer blender borra tiempo_real', rutas)
        c, _ = pedir(base, 'api/assets/cris/json', 'PATCH', {'cambios': {'tiempo_real': {}, 'tiempo_real.huesos': 'godot'}})
        c2, d = pedir(base, 'api/assets/cris')
        chequear(c == 200 and d['json'].get('tiempo_real') == {'huesos': 'godot'}, 'Ajustes > Juego 3D: prender y elegir huesos',
                 d['json'].get('tiempo_real'))

        print('exportar')
        c, g = pedir(base, 'api/assets/caja/exportar')
        ids = [x['id'] for x in g] if c == 200 else []
        chequear('modelo' in ids and 'fuente' in ids, 'grupos para exportar de la caja', ids)
        c, b = pedir(base, 'api/assets/caja/zip?grupos=modelo,fuente', crudo=True)
        import io, zipfile
        nombres = zipfile.ZipFile(io.BytesIO(b)).namelist() if c == 200 else []
        esperados = sorted(f'caja/{r}' for x in g if x['id'] in ('modelo', 'fuente') for r in x['archivos'])
        chequear(sorted(nombres) == esperados and 'caja/objeto.json' in nombres, 'zip con los grupos pedidos', nombres)
        c, _ = pedir(base, 'api/assets/caja/zip?grupos=nada')
        chequear(c == 400, 'zip de un grupo que no existe: 400')
        c, _ = pedir(base, 'api/assets/..%2F..%2Fejemplos/exportar')
        chequear(c == 404, 'nombre de asset con ..: 404')

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
        c, d = pedir(base, 'api/assets/caja')
        chequear(c == 200 and d.get('prompt_estilo', {}).get('render_objeto') and d.get('prompt_imagen'),
                 'prompt del estilo y prompt armado en el detalle')
        c, _ = pedir(base, 'api/assets/caja/json', 'PATCH', {'cambios': {'prompt.tema': 'a pirate ship deck', 'prompt.extra': ''}})
        c2, d = pedir(base, 'api/assets/caja')
        chequear(c == 200 and 'A pirate ship deck.' in (d.get('prompt_imagen') or '') and
                 d['prompt_imagen'].endswith('no text.'), 'bloque prompt pisa el tema y saca el extra', d.get('prompt_imagen'))
        c, _ = pedir(base, 'api/assets/caja/json', 'PATCH', {'cambios': {'prompt.tema': None, 'prompt.extra': None}})

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
        # las vistas que deja `comparar` por candidato (trabajo/comparar/<c>/<vista>.png) van a su tarjeta
        ref_png = os.path.join(RAIZ, 'ejemplos', 'objetos', 'caja', 'trabajo', 'malla', 'sin_fondo.png')
        os.makedirs(os.path.join(trabajo_caja, 'comparar', 'pixal3d'), exist_ok=True)
        for v in ('s', 'se'):
            shutil.copy(ref_png, os.path.join(trabajo_caja, 'comparar', 'pixal3d', f'{v}.png'))
        os.makedirs(os.path.join(trabajo_caja, 'comparar', 'trellis2'), exist_ok=True)   # sin malla: no cuenta
        shutil.copy(ref_png, os.path.join(trabajo_caja, 'comparar', 'trellis2', 's.png'))
        c, d = pedir(base, 'api/assets/caja')
        ops = {o['valor']: o for e in d.get('elecciones', []) if e['clave'] == 'malla.elegida' for o in e['opciones']}
        p3 = ops.get('pixal3d', {})
        chequear([v['id'] for v in p3.get('vistas', [])] == ['s', 'se'] and p3.get('imagen') == 'trabajo/comparar/pixal3d/s.png'
                 and p3.get('hecho') and p3.get('glb') == 'trabajo/malla_pixal3d/modelo.glb' and p3.get('motor') == 'pixal3d'
                 and p3.get('seed') == 1, 'tarjeta de un candidato con sus vistas', json.dumps(p3))
        chequear(ops.get('trellis2', {}).get('vistas') == [] and not ops['trellis2']['hecho'] and ops['trellis2']['glb'] is None,
                 'candidato sin generar: tarjeta sin imagen', json.dumps(ops.get('trellis2')))
        chequear(ops.get('ultratex', {}).get('desde') == 'trellis2' and ops['ultratex'].get('ultratex') == 2,
                 'cómo se hace un repintado', json.dumps(ops.get('ultratex')))
        c, b = pedir(base, 'mini/caja/' + p3.get('imagen', 'x') + '?lado=100', crudo=True)
        chequear(c == 200 and b[:4] == b'\x89PNG', 'miniatura de la vista de un candidato')
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
        chequear(c == 200 and d['borrados'] == ['pixal3d'] and not os.path.exists(os.path.join(trabajo_caja, 'malla_pixal3d'))
                 and not os.path.exists(os.path.join(trabajo_caja, 'comparar', 'pixal3d')), 'rehacer un candidato generado (y sus vistas)')

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
        probar_token(env)
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
