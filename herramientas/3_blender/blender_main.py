# Paso 3 (Blender headless). Lo lanza pipeline.py:
#   blender -b --factory-startup --python blender_main.py -- <guia|construir|iso|objeto> <dir>
# guia:      importa la malla y renderiza frente/costado ortográficos + articulaciones (para revisar/ajustar)
# construir: importa, arma rig + pesos, anima (anim.TODAS), guarda trabajo/<n>.blend, renderiza los frames
#            laterales en trabajo/frames/<anim>/NN.png y el retrato/frente en trabajo/retrato/
# objeto:    objetos/<n>/: sin rig; vista lateral + N vistas isométricas -> trabajo/render/
# vehiculo:  objetos/<n>/ con bloque `vehiculo`: largo, simetría, ruedas armadas -> trabajo/vehiculo.glb + revisión
# retrato:   solo el retrato/frente de construir (sin frames ni .blend)
# reves:     rig + poses con las caras de atrás en magenta -> trabajo/reves/ (lo usa el paso revisar)
# iso:       igual que construir pero renderiza las animaciones en 8 direcciones con cámara isométrica -> trabajo/iso/
# alinear:   objeto de Pixal3D de una vista: endereza modelo.glb en el lugar (lo llama el paso malla)
# limpia:    solo importa (soldar, sacar interior) y exporta trabajo/malla/limpia.glb (para re-texturizar)
# anclas:    las mismas animaciones y direcciones que iso, sin renderizar: posición y giro de algunos huesos
#            por cuadro (para colgarle cosas al sprite en el juego: espada en la mano, casco...) -> trabajo/iso/anclas.json
import json, math, os, sys

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Euler, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anim, kimodo_clip, rig_lib, vehiculo  # noqa: E402

modo, pdir = sys.argv[sys.argv.index('--') + 1:][:2]
nombre = os.path.basename(os.path.normpath(pdir))
with open(os.path.join(pdir, 'trabajo', '_config.json')) as f:   # json + estilo, lo escribe pipeline.py
    PJ = json.load(f)
ESTILO = PJ['_estilo']['render']
TRABAJO = os.path.join(pdir, 'trabajo')
GLB = PJ.get('_glb') or os.path.join(TRABAJO, 'malla', 'modelo.glb')   # _glb: un candidato (comparar)
ALTURA = PJ['modelo']['altura']
ORTHO = ALTURA * 1.27          # encuadre con margen para brazos arriba / sombrero
CAM_Z = ALTURA * 0.52


def preparar_escena():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = 32
    sc.render.filter_size = 1.5
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.view_settings.view_transform = 'Standard'  # la textura ya trae el color "horneado"
    sc.render.fps = 12
    w = sc.world or bpy.data.worlds.new('World')
    sc.world = w
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (*ESTILO['ambiente'], 1)
    if ESTILO.get('entorno'):
        entorno(w.node_tree, bg, ESTILO['entorno'])
    for nm, clave in (('Key', 'luz_principal'), ('Fill', 'luz_relleno')):
        L = ESTILO[clave]
        ld = bpy.data.lights.new(nm, 'SUN'); ld.energy = L['energia']; ld.color = L['color']
        lo = bpy.data.objects.new(nm, ld)
        lo.rotation_euler = (math.radians(90 - L['elevacion_grados']), 0, math.radians(L['azimut_grados']))
        sc.collection.objects.link(lo)
    cd = bpy.data.cameras.new('Cam'); cd.type = 'ORTHO'; cd.ortho_scale = ORTHO
    cam = bpy.data.objects.new('Cam', cd)
    sc.collection.objects.link(cam); sc.camera = cam
    return sc, cam


def entorno(nt, bg, puntos):
    """render > entorno [[altura, gris], ...]: el ambiente pasa a ser un degradé de abajo (0) hacia arriba (1), con
    0.5 = horizonte. Con `metal` el material refleja el entorno y uno liso (gris parejo) lo deja opaco: una franja
    clara en el horizonte hace los brillos de metal. El fondo no se ve (film transparente)."""
    tc = nt.nodes.new('ShaderNodeTexCoord'); sx = nt.nodes.new('ShaderNodeSeparateXYZ')
    mp = nt.nodes.new('ShaderNodeMapRange'); mp.inputs['From Min'].default_value = -1   # dirección z: -1..1 -> 0..1
    cr = nt.nodes.new('ShaderNodeValToRGB')
    nt.links.new(tc.outputs['Generated'], sx.inputs[0]); nt.links.new(sx.outputs['Z'], mp.inputs['Value'])
    nt.links.new(mp.outputs['Result'], cr.inputs['Fac'])
    els = cr.color_ramp.elements
    (p0, g0), (p1, g1) = puntos[0], puntos[-1]
    els[0].position, els[0].color = p0, (g0, g0, g0, 1)
    els[1].position, els[1].color = p1, (g1, g1, g1, 1)
    for p, g in puntos[1:-1]:
        els.new(p).color = (g, g, g, 1)
    nt.links.new(cr.outputs['Color'], bg.inputs['Color'])


def sacar_interior(bm, minimo, dos_lados=False):
    """TRELLIS.2 (remesh de o-voxel) entrega capas escondidas: el cuerpo entero debajo de la ropa y, pegada a él,
    la cara interior de la ropa (en un personaje de foto, 3/4 de las caras). No se ven, pero el bone heat les da otros
    pesos y al moverse atraviesan la capa de afuera (manchas, "volados" en el pantalón, "agujeros" en la
    remera). Una cara es interior si ningún rayo hacia donde mira (normal + dos anillos, 45° y 75°) sale de la
    malla; una zona cóncava de afuera (axila, entre mechones) ve el cielo por algún lado. Después saca los
    pedacitos de < `minimo` caras que deja el borrado (como el paso malla: con ellos el bone heat falla).
    `dos_lados` (vehículos): TRELLIS.2 a 1536 trae caras de afuera con la normal al revés y se iban como interiores
    (autos agujereados); así una cara es de afuera si los rayos salen por cualquiera de los dos lados, y si salen solo
    por atrás se da vuelta."""
    from mathutils.bvhtree import BVHTree
    bm.normal_update()
    bvh = BVHTree.FromBMesh(bm)
    anillos = [(math.cos(math.radians(g)), math.sin(math.radians(g))) for g in (45, 75)]
    giros = [(math.cos(k * math.pi / 4), math.sin(k * math.pi / 4)) for k in range(8)]
    interior, al_reves = [], []
    for f in bm.faces:
        n = f.normal
        if n.length < 0.5:
            continue
        t = n.orthogonal().normalized(); b = n.cross(t)
        c = f.calc_center_median()
        dirs = [n] + [n * ca + (t * cg + b * sg) * sa for ca, sa in anillos for cg, sg in giros]
        if all(bvh.ray_cast(c + n * 1e-5, d)[2] is not None for d in dirs):
            if dos_lados and not all(bvh.ray_cast(c - n * 1e-5, -d)[2] is not None for d in dirs):
                al_reves.append(f)
            else:
                interior.append(f)
    if al_reves:
        bmesh.ops.reverse_faces(bm, faces=al_reves)
        print(f'[blender] caras de afuera con la normal al revés: {len(al_reves)} (dadas vuelta)')
    if not interior:
        return
    bmesh.ops.delete(bm, geom=interior, context='FACES')
    bm.faces.ensure_lookup_table()
    visto, piezas = set(), []
    for f0 in bm.faces:
        if f0.index in visto:
            continue
        pila, pieza = [f0], []; visto.add(f0.index)
        while pila:
            f = pila.pop(); pieza.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in visto:
                        visto.add(g.index); pila.append(g)
        piezas.append(pieza)
    piezas.sort(key=len)
    chicas = [f for p in piezas[:-1] if len(p) < minimo for f in p]
    if chicas:
        bmesh.ops.delete(bm, geom=chicas, context='FACES')
    print(f'[blender] capas escondidas de la malla: {len(interior)} caras sacadas '
          f'(+ {len(chicas)} en pedacitos sueltos)')


