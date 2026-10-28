# UI web local de AssetCrisol (`crisol ui`): un servidor HTTP de la biblioteca estándar en 127.0.0.1 que sirve la
# página (herramientas/ui/web, Preact + htm sin build) y una API JSON sobre la CLI. No tiene lógica propia del
# pipeline: los pasos corren como `crisol <paso> <n> --json` en la cola (cola.py, de a uno), el estado sale de
# estado.py y las elecciones y ajustes de operaciones.py, como en el MCP. Corre con el python3 del sistema (Pillow
# para las miniaturas). Solo acepta pedidos con Host local y, si cambian algo, con Origin de la misma página: corre
# comandos en esta PC.
import argparse, ast, glob, io, json, mimetypes, os, re, subprocess, sys, tempfile, threading, time, uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
import pipeline  # noqa: E402 (DATOS, CARPETAS, recetas, estilos; no importa bpy ni torch)
import estado as est  # noqa: E402 (herramientas/0_entorno, en el path por pipeline)
import operaciones as op  # noqa: E402
from cola import Cola  # noqa: E402

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')
SUBIDAS = os.path.join(tempfile.gettempdir(), 'crisol_ui_subidas')
MAX_SUBIDA = 40 * 1024 * 1024
NOMBRE = re.compile(r'^[a-z0-9][a-z0-9_]{0,47}$')
IMAGENES = ('.png', '.gif', '.jpg', '.jpeg', '.webp')
mimetypes.add_type('text/javascript', '.mjs')
mimetypes.add_type('model/gltf-binary', '.glb')

# pasos que la UI puede encolar para un asset (más rehacer y movimiento, que van aparte)
PASOS_ASSET = set(op.PASOS)


# ---------- lectura de assets ----------

def cargar(nombre):
    """pipeline.cargar sin el sys.exit: (pdir, pj) o ValueError."""
    try:
        return pipeline.cargar(nombre)
    except SystemExit as e:
        raise ValueError(str(e.code)) from None


def nombres():
    for carpeta, archivo in pipeline.CARPETAS:
        d = os.path.join(pipeline.DATOS, carpeta)
        for n in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if os.path.exists(os.path.join(d, n, archivo)):
                yield n


def rel(pdir, ruta):
    return os.path.relpath(ruta, pdir) if ruta else None


def existe(pdir, *partes):
    r = os.path.join(pdir, *partes)
    return os.path.relpath(r, pdir) if os.path.isfile(r) else None


def miniatura_de(pdir, pj, nombre, tipo):
    """La imagen que representa al asset en la biblioteca: el asset solo y de frente (no una hoja ni una tira de
    vistas), si no la elegida, la referencia o una candidata."""
    elegida = rel(pdir, est.imagen_elegida(pdir, pj)) if tipo != 'escenario' else None
    cands = sorted(glob.glob(os.path.join(pdir, 'trabajo', 'imagen', 'cand_*.png')))
    t = 'trabajo'
    if tipo == 'personaje':
        orden = (f'godot/personajes/{nombre}/{nombre}_frente.png', f'{t}/malla/sin_fondo.png')
    elif tipo == 'vehiculo':
        orden = (f'{t}/tarjeta.png', f'{t}/malla/sin_fondo.png', 'preview.png')
    elif tipo == 'objeto':
        orden = (f'{t}/render/iso_0.png', f'{t}/malla/sin_fondo.png', 'preview.png')
    else:
        orden = ('preview.png', f'{t}/texturas/candidatos.png')
    for r in (*orden, elegida, 'referencia.png', rel(pdir, cands[0]) if cands else None):
        if r and os.path.isfile(os.path.join(pdir, r)):
            return r
    return None


