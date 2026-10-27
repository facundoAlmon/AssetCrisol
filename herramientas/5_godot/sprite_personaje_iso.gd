extends Node2D

# Visual isométrico (2:1) de un personaje de generador-personajes: AnimatedSprite2D con una animación
# por acción y dirección ("walk_se", "idle_n", ...; ver <nombre>_iso_frames.tres). El origen = los pies.
# La sombra no viene en los sprites: se dibuja acá como una elipse en el piso.
# API: set_animacion(nombre, direccion) — direccion es un vector en pantalla (p. ej. la velocidad);
# Vector2.ZERO conserva la dirección anterior.

const DIRECCIONES := ["e", "se", "s", "sw", "w", "nw", "n", "ne"]  # sentido horario desde la derecha

@export var shadow_radius := Vector2(30.0, 13.0)
@export_range(0.0, 1.0) var shadow_alpha := 0.35
@export var direccion_inicial := "s"

@onready var sprite: AnimatedSprite2D = $Sprite

var direccion := "s"
var animacion := "idle"

func _ready() -> void:
	direccion = direccion_inicial
	set_animacion("idle")

# Vector en pantalla -> una de las 8 direcciones. Deshace el aplastamiento 2:1 del piso: un movimiento
# a lo largo del borde de una baldosa (2, 1) cuenta como diagonal (sureste).
static func direccion_de(v: Vector2) -> String:
	var a := Vector2(v.x, v.y * 2.0).angle()
	return DIRECCIONES[posmod(roundi(a / (PI / 4.0)), 8)]

func set_animacion(nombre: String, dir := Vector2.ZERO) -> void:
	if dir != Vector2.ZERO:
		direccion = direccion_de(dir)
	var clave := "%s_%s" % [nombre, direccion]
	if sprite == null:  # llamado antes de _ready
		sprite = $Sprite
	if not sprite.sprite_frames.has_animation(clave):
		return
	if sprite.animation != clave:
		var cuadro := sprite.frame
		var seguir := nombre == animacion  # mismo ciclo, otra dirección: no reiniciar
		sprite.play(clave)
		if seguir:
			sprite.frame = cuadro
	animacion = nombre

func _draw() -> void:
	const STEPS := 6
	for i in STEPS:
		var r := 1.0 - float(i) / STEPS * 0.6
		draw_set_transform(Vector2.ZERO, 0.0, shadow_radius * r)
		draw_circle(Vector2.ZERO, 1.0, Color(0, 0, 0, shadow_alpha / STEPS * 1.6))
	draw_set_transform(Vector2.ZERO)
