# Esqueleto humanoide + pesos automáticos para una malla única (Blender 5.x).
# Los nombres de huesos son el contrato con anim.py: root, hips, spine, chest, neck, head,
# shoulder/upper_arm/forearm/hand/thigh/shin/foot .L/.R y los controles foot_ik.L/R, knee_pole.L/R.
import math
import bmesh
import bpy
from mathutils import Vector

# Articulaciones de referencia (personaje de prueba, 1.85 de alto, frente = -Y). '.S' = lado L (+X), se espeja a R.
# nombre: (head, tail, parent, connect, deform)
PLANTILLA = {
    'root': ((0, 0, 0), (0, 0.4, 0), None, False, False),
    'hips': ((0, 0.02, 0.8), (0, 0.02, 0.95), 'root', False, True),
    'spine': ((0, 0.02, 0.95), (0, 0.02, 1.08), 'hips', True, True),
    'chest': ((0, 0.02, 1.08), (0, 0.02, 1.2), 'spine', True, True),
    'neck': ((0, 0.02, 1.2), (0, 0.02, 1.27), 'chest', True, True),
    'head': ((0, 0.02, 1.27), (0, 0.02, 1.95), 'neck', True, True),
    'shoulder.S': ((0.07, 0.02, 1.13), (0.23, 0.02, 1.08), 'chest', False, True),
    'upper_arm.S': ((0.25, 0.02, 1.07), (0.31, 0.03, 0.93), 'shoulder.S', False, True),
    'forearm.S': ((0.31, 0.03, 0.93), (0.37, 0.02, 0.83), 'upper_arm.S', True, True),
    'hand.S': ((0.37, 0.02, 0.83), (0.40, 0.0, 0.6), 'forearm.S', True, True),
    'thigh.S': ((0.13, 0.02, 0.8), (0.17, 0.0, 0.46), 'hips', False, True),
    'shin.S': ((0.17, 0.0, 0.46), (0.21, 0.02, 0.12), 'thigh.S', True, True),
    'foot.S': ((0.21, 0.02, 0.12), (0.23, -0.22, 0.03), 'shin.S', True, True),
    'foot_ik.S': ((0.21, 0.02, 0.12), (0.23, -0.22, 0.03), 'root', False, False),
    'knee_pole.S': ((0.17, -0.7, 0.46), (0.17, -0.8, 0.46), 'root', False, False),
}
ALTURA_PLANTILLA = 1.85
BRAZO = ('shoulder.S', 'upper_arm.S', 'forearm.S', 'hand.S')
PIERNA = ('thigh.S', 'shin.S', 'foot.S', 'foot_ik.S', 'knee_pole.S')


def _cortes_x(verts, z, dz):
    """Grupos de vértices contiguos en X de una rebanada horizontal -> [[xmin, xmax], ...]."""
    xs = sorted(v.x for v in verts if abs(v.z - z) < dz)
    if not xs:
        return []
    grupos = [[xs[0], xs[0]]]
    for x in xs[1:]:
        if x - grupos[-1][1] > dz * 2:
            grupos.append([x, x])
        else:
            grupos[-1][1] = x
    return grupos


def estimar_articulaciones(mesh, altura):
    """Punto de partida: la plantilla escalada a la altura, con piernas y brazos ajustados al ancho
    real de la malla (rebanadas horizontales). Revisarlo siempre con `crisol guia`."""
    k = altura / ALTURA_PLANTILLA
    verts = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    J = {n: (tuple(c * k for c in h), tuple(c * k for c in t), p, cn, d)
         for n, (h, t, p, cn, d) in PLANTILLA.items()}

    def escalar_x(nombres, sx):
        for n in nombres:
            h, t, p, cn, d = J[n]
            J[n] = ((h[0] * sx, h[1], h[2]), (t[0] * sx, t[1], t[2]), p, cn, d)

    # piernas: centro de la pierna derecha (+X) a la altura de la rodilla
    g = [c for c in _cortes_x(verts, 0.46 * k, 0.01 * altura) if c[0] > 0]
    if g:
        cx = (g[0][0] + g[0][1]) / 2
        if 0.3 < cx / (0.17 * k) < 2.5:
            escalar_x(PIERNA, cx / (0.17 * k))
    # brazos: ancho máximo a la altura de las manos
    g = _cortes_x(verts, 0.7 * k, 0.01 * altura)
    if g and 0.3 < g[-1][1] / (0.47 * k) < 2.5:
        escalar_x(BRAZO, g[-1][1] / (0.47 * k))
    return J


