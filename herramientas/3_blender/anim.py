# Animaciones procedurales sobre el rig de rig_lib.py (adaptadas de blender/build_walk.py y build_jump.py).
# Cada función crea una Action nueva y devuelve la lista de frames a renderizar.
import math
import bpy
from mathutils import Matrix, Vector

D = math.radians


def _nueva_accion(arm, nombre):
    if arm.animation_data is None:
        arm.animation_data_create()
    old = bpy.data.actions.get(nombre)
    if old:
        bpy.data.actions.remove(old)
    act = bpy.data.actions.new(nombre)
    act.use_fake_user = True
    arm.animation_data.action = act
    for p in arm.pose.bones:
        p.rotation_mode = 'XYZ'; p.location = (0, 0, 0); p.rotation_euler = (0, 0, 0); p.scale = (1, 1, 1)
    for sd in ('L', 'R'):  # el brazo se gira en ejes del cuerpo (ver _brazo)
        ua = arm.pose.bones[f'upper_arm.{sd}']
        ua.rotation_mode = 'QUATERNION'; ua.rotation_quaternion = (1, 0, 0, 0)
    return act


def _brazo(arm, sd, x, ap, f):
    """Gira el brazo en ejes del cuerpo, no del hueso: primero lo abre `ap` grados en el plano frontal (+ = hacia
    afuera, respecto del reposo) y después lo balancea `x` grados alrededor del eje lateral (- = adelante/arriba).
    En ejes del hueso (que en la pose A está inclinado ~23°) el balanceo describe un cono: atrás el brazo se abre
    (alas al correr) y adelante cruza por delante del cuerpo."""
    s = 1 if sd == 'L' else -1
    q = Matrix.Rotation(D(x), 3, 'X') @ Matrix.Rotation(-D(ap) * s, 3, 'Y')      # en espacio del rig
    r = arm.data.bones[f'upper_arm.{sd}'].matrix_local.to_3x3()
    ua = arm.pose.bones[f'upper_arm.{sd}']
    ua.rotation_quaternion = (r.inverted() @ q @ r).to_quaternion()
    _key(ua, 'rotation_quaternion', f=f)


def _fcurves(act):
    if hasattr(act, 'fcurves'):
        return list(act.fcurves)
    return [fc for layer in act.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]


def _local(arm, bone, v):
    """desplazamiento en ejes mundo -> espacio local de reposo del hueso"""
    return arm.data.bones[bone].matrix_local.to_3x3().inverted() @ Vector(v)


def cierre_brazos(arm, a):
    """Grados que se cierran los brazos (hacia el cuerpo) en todas las poses. La malla sale en pose A (el brazo a
    ~23° del cuerpo) y las animaciones suman su apertura encima: con brazos largos quedan muy separados. Se mide en
    reposo el hueco entre el brazo y el torso a la altura del codo y de la muñeca y se cierra lo que deja 3 cm de
    margen (tope 20°); `animacion.cerrar_brazos_grados` lo fuerza. Se calcula una vez y queda en el rig."""
    if a.get('cerrar_brazos_grados') is not None:
        return float(a['cerrar_brazos_grados'])
    if 'cierre_brazos' in arm:
        return arm['cierre_brazos']
    mesh = next(o for o in arm.children if o.type == 'MESH')
    k = arm.get('escala_plantilla', 1.0)
    nom = {g.index: g.name for g in mesh.vertex_groups}
    dom = [nom[max(v.groups, key=lambda g: g.weight).group] if len(v.groups) else None for v in mesh.data.vertices]
    B = arm.data.bones
    cierre = 20.0
    for sd, sg in (('L', 1), ('R', -1)):
        ua, fa = B[f'upper_arm.{sd}'], B[f'forearm.{sd}']
        brazo = (f'upper_arm.{sd}', f'forearm.{sd}', f'hand.{sd}')
        cuerpo = ('hips', 'spine', 'chest', f'thigh.{sd}')
        for zz in (ua.tail_local.z, fa.tail_local.z):             # codo y muñeca
            bx = [v.co.x * sg for v, d in zip(mesh.data.vertices, dom) if d in brazo and abs(v.co.z - zz) < 0.02 * k]
            tx = [v.co.x * sg for v, d in zip(mesh.data.vertices, dom)
                  if d in cuerpo and abs(v.co.z - zz) < 0.02 * k and v.co.x * sg > 0]
            if not bx or not tx:
                continue
            hueco = min(bx) - max(tx) - 0.03 * k
            cierre = min(cierre, math.degrees(math.atan2(max(0.0, hueco), ua.head_local.z - zz)))
    arm['cierre_brazos'] = round(cierre, 1)
    print(f'[anim] brazos cerrados {cierre:.1f}° hacia el cuerpo')
    return arm['cierre_brazos']


def cierre_piernas(arm, a):
    """Metros que se acerca cada pie al centro al caminar y correr. La malla sale con las piernas separadas (para que
    el rig salga bien) y el control IK conserva esa separación: caminaban con las piernas abiertas. Se lleva el
    tobillo debajo de la cadera, sin que los pies queden a menos de 2 cm entre sí (se mide en reposo el borde de
    adentro del pie; la canilla no, porque al cruzarse una pierna va adelante y la otra atrás). `animacion.cerrar_piernas` (metros) lo fuerza. Se calcula una vez y queda en el rig."""
    if a.get('cerrar_piernas') is not None:
        return float(a['cerrar_piernas'])
    if 'cierre_piernas' in arm:
        return arm['cierre_piernas']
    mesh = next(o for o in arm.children if o.type == 'MESH')
    k = arm.get('escala_plantilla', 1.0)
    nom = {g.index: g.name for g in mesh.vertex_groups}
    B = arm.data.bones
    cierre = 1.0
    for sd, sg in (('L', 1), ('R', -1)):
        bx = [v.co.x * sg for v in mesh.data.vertices
              if len(v.groups) and nom[max(v.groups, key=lambda g: g.weight).group] == f'foot.{sd}']
        tobillo, cadera = B[f'foot.{sd}'].head_local.x * sg, B[f'thigh.{sd}'].head_local.x * sg
        adentro = min(bx) if bx else tobillo
        cierre = min(cierre, tobillo - cadera, adentro - 0.01 * k)
    arm['cierre_piernas'] = round(max(0.0, cierre), 3)
    print(f'[anim] pies {arm["cierre_piernas"]:.3f} m más cerca del centro al caminar/correr')
    return arm['cierre_piernas']


