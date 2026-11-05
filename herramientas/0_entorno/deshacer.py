# `crisol deshacer <n> --paso <p> [--ver]`: borra lo que generó un paso (para volver a correrlo de cero o liberar
# espacio) y `crisol renombrar <n> --nuevo <m>`. Solo stdlib: lo usan la CLI, el MCP y `crisol ui`.
# Deshacer nunca toca el json del asset ni lo que puso la persona (referencia.png, base_*.png, las elecciones); dos
# pasos se deshacen en serio en vez de solo borrar: `ultratex` vuelve a poner la malla del motor y `articulaciones`
# vuelve a las de antes (modelo._articulaciones_previas, o ninguna: las estimadas).
# También la papelera (`crisol borrar <n>`, `crisol papelera`): borrar un asset lo mueve a
# <datos_dir>/.papelera/<carpeta>/<n>_<fecha>/, de donde se restaura o se vacía.
import glob, json, os, re, shutil, time

NOMBRE = re.compile(r'^[a-z0-9][a-z0-9_]{0,47}$')


def _patrones(paso, tipo, n):
    """Rutas (relativas a la carpeta del asset, con comodines) que deja `paso` en un asset de `tipo`."""
    t, gd, go = 'trabajo', f'godot/personajes/{n}', f'godot/objetos/{n}'
    blend = [f'{t}/{n}.blend', f'{t}/{n}.blend1']
    comun = {
        'imagen': [f'{t}/imagen/cand_*.png', f'{t}/imagen/candidatos.png', f'{t}/imagen/prompt.txt', f'{t}/imagen/wf_s*.json'],
        'vistas': [f'{t}/imagen/vista_*.png', f'{t}/imagen/vistas.png', f'{t}/imagen/wf_vista_*.json'],
        'malla': [f'{t}/malla', f'{t}/malla_*', f'{t}/comparar', f'{t}/candidatos.png'],
        'ultratex': [f'{t}/malla/ultratex_*.png'],   # + la malla del motor de vuelta (deshacer)
        'comparar': [f'{t}/comparar', f'{t}/candidatos.png'],
    }
    if tipo == 'personaje':
        return {**comun,
                'articulaciones': [f'{t}/guia/articulaciones.json', f'{t}/guia/pose_*.png'],   # + las de antes
                'guia': [f'{t}/guia/guia.png', f'{t}/guia/guia.json', f'{t}/guia/frente.png', f'{t}/guia/costado.png'],
                'blender': blend + [f'{t}/frames', f'{t}/animado.glb', f'{t}/animado.json', f'{t}/tiempo_real'],
                'sprites': [f'{gd}/{n}_sheet.*', f'{gd}/{n}_meta.json', f'{gd}/{n}_retrato.png', f'{gd}/{n}_frente.png',
                            'preview.gif'],
                'retrato': [f'{t}/retrato', f'{gd}/{n}_retrato.png', f'{gd}/{n}_frente.png'],
                'iso': [f'{gd}/iso', 'preview_iso.gif', f'{t}/iso/*/', f'{t}/iso/iso.json'],
                'anclas': [f'{t}/iso/anclas.json'],
                'revisar': [f'{t}/reves', f'{t}/revision.png', f'{t}/cerca', f'{t}/revision_cerca.png'],
                'godot': [f'{gd}/*.tscn', f'{gd}/*.tres', f'{gd}/iso/*.tscn', f'{gd}/iso/*.tres', 'godot/personajes/_comun'],
                }.get(paso, [])
    if tipo == 'vehiculo':
        return {**comun,
                'blender': blend + [f'{t}/vehiculo*.glb', f'{t}/tarjeta*.png', f'{t}/revision*.png', f'{t}/licencias.json'],
                }.get(paso, [])
    if tipo == 'objeto':
        return {**comun,
                'blender': blend + [f'{t}/render', f'{t}/tiempo_real'],
                'sprites': [go, 'preview.png'],
                'godot': [f'{go}/*.tscn', f'{go}/*.tres', 'godot/objetos/_comun'],
                }.get(paso, [])
    return {'texturas': [f'{t}/texturas'], 'tema': [f'{t}/tema', 'preview.png']}.get(paso, [])


PASOS = ('imagen', 'vistas', 'malla', 'ultratex', 'articulaciones', 'guia', 'blender', 'sprites', 'retrato', 'iso',
         'anclas', 'revisar', 'godot', 'comparar', 'texturas', 'tema')


def que_borra(pdir, tipo, nombre, paso):
    """Las rutas (relativas) que existen y se borrarían: [(ruta, bytes)], carpetas con todo su contenido."""
    if paso not in PASOS:
        raise ValueError(f'paso: {", ".join(PASOS)}')
    out = {}
    for pat in _patrones(paso, tipo, nombre):
        for r in glob.glob(os.path.join(pdir, pat)):
            r = r.rstrip('/')
            if os.path.isdir(r):
                tam = sum(os.path.getsize(os.path.join(a, f)) for a, _, fs in os.walk(r) for f in fs)
            elif os.path.isfile(r):
                tam = os.path.getsize(r)
            else:
                continue
            out[os.path.relpath(r, pdir)] = tam
    return sorted(out.items())


