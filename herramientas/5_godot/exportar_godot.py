# Paso 5: arma personajes/<n>/godot/personajes/{<n>,_comun}/ listo para copiar a la raíz de un proyecto Godot
# (queda en res://personajes/...), y opcionalmente lo instala en un proyecto e importa en headless.
import json, os, shutil, subprocess

AQUI = os.path.dirname(os.path.abspath(__file__))

TSCN = '''[gd_scene format=3]

[ext_resource type="Script" path="res://personajes/_comun/sprite_personaje.gd" id="1_script"]
[ext_resource type="Texture2D" path="res://personajes/{n}/{n}_sheet.png" id="2_sheet"]
{ext_retrato}
[node name="{N}Visual" type="Node2D"]
script = ExtResource("1_script")
animaciones = {anims}
{props_retrato}
[node name="Sprite" type="Sprite2D" parent="."]
texture_filter = 4
position = Vector2({ox}, {oy})
scale = Vector2({e}, {e})
texture = ExtResource("2_sheet")
centered = false
hframes = {hf}
vframes = {vf}
'''

# mipmaps activados: la tira está en superresolución y se muestra reducida
IMPORT = '''[remap]

importer="texture"
type="CompressedTexture2D"

[deps]

source_file="res://personajes/{n}/{archivo}"

[params]

compress/mode=0
mipmaps/generate=true
mipmaps/limit=-1
process/fix_alpha_border=true
process/premult_alpha=false
process/size_limit=0
detect_3d/compress_to=1
'''


def exportar(nombre, dir_godot_raiz, meta):
    d = os.path.join(dir_godot_raiz, 'personajes', nombre)
    comun = os.path.join(dir_godot_raiz, 'personajes', '_comun')
    os.makedirs(comun, exist_ok=True)
    shutil.copy(os.path.join(AQUI, 'sprite_personaje.gd'), comun)
    ox, oy = meta['offset']
    ext, props = '', ''
    for i, clave in enumerate(('retrato', 'frente')):
        if meta.get(clave):
            ext += f'[ext_resource type="Texture2D" path="res://personajes/{nombre}/{meta[clave]}" id="{3 + i}_{clave}"]\n'
            props += f'{clave} = ExtResource("{3 + i}_{clave}")\n'
    with open(os.path.join(d, f'{nombre}_visual.tscn'), 'w') as f:
        f.write(TSCN.format(n=nombre, N=nombre.capitalize(), ox=ox, oy=oy, e=meta['escala'], hf=meta['hframes'],
                            vf=meta.get('vframes', 1), anims=a_godot(meta.get('animaciones', {})),
                            ext_retrato=ext, props_retrato=props))
    for archivo in [meta['imagen']] + [meta[c] for c in ('retrato', 'frente') if meta.get(c)]:
        escribir_import(d, nombre, archivo)
    print('[godot] exportado en', d)


def escribir_import(d, nombre, archivo, sub=''):
    imp = os.path.join(d, archivo + '.import')
    if not os.path.exists(imp):  # no pisar el que ya reescribió Godot (tiene uid)
        with open(imp, 'w') as f:
            f.write(IMPORT.format(n=nombre, archivo=sub + archivo))


TSCN_ISO = '''[gd_scene format=3]

[ext_resource type="Script" path="res://personajes/_comun/sprite_personaje_iso.gd" id="1_script"]
[ext_resource type="SpriteFrames" path="res://personajes/{n}/iso/{n}_iso_frames.tres" id="2_frames"]

[node name="{N}Iso" type="Node2D"]
script = ExtResource("1_script")
shadow_radius = Vector2({sx}, {sy})

[node name="Sprite" type="AnimatedSprite2D" parent="."]
texture_filter = 4
scale = Vector2({e}, {e})
sprite_frames = ExtResource("2_frames")
animation = &"idle_s"
centered = false
offset = Vector2({ox}, {oy})
'''


