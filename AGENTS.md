# AGENTS.md

Las instrucciones para agentes de este repo (reglas, cómo correr, mapa del código, contratos y gotchas del motor)
están en [CLAUDE.md](CLAUDE.md): sirven para cualquier agente, no solo Claude Code. La documentación para usuarios
está en [README.md](README.md).

Lo esencial:
- Una generación por vez en la GPU (revisar la cola de ComfyUI y `nvidia-smi` antes de `imagen`, `vistas`, `malla`,
  `ultratex`, `articulaciones` o `texturas`).
- No elegir por el usuario `imagen.elegida`, `malla.elegida` ni las texturas elegidas.
- Mirar los resultados visuales (hojas de candidatos, `preview.gif`, `revision.png`) antes de darlos por buenos.
- `pipeline.py` corre con el python3 del sistema; no importar `bpy` ni `torch` desde ahí.
- Los datos generados y `config.json` no se versionan.
