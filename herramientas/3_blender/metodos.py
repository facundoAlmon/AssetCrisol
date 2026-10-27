# Método de cada animación: 'procedural' (anim.py, poses a mano) o 'kimodo' (clip de movimientos/, traducido por
# kimodo_clip.py). Por defecto, el recomendado en movimientos/biblioteca.json; un personaje lo pisa con
# animacion.metodos = {"<anim>": "procedural" | "kimodo"}. Sin bpy: lo usan pipeline.py y blender_main.py.
import json, os

MOVIMIENTOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'movimientos')
METODOS = ('procedural', 'kimodo')


def biblioteca():
    with open(os.path.join(MOVIMIENTOS, 'biblioteca.json')) as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith('_')}


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
        raise ValueError(f'{nombre}: no hay clip de Kimodo en movimientos/biblioteca.json '
                         f'(generar con `pipeline.py movimiento {nombre} --prompt ...`)')
    return m