def _rodillas(arm, junta, fr):
    """Pone el polo de cada rodilla en el plano vertical de la cadera y el tobillo (ya acercado `junta`): con el polo
    en su lugar de reposo, al doblar la pierna la rodilla se iba hacia afuera (piernas arqueadas)."""
    B = arm.data.bones
    for sd, sg in (('L', 1), ('R', -1)):
        x = (B[f'thigh.{sd}'].head_local.x + B[f'foot.{sd}'].head_local.x - sg * junta) / 2
        pole = arm.pose.bones[f'knee_pole.{sd}']
        pole.location = _local(arm, pole.name, (x - B[pole.name].head_local.x, 0, 0))
        _key(pole, 'location', f=fr)


def _key(p, *paths, f):
    for path in paths:
        p.keyframe_insert(path, frame=f)


def idle(arm, a, pitch=None):
    act = _nueva_accion(arm, 'Idle')
    pb = arm.pose.bones
    pb['head'].rotation_euler = (D(a['cabeza_arriba_grados'] if pitch is None else pitch), 0, 0)
    _key(pb['head'], 'rotation_euler', f=1)
    c = cierre_brazos(arm, a)
    for sd, sg in (('L', 1), ('R', -1)):
        _brazo(arm, sd, 0, -c, 1)
    return [1]


# pierna en el aire al caminar: u (0 despega atrás, 1 apoya adelante) -> y como fracción de la zancada (+ = atrás),
# z como fracción de levantar_pie, tobillo respecto de la canilla (+ = punta abajo). Sale con la punta (talón arriba
# y pie estirado), la rodilla pasa doblada con la punta arriba (no arrastra) y llega con el talón primero.
VUELO_CAMINATA = [(0.0, 1.0, 0.0, 25), (0.3, 0.55, 0.8, 5), (0.55, -0.05, 1.0, -10),
                  (0.8, -0.65, 0.55, -15), (1.0, -1.0, 0.0, -15)]


def caminar(arm, a, n=8):
    """Ciclo de caminata en el lugar (frente = -Y), 8 cuadros. Cada pie apoya el 60 % del ciclo (doble apoyo): entra
    de talón con la punta arriba, queda plano, y al final del apoyo levanta el talón y despega con la punta. La cadera
    baja al recibir el peso y sube cuando la otra pierna pasa; pelvis y pecho giran en contra, brazos opuestos a las
    piernas con el codo apenas doblado. Antes los pies iban siempre planos (arrastraba), la rodilla que avanza casi no
    se doblaba y el antebrazo quedaba horizontal adelante (como llevando una bandeja)."""
    zc = a['zancada'] * 1.3
    alto = a['levantar_pie']
    swing = a['balanceo_brazos_grados'] * 1.1
    APOYO = 0.6

    def pie(t):
        """(y, z, pitch, talón levantado, tobillo respecto de la canilla o None)"""
        t %= 1.0
        if t < APOYO:
            u = t / APOYO
            punta = -12 * max(0.0, 1 - u / 0.15)                     # talón primero, punta arriba
            return (-zc + 2 * zc * u, 0.012 * max(0.0, 1 - u / 0.15), punta, max(0.0, (u - 0.6) / 0.4) * 30, None)
        y, z, tob = _tabla(VUELO_CAMINATA, (t - APOYO) / (1 - APOYO))
        return (y * zc, z * alto, 0, 0, tob)

    poses = []
    for i in range(n):
        t = i / n
        c = math.cos(2 * math.pi * t)                    # +1: pierna L adelante -> brazo L atrás
        dz = -0.03 - 0.014 * math.cos(4 * math.pi * (t - 0.06))     # abajo al recibir el peso, arriba al pasar
        P = dict(hips=(0, dz), hips_rot=(2, 6 * c, 0), spine=(2, 0, 0), chest=(3, -9 * c, 0),
                 head=-2 + 1.5 * math.cos(4 * math.pi * t),
                 brazo_L=(swing * c, 2), brazo_R=(-swing * c, 2),
                 antebrazo_L=-6 - 10 * max(0, -c), antebrazo_R=-6 - 10 * max(0, c),     # adelante se dobla más
                 hombro_L=(-5 * c, 0), hombro_R=(5 * c, 0), puno=0.25)
        for sd, ph in (('L', 0.0), ('R', 0.5)):
            y, z, p, tal, tob = pie(t + ph)
            P[f'pie_{sd}'] = (y, z, p)
            P[f'talon_{sd}'] = tal
            if tob is not None:
                P[f'tobillo_{sd}'] = tob
        poses.append(P)
    return _poses(arm, a, 'Walk', poses, ciclo=True, junta=cierre_piernas(arm, a))


