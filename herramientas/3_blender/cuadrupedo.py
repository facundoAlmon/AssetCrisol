# Cuadrúpedos (perro, gato, caballo, vaca...): esqueleto, articulaciones estimadas de la malla y animaciones
# procedurales. Lo usa blender_main.py cuando modelo.esqueleto = "cuadrupedo" (receta `cuadrupedo`); el humanoide
# sigue en rig_lib.py + anim.py. Mismas convenciones: frente = -Y, pies en z=0, '.S' = lado L (+X) que se espeja a R.
# Huesos: root, hips (de la cadera hacia adelante), spine, chest, neck, head (hasta el hocico), tail.0-2 (si hay
# cola), y por pata (front = delanteras, back = traseras) <p>_upper, <p>_lower, <p>_foot con el IK en <p>_lower
# (objetivo <p>_ik, polo <p>_pole: atrás del codo en las delanteras, adelante de la rodilla en las traseras).
# Las animaciones usan las carpetas del humanoide (idle, caminar, saltar...) con sus mismos cuadros: la hoja y el
# juego las encuentran por nombre; las que no tiene (rodar, patada...) no salen en la hoja.
import math

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

import rig_lib

D = math.radians
PATAS = ('front', 'back')
# nombre: (padre, conectado, deforma), en orden de creación (el padre antes)
JERARQUIA = {
    'root': (None, False, False),
    'hips': ('root', False, True),
    'spine': ('hips', True, True),
    'chest': ('spine', True, True),
    'neck': ('chest', True, True),
    'head': ('neck', True, True),
    'tail.0': ('hips', False, True),
    'tail.1': ('tail.0', True, True),
    'tail.2': ('tail.1', True, True),
    'front_upper.S': ('chest', False, True),
    'front_lower.S': ('front_upper.S', True, True),
    'front_foot.S': ('front_lower.S', True, True),
    'front_ik.S': ('root', False, False),
    'front_pole.S': ('root', False, False),
    'back_upper.S': ('hips', False, True),
    'back_lower.S': ('back_upper.S', True, True),
    'back_foot.S': ('back_lower.S', True, True),
    'back_ik.S': ('root', False, False),
    'back_pole.S': ('root', False, False),
}
HUESOS_ANCLA = ['hips', 'chest', 'neck', 'head', 'front_foot.L', 'front_foot.R', 'back_foot.L', 'back_foot.R']


def _vertices(mesh):
    co = np.empty(len(mesh.data.vertices) * 3, dtype=np.float64)
    mesh.data.vertices.foreach_get('co', co)
    return co.reshape(-1, 3)


def orientar(mesh):
    """Gira la malla en Z para que el largo del cuerpo quede sobre Y y la cabeza hacia -Y (el frente). TRELLIS.2 y
    Pixal3D dejan el animal como venía en la imagen (de tres cuartos o de costado): el eje largo sale del análisis
    de componentes de la planta y la punta de la cabeza es la mitad con lo más alto (la cabeza va arriba del lomo;
    si no, `modelo.giro_grados` corrige después)."""
    V = _vertices(mesh)
    xy = V[:, :2] - V[:, :2].mean(axis=0)
    _, vecs = np.linalg.eigh(np.cov(xy.T))
    eje = vecs[:, -1]                                   # dirección de mayor varianza
    ang = math.atan2(eje[0], eje[1])                    # llevarla a +Y
    R = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
    xy = xy @ R.T
    alto = V[:, 2] > V[:, 2].min() + 0.9 * (V[:, 2].max() - V[:, 2].min())
    if xy[alto, 1].mean() > 0:                          # la cabeza quedó atrás: media vuelta
        ang += math.pi
    mesh.data.transform(Matrix.Rotation(ang, 4, 'Z'))
    print(f'[cuadrupedo] orientado: giro de {math.degrees(ang) % 360:.0f}° en Z (cabeza hacia -Y)')


