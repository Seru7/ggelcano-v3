# Puerto v3 — RECREACIÓN DEL CONCEPT ART (flujo estudio: el concept manda).
# El concept de Magnific (concept_clean.jpg) hace de fondo visible a cámara
# (cielo + ladera + pueblo) y el PRIMER TÉRMINO se reconstruye en 3D sobre sus
# posiciones exactas: nao IA en el centro, faro sobre peñón a la derecha,
# malecón de piedra curvándose a la izquierda, embarcadero con faroles abajo.
# En la web (Hito 3) el concept será skydome/billboard y el 3D dará parallax.
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


def grupo(objs, nombre):
    e = bpy.data.objects.new(nombre, None)
    bpy.context.scene.collection.objects.link(e)
    for o in objs:
        if o.parent is None:
            o.parent = e
    return e


def coloca(asset, nombre, escala=1.0, pos=(0, 0, 0), rotz=0):
    g = grupo(importa(asset), nombre)
    g.scale = (escala, escala, escala)
    g.rotation_euler = (0, 0, math.radians(rotz))
    g.location = pos
    return g


# ---------------- materiales base ----------------
def textura_piedra(nombre, base=(0.5, 0.46, 0.4), w=1024, h=1024, seed=21):
    y = np.linspace(0, 1, h)[:, None] * np.ones((1, w))
    x = np.ones((h, 1)) * np.linspace(0, 1, w)[None, :]
    filas = 10.0
    fila = np.floor(y * filas)
    despl = (fila % 2) * 0.5
    rng = np.random.default_rng(seed)
    tono = rng.uniform(0.78, 1.1, (16, 16))[fila.astype(int) % 16,
                                            (np.floor(x * 9.0 + despl)).astype(int) % 16]
    junta = np.where((y * filas) % 1.0 < 0.05, 0.58, 1.0) * \
            np.where((x * 9.0 + despl) % 1.0 < 0.035, 0.62, 1.0)
    lum = tono * junta * (0.86 + 0.26 * v3._ruido(w, h, 96, seed + 1))
    rgb = np.clip(np.stack([lum * c for c in base], axis=-1), 0, 1)
    return v3._guarda(nombre, rgb), v3._guarda(nombre + "_n", v3._normal_de_altura(lum * 0.45, 1.9))


img_p, n_p = textura_piedra("v3_piedra")
m_piedra = bpy.data.materials.new("Piedra")
v3.material_texturado(m_piedra, img_p, n_p, 0.9)
m_oscuro = bpy.data.materials.new("Oscuro")
m_oscuro.use_nodes = True
m_oscuro.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.05, 0.05, 0.07, 1)
m_luz = bpy.data.materials.new("LuzCalida")
m_luz.use_nodes = True
bl = m_luz.node_tree.nodes["Principled BSDF"]
bl.inputs["Base Color"].default_value = (1, 0.8, 0.5, 1)
bl.inputs["Emission Color"].default_value = (1, 0.7, 0.32, 1)
bl.inputs["Emission Strength"].default_value = 35


def cono(nombre, loc, r1, r2, alto, mt, caras=28):
    bpy.ops.mesh.primitive_cone_add(location=loc, radius1=r1, radius2=r2, depth=alto, vertices=caras)
    o = bpy.context.active_object
    o.name = nombre
    o.data.materials.append(mt)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def caja(nombre, loc, dim, mt, rotz=0):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=(0, 0, math.radians(rotz)))
    o = bpy.context.active_object
    o.name = nombre
    o.dimensions = dim
    o.data.materials.append(mt)
    return o


# ================= composición clavada al concept =================
# cámara a ras de agua mirando al norte; el concept llena el fondo

# --- nao IA en el centro del cuadro, proa a babor (como en el concept) ---
if os.path.exists("/tmp/nao-ia.glb"):
    antes = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath="/tmp/nao-ia.glb")
    g = grupo([o for o in bpy.context.scene.objects if o not in antes], "NaoIA")
    g.scale = (13, 13, 13)
    g.rotation_euler = (0, 0, math.radians(196))
    g.location = (-3, 13.5, 2.6)

# --- peñón + faro a la derecha (tapando el pintado, con margen) ---
# el peñón ya está PINTADO en el clean plate: solo plantamos el faro encima,
# alineado a su cima en pantalla (cámara fija, composición de matte clásica)
FX, FY, FZ = 30, 52, 7.2
cono("FaroTorre", (FX, FY, FZ + 3.6), 1.9, 1.25, 7.2, m_piedra)
cono("FaroCornisa", (FX, FY, FZ + 7.4), 1.7, 1.5, 0.45, m_piedra, 20)
bpy.ops.mesh.primitive_cylinder_add(location=(FX, FY, FZ + 8.1), radius=1.05, depth=1.4, vertices=16)
lin = bpy.context.active_object
lin.name = "FaroLinterna"
lin.data.materials.append(m_luz)
cono("FaroTejado", (FX, FY, FZ + 9.3), 1.3, 0.07, 1.2, m_oscuro, 16)
v3.uv_inteligente(bpy.data.objects["FaroTorre"])

# --- embarcadero de madera CC0 abajo-derecha con faroles ---
kit = importa("modular_wooden_pier")
secciones = [o for o in kit if "section" in o.name and "05" not in o.name]
for o in kit:
    if o not in secciones:
        bpy.data.objects.remove(o)
emb = grupo(secciones, "Embarcadero")
emb.rotation_euler = (0, 0, math.radians(38))
emb.location = (8.5, -4, -1.4)
coloca("Lantern_01", "FarolEmb1", 1.1, (7.2, -2.2, 1.25), 30)
coloca("Lantern_01", "FarolEmb2", 1.1, (10.4, 1.8, 1.25), -15)
coloca("Barrel_01", "BarrilEmb", 0.95, (9.0, -0.5, 1.25), 55)