def _json_del_asset(pdir):
    for f in ('personaje.json', 'objeto.json', 'escenario.json'):
        if os.path.exists(os.path.join(pdir, f)):
            return os.path.join(pdir, f)


def extra(pdir, paso):
    """Lo que el paso deshace además de borrar (para mostrarlo antes), o None."""
    if paso == 'ultratex' and os.path.exists(os.path.join(pdir, 'trabajo', 'malla', 'modelo_motor.glb')):
        return 'trabajo/malla/modelo.glb vuelve a ser la malla del motor (modelo_motor.glb), sin el repintado'
    if paso == 'articulaciones':
        with open(_json_del_asset(pdir)) as f:
            m = json.load(f).get('modelo', {})
        if m.get('_articulaciones_previas'):
            return 'modelo.articulaciones vuelve a las de antes (modelo._articulaciones_previas)'
        if m.get('articulaciones') and os.path.exists(os.path.join(pdir, 'trabajo', 'guia', 'articulaciones.json')):
            return 'se borra modelo.articulaciones: quedan las estimadas por rebanadas'
    return None


def deshacer(pdir, tipo, nombre, paso):
    """Borra lo de `que_borra` y hace lo de `extra`. Devuelve (borrados, extra)."""
    hecho = extra(pdir, paso)
    if paso == 'ultratex' and hecho:
        m = os.path.join(pdir, 'trabajo', 'malla')
        shutil.copy(os.path.join(m, 'modelo_motor.glb'), os.path.join(m, 'modelo.glb'))
        os.remove(os.path.join(m, 'modelo_motor.glb'))
    if paso == 'articulaciones' and hecho:
        ruta = _json_del_asset(pdir)
        with open(ruta) as f:
            j = json.load(f)
        m = j['modelo']
        m['articulaciones'] = m.pop('_articulaciones_previas', None)
        with open(ruta, 'w') as f:
            json.dump(j, f, indent=2, ensure_ascii=False)
            f.write('\n')
    borrados = que_borra(pdir, tipo, nombre, paso)
    for r, _ in borrados:
        a = os.path.join(pdir, r)
        shutil.rmtree(a) if os.path.isdir(a) else os.remove(a)
    return [r for r, _ in borrados], hecho


# ---------- renombrar ----------

def renombrar(pdir, nombre, nuevo):
    """Mueve la carpeta del asset a `nuevo` y cambia el nombre en lo que lo lleva: godot/<tipo>/<n>/ (archivos, las
    rutas res:// y los nombres de las escenas y metas; los .import se borran: Godot los rehace) y trabajo/<n>.blend.
    Las rutas absolutas del json que apuntaban a la carpeta vieja pasan a la nueva. Devuelve la carpeta nueva."""
    if not NOMBRE.match(nuevo):
        raise ValueError('nombre nuevo: minúsculas, números y _ (empieza con letra o número, hasta 48)')
    destino = os.path.join(os.path.dirname(pdir), nuevo)
    for carpeta in ('personajes', 'objetos', 'escenarios'):
        if os.path.exists(os.path.join(os.path.dirname(os.path.dirname(pdir)), carpeta, nuevo)):
            raise ValueError(f'ya existe {carpeta}/{nuevo}')
    os.rename(pdir, destino)
    n = re.escape(nombre)
    # solo como tramo de ruta (res://personajes/<n>/) o nombre de archivo con extensión ("<n>_sheet.png"): las claves
    # de los metas (retrato, iso, idle_loop...) no llevan extensión y un asset puede llamarse así
    en_texto = re.compile(rf'(?<=/){n}(?=/)|(?<=["/]){n}(?=_[A-Za-z0-9_]*\.[A-Za-z0-9]+")')
    archivo = re.compile(rf'^{n}(?=_)')
    for sub in ('personajes', 'objetos'):
        d = os.path.join(destino, 'godot', sub, nombre)
        if not os.path.isdir(d):
            continue
        nd = os.path.join(destino, 'godot', sub, nuevo)
        os.rename(d, nd)
        for raiz, _, fs in os.walk(nd):
            for f in fs:
                a = os.path.join(raiz, f)
                if f.endswith('.import'):
                    os.remove(a)
                    continue
                if f.endswith(('.tscn', '.tres', '.json', '.gd')):
                    with open(a, encoding='utf-8') as x:
                        texto = x.read()
                    nuevo_texto = en_texto.sub(nuevo, texto)
                    if nuevo_texto != texto:
                        with open(a, 'w', encoding='utf-8') as x:
                            x.write(nuevo_texto)
                if archivo.match(f):
                    os.rename(a, os.path.join(raiz, archivo.sub(nuevo, f, count=1)))
    for ext in ('.blend', '.blend1'):
        a = os.path.join(destino, 'trabajo', nombre + ext)
        if os.path.exists(a):
            os.rename(a, os.path.join(destino, 'trabajo', nuevo + ext))
    ruta = _json_del_asset(destino)
    with open(ruta) as f:
        texto = f.read()
    if pdir in texto:
        with open(ruta, 'w') as f:
            f.write(texto.replace(pdir, destino))
    return destino