def importar():
    col = bpy.data.collections.new(nombre)
    bpy.context.scene.collection.children.link(col)
    antes = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=GLB)
    nuevos = [o for o in bpy.data.objects if o not in antes]
    mesh = next(o for o in nuevos if o.type == 'MESH')
    for o in nuevos:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        if o is not mesh:
            bpy.data.objects.remove(o, do_unlink=True)
    col.objects.link(mesh)
    mesh.name = f'{nombre}_malla'
    mesh.parent = None
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if PJ['modelo'].get('alinear') and PJ.get('_objeto') and not PJ.get('vehiculo'):   # los de Pixal3D ya vienen
        alinear_objeto(mesh)                                                           # alineados del paso malla
    # normalizar: altura fija, pies en z=0, centrado en XY (frente = -Y, como sale de TRELLIS.2 y Pixal3D)
    vs = [v.co for v in mesh.data.vertices]
    zmin, zmax = min(v.z for v in vs), max(v.z for v in vs)
    cx = (min(v.x for v in vs) + max(v.x for v in vs)) / 2
    cy = (min(v.y for v in vs) + max(v.y for v in vs)) / 2
    s = ALTURA / (zmax - zmin)
    for v in mesh.data.vertices:
        v.co = Vector(((v.co.x - cx) * s, (v.co.y - cy) * s, (v.co.z - zmin) * s))
    # 'izquierda' (+X) o 'derecha': ese lado se espeja sobre el otro (plano x = 0, el centro de la caja). Solo para
    # modelos en pose simétrica: con un pie adelante o el cuerpo apenas girado (un robot) se rompe; espeja la cara
    if PJ['modelo'].get('simetria') and not PJ.get('vehiculo'):
        vehiculo.simetria(mesh, PJ['modelo']['simetria'])
    # el glTF viene partido en las costuras UV: soldar (el UV es por loop, no se pierde) -> bone heat funciona
    bm = bmesh.new(); bm.from_mesh(mesh.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    if PJ['modelo'].get('pesos_estanca') and modo not in ('objeto', 'limpia'):
        # la copia estanca para los pesos sale de la malla cerrada, antes de sacarle el interior
        mesh['estanca'] = bpy.data.meshes.new(f'{nombre}_cerrada')
        bm.to_mesh(mesh['estanca'])
    # normales consistentes por pieza (TRELLIS.2 a 1536 trae parches al revés: manchas oscuras); en personajes y
    # objetos con modelo.normales (el pecho de plumas de un pájaro chibi salía al revés)
    normales = bool(PJ.get('vehiculo') or PJ['modelo'].get('normales'))
    if normales:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if PJ['malla'].get('sacar_interior', True):
        sacar_interior(bm, 10 if modo == 'objeto' or PJ.get('vehiculo') else 100,   # los mismos mínimos que el paso malla
                       dos_lados=normales)
    if PJ['modelo'].get('alisar_cara'):
        alisar_cara(bm, PJ['modelo']['alisar_cara'])
    if PJ['modelo'].get('ojos') and modo not in ('objeto', 'limpia'):
        parche_ojos(bm, mesh, PJ['modelo']['ojos'])
    bm.to_mesh(mesh.data); bm.free()
    if PJ['modelo'].get('cabeza') and modo not in ('objeto', 'limpia'):
        unir_cabeza(mesh, PJ['modelo']['cabeza'])
    for p in mesh.data.polygons:
        p.use_smooth = True
    for m in mesh.data.materials:
        b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if b:
            b.inputs['Roughness'].default_value = ESTILO['rugosidad']
            b.inputs['Metallic'].default_value = ESTILO.get('metal', 0.0)
            if ESTILO.get('metal_gris'):
                metal_gris(m, b, ESTILO['metal_gris'])
            if ESTILO.get('oscuro_brillante'):
                oscuro_brillante(m, b, ESTILO['oscuro_brillante'])
            if ESTILO.get('oclusion'):
                oclusion(m, b, ESTILO['oclusion'])
            if ESTILO.get('emisivo'):
                emisivo(m, b, ESTILO['emisivo'])
    return col, mesh


def alinear_objeto(mesh):
    """Pixal3D de una vista entrega el objeto en el marco de la cámara (inclinado y girado como en la imagen de tres
    cuartos). Lo apoya y lo endereza: la base (la dirección a menos de 60° de abajo que junta más área de caras, entre
    600 direcciones repartidas en la esfera; después el promedio de las caras a menos de 15°) pasa a mirar a -Z, y la
    huella (rectángulo de área mínima en XY) queda paralela a los ejes. Qué lado es el frente no lo sabe: girarlo con
    modelo.giro_grados. El cofre de Pixal3D venía 21° inclinado y 60° girado."""
    import numpy as np
    from mathutils import Matrix
    camara = Vector((0, -1, 0))   # de dónde miraba la cámara de la imagen (Pixal3D deja el objeto en su marco)
    bm = bmesh.new(); bm.from_mesh(mesh.data); bm.normal_update()
    N = np.array([f.normal[:] for f in bm.faces]); A = np.array([f.calc_area() for f in bm.faces])
    bm.free()
    k = np.arange(600) + 0.5   # direcciones de Fibonacci
    z = 1 - 2 * k / 600; r = np.sqrt(1 - z * z); fi = math.pi * (1 + 5 ** 0.5) * k
    D = np.stack([r * np.cos(fi), r * np.sin(fi), z], 1)
    cerca = np.argmax(N @ D.T, axis=1)
    por_dir = np.bincount(cerca, weights=A, minlength=600)
    por_dir[D[:, 2] > -0.5] = 0
    if por_dir.max() > 0:
        d = D[np.argmax(por_dir)]
        sel = N @ d > math.cos(math.radians(15))
        ref = Vector((N[sel] * A[sel, None]).sum(0)).normalized()
        R = ref.rotation_difference(Vector((0, 0, -1))).to_matrix()
        print(f'[blender] objeto: base inclinada {math.degrees(ref.angle(Vector((0, 0, -1)))):.1f}°, enderezada')
        for v in mesh.data.vertices:
            v.co = R @ v.co
        camara = R @ camara
    vs = [v.co for v in mesh.data.vertices]

    def area(g):
        c, s_ = math.cos(g), math.sin(g)
        u = [c * v.x + s_ * v.y for v in vs]; w = [-s_ * v.x + c * v.y for v in vs]
        return (max(u) - min(u)) * (max(w) - min(w))
    g = min((area(math.radians(k / 2)), math.radians(k / 2)) for k in range(180))[1]
    # de los 4 giros que dejan la huella derecha, el que pone de frente (-Y) el lado que veía la cámara
    c = Matrix.Rotation(-g, 3, 'Z') @ camara
    g += round((math.atan2(c.y, c.x) + math.pi / 2) / (math.pi / 2)) * math.pi / 2
    R = Matrix.Rotation(-g, 3, 'Z')
    for v in mesh.data.vertices:
        v.co = R @ v.co
    print(f'[blender] objeto alineado (huella girada {math.degrees(g):.1f}°)')


def bbox_png(ruta):
    """caja (x0, y0, x1, y1) de lo opaco de un PNG RGBA, con bpy (el Python de Blender no trae Pillow)"""
    import numpy as np
    img = bpy.data.images.load(ruta)
    w, h = img.size
    a = np.array(img.pixels[:], np.float32).reshape(h, w, 4)[::-1, :, 3] > 0.5     # Blender guarda de abajo arriba
    bpy.data.images.remove(img)
    ys, xs = np.where(a)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1, w


def unir_cabeza(mesh, cfg):
    """modelo > cabeza {objeto, recorte: [x0, y0, x1, y1], corte_z, solape?}: reemplaza la cabeza del cuerpo por la
    malla de un objeto hecho aparte con el recorte de la cabeza de la imagen elegida (redibujado con el mismo
    encuadre). De cuerpo entero TRELLIS ve la cara con ~50 px y la deforma; de cerca sale bien. La ubicación sale
    del recorte: la imagen del cuerpo (trabajo/malla/sin_fondo.png) dice cuánto mide cada píxel en el modelo y la de la
    cabeza dónde empieza la cabeza y dónde la corta el borde. El cuerpo se corta en `corte_z` y la cabeza llega
    `solape` más abajo (dentro del cuello de la ropa: sin hueco). `mesh['cabeza_desde']`: primer vértice de la cabeza
    (los pesos los pone pesos_cabeza; un grupo de vértices no sirve, el bone heat lo vacía)."""
    raiz = os.path.dirname(os.path.dirname(os.path.normpath(pdir)))
    odir = os.path.join(raiz, 'objetos', cfg['objeto'], 'trabajo', 'malla')
    bx0, by0, bx1, by1, _ = bbox_png(os.path.join(TRABAJO, 'malla', 'sin_fondo.png'))
    hx0, hy0, hx1, hy1, hw = bbox_png(os.path.join(odir, 'sin_fondo.png'))
    rx0, ry0, rx1, ry1 = cfg['recorte']
    f = (rx1 - rx0) / hw                                   # px de la imagen de la cabeza -> px de la del cuerpo
    alto_px = by1 - by0
    zf = lambda fila: (by1 - fila) / alto_px * ALTURA
    xf = lambda col: (col - (bx0 + bx1) / 2) / alto_px * ALTURA
    z_top, z_bot = zf(ry0 + hy0 * f), zf(ry0 + hy1 * f)
    x_c = xf(rx0 + (hx0 + hx1) / 2 * f)
    antes = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(odir, 'modelo.glb'))
    nuevos = [o for o in bpy.data.objects if o not in antes]
    cab = next(o for o in nuevos if o.type == 'MESH')
    for o in nuevos:
        if o is not cab:
            bpy.data.objects.remove(o, do_unlink=True)
    cab.parent = None
    for c in list(cab.users_collection):
        c.objects.unlink(cab)
    mesh.users_collection[0].objects.link(cab)
    bpy.ops.object.select_all(action='DESELECT')
    cab.select_set(True); bpy.context.view_layer.objects.active = cab
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    vs = [v.co for v in cab.data.vertices]
    zmin, zmax = min(v.z for v in vs), max(v.z for v in vs)
    cx = (min(v.x for v in vs) + max(v.x for v in vs)) / 2
    with open(os.path.join(os.path.dirname(os.path.dirname(odir)), 'objeto.json')) as fo:
        alisar = (json.load(fo).get('modelo') or {}).get('alisar_cara')
    if alisar:                 # en las unidades del objeto normalizado (alto 1.85), como la caja que usa su `textura`
        k0 = ALTURA / (zmax - zmin)
        bm = bmesh.new(); bm.from_mesh(cab.data)
        for v in bm.verts:
            v.co = Vector(((v.co.x - cx) * k0, v.co.y * k0, (v.co.z - zmin) * k0))
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        piezas_chicas(bm, 100)       # láminas sueltas delante de la cara (p. ej. una ceja doble)
        if alisar.get('mascara'):
            mascara_cara(bm, alisar, os.path.join(odir, 'sin_fondo.png'), cab)
        else:
            if alisar.get('rellenar'):
                rellenar_cara(bm, alisar)
            if alisar.get('vueltas'):
                alisar_cara(bm, alisar)
        bm.to_mesh(cab.data); bm.free()
        vs = [v.co for v in cab.data.vertices]
        zmin, zmax, cx = 0.0, ALTURA, 0.0
    k = (z_top - z_bot) / (zmax - zmin)
    for v in cab.data.vertices:
        v.co = Vector((x_c + (v.co.x - cx) * k, v.co.y * k, z_bot + (v.co.z - zmin) * k))
    corte, solape = cfg['corte_z'], cfg.get('solape', 0.02)
    # profundidad: el centro de lo que queda arriba del corte, igual al de la cabeza del cuerpo
    yc = lambda o: (lambda ys: (min(ys) + max(ys)) / 2)([v.co.y for v in o.data.vertices if v.co.z > corte + 0.05])
    dy = yc(mesh) - yc(cab)
    bm = bmesh.new(); bm.from_mesh(cab.data)
    for v in bm.verts:
        v.co.y += dy
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < corte - solape], context='VERTS')
    # sin sacar_interior: los ojos y la boca están hundidos y los tomaba por capas escondidas (quedaban huecos)
    bm.to_mesh(cab.data); bm.free()
    bm = bmesh.new(); bm.from_mesh(mesh.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > corte], context='VERTS')
    bm.to_mesh(mesh.data); bm.free()
    n_cuerpo = len(mesh.data.vertices)
    bpy.ops.object.select_all(action='DESELECT')
    cab.select_set(True); mesh.select_set(True); bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.join()
    mesh['cabeza_desde'] = n_cuerpo      # join pone los vértices de la cabeza después de los del cuerpo
    print(f'[blender] cabeza aparte ({cfg["objeto"]}): escala {k:.3f}, z {z_bot:.3f}-{z_top:.3f}, corte {corte}')


