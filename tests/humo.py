#!/usr/bin/env python3
"""Test de humo sin GPU: corre los pasos de Blender en adelante sobre los ejemplos versionados (Cris, los objetos,
el bosque y el taller traen su malla o sus texturas elegidas) en una carpeta temporal y revisa lo que dejan.

uso: python3 tests/humo.py [--rapido] [--dejar]
  --rapido  sin iso, anclas, revisar ni Godot (solo blender + sprites + godot de cris y los objetos, tema): ~2 min
  --dejar   no borrar la carpeta temporal (para mirar los resultados)

Usa la config de siempre (config.json o ASSETCRISOL_CONFIG) para Blender y Godot, con un `datos_dir` temporal: no
toca los datos de la persona. No genera nada con IA: no pasa por ComfyUI ni TRELLIS.2. Con Godot configurado,
instala en un proyecto vacío temporal y lo abre headless instanciando cada escena. Sale con 1 si algo falla.
"""
import json, os, shutil, subprocess, sys, tempfile, time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRISOL = os.path.join(RAIZ, 'crisol')
RAPIDO, DEJAR = '--rapido' in sys.argv, '--dejar' in sys.argv
fallas = []


def paso(env, *args):
    t = time.time()
    r = subprocess.run([sys.executable, CRISOL, *args], env=env, capture_output=True, text=True)
    ok = r.returncode == 0
    print(f"  {'✔' if ok else '✘'} crisol {' '.join(args)} ({time.time() - t:.0f} s)", flush=True)
    if not ok:
        fallas.append(f"crisol {' '.join(args)}")
        print('\n'.join('      ' + l for l in (r.stdout + r.stderr).strip().splitlines()[-15:]))
    return ok