# root_z (relativo a la altura del salto), hips_z, pie (dy, dz, pitch), pecho, cabeza, brazo, antebrazo, apertura
# brazos: al despegar suben adelante y arriba (a la altura del hombro parecían de zombie), en la cima se abren y
# al caer bajan abiertos (equilibrio); las piernas se recogen en el aire (colgaban derechas)
POSES_SALTO = [
    dict(root=0.0, hips=-0.03, foot=(0, 0, 0), chest=4, head=0, arm=10, fore=-15, spread=0),           # listo
    dict(root=0.0, hips=-0.15, foot=(0, 0, 0), chest=18, head=-10, arm=45, fore=-25, spread=0),        # agachado
    dict(root=0.31, hips=0.0, foot=(0.02, -0.02, -35), chest=-4, head=5, arm=-115, fore=-20, spread=15),  # despegue
    dict(root=0.8, hips=0.0, foot=(0.08, 0.2, -20), chest=-2, head=4, arm=-135, fore=-25, spread=25),    # subida
    dict(root=1.0, hips=0.0, foot=(0.1, 0.28, -10), chest=6, head=0, arm=-75, fore=-20, spread=60),     # cima
    dict(root=0.6, hips=0.0, foot=(0.02, 0.08, -25), chest=4, head=-4, arm=-50, fore=-25, spread=60),    # caída
    dict(root=0.0, hips=-0.17, foot=(0, 0, 0), chest=20, head=-8, arm=-35, fore=-30, spread=15),       # aterrizaje
    dict(root=0.0, hips=-0.06, foot=(0, 0, 0), chest=8, head=-2, arm=0, fore=-15, spread=2),           # recuperación
]


def saltar(arm, a, altura=0.0, paso=2):
    """Salto: 8 poses clave. altura=0 -> en el lugar (el motor del juego mueve el cuerpo)."""
    act = _nueva_accion(arm, 'Jump')
    pb = arm.pose.bones
    pitch = a['cabeza_arriba_grados']
    cierre = cierre_brazos(arm, a)
    frames = []
    for i, P in enumerate(POSES_SALTO):
        fr = 1 + i * paso
        frames.append(fr)
        pb['root'].location = _local(arm, 'root', (0, 0, P['root'] * altura)); _key(pb['root'], 'location', f=fr)
        pb['hips'].location = _local(arm, 'hips', (0, 0, P['hips'])); _key(pb['hips'], 'location', f=fr)
        dy, dz, p = P['foot']
        for sd in ('L', 'R'):
            b = pb[f'foot_ik.{sd}']
            b.location = _local(arm, b.name, (0, dy, dz)); b.rotation_euler = (D(p), 0, 0)
            _key(b, 'location', 'rotation_euler', f=fr)
        pb['chest'].rotation_euler = (D(P['chest']), 0, 0); _key(pb['chest'], 'rotation_euler', f=fr)
        pb['head'].rotation_euler = (D(P['head'] + pitch), 0, 0); _key(pb['head'], 'rotation_euler', f=fr)
        for sd, s in (('L', 1), ('R', -1)):
            _brazo(arm, sd, P['arm'], P['spread'] - cierre, fr)
            fa = pb[f'forearm.{sd}']
            fa.rotation_euler = (D(P['fore']), 0, 0); _key(fa, 'rotation_euler', f=fr)
    for fc in _fcurves(act):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    return frames


# ---------------------------------------------------------------------------------------------
# Poses genéricas. Una pose es un dict (todo opcional, ángulos en grados, distancias en unidades
# del modelo de 1.85; se escalan con la altura):
#   rodar: giro de todo el cuerpo en X (+ = hacia adelante) alrededor de pivote (dy, dz)
#   root: (dy, dz) desplaza todo el cuerpo        hips: (dy, dz) desplaza la cadera (IK de pies fijo)
#   hips_rot, spine, chest: (x, y, z) (x + = inclinarse adelante, y = torsión)   head: x (+ = mirar abajo)
#   pie / pie_L / pie_R: (dy, dz, pitch)          frente = -dy
#   pierna_L / pierna_R: (muslo, rodilla) ángulos de la pierna (ver _piernas); pisa el (dy, dz) de pie_*
#   tobillo_L / tobillo_R: flexión del pie respecto de la canilla (+ = punta abajo); pisa el pitch de pie_*
#   talon / talon_L / talon_R: levanta el talón (grados) girando sobre la punta: sube el tobillo lo necesario
#     para que la punta quede donde estaba (apoyado en el piso); se suma al pitch de pie_*
#   brazo / brazo_L / brazo_R: (x, apertura) (x - = adelante/arriba)   antebrazo(_L/_R): x (- = doblar codo)
#   hombro(_L/_R): (adelante, arriba) mueve la clavícula (+ = adelantar el hombro / subirlo)
#   mano(_L/_R): x (- = doblar la muñeca hacia adelante / adentro)
#   puno(_L/_R): 0..1 cierra la mano (no hay huesos de dedos: la mano se acorta a lo largo y se ensancha un poco)
# L = lado lejano a la cámara en la vista lateral, R = el cercano.

