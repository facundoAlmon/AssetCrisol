# Changelog

Los cambios de cada versión de AssetCrisol, del más nuevo al más viejo. Versionado semántico; mientras sea 0.x,
cualquier versión puede cambiar el formato de `personaje.json` o de las hojas (se avisa acá).
*English: each version's changes, newest first. Semantic versioning; while on 0.x, any version may change the
`personaje.json` or sprite-sheet format (noted here).*

## [Sin publicar]

### Agregado
- **UI en el navegador** (`crisol ui`, local en `127.0.0.1:8190`, sin dependencias nuevas): biblioteca de assets,
  crear con referencia o descripción, la cadena de pasos con correr/rehacer, las candidatas para elegir (y cambiar
  una elección), visor de resultados con el reproductor iso por dirección, ajustes comunes sin json (y el json
  completo como modo avanzado), cola de pasos de a uno con tiempo estimado, log en vivo y cancelar, movimientos de
  Kimodo y la revisión de la instalación. Visor 3D del `.glb` (three.js vendorizado) en el resultado y para comparar
  los candidatos de malla uno al lado del otro. En español e inglés, tema claro y oscuro, también en el celular
  (README > Empezá acá > En el navegador). `tests/ui.py` la prueba sin GPU.
- Editor de **candidatos de malla** en la UI (Ajustes > Malla): motor, seed y resolución de cada uno (también el
  principal), repintados con UltraTex `desde` otro, cuáles ya están generados y **Rehacer** uno (borra su
  `trabajo/malla_<c>/` y pone Malla 3D en la cola).
- `crisol ui --host 0.0.0.0`: la UI desde otra PC o el celular en la misma red, con token: al arrancar imprime
  `http://<ip>:<puerto>/?token=...` (al azar en cada arranque, o fijo con `--token` / `CRISOL_UI_TOKEN`). Abrir esa
  URL deja una cookie (HttpOnly, SameSite=Strict) y la URL queda sin el token; sin ella, la página pide el token y la
  API, los eventos, las miniaturas y los archivos dan 401. Desde la misma PC (127.0.0.1) no hace falta.
- Los logs llevan la hora al principio de cada línea (`14:03:27 ...`): los de los pasos que lanza la UI,
  `trabajo/malla/trellis2.log` y `trabajo/blender_<modo>.log` (las barras de progreso, en cada actualización; en
  Blender, stdout y stderr quedan intercalados en el orden en que salieron). `comfyui.log` sigue sin hora.
- `crisol ui`: en *Te toca elegir* los candidatos de malla son tarjetas, una por candidato, con su render (todas en
  la misma vista, elegida arriba; en vehículos, la tarjeta y las vistas de `blender`, recortadas al centro), cómo se
  hace (motor, seed, resolución, UltraTex), si ya está generado, **Ver en 3D** dentro de la tarjeta y **Elegir
  esta**. Las mallas anteriores, sin vistas propias, muestran la hoja hasta correr **Comparar mallas** (que ya no
  aparece en vehículos). `crisol comparar` guarda cada vista de cada candidato en `trabajo/comparar/<c>/<vista>.png`.
- `crisol clip`: biblioteca de movimientos propia en `<datos_dir>/movimientos/` (`biblioteca.json` + `<anim>.npz`,
  encima de la del repo, que no se toca). Pasa un candidato de `crisol movimiento` (`--candidato <anim>_s<seed>_<i>`),
  cambia la ventana (`--desde`/`--hasta`) o si es el método por defecto (`--recomendado si|no`), también sobre un clip
  del repo, y `--quitar` vuelve al del repo. En `crisol ui` > Movimientos: la fila de esqueletos de cada muestra,
  pasarla a la biblioteca, elegir si es el método por defecto, quitarla y usarla en un personaje, sin json.
- **Recetas por tipo**: `crisol nuevo <n> --receta humanoide|chibi|robot|juguete|objeto|vegetacion|vehiculo|escenario`
  arma el json con lo que anda para cada tipo (`plantilla/recetas/`); `--descripcion` completa `imagen.descripcion`
  sin editar el json. `--objeto`, `--vehiculo` y `--escenario` siguen como atajos.
- **Servidor MCP** (`crisol mcp`, por stdio, con `uv`): `recetas`, `crear`, `estado`, `correr`/`esperar`, `ver`,
  `elegir`, `ajustar` y `doctor`, con las imágenes para mostrarle a la persona (README > Para agentes de IA).
- `instalar.sh --kimodo`: Kimodo para `crisol movimiento` (~19 GB, en CPU, sin token de Hugging Face).
- `crisol doctor` revisa `uv` (opcional, para `crisol mcp`).
- `CONTRIBUTING.md`, plantillas de issues (error con `crisol doctor --json`, propuesta) y este CHANGELOG.

### Cambiado
- `crisol ui`, Ajustes > Sprites: el tamaño de los sprites sin json (además del alto en pantalla, la calidad de la hoja,
  la baldosa y la calidad del iso; en objetos, también la escala y la calidad de la vista de costado), con lo que sale
  en el juego y lo que se renderiza a la vista mientras se cambia.
- `crisol ui`: los pasos van numerados y con su ayuda corta a la vista (antes, solo al pasar el mouse); las pestañas
  del visor llevan el número del paso que dejó cada resultado, en ese orden. El historial de la cola se puede borrar
  (todo o lo marcado, con sus logs). En el celular, los pasos (con cuántos hay hechos y cuál sigue), los grupos de
  ajustes y el historial se pliegan. **Más**, junto a cada paso, abre una ayuda más larga: qué hace, qué mirar, qué
  probar si sale mal y su sección del README (`web/i18n/ayuda_{es,en}.mjs`).