def exportar_iso(nombre, dir_godot_raiz):
    """<n>/iso/: SpriteFrames (una animación por acción y dirección) + escena con sprite_personaje_iso.gd"""
    d = os.path.join(dir_godot_raiz, 'personajes', nombre, 'iso')
    with open(os.path.join(d, f'{nombre}_iso_meta.json')) as f:
        meta = json.load(f)
    shutil.copy(os.path.join(AQUI, 'sprite_personaje_iso.gd'), os.path.join(dir_godot_raiz, 'personajes', '_comun'))
    fw, fh = meta['frame_width'], meta['frame_height']
    ext, subs, anims = [], [], []
    for k, (n, A) in enumerate(meta['animaciones'].items()):
        ext.append(f'[ext_resource type="Texture2D" path="res://personajes/{nombre}/iso/{A["imagen"]}" id="{k + 1}_{n}"]')
        escribir_import(d, nombre, A['imagen'], 'iso/')
        for r, dn in enumerate(meta['direcciones']):
            cuadros = []
            for i in range(A['frames']):
                sid = f'{n}_{dn}_{i}'
                subs.append(f'[sub_resource type="AtlasTexture" id="{sid}"]\natlas = ExtResource("{k + 1}_{n}")\n'
                            f'region = Rect2({i * fw}, {r * fh}, {fw}, {fh})\n')
                cuadros.append(f'{{"duration": 1.0, "texture": SubResource("{sid}")}}')
            anims.append(f'{{\n"frames": [{", ".join(cuadros)}],\n"loop": {a_godot(A["loop"])},\n'
                         f'"name": &"{n}_{dn}",\n"speed": {float(A["fps"])}\n}}')
    with open(os.path.join(d, f'{nombre}_iso_frames.tres'), 'w') as f:
        f.write('[gd_resource type="SpriteFrames" format=3]\n\n' + '\n'.join(ext) + '\n\n' + '\n'.join(subs) +
                '\n[resource]\nanimations = [' + ', '.join(anims) + ']\n')
    b = meta['baldosa_px']
    with open(os.path.join(d, f'{nombre}_iso.tscn'), 'w') as f:
        f.write(TSCN_ISO.format(n=nombre, N=nombre.capitalize(), e=meta['escala'], ox=meta['offset'][0],
                                oy=meta['offset'][1], sx=round(b * 0.22, 1), sy=round(b * 0.11, 1)))
    print('[godot] iso exportado en', d)


def a_godot(v):
    """valor JSON -> literal de Godot (.tscn/.tres)"""
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, dict):
        return '{\n' + ',\n'.join(f'"{k}": {a_godot(x)}' for k, x in v.items()) + '\n}'
    if isinstance(v, (list, tuple)):
        return '[' + ', '.join(a_godot(x) for x in v) + ']'
    if isinstance(v, str):
        return json.dumps(v)
    return str(v)


def instalar(nombre, dir_godot_raiz, proyecto, godot_bin, carpeta='personajes'):
    if not os.path.exists(os.path.join(proyecto, 'project.godot')):
        raise SystemExit(f'[godot] {proyecto} no es un proyecto Godot (falta project.godot)')
    for sub in ('_comun', nombre):
        src = os.path.join(dir_godot_raiz, carpeta, sub)
        if not os.path.isdir(src):
            continue
        dst = os.path.join(proyecto, carpeta, sub)
        os.makedirs(dst, exist_ok=True)
        for raiz, _, archivos in os.walk(src):
            destino = os.path.join(dst, os.path.relpath(raiz, src))
            os.makedirs(destino, exist_ok=True)
            for fn in archivos:
                if fn.endswith('.import') and os.path.exists(os.path.join(destino, fn)):
                    continue  # conservar el .import del proyecto (uid estable)
                shutil.copy(os.path.join(raiz, fn), destino)
    print('[godot] instalado en', os.path.join(proyecto, carpeta, nombre))
    if godot_bin and os.path.exists(godot_bin):
        r = subprocess.run([godot_bin, '--headless', '--path', proyecto, '--import'], capture_output=True, text=True,
                           timeout=300)
        errores = [l for l in (r.stdout + r.stderr).splitlines() if 'ERROR' in l]
        print('[godot] importado' + (' con errores:\n' + '\n'.join(errores) if errores else ' sin errores'))
