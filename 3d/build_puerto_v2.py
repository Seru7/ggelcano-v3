# Puerto v2 (recomposición) — arte real CC0 de Poly Haven bien ensamblado:
# las secciones 01-04 del muelle modular encadenadas (×2 tramos), acantilados
# escaneados realzados, faroles y barriles de artista, barco holandés de
# atrezzo a contraluz, la nao IA amarrada, faro propio en lo alto del
# acantilado e iluminación HDRI fotográfica (venice_sunset).
import bpy
import importlib.util
import math
import os

import mathutils
import numpy as np

DIR = os.path.dirname(os.path.abspath(__file__))
CC0 = DIR + "/cc0"

bpy.ops.wm.read_factory_settings(use_empty=True)

spec = importlib.util.spec_from_file_location("v3", DIR + "/build_nao_v3.py")
v3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v3)


def importa(asset):
    antes = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=f"{CC0}/{asset}/{asset}.gltf")
    return [o for o in bpy.context.scene.objects if o not in antes]


def bbox(objs):
    mins = [1e9] * 3
    maxs = [-1e9] * 3
    for o in objs:
        if o.type != "MESH":
            continue
        for c in o.bound_box:
            w = o.matrix_world @ mathutils.Vector(c)
            for i in range(3):
                mins[i] = min(mins[i], w[i])
                maxs[i] = max(maxs[i], w[i])
    return mins, maxs


def grupo(objs, nombre):
    e = bpy.data.objects.new(nombre, None)
    bpy.context.scene.collection.objects.link(e)
    for o in objs:
        if o.parent is None:
            o.parent = e
    return e


# ---------------- muelle: cadena de secciones, dos tramos ----------------
kit = importa("modular_wooden_pier")
secciones = [o for o in kit if "section" in o.name and "05" not in o.name]
for o in kit:
    if o not in secciones:
        bpy.data.objects.remove(o)
g1 = grupo(secciones, "MuelleA")
# segundo tramo: duplicado empalmado midiendo la cadena real
mn, mx = bbox(secciones)
largo = mx[1] - mn[1] - 0.35          # solape leve para esconder la junta
bpy.ops.object.select_all(action="DESELECT")
for o in secciones:
    o.select_set(True)
bpy.ops.object.duplicate()
dup = [o for o in bpy.context.selected_objects]
g2 = grupo(dup, "MuelleB")
g2.location = (0, -largo, 0)
muelle = grupo([g1, g2], "Muelle")
muelle.rotation_euler = (0, 0, math.radians(90))   # el muelle corre a lo largo de X
muelle.location = (-22, 2, -1.5)                   # cubierta ≈ +1.1 sobre el agua
print("MUELLE colocado")

# ---------------- faroles y barriles sobre la cubierta ----------------
def coloca(asset, nombre, escala=1.0, pos=(0, 0, 0), rotz=0):
    objs = importa(asset)
    g = grupo(objs, nombre)
    g.scale = (escala, escala, escala)
    g.rotation_euler = (0, 0, math.radians(rotz))
    g.location = pos
    return g

DECK = 1.12
for i in range(6):
    coloca("Lantern_01", f"Farol{i}", 1.0, (-20 + i * 3.4, 3.3, DECK), 20 * i)
coloca("Barrel_01", "Barril1", 1.0, (-21.5, 1.2, DECK), 10)
coloca("Barrel_01", "Barril2", 0.92, (-20.6, 1.5, DECK), 75)

# ---------------- costa: acantilados realzados + rocas ----------------
def acantilado(asset, nombre, ancho, alto_extra, pos, rotz):
    objs = importa(asset)
    mins, maxs = bbox(objs)
    g = grupo(objs, nombre)
    s = ancho / (maxs[0] - mins[0])
    g.scale = (s, s, s * alto_extra)
    g.rotation_euler = (0, 0, math.radians(rotz))
    g.location = (pos[0], pos[1], -mins[2] * s * alto_extra - 3.2)
    return g, maxs[2] * s * alto_extra - 3.2

acantilado("coastal_cliff_01", "Acantilado1", 70, 1.0, (-4, 46), 196)
_, topF = acantilado("coastal_cliff_02", "Acantilado2", 34, 1.0, (34, 26), 205)
acantilado("coast_rocks_01", "Rocas1", 18, 1.4, (-31, 0), 25)

# ---------------- barco holandés de atrezzo, fondeado a contraluz ----------------
# (barco de fondo retirado: la nao manda sola en el plano)

# ---------------- nao IA protagonista amarrada al muelle ----------------
if os.path.exists("/tmp/nao-ia.glb"):
    antes = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath="/tmp/nao-ia.glb")
    nuevos = [o for o in bpy.context.scene.objects if o not in antes]
    g = grupo(nuevos, "NaoIA")
    g.scale = (11, 11, 11)
    g.rotation_euler = (0, 0, math.radians(8))
    g.location = (-12, 6.6, 2.45)
    print("NAO colocada")

# ---------------- faro propio sobre el acantilado 2 ----------------
def textura_piedra(nombre, base=(0.52, 0.49, 0.44), w=1024, h=1024, seed=21):
    y = np.linspace(0, 1, h)[:, None] * np.ones((1, w))
    x = np.ones((h, 1)) * np.linspace(0, 1, w)[None, :]
    filas = 11.0
    fila = np.floor(y * filas)
    despl = (fila % 2) * 0.5
    rng = np.random.default_rng(seed)
    tono = rng.uniform(0.8, 1.1, (16, 16))[fila.astype(int) % 16,
                                           (np.floor(x * 8.0 + despl)).astype(int) % 16]
    junta = np.where((y * filas) % 1.0 < 0.045, 0.6, 1.0) * \
            np.where((x * 8.0 + despl) % 1.0 < 0.03, 0.65, 1.0)
    lum = tono * junta * (0.88 + 0.24 * v3._ruido(w, h, 96, seed + 1))
    rgb = np.clip(np.stack([lum * c for c in base], axis=-1), 0, 1)
    return v3._guarda(nombre, rgb), v3._guarda(nombre + "_n", v3._normal_de_altura(lum * 0.4, 1.8))

