# Roadmap

AssetCrisol está en desarrollo (0.x): el motor funciona y está probado con decenas de personajes y objetos, y la 0.4.0
(2026-11-04) es la primera versión pensada para que cualquiera la instale y la use. Acá se marca qué está hecho y qué
falta.

**Objetivo:** que cualquiera con Linux + NVIDIA de 16 GB pueda generar assets visuales para juegos 2D, 2.5D y 3D
(personajes animados, objetos, vehículos, escenarios) de punta a punta, a partir de una imagen o una descripción.
Dos tipos de usuario, los dos de primera:
- **una persona con conocimientos básicos de diseño**, desde una UI, sin tocar la terminal ni json;
- **un agente de IA** (Claude Code u otro) comandado por alguien sin conocimientos técnicos: el agente instala,
  corre los pasos y le muestra a la persona lo que tiene que decidir.

## Principios
- **Todo local y open source** en el código (GPL-3.0). Los modelos que se usan tienen sus propias licencias: algunos
  no permiten uso comercial; la receta por defecto prioriza la calidad y **avisa** cuando un asset sale de un modelo
  no comercial (ver [licencias](docs/licencias.md)).
- **La persona decide**: imagen, candidatos de malla, texturas. Ni la UI ni un agente eligen por ella.
- **Una generación por vez en la GPU** (con 16 GB, dos a la vez se quedan sin memoria o tardan 20 veces más).
- Código, comentarios y CLI en español; README, landing y docs en español e inglés.
- Plataforma soportada: Linux + NVIDIA 16 GB+. Otras: sin soporte por ahora, PRs bienvenidos.
- Sin telemetría. Versionado semántico + CHANGELOG.

**Orden de trabajo:** base → instalación → CLI para agentes → UI → salida 3D y otros motores → docs, landing y
lanzamiento (0.4.0). Lo que sigue: cerrar lo pendiente de la fase 7 (difusión, video con un agente, instalación desde
cero) y las mejoras del motor.

## 1. Base del repo
- [x] Licencia GPL-3.0 (coherente con Blender: los scripts que importan `bpy` se consideran GPL).
- [x] Motor publicado, sin el código heredado de motores viejos (Hunyuan3D-2 y sus retoques de textura).
- [x] `config.ejemplo.json` + `config.json` local (o `ASSETCRISOL_CONFIG`); `datos_dir`: dónde viven
      `personajes/`, `objetos/`, `escenarios/` y `movimientos/candidatos/`.
- [x] Comentarios, estilos y plantillas sin nombres de personajes ni marcas ajenas; estilo base `animacion3d`.
- [x] README (es/en), CLAUDE.md y AGENTS.md para el repo público.
- [x] Comando `crisol` (`crisol todo cris`) como entrada a `pipeline.py`.
- [x] Ejemplos versionados: Cris, sus objetos, una caja y dos escenarios (bosque, taller), probados con `tests/humo.py`.
- [x] Rehacer la caja de ejemplo con TRELLIS.2 (Z-Image seed 777, candidato trellis2, `modelo.alinear`).
- [x] Gif de demo para la portada del README (`ejemplos/personajes/cris/demo_acciones.gif`; también `demo_paseo` y
      `demo_direcciones`).
- [x] Textura de piso del bosque con un modelo de licencia comercial (Z-Image Turbo).

## Cris, la protagonista
La herrera joven del crisol: el ejemplo de los docs y los tests, el logo y la protagonista de la landing.
Elegida/o para no complicar el pipeline: humanoide de proporciones normales, ropa ajustada (mameluco, guantes, botas,
antiparras levantadas), pelo corto, brazos separados, simétrico. Con cada versión estrena lo nuevo.
- [x] Personaje: Z-Image (sin referencia) → Qwen (limpieza) → vistas → Pixal3D 4 vistas + UltraTex (seed 2) → rig →
      revisión (revés 0,2 %). En `ejemplos/personajes/cris`.