def _pose(arm, P, fr, pitch, k, cierre=0.0, junta=None):
    pb = arm.pose.bones
    rx = D(P.get('rodar', 0))
    piv = Vector((0, *P.get('pivote', (0, 0.45)))) * k
    R = Matrix.Rotation(rx, 3, 'X')
    loc = piv - R @ piv + Vector((0, *P.get('root', (0, 0)))) * k
    pb['root'].location = _local(arm, 'root', loc); pb['root'].rotation_euler = (rx, 0, 0)
    _key(pb['root'], 'location', 'rotation_euler', f=fr)
    pb['hips'].location = _local(arm, 'hips', Vector((0, *P.get('hips', (0, 0)))) * k * arm.get('factor_pierna', 1.0))
    pb['hips'].rotation_euler = [D(x) for x in P.get('hips_rot', (0, 0, 0))]
    _key(pb['hips'], 'location', 'rotation_euler', f=fr)
    fp = arm.get('factor_pierna', 1.0)   # chibis: la cabeza grande va arriba del pecho; inclinarlo como a un adulto
    for b in ('spine', 'chest'):         # la tiraba adelante y desgarraba la espalda (un chibi agachado)
        x, y, z = P.get(b, (0, 0, 0))
        pb[b].rotation_euler = (D(x * fp), D(y), D(z)); _key(pb[b], 'rotation_euler', f=fr)
    # la cabeza compensa la inclinación del pecho: con el pecho achicado, también ella (si no, se va atrás)
    pb['head'].rotation_euler = (D(P.get('head', 0) * fp + pitch), 0, 0); _key(pb['head'], 'rotation_euler', f=fr)
    for sd, s in (('L', 1), ('R', -1)):
        dy, dz, p = P.get(f'pie_{sd}', P.get('pie', (0, 0, 0)))
        tal = P.get(f'talon_{sd}', P.get('talon', 0))
        if tal:
            fb = arm.data.bones[f'foot.{sd}']
            largo = (fb.tail_local - fb.head_local).length / k
            a0 = math.asin(min(1, (fb.head_local.z - fb.tail_local.z) / k / largo))   # el pie ya baja hacia la punta
            dz += largo * (math.sin(a0 + D(tal)) - math.sin(a0)); p += tal            # + = punta abajo
        b = pb[f'foot_ik.{sd}']
        b.location = _local(arm, b.name, Vector((-s * (junta or 0.0), dy * k, dz * k))); b.rotation_euler = (D(p), 0, 0)
        _key(b, 'location', 'rotation_euler', f=fr)
        x, ap = P.get(f'brazo_{sd}', P.get('brazo', (0, 0)))
        _brazo(arm, sd, x, ap - cierre, fr)
        fa = pb[f'forearm.{sd}']
        fa.rotation_euler = (D(P.get(f'antebrazo_{sd}', P.get('antebrazo', -15))), 0, 0)
        _key(fa, 'rotation_euler', f=fr)
        ad, ar = P.get(f'hombro_{sd}', P.get('hombro', (0, 0)))
        sh = pb[f'shoulder.{sd}']
        sh.rotation_euler = (D(ar), 0, -D(ad) * s); _key(sh, 'rotation_euler', f=fr)   # Z: adelante con signo espejado
        mn = pb[f'hand.{sd}']
        mn.rotation_euler = (D(P.get(f'mano_{sd}', P.get('mano', 0))), 0, 0); _key(mn, 'rotation_euler', f=fr)
        pu = P.get(f'puno_{sd}', P.get('puno', 0))      # sin huesos de dedos: la mano se acorta a lo largo
        mn.scale = (1 + 0.15 * pu, 1 - 0.5 * pu, 1 + 0.15 * pu); _key(mn, 'scale', f=fr)
    if junta is not None:
        _rodillas(arm, junta, fr)


def _apoyar(arm, fr):
    """Sube/baja todo el cuerpo para que el punto más bajo de la malla deformada toque el piso (z=0)."""
    sc = bpy.context.scene
    sc.frame_set(fr)
    mesh = next(o for o in arm.children if o.type == 'MESH')
    ev = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    zmin = min((ev.matrix_world @ v.co).z for v in me.vertices)
    ev.to_mesh_clear()
    r = arm.pose.bones['root']
    r.location = r.location + _local(arm, 'root', (0, 0, -zmin))
    _key(r, 'location', f=fr)


def _angulo_lateral(arm, bone):
    """ángulo del hueso en el plano lateral del rig (y, z), en grados: 0 = hacia abajo, + = hacia atrás (+Y)"""
    pb = arm.pose.bones[bone]
    v = pb.tail - pb.head
    return math.degrees(math.atan2(v.y, -v.z))


def _tobillos(arm, fr, P):
    """tobillo_L/R en la pose: flexión del pie respecto de la canilla (grados; 0 = como en reposo, + = punta abajo,
    - = punta arriba), en vez del pitch del pie respecto del piso. El pie copia la rotación absoluta del control
    IK, así que con la canilla muy inclinada (talón arriba en la carrera) un pitch fijo le quiebra el tobillo."""
    sc = bpy.context.scene
    pb = arm.pose.bones
    for sd in ('L', 'R'):
        flex = P.get(f'tobillo_{sd}')
        if flex is None:
            continue
        b = pb[f'foot_ik.{sd}']
        rest = arm.data.bones[f'foot.{sd}']
        rel0 = math.degrees(math.atan2((rest.tail_local - rest.head_local).y, -(rest.tail_local - rest.head_local).z)) \
            - math.degrees(math.atan2((arm.data.bones[f'shin.{sd}'].tail_local - arm.data.bones[f'shin.{sd}'].head_local).y,
                                      -(arm.data.bones[f'shin.{sd}'].tail_local - arm.data.bones[f'shin.{sd}'].head_local).z))
        sc.frame_set(fr)
        p0 = b.rotation_euler.x
        objetivo = _angulo_lateral(arm, f'shin.{sd}') + rel0 + flex      # + = punta abajo = hacia atrás
        a0 = _angulo_lateral(arm, f'foot.{sd}')
        b.rotation_euler.x = p0 + D(10); bpy.context.view_layer.update()
        pend = (_angulo_lateral(arm, f'foot.{sd}') - a0) / 10              # grados de pie por grado de control
        b.rotation_euler.x = p0 + D((objetivo - a0) / pend)
        _key(b, 'rotation_euler', f=fr)


