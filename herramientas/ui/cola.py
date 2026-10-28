# Cola de trabajos de la UI: corre los pasos de crisol de a uno (una generación por vez en la GPU; Blender también la
# usa con EEVEE). Cada trabajo es `crisol <args> --json` con la salida a <datos_dir>/.crisol_ui/trabajos/<id>.{json,log};
# la cola y el historial quedan en cola.json (sobreviven a un reinicio) y las duraciones reales en duraciones.json
# (para estimar el tiempo de los próximos). Cancelar mata el grupo de procesos del paso por su PID.
import json, os, re, signal, statistics, threading, time

import operaciones as op

# segundos aproximados en la placa de referencia (README > Requisitos en detalle), hasta tener duraciones medidas
BASE = {'imagen': 90, 'vistas': 60, 'malla': 360, 'ultratex': 240, 'guia': 30, 'articulaciones': 60, 'blender': 60,
        'sprites': 20, 'retrato': 20, 'iso': 30, 'anclas': 5, 'revisar': 20, 'godot': 5, 'comparar': 30,
        'texturas': 60, 'tema': 20, 'todo': 600, 'rehacer': 180, 'movimiento': 150}
BASE_TIPO = {('malla', 'objeto'): 720, ('malla', 'vehiculo'): 720, ('blender', 'objeto'): 20}
MAX_HISTORIAL = 200
MEDIDAS = 10             # duraciones que se guardan por paso y tipo


