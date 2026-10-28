# Contribuir a AssetCrisol

Gracias por querer sumar. Issues y PRs en **español o inglés**; el código, los comentarios y los mensajes del CLI
van en español. *Issues and PRs are welcome in English or Spanish; code, comments and CLI messages are in Spanish.*

## Principios (no se negocian en un PR)
- **Todo local y open source**: nada de servicios pagos ni APIs en la nube, ni para generar ni para probar.
- **La persona decide**: imagen, candidatos de malla y texturas. Ni la UI, ni el MCP, ni un agente eligen por ella.
- **Una generación por vez en la GPU** (16 GB): un paso nuevo que genera llama a `gpu.reservar`.
- Plataforma soportada: Linux + NVIDIA 16 GB+. Otras: PRs bienvenidos, sin soporte oficial por ahora.

## Antes de empezar
- Instalación: `./instalar.sh` o la imagen Docker (README > Instalación). `crisol doctor` dice si falta algo.
- Leé [CLAUDE.md](CLAUDE.md) aunque no uses un agente: tiene el mapa del código, los **contratos** que no hay que
  romper (orden de la hoja, direcciones iso, API del visual de Godot, nombres de huesos) y los problemas ya resueltos
  (y lo descartado: no reintentarlo sin un motivo nuevo).
- Para algo grande (un paso, un motor, un cambio de formato), abrí antes un issue con la propuesta.
- Mirá el [ROADMAP](ROADMAP.md): lo que está ahí ya tiene un camino pensado.

## Probar
Todo se prueba local (no hay CI):
- **Antes de cada PR** que toque Blender, sprites, iso, Godot o escenarios: `python3 tests/humo.py` (~3 min, usa la
  GPU para renderizar: no correrlo mientras hay una generación) o `--rapido` (~1,5 min). Corre sobre una copia
  temporal de `ejemplos/`.
- Cambios visuales: mirar el resultado (`preview.gif`, `preview_iso.gif`, `trabajo/revision.png`), no solo que no
  falle. Poné capturas en el PR.
- `instalar.sh`: `--plan` sobre una instalación hecha (no tiene que tocar nada) y, si cambia lo que instala, una
  instalación en limpio con una config de prueba (CLAUDE.md > Verificar cambios).
- Probá con datos temporales (otro `datos_dir` en una config de prueba), nunca sobre tus personajes.

## Qué tiene que traer un PR
- Una cosa por PR, con el porqué en la descripción.
- README **en español y en inglés** si cambia el comportamiento, y CLAUDE.md si cambia el mapa, un contrato o hay un
  gotcha nuevo. CHANGELOG en *Sin publicar*.
- Animaciones nuevas **al final** de la hoja (`anim.TODAS`, `armar_iso.NOMBRES`, README).
- Un modelo nuevo: su licencia en `docs/licencias.md` y `licencias.MODELOS`, y su instalación en `instalar.sh` y
  `doctor` (`MODELOS`/`NODOS`/`PASOS`).
- Nada generado en el repo (`personajes/`, `objetos/`, `escenarios/`, `movimientos/` de `datos_dir`), ni
  `config.json`, ni pesos de modelos. Los ejemplos de `ejemplos/` solo con mallas reducidas (soldar antes del
  Decimate: CLAUDE.md > Malla).
- Sin personajes ni marcas ajenas en ejemplos, capturas o docs.

## Licencia
AssetCrisol es GPL-3.0: lo que aportes se publica con esa licencia.
