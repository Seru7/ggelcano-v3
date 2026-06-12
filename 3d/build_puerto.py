# Puerto de "La Travesía" (Hito 2, escenas E5-E6) — espigón de piedra, faro,
# muelle de madera con 6 faroles (uno por sector), pueblo en ladera con
# ventanas emisivas INDIVIDUALES (la web las enciende una a una en E6).
# Estética: low-poly elegante en paleta Elcano. 0 créditos: primitivas +
# texturas numpy. Exporta puerto.glb (sin agua: el mar lo pone la web) y
# renderiza el look en atardecer y noche para aprobación del CEO.
# Ejecutar: blender --background --python-use-system-env --python build_puerto.py
import bpy
import importlib.util
import math
import os
import random

import numpy as np

DIR = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("v3", DIR + "/build_nao_v3.py")
v3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v3)  # trae texturas numpy, material_texturado, uv_inteligente

random.seed(7)
bpy.ops.wm.read_factory_settings(use_empty=True)


# ---------------- texturas ----------------
def textura_piedra(nombre, base=(0.42, 0.40, 0.37), w=1024, h=1024, seed=21):
    y = np.linspace(0, 1, h)[:, None] * np.ones((1, w))
    x = np.ones((h, 1)) * np.linspace(0, 1, w)[None, :]
    filas = 9.0
    fila = np.floor(y * filas)
    despl = (fila % 2) * 0.5
    col = np.floor(x * 7.0 + despl)
    rng = np.random.default_rng(seed)
    tono = rng.uniform(0.78, 1.12, (16, 16))[fila.astype(int) % 16, col.astype(int) % 16]
    junta_h = np.where((y * filas) % 1.0 < 0.05, 0.55, 1.0)
    junta_v = np.where((x * 7.0 + despl) % 1.0 < 0.035, 0.6, 1.0)
    mugre = 0.88 + 0.24 * v3._ruido(w, h, 96, seed + 1)
    lum = tono * junta_h * junta_v * mugre
    rgb = np.clip(np.stack([lum * c for c in base], axis=-1), 0, 1)
    alt = lum * 0.4 + np.where((y * filas) % 1.0 < 0.05, -0.5, 0.0)
    return v3._guarda(nombre, rgb), v3._guarda(nombre + "_n", v3._normal_de_altura(alt, 1.8))


img_piedra, n_piedra = textura_piedra("pto_piedra")
img_mad, n_mad = v3.textura_madera("pto_madera", (0.34, 0.22, 0.12), tablones=16, seed=14)

M = {}
def mat(nombre, **kw):
    if nombre in M:
        return M[nombre]
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    if "color" in kw:
        b.inputs["Base Color"].default_value = (*kw["color"], 1)
    b.inputs["Roughness"].default_value = kw.get("rug", 0.85)
    b.inputs["Metallic"].default_value = kw.get("met", 0.0)
    if "emisivo" in kw:
        b.inputs["Emission Color"].default_value = (*kw["emisivo"], 1)
        b.inputs["Emission Strength"].default_value = kw.get("fuerza", 4.0)
    M[nombre] = m
    return m

m_piedra = bpy.data.materials.new("Piedra")
v3.material_texturado(m_piedra, img_piedra, n_piedra, 0.92)
m_madera = bpy.data.materials.new("MaderaPuerto")
v3.material_texturado(m_madera, img_mad, n_mad, 0.8)
m_faro = mat("FaroMuro", color=(0.86, 0.82, 0.72), rug=0.8)
m_oscuro = mat("TejadoOscuro", color=(0.10, 0.12, 0.18), rug=0.7)
m_casa = mat("CasaMuro", color=(0.72, 0.66, 0.55), rug=0.9)
m_tierra = mat("Ladera", color=(0.13, 0.16, 0.24), rug=1.0)
m_farol = mat("FarolLuz", color=(1.0, 0.85, 0.55), emisivo=(1.0, 0.72, 0.35), fuerza=6.0)
m_ventana = mat("VentanaLuz", color=(1.0, 0.86, 0.6), emisivo=(1.0, 0.76, 0.42), fuerza=5.0)
m_faroluz = mat("FaroLuz", color=(1.0, 0.9, 0.7), emisivo=(1.0, 0.85, 0.55), fuerza=10.0)