def medidas(mesh, altura):
    """Lo que se mide de la malla (ya normalizada: pies en 0, centrada, cabeza hacia -Y): patas, panza, lomo,
    hocico y cola. Todo en unidades del modelo."""
    V = _vertices(mesh)
    x, y, z = V[:, 0], V[:, 1], V[:, 2]
    H = altura
    ymin, ymax = float(y.min()), float(y.max())
    largo = ymax - ymin
    bajo = V[z < 0.15 * H]
    if len(bajo) < 20:
        bajo = V[z < 0.3 * H]
    ys = np.sort(bajo[:, 1])
    gaps = np.diff(ys)
    i = int(gaps.argmax())
    corte = (ys[i] + ys[i + 1]) / 2 if gaps[i] > 0.03 * H else float(np.median(ys))
    M = {'H': H, 'ymin': ymin, 'ymax': ymax, 'largo': largo}
    for p, g in (('front', bajo[bajo[:, 1] < corte]), ('back', bajo[bajo[:, 1] >= corte])):
        if len(g) < 5:
            g = bajo
        der = g[g[:, 0] > 0]
        M[f'{p}_x'] = float(np.median(der[:, 0])) if len(der) else 0.12 * H
        M[f'{p}_y'] = float(np.median(g[:, 1]))
        M[f'{p}_punta'] = float(g[:, 1].min())
        M[f'{p}_talon'] = float(g[:, 1].max())
    xc = min(M['front_x'], M['back_x'])
    for p in PATAS:
        w = max(0.04 * largo, (M[f'{p}_talon'] - M[f'{p}_punta']) * 0.5)
        col = (np.abs(y - M[f'{p}_y']) < w) & (np.abs(x) < 0.4 * xc)
        panza = col & (z > 0.08 * H)
        M[f'{p}_panza'] = float(z[panza].min()) if panza.any() else 0.45 * H
        M[f'{p}_lomo'] = float(z[col].max()) if col.any() else 0.75 * H
    # el lomo de adelante puede quedar tapado por el cuello: el grosor del cuerpo sale de atrás
    grosor = max(0.1 * H, M['back_lomo'] - M['back_panza'])
    M['grosor'] = grosor
    for p in PATAS:
        M[f'{p}_columna'] = M[f'{p}_panza'] + 0.55 * grosor
        M[f'{p}_hombro'] = M[f'{p}_panza'] + 0.4 * grosor          # donde arranca la pata (adentro del cuerpo)
    # cabeza: el hocico es lo de más adelante; la cabeza, lo que está por encima del lomo de atrás y por delante de
    # las patas delanteras. La nuca (de donde gira) va atrás del centro de la cabeza y a un tercio de su alto: con la
    # mediana de una rebanada quedaba en la mandíbula (cabeza grande) y el hueso no salía del cráneo
    Lc = max(0.2 * largo, M['back_y'] - ymin)
    nariz = y < ymin + 0.03 * largo
    M['nariz_z'] = float(np.median(z[nariz]))
    cab = V[(z > M['back_lomo']) & (y < M['front_y'] + 0.05 * largo)]
    if len(cab) > 50:
        z0, z1 = float(cab[:, 2].min()), float(cab[:, 2].max())
        cy = float(cab[:, 1].mean())
        M['nuca'] = (min(cy + 0.25 * (float(cab[:, 1].max()) - cy), M['front_y']), z0 + 0.35 * (z1 - z0))
    else:
        yb = ymin + min(max(0.4 * (M['front_y'] - ymin), 0.12 * Lc), 0.35 * Lc)
        M['nuca'] = (yb, M['nariz_z'])
    # cola: lo que asoma bien atrás de la grupa
    grupa = M['back_y'] + 0.12 * Lc
    cola = V[y > grupa]
    M['cola'] = None
    if len(cola) > 50 and ymax - grupa > 0.05 * largo:
        base = (M['back_y'] + 0.06 * Lc, M['back_columna'] + 0.15 * grosor)
        punta = cola[cola[:, 1] > ymax - 0.04 * largo][:, 1:].mean(axis=0)
        pts = [base]
        for t in (1 / 3, 2 / 3):
            yt = base[0] + t * (punta[0] - base[0])
            cerca = cola[np.abs(cola[:, 1] - yt) < 0.03 * largo]
            pts.append((yt, float(np.median(cerca[:, 2])) if len(cerca) else base[1] + t * (punta[1] - base[1])))
        pts.append((float(punta[0]), float(punta[1])))
        M['cola'] = pts
    return M


