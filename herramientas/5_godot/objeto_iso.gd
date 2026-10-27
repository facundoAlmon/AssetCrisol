@tool
extends StaticBody2D

# Objeto isométrico de generador-personajes: Sprite2D con una celda por dirección y la huella en el piso
# como colisión. Cambiar `direccion` (también en el editor) gira el objeto. El origen = centro de la base
# (apto para y_sort).

## huella (polígono en el piso, en píxeles de pantalla) de cada dirección; lo completa el generador
@export var huellas: Array = []
@export var nombres_direcciones: PackedStringArray = []
@export var direccion := 0:
	set(v):
		direccion = v
		_aplicar()

func _ready() -> void:
	_aplicar()

func _aplicar() -> void:  # al cargar la escena el setter corre antes de que existan los hijos: get_node_or_null
	var sprite := get_node_or_null("Sprite") as Sprite2D
	if sprite:
		sprite.frame = posmod(direccion, sprite.hframes)
	var col := get_node_or_null("Colision") as CollisionPolygon2D
	if col and not huellas.is_empty():
		var pts := PackedVector2Array()
		for p in huellas[posmod(direccion, huellas.size())]:
			pts.append(Vector2(p[0], p[1]))
		col.polygon = pts
