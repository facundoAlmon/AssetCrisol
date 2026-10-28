# Qué modelos hicieron un asset y si eso permite venderlo (docs/licencias.md, con el detalle y las condiciones de cada
# licencia). Sale de la configuración actual del json: si se cambió un motor después de generar, rehacer ese paso.
# Es una guía, no asesoramiento legal.

# clave: (nombre, licencia, permite uso comercial)
MODELOS = {
    'qwen_edit': ('Qwen Image Edit 2511 + LoRA Lightning', 'Apache-2.0', True),
    'zimage': ('Z-Image Turbo', 'Apache-2.0', True),
    'flux2': ('FLUX.2 Dev', 'FLUX.2 [dev] Non-Commercial License', False),
    'trellis2': ('TRELLIS.2', 'MIT (+ DINOv3 License)', True),
    'pixal3d': ('Pixal3D', 'MIT (+ DINOv3 License)', True),
    'ultratex': ('UltraTex (FLUX.2 Klein base 9B)', 'licencia no comercial de Black Forest Labs', False),
    'dwpose': ('DWPose', 'Apache-2.0', True),
    'kimodo': ('Kimodo-SOMA-RP', 'NVIDIA Open Model License (+ Llama 3 Community License)', True),
    'sdxl': ('DreamShaper XL Turbo', 'CreativeML Open RAIL++-M', True),
    'ip_adapter': ('IP-Adapter Plus SDXL', 'Apache-2.0', True),
}
DOC = 'docs/licencias.md'


def _imagen(pj, cfg):
    img = pj.get('imagen', {})
    if img.get('referencia'):
        return ['qwen_edit']
    import generar_imagen
    return [generar_imagen.motor_texto(cfg, pj)]


def claves(pj, cfg):
    """Claves de MODELOS que usó el asset (en el orden de los pasos)."""
    if pj.get('_escenario'):
        usados = []
        for t in pj.get('texturas', {}).values():
            motor = t.get('motor') or pj.get('motor', 'sdxl')
            usados.append({'flux': 'flux2'}.get(motor, motor))
            if motor == 'sdxl' and (t.get('referencia') or pj.get('referencia')):
                usados.append('ip_adapter')
        return list(dict.fromkeys(usados))
    m = pj.get('malla', {})
    elegida = m.get('elegida')
    if m.get('candidatos') and elegida and elegida in m['candidatos']:   # el candidato pisa claves de malla
        m = dict(m, **m['candidatos'][elegida])
    usados = _imagen(pj, cfg)
    if m.get('vistas') or pj.get('vehiculo'):
        usados.append('qwen_edit')
    usados.append(m.get('motor', 'trellis2'))
    if m.get('ultratex'):
        usados.append('ultratex')
    if not pj.get('_objeto'):
        if _usa_kimodo(pj.get('animacion', {})):
            usados.append('kimodo')
    return list(dict.fromkeys(usados))


def _usa_kimodo(animacion):
    """¿Alguna animación sale de un clip de Kimodo? (animacion.metodos o el recomendado de movimientos/biblioteca.json)"""
    try:
        import armar_iso, metodos
        bib = metodos.biblioteca()
        return any(metodos.metodo(a, animacion, bib) == 'kimodo' for a in armar_iso.NOMBRES)
    except Exception:  # noqa: BLE001
        return False


def del_asset(pj, cfg):
    """{'comercial': bool, 'modelos': [{nombre, licencia, comercial}], 'nota', 'detalle'} para el meta."""
    ks = claves(pj, cfg)
    modelos = [dict(zip(('nombre', 'licencia', 'comercial'), MODELOS[k])) for k in ks if k in MODELOS]
    no = [x['nombre'] for x in modelos if not x['comercial']]
    nota = (f'no comercial por {", ".join(no)}' if no else 'los modelos permiten uso comercial')
    if pj.get('imagen', {}).get('referencia'):
        nota += '; la referencia es de quien la puso: sus derechos también cuentan'
    return {'comercial': not no, 'modelos': modelos, 'nota': nota + ' (guía, no asesoramiento legal)', 'detalle': DOC}


def texto(lic):
    return ('apto para uso comercial' if lic['comercial'] else 'NO COMERCIAL') + f': {lic["nota"]}'
