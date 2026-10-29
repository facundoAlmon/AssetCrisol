# UI web local de AssetCrisol (`crisol ui`): un servidor HTTP de la biblioteca estándar en 127.0.0.1 que sirve la
# página (herramientas/ui/web, Preact + htm sin build) y una API JSON sobre la CLI. No tiene lógica propia del
# pipeline: los pasos corren como `crisol <paso> <n> --json` en la cola (cola.py, de a uno), el estado sale de
# estado.py y las elecciones y ajustes de operaciones.py, como en el MCP. Corre con el python3 del sistema (Pillow
# para las miniaturas). Solo acepta pedidos con Host local y, si cambian algo, con Origin de la misma página: corre
# comandos en esta PC. Con --host 0.0.0.0 (la red local), además pide un token a todo lo que no venga de esta misma PC.
import argparse, ast, glob, hmac, html, io, ipaddress, json, mimetypes, os, re, secrets, shutil, socket, subprocess, sys, \
    tempfile, threading, time, uuid, zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
import pipeline  # noqa: E402 (DATOS, CARPETAS, recetas, estilos; no importa bpy ni torch)
import estado as est  # noqa: E402 (herramientas/0_entorno, en el path por pipeline)
import operaciones as op  # noqa: E402
import deshacer  # noqa: E402 (herramientas/0_entorno: deshacer un paso y renombrar)
import metodos  # noqa: E402 (herramientas/3_blender: la biblioteca de movimientos y sus candidatos, sin bpy)
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


def textos_acceso(idioma):
    """Las claves `acceso.*` de web/i18n/<idioma>.mjs (lo que falte, de es.mjs), para la página del token, que se arma
    acá: sin token no se sirve ningún archivo de la página."""
    def leer(i):
        d = {}
        with open(os.path.join(WEB, 'i18n', i + '.mjs'), encoding='utf-8') as fh:
            for linea in fh:
                m = re.match(r"\s*'(acceso\.[\w.]+)':\s*('(?:[^'\\]|\\.)*'),?\s*$", linea)
                if m:
                    d[m.group(1)] = ast.literal_eval(m.group(2))
        return d
    return {**leer('es'), **(leer(idioma) if idioma != 'es' else {})}


def pagina_acceso(idioma, incorrecto=False, listo_a=None):
    """La página mínima del token (401) o, con listo_a, la que entra a la UI después de dejar la cookie."""
    t = {k: html.escape(v) for k, v in textos_acceso(idioma).items()}
    if listo_a is not None:
        cabeza = f'<meta http-equiv="refresh" content="0;url={html.escape(listo_a)}">'
        cuerpo = f'<p><a href="{html.escape(listo_a)}">{t["acceso.listo"]}</a></p>'
    else:
        cabeza = ''
        aviso = f'<p class="mal" role="alert">{t["acceso.incorrecto"]}</p>' if incorrecto else ''
        cuerpo = (f'<p>{t["acceso.explicacion"]}</p>{aviso}<form method="get" action="/">'
                  f'<label for="token">{t["acceso.token"]}</label>'
                  '<input id="token" name="token" type="password" autocomplete="current-password" required autofocus>'
                  f'<button>{t["acceso.entrar"]}</button></form>')
    return f'''<!doctype html>
<html lang="{idioma}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AssetCrisol</title>{cabeza}
<style>
:root {{ color-scheme: dark; --fondo: #1a2028; --superficie: #222a34; --linea: #3a4553; --texto: #e7ebf0;
  --texto-2: #a2acb9; --brasa: #ff9e45; --sobre-brasa: #23140a; --error: #ff7a6b; }}
@media (prefers-color-scheme: light) {{ :root {{ color-scheme: light; --fondo: #eef1f5; --superficie: #fff;
  --linea: #c9d0d9; --texto: #18202a; --texto-2: #4b5664; --brasa: #b35200; --sobre-brasa: #fff; --error: #b3261e; }} }}
body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; background: var(--fondo); color: var(--texto);
  font: 16px/1.5 system-ui, sans-serif; padding: 16px; box-sizing: border-box; }}
main {{ max-width: 26rem; width: 100%; background: var(--superficie); border: 1px solid var(--linea);
  border-radius: 12px; padding: 24px; box-sizing: border-box; }}
h1 {{ font-size: 1.3rem; margin: 0 0 8px; }} p {{ color: var(--texto-2); margin: 0 0 16px; }} a {{ color: var(--brasa); }}
.mal {{ color: var(--error); }} form {{ display: grid; gap: 8px; }}
input {{ font: inherit; padding: 10px; border-radius: 8px; border: 1px solid var(--linea); background: var(--fondo);
  color: var(--texto); }}
button {{ font: inherit; font-weight: 600; padding: 10px; border: 0; border-radius: 8px; background: var(--brasa);
  color: var(--sobre-brasa); cursor: pointer; }}
</style></head>
<body><main><h1>{t["acceso.titulo"]}</h1>{cuerpo}</main></body></html>
'''.encode()


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


