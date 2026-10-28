# Copia la entrada a la salida con la hora al principio de cada línea ("14:03:27 ..."): los logs de los pasos que lanza
# `crisol ui`. Corre en su propio proceso (no en el de la UI): si la UI se cierra, el paso sigue escribiendo acá.
import sys, time

entrada, salida = sys.stdin.buffer, sys.stdout.buffer
inicio = True
while True:
    trozo = entrada.read1(65536)
    if not trozo:
        break
    partes = trozo.split(b'\n')
    for i, p in enumerate(partes):
        if inicio and (p or i < len(partes) - 1):
            salida.write(time.strftime('%H:%M:%S ').encode())
        salida.write(p)
        if i < len(partes) - 1:
            salida.write(b'\n')
            inicio = True
        elif p:
            inicio = False
    salida.flush()
