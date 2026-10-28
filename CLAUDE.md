# AssetCrisol

Guía para agentes (Claude Code u otros; `AGENTS.md` remite acá). Pipeline local que convierte una imagen de
referencia en assets de juego: ComfyUI (imagen) → Pixal3D o TRELLIS.2 (malla, repintada con UltraTex) → Blender
headless (rig, pesos, animaciones, render) → hojas de sprites e iso → Godot. También objetos sin rig, vehículos y
kits de escenario. `README.md` es la doc de usuario (instalación, cada paso, opciones de `personaje.json`): leerlo
antes de cambios grandes y actualizarlo cuando cambie el comportamiento. Código, comentarios y docs en español. Todo
corre local: no proponer servicios pagos ni APIs en la nube.

## Reglas

- **Una generación por vez en la GPU** (aunque la otra sea de otra sesión u otro programa). Antes de `imagen`,
  `vistas`, `malla`, `ultratex`, `articulaciones` o `texturas`:
  `curl -s 127.0.0.1:8188/queue` (o `comfyui_url`): `queue_running`/`queue_pending` no vacías = ocupada;
  `nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv`: un python de TRELLIS.2 = malla en curso.
  Si está ocupada, esperar. No cuentan ComfyUI con la cola vacía ni Godot/Blender abiertos.
- **No elegir por el usuario** `imagen.elegida`, `malla.elegida` ni `texturas.<clave>.elegida`: mostrarle la hoja
  (`trabajo/imagen/candidatos.png`, `trabajo/candidatos.png`, `revision.png`) y preguntar.
- **Mirar antes de dar por bueno** un resultado visual (frames del GIF con PIL). En humanoides nuevos, mostrar
  `trabajo/imagen/vistas.png` antes de la malla y `trabajo/revision.png` antes de darlo por terminado.
- No versionar datos generados (`personajes/`, `objetos/`, `escenarios/`, `movimientos/` de `datos_dir`) ni
  `config.json`; no sacarlos del `.gitignore`.
- Matar procesos por PID: `pkill -f <patrón>` puede matar al propio shell y `pgrep -f` en un `until` se encuentra a
  sí mismo y no termina.

## Correr

```bash
crisol <nuevo|imagen|vistas|malla|ultratex|guia|articulaciones|blender|sprites|retrato|iso|anclas|revisar|godot|todo> <n> [--referencia img] [--objeto|--vehiculo] [--instalar <proyecto>]
crisol estado [<n>] [--json]                        # qué está hecho, qué quedó viejo, qué falta elegir
crisol comparar <n>                                 # trabajo/candidatos.png de malla.candidatos
crisol <nuevo --escenario|texturas|tema> <n>
crisol rehacer <n1,n2,...|todos>                    # blender..revisar en lote
crisol metodo <n> [anim=kimodo|procedural ...]
crisol movimiento <anim> --prompt "..." [--duracion s] [--seed n]   # clips Kimodo (CPU)
```

- `crisol` (raíz del repo) importa `pipeline` y llama `main()`: es lo mismo que `python3 pipeline.py`; si no está
  en el PATH, `./crisol`. Los mensajes al usuario nombran `crisol <paso>`.
- Config: `config.json` junto a `pipeline.py` (de `config.ejemplo.json`) o `ASSETCRISOL_CONFIG`. `datos_dir`
  (relativo a la config) → `DATOS`, donde viven `personajes/`, `objetos/`, `escenarios/`. `<n>` se busca en los tres.
- `pipeline.py` corre con el python3 del sistema (Pillow); cada paso lanza su herramienta con su intérprete (venv de
  ComfyUI, de TRELLIS.2 —también rembg—, de Kimodo; Blender `-b --factory-startup`; Godot `--headless`).
  **No importar `bpy`/`torch` desde `pipeline.py`.**
- Duraciones: `imagen` ~20 s/seed (con referencia Qwen Image Edit; sin referencia Z-Image Turbo, el `imagen.motor`
  por defecto si la config tiene `modelos_imagen.zimage_unet`; con `motor: "flux2"`, FLUX.2 Dev ~3,5 min y llena
  16 GB), `malla` 3-6
  min y `ultratex` 1-6 min (en background, esperar la notificación), `blender` segundos a 1 min, `iso` ~25 s.