def desde_json(d):
    """personaje.json guarda las articulaciones como {nombre: [head, tail]}; completa padre/flags. Un modelo
    asimétrico puede traer además un lado suelto (`upper_arm.R`, coordenadas tal cual, sin espejar) que reemplaza a
    ese lado del `.S` (un robot: el brazo derecho pegado al cuerpo y el cañón por fuera; espejado del izquierdo, el
    hueso pasaba por el cañón). Solo brazos: la rodilla se alinea con el `.S` (`rodilla_en_linea`)."""
    J = {}
    for n, (h, t, p, cn, dfm) in PLANTILLA.items():
        if n in d:
            h, t = d[n]
        J[n] = (tuple(h), tuple(t), p, cn, dfm)
    for n in PLANTILLA:   # en el orden de la plantilla: el padre se crea antes
        for sd in ('L', 'R'):
            k = f'{n[:-2]}.{sd}'
            if n.endswith('.S') and k in d:
                h, t = d[k]
                _, _, p, cn, dfm = PLANTILLA[n]
                J[k] = (tuple(h), tuple(t), p and p.replace('.S', f'.{sd}'), cn, dfm)
    return J


def a_json(J):
    return {n: [[round(c, 4) for c in h], [round(c, 4) for c in t]] for n, (h, t, *_) in J.items()}


ADELANTO_RODILLA = 0.011   # fracción de la altura (2 cm en 1,85 m)


def rodilla_en_linea(J):
    """La rodilla (cola del muslo = cabeza de la canilla) y su polo, sobre el plano vertical de la cadera y el
    tobillo: el IK dobla la pierna en el plano en que está doblada en reposo. Con la rodilla a un costado de la línea
    (un muñeco con armadura: 2 cm afuera) ese plano queda en diagonal y la rodilla se abre al doblarse o, si el polo
    la obliga a ir adelante, la canilla entera gira hacia adentro. La rodilla conserva su altura y su adelanto, pero
    nunca menos de ADELANTO_RODILLA de la altura (la plantilla: 2 cm en 1,85 m): con la pierna recta o la rodilla
    apenas atrás (DWPose de costado sobre una pierna recta) el IK la doblaba para atrás al agacharse (patas de fauno)."""
    J = dict(J)
    cad, rod, tob = J['thigh.S'][0], J['thigh.S'][1], J['shin.S'][1]
    t = (cad[2] - rod[2]) / (cad[2] - tob[2]) if cad[2] != tob[2] else 0.5
    y_linea = cad[1] + (tob[1] - cad[1]) * t                  # frente = -Y: adelante es y menor
    minimo = ADELANTO_RODILLA * J['head'][1][2]               # la punta de la cabeza = la altura
    nueva = (cad[0] + (tob[0] - cad[0]) * t, min(rod[1], y_linea - minimo), rod[2])
    J['thigh.S'] = (J['thigh.S'][0], nueva, *J['thigh.S'][2:])
    J['shin.S'] = (nueva, *J['shin.S'][1:])
    for n in ('knee_pole.S',):
        h, tl, *resto = J[n]
        J[n] = ((nueva[0], h[1], h[2]), (nueva[0], tl[1], tl[2]), *resto)
    return J


def construir_rig(col, nombre, J):
    J = rodilla_en_linea(J)
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
        variants = [(name, 1)]
        if name.endswith('.S'):   # sin el lado que viene suelto (desde_json)
            variants = [(name[:-2] + sd, s) for sd, s in (('.L', 1), ('.R', -1)) if name[:-2] + sd not in J]
        for bn, s in variants:
            b = eb.new(bn)
            b.head = (h[0] * s, h[1], h[2]); b.tail = (t[0] * s, t[1], t[2]); b.roll = 0
            if parent:
                b.parent = eb[parent.replace('.S', '.L' if s > 0 else '.R')]
                b.use_connect = connect
            b.use_deform = deform
    for sd in ('L', 'R'):
        eb[f'foot_ik.{sd}'].roll = eb[f'foot.{sd}'].roll
    bpy.ops.object.mode_set(mode='POSE')
    pb = arm.pose.bones
    for sd in ('L', 'R'):
        ik = pb[f'shin.{sd}'].constraints.new('IK')
        ik.target = arm; ik.subtarget = f'foot_ik.{sd}'
        ik.pole_target = arm; ik.pole_subtarget = f'knee_pole.{sd}'
        ik.pole_angle = math.radians(-90); ik.chain_count = 2
        cr = pb[f'foot.{sd}'].constraints.new('COPY_ROTATION')
        cr.target = arm; cr.subtarget = f'foot_ik.{sd}'
    for p in pb:
        p.rotation_mode = 'XYZ'
    bpy.ops.object.mode_set(mode='OBJECT')
    for sd in ('L', 'R'):
        print(f'[rig] polo de la rodilla {sd}: {math.degrees(angulo_polo(arm, sd)):.1f}°')
    return arm


