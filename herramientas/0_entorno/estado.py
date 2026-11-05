# `crisol estado <n>`: qué pasos de un personaje, objeto o escenario están hechos, cuáles quedaron viejos (su salida
# es anterior a la de un paso previo) y qué falta decidir. Solo mira archivos y el json: no corre nada.
import glob, json, os


def _fecha(ruta):
    return os.path.getmtime(ruta) if ruta and os.path.exists(ruta) else None


def _aviso(d, nota, id_, **datos):
    """La nota del paso para la terminal y, para la UI, `aviso` = {id, ...datos}: la UI lo dice en palabras (i18n
    `aviso.<id>`) en vez de mostrar rutas y claves del json."""
    d['nota'] = nota
    d['aviso'] = dict(id=id_, **datos)
    return d


def _paso(nombre, salida, entradas=(), aplica=True, opcional=False, nota=None, aviso=None):
    """Un paso de la cadena: hecho si existe `salida`, viejo si alguna entrada es más nueva. `salida` y `entradas`
    son rutas absolutas (o None). `aviso` = (id, {datos}) acompaña a `nota` (ver _aviso)."""
    if not aplica:
        return {'paso': nombre, 'estado': 'no_aplica'}
    t = _fecha(salida)
    if t is None:
        e = 'opcional' if opcional else 'falta'
    else:
        rutas = [r for r in entradas if r and (_fecha(r) or 0) > t + 1]
        nuevas = [os.path.basename(r) for r in rutas]
        e = 'viejo' if nuevas else 'hecho'
    d = {'paso': nombre, 'estado': e, 'archivo': salida}
    if opcional:
        d['opcional'] = True
    if e == 'viejo':
        _aviso(d, f'anterior a {", ".join(nuevas)}', 'viejo', _rutas=rutas)   # estado() pasa rutas a pasos
    elif nota:
        d['nota'] = nota
        if aviso:
            d['aviso'] = dict(id=aviso[0], **aviso[1])
    return d