def pesos_cabeza(mesh, arm, J):
    """Pesos de la cabeza aparte: en el cuello los del vértice del cuerpo más cercano, hacia arriba el hueso de la
    cabeza (el bone heat le daba a una pieza suelta los del cuello entero)."""
    from mathutils.kdtree import KDTree
    if 'cabeza_desde' not in mesh:
        return
    es_cab = [v.index >= mesh['cabeza_desde'] for v in mesh.data.vertices]
    cuerpo = [v for v, c in zip(mesh.data.vertices, es_cab) if not c]
    kd = KDTree(len(cuerpo))
    for i, v in enumerate(cuerpo):
        kd.insert(v.co, i)
    kd.balance()
    nombres = {vg.index: vg.name for vg in mesh.vertex_groups}
    z0, z1 = J['neck'][0][2], J['head'][0][2] + 0.03
    hg = mesh.vertex_groups['head']
    copias = []
    for v, c in zip(mesh.data.vertices, es_cab):
        if not c:
            continue
        _, j, _ = kd.find(v.co)
        t = min(1.0, max(0.0, (v.co.z - z0) / (z1 - z0)))
        t = t * t * (3 - 2 * t)
        pesos = {nombres[e.group]: e.weight * (1 - t) for e in cuerpo[j].groups}
        pesos['head'] = pesos.get('head', 0.0) + t
        copias.append((v.index, pesos))
    for vi, pesos in copias:
        for vg in mesh.vertex_groups:
            vg.remove([vi])
        for n, w in pesos.items():
            if w > 0.001:
                mesh.vertex_groups[n].add([vi], w, 'REPLACE')
    print(f'[blender] pesos de la cabeza aparte: {len(copias)} vértices')


def piezas_chicas(bm, minimo):
    """borra las piezas sueltas de menos de `minimo` vértices (no la más grande)"""
    visto, piezas = set(), []
    for v0 in bm.verts:
        if v0 in visto:
            continue
        pila, pieza = [v0], []; visto.add(v0)
        while pila:
            v = pila.pop(); pieza.append(v)
            for e in v.link_edges:
                o = e.other_vert(v)
                if o not in visto:
                    visto.add(o); pila.append(o)
        piezas.append(pieza)
    piezas.sort(key=len)
    chicas = [v for p in piezas[:-1] if len(p) < minimo for v in p]
    if chicas:
        bmesh.ops.delete(bm, geom=chicas, context='VERTS')
        print(f'[blender] piezas sueltas chicas: {len(chicas)} vértices')


def erosionar(m, n):
    import numpy as np
    for _ in range(n):
        p = np.pad(m, 1, constant_values=False)
        m = p[1:-1, 1:-1] & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    return m


def dilatar(m, n):
    import numpy as np
    for _ in range(n):
        p = np.pad(m, 1, constant_values=False)
        m = p[1:-1, 1:-1] | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    return m


def mayor_mancha(m, borde=False):
    """la mancha (4-vecinos) más grande de una máscara; borde=True: todas las que tocan el borde (para rellenar
    huecos: lo que no las toca es un hueco)"""
    import numpy as np
    from collections import deque
    lab = np.zeros(m.shape, int); n = 0; tam = [0]; toca = [False]
    H, W = m.shape
    for i0, j0 in zip(*np.nonzero(m)):
        if lab[i0, j0]:
            continue
        n += 1; tam.append(0); toca.append(False)
        q = deque([(i0, j0)]); lab[i0, j0] = n
        while q:
            i, j = q.popleft(); tam[n] += 1
            if i in (0, H - 1) or j in (0, W - 1):
                toca[n] = True
            for a, b in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                if 0 <= a < H and 0 <= b < W and m[a, b] and not lab[a, b]:
                    lab[a, b] = n; q.append((a, b))
    if not n:
        return m
    if borde:
        return np.isin(lab, [k for k in range(1, n + 1) if toca[k]])
    return lab == int(np.argmax(tam))


def mapa_cara(bm, cfg, paso):
    """alto (-y) de lo de adelante de la cabeza en una grilla sobre la caja; celdas vacías: la vecina más cercana"""
    import numpy as np
    x0, x1, z0, z1 = cfg['caja']
    nx, nz = int((x1 - x0) / paso) + 1, int((z1 - z0) / paso) + 1
    en = [v for v in bm.verts if x0 < v.co.x < x1 and z0 < v.co.z < z1]
    frente = min(v.co.y for v in en)
    hondo = cfg.get('hondo', 0.06)
    alto = np.full((nz, nx), -np.inf)
    for v in en:
        if v.co.y <= frente + hondo:
            i, j = int((v.co.z - z0) / paso), int((v.co.x - x0) / paso)
            alto[i, j] = max(alto[i, j], -v.co.y)
    lleno = np.isfinite(alto)
    ii, jj = np.nonzero(lleno)
    for i, j in zip(*np.nonzero(~lleno)):
        k = np.argmin((ii - i) ** 2 + (jj - j) ** 2)
        alto[i, j] = alto[ii[k], jj[k]]
    return alto, en, frente, hondo