# ---------- exportar ----------

def grupos_exportar(pdir, pj, nombre, tipo):
    """Lo que se puede bajar en un zip, por grupos (en la UI se marcan): [{'id', 'archivos': [rutas relativas a pdir],
    'tamanos': [bytes de cada uno], 'bytes'}], solo los que tienen algo. Un archivo puede estar en dos grupos (godot y hoja): el zip lo lleva una vez."""
    t = 'trabajo'

    def hay(*patrones):
        out = []
        for pat in patrones:
            for r in sorted(glob.glob(os.path.join(pdir, pat), recursive=True)):
                if os.path.isfile(r) and not r.endswith('.import') and rel(pdir, r) not in out:
                    out.append(rel(pdir, r))
        return out

    elegida = est.imagen_elegida(pdir, pj) if tipo != 'escenario' else None
    if tipo == 'personaje':
        gd = f'godot/personajes/{nombre}'
        g = [('godot', hay('godot/**/*')),
             ('hoja', hay(f'{gd}/{nombre}_sheet.*', f'{gd}/{nombre}_meta.json')),
             ('iso', hay(f'{gd}/iso/*.png', f'{gd}/iso/*.json')),
             ('retrato', hay(f'{gd}/{nombre}_retrato.png', f'{gd}/{nombre}_frente.png')),
             ('anclas', hay(f'{t}/iso/anclas.json')),
             ('modelo', hay(f'{t}/malla/modelo.glb')),
             ('previas', hay('preview.gif', 'preview_iso.gif', f'{t}/revision.png')),
             ('fuente', hay('personaje.json', 'referencia.png', rel(pdir, elegida) if elegida else ''))]
    elif tipo in ('objeto', 'vehiculo'):
        g = [('godot', hay('godot/**/*')),
             ('modelo', hay(f'{t}/vehiculo.glb') or hay(f'{t}/malla/modelo.glb')),
             ('tarjeta', hay(f'{t}/tarjeta.png')),
             ('previas', hay('preview.png', f'{t}/revision.png')),
             ('fuente', hay('objeto.json', 'referencia.png', rel(pdir, elegida) if elegida else ''))]
    else:
        g = [('tema', hay(f'{t}/tema/*')), ('previas', hay('preview.png')), ('fuente', hay('escenario.json'))]
    out = []
    for i, a in g:
        if a:
            tam = [os.path.getsize(os.path.join(pdir, r)) for r in a]
            out.append({'id': i, 'archivos': a, 'tamanos': tam, 'bytes': sum(tam)})
    return out


# los que ya vienen comprimidos van tal cual (comprimirlos de nuevo solo gasta tiempo)
YA_COMPRIMIDOS = ('.png', '.gif', '.glb', '.jpg', '.webp')


# qué paso deja cada grupo del visor (la UI les pone su número de la cadena); en vehículos, `blender` arma el 3D y la
# revisión
PASO_VISUAL = {'animacion': 'sprites', '3d': 'malla', 'iso': 'iso', 'retrato': 'sprites', 'revision': 'revisar',
               'hoja': 'sprites', 'guia': 'guia', 'tarjeta': 'blender', 'objeto': 'sprites', 'comparar': 'malla',
               'tema': 'tema', 'repetibles': 'tema', 'malla': 'malla', 'vistas': 'vistas', 'imagen': 'imagen'}


def visuales(pdir, pj, nombre, tipo):
    """Grupos de archivos para el visor, solo los que existen: [{'id', 'paso', 'archivos': [rutas relativas]}]."""
    t = 'trabajo'
    g = []
    armado = tipo == 'vehiculo' and os.path.isfile(os.path.join(pdir, t, 'vehiculo.glb'))   # ruedas en su nodo

    def grupo(gid, *rutas):
        hay = [r for r in rutas if r and os.path.isfile(os.path.join(pdir, r))]
        if hay:
            paso = 'blender' if armado and gid in ('3d', 'revision') else PASO_VISUAL[gid]
            g.append({'id': gid, 'paso': paso, 'archivos': hay})

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


# ---------- editor de articulaciones ----------

