# Clips de Kimodo (NPZ, esqueleto SOMA de 77 articulaciones) -> Action sobre el rig de rig_lib.py.
# Se toma de cada articulación su rotación global respecto de la T-pose de SOMA (el NPZ la guarda así) y se aplica
# a nuestro hueso (en brazos y piernas, después de alinear la pose A de la malla con la T-pose). La cadera se escala por el
# largo de la pierna y queda en el lugar; el IK de las piernas se lleva a donde quedó el pie del FK. Qué animaciones
# salen de clips lo decide metodos.py.
import math
import os
import numpy as np
from mathutils import Matrix, Vector

import anim, metodos

# hueso nuestro -> (articulación SOMA que lo gira, articulación hija que marca su dirección de reposo)
MAPA = {
    'hips': ('Hips', 'Spine1'), 'spine': ('Spine1', 'Spine2'), 'chest': ('Chest', 'Neck1'),
    'neck': ('Neck1', 'Head'), 'head': ('Head', 'HeadEnd'),
}
for _sd, _lado in (('L', 'Left'), ('R', 'Right')):
    MAPA.update({
        f'shoulder.{_sd}': (f'{_lado}Shoulder', f'{_lado}Arm'), f'upper_arm.{_sd}': (f'{_lado}Arm', f'{_lado}ForeArm'),
        f'forearm.{_sd}': (f'{_lado}ForeArm', f'{_lado}Hand'), f'hand.{_sd}': (f'{_lado}Hand', f'{_lado}HandMiddle1'),
        f'thigh.{_sd}': (f'{_lado}Leg', f'{_lado}Shin'), f'shin.{_sd}': (f'{_lado}Shin', f'{_lado}Foot'),
        f'foot.{_sd}': (f'{_lado}Foot', f'{_lado}ToeBase'),
    })
BRAZO = ('shoulder', 'upper_arm', 'forearm', 'hand')
PIERNA = ('thigh', 'shin')
CUADROS = metodos.CUADROS   # cuadros y loop de cada animación que puede salir de un clip
ACCIONES = {'caminar': 'Walk'}   # blender_main guarda el .blend con la Action 'Walk'
# Kimodo: y arriba, +z adelante, +x a la izquierda del personaje. Rig: z arriba, frente -Y, .L en +X.
M = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)


def _yaw(ang):
    c, s = math.cos(ang), math.sin(ang)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def _tiempos(d, J, fps, n, ciclo, desde, hasta):
    """Cuadros del clip a muestrear. En un ciclo sin `desde` se toma de un apoyo del pie izquierdo al siguiente
    (salteando el primero: el arranque desde quieto no es parte del ciclo). El apoyo se mide con la altura del
    tobillo: en `foot_contacts` el canal del talón derecho sale igual al de la punta izquierda."""
    T = len(d['posed_joints'])
    if ciclo and desde is None:
        y = d['posed_joints'][:, J['LeftFoot'], 1]
        talon = y < y.min() + 0.02
        apoyos = [i for i in range(1, T) if talon[i] and not talon[i - 1]]
        if len(apoyos) >= 3:
            desde, hasta = apoyos[1] / fps, apoyos[2] / fps
        elif len(apoyos) == 2:
            desde, hasta = apoyos[0] / fps, apoyos[1] / fps
    desde = 0.0 if desde is None else desde
    hasta = (T - 1) / fps if hasta is None else hasta
    paso = (hasta - desde) / (n if ciclo else max(n - 1, 1))
    return [min(T - 1, round((desde + i * paso) * fps)) for i in range(n)], (desde, hasta)


