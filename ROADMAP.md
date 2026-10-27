# Roadmap

AssetCrisol está en construcción: el motor funciona y está probado con decenas de personajes y objetos, y la v0.1 es el
trabajo de convertirlo en algo que cualquiera pueda instalar y usar. Acá se marca qué está hecho y qué falta.

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

**Orden de trabajo:** base → instalación → CLI para agentes → UI → salida 3D y otros motores → docs, landing y v0.1.

## 1. Base del repo
- [x] Licencia GPL-3.0 (coherente con Blender: los scripts que importan `bpy` se consideran GPL).
- [x] Motor publicado, sin el código heredado de motores viejos (Hunyuan3D-2 y sus retoques de textura).
- [x] `config.ejemplo.json` + `config.json` local (o `ASSETCRISOL_CONFIG`); `datos_dir`: dónde viven
      `personajes/`, `objetos/`, `escenarios/` y `movimientos/candidatos/`.
- [x] Comentarios, estilos y plantillas sin nombres de personajes ni marcas ajenas; estilo base `animacion3d`.
- [x] README (es/en), CLAUDE.md y AGENTS.md para el repo público.
- [x] Comando `crisol` (`crisol todo cris`) como entrada a `pipeline.py`.
- [x] Ejemplos versionados: un personaje (Cris), un objeto (caja) y un escenario (bosque), probados desde un clon limpio.
- [ ] Rehacer la caja de ejemplo con TRELLIS.2 (la malla actual salió del motor viejo, Hunyuan3D-2).
- [x] Gif de demo para la portada del README (`ejemplos/personajes/cris/demo_acciones.gif`; también `demo_paseo` y
      `demo_direcciones`).
- [x] Textura de piso del bosque con un modelo de licencia comercial (Z-Image Turbo).

## Cris, la protagonista
La herrera joven del crisol: el ejemplo de los docs y los tests, el logo y la protagonista de la landing.
Elegida/o para no complicar el pipeline: humanoide de proporciones normales, ropa ajustada (mameluco, guantes, botas,
antiparras levantadas), pelo corto, brazos separados, simétrico. Con cada versión estrena lo nuevo.
- [x] Personaje: Z-Image (sin referencia) → Qwen (limpieza) → vistas → Pixal3D 4 vistas + UltraTex (seed 2) → rig →
      revisión (revés 0,2 %). En `ejemplos/personajes/cris`.
- [ ] Objetos: el crisol con metal brillando (logo), yunque, martillo, horno de fundición, caja de herramientas.
- [ ] Vehículo (opcional): vagoneta minera o carretilla.
- [x] Escenario: el taller (piso de piedra, camino y pared de ladrillo; Z-Image Turbo). En `ejemplos/escenarios/taller`.

## 2. Requisitos e instalación (humanos y agentes)
- [ ] Requisitos explícitos: GPU y VRAM, driver/CUDA, RAM, disco por nivel, distribuciones probadas, tiempo de cada
      paso en la placa de referencia (RTX de 16 GB).
- [ ] **Imagen Docker** publicada en GHCR (nvidia-container-toolkit), sin modelos: van en un volumen que llena un
      script. Camino recomendado.
- [ ] `instalar.sh` nativo como alternativa. Repos externos en commits fijos, modelos con `hf download` a una caché
      configurable.
- [ ] Niveles:
  - **mínimo:** ComfyUI (Qwen Image Edit, Z-Image Turbo) + TRELLIS.2 + Blender → animación procedural, sprites y Godot;
  - **completo:** + Pixal3D, UltraTex (FLUX.2 Klein), DWPose, Kimodo, FLUX.2 Dev.
- [ ] Modelos gated (DINOv3, FLUX.2 Klein, el codificador de texto de Kimodo): cómo aceptarlos en Hugging Face.
- [x] `crisol doctor`: rutas, versiones, VRAM, nodos de ComfyUI y modelos; qué falta, cómo arreglarlo y qué pasos
      quedan deshabilitados. Legible y `--json`.
- [x] `docs/licencias.md` (y `docs/licenses.md`): componente → licencia → qué paso lo usa → si permite uso comercial.

## 3. CLI para agentes
- [ ] `--json` en todos los pasos (estado, archivos generados, avisos), códigos de salida claros, sin preguntas
      interactivas.
- [ ] `crisol estado <n>`: qué pasos están hechos y qué falta decidir.
- [ ] Cola de GPU dentro del pipeline: antes de generar chequea ComfyUI y la GPU, y espera o avisa.
- [ ] Recetas por tipo de asset (humanoide, chibi, objeto, vehículo, escenario) que arman el json solas.
- [ ] Avisos de licencia en el meta de cada asset (qué modelos lo hicieron, si es apto para venta).
- [ ] Servidor MCP con las operaciones de alto nivel (crear, listar candidatos, elegir, generar, exportar), que
      devuelva las imágenes para mostrárselas a la persona.