- [x] Objetos: crisol, yunque, martillo, horno de fundición, caja de herramientas. En `ejemplos/objetos/`.
- [x] Crisol del logo: el metal fundido no brilla (ningún motor lo pinta incandescente): `render.emisivo` en Blender
      (máscara por color de la textura). Falta, si hace falta, un halo (glare del compositor).
- [x] Vehículo: la camioneta de Cris (receta de vehículos). En `ejemplos/objetos/camioneta`.
- [x] Escenario: el taller (piso de piedra, camino y pared de ladrillo; Z-Image Turbo). En `ejemplos/escenarios/taller`.

## 2. Requisitos e instalación (humanos y agentes)
- [x] Requisitos explícitos (README > Requisitos en detalle): GPU, driver/CUDA, RAM, disco por nivel, tiempo de cada
      paso en la placa de referencia. Falta probar otras distribuciones.
- [x] **Imagen Docker** (`Dockerfile`, `docs/docker.md`): instalar.sh en el build, sin modelos (volumen que llena
      `docker run ... modelos`), corre como el dueño de `/datos`. Probada: Blender, TRELLIS.2 + UltraTex (EGL).
- [x] Publicada en GHCR (`ghcr.io/facundoalmon/assetcrisol`, pública): `0.1.0-alpha.1` + `latest`, con
      `docker/publicar.sh` (se construye acá: 23 GB no entran en los runners gratis de GitHub).
- [x] `instalar.sh` nativo: repos externos en commits fijos, venvs con `uv`, extensiones de TRELLIS.2 compiladas para
      la GPU, modelos con `hf download`; reconoce lo ya instalado y se puede volver a correr. Probado en limpio con
      el nivel completo (2026-10-28, 44 min): imagen con Z-Image y con Qwen, malla con TRELLIS.2 + UltraTex + Pixal3D,
      Blender y sprites.
- [x] Niveles (`--nivel`): **mínimo** ComfyUI (Qwen Image Edit, Z-Image Turbo) + TRELLIS.2 + Blender; **completo**
      + Pixal3D, UltraTex (FLUX.2 Klein), DWPose y escenarios; `--flux2` suma FLUX.2 Dev.
- [x] Kimodo en `instalar.sh` (`--kimodo`; el codificador de texto sale del espejo de Llama 3 de NousResearch, sin
      token).
- [x] Modelos gated (DINOv3, FLUX.2 Klein): `instalar.sh` pide el token y dice cuál falta aceptar.
- [x] `crisol doctor`: rutas, versiones, VRAM, nodos de ComfyUI y modelos; qué falta, cómo arreglarlo y qué pasos
      quedan deshabilitados. Legible y `--json`.
- [x] `docs/licencias.md` (y `docs/licenses.md`): componente → licencia → qué paso lo usa → si permite uso comercial.

## 3. CLI para agentes
- [x] `--json` en todos los pasos (archivos generados, qué mirar, estado después), códigos de salida (3 GPU ocupada,
      4 falta elegir, 5 falta un paso), sin preguntas interactivas.
- [x] `crisol estado [<n>]`: qué pasos están hechos, cuáles quedaron viejos y qué falta decidir.
- [x] Cola de GPU dentro del pipeline: antes de generar chequea otros `crisol`, ComfyUI y la GPU, y espera (o sale
      con `--sin-esperar`).
- [x] Recetas por tipo de asset (`crisol nuevo --receta`: humanoide, chibi, robot, juguete, objeto, vegetación,
      vehículo, escenario) que arman el json solas; `--descripcion` sin editar el json.
- [x] Avisos de licencia en el meta de cada asset (qué modelos lo hicieron, si es apto para venta).
- [x] Servidor MCP (`crisol mcp`) con las operaciones de alto nivel (recetas, crear, estado, correr/esperar, ver,
      elegir, ajustar), que devuelve las imágenes para mostrárselas a la persona.

