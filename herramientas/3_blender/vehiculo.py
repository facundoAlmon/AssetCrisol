# Vehículos (objeto.json con bloque `vehiculo`) para un juego 3D de carreras: lo usa blender_main en el
# modo `vehiculo`. La malla llega normalizada por importar() (frente = -Y, ruedas en z=0, centrada en XY):
#   largo     -> escala al largo del juego (vehiculo.largo_m)
#   simetria  -> se queda con un costado y lo espeja (malla y UV: la textura sale igual de los dos lados)
#   ruedas    -> detecta las 4 por el contacto con el piso, las saca de la carrocería y pone ruedas armadas
#                (cubierta + llanta con la imagen de la original), cada una con su origen en el eje
#   exportar  -> trabajo/vehiculo.glb: nodos `carroceria`, `rueda_di`, `rueda_dd`, `rueda_ti`, `rueda_td`
#                (d/t = delantera/trasera, i/d = izquierda/derecha del auto); trompa en +Z del glTF
#   revision  -> trabajo/revision_<vista>.png (cámara del juego, costado, arriba, tres cuartos)
# Lado izquierdo del auto = +X (mira a -Y).
import math, os

import bmesh
import bpy
from mathutils import Vector

RUEDAS = ('di', 'dd', 'ti', 'td')


def escalar_largo(mesh, largo):
    vs = mesh.data.vertices
    ys = [v.co.y for v in vs]
    s = largo / (max(ys) - min(ys))
    for v in vs:
        v.co *= s
    return s


def simetria(mesh, lado):
    """lado 'izquierda' (+X) o 'derecha' (-X): ese costado se espeja sobre el otro."""
    signo = 1 if lado == 'izquierda' else -1
    bm = bmesh.new(); bm.from_mesh(mesh.data)
    geo = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geo, plane_co=(0, 0, 0), plane_no=(signo, 0, 0),
                           clear_inner=True, clear_outer=False, dist=1e-6)
    bm.to_mesh(mesh.data); bm.free()
    mod = mesh.modifiers.new('simetria', 'MIRROR')
    mod.use_axis = (True, False, False); mod.use_clip = True; mod.use_mirror_merge = True
    mod.merge_threshold = 1e-4
    aplicar(mesh, mod)


def alisar(mesh, pasos, fuerza=0.5):
    """Saca los bollos de la carrocería (las chapas salen onduladas de Pixal3D): suavizado laplaciano que conserva
    el volumen, `pasos` iteraciones. Va después de sacar las ruedas (si no, las aplasta antes de medirlas)."""
    mod = mesh.modifiers.new('alisar', 'LAPLACIANSMOOTH')
    mod.iterations = pasos; mod.lambda_factor = fuerza; mod.lambda_border = 0.0
    mod.use_volume_preserve = True; mod.use_normalized = True
    aplicar(mesh, mod)


def aplicar(obj, mod):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)


def _altura_abajo(bvh, x, y):
    """z de la superficie vista desde abajo en (x, y) (el primer choque de un rayo hacia arriba), o None."""
    hit = bvh.ray_cast(Vector((x, y, -1.0)), Vector((0, 0, 1)))
    return hit[0].z if hit[0] is not None else None


