# AssetCrisol

Guía para agentes (Claude Code u otros) que trabajen con este repo. `AGENTS.md` remite acá.

Pipeline local (sin APIs pagas) que convierte una imagen de referencia en assets de juego: ComfyUI (imagen limpia)
→ Pixal3D o TRELLIS.2 (malla texturizada, opcionalmente repintada con UltraTex) → Blender headless (rig, pesos,
animaciones, frames, retrato) → hoja de sprites → escena Godot. Extras: `iso` (8 direcciones isométricas,
SpriteFrames), objetos estáticos (mismos pasos 1-2, sin rig), vehículos (`.glb` con ruedas separadas) y kits de
escenario (texturas repetibles de piso/camino/pared, telón de fondo y colores del tema).

`README.md` es la documentación para el usuario (instalación, cada paso, `personaje.json`, problemas conocidos):
leerlo antes de cambios grandes y mantenerlo al día cuando cambie el comportamiento. Código, comentarios, mensajes
y docs van en español. Todo corre en la PC del usuario: no proponer servicios pagos ni APIs en la nube.

## Reglas

- **Una generación por vez en la GPU.** Antes de `imagen`, `vistas`, `malla`, `ultratex`, `articulaciones` o
  `texturas`, revisar:
  - `curl -s 127.0.0.1:8188/queue` (o la `comfyui_url` de la config): si `queue_running` o `queue_pending` no están
    vacías, ComfyUI está generando;
  - `nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv`: si aparece un python de TRELLIS.2,
    hay una malla en curso.

  Si la GPU está ocupada (aunque sea por otra sesión u otro programa), esperar a que termine en vez de lanzar el paso:
  con dos a la vez cada imagen pasa de ~20 s a varios minutos y la malla se queda sin VRAM. No cuentan: ComfyUI
  cargado con la cola vacía (`malla` lo libera con `POST /free`) ni Godot/Blender abiertos.
- **No elegir por el usuario**: `imagen.elegida` (mirando `trabajo/imagen/candidatos.png`), `malla.elegida` (mirando
  `trabajo/candidatos.png` o `revision.png`) y `texturas.<clave>.elegida` los decide el usuario. Mostrarle las
  hojas y preguntar.
- **Mirar los resultados visuales antes de darlos por buenos**: no dar por bueno un cambio visual sin abrir la imagen
  (extraer frames del GIF con PIL y leerlos). En humanoides nuevos, mostrar `trabajo/imagen/vistas.png` antes de la
  malla y `trabajo/revision.png` (`pipeline.py revisar`) antes de darlo por terminado.
- Los datos generados (`personajes/`, `objetos/`, `escenarios/`, `movimientos/candidatos/` dentro de `datos_dir`)
  **no se versionan**: no hacer `git add` de ellos ni sacarlos del `.gitignore`. `config.json` tampoco.
- No usar `pkill -f <patrón>` si el patrón puede coincidir con el shell que lo ejecuta (mata jobs en background):
  matar por PID. `pgrep -f <patrón>` dentro de un `until` se encuentra a sí mismo y no termina nunca.

## Correr

```bash
python3 pipeline.py <nuevo|imagen|vistas|malla|ultratex|guia|articulaciones|blender|sprites|retrato|iso|anclas|revisar|godot|todo> <n> [--referencia img] [--objeto|--vehiculo] [--instalar <proyecto>]
python3 pipeline.py comparar <n>                               # trabajo/candidatos.png de malla.candidatos
python3 pipeline.py <nuevo --escenario|texturas|tema> <n>     # escenarios
python3 pipeline.py rehacer <n1,n2,...|todos>                 # blender..revisar en lote (tras tocar rig/animaciones)
python3 pipeline.py metodo <n> [anim=kimodo|procedural ...]    # método de cada animación
python3 pipeline.py movimiento <anim> --prompt "..." [--duracion s] [--seed n]   # clips candidatos (Kimodo)
```

- Config: `config.json` junto a `pipeline.py` (copiado de `config.ejemplo.json`) o la ruta en `ASSETCRISOL_CONFIG`.
  `datos_dir` (relativo al archivo de config) dice dónde viven `personajes/`, `objetos/`, `escenarios/` y
  `movimientos/candidatos/`; `pipeline.py` lo resuelve en `DATOS`.
