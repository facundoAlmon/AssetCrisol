#!/usr/bin/env python3
"""Capturas de `crisol ui` para el manual (docs/ui.md, docs/ui.en.md): recorre las pantallas con el Chrome instalado
(Playwright, sin bajar otro navegador) sobre una UI que ya esté corriendo y guarda un PNG por captura e idioma.

La UI tiene que tener los datos del manual: los ejemplos con sus pasos de Blender hechos y el personaje del capítulo
1 (docs/ui.md > *Rehacer las capturas*). Nunca se corre contra los datos de trabajo: los pasos no se lanzan, pero las
capturas abren pantallas y no tienen que mostrar assets privados.

uso: python3 tests/capturas_ui.py  [--url http://127.0.0.1:8191] [--salida docs/ui/img] [--idiomas es,en]
                                          [--solo nombre1,nombre2] [--lista]
Se relanza con `uv run` y Playwright y Pillow fijados en PLAYWRIGHT; el navegador es `google-chrome` (channel "chrome").
"""
import argparse, json, os, re, shutil, sys, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(RAIZ, 'herramientas', 'ui', 'web')
PLAYWRIGHT = ('playwright==1.55.0', 'pillow==11.3.0')

ESCRITORIO = (1400, 900)
CELULAR = (390, 844)

