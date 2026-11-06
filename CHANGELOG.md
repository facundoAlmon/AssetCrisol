# Changelog

Los cambios de cada versión de AssetCrisol, del más nuevo al más viejo. Versionado semántico; mientras sea 0.x,
cualquier versión puede cambiar el formato de `personaje.json` o de las hojas (se avisa acá).
*English: each version's changes, newest first. Semantic versioning; while on 0.x, any version may change the
`personaje.json` or sprite-sheet format (noted here).*

## [Sin publicar]

### Cambiado
- La landing y la galería muestran los cuadrúpedos en su propia tarjeta (el gato gris de la receta `cuadrupedo`, `gato_acciones.gif` de `vitrina.py`).
- Objetos nuevos: el candidato `pixal3d` de la plantilla va a 1024 en vez de 1536 (14-44 % menos de Pixal3D,
  calidad pareja en tres objetos). Los objetos existentes conservan su json.
- `crisol ui` > Movimientos: un listado por animación (en el orden de la hoja, con su método por defecto, clip y
  variantes sin pasar) y el detalle de cada una: la procedural al lado del clip de la biblioteca, generar con esa
  animación ya elegida, sus variantes (que ahora se pueden borrar) y qué personajes la usan. El esqueleto de las
  procedurales sale de `herramientas/3_blender/movimientos/procedurales.json` (lo arma
  `herramientas/3_blender/procedurales.py` con el rig de Cris: rehacerlo al cambiar `anim.py`).

### Agregado
- Pesos por zonas desde `crisol ui` (Resultado > Guía > *Pesos por zonas*): las cajas de `modelo.pesos_zonas` se
  dibujan y se arrastran sobre los renders de frente y de costado de la guía, con el hueso de cada una; al guardar
  ofrece rehacer el rig.
- Candidatos de cara de UltraTex: con `malla.ultratex.seeds` (las recetas `humanoide` y `chibi` traen `[1, 2, 3]`),
  `malla` repinta con cada seed (`trabajo/malla/ultratex_s<seed>.glb`) y arma `caras.png` con la cabeza de frente de
  cada una (Blender, modo `cara`). La persona elige con `malla.ultratex.elegida` (también en *Te toca elegir* de
  `crisol ui` y con `elegir` del MCP), que copia ese repintado a `modelo.glb` sin generar de nuevo. Suma 1-6 min por
  seed a la malla de los personajes nuevos; los existentes conservan su json.
- Vehículos que no son autos: si `imagen.descripcion` no nombra un auto, las vistas de Qwen nombran el vehículo con la
  descripción y no piden luces traseras ni alerón (una vagoneta salía convertida en auto). Los autos siguen con los
  prompts de antes. La receta `vehiculo` dice "whole vehicle visible" en vez de "whole car visible".
- Editor del retrato en `crisol ui` (Resultado > Retrato > *Editar el encuadre*): un cuadro 4:5 sobre la imagen sin
  fondo o sobre el render de frente del modelo, que se arrastra y se agranda, con vista previa. Guarda
  `retrato.caja.<fuente>` (fracciones de la fuente; *Automático* la borra) y rehace el retrato: con la imagen solo
  recorta (sin Blender, menos de un segundo), con el modelo la caja pasa a la cámara. Avisa si el recorte se va a ver
  borroso y, en `crisol estado`, si la caja es de otra imagen elegida. `retrato.json` guarda el encuadre de
  `frente.png`.
