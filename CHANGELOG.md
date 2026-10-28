# Changelog

Los cambios de cada versión de AssetCrisol, del más nuevo al más viejo. Versionado semántico; mientras sea 0.x,
cualquier versión puede cambiar el formato de `personaje.json` o de las hojas (se avisa acá).
*English: each version's changes, newest first. Semantic versioning; while on 0.x, any version may change the
`personaje.json` or sprite-sheet format (noted here).*

## [Sin publicar]

### Agregado
- **Recetas por tipo**: `crisol nuevo <n> --receta humanoide|chibi|robot|juguete|objeto|vegetacion|vehiculo|escenario`
  arma el json con lo que anda para cada tipo (`plantilla/recetas/`); `--descripcion` completa `imagen.descripcion`
  sin editar el json. `--objeto`, `--vehiculo` y `--escenario` siguen como atajos.
- **Servidor MCP** (`crisol mcp`, por stdio, con `uv`): `recetas`, `crear`, `estado`, `correr`/`esperar`, `ver`,
  `elegir`, `ajustar` y `doctor`, con las imágenes para mostrarle a la persona (README > Para agentes de IA).
- `instalar.sh --kimodo`: Kimodo para `crisol movimiento` (~19 GB, en CPU, sin token de Hugging Face).
- `crisol doctor` revisa `uv` (opcional, para `crisol mcp`).

### Cambiado
- `plantilla/vehiculo.json` pasó a `plantilla/recetas/vehiculo.json`.
- Los tiempos de Pixal3D en objetos (README): el candidato `pixal3d` a 1536 tarda 1-8 min según el volumen.

### Arreglado
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