def clip(arm, a, accion, ruta, n, ciclo=False, desde=None, hasta=None, paso=2):
    """Action `accion` con `n` cuadros del clip `ruta` (NPZ de Kimodo + 'nombres'); devuelve los frames clave."""
    d = dict(np.load(ruta))
    J = {nm: i for i, nm in enumerate(d['nombres'])}
    fps = float(d.get('fps', 30))
    P = d['posed_joints'].astype(float)          # [T, J, 3] posiciones globales
    G = d['global_rot_mats'].astype(float)       # [T, J, 3, 3] rotación global respecto de la T-pose
    idx, ventana = _tiempos(d, J, fps, n, ciclo, desde, hasta)

    # dirección de reposo de cada hueso SOMA (en la T-pose): o = G^T (P_hija - P), constante en todo el clip
    reposo = {}
    for b, (j, h) in MAPA.items():
        o = G[0, J[j]].T @ (P[0, J[h]] - P[0, J[j]])
        reposo[b] = Vector(M @ o).normalized()

    # orientación media de la ventana -> el personaje mira a -Y (frente del rig)
    f = np.array([G[i, J['Hips']] @ [0, 0, 1] for i in idx]).mean(axis=0)
    Y = _yaw(-math.atan2(f[0], f[2]))
    R = M @ Y                                     # Kimodo -> rig
    # rotaciones: R @ G @ M.T (girar el mundo y pasar a ejes del rig). Con R @ G @ R.T el giro de la cadera no se
    # iba (conjugar por un giro vertical lo deja igual): el cuerpo quedaba girado ~5° y un pie miraba adentro.
    Mt = M.T

    B = arm.data.bones
    pb = arm.pose.bones
    largo_soma = (np.linalg.norm(P[0, J['LeftShin']] - P[0, J['LeftLeg']]) +
                  np.linalg.norm(P[0, J['LeftFoot']] - P[0, J['LeftShin']]))
    largo = B['thigh.L'].length + B['shin.L'].length
    k = largo / largo_soma
    # piso: el tobillo más bajo del clip (pie apoyado) queda a la altura del tobillo en reposo
    tobillo_min = min(P[:, J['LeftFoot'], 1].min(), P[:, J['RightFoot'], 1].min())
    dz = B['foot.L'].head_local.z - k * tobillo_min
    raiz = d['smooth_root_pos'].astype(float)

    act = anim._nueva_accion(arm, accion)
    # En los ciclos Kimodo lleva la cara arriba (caminar 18°, correr 24°, respecto de la T-pose; idle ~1°): se nivela
    # restando la media de la ventana, así la cabeza queda como en las procedurales (cabeza_arriba_grados).
    # animacion.cabeza_kimodo_grados: retoque extra solo en los clips (+ = bajar la cara).
    nivel = 0.0
    if ciclo:
        nivel = float(np.mean([math.degrees(math.asin(np.clip((G[t, J['Head']] @ [0, 0, 1])[1], -1, 1)))
                               for t in idx]))
    pitch = math.radians(a.get('cabeza_arriba_grados', 0) + a.get('cabeza_kimodo_grados', 0) + nivel)
    orden = ['root'] + list(MAPA)
    rest = {b.name: b.matrix_local.copy() for b in B}
    # Brazos y piernas: es en lo que difieren las poses de reposo (T-pose con piernas verticales contra pose A con las
    # piernas abiertas ~10°: sin alinearlas la caminata conservaba la apertura y los pies iban muy separados). En el
    # resto, alinear la dirección del hueso suma la diferencia de anatomía (Head->HeadEnd va adelante y arriba: la cara subía 33°;
    # el pie de SOMA tiene otra inclinación y la suela no quedaba plana).
    alinear = {b: (B[b].matrix_local.to_3x3().col[1].rotation_difference(reposo[b]).to_matrix()
                   if b.split('.')[0] in BRAZO + PIERNA else Matrix.Identity(3)) for b in MAPA}
    frames = []
    for i, t in enumerate(idx):
        fr = 1 + i * paso
        pose = {'root': rest['root']}
        for b in orden[1:]:
            par = B[b].parent.name
            cadena = pose[par] @ rest[par].inverted() @ rest[b]
            j = J[MAPA[b][0]]
            rot = Matrix((R @ G[t, j] @ Mt).tolist()) @ alinear[b] @ rest[b].to_3x3()
            cabeza = cadena.translation
            if b == 'hips':   # en el lugar: sin el avance de la raíz, con el vaivén de la cadera
                rel = P[t, j] - [raiz[t, 0], 0, raiz[t, 2]]
                cabeza = Vector(k * (R @ rel)) + Vector((0, 0, dz))
            m = Matrix.Translation(cabeza) @ rot.to_4x4()
            if b == 'head':
                m = m @ Matrix.Rotation(pitch, 4, 'X')
            pose[b] = m
            _poner(pb[b], cadena.inverted() @ m, fr)
        for sd in ('L', 'R'):
            # IK: el control del pie donde quedó el pie y el polo delante de la rodilla, en su plano de doblez
            pie = pose[f'foot.{sd}']
            _poner(pb[f'foot_ik.{sd}'], rest[f'foot_ik.{sd}'].inverted() @ pie, fr)
            cadera, rodilla, tobillo = (pose[f'thigh.{sd}'].translation, pose[f'shin.{sd}'].translation,
                                        pie.translation)
            n_ = rodilla - (cadera + tobillo) / 2
            if n_.length < 1e-3 * largo:
                n_ = pie.to_3x3().col[1]
            polo = rodilla + n_.normalized() * largo
            pr = rest[f'knee_pole.{sd}']
            _poner(pb[f'knee_pole.{sd}'], pr.inverted() @ (Matrix.Translation(polo) @ pr.to_3x3().to_4x4()), fr)
        frames.append(fr)
    if ciclo:
        for fc in anim._fcurves(act):
            fc.modifiers.new('CYCLES')
    print(f'[kimodo] {accion}: {ruta} cuadros {idx} (ventana {ventana[0]:.2f}-{ventana[1]:.2f} s, escala {k:.2f}'
          f', cabeza nivelada {nivel:.0f}°)')
    return frames


def todas(a):
    """anim.TODAS con las animaciones que van por Kimodo (metodos.metodo) armadas desde su clip de la biblioteca."""
    bib = metodos.biblioteca()
    lista = []
    for nombre, fn in anim.TODAS:
        if metodos.metodo(nombre, a, bib) == 'kimodo':
            c = bib[nombre]
            n, ciclo = CUADROS[nombre]
            ruta = metodos.ruta_clip(c)
            fn = (lambda arm, a, ruta=ruta, n=n, ciclo=ciclo, c=c, nombre=nombre:
                  clip(arm, a, ACCIONES.get(nombre, f'Kimodo_{nombre}'), ruta, n, ciclo, c.get('desde'), c.get('hasta')))
        lista.append((nombre, fn))
    return lista


def _poner(p, basis, fr):
    p.location = basis.translation
    q = basis.to_quaternion()
    if p.rotation_mode == 'QUATERNION':
        p.rotation_quaternion = q
        anim._key(p, 'location', 'rotation_quaternion', f=fr)
    else:
        p.rotation_euler = q.to_euler(p.rotation_mode)
        anim._key(p, 'location', 'rotation_euler', f=fr)
