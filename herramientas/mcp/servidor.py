# Servidor MCP de AssetCrisol (stdio): las operaciones de alto nivel para un agente (recetas, crear, estado, correr un
# paso, ver, elegir, ajustar) sobre la CLI (`crisol <paso> <n> --json`), con las imágenes para mostrárselas a la
# persona. Lo lanza `crisol mcp` con uv (SDK de MCP + Pillow); los pasos corren con el python3 del sistema, como
# siempre. Los pasos largos (malla, ultratex...) siguen en segundo plano: `correr` espera un rato y si no terminó
# devuelve el trabajo para `esperar`.
import io, itertools, json, os, subprocess, sys, tempfile, time
from typing import Any

from mcp.server.mcpserver import Image, MCPServer
from PIL import Image as PILImage

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
import pipeline  # noqa: E402 (DATOS, CARPETAS y las recetas; no importa bpy ni torch)
import operaciones as op  # noqa: E402 (herramientas/0_entorno, en el path por pipeline)
from operaciones import PASOS, crisol  # noqa: E402

LADO_MAX = 1568          # lado máximo de las imágenes que se devuelven
MAX_IMAGENES = 6
TRABAJOS = {}            # id -> {'proc', 'paso', 'nombre', 'inicio', 'log'}
_ids = itertools.count(1)

app = MCPServer('assetcrisol', instructions="""\
AssetCrisol genera assets de juego (personajes animados, objetos, vehículos, escenarios) en esta PC, paso a paso.
Flujo: `recetas` -> `crear` -> `estado` (dice el paso siguiente y qué falta decidir) -> `correr` ese paso -> mirar
las imágenes que devuelve -> repetir. Reglas:
- La persona decide: imagen, candidatos de malla y texturas. Mostrale las hojas (vienen como imágenes en `estado`,
  `correr` y `ver`), preguntale y recién ahí usá `elegir` con lo que dijo. Nunca elijas por ella.
- Una generación por vez en la GPU: `correr` espera solo si está ocupada. Los pasos largos (malla 3-6 min) siguen
  en segundo plano: si `correr` devuelve un trabajo sin terminar, `esperar` con ese id.
- Las descripciones (`crear --descripcion`, imagen.descripcion) van en inglés.""")