def visuales(pdir, pj, nombre, tipo):
    """Grupos de archivos para el visor, solo los que existen: [{'id', 'archivos': [rutas relativas]}]."""
    t = 'trabajo'
    g = []

    def grupo(gid, *rutas):
        hay = [r for r in rutas if r and os.path.isfile(os.path.join(pdir, r))]
        if hay:
            g.append({'id': gid, 'archivos': hay})

    if tipo == 'personaje':
        gd = f'godot/personajes/{nombre}'
        grupo('animacion', 'preview.gif')
        grupo('3d', f'{t}/malla/modelo.glb')
        grupo('iso', 'preview_iso.gif')
        grupo('retrato', f'{gd}/{nombre}_retrato.png', f'{gd}/{nombre}_frente.png')
        grupo('revision', f'{t}/revision.png')
        grupo('hoja', f'{gd}/{nombre}_sheet.png')
        grupo('guia', f'{t}/guia/guia.png')
    elif tipo == 'vehiculo':
        armado = os.path.isfile(os.path.join(pdir, t, 'vehiculo.glb'))   # con las ruedas en su nodo, si ya está
        grupo('3d', f'{t}/vehiculo.glb' if armado else f'{t}/malla/modelo.glb')
        grupo('tarjeta', f'{t}/tarjeta.png')
        grupo('revision', f'{t}/revision.png')
    elif tipo == 'objeto':
        grupo('3d', f'{t}/malla/modelo.glb')
        grupo('objeto', 'preview.png', *sorted(rel(pdir, r) for r in glob.glob(os.path.join(pdir, t, 'render', 'iso_*.png'))),
              f'{t}/render/lateral.png')
        grupo('comparar', f'{t}/candidatos.png')
    else:
        grupo('tema', 'preview.png')
        grupo('repetibles', *(f'{t}/tema/{k}.png' for k in ('piso', 'camino', 'pared', 'fondo')))
    if tipo != 'escenario':
        grupo('malla', f'{t}/malla/sin_fondo.png', f'{t}/malla/ultratex_vistas.png', f'{t}/malla/ultratex_espalda.png',
              f'{t}/malla/ultratex_costados.png')
        grupo('vistas', f'{t}/imagen/vistas.png')
        grupo('imagen', rel(pdir, est.imagen_elegida(pdir, pj)), 'referencia.png')
    return g


def iso_meta(pdir, nombre):
    """El meta de las hojas iso de un personaje (para el reproductor por dirección), con la carpeta relativa."""
    r = os.path.join(pdir, 'godot', 'personajes', nombre, 'iso', f'{nombre}_iso_meta.json')
    if not os.path.exists(r):
        return None
    m = op.leer(r)
    m['carpeta'] = os.path.relpath(os.path.dirname(r), pdir)
    return m


def opciones_decidir(pdir, pj, d):
    """Cada opción de una decisión con su imagen propia (o None si solo está la hoja) y, en las mallas, su .glb para
    el visor 3D (el vehículo armado de ese candidato si ya está, si no la malla)."""
    t = os.path.join(pdir, 'trabajo')
    clave, ops = d['clave'], []
    for o in d['opciones']:
        img = glb = None
        if clave == 'imagen.elegida':
            img = existe(t, 'imagen', f'cand_{o}.png') and f'trabajo/imagen/cand_{o}.png'
        elif clave == 'malla.elegida':
            img = existe(t, f'tarjeta_{o}.png') and f'trabajo/tarjeta_{o}.png'
            glb = (existe(t, f'vehiculo_{o}.glb') and f'trabajo/vehiculo_{o}.glb') or \
                (existe(t, f'malla_{o}', 'modelo.glb') and f'trabajo/malla_{o}/modelo.glb')
        elif clave.startswith('texturas.'):
            k = clave.split('.')[1]
            img = existe(t, 'texturas', k, f'cand_{o}.png') and f'trabajo/texturas/{k}/cand_{o}.png'
        ops.append({'valor': o, 'imagen': img, 'glb': glb})
    return ops