- Cada paso lee `<datos_dir>/<tipo>/<n>/personaje.json` y escribe en `<n>/trabajo/`; se puede re-correr aislado.
  Logs: `trabajo/malla/trellis2.log`, `trabajo/blender_<modo>.log`, `trabajo/imagen/comfyui.log`.
- **Estilo**: su `prompt` define la imagen (`generar_imagen.componer_prompt` desde `imagen.descripcion`; con
  `imagen.descripcion` presente, `imagen.prompt` se ignora) y su `render` solo Blender. `moderno` y `moderno_juguete`
  tienen el mismo prompt (cambiar entre ellos = rehacer `blender`/`sprites`/`iso`, no la imagen); `semirealista`
  cambia el prompt y comparte el render de `moderno`. `cargar()` fusiona `estilos/<estilo>.json` sobre `animacion3d.json` (base) en
  `pj['_estilo']`; un bloque `render` del json pisa al del estilo. `blender()` escribe la config efectiva en
  `trabajo/_config.json`, que es lo que lee `blender_main.py`. Personas: `moderno`/`semirealista`;
  `moderno_juguete` solo para juguetes de plástico (en una persona la ropa sale lustrada: pasar a `moderno` y
  rehacer el render).
- Humanoides nuevos: README > *Qué mirar en cada paso (receta para humanoides)* (Pixal3D 4 vistas + UltraTex). Sin
  referencia: Z-Image para la idea → la elegida como `base_<seed>.png` de `referencia` → Qwen con un `imagen.prompt`
  de edición (sin `descripcion`) que saque piezas sueltas y ajuste la ropa.

## Mapa del código

`herramientas/` por paso. Intérprete: python3 del sistema salvo `generar_malla_trellis.py` (venv TRELLIS.2),
`generar_movimiento.py` (venv Kimodo) y `blender_main`/`rig_lib`/`anim`/`kimodo_clip`/`vehiculo` (Blender).
- `0_entorno/doctor.py` (`crisol doctor [--json]`): revisa config, rutas, venvs, nodos, modelos y GPU; corre antes
  de leer la config. `PASOS` dice qué necesita cada paso: actualizarlo al sumar un paso, modelo o nodo.
- `0_entorno/estado.py` (`crisol estado [<n>] [--json]`): pasos hechos/viejos (por fecha de la salida contra la del
  paso previo) y qué falta elegir; al sumar un paso o cambiar dónde escribe, actualizar su cadena.
- `instalar.sh` (raíz, bash): instalación nativa por niveles. Commits fijados y tabla de modelos (`MODELOS_COMFY`,
  repo → nombre final) arriba: al sumar un modelo o nodo, también ahí (y en `doctor.MODELOS`/`NODOS`). `--plan` lo
  prueba sin instalar; con la config de esta PC reconoce lo instalado y no lo toca.
- `Dockerfile` + `docker/` (`entrypoint.sh`, `config.json` con las rutas de adentro): la imagen corre instalar.sh sin
  GPU (`CRISOL_CUDA_ARCH`); modelos en el volumen `/modelos`, datos en `/datos`, pasos como el dueño de `/datos`.
- `1_imagen/generar_imagen.py` + `*.recipe.json`: workflows con `comfy workflow apply` + modelos fijados (Qwen Edit,
  FLUX.2 Dev); Z-Image (`motor_texto`, `workflow_zimage`) en formato API armado en Python; hoja de contacto.
- `2_malla/`: `generar_malla_pixal3d.py` (workflow API armado en Python; modo `alinear`), `generar_malla_trellis.py`
  (venv TRELLIS.2; se relanza con `os.execv` tras un OOM), `retexturizar_ultratex.py` (`limpia.glb` + `sin_fondo.png`
  → `modelo.glb`; el del motor queda en `modelo_motor.glb`; `espalda`/`costados` con las vistas de Qwen).
- `3_blender/`: `blender_main.py` (modos `limpia`, `guia`, `construir`, `retrato`, `reves`, `comparar`, `iso`,
  `anclas`, `objeto`, `alinear`), `rig_lib.py` (`PLANTILLA`, estimación, rig, pesos, `cortar_puentes`), `anim.py`
  (`TODAS`, poses-dict `_pose`/`_poses`), `kimodo_clip.py` (NPZ → Action), `metodos.py` (procedural/kimodo por
  animación; `movimientos/biblioteca.json`), `generar_movimiento.py` (venv Kimodo), `articulaciones_pose.py`
  (DWPose), `dibujar_guia.py`, `vehiculo.py`.