def _en_trabajo(t, nombres):
    """Qué candidato de malla está en trabajo/malla (lo anota pipeline.copiar_candidato; en copias de antes, el único
    candidato con un modelo.glb del mismo tamaño), o None si no se sabe."""
    try:
        with open(os.path.join(t, 'malla', 'candidato.txt')) as f:
            return f.read().strip() or None
    except OSError:
        pass
    tam = lambda d: os.path.getsize(os.path.join(t, d, 'modelo.glb')) if os.path.exists(os.path.join(t, d, 'modelo.glb')) else None
    iguales = [n for n in nombres if tam(f'malla_{n}') is not None and tam(f'malla_{n}') == tam('malla')]
    return iguales[0] if len(iguales) == 1 else None


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
                   nota=f'{len(cands)} candidata(s) en trabajo/imagen/candidatos.png' if cands else None,
                   aviso=('candidatas', {'n': len(cands)}) if elegida is None else
                   ('imagen_elegida', {'elegida': elegida}))]
    if elegida is None:
        if cands:
            decidir.append({'clave': 'imagen.elegida', 'mirar': os.path.join(t, 'imagen', 'candidatos.png'),
                            'opciones': [os.path.basename(c)[5:-4] for c in cands]})
    elif img is None:
        pasos[0] = _aviso({'paso': 'imagen', 'estado': 'falta'}, f'imagen.elegida = {elegida!r} no existe',
                          'imagen_no_existe', elegida=elegida)
        if os.path.exists(os.path.join(t, 'malla', 'modelo.glb')):   # p. ej. los ejemplos: traen la malla sola
            _aviso(pasos[0], pasos[0]['nota'] + ', pero la malla ya está', 'imagen_sin_archivo', elegida=elegida)
            pasos[0]['estado'] = 'hecho'
    m = pj.get('malla', {})
    vistas = bool(pj.get('vehiculo')) or (m.get('motor') == 'pixal3d' and m.get('vistas'))
    pasos.append(_paso('vistas', os.path.join(t, 'imagen', 'vistas.png'), [img], aplica=vistas))
    glb = os.path.join(t, 'malla', 'modelo.glb')
    if pasos[-1]['estado'] == 'falta' and glb_hecho(glb, img):   # la malla ya salió (con vistas sueltas o sin la hoja)
        _aviso(pasos[-1], 'sin trabajo/imagen/vistas.png, pero la malla ya está', 'vistas_sin_hoja')
        pasos[-1]['estado'] = 'hecho'
    ent = [img] + ([os.path.join(t, 'imagen', 'vistas.png')] if vistas else [])
    if m.get('candidatos'):
        nombres = [m.get('motor', 'trellis2')] + list(m['candidatos'])
        hechos = [n for n in nombres if os.path.exists(os.path.join(t, f'malla_{n}', 'modelo.glb'))]
        p = _paso('malla', glb, ent, nota=f'candidatos hechos: {", ".join(hechos) or "ninguno"} de {", ".join(nombres)}'
                                            f'; elegida: {m.get("elegida", nombres[0])}',
                  aviso=('candidatos', {'hechos': len(hechos), 'total': len(nombres),
                                        'elegida': m.get('elegida', nombres[0])}))
        pasos.append(p)
        elegida = m.get('elegida', nombres[0])
        actual = _en_trabajo(t, nombres) if p['estado'] == 'hecho' else None
        if actual not in (None, elegida):
            _aviso(p, f'trabajo/malla es {actual}, no la elegida ({elegida}): `malla` la copia (los generados no se '
                      'rehacen)', 'malla_otra' if elegida in hechos else 'malla_sin_generar', actual=actual,
                   elegida=elegida)
            p['estado'] = 'viejo'
        if 'elegida' not in m and hechos:
            hoja = os.path.join(t, 'revision.png' if pj.get('vehiculo') else 'candidatos.png')
            decidir.append({'clave': 'malla.elegida', 'mirar': hoja, 'opciones': nombres,
                            'nota': f'sin elegir queda {nombres[0]}', 'aviso': {'id': 'sin_elegir', 'n': nombres[0]}})
    else:
        pasos.append(_paso('malla', glb, ent, nota='con UltraTex' if m.get('ultratex') else None,
                           aviso=('ultratex', {})))
    if pj.get('modelo', {}).get('esqueleto') == 'cuadrupedo':   # Pixal3D anima mal los cuadrúpedos: TRELLIS.2
        principal = m.get('motor', 'trellis2')   # el principal es el candidato que se llama como su motor
        elegida = m.get('elegida', principal)
        motor = principal if elegida == principal else (m.get('candidatos') or {}).get(elegida, {}).get('motor', principal)
        p = pasos[-1]
        if motor == 'pixal3d' and p.get('aviso', {}).get('id') in (None, 'ultratex', 'candidatos'):
            _aviso(p, 'Pixal3D anima mal los cuadrúpedos (patas quietas, capas de adentro): usar TRELLIS.2',
                   'pixal3d_cuadrupedo')
    return pasos, glb


def _articulaciones(marca, glb, pj):
    """Hecho si corrió (trabajo/guia/articulaciones.json, aunque DWPose no haya podido) o si están cargadas a mano."""
    p = _paso('articulaciones', marca, [glb])
    if p['estado'] == 'falta' and pj['modelo'].get('articulaciones'):
        return _aviso(dict(p, estado='hecho'), 'ya están en modelo.articulaciones', 'art_cargadas')
    if p['estado'] == 'hecho':
        try:
            with open(marca) as f:
                m = json.load(f)
        except (OSError, ValueError):
            m = {}
        if m.get('motivo'):
            antes = bool(pj['modelo'].get('articulaciones'))
            quedan = 'las de antes' if antes else 'estimadas por rebanadas'
            _aviso(p, f'DWPose no pudo ({m["motivo"]}): quedan {quedan}; revisar la guía',
                   'dwpose_no_antes' if antes else 'dwpose_no', motivo=m['motivo'])
        elif m.get('fuente') == 'a mano':
            _aviso(p, 'a mano (editor de crisol ui)', 'art_mano')
        else:
            _aviso(p, 'DWPose', 'art_dwpose')
    return p