def detectar_ruedas(mesh, cfg):
    """Ruedas por el perfil de abajo (rayos hacia arriba, no vértices: la malla puede ser rala): en cada esquina la
    parte más baja es la base de la cubierta (centro en y) y su ancho en x; el radio es el mayor arco
    z = r - sqrt(r² - d²) que no deja la superficie de la cubierta por encima. Devuelve {clave: (centro, radio,
    ancho)}; con simetría las del costado que se conserva se copian espejadas."""
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromObject(mesh, bpy.context.evaluated_depsgraph_get())
    vs = mesh.data.vertices
    ys = [v.co.y for v in vs]; xs = [v.co.x for v in vs]
    largo, ancho = max(ys) - min(ys), max(xs) - min(xs)
    paso = largo * 0.004
    ruedas = {}
    for eje, (y0, y1) in (('d', (min(ys), min(ys) + largo * 0.5)), ('t', (min(ys) + largo * 0.5, max(ys)))):
        for lado, signo in (('i', 1), ('d', -1)):
            banda = [signo * ancho * (0.2 + 0.3 * k / 11) for k in range(12)]   # del 20 % al 50 % del ancho
            perfil = {}
            y = y0
            while y <= y1:
                zs = [z for z in (_altura_abajo(bvh, x, y) for x in banda) if z is not None]
                if zs:
                    perfil[y] = min(zs)
                y += paso
            zmin = min(perfil.values())
            bajos = [y for y, z in perfil.items() if z < zmin + largo * 0.004]
            yc = (min(bajos) + max(bajos)) / 2
            # ancho de la cubierta: dónde la superficie toca abajo cruzando en x por el centro
            xs_pie = [x for x in (signo * ancho * k / 200 for k in range(20, 101))
                      if (_altura_abajo(bvh, x, yc) or 1e9) < zmin + largo * 0.01]
            x_int, x_ext = min(abs(x) for x in xs_pie), max(abs(x) for x in xs_pie)
            w = cfg.get('ancho_rueda_m') or max(x_ext - x_int, largo * 0.04)
            # perfil sobre la cubierta sola (su franja en x) para el radio
            tira = [signo * (x_int + (x_ext - x_int) * k / 4) for k in range(5)]
            sobre = {}
            for k in range(-int(largo * 0.2 / paso), int(largo * 0.2 / paso) + 1):
                zs = [z for z in (_altura_abajo(bvh, x, yc + k * paso) for x in tira) if z is not None]
                if zs:
                    sobre[k * paso] = min(zs) - zmin
            r = cfg.get('radio_m') or radio_por_perfil(sobre, largo)
            ruedas[eje + lado] = (Vector((signo * (x_int + x_ext) / 2, yc, zmin + r)), r, w)
    if cfg.get('simetria'):   # la del lado que se conserva manda (los dos lados ya son iguales)
        ref = 'i' if cfg['simetria'] == 'izquierda' else 'd'
        for eje in 'dt':
            c, r, w = ruedas[eje + ref]
            ruedas[eje + ('d' if ref == 'i' else 'i')] = (Vector((-c.x, c.y, c.z)), r, w)
    return ruedas


def radio_por_perfil(perfil, largo):
    """perfil {d: z} de abajo de la cubierta: z está sobre el arco z = r - sqrt(r² - d²) o por debajo (carrocería que
    baja más, zócalo), nunca por encima. Con un radio más grande que el real el arco se aplana y la cubierta le queda
    arriba: gana el mayor radio sin puntos arriba del arco (con tolerancia y un par de puntos de ruido)."""
    tol = largo * 0.006
    mejor = r = largo * 0.05
    while r <= largo * 0.2:
        arriba = sum(1 for d, z in perfil.items() if abs(d) < r * 0.9 and z > r - math.sqrt(r * r - d * d) + tol)
        if arriba <= 2:
            mejor = r
        r += largo * 0.0025
    return mejor


def sacar_ruedas(mesh, ruedas, margen=1.1, margen_pintura=1.02):
    """Borra las caras de la carrocería que caen dentro del cilindro de cada rueda: lo oscuro (la cubierta vieja)
    hasta `margen` (con 1.04 quedaban dientes alrededor), lo pintado solo hasta `margen_pintura` (los guardabarros
    pegados a la rueda de un auto de prueba se agujereaban)."""
    bm = bmesh.new(); bm.from_mesh(mesh.data)
    bm.faces.ensure_lookup_table()
    oscuro = oscuras(mesh, bm) or {}
    borrar = []
    for f in bm.faces:
        c = f.calc_center_median()
        m = margen if oscuro.get(f.index, True) else margen_pintura
        for centro, r, w in ruedas.values():
            if abs(c.x - centro.x) <= w / 2 * m + 0.01 and math.hypot(c.y - centro.y, c.z - centro.z) <= r * m:
                borrar.append(f); break
    bmesh.ops.delete(bm, geom=borrar, context='FACES')
    # el corte por caras deja el arco serruchado: los vértices del borde nuevo (cerca del cilindro) van al círculo
    for v in bm.verts:
        if not v.is_boundary:
            continue
        for centro, r, w in ruedas.values():
            d = math.hypot(v.co.y - centro.y, v.co.z - centro.z)
            if abs(v.co.x - centro.x) <= w / 2 * margen + 0.02 and r * 0.95 < d < r * margen * 1.15 \
                    and v.co.z > centro.z - r * 0.5:
                k = max(d, r * 1.06) / d
                v.co.y = centro.y + (v.co.y - centro.y) * k
                v.co.z = centro.z + (v.co.z - centro.z) * k
                break
    bm.to_mesh(mesh.data); bm.free()
    return len(borrar)