def _piernas(arm, fr, P):
    """pierna_L/R en la pose: (muslo, rodilla) en grados. muslo = ángulo del muslo desde la vertical en el plano
    lateral (+ = adelante, 90 = horizontal), rodilla = flexión de la canilla respecto del muslo (0 = estirada). Se
    mide desde la cadera ya posada (hips, hips_rot) y se lleva el control IK del pie ahí; pisa el (dy, dz) de pie_*.
    Con offsets fijos del pie la pierna quedaba según el largo de cada personaje (rodilla a 45° en vez de arriba)."""
    sc = bpy.context.scene
    pb, B = arm.pose.bones, arm.data.bones
    for sd in ('L', 'R'):
        pi = P.get(f'pierna_{sd}')
        if pi is None:
            continue
        m, r = D(pi[0]), D(pi[0] - pi[1])
        sc.frame_set(fr)
        cad = pb[f'thigh.{sd}'].head
        lt, ls = B[f'thigh.{sd}'].length, B[f'shin.{sd}'].length * 0.995   # sin estirar del todo (el IK no salta)
        obj = cad + Vector((0, -math.sin(m) * lt - math.sin(r) * ls, -math.cos(m) * lt - math.cos(r) * ls))
        b = pb[f'foot_ik.{sd}']
        delta = obj - b.head
        delta.x = 0
        b.location = b.location + _local(arm, b.name, delta)
        _key(b, 'location', f=fr)
        # polo delante de la rodilla, perpendicular a la línea cadera-tobillo: con la pierna horizontal el polo de
        # reposo (adelante, a la altura de la rodilla) queda sobre esa línea y el IK la doblaba para atrás
        dy, dz = obj.y - cad.y, obj.z - cad.z
        n = math.hypot(dy, dz) or 1.0
        rod = cad + Vector((0, -math.sin(m) * lt, -math.cos(m) * lt))
        po = pb[f'knee_pole.{sd}']
        meta = rod + Vector((0, dz / n, -dy / n)) * 0.5 * arm.get('escala_plantilla', 1.0)
        d = meta - po.head
        d.x = 0
        po.location = po.location + _local(arm, po.name, d)
        _key(po, 'location', f=fr)


def _poses(arm, a, nombre, poses, paso=2, ciclo=False, piso=False, junta=None):
    """Una Action con una pose clave cada `paso` frames; devuelve los frames clave (los que se renderizan).
    piso=True: cada pose se apoya en el piso midiendo la malla (volteretas, caídas). junta: metros que se acercan
    los pies al centro (ver cierre_piernas); con junta, las rodillas apuntan adelante (_rodillas)."""
    act = _nueva_accion(arm, nombre)
    k = arm.get('escala_plantilla', 1.0)
    cierre = cierre_brazos(arm, a)
    frames = []
    for i, P in enumerate(poses):
        fr = 1 + i * paso
        _pose(arm, P, fr, a['cabeza_arriba_grados'], k, cierre, junta)
        frames.append(fr)
    for fr, P in zip(frames, poses):
        _piernas(arm, fr, P)
    for fr, P in zip(frames, poses):
        _tobillos(arm, fr, P)
    for fr in frames if piso else []:
        _apoyar(arm, fr)
    if ciclo:  # cerrar el loop repitiendo la primera pose
        _pose(arm, poses[0], 1 + len(poses) * paso, a['cabeza_arriba_grados'], k, cierre, junta)
        _tobillos(arm, 1 + len(poses) * paso, poses[0])
        for fc in _fcurves(act):
            fc.modifiers.new('CYCLES')
    return frames


def respirar(arm, a, n=8):
    """Quieto en loop: respiración suave (pecho, hombros, cadera)."""
    poses = []
    for i in range(n):
        s = math.sin(2 * math.pi * i / n)
        poses.append(dict(hips=(0, -0.004 + 0.004 * s), chest=(1.5 - 1.5 * s, 0, 0), head=-1 * s,
                          brazo=(-2 * s, 3 + 1.5 * s), antebrazo=-15 - 3 * s))
    return _poses(arm, a, 'IdleLoop', poses, ciclo=True)


def _tabla(tabla, u):
    """interpolación lineal en una tabla [(u, valor...), ...] ordenada por u"""
    for (u0, *v0), (u1, *v1) in zip(tabla, tabla[1:]):
        if u <= u1:
            f = (u - u0) / (u1 - u0) if u1 > u0 else 0
            return [x0 + (x1 - x0) * f for x0, x1 in zip(v0, v1)]
    return tabla[-1][1:]


# pierna en el aire durante la carrera: u (0 despega atrás, 1 apoya adelante) -> y como fracción de la zancada
# (+ = atrás), z como fracción de la altura, tobillo respecto de la canilla (+ = punta abajo). El talón sube atrás
# con el pie relajado y la rodilla pasa alta adelante; antes de apoyar la punta sube (entra el talón).
VUELO_CARRERA = [(0.0, 1.0, 0.0, 30), (0.25, 0.75, 0.75, 25), (0.5, 0.05, 1.0, 10),
                 (0.75, -0.75, 0.7, -5), (1.0, -1.0, 0.0, -10)]