def mascara_cara(bm, cfg, img_ruta, obj):
    """alisar_cara > mascara (radio, m): el frente de la cara pasa a ser una superficie nueva, lisa (los ojos de TRELLIS
    son cráteres con el borde volcado: al inclinar la cabeza tapaban el iris, y deformarlos rompía boca y cejas), con
    la imagen de la cabeza mapeada directo (UV = píxel de la imagen, como la proyección de `textura`). Alto: el mapa
    de lo de adelante con los pozos más angostos que `mascara` cerrados y suavizado. Es un óvalo inscripto en la caja:
    la malla original queda 6 mm detrás en todo el óvalo; en el borde (`borde_ovalo`, fracción del radio) la máscara
    vuelve a la altura de la superficie de antes. Con un rectángulo el borde se veía dentado y con una transición larga
    a la misma profundidad las dos superficies se peleaban (manchas). Material `mascara_cara`."""
    import numpy as np
    paso = cfg.get('paso', 0.006)
    x0, x1, z0, z1 = cfg['caja']
    alto, en, frente, hondo = mapa_cara(bm, cfg, paso)
    r = max(1, int(cfg['mascara'] / paso))
    def filtro(a, f, r):
        p = np.pad(a, r, mode='edge')
        return f([p[r + di:r + di + a.shape[0], r + dj:r + dj + a.shape[1]]
                  for di in range(-r, r + 1) for dj in range(-r, r + 1) if di * di + dj * dj <= r * r], axis=0)
    cerr = filtro(filtro(alto, np.max, r), np.min, r)
    for _ in range(cfg.get('suavizar', 3)):     # los rasgos los pone la imagen; los relieves de mechones, no
        cerr = filtro(cerr, np.mean, 3)
    nz, nx = cerr.shape
    jj, ii = np.meshgrid(np.arange(nx), np.arange(nz))
    rho = np.hypot((jj - (nx - 1) / 2) / ((nx - 1) / 2), (ii - (nz - 1) / 2) / ((nz - 1) / 2))   # óvalo en la caja
    t = np.clip((1 - rho) / cfg.get('borde_ovalo', 0.25), 0, 1)
    w = t * t * (3 - 2 * t)
    sup = alto + (cerr - alto) * w
    # piel en la imagen (ni pelo ni fondo): la máscara va solo ahí; el pelo de adelante queda con su forma
    ix0, iy0, ix1, iy1, iw = bbox_png(img_ruta)
    s_px = (iy1 - iy0) / ALTURA
    img = bpy.data.images.load(img_ruta)
    px = np.array(img.pixels[:], np.float32).reshape(img.size[1], img.size[0], 4)[::-1]
    bpy.data.images.remove(img)
    X = np.clip(((ix0 + ix1) / 2 + (x0 + jj * paso) * s_px).astype(int), 0, iw - 1)
    Y = np.clip((iy0 + (ALTURA - (z0 + ii * paso)) * s_px).astype(int), 0, px.shape[0] - 1)
    c = px[Y, X]
    lum = c[..., :3] @ np.array([0.3, 0.59, 0.11])
    piel = (c[..., 3] > 0.9) & (lum > cfg.get('piel_min', 0.45)) & (c[..., 0] > c[..., 2] + 0.05)
    # pelo = lo que no es piel y llega al borde del óvalo; las uniones finas (delineado, pestañas contra un mechón) se
    # cortan antes, si no los ojos contaban como pelo. Lo que no es piel adentro (ojos, cejas, boca) es de la cara.
    afuera = ~piel | (rho >= 1)
    r_corte = cfg.get('corte_pelo', 3)
    exterior = mayor_mancha(erosionar(afuera, r_corte) | (rho >= 1), borde=True)
    pelo = dilatar(exterior, r_corte + 1) & afuera
    piel = ~pelo & (rho < 1)
    piel = mayor_mancha(erosionar(piel, 1))
    piel_cerca = dilatar(piel, 1)
    # la malla original: lo de adelante dentro de la máscara, 6 mm detrás
    for v in en:
        if v.co.y <= frente + hondo:
            i, j = min(nz - 1, int((v.co.z - z0) / paso)), min(nx - 1, int((v.co.x - x0) / paso))
            y_m = -sup[i, j]
            if piel_cerca[i, j] and v.co.y < y_m + 0.006:      # la cara de antes detrás de la máscara
                v.co.y = y_m + 0.006
    # píxeles: como retocar.py (alto del objeto = alto de lo opaco de la imagen, centrado en x)
    ih = iw
    uv_de = lambda x, z: (((ix0 + ix1) / 2 + x * s_px) / iw, 1 - (iy0 + (ALTURA - z) * s_px) / ih)
    uv = bm.loops.layers.uv.active
    mat_i = len(obj.data.materials)
    vg = {}
    for i in range(nz):
        for j in range(nx):
            # en el borde del óvalo la máscara queda detrás de la cara de antes (se funde sin escalón)
            vg[i, j] = bm.verts.new((x0 + j * paso, -sup[i, j], z0 + i * paso))
    for i in range(nz - 1):
        for j in range(nx - 1):
            if not (piel[i, j] and piel[i, j + 1] and piel[i + 1, j + 1] and piel[i + 1, j]):
                continue
            f = bm.faces.new((vg[i, j], vg[i, j + 1], vg[i + 1, j + 1], vg[i + 1, j]))
            f.material_index = mat_i
            for l in f.loops:
                l[uv].uv = uv_de(l.vert.co.x, l.vert.co.z)
            f.normal_flip() if f.normal.y > 0 else None
    bmesh.ops.delete(bm, geom=[v for v in vg.values() if not v.link_faces], context='VERTS')
    m = bpy.data.materials.new('mascara_cara'); m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    t = m.node_tree.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(img_ruta)
    m.node_tree.links.new(t.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = ESTILO['rugosidad']
    b.inputs['Metallic'].default_value = ESTILO.get('metal', 0.0)
    obj.data.materials.append(m)
    print(f'[blender] máscara de la cara: {nx}x{nz} ({cfg["mascara"]} m de cierre)')


def rellenar_cara(bm, cfg):
    """alisar_cara > rellenar (radio, m): TRELLIS hace los ojos como cráteres con el borde volcado hacia adentro (un
    pliegue de la misma superficie): de frente se ve el fondo con el iris proyectado y apenas se inclina la cabeza el
    borde lo tapa (manchas). El alisado por vecinos no deshace pliegues. Mapa de profundidad de lo de adelante en una
    grilla, cierre morfológico (llena los pozos más angostos que `radio`, conserva lo que sobresale: nariz, cachetes)
    y lo que quedó detrás de esa superficie se trae hasta ella. Solo en profundidad: la proyección sigue calzando."""
    import numpy as np
    x0, x1, z0, z1 = cfg['caja']
    paso = 0.01
    nx, nz = int((x1 - x0) / paso) + 1, int((z1 - z0) / paso) + 1
    en = [v for v in bm.verts if x0 < v.co.x < x1 and z0 < v.co.z < z1]
    frente = min(v.co.y for v in en)
    hondo = cfg.get('hondo', 0.06)
    alto = np.full((nz, nx), -np.inf)                     # alto = -y: más grande = más adelante
    for v in en:
        if v.co.y <= frente + hondo:
            i, j = int((v.co.z - z0) / paso), int((v.co.x - x0) / paso)
            alto[i, j] = max(alto[i, j], -v.co.y)
    lleno = np.isfinite(alto)
    if not lleno.any():
        return
    ii, jj = np.nonzero(lleno)
    for i, j in zip(*np.nonzero(~lleno)):                 # celdas vacías: la más cercana con algo
        k = np.argmin((ii - i) ** 2 + (jj - j) ** 2)
        alto[i, j] = alto[ii[k], jj[k]]
    r = max(1, int(cfg['rellenar'] / paso))
    def filtro(a, f):
        p = np.pad(a, r, mode='edge')
        return f([p[r + di:r + di + a.shape[0], r + dj:r + dj + a.shape[1]]
                  for di in range(-r, r + 1) for dj in range(-r, r + 1) if di * di + dj * dj <= r * r], axis=0)
    cerrado = filtro(filtro(alto, np.max), np.min)        # dilatar y erosionar: cierra los pozos
    borde = cfg.get('borde', 0.03)
    n = 0
    for v in en:
        i, j = int((v.co.z - z0) / paso), int((v.co.x - x0) / paso)
        y_sup = -cerrado[i, j]
        if v.co.y > y_sup + 0.003 and v.co.y <= frente + hondo:
            d = min(v.co.x - x0, x1 - v.co.x, v.co.z - z0, z1 - v.co.z)
            w = min(1.0, d / borde)
            v.co.y += (y_sup - v.co.y) * w
            n += 1
    print(f'[blender] cara rellenada: {n} vértices traídos a la superficie (radio {cfg["rellenar"]})')


def alisar_cara(bm, cfg):
    """modelo > alisar_cara {caja: [x0, x1, z0, z1], vueltas, borde}: alisa la forma de la cara (lo que mira al frente
    dentro de la caja, en unidades del modelo normalizado). En una imagen de cuerpo entero TRELLIS esculpe una cara
    que no es la de la imagen (boca seria, cuencas); con la cara de la imagen proyectada (textura modo frente) la luz
    dibujaba esa boca debajo de la sonrisa ("fantasma"). Alisada, los rasgos los pone la textura. Se mueve solo en
    profundidad (y): con un alisado común los vértices se corren de costado y la textura se estira. `borde` (m): ancho
    de la transición en los bordes de la caja. La misma caja hace que `textura` proyecte la cara entera, sin mezclar."""
    x0, x1, z0, z1 = cfg['caja']
    borde = cfg.get('borde', 0.03)
    en_caja = [v for v in bm.verts if x0 < v.co.x < x1 and z0 < v.co.z < z1]
    if not en_caja:
        return
    frente = min(v.co.y for v in en_caja)
    hondo = cfg.get('hondo', 0.06)       # lo de adelante de la cabeza (frente = -y); los costados de la nariz también:
    peso = {}                            # si quedan fijos, la sostienen y no se alisa
    for v in en_caja:
        if v.co.y > frente + hondo:
            continue
        d = min(v.co.x - x0, x1 - v.co.x, v.co.z - z0, z1 - v.co.z)
        peso[v] = min(1.0, d / borde) * min(1.0, (frente + hondo - v.co.y) / 0.02)
    for _ in range(int(cfg.get('vueltas', 40))):
        nuevo = {}
        for v, w in peso.items():
            vec = [e.other_vert(v).co for e in v.link_edges]
            if vec:
                prom = sum(vec, Vector()) / len(vec)        # solo en profundidad: de costado la textura se estira
                nuevo[v] = Vector((v.co.x, v.co.y + (prom.y - v.co.y) * 0.5 * w, v.co.z))
        for v, c in nuevo.items():
            v.co = c
    print(f'[blender] cara alisada: {len(peso)} vértices')


def textura_ojo(cfg, rx, rz):
    """Imagen del ojo para el disco de parche_ojos (u, v = -1..1 sobre los radios): esclerótica con la sombra del
    párpado de arriba, iris (más oscuro en el centro y el borde), pupila y un brillo. Valores sRGB."""
    import numpy as np
    W, H = 512, 256
    U, V = np.meshgrid((np.arange(W) + 0.5) / W * 2 - 1, (np.arange(H) + 0.5) / H * 2 - 1)  # fila 0 = abajo
    X, Z = U * rx, V * rz
    c = lambda rgb: np.array(rgb, np.float64) / 255
    def pintar(img, r, radio, color):
        a = np.clip((radio - r) / 0.0003, 0, 1)[..., None]
        return img * (1 - a) + color * a
    img = np.empty((H, W, 3)); img[:] = c(cfg.get('esclerotica', (232, 224, 218)))
    img *= (1 - 0.4 * np.clip(V, 0, 1) ** 1.3)[..., None]
    ri, rp, alto = cfg.get('iris_radio', 0.0062), cfg.get('pupila_radio', 0.0024), cfg.get('iris_alto', 0.0012)
    r = np.hypot(X, Z - alto)
    iris = c(cfg.get('iris', (88, 50, 28))) * (0.7 + 0.55 * np.clip(r / ri, 0, 1))[..., None]
    iris *= (1 - 0.45 * np.clip((Z - 0.001) / 0.005, 0, 1))[..., None]        # sombra del párpado
    b = np.clip((r - ri * 0.85) / (ri * 0.15), 0, 1)[..., None]
    iris = iris * (1 - b) + iris * 0.45 * b
    img = pintar(img, r, ri, iris)
    img = pintar(img, r, rp, c((10, 7, 5)))
    img = pintar(img, np.hypot(X - ri * 0.3, Z - alto - ri * 0.23), ri * 0.16, c((255, 255, 255)))
    im = bpy.data.images.new('ojo', W, H)
    im.pixels.foreach_set(np.concatenate([img, np.ones((H, W, 1))], -1).astype(np.float32).ravel())
    im.pack()
    return im


def sin_manchitas(m, minimo):
    """la máscara m sin sus manchas conexas (4-vecinos) de menos de `minimo` celdas"""
    import numpy as np
    m = m.copy(); visto = np.zeros_like(m)
    for j0, i0 in zip(*np.nonzero(m)):
        if visto[j0, i0]:
            continue
        pila, mancha = [(j0, i0)], []; visto[j0, i0] = True
        while pila:
            j, i = pila.pop(); mancha.append((j, i))
            for a, b in ((j + 1, i), (j - 1, i), (j, i + 1), (j, i - 1)):
                if 0 <= a < m.shape[0] and 0 <= b < m.shape[1] and m[a, b] and not visto[a, b]:
                    visto[a, b] = True; pila.append((a, b))
        if len(mancha) < minimo:
            for c in mancha:
                m[c] = False
    return m


def parche_ojos(bm, mesh, cfg):
    """modelo > ojos {centros: [[x, z], ...], radio: [rx, rz], tapar: [[x0, z0, x1, z1], ...], iris, ...}: TRELLIS a
    veces deja el ojo como un cráter arrugado que sacar_interior borra: queda un agujero al interior de la cabeza.
    Por ojo, un disco elíptico (algo abombado) apenas detrás del borde del párpado, con un ojo dibujado
    (textura_ojo). `tapar`: cajas (vista de frente) donde lo que es agujero o borde hundido gris (el cráter volcado)
    se tapa con una superficie color piel, a la profundidad interpolada de lo de alrededor. Las piezas quedan
    sueltas: pesos_de_piezas_sueltas les copia los pesos del vértice más cercano (siguen a la cabeza)."""
    import numpy as np
    from mathutils.bvhtree import BVHTree
    from mathutils.geometry import barycentric_transform
    originales = list(bm.faces)                                       # el BVH es de estas (después se agregan)
    bvh = BVHTree.FromBMesh(bm)
    uv = bm.loops.layers.uv.active
    tex = next(n.image for n in mesh.data.materials[0].node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
    T = tex.size[0]
    tp = np.empty(T * T * 4, np.float32); tex.pixels.foreach_get(tp); tp = tp.reshape(T, T, 4)

    def frente(x, z):
        """y y color (sRGB) de lo primero que se ve desde adelante; y = 9 si no hay nada"""
        p, _, fi, _ = bvh.ray_cast(Vector((x, -5, z)), Vector((0, 1, 0)))
        if p is None:
            return 9.0, (0, 0, 0)
        a, b, c = originales[fi].loops[:3]                            # TRELLIS: triángulos
        q = barycentric_transform(p, a.vert.co, b.vert.co, c.vert.co, a[uv].uv.to_3d(), b[uv].uv.to_3d(),
                                  c[uv].uv.to_3d())
        return p.y, tuple(tp[min(max(int(q.y * T), 0), T - 1), min(max(int(q.x * T), 0), T - 1), :3])

    rx, rz = cfg.get('radio', (0.0155, 0.0075))
    bulto = cfg.get('bulto', 0.004)
    centros = cfg['centros']
    nuevas = []

    # piel: tapar agujeros y bordes grises en las cajas
    st = 0.0005
    tapadas = 0
    for x0, z0, x1, z1 in cfg.get('tapar', []):
        xs = np.arange(x0, x1, st); zs = np.arange(z0, z1, st)
        p = np.empty((len(zs), len(xs))); col = np.empty((len(zs), len(xs), 3))
        for j, z in enumerate(zs):
            for i, x in enumerate(xs):
                p[j, i], col[j, i] = frente(x, z)
        X, Z = np.meshgrid(xs, zs)
        en_ojo = np.zeros_like(p, bool)
        for cx, cz in centros:
            en_ojo |= ((X - cx) / rx) ** 2 + ((Z - cz) / rz) ** 2 < 1
        lum = col.mean(2)
        gris = (np.abs(col[..., 0] - col[..., 2]) < 0.08) & (lum > 0.4)
        lejos = np.median(p[p < 5]) + 0.1          # agujero: se ve el fondo de la cabeza (la sien solo se curva)
        d = ((p > lejos) | gris) & ~en_ojo
        d = sin_manchitas(d, cfg.get('tapar_min', 40))                 # brillos sueltos del pelo: no
        dil = lambda m: m | np.roll(m, 1, 0) | np.roll(m, -1, 0) | np.roll(m, 1, 1) | np.roll(m, -1, 1)
        for _ in range(2):
            d = dil(d)
        d &= ~en_ojo
        d[0] = d[-1] = d[:, 0] = d[:, -1] = False
        # Laplace: lo tapado sigue a la piel de alrededor (no al pelo, la ceja ni el fondo del agujero del ojo)
        fijo = ~d & (p < lejos) & ~en_ojo & ~gris & (lum > 0.4)
        yy = np.where(fijo, p, np.median(p[fijo]))
        for _ in range(800):
            yy = np.where(fijo, yy, (np.roll(yy, 1, 0) + np.roll(yy, -1, 0) + np.roll(yy, 1, 1) + np.roll(yy, -1, 1)) / 4)
        anillo = d.copy()
        for _ in range(6):
            anillo = dil(anillo)
        anillo &= ~d & ~gris & (lum > 0.6) & (p < 5)
        piel = np.median(col[anillo], 0) if anillo.any() else np.array((0.85, 0.7, 0.62))
        mat = bpy.data.materials.new('parche_piel'); mat.use_nodes = True
        next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED').inputs['Base Color'].default_value = \
            (*(piel ** 2.2), 1)
        mesh.data.materials.append(mat); mi = len(mesh.data.materials) - 1
        vid = {}
        def vert(j, i):
            """esquina (j, i) de las celdas: profundidad = promedio de las celdas tapadas que la tocan"""
            if (j, i) not in vid:
                ys = [yy[a, b] for a in (j - 1, j) for b in (i - 1, i) if d[a, b]]
                vid[(j, i)] = bm.verts.new((xs[i] - st / 2, sum(ys) / len(ys) + 0.0012, zs[j] + st / 2))
            return vid[(j, i)]                                            # (+1,2 mm: detrás de lo de alrededor)
        for j, i in zip(*np.nonzero(d)):
            f = bm.faces.new((vert(j, i), vert(j + 1, i), vert(j + 1, i + 1), vert(j, i + 1)))
            f.material_index = mi; nuevas.append(f)
        tapadas += int(d.sum())

    # ojos: disco detrás del borde del párpado (lo más atrás del borde + 3 mm)
    im = textura_ojo(cfg, rx, rz)
    mat = bpy.data.materials.new('ojo'); mat.use_nodes = True
    nt = mat.node_tree
    tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = im
    nt.links.new(tx.outputs['Color'], next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED').inputs['Base Color'])
    mesh.data.materials.append(mat); mi = len(mesh.data.materials) - 1
    NR, NS = 8, 48
    for cx, cz in centros:
        borde = [frente(cx + rx * 1.15 * math.cos(a), cz + rz * 1.15 * math.sin(a))[0]
                 for a in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
        borde = [y for y in borde if y < 5]
        y_borde = max(y for y in borde if y < np.median(borde) + 0.02) + 0.003
        c = bm.verts.new((cx, y_borde - bulto, cz))
        anillos = [[bm.verts.new((cx + rx * r * math.cos(2 * math.pi * k / NS), y_borde - bulto * (1 - r * r),
                                  cz + rz * r * math.sin(2 * math.pi * k / NS))) for k in range(NS)]
                   for r in (i / NR for i in range(1, NR + 1))]
        caras = [bm.faces.new((c, anillos[0][k], anillos[0][(k + 1) % NS])) for k in range(NS)]
        for a, b in zip(anillos, anillos[1:]):
            caras += [bm.faces.new((a[k], b[k], b[(k + 1) % NS], a[(k + 1) % NS])) for k in range(NS)]
        for f in caras:
            f.material_index = mi
            for lp in f.loops:
                lp[uv].uv = ((lp.vert.co.x - cx) / rx * 0.5 + 0.5, (lp.vert.co.z - cz) / rz * 0.5 + 0.5)
        nuevas += caras
        print(f'[blender] ojo en ({cx:.3f}, {cz:.3f}): borde del párpado y={y_borde - 0.003:.3f}')
    for f in nuevas:                                                 # que miren al frente (-y)
        f.normal_update()
        if f.normal.y > 0:
            f.normal_flip()
    print(f'[blender] parche de ojos: {len(centros)} ojos, {tapadas} celdas de piel tapadas')


def metal_gris(m, b, mg):
    """render > metal_gris [sat_metal, sat_no_metal]: solo es metal lo gris/blanco de la textura (UltraTex hornea solo
    el color base). Saturación <= sat_metal -> Metallic = render.metal y Roughness = render.rugosidad_metal; >=
    sat_no_metal -> 0 y render.rugosidad. Probado en una armadura cromada sobre músculo rojo."""
    if not b.inputs['Base Color'].is_linked:
        return
    nt = m.node_tree
    sep = nt.nodes.new('ShaderNodeSeparateColor'); sep.mode = 'HSV'
    nt.links.new(b.inputs['Base Color'].links[0].from_socket, sep.inputs['Color'])
    for entrada, a, z in (('Metallic', ESTILO.get('metal', 0.8), 0.0),
                          ('Roughness', ESTILO.get('rugosidad_metal', ESTILO['rugosidad']), ESTILO['rugosidad'])):
        mr = nt.nodes.new('ShaderNodeMapRange'); mr.interpolation_type = 'SMOOTHSTEP'
        mr.inputs['From Min'].default_value, mr.inputs['From Max'].default_value = mg
        mr.inputs['To Min'].default_value, mr.inputs['To Max'].default_value = a, z
        nt.links.new(sep.outputs[1], mr.inputs['Value'])
        nt.links.new(mr.outputs['Result'], b.inputs[entrada])


def oscuro_brillante(m, b, ob):
    """render > oscuro_brillante {valor, saturacion, rugosidad}: lo oscuro y sin color de la textura (visores, vidrios,
    partes negras) con otra rugosidad, como el material `oscuro` de los vehículos (vehiculo.separar_materiales), pero
    por píxel. Brillo (V de HSV) < valor y saturación < saturacion -> Roughness = rugosidad (con un borde suave)."""
    if not b.inputs['Base Color'].is_linked:
        return
    nt = m.node_tree
    sep = nt.nodes.new('ShaderNodeSeparateColor'); sep.mode = 'HSV'
    nt.links.new(b.inputs['Base Color'].links[0].from_socket, sep.inputs['Color'])
    mascaras = []
    for canal, tope in ((2, ob.get('valor', 0.12)), (1, ob.get('saturacion', 0.35))):
        mr = nt.nodes.new('ShaderNodeMapRange'); mr.interpolation_type = 'SMOOTHSTEP'
        mr.inputs['From Min'].default_value, mr.inputs['From Max'].default_value = tope, tope * 1.5
        mr.inputs['To Min'].default_value, mr.inputs['To Max'].default_value = 1.0, 0.0
        nt.links.new(sep.outputs[canal], mr.inputs['Value'])
        mascaras.append(mr)
    por = nt.nodes.new('ShaderNodeMath'); por.operation = 'MULTIPLY'
    nt.links.new(mascaras[0].outputs['Result'], por.inputs[0]); nt.links.new(mascaras[1].outputs['Result'], por.inputs[1])
    mix = nt.nodes.new('ShaderNodeMapRange')
    mix.inputs['To Min'].default_value = ESTILO['rugosidad']; mix.inputs['To Max'].default_value = ob.get('rugosidad', 0.12)
    nt.links.new(por.outputs['Value'], mix.inputs['Value'])
    nt.links.new(mix.outputs['Result'], b.inputs['Roughness'])


def emisivo(m, b, em):
    """render > emisivo {tono: [min, max] (grados), saturacion, valor, fuerza}: lo que tiene ese color en la textura
    brilla (emisión = el color base × fuerza): metal fundido, brasas, lava, pantallas. Ningún motor pinta algo
    incandescente: la textura lo trae naranja plano. Máscara = tono adentro del rango × saturación >= saturacion ×
    brillo (V) >= valor, con bordes suaves. Lo apagado no cambia."""
    if not b.inputs['Base Color'].is_linked:
        return
    nt = m.node_tree
    src = b.inputs['Base Color'].links[0].from_socket
    sep = nt.nodes.new('ShaderNodeSeparateColor'); sep.mode = 'HSV'
    nt.links.new(src, sep.inputs['Color'])
    t0, t1 = (x / 360 for x in em.get('tono', [15, 60]))
    mascaras = []
    for canal, desde, hasta in ((0, t0 - 0.02, t0 + 0.02), (0, t1 + 0.02, t1 - 0.02),
                                (1, em.get('saturacion', 0.5) - 0.1, em.get('saturacion', 0.5)),
                                (2, em.get('valor', 0.6) - 0.1, em.get('valor', 0.6))):
        mr = nt.nodes.new('ShaderNodeMapRange'); mr.interpolation_type = 'SMOOTHSTEP'
        mr.inputs['From Min'].default_value, mr.inputs['From Max'].default_value = desde, hasta
        nt.links.new(sep.outputs[canal], mr.inputs['Value'])
        mascaras.append(mr.outputs['Result'])
    total = mascaras[0]
    for otra in mascaras[1:]:
        por = nt.nodes.new('ShaderNodeMath'); por.operation = 'MULTIPLY'
        nt.links.new(total, por.inputs[0]); nt.links.new(otra, por.inputs[1])
        total = por.outputs['Value']
    fuerza = nt.nodes.new('ShaderNodeMath'); fuerza.operation = 'MULTIPLY'
    fuerza.inputs[1].default_value = em.get('fuerza', 1.0)
    nt.links.new(total, fuerza.inputs[0])
    nt.links.new(src, b.inputs['Emission Color'])
    nt.links.new(fuerza.outputs['Value'], b.inputs['Emission Strength'])


def oclusion(m, b, oc):
    """estilo > render > oclusion {distancia, fuerza}: oscurece ranuras y uniones (nodo Ambient Occlusion sobre el
    color base: color * mezcla(1, ao, fuerza)). Sin esto, la textura suave de TRELLIS se ve como plastilina."""
    if not b.inputs['Base Color'].is_linked:
        return
    nt = m.node_tree
    src = b.inputs['Base Color'].links[0].from_socket
    ao = nt.nodes.new('ShaderNodeAmbientOcclusion')
    ao.inputs['Distance'].default_value = oc.get('distancia', 0.08)
    ao.samples = 16
    nt.links.new(src, ao.inputs['Color'])
    suave = nt.nodes.new('ShaderNodeMix'); suave.data_type = 'RGBA'; suave.blend_type = 'MIX'
    sa, sb = [s for s in suave.inputs if s.type == 'RGBA'][:2]
    suave.inputs['Factor'].default_value = oc.get('fuerza', 0.7)
    sa.default_value = (1, 1, 1, 1)
    nt.links.new(ao.outputs['AO'], sb)
    mult = nt.nodes.new('ShaderNodeMix'); mult.data_type = 'RGBA'; mult.blend_type = 'MULTIPLY'
    ma, mb = [s for s in mult.inputs if s.type == 'RGBA'][:2]
    mult.inputs['Factor'].default_value = 1.0
    nt.links.new(src, ma)
    nt.links.new([s for s in suave.outputs if s.type == 'RGBA'][0], mb)
    nt.links.new([s for s in mult.outputs if s.type == 'RGBA'][0], b.inputs['Base Color'])


def articulaciones(mesh):
    j = PJ['modelo'].get('articulaciones')
    return rig_lib.desde_json(j) if j else rig_lib.estimar_articulaciones(mesh, ALTURA)


def apuntar(cam, loc, rot):
    cam.location = Vector(loc); cam.rotation_euler = Euler(rot)


def render(path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def origen_px(size):
    """píxel (x, y desde arriba) donde cae el origen del mundo (los pies) en el render"""
    v = world_to_camera_view(sc, cam, Vector((0, 0, 0)))
    return [round(v.x * size, 2), round((1 - v.y) * size, 2)]


# direcciones en pantalla (sentido horario desde la derecha) -> giro del personaje (0 = mira a la cámara)
DIRECCIONES_ISO = [('e', 90), ('se', 45), ('s', 0), ('sw', -45), ('w', -90), ('nw', -135), ('n', 180), ('ne', 135)]

if modo == 'guia':
    sc, cam = preparar_escena()
    col, mesh = importar()
    J = articulaciones(mesh)
    out = os.path.join(TRABAJO, 'guia'); os.makedirs(out, exist_ok=True)
    sc.render.film_transparent = False
    sc.render.resolution_x = sc.render.resolution_y = 1000
    cam.data.ortho_scale = ALTURA * 1.1
    for vista, loc, rot in (('frente', (0, -10, ALTURA / 2), (math.pi / 2, 0, 0)),
                            ('costado', (10, 0, ALTURA / 2), (math.pi / 2, 0, math.pi / 2))):
        apuntar(cam, loc, rot)
        sc.render.filepath = os.path.join(out, f'{vista}.png')
        bpy.ops.render.render(write_still=True)
    with open(os.path.join(out, 'guia.json'), 'w') as f:
        json.dump({'ortho': cam.data.ortho_scale, 'centro_z': ALTURA / 2, 'px': 1000,
                   'articulaciones': rig_lib.a_json(J),
                   'origen': 'personaje.json' if PJ['modelo'].get('articulaciones') else 'estimadas'}, f, indent=1)
    print('GUIA OK')

elif modo == 'limpia':
    # la malla soldada y sin interior (sin ojos ni cabeza aparte, que se agregan después) para re-texturizarla
    preparar_escena()
    col, mesh = importar()
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); bpy.context.view_layer.objects.active = mesh
    bpy.ops.export_scene.gltf(filepath=os.path.join(TRABAJO, 'malla', 'limpia.glb'), export_format='GLB',
                              use_selection=True, export_materials='NONE')
    print(f'[blender] malla limpia: {len(mesh.data.polygons)} caras')
    print('LIMPIA OK')

elif modo == 'alinear':
    # paso malla, objeto de Pixal3D de una vista: modelo.glb (en el marco de la cámara) -> apoyado, derecho y de frente,
    # con su textura; así el juego puede usar modelo.glb tal cual
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.import_scene.gltf(filepath=GLB)
    mesh = next(o for o in bpy.data.objects if o.type == 'MESH')
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    alinear_objeto(mesh)
    vs = [v.co for v in mesh.data.vertices]
    base = Vector(((min(v.x for v in vs) + max(v.x for v in vs)) / 2, (min(v.y for v in vs) + max(v.y for v in vs)) / 2,
                   min(v.z for v in vs)))
    for v in mesh.data.vertices:   # origen = centro de la base
        v.co -= base
    bpy.ops.export_scene.gltf(filepath=GLB, export_format='GLB', use_selection=True)
    print('ALINEAR OK')

elif modo == 'comparar':
    # un candidato de malla (personaje u objeto) tal como lo importa `blender`, con la cámara iso y las luces del
    # estilo, sin rig: frente, tres cuartos, costado y espalda -> trabajo/comparar/<dir>.png (pipeline arma la hoja)
    sc, cam = preparar_escena()
    col, mesh = importar()
    xs = [v.co.x for v in mesh.data.vertices]; ys = [v.co.y for v in mesh.data.vertices]
    ancho = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    elev = math.radians(30)
    cam.data.ortho_scale = max(ALTURA, ancho * 0.8) * 1.3
    sc.render.resolution_x = sc.render.resolution_y = 720
    zc = ALTURA * 0.47
    apuntar(cam, (0, -10 * math.cos(elev), zc + 10 * math.sin(elev)), (math.pi / 2 - elev, 0, 0))
    mesh.rotation_mode = 'XYZ'
    out = os.path.join(TRABAJO, 'comparar'); os.makedirs(out, exist_ok=True)
    for dn, ang in DIRECCIONES_ISO:
        if dn in PJ.get('_vistas_comparar', ('s', 'se', 'e', 'n')):
            mesh.rotation_euler.z = math.radians(ang)
            render(os.path.join(out, f'{dn}.png'))
    print('COMPARAR OK')

elif modo == 'objeto':
    # objeto estático (caja, mesa, tronco...): sin rig. Una vista lateral a nivel (juego de costado) y N vistas
    # isométricas girando el objeto de a 360/N grados, con sombra de contacto opcional (Cycles, shadow catcher).
    sc, cam = preparar_escena()
    col, mesh = importar()
    giro = math.radians(PJ['modelo'].get('giro_grados', 0))
    if giro:
        for v in mesh.data.vertices:
            v.co = Euler((0, 0, giro)).to_matrix() @ v.co
    xs = [v.co.x for v in mesh.data.vertices]; ys = [v.co.y for v in mesh.data.vertices]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    for v in mesh.data.vertices:
        v.co.x -= cx; v.co.y -= cy
    dx, dy = max(xs) - min(xs), max(ys) - min(ys)
    out = os.path.join(TRABAJO, 'render'); os.makedirs(out, exist_ok=True)
    info = {'dimensiones': [round(dx, 4), round(dy, 4), ALTURA]}

    lat = PJ.get('lateral', {})
    ppu = lat.get('px_por_unidad', 182 / 1.85) * lat.get('superresolucion', 3)
    orto = max(dx, ALTURA) * 1.15
    size = int(math.ceil(orto * ppu / 2) * 2)
    sc.render.resolution_x = sc.render.resolution_y = size
    cam.data.ortho_scale = orto
    apuntar(cam, (0, -10, ALTURA / 2), (math.pi / 2, 0, 0))
    render(os.path.join(out, 'lateral.png'))
    info['lateral'] = {'size': size, 'ppu': ppu, 'origen_px': origen_px(size)}

    iso = PJ.get('isometrico', {})
    elev = math.radians(iso.get('elevacion_grados', 30))
    ppu = iso.get('baldosa_px', 128) / math.sqrt(2) * iso.get('superresolucion', 2)
    diag = math.hypot(dx, dy)
    orto = max(diag, ALTURA * math.cos(elev) + diag * math.sin(elev)) * 1.12
    size = int(math.ceil(orto * ppu / 2) * 2)
    sc.render.resolution_x = sc.render.resolution_y = size
    cam.data.ortho_scale = orto
    zc = ALTURA / 2
    apuntar(cam, (0, -10 * math.cos(elev), zc + 10 * math.sin(elev)), (math.pi / 2 - elev, 0, 0))
    mesh.rotation_mode = 'XYZ'  # el importador glTF deja cuaterniones
    if iso.get('sombra', True):
        key = bpy.data.objects['Key']   # sol más alto y blando: sombra de contacto, no una mancha larga
        key.rotation_euler.x = math.radians(90 - 58); key.data.angle = math.radians(25)
        bpy.data.objects['Fill'].data.use_shadow = False
        sc.render.engine = 'CYCLES'
        sc.cycles.samples = 96
        sc.cycles.use_denoising = True
        bpy.ops.mesh.primitive_plane_add(size=diag * 6 + 2)
        bpy.context.active_object.is_shadow_catcher = True
    n = iso.get('direcciones', 4)
    for k in range(n):  # +45°: las caras del objeto quedan paralelas a los bordes de las baldosas 2:1
        mesh.rotation_euler.z = math.pi / 4 + 2 * math.pi * k / n
        render(os.path.join(out, f'iso_{k}.png'))
    info['iso'] = {'size': size, 'ppu': ppu, 'origen_px': origen_px(size), 'direcciones': n,
                   'elevacion_grados': math.degrees(elev)}
    mesh.rotation_euler.z = 0
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(TRABAJO, f'{nombre}.blend'))
    with open(os.path.join(out, 'render.json'), 'w') as f:
        json.dump(info, f)
    print('OBJETO OK', info['dimensiones'])

elif modo == 'vehiculo':
    # auto para el juego 3D: el .glb es lo que se usa (sin sprites). Ver vehiculo.py
    sc, cam = preparar_escena()
    col, mesh = importar()
    V = PJ['vehiculo']
    if PJ['malla'].get('motor') == 'pixal3d' and not PJ['malla'].get('vistas'):   # alineado a la imagen: enderezar
        vehiculo.alinear(mesh, trompa_lejos=PJ['malla'].get('vista') == 'atras')
    vehiculo.escalar_largo(mesh, V.get('largo_m', 2.3))
    if V.get('simetria'):
        vehiculo.simetria(mesh, V['simetria'])
    partes = [mesh]
    modo_ruedas = V.get('ruedas', 'originales')   # 'originales' (separadas de la malla) | 'armadas' | False
    if modo_ruedas is True:
        modo_ruedas = 'armadas'
    if modo_ruedas:
        ruedas = vehiculo.detectar_ruedas(mesh, V)
        for k, (c, r, w) in ruedas.items():
            print(f'[blender] rueda {k}: centro ({c.x:.3f}, {c.y:.3f}, {c.z:.3f}) radio {r:.3f} ancho {w:.3f}')
    hueco = vehiculo.material_color('pasarrueda', (0.01, 0.01, 0.01), 0.9)
    huecos = []
    if modo_ruedas == 'originales':
        mat_rueda = mesh.data.materials[0].copy(); mat_rueda.name = 'llanta_original'
        for k, (c, r, w) in ruedas.items():
            rueda = vehiculo.separar_rueda(mesh, col, f'rueda_{k}', c, r, w, mat_rueda)
            vehiculo.fondo_rueda(rueda, r, w, hueco)
            partes.append(rueda)
            huecos.append(vehiculo.pasarrueda(f'pasarrueda_{k}', col, c, r, w, hueco, pared=1.2))
    elif modo_ruedas == 'armadas':
        dir_llantas = os.path.join(TRABAJO, 'vehiculo'); os.makedirs(dir_llantas, exist_ok=True)
        # la imagen de cada llanta sale de la rueda original; con simetría, las del costado que se conserva
        lado = {'izquierda': 'i', 'derecha': 'd'}.get(V.get('simetria'))
        mats = {}
        for k, (c, r, w) in ruedas.items():
            fuente = k[0] + lado if lado else k
            if fuente not in mats:
                cf, rf, _ = ruedas[fuente]
                ruta = vehiculo.capturar_llanta(mesh, cf, rf, os.path.join(dir_llantas, f'llanta_{fuente}.png'))
                mats[fuente] = vehiculo.material_imagen(f'llanta_{fuente}', ruta, 0.4)
        print(f'[blender] caras de las ruedas originales: {vehiculo.sacar_ruedas(mesh, ruedas)}')
    if V.get('alisar'):
        vehiculo.alisar(mesh, V['alisar'])
    if V.get('materiales', True):
        print(f'[blender] caras oscuras (vidrio, tomas, bajos): {vehiculo.separar_materiales(mesh)}')
    if modo_ruedas == 'armadas':
        cubierta = vehiculo.material_color('cubierta', V.get('color_cubierta', (0.025, 0.025, 0.025)), 0.75)
        for k, (c, r, w) in ruedas.items():
            partes.append(vehiculo.armar_rueda(f'rueda_{k}', col, c, r, w, mats[k[0] + lado if lado else k], cubierta))
            huecos.append(vehiculo.pasarrueda(f'pasarrueda_{k}', col, c, r, w, hueco))
    if huecos:   # después de separar_materiales (sus caras no tienen UV)
        bpy.ops.object.select_all(action='DESELECT')
        for o in huecos:
            o.select_set(True)
        mesh.select_set(True); bpy.context.view_layer.objects.active = mesh
        bpy.ops.object.join()
    mesh.name = 'carroceria'
    vehiculo.exportar(os.path.join(TRABAJO, 'vehiculo.glb'), partes)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(TRABAJO, f'{nombre}.blend'))
    vehiculo.material_juego(partes)
    vehiculo.revision(TRABAJO, V.get('largo_m', 2.3))
    vehiculo.tarjeta(TRABAJO)
    print(f'[blender] carrocería: {len(mesh.data.polygons)} caras')
    print('VEHICULO OK')

else:
    sc, cam = preparar_escena()
    col, mesh = importar()
    J = articulaciones(mesh)
    arm = rig_lib.construir_rig(col, f'{nombre}_rig', J)
    arm['escala_plantilla'] = ALTURA / rig_lib.ALTURA_PLANTILLA
    # piernas cortas (chibis): las bajadas de cadera de las poses se achican con el largo de pierna (cadera-tobillo
    # respecto de la plantilla, desde 0,9: en los de proporciones normales no cambia nada). Sin esto el agachado bajaba
    # la cadera de un chibi (pierna 0,37) más de lo que medían sus piernas y el torso se aplastaba contra ellas
    B = arm.data.bones
    pierna = (B['thigh.L'].head_local.z - B['shin.L'].tail_local.z) / (0.68 * arm['escala_plantilla'])
    arm['factor_pierna'] = min(1.0, pierna / 0.9)
    # radio en unidades de un personaje de 1.85 (3 cm); 0 = sin suavizar (como antes de TRELLIS.2)
    radio = PJ['modelo'].get('suavizar_pesos', 0.03) * ALTURA / rig_lib.ALTURA_PLANTILLA
    # lado del vóxel de la copia estanca, también en escala de 1.85; 0 = bone heat sobre la malla misma
    voxel = PJ['modelo'].get('pesos_estanca', 0.0) * ALTURA / rig_lib.ALTURA_PLANTILLA
    if PJ['modelo'].get('pesos', 'heat') == 'distancia':   # donde el bone heat falla (chibis con capas internas)
        rig_lib.pesos_por_distancia(mesh, arm, PJ['modelo'].get('pesos_exponente', 6.0))
        if radio > 0:
            rig_lib.suavizar_pesos_espacial(mesh, radio)
        sin_peso = 0
    else:
        sin_peso = rig_lib.pesos_automaticos(mesh, arm, radio, voxel, mesh.pop('estanca', None),
                                             PJ['modelo'].get('piezas_por_distancia', False))
    if PJ['modelo'].get('afinar_pesos'):
        rig_lib.afinar_pesos_miembros(mesh, PJ['modelo']['afinar_pesos'])
    if PJ['modelo'].get('pesos_rigidos'):
        rig_lib.pesos_rigidos(mesh)
    # cuaterniones duales (preserve volume): con la mezcla lineal el codo doblado 110-135° (golpe, caminata) se
    # aplastaba por dentro y doblaba como plastilina; así conserva el grosor y marca el codo
    for m in mesh.modifiers:
        if m.type == 'ARMATURE':
            m.use_deform_preserve_volume = PJ['modelo'].get('preservar_volumen', True)
    pesos_cabeza(mesh, arm, J)
    if PJ['modelo'].get('pesos_zonas'):
        rig_lib.pesos_zonas(mesh, PJ['modelo']['pesos_zonas'])
    if PJ['modelo'].get('cortar_puentes', True):
        n = rig_lib.cortar_puentes(mesh, arm)
        if n:
            print(f'[blender] caras que unían partes lejanas del cuerpo: {n} (cortadas)')
    if PJ['modelo'].get('girar_manos_grados'):
        rig_lib.girar_antebrazos(mesh, arm, PJ['modelo']['girar_manos_grados'])
    print(f'[blender] vértices: {len(mesh.data.vertices)}, sin peso: {sin_peso}')
    if sin_peso > len(mesh.data.vertices) * 0.01:
        sys.exit('[blender] el bone heat falló (malla no soldada o articulaciones fuera del cuerpo): revisar con `guia`')
    a = PJ['animacion']


HUESOS_ANCLA = ['hips', 'chest', 'neck', 'head', 'hand.R', 'hand.L', 'foot.R', 'foot.L']


def exportar_animado(arm, acciones):
    """trabajo/animado.glb: la malla con el rig y una animación por Action, para el visor 3D de crisol ui. El glTF se
    muestrea cuadro a cuadro (el IK de las piernas queda horneado) y cada animación empieza en 0 desde su primer
    cuadro; en las de loop (con CYCLES) llega hasta la pose que cierra el ciclo. animado.json: por animación, la
    Action y el tiempo de cada cuadro de los sprites (en segundos del glTF), para que el visor vaya a su ritmo."""
    arm.rotation_euler.z = 0   # de frente (-Y), como modelo.glb
    fps = sc.render.fps
    out = {}
    for nombre_anim, (accion, frames) in acciones.items():
        act = bpy.data.actions[accion]
        ciclo = any(m.type == 'CYCLES' for fc in anim._fcurves(act) for m in fc.modifiers)
        paso = frames[-1] - frames[-2] if len(frames) > 1 else 0
        fin = frames[-1] + paso if ciclo else frames[-1]
        act.use_frame_range = True
        act.frame_start, act.frame_end = frames[0], max(fin, frames[0] + 1)
        out[nombre_anim] = {'clip': accion, 'tiempos': [round((f - frames[0]) / fps, 4) for f in frames],
                            'fin': round((fin - frames[0]) / fps, 4), 'ciclo': ciclo}
    bpy.ops.object.select_all(action='DESELECT')
    for o in [arm] + list(arm.children_recursive):
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(TRABAJO, 'animado.glb'), export_format='GLB', use_selection=True,
                              export_animation_mode='ACTIONS', export_force_sampling=True,
                              export_anim_slide_to_zero=True, export_optimize_animation_size=True)
    with open(os.path.join(TRABAJO, 'animado.json'), 'w') as f:
        json.dump(out, f, indent=1)


def anclas_cuadro(arm, size, f):
    """Cabeza de cada hueso (posición y giro en el mundo) en el cuadro f, más su píxel en el render iso."""
    bpy.context.scene.frame_set(f)
    out = {}
    for b in HUESOS_ANCLA:
        m = arm.matrix_world @ arm.pose.bones[b].matrix
        p = m.to_translation(); q = m.to_quaternion()
        v = world_to_camera_view(bpy.context.scene, bpy.context.scene.camera, p)
        out[b] = [round(x, 4) for x in (p.x, p.y, p.z, q.w, q.x, q.y, q.z)] + \
                 [round(v.x * size, 1), round((1 - v.y) * size, 1)]
    return out


def retratos():
    """Selector de personajes y diálogos: retrato (cabeza y hombros) y cuerpo entero, de frente, en reposo.
    La inclinación de cabeza es propia (cabeza_arriba_grados compensa la vista lateral, no la frontal).
    Además de los renders deja retrato.json con la caja del retrato en unidades del modelo (x, z), para
    recortar el mismo encuadre de la imagen que generó la malla (armar_tira.retratos)."""
    rt = PJ.get('retrato', {})
    sp = PJ['sprites']
    size = int(math.ceil(ORTHO * sp['alto_en_pantalla_px'] * sp['superresolucion'] / ALTURA / 2) * 2)
    sc.render.resolution_x = sc.render.resolution_y = size   # frente: mismo encuadre que los laterales
    cam.data.ortho_scale = ORTHO
    apuntar(cam, (0, -10, CAM_Z), (math.pi / 2, 0, 0))
    arm.rotation_euler.z = 0
    anim.idle(arm, a, pitch=rt.get('cabeza_grados', -5)); sc.frame_set(1)
    d = os.path.join(TRABAJO, 'retrato'); os.makedirs(d, exist_ok=True)
    render(os.path.join(d, 'frente.png'))
    ev = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    vs = [ev.matrix_world @ v.co for v in ev.to_mesh().vertices]
    cuello = J['head'][0][2]
    arriba = max(v.z for v in vs)
    abajo = cuello - (arriba - cuello) * rt.get('hombros', 0.55)
    ancho = 2 * max(abs(v.x) for v in vs if v.z > cuello)     # ancho de la cabeza (pelo, sombrero)
    ev.to_mesh_clear()
    ancho_px = rt.get('ancho_px', 512)
    sc.render.resolution_x, sc.render.resolution_y = ancho_px, int(ancho_px * 1.25)
    orto = cam.data.ortho_scale = max(arriba - abajo, ancho * 1.25) * 1.06
    zc = arriba + 0.03 * orto - orto / 2
    apuntar(cam, (0, -10, zc), (math.pi / 2, 0, 0))
    render(os.path.join(d, 'retrato.png'))
    with open(os.path.join(d, 'retrato.json'), 'w') as f:   # ortho_scale = lado mayor (el alto)
        json.dump({'altura': ALTURA, 'x': [-orto / 2.5, orto / 2.5], 'z': [zc - orto / 2, zc + orto / 2],
                   'ancho_px': ancho_px, 'alto_px': int(ancho_px * 1.25)}, f)


# poses del control de revés (paso revisar): las que más estiran la malla
POSES_REVES = [('idle', 0), ('caminar', 2), ('correr', 3), ('golpe', 2), ('patada', 3), ('agacharse', 0), ('rodar', 3)]


def control_reves():
    """Revés a la vista (paso revisar): las poses de POSES_REVES de costado y de frente en Workbench, con y sin
    descartar las caras de atrás; donde difieren, lo que se veía era una cara de atrás -> magenta sobre el render ->
    trabajo/reves/<anim>_<costado|frente>.png. Magenta = se ve el interior de la malla: agujeros, capas escondidas
    que atraviesan la de afuera al moverse, normales al revés (en los sprites, manchas oscuras)."""
    import numpy as np
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'; sh.color_type = 'TEXTURE'
    sc.render.resolution_x = sc.render.resolution_y = 640
    cam.data.ortho_scale = ORTHO
    apuntar(cam, (0, -10, CAM_Z), (math.pi / 2, 0, 0))
    d = os.path.join(TRABAJO, 'reves'); os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, '_tmp.png')

    def pixeles(culling):
        sh.show_backface_culling = culling
        render(tmp)
        im = bpy.data.images.load(tmp)
        px = np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4)
        bpy.data.images.remove(im)
        return px
    funciones = dict(kimodo_clip.todas(a))
    for nombre_anim, i in POSES_REVES:
        if nombre_anim not in funciones:
            continue
        frames = funciones[nombre_anim](arm, a)
        sc.frame_set(frames[min(i, len(frames) - 1)])
        for vista, giro in (('costado', 90), ('frente', 0)):
            arm.rotation_euler.z = math.radians(giro)
            con, sin = pixeles(False), pixeles(True)
            dif = (np.abs(con - sin).max(axis=2) > 0.04) & (con[..., 3] > 0.5)
            con[dif] = (1, 0, 1, 1)
            im = bpy.data.images.new('reves', con.shape[1], con.shape[0], alpha=True)
            im.pixels[:] = con.ravel()
            im.filepath_raw = os.path.join(d, f'{nombre_anim}_{vista}.png'); im.file_format = 'PNG'
            im.save()
            bpy.data.images.remove(im)
    os.remove(tmp)
    arm.rotation_euler.z = math.radians(90)