def capturar_llanta(mesh, centro, r, ruta, px=512):
    """Imagen de la rueda original vista de costado (desde afuera, color de la textura sin luces): la cara de la
    rueda armada la usa tal cual. Workbench plano: lo que se ve es el color horneado."""
    sc = bpy.context.scene
    previo = (sc.render.engine, sc.render.resolution_x, sc.render.resolution_y, sc.camera, sc.render.film_transparent)
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light, sh.color_type = 'FLAT', 'TEXTURE'
    sc.render.resolution_x = sc.render.resolution_y = px
    sc.render.film_transparent = True
    cd = bpy.data.cameras.new('cam_llanta'); cd.type = 'ORTHO'; cd.ortho_scale = 2 * r
    cam = bpy.data.objects.new('cam_llanta', cd); sc.collection.objects.link(cam)
    signo = 1 if centro.x > 0 else -1
    cam.location = (centro.x + signo * 5, centro.y, centro.z)
    cam.rotation_euler = (math.pi / 2, 0, signo * math.pi / 2)
    sc.camera = cam
    sc.render.filepath = ruta
    bpy.ops.render.render(write_still=True)
    contraste(ruta)
    bpy.data.objects.remove(cam, do_unlink=True)
    sc.render.engine, sc.render.resolution_x, sc.render.resolution_y, sc.camera, sc.render.film_transparent = previo
    return ruta


def contraste(ruta, rango=0.35):
    """Las llantas negras de Pixal3D salen gris oscuro sobre negro y los rayos casi no se ven: si el brillo cubre
    menos de `rango`, se estira (hasta 3x) desde el oscuro."""
    import numpy as np
    img = bpy.data.images.load(ruta)
    px = np.array(img.pixels[:], dtype=np.float32).reshape(-1, 4)
    vis = px[:, 3] > 0.5
    if vis.sum() < 100:
        return
    lum = px[vis, :3].mean(axis=1)
    lo, hi = np.percentile(lum, 3), np.percentile(lum, 97)
    k = min(3.0, rango / max(hi - lo, 1e-3))
    if k > 1.0:
        px[:, :3] = np.clip(lo + (px[:, :3] - lo) * k, 0, 1)
        img.pixels[:] = px.ravel()
        img.save()
    bpy.data.images.remove(img)


def material_imagen(nombre, ruta, rugosidad):
    m = bpy.data.materials.new(nombre); m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(ruta)
    nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rugosidad
    return m


def material_color(nombre, color, rugosidad):
    m = bpy.data.materials.new(nombre); m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rugosidad
    return m