def estimar_articulaciones(mesh, altura):
    """Esqueleto a partir de las medidas de la malla. Punto de partida: revisarlo con `crisol guia` y corregirlo en
    crisol ui (Guía > Editar articulaciones) o en modelo.articulaciones."""
    M = medidas(mesh, altura)
    H = M['H']
    P = {}
    yf, yb = M['front_y'], M['back_y']
    zf, zb = M['front_columna'], M['back_columna']
    P['root'] = ((0, 0, 0), (0, 0.3 * H, 0))
    medio = (yf + yb) / 2
    pecho = yf + 0.1 * (yb - yf)
    P['hips'] = ((0, yb, zb), (0, medio, (zb + zf) / 2))
    P['spine'] = (P['hips'][1], (0, pecho, zf))
    cruz = (0, yf - 0.05 * (yb - yf), zf + 0.1 * M['grosor'])
    P['chest'] = ((0, pecho, zf), cruz)
    nuca = (0, *M['nuca'])
    P['neck'] = (cruz, nuca)
    P['head'] = (nuca, (0, M['ymin'], M['nariz_z']))
    if M['cola']:
        c = M['cola']
        for i in range(3):
            P[f'tail.{i}'] = ((0, *c[i]), (0, *c[i + 1]))
    for p, s in (('front', 1), ('back', -1)):   # s: hacia dónde va la articulación del medio (+ = atrás)
        xp, yp = M[f'{p}_x'], M[f'{p}_y']
        zj = M[f'{p}_hombro']
        zw = (0.13 if p == 'front' else 0.28) * zj                 # muñeca / garrón
        zm = min(M[f'{p}_panza'], zw + 0.6 * (zj - zw)) if p == 'front' else zw + 0.55 * (zj - zw)
        ym = yp + s * 0.09 * zj                                    # codo atrás, rodilla adelante
        yw = yp + (0.0 if p == 'front' else 0.08 * zj)             # el garrón queda atrás de la pata
        punta = (xp, min(M[f'{p}_punta'] + 0.02 * zj, yw - 0.06 * zj), 0.02 * zj)
        P[f'{p}_upper.S'] = ((xp, yp, zj), (xp, ym, zm))
        P[f'{p}_lower.S'] = ((xp, ym, zm), (xp, yw, zw))
        P[f'{p}_foot.S'] = ((xp, yw, zw), punta)
        P[f'{p}_ik.S'] = P[f'{p}_foot.S']
        P[f'{p}_pole.S'] = ((xp, ym + s * 0.6 * zj, zm), (xp, ym + s * 0.7 * zj, zm))
    print(f'[cuadrupedo] largo {M["largo"]:.2f}, patas en y {yf:.2f} / {yb:.2f}, panza {M["front_panza"]:.2f}, '
          f'cola {"sí" if M["cola"] else "no"}')
    return completar(P)


def completar(P):
    """{nombre: (head, tail)} -> {nombre: (head, tail, padre, conectado, deforma)} en el orden de JERARQUIA."""
    return {n: (tuple(P[n][0]), tuple(P[n][1]), *JERARQUIA[n]) for n in JERARQUIA if n in P}


def desde_json(d, mesh, altura):
    """modelo.articulaciones ({nombre: [head, tail]}) sobre las estimadas: lo que no trae, sale de la malla."""
    J = estimar_articulaciones(mesh, altura)
    P = {n: (h, t) for n, (h, t, *_) in J.items()}
    P.update({n: tuple(v) for n, v in d.items() if n in JERARQUIA})
    for p in PATAS:   # el objetivo del IK es el pie y el polo sigue a la articulación del medio
        P[f'{p}_ik.S'] = P[f'{p}_foot.S']
        if f'{p}_upper.S' in d:
            m = P[f'{p}_upper.S'][1]
            ph, pt = P[f'{p}_pole.S']
            P[f'{p}_pole.S'] = ((m[0], ph[1], m[2]), (m[0], pt[1], m[2]))
    return completar(P)