## 4. UI
- [ ] Web local servida por el mismo pipeline (se abre en el navegador; sin cuentas ni nube), sobre la CLI.
- [ ] Flujo guiado: referencia o descripción → tipo y estilo → galería de candidatos para elegir → visor del
      resultado (gif, iso por dirección, retrato, hoja de revisión) → exportar.
- [ ] Cola de trabajos con progreso y tiempo estimado; logs a un clic.
- [ ] Biblioteca de assets (miniaturas, estado, rehacer un paso).
- [ ] Ajustes comunes sin json (seed, estilo, altura, animaciones); el json queda como modo avanzado.

## 5. Salida 3D y otros motores
- [ ] Personaje como GLB con rig y animaciones (las mismas de los sprites).
- [ ] Polígonos para tiempo real (p. ej. 10-30 k caras) + LODs, conservando UV y pesos (hoy salen de 100-200 k).
- [ ] Revisión de cerca: lo que en un sprite no se nota (codos, ropa que atraviesa, costuras de textura).
- [ ] Esqueleto compatible: mapeo a Mixamo, Humanoid de Unity y `SkeletonProfileHumanoid` de Godot (sin dedos ni cara).
- [ ] Materiales completos (normal, AO, metal) como opción.
- [ ] Sprites para otros motores: hoja + json estilo Aseprite/TexturePacker (Unity, Phaser, Defold...).

## 6. Robustez
- [x] Test de humo sin generación (`tests/humo.py`): `blender` → `sprites` → `iso` → `revisar` → `godot` de Cris, la caja,
      `tema` del bosque y el taller, e instancia las escenas en un proyecto Godot vacío (~3 min).
- [ ] Correrlo en GitHub Actions (Blender headless sin GPU: probar EEVEE por software o Workbench).
- [ ] Errores claros cuando falta una herramienta o un modelo, en vez de un traceback.
- [ ] Ajustes según la VRAM detectada (hoy el pipeline asume 16 GB).

## 7. Documentación, landing y v0.1
- [ ] Landing en GitHub Pages: qué hace, galería antes/después, requisitos, "empezá acá" para personas y agentes.
- [ ] Docs bilingües: instalación, primer asset, recetas por tipo, referencia de `personaje.json` y estilos,
      problemas conocidos, preguntas sobre licencias.
- [ ] Demos: proyecto Godot de ejemplo (Cris caminando por el taller iso) y videos cortos con la UI y con un agente.
- [ ] Prueba en limpio: instalar desde cero (Docker y nativo) siguiendo solo la doc, una vez una persona y otra un
      agente sin contexto.
- [ ] CONTRIBUTING, plantillas de issues (con `crisol doctor --json`), CHANGELOG. Issues en español o inglés.
- [ ] Tag `v0.1`.
- [ ] Post de lanzamiento (es/en) y difusión (Reddit, Show HN, itch.io, comunidades de gamedev, Discords de ComfyUI
      y Godot); después, un devlog por versión.

## Mejoras del motor (en paralelo)
- [x] UltraTex con las vistas de costado (`malla.ultratex.costados`, opcional).
- [x] Recorte con margen antes de TRELLIS.2 (`malla.margen`, opcional).
- [x] Imagen sin referencia con Z-Image Turbo (segundos, Apache-2.0) + Qwen para limpiarla.
- [ ] Kimodo: decidir si `correr` pasa a recomendado; candidatos para respirar, herido, rodar y lanzar.
- [ ] Kimodo, traducción: muñeca de los golpes, cierre de brazos en torsos anchos, adaptación a chibis.
- [ ] Articulaciones de muñecos/juguetes (DWPose no los detecta): vistas de Qwen o Make-It-Animatable v2.
- [ ] Separar la seed de estructura y la de forma también en TRELLIS.2.
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
- [ ] Manos: siempre abiertas (el rig no tiene dedos); evaluar un puño por forma o huesos de dedos simples.
- [ ] Opciones dudosas: `modelo.simetria` y `render.oscuro_brillante` (probadas sin uso claro): documentar o sacar.

## Ideas para después
- Galería comunitaria de estilos y recetas.
- Tiempos medidos en otras placas (12 GB, 24 GB) para ampliar los requisitos con datos.
- Aviso de uso responsable: propiedad intelectual de personajes ajenos y fotos de personas reales.

## Descartado (y por qué)
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
