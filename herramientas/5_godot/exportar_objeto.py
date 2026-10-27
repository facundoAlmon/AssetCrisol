# Paso godot de un objeto: arma <dir>/godot/objetos/{<n>,_comun}/ (replica res://objetos/...):
#   <n>_lateral.tscn  StaticBody2D + Sprite2D + colisión rectangular (juego de costado; origen = centro de la base)
#   <n>_iso.tscn      StaticBody2D con objeto_iso.gd: Sprite2D por dirección + huella como CollisionPolygon2D
import json, os, shutil

from exportar_godot import IMPORT, a_godot

AQUI = os.path.dirname(os.path.abspath(__file__))

LATERAL = '''[gd_scene format=3]

[ext_resource type="Texture2D" path="res://objetos/{n}/{n}_lateral.png" id="1_tex"]

[sub_resource type="RectangleShape2D" id="forma"]
size = Vector2({cw}, {chh})

[node name="{N}" type="StaticBody2D"]

[node name="Sprite" type="Sprite2D" parent="."]
texture_filter = 4
position = Vector2({ox}, {oy})
scale = Vector2({e}, {e})
texture = ExtResource("1_tex")
centered = false
{colision}'''

COLISION_LATERAL = '''
[node name="Colision" type="CollisionShape2D" parent="."]
position = Vector2(0, {py})
shape = SubResource("forma")
'''

ISO = '''[gd_scene format=3]

[ext_resource type="Script" path="res://objetos/_comun/objeto_iso.gd" id="1_script"]
[ext_resource type="Texture2D" path="res://objetos/{n}/{n}_iso.png" id="2_tex"]

[node name="{N}Iso" type="StaticBody2D"]
script = ExtResource("1_script")
huellas = {huellas}
nombres_direcciones = PackedStringArray({dirs})

[node name="Sprite" type="Sprite2D" parent="."]
texture_filter = 4
position = Vector2({ox}, {oy})
scale = Vector2({e}, {e})
texture = ExtResource("2_tex")
centered = false
hframes = {hf}
{colision}'''


def exportar(nombre, dir_godot_raiz):
    d = os.path.join(dir_godot_raiz, 'objetos', nombre)
    comun = os.path.join(dir_godot_raiz, 'objetos', '_comun')
    os.makedirs(comun, exist_ok=True)
    shutil.copy(os.path.join(AQUI, 'objeto_iso.gd'), comun)
    with open(os.path.join(d, f'{nombre}_meta.json')) as f:
        meta = json.load(f)
    N = ''.join(p.capitalize() for p in nombre.split('_'))
    L, I = meta['lateral'], meta['iso']
    cw, chh = L['colision_size']
    col = COLISION_LATERAL.format(py=-chh / 2) if meta['colision'] else ''
    with open(os.path.join(d, f'{nombre}_lateral.tscn'), 'w') as f:
        f.write(LATERAL.format(n=nombre, N=N, cw=cw, chh=chh, ox=L['offset'][0] * L['escala'],
                               oy=L['offset'][1] * L['escala'], e=L['escala'], colision=col))
    col = ('\n[node name="Colision" type="CollisionPolygon2D" parent="."]\npolygon = PackedVector2Array(' +
           ', '.join(f'{x}, {y}' for x, y in I['huellas'][0]) + ')\n') if meta['colision'] else ''
    with open(os.path.join(d, f'{nombre}_iso.tscn'), 'w') as f:
        f.write(ISO.format(n=nombre, N=N, huellas=a_godot(I['huellas']),
                           dirs=', '.join(json.dumps(x) for x in I['direcciones']),
                           ox=round(I['offset'][0] * I['escala'], 3), oy=round(I['offset'][1] * I['escala'], 3),
                           e=I['escala'], hf=I['hframes'], colision=col))
    for archivo in (L['imagen'], I['imagen']):
        imp = os.path.join(d, archivo + '.import')
        if not os.path.exists(imp):  # no pisar el que ya reescribió Godot (tiene uid)
            with open(imp, 'w') as f:
                f.write(IMPORT.format(n=nombre, archivo=archivo).replace('res://personajes/', 'res://objetos/'))
    print('[godot] exportado en', d)