if modo == 'construir':
    sp = PJ['sprites']
    ppu = sp['alto_en_pantalla_px'] * sp['superresolucion'] / ALTURA   # píxeles por unidad
    size = int(math.ceil(ORTHO * ppu / 2) * 2)
    sc.render.resolution_x = sc.render.resolution_y = size
    cam.data.ortho_scale = ORTHO
    apuntar(cam, (0, -10, CAM_Z), (math.pi / 2, 0, 0))   # cámara a nivel: mira al frente
    arm.rotation_euler.z = math.radians(90)              # el personaje mira a la derecha (+X)
    info = {}
    acciones = {}
    for nombre_anim, fn in kimodo_clip.todas(a):
        frames = fn(arm, a)
        acciones[nombre_anim] = (arm.animation_data.action.name, frames)
        d = os.path.join(TRABAJO, 'frames', nombre_anim); os.makedirs(d, exist_ok=True)
        for i, f in enumerate(frames):
            sc.frame_set(f)
            render(os.path.join(d, f'{i:02d}.png'))
        info[nombre_anim] = len(frames)

    retratos()

    arm.animation_data.action = bpy.data.actions['Walk']
    sc.frame_start, sc.frame_end = 1, 16
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(TRABAJO, f'{nombre}.blend'))
    exportar_animado(arm, acciones)
    with open(os.path.join(TRABAJO, 'frames', 'frames.json'), 'w') as f:
        json.dump({'size': size, 'ppu': ppu, 'frames': info}, f)
    print('CONSTRUIR OK', info)

