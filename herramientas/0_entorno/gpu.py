# Una generación por vez en la GPU: antes de un paso que genera (imagen, vistas, malla, ultratex, articulaciones,
# texturas) se mira si la GPU está ocupada y se espera (o se sale con GPU_OCUPADA). Ocupada =
#  - otro `crisol` de esta PC con un paso de GPU en curso (candado en el temporal del sistema),
#  - la cola de ComfyUI con trabajos (corriendo o pendientes), o
#  - un proceso CUDA que no sea el servidor de ComfyUI, Blender ni Godot (TRELLIS.2, otro programa...).
# ComfyUI con la cola vacía no cuenta aunque tenga modelos cargados: `malla` los descarga con POST /free.
# Al cortar el paso (SIGTERM de `crisol ui` al cancelar, o Ctrl+C) se vacía la cola de ComfyUI: lo que tiene es de
# este paso (estaba vacía al reservar y los demás esperan), y sin eso seguía generando con el paso ya muerto.
import fcntl, json, os, signal, subprocess, sys, tempfile, time, urllib.request
from salida import GPU_OCUPADA, salir
CANDADO = os.path.join(tempfile.gettempdir(), 'assetcrisol_gpu.lock')
NO_CUENTAN = ('blender', 'godot')
_candado = None   # el archivo abierto: el candado dura lo que el proceso


def _cola_comfyui(cfg):
    try:
        with urllib.request.urlopen(cfg['comfyui_url'] + '/queue', timeout=3) as r:
            q = json.load(r)
    except Exception:   # ComfyUI apagado (o sin url): no hay cola
        return None
    n = len(q.get('queue_running', [])) + len(q.get('queue_pending', []))
    return f'ComfyUI tiene {n} trabajo(s) en la cola' if n else None


def _cmdline(pid):
    try:
        with open(f'/proc/{pid}/cmdline', 'rb') as f:
            return f.read().replace(b'\0', b' ').decode(errors='replace').strip()
    except OSError:
        return ''


def _cwd(pid):
    try:
        return os.path.realpath(os.readlink(f'/proc/{pid}/cwd'))
    except OSError:
        return ''


def _procesos_cuda(cfg):
    """Procesos CUDA ajenos: [(pid, descripción)]. Sin nvidia-smi, ninguno."""
    try:
        r = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,process_name,used_memory', '--format=csv,noheader'],
                           capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return []
    comfy = os.path.realpath(cfg.get('comfyui_dir') or '/nonexistent')
    ajenos = []
    for linea in r.stdout.strip().splitlines():
        partes = [x.strip() for x in linea.split(',')]
        if len(partes) < 3 or not partes[0].isdigit():
            continue
        pid, nombre, mem = int(partes[0]), partes[1], partes[2]
        cmd = _cmdline(pid) or nombre
        if pid == os.getpid() or os.path.basename(nombre).lower().startswith(NO_CUENTAN):
            continue
        if 'main.py' in cmd and (nombre.startswith(comfy) or _cwd(pid).startswith(comfy)):   # el servidor: cuenta su cola
            continue
        que = 'TRELLIS.2 (una malla)' if 'generar_malla_trellis' in cmd else os.path.basename(nombre)
        ajenos.append((pid, f'{que}, pid {pid}, {mem}'))
    return ajenos


def ocupada(cfg):
    """Motivo por el que la GPU está ocupada, o None si está libre (sin contar el candado)."""
    motivo = _cola_comfyui(cfg)
    if motivo:
        return motivo
    ajenos = _procesos_cuda(cfg)
    return 'proceso en la GPU: ' + '; '.join(d for _, d in ajenos) if ajenos else None


def _tomar_candado():
    global _candado
    if _candado:
        return True
    f = open(CANDADO, 'a+')
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return False
    f.seek(0), f.truncate(), f.write(f'{os.getpid()} {" ".join(sys.argv[1:3])}\n'), f.flush()
    _candado = f
    return True


def _post(cfg, ruta, cuerpo):
    req = urllib.request.Request(cfg['comfyui_url'] + ruta, method='POST', headers={'Content-Type': 'application/json'},
                                 data=json.dumps(cuerpo).encode())
    urllib.request.urlopen(req, timeout=3).close()