def construir_rig(col, nombre, J):
    ad = bpy.data.armatures.new(nombre)
    arm = bpy.data.objects.new(nombre, ad)
    col.objects.link(arm)
    arm.show_in_front = True
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = ad.edit_bones
    for name, (h, t, parent, connect, deform) in J.items():
        variantes = [(name[:-2] + sd, s) for sd, s in (('.L', 1), ('.R', -1))] if name.endswith('.S') else [(name, 1)]
        for bn, s in variantes:
            b = eb.new(bn)
            b.head = (h[0] * s, h[1], h[2]); b.tail = (t[0] * s, t[1], t[2]); b.roll = 0
            if parent:
                b.parent = eb[parent.replace('.S', '.L' if s > 0 else '.R')]
                b.use_connect = connect
            b.use_deform = deform
    for p in PATAS:
        for sd in ('L', 'R'):
            eb[f'{p}_ik.{sd}'].roll = eb[f'{p}_foot.{sd}'].roll
    bpy.ops.object.mode_set(mode='POSE')
    pb = arm.pose.bones
    for p in PATAS:
        for sd in ('L', 'R'):
            ik = pb[f'{p}_lower.{sd}'].constraints.new('IK')
            ik.target = arm; ik.subtarget = f'{p}_ik.{sd}'
            ik.pole_target = arm; ik.pole_subtarget = f'{p}_pole.{sd}'
            ik.pole_angle = math.radians(-90); ik.chain_count = 2
            cr = pb[f'{p}_foot.{sd}'].constraints.new('COPY_ROTATION')
            cr.target = arm; cr.subtarget = f'{p}_ik.{sd}'
    for b in pb:
        b.rotation_mode = 'QUATERNION'
    bpy.ops.object.mode_set(mode='OBJECT')
    for p in PATAS:
        for sd in ('L', 'R'):
            a = rig_lib.angulo_polo(arm, sd, f'{p}_upper', f'{p}_lower', f'{p}_foot', f'{p}_ik', f'{p}_pole')
            print(f'[rig] polo de la pata {p} {sd}: {math.degrees(a):.1f}°')
    B = arm.data.bones
    arm['u'] = B['front_upper.L'].head_local.z      # unidad de las poses: el alto donde arranca la pata delantera
    return arm


# ---------------------------------------------------------------------------------------------
# Poses. Un dict, todo opcional; distancias en `u` (el alto del hombro), ángulos en grados en ejes del cuerpo
# (frente = -Y, arriba = +Z):
#   root: (dy, dz) todo el animal        rodar: giro sobre el largo del cuerpo (caer de costado)
#   hips: (dy, dz) el cuerpo, con las patas apoyadas (IK)     hips_rot / spine / chest: (x, y, z) (x + = bajar
#   la parte de adelante)   neck / head: x (+ = bajar el hocico)   tail: (arriba, costado)
#   pata / pata_FL / pata_FR / pata_BL / pata_BR: (dy, dz, flexión del pie: + = punta abajo)
# L = el lado lejano a la cámara en la vista lateral, R = el cercano.

def _local(arm, bone, v):
    return arm.data.bones[bone].matrix_local.to_3x3().inverted() @ Vector(v)


def _giro(arm, bone, x=0.0, y=0.0, z=0.0):
    """giro en ejes del cuerpo -> cuaternión en los ejes de reposo del hueso"""
    M = arm.data.bones[bone].matrix_local.to_3x3()
    return (M.inverted() @ Euler((D(x), D(y), D(z))).to_matrix() @ M).to_quaternion()


def _key(p, *paths, f):
    for path in paths:
        p.keyframe_insert(path, frame=f)


def _accion(arm, nombre):
    if arm.animation_data is None:
        arm.animation_data_create()
    vieja = bpy.data.actions.get(nombre)
    if vieja:
        bpy.data.actions.remove(vieja)
    act = bpy.data.actions.new(nombre)
    act.use_fake_user = True
    arm.animation_data.action = act
    for p in arm.pose.bones:
        p.rotation_mode = 'QUATERNION'; p.location = (0, 0, 0); p.rotation_quaternion = (1, 0, 0, 0)
        p.scale = (1, 1, 1)
    return act


