# `crisol estado <n>`: qué pasos de un personaje, objeto o escenario están hechos, cuáles quedaron viejos (su salida
# es anterior a la de un paso previo) y qué falta decidir. Solo mira archivos y el json: no corre nada.
import glob, os


def _fecha(ruta):
    return os.path.getmtime(ruta) if ruta and os.path.exists(ruta) else None


def _paso(nombre, salida, entradas=(), aplica=True, opcional=False, nota=None):
    """Un paso de la cadena: hecho si existe `salida`, viejo si alguna entrada es más nueva. `salida` y `entradas`
    son rutas absolutas (o None)."""
    if not aplica:
        return {'paso': nombre, 'estado': 'no_aplica'}
    t = _fecha(salida)
    if t is None:
        e = 'opcional' if opcional else 'falta'
    else:
        nuevas = [os.path.basename(r) for r in entradas if r and (_fecha(r) or 0) > t + 1]
        e = 'viejo' if nuevas else 'hecho'
    d = {'paso': nombre, 'estado': e, 'archivo': salida}
    if opcional:
        d['opcional'] = True
    if e == 'viejo':
        d['nota'] = f'anterior a {", ".join(nuevas)}'
    elif nota:
        d['nota'] = nota
    return d


def glb_hecho(glb, img):
    return _fecha(glb) is not None and (_fecha(img) or 0) <= _fecha(glb) + 1


def imagen_elegida(pdir, pj):
    """Ruta de la imagen elegida (cand_<seed>.png o un archivo de la carpeta), o None."""
    seed = pj.get('imagen', {}).get('elegida')
    if seed is None:
        return None
    for p in (os.path.join(pdir, 'trabajo', 'imagen', f'cand_{seed}.png'), os.path.join(pdir, str(seed))):
        if os.path.isfile(p):
            return p
    return None


def _cadena_malla(pdir, pj, decidir):
    """imagen -> vistas -> malla, comunes a personajes y objetos. Devuelve (pasos, ruta de modelo.glb)."""
    t = os.path.join(pdir, 'trabajo')
    img = imagen_elegida(pdir, pj)
    cands = sorted(glob.glob(os.path.join(t, 'imagen', 'cand_*.png')))
    elegida = pj.get('imagen', {}).get('elegida')
    pasos = [_paso('imagen', img or (cands[-1] if cands else None),
                   nota=f'{len(cands)} candidata(s) en trabajo/imagen/candidatos.png' if cands else None)]
    if elegida is None:
        if cands:
            decidir.append({'clave': 'imagen.elegida', 'mirar': os.path.join(t, 'imagen', 'candidatos.png'),
                            'opciones': [os.path.basename(c)[5:-4] for c in cands]})
    elif img is None:
        pasos[0] = {'paso': 'imagen', 'estado': 'falta', 'nota': f'imagen.elegida = {elegida!r} no existe'}
    m = pj.get('malla', {})
    vistas = bool(pj.get('vehiculo')) or (m.get('motor') == 'pixal3d' and m.get('vistas'))
    pasos.append(_paso('vistas', os.path.join(t, 'imagen', 'vistas.png'), [img], aplica=vistas))
    glb = os.path.join(t, 'malla', 'modelo.glb')
    if pasos[-1]['estado'] == 'falta' and glb_hecho(glb, img):   # la malla ya salió (con vistas sueltas o sin la hoja)
        pasos[-1].update(estado='hecho', nota='sin trabajo/imagen/vistas.png, pero la malla ya está')
    ent = [img] + ([os.path.join(t, 'imagen', 'vistas.png')] if vistas else [])
    if m.get('candidatos'):
        nombres = [m.get('motor', 'trellis2')] + list(m['candidatos'])
        hechos = [n for n in nombres if os.path.exists(os.path.join(t, f'malla_{n}', 'modelo.glb'))]
        p = _paso('malla', glb, ent, nota=f'candidatos hechos: {", ".join(hechos) or "ninguno"} de {", ".join(nombres)}'
                                            f'; elegida: {m.get("elegida", nombres[0])}')
        if len(hechos) < len(nombres) and p['estado'] == 'hecho':
            p['estado'], p['nota'] = 'falta', f'faltan candidatos: {", ".join(n for n in nombres if n not in hechos)}'
        pasos.append(p)
        if 'elegida' not in m and hechos:
            hoja = os.path.join(t, 'revision.png' if pj.get('vehiculo') else 'candidatos.png')
            decidir.append({'clave': 'malla.elegida', 'mirar': hoja, 'opciones': nombres,
                            'nota': f'sin elegir queda {nombres[0]}'})
    else:
        pasos.append(_paso('malla', glb, ent, nota='con UltraTex' if m.get('ultratex') else None))
    return pasos, glb