def ocupado(nombre):
    """PID de un `crisol` que esté corriendo un paso de este asset (no se puede renombrar ni deshacer), o None."""
    for d in os.listdir('/proc'):
        if not d.isdigit() or int(d) == os.getpid():
            continue
        try:
            with open(f'/proc/{d}/cmdline', 'rb') as f:
                cmd = [x.decode(errors='replace') for x in f.read().split(b'\0')]
        except OSError:
            continue
        if any(c.endswith('pipeline.py') or c.endswith('/crisol') for c in cmd) and \
                any(nombre in c.split(',') for c in cmd[2:]) and not {'estado', 'renombrar', 'deshacer', 'borrar', 'papelera'} & set(cmd):
            return int(d)
    return None


# ---------- papelera ----------

PAPELERA = '.papelera'
EN_PAPELERA = re.compile(r'^(personajes|objetos|escenarios)/([a-z0-9][a-z0-9_]{0,47})_(\d{8}-\d{6})$')


def tamano(ruta):
    return sum(os.path.getsize(os.path.join(a, f)) for a, _, fs in os.walk(ruta) for f in fs
               if not os.path.islink(os.path.join(a, f)))


def a_papelera(datos, pdir):
    """Mueve la carpeta del asset a <datos>/.papelera/<carpeta>/<n>_<fecha>/. Devuelve el id (<carpeta>/<n>_<fecha>).
    Lo instalado en un juego no se toca: es una copia."""
    carpeta, nombre = os.path.basename(os.path.dirname(pdir)), os.path.basename(pdir)
    destino_dir = os.path.join(datos, PAPELERA, carpeta)
    os.makedirs(destino_dir, exist_ok=True)
    fecha = time.strftime('%Y%m%d-%H%M%S')
    while os.path.exists(os.path.join(destino_dir, f'{nombre}_{fecha}')):   # dos borrados en el mismo segundo
        time.sleep(1)
        fecha = time.strftime('%Y%m%d-%H%M%S')
    os.rename(pdir, os.path.join(destino_dir, f'{nombre}_{fecha}'))
    return f'{carpeta}/{nombre}_{fecha}'


def papelera(datos):
    """Lo que hay en la papelera, lo último borrado primero: [{id, carpeta, nombre, borrado (epoch), bytes}]."""
    out = []
    raiz = os.path.join(datos, PAPELERA)
    for carpeta in ('personajes', 'objetos', 'escenarios'):
        d = os.path.join(raiz, carpeta)
        for x in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            m = EN_PAPELERA.match(f'{carpeta}/{x}')
            if not m or not os.path.isdir(os.path.join(d, x)):
                continue
            out.append({'id': f'{carpeta}/{x}', 'carpeta': carpeta, 'nombre': m[2],
                        'borrado': time.mktime(time.strptime(m[3], '%Y%m%d-%H%M%S')),
                        'bytes': tamano(os.path.join(d, x))})
    return sorted(out, key=lambda e: -e['borrado'])


def _de_papelera(datos, id_):
    m = EN_PAPELERA.match(id_ or '')
    ruta = os.path.join(datos, PAPELERA, id_) if m else None
    if not ruta or not os.path.isdir(ruta):
        raise ValueError(f'no está en la papelera: {id_}')
    return m, ruta


def restaurar(datos, id_):
    """Vuelve a poner el asset donde estaba. Si ya hay otro con ese nombre (en cualquier carpeta), no."""
    m, ruta = _de_papelera(datos, id_)
    nombre = m[2]
    for carpeta in ('personajes', 'objetos', 'escenarios'):
        if os.path.exists(os.path.join(datos, carpeta, nombre)):
            raise ValueError(f'ya existe {carpeta}/{nombre}: renombrar ese antes de restaurar')
    destino = os.path.join(datos, m[1], nombre)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    os.rename(ruta, destino)
    return destino


def vaciar(datos, ids=None):
    """Borra para siempre lo de la papelera (todo, o esos ids). Devuelve [(id, bytes)]."""
    lista = papelera(datos) if ids is None else [{'id': i} for i in ids]
    out = []
    for e in lista:
        _, ruta = _de_papelera(datos, e['id'])
        b = tamano(ruta)
        shutil.rmtree(ruta)
        out.append((e['id'], b))
    return out