def elecciones(pdir, pj, tipo):
    """Todo lo que la persona puede elegir (ya elegido o no), para cambiar una elección: [{clave, actual, opciones,
    mirar}]."""
    t = os.path.join(pdir, 'trabajo')
    out = []
    if tipo == 'escenario':
        for k, tx in (pj.get('texturas') or {}).items():
            seeds = sorted(os.path.basename(c)[5:-4] for c in glob.glob(os.path.join(t, 'texturas', k, 'cand_*.png')))
            if seeds:
                out.append({'clave': f'texturas.{k}.elegida', 'actual': tx.get('elegida'), 'opciones': seeds,
                            'mirar': 'trabajo/texturas/candidatos.png'})
    else:
        seeds = sorted(os.path.basename(c)[5:-4] for c in glob.glob(os.path.join(t, 'imagen', 'cand_*.png')))
        if seeds:
            out.append({'clave': 'imagen.elegida', 'actual': (pj.get('imagen') or {}).get('elegida'), 'opciones': seeds,
                        'mirar': 'trabajo/imagen/candidatos.png'})
        m = pj.get('malla') or {}
        if m.get('candidatos'):
            nombres = [m.get('motor', 'trellis2')] + list(m['candidatos'])
            out.append({'clave': 'malla.elegida', 'actual': m.get('elegida'), 'opciones': nombres,
                        'mirar': 'trabajo/revision.png' if pj.get('vehiculo') else 'trabajo/candidatos.png'})
    for e in out:
        e['mirar'] = e['mirar'] if os.path.isfile(os.path.join(pdir, e['mirar'])) else None
        e['opciones'] = opciones_decidir(pdir, pj, e)
    return out


def resumen_asset(n):
    try:
        pdir, pj = cargar(n)
        e = est.estado(pdir, pj, n)
    except Exception as ex:  # noqa: BLE001 (un json roto no tiene que tirar la biblioteca)
        return {'nombre': n, 'error': str(ex)}
    return {'nombre': n, 'tipo': e['tipo'], 'estilo': pj.get('estilo') or pipeline.CFG.get('estilo', 'animacion3d'),
            'receta': pj.get('_receta'), 'miniatura': miniatura_de(pdir, pj, n, e['tipo']), 'pasos': e['pasos'],
            'decidir': [x['clave'] for x in e['decidir']], 'siguiente': e['siguiente'],
            'modificado': max((os.path.getmtime(os.path.join(pdir, x)) for x in os.listdir(pdir)), default=0)}


def detalle_asset(n):
    pdir, pj = cargar(n)
    e = est.estado(pdir, pj, n)
    ruta = op.json_del_asset(pipeline.DATOS, pipeline.CARPETAS, n)
    for d in e['decidir']:
        d['mirar'] = rel(pdir, d.get('mirar')) if d.get('mirar') and os.path.exists(d['mirar']) else None
        d['opciones'] = opciones_decidir(pdir, pj, d)
    for p in e['pasos']:
        p['archivo'] = rel(pdir, p.get('archivo'))
    licencias = None
    for r in glob.glob(os.path.join(pdir, 'godot', '*', n, f'{n}_meta.json')) + \
            [os.path.join(pdir, 'trabajo', 'tema', 'licencias.json'), os.path.join(pdir, 'trabajo', 'licencias.json')]:
        if os.path.exists(r):
            m = op.leer(r)
            licencias = m.get('licencias', m)
            break
    logs = sorted(rel(pdir, r) for r in glob.glob(os.path.join(pdir, 'trabajo', '*.log')) +
                  glob.glob(os.path.join(pdir, 'trabajo', 'malla*', '*.log')) +
                  glob.glob(os.path.join(pdir, 'trabajo', 'imagen', '*.log')))
    return {**resumen_asset(n), 'carpeta': pdir, 'json': op.leer(ruta), 'archivo_json': os.path.basename(ruta),
            'pasos': e['pasos'], 'decidir': e['decidir'], 'visuales': visuales(pdir, pj, n, e['tipo']),
            'iso': iso_meta(pdir, n) if e['tipo'] == 'personaje' else None,
            'elecciones': elecciones(pdir, pj, e['tipo']), 'licencias': licencias, 'logs': logs}


# ---------- catálogos ----------

def recetas():
    return [{'id': r, 'base': pipeline.cargar_receta(r)['_base'], 'doc': pipeline.cargar_receta(r).get('_doc', '')}
            for r in pipeline.RECETAS]


def estilos():
    d = os.path.join(RAIZ, 'estilos')
    out = []
    for x in sorted(os.listdir(d)):
        if x.endswith('.json'):
            out.append({'id': x[:-5], 'doc': op.leer(os.path.join(d, x)).get('_doc', '')})
    return {'estilos': out, 'defecto': pipeline.CFG.get('estilo', 'animacion3d')}


