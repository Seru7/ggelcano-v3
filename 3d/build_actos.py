# Actos II y IV del guion v2 — renders de look para aprobación.
# ACTO II · LA FLOTA: tres naos IA en formación sobre mar abierto al alba,
#   matte de atardecer dorado de fondo, niebla por pase Mist en compositor.
# ACTO IV · LA TORMENTA: mar grueso oscuro, matte de tormenta pintado de
#   fondo, la nao escorada cruzando firme, haz dorado lejano (la lluvia
#   fina será partículas en la web, el matte ya trae sus cortinas).
import bpy
import math
import os

import mathutils

DIR = os.path.dirname(os.path.abspath(__file__))
CC0 = DIR + "/cc0"


def escena_limpia():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mar(strength, color, rough):
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=220, y_subdivisions=220, size=320)
    o = bpy.context.active_object
    o.name = "Mar"
    tex = bpy.data.textures.new("olas", "CLOUDS")
    tex.noise_scale = 7.0
    mod = o.modifiers.new("Olas", "DISPLACE")
    mod.texture = tex
    mod.strength = strength
    bpy.ops.object.modifier_apply(modifier="Olas")
    for p in o.data.polygons:
        p.use_smooth = True
    m = bpy.data.materials.new("Agua")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    nt = m.node_tree
    ruido = nt.nodes.new("ShaderNodeTexNoise")
    ruido.inputs["Scale"].default_value = 110
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    nt.links.new(ruido.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    o.data.materials.append(m)
    return o




def aplana(mar_obj, cx, cy, rx=10.0, ry=4.5):
    """Calma el agua bajo el casco (huella elíptica) y devuelve el nivel local:
    el barco se asienta SOBRE su agua, no atravesado por las crestas."""
    me = mar_obj.data
    zs = []
    for v in me.vertices:
        dx = (v.co.x - cx) / rx
        dy = (v.co.y - cy) / ry
        if dx * dx + dy * dy < 4.0:
            zs.append(v.co.z)
    nivel = sum(zs) / max(1, len(zs))
    for v in me.vertices:
        dx = (v.co.x - cx) / rx
        dy = (v.co.y - cy) / ry
        d = (dx * dx + dy * dy) ** 0.5
        if d < 2.2:
            t = max(0.0, 1.0 - max(0.0, d - 1.0) / 1.2)
            v.co.z = v.co.z * (1 - t) + nivel * t
    return nivel

def nao(nombre, pos, rotz, escora=0, escala=11):
    antes = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath="/tmp/nao-ia.glb")
    nuevos = [o for o in bpy.context.scene.objects if o not in antes]
    e = bpy.data.objects.new(nombre, None)
    bpy.context.scene.collection.objects.link(e)
    for o in nuevos:
        if o.parent is None:
            o.parent = e
    e.scale = (escala, escala, escala)
    e.rotation_euler = (math.radians(escora), 0, math.radians(rotz))
    e.location = pos
    return e


def mundo(matte_jpg, hdri_strength, sol_color, sol_energy, sol_rot):
    s = bpy.context.scene
    w = bpy.data.worlds.new("W")
    w.use_nodes = True
    nt = w.node_tree
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(CC0 + "/sunset_puresky_2k.hdr")
    fondo = nt.nodes["Background"]
    nt.links.new(env.outputs["Color"], fondo.inputs["Color"])
    fondo.inputs["Strength"].default_value = hdri_strength
    coords = nt.nodes.new("ShaderNodeTexCoord")
    matte = nt.nodes.new("ShaderNodeTexImage")
    matte.image = bpy.data.images.load(CC0 + "/" + matte_jpg)
    nt.links.new(coords.outputs["Window"], matte.inputs["Vector"])
    fondoM = nt.nodes.new("ShaderNodeBackground")
    nt.links.new(matte.outputs["Color"], fondoM.inputs["Color"])
    lp = nt.nodes.new("ShaderNodeLightPath")
    mixw = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mixw.inputs["Fac"])
    nt.links.new(fondo.outputs["Background"], mixw.inputs[1])
    nt.links.new(fondoM.outputs["Background"], mixw.inputs[2])
    nt.links.new(mixw.outputs["Shader"], nt.nodes["World Output"].inputs["Surface"])
    s.world = w
    sol = bpy.data.objects.new("Sol", bpy.data.lights.new("Sol", "SUN"))
    sol.data.energy = sol_energy
    sol.data.color = sol_color
    sol.rotation_euler = sol_rot
    s.collection.objects.link(sol)
    return w


def render(nombre, cam_loc, cam_dir, lens=33, mist=(18, 90), mist_color=(0.93, 0.88, 0.78, 1)):
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.samples = 64
    s.cycles.use_denoising = False
    s.render.resolution_x = 1280
    s.render.resolution_y = 800
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    s.collection.objects.link(cam)
    s.camera = cam
    cam.location = cam_loc
    cam.rotation_euler = mathutils.Vector(cam_dir).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    # (la atmósfera la traen los mattes pintados; el compositor de Blender 5
    #  cambió de API y no compensa para un render de look)
    s.render.filepath = DIR + "/" + nombre
    bpy.ops.render.render(write_still=True)


# ================= ACTO II · LA FLOTA =================
escena_limpia()
m2 = mar(1.1, (0.06, 0.10, 0.22), 0.18)
for nombre, (px, py), rz, esc in (("NaoLider", (0, 10), 196, 0),
                                  ("NaoAla1", (-19, 30), 203, 2),
                                  ("NaoAla2", (16, 36), 190, -2)):
    nivel = aplana(m2, px, py)
    nao(nombre, (px, py, nivel + 2.5), rz, escora=esc)
mundo("matte_atardecer.jpg", 1.0, (1.0, 0.66, 0.34), 3.2,
      (math.radians(75), 0, math.radians(-150)))
render("acto2_flota.png", (3, -24, 4.2), (-1, 30, 1.0), lens=31, mist=(25, 110))
print("ACTO2_OK")

# ================= ACTO IV · LA TORMENTA =================
escena_limpia()
m4 = mar(2.6, (0.025, 0.04, 0.07), 0.32)
nivel4 = aplana(m4, -2, 14, rx=12.0, ry=5.5)
nao("NaoTormenta", (-2, 14, nivel4 + 2.35), 188, escora=6)
mundo("matte_tormenta.jpg", 0.22, (0.6, 0.68, 0.9), 1.1,
      (math.radians(70), 0, math.radians(-120)))
# el haz dorado del matte toca el agua tras la nao
foco = bpy.data.objects.new("Haz", bpy.data.lights.new("Haz", "SPOT"))
foco.data.energy = 220000
foco.data.color = (1.0, 0.75, 0.4)
foco.data.spot_size = math.radians(24)
foco.data.spot_blend = 0.7
foco.location = (26, 70, 46)
foco.rotation_euler = mathutils.Vector((-18, -50, -46)).to_track_quat("-Z", "Y").to_euler()
bpy.context.scene.collection.objects.link(foco)
render("acto4_tormenta.png", (4, -22, 4.6), (-1, 30, 1.4), lens=31,
       mist=(30, 140), mist_color=(0.32, 0.36, 0.45, 1))
print("ACTO4_OK")