class Cola:
    def __init__(self, carpeta, env=None):
        self.carpeta = carpeta
        self.dir_trabajos = os.path.join(carpeta, 'trabajos')
        os.makedirs(self.dir_trabajos, exist_ok=True)
        self.env = env
        self.trabajos = []                 # en orden: historial, el que corre y los pendientes
        self.version = 0                   # sube con cada cambio (la UI lo mira por SSE)
        self.al_terminar = None            # callback(trabajo)
        self._cv = threading.Condition()
        self._procs = {}
        self._ids = 0
        self.duraciones = self._leer('duraciones.json', {})
        for t in self._leer('cola.json', []):
            if t['estado'] == 'corriendo':   # la UI se cerró con un paso en marcha: no se sabe cómo terminó
                t.update(estado='interrumpido', fin=t.get('fin') or time.time())
            self.trabajos.append(t)
            self._ids = max(self._ids, int(t['id'][1:]))
        threading.Thread(target=self._trabajar, daemon=True).start()

    def _leer(self, nombre, defecto):
        try:
            with open(os.path.join(self.carpeta, nombre)) as f:
                return json.load(f)
        except (OSError, ValueError):
            return defecto

    def _guardar(self):
        self.version += 1
        viejos = [t for t in self.trabajos if t['estado'] not in ('pendiente', 'corriendo')][:-MAX_HISTORIAL]
        if viejos:
            self.trabajos = [t for t in self.trabajos if t not in viejos]
        tmp = os.path.join(self.carpeta, 'cola.json.tmp')
        with open(tmp, 'w') as f:
            json.dump(self.trabajos, f, ensure_ascii=False)
        os.replace(tmp, os.path.join(self.carpeta, 'cola.json'))

    def estimado(self, paso, tipo):
        medidas = self.duraciones.get(f'{paso}|{tipo}') or self.duraciones.get(paso)
        if medidas:
            return round(statistics.median(medidas))
        return BASE_TIPO.get((paso, tipo), BASE.get(paso, 60))

    def agregar(self, args, nombre, tipo=None, titulo=None):
        """args: los de crisol sin --json (p. ej. ['malla', 'cris']). Devuelve el trabajo."""
        with self._cv:
            self._ids += 1
            t = {'id': f't{self._ids}', 'args': list(args), 'paso': args[0], 'nombre': nombre, 'tipo': tipo,
                 'titulo': titulo, 'estado': 'pendiente', 'creado': time.time(), 'inicio': None, 'fin': None,
                 'codigo': None, 'pid': None, 'estimado': self.estimado(args[0], tipo), 'resultado': None}
            self.trabajos.append(t)
            self._guardar()
            self._cv.notify_all()
            return t

    def buscar(self, tid):
        return next((t for t in self.trabajos if t['id'] == tid), None)

    def quitar(self, tid):
        """Saca un pendiente o cancela el que corre (SIGTERM al grupo del paso; SIGKILL si no sale en 10 s)."""
        with self._cv:
            t = self.buscar(tid)
            if t is None:
                raise KeyError(tid)
            if t['estado'] == 'pendiente':
                t.update(estado='cancelado', fin=time.time())
                self._guardar()
                return t
            proc = self._procs.get(tid)
            if t['estado'] != 'corriendo' or proc is None:
                raise ValueError(f'{tid} ya terminó')
            t['cancelando'] = True
            self._guardar()
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            return t

        def rematar():
            try:
                proc.wait(10)
            except Exception:  # noqa: BLE001 (TimeoutExpired)
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        threading.Thread(target=rematar, daemon=True).start()
        return t

    def ruta(self, tid, ext):
        return os.path.join(self.dir_trabajos, f'{tid}.{ext}')

    def log(self, tid, lineas=None):
        try:
            with open(self.ruta(tid, 'log'), errors='replace') as f:
                texto = f.read()
        except OSError:
            return ''
        return '\n'.join(texto.splitlines()[-lineas:]) if lineas else texto

    def corriendo(self):
        return next((t for t in self.trabajos if t['estado'] == 'corriendo'), None)

    def foto(self):
        return {'version': self.version, 'trabajos': self.trabajos, 'ahora': time.time()}

    def _trabajar(self):
        while True:
            with self._cv:
                while not any(t['estado'] == 'pendiente' for t in self.trabajos):
                    self._cv.wait()
                t = next(t for t in self.trabajos if t['estado'] == 'pendiente')
                t.update(estado='corriendo', inicio=time.time())
                proc = op.lanzar(t['args'], os.path.join(self.dir_trabajos, t['id']), env=self.env, start_new_session=True)
                t['pid'] = proc.pid
                self._procs[t['id']] = proc
                self._guardar()
            codigo = proc.wait()
            self._terminar(t, codigo)

    def _terminar(self, t, codigo):
        try:
            with open(self.ruta(t['id'], 'json')) as f:
                d = json.load(f)
        except (OSError, ValueError):
            d = None
        est = (d or {}).get('estado') or {}
        with self._cv:
            self._procs.pop(t['id'], None)
            fin = time.time()
            cancelado = t.pop('cancelando', False)
            t.update(fin=fin, codigo=codigo,
                     estado='cancelado' if cancelado else 'hecho' if codigo == 0 else 'fallo',
                     resultado=None if d is None else {
                         'ok': d.get('ok'), 'error': d.get('error'), 'mirar': d.get('mirar') or [],
                         'siguiente': est.get('siguiente'), 'decidir': [x['clave'] for x in est.get('decidir') or []]})
            if d is None and not cancelado:
                t['resultado'] = {'ok': False, 'error': f'terminó sin JSON (código {codigo}): ver el log'}
            if codigo == 0:   # lo que el paso esperó a la GPU (gpu.py: "[gpu] libre tras N s") no cuenta
                espera = sum(float(x) for x in re.findall(r'\[gpu\] libre tras (\d+) s', self.log(t['id'])))
                clave = f'{t["paso"]}|{t["tipo"]}'
                self.duraciones[clave] = (self.duraciones.get(clave, []) + [round(fin - t['inicio'] - espera, 1)])[-MEDIDAS:]
                with open(os.path.join(self.carpeta, 'duraciones.json'), 'w') as f:
                    json.dump(self.duraciones, f)
            self._guardar()
        if self.al_terminar:
            self.al_terminar(t)