def armar_rueda(nombre, col, centro, r, w, mat_llanta, mat_cubierta, lados=48):
    """Cilindro sobre el eje X con el origen en el centro: las dos tapas llevan la imagen de la llanta (UV planar en
    Y-Z: del lado de afuera se ve como en la captura), la banda va de goma. Bordes redondeados."""
    me = bpy.data.meshes.new(nombre)
    bm = bmesh.new()
    afuera = 1 if centro.x > 0 else -1
    anillos = []
    for x in (-w / 2, w / 2):
        anillos.append([bm.verts.new((x, r * math.cos(2 * math.pi * k / lados), r * math.sin(2 * math.pi * k / lados)))
                        for k in range(lados)])
    tapa_in = bm.faces.new(anillos[0][::-1]); tapa_out = bm.faces.new(anillos[1])
    banda = [bm.faces.new((anillos[0][k], anillos[0][(k + 1) % lados], anillos[1][(k + 1) % lados], anillos[1][k]))
             for k in range(lados)]
    if afuera < 0:   # del lado derecho la tapa de afuera es la de -X
        tapa_in, tapa_out = tapa_out, tapa_in
    uv = bm.loops.layers.uv.new('UVMap')
    for f in (tapa_in, tapa_out):
        for l in f.loops:   # la cámara de la captura mira desde afuera: del lado izquierdo la u crece hacia +Y
            l[uv].uv = (0.5 + afuera * l.vert.co.y / (2 * r), 0.5 + l.vert.co.z / (2 * r))
    for k, f in enumerate(banda):
        for l in f.loops:
            l[uv].uv = (k / lados, 0.5)
    for f in banda:
        f.material_index = 1
        f.smooth = True
    bm.to_mesh(me); bm.free()
    me.materials.append(mat_llanta); me.materials.append(mat_cubierta)
    ob = bpy.data.objects.new(nombre, me)
    col.objects.link(ob)
    ob.location = centro
    bev = ob.modifiers.new('borde', 'BEVEL'); bev.width = min(r, w) * 0.12; bev.segments = 3
    bev.limit_method = 'ANGLE'
    aplicar(ob, bev)
    return ob


def separar_rueda(mesh, col, nombre, centro, r, w, mat):
    """La rueda original como objeto aparte (las caras dentro de su cilindro, `r` y el ancho con un poco de margen),
    con el origen en el eje: conserva cómo la hizo el modelo 3D y puede girar. Devuelve el objeto."""
    bm = bmesh.new(); bm.from_mesh(mesh.data)
    dentro = [f for f in bm.faces
              if abs(f.calc_center_median().x - centro.x) <= w / 2 * 1.15 + 0.01
              and math.hypot(f.calc_center_median().y - centro.y, f.calc_center_median().z - centro.z) <= r * 0.99]
    rueda = bmesh.new()
    uv_src = bm.loops.layers.uv.active
    uv = rueda.loops.layers.uv.new('UVMap')
    mapa = {}
    for f in dentro:
        vs = []
        for v in f.verts:
            if v not in mapa:
                mapa[v] = rueda.verts.new(v.co - centro)
            vs.append(mapa[v])
        try:
            nf = rueda.faces.new(vs)
        except ValueError:   # cara repetida
            continue
        nf.smooth = f.smooth
        for l, nl in zip(f.loops, nf.loops):
            nl[uv].uv = l[uv_src].uv
    bmesh.ops.delete(bm, geom=dentro, context='FACES')
    bm.to_mesh(mesh.data); bm.free()
    me = bpy.data.meshes.new(nombre)
    rueda.to_mesh(me); rueda.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(nombre, me)
    col.objects.link(ob)
    ob.location = centro
    return ob


def fondo_rueda(rueda, r, w, mat, lados=32):
    """Disco oscuro del lado de adentro de una rueda original (en su objeto: gira con ella). TRELLIS.2 deja la llanta
    sin fondo y entre los rayos se veía a través del auto (puntitos del color del fondo)."""
    me = rueda.data
    me.materials.append(mat)
    bm = bmesh.new(); bm.from_mesh(me)
    x = (-1 if rueda.location.x > 0 else 1) * w * 0.42   # detrás de rayos y maza, antes del flanco de adentro
    f = bm.faces.new([bm.verts.new((x, r * 0.97 * math.cos(2 * math.pi * k / lados),
                                    r * 0.97 * math.sin(2 * math.pi * k / lados))) for k in range(lados)])
    f.material_index = len(me.materials) - 1
    bm.to_mesh(me); bm.free()


