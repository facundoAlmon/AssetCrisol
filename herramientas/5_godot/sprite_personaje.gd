extends Node2D

# Visual de un personaje generado con generador-personajes (render 3D -> hoja de sprites en grilla).
# Mira a la derecha; frames: 0 quieto, 1-8 caminata, 9 despegue, 10 subida, 11 cima, 12 caída, y desde el 13
# las animaciones agregadas después (ver `animaciones` o <nombre>_meta.json).
# La hoja viene en superresolución y el Sprite se escala (ver <nombre>_visual.tscn).
# La sombra no viene en los sprites: se dibuja acá, pegada al piso que haya debajo (rayo hacia abajo).
# API usada por el player: set_frame(frame, flip_h). Por nombre: frame_de(animacion, tiempo).

## animación -> {frames: [índices], fps, loop} (lo completa el generador)
@export var animaciones: Dictionary = {}
## para la pantalla de selección: cabeza y hombros de frente / cuerpo entero de frente
@export var retrato: Texture2D
@export var frente: Texture2D

@export var shadow_radius := Vector2(40.0, 9.0)
@export_range(0.0, 1.0) var shadow_alpha := 0.4
@export var shadow_fade_height := 260.0  # a esta altura sobre el piso la sombra desaparece
@export var shadow_ray_length := 600.0

@onready var sprite: Sprite2D = $Sprite

var _shadow_y := 0.0      # distancia (local) hasta el piso; 0 = parado
var _shadow_k := 1.0      # 1 = sombra completa, 0 = invisible

func set_frame(frame: int, flip_h: bool) -> void:
	sprite.frame = frame
	sprite.flip_h = flip_h

# Frame de `animacion` a los `tiempo` segundos de empezada (las que no hacen loop quedan en el último).
func frame_de(animacion: String, tiempo: float) -> int:
	var a: Dictionary = animaciones.get(animacion, animaciones.get("idle", {"frames": [0], "fps": 1}))
	var frames: Array = a["frames"]
	var i := int(tiempo * float(a["fps"]))
	i = i % frames.size() if a.get("loop", false) else mini(i, frames.size() - 1)
	return frames[i]

func duracion(animacion: String) -> float:
	var a: Dictionary = animaciones.get(animacion, {"frames": [0], "fps": 1})
	return float(a["frames"].size()) / float(a["fps"])

func _physics_process(_delta: float) -> void:
	var from := global_position + Vector2(0, -2)
	var query := PhysicsRayQueryParameters2D.create(from, from + Vector2(0, shadow_ray_length))
	var body := get_parent() as CollisionObject2D
	if body:
		query.exclude = [body.get_rid()]
	var hit := get_world_2d().direct_space_state.intersect_ray(query)
	if hit.is_empty():
		_shadow_k = 0.0  # sobre un pozo: no hay piso donde proyectar
	else:
		var height: float = hit.position.y - global_position.y
		_shadow_y = height / global_scale.y
		_shadow_k = clampf(1.0 - height / shadow_fade_height, 0.0, 1.0)
	queue_redraw()

func _draw() -> void:
	if _shadow_k <= 0.01:
		return
	# elipse suave: discos concéntricos semitransparentes, achicados con la altura
	var size := 0.55 + 0.45 * _shadow_k
	draw_set_transform(Vector2(0, _shadow_y), 0.0, shadow_radius * size)
	const STEPS := 6
	for i in STEPS:
		var r := 1.0 - float(i) / STEPS * 0.6
		draw_circle(Vector2.ZERO, r, Color(0, 0, 0, shadow_alpha * _shadow_k / STEPS * 1.6))
	draw_set_transform(Vector2.ZERO)