# Cada captura: nombre (archivo <nombre>.webp: un tercio de un PNG, y 256 colores manchaban las caras), ruta (el hash de la UI), pasos antes de capturar y cómo.
#   pasos: ('clic', rol, clave)   clic en el elemento con ese rol y el texto de la clave de i18n (o 'txt:literal');
#                                 el texto puede venir precedido del número del paso ("6 3D animado") y seguido
#                                 de una cuenta ("Pesos por zonas (2)")
#          ('visor', clave)       clic en la pestaña del visor de Resultado (no en el botón del paso que se llama
#                                 igual: «Retrato» en la cadena corre `crisol retrato`)
#          ('texto', clave)       clic en el primer elemento con ese texto
#   Ningún paso tiene que lanzar trabajos: las capturas solo miran.
#          ('llenar', css, txt)   escribe txt en el campo
#          ('esperar', ms)
#          ('js', código)
#   recorte: selector CSS de lo que se captura, o ('seccion', clave) = la <section> con ese título (sin él, la
#            ventana; las barras fijas de guardar/bajar quedan en su lugar, no encima)
#   pagina: True = la ventana se estira al alto de la página (full_page deja el lateral y las barras fijas a mitad)
#   alto: sin recorte, solo los primeros `alto` px de la ventana
#   tema: 'light' | 'dark'; tam: (ancho, alto)
#   momento: True = muestra un punto del capítulo 1 que ya pasó (la exploradora antes de elegir...), o datos que se
#            arman solo para la captura (docs/ui.md > *Rehacer las capturas*): solo con --solo
VER_3D = ('esperar', 3000)   # el visor 3D carga three.js y el glb
PANEL = 'section.panel:has(> .pestanas)'   # el panel de Resultado / Ajustes / Archivos, sin la cadena de pasos
CAPTURAS = [
    # 0. antes de empezar
    dict(nombre='biblioteca', ruta='#/'),
    dict(nombre='biblioteca_oscuro', ruta='#/', tema='dark'),
    dict(nombre='biblioteca_celular', ruta='#/', tam=CELULAR),
    dict(nombre='instalacion', ruta='#/instalacion', recorte=('seccion', 'inst.pasos')),
    # 1. el primer personaje (la exploradora)
    dict(nombre='nuevo', ruta='#/nuevo', pagina=True, pasos=[
        ('llenar', 'textarea', 'a young explorer woman with short curly dark hair, fitted olive green field jacket'
                               ' with rolled-up sleeves, tan cargo pants tucked into brown hiking boots'),
        ('llenar', 'input.entrada.mono', 'aventurera')]),
    dict(nombre='elegir_imagen', ruta='#/a/exploradora', pagina=True, momento=True),
    dict(nombre='cola', ruta='#/cola', momento=True),
    # aventurera: copia de la exploradora sin elegir, con una corrección de la 101 (y una con caras de UltraTex)
    dict(nombre='corregir_imagen', ruta='#/a/aventurera', recorte=('seccion', 'decidir.titulo'), momento=True, pasos=[
        ('js', "document.querySelectorAll('.opcion')[3].querySelector('button[aria-expanded]').click()"),
        ('llenar', 'form.corregir textarea', 'remove the hanging compass')]),
    dict(nombre='elegir_vistas', ruta='#/a/exploradora', momento=True),
    dict(nombre='elegir_malla', ruta='#/a/exploradora', pagina=True, momento=True),
    dict(nombre='elegir_cara', ruta='#/a/aventurera', recorte=('seccion', 'decidir.titulo'), momento=True),
    # 2. ver el resultado (Cris)
    dict(nombre='asset', ruta='#/a/cris'),   # la página de un asset: la cadena de pasos y el resultado
    dict(nombre='resultado_iso', ruta='#/a/cris', recorte=PANEL),
    dict(nombre='resultado_animado', ruta='#/a/cris', recorte=PANEL, pasos=[('visor', 'visor.animado'), VER_3D]),
    dict(nombre='resultado_animacion', ruta='#/a/cris', recorte=PANEL, pasos=[('visor', 'visor.animacion')]),
    dict(nombre='resultado_retrato', ruta='#/a/cris', recorte=PANEL, pasos=[('visor', 'visor.retrato')]),
    dict(nombre='retrato_editar', ruta='#/a/cris', recorte=PANEL,
         pasos=[('visor', 'visor.retrato'), ('clic', 'button', 'retrato.editar'), ('esperar', 1500)]),
    dict(nombre='resultado_juego3d', ruta='#/a/cris', recorte=PANEL, pasos=[('visor', 'visor.juego3d'), VER_3D]),
    dict(nombre='resultado_revision', ruta='#/a/cris', recorte=PANEL, pasos=[('visor', 'visor.revision')]),
    dict(nombre='resultado_guia', ruta='#/a/cris', recorte=PANEL, pasos=[('visor', 'visor.guia')]),
    dict(nombre='articulaciones', ruta='#/a/cris', recorte=PANEL,
         pasos=[('visor', 'visor.guia'), ('clic', 'button', 'art.editar'), ('esperar', 1000)]),
    # la exploradora tiene modelo.pesos_zonas (las manos en los bolsillos): solo se abre el editor, no se guarda
    dict(nombre='zonas', ruta='#/a/exploradora', recorte=PANEL,
         pasos=[('visor', 'visor.guia'), ('clic', 'button', 'zonas.boton'), ('esperar', 1500)]),
    # 3. cuando algo sale mal
    dict(nombre='paso_mas', ruta='#/a/cris', recorte='ol.cadena > li:first-child', pasos=[('clic', 'button', 'ayuda.mas')]),
    # Deshacer solo abre la confirmación (qué borra y cuánto pesa): Borrar no se toca
    dict(nombre='deshacer', ruta='#/a/cris', recorte='ol.cadena > li:first-child', pasos=[('clic', 'button', 'desh.boton')]),
    # 4. ajustes (Cris), una sección por captura
    dict(nombre='ajustes_prompt', ruta='#/a/exploradora/ajustes', recorte=('seccion', 'aj.g.prompt')),
    *[dict(nombre=f'ajustes_{g}', ruta='#/a/cris/ajustes', recorte=('seccion', f'aj.g.{g}'))
      for g in ('estilo', 'imagen', 'malla', 'modelo', 'sprites', 'animaciones', 'juego3d')],
    # 5. otros tipos de asset
    dict(nombre='objeto', ruta='#/a/caja', pasos=[VER_3D]),
    dict(nombre='vehiculo', ruta='#/a/camioneta', pasos=[VER_3D]),
    dict(nombre='escenario', ruta='#/a/taller'),
    # 6. movimientos
    dict(nombre='movimientos', ruta='#/movimientos'),
    dict(nombre='movimientos_animacion', ruta='#/movimientos/golpe', recorte='section.panel:has(.clips.dos)'),
    # variantes de golpe sin pasar (movimientos/candidatos de datos_dir) con Borrar abierto, sin confirmar
    dict(nombre='movimientos_variantes', ruta='#/movimientos/golpe', recorte='.clip.generacion', momento=True, tam=(1400, 1800),
         pasos=[('js', "document.querySelector('.variante button.peligro').click()")]),
    # 7. llevarlo al juego
    dict(nombre='exportar', ruta='#/a/cris/archivos', recorte=('seccion', 'exp.titulo')),
    # 8. cola y biblioteca
    dict(nombre='biblioteca_seleccionar', ruta='#/', pasos=[('clic', 'button', 'bib.seleccionar')]),
    dict(nombre='cola_historial', ruta='#/cola', pagina=True),
    # Borrar solo abre la confirmación (cuánto ocupa): «A la papelera» no se toca
    dict(nombre='borrar', ruta='#/a/cris', alto=330, pasos=[('clic', 'button', 'borrar.boton'), ('esperar', 800)]),
    dict(nombre='papelera', ruta='#/papelera', alto=420, momento=True),   # con algo en la papelera
]