def vaciar_comfyui(cfg):
    """Saca los pendientes de la cola de ComfyUI e interrumpe el que corre. Devuelve cuántos había."""
    try:
        with urllib.request.urlopen(cfg['comfyui_url'] + '/queue', timeout=3) as r:
            q = json.load(r)
        pendientes = [x[1] for x in q.get('queue_pending', [])]
        if pendientes:
            _post(cfg, '/queue', {'delete': pendientes})
        if q.get('queue_running'):
            _post(cfg, '/interrupt', {})
        return len(pendientes) + len(q.get('queue_running', []))
    except Exception:   # ComfyUI apagado: no hay nada que vaciar
        return 0


def _al_cortar(cfg):
    """SIGTERM y SIGINT: vaciar la cola de ComfyUI y salir como antes (SystemExit / KeyboardInterrupt)."""
    def cortar(sig, _frame):
        signal.signal(sig, signal.SIG_DFL)   # una segunda señal corta sin esperar
        n = vaciar_comfyui(cfg)
        if n:
            print(f'[gpu] cortado: saqué {n} trabajo(s) de la cola de ComfyUI', file=sys.stderr, flush=True)
        if sig == signal.SIGINT:
            raise KeyboardInterrupt
        sys.exit(128 + sig)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, cortar)


def _quien_tiene_candado():
    try:
        with open(CANDADO) as f:
            pid, _, paso = f.read().strip().partition(' ')
        return f'otro crisol ({paso}, pid {pid})'
    except OSError:
        return 'otro crisol'


def reservar(cfg, paso, esperar=True, cada=15):
    """Espera a que la GPU esté libre y la reserva para este proceso (los demás `crisol` esperan). Con esperar=False
    sale con GPU_OCUPADA si está ocupada."""
    anterior, desde = None, time.time()
    while True:
        motivo = None if _tomar_candado() else _quien_tiene_candado()
        motivo = motivo or ocupada(cfg)
        if not motivo:
            if anterior:
                print(f'[gpu] libre tras {time.time() - desde:.0f} s', flush=True)
            _al_cortar(cfg)
            return
        if not esperar:
            salir(GPU_OCUPADA, f'[{paso}] GPU ocupada: {motivo}')
        if motivo != anterior:
            print(f'[gpu] ocupada ({motivo}): espero antes de `{paso}` (Ctrl+C para cortar; '
                  f'--sin-esperar sale con código {GPU_OCUPADA})', flush=True)
            anterior = motivo
        time.sleep(cada)


# ---------- según la VRAM ----------
# Los valores por defecto de la malla están medidos en 16 GB. Con menos, se arranca más abajo en vez de esperar el OOM
# (TRELLIS.2 lo reintenta a menor resolución, pero cada intento cuesta minutos; Pixal3D no reintenta). Lo que el json
# fija (malla.resolucion) se respeta siempre. `vram_gb` en config.json pisa lo que dice nvidia-smi (para probar).
VRAM_REFERENCIA = 15.5   # GB: una placa de 16 GB reporta ~15,6-16
_vram = []


def vram_gb(cfg):
    """VRAM total de la primera GPU en GB (config `vram_gb` o nvidia-smi), o None si no se sabe."""
    if cfg.get('vram_gb'):
        return float(cfg['vram_gb'])
    if not _vram:
        try:
            r = subprocess.run(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'],
                               capture_output=True, text=True, timeout=15)
            _vram.append(int(r.stdout.split()[0]) / 1024)
        except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
            _vram.append(None)
    return _vram[0]


def poca_vram(cfg):
    g = vram_gb(cfg)
    return g is not None and g < VRAM_REFERENCIA


def resolucion_malla(cfg, m, motor, objeto):
    """malla.resolucion si está; si no, la de 16 GB (TRELLIS.2: 1024, objetos macizos 512; Pixal3D: 1536) o, con
    menos VRAM, una más baja (TRELLIS.2 512; Pixal3D 1024: a 512 falla). Avisa cuando baja."""
    if m.get('resolucion'):
        return m['resolucion']
    normal = 1536 if motor == 'pixal3d' else 512 if objeto else 1024
    if not poca_vram(cfg):
        return normal
    baja = 1024 if motor == 'pixal3d' else 512
    if baja < normal:
        print(f'[malla] {vram_gb(cfg):.0f} GB de VRAM: resolución {baja} (con 16 GB, {normal}); malla.resolucion la '
              'fija', flush=True)
    return baja
