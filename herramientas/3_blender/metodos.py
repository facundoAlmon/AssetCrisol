# Método de cada animación: 'procedural' (anim.py, poses a mano) o 'kimodo' (clip de movimientos/, traducido por
# kimodo_clip.py). Por defecto, el recomendado en la biblioteca de movimientos; un personaje lo pisa con
# animacion.metodos = {"<anim>": "procedural" | "kimodo"}. Sin bpy ni numpy: lo usan pipeline.py, blender_main.py y
# crisol ui.
#
# La biblioteca son dos: la del repo (herramientas/3_blender/movimientos/biblioteca.json, versionada) y la propia de
# datos_dir (<datos_dir>/movimientos/biblioteca.json + <anim>.npz, la que escribe `crisol clip`; pipeline.py pasa su
# carpeta en CRISOL_MOVIMIENTOS). Una entrada propia con `clip` reemplaza a la del repo; sin `clip` (solo
# recomendado, desde, hasta) se aplica encima de la del repo (un null borra ese campo).
import ast, json, os, re, struct, zipfile

MOVIMIENTOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'movimientos')
METODOS = ('procedural', 'kimodo')
# cuadros y loop de cada animación que puede salir de un clip (los de anim.py: cambiarlos corre los índices de la hoja)
CUADROS = {'caminar': (8, True), 'respirar': (8, True), 'correr': (12, True), 'rodar': (8, False),
           'golpe': (7, False), 'patada': (8, False), 'herido': (3, False), 'morir': (6, False),
           'lanzar': (6, False), 'brazos_arriba': (6, False), 'cargar': (6, True)}
CANDIDATO = re.compile(r'^([a-z_]+)_s(-?\d+)_(\d+)$')   # movimientos/candidatos/<anim>_s<seed>_<muestra>.npz


def propia():
    """Carpeta de la biblioteca propia (<datos_dir>/movimientos) o None."""
    return os.environ.get('CRISOL_MOVIMIENTOS') or None


def leer(carpeta):
    """El biblioteca.json de `carpeta` tal cual (con _doc) o {} si no hay."""
    ruta = os.path.join(carpeta, 'biblioteca.json') if carpeta else None
    if not ruta or not os.path.exists(ruta):
        return {}
    with open(ruta) as f:
        return json.load(f)


def biblioteca():
    """{anim: entrada} de las dos bibliotecas; cada entrada con `_dir` (dónde está su clip) y `_origen`
    ('repo', 'propia' o 'repo+propia': la del repo con cambios de la propia)."""
    bib = {k: dict(v, _dir=MOVIMIENTOS, _origen='repo') for k, v in leer(MOVIMIENTOS).items() if not k.startswith('_')}
    d = propia()
    for k, v in leer(d).items():
        if k.startswith('_') or not isinstance(v, dict):
            continue
        if v.get('clip'):
            e = dict(v, _dir=d, _origen='propia')
        elif k in bib:
            e = dict(bib[k], **v, _origen='repo+propia')
        else:
            continue          # cambios sobre una entrada del repo que ya no existe
        bib[k] = {kk: vv for kk, vv in e.items() if vv is not None}
    return bib


def ruta_clip(c):
    return os.path.join(c.get('_dir') or MOVIMIENTOS, c['clip'])


def recomendado(nombre, bib=None):
    c = (biblioteca() if bib is None else bib).get(nombre)
    return 'kimodo' if c and c.get('recomendado') else 'procedural'


def metodo(nombre, a, bib=None):
    """Método con que se arma la animación `nombre` para la config de animación `a`."""
    bib = biblioteca() if bib is None else bib
    m = (a.get('metodos') or {}).get(nombre) or recomendado(nombre, bib)
    if m not in METODOS:
        raise ValueError(f'animacion.metodos.{nombre} = {m!r}: tiene que ser {" o ".join(METODOS)}')
    if m == 'kimodo' and nombre not in bib:
        raise ValueError(f'{nombre}: no hay clip de Kimodo en la biblioteca de movimientos '
                         f'(generar con `crisol movimiento {nombre} --prompt ...` y pasarlo con `crisol clip`)')
    return m


# ---------- candidatos (los .npz de `crisol movimiento`), leídos sin numpy ----------

def _npy(z, nombre, datos=False):
    """(descr, shape, bytes o None) del arreglo `nombre` de un .npz abierto con zipfile."""
    with z.open(nombre + '.npy') as f:
        cab = f.read(10)
        if cab[:6] != b'\x93NUMPY':
            raise ValueError(f'{nombre}: no es un .npy')
        largo = struct.unpack('<H', cab[8:10])[0] if cab[6] == 1 else struct.unpack('<I', cab[8:10] + f.read(2))[0]
        h = ast.literal_eval(f.read(largo).decode('latin1'))
        return h['descr'], tuple(h['shape']), f.read() if datos else None


def info_clip(ruta):
    """{cuadros, fps, duracion, prompt} de un clip (lo que se pueda leer; {} si no se puede)."""
    r = {}
    try:
        with zipfile.ZipFile(ruta) as z:
            _, forma, _ = _npy(z, 'posed_joints')
            r['cuadros'] = forma[0]
            descr, _, b = _npy(z, 'fps', True)
            formato = {'<f8': '<d', '<f4': '<f'}.get(descr)
            r['fps'] = struct.unpack_from(formato, b)[0] if formato else 30.0
            r['duracion'] = round(r['cuadros'] / r['fps'], 2)
            descr, _, b = _npy(z, 'prompt', True)
            if descr.startswith('<U'):
                r['prompt'] = b.decode('utf-32-le').rstrip('\0')
    except (OSError, KeyError, ValueError, SyntaxError, zipfile.BadZipFile, struct.error):
        pass
    return r


def candidatos(carpeta):
    """Los clips de `crisol movimiento` en `carpeta` (movimientos/candidatos), los más nuevos primero:
    [{id, animacion, seed, muestra, hoja, modificado, cuadros, fps, duracion, prompt}]."""
    out = []
    for a in os.listdir(carpeta) if os.path.isdir(carpeta) else []:
        m = CANDIDATO.match(a[:-4]) if a.endswith('.npz') else None
        if not m:
            continue
        ruta = os.path.join(carpeta, a)
        hoja = f'{m[1]}_s{m[2]}.png'
        out.append({'id': a[:-4], 'animacion': m[1], 'seed': int(m[2]), 'muestra': int(m[3]),
                    'hoja': hoja if os.path.exists(os.path.join(carpeta, hoja)) else None,
                    'modificado': os.path.getmtime(ruta), **info_clip(ruta)})
    return sorted(out, key=lambda c: (-round(c['modificado']), c['id']))