elif modo == 'reves':
    control_reves()
    print('REVES OK')

elif modo == 'retrato':
    retratos()
    print('RETRATO OK')

elif modo in ('iso', 'anclas'):
    # vista isométrica 2:1 (cámara ortográfica a 30° de elevación); el personaje gira de a 45°
    iso = PJ.get('isometrico', {})
    elev = math.radians(iso.get('elevacion_grados', 30))
    ppu = iso.get('baldosa_px', 128) / math.sqrt(2) * iso.get('superresolucion', 2)
    orto = ALTURA * 1.45
    size = int(math.ceil(orto * ppu / 2) * 2)
    sc.render.resolution_x = sc.render.resolution_y = size
    cam.data.ortho_scale = orto
    zc = ALTURA * 0.42
    apuntar(cam, (0, -10 * math.cos(elev), zc + 10 * math.sin(elev)), (math.pi / 2 - elev, 0, 0))
    pedidas = iso.get('animaciones') or [n for n, _ in anim.TODAS]
    if 'cabeza_arriba_grados' in iso:  # desde arriba puede convenir otra inclinación que en la vista lateral
        a = dict(a, cabeza_arriba_grados=iso['cabeza_arriba_grados'])
    funciones = dict(kimodo_clip.todas(a))
    info = {}
    anclas = {}
    for nombre_anim in pedidas:
        frames = funciones[nombre_anim](arm, a)
        for dn, ang in DIRECCIONES_ISO:
            arm.rotation_euler.z = math.radians(ang)
            if modo == 'anclas':
                anclas.setdefault(nombre_anim, {})[dn] = [anclas_cuadro(arm, size, f) for f in frames]
                continue
            d = os.path.join(TRABAJO, 'iso', nombre_anim, dn); os.makedirs(d, exist_ok=True)
            for i, f in enumerate(frames):
                sc.frame_set(f)
                render(os.path.join(d, f'{i:02d}.png'))
        info[nombre_anim] = len(frames)
    if modo == 'anclas':
        os.makedirs(os.path.join(TRABAJO, 'iso'), exist_ok=True)
        largos = {b: round(arm.data.bones[b].length, 4) for b in HUESOS_ANCLA}
        # tamaño real de la cabeza (pelo, sombrero, casco) en reposo: para escalar lo que se pone ahí
        # (ancho y fondo de la mitad de arriba: abajo del todo pueden entrar hombreras)
        cuello = J['head'][0][2]
        todos = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
        arriba = max(v.z for v in todos)
        vs = [v for v in todos if v.z > cuello + (arriba - cuello) * 0.45]
        cabeza = {'ancho': round(2 * max(abs(v.x) for v in vs), 4), 'fondo': round(max(v.y for v in vs) - min(v.y for v in vs), 4),
                  'alto': round(arriba - cuello, 4)} if vs else {}
        with open(os.path.join(TRABAJO, 'iso', 'anclas.json'), 'w') as f:
            json.dump({'size': size, 'ppu': ppu, 'origen_px': origen_px(size), 'altura': ALTURA,
                       'elevacion_grados': math.degrees(elev), 'huesos': HUESOS_ANCLA, 'largos': largos, 'cabeza': cabeza,
                       'formato': 'por hueso: [x, y, z, qw, qx, qy, qz, px, py]; mundo de Blender (Z arriba, '
                                  'la cámara mira hacia +Y), origen = pies; px/py = píxel en el render iso',
                       'cuadros': anclas}, f, separators=(',', ':'))
        print('ANCLAS OK', info)
    else:
        with open(os.path.join(TRABAJO, 'iso', 'iso.json'), 'w') as f:
            json.dump({'size': size, 'ppu': ppu, 'origen_px': origen_px(size), 'frames': info,
                       'direcciones': [dn for dn, _ in DIRECCIONES_ISO]}, f)
        print('ISO OK', info)
