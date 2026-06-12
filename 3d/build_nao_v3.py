# Nao Victoria v3 "de autor" — reutiliza la construcción geométrica del builder
# base y le añade lo que separa un asset de código de un asset de artista:
#   1. Texturas generadas píxel a píxel (numpy): madera con vetas y tablones,
#      lona con trama de hilo y costuras — con sus mapas de normales.
#   2. UVs por proyección inteligente en las mallas hechas a mano.
#   3. Velas por SIMULACIÓN DE TELA de Blender (pinneadas a la verga, viento
#      real): caída y arrugas físicas, no curvas paramétricas.
#   4. Subdivisión del casco para una silueta sin facetas.
# Ejecutar: blender --background --python-use-system-env --python build_nao_v3.py
import bpy
import importlib.util
import math
import os
import sys

import numpy as np

DIR = os.path.dirname(os.path.abspath(__file__))
OUT = DIR + "/"

# cargar el builder base como módulo (tiene guard de __main__)
spec = importlib.util.spec_from_file_location("base", DIR + "/build_nao_victoria.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


# ---------------- texturas procedurales (numpy → bpy.Image) ----------------
def _suaviza(a, n=3):
    """Desenfoque caja separable y barato (sin scipy)."""
    for _ in range(n):
        a = (a + np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 5.0
    return a


def _ruido(w, h, esc, seed):
    """Ruido de valor: rejilla aleatoria ampliada con suavizado."""
    rng = np.random.default_rng(seed)
    g = rng.random((max(2, -(-h // esc)), max(2, -(-w // esc))))   # techo
    g = np.kron(g, np.ones((esc, esc)))[:h, :w]
    return _suaviza(g, 4)


def _guarda(nombre, rgb):
    """rgb: float HxWx3 en [0,1] → bpy.Image PNG."""
    h, w, _ = rgb.shape
    img = bpy.data.images.new(nombre, width=w, height=h, alpha=False)
    px = np.ones((h, w, 4), dtype=np.float32)
    px[:, :, :3] = rgb.astype(np.float32)
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = OUT + nombre + ".png"
    img.file_format = "PNG"
    img.save()
    return img


def _normal_de_altura(alt, fuerza=2.0):
    """Mapa de normales tangente desde un campo de altura."""
    dx = (np.roll(alt, -1, 1) - np.roll(alt, 1, 1)) * fuerza
    dy = (np.roll(alt, -1, 0) - np.roll(alt, 1, 0)) * fuerza
    nz = np.ones_like(alt)
    ln = np.sqrt(dx * dx + dy * dy + nz * nz)
    n = np.stack([-dx / ln, -dy / ln, nz / ln], axis=-1)
    return n * 0.5 + 0.5


def textura_madera(nombre, base_rgb, tablones=12, seed=3, w=1024, h=1024):
    y = np.linspace(0, 1, h)[:, None] * np.ones((1, w))
    x = np.ones((h, 1)) * np.linspace(0, 1, w)[None, :]
    fila = np.floor(y * tablones)
    rng = np.random.default_rng(seed)
    tono_fila = rng.uniform(0.82, 1.12, int(tablones) + 1)[fila.astype(int)]
    desfase = rng.uniform(0, 9, int(tablones) + 1)[fila.astype(int)]
    # vetas: ondas largas con meandro de ruido por tablón
    meandro = _ruido(w, h, 64, seed + 1) * 2.2
    veta = 0.5 + 0.5 * np.sin(x * 95.0 + desfase * 7.0 + meandro * 3.0)
    veta = 0.86 + 0.14 * veta ** 2
    # juntas entre tablones + variación sucia general
    junta = np.where((y * tablones) % 1.0 < 0.035, 0.55, 1.0)
    mugre = 0.9 + 0.2 * _ruido(w, h, 128, seed + 2)
    lum = tono_fila * veta * junta * mugre
    rgb = np.stack([lum * base_rgb[0], lum * base_rgb[1], lum * base_rgb[2]], axis=-1)
    rgb = np.clip(rgb, 0, 1)
    alt = lum * 0.5 + np.where((y * tablones) % 1.0 < 0.035, -0.5, 0.0)
    return _guarda(nombre, rgb), _guarda(nombre + "_n", _normal_de_altura(alt, 1.6))


def textura_lona(nombre, base_rgb=(0.93, 0.89, 0.79), seed=11, w=1024, h=1024, cruz=False):
    y = np.linspace(0, 1, h)[:, None] * np.ones((1, w))
    x = np.ones((h, 1)) * np.linspace(0, 1, w)[None, :]
    trama = (0.5 + 0.5 * np.sin(x * 880.0)) * (0.5 + 0.5 * np.sin(y * 880.0))
    trama = 0.93 + 0.07 * trama
    # paños horizontales con costura
    costura = np.where((y * 6.0) % 1.0 < 0.02, 0.78, 1.0)
    manchas = 0.92 + 0.16 * _ruido(w, h, 160, seed)
    lum = trama * costura * manchas
    rgb = np.clip(np.stack([lum * c for c in base_rgb], axis=-1), 0, 1)
    if cruz:
        # cruz de Santiago pintada EN la tela (se arruga con ella): banda
        # vertical u∈[.43,.57] v∈[.10,.90] y horizontal u∈[.18,.82] v∈[.50,.68]
        # (v de textura = 1 - v paramétrico de la vela), borde roído con ruido
        borde = (_ruido(w, h, 24, seed + 5) - 0.5) * 0.02
        en_v = (np.abs(x - 0.5) < 0.07 + borde) & (np.abs(y - 0.5) < 0.40 + borde)
        en_h = (np.abs(x - 0.5) < 0.32 + borde) & (np.abs(y - 0.59) < 0.09 + borde)
        mascara = (en_v | en_h).astype(float)
        mascara = _suaviza(mascara, 2)
        rojo = np.stack([0.62 * lum, 0.16 * lum, 0.10 * lum], axis=-1)
        rgb = rgb * (1 - mascara[..., None]) + rojo * mascara[..., None]
    alt = trama * 0.3 + np.where((y * 6.0) % 1.0 < 0.02, -0.3, 0.0)
    return _guarda(nombre, rgb), _guarda(nombre + "_n", _normal_de_altura(alt, 1.0))


def uv_parametrico(nombre, filas, cols):
    """UVs directos de la rejilla paramétrica de la vela (vértices en orden
    fila-a-fila): u = columna, v = 1 - fila. Se asignan ANTES de la simulación
    de tela, así la textura (y la cruz pintada) se arruga CON la tela."""
    obj = bpy.data.objects.get(nombre)
    if not obj:
        return
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for loop in me.loops:
        v = loop.vertex_index
        i, j = divmod(v, cols)
        uv.data[loop.index].uv = (j / (cols - 1), 1.0 - i / (filas - 1))


# ---------------- materiales con textura ----------------
def material_texturado(mat, img, img_n, rugosidad=0.8, metal=0.0, tinte=None):
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = rugosidad
    bsdf.inputs["Metallic"].default_value = metal
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    if tinte:
        mezcla = nt.nodes.new("ShaderNodeMix")
        mezcla.data_type = "RGBA"
        mezcla.blend_type = "MULTIPLY"
        mezcla.inputs["Factor"].default_value = 1.0
        mezcla.inputs[7].default_value = (*tinte, 1.0)  # B color
        nt.links.new(tex.outputs["Color"], mezcla.inputs[6])  # A color
        nt.links.new(mezcla.outputs[2], bsdf.inputs["Base Color"])
    else:
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    texn = nt.nodes.new("ShaderNodeTexImage")
    texn.image = img_n
    img_n.colorspace_settings.name = "Non-Color"
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = 0.8
    nt.links.new(texn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])


def uv_inteligente(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")


# ---------------- velas: simulación de tela ----------------
def simula_velas(nombres_velas, frames=26):
    """Pinnea la fila superior de cada vela (cuelga de su verga) y deja que el
    viento de +X la hinche. Al final se aplica el modificador (malla estática
    con arrugas reales; el vaivén fino lo pone el shader web)."""
    esc = bpy.context.scene
    # gravedad reducida: queremos tela HINCHADA por el viento, no cortinas caídas
    esc.gravity = (0, 0, -1.6)
    # viento desde popa (+X hincha hacia proa como el builder original: vientre +X)
    bpy.ops.object.effector_add(type="WIND", location=(-8, 0, 5))
    viento = bpy.context.active_object
    viento.rotation_euler = (0, math.radians(90), 0)   # eje Z del empty → +X
    viento.field.strength = 1050
    viento.field.noise = 1.2
    viento.field.flow = 0.4
    esc.frame_start = 1
    esc.frame_end = frames
    for nombre, fila_sup in nombres_velas:
        obj = bpy.data.objects.get(nombre)
        if not obj:
            continue
        vg = obj.vertex_groups.new(name="pin")
        vg.add(list(range(fila_sup)), 1.0, "REPLACE")
        # esquinas bajas también sujetas (escotas) para que no salga volando
        n = len(obj.data.vertices)
        vg.add([n - 1, n - fila_sup], 0.9, "REPLACE")
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new("Tela", "CLOTH")
        mod.settings.vertex_group_mass = "pin"
        mod.settings.quality = 6
        mod.settings.mass = 0.25
        mod.settings.air_damping = 1.0
        mod.settings.tension_stiffness = 8
        mod.settings.bending_stiffness = 0.15
    for f in range(1, frames + 1):
        esc.frame_set(f)
    for nombre, _ in nombres_velas:
        obj = bpy.data.objects.get(nombre)
        if not obj or "Tela" not in obj.modifiers:
            continue
        bpy.context.view_layer.objects.active = obj
        try:
            bpy.ops.object.modifier_apply(modifier="Tela")
        except RuntimeError as e:
            print("CLOTH_FALLO", nombre, e)
    bpy.data.objects.remove(viento)


def render_preview_cycles():
    """Preview con Cycles (las texturas de nodos NO se ven en Workbench)."""
    import mathutils
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.samples = 24
    s.cycles.use_denoising = False
    s.render.resolution_x = 1000
    s.render.resolution_y = 700
    luz = bpy.data.objects.new("Sol", bpy.data.lights.new("Sol", "SUN"))
    luz.data.energy = 4.0
    luz.rotation_euler = (math.radians(55), 0, math.radians(-140))
    s.collection.objects.link(luz)
    w = bpy.data.worlds.new("W")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.85, 0.83, 0.78, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.7
    s.world = w
    cam = bpy.data.objects.new("PrevCam", bpy.data.cameras.new("PrevCam"))
    s.collection.objects.link(cam)
    s.camera = cam
    for nombre, loc in (("3q", (16, -13, 7)), ("perfil", (0.5, -20, 4))):
        cam.location = loc
        d = mathutils.Vector((-loc[0], -loc[1], 2.5 - loc[2]))
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        s.render.filepath = OUT + f"preview_{nombre}.png"
        bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)
    bpy.data.objects.remove(luz)
    print("PREVIEWS_OK")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    base.MATS.clear()
    base.construye_casco()
    base.construye_castillos()
    base.construye_arboladura()
    base.construye_velamen()

    # --- la cruz ya no es malla: va pintada en la textura de la vela mayor ---
    for nombre in ("CruzVertical", "CruzHorizontal"):
        o = bpy.data.objects.get(nombre)
        if o:
            bpy.data.objects.remove(o)

    # --- UVs paramétricos de las velas ANTES de simular (la textura se arruga
    #     con la tela) ---
    for nombre, filas, cols in (("VelaMayor", 17, 25), ("GaviaMayor", 17, 25),
                                ("VelaTrinquete", 17, 25), ("Cebadera", 17, 25),
                                ("VelaMesana", 13, 17)):
        uv_parametrico(nombre, filas, cols)

    # --- velas de tela real ---
    # (nombre, nº de vértices de la fila superior pinneada)
    simula_velas([
        ("VelaMayor", 25), ("GaviaMayor", 25), ("VelaTrinquete", 25),
        ("Cebadera", 25), ("VelaMesana", 17),
    ])

    # --- texturas ---
    img_casco, n_casco = textura_madera("nao_casco", (0.36, 0.23, 0.12), tablones=14, seed=3)
    img_cub, n_cub = textura_madera("nao_cubierta", (0.55, 0.42, 0.25), tablones=10, seed=8)
    img_vela, n_vela = textura_lona("nao_vela")
    img_vcruz, n_vcruz = textura_lona("nao_velacruz", cruz=True)
    # la vela mayor estrena material propio con la cruz pintada
    mat_cruz = bpy.data.materials.new("VelaCruz")
    material_texturado(mat_cruz, img_vcruz, n_vcruz, 0.92)
    vmayor = bpy.data.objects.get("VelaMayor")
    if vmayor:
        vmayor.data.materials.clear()
        vmayor.data.materials.append(mat_cruz)

    # --- materiales: textura donde hay superficie, color donde hay cabo ---
    M = bpy.data.materials
    if "CascoAlto" in M:
        material_texturado(M["CascoAlto"], img_casco, n_casco, 0.78)
    if "CascoBajo" in M:
        material_texturado(M["CascoBajo"], img_casco, n_casco, 0.85, tinte=(0.55, 0.5, 0.48))
    if "Cubierta" in M:
        material_texturado(M["Cubierta"], img_cub, n_cub, 0.8)
    if "Madera" in M:
        material_texturado(M["Madera"], img_casco, n_casco, 0.75, tinte=(1.25, 1.1, 0.95))
    if "Vela" in M:
        material_texturado(M["Vela"], img_vela, n_vela, 0.92)
    if "Oro" in M:
        nt = M["Oro"].node_tree
        b = nt.nodes["Principled BSDF"]
        b.inputs["Metallic"].default_value = 0.85
        b.inputs["Roughness"].default_value = 0.38
    if "Rojo" in M:
        nt = M["Rojo"].node_tree
        nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.88

    # --- UVs en las mallas artesanales (las velas ya tienen el paramétrico) ---
    for nombre in ["Casco", "Cubierta", "AmuradaB", "AmuradaE",
                   "CintonAlto0", "CintonAlto1", "CintonBajo0", "CintonBajo1"]:
        o = bpy.data.objects.get(nombre)
        if o:
            uv_inteligente(o)

    # --- silueta sin facetas: subsurf ligero en el casco ---
    casco = bpy.data.objects.get("Casco")
    if casco:
        bpy.context.view_layer.objects.active = casco
        mod = casco.modifiers.new("Sub", "SUBSURF")
        mod.levels = 1
        mod.render_levels = 1
        bpy.ops.object.modifier_apply(modifier="Sub")

    total = 0
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            o.data.calc_loop_triangles()
            total += len(o.data.loop_triangles)
    print(f"TRIS_TOTALES:{total}")

    render_preview_cycles()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=OUT + "ship.glb",
        export_format="GLB",
        export_animations=False,
        export_cameras=False,
        export_yup=True,
    )
    print("SHIP_V3_OK")


if __name__ == "__main__":
    main()