- `pipeline.py` corre con el **python3 del sistema** (necesita Pillow). Cada paso lanza su propia herramienta con su
  propio intérprete: ComfyUI (`<comfyui_dir>/venv/bin/python` y el CLI `comfy`), venv de TRELLIS.2 (Python 3.10;
  también para rembg), Blender (`-b --factory-startup`), Kimodo (`<kimodo_dir>/venv`), Godot (`--headless
  --import`). **No importar `bpy`/`torch` desde `pipeline.py`.**
- Duraciones: `imagen` ≈ 20 s por seed con referencia (+ arranque de ComfyUI; sin referencia, FLUX.2 Dev ≈ 3 min 20 s
  por seed y llena los 16 GB), `malla` ≈ 3-6 min (correr en background y esperar la notificación), `ultratex` ≈ 1-6
  min, `guia`/`blender` segundos a ~1 min, `iso` ≈ 25 s, `sprites`/`godot` instantáneo, `movimiento` ≈ 2,5 min (todo
  en CPU: no cuenta para la regla de la GPU).
- `<n>` se busca en `personajes/`, `objetos/` y `escenarios/` (`cargar()` pone `pj['_objeto']`/`pj['_escenario']`;
  un escenario solo admite `nuevo`/`texturas`/`tema`); cada `paso_*` despacha.
- **Estilo**: `cargar()` fusiona `estilos/<estilo>.json` sobre `estilos/animacion3d.json` en `pj['_estilo']` y
  completa las escalas en `null`; un bloque `render` en el json del personaje/objeto pisa al del estilo. `blender()`
  escribe esa config efectiva en `trabajo/_config.json`, que es lo que lee `blender_main.py` (no el json crudo). El
  prompt lo arma `generar_imagen.componer_prompt` desde `imagen.descripcion` (o `imagen.prompt` tal cual).
  `posproceso.aplicar` en cada `armar_*`.
- `render.oclusion` (`blender_main.oclusion`) y `posproceso.nitidez` son opcionales y solo actúan si el estilo las
  trae (`moderno_juguete`). La oclusión es un nodo Ambient Occlusion de EEVEE multiplicado sobre el color base, no
  un pase de render.
- Cada paso lee `<datos_dir>/personajes/<n>/personaje.json` y escribe en `.../<n>/trabajo/`; se puede re-correr
  cualquier paso aislado.
- Logs: `trabajo/malla/trellis2.log`, `trabajo/blender_<modo>.log`, `trabajo/imagen/comfyui.log`.
- **Humanoides nuevos**: seguir README > *Qué mirar en cada paso (receta para humanoides)* (plantilla = Pixal3D 4
  vistas + UltraTex `giro` 45 y `espalda`, `cabeza_arriba_grados` 0, estilo `semirealista`/`moderno`/`moderno_juguete`).

## Mapa del código

