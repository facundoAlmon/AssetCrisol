# Paso 2: imagen -> malla 3D texturizada con TRELLIS.2 (local). Corre con el venv de TRELLIS.2
# (pipeline.py lo lanza con las variables de config.json > env_modelos: cachés de HuggingFace y de rembg).
# uso: <venv>/bin/python generar_malla_trellis.py <imagen> <dir_salida> <caras> <resolucion> <seed> <textura_px> [alfa_min [remesh [caras_min]]]
#   resolucion: 512 | 1024 | 1536 (tipo de pipeline de TRELLIS.2; 1024/1536 son en cascada desde 512)
# Salida: sin_fondo.png, forma.glb (sin textura), modelo.glb (texturizado, solo color base).
import os, sys
os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')
os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR', '1')
import numpy as np
import trimesh
from PIL import Image

CARAS_MIN = 100


def sin_sueltos(m, minimo=CARAS_MIN, tope=1.0):
    """Saca los pedacitos sueltos (cientos de 1-50 caras que deja el remesh; con ellos el bone heat de
    Blender falla con todo). Las piezas separadas de verdad (ojos, banda del sombrero) quedan, y la más grande
    siempre. Saca como mucho `tope` de las caras, empezando por las más chicas: en objetos (sin rig) va 0.1,
    un arbusto son miles de hojas sueltas; en personajes 1.0 (sin tope) o el bone heat falla."""
    s = m.copy(); s.merge_vertices(merge_tex=True, merge_norm=True)  # conectividad sin las costuras UV
    lab = trimesh.graph.connected_component_labels(s.face_adjacency, node_count=len(s.faces))
    cnt = np.bincount(lab)
    sacar = np.zeros(len(cnt), bool); total = 0
    for p in np.argsort(cnt)[:-1]:
        if cnt[p] >= minimo or total + cnt[p] > tope * len(lab):
            break
        sacar[p] = True; total += cnt[p]
    m.update_faces(~sacar[lab]); m.remove_unreferenced_vertices()
    print(f'[malla] piezas: {len(cnt)}, quedan {(~sacar).sum()} (sacadas {sacar.sum()} de < {minimo} caras, '
          f'{100 * total / len(lab):.1f} % de las caras)', flush=True)
    return m


def solo_color_base(m):
    """Material opaco con solo color base : el resto del pipeline pone su rugosidad y metal 0."""
    base = np.array(m.visual.material.baseColorTexture.convert('RGB'))
    m.visual.material = trimesh.visual.material.PBRMaterial(
        baseColorTexture=Image.fromarray(base), metallicFactor=0.0, roughnessFactor=1.0)
    return m


def sin_vram(e):
    return 'out of memory' in str(e)  # torch.OutOfMemoryError o RuntimeError de CuMesh


def relanzar(**cambios):
    """Vuelve a correr el script en un proceso nuevo: después de quedarse sin VRAM, la memoria del intento
    fallido no se libera del todo (CuMesh, referencias de la traza) y reintentar en el mismo proceso falla."""
    args = dict(zip(['img', 'out', 'caras', 'reso', 'seed', 'tex_px', 'alfa_min', 'remesh', 'caras_min'], sys.argv[1:]))
    args.setdefault('alfa_min', '0'); args.setdefault('remesh', '1'); args.setdefault('caras_min', str(CARAS_MIN))
    args.update({k: str(v) for k, v in cambios.items()})
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)] + list(args.values()))