- `4_sprites/`: `armar_tira.py` (`ANIMACIONES`, hoja, retrato), `armar_iso.py`, `armar_objeto.py`, `revisar.py`
  (`revision.png`), `posproceso.py` (color, nitidez, contorno del estilo), `vitrina.py` (gifs de `docs/vitrina/` desde los
  ejemplos ya renderizados en datos_dir).
- `5_godot/`: `exportar_godot.py`, `exportar_objeto.py`, `sprite_personaje.gd`, `sprite_personaje_iso.gd`, `objeto_iso.gd`.
- `6_escenario/`: `texturas.py`, `repetible.py`, `tema.py`.
- `estilos/*.json` (base `animacion3d`), `plantilla/{personaje,objeto,vehiculo,escenario}.json`, `ejemplos/`.

## Contratos (cambiarlos rompe juegos o pasos siguientes)

- **Orden de la hoja** (`armar_tira.ANIMACIONES`): 0 idle, 1-8 caminata, 9-12 salto, 13+ las agregadas. Grilla de 13
  columnas, celdas seguidas (índice = fila × 13 + col): cambiar los cuadros de una corre las siguientes; el visual las
  busca por nombre (`frame_de`/`meta.json`). Animaciones nuevas **al final** (+ `anim.TODAS`, + `armar_iso.NOMBRES`, + README).
- **Iso**: direcciones `e,se,s,sw,w,nw,n,ne` (filas y sufijo `<anim>_<dir>`); cámara 30°; `baldosa_px` = ancho de 1×1.
- **API del visual**: `set_frame(frame, flip_h)` (+ `frame_de`, `retrato`, `frente`); hijo directo del
  `CharacterBody2D`; origen = los pies. La sombra nunca va en los sprites: la dibuja el `.gd`.
- **Huesos**: nombres de `rig_lib.PLANTILLA`, usados por `anim.py`; `.S` = lado +X, se espeja.
- **Orientación**: frente -Y, pies en z=0, alto `modelo.altura`; al renderizar el rig rota 90° en Z (mira a +X), cámara a nivel.
- **Godot**: `godot/personajes/{_comun,<n>}/` replica `res://personajes/...`; `--instalar` conserva los `.import`
  (uid estable). Lo instalado se regenera, no se edita. No instalar en ningún proyecto sin que el usuario lo pida.
- **Escala**: render a `sprites.superresolucion`×, Sprite2D a 1/N con filtro lineal + mipmaps.
- **Vehículos**: `vehiculo.glb` con nodos `carroceria`, `rueda_di/dd/ti/td` (origen en el eje), trompa en +Z.

## Gotchas (síntoma → causa → qué hacer)

### Malla
- TRELLIS.2 necesita `transformers==4.57.1` (con 5.x: `DINOv3ViTModel has no attribute 'layer'`).
- TRELLIS.2 sale en cientos de piezas: se sacan las < 100 caras (objetos: solo migas < 10, máx. 10 %; nunca la
  mayor) y `rig_lib.pesos_de_piezas_sueltas` pesa las que quedan; sin eso el bone heat falla.
- **Capas escondidas** (cuerpo bajo la ropa + cara interior de la ropa): en reposo no se ven, al animar atraviesan
  (manchas oscuras, "agujeros"). Las borra `blender_main.sacar_interior` (rayos); diagnosticar con
  `show_backface_culling` y probar poses, no solo la caminata. En mallas de pocas caras agujerea.
- El glTF viene partido en las costuras UV: `importar()` suelda (`remove_doubles`); sin soldar, todo queda sin peso.
- OOM: tras uno la VRAM no se libera en el proceso (CuMesh avisa con `RuntimeError`, mirar `'out of memory' in
  str(e)`): por eso el relanzado a menor resolución. Objetos a 512. `max_num_tokens` no sirve.
- **La seed pesa mucho**: probar 2-3 seeds antes de tocar código. Color base en sRGB: si sale oscuro es la predicción.
  `TRELLIS_CRUDO=1` guarda el GLB con metal/rugosidad para diagnosticar.
