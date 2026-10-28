# Operaciones de alto nivel sobre la CLI (`crisol <paso> <n> --json`), comunes al servidor MCP (herramientas/mcp) y
# a la UI web (herramientas/ui): correr un paso y leer su JSON, lanzarlo en segundo plano a archivos, encontrar el json
# de un asset, anotar lo que eligió la persona y ajustar valores. Solo stdlib: lo importan el python del sistema y el
# de `uv run` del MCP.
import json, os, subprocess

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PIPELINE = os.path.join(RAIZ, 'pipeline.py')
PY = os.environ.get('CRISOL_PYTHON', 'python3')   # el del sistema: `crisol mcp` y `crisol ui` lo pasan
PASOS = ('imagen', 'vistas', 'malla', 'ultratex', 'guia', 'articulaciones', 'blender', 'sprites', 'retrato', 'iso',
         'anclas', 'revisar', 'godot', 'comparar', 'texturas', 'tema', 'todo')


def crisol(*args, timeout=120, env=None):
    """crisol <args> --json y espera: (dict del JSON o None, stderr)."""
    r = subprocess.run([PY, PIPELINE, *args, '--json'], capture_output=True, text=True, timeout=timeout, env=env)
    try:
        return json.loads(r.stdout), r.stderr
    except ValueError:
        return None, (r.stdout + r.stderr)[-3000:]


def lanzar(args, base, env=None, **kw):
    """crisol <args> --json en segundo plano: el JSON a `base`.json y lo demás a `base`.log (a archivos: un pipe lleno
    trabaría el paso). Devuelve el Popen."""
    with open(base + '.json', 'w') as out, open(base + '.log', 'w') as err:
        return subprocess.Popen([PY, PIPELINE, *args, '--json'], stdout=out, stderr=err, stdin=subprocess.DEVNULL,
                                env=env, **kw)


def json_del_asset(datos, carpetas, nombre):
    """Ruta del personaje.json / objeto.json / escenario.json de `nombre` (pipeline.DATOS, pipeline.CARPETAS)."""
    for carpeta, archivo in carpetas:
        ruta = os.path.join(datos, carpeta, nombre, archivo)
        if os.path.exists(ruta):
            return ruta
    raise ValueError(f'no existe {nombre} en personajes/, objetos/ ni escenarios/ de {datos}')


def leer(ruta):
    with open(ruta) as f:
        return json.load(f)


def guardar(ruta, cfg):
    with open(ruta, 'w') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write('\n')


def poner(cfg, clave, valor):
    """cfg['a']['b'] = valor para la clave 'a.b' (crea los bloques que falten)."""
    *ruta, ultima = clave.split('.')
    d = cfg
    for k in ruta:
        d = d.setdefault(k, {})
        if not isinstance(d, dict):
            raise ValueError(f'{clave}: {k} no es un bloque')
    d[ultima] = valor


def clave_de_eleccion(clave):
    """Las elecciones de la persona: imagen.elegida, malla.elegida, texturas.<clave>.elegida."""
    return clave in ('imagen.elegida', 'malla.elegida') or \
        (clave.startswith('texturas.') and clave.endswith('.elegida') and clave.count('.') == 2)


def elegir(ruta, clave, valor):
    """Anota lo que ELIGIÓ LA PERSONA en el json de `ruta`. Devuelve el valor guardado (una seed queda como int)."""
    if not clave_de_eleccion(clave):
        raise ValueError('clave: imagen.elegida, malla.elegida o texturas.<clave>.elegida')
    v = int(valor) if isinstance(valor, str) and valor.lstrip('-').isdigit() else valor
    cfg = leer(ruta)
    poner(cfg, clave, v)
    guardar(ruta, cfg)
    return v


def ajustar(ruta, cambios):
    """Cambia valores con claves de puntos; las elecciones no (van con `elegir`)."""
    if any(k.endswith('.elegida') for k in cambios):
        raise ValueError('las elecciones de la persona van con `elegir`')
    cfg = leer(ruta)
    for k, v in cambios.items():
        poner(cfg, k, v)
    guardar(ruta, cfg)