def _constante(ruta, nombre):
    """El nodo del valor de una constante de un módulo, sin importarlo (anim.py necesita bpy)."""
    with open(ruta) as f:
        arbol = ast.parse(f.read())
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign) and any(getattr(x, 'id', None) == nombre for x in nodo.targets):
            return nodo.value
    return None


def animaciones():
    nodo = _constante(os.path.join(RAIZ, 'herramientas', '3_blender', 'anim.py'), 'TODAS')   # [(nombre, función)]
    todas = [e.elts[0].value for e in nodo.elts] if nodo else []
    nodo = _constante(os.path.join(RAIZ, 'herramientas', '4_sprites', 'armar_iso.py'), 'NOMBRES')
    nombres_iso = ast.literal_eval(nodo) if nodo else {}
    return [{'id': a, 'godot': nombres_iso.get(a, a)} for a in todas]


class Doctor:
    """`crisol doctor --json` en segundo plano (tarda unos segundos): lo último que dijo y qué pasos deshabilita."""
    def __init__(self, env):
        self.env, self.datos, self.corriendo = env, None, False
        self.refrescar()

    def refrescar(self):
        if self.corriendo:
            return
        self.corriendo = True

        def correr():
            try:
                r = subprocess.run([op.PY, op.PIPELINE, 'doctor', '--json'], capture_output=True, text=True,
                                   timeout=180, env=self.env)
                d = json.loads(r.stdout)
            except Exception as e:  # noqa: BLE001
                d = {'ok': False, 'error': f'no se pudo correr crisol doctor: {e}', 'revisiones': [], 'pasos': []}
            d['deshabilitados'] = self.deshabilitados(d)
            d['hora'] = time.time()
            self.datos, self.corriendo = d, False
        threading.Thread(target=correr, daemon=True).start()

    @staticmethod
    def deshabilitados(d):
        """{paso: lo que falta} de las etiquetas agrupadas del doctor ("guia, blender, ...", "imagen (con
        referencia)"). Un paso con variantes (imagen con y sin referencia) queda deshabilitado solo si fallan todas."""
        bien, mal = set(), {}
        for p in d.get('pasos', []):
            for nombre in re.sub(r'\([^)]*\)', '', p['paso']).split(','):
                nombre = nombre.strip()
                if not nombre:
                    continue
                if p.get('disponible'):
                    bien.add(nombre)
                else:
                    mal.setdefault(nombre, []).append(p.get('necesita') or ', '.join(p.get('falta') or []))
        return {k: v for k, v in mal.items() if k not in bien}


# ---------- servidor ----------

class App:
    def __init__(self, puerto):
        self.puerto = puerto
        self.env = dict(os.environ, CRISOL_PYTHON=op.PY)
        self.cola = Cola(os.path.join(pipeline.DATOS, '.crisol_ui'), env=self.env)
        self.cola.al_terminar = lambda t: self.cambio()
        self.doctor = Doctor(self.env)
        self.version_assets = 0

    def cambio(self):
        self.version_assets += 1