- Caras chicas (~50 px en cuerpo entero) → TRELLIS las redondea y pinta manchas; otra seed no lo arregla: Pixal3D + UltraTex.
- Ojos agujereados (cráter del ojo tomado como interior) → `modelo.ojos` (`parche_ojos`). Lo editado en `<n>.blend`
  se pierde: todos los modos rearman desde `modelo.glb`.
- Pixal3D: mejor en caras y estampados; con 4 vistas el color es malo → UltraTex. El GLB trae normal/AO/metal: se deja
  solo el color base. `resolucion` 512 falla (usar 1024/1536); pocas `caras` → astillado; follaje no entra en 16 GB;
  autos en tres cuartos desde arriba salen astillados (TRELLIS.2 anda mejor). Cara derecha: `cabeza_arriba_grados` 0.
- Vistas de Qwen: pueden copiar a la espalda lo del pecho o salir con el costado espejado: mirar `vista_*.png`.
- UltraTex solo mira `sin_fondo.png`: sin `espalda` inventa la espalda copiando el pecho. **Los ojos dependen de
  `malla.ultratex.seed`**: mirar la cara de cerca. Mientras corre, `modelo.glb` es la malla del motor (no evaluar una `guia`).
  Ojos achinados en la imagen elegida → editarla con Qwen ("only change the eyes") como `base_<seed>.png`.