def correr(arm, a, n=12):
    """Ciclo de carrera: cada pie apoya el 35 % del ciclo y hay fase de vuelo (los dos pies en el aire, el cuerpo
    arriba); el cuerpo baja al amortiguar. En el apoyo el pie queda plano y al final despega levantando el talón
    (gira sobre la punta). Torso inclinado, braceo amplio desde el hombro, brazo y pierna opuestos. Se muestrea a
    mitad de cada cuadro para que haya cuadros en cada vuelo."""
    zc = a['zancada'] * 2.2
    alto = a['levantar_pie'] * 3.2
    swing = a['balanceo_brazos_grados'] * 2.5
    APOYO = 0.35
    # atrás menos que adelante: con 60° atrás el codo pasaba por encima del hombro (ala de pollo); adelante la mano
    # llega al pecho, no a la boca
    braceo = lambda c: swing * 0.6 * c if c > 0 else swing * 0.85 * c
    def pie(t):
        """(y, z, talón levantado o 0, tobillo respecto de la canilla o None)"""
        t %= 1.0
        if t < APOYO:                                # apoyo: de adelante hacia atrás, plano; al final sube el talón
            u = t / APOYO
            return (-zc + 2 * zc * u, 0.0, max(0.0, (u - 0.45) / 0.55) * 40, None)
        y, z, tob = _tabla(VUELO_CARRERA, (t - APOYO) / (1 - APOYO))
        return (y * zc, z * alto, 0, tob)

    poses = []
    for i in range(n):
        t = (i + 0.5) / n
        tau = t % 0.5
        vuelo = math.sin(math.pi * (tau - APOYO) / (0.5 - APOYO)) if tau >= APOYO else 0.0
        baja = math.sin(math.pi * tau / APOYO) if tau < APOYO else 0.0     # amortigua en el apoyo
        dz = 0.06 * vuelo - 0.05 * baja
        c = math.cos(2 * math.pi * t)                # +1: pierna L adelante -> brazo L atrás
        P = dict(
            hips=(0, -0.04 + dz), hips_rot=(12, 12 * c, 0), spine=(8, 0, 0), chest=(12, -16 * c, 0), head=-20,
            brazo_L=(braceo(c), 10), brazo_R=(braceo(-c), 10),
            antebrazo_L=-80 - 20 * max(0, -c), antebrazo_R=-80 - 20 * max(0, c),     # adelante se dobla más
            hombro_L=(-10 * c, 0), hombro_R=(10 * c, 0), mano=-10, puno=0.8)
        for sd, ph in (('L', 0.0), ('R', 0.5)):
            y, z, tal, tob = pie(t + ph)
            P[f'pie_{sd}'] = (y, z + 0.06 * vuelo, 0)
            P[f'talon_{sd}'] = tal
            if tob is not None:
                P[f'tobillo_{sd}'] = tob
        poses.append(P)
    return _poses(arm, a, 'Run', poses, ciclo=True, junta=cierre_piernas(arm, a))


def rodar(arm, a):
    """Voltereta hacia adelante en el lugar (el juego desplaza el cuerpo): encogerse, girar 360°, pararse."""
    bolita = dict(hips=(0.02, -0.38), chest=(55, 0, 0), spine=(25, 0, 0), head=35,
                  pie=(-0.12, 0.2, -20), brazo=(-55, 10), antebrazo=-110)
    poses = [dict(hips=(0, -0.2), chest=(30, 0, 0), head=15, pie=(0, 0, 0), brazo=(-30, 10), antebrazo=-60)]
    for g in (60, 130, 200, 270, 330):
        poses.append(dict(bolita, rodar=g))
    poses.append(dict(hips=(0, -0.28), chest=(35, 0, 0), head=15, pie=(0, 0, 0), brazo=(-40, 20), antebrazo=-60))
    poses.append(dict(hips=(0, -0.08), chest=(10, 0, 0), head=0, brazo=(-10, 5), antebrazo=-25))
    return _poses(arm, a, 'Roll', poses, piso=True)


# guardia de costado: pierna lejana (L) adelante, talón de atrás (R) levantado, puño lejano adelante a la altura
# del mentón, el cercano (R) pegado a la cara; las manos no se superponen en la vista lateral
# Guardia: brazos casi verticales junto al cuerpo y antebrazos arriba (codo marcado, puños al mentón). Con el brazo
# 35-50° adelante y la mano abierta arriba el brazo entero se leía como un caño curvo ("rezando", codo de goma).
GUARDIA = dict(hips=(0, -0.08), chest=(8, 8, 0), head=8, pie_L=(-0.13, 0, 0), pie_R=(0.11, 0, 0), talon_R=20,
               brazo_L=(-62, 4), antebrazo_L=-85, brazo_R=(-12, 12), antebrazo_R=-135,
               hombro_L=(8, 2), hombro_R=(0, 2), mano=5, puno=1)


def golpe(arm, a):
    """Uno-dos: primero el jab con la mano de adelante (L, la lejana), después el directo con la de atrás (R).
    7 cuadros: guardia, jab, jab vuelve mientras carga el directo, directo (paso adelante, cadera y hombro al
    frente), directo sostenido, retorno, guardia."""
    jab = dict(GUARDIA, hips=(-0.03, -0.08), chest=(10, 14, 0), pie_L=(-0.17, 0, 0),
               brazo_L=(-98, 4), antebrazo_L=-5, hombro_L=(25, 3), mano_L=0)
    carga = dict(GUARDIA, hips=(0.03, -0.09), chest=(2, 18, 0), brazo_R=(10, 15), antebrazo_R=-125,
                 hombro_R=(-20, 0), brazo_L=(-30, 4), antebrazo_L=-110, hombro_L=(10, 0))
    directo = dict(GUARDIA, hips=(-0.09, -0.1), hips_rot=(4, -8, 0), chest=(10, -14, 0), head=4,
                   pie_L=(-0.24, 0, 0), pie_R=(0.1, 0, 0), talon_R=35,
                   brazo_R=(-104, 0), antebrazo_R=-4, hombro_R=(30, 4), mano_R=0,
                   brazo_L=(-30, 10), antebrazo_L=-135, hombro_L=(-10, 0))
    poses = [
        GUARDIA,
        jab,
        carga,
        directo,
        dict(directo, hips=(-0.1, -0.11), chest=(12, -16, 0), hombro_R=(34, 4), antebrazo_R=0),   # sostenido
        dict(GUARDIA, hips=(-0.04, -0.08), pie_L=(-0.2, 0, 0), chest=(10, -5, 0),
             brazo_R=(-30, 8), antebrazo_R=-110, hombro_R=(10, 0)),                                # retorno
        GUARDIA,
    ]
    return _poses(arm, a, 'Punch', poses)