def _pose(arm, P, fr, pitch):
    pb = arm.pose.bones
    u = arm['u']
    dy, dz = P.get('root', (0, 0))
    pb['root'].location = _local(arm, 'root', (0, dy * u, dz * u))
    pb['root'].rotation_quaternion = _giro(arm, 'root', 0, P.get('rodar', 0), 0)
    _key(pb['root'], 'location', 'rotation_quaternion', f=fr)
    dy, dz = P.get('hips', (0, 0))
    pb['hips'].location = _local(arm, 'hips', (0, dy * u, dz * u))
    pb['hips'].rotation_quaternion = _giro(arm, 'hips', *P.get('hips_rot', (0, 0, 0)))
    _key(pb['hips'], 'location', 'rotation_quaternion', f=fr)
    for b in ('spine', 'chest'):
        pb[b].rotation_quaternion = _giro(arm, b, *P.get(b, (0, 0, 0))); _key(pb[b], 'rotation_quaternion', f=fr)
    pb['neck'].rotation_quaternion = _giro(arm, 'neck', P.get('neck', 0))
    pb['head'].rotation_quaternion = _giro(arm, 'head', P.get('head', 0) + pitch)
    _key(pb['neck'], 'rotation_quaternion', f=fr); _key(pb['head'], 'rotation_quaternion', f=fr)
    arriba, costado = P.get('tail', (0, 0))
    for i in range(3):
        if f'tail.{i}' in pb:   # + arriba: la cola apunta atrás (+Y); girar en +X la sube
            t = pb[f'tail.{i}']
            t.rotation_quaternion = _giro(arm, t.name, arriba / 3, 0, costado / 3)
            _key(t, 'rotation_quaternion', f=fr)
    for p, letra in (('front', 'F'), ('back', 'B')):
        for sd in ('L', 'R'):
            dy, dz, flex = P.get(f'pata_{letra}{sd}', P.get('pata', (0, 0, 0)))
            b = pb[f'{p}_ik.{sd}']
            b.location = _local(arm, b.name, (0, dy * u, dz * u))
            b.rotation_quaternion = _giro(arm, b.name, flex)
            _key(b, 'location', 'rotation_quaternion', f=fr)


def _poses(arm, a, nombre, poses, paso=2, ciclo=False, piso=False):
    """Una Action con una pose clave cada `paso` frames; devuelve los frames clave (los que se renderizan)."""
    import anim
    act = _accion(arm, nombre)
    pitch = a.get('cabeza_arriba_grados', 0)
    frames = []
    for i, P in enumerate(poses):
        fr = 1 + i * paso
        _pose(arm, P, fr, pitch)
        frames.append(fr)
    for fr in frames if piso else []:
        anim._apoyar(arm, fr)
    if ciclo:
        _pose(arm, poses[0], 1 + len(poses) * paso, pitch)
        for fc in anim._fcurves(act):
            fc.modifiers.new('CYCLES')
    return frames


def idle(arm, a, pitch=None):
    _accion(arm, 'Idle')
    _pose(arm, {}, 1, a.get('cabeza_arriba_grados', 0) if pitch is None else pitch)
    return [1]


def _marcha(n, fases, apoyo, zancada, alto, flex):
    """{pata: [(dy, dz, flexión) por cuadro]} de un ciclo en el lugar: apoyada va de adelante (-dy) hacia atrás;
    en el aire vuelve adelante levantada (y con la punta abajo)."""
    out = {}
    for k, ph in fases.items():
        lista = []
        for i in range(n):
            t = (i / n + ph) % 1.0
            if t < apoyo:
                lista.append((-zancada + 2 * zancada * t / apoyo, 0.0, 0.0))
            else:
                v = (t - apoyo) / (1 - apoyo)
                s = math.sin(math.pi * v)
                lista.append((zancada - 2 * zancada * v, alto * s, flex * s))
        out[k] = lista
    return out