## 4. UI
- [x] Web local servida por el mismo pipeline (`crisol ui`: se abre en el navegador; sin cuentas ni nube), sobre la CLI.
- [x] Flujo guiado: referencia o descripción → tipo y estilo → galería de candidatos para elegir → visor del
      resultado (gif, iso por dirección, retrato, hoja de revisión). Exportar = el paso `godot` (sin `--instalar`).
- [x] Cola de trabajos con progreso y tiempo estimado (duraciones medidas en la PC); logs a un clic.
- [x] Biblioteca de assets (miniaturas, estado, rehacer un paso o en lote).
- [x] Ajustes comunes sin json (seed, estilo, altura, animaciones y su método); el json queda como modo avanzado.
- [x] Visor 3D del `.glb` (three.js): el resultado y los candidatos de malla uno al lado del otro.
- [x] Candidatos de malla desde la UI (motor, seed, resolución, repintados con UltraTex; rehacer uno).
- [x] `crisol ui --host 0.0.0.0` (la red local); la cola retoma el paso que siguió corriendo con la UI cerrada.
- [x] Token para `--host 0.0.0.0` (cookie tras abrir la URL con `?token=`; desde 127.0.0.1, sin token).
- [x] Hora en los logs de los pasos (`trellis2.log`, `blender_<modo>.log`; `comfyui.log` no: ComfyUI sigue vivo).
- [x] Candidatos de malla como tarjetas con imagen (una vista por candidato que guarda `comparar`).
- [x] Pasar un clip de Kimodo a la biblioteca de movimientos desde la UI (`crisol clip`, biblioteca propia en
      `<datos_dir>/movimientos/`).

Errores vistos probando la UI (2026-10-28):
- [x] Al cancelar un trabajo que usaba ComfyUI no se liberó la cola (de ComfyUI).
- [x] Objeto: cambiar la malla elegida y rehacer `sprites` no usa la malla nueva.
- [x] El log del paso en curso no muestra nada hasta que termina (visto en `imagen`).
- [x] La hoja de candidatos de malla dice siempre "trellis (elegida)", aunque la elegida sea otra.
- [x] Ajustes: al cambiar la seed de la imagen, el botón de guardar sigue en gris.
- [x] Los tiempos estimados de la cola no se acercan a lo que tardan los pasos.
- [x] "Mirá esto antes de seguir" sale aunque ya se haya elegido (`Mirar` de `asset.mjs` muestra lo último que
      pidió mirar un paso durante una hora, sin mirar si ya no queda nada por decidir).

Mejoras pedidas (2026-10-28):
- [x] En el celular, secciones colapsables (hoy hay que bajar mucho).
- [x] Pasos y resultados numerados (mismo número el paso y su resultado) y las pestañas de resultados en ese orden.
- [x] Qué hace cada paso, a la vista (ayuda corta junto al paso).
- [x] Deshacer un paso: borra lo que generó.
- [x] Editor de articulaciones (moverlas sobre `guia.png`).
- [x] Articulaciones: casi siempre salen mal y al recalcular andan; recalcular sola en el paso (ver por qué la
      primera falla).
- [x] Cambiar el nombre de un asset.
- [x] Exportar: elegir qué archivos y bajarlos en un zip.
- [x] Elegir la resolución de los sprites.
- [x] Borrar el historial de la cola (todo o lo seleccionado).
- [x] Receta para cuadrúpedos (perro, gato, caballo, vaca...): esqueleto propio (`cuadrupedo.py`), articulaciones
      estimadas de la malla y 8 animaciones procedurales.

Revisión de animaciones y movimientos (2026-11-04):
- [x] Movimientos no se entendía: pasos a la vista, esqueleto animado por variante (también los candidatos sin hoja
      PNG), recorte marcando un instante, qué personajes usan cada clip; faltaba en la barra del celular.