def articulaciones_guia(pdir, pj):
    """Lo que necesita el editor: la cámara de los renders de la guía (trabajo/guia/guia.json, frente.png y
    costado.png) y las articulaciones (las de modelo.articulaciones; si no hay, las estimadas con que se dibujó)."""
    gdir = os.path.join(pdir, 'trabajo', 'guia')
    if not all(os.path.isfile(os.path.join(gdir, a)) for a in ('guia.json', 'frente.png', 'costado.png')):
        raise ValueError('faltan los renders de la guía: correr antes `articulaciones` o `guia`')
    g = op.leer(os.path.join(gdir, 'guia.json'))
    marca = os.path.join(gdir, 'articulaciones.json')
    propias = pj['modelo'].get('articulaciones') or {}
    return {'px': g['px'], 'ortho': g['ortho'], 'centro_z': g['centro_z'],
            'articulaciones': {**g['articulaciones'], **propias},
            'origen': 'personaje.json' if propias else 'estimadas',
            'fuente': op.leer(marca).get('fuente') if os.path.exists(marca) else None,
            'frente': 'trabajo/guia/frente.png', 'costado': 'trabajo/guia/costado.png',
            'version': round(os.path.getmtime(os.path.join(gdir, 'frente.png')))}


def guardar_articulaciones(pdir, pj, ruta, nuevas):
    """Las del editor a modelo.articulaciones (las de antes quedan en _articulaciones_previas: `deshacer
    articulaciones` vuelve a ellas), guia.png redibujada sin Blender y la marca del paso como hechas a mano (blender
    queda viejo)."""
    import dibujar_guia   # herramientas/3_blender, en el path por pipeline (PIL, sin bpy)
    base = articulaciones_guia(pdir, pj)['articulaciones']
    if not isinstance(nuevas, dict) or not nuevas or set(nuevas) - set(base):
        raise ValueError('articulaciones: {hueso: [cabeza, cola]} con los huesos de la guía')
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and abs(v) <= 10  # noqa: E731
    for n, par in nuevas.items():
        if not (isinstance(par, list) and len(par) == 2 and all(isinstance(c, list) and len(c) == 3 and all(map(num, c))
                                                               for c in par)):
            raise ValueError(f'{n}: [[x, y, z], [x, y, z]] en metros')
    nuevas = {n: [[round(v, 4) for v in c] for c in par] for n, par in nuevas.items()}
    crudo = op.leer(ruta)
    m = crudo.setdefault('modelo', {})
    if m.get('articulaciones') and m['articulaciones'] != nuevas:
        m['_articulaciones_previas'] = m['articulaciones']
    m['articulaciones'] = nuevas
    op.guardar(ruta, crudo)
    gdir = os.path.join(pdir, 'trabajo', 'guia')
    g = op.leer(os.path.join(gdir, 'guia.json'))
    g.update(articulaciones={**g['articulaciones'], **nuevas}, origen='personaje.json')
    op.guardar(os.path.join(gdir, 'guia.json'), g)
    dibujar_guia.dibujar(gdir)
    op.guardar(os.path.join(gdir, 'articulaciones.json'), {'fuente': 'a mano', 'motivo': None})


# vistas de cada candidato de malla para su tarjeta: (id, archivo relativo a trabajo/ con {c} = el candidato). Las de
# personajes y objetos las deja `comparar` (pipeline.VISTAS_COMPARAR, misma escala en todos); las de vehículos, `blender`
VISTAS_MALLA = [(v, f'comparar/{{c}}/{v}.png') for v in pipeline.VISTAS_COMPARAR]
VISTAS_VEHICULO = [('tarjeta', 'tarjeta_{c}.png')] + [(v, f'revision_{{c}}_{v}.png') for v in pipeline.VISTAS_VEHICULO]


def datos_candidato(pj, nombre):
    """Cómo se hace un candidato de malla (lo que no pisa lo hereda del principal, como pipeline.candidatos_malla):
    {motor, seed, resolucion, desde, ultratex (su seed, o None)}."""
    m = pj.get('malla') or {}
    base = {k: v for k, v in m.items() if k not in ('candidatos', 'elegida')}
    c = dict(base, **((m.get('candidatos') or {}).get(nombre) or {})) if nombre != m.get('motor', 'trellis2') else base
    ut = c.get('ultratex')
    return {'motor': c.get('motor', 'trellis2'), 'seed': c.get('seed'), 'resolucion': c.get('resolucion'),
            'desde': c.get('desde'), 'ultratex': ((ut.get('seed', 1) if isinstance(ut, dict) else 1) if ut else None)}


def opcion_malla(pdir, pj, o):
    """Un candidato de malla para su tarjeta: si ya está generado, sus vistas (las que existen; `vieja` si son de antes
    que la malla), su .glb para el visor 3D (el vehículo armado si ya está, si no la malla) y cómo se hace."""
    t = os.path.join(pdir, 'trabajo')
    glb = existe(t, f'malla_{o}', 'modelo.glb')
    fecha = os.path.getmtime(os.path.join(t, glb)) if glb else None
    vistas = []
    for v, ruta in VISTAS_VEHICULO if pj.get('vehiculo') else VISTAS_MALLA:
        r = existe(t, ruta.format(c=o))
        if r and glb:
            vistas.append({'id': v, 'imagen': f'trabajo/{r}', 'vieja': os.path.getmtime(os.path.join(t, r)) < fecha,
                           'centro': bool(pj.get('vehiculo')) and v in pipeline.VISTAS_VEHICULO_CENTRO})
    armado = pj.get('vehiculo') and existe(t, f'vehiculo_{o}.glb')
    return {'valor': o, 'imagen': vistas[0]['imagen'] if vistas else None, 'vistas': vistas, 'hecho': bool(glb),
            'glb': f'trabajo/{armado or glb}' if glb else None, **datos_candidato(pj, o)}