def paso_json(env, *args):
    """crisol <args> --json: stdout tiene que ser un solo JSON con ok y el estado del asset."""
    r = subprocess.run([sys.executable, CRISOL, *args, '--json'], env=env, capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
    except ValueError:
        d = None
    ok = r.returncode == 0 and d is not None and (not isinstance(d, dict) or d.get('ok') is not False)
    print(f"  {'✔' if ok else '✘'} crisol {' '.join(args)} --json")
    if not ok:
        fallas.append(f"crisol {' '.join(args)} --json")
        print('\n'.join('      ' + l for l in (r.stdout[-1500:] + r.stderr[-1500:]).strip().splitlines()[-15:]))
    return d if ok else None


def hay(base, *rutas):
    for r in rutas:
        p = os.path.join(base, r)
        ok = os.path.exists(p) and (os.path.isdir(p) or os.path.getsize(p) > 0)
        if not ok:
            fallas.append(f'falta {r}')
            print(f'  ✘ falta {r}')
    return all(os.path.exists(os.path.join(base, r)) for r in rutas)


def revisar_imagen(ruta, ancho_min=64, alto_min=64):
    """Que abra, tenga el tamaño mínimo y no esté vacía (todo transparente o de un solo color)."""
    from PIL import Image
    try:
        im = Image.open(ruta)
        im.load()
    except Exception as e:  # noqa: BLE001
        fallas.append(f'{ruta}: {e}')
        print(f'  ✘ {os.path.basename(ruta)} no abre: {e}')
        return
    vacia = im.convert('RGBA').getextrema()
    plana = all(lo == hi for lo, hi in vacia[:3]) or vacia[3][1] == 0
    if im.width < ancho_min or im.height < alto_min or plana:
        fallas.append(f'{ruta}: {im.size}, vacía' if plana else f'{ruta}: {im.size}')
        print(f'  ✘ {os.path.basename(ruta)}: {im.size}' + (' vacía' if plana else ''))


def revisar_aseprite(ruta, etiqueta):
    """El .json estilo Aseprite: que nombre la hoja de al lado, tenga la etiqueta y cuadros dentro de la imagen."""
    from PIL import Image
    try:
        with open(ruta) as f:
            d = json.load(f)
        W, H = Image.open(os.path.join(os.path.dirname(ruta), d['meta']['image'])).size
        assert any(t['name'] == etiqueta for t in d['meta']['frameTags']), f'sin la etiqueta {etiqueta}'
        assert all(c['frame']['x'] + c['frame']['w'] <= W and c['frame']['y'] + c['frame']['h'] <= H
                   for c in d['frames']), 'cuadros fuera de la hoja'
        assert d['meta']['frameTags'][-1]['to'] < len(d['frames']), 'etiqueta fuera de los cuadros'
    except (OSError, ValueError, KeyError, AssertionError) as e:
        fallas.append(f'{ruta}: {e}')
        print(f'  ✘ {os.path.basename(ruta)}: {e}')


def godot_headless(godot, proyecto, escenas):
    """Proyecto vacío + las escenas instaladas: las instancia una por una y sale con error si alguna no carga."""
    lineas = ['extends SceneTree', '', 'func _init():', '\tvar mal := 0']
    for i, e in enumerate(escenas):
        lineas += [f'\tvar p{i} = load("res://{e}")', f'\tif p{i} == null or p{i}.instantiate() == null:',
                   f'\t\tprinterr("NO CARGA: {e}")', '\t\tmal += 1']
    lineas += ['\tprint("ESCENAS OK" if mal == 0 else "ESCENAS MAL")', '\tquit(1 if mal else 0)']
    with open(os.path.join(proyecto, 'humo.gd'), 'w') as f:
        f.write('\n'.join(lineas) + '\n')
    r = subprocess.run([godot, '--headless', '--path', proyecto, '-s', 'res://humo.gd'], capture_output=True,
                       text=True, timeout=300)
    salida = r.stdout + r.stderr
    ok = 'ESCENAS OK' in salida
    print(f"  {'✔' if ok else '✘'} Godot instancia {len(escenas)} escena(s)")
    if not ok:
        fallas.append('Godot no instancia las escenas')
        print('\n'.join('      ' + l for l in salida.strip().splitlines()[-15:]))


def main():
    config = os.environ.get('ASSETCRISOL_CONFIG') or os.path.join(RAIZ, 'config.json')
    if not os.path.exists(config):
        sys.exit(f'falta {config}: el test usa la config para encontrar Blender (README > Instalación)')
    with open(config) as f:
        cfg = json.load(f)
    tmp = tempfile.mkdtemp(prefix='crisol_humo_')
    print(f'[humo] carpeta temporal: {tmp}')
    cfg['datos_dir'] = os.path.join(tmp, 'datos')
    with open(os.path.join(tmp, 'config.json'), 'w') as f:
        json.dump(cfg, f, indent=1)
    shutil.copytree(os.path.join(RAIZ, 'ejemplos'), cfg['datos_dir'])
    env = dict(os.environ, ASSETCRISOL_CONFIG=os.path.join(tmp, 'config.json'))
    D = cfg['datos_dir']
    t0 = time.time()
    try:
        print('[humo] personaje: cris')
        if paso(env, 'blender', 'cris') and paso(env, 'sprites', 'cris'):
            c = os.path.join(D, 'personajes', 'cris')
            g = os.path.join('godot', 'personajes', 'cris')
            hay(c, 'preview.gif', os.path.join(g, 'cris_meta.json'), os.path.join(g, 'cris_sheet.png'))
            revisar_aseprite(os.path.join(c, g, 'cris_sheet.json'), 'walk')
            revisar_imagen(os.path.join(c, g, 'cris_sheet.png'), 512, 512)
            if not RAPIDO and paso(env, 'iso', 'cris'):
                hay(c, 'preview_iso.gif', os.path.join(g, 'iso', 'cris_iso_meta.json'))
                with open(os.path.join(c, g, 'iso', 'cris_iso_meta.json')) as f:
                    meta = json.load(f)
                if len(meta['direcciones']) != 8 or 'walk' not in meta['animaciones']:
                    fallas.append('iso: meta sin 8 direcciones o sin walk')
                revisar_aseprite(os.path.join(c, g, 'iso', 'cris_iso_walk.json'), 'walk_s')
                for a in meta['animaciones'].values():
                    revisar_imagen(os.path.join(c, g, 'iso', a['imagen']), meta['frame_width'] * a['frames'],
                                   meta['frame_height'] * 8)
                if paso(env, 'anclas', 'cris'):
                    hay(c, os.path.join('trabajo', 'iso', 'anclas.json'))
                if paso(env, 'revisar', 'cris'):
                    hay(c, os.path.join('trabajo', 'revision.png'))
            if paso(env, 'godot', 'cris'):
                hay(c, os.path.join(g, 'cris_visual.tscn'))
        for obj in sorted(os.listdir(os.path.join(D, 'objetos'))):
            o = os.path.join(D, 'objetos', obj)
            with open(os.path.join(o, 'objeto.json')) as f:
                vehiculo = 'vehiculo' in json.load(f)
            print(f"[humo] {'vehículo' if vehiculo else 'objeto'}: {obj}")
            if vehiculo:   # sin sprites: el juego usa el .glb
                if paso(env, 'blender', obj):
                    hay(o, os.path.join('trabajo', 'vehiculo.glb'), os.path.join('trabajo', 'tarjeta.png'))
                    revisar_imagen(os.path.join(o, 'trabajo', 'revision.png'))
                continue
            if paso(env, 'blender', obj) and paso(env, 'sprites', obj) and paso(env, 'godot', obj):
                hay(o, 'preview.png', os.path.join('godot', 'objetos', obj, f'{obj}_iso.tscn'))
                with open(os.path.join(o, 'godot', 'objetos', obj, f'{obj}_meta.json')) as f:
                    revisar_aseprite(os.path.join(o, 'godot', 'objetos', obj, f'{obj}_iso.json'),
                                     json.load(f)['iso']['direcciones'][0])
                revisar_imagen(os.path.join(o, 'preview.png'))
        for esc in ('bosque', 'taller'):
            print(f'[humo] escenario: {esc}')
            d = paso_json(env, 'tema', esc)
            if d:
                e = os.path.join(D, 'escenarios', esc)
                hay(e, 'preview.png', os.path.join('trabajo', 'tema', 'tema.json'))
                revisar_imagen(os.path.join(e, 'preview.png'))
                if os.path.join(e, 'preview.png') not in d['mirar'] or d['estado']['siguiente']:
                    fallas.append(f'tema {esc} --json: sin preview.png en mirar o con un paso pendiente')
        print('[humo] estado')
        todos = paso_json(env, 'estado') or []
        for est in todos:
            if est['siguiente'] and not (RAPIDO and est['tipo'] == 'personaje'):
                fallas.append(f"estado {est['nombre']}: queda {est['siguiente']}")
                print(f"  ✘ estado {est['nombre']}: queda {est['siguiente']}")
        godot = cfg.get('godot')
        if not RAPIDO and godot and os.path.exists(godot) and not fallas:
            print('[humo] Godot: proyecto vacío temporal')
            proy = os.path.join(tmp, 'proyecto_godot')
            os.makedirs(proy)
            with open(os.path.join(proy, 'project.godot'), 'w') as f:
                f.write('config_version=5\n\n[application]\nconfig/name="humo"\n')
            escenas = ['personajes/cris/cris_visual.tscn', 'objetos/caja/caja_iso.tscn']
            if os.path.exists(os.path.join(D, 'personajes', 'cris', 'godot', 'personajes', 'cris', 'iso', 'cris_iso.tscn')):
                escenas.append('personajes/cris/iso/cris_iso.tscn')
            if paso(env, 'godot', 'cris', '--instalar', proy) and paso(env, 'godot', 'caja', '--instalar', proy):
                godot_headless(godot, proy, escenas)
    finally:
        if DEJAR:
            print(f'[humo] resultados en {tmp}')
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    print(f'[humo] {time.time() - t0:.0f} s: ' + ('todo bien' if not fallas else f'{len(fallas)} falla(s): ' +
                                                  '; '.join(fallas)))
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main())