- Vegetación: hojas sueltas → cáscaras con agujeros; pedir masas lisas de follaje ("no individual leaves, solid
  silhouette"), `malla.fondo` `birefnet-general`, TRELLIS.2 a 512.
- Reducir caras de un GLB (p. ej. para versionar un ejemplo): soldar (`remove_doubles`) antes del Decimate; sin eso
  se abren las costuras UV y `sacar_interior` borra media malla. Comparar el `preview.png` antes y después.
- Vehículos: la receta supone un auto (los prompts de `vistas` dicen "toy car"): una vagoneta sale auto; otros
  vehículos, como objeto común. Malla desde la cola en tres cuartos (`malla.vista: "atras"`). Buscar agujeros con Workbench +
  `show_backface_culling` y fondo verde.

### Rig, pesos y animación
- **Rodillas**: `rig_lib.angulo_polo` calibra el `pole_angle` probando (no es -90° fijo) y `rodilla_en_linea` lleva
  la rodilla al plano cadera-tobillo, siempre al menos `ADELANTO_RODILLA` adelante: con la pierna recta el IK la
  doblaba para atrás.
- Codos "de plastilina" → mezcla lineal a 110-135°, no los pesos: `modelo.preservar_volumen` (cuaterniones duales).
- Pesos que fallan: chibis redondos → `modelo.pesos: "distancia"`; robots en bloques → `modelo.pesos_rigidos`; pieza
  cerca de la mano con peso del antebrazo → `modelo.pesos_zonas`; modelo asimétrico sin hueso en un brazo → lado
  suelto (`upper_arm.R`...). Diagnóstico: render coloreado por hueso dominante en reposo y en poses. Detalle: README
  > *Cuando los pesos fallan*. Chibis con brazos fundidos al cuerpo: regenerar con brazos separados.
- Descartado, no reintentar: filtros de "hueso implausible"/visibilidad, devolver al cuerpo lo lejano de la mano,
  híbridos bone heat + distancia.
- `cortar_puentes` solo tapa agujeros < 12 cm (uno grande arma una lámina). `modelo.normales: true` solo si la fila
  de revés muestra caras de afuera borradas (en otros suma manchas).
- Articulaciones: las rebanadas fallan en chibis/torso ancho → `crisol articulaciones` (DWPose); en muñecos
  DWPose tampoco anda → cargarlas a mano mirando `guia.png`.
- Brazos (`anim._brazo`): girar en ejes del cuerpo, no del hueso (en pose A hace un cono). Pies: `tobillo_*` es
  respecto de la canilla; medir tras cambiar poses (rango ~ -30..+50).
- `cabeza_arriba_grados`: **negativo = levantar la cara**. Probar 2-3 valores renderizando el idle.
- Blender 5: Actions por capas/slots (usar `anim._fcurves()`); buscar nodos por `type`, no por nombre.
- Kimodo: `foot_contacts` del NPZ está mal (ciclo por altura del tobillo). Ejes y arriba, +z adelante, +x izquierda;
  alinear el reposo solo en brazos y muslo/canilla; rotación al rig `R @ G @ M.T` (no `R @ G @ R.T`). Gana en cuerpo
  entero (caminar, morir), pierde en golpes: elegir por animación. Los avisos `MISSING` del LoRA son normales.

### Imagen, escenarios y entorno
- Las recetas dejan los loaders en el primer valor del combo: `generar_imagen.py` fija los modelos (`modelos_imagen`).
- Foto de referencia + estilo de dibujo → pedir "3D ... no outlines, not a 2D drawing" o sale plano con contorno.
- Escenarios: detalle **relativo al promedio en lineal** (se multiplica color × detalle × 2); detalle fino = ruido
  desde la cámara iso (`contraste` 0,5, formas grandes). Para sacar texturas de una imagen: IP-Adapter, no Qwen-Edit.
- Comparar RGBA canal por canal: `getbbox()` de una diferencia RGBA solo mira el alfa.
- VRAM 16 GB: ComfyUI con Qwen ~12 GB; `paso_malla` hace `POST /free`. Cachés de modelos en `env_modelos`, no `~/.cache`.

### Instalación y Docker
- El disco del sistema de la PC de referencia es chico: la caché de `uv` (~15 GB por instalación) y los temporales de
  nvcc van a `--destino` (`UV_CACHE_DIR`, `TMPDIR`); nunca a `~/.cache`. Los MCP de Godot/Blender corren con `uvx`
  y bloquean `~/.cache/uv` (`uv cache prune` espera; limpiar por paquete con `uv cache clean --force <pkgs>`).
- `hf auth whoami` sale con 0 sin sesión: mirar si dice `Not logged in`/`Invalid`.
- Contenedor (corre como el dueño de `/datos`, no root): numba cachea junto a su código (`NUMBA_CACHE_DIR` al
  volumen), Triton compila C en el primer uso (`gcc` en la imagen), lo que el entrypoint crea en `/modelos` tiene que
  crearse después de bajar a ese usuario. Sin pantalla: Blender y UltraTex por EGL (`NVIDIA_DRIVER_CAPABILITIES=all`).

## Verificar cambios

- **Antes de commitear cambios de Blender, sprites, iso, Godot o escenarios**: `python3 tests/humo.py` (~3 min; usa la
  GPU para renderizar con EEVEE: no correrlo mientras hay una generación) o `--rapido` (~1,5 min). Datos temporales.
- Referencias: `cris` (personaje) y `caja` (objeto) en `ejemplos/`; copiarlos con `cp -r ejemplos/* <datos_dir>/`.
- Blender/animación: `crisol blender cris && crisol sprites cris` y mirar `preview.gif`; también `iso cris`
  → `preview_iso.gif` y poses (golpe, patada, brazos arriba). Celdas sueltas: recortar la hoja con `meta.json`.
- Objetos: `blender caja && sprites caja` → `preview.png`. Articulaciones: `guia <n>` → `trabajo/guia/guia.png`.
- Tras tocar rig/animaciones: `rehacer <n1,...>` y mirar cada `revision.png`.
- Godot: proyecto vacío temporal, `godot <n> --instalar <dir>` y un `-s script.gd` headless que instancie.
- Sin gastar minutos de malla: personaje temporal con `personaje.json` + `trabajo/malla/modelo.glb` copiados; borrarlo al terminar.
- `instalar.sh`: `--plan` con la config real (no tiene que tocar nada) y, si cambia la instalación, en limpio con una
  config de prueba (`ASSETCRISOL_CONFIG=<tmp>/config.json ./instalar.sh --destino <tmp> --nivel minimo --solo
  comfyui,trellis,blender,config`, ~20 min) y una `malla` de TRELLIS.2 con esa config.
- Docker: `docker build -t assetcrisol:prueba .` y correr `doctor`, `blender`/`sprites` y una `malla` con UltraTex
  montando los modelos de la PC en `/modelos/comfyui`, `/modelos/hf`, `/modelos/u2net` y `/modelos/dwpose`.