def patada(arm, a):
    """Patada frontal con la pierna de atrás (R, la cercana). 8 cuadros: guardia, anticipación (el peso pasa a la
    pierna de adelante, el talón de atrás sube), recogida (muslo arriba, talón hacia la cola), extensión, sostenida,
    recogida de vuelta, apoyo atrás, guardia. La pierna va por ángulos (pierna_R, ver _piernas): con offsets del pie
    la recogida quedaba a 45° (parecía marchar). La pelvis bascula atrás (hips_rot) y la columna compensa: con la
    pelvis fija toda la flexión salía de la cadera (bulto en la cola) y el torso tirado atrás con la cabeza al techo
    parecía caerse; la cabeza sigue mirando al frente. Rodilla de apoyo flexionada, la cadera de la pierna que patea
    va adelante y el brazo de ese lado baja de contrapeso. Pies acercados al centro (cierre_piernas): con las piernas
    abiertas en reposo pateaba en diagonal hacia afuera."""
    rec = dict(GUARDIA, hips=(-0.04, -0.08), hips_rot=(-8, -10, 0), spine=(4, 0, 0), chest=(4, 16, 0), head=4,
               pierna_R=(105, 110), tobillo_R=30, brazo_R=(-5, 12), antebrazo_R=-120)
    ext = dict(GUARDIA, hips=(-0.03, -0.06), hips_rot=(-18, -14, 0), spine=(6, 0, 0), chest=(4, 18, 0), head=10,
               pierna_R=(86, 4), tobillo_R=35,
               brazo_R=(15, 16), antebrazo_R=-100, hombro_R=(-8, 0), brazo_L=(-30, 6), antebrazo_L=-110)
    poses = [
        GUARDIA,
        dict(GUARDIA, hips=(-0.05, -0.1), hips_rot=(0, -4, 0), chest=(10, 12, 0), talon_R=45),        # anticipación
        rec,                                                                                         # recogida
        ext,                                                                                         # extensión
        dict(ext, hips_rot=(-20, -16, 0), pierna_R=(92, 0), head=12),                                # sostenida
        dict(rec, pierna_R=(100, 115), hips_rot=(-6, -8, 0)),                                         # recoge
        dict(GUARDIA, hips=(0.0, -0.1), chest=(10, 8, 0), pie_R=(0.12, 0.03, 0), talon_R=30),       # apoyo atrás
        GUARDIA,
    ]
    return _poses(arm, a, 'Kick', poses, junta=cierre_piernas(arm, a))


def agacharse(arm, a):
    return _poses(arm, a, 'Crouch', [dict(hips=(0.04, -0.36), chest=(28, 0, 0), head=-18, pie_L=(-0.1, 0, 0),
                                          pie_R=(0.08, 0, 0), brazo=(-40, 12), antebrazo=-100, puno=0.6)])


def defender(arm, a):
    """Bloqueo alto: antebrazos verticales delante de la cara, separados de ella (pegados al visor parecía taparse
    la cara con la mano)."""
    return _poses(arm, a, 'Block', [dict(GUARDIA, hips=(0.03, -0.1), chest=(6, 5, 0), head=4,
                                         brazo_L=(-100, 6), antebrazo_L=-70, brazo_R=(-92, 14), antebrazo_R=-74)])


def herido(arm, a):
    """Recibe un golpe de frente: el pecho se va atrás, los brazos salen despedidos hacia atrás y afuera, da un
    paso atrás y vuelve. Con la cabeza tirada atrás y los brazos adelante parecía mirar al cielo (zombie)."""
    poses = [
        dict(hips=(0.05, -0.06), spine=(-4, 0, 0), chest=(-10, 6, 0), head=4, brazo=(28, 30), antebrazo=-40,
             puno=0.3),
        dict(hips=(0.08, -0.1), chest=(-6, 4, 0), head=2, pie_R=(0.1, 0, 0), talon_R=10, brazo=(12, 18),
             antebrazo=-55, puno=0.3),
        dict(hips=(0.03, -0.08), chest=(10, 0, 0), head=6, pie_R=(0.05, 0, 0), brazo=(-15, 8), antebrazo=-60,
             puno=0.5),
    ]
    return _poses(arm, a, 'Hurt', poses)


def morir(arm, a):
    """Cae de espaldas y queda acostado (último frame = en el piso). Los brazos salen hacia atrás y afuera
    (adelante parecían de zombie). El cuerpo se corre hacia adelante
    mientras cae para que acostado quede centrado en el origen (si no, la celda de la hoja se duplica)."""
    poses = [
        dict(hips=(0.06, -0.06), spine=(-5, 0, 0), chest=(-14, 6, 0), head=2, brazo=(32, 35), antebrazo=-35,
             puno=0.3),
        dict(hips=(0.05, -0.25), chest=(-6, 0, 0), head=-4, pie=(-0.08, 0, 0), brazo=(15, 40), antebrazo=-45),
        dict(rodar=-35, pivote=(0.1, 0), root=(-0.3, 0), hips=(0.02, -0.3), chest=(-5, 0, 0), head=-6,
             pie=(-0.1, 0.05, 0), brazo=(5, 50), antebrazo=-40),
        dict(rodar=-70, pivote=(0.1, 0), root=(-0.65, 0), hips=(0, -0.2), head=-2, pie=(-0.1, 0.08, 10),
             brazo=(10, 60), antebrazo=-30),
        dict(rodar=-88, pivote=(0.1, 0), root=(-0.9, 0), hips=(0, -0.08), head=5, pie=(-0.05, 0.03, 10),
             brazo=(5, 25), antebrazo=-15),
        dict(rodar=-90, pivote=(0.1, 0), root=(-0.95, 0), hips=(0, -0.05), head=8, pie=(0, 0, 0),
             brazo=(15, 20), antebrazo=-10),
    ]
    return _poses(arm, a, 'Die', poses, piso=True)