def opciones_decidir(pdir, pj, d):
    """Cada opción de una decisión con su imagen propia (o None si solo está la hoja); los candidatos de malla con lo
    de opcion_malla."""
    t = os.path.join(pdir, 'trabajo')
    clave, ops = d['clave'], []
    for o in d['opciones']:
        img = None
        if clave == 'malla.elegida':
            ops.append(opcion_malla(pdir, pj, o))
            continue
        if clave == 'imagen.elegida':
            img = existe(t, 'imagen', f'cand_{o}.png') and f'trabajo/imagen/cand_{o}.png'
        elif clave.startswith('texturas.'):
            k = clave.split('.')[1]
            img = existe(t, 'texturas', k, f'cand_{o}.png') and f'trabajo/texturas/{k}/cand_{o}.png'
        ops.append({'valor': o, 'imagen': img})
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


def mallas_hechas(pdir):
    """{candidato: fecha} de los candidatos de malla ya generados (trabajo/malla_<c>/modelo.glb: `malla` no los
    rehace)."""
    out = {}
    for r in glob.glob(os.path.join(pdir, 'trabajo', 'malla_*', 'modelo.glb')):
        out[os.path.basename(os.path.dirname(r))[len('malla_'):]] = os.path.getmtime(r)
    return out


def nombres_candidatos(pj):
    """El principal (su nombre es el motor) y los de malla.candidatos, como los arma pipeline.candidatos_malla."""
    m = pj.get('malla') or {}
    return [m.get('motor', 'trellis2')] + list(m.get('candidatos') or {})


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
            'elecciones': elecciones(pdir, pj, e['tipo']), 'licencias': licencias, 'logs': logs,
            'mallas_hechas': mallas_hechas(pdir) if e['tipo'] != 'escenario' else {},
            # para el tamaño de los sprites en Ajustes: lo que pone el estilo cuando el json deja null
            'escala': None if e['tipo'] == 'escenario' else {**pj['_estilo']['escala'], 'altura': pj['modelo'].get('altura')}}


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


def carga(paso, pdir, pj, solo=None):
    """Cuánto trabajo trae un paso, para estimar su tiempo (cola.estimado): (variante, unidades). La variante separa
    lo que tarda distinto por unidad (el motor); las unidades son lo que se repite (seeds, candidatos de malla que
    faltan generar, animaciones iso, texturas); (None, None) en los demás."""
    if paso == 'imagen':
        import generar_imagen
        motor = 'qwen' if pj['imagen'].get('referencia') else generar_imagen.motor_texto(pipeline.CFG, pj)
        return motor, len(pj['imagen'].get('seeds') or [])
    if paso == 'malla':
        lista = pipeline.candidatos_malla(pj) or [(None, pj)]
        t = os.path.join(pdir, 'trabajo')
        faltan = [c for n, c in lista if n is None or not os.path.exists(os.path.join(t, f'malla_{n}', 'modelo.glb'))]
        motores = sorted({c['malla'].get('motor', 'trellis2') + ('+ultratex' if c['malla'].get('ultratex') else '')
                          for c in faltan})
        return '/'.join(motores), len(faltan)
    if paso == 'iso':
        return '', len(pj.get('isometrico', {}).get('animaciones') or animaciones())
    if paso == 'texturas':
        tex = pj.get('texturas') or {}
        return '', sum(len(t.get('seeds') or []) for k, t in tex.items() if not solo or k in solo.split(','))
    return None, None   # siempre lo mismo: alcanza con lo que tardó entero


def movimientos():
    """La biblioteca de movimientos (la del repo con la propia de datos_dir encima, metodos.biblioteca) y los
    candidatos de `crisol movimiento`, con su hoja de esqueletos."""
    d = os.path.join(pipeline.DATOS, 'movimientos', 'candidatos')
    bib = metodos.biblioteca()
    return {'animaciones': list(metodos.CUADROS),
            'biblioteca': [{'animacion': a, 'origen': c['_origen'], 'clip': c['clip'],
                            'recomendado': bool(c.get('recomendado')), 'desde': c.get('desde'), 'hasta': c.get('hasta'),
                            'duracion': c.get('duracion'), 'prompt': c.get('prompt'), 'candidato': c.get('candidato'),
                            'nota': c.get('_nota')} for a, c in bib.items()],
            'candidatos': metodos.candidatos(d)}


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

def t_no_existe(e):
    return f'no existe: {e.args[0] if e.args else e}'