def pasarrueda(nombre, col, centro, r, w, mat, R=1.04, pared=None):
    """Hueco oscuro detrás de la rueda: medio cilindro hacia arriba (un poco más grande que la rueda) y la pared del
    lado de adentro. Tapa lo que queda abierto de la carrocería al sacar la rueda original. `pared` (en radios) agranda
    la pared de adentro por arriba del eje: con las ruedas originales el guardabarros de TRELLIS.2 queda más alto que la
    cubierta y por la medialuna se veía a través del auto."""
    me = bpy.data.meshes.new(nombre)
    bm = bmesh.new()
    R, lados = r * R, 24   # con 1.1 asomaba sobre los guardabarros pegados a la rueda (un auto de prueba)
    adentro = -1 if centro.x > 0 else 1
    x_out, x_in = centro.x + adentro * w * 0.1, centro.x + adentro * w * 0.55
    arco = [(R * math.cos(math.pi * k / lados), R * math.sin(math.pi * k / lados)) for k in range(lados + 1)]
    a = [bm.verts.new((x_out, centro.y + y, centro.z + z)) for y, z in arco]
    b = [bm.verts.new((x_in, centro.y + y, centro.z + z)) for y, z in arco]
    for k in range(lados):
        bm.faces.new((a[k], a[k + 1], b[k + 1], b[k]))
    piso = [bm.verts.new((x_in, centro.y + y, max(centro.z + z, 0.01))) for y, z in
            [(R * math.cos(math.pi * k / lados), -R * math.sin(math.pi * k / lados)) for k in range(1, lados)]]
    bm.faces.new(b + piso)
    if pared:   # media luna más grande, apenas más adentro (sin pelearse con la pared de arriba)
        x2 = x_in + adentro * 0.002
        bm.faces.new([bm.verts.new((x2, centro.y + r * pared * math.cos(math.pi * k / lados),
                                    centro.z + r * pared * math.sin(math.pi * k / lados))) for k in range(lados + 1)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me); bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(nombre, me)
    col.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = False
    mat.use_backface_culling = False
    return ob


def exportar(ruta, objetos):
    # doble cara (glTF doubleSided): TRELLIS.2 deja cavidades abiertas (detrás de la cabina de un auto de prueba) que
    # con el descarte de caras de atrás se veían transparentes; así se ven oscuras por dentro
    for o in objetos:
        for m in o.data.materials:
            m.use_backface_culling = False
    bpy.ops.object.select_all(action='DESELECT')
    for o in objetos:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=ruta, export_format='GLB', use_selection=True, export_yup=True,
                              export_apply=True)


# vistas de la revisión: (nombre, perspectiva?, posición, mira a, ortho/fov). `juego` imita la cámara de la carrera
# de un juego de prueba (4,6 m atrás, 1,7 arriba), apuntada al auto y con zoom para ver el detalle (en la carrera
# mira 5 m adelante con 62-78°)
VISTAS = (('juego', True, (0.6, 4.6, 1.7), (0, 0, 0.4), 30),   # misma posición, mirando al auto y con zoom
          ('tres_cuartos', True, (3.4, -3.4, 2.0), (0, 0, 0.45), 40),
          ('costado', False, (8, 0, 0.6), (0, 0, 0.6), 2.8),
          ('arriba', False, (0, 0, 8), (0, 0, 0), 2.8))


def material_juego(objetos):
    """Como el material de pintura del auto en el juego: rugosidad 0.35, metal 0.1 (sin laca)."""
    vistos = set()
    for o in objetos:
        for m in o.data.materials:
            if m and m.name not in vistos:
                vistos.add(m.name)
                b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
                if b:
                    b.inputs['Metallic'].default_value = 0.1
                    if m.name == 'oscuro':   # como la pintura del auto en el juego para `oscuro`
                        b.inputs['Roughness'].default_value = 0.12
                    elif m.name not in ('cubierta', 'pasarrueda'):
                        b.inputs['Roughness'].default_value = 0.35


