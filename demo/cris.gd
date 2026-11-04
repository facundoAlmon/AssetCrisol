extends CharacterBody2D

# Cris: se mueve en pantalla con flechas o WASD y le pasa al visual de AssetCrisol (cris_iso.tscn) la animación y la
# dirección con set_animacion(nombre, velocidad). Las acciones (golpe, patada, salto, brazos arriba) se reproducen una
# vez y vuelven al reposo.

const CAMINAR := 150.0     # px/s
const CORRER := 300.0
const ACCIONES := {"golpe": "punch", "patada": "kick", "saltar": "jump", "brazos_arriba": "arms_up"}

var limites := Rect2()     # el piso en metros (u, v): no se sale
var visual: Node2D
var accion := ""


func _ready() -> void:
	visual = load("res://personajes/cris/iso/cris_iso.tscn").instantiate()
	add_child(visual)
	var forma := CollisionShape2D.new()
	var circulo := CircleShape2D.new()
	circulo.radius = 14.0
	forma.shape = circulo
	forma.scale = Vector2(1.0, 0.5)   # una elipse en el piso, como la huella de los objetos
	add_child(forma)
	visual.get_node("Sprite").animation_finished.connect(_termino)


func _termino() -> void:
	accion = ""


func _physics_process(_delta: float) -> void:
	if accion != "":
		velocity = Vector2.ZERO
		return
	for a in ACCIONES:
		if Input.is_action_just_pressed(a):
			accion = ACCIONES[a]
			visual.set_animacion(accion)
			return
	var dir := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	dir += Vector2(float(Input.is_physical_key_pressed(KEY_D)) - float(Input.is_physical_key_pressed(KEY_A)),
		float(Input.is_physical_key_pressed(KEY_S)) - float(Input.is_physical_key_pressed(KEY_W)))
	dir = dir.limit_length(1.0)
	dir.y *= 0.5   # en el piso iso, arriba/abajo recorre la mitad de píxeles que izquierda/derecha
	var corre := Input.is_action_pressed("correr")
	velocity = dir * (CORRER if corre else CAMINAR)
	move_and_slide()
	var m: Vector2 = get_parent().get_parent().de_iso(position)
	if limites.size != Vector2.ZERO:
		m = m.clamp(limites.position, limites.end)
		position = get_parent().get_parent().iso(m)
	if velocity.length() < 1.0:
		visual.set_animacion("idle_loop")
	else:
		visual.set_animacion("run" if corre else "walk", velocity)