def angulo_polo(arm, sd):
    """pole_angle del IK de la pierna que deja la rodilla en el plano cadera-tobillo-polo, apuntando al polo. Un -90°
    fijo solo sirve con la pierna derecha y vertical; con la pose A (piernas separadas, rodilla doblada en diagonal)
    la rodilla salía de ese plano y al doblarse se abría hacia afuera (en un muñeco con armadura el bueno era
    -30°/-150°). La fórmula clásica (eje X del muslo contra el polo proyectado) tampoco da: se calibra doblando la
    pierna y probando ángulos."""
    pb = arm.pose.bones
    ik = pb[f'shin.{sd}'].constraints['IK']
    B = arm.data.bones
    pie, polo = pb[f'foot_ik.{sd}'], B[f'knee_pole.{sd}'].head_local
    largo = B[f'thigh.{sd}'].length + B[f'shin.{sd}'].length
    pie.location = B[pie.name].matrix_local.to_3x3().inverted() @ Vector((0, -0.15 * largo, 0.3 * largo))
    vl = bpy.context.view_layer

    def error(a):
        ik.pole_angle = math.radians(a); vl.update()
        cadera, rodilla, tobillo = pb[f'thigh.{sd}'].head, pb[f'shin.{sd}'].head, pb[f'foot.{sd}'].head
        n = (tobillo - cadera).cross(polo - cadera).normalized()
        eje = (tobillo - cadera).normalized()
        sale = rodilla - cadera; sale -= eje * sale.dot(eje)          # hacia dónde se dobla la rodilla
        hacia = polo - cadera; hacia -= eje * hacia.dot(eje)
        e = abs(sale.dot(n)) + (1.0 if sale.dot(hacia) < 0 else 0.0)
        # y que en reposo la pierna no quede girada sobre su eje: con la pierna casi recta (un chibi) el ángulo que
        # dobla bien la rodilla podía dejar el muslo girado 180° en reposo, y lo pesado al muslo (el borde del
        # delantal) daba media vuelta en todas las poses
        loc = pie.location.copy(); pie.location = (0, 0, 0); vl.update()
        giro = max(abs(x) for h in ('thigh', 'shin')
                   for fila in pb[f'{h}.{sd}'].matrix.to_3x3() - B[f'{h}.{sd}'].matrix_local.to_3x3() for x in fila)
        pie.location = loc
        return e + giro

    mejor = min(range(-180, 180, 5), key=error)
    mejor = min((mejor + d * 0.5 for d in range(-10, 11)), key=error)
    pie.location = (0, 0, 0); ik.pole_angle = math.radians(mejor); vl.update()
    return math.radians(mejor)