- [x] Ajustes > Animaciones: el botón «kimodo» deshabilitado sin explicación en las animaciones sin clip.
- [x] Resultado > Animación: el gif con las 15 animaciones juntas y los nombres ilegibles → la hoja animada de a una.

Errores vistos armando el manual de la UI (2026-11-04):
- [x] Los campos numéricos (altura, seeds, duración y recorte de un clip) rearmaban el texto a medio escribir: "1.65"
      quedaba 651. Ahora guardan el texto mientras se escribe (`EntradaNumero` de `comunes.mjs`).
- [x] Con las candidatas de imagen a la vista, Resultado decía "Corré el primer paso".
- [x] "Mirá esto antes de seguir" repetía en miniatura las candidatas de *Te toca elegir*, y las hojas anchas (vistas)
      quedaban ilegibles en un cuadrado de 120 px.
- [x] Elegir un candidato de malla deja Malla 3D "desactualizado" y el botón dice *Siguiente: Malla 3D*: parece que va a
      generar de nuevo (minutos) y solo copia el elegido. Ahora `operaciones.elegir` lo copia al elegir.
- [ ] Pesos por zonas desde la UI: dibujar las cajas de `modelo.pesos_zonas` sobre la guía (hoy solo el json). Lo
      necesitó la exploradora del manual (manos que tocan los bolsillos del pantalón).
- [x] El estado de cada paso usa el lenguaje de la terminal ("imagen.elegida = 777 no existe, pero la malla ya está",
      "sin trabajo/imagen/vistas.png"): pasarlo a palabras para quien no conoce el json (los ejemplos lo muestran).
      En inglés, ese detalle y la descripción de los estilos (en Nuevo) salen en español. Los ejemplos dicen "4 candidata(s)
      en trabajo/imagen/candidatos.png" aunque ese archivo no viene.

## 5. Salida 3D y otros motores
- [x] Personaje como GLB con rig y animaciones (las mismas de los sprites): `trabajo/animado.glb`, también en el visor
      3D de `crisol ui`.
- [x] Polígonos para tiempo real + LODs, conservando UV y pesos: `trabajo/tiempo_real/<n>.glb` (LOD0, para Godot) y
      `<n>_lods.glb` (un esqueleto con `<n>_LOD0..2`; personajes 20/10/5 k triángulos con rig y animaciones, objetos
      10/5/2 k; textura 2048). Falta: vehículos (piezas separadas) y costuras de textura en el LOD más bajo.
- [x] Revisión de cerca: lo que en un sprite no se nota (codos, ropa que atraviesa, costuras de textura):
      `trabajo/revision_cerca.png` del paso `revisar`.
- [x] Esqueleto compatible en `tiempo_real/`: nombres de Mixamo (Unity Humanoid, Unreal, mapeo automático de Godot) o de
      `SkeletonProfileHumanoid` (`tiempo_real.huesos`), sin los auxiliares del IK (sin dedos ni cara). Falta probarlo
      dentro de Unity y Unreal (no están en esta PC).
- [x] Materiales completos en `tiempo_real/`: normales horneadas de la malla entera a cada LOD, ORM (rugosidad, metal y,
      con `"ao"`, oclusión) y emisión, de lo que el estilo arma con nodos (`tiempo_real.mapas`).
- [x] Sprites para otros motores: hoja + json estilo Aseprite/TexturePacker (Unity, Phaser, Defold...).

## 6. Robustez
- [x] Test de humo sin generación (`tests/humo.py`): `blender` → `sprites` → `iso` → `revisar` → `godot` de Cris, la caja,
      `tema` del bosque y el taller, e instancia las escenas en un proyecto Godot vacío (~3 min).
- [x] Errores claros cuando falta una herramienta o un modelo, en vez de un traceback.
- [ ] Ajustes según la VRAM detectada (hoy el pipeline asume 16 GB).

