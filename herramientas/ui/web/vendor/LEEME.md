# Dependencias vendorizadas de la UI (sin npm ni build; se sirven tal cual)

| archivo | qué es | versión | licencia | de dónde |
|---|---|---|---|---|
| `preact-htm.mjs` | Preact 10 + hooks + htm en un módulo | htm 3.1.1 (`preact/standalone`) | MIT | https://unpkg.com/htm@3.1.1/preact/standalone.module.js |
| `bricolage-grotesque.woff2` | tipografía de los títulos (variable, latin) | @fontsource-variable/bricolage-grotesque 5.1.0 | OFL-1.1 | https://cdn.jsdelivr.net/npm/@fontsource-variable/bricolage-grotesque@5.1.0/files/bricolage-grotesque-latin-wght-normal.woff2 |
| `three/` | three.js (`three.module.min.js`) + `GLTFLoader.js`, `OrbitControls.js` y `BufferGeometryUtils.js` de `examples/jsm/`, para el visor 3D | three@0.160.0 | MIT (`three/LICENSE`) | https://cdn.jsdelivr.net/npm/three@0.160.0/ |

Los tres módulos de `examples/jsm/` importan `three` y `../utils/BufferGeometryUtils.js`: en la copia esos imports se reescribieron a `./three.module.min.js` y `./BufferGeometryUtils.js` (todo en `three/`, sin importmap). Lo único cambiado; al actualizar, repetir ese reemplazo.

Para actualizar: bajar la versión nueva a la misma ruta, cambiar esta tabla y probar `crisol ui`.