class Manejador(BaseHTTPRequestHandler):
    server_version = 'crisol-ui'
    protocol_version = 'HTTP/1.1'
    app: App = None

    def log_message(self, fmt, *args):   # sin una línea por pedido en la terminal
        if os.environ.get('CRISOL_UI_LOG'):
            super().log_message(fmt, *args)

    # --- respuestas ---
    def enviar(self, codigo, cuerpo=b'', tipo='application/json; charset=utf-8', extra=None):
        self.send_response(codigo)
        self.send_header('Content-Type', tipo)
        self.send_header('Content-Length', str(len(cuerpo)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(cuerpo)

    def json(self, d, codigo=200):
        self.enviar(codigo, json.dumps(d, ensure_ascii=False).encode())

    def error(self, codigo, msg):
        self.json({'error': msg}, codigo)

    def cuerpo(self):
        n = int(self.headers.get('Content-Length') or 0)
        if n > MAX_SUBIDA:
            raise ValueError('demasiado grande')
        return self.rfile.read(n) if n else b''

    def cuerpo_json(self):
        b = self.cuerpo()
        return json.loads(b) if b else {}

    # --- seguridad ---
    def host_local(self):
        host = (self.headers.get('Host') or '').lower()
        return host in {f'127.0.0.1:{self.app.puerto}', f'localhost:{self.app.puerto}', f'[::1]:{self.app.puerto}'}

    def origen_propio(self):
        origen = self.headers.get('Origin')
        return origen in {f'http://127.0.0.1:{self.app.puerto}', f'http://localhost:{self.app.puerto}',
                          f'http://[::1]:{self.app.puerto}'}

    def despachar(self, metodo):
        if not self.host_local():
            return self.error(403, 'solo desde esta PC (Host)')
        if metodo not in ('GET', 'HEAD') and not self.origen_propio():
            return self.error(403, 'solo desde la página de crisol ui (Origin)')
        url = urlsplit(self.path)
        partes = [unquote(p) for p in url.path.split('/') if p]
        q = {k: v[-1] for k, v in parse_qs(url.query).items()}
        try:
            return self.rutear(metodo, partes, q)
        except (ValueError, KeyError) as e:
            return self.error(400, str(e).strip("'"))
        except BrokenPipeError:
            pass
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            return self.error(500, f'{type(e).__name__}: {e}')

    def do_GET(self):
        self.despachar('GET')

    def do_HEAD(self):
        self.despachar('HEAD')

    def do_POST(self):
        self.despachar('POST')

    def do_PATCH(self):
        self.despachar('PATCH')

    def do_PUT(self):
        self.despachar('PUT')

    def do_DELETE(self):
        self.despachar('DELETE')

    # --- rutas ---
    def rutear(self, m, p, q):
        app = self.app
        if not p:
            return self.estatico(['index.html'])
        if p[0] == 'archivos' and len(p) >= 3:
            return self.archivo(p[1], p[2:])
        if p[0] == 'mini' and len(p) >= 3:
            return self.miniatura(p[1], p[2:], q)
        if p[0] == 'movimientos' and len(p) == 2:
            return self.hoja_movimiento(p[1])
        if p[0] != 'api':                     # la página: index.html, app.mjs, componentes/, vendor/...
            return self.estatico(p)
        p = p[1:]
        if p == ['assets'] and m == 'GET':
            return self.json({'version': app.version_assets, 'datos': pipeline.DATOS,
                              'assets': [resumen_asset(n) for n in nombres()]})
        if p == ['assets'] and m == 'POST':
            return self.crear(self.cuerpo_json())
        if len(p) >= 2 and p[0] == 'assets':
            n = p[1]
            if len(p) == 2 and m == 'GET':
                return self.json(detalle_asset(n))
            ruta = op.json_del_asset(pipeline.DATOS, pipeline.CARPETAS, n)
            if p[2:] == ['elegir'] and m == 'POST':
                b = self.cuerpo_json()
                v = op.elegir(ruta, b['clave'], b['valor'])
                app.cambio()
                return self.json({'clave': b['clave'], 'valor': v})
            if p[2:] == ['json'] and m == 'PATCH':
                op.ajustar(ruta, self.cuerpo_json()['cambios'])
                app.cambio()
                return self.json({'ok': True})
            if p[2:] == ['json'] and m == 'PUT':
                return self.reemplazar_json(ruta, self.cuerpo_json())
            if p[2:] == ['metodos']:
                return self.metodos(n, self.cuerpo_json().get('cambios') if m == 'POST' else None)
            if p[2:] == ['log'] and m == 'GET':
                return self.archivo(n, q['ruta'].split('/'), texto=True)
        if p == ['cola'] and m == 'GET':
            return self.json(app.cola.foto())
        if p == ['cola'] and m == 'POST':
            return self.encolar(self.cuerpo_json())
        if len(p) == 2 and p[0] == 'cola' and m == 'DELETE':
            return self.json(app.cola.quitar(p[1]))
        if len(p) == 3 and p[0] == 'trabajos' and p[2] == 'log':
            if not app.cola.buscar(p[1]):
                return self.error(404, f'no hay trabajo {p[1]}')
            return self.enviar(200, app.cola.log(p[1]).encode(), 'text/plain; charset=utf-8')
        if p == ['eventos']:
            return self.eventos()
        if p == ['subidas'] and m == 'POST':
            return self.subir()
        if p == ['movimientos']:
            d = os.path.join(pipeline.DATOS, 'movimientos', 'candidatos')
            hojas = sorted(glob.glob(os.path.join(d, '*.png')), key=os.path.getmtime, reverse=True)
            return self.json([{'archivo': os.path.basename(h), 'modificado': os.path.getmtime(h),
                               'clips': len(glob.glob(h[:-4] + '_*.npz'))} for h in hojas])
        if p == ['recetas']:
            return self.json(recetas())
        if p == ['estilos']:
            return self.json(estilos())
        if p == ['animaciones']:
            return self.json(animaciones())
        if p == ['doctor'] and m == 'GET':
            return self.json(app.doctor.datos or {'cargando': True})
        if p == ['doctor'] and m == 'POST':
            app.doctor.refrescar()
            return self.json({'cargando': True})
        return self.error(404, 'no existe')

    def estatico(self, partes):
        ruta = os.path.realpath(os.path.join(WEB, *partes))
        if not ruta.startswith(os.path.realpath(WEB) + os.sep) or not os.path.isfile(ruta):
            return self.error(404, 'no existe')
        with open(ruta, 'rb') as f:
            datos = f.read()
        tipo = mimetypes.guess_type(ruta)[0] or 'application/octet-stream'
        if tipo.startswith('text/') or tipo.endswith(('javascript', 'json', 'svg+xml')):
            tipo += '; charset=utf-8'
        self.enviar(200, datos, tipo, {'Cache-Control': 'no-cache'})

    def ruta_de_asset(self, nombre, partes):
        pdir = os.path.dirname(op.json_del_asset(pipeline.DATOS, pipeline.CARPETAS, nombre))
        ruta = os.path.realpath(os.path.join(pdir, *partes))
        if not ruta.startswith(os.path.realpath(pdir) + os.sep):
            raise PermissionError
        return ruta

    def archivo(self, nombre, partes, texto=False):
        try:
            ruta = self.ruta_de_asset(nombre, partes)
        except PermissionError:
            return self.error(403, 'solo archivos dentro de la carpeta del asset')
        if not os.path.isfile(ruta):
            return self.error(404, 'no existe')
        if texto and not ruta.endswith(('.log', '.txt', '.json')):
            return self.error(400, 'solo logs y textos')
        etag = f'"{os.path.getmtime(ruta):.0f}-{os.path.getsize(ruta)}"'
        if self.headers.get('If-None-Match') == etag:
            return self.enviar(304, extra={'ETag': etag})
        with open(ruta, 'rb') as f:
            datos = f.read()
        tipo = 'text/plain; charset=utf-8' if texto else mimetypes.guess_type(ruta)[0] or 'application/octet-stream'
        self.enviar(200, datos, tipo, {'ETag': etag, 'Cache-Control': 'no-cache'})

    def hoja_movimiento(self, archivo):
        """Una hoja de esqueletos de `crisol movimiento` (movimientos/candidatos/<anim>_s<seed>.png)."""
        ruta = os.path.join(pipeline.DATOS, 'movimientos', 'candidatos', archivo)
        if not re.fullmatch(r'[a-z0-9_]+\.png', archivo) or not os.path.isfile(ruta):
            return self.error(404, 'no existe')
        with open(ruta, 'rb') as f:
            self.enviar(200, f.read(), 'image/png', {'Cache-Control': 'no-cache'})

    _minis = {}

    def miniatura(self, nombre, partes, q):
        try:
            ruta = self.ruta_de_asset(nombre, partes)
        except PermissionError:
            return self.error(403, 'solo archivos dentro de la carpeta del asset')
        if not os.path.isfile(ruta) or not ruta.lower().endswith(IMAGENES):
            return self.error(404, 'no existe')
        lado = max(32, min(int(q.get('lado', 320)), 1600))
        fila, filas = q.get('fila'), q.get('filas')
        clave = (ruta, os.path.getmtime(ruta), lado, fila, filas)
        datos = self._minis.get(clave)
        if datos is None:
            from PIL import Image
            im = Image.open(ruta)
            im.seek(0)
            im = im.convert('RGBA')
            if fila is not None and filas:    # una fila de una hoja (los candidatos de malla, uno por fila)
                h = im.height / int(filas)
                im = im.crop((0, round(int(fila) * h), im.width, round((int(fila) + 1) * h)))
            im.thumbnail((lado, lado))
            b = io.BytesIO()
            im.save(b, 'PNG')
            datos = b.getvalue()
            if len(self._minis) > 400:
                self._minis.clear()
            self._minis[clave] = datos
        self.enviar(200, datos, 'image/png', {'Cache-Control': 'no-cache', 'ETag': f'"{hash(clave)}"'})

    def eventos(self):
        """SSE: la cola (cuando cambia), las últimas líneas del log del trabajo en curso y la versión de los assets."""
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.end_headers()
        app, ultimo, ultimo_log, ultima_av, latido = self.app, None, None, None, 0
        try:
            while True:
                if app.cola.version != ultimo:
                    ultimo = app.cola.version
                    self.wfile.write(f'event: cola\ndata: {json.dumps(app.cola.foto(), ensure_ascii=False)}\n\n'.encode())
                t = app.cola.corriendo()
                if t:
                    log = app.cola.log(t['id'], 40)
                    if log != ultimo_log:
                        ultimo_log = log
                        d = {'id': t['id'], 'log': log, 'ahora': time.time()}
                        self.wfile.write(f'event: log\ndata: {json.dumps(d, ensure_ascii=False)}\n\n'.encode())
                if app.version_assets != ultima_av:
                    ultima_av = app.version_assets
                    self.wfile.write(f'event: assets\ndata: {ultima_av}\n\n'.encode())
                latido += 1
                if latido % 15 == 0:
                    self.wfile.write(b': latido\n\n')
                self.wfile.flush()
                time.sleep(1)
        except (BrokenPipeError, ConnectionResetError):
            pass
        self.close_connection = True

    def subir(self):
        datos = self.cuerpo()
        if not datos:
            raise ValueError('falta la imagen')
        from PIL import Image
        try:
            im = Image.open(io.BytesIO(datos))
            im.verify()
            formato = im.format
        except Exception:  # noqa: BLE001
            raise ValueError('no es una imagen que se pueda abrir (png, jpg, webp)') from None
        os.makedirs(SUBIDAS, exist_ok=True)
        sid = uuid.uuid4().hex
        with open(os.path.join(SUBIDAS, f'{sid}.{(formato or "png").lower()}'), 'wb') as f:
            f.write(datos)
        return self.json({'id': sid})

    def crear(self, b):
        n, receta = b.get('nombre', ''), b.get('receta', 'humanoide')
        if not NOMBRE.match(n):
            raise ValueError('nombre: minúsculas, números y _ (sin espacios), hasta 48')
        if receta not in pipeline.RECETAS:
            raise ValueError(f'receta: {", ".join(pipeline.RECETAS)}')
        args = ['nuevo', n, '--receta', receta]
        if b.get('descripcion'):
            args += ['--descripcion', b['descripcion']]
        if b.get('subida'):
            sub = [x for x in glob.glob(os.path.join(SUBIDAS, f'{b["subida"]}.*')) if re.fullmatch(r'[0-9a-f]{32}', b['subida'])]
            if not sub:
                raise ValueError('la imagen subida ya no está: volver a subirla')
            args += ['--referencia', sub[0]]
        d, err = op.crisol(*args, env=self.app.env)
        if not d or not d.get('ok'):
            return self.error(400, (d or {}).get('error') or err)
        if b.get('estilo'):
            op.ajustar(op.json_del_asset(pipeline.DATOS, pipeline.CARPETAS, n), {'estilo': b['estilo']})
        self.app.cambio()
        return self.json({'nombre': n, 'siguiente': (d.get('estado') or {}).get('siguiente')})

    def reemplazar_json(self, ruta, b):
        nuevo = b.get('json')
        if not isinstance(nuevo, dict):
            raise ValueError('el json tiene que ser un objeto')
        viejo = op.leer(ruta)

        def elecciones(cfg):
            r = {k: (cfg.get(k) or {}).get('elegida') for k in ('imagen', 'malla')}
            r.update({f't.{k}': (v or {}).get('elegida') for k, v in (cfg.get('texturas') or {}).items()})
            return r
        if elecciones(viejo) != elecciones(nuevo):
            raise ValueError('las elecciones (imagen, malla, texturas) se cambian desde Decidir, no en el json')
        op.guardar(ruta, nuevo)
        self.app.cambio()
        return self.json({'ok': True})

    def metodos(self, n, cambios):
        """`crisol metodo <n> [anim=metodo ...]`: [{animacion, metodo, notas}] (las notas dicen el recomendado)."""
        args = ['metodo', n]
        for anim, metodo in (cambios or {}).items():
            if not re.fullmatch(r'[a-z_]+', anim) or metodo not in ('procedural', 'kimodo'):
                raise ValueError(f'{anim}={metodo}: animación y procedural|kimodo')
            args.append(f'{anim}={metodo}')
        d, err = op.crisol(*args, env=self.app.env)
        if not d or not d.get('ok'):
            return self.error(400, (d or {}).get('error') or err)
        out = []
        for linea in d.get('mensajes') or []:
            partes = linea.split(None, 2)
            if len(partes) >= 2:
                out.append({'animacion': partes[0], 'metodo': partes[1], 'nota': partes[2] if len(partes) > 2 else ''})
        if cambios:
            self.app.cambio()
        return self.json(out)

    def encolar(self, b):
        paso, n = b.get('paso'), b.get('nombre')
        tipo = None
        if paso == 'rehacer':
            lista = b.get('nombres') or []
            if not lista or not all(NOMBRE.match(x) for x in lista):
                raise ValueError('rehacer: lista de nombres')
            args, n = ['rehacer', ','.join(lista)], ','.join(lista)
        elif paso == 'movimiento':
            anim = b.get('animacion', '')
            if not re.fullmatch(r'[a-z_]+', anim) or not b.get('prompt'):
                raise ValueError('movimiento: animacion y prompt')
            args = ['movimiento', anim, '--prompt', str(b['prompt']), '--duracion', str(float(b.get('duracion', 4))),
                    '--seed', str(int(b.get('seed', 1))), '--muestras', str(int(b.get('muestras', 3)))]
            n = anim
        elif paso in PASOS_ASSET:
            pdir, pj = cargar(n)
            tipo = est.estado(pdir, pj, n)['tipo']
            args = [paso, n]
            if paso == 'texturas' and b.get('solo'):
                if not re.fullmatch(r'[a-z_,]+', b['solo']):
                    raise ValueError('solo: claves separadas por coma')
                args += ['--solo', b['solo']]
        else:
            raise ValueError(f'paso desconocido: {paso}')
        if any(t['estado'] in ('pendiente', 'corriendo') and t['args'] == args for t in self.app.cola.trabajos):
            raise ValueError('ese paso ya está en la cola')
        return self.json(self.app.cola.agregar(args, n, tipo))


def main():
    ap = argparse.ArgumentParser(prog='crisol ui', description='UI web local de AssetCrisol')
    ap.add_argument('--puerto', type=int, default=8190)
    ap.add_argument('--no-abrir', action='store_true', help='no abrir el navegador')
    a = ap.parse_args()
    Manejador.app = App(a.puerto)
    srv = ThreadingHTTPServer(('127.0.0.1', a.puerto), Manejador)
    srv.daemon_threads = True
    url = f'http://127.0.0.1:{a.puerto}/'
    print(f'crisol ui en {url} (datos: {pipeline.DATOS}); Ctrl+C para cerrar', flush=True)
    if not a.no_abrir:
        import webbrowser
        threading.Timer(0.5, webbrowser.open, (url,)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\ncerrado (los pasos en marcha siguen hasta terminar)')


if __name__ == '__main__':
    main()