def textos(idioma):
    """las claves de i18n de la UI ('clave': 'texto'), con las de es.mjs de base"""
    def leer(archivo):
        with open(os.path.join(WEB, 'i18n', archivo), encoding='utf-8') as f:
            src = f.read()
        return {m[1]: m[2].replace("\\'", "'") for m in re.finditer(r"^\s*'([\w.]+)':\s*'((?:[^'\\]|\\.)*)'", src, re.M)}
    t = leer('es.mjs')
    if idioma != 'es':
        t.update(leer(f'{idioma}.mjs'))
    return t


def texto(t, clave):
    if clave.startswith('txt:'):
        return clave[4:]
    if clave not in t:
        sys.exit(f'capturas: no existe la clave de i18n {clave!r}')
    return re.sub(r'\{\w+\}', '', t[clave]).strip()


def ids_cola(url):
    with urllib.request.urlopen(url.rstrip('/') + '/api/cola', timeout=10) as r:
        return {x['id'] for x in json.load(r)['trabajos']}


fallas = []


def recortar(pagina, elemento, destino, margen=16):
    """el elemento con un margen alrededor del color de fondo de lo que lo contiene (no se ve lo de al lado)"""
    from PIL import Image
    elemento.screenshot(path=destino)
    fondo = elemento.evaluate("""e => { for (; e; e = e.parentElement) { const c = getComputedStyle(e).backgroundColor
        if (c && c !== 'transparent' && !c.endsWith(', 0)')) return c.match(/\\d+/g).slice(0, 3).map(Number) }
        return [255, 255, 255] }""")
    im = Image.open(destino).convert('RGB')
    lienzo = Image.new('RGB', (im.width + 2 * margen, im.height + 2 * margen), tuple(fondo))
    lienzo.paste(im, (margen, margen))
    lienzo.save(destino)