| archivo | intérprete | rol |
|---|---|---|
| `pipeline.py` | python3 sistema | CLI / orquestador, un `paso_*` por comando; config y `datos_dir` |
| `herramientas/1_imagen/generar_imagen.py` | python3 sistema | arma workflows con `comfy workflow apply <receta>` + `set-widget` de modelos, corre por seed, hoja de contacto |
| `herramientas/1_imagen/*.recipe.json` | — | recetas de ComfyUI (op-batches con `${param}`): `qwen_edit`, `flux2_t2i` |
| `herramientas/2_malla/generar_malla_pixal3d.py` | python3 sistema | `malla.motor = "pixal3d"`: workflow API de ComfyUI (Pixal3D 1 o 4 vistas, vistas extra con Qwen Edit), `sin_fondo.png`, GLB solo color base; modo `alinear` para objetos |
| `herramientas/2_malla/generar_malla_trellis.py` | venv TRELLIS.2 | `malla.motor = "trellis2"`: rembg → TRELLIS.2 (forma+color) → o-voxel (UV, horneado) → sin pedacitos sueltos; se relanza con `os.execv` tras un OOM |
| `herramientas/2_malla/retexturizar_ultratex.py` | python3 sistema | `malla.ultratex` / paso `ultratex`: `limpia.glb` + `sin_fondo.png` → 6 vistas FLUX.2 Klein (nodos UltraTex) → `modelo.glb` (motor en `modelo_motor.glb`); `espalda`/`costados`: 2 pasadas con las vistas de Qwen (rembg del venv de TRELLIS.2) |
| `herramientas/3_blender/blender_main.py` | Blender | modos `limpia`, `guia`, `construir` (lateral + retrato), `retrato`, `reves`, `comparar`, `iso`, `anclas` (sin render), `objeto`, `alinear`: escena, importación/normalización/soldado, `sacar_interior`, rig, render |
| `herramientas/3_blender/vehiculo.py` | Blender | modo `vehiculo`: largo, simetría, ruedas detectadas (originales separadas o armadas) → `trabajo/vehiculo.glb` (nodos `rueda_*`) + `revision.png` + `tarjeta.png` |
| `herramientas/3_blender/rig_lib.py` | Blender | `PLANTILLA` de articulaciones, estimación, construcción del rig, bone heat, pesos alternativos, `cortar_puentes` |
| `herramientas/3_blender/anim.py` | Blender | `TODAS`: idle, caminar, saltar (procedurales) + poses-dict (`_pose`/`_poses`, `piso=True` apoya midiendo la malla) |
| `herramientas/3_blender/metodos.py` | python3 sistema / Blender | método de cada animación (`procedural`/`kimodo`): recomendado de `movimientos/biblioteca.json`, pisado por `animacion.metodos` |
| `herramientas/3_blender/kimodo_clip.py` | Blender | clip de Kimodo (NPZ, SOMA 77) → Action del rig; `todas(a)` = `anim.TODAS` con las de Kimodo reemplazadas |
| `herramientas/3_blender/generar_movimiento.py` | venv Kimodo | paso `movimiento`: candidatos a `<datos_dir>/movimientos/candidatos/` + hoja de esqueletos |
| `herramientas/3_blender/articulaciones_pose.py` | python3 sistema | paso `articulaciones`: DWPose (ComfyUI) sobre los renders de `guia` → `modelo.articulaciones`, con validación anatómica |
| `herramientas/3_blender/dibujar_guia.py` | python3 sistema | grilla + esqueleto sobre los renders de `guia` |
| `herramientas/4_sprites/armar_tira.py` | python3 sistema | `ANIMACIONES` (orden de la hoja), grilla de 13 col., meta, `preview.gif`, retrato (recorte de `sin_fondo.png` con la caja de `retrato.json`) |
| `herramientas/4_sprites/revisar.py` | python3 sistema | paso `revisar`: hoja de control (cabeza, codos, caminata iso de frente/espalda, poses, revés) → `trabajo/revision.png` |
| `herramientas/4_sprites/armar_iso.py` | python3 sistema | hojas iso por animación (filas = 8 direcciones), meta, `preview_iso.gif` |
| `herramientas/4_sprites/armar_objeto.py` | python3 sistema | objeto: lateral + tira iso + huellas, `preview.png` |
| `herramientas/4_sprites/posproceso.py` | python3 sistema | color (sat/contraste/brillo/tinte) + nitidez + contorno del estilo |
| `herramientas/5_godot/exportar_godot.py` | python3 sistema | `.tscn`/`.import`/SpriteFrames iso, instala en un proyecto (recursivo) |
| `herramientas/5_godot/exportar_objeto.py` | python3 sistema | objeto: `_lateral.tscn` y `_iso.tscn` (StaticBody2D) |
| `herramientas/5_godot/sprite_personaje.gd` | Godot | visual genérico: `set_frame()`, `frame_de()`, retrato + sombra en runtime |
| `herramientas/5_godot/sprite_personaje_iso.gd` | Godot | visual iso: `set_animacion(nombre, vector)` + sombra |
| `herramientas/5_godot/objeto_iso.gd` | Godot | `@tool`: `direccion` cambia celda y huella |
| `herramientas/6_escenario/texturas.py` | python3 sistema | paso `texturas`: candidatas por textura (DreamShaper XL por API, IP-Adapter con referencia; o receta FLUX.2) |
| `herramientas/6_escenario/repetible.py` | python3 sistema | textura → repetible (media vuelta + parches sobre la cruz de costuras) |
| `herramientas/6_escenario/tema.py` | python3 sistema | paso `tema`: detalle normalizado (lineal, 0,5 = color del tema) + `tema.json` + preview |
| `estilos/*.json` | — | pautas visuales compartidas (prompt, luces, posproceso, escala); `animacion3d` = base completa |
| `plantilla/{personaje,objeto,vehiculo,escenario}.json` | — | valores por defecto de uno nuevo (vehículo: se fusiona sobre objeto) |