def main():
    img_path, out = sys.argv[1], sys.argv[2]
    caras, reso, seed, tex_px = (int(a) for a in sys.argv[3:7])
    alfa_min = int(sys.argv[7]) if len(sys.argv) > 7 else 0
    remesh = sys.argv[8] != '0' if len(sys.argv) > 8 else True
    caras_min = int(sys.argv[9]) if len(sys.argv) > 9 else CARAS_MIN
    tipo = {512: '512', 1024: '1024_cascade', 1536: '1536_cascade'}[reso]
    os.makedirs(out, exist_ok=True)

    # fondo con rembg (u2net o malla.fondo, vía TRELLIS_FONDO), sin_fondo.png también lo usa el retrato. Con alfa,
    # TRELLIS no corre su removedor (RMBG-2.0, acceso restringido en HF), así que ni se carga.
    from rembg import remove, new_session
    image = remove(Image.open(img_path).convert('RGB'), session=new_session(os.environ.get('TRELLIS_FONDO', 'u2net')))
    image.save(os.path.join(out, 'sin_fondo.png'))
    if alfa_min:  # sombras semitransparentes que rembg deja (entre las cadenas de la hamaca) se vuelven una tela
        a = np.array(image.getchannel('A'))
        image.putalpha(Image.fromarray(np.where(a < alfa_min, 0, a).astype(np.uint8)))

    import torch
    from trellis2.pipelines import rembg as t_rembg
    class SinRembg:
        def __init__(self, *a, **k): pass
        def to(self, *a): return self
        def cpu(self): return self
    t_rembg.BiRefNet = SinRembg
    from trellis2.pipelines import Trellis2ImageTo3DPipeline
    import o_voxel
    from trellis2.representations.mesh.base import Mesh

    # fill_holes de TRELLIS se queda sin VRAM con superficies muy rugosas (arbusto de bolas de follaje con
    # cualquier seed): se reintenta con la caché vacía y, si no alcanza, sigue sin tapar los agujeritos
    tapar = Mesh.fill_holes
    def fill_holes_sin_vram(self, *a, **k):
        torch.cuda.empty_cache()
        try:
            return tapar(self, *a, **k)
        except (torch.OutOfMemoryError, RuntimeError) as e:
            if not sin_vram(e):
                raise
            print(f'[malla] AVISO: sin VRAM para tapar agujeros ({len(self.faces)} caras crudas), sigue sin taparlos',
                  flush=True)
            torch.cuda.empty_cache()
    Mesh.fill_holes = fill_holes_sin_vram

    # preprocess_image de TRELLIS.2 achica la imagen entera a 1024 de lado y después recorta un cuadrado justo a la caja
    # del alfa (> 0,8), sin margen: el personaje toca los bordes y, si es chico en la imagen, pierde resolución.
    # malla.margen (TRELLIS_MARGEN, p. ej. 1.1 como Pixal3D y PixelArtistry): primero el recorte cuadrado con ese
    # margen (fondo transparente) y después a 1024
    margen = float(os.environ.get('TRELLIS_MARGEN') or 0)
    if margen:
        def preprocesar(self, entrada):
            a = np.array(entrada.getchannel('A'))
            ys, xs = np.nonzero(a > 0.8 * 255)
            cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
            lado = max(xs.max() - xs.min(), ys.max() - ys.min()) * margen
            caja = tuple(round(v) for v in (cx - lado / 2, cy - lado / 2, cx + lado / 2, cy + lado / 2))
            rec = entrada.crop(caja).resize((1024, 1024), Image.Resampling.LANCZOS)  # afuera: transparente
            r = np.array(rec).astype(np.float32) / 255
            print(f'[malla] recorte a la máscara con margen {margen} ({caja[2] - caja[0]} px -> 1024)', flush=True)
            return Image.fromarray((r[:, :, :3] * r[:, :, 3:4] * 255).astype(np.uint8))
        Trellis2ImageTo3DPipeline.preprocess_image = preprocesar

    print(f'[malla] TRELLIS.2 {tipo}...', flush=True)
    pipe = Trellis2ImageTo3DPipeline.from_pretrained('microsoft/TRELLIS.2-4B')
    pipe.low_vram = True  # cada modelo en la GPU solo mientras se usa: entra en 16 GB
    pipe.cuda()
    # objetos macizos (una caja) tienen muchos más voxeles que un personaje y a 1024 no entran en 16 GB:
    # se reintenta con la resolución de abajo (max_num_tokens no sirve: la cascada nunca baja de 1024)
    try:
        mesh = pipe.run(image, seed=seed, pipeline_type=tipo)[0]
    except (torch.OutOfMemoryError, RuntimeError) as e:
        if not sin_vram(e) or reso == 512:
            raise
        abajo = {1536: 1024, 1024: 512}[reso]
        print(f'[malla] AVISO: sin VRAM; reintento con resolucion {abajo} (menos detalle)', flush=True)
        relanzar(reso=abajo)
    del pipe; torch.cuda.empty_cache()  # antes de simplificar: con superficies rugosas no entran los dos
    print(f'[malla] caras crudas: {len(mesh.faces)}', flush=True)
    # límite de nvdiffrast; a 1536 la cruda (18 M de caras en un auto de prueba) no entra al remesh en 16 GB y sin
    # remesh quedan capas dobles y caras al revés (manchas en los autos): se baja antes
    mesh.simplify(int(os.environ.get('TRELLIS_CARAS_REMESH', 4000000 if reso == 1536 else 16777216)))

    # el dual contouring del remesh va a la resolución de la grilla: a 1536 no entra en 16 GB (ni con 4 M de caras) y
    # sin remesh el auto sale con capas dobles y caras al revés. Se hace a una grilla más chica (la forma sigue siendo
    # la de 1536); si tampoco entra, se baja hasta 1024 antes de abandonar el remesh
    import cumesh.remeshing
    tope_dc = int(os.environ.get('TRELLIS_RES_REMESH', 1280))
    dc = cumesh.remeshing.remesh_narrow_band_dc
    def dc_con_tope(vertices, faces, center, scale, resolution, band, **k):
        if resolution > tope_dc:
            base = scale * resolution / (resolution + 3 * band)
            resolution = tope_dc
            scale = (resolution + 3 * band) / resolution * base
            print(f'[malla] remesh a {resolution} (grilla de {reso})', flush=True)
        return dc(vertices, faces, center=center, scale=scale, resolution=resolution, band=band, **k)
    cumesh.remeshing.remesh_narrow_band_dc = dc_con_tope

    print('[malla] limpieza, UV y horneado de textura...', flush=True)
    def a_glb(remesh):
        return o_voxel.postprocess.to_glb(
            vertices=mesh.vertices, faces=mesh.faces, attr_volume=mesh.attrs, coords=mesh.coords,
            attr_layout=mesh.layout, voxel_size=mesh.voxel_size, aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
            decimation_target=caras, texture_size=tex_px, remesh=remesh, remesh_band=1, remesh_project=0,
            verbose=True)
    try:
        glb = a_glb(remesh)
    except (torch.OutOfMemoryError, RuntimeError) as e:
        # mallas muy densas (plumas de un pájaro chibi): el remesh las lleva a 28 M de caras y CuMesh no las simplifica
        # en 16 GB. Sin remesh se simplifica directo la malla original
        if not sin_vram(e) or not remesh:
            raise
        if reso > 1024 and tope_dc > 1024:
            os.environ['TRELLIS_RES_REMESH'] = '1024'
            print(f'[malla] AVISO: remesh a {tope_dc} sin VRAM; reintento a 1024', flush=True)
            relanzar()
        print('[malla] AVISO: malla muy densa sin VRAM; reintento sin remesh', flush=True)
        relanzar(remesh=0)
    if isinstance(glb, trimesh.Scene):
        glb = glb.dump(concatenate=True)
    glb = sin_sueltos(glb, caras_min, 1.0 if caras_min >= CARAS_MIN else 0.1)  # objetos: 10 caras, tope 10 %
    if os.environ.get('TRELLIS_CRUDO'):  # diagnóstico: el glb con metal/rugosidad, antes de dejar solo el color base
        glb.export(os.path.join(out, 'modelo_crudo.glb'))
    glb = solo_color_base(glb)
    # glTF Y arriba (Z arriba en Blender); el frente queda en -Y de Blender
    trimesh.Trimesh(glb.vertices, glb.faces, process=False).export(os.path.join(out, 'forma.glb'))
    glb.export(os.path.join(out, 'modelo.glb'))
    print('[malla] caras:', len(glb.faces), flush=True)
    print('[malla] listo:', os.path.join(out, 'modelo.glb'), flush=True)


if __name__ == '__main__':
    main()