def fecha_codigo():
    """La fecha del código Python que tiene cargado este proceso (la UI, la cola, operaciones, estado, pipeline): si
    cambia en el disco, la página avisa que hay que reiniciar `crisol ui` (la web sí se lee de nuevo, y una página
    nueva contra un servidor viejo pide rutas que no existen)."""
    entorno = os.path.join(RAIZ, 'herramientas', '0_entorno')
    rutas = glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), '*.py')) + \
        [os.path.join(entorno, f) for f in ('operaciones.py', 'estado.py')] + [pipeline.__file__, metodos.__file__]
    return max((os.path.getmtime(r) for r in rutas if os.path.exists(r)), default=0)


class App:
    def __init__(self, puerto, red=False, token=None):
        self.puerto, self.red = puerto, red
        self.token = token   # solo en la red (red=True); None = sin token
        self.cookie = f'crisol_ui_{puerto}'   # las cookies no distinguen puertos: una por instancia
        self.env = dict(os.environ, CRISOL_PYTHON=op.PY)
        self.cola = Cola(os.path.join(pipeline.DATOS, '.crisol_ui'), env=self.env)
        self.cola.al_terminar = lambda t: self.cambio()
        self.doctor = Doctor(self.env)
        self.version_assets = 0
        self.codigo = fecha_codigo()

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
        """Host de esta PC (contra DNS rebinding: un dominio ajeno que apunte acá no pasa). Con --host 0.0.0.0 (u
        otra interfaz) también una IP cualquiera o el nombre de la PC, para entrar desde la red local."""
        host = (self.headers.get('Host') or '').lower()
        nombre, _, puerto = host.rpartition(':')
        if puerto != str(self.app.puerto):
            return False
        if nombre in ('127.0.0.1', 'localhost', '[::1]'):
            return True
        if not self.app.red:
            return False
        try:
            ipaddress.ip_address(nombre.strip('[]'))
            return True
        except ValueError:
            pc = socket.gethostname().lower()
            return nombre in (pc, pc + '.local', pc + '.lan')

    def origen_propio(self):
        """Los pedidos que cambian algo, solo desde la misma página (Origin = el Host al que se habló)."""
        return self.headers.get('Origin') == 'http://' + (self.headers.get('Host') or '').lower()

    def desde_esta_pc(self):
        """El pedido llega por loopback (la dirección de la conexión, no el Host, que lo escribe el cliente)."""
        try:
            ip = ipaddress.ip_address(self.client_address[0])
        except ValueError:
            return False
        return ip.is_loopback or bool(getattr(ip, 'ipv4_mapped', None) and ip.ipv4_mapped.is_loopback)

    def token_valido(self, valor):
        return bool(valor) and hmac.compare_digest(valor.encode(), self.app.token.encode())

    def cookie_token(self):
        for parte in (self.headers.get('Cookie') or '').split(';'):
            k, _, v = parte.strip().partition('=')
            if k == self.app.cookie:
                return v
        return ''

    def idioma(self):
        return 'es' if (self.headers.get('Accept-Language') or 'es').lower().startswith('es') else 'en'

    def acceso(self, metodo, url, partes, q):
        """Con token (--host 0.0.0.0, pedido de otra PC): True si pasa; si no, ya respondió. `?token=` bueno deja la
        cookie y vuelve a la misma ruta sin el token (con una página que recarga y no con un 302: así SameSite=Strict
        manda la cookie aunque el enlace se haya abierto desde otro sitio); sin cookie ni token bueno, 401."""
        if not self.app.token or self.desde_esta_pc():
            return True
        sin_cache = {'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'}
        if 'token' in q:
            if metodo in ('GET', 'HEAD') and self.token_valido(q['token']):
                resto = '&'.join(p for p in url.query.split('&') if p and not p.startswith('token='))
                destino = url.path + ('?' + resto if resto else '')
                cookie = f'{self.app.cookie}={self.app.token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=2592000'
                self.enviar(200, pagina_acceso(self.idioma(), listo_a=destino), 'text/html; charset=utf-8',
                            {**sin_cache, 'Set-Cookie': cookie})
                return False
        elif self.token_valido(self.cookie_token()):
            return True
        if partes[:1] in (['api'], ['archivos'], ['mini'], ['movimientos']) or metodo not in ('GET', 'HEAD'):
            self.json({'error': 'falta el token de crisol ui (está en la terminal donde se abrió)'}, 401)
        else:
            self.enviar(401, pagina_acceso(self.idioma(), 'token' in q), 'text/html; charset=utf-8', sin_cache)
        return False

    def despachar(self, metodo):
        if not self.host_local():
            return self.error(403, 'solo desde esta PC (Host)')
        url = urlsplit(self.path)
        partes = [unquote(p) for p in url.path.split('/') if p]
        q = {k: v[-1] for k, v in parse_qs(url.query).items()}
        if not self.acceso(metodo, url, partes, q):
            return
        if metodo not in ('GET', 'HEAD') and not self.origen_propio():
            return self.error(403, 'solo desde la página de crisol ui (Origin)')
        try:
            return self.rutear(metodo, partes, q)
        except ValueError as e:
            return self.error(400, str(e))
        except KeyError as e:   # un id o una clave que no está: solo el nombre no se entiende como error
            return self.error(400, t_no_existe(e))
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
            return self.hoja_movimiento(p[1], q)
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
            if not NOMBRE.match(n):   # arma rutas con él (el zip lee archivos): nada de '..' ni '/'
                return self.error(404, 'no existe')
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
            if len(p) == 5 and p[2] == 'malla' and p[4] == 'rehacer' and m == 'POST':
                return self.rehacer_candidato(n, p[3])
            if p[2:] == ['metodos']:
                return self.metodos(n, self.cuerpo_json().get('cambios') if m == 'POST' else None)
            if p[2:] == ['log'] and m == 'GET':
                return self.archivo(n, q['ruta'].split('/'), texto=True)
            if p[2:] == ['deshacer'] and m == 'GET':   # ?paso=p: qué borraría
                pdir, pj = cargar(n)
                tipo = est.estado(pdir, pj, n)['tipo']
                return self.json({'borraria': deshacer.que_borra(pdir, tipo, n, q.get('paso', '')),
                                  'extra': deshacer.extra(pdir, q.get('paso', ''))})
            if p[2:] == ['deshacer'] and m == 'POST':
                self.libre(n)
                pdir, pj = cargar(n)
                borrados, extra = deshacer.deshacer(pdir, est.estado(pdir, pj, n)['tipo'], n, self.cuerpo_json().get('paso', ''))
                app.cambio()
                return self.json({'borrados': borrados, 'extra': extra})
            if p[2:] == ['renombrar'] and m == 'POST':
                self.libre(n)
                nuevo = self.cuerpo_json().get('nuevo', '')
                deshacer.renombrar(cargar(n)[0], n, nuevo)
                app.cola.renombrar(n, nuevo)
                app.cambio()
                return self.json({'nombre': nuevo})
            if p[2:] == ['articulaciones'] and m == 'GET':
                return self.json(articulaciones_guia(*cargar(n)))
            if p[2:] == ['articulaciones'] and m == 'PUT':
                self.libre(n)
                pdir, pj = cargar(n)
                guardar_articulaciones(pdir, pj, ruta, self.cuerpo_json().get('articulaciones'))
                app.cambio()
                return self.json(articulaciones_guia(*cargar(n)))
            if p[2:] == ['exportar'] and m == 'GET':
                pdir, pj = cargar(n)
                return self.json(grupos_exportar(pdir, pj, n, est.estado(pdir, pj, n)['tipo']))
            if p[2:] == ['zip'] and m == 'GET':   # ?grupos=a,b (los de exportar)
                return self.zip(n, [x for x in q.get('grupos', '').split(',') if x])
        if p == ['cola'] and m == 'GET':
            return self.json(app.cola.foto())
        if p == ['cola'] and m == 'POST':
            return self.encolar(self.cuerpo_json())
        if p == ['cola', 'historial'] and m == 'DELETE':   # {ids: [...]} o sin ids: todo lo terminado
            return self.json({'borrados': app.cola.borrar_historial((self.cuerpo_json() or {}).get('ids'))})
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
        if p == ['movimientos'] and m == 'GET':
            return self.json(movimientos())
        if p == ['movimientos', 'clip'] and m == 'POST':
            return self.clip(self.cuerpo_json())
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

    def libre(self, n):
        """Que no haya un paso de este asset corriendo o esperando (ni en la cola ni de la terminal)."""
        if any(t['estado'] in ('pendiente', 'corriendo') and n in t['nombre'].split(',') for t in self.app.cola.trabajos):
            raise ValueError(f'{n} tiene pasos en la cola: esperar a que terminen o quitarlos')
        pid = deshacer.ocupado(n)
        if pid:
            raise ValueError(f'hay un crisol con {n} corriendo (pid {pid}): esperar a que termine')

    def zip(self, n, ids):
        """<n>.zip con los archivos de esos grupos, adentro de una carpeta <n>/ (armado en un temporal y mandado de a
        pedazos: las hojas iso pueden pesar decenas de MB)."""
        pdir, pj = cargar(n)
        grupos = {g['id']: g['archivos'] for g in grupos_exportar(pdir, pj, n, est.estado(pdir, pj, n)['tipo'])}
        if not ids or any(i not in grupos for i in ids):
            raise ValueError(f'grupos: {", ".join(grupos)}')
        archivos = list(dict.fromkeys(r for i in ids for r in grupos[i]))
        with tempfile.TemporaryFile() as tmp:
            with zipfile.ZipFile(tmp, 'w') as z:
                for r in archivos:
                    z.write(os.path.join(pdir, r), f'{n}/{r}', zipfile.ZIP_STORED if r.lower().endswith(YA_COMPRIMIDOS)
                            else zipfile.ZIP_DEFLATED)
            largo = tmp.tell()
            tmp.seek(0)
            self.send_response(200)
            self.send_header('Content-Type', 'application/zip')
            self.send_header('Content-Length', str(largo))
            self.send_header('Content-Disposition', f'attachment; filename="{n}.zip"')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            shutil.copyfileobj(tmp, self.wfile, 1 << 20)

    def hoja_movimiento(self, archivo, q):
        """Una hoja de esqueletos de `crisol movimiento` (movimientos/candidatos/<anim>_s<seed>.png); con
        ?fila=i, solo la fila de la muestra i (generar_movimiento.py las dibuja de 240 px de alto)."""
        ruta = os.path.join(pipeline.DATOS, 'movimientos', 'candidatos', archivo)
        if not re.fullmatch(r'[a-z0-9_-]+\.png', archivo) or not os.path.isfile(ruta):
            return self.error(404, 'no existe')
        if q.get('fila') is None:
            with open(ruta, 'rb') as f:
                return self.enviar(200, f.read(), 'image/png', {'Cache-Control': 'no-cache'})
        from PIL import Image
        im, fila = Image.open(ruta), int(q['fila'])
        if not 0 <= fila < round(im.height / 240):
            return self.error(404, 'no hay esa fila')
        b = io.BytesIO()
        im.crop((0, fila * 240, im.width, (fila + 1) * 240)).save(b, 'PNG')
        self.enviar(200, b.getvalue(), 'image/png', {'Cache-Control': 'no-cache'})

    _minis = {}

    def miniatura(self, nombre, partes, q):
        try:
            ruta = self.ruta_de_asset(nombre, partes)
        except PermissionError:
            return self.error(403, 'solo archivos dentro de la carpeta del asset')
        if not os.path.isfile(ruta) or not ruta.lower().endswith(IMAGENES):
            return self.error(404, 'no existe')
        lado = max(32, min(int(q.get('lado', 320)), 1600))
        fila, filas, centro = q.get('fila'), q.get('filas'), q.get('centro')
        clave = (ruta, os.path.getmtime(ruta), lado, fila, filas, centro)
        datos = self._minis.get(clave)
        if datos is None:
            from PIL import Image
            im = Image.open(ruta)
            im.seek(0)
            im = im.convert('RGBA')
            if fila is not None and filas:    # una fila de una hoja (los candidatos de malla, uno por fila)
                h = im.height / int(filas)
                im = im.crop((0, round(int(fila) * h), im.width, round((int(fila) + 1) * h)))
            if centro:    # vistas de vehículo con el auto chico en el medio (la imagen ampliada queda entera)
                im = pipeline.recorte_centro(im)
            im.thumbnail((lado, lado))
            b = io.BytesIO()
            im.save(b, 'PNG')
            datos = b.getvalue()
            if len(self._minis) > 400:
                self._minis.clear()
            self._minis[clave] = datos
        self.enviar(200, datos, 'image/png', {'Cache-Control': 'no-cache', 'ETag': f'"{hash(clave)}"'})

    def eventos(self):
        """SSE: la cola (cuando cambia), las últimas líneas del log del trabajo en curso, la versión de los assets y si
        el código cambió en el disco (reiniciar)."""
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
                if latido % 10 == 1 and fecha_codigo() > app.codigo + 1:
                    self.wfile.write(b'event: reiniciar\ndata: 1\n\n')
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

    def rehacer_candidato(self, n, candidato):
        """Borra trabajo/malla_<candidato>/ (y los que se hacen `desde` él) para que el próximo `malla` los genere de
        nuevo: `malla` no rehace un candidato que ya tiene modelo.glb aunque su json haya cambiado."""
        pdir, _ = cargar(n)
        crudo = op.leer(op.json_del_asset(pipeline.DATOS, pipeline.CARPETAS, n))
        if not re.fullmatch(r'[a-z0-9][a-z0-9_]{0,31}', candidato) or candidato not in nombres_candidatos(crudo):
            raise ValueError(f'{candidato}: no es un candidato de malla de {n}')
        if any(t['estado'] in ('pendiente', 'corriendo') and t['args'][:1] in (['malla'], ['todo']) and t['nombre'] == n
               for t in self.app.cola.trabajos):
            raise ValueError(f'{n} tiene un paso de malla en la cola: esperar a que termine')
        cands = (crudo.get('malla') or {}).get('candidatos') or {}
        borrar = [candidato] + [c for c, v in cands.items() if isinstance(v, dict) and v.get('desde') == candidato]
        base = os.path.realpath(os.path.join(pdir, 'trabajo'))
        borrados = []
        for c in borrar:
            d = os.path.realpath(os.path.join(base, f'malla_{c}'))
            if os.path.dirname(d) != base:
                raise ValueError(f'{c}: fuera de la carpeta del asset')
            if os.path.isdir(d):
                shutil.rmtree(d)
                borrados.append(c)
            shutil.rmtree(os.path.join(base, 'comparar', c), ignore_errors=True)   # sus vistas para la tarjeta
        self.app.cambio()
        return self.json({'borrados': borrados})

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

    def clip(self, b):
        """`crisol clip <anim> [--candidato c] [--desde s] [--hasta s] [--recomendado si|no] [--quitar]`: pasar un
        candidato a la biblioteca propia o cambiar/quitar una entrada. Devuelve la biblioteca y los candidatos."""
        anim = b.get('animacion', '')
        if anim not in metodos.CUADROS:
            raise ValueError(f'animacion: una de {", ".join(metodos.CUADROS)}')
        args = ['clip', anim]
        if b.get('candidato'):
            if not metodos.CANDIDATO.match(str(b['candidato'])):
                raise ValueError('candidato: <anim>_s<seed>_<muestra>')
            args += ['--candidato', b['candidato']]
        for k in ('desde', 'hasta'):
            if k in b and b[k] is not None:
                v = '' if b[k] == '' else float(b[k])
                args += [f'--{k}', str(v)]
        if b.get('recomendado') is not None:
            args += ['--recomendado', 'si' if b['recomendado'] else 'no']
        if b.get('quitar'):
            args.append('--quitar')
        if len(args) == 2:
            raise ValueError('nada que cambiar')
        d, err = op.crisol(*args, env=self.app.env)
        if not d or not d.get('ok'):
            return self.error(400, (d or {}).get('error') or err)
        self.app.cambio()
        return self.json(movimientos())

    def encolar(self, b):
        paso, n = b.get('paso'), b.get('nombre')
        tipo = variante = unidades = None
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
            try:
                variante, unidades = carga(paso, pdir, pj, b.get('solo'))
            except Exception:  # noqa: BLE001 (un json a medio editar no impide encolar: se estima sin carga)
                variante, unidades = None, None
        else:
            raise ValueError(f'paso desconocido: {paso}')
        if any(t['estado'] in ('pendiente', 'corriendo') and t['args'] == args for t in self.app.cola.trabajos):
            raise ValueError('ese paso ya está en la cola')
        return self.json(self.app.cola.agregar(args, n, tipo, variante=variante, unidades=unidades))