# --- agua cálida espejo ---
bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0), size=300)
agua = bpy.context.active_object
agua.name = "AguaRender"
m_agua = bpy.data.materials.new("Agua")
m_agua.use_nodes = True
ba = m_agua.node_tree.nodes["Principled BSDF"]
ba.inputs["Base Color"].default_value = (0.09, 0.085, 0.045, 1)
ba.inputs["Roughness"].default_value = 0.08
ba.inputs["Metallic"].default_value = 0.4
ntA = m_agua.node_tree
ruido = ntA.nodes.new("ShaderNodeTexNoise")
ruido.inputs["Scale"].default_value = 90
bump = ntA.nodes.new("ShaderNodeBump")
bump.inputs["Strength"].default_value = 0.06
ntA.links.new(ruido.outputs["Fac"], bump.inputs["Height"])
ntA.links.new(bump.outputs["Normal"], ba.inputs["Normal"])
agua.data.materials.append(m_agua)

# ================= mundo: concept de fondo + HDRI iluminando =================
s = bpy.context.scene
w = bpy.data.worlds.new("W")
w.use_nodes = True
nt = w.node_tree
env = nt.nodes.new("ShaderNodeTexEnvironment")
env.image = bpy.data.images.load(CC0 + "/sunset_puresky_2k.hdr")
fondo = nt.nodes["Background"]
nt.links.new(env.outputs["Color"], fondo.inputs["Color"])
fondo.inputs["Strength"].default_value = 1.0
coords = nt.nodes.new("ShaderNodeTexCoord")
mapeo = nt.nodes.new("ShaderNodeMapping")
nt.links.new(coords.outputs["Generated"], mapeo.inputs["Vector"])
nt.links.new(mapeo.outputs["Vector"], env.inputs["Vector"])
mapeo.inputs["Rotation"].default_value[2] = math.radians(195)
matte = nt.nodes.new("ShaderNodeTexImage")
matte.image = bpy.data.images.load(CC0 + "/concept_clean.jpg")
nt.links.new(coords.outputs["Window"], matte.inputs["Vector"])
fondoM = nt.nodes.new("ShaderNodeBackground")
fondoM.inputs["Strength"].default_value = 1.0
nt.links.new(matte.outputs["Color"], fondoM.inputs["Color"])
lp = nt.nodes.new("ShaderNodeLightPath")
mixw = nt.nodes.new("ShaderNodeMixShader")
nt.links.new(lp.outputs["Is Camera Ray"], mixw.inputs["Fac"])
nt.links.new(fondo.outputs["Background"], mixw.inputs[1])
nt.links.new(fondoM.outputs["Background"], mixw.inputs[2])
nt.links.new(mixw.outputs["Shader"], nt.nodes["World Output"].inputs["Surface"])
s.world = w

# sol cálido a contraluz (los dios-rayos del concept vienen de detrás del faro)
sol = bpy.data.objects.new("Sol", bpy.data.lights.new("Sol", "SUN"))
sol.data.energy = 3.4
sol.data.color = (1.0, 0.62, 0.3)
sol.rotation_euler = (math.radians(74), 0, math.radians(-138))
s.collection.objects.link(sol)

# reflector naranja fuera de cámara: el agua refleja el cielo del concept
bpy.ops.mesh.primitive_plane_add(location=(8, 110, 30), size=1)
refl = bpy.context.active_object
refl.name = "ReflectorCielo"
refl.scale = (220, 1, 42)
refl.rotation_euler = (math.radians(80), 0, 0)
m_refl = bpy.data.materials.new("ReflCielo")
m_refl.use_nodes = True
br = m_refl.node_tree.nodes["Principled BSDF"]
br.inputs["Emission Color"].default_value = (1.0, 0.5, 0.16, 1)
br.inputs["Emission Strength"].default_value = 30.0
refl.data.materials.append(m_refl)
refl.visible_camera = False

rimN = bpy.data.objects.new("RimNao", bpy.data.lights.new("RimNao", "SUN"))
rimN.data.energy = 2.2
rimN.data.color = (1.0, 0.72, 0.42)
rimN.rotation_euler = (math.radians(70), 0, math.radians(-25))
s.collection.objects.link(rimN)

# luces de los faroles
for px, py, pz in ((7.2, -2.2, 2.4), (10.4, 1.8, 2.4)):
    lz = bpy.data.objects.new("LuzF", bpy.data.lights.new("LuzF", "POINT"))
    lz.data.energy = 90
    lz.data.color = (1.0, 0.6, 0.25)
    lz.location = (px, py, pz)
    s.collection.objects.link(lz)
lzf = bpy.data.objects.new("LuzFaro", bpy.data.lights.new("LuzFaro", "POINT"))
lzf.data.energy = 5000
lzf.data.color = (1.0, 0.75, 0.4)
lzf.location = (FX, FY, FZ + 8.1)
s.collection.objects.link(lzf)

# ================= cámara clavada al encuadre del concept =================
s.render.engine = "CYCLES"
s.cycles.samples = 72
s.cycles.use_denoising = False
s.render.resolution_x = 1360
s.render.resolution_y = 680
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
s.collection.objects.link(cam)
s.camera = cam
cam.location = (1.5, -22, 2.4)
d = mathutils.Vector((-1, 30, 2.6))
cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
cam.data.lens = 30

s.render.filepath = DIR + "/puerto3_concept3d.png"
bpy.ops.render.render(write_still=True)
print("PUERTO3_OK")