img_p, n_p = textura_piedra("faro_piedra")
m_piedra = bpy.data.materials.new("FaroPiedra")
v3.material_texturado(m_piedra, img_p, n_p, 0.9)
m_oscuro = bpy.data.materials.new("FaroOscuro")
m_oscuro.use_nodes = True
m_oscuro.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.05, 0.06, 0.09, 1)
m_luz = bpy.data.materials.new("FaroLuz")
m_luz.use_nodes = True
bl = m_luz.node_tree.nodes["Principled BSDF"]
bl.inputs["Base Color"].default_value = (1, 0.85, 0.6, 1)
bl.inputs["Emission Color"].default_value = (1, 0.8, 0.45, 1)
bl.inputs["Emission Strength"].default_value = 40

FX, FY, FZ = 33, 23, min(10.0, max(5.0, topF - 1.4))
def cono(nombre, loc, r1, r2, alto, mt, caras=28):
    bpy.ops.mesh.primitive_cone_add(location=loc, radius1=r1, radius2=r2, depth=alto, vertices=caras)
    o = bpy.context.active_object
    o.name = nombre
    o.data.materials.append(mt)
    for p in o.data.polygons:
        p.use_smooth = True
    return o

cono("FaroTorre", (FX, FY, FZ + 4.0), 2.2, 1.5, 8.0, m_piedra)
cono("FaroCornisa", (FX, FY, FZ + 8.2), 2.0, 1.8, 0.5, m_piedra, 20)
bpy.ops.mesh.primitive_cylinder_add(location=(FX, FY, FZ + 9.0), radius=1.3, depth=1.5, vertices=16)
lin = bpy.context.active_object
lin.name = "FaroLinterna"
lin.data.materials.append(m_luz)
cono("FaroTejado", (FX, FY, FZ + 10.4), 1.55, 0.08, 1.3, m_oscuro, 16)
v3.uv_inteligente(bpy.data.objects["FaroTorre"])
print(f"FARO en z={FZ:.1f}")

# ---------------- agua para el render ----------------
bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0), size=240)
agua = bpy.context.active_object
agua.name = "AguaRender"
m_agua = bpy.data.materials.new("Agua")
m_agua.use_nodes = True
ba = m_agua.node_tree.nodes["Principled BSDF"]
ba.inputs["Base Color"].default_value = (0.05, 0.09, 0.2, 1)
ba.inputs["Roughness"].default_value = 0.13
ntA = m_agua.node_tree
ruido = ntA.nodes.new("ShaderNodeTexNoise")
ruido.inputs["Scale"].default_value = 60
bump = ntA.nodes.new("ShaderNodeBump")
bump.inputs["Strength"].default_value = 0.12
ntA.links.new(ruido.outputs["Fac"], bump.inputs["Height"])
ntA.links.new(bump.outputs["Normal"], ba.inputs["Normal"])
agua.data.materials.append(m_agua)

# ---------------- HDRI + cámara + luces de farol ----------------
s = bpy.context.scene
w = bpy.data.worlds.new("W")
w.use_nodes = True
nt = w.node_tree
env = nt.nodes.new("ShaderNodeTexEnvironment")
env.image = bpy.data.images.load(CC0 + "/sunset_puresky_2k.hdr")
fondo = nt.nodes["Background"]
nt.links.new(env.outputs["Color"], fondo.inputs["Color"])
fondo.inputs["Strength"].default_value = 1.1
mapeo = nt.nodes.new("ShaderNodeMapping")
coords = nt.nodes.new("ShaderNodeTexCoord")
nt.links.new(coords.outputs["Generated"], mapeo.inputs["Vector"])
nt.links.new(mapeo.outputs["Vector"], env.inputs["Vector"])
mapeo.inputs["Rotation"].default_value[2] = math.radians(205)  # sol tras el barco de fondo
s.world = w

s.render.engine = "CYCLES"
s.cycles.samples = 64
s.cycles.use_denoising = False
s.render.resolution_x = 1280
s.render.resolution_y = 800
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
s.collection.objects.link(cam)
s.camera = cam
cam.location = (-31, -15, 6.6)
d = mathutils.Vector((22, 23, -2.6))
cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
cam.data.lens = 36

for i in range(6):
    lz = bpy.data.objects.new(f"LuzFarol{i}", bpy.data.lights.new(f"LuzFarol{i}", "POINT"))
    lz.data.energy = 80
    lz.data.color = (1.0, 0.62, 0.28)
    lz.location = (-20 + i * 3.4, 3.3, DECK + 1.0)
    s.collection.objects.link(lz)
luzfaro = bpy.data.objects.new("LuzFaro", bpy.data.lights.new("LuzFaro", "POINT"))
luzfaro.data.energy = 4000
luzfaro.data.color = (1.0, 0.78, 0.45)
luzfaro.location = (FX, FY, FZ + 9.0)
s.collection.objects.link(luzfaro)

s.render.filepath = DIR + "/puerto2_atardecer.png"
bpy.ops.render.render(write_still=True)

fondo.inputs["Strength"].default_value = 0.06
s.render.filepath = DIR + "/puerto2_noche.png"
bpy.ops.render.render(write_still=True)
print("PUERTO2_OK")