def imagen(ruta):
    """PNG achicado a LADO_MAX; un gif animado, sus cuadros (hasta 8) en una grilla de 4 columnas."""
    im = PILImage.open(ruta)
    cuadros = getattr(im, 'n_frames', 1)
    if cuadros > 1:
        idx = sorted({round(i * (cuadros - 1) / 7) for i in range(8)})
        fotos = []
        for i in idx:
            im.seek(i)
            fotos.append(im.convert('RGBA'))
        w, h = fotos[0].size
        cols = min(4, len(fotos))
        hoja = PILImage.new('RGBA', (w * cols, h * ((len(fotos) + cols - 1) // cols)), (255, 255, 255, 255))
        for k, f in enumerate(fotos):
            hoja.paste(f, ((k % cols) * w, (k // cols) * h), f)
        im = hoja
    im.thumbnail((LADO_MAX, LADO_MAX))
    b = io.BytesIO()
    im.save(b, 'PNG')
    return Image(data=b.getvalue(), format='png')


def imagenes(rutas):
    out = []
    for r in rutas:
        if len(out) >= MAX_IMAGENES:
            break
        if r and r.lower().endswith(('.png', '.gif', '.jpg', '.jpeg', '.webp')) and os.path.exists(r):
            out += [f'[{r}]', imagen(r)]
    return out


def json_del_asset(nombre):
    return op.json_del_asset(pipeline.DATOS, pipeline.CARPETAS, nombre)


def resumen(d):
    """Lo que el agente necesita de un `--json`: ok, error, mensajes, siguiente y qué decidir (sin el estado entero)."""
    est = d.get('estado') or {}
    return json.dumps({'ok': d.get('ok'), 'codigo': d.get('codigo'), 'error': d.get('error'),
                       'mensajes': (d.get('mensajes') or [])[-12:], 'mirar': d.get('mirar'),
                       'siguiente': est.get('siguiente'), 'decidir': est.get('decidir')}, ensure_ascii=False, indent=1)


def resultado_trabajo(tid):
    t = TRABAJOS[tid]
    if t['proc'].poll() is None:
        return [f'trabajo {tid} ({t["paso"]} {t["nombre"]}) sigue corriendo ({time.time() - t["inicio"]:.0f} s): '
                f'`esperar` con trabajo="{tid}". Log: {t["log"]}']
    try:
        with open(t['log'][:-4] + '.json') as f:
            d = json.load(f)
    except ValueError:
        with open(t['log']) as f:
            return [f'trabajo {tid} terminó sin JSON (código {t["proc"].returncode}); fin del log:\n'
                    + ''.join(f.readlines()[-25:])]
    est = d.get('estado') or {}
    return [f'trabajo {tid} ({t["paso"]} {t["nombre"]}) terminó en {time.time() - t["inicio"]:.0f} s\n' + resumen(d)] \
        + imagenes((d.get('mirar') or []) + [x.get('mirar') for x in est.get('decidir') or []])


def esperar_trabajo(tid, segundos):
    fin = time.time() + max(0, min(segundos, 600))
    while TRABAJOS[tid]['proc'].poll() is None and time.time() < fin:
        time.sleep(1)
    return resultado_trabajo(tid)


@app.tool()
def recetas() -> str:
    """Tipos de asset que se pueden crear (humanoide, chibi, robot, juguete, objeto, vegetacion, vehiculo,
    escenario), con qué pone cada receta."""
    return '\n'.join(f'- {r} ({pipeline.cargar_receta(r)["_base"]}): {pipeline.cargar_receta(r)["_doc"]}'
                     for r in pipeline.RECETAS)


@app.tool()
def crear(nombre: str, receta: str = 'humanoide', descripcion: str | None = None,
          referencia: str | None = None) -> str:
    """Crea un asset nuevo con la receta de su tipo. `descripcion`: qué es, en inglés (ropa, colores, materiales);
    la receta le suma lo suyo. `referencia`: ruta a una imagen (foto o boceto) opcional. Nombre en minúsculas, sin
    espacios."""
    args = ['nuevo', nombre, '--receta', receta]
    if descripcion:
        args += ['--descripcion', descripcion]
    if referencia:
        args += ['--referencia', referencia]
    d, err = crisol(*args)
    return resumen(d) if d else f'falló: {err}'


@app.tool()
def estado(nombre: str | None = None) -> list:
    """Qué pasos están hechos, cuáles quedaron viejos, qué falta decidir (con la hoja a mirar, que se devuelve como
    imagen) y el comando siguiente. Sin nombre: todos los assets."""
    d, err = crisol('estado', *([nombre] if nombre else []))
    if d is None:
        return [f'falló: {err}']
    lista = d if isinstance(d, list) else [d]
    return [json.dumps(d, ensure_ascii=False, indent=1)] + \
        (imagenes([x.get('mirar') for e in lista for x in e.get('decidir') or []]) if nombre else [])


@app.tool()
def correr(nombre: str, paso: str, esperar_s: int = 50) -> list:
    """Corre un paso de crisol (imagen, vistas, malla, ultratex, articulaciones, guia, blender, sprites, retrato, iso,
    anclas, revisar, godot, comparar, texturas, tema, todo) y devuelve lo que hay que mirar como imágenes. Si tarda
    más que `esperar_s`, sigue en segundo plano: usar `esperar` con el id del trabajo."""
    if paso not in PASOS:
        return [f'paso desconocido: {paso} (hay: {", ".join(PASOS)})']
    for tid, t in TRABAJOS.items():
        if t['nombre'] == nombre and t['proc'].poll() is None:
            return [f'{nombre} ya tiene un trabajo corriendo ({tid}: {t["paso"]}): `esperar` antes']
    tid = f't{next(_ids)}'
    log = os.path.join(tempfile.gettempdir(), f'crisol_mcp_{os.getpid()}_{tid}_{paso}_{nombre}')
    proc = op.lanzar([paso, nombre], log)
    TRABAJOS[tid] = {'proc': proc, 'paso': paso, 'nombre': nombre, 'inicio': time.time(), 'log': log + '.log'}
    return esperar_trabajo(tid, esperar_s)


@app.tool()
def esperar(trabajo: str, esperar_s: int = 50) -> list:
    """Espera (hasta `esperar_s`, máx. 600) un trabajo de `correr` y devuelve su resultado, o que sigue corriendo."""
    if trabajo not in TRABAJOS:
        return [f'no hay trabajo {trabajo} (hay: {", ".join(TRABAJOS) or "ninguno"})']
    return esperar_trabajo(trabajo, esperar_s)


@app.tool()
def ver(nombre: str, archivo: str) -> list:
    """Devuelve una imagen del asset para mostrarla: `archivo` relativo a su carpeta (p. ej.
    trabajo/imagen/candidatos.png, trabajo/revision.png, preview.gif: de un gif, sus cuadros en una grilla)."""
    base = os.path.dirname(json_del_asset(nombre))
    ruta = os.path.realpath(os.path.join(base, archivo))
    if not ruta.startswith(os.path.realpath(base) + os.sep):
        return ['solo archivos dentro de la carpeta del asset']
    if not os.path.exists(ruta):
        return [f'no existe {ruta}']
    return imagenes([ruta]) or [f'{ruta} no es una imagen']


@app.tool()
def elegir(nombre: str, clave: str, valor: str) -> str:
    """Anota lo que ELIGIÓ LA PERSONA: imagen.elegida (seed), malla.elegida (candidato) o texturas.<clave>.elegida
    (seed). Solo con su respuesta explícita después de mostrarle la hoja: nunca elegir por ella. `estado` lista qué
    falta decidir y las opciones."""
    ruta = json_del_asset(nombre)
    try:
        v = op.elegir(ruta, clave, valor)
    except ValueError as e:
        return str(e)
    d, _ = crisol('estado', nombre)
    return f'{clave} = {v!r} en {ruta}; siguiente: {(d or {}).get("siguiente")}'


@app.tool()
def ajustar(nombre: str, cambios: dict[str, Any]) -> str:
    """Cambia valores del json del asset con claves de puntos, p. ej. {"imagen.seeds": [5, 6, 7, 8],
    "modelo.altura": 1.6, "estilo": "semirealista", "animacion.cabeza_arriba_grados": -5} (README > personaje.json).
    Las elecciones van con `elegir`. Después del cambio, `estado` dice qué pasos quedan viejos."""
    ruta = json_del_asset(nombre)
    try:
        op.ajustar(ruta, cambios)
    except ValueError as e:
        return str(e)
    return f'cambiado en {ruta}: ' + ', '.join(f'{k} = {v!r}' for k, v in cambios.items())


@app.tool()
def doctor() -> str:
    """Revisa la instalación: qué falta, cómo arreglarlo y qué pasos quedan deshabilitados."""
    r = subprocess.run([op.PY, op.PIPELINE, 'doctor'], capture_output=True, text=True)
    return (r.stdout + r.stderr)[-6000:]


if __name__ == '__main__':
    app.run()