## Contratos (romperlos rompe el juego o los pasos siguientes)

- **Orden de la hoja** (`armar_tira.ANIMACIONES`): 0 idle, 1-8 caminata, 9 despegue, 10 subida, 11 cima, 12 caída;
  13+ las agregadas (idle_loop, run, roll, punch, kick, crouch, block, land, hurt, die, throw, arms_up, charge). Las
  celdas van seguidas, así que cambiar los cuadros de una corre los índices de las siguientes (el visual las busca
  por nombre: `frame_de`/`meta.json`). Animaciones nuevas: **al final** de `ANIMACIONES` (+ función en `anim.TODAS`,
  + `armar_iso.NOMBRES`) y actualizar el README. Grilla de 13 columnas (fila 0 = la tira original); índice = fila ×
  13 + col.
- **Iso**: direcciones `e,se,s,sw,w,nw,n,ne` (filas de las hojas y sufijo de las animaciones de SpriteFrames
  `<anim>_<dir>`); cámara 30°, `baldosa_px` = ancho de una baldosa de 1×1 unidad.
- **API del visual**: `set_frame(frame: int, flip_h: bool)` (+ `frame_de`, `retrato`, `frente`); el nodo es hijo
  directo del `CharacterBody2D` (el rayo de la sombra excluye al padre). El origen del nodo = los pies.
- **Nombres de huesos** (`rig_lib.PLANTILLA`) son los que usa `anim.py`. `.S` = lado +X, se espeja.
- **Orientación**: modelo con frente = -Y, pies en z=0, alto `modelo.altura`; en el render el rig rota 90° en Z para
  mirar a la derecha (+X) y la cámara está a nivel (sin inclinación).
- **Salida para Godot**: `personajes/<n>/godot/personajes/{_comun,<n>}/` replica `res://personajes/...`.
  `--instalar` copia ahí y conserva `.import` existentes (uid estable). Lo instalado en un proyecto no se edita a
  mano: se regenera. No instalar en ningún proyecto sin que el usuario lo pida y diga dónde.
- **Sombra**: nunca en los sprites (subiría con el salto); la dibuja `sprite_personaje.gd`.
- **Escala**: la tira se renderiza `sprites.superresolucion`× y el Sprite2D se escala 1/N con filtro lineal +
  mipmaps (`texture_filter = 4`, `mipmaps/generate=true`).
- **Vehículos**: `vehiculo.glb` con nodos `carroceria`, `rueda_di/dd/ti/td` (origen en el eje), trompa en +Z del glTF.

## Gotchas del motor (no redescubrir)

### TRELLIS.2
- ~3 min en 16 GB con `low_vram`. Necesita `transformers==4.57.1` (con 5.x: `DINOv3ViTModel has no attribute
  'layer'`); DINOv3 es gated en Hugging Face.
- La malla sale en cientos de piezas: se sacan las < 100 caras y `rig_lib.pesos_de_piezas_sueltas` le da a las que
  quedan (ojos, cartucheras) los pesos del cuerpo; sin eso el bone heat falla o quedan flotando. En objetos solo
  migas < 10 caras y como mucho el 10 % de las caras (un arbusto son miles de hojas). La pieza más grande nunca se saca.
- **Capas escondidas**: la malla trae el cuerpo entero bajo la ropa + la cara interior de la ropa (1/2 a 3/4 de las
  caras); con otros pesos atraviesan la de afuera al animar (manchas oscuras en Workbench, "volados", "agujeros";
  en reposo no se ve). `blender_main.sacar_interior` borra las caras desde las que ningún rayo sale (17 rayos, hasta
  75°) y después los pedacitos < 100 caras (si no, bone heat falla); `rig_lib.suavizar_pesos_espacial` promedia por
  distancia (3 cm). Para diagnosticar: render con `show_backface_culling` (las manchas son revés). Probar poses
  (golpe, patada), no solo la caminata. `sacar_interior` agujerea mallas de pocas caras (un cofre de 4 k).
- El glTF viene partido en las costuras UV → `blender_main.importar()` suelda (`remove_doubles` 1e-5; el UV es por
  loop, se conserva); sin soldar, el bone heat falla con todo sin peso.