## 7. Documentación, landing y lanzamiento
- [x] Vitrina de los ejemplos (`docs/vitrina/`, imágenes con `herramientas/4_sprites/vitrina.py`), para la landing.
- [x] Landing en GitHub Pages: qué hace, galería antes/después, requisitos, "empezá acá" para personas y agentes.
      https://facundoalmon.github.io/AssetCrisol/ (`docs/index.html`, bilingüe; Pages desde `main` `/docs`).
- [x] Manual de `crisol ui` (`docs/ui.md`, `docs/ui.en.md`) con capturas que se rehacen con `tests/capturas_ui.py`
      (Playwright sobre el Chrome instalado; es/en, claro/oscuro, celular).
- [ ] Docs bilingües: instalación, primer asset, recetas por tipo, referencia de `personaje.json` y estilos,
      problemas conocidos, preguntas sobre licencias. Hoy todo está en el README (es/en), el manual de la UI y
      `docs/licencias.md`; falta decidir si se pasa a páginas aparte (en el sitio) o queda así.
- [x] Demo en Godot: `demo/` (Cris caminando por el taller iso entre sus objetos; `preparar.sh` instala los ejemplos).
- [x] Video corto de la UI (`docs/vitrina/img/ui_recorrido.mp4`, en la landing): grabado con el screencast de Chrome.
- [ ] Video corto con un agente (Claude Code eligiendo con la persona): se graba después del lanzamiento; la landing
      lo marca como pendiente en la sección del MCP.
- [ ] Prueba en limpio: instalar desde cero (Docker y nativo) siguiendo solo la doc, una vez una persona y otra un
      agente sin contexto. Hecha la primera parte con un agente (2026-11-04, sobre esta instalación: plan, doctor,
      ejemplos, demo, manual): 13 hallazgos de docs, arreglados salvo estos:
  - [x] `instalar.sh --plan` con todo instalado avisa que el destino no tiene lugar para ~135 GB y que va a completar
        rutas de config.json, aunque no va a instalar ni cambiar nada; no lista los modelos de DWPose ni rembg.
  - [ ] Falta la instalación desde cero de verdad (Docker y nativo, en otra PC o un disco vacío).
- [x] CONTRIBUTING, plantillas de issues (con `crisol doctor --json`), CHANGELOG. Issues en español o inglés.
- [x] Primera versión para usar: `v0.4.0` (2026-11-04; las anteriores eran alfas), con su imagen Docker.
- [ ] Post de lanzamiento (es/en) y difusión (Reddit, Show HN, itch.io, comunidades de gamedev, Discords de ComfyUI
      y Godot); después, un devlog por versión. Los borradores están escritos (fuera del repo); falta publicarlos.

## Mejoras del motor (en paralelo)
- [x] UltraTex con las vistas de costado (`malla.ultratex.costados`, opcional).
- [x] Recorte con margen antes de TRELLIS.2 (`malla.margen`, opcional).
- [x] Imagen sin referencia con Z-Image Turbo (segundos, Apache-2.0) + Qwen para limpiarla.
- [ ] Kimodo: decidir si `correr` pasa a recomendado; candidatos para respirar, herido, rodar y lanzar.
- [ ] Kimodo, traducción: muñeca de los golpes, cierre de brazos en torsos anchos, adaptación a chibis.
- [ ] Articulaciones de muñecos/juguetes (DWPose no los detecta): vistas de Qwen o Make-It-Animatable v2.
- [ ] Separar la seed de estructura y la de forma también en TRELLIS.2.
- [ ] Candidato `pixal3d` de los objetos a 1024 en vez de 1536: a 1536 tarda 1-8 min según el volumen (la subida
      domina); probar en 2-3 objetos si conserva la geometría que lo hace útil (el cofre).
- [ ] Pesos con SkinTokens/Puppeteer, solo si las opciones actuales dejan de alcanzar.
- [x] Rodilla siempre un poco adelante de la línea cadera-tobillo (con DWPose sobre piernas rectas el IK la doblaba
      para atrás al agacharse).