def radio_hueso(bvh, a, b, maximo):
    """Medio ancho de la malla alrededor del hueso a-b: mediana de (pared de un lado + pared del otro) / 2 con rayos
    perpendiculares. Con un solo lado salía 1 cm en la canilla: el hueso no va centrado en el miembro."""
    eje = (b - a).normalized()
    u = eje.orthogonal().normalized(); w = eje.cross(u)
    ds = []
    for t in (0.2, 0.35, 0.5, 0.65, 0.8):
        p = a + (b - a) * t
        for k in range(8):
            d = u * math.cos(math.pi * k / 8) + w * math.sin(math.pi * k / 8)
            h1, h2 = bvh.ray_cast(p, d, maximo), bvh.ray_cast(p, -d, maximo)
            if h1[0] is not None and h2[0] is not None:
                ds.append((h1[3] + h2[3]) / 2)
    return sorted(ds)[len(ds) // 2] if len(ds) >= 8 else None


def distancias_huesos(mesh, arm):
    """(nombres de los huesos que deforman, matriz vértices × huesos): distancia de cada vértice al segmento del
    hueso dividida por el grosor del miembro (`radio_hueso`). ~1 = sobre la piel de ese hueso. Con la distancia sin
    dividir el torso (grueso) perdía contra una mano que lo tocaba."""
    import numpy as np
    from mathutils.bvhtree import BVHTree
    esc = arm.get('escala_plantilla', 1.0)
    bm = bmesh.new(); bm.from_mesh(mesh.data)
    bvh = BVHTree.FromBMesh(bm); bm.free()
    V = np.array([v.co[:] for v in mesh.data.vertices])
    huesos = [b.name for b in arm.data.bones if b.use_deform]
    Q = np.zeros((len(V), len(huesos)))
    for j, n in enumerate(huesos):
        b = arm.data.bones[n]
        r = radio_hueso(bvh, b.head_local, b.tail_local, 0.6 * esc) or 0.05 * esc
        r = min(max(r, 0.015 * esc), 0.5 * esc)
        a, ab = np.array(b.head_local), np.array(b.tail_local - b.head_local)
        t = np.clip(((V - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
        Q[:, j] = np.linalg.norm(V - (a + t[:, None] * ab), axis=1) / r
    return huesos, Q


def pesos_de_distancias(Q, exponente=6.0):
    """Pesos ∝ distancia normalizada ^ -exponente, los 4 huesos más cercanos, normalizados."""
    import numpy as np
    W = np.maximum(Q, 0.25) ** -exponente
    orden = np.argsort(-W, axis=1)
    m = np.zeros(W.shape, dtype=bool)
    np.put_along_axis(m, orden[:, :4], True, axis=1)
    W = np.where(m, W, 0)
    return W / W.sum(1, keepdims=True)


def escribir_pesos(mesh, huesos, W, filas=None):
    """Reemplaza los pesos de los vértices `filas` (todos si None) por las filas de W (columnas = `huesos`)."""
    import numpy as np
    grupos = {n: mesh.vertex_groups.get(n) or mesh.vertex_groups.new(name=n) for n in huesos}
    filas = range(len(W)) if filas is None else filas
    vs = mesh.data.vertices
    for i in filas:
        i = int(i)
        for g in list(vs[i].groups):
            mesh.vertex_groups[g.group].remove([i])
        for j in np.nonzero(W[i] > 1e-3)[0]:
            grupos[huesos[j]].add([i], float(W[i, j]), 'REPLACE')


def pesos_por_distancia(mesh, arm, exponente=6.0):
    """`modelo.pesos: "distancia"`: pesos solo por distancia normalizada a los huesos, sin bone heat. Para mallas
    donde el bone heat da cualquier cosa (dos chibis de un motor viejo, con capas internas y cuerpo redondo;
    el muslo se quedaba con el hombro y la panza se iba con la pierna). En humanoides normales es peor (mezcla las
    piernas en la entrepierna y pega los brazos al torso): no es el método por defecto."""
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_NAME')   # grupos vacíos + modificador Armature
    huesos, Q = distancias_huesos(mesh, arm)
    escribir_pesos(mesh, huesos, pesos_de_distancias(Q, exponente))
    print(f'[blender] pesos por distancia a los huesos (exponente {exponente})')


def _emparentados(B, a, b):
    """mismo hueso, padre/hijo o hermanos (codo, cadera: ahí el bone heat y la distancia pueden diferir sin error)"""
    A, C = B[a], B[b]
    return a == b or A.parent == C or C.parent == A or (A.parent is not None and A.parent == C.parent)


def pesos_de_piezas_sueltas(mesh, arm, por_distancia_todas=False):
    """Las piezas separadas del cuerpo (ojos, cartucheras: TRELLIS.2 las deja sueltas) copian los pesos del
    vértice más cercano de la pieza más grande. Solas, el bone heat las deja sin peso (quedan quietas en el
    aire) o con el hueso equivocado (se despegan al rodar). Si lo copiado no cuadra con los huesos que la pieza
    tiene cerca (más de 1/20 de sus vértices con un hueso que no es el más cercano ni pariente de él), la pieza toma
    los pesos por distancia a los huesos: los pies de un pájaro chibi copiaban el ala (la punta cuelga al lado) y la
    cola medio ala; los zapatos de un chibi, el muslo en vez del pie. Una malla de una pieza no cambia.
    `por_distancia_todas` (`modelo.piezas_por_distancia`): todas menos la más grande por distancia, tengan hueso o no
    (pájaro chibi: la cola es una pieza con el pantalón y con bone heat se estiraba con la pierna)."""
    import numpy as np
    from mathutils.kdtree import KDTree
    vs = mesh.data.vertices
    vecinos = [[] for _ in vs]
    for e in mesh.data.edges:
        a, b = e.vertices
        vecinos[a].append(b); vecinos[b].append(a)
    pieza, n = [-1] * len(vs), 0
    for i0 in range(len(vs)):
        if pieza[i0] >= 0:
            continue
        pila = [i0]; pieza[i0] = n
        while pila:
            for o in vecinos[pila.pop()]:
                if pieza[o] < 0:
                    pieza[o] = n; pila.append(o)
        n += 1
    if n == 1:
        return
    tam = [0] * n
    for p in pieza:
        tam[p] += 1
    # las piezas que tienen adentro el medio de algún hueso son cuerpo y se quedan con el bone heat: en
    # Pixal3D la cabeza puede salir separada del resto en el cuello y ser la más grande (un chibi); tomarla como "el
    # cuerpo" hacía copiar todo lo demás (brazos, piernas) de la cabeza
    P = np.array(pieza)
    V = np.array([v.co[:] for v in vs])
    medios = np.array([(b.head_local + b.tail_local)[:] for b in arm.data.bones if b.use_deform]) / 2
    from mathutils.bvhtree import BVHTree
    cuerpo = {tam.index(max(tam))}
    caras = {}
    for f in mesh.data.polygons:
        caras.setdefault(pieza[f.vertices[0]], []).append(list(f.vertices))
    for p in range(n):
        if tam[p] < 50 or p in cuerpo or por_distancia_todas:
            continue
        lo, hi = V[P == p].min(0), V[P == p].max(0)
        dentro_caja = medios[((medios >= lo) & (medios <= hi)).all(1)]
        if not len(dentro_caja):
            continue
        # adentro de verdad (la caja de la cola de un pájaro chibi llegaba al medio de la cadera): la cara más
        # cercana mira hacia el otro lado
        bvh = BVHTree.FromPolygons([vs[i].co for i in range(len(vs))], caras.get(p, []))
        for m in dentro_caja:
            loc, nor, _, _ = bvh.find_nearest(Vector(m))
            if loc is not None and (Vector(m) - loc).dot(nor) < 0:
                cuerpo.add(p)
                break
    es_cuerpo = np.isin(P, list(cuerpo))
    if es_cuerpo.all():
        return
    kd = KDTree(int(es_cuerpo.sum()))
    for i in np.nonzero(es_cuerpo)[0]:
        kd.insert(vs[int(i)].co, int(i))
    kd.balance()
    huesos, Q = distancias_huesos(mesh, arm)
    col = {g.index: huesos.index(g.name) for g in mesh.vertex_groups if g.name in huesos}
    W = np.zeros(Q.shape)
    for i in np.nonzero(~es_cuerpo)[0]:
        for g in vs[kd.find(vs[int(i)].co)[1]].groups:
            if g.group in col:
                W[i, col[g.group]] = g.weight
    D = pesos_de_distancias(Q)
    por_distancia = []
    for p in set(pieza) - cuerpo:
        idx = np.nonzero(P == p)[0]
        mal = sum(not _emparentados(arm.data.bones, huesos[W[i].argmax()], huesos[D[i].argmax()]) for i in idx)
        if mal > len(idx) / 20 or por_distancia_todas:   # con 1/5 la cola copiaba de los pies y se estiraba con la pierna
            W[idx] = D[idx]
            por_distancia.append(len(idx))
    escribir_pesos(mesh, huesos, W, np.nonzero(~es_cuerpo)[0])
    print(f'[blender] piezas sueltas: {n - len(cuerpo)} ({int((~es_cuerpo).sum())} vértices; {len(cuerpo)} con huesos quedan con el bone heat), pesos copiados del cuerpo'
          + (f'; {len(por_distancia)} por distancia a los huesos ({sum(por_distancia)} vértices)' if por_distancia else ''))


def pesos_rigidos(mesh):
    """`modelo.pesos_rigidos`: cada vértice entero en su hueso dominante, sin mezcla. Para robots y muñecos de bloques
    (un robot): con la mezcla del bone heat el bloque del antebrazo se doblaba en C al levantar el brazo ("brazo de
    goma"); `afinar_pesos` no alcanzaba y suavizar después inflaba la manga. Las caras que unen dos bloques se
    estiran un poco en el borde."""
    grupos = mesh.vertex_groups
    for v in mesh.data.vertices:
        if len(v.groups) < 2:
            continue
        dom = max(v.groups, key=lambda e: e.weight).group
        for g in [g.group for g in v.groups if g.group != dom]:
            grupos[g].remove([v.index])
        grupos[dom].add([v.index], 1.0, 'REPLACE')
    print('[blender] pesos rígidos (un hueso por vértice)')


def pesos_zonas(mesh, zonas):
    """`modelo.pesos_zonas`: [{"min": [x, y, z], "max": [x, y, z], "hueso": nombre}, ...]. Los vértices de la caja
    (coordenadas del modelo, como las articulaciones) quedan enteros en ese hueso: piezas rígidas que el bone heat
    reparte mal. El comunicador de un traje liso de superhéroe en la cadera (a 2 cm de la mano, se iba con el
    antebrazo: "un tercer brazo") y el cañón de un robot por fuera del antebrazo (se estiraba como goma)."""
    import numpy as np
    for z in zonas:
        lo, hi = Vector(z['min']), Vector(z['max'])
        filas = [v.index for v in mesh.data.vertices
                 if all(lo[k] <= (mesh.matrix_world @ v.co)[k] <= hi[k] for k in range(3))]
        escribir_pesos(mesh, [z['hueso']], np.ones((len(mesh.data.vertices), 1)), filas)
        print(f'[blender] zona -> {z["hueso"]}: {len(filas)} vértices')


def girar_antebrazos(mesh, arm, grados):
    """Gira antebrazo y mano de la malla en reposo alrededor del eje codo-muñeca (0 en el codo, todo en la muñeca,
    como el radio sobre el cúbito). + = las palmas hacia el cuerpo. Los modelos salen con las palmas al frente
    (pose A de la imagen): al balancear los brazos la mano quedaba girada hacia afuera. Se hace en la malla (no en
    las poses) para que valga para todas las animaciones, procedurales y de Kimodo. Pesa la suma de pesos del
    antebrazo y la mano, solo en vértices cuyo hueso dominante es del brazo (el suavizado deja algo de peso de la
    mano en el muslo)."""
    from mathutils import Matrix
    B = arm.data.bones
    nom = {g.index: g.name for g in mesh.vertex_groups}
    for sd, sg in (('L', 1), ('R', -1)):
        codo, muneca = B[f'forearm.{sd}'].head_local, B[f'forearm.{sd}'].tail_local
        eje = (muneca - codo).normalized()
        largo = (muneca - codo).length
        brazo = (f'upper_arm.{sd}', f'forearm.{sd}', f'hand.{sd}')
        for v in mesh.data.vertices:
            if not len(v.groups):
                continue
            pesos = {nom[g.group]: g.weight for g in v.groups}
            if max(pesos, key=pesos.get) not in brazo:
                continue
            w = pesos.get(f'forearm.{sd}', 0) + pesos.get(f'hand.{sd}', 0)
            t = min(1.0, max(0.0, (v.co - codo).dot(eje) / largo))
            ang = math.radians(grados) * sg * min(1.0, w) * (3 * t * t - 2 * t * t * t)
            if ang:
                v.co = codo + Matrix.Rotation(ang, 3, eje) @ (v.co - codo)
    print(f'[blender] antebrazos girados {grados:.0f}° (palmas hacia el cuerpo)')


def suavizar_pesos_espacial(mesh, radio):
    """Promedia los pesos de cada vértice con los de todos los que tiene a menos de `radio` (en el espacio, no
    por aristas). TRELLIS.2 arma la ropa como cáscaras finas (capa de afuera y de adentro a milímetros, unidas
    solo en el borde) y el bone heat les da pesos distintos: al moverse, la de adentro atraviesa a la de afuera
    y se ve su revés (manchas, "volados" en el pantalón, "agujeros" en la remera). Suavizar por aristas no
    alcanza: las dos capas están lejos en la malla."""
    from mathutils.kdtree import KDTree
    vs = mesh.data.vertices
    kd = KDTree(len(vs))
    for v in vs:
        kd.insert(v.co, v.index)
    kd.balance()
    viejo = [{x.group: x.weight for x in v.groups} for v in vs]
    grupos = mesh.vertex_groups
    for v in vs:
        acc = {}
        for _, i, d in kd.find_range(v.co, radio):
            k = 1 - d / radio
            for g, w in viejo[i].items():
                acc[g] = acc.get(g, 0) + w * k
        tot = sum(acc.values())
        if not tot:
            continue
        for g in viejo[v.index]:
            grupos[g].remove([v.index])
        for g, w in acc.items():
            if w / tot > 1e-3:
                grupos[g].add([v.index], w / tot, 'REPLACE')
    print(f'[blender] pesos suavizados en el espacio (radio {radio:.3f})')


def afinar_pesos_miembros(mesh, exponente):
    """Achica la zona de mezcla entre los huesos de brazos y piernas: eleva sus pesos a `exponente` y los vuelve a
    repartir dentro de lo que ya tenían entre todos (lo del torso no cambia). En un traje liso de superhéroe el bone
    heat mezclaba brazo y antebrazo en ~27 cm y el codo doblaba como un caño de goma."""
    miembro = ('shoulder.', 'upper_arm.', 'forearm.', 'hand.', 'thigh.', 'shin.', 'foot.')
    grupos = mesh.vertex_groups
    es = {g.index for g in grupos if g.name.startswith(miembro)}
    for v in mesh.data.vertices:
        w = {e.group: e.weight for e in v.groups if e.group in es}
        if len(w) < 2:
            continue
        tot, pot = sum(w.values()), {g: x ** exponente for g, x in w.items()}
        sp = sum(pot.values())
        for g, x in pot.items():
            grupos[g].add([v.index], x / sp * tot, 'REPLACE')
    print(f'[blender] pesos de brazos y piernas afinados (exponente {exponente})')


def _quedarse_con_la_mayor(obj):
    """Borra todas las piezas de `obj` menos la de más vértices."""
    import bmesh
    bm = bmesh.new(); bm.from_mesh(obj.data)
    vistos, piezas = set(), []
    for v0 in bm.verts:
        if v0 in vistos:
            continue
        pila, pieza = [v0], [v0]; vistos.add(v0)
        while pila:
            v = pila.pop()
            for e in v.link_edges:
                o = e.other_vert(v)
                if o not in vistos:
                    vistos.add(o); pila.append(o); pieza.append(o)
        piezas.append(pieza)
    piezas.sort(key=len, reverse=True)
    bmesh.ops.delete(bm, geom=[v for p in piezas[1:] for v in p], context='VERTS')
    bm.to_mesh(obj.data); bm.free()
    return len(piezas)


def pesos_por_copia_estanca(mesh, arm, voxel, datos=None):
    """Bone heat sobre una copia estanca de la malla y pesos pasados a la real por cercanía. La copia es el remesh
    por vóxeles de Blender (lado `voxel`): una sola pieza cerrada, sin las cáscaras de ropa ni las piezas sueltas
    de TRELLIS.2, que es donde el bone heat falla o da pesos distintos a capas pegadas. Cada vértice de la malla
    real toma los pesos interpolados de la cara más cercana de la copia, así las capas de afuera y de adentro
    (y los ojos, cartucheras) quedan con los mismos. `datos`: la malla de la que sale la copia, si no es la de
    `mesh`; tiene que ser la cerrada (antes de `sacar_interior`: con huecos el remesh da cientos de migas).
    Devuelve vértices sin peso de la copia."""
    sc = bpy.context.scene
    copia = mesh.copy(); copia.data = datos or mesh.data.copy(); copia.name = mesh.name + '_estanca'
    sc.collection.objects.link(copia)
    copia.vertex_groups.clear()
    copia.modifiers.clear()
    copia.data.materials.clear()
    mod = copia.modifiers.new('estanca', 'REMESH')
    mod.mode = 'VOXEL'; mod.voxel_size = voxel
    bpy.ops.object.select_all(action='DESELECT')
    copia.select_set(True); bpy.context.view_layer.objects.active = copia
    bpy.ops.object.modifier_apply(modifier=mod.name)
    n = _quedarse_con_la_mayor(copia)
    print(f'[blender] copia estanca: vóxel {voxel:.4f}, {len(copia.data.polygons)} caras, {n} piezas -> 1')
    # bone heat en la copia
    bpy.ops.object.select_all(action='DESELECT')
    copia.select_set(True); arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    sin_peso = sum(1 for v in copia.data.vertices if not any(e.weight > 0.01 for e in v.groups))
    # la malla real: grupos vacíos con los nombres de los huesos + modificador Armature, y los pesos de la copia
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_NAME')
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); bpy.context.view_layer.objects.active = mesh
    dt = mesh.modifiers.new('pesos_estanca', 'DATA_TRANSFER')
    dt.object = copia
    dt.use_vert_data = True
    dt.data_types_verts = {'VGROUP_WEIGHTS'}
    dt.vert_mapping = 'POLYINTERP_NEAREST'
    dt.layers_vgroup_select_src = 'ALL'
    dt.layers_vgroup_select_dst = 'NAME'
    while mesh.modifiers[0] != dt:
        bpy.ops.object.modifier_move_up(modifier=dt.name)
    bpy.ops.object.modifier_apply(modifier=dt.name)
    bpy.data.objects.remove(copia, do_unlink=True)
    return sin_peso


def pesos_automaticos(mesh, arm, radio_suavizado=0.0, voxel_estanca=0.0, datos_estanca=None, piezas_distancia=False):
    """Bone heat (+ suavizado espacial si `radio_suavizado` > 0). Requiere malla soldada (sin cortes en las
    costuras UV). Con `voxel_estanca` > 0 el bone heat se calcula sobre una copia estanca
    (`pesos_por_copia_estanca`). Devuelve vértices sin peso."""
    if voxel_estanca > 0:
        sin_peso = pesos_por_copia_estanca(mesh, arm, voxel_estanca, datos_estanca)
        if radio_suavizado > 0:
            suavizar_pesos_espacial(mesh, radio_suavizado)
        return sin_peso
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    pesos_de_piezas_sueltas(mesh, arm, piezas_distancia)
    if radio_suavizado > 0:
        suavizar_pesos_espacial(mesh, radio_suavizado)
    return sum(1 for v in mesh.data.vertices if not any(e.weight > 0.01 for e in v.groups))


def _saltos(B, a, b):
    """cantidad de huesos entre a y b en el árbol del esqueleto (padre/hijo = 1, hermanos = 2)"""
    def cadena(n):
        c, x = [], B[n]
        while x:
            c.append(x.name); x = x.parent
        return c
    ca, cb = cadena(a), cadena(b)
    return next((i + cb.index(x) for i, x in enumerate(ca) if x in cb), 99)


def cortar_puentes(mesh, arm, saltos=4):
    """Borra las caras que unen partes del cuerpo lejanas en el esqueleto (hueso dominante de sus vértices a `saltos`
    o más huesos de distancia: mano-cadera, antebrazo-muslo, pie-pie) y tapa cada lado. El generador de mallas funde lo
    que se toca o casi: con los pesos bien, esas caras se estiran como una membrana al moverse. El comunicador de un
    traje de superhéroe pegado al antebrazo (una lámina subía con el brazo), la mano de un chibi y de un personaje de
    prueba en el muslo, las alas de un pájaro chibi contra la panza, los zapatos de otro chibi (sábana entre los pies
    al correr). Con 3 saltos hay transiciones legítimas (cuello-hombro, pecho-muslo); la cabeza y el cuello no cuentan
    (en los cabezones el brazo nace pegado a la cabeza). Devuelve cuántas caras."""
    B = arm.data.bones
    esc = arm.get('escala_plantilla', 1.0)
    idx = {g.index: g.name for g in mesh.vertex_groups}
    dom = {}
    for v in mesh.data.vertices:
        if v.groups:
            n = idx.get(max(v.groups, key=lambda e: e.weight).group)
            if n in B:
                dom[v.index] = n
    lejos = {}
    def es_puente(hs):
        hs = sorted(h for h in hs if not h.startswith(('head', 'neck')))
        for a in range(len(hs)):
            for b in range(a + 1, len(hs)):
                k = (hs[a], hs[b])
                if k not in lejos:
                    lejos[k] = _saltos(B, *k) >= saltos
                if lejos[k]:
                    return True
        return False
    bm = bmesh.new(); bm.from_mesh(mesh.data)
    puentes = [f for f in bm.faces if len({dom.get(v.index) for v in f.verts} - {None}) > 1
               and es_puente({dom.get(v.index) for v in f.verts} - {None})]
    if puentes:
        bordes = {e for f in puentes for e in f.edges}
        bmesh.ops.delete(bm, geom=puentes, context='FACES_ONLY')
        # un tapón por agujero: al borrar la tira, el borde de cada lado queda como una componente aparte (las aristas
        # del medio quedan sueltas, no son borde); con un solo llenado salía un polígono que volvía a unir los dos lados
        abiertos = {e for e in bordes if e.is_valid and e.is_boundary}
        uv = bm.loops.layers.uv.active
        nuevas = []
        while abiertos:
            pila, comp = [abiertos.pop()], []
            while pila:
                e = pila.pop(); comp.append(e)
                for v in e.verts:
                    for o in v.link_edges:
                        if o in abiertos:
                            abiertos.discard(o); pila.append(o)
            # solo agujeros chicos (la suela de un zapato): tapar un borde grande y torcido armaba una lámina que
            # cruzaba el cuerpo (el delantal de un chibi quedaba en diagonal); uno grande queda abierto
            cs = [v.co for e in comp for v in e.verts]
            if len(comp) >= 3 and max((a - b).length for a in cs[::4] for b in cs[::4]) < 0.12 * esc:
                nuevas += bmesh.ops.triangle_fill(bm, edges=comp, use_beauty=True, use_dissolve=False)['geom']
        nuevas = [f for f in nuevas if isinstance(f, bmesh.types.BMFace)]
        tapa = set(nuevas)
        for f in nuevas:
            vecina = next((g for e in f.edges for g in e.link_faces if g not in tapa), None)
            if vecina is None:
                continue
            f.material_index = vecina.material_index
            if uv:   # un solo punto de la textura (el de la cara de al lado): color parejo; interpolar
                c = sum((l[uv].uv for l in vecina.loops), vecina.loops[0][uv].uv * 0) / len(vecina.loops)
                for l in f.loops:   # entre islas de UV distintas salían parches de otros colores
                    l[uv].uv = c
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        bm.normal_update()
        bmesh.ops.recalc_face_normals(bm, faces=nuevas)
        bm.to_mesh(mesh.data)
        print(f'[blender] puentes: {len(nuevas)} caras de tapa')
    bm.free()
    return len(puentes)