def lanzar(arm, a):
    """Lanza algo hacia adelante con la mano de atrás (R, la cercana): bumerán, plumas, granadas. 6 cuadros:
    carga (brazo por encima del hombro y pasado atrás, abierto hacia afuera para que se vea detrás de la cabeza, la
    mano atrás a la altura del hombro, el pecho girado atrás y el peso en la pierna de atrás), paso adelante con el pie de adelante (L) y el codo que adelanta a la mano, suelta (brazo
    estirado al frente, hombro y cadera al frente, talón de atrás arriba), acompañamiento (el brazo sigue hacia
    abajo y el torso se inclina) y vuelta. El brazo libre (L) apunta adelante en la carga y se recoge al soltar."""
    carga = dict(hips=(0.05, -0.07), hips_rot=(0, 4, 0), chest=(-6, 14, 0), head=2,
                 pie_L=(-0.12, 0, 0), pie_R=(0.12, 0, 0),
                 brazo_R=(-200, 35), antebrazo_R=-90, hombro_R=(-10, 8), mano_R=-10, puno_R=0.6,
                 brazo_L=(-70, 10), antebrazo_L=-35, hombro_L=(10, 0), puno_L=0.3)
    suelta = dict(hips=(-0.1, -0.12), hips_rot=(4, -8, 0), chest=(14, -18, 0), head=4,
                  pie_L=(-0.26, 0, 0), pie_R=(0.1, 0, 0), talon_R=35,
                  brazo_R=(-100, 2), antebrazo_R=-6, hombro_R=(30, 4), mano_R=10, puno_R=0,
                  brazo_L=(15, 18), antebrazo_L=-70, hombro_L=(-10, 0), puno_L=0.6)
    poses = [
        carga,
        dict(carga, hips=(0.07, -0.09), chest=(-10, 18, 0), pie_L=(-0.18, 0.05, 0),               # máxima carga
             brazo_R=(-212, 32), antebrazo_R=-100, head=0),
        dict(carga, hips=(-0.05, -0.11), hips_rot=(2, 0, 0), chest=(4, 6, 0), pie_L=(-0.26, 0, 0),   # paso
             talon_R=15, brazo_R=(-175, 22), antebrazo_R=-70, hombro_R=(10, 4), brazo_L=(-20, 14), antebrazo_L=-60),
        suelta,
        dict(suelta, hips=(-0.11, -0.13), chest=(17, -20, 0), head=2, talon_R=40,                  # acompaña
             brazo_R=(-55, 2), antebrazo_R=-15, hombro_R=(32, 4)),
        dict(hips=(-0.04, -0.06), chest=(6, -4, 0), pie_L=(-0.14, 0, 0), pie_R=(0.06, 0, 0),         # vuelta
             brazo=(-12, 6), antebrazo=-30, puno=0.4),
    ]
    return _poses(arm, a, 'Throw', poses)


def brazos_arriba(arm, a):
    """Los dos brazos arriba de la cabeza (festejo, conjuro, grito): curas, refuerzos, rugidos, súper. 6 cuadros:
    se junta (rodillas flexionadas, brazos bajos), sube (pecho arriba, se inclina un poco atrás, la cabeza mira
    arriba) y sostiene con los brazos en V; el último cuadro queda sostenido."""
    arriba = dict(hips=(0.02, 0.0), spine=(-4, 0, 0), chest=(-10, 0, 0), head=-4, talon=8,
                  brazo=(-172, 26), antebrazo=-12, hombro=(0, 6), mano=0, puno=0.3)
    poses = [
        dict(hips=(0, -0.09), chest=(10, 0, 0), head=4, brazo=(-20, 10), antebrazo=-70, puno=0.7),    # se junta
        dict(hips=(0.01, -0.03), spine=(-2, 0, 0), chest=(-4, 0, 0), head=-4,                          # sube
             brazo=(-115, 20), antebrazo=-40, puno=0.5),
        arriba,
        dict(arriba, hips=(0.025, 0.01), chest=(-12, 0, 0), head=-6, brazo=(-178, 30)),              # pico
        dict(arriba, brazo=(-174, 28), chest=(-11, 0, 0), head=-5),
        dict(arriba, hips=(0.025, 0.01), chest=(-12, 0, 0), head=-6, brazo=(-176, 29)),              # sostiene
    ]
    return _poses(arm, a, 'RaiseArms', poses)


def cargar(arm, a, n=6):
    """Carga energía en el lugar (loop): agachado en postura de fuerza, piernas abiertas adelante/atrás, pecho
    inclinado, puños apretados junto a la cadera con los codos atrás; respira y tiembla un poco (el pecho y los
    hombros alternan un temblor chico en cada cuadro)."""
    poses = []
    for i in range(n):
        s = math.sin(2 * math.pi * i / n)
        t = 1 if i % 2 else -1                         # temblor
        poses.append(dict(hips=(0.03, -0.2 + 0.012 * s), chest=(14 + 2 * s, 1.5 * t, 0), spine=(4, 0, 0),
                          head=-8 - 1.5 * s, pie_L=(-0.15, 0, 0), pie_R=(0.13, 0, 0),
                          brazo=(28 + 3 * s, 16 + 2 * s), antebrazo=-100 - 4 * s, hombro=(0, 4 + 2 * s),
                          mano=-5, puno=1))
    return _poses(arm, a, 'Charge', poses, ciclo=True)


# nombre (= carpeta de frames), función. El orden de la tira lo define armar_tira.ANIMACIONES.
TODAS = [('idle', idle), ('caminar', caminar), ('saltar', saltar), ('respirar', respirar), ('correr', correr),
         ('rodar', rodar), ('golpe', golpe), ('patada', patada), ('agacharse', agacharse),
         ('defender', defender), ('herido', herido), ('morir', morir),
         ('lanzar', lanzar), ('brazos_arriba', brazos_arriba), ('cargar', cargar)]