def personaje(pdir, pj, nombre):
    t = os.path.join(pdir, 'trabajo')
    g = os.path.join(pdir, 'godot', 'personajes', nombre)
    decidir = []
    pasos, glb = _cadena_malla(pdir, pj, decidir)
    blend = os.path.join(t, f'{nombre}.blend')
    meta, iso = os.path.join(g, f'{nombre}_meta.json'), os.path.join(g, 'iso', f'{nombre}_iso_meta.json')
    art = 'cargadas en modelo.articulaciones' if pj['modelo'].get('articulaciones') else 'estimadas (sin modelo.articulaciones)'
    pasos += [
        _paso('guia', os.path.join(t, 'guia', 'guia.png'), [glb], opcional=True, nota=art),
        _paso('blender', blend, [glb]),
        _paso('sprites', meta, [blend]),
        _paso('iso', iso, [glb]),
        _paso('anclas', os.path.join(t, 'iso', 'anclas.json'), [iso]),
        _paso('revisar', os.path.join(t, 'revision.png'), [meta, iso]),
        _paso('godot', os.path.join(g, f'{nombre}_visual.tscn'), [meta], opcional=True),
    ]
    return pasos, decidir


def objeto(pdir, pj, nombre):
    t = os.path.join(pdir, 'trabajo')
    decidir = []
    pasos, glb = _cadena_malla(pdir, pj, decidir)
    if pj.get('vehiculo'):
        pasos.append(_paso('blender', os.path.join(t, 'vehiculo.glb'), [glb],
                           nota='mirar trabajo/revision.png'))
        return pasos, decidir
    blend = os.path.join(t, f'{nombre}.blend')
    g = os.path.join(pdir, 'godot', 'objetos', nombre)
    meta = os.path.join(g, f'{nombre}_meta.json')
    pasos += [_paso('blender', blend, [glb]), _paso('sprites', meta, [blend]),
              _paso('godot', os.path.join(g, f'{nombre}_iso.tscn'), [meta], opcional=True)]
    return pasos, decidir


def escenario(pdir, esc, nombre):
    t = os.path.join(pdir, 'trabajo')
    hoja = os.path.join(t, 'texturas', 'candidatos.png')
    decidir, faltan = [], []
    for clave, tx in esc.get('texturas', {}).items():
        cands = glob.glob(os.path.join(t, 'texturas', clave, '*.png'))
        if not cands:
            faltan.append(clave)
        elif tx.get('elegida') is None:
            decidir.append({'clave': f'texturas.{clave}.elegida', 'mirar': hoja, 'opciones': tx.get('seeds', [])})
    p = _paso('texturas', hoja)
    if faltan and p['estado'] != 'falta':
        p['estado'], p['nota'] = 'falta', f'sin candidatas: {", ".join(faltan)}'
    return [p, _paso('tema', os.path.join(t, 'tema', 'tema.json'), [hoja])], decidir


def estado(pdir, pj, nombre):
    """{'nombre', 'tipo', 'carpeta', 'pasos': [...], 'decidir': [...], 'siguiente': 'crisol <paso> <n>' | None}"""
    if pj.get('_escenario'):
        tipo, (pasos, decidir) = 'escenario', escenario(pdir, pj, nombre)
    elif pj.get('_objeto'):
        tipo, (pasos, decidir) = 'vehiculo' if pj.get('vehiculo') else 'objeto', objeto(pdir, pj, nombre)
    else:
        tipo, (pasos, decidir) = 'personaje', personaje(pdir, pj, nombre)
    siguiente = None
    for p in pasos:
        if p['estado'] in ('falta', 'viejo') and not p.get('opcional'):
            bloquea = [d for d in decidir if p['paso'] != 'imagen' and d['clave'] == 'imagen.elegida'
                       or p['paso'] == 'tema' and d['clave'].startswith('texturas.')]
            siguiente = None if bloquea else f'crisol {p["paso"]} {nombre}'
            break
    return {'nombre': nombre, 'tipo': tipo, 'carpeta': pdir, 'pasos': pasos, 'decidir': decidir,
            'siguiente': siguiente}


MARCAS = {'hecho': '✔', 'viejo': '↻', 'falta': '·', 'opcional': '-', 'no_aplica': ' '}


def texto(e):
    """Versión para leer en la terminal."""
    lineas = [f'{e["nombre"]} ({e["tipo"]}): {e["carpeta"]}']
    for p in e['pasos']:
        if p['estado'] == 'no_aplica':
            continue
        lineas.append(f'  {MARCAS[p["estado"]]} {p["paso"]:9s} {p["estado"]:9s}' + (f' {p["nota"]}' if p.get('nota') else ''))
    for d in e['decidir']:
        op = ', '.join(str(o) for o in d['opciones'])
        lineas.append(f'  decidir {d["clave"]} ({op}) mirando {d["mirar"]}' + (f'; {d["nota"]}' if d.get('nota') else ''))
    if e['siguiente']:
        lineas.append(f'  siguiente: {e["siguiente"]}')
    elif e['decidir']:
        lineas.append('  siguiente: elegir (lo de arriba) en el json')
    else:
        lineas.append('  todo hecho')
    return '\n'.join(lineas)