- VRAM: un objeto macizo a 1024 no entra (el decoder de textura pide >16 GB). `max_num_tokens` no sirve: la cascada
  nunca baja de 1024. Tras un OOM la memoria no se libera en el mismo proceso (CuMesh): el script se relanza con
  `os.execv` a la resolución de abajo, o sin remesh si falló `to_glb` (plumas → 28 M caras tras el remesh). Objetos
  a 512 por defecto. CuMesh avisa la falta de VRAM con `RuntimeError`, no `torch.OutOfMemoryError`: mirar
  `'out of memory' in str(e)`. A 1536 el remesh no entra: se simplifica la cruda a 4 M y se hace el remesh a 1280
  (`TRELLIS_RES_REMESH`).
- **La seed pesa mucho** en casos difíciles (una cara perdida dentro de un casco de vidrio con una seed, perfecta con
  otra): probar 2-3 seeds antes de tocar código. El color base es sRGB (el renderer de TRELLIS lo eleva a 2.2), no
  lineal: si sale oscuro es la predicción. `alfa_min` para sombras semitransparentes de rembg (TRELLIS las vuelve
  telas). `TRELLIS_CRUDO=1` guarda `modelo_crudo.glb` con metal/rugosidad para diagnosticar.
- Orientación y escala: frente -Y en Blender, no hay que girar nada. Los objetos salen derechos.
- **Caras chicas**: en una imagen de cuerpo entero con proporciones reales la cara ocupa ~50 px y TRELLIS la
  redondea y pinta ojos y boca como manchas; otra seed no lo arregla. Pixal3D + UltraTex lo resuelven.
- **Ojos agujereados**: el cráter del ojo puede quedar todo "interior" y `sacar_interior` lo borra (se ve el gris de
  adentro de la cabeza; pintar no sirve). `modelo.ojos` (`blender_main.parche_ojos`) pone discos con un ojo dibujado
  y tapa con piel los agujeros de alrededor. Lo que se toque solo en `<n>.blend` se pierde: todos los modos de
  Blender rearman desde `modelo.glb`.

### Pixal3D
- Mejor que TRELLIS.2 en caras, estampados y luces/emblemas. Corre en ComfyUI: cuenta para la regla de la GPU.
- Con `vistas: true`, las vistas de Qwen pueden copiar a la espalda lo del pecho (una luz en el pecho de un
  superhéroe con armadura): mirar `trabajo/imagen/vista_*.png` antes de la malla. Pueden salir con el costado al
  revés (`left` mira al borde izquierdo de la imagen): espejar.
- El GLB de ComfyUI trae mapas de normal/AO/metal: se deja solo el color base (si no, Blender ignora la rugosidad del
  estilo). La plantilla oficial no valida tal cual (`target_resolution` int, cargador de TRELLIS.2 sin modelo): por eso
  el workflow se arma en Python. Con `resolucion` 512 ComfyUI no corre la malla y falla el `glob` del GLB: 1024/1536.
- Con 4 vistas el color es malo (cambia de tono según la seed): repintar con UltraTex.
- Objetos de una vista vienen en el marco de la cámara: el paso malla los endereza en el GLB (modo `alinear`). En un
  auto en tres cuartos desde arriba salieron astillas: ahí TRELLIS.2 (+ UltraTex) anduvo mucho mejor. Con follaje no
  entra en 16 GB. Con pocas caras (5000) sale astillado: los candidatos heredan `caras`.
- La cara sale derecha: `cabeza_arriba_grados` 0 (con -15 mira al cielo en todas las poses).

### UltraTex
- La mejor textura para humanoides (sobre la forma de Pixal3D 4 vistas). ~40 s de muestreo; cuenta para la regla de
  la GPU. Solo mira `sin_fondo.png`: sin `espalda` la inventa y copia lo del pecho (un logo, un emblema, una
  mochila de otro color). Mientras corre, `modelo.glb` es la malla del motor: no sacar conclusiones de una `guia`
  hecha en ese momento.
- Ojos achinados en la imagen elegida (sonrisa): editarla con Qwen como `base_<seed>.png` ("only change the eyes").

### Rig y pesos
- **Rodillas**: el `pole_angle` del IK de la pierna no es -90° fijo: `rig_lib.angulo_polo` lo calibra doblando la
  pierna y probando ángulos (la fórmula clásica daba -73° donde hacía falta -30°). Antes, `rig_lib.rodilla_en_linea`
  lleva la rodilla (y su polo) al plano vertical cadera-tobillo: con la rodilla a un costado el plano de doblez
  queda en diagonal y forzarla adelante gira la canilla hacia adentro.