def main():
    ap = argparse.ArgumentParser(prog='crisol ui', description='UI web local de AssetCrisol')
    ap.add_argument('--puerto', type=int, default=8190)
    ap.add_argument('--host', default='127.0.0.1',
                    help='interfaz donde escuchar (0.0.0.0: toda la red local, con token)')
    ap.add_argument('--token', default=os.environ.get('CRISOL_UI_TOKEN') or None,
                    help='token fijo para entrar desde la red (por defecto CRISOL_UI_TOKEN o uno al azar en cada arranque)')
    ap.add_argument('--no-abrir', action='store_true', help='no abrir el navegador')
    a = ap.parse_args()
    red = a.host not in ('127.0.0.1', 'localhost', '::1')
    token = (a.token or secrets.token_urlsafe(16)) if red else None
    if token and not re.fullmatch(r'[A-Za-z0-9._~-]+', token):
        ap.error('--token/CRISOL_UI_TOKEN: solo letras, números y . _ ~ - (va en la URL y en una cookie)')
    Manejador.app = App(a.puerto, red, token)
    clase = ThreadingHTTPServer
    if ':' in a.host:   # IPv6 ('::' = todas)
        clase = type('ServidorV6', (ThreadingHTTPServer,), {'address_family': socket.AF_INET6})
    srv = clase((a.host, a.puerto), Manejador)
    srv.daemon_threads = True
    url = f'http://127.0.0.1:{a.puerto}/'
    print(f'crisol ui en {url} (datos: {pipeline.DATOS}); Ctrl+C para cerrar', flush=True)
    if red:
        try:   # la IP de esta PC en la red (sin mandar nada: connect de UDP solo elige la interfaz)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sk:
                sk.connect(('10.255.255.255', 1))
                ip = sk.getsockname()[0]
        except OSError:
            ip = socket.gethostname()
        print(f'  en la red: http://{ip}:{a.puerto}/?token={token} (escucha en {a.host})\n'
              '  desde otra PC o el celular se entra con esa URL (o con el token); desde esta PC, sin token.',
              flush=True)
    if not a.no_abrir:
        import webbrowser
        threading.Timer(0.5, webbrowser.open, (url,)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\ncerrado (los pasos en marcha siguen hasta terminar)')


if __name__ == '__main__':
    main()