def caminar(arm, a, n=8):
    """Paso (secuencia lateral, como camina un perro o un caballo): trasera izquierda, delantera izquierda, trasera
    derecha, delantera derecha; cada pata apoya el 65 % del ciclo. El cuerpo sube y baja apenas, la cabeza
    acompaña y la cola se balancea."""
    zc, alto = a.get('zancada_patas', 0.3), a.get('levantar_pata', 0.16)
    patas = _marcha(n, {'BL': 0.0, 'FL': 0.25, 'BR': 0.5, 'FR': 0.75}, 0.65, zc, alto, 35)
    poses = []
    for i in range(n):
        t = i / n
        P = dict(hips=(0, -0.01 + 0.01 * math.cos(4 * math.pi * t)), spine=(0, 0, 3 * math.sin(2 * math.pi * t)),
                 head=2 * math.cos(4 * math.pi * t), tail=(5, 12 * math.sin(2 * math.pi * t)))
        for k, v in patas.items():
            P[f'pata_{k}'] = v[i]
        poses.append(P)
    return _poses(arm, a, 'Walk', poses, ciclo=True)


def correr(arm, a, n=12):
    """Galope en el lugar: primero las traseras, después las delanteras (cada par un poco desfasado); el lomo se
    recoge cuando las traseras pasan adelante y se estira cuando las delanteras se adelantan."""
    zc, alto = a.get('zancada_patas', 0.3) * 1.7, a.get('levantar_pata', 0.16) * 1.6
    patas = _marcha(n, {'BL': 0.0, 'BR': 0.08, 'FL': 0.5, 'FR': 0.58}, 0.38, zc, alto, 50)
    poses = []
    for i in range(n):
        s = math.sin(2 * math.pi * i / n)
        P = dict(hips=(0, 0.03 * math.sin(4 * math.pi * i / n)), hips_rot=(-7 * s, 0, 0), chest=(9 * s, 0, 0),
                 neck=-6 * s, head=4 * s, tail=(15 + 10 * s, 0))
        for k, v in patas.items():
            P[f'pata_{k}'] = v[i]
        poses.append(P)
    return _poses(arm, a, 'Run', poses, ciclo=True)


def respirar(arm, a, n=8):
    """Quieto en loop: respira (el pecho sube y baja), la cabeza acompaña y la cola se mueve despacio."""
    poses = []
    for i in range(n):
        s = math.sin(2 * math.pi * i / n)
        poses.append(dict(hips=(0, -0.004 + 0.004 * s), chest=(-1.5 * s, 0, 0), head=-1.5 * s,
                          tail=(3, 8 * s)))
    return _poses(arm, a, 'IdleLoop', poses, ciclo=True)


def saltar(arm, a):
    """Salto en el lugar (el juego mueve el cuerpo), 8 poses como el humanoide (la hoja usa 2-5 y el aterrizaje, 6):
    listo, agachado, despegue (se para de manos con las traseras empujando), subida (delanteras recogidas adelante,
    traseras estiradas atrás), cima (todo recogido), caída (estira las delanteras hacia el piso), aterrizaje y
    recuperación."""
    poses = [
        dict(),
        dict(hips=(0.04, -0.12), chest=(6, 0, 0), neck=-6, head=-4, tail=(-5, 0)),
        dict(hips_rot=(-22, 0, 0), neck=-8, pata_FL=(-0.1, 0.35, 35), pata_FR=(-0.08, 0.3, 30),
             pata_BL=(0.18, 0.04, -15), pata_BR=(0.16, 0.02, -15), tail=(10, 0)),
        dict(hips=(0, 0.05), hips_rot=(-12, 0, 0), pata_FL=(-0.2, 0.42, 45), pata_FR=(-0.18, 0.38, 40),
             pata_BL=(0.32, 0.16, -10), pata_BR=(0.3, 0.14, -10), tail=(20, 0)),
        dict(hips=(0, 0.05), pata=(0, 0.3, 40), pata_FL=(-0.12, 0.36, 45), pata_FR=(-0.1, 0.34, 45),
             tail=(15, 0)),
        dict(hips_rot=(12, 0, 0), neck=4, pata_FL=(-0.26, 0.12, 5), pata_FR=(-0.24, 0.1, 5),
             pata_BL=(0.2, 0.3, 25), pata_BR=(0.18, 0.28, 25), tail=(25, 0)),
        dict(hips=(-0.03, -0.1), hips_rot=(6, 0, 0), chest=(4, 0, 0), head=5, pata_FL=(-0.06, 0, 0),
             pata_BL=(0.05, 0.04, 0), tail=(10, 0)),
        dict(hips=(0, -0.03), tail=(5, 0)),
    ]
    return _poses(arm, a, 'Jump', poses)