def revision(dir_salida):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'AgX'   # con Standard el blanco se quemaba y no se veían las chapas
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    w = sc.world
    bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
    for l in list(bg.inputs['Color'].links):
        w.node_tree.links.remove(l)
    bg.inputs['Color'].default_value = (0.55, 0.75, 0.95, 1)   # cielo de la carrera, aprox.
    bg.inputs['Strength'].default_value = 0.45
    bpy.ops.mesh.primitive_plane_add(size=40)
    piso = bpy.context.active_object
    piso.data.materials.append(material_color('piso_revision', (0.45, 0.36, 0.26), 0.8))
    rutas = []
    for nombre, persp, pos, mira, k in VISTAS:
        cd = bpy.data.cameras.new(nombre)
        if persp:
            cd.type = 'PERSP'; cd.sensor_fit = 'VERTICAL'; cd.angle = math.radians(k)
        else:
            cd.type = 'ORTHO'; cd.ortho_scale = k
        cam = bpy.data.objects.new(nombre, cd); sc.collection.objects.link(cam)
        cam.location = pos
        cam.rotation_euler = (Vector(mira) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
        sc.camera = cam
        sc.render.filepath = os.path.join(dir_salida, f'revision_{nombre}.png')
        bpy.ops.render.render(write_still=True)
        rutas.append(sc.render.filepath)
    bpy.data.objects.remove(piso, do_unlink=True)
    return rutas


def tarjeta(dir_salida, px=1600):
    """Tarjeta del auto (para un selector en el juego): tres cuartos de frente desde arriba, fondo
    transparente, sin piso, con las luces de la revisión. pipeline.py la recorta al auto (trabajo/tarjeta.png)."""
    sc = bpy.context.scene
    sc.render.film_transparent = True
    sc.render.resolution_x, sc.render.resolution_y = px, px * 9 // 16
    cd = bpy.data.cameras.new('tarjeta'); cd.type = 'PERSP'; cd.sensor_fit = 'VERTICAL'; cd.angle = math.radians(32)
    cam = bpy.data.objects.new('tarjeta', cd); sc.collection.objects.link(cam)
    cam.location = (3.6, -3.0, 2.2)
    cam.rotation_euler = (Vector((0, 0, 0.35)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    sc.render.filepath = os.path.join(dir_salida, 'tarjeta_render.png')
    bpy.ops.render.render(write_still=True)
    return sc.render.filepath


def oscuras(mesh, bm, umbral=0.12):
    """{índice de cara: True si su color (la textura en el centro de su UV) es oscuro y sin color} o None sin textura."""
    import numpy as np
    mat = mesh.data.materials[0] if mesh.data.materials else None
    tex = mat and next((n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image), None)
    if not tex:
        return None
    w, h = tex.image.size
    px = np.array(tex.image.pixels[:], dtype=np.float32).reshape(h, w, 4)
    uv = bm.loops.layers.uv.active
    out = {}
    for f in bm.faces:
        u = sum(l[uv].uv.x for l in f.loops) / len(f.loops)
        v = sum(l[uv].uv.y for l in f.loops) / len(f.loops)
        r, g, b, _ = px[min(h - 1, max(0, int(v * h))), min(w - 1, max(0, int(u * w)))]
        out[f.index] = max(r, g, b) < umbral and max(r, g, b) - min(r, g, b) < 0.08
    return out


def separar_materiales(mesh, umbral=0.12, vecinos=2):
    """Divide la carrocería en `pintura` y `oscuro` (vidrios, tomas de aire, bajos: lo oscuro y sin color de la
    textura), con la misma textura: el juego le da a cada uno su brillo. Cada cara toma el color de la textura en el
    centro de su UV; después `vecinos` pasadas de mayoría con las caras vecinas (sin pecas sueltas)."""
    bm = bmesh.new(); bm.from_mesh(mesh.data)
    bm.faces.ensure_lookup_table()
    oscuro = oscuras(mesh, bm, umbral)
    if oscuro is None:
        bm.free()
        return 0
    mat = mesh.data.materials[0]
    for _ in range(vecinos):
        nuevo = {}
        for f in bm.faces:
            vs = [oscuro[o.index] for e in f.edges for o in e.link_faces if o is not f]
            nuevo[f.index] = (sum(vs) * 2 > len(vs)) if vs else oscuro[f.index]
        oscuro = nuevo
    m2 = mat.copy(); m2.name = 'oscuro'; mat.name = 'pintura'
    mesh.data.materials.append(m2)
    idx = len(mesh.data.materials) - 1
    for f in bm.faces:
        if oscuro[f.index]:
            f.material_index = idx
    bm.to_mesh(mesh.data); bm.free()
    return sum(oscuro.values())


def nivelar(mesh, pasadas=3):
    """Apoya las cuatro ruedas a la misma altura: lo más bajo de la mitad de adelante contra lo de atrás (cabeceo, giro
    sobre X) y lo de la izquierda contra la derecha (rolido, giro sobre Y). Los componentes principales solos se
    torcían con un alerón grande (un auto de prueba de Pixal3D quedaba con la trompa arriba)."""
    from mathutils import Matrix
    for _ in range(pasadas):
        vs = [v.co for v in mesh.data.vertices]
        ys = [v.y for v in vs]; xs = [v.x for v in vs]
        y0, y1, x0, x1 = min(ys), max(ys), min(xs), max(xs)
        cy, cx = (y0 + y1) / 2, (x0 + x1) / 2

        def bajo(sel):   # el más bajo entre los del 2 % inferior de la zona (robusto a un vértice suelto)
            zs = sorted(v.z for v in vs if sel(v))
            return zs[min(len(zs) - 1, len(zs) // 50)], sum(1 for _ in zs)

        def punto(sel):
            z, _ = bajo(sel)
            cand = [v for v in vs if sel(v) and v.z <= z]
            return sum((v.copy() for v in cand), Vector()) / len(cand)
        pd = punto(lambda v: v.y < cy - (y1 - y0) * 0.15)
        pt = punto(lambda v: v.y > cy + (y1 - y0) * 0.15)
        cabeceo = math.atan2(pt.z - pd.z, pt.y - pd.y)
        pi = punto(lambda v: v.x > cx + (x1 - x0) * 0.15)
        pdr = punto(lambda v: v.x < cx - (x1 - x0) * 0.15)
        rolido = math.atan2(pi.z - pdr.z, pi.x - pdr.x)
        R = Matrix.Rotation(rolido, 3, 'Y') @ Matrix.Rotation(-cabeceo, 3, 'X')
        for v in mesh.data.vertices:
            v.co = R @ v.co


def alinear(mesh, trompa_lejos=True):
    """Pixal3D de una vista entrega el auto en el marco de la cámara (alineado a píxel: inclinado y girado como en la
    imagen). Lo endereza por componentes principales: largo -> Y, ancho -> X, alto -> Z. El arriba es el lado que mira
    a la cámara (está en -Y, arriba) y la trompa (-Y al final) es el extremo más lejos de la cámara si la imagen es la
    cola en tres cuartos (`trompa_lejos`), o el más cerca si es de frente. Después: centrado y ruedas en z=0."""
    import numpy as np
    from mathutils import Matrix
    vs = np.array([v.co[:] for v in mesh.data.vertices])
    c = vs.mean(axis=0)
    val, vec = np.linalg.eigh(np.cov((vs - c).T))
    largo, ancho, alto = vec[:, 2], vec[:, 1], vec[:, 0]   # de mayor a menor varianza
    hacia_camara = np.array([0.0, -1.0, 1.0]) / math.sqrt(2)
    if alto @ hacia_camara < 0:
        alto = -alto
    # la trompa queda en -Y: el eje del largo apunta a la cola
    cola_cerca = largo @ np.array([0.0, -1.0, 0.0]) > 0   # +largo apunta hacia la cámara
    if cola_cerca != trompa_lejos:
        largo = -largo
    ancho = np.cross(largo, alto)   # base derecha: X = Y × Z
    R = Matrix((ancho.tolist(), largo.tolist(), alto.tolist()))   # filas: los ejes nuevos
    for v in mesh.data.vertices:
        v.co = R @ (v.co - Vector(c))
    nivelar(mesh)
    vs = [v.co for v in mesh.data.vertices]
    zmin = min(v.z for v in vs)
    cx = (min(v.x for v in vs) + max(v.x for v in vs)) / 2
    cy = (min(v.y for v in vs) + max(v.y for v in vs)) / 2
    for v in mesh.data.vertices:
        v.co.x -= cx; v.co.y -= cy; v.co.z -= zmin
    mesh.data.update()
