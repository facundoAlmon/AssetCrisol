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
  no comercial (ver [licencias](#licencias-de-terceros)).
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
- [ ] README (es/en), CLAUDE.md y AGENTS.md para el repo público.
- [ ] Comando `crisol` (`crisol todo cris`) como entrada a `pipeline.py`.
- [ ] Ejemplos versionados: la mascota (Cris), un objeto y un escenario; gifs de muestra (las hojas se regeneran).

## Mascota: Cris
La/el herrera/o joven del crisol: el ejemplo de los docs y los tests, el logo y el protagonista de la landing.
Elegida/o para no complicar el pipeline: humanoide de proporciones normales, ropa ajustada (mameluco, guantes, botas,
antiparras levantadas), pelo corto, brazos separados, simétrico. Con cada versión estrena lo nuevo.
- [ ] Personaje: imagen (candidatos) → vistas → malla → rig → revisión.
- [ ] Objetos: el crisol con metal brillando (logo), yunque, martillo, horno de fundición, caja de herramientas.
- [ ] Vehículo (opcional): vagoneta minera o carretilla.
- [ ] Escenario: el taller (piso de ladrillo o piedra, pared de ladrillo, paleta cálida).

## 2. Requisitos e instalación (humanos y agentes)
- [ ] Requisitos explícitos: GPU y VRAM, driver/CUDA, RAM, disco por nivel, distribuciones probadas, tiempo de cada
      paso en la placa de referencia (RTX de 16 GB).
- [ ] **Imagen Docker** publicada en GHCR (nvidia-container-toolkit), sin modelos: van en un volumen que llena un
      script. Camino recomendado.
- [ ] `instalar.sh` nativo como alternativa. Repos externos en commits fijos, modelos con `hf download` a una caché
      configurable.
- [ ] Niveles:
  - **mínimo:** ComfyUI (Qwen Image Edit) + TRELLIS.2 + Blender → animación procedural, sprites y Godot;
  - **completo:** + Pixal3D, UltraTex (FLUX.2 Klein), DWPose, Kimodo, FLUX.2 Dev.
- [ ] Modelos gated (DINOv3, FLUX.2 Klein, el codificador de texto de Kimodo): cómo aceptarlos en Hugging Face.
- [ ] `crisol doctor`: rutas, versiones, VRAM, nodos de ComfyUI y modelos; qué falta, cómo arreglarlo y qué pasos
      quedan deshabilitados. Legible y `--json`.
- [ ] `docs/licencias.md`: componente → licencia → qué paso lo usa → si permite uso comercial.

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
- [ ] Tests de humo sin GPU (`blender` → `sprites` → `iso` → `godot` sobre un modelo de ejemplo) en GitHub Actions.
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
- [ ] Kimodo: decidir si `correr` pasa a recomendado; candidatos para respirar, herido, rodar y lanzar.
- [ ] Kimodo, traducción: muñeca de los golpes, cierre de brazos en torsos anchos, adaptación a chibis.
- [ ] Articulaciones de muñecos/juguetes (DWPose no los detecta): vistas de Qwen o Make-It-Animatable v2.
- [ ] Separar la seed de estructura y la de forma también en TRELLIS.2.
- [ ] Pesos con SkinTokens/Puppeteer, solo si las opciones actuales dejan de alcanzar.

## Ideas para después
- Galería comunitaria de estilos y recetas.
- Tiempos medidos en otras placas (12 GB, 24 GB) para ampliar los requisitos con datos.
- Aviso de uso responsable: propiedad intelectual de personajes ajenos y fotos de personas reales.

## Licencias de terceros
El repo no distribuye modelos. Resumen (detalle en `docs/licencias.md` cuando esté): TRELLIS.2, Pixal3D, rembg y
BiRefNet MIT; Qwen Image Edit Apache-2.0; FLUX.2 Dev y FLUX.2 Klein no comerciales; DINOv3 con licencia propia
(gated); Kimodo: código Apache-2.0, pesos a verificar.