def golpe(arm, a):
    """Ataque: muerde hacia adelante. Se carga atrás (cadera atrás y abajo, cabeza arriba), se lanza (el cuerpo
    adelante, el cuello estirado, las delanteras despegan), muerde (el hocico baja de golpe), sostiene y vuelve."""
    poses = [
        dict(hips=(0.06, -0.04), chest=(4, 0, 0), neck=-10, head=-10, tail=(20, 0)),
        dict(hips=(0.1, -0.08), chest=(8, 0, 0), neck=-6, head=-6, pata_FL=(0.04, 0, 0), pata_FR=(0.04, 0, 0),
             tail=(25, 0)),
        dict(hips=(-0.15, 0.02), chest=(-4, 0, 0), neck=14, head=8, pata_FL=(-0.2, 0.16, 20),
             pata_FR=(-0.18, 0.14, 20), pata_BL=(0.05, 0, 0), pata_BR=(0.05, 0, 0), tail=(15, 0)),
        dict(hips=(-0.2, 0.0), neck=22, head=20, pata_FL=(-0.26, 0.05, 10), pata_FR=(-0.24, 0.04, 10),
             pata_BL=(0.06, 0, 0), pata_BR=(0.06, 0, 0), tail=(15, 0)),
        dict(hips=(-0.2, 0.0), neck=20, head=26, pata_FL=(-0.26, 0, 0), pata_FR=(-0.24, 0, 0),
             pata_BL=(0.06, 0, 0), pata_BR=(0.06, 0, 0), tail=(12, 0)),
        dict(hips=(-0.06, -0.02), neck=6, head=2, pata_FL=(-0.1, 0, 0), pata_FR=(-0.08, 0, 0), tail=(8, 0)),
        dict(hips=(0, -0.01), tail=(5, 0)),
    ]
    return _poses(arm, a, 'Bite', poses)


def herido(arm, a):
    """Recibe un golpe de frente: se echa atrás con la cabeza arriba y la cola baja, y vuelve."""
    poses = [
        dict(hips=(0.08, -0.03), hips_rot=(-6, 0, 0), neck=-15, head=-12, tail=(-20, 0)),
        dict(hips=(0.1, -0.06), neck=-8, head=-6, pata_BL=(0.08, 0, 0), pata_BR=(0.06, 0, 0), tail=(-25, 0)),
        dict(hips=(0.04, -0.03), neck=2, head=4, tail=(-10, 0)),
    ]
    return _poses(arm, a, 'Hurt', poses)


def morir(arm, a):
    """Se le doblan las patas y cae de costado (último cuadro = acostado, con las patas sueltas). Cae sobre el lado
    cercano a la cámara (rodar negativo): mostrando el lomo; al revés quedaba panza arriba con las patas al frente."""
    poses = [
        dict(hips=(0.06, -0.04), neck=-14, head=-10, tail=(-20, 0)),
        dict(hips=(0, -0.16), chest=(8, 0, 0), neck=6, head=6, pata=(0, 0.04, 20), tail=(-25, 0)),
        dict(rodar=-30, hips=(0, -0.22), chest=(6, 0, 0), neck=10, head=8, pata=(0, 0.06, 25), tail=(-20, 0)),
        dict(rodar=-65, hips=(0, -0.18), neck=12, head=10, pata=(0.02, 0.08, 25), tail=(-10, 0)),
        dict(rodar=-88, hips=(0, -0.1), neck=8, head=6, pata=(0.04, 0.05, 15), tail=(0, 0)),
        dict(rodar=-90, hips=(0, -0.08), neck=6, head=4, pata=(0.04, 0.04, 10), tail=(0, 0)),
    ]
    return _poses(arm, a, 'Die', poses, piso=True)


# nombre (= carpeta de frames, las mismas del humanoide y con los mismos cuadros), función
TODAS = [('idle', idle), ('caminar', caminar), ('saltar', saltar), ('respirar', respirar), ('correr', correr),
         ('golpe', golpe), ('herido', herido), ('morir', morir)]
