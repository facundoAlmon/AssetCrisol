# Códigos de salida de `crisol` (para agentes y scripts) y la salida --json de los pasos.
import io, json, os, sys, traceback

OK = 0
ERROR = 1          # el paso falló (ver el mensaje o el log que nombra)
USO = 2            # argumentos mal (argparse)
GPU_OCUPADA = 3    # con --sin-esperar (gpu.py)
FALTA_ELEGIR = 4   # falta una decisión de la persona (imagen.elegida, texturas.<clave>.elegida...)
FALTA_PASO = 5     # falta la salida de un paso anterior (correr ese paso primero)
FALTA_INSTALAR = 6 # a la instalación le falta algo que el paso necesita (`crisol doctor`)

# imágenes para mostrarle a la persona o mirar antes de dar el paso por bueno
PARA_MIRAR = ('candidatos.png', 'vistas.png', 'revision.png', 'guia.png', 'preview.gif', 'preview_iso.gif',
              'preview.png', 'ultratex_vistas.png', 'ultratex_espalda.png', 'ultratex_costados.png', 'tarjeta.png')
MAX_POR_CARPETA = 20   # más archivos nuevos en una carpeta (frames, celdas iso): se resume la carpeta


motivo = None   # el mensaje de la última salida con código (para el JSON)


def salir(codigo, msg):
    """Sale con `codigo` y el mensaje en stderr."""
    global motivo
    motivo = msg
    print(msg, file=sys.stderr, flush=True)
    sys.exit(codigo)


def falta_elegir(msg):
    salir(FALTA_ELEGIR, msg)


def falta_paso(msg):
    salir(FALTA_PASO, msg)


def foto(carpetas):
    """{ruta: mtime} de todos los archivos bajo `carpetas` (para ver qué escribió un paso)."""
    f = {}
    for c in carpetas:
        for raiz, _, archivos in os.walk(c):
            for a in archivos:
                p = os.path.join(raiz, a)
                try:
                    f[p] = os.path.getmtime(p)
                except OSError:
                    pass
    return f


def cambios(antes, despues):
    """(archivos, carpetas): los nuevos o modificados; una carpeta con más de MAX_POR_CARPETA va resumida."""
    nuevos = sorted(p for p, t in despues.items() if antes.get(p) != t)
    por_dir = {}
    for p in nuevos:
        por_dir.setdefault(os.path.dirname(p), []).append(p)
    archivos, carpetas = [], []
    for d, ps in sorted(por_dir.items()):
        if len(ps) > MAX_POR_CARPETA:
            carpetas.append({'carpeta': d, 'archivos': len(ps)})
        else:
            archivos += ps
    return archivos, carpetas


class _Copia(io.TextIOBase):
    """stdout que además guarda las líneas (los mensajes `[paso] ...` del pipeline)."""
    def __init__(self, destino):
        self.destino, self.lineas, self._resto = destino, [], ''

    def write(self, s):
        self.destino.write(s)
        self._resto += s
        *hechas, self._resto = self._resto.split('\n')
        self.lineas += [l for l in hechas if l.strip()]
        return len(s)

    def flush(self):
        self.destino.flush()


def correr_json(paso, nombre, carpetas, fn, estado_de=None):
    """Corre fn() con todo lo que se imprime (también lo de los subprocesos) yendo a stderr, y al final escribe en
    stdout un solo JSON: {paso, nombre, ok, codigo, error, archivos, carpetas, mirar, mensajes, estado}. Sale con el
    código del paso."""
    sys.stdout.flush()
    fd_json = os.dup(1)
    os.dup2(2, 1)                        # subprocesos (Blender, ComfyUI...) heredan el fd 1: van a stderr
    copia = _Copia(sys.stdout)
    sys.stdout = copia
    antes = foto(carpetas)
    codigo, error = OK, None
    try:
        fn()
    except SystemExit as e:
        if isinstance(e.code, int) or e.code is None:
            codigo = e.code or OK
        else:
            codigo, error = ERROR, str(e.code)
            print(error, file=sys.stderr)
    except KeyboardInterrupt:
        codigo, error = ERROR, 'cortado (Ctrl+C)'
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        codigo, error = ERROR, f'{type(e).__name__}: {e}'
    sys.stdout.flush()
    archivos, carpetas_n = cambios(antes, foto(carpetas))
    if codigo and error is None:          # salir(): falta elegir, falta un paso, GPU ocupada
        error = motivo or {FALTA_ELEGIR: 'falta elegir', FALTA_PASO: 'falta un paso anterior',
                 GPU_OCUPADA: 'GPU ocupada', USO: 'argumentos', FALTA_INSTALAR: 'falta instalar algo'}.get(codigo, 'falló')
    r = {'paso': paso, 'nombre': nombre, 'ok': codigo == OK, 'codigo': codigo, 'error': error,
         'archivos': archivos, 'carpetas': carpetas_n,
         'mirar': [p for p in archivos if os.path.basename(p) in PARA_MIRAR], 'mensajes': copia.lineas}
    if estado_de:
        try:
            r['estado'] = estado_de()
        except BaseException:  # noqa: BLE001 (el asset puede no existir: nuevo fallido)
            pass
    with os.fdopen(fd_json, 'w') as f:
        json.dump(r, f, indent=1, ensure_ascii=False)
        f.write('\n')
    sys.exit(codigo)