- [ ] Candidatos de UltraTex: la cara (ojos estrábicos, delineado) cambia mucho con `malla.ultratex.seed`; generar 2-3 seeds
      y armar una hoja de caras de cerca para elegir, como los candidatos de malla.
- [ ] Brillos pintados: UltraTex hornea en la textura las luces de sus vistas (ropa que parece lustrada); probar a
      sacarlas (delighting) o compensar con la rugosidad.
- [ ] Ropa: capas que se atraviesan a los costados (remera bajo un chaleco), la boca de un pantalón ancho al levantar la
      pierna y placas rígidas que se cruzan en golpes (robots).
- [ ] Animación nueva: saludar (mano en alto, de frente). Al final de la hoja (`anim.TODAS`, `armar_iso.NOMBRES`, README);
      probar procedural y Kimodo.
- [ ] Vehículos que no son autos: los prompts de `vistas` y la vista de atrás dicen "toy car" (luces traseras,
      alerón) y Qwen convierte una vagoneta en un auto; armarlos desde la descripción del objeto.
- [ ] Manos: siempre abiertas (el rig no tiene dedos); evaluar un puño por forma o huesos de dedos simples.
- [ ] Opciones dudosas: `modelo.simetria` y `render.oscuro_brillante` (probadas sin uso claro): documentar o sacar.

## Ideas para después
- Animación desde un video con MoCapAnything V2 (cualquier esqueleto, MIT): probado el 2026-11-04 con un cuadrúpedo y un
  humanoide; anda local (~10 GB de GPU) pero copia el tipo de movimiento y no el movimiento (peor que la caminata
  procedural de los cuadrúpedos y que Kimodo), y saca el fondo con RMBG-1.4 (no comercial). Esperar una versión mejor.
- Galería comunitaria de estilos y recetas.
- Tiempos medidos en otras placas (12 GB, 24 GB) para ampliar los requisitos con datos.
- Aviso de uso responsable: propiedad intelectual de personajes ajenos y fotos de personas reales.

## Descartado (y por qué)
- **CI en GitHub Actions**: todo se prueba local (`tests/humo.py` antes de cada PR); los runners gratis no tienen
  GPU y el proyecto no depende de servicios externos.
- **Re-texturizar con el pipeline de texturas de TRELLIS.2**: sale más oscuro y borroso que UltraTex.
- **Pixal3D con dos tres cuartos** (vehículos): las cámaras no son consistentes y aparecen fantasmas.
- **TRELLIS.2 a 1536**: el remesh no entra en 16 GB; simplificando antes sale limpio pero no mejor que 1024.
- **Mesh2Motion, UniRig, RigNet, MagicArticulate, AniGS**: o el encaje es a mano, o los superan SkinTokens/Puppeteer,
  o no dan una malla con rig.
- **Rigify, Auto-Rig Pro, Voxel Heat Diffuse, Rokoko**: manuales o pagos.
- **3D Print Toolbox, LODTailor, reconstrucción en quads**: no detectan las capas internas o no hacen falta para
  renderizar sprites (la salida 3D va a necesitar reducción de polígonos: ver fase 5).
- **Filtros automáticos de pesos "implausibles"** y mezclas bone heat + distancia: marcan miles de vértices buenos o
  dejan los brazos de los chibis como aletas. Los chibis con brazos fundidos al cuerpo se regeneran con brazos separados.

## Licencias de terceros
El repo no distribuye modelos. Resumen (detalle en [`docs/licencias.md`](docs/licencias.md)): TRELLIS.2, Pixal3D, rembg y
BiRefNet MIT; Qwen Image Edit y Z-Image Turbo Apache-2.0; FLUX.2 Dev (opcional) y FLUX.2 Klein no comerciales; DINOv3 con licencia propia
(gated); Kimodo: código Apache-2.0, pesos NVIDIA Open Model License (comercial).