def capturar(pw, url, salida, idioma, capturas):
    t = textos(idioma)
    antes = ids_cola(url)
    nav = pw.chromium.launch(channel='chrome')
    try:
        for c in capturas:
            try:
                ancho, alto = c.get('tam', ESCRITORIO)
                ctx = nav.new_context(viewport={'width': ancho, 'height': alto}, device_scale_factor=1,
                                      color_scheme=c.get('tema', 'light'), locale='es-AR' if idioma == 'es' else 'en-US')
                ctx.add_init_script(f"try {{ localStorage.setItem('crisol.idioma', '{idioma}');"
                                    f" localStorage.setItem('crisol.tema', 'sistema') }} catch (e) {{}}")
                ctx.set_default_timeout(8000)
                pagina = ctx.new_page()
                pagina.goto(url.rstrip('/') + '/' + c['ruta'], wait_until='load')   # networkidle no llega nunca: el SSE de la cola queda abierto
                pagina.wait_for_timeout(1500)
                for p in c.get('pasos', ()):
                    if p[0] == 'clic':
                        nombre = re.compile(r'^\s*(\d+\s*)?' + re.escape(texto(t, p[2])) + r'\s*(\(\d+\))?\s*$')   # «Pesos por zonas (2)»
                        pagina.get_by_role(p[1], name=nombre).first.click()
                    elif p[0] == 'visor':
                        nombre = re.compile(r'^\s*(\d+\s*)?' + re.escape(texto(t, p[1])) + r'\s*$')
                        pagina.locator('.segmentos.desplazable[role=group]').get_by_role('button', name=nombre).first.click()
                    elif p[0] == 'llenar':
                        pagina.locator(p[1]).first.fill(p[2])
                    elif p[0] == 'texto':
                        pagina.get_by_text(texto(t, p[1]), exact=True).first.click()
                    elif p[0] == 'esperar':
                        pagina.wait_for_timeout(p[1])
                    elif p[0] == 'js':
                        pagina.evaluate(p[1])
                    pagina.wait_for_timeout(400)
                pagina.wait_for_timeout(c.get('espera', 600))
                destino = os.path.join(salida, idioma, c['nombre'] + '.png')
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                pagina.add_style_tag(content='.barra-guardar { position: static !important }')
                r = c.get('recorte')
                if isinstance(r, tuple):
                    # la sección cuyo título propio es ese (no una de afuera que la contiene)
                    tit = texto(t, r[1]).replace('"', '')
                    n = 'normalize-space()'   # el título puede traer el número del paso delante ("1Generar...")
                    h = (f'*[self::h2 or self::h3][substring({n}, string-length({n}) - {len(tit)} + 1) = "{tit}"'
                         f' and string-length({n}) <= {len(tit) + 3}]')
                    recortar(pagina, pagina.locator(f'xpath=//section[./{h} or ./header/{h}]').first, destino)
                elif r:
                    recortar(pagina, pagina.locator(r).first, destino)
                else:
                    if c.get('pagina'):
                        alto_pagina = pagina.evaluate('document.documentElement.scrollHeight')
                        pagina.set_viewport_size({'width': ancho, 'height': alto_pagina})
                        pagina.wait_for_timeout(500)
                    pagina.screenshot(path=destino, clip={'x': 0, 'y': 0, 'width': ancho, 'height': c['alto']}
                                      if c.get('alto') else None)
                from PIL import Image
                Image.open(destino).convert('RGB').save(destino[:-4] + '.webp', quality=88, method=6)
                os.remove(destino)
                print(f'  {idioma}/{c["nombre"]}.webp', flush=True)
                ctx.close()
                if ids_cola(url) - antes:   # las capturas solo miran: un clic que lanzó un paso es un error del script
                    sys.exit(f'capturas: {c["nombre"]} puso un trabajo en la cola ({", ".join(ids_cola(url) - antes)}): '
                             'revisar sus pasos y cancelarlo en la Cola')
            except Exception as e:   # una pantalla que no está (un paso sin hacer): seguir con las otras
                ctx.close()
                fallas.append(f'{idioma}/{c["nombre"]}: {str(e).splitlines()[0]}')
                print(f'  ✘ {fallas[-1]}', flush=True)
    finally:
        nav.close()


def main():
    ap = argparse.ArgumentParser(description='capturas de crisol ui para el manual')
    ap.add_argument('--url', default='http://127.0.0.1:8191')
    ap.add_argument('--salida', default=os.path.join(RAIZ, 'docs', 'ui', 'img'))
    ap.add_argument('--idiomas', default='es,en')
    ap.add_argument('--solo', default='')
    ap.add_argument('--lista', action='store_true', help='solo listar las capturas')
    a = ap.parse_args()
    if a.lista:
        print('\n'.join(c['nombre'] + ('   (momento: solo con --solo)' if c.get('momento') else '') for c in CAPTURAS))
        return
    elegidas = [c for c in CAPTURAS if c['nombre'] in a.solo.split(',')] if a.solo else \
        [c for c in CAPTURAS if not c.get('momento')]
    if a.solo and len(elegidas) != len(a.solo.split(',')):
        sys.exit(f'capturas: alguna de {a.solo} no está en la lista (--lista)')
    try:
        from playwright.sync_api import sync_playwright
        import PIL   # noqa: F401
    except ImportError:
        if os.environ.get('CRISOL_CAPTURAS_UV') or not shutil.which('uv'):
            sys.exit(f'capturas: hacen falta {" y ".join(PLAYWRIGHT)} (con uv se pone solo: curl -LsSf https://astral.sh/uv/install.sh | sh)')
        os.environ['CRISOL_CAPTURAS_UV'] = '1'
        os.execvp('uv', ['uv', 'run', '--quiet', '--no-project', *(x for d in PLAYWRIGHT for x in ('--with', d)),
                         'python', *sys.argv])
    with sync_playwright() as pw:
        for idioma in a.idiomas.split(','):
            capturar(pw, a.url, a.salida, idioma, elegidas)
    if fallas:
        sys.exit(f'capturas: {len(fallas)} sin sacar')


if __name__ == '__main__':
    main()