- **Codos "de plastilina"**: no eran los pesos sino la mezcla lineal del Armature a 110-135°:
  `use_deform_preserve_volume` (cuaterniones duales, `modelo.preservar_volumen`) marca el codo y conserva el grosor.
- **Pesos que fallan**: el bone heat da basura en chibis de cuerpo redondo (`modelo.pesos: "distancia"`), mezcla
  bloques de robot en C (`modelo.pesos_rigidos`) y le da a una pieza cercana a la mano el peso del antebrazo aunque no
  la toque (`modelo.pesos_zonas`, cajas → hueso). Las piezas sueltas copian el vértice más cercano salvo que no cuadre
  con los huesos (pies de un pájaro con peso del ala). Diagnóstico: render coloreado por hueso dominante en reposo y en
  poses (throw, arms_up, kick). Las articulaciones `.S` espejadas pueden dejar un brazo sin hueso en modelos
  asimétricos (un robot con un cañón en un brazo): lado suelto `upper_arm.R` etc. `cortar_puentes` corta y tapa caras
  que unen partes a ≥4 huesos (los dos zapatos, mano-cadera), y solo tapa agujeros chicos (< 12 cm): tapar uno grande
  armaba una lámina.
- Descartado (no reintentar): filtros automáticos de "hueso implausible" o por visibilidad (doble cáscara: marcan
  miles de vértices buenos), devolver al cuerpo lo que la mano tiene lejos (arranca tiras del guante, rompe túnicas) e
  híbridos bone heat + distancia (los brazos de los chibis quedan como aletas). Chibis con los brazos fundidos al
  cuerpo no tienen arreglo de pesos: regenerar con brazos separados.
- `factor_pierna` (`blender_main` → `anim._pose`) achica bajada de cadera e inclinación de pecho/cabeza en chibis
  (pierna < 0,9 de la plantilla).
- `modelo.normales: true` solo cuando la fila de revés de `revisar` muestra caras de afuera borradas (cabeza o pecho
  que faltan); en otros modelos suma manchas. `modelo.simetria` y `render.oscuro_brillante` son opcionales y dudosos.
- La estimación de articulaciones por rebanadas (`rig_lib`) falla en cuerpos chibi/cabezones o de torso ancho: usar
  `pipeline.py articulaciones` (DWPose); con muñecos/juguetes DWPose tampoco anda (la validación descarta los puntos)
  y hay que cargarlas a mano mirando `guia.png`.

### Animación
- Brazos (`anim._brazo`): se giran en ejes del cuerpo (apertura en el plano frontal, balanceo alrededor del eje
  lateral), no en los del hueso: en pose A el hueso está a ~23° y el balanceo hacía un cono (alas al correr).
  `anim.cierre_brazos` cierra lo que deja el hueco brazo-torso.
- Pies: `tobillo_*` es respecto de la canilla (el control IK copia la rotación absoluta) y `talon_*` gira sobre la
  punta; medir el tobillo tras cambiar poses (rango natural ~ -30..+50).
- `cabeza_arriba_grados`: **negativo = levantar la cara**. TRELLIS.2 deja la cara gacha (0 a -15); Pixal3D, derecha
  (0). Probar por personaje renderizando el idle con 2-3 valores y mirando.
- Blender 5: las Actions son por capas/slots (`act.layers[].strips[].channelbags[].fcurves`); `anim._fcurves()` cubre
  ambos casos. Buscar nodos por `type`, no por nombre.

### Kimodo
- El codificador de texto es LLM2Vec sobre Llama-3-8B-Instruct (gated en HF; sirve un espejo con los
  `adapter_config.json` apuntados a esa carpeta). Los avisos `MISSING` del LoRA al cargar son normales.
- En el NPZ, `foot_contacts` está mal (el canal del talón derecho repite al de la punta izquierda): el ciclo se
  detecta con la altura del tobillo.
- Ejes: y arriba, +z adelante, +x = izquierda; `global_rot_mats` es relativa a la T-pose. Al traducir, alinear la
  dirección de reposo **solo en los brazos** (T-pose vs pose A) y en muslo/canilla (piernas verticales; sin eso de
  frente los pies iban muy separados); en cabeza/torso/pies suma la diferencia de anatomía (la cara subía 33°).
