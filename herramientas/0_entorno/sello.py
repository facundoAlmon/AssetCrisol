# La hora al principio de cada línea de un log ("14:03:27 ..."). Dos usos:
# - como programa (`python3 sello.py < entrada > log`): los logs de los pasos que lanza `crisol ui`. Corre en su
#   propio proceso: si la UI termina, el paso sigue. (comfyui.log no se sella: ComfyUI sigue vivo después del paso y,
#   si se cae el que sella, moriría al escribir.)
# - como módulo: `correr(cmd, log, ...)` lanza un subproceso y sella su salida desde el mismo proceso del paso
#   (trellis2.log, blender_<modo>.log): no hay un tercero que pueda caerse.
# Las barras de progreso que reescriben la línea con \r llevan la hora en cada actualización (después de cada \r):
# se escriben apenas llegan, aunque la línea no termine, y en una terminal se ven como antes.
import re, subprocess, sys, time

_CORTE = re.compile(rb'([\r\n])')


class Sello:
    """Copia trozos de bytes a `salida` (binaria) con la hora antes de cada línea o tramo de \r no vacío. Un error al
    escribir (disco lleno, log borrado) no corta nada: se sigue leyendo para que el que escribe no se trabe."""

    def __init__(self, salida):
        self.salida, self.inicio, self.roto = salida, True, False

    def escribir(self, trozo):
        if self.roto:
            return
        try:
            for t in _CORTE.split(trozo):
                if t in (b'\r', b'\n'):
                    self.salida.write(t)
                    self.inicio = True
                elif t:
                    if self.inicio:
                        self.salida.write(time.strftime('%H:%M:%S ').encode())
                        self.inicio = False
                    self.salida.write(t)
            self.salida.flush()
        except (OSError, ValueError):
            self.roto = True


def copiar(entrada, salida):
    """De `entrada` a `salida` (binarias), sellando, hasta que se cierre la entrada."""
    s = Sello(salida)
    while True:
        trozo = entrada.read1(65536)
        if not trozo:
            return
        s.escribir(trozo)


def correr(cmd, log, guardar=False, **kw):
    """subprocess.run con stdout y stderr juntos al archivo `log`, cada línea con su hora. Devuelve
    (código de salida, la salida sin sellar como texto si `guardar`, si no '')."""
    with open(log, 'wb') as f:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **kw)
        s, todo = Sello(f), []
        try:
            while True:
                trozo = proc.stdout.read1(65536)
                if not trozo:
                    break
                if guardar:
                    todo.append(trozo)
                s.escribir(trozo)
        finally:
            proc.stdout.close()
            proc.wait()
    return proc.returncode, b''.join(todo).decode('utf-8', 'replace')


if __name__ == '__main__':
    copiar(sys.stdin.buffer, sys.stdout.buffer)