- `crisol ui` avisa cuando su código cambió en el disco (por ejemplo, tras un `git pull`) y hay que reiniciarla: la
  página nueva contra el servidor viejo pedía rutas que no existían (borrar el historial daba un error con solo
  "historial"). Un 400 por algo que no existe ahora dice "no existe: ...".
- `plantilla/vehiculo.json` pasó a `plantilla/recetas/vehiculo.json`.
- `instalar.sh` probado en limpio con el nivel completo (44 min, ~138 GB).
- Los tiempos de Pixal3D en objetos (README): el candidato `pixal3d` a 1536 tarda 1-8 min según el volumen.

### Arreglado
- Las articulaciones salían mal la primera vez y "al recalcular" andaban: lo primero eran las estimadas por
  rebanadas (sin `modelo.articulaciones`), y lo segundo, DWPose (`crisol articulaciones`), que no estaba en la cadena
  (en `crisol ui`, un botón aparte). Ahora `articulaciones` es un paso de la cadena de los personajes, antes de `guia` y
  `blender` (`crisol todo` lo corre si no hay articulaciones); anota el resultado en `trabajo/guia/articulaciones.json`
  y `crisol estado` dice si DWPose no pudo. `blender` queda viejo si las articulaciones son más nuevas.
- Con `--json` (los pasos que lanza la UI) los mensajes del paso y la salida de sus subprocesos de python quedaban en
  un búfer y el log aparecía recién al terminar (visto en `imagen`): ahora se escriben al momento.
- Cambiar `malla.elegida` y rehacer lo que sigue usaba la malla anterior: `trabajo/malla` sigue siendo el candidato
  copiado hasta volver a correr `malla` (que copia, no regenera), y `crisol estado` lo daba por hecho. Ahora marca
  `malla` como vieja si `trabajo/malla` no es la elegida (lo anota `trabajo/malla/candidato.txt`), y la copia lleva
  la fecha de ahora, así `blender` y lo que sigue quedan viejos.
- Cancelar un paso en `crisol ui` (o Ctrl+C en la terminal) dejaba su trabajo en la cola de ComfyUI, generando con
  el paso ya muerto y trabando al siguiente. Ahora, al cortar, el paso que reservó la GPU saca sus pendientes de la
  cola de ComfyUI e interrumpe el que corre (`gpu.vaciar_comfyui`).
- `crisol ui`: el tiempo estimado de `imagen`, `malla`, `iso` y `texturas` era la mediana de las corridas anteriores,
  sin mirar cuánto trabajo traían (Z-Image con 1 seed contra Qwen con 3; una malla de 3 candidatos contra una que
  solo copia). Ahora se mide por unidad (seed, candidato que falta generar, animación, textura) y por motor, y se
  multiplica por las del trabajo nuevo (`servidor.carga`). Hasta tener medidas así, sigue la mediana de antes.
- `crisol ui`, Ajustes: al escribir las seeds, Guardar seguía en gris hasta salir del campo.
- `crisol ui`: al reabrirla con un paso que siguió corriendo, quedaba "interrumpido" y el siguiente de la cola
  arrancaba encima; ahora lo espera. En el celular, deslizar en vertical sobre el visor 3D baja la página (girar es
  de costado). Al comparar mallas en 3D, "Elegir esta" aparecía dos veces.
- La hoja de candidatos de malla (`trabajo/candidatos.png`, y `revision.png` en vehículos) marcaba "(elegida)" en
  la última fila aunque la elegida fuera otra; ahora marca solo la de `malla.elegida`.
- `crisol metodo` (y Ajustes > Animaciones) ofrece kimodo también para clips sin `_nota`.
- `instalar.sh` daba por buena una sesión de Hugging Face con un token vencido o inválido; ahora pide login.
- Con `comfyui_url` en otro puerto que el 8188, la imagen con referencia, las vistas, Pixal3D y las texturas con
  FLUX.2 buscaban ComfyUI en el 8188 (`comfy run` sin `--host`/`--port`).

## [0.1.0-alpha.1] - 2026-10-28

Primera versión pública: el motor completo, la instalación (nativa y Docker) y la CLI para agentes. La imagen Docker
está en `ghcr.io/facundoalmon/assetcrisol:0.1.0-alpha.1`.

### Agregado
- Pipeline imagen → malla → rig y animaciones → sprites e iso → Godot, para personajes, objetos, vehículos y kits de
  escenario. Imagen con Qwen Image Edit (con referencia) o Z-Image Turbo (sin referencia; FLUX.2 Dev opcional); malla
  con Pixal3D (4 vistas) o TRELLIS.2, repintada con UltraTex.
- Ejemplos versionados: Cris (la protagonista), sus objetos, su camioneta, una caja y dos escenarios (bosque y taller).
- `instalar.sh` (niveles mínimo y completo, `--flux2`, `--plan`) e imagen Docker (`docker/publicar.sh`).
- `crisol doctor`, `crisol estado`, `--json` en todos los pasos, códigos de salida, cola de GPU y errores claros
  (código 6 si falta algo de la instalación, 5 si falta un paso previo).
- Avisos de licencia en el meta de cada asset y `docs/licencias.md`.
- Hojas con `.json` estilo Aseprite para otros motores; `render.emisivo`; vitrina de los ejemplos.
- `tests/humo.py`: test de humo sin generación (~3 min).

[Sin publicar]: https://github.com/facundoAlmon/AssetCrisol/compare/v0.1.0-alpha.1...main
[0.1.0-alpha.1]: https://github.com/facundoAlmon/AssetCrisol/releases/tag/v0.1.0-alpha.1