def caja(nombre, loc, dim, material, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = nombre
    o.dimensions = dim
    o.data.materials.append(material)
    return o


def cono(nombre, loc, r1, r2, alto, material, caras=24, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(location=loc, rotation=rot,
                                    radius1=r1, radius2=r2, depth=alto, vertices=caras)
    o = bpy.context.active_object
    o.name = nombre
    o.data.materials.append(material)
    return o


# ---------------- espigón de piedra (arco que abraza la dársena) ----------------
for i in range(15):
    a = math.radians(-30 + i * 9)
    r = 26
    x, y = 18 + math.cos(a) * r - r, math.sin(a) * r
    caja(f"Espigon{i}", (x, y, 0.7), (3.4, 3.0, 2.6), m_piedra, rot=(0, 0, a))
    if i % 3 == 1:
        caja(f"EspigonRemate{i}", (x, y, 2.25), (2.2, 2.0, 0.5), m_piedra, rot=(0, 0, a))

# ---------------- faro en la punta del espigón ----------------
fx, fy = 18 + math.cos(math.radians(-30)) * 26 - 26, math.sin(math.radians(-30)) * 26
cono("FaroTorre", (fx, fy, 5.4), 2.0, 1.35, 8.4, m_faro)
cono("FaroBase", (fx, fy, 1.2), 2.8, 2.45, 1.6, m_piedra, caras=20)
bpy.ops.mesh.primitive_torus_add(location=(fx, fy, 9.65), major_radius=1.55, minor_radius=0.12,
                                 major_segments=20, minor_segments=6)
gal = bpy.context.active_object; gal.name = "FaroGaleria"; gal.data.materials.append(m_oscuro)
caja("FaroLinterna", (fx, fy, 10.3), (1.7, 1.7, 1.2), m_faroluz)
cono("FaroTejado", (fx, fy, 11.4), 1.35, 0.06, 1.1, m_oscuro, caras=12)

# ---------------- muelle de madera con 6 amarres-farol ----------------
caja("MuelleTablero", (-6, -10, 1.18), (26, 5.2, 0.36), m_madera)
for i in range(9):
    x = -18 + i * 3.1
    for lado in (-1, 1):
        cono(f"MuellePoste{i}{'a' if lado < 0 else 'b'}", (x, -10 + lado * 2.3, 0.4),
             0.22, 0.18, 1.7, m_madera, caras=10)
for i in range(6):
    x = -17 + i * 4.6
    cono(f"FarolPoste{i}", (x, -12.2, 2.2), 0.10, 0.08, 2.1, m_oscuro, caras=8)
    caja(f"FarolCabeza{i}", (x, -12.2, 3.45), (0.42, 0.42, 0.52), m_farol)
    cono(f"FarolTapa{i}", (x, -12.2, 3.85), 0.34, 0.04, 0.3, m_oscuro, caras=8)
    caja(f"Bolardo{i}", (x, -8.4, 1.55), (0.3, 0.3, 0.55), m_oscuro)

# ---------------- ladera y pueblo (ventanas emisivas individuales) ----------------
bpy.ops.mesh.primitive_uv_sphere_add(location=(6, 16, -2.2), segments=28, ring_count=14)
lad = bpy.context.active_object
lad.name = "Ladera"
lad.scale = (34, 22, 6.5)
lad.data.materials.append(m_tierra)
for p in lad.data.polygons:
    p.use_smooth = True

nven = 0
for i in range(11):
    cx = -16 + i * 3.4 + random.uniform(-0.8, 0.8)
    cy = 8 + (i % 4) * 3.2 + random.uniform(-0.9, 0.9)
    cz = 1.1 + (cy - 6) * 0.27
    an, fo, al = random.uniform(2.2, 3.2), random.uniform(2.0, 2.6), random.uniform(2.0, 2.9)
    caja(f"Casa{i}", (cx, cy, cz + al / 2), (an, fo, al), m_casa)
    cono(f"CasaTejado{i}", (cx, cy, cz + al + 0.55), an * 0.78, 0.05, 1.1, m_oscuro, caras=4,
         rot=(0, 0, math.radians(45)))
    for k in range(random.choice((1, 2))):
        wx = cx + (k - 0.5) * an * 0.42
        caja(f"Ventana{nven}", (wx, cy - fo / 2 - 0.03, cz + al * 0.55), (0.5, 0.1, 0.65), m_ventana)
        nven += 1
print(f"VENTANAS:{nven}")

total = 0
for o in bpy.context.scene.objects:
    if o.type == "MESH":
        o.data.calc_loop_triangles()
        total += len(o.data.loop_triangles)
print(f"TRIS_PUERTO:{total}")

# ---------------- renders del look (con agua y nao solo para el render) ----------------
bpy.ops.mesh.primitive_plane_add(location=(0, -16, 0), size=90)
agua = bpy.context.active_object
agua.name = "AguaRender"
ma = mat("AguaMat", color=(0.085, 0.14, 0.30), rug=0.08)
agua.data.materials.append(ma)
# el ship-ia.glb del repo va comprimido con meshopt (Blender no lo importa):
# usar el crudo de /tmp si sigue ahí; si no, render sin nao
if os.path.exists("/tmp/nao-ia.glb"):
    bpy.ops.import_scene.gltf(filepath="/tmp/nao-ia.glb")
    for o in bpy.context.selected_objects:
        o.scale = (11, 11, 11)
        o.location = (-2, -17.5, 1.75)
        o.rotation_euler = (o.rotation_euler[0], o.rotation_euler[1], math.radians(38))

s = bpy.context.scene
s.render.engine = "CYCLES"
s.cycles.samples = 48
s.cycles.use_denoising = False
s.render.resolution_x = 1200
s.render.resolution_y = 750
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
s.collection.objects.link(cam)
s.camera = cam
import mathutils
cam.location = (-30, -34, 9)
d = mathutils.Vector((24, 28, -7))
cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

# E5 · atardecer
sol = bpy.data.objects.new("Sol", bpy.data.lights.new("Sol", "SUN"))
sol.data.energy = 3.2
sol.data.color = (1.0, 0.72, 0.45)
sol.rotation_euler = (math.radians(78), 0, math.radians(35))
s.collection.objects.link(sol)
w = bpy.data.worlds.new("W")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.38, 0.28, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.55
s.world = w
s.render.filepath = DIR + "/puerto_atardecer.png"
bpy.ops.render.render(write_still=True)

# E6 · noche (sol fuera, mundo azul noche, emisivos cantando)
sol.data.energy = 0.25
sol.data.color = (0.5, 0.62, 0.95)
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.045, 0.07, 0.16, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
s.render.filepath = DIR + "/puerto_noche.png"
bpy.ops.render.render(write_still=True)
print("RENDERS_OK")

# ---------------- export limpio (sin agua, sin nao, sin cámara/luces) ----------------
bpy.ops.object.select_all(action="DESELECT")
for o in bpy.context.scene.objects:
    if o.type == "MESH" and o.name != "AguaRender" and not o.name.startswith("tripo"):
        o.select_set(True)
bpy.ops.export_scene.gltf(
    filepath=DIR + "/puerto.glb", export_format="GLB", use_selection=True,
    export_animations=False, export_cameras=False, export_yup=True)
print("PUERTO_OK")