def personaje(pdir, pj, nombre):
    t = os.path.join(pdir, 'trabajo')
    g = os.path.join(pdir, 'godot', 'personajes', nombre)
    decidir = []
    pasos, glb = _cadena_malla(pdir, pj, decidir)
    blend = os.path.join(t, f'{nombre}.blend')
    meta, iso = os.path.join(g, f'{nombre}_meta.json'), os.path.join(g, 'iso', f'{nombre}_iso_meta.json')
    cargadas = bool(pj['modelo'].get('articulaciones'))
    art = 'cargadas en modelo.articulaciones' if cargadas else 'estimadas (sin modelo.articulaciones)'
    marca = os.path.join(t, 'guia', 'articulaciones.json')
    cuadrupedo = pj['modelo'].get('esqueleto') == 'cuadrupedo'   # DWPose es para humanoides: sin ese paso
    pasos += [] if cuadrupedo else [_articulaciones(marca, glb, pj)]
    pasos += [
        _paso('guia', os.path.join(t, 'guia', 'guia.png'), [glb], opcional=True, nota=art,
              aviso=('guia_cargadas' if cargadas else 'guia_estimadas', {})),
        _paso('blender', blend, [glb] if cuadrupedo else [glb, marca]),
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
        vglb = os.path.join(t, 'vehiculo.glb')
        pasos.append(_paso('blender', vglb, [glb], nota='mirar trabajo/revision.png' if os.path.exists(vglb) else None,
                           aviso=('mirar_revision', {})))
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
    decidir, faltan, todas = [], [], []
    for clave, tx in esc.get('texturas', {}).items():
        cands = glob.glob(os.path.join(t, 'texturas', clave, '*.png'))
        todas += cands
        if not cands:
            faltan.append(clave)
        elif tx.get('elegida') is None:
            decidir.append({'clave': f'texturas.{clave}.elegida', 'mirar': hoja, 'opciones': tx.get('seeds', [])})
    ultima = max(todas, key=os.path.getmtime) if todas else None
    if faltan:
        p = _aviso({'paso': 'texturas', 'estado': 'falta'}, f'sin candidatas: {", ".join(faltan)}', 'texturas_faltan',
                   claves=', '.join(faltan))
    else:
        p = _paso('texturas', ultima)
    return [p, _paso('tema', os.path.join(t, 'tema', 'tema.json'), [ultima])], decidir


def estado(pdir, pj, nombre):
    """{'nombre', 'tipo', 'carpeta', 'pasos': [...], 'decidir': [...], 'siguiente': 'crisol <paso> <n>' | None}"""
    if pj.get('_escenario'):
        tipo, (pasos, decidir) = 'escenario', escenario(pdir, pj, nombre)
    elif pj.get('_objeto'):
        tipo, (pasos, decidir) = 'vehiculo' if pj.get('vehiculo') else 'objeto', objeto(pdir, pj, nombre)
    else:
        tipo, (pasos, decidir) = 'personaje', personaje(pdir, pj, nombre)
    de_archivo = {p.get('archivo'): p['paso'] for p in pasos if p.get('archivo')}
    for p in pasos:   # el aviso de un paso viejo nombra los pasos (no los archivos) que cambiaron después
        rutas = p.get('aviso', {}).pop('_rutas', None)
        if rutas is not None:
            p['aviso']['pasos'] = [de_archivo.get(r, os.path.basename(r)) for r in rutas]
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
        lineas.append(f'  {MARCAS[p["estado"]]} {p["paso"]:14s} {p["estado"]:9s}' + (f' {p["nota"]}' if p.get('nota') else ''))
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