- Rotaciones del clip al rig: `R @ G @ M.T` (con `R @ G @ R.T` el giro de la cadera quedaba: cuerpo girado ~5°, un
  pie hacia adentro). En los ciclos Kimodo trae la cara 18-24° arriba: `kimodo_clip` la nivela sola.
- Kimodo gana en movimientos de cuerpo entero (caminar, morir) y pierde en golpes (rápidos, sin exagerar, mano
  abierta): elegir por animación, no reemplazar todo. Medir con el rig (huesos por cuadro en la Action del
  `.blend`), no a ojo.

### Vehículos
- La malla sale de la **cola** en tres cuartos desde arriba (Qwen, `malla.vista: "atras"`): el modelo inventa lo que
  no ve, y en una carrera la cola es lo que se ve. Pixal3D con dos tres cuartos (cola + frente) da fantasmas:
  necesita cámaras consistentes (descartado).
- Ruedas: rayos desde abajo; por defecto las originales separadas en su nodo (las armadas salían borrosas), con un
  disco oscuro adentro y el pasarrueda cerrado (si no, se ve a través). Para buscar agujeros: render Workbench con
  `show_backface_culling` y fondo verde (con magenta el violeta no se distingue).

### Imagen y escenarios
- Las recetas de ComfyUI dejan los loaders en el primer valor del combo: por eso `generar_imagen.py` fija los
  nombres de modelo (de `config.json > modelos_imagen`).
- Con referencia foto + prompt de dibujo: pedir "3D ... no outlines, not a 2D drawing" o Qwen devuelve una
  ilustración plana con contorno (mala para la malla).
- El modelo 3D inventa el costado y la espalda; la calidad lateral depende de la imagen frontal.
- **Vegetación**: hojitas sueltas dan cáscaras con agujeros (a 512 cada hoja es menos de un vóxel); pedir masas lisas
  ("big smooth puffy rounded foliage clumps, no individual leaves, solid silhouette, toy-like" + negativo "many
  leaves, moss, fuzzy texture", `malla.fondo` `birefnet-general`, TRELLIS.2 a 512). Esas superficies salen con ~50 M
  de caras crudas: `fill_holes` vacía la caché antes y el pipeline se libera antes de `simplify`.
- Escenarios: el detalle se guarda **relativo al promedio en lineal** y el juego multiplica color × detalle × 2; con
  contraste 1 y detalle fino el piso se ve como ruido desde la cámara iso (por eso `contraste` 0,5, `repeticion_m` 6
  y "large simple shapes" en el prompt). Qwen-Edit no saca texturas de una imagen de escenario (conserva la
  composición); IP-Adapter style transfer sí, mejor con `recorte`.
- Imágenes RGBA: comparar canal por canal; `getbbox()` de una diferencia RGBA solo mira el alfa y da `None` aunque el
  color cambie.

### Entorno
- VRAM 16 GB: ComfyUI con Qwen cargado ocupa ~12 GB. `paso_malla` hace `POST /free` a ComfyUI.
- Las cachés de modelos van a donde diga `config.json > env_modelos`, no a `~/.cache` (suele llenar el disco del
  sistema).

## Verificar cambios

- Personaje de referencia: el de ejemplo (`cris`, ver `ejemplos/` cuando esté). Objeto de referencia: `caja`.
- Cambios en Blender/animación: `python3 pipeline.py blender cris && python3 pipeline.py sprites cris` y **mirar**
  `personajes/cris/preview.gif` (extraer frames con PIL y leer la imagen). Para ver celdas sueltas, recortar la hoja
  con `meta.json` (`frame_width/height`, 13 columnas). Iso: `pipeline.py iso cris` → `preview_iso.gif`. Revisar
  también `iso`, no solo la vista lateral, y poses (golpe, patada, brazos arriba), no solo la caminata.
- Objetos: `pipeline.py blender caja && pipeline.py sprites caja` → `preview.png`.
- Articulaciones: `pipeline.py guia <n>` y mirar `trabajo/guia/guia.png`.
- Tras cambiar rig o animaciones: `pipeline.py rehacer <n1,n2,...>` y mirar cada `trabajo/revision.png`.
- Godot: proyecto vacío en un directorio temporal (`project.godot` mínimo), `godot <n> --instalar <ese dir>` y un
  `-s script.gd` headless que instancie y haga `print`.
- Para probar sin gastar los minutos de malla: crear un personaje temporal copiando `personaje.json` y un
  `trabajo/malla/modelo.glb` existente, y borrarlo al terminar.