- Corregir una imagen candidata: `crisol corregir <n> --desde <seed|edit_k> --pedido "..."` (y *Corregir* en cada
  candidata de `crisol ui`, y la herramienta `corregir` del MCP) pasa el pedido a Qwen Edit sobre esa imagen ("Keep
  this exact image… Only make these changes…") y saca 2 candidatas nuevas `edit_<k>` (`cand_edit_<k>.png`), que se
  eligen como las otras (`imagen.elegida: "edit_<k>"`) y se pueden encadenar. No pisa las originales; el pedido y de
  dónde salió cada una quedan en `trabajo/imagen/correcciones.json`. Reemplaza la receta a mano de `base_<seed>.png`.
- Papelera: `crisol borrar <n>` (y el tacho junto al nombre en `crisol ui`) mueve el asset a
  `<datos_dir>/.papelera/<carpeta>/<n>_<fecha>/`; `crisol papelera` la lista, `--restaurar <id>` lo devuelve y
  `--vaciar [<ids>]` borra para siempre. En la UI, Biblioteca > Papelera. No con pasos del asset en la cola.
- `crisol movimiento --borrar <anim>_s<seed>[_<i>]`: borra candidatos de Kimodo (una muestra, o la generación entera
  con su hoja de esqueletos); los clips de la biblioteca son copias y no cambian. También en la UI (Movimientos).
- Cuadrúpedos con Pixal3D de una vista: `malla` los endereza sobre las cuatro patas (`cuadrupedo.apoyar`) y
  `blender` no les saca las capas escondidas; antes salían inclinados como la cámara y sin ningún vértice con peso.
  `modelo.alinear` (enderezar la malla de Pixal3D de una vista) vale ahora también en personajes: por defecto sí en
  objetos y cuadrúpedos, no en humanoides; casilla en Ajustes > Modelo de `crisol ui`.
- Cuadrúpedos: aviso de que Pixal3D no se recomienda (aun enderezada, la malla anima mal: patas que casi no se
  mueven, la capa de adentro que se ve; con TRELLIS.2 el mismo animal anima bien). Lo dicen `malla`, `crisol estado`
  y la UI cuando la malla elegida es de Pixal3D, el README y la receta.
- Cuadrúpedos: el encuadre de la imagen pide la cabeza girada como el cuerpo (con "head up looking forward" y una
  foto de referencia, Qwen dejaba al animal mirando a la cámara y la malla con la cara de costado en todas las
  animaciones), y el retrato sale del render del modelo (`retrato.fuente: "modelo"` por defecto): el recorte de la
  imagen de tres cuartos caía sobre el lomo.
- `retrato.zoom` (1 por defecto): más de 1 acerca el retrato, para alas, mochilas o cuellos altos que agrandan
  el ancho sobre el cuello y dejaban la cabeza chica. También en Ajustes > Sprites de `crisol ui`.
- Animación `saludar` (`wave`, 7 cuadros): la mano cercana en alto, de lado a lado; al final de la hoja (86-92) y
  en las 8 direcciones del iso. Por ahora procedural (`metodos.CUADROS` ya la acepta para un clip de Kimodo).
- Malla según la VRAM: con menos de 16 GB (`nvidia-smi`, o `vram_gb` en la config), sin `malla.resolucion` arranca
  a 512 en TRELLIS.2 y a 1024 en Pixal3D en vez de esperar el OOM; `doctor` lo avisa. Sin probar en una placa así.

### Arreglado
- Renombrar, deshacer o borrar un asset decía "hay un crisol con <n> corriendo" si corría un paso de un asset con el
  mismo nombre en otro `datos_dir` (otra config): ahora solo cuentan los `crisol` con la misma config.
- `instalar.sh --plan` con todo instalado ya no avisa que faltan ~135 GB ni que va a completar `config.json`: dice
  qué cambiaría de la config (o que está completa) y lista los pesos que DWPose y rembg bajan en el primer uso.
- UI: el estado de cada paso y de cada elección se dice en palabras ("se hizo antes del último cambio en Malla 3D",
  "la malla ya está hecha") en vez de rutas y claves del json; en inglés también, y la descripción de los estilos en
  *Nuevo* (salían en español). `crisol estado --json` suma `aviso` (`{id, ...datos}`) junto a cada `nota`.
- Elegir un candidato de malla (UI o MCP) lo copia a `trabajo/malla` en el momento: Malla 3D quedaba
  "desactualizado" y el botón decía *Siguiente: Malla 3D*, como si fuera a generar de nuevo.
- README: enlace al sitio web y al manual arriba; "Empezá acá" y el badge de Godot no saltaban (anclas con tilde en
  el bloque centrado: ahora `#empezar` y `#guia-de-godot`); el badge de Blender apuntaba a una sección que no existe.

## [0.4.0] - 2026-11-04

La primera versión para usar sin ser parte del proyecto: un manual de la UI con capturas, la landing en GitHub Pages,
una demo en Godot y la documentación revisada por un agente que la siguió sin contexto. La imagen Docker está en
`ghcr.io/facundoalmon/assetcrisol:0.4.0`.

### Agregado
- **Manual de `crisol ui`** ([docs/ui.md](docs/ui.md), [en](docs/ui.en.md)): un personaje de punta a punta, ver el
  resultado, qué hacer cuando algo sale mal, ajustes, otros tipos de asset, movimientos, exportar y licencias, con
  capturas en español e inglés. `tests/capturas_ui.py` las rehace (Playwright sobre el Chrome instalado).

- Landing en GitHub Pages (https://facundoalmon.github.io/AssetCrisol/, `docs/index.html`): qué hace, Cris paso a
  paso (`vitrina.py` arma `proceso_1..5.jpg`), qué se puede hacer, la demo en Godot, las tres maneras de usarlo (la UI
  con un video del recorrido, un agente por MCP con una conversación de ejemplo y la CLI con `--json` y sus códigos),
  requisitos, instalación y licencias, en español e inglés.

- **Demo en Godot** (`demo/`): Cris camina por su taller isométrico entre sus objetos, con el piso y las paredes del tema
  `taller`; `demo/preparar.sh` instala los ejemplos con `godot --instalar`.

### Arreglado
- `crisol ui`: los campos numéricos (altura, seeds, duración y recorte de un clip) se rearmaban a medio escribir y
  "1.65" quedaba 651.
- `crisol ui`, Exportar > *Archivos de origen*: incluye la imagen de referencia que nombra el json (`base_<seed>.png`),
  no solo un `referencia.png`.
- `crisol ui`: mientras falta elegir la imagen, Resultado ya no dice "Corré el primer paso"; "Mirá esto antes de
  seguir" no repite las candidatas de *Te toca elegir* y muestra las hojas anchas (vistas) a lo ancho.
- README: anclas internas rotas, la estructura del repo, numpy para `tema`, `anclas` y `guia` en la tanda de los
  ejemplos, `tema.colores: false` y Godot 4.4 o más nuevo.

## [0.3.0-alpha.1] - 2026-11-04

Modelos para juegos 3D (LODs, huesos de Mixamo, materiales horneados), cuadrúpedos, la revisión de cerca y
Movimientos más claro en `crisol ui`. La imagen Docker está en `ghcr.io/facundoalmon/assetcrisol:0.3.0-alpha.1`.

### Agregado
- **Modelos para tiempo real**: `blender` deja también en `trabajo/tiempo_real/` la malla reducida (Decimate por
  colapso, que conserva UV y pesos) a 20 k, 10 k y 5 k triángulos en personajes (con el rig y las animaciones) y a
  10 k, 5 k y 2 k en objetos, con la textura a 2048 px: `<n>.glb` (solo el LOD0, para Godot, que arma sus LOD) y
  `<n>_lods.glb` (un esqueleto con las mallas `<n>_LOD0..2`, para Unity y Unreal), más `lods.json`. Se ajusta con
  el bloque `tiempo_real` del json (`false` lo apaga). En `crisol ui`, Resultado > Juego 3D (un LOD por vez, en alambre si se pide), Ajustes > Juego 3D y Exportar > Juego 3D. Los huesos de los
  humanoides salen con los nombres de Mixamo (Unity Humanoid, Unreal, mapeo automático de Godot) o, con
  `tiempo_real.huesos: "godot"`, los de `SkeletonProfileHumanoid`; sin los huesos auxiliares del IK. Materiales
  horneados (Cycles en CPU): mapa de normales por LOD con el relieve de la malla entera, ORM con la rugosidad y el
  metal del estilo, emisión y, con `tiempo_real.mapas` `"ao"`, oclusión ambiente. `"tiempo_real": false` en
  `config.json` lo apaga para todos los assets (~20-25 MB y ~10 s menos por asset en `blender`).
- **Revisión de cerca** (paso `revisar`): `trabajo/revision_cerca.png` con codos, hombros, rodillas, cadera y cara
  de cerca en las poses que más los doblan, de frente y de costado, con textura y el interior a la vista en magenta
  (ropa que se atraviesa, codos de plastilina, costuras de la textura); en cuadrúpedos, patas y cara. En `crisol ui`,
  junto a la hoja de revisión.
- **Cuadrúpedos** (`crisol nuevo <n> --receta cuadrupedo`): perros, gatos, caballos... con su propio esqueleto
  (`modelo.esqueleto: "cuadrupedo"`: cuatro patas con IK, cuello, cabeza y cola), las articulaciones estimadas de la
  malla (sin DWPose; el animal se gira solo para mirar adelante) y 8 animaciones procedurales (idle, paso, salto,
  respirar, galope, mordida, herido y morir) con los nombres y cuadros del humanoide. La imagen sale de tres cuartos y
  de costado; la malla, con TRELLIS.2 + UltraTex. El editor de articulaciones de `crisol ui` los entiende.
- Bloque `prompt` en el json de un asset (`render_personaje`/`render_objeto`, `tema`, `paleta`, `extra`): pisa esas
  partes del prompt del estilo solo para ese asset (`""` la saca). En `crisol ui`, Ajustes > *Prompt del estilo*, con
  el prompt que sale.

### Cambiado
- `crisol ui`, **Movimientos**: los pasos a la vista (generar, mirar y recortar, biblioteca, rehacer), las variantes
  agrupadas por generación con el esqueleto animado (también los candidatos viejos sin hoja de esqueletos) y el
  recorte marcando un instante; cada clip dice qué personajes lo usan. Está en la barra del celular.
- `crisol ui`, **Resultado > Animación**: la hoja de costado animada, una animación por vez (antes, el gif con todas
  juntas y los nombres ilegibles). **Ajustes > Animaciones**: el método se elige solo donde hay clip de Kimodo (antes
  el botón «kimodo» estaba deshabilitado sin explicación) y las animaciones del iso vienen todas marcadas.
- La `caja` de ejemplo se rehízo con TRELLIS.2 (antes era de Hunyuan3D-2, el motor viejo).
- La hoja de sprites lleva solo las animaciones que se renderizaron (las que hay conservan su orden y, con idle,
  caminata y salto, los índices 0-12).
- El `tema` de `moderno`, `moderno_juguete` y `semirealista` ya no dice "casual clothes, ... denim": los personajes
  salían casi siempre con jeans. `medieval` y `futurista` nombran materiales del mundo pero no la ropa (sin "armor
  panels"). Los assets ya hechos cambian recién al rehacer `imagen`.
- La vista de atrás de los vehículos (`vistas`) ya no pide un alerón.

## [0.2.0-alpha.1] - 2026-10-29

La UI en el navegador (`crisol ui`), con el editor de articulaciones y el personaje animado en 3D, y `crisol
deshacer`/`crisol renombrar`. La imagen Docker está en `ghcr.io/facundoalmon/assetcrisol:0.2.0-alpha.1`.

### Agregado
- **3D animado** en `crisol ui`: el personaje con su rig en el visor 3D, con la animación elegida al ritmo de las hojas.
  `blender` exporta `trabajo/animado.glb` (malla + rig + una animación por acción, IK horneado) y `animado.json` (el
  tiempo de cada cuadro de los sprites); el `.glb` también sale en Exportar > Modelo 3D. Barra para ir a un cuadro.
- Visores 3D de `crisol ui`: en el celular dos dedos acercan y mueven la cámara (antes giraban), doble toque o doble
  clic enfoca el punto tocado, y pantalla completa (en el iPhone, sobre toda la página).
- **Editor de articulaciones** en `crisol ui` (Resultado > Guía > Editar articulaciones): arrastrar los puntos del
  esqueleto sobre los renders de frente y de costado (o moverlos con las flechas), con deshacer. Guarda
  `modelo.articulaciones` (las de antes en `_articulaciones_previas`), redibuja `guia.png` sin Blender y marca el paso
  como hecho a mano, así Rig y animaciones queda para rehacer.
- `crisol deshacer <n> --paso <p> [--ver]`: borra lo que generó un paso (con `--ver`, solo lo lista), sin tocar el json
  ni las elecciones; `ultratex` vuelve a la malla del motor y `articulaciones` a las de antes. `crisol renombrar <n>
  --nuevo <m>`: la carpeta, `godot/<tipo>/<n>/` (archivos, rutas `res://` y nombres en escenas y metas; los `.import`
  se borran) y el `.blend`. Los dos se niegan si hay un paso de ese asset corriendo. En `crisol ui`: **Deshacer** junto
  al estado de cada paso (con la lista de lo que borra antes de confirmar) y el lápiz junto al nombre.
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
- `crisol ui`: **Exportar** en la pestaña Archivos y logs: grupos de archivos para marcar (con cuántos son y cuánto
  pesan) y un zip con lo marcado (`GET /api/assets/<n>/zip?grupos=...`). Las rutas de los assets solo aceptan nombres
  válidos (sin `..`). En el celular, la pestaña ya no se sale de la pantalla con nombres de logs largos.
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
- `crisol ui`: el reproductor iso, en las animaciones sin loop (golpe, patada, salto...), después de la primera pasada
  quedaba saltando entre los cuadros 0 y 1.
- `crisol ui`: "Mirá esto antes de seguir" seguía apareciendo después de elegir (la imagen, la malla o las
  texturas que pedía mirar el paso).
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

[Sin publicar]: https://github.com/facundoAlmon/AssetCrisol/compare/v0.4.0...main
[0.4.0]: https://github.com/facundoAlmon/AssetCrisol/releases/tag/v0.4.0
[0.3.0-alpha.1]: https://github.com/facundoAlmon/AssetCrisol/releases/tag/v0.3.0-alpha.1
[0.2.0-alpha.1]: https://github.com/facundoAlmon/AssetCrisol/releases/tag/v0.2.0-alpha.1
[0.1.0-alpha.1]: https://github.com/facundoAlmon/AssetCrisol/releases/tag/v0.1.0-alpha.1
