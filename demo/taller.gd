extends Node2D

# El taller de Cris: piso y paredes con las texturas del tema `taller`, sus objetos y Cris, en isométrico.
# Todo sale de AssetCrisol (ver README.md de esta carpeta); esta escena solo lo acomoda. 1 unidad = 1 metro y una
# baldosa de 1×1 mide BALDOSA_PX de ancho en pantalla (la `baldosa_px` del estilo: 128).

const BALDOSA_PX := 128.0
const ANCHO := 10.0          # metros del piso a lo largo de u (de izquierda-arriba a derecha-abajo)
const FONDO := 8.0           # metros a lo largo de v
const ALTO_PARED := 1.6      # metros
const PX_POR_METRO_ALTO := 78.0   # en pantalla, de pie (cámara a 30°: Cris de 1,85 m mide ~145 px)
const TEMA := "res://escenarios/taller/"
const OBJETOS := {           # nombre: posición en metros (u, v) y dirección (0..3)
	"horno": [Vector2(1.4, 1.6), 1],
	"yunque": [Vector2(4.2, 2.6), 0],
	"crisol": [Vector2(2.3, 4.4), 0],
	"caja_herramientas": [Vector2(7.6, 1.3), 1],
	"martillo": [Vector2(5.3, 2.2), 0],
}

var tema := {}


# metros en el piso -> píxeles en pantalla (u hacia abajo-derecha, v hacia abajo-izquierda)
static func iso(p: Vector2) -> Vector2:
	return Vector2((p.x - p.y) * BALDOSA_PX / 2.0, (p.x + p.y) * BALDOSA_PX / 4.0)


static func de_iso(s: Vector2) -> Vector2:
	var a := s.x / (BALDOSA_PX / 2.0)
	var b := s.y / (BALDOSA_PX / 4.0)
	return Vector2((a + b) / 2.0, (b - a) / 2.0)


func _ready() -> void:
	var faltan := []
	for r in [TEMA + "tema.json", "res://personajes/cris/iso/cris_iso.tscn"]:
		if not ResourceLoader.exists(r) and not FileAccess.file_exists(r):
			faltan.append(r)
	if not faltan.is_empty():
		_aviso("Faltan los assets de AssetCrisol (%s).\nCorré ./preparar.sh en esta carpeta (README.md).\n\nMissing the AssetCrisol assets: run ./preparar.sh in this folder." % ", ".join(faltan))
		return
	tema = JSON.parse_string(FileAccess.get_file_as_string(TEMA + "tema.json"))
	_piso()
	_paredes()
	var mundo := Node2D.new()
	mundo.name = "Mundo"
	mundo.y_sort_enabled = true   # objetos y Cris se tapan según quién está más adelante (origen = la base)
	add_child(mundo)
	for n in OBJETOS:
		var ruta := "res://objetos/%s/%s_iso.tscn" % [n, n]
		if not ResourceLoader.exists(ruta):
			push_warning("falta %s (preparar.sh)" % ruta)
			continue
		var o: Node2D = load(ruta).instantiate()
		o.position = iso(OBJETOS[n][0])
		o.set("direccion", OBJETOS[n][1])
		mundo.add_child(o)
	var cris: CharacterBody2D = preload("res://cris.gd").new()
	cris.name = "Cris"
	cris.position = iso(Vector2(5.5, 5.5))
	cris.limites = Rect2(0.35, 0.35, ANCHO - 0.7, FONDO - 0.7)
	mundo.add_child(cris)
	var cam := Camera2D.new()
	cam.position_smoothing_enabled = true
	cris.add_child(cam)
	_ayuda()


# Un polígono con la textura de detalle del tema: el shader hace color del tema × detalle × 2 (en lineal), como un
# juego. uv en píxeles de la textura: `repeticion_m` metros por repetición.
func _poligono(puntos: PackedVector2Array, uv_m: PackedVector2Array, textura: String, color: String, luz := 1.0) -> void:
	var p := Polygon2D.new()
	p.polygon = puntos
	# como imagen y no con load(): preparar.sh copia el tema sin pasar por el importador de Godot
	var tex := ImageTexture.create_from_image(Image.load_from_file(TEMA + textura))
	p.texture = tex
	var px_por_m := tex.get_width() / float(tema.get("repeticion_m", 6.0))
	var uv := PackedVector2Array()
	for m in uv_m:
		uv.append(m * px_por_m)
	p.uv = uv
	p.texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED
	var mat := ShaderMaterial.new()
	mat.shader = preload("res://detalle.gdshader")
	mat.set_shader_parameter("tinte", Color.html(color))
	mat.set_shader_parameter("luz", luz)
	p.material = mat
	add_child(p)


func _piso() -> void:
	var t: Dictionary = tema["texturas"]
	var esquinas := [Vector2(0, 0), Vector2(ANCHO, 0), Vector2(ANCHO, FONDO), Vector2(0, FONDO)]
	var pts := PackedVector2Array()
	for e in esquinas:
		pts.append(iso(e))
	_poligono(pts, PackedVector2Array(esquinas), t["floor_detail"], tema["floor_color"])
	# una alfombra de camino desde la puerta (abajo) hasta el yunque
	var cam := [Vector2(3.6, 3.4), Vector2(4.8, 3.4), Vector2(4.8, FONDO), Vector2(3.6, FONDO)]
	pts = PackedVector2Array()
	for e in cam:
		pts.append(iso(e))
	_poligono(pts, PackedVector2Array(cam), t["path_detail"], tema["path_color"])


func _paredes() -> void:
	var t: Dictionary = tema["texturas"]
	var h := Vector2(0, -ALTO_PARED * PX_POR_METRO_ALTO)
	# pared de atrás a la derecha (v = 0) y de atrás a la izquierda (u = 0), un poco más oscura
	for pared in [[Vector2(0, 0), Vector2(ANCHO, 0), 1.0], [Vector2(0, FONDO), Vector2(0, 0), 0.8]]:
		var a: Vector2 = pared[0]
		var b: Vector2 = pared[1]
		var largo := a.distance_to(b)
		var pts := PackedVector2Array([iso(a) + h, iso(b) + h, iso(b), iso(a)])
		var uv := PackedVector2Array([Vector2(0, 0), Vector2(largo, 0), Vector2(largo, ALTO_PARED), Vector2(0, ALTO_PARED)])
		_poligono(pts, uv, t["wall_detail"], tema["wall_color"], pared[2])


func _aviso(texto: String) -> void:
	var capa := CanvasLayer.new()
	var l := Label.new()
	l.text = texto
	l.position = Vector2(40, 40)
	capa.add_child(l)
	add_child(capa)


func _ayuda() -> void:
	_aviso("Flechas o WASD: caminar · Shift: correr · J: golpe · K: patada · L: brazos arriba · Espacio: salto\n"
		+ "Arrows or WASD: walk · Shift: run · J: punch · K: kick · L: arms up · Space: jump")
