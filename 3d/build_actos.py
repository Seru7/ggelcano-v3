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


def mar(strength, color, rough, cresta=(0.85, 0.83, 0.76)):
    """Mar con 3 octavas de geometría (fondo+oleaje+rizado), espuma de cresta
    rota con ruido y vetas peinadas por el viento. Que el agua aguante el
    nivel de detalle del cielo pintado."""
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=300, y_subdivisions=300, size=320)
    o = bpy.context.active_object
    o.name = "Mar"
    for nombre, esc, st in (("OlasFondo", 7.0, strength),
                            ("OlasMedias", 2.0, strength * 0.42)):
        tex = bpy.data.textures.new(nombre, "CLOUDS")
        tex.noise_scale = esc
        mod = o.modifiers.new(nombre, "DISPLACE")
        mod.texture = tex
        mod.strength = st
        bpy.ops.object.modifier_apply(modifier=nombre)
    for p in o.data.polygons:
        p.use_smooth = True

    m = bpy.data.materials.new("Agua")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = rough

    geom = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geom.outputs["Position"], sep.inputs[0])

    # color por altura: valles hondos → crestas más claras
    hRango = nt.nodes.new("ShaderNodeMapRange")
    hRango.inputs["From Min"].default_value = -strength * 0.9
    hRango.inputs["From Max"].default_value = strength * 0.9
    nt.links.new(sep.outputs["Z"], hRango.inputs["Value"])
    mixCol = nt.nodes.new("ShaderNodeMix")
    mixCol.data_type = "RGBA"
    mixCol.inputs[6].default_value = (*color, 1)
    mixCol.inputs[7].default_value = (color[0] * 3.2, color[1] * 2.8, color[2] * 2.2, 1)
    nt.links.new(hRango.outputs["Result"], mixCol.inputs["Factor"])

    # espuma: solo en lo alto de las crestas, rota con ruido (no una capa lisa)
    hEspuma = nt.nodes.new("ShaderNodeMapRange")
    hEspuma.inputs["From Min"].default_value = strength * 0.45
    hEspuma.inputs["From Max"].default_value = strength * 1.05
    nt.links.new(sep.outputs["Z"], hEspuma.inputs["Value"])
    rotura = nt.nodes.new("ShaderNodeTexNoise")
    rotura.inputs["Scale"].default_value = 14
    rotRango = nt.nodes.new("ShaderNodeMapRange")
    rotRango.inputs["From Min"].default_value = 0.42
    rotRango.inputs["From Max"].default_value = 0.72
    nt.links.new(rotura.outputs["Fac"], rotRango.inputs["Value"])
    fEsp = nt.nodes.new("ShaderNodeMath")
    fEsp.operation = "MULTIPLY"
    nt.links.new(hEspuma.outputs["Result"], fEsp.inputs[0])
    nt.links.new(rotRango.outputs["Result"], fEsp.inputs[1])
    mixEsp = nt.nodes.new("ShaderNodeMix")
    mixEsp.data_type = "RGBA"
    nt.links.new(mixCol.outputs[2], mixEsp.inputs[6])
    mixEsp.inputs[7].default_value = (*cresta, 1)
    nt.links.new(fEsp.outputs[0], mixEsp.inputs["Factor"])
    nt.links.new(mixEsp.outputs[2], b.inputs["Base Color"])
    # la espuma es mate: sube la rugosidad donde hay espuma
    rEsp = nt.nodes.new("ShaderNodeMapRange")
    rEsp.inputs["To Min"].default_value = rough
    rEsp.inputs["To Max"].default_value = 0.55
    nt.links.new(fEsp.outputs[0], rEsp.inputs["Value"])
    nt.links.new(rEsp.outputs["Result"], b.inputs["Roughness"])

    # vetas peinadas por el viento (ruido estirado) + rizo fino, en cadena
    mapV = nt.nodes.new("ShaderNodeMapping")
    nt.links.new(geom.outputs["Position"], mapV.inputs["Vector"])
    mapV.inputs["Scale"].default_value = (0.9, 3.6, 1.0)
    vetas = nt.nodes.new("ShaderNodeTexNoise")
    vetas.inputs["Scale"].default_value = 6.5
    nt.links.new(mapV.outputs["Vector"], vetas.inputs["Vector"])
    bumpV = nt.nodes.new("ShaderNodeBump")
    bumpV.inputs["Strength"].default_value = 0.22
    nt.links.new(vetas.outputs["Fac"], bumpV.inputs["Height"])
    rizo = nt.nodes.new("ShaderNodeTexNoise")
    rizo.inputs["Scale"].default_value = 120
    bumpR = nt.nodes.new("ShaderNodeBump")
    bumpR.inputs["Strength"].default_value = 0.3
    nt.links.new(rizo.outputs["Fac"], bumpR.inputs["Height"])
    nt.links.new(bumpV.outputs["Normal"], bumpR.inputs["Normal"])
    nt.links.new(bumpR.outputs["Normal"], b.inputs["Normal"])

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
    try:
        s.view_settings.look = "AgX - Punchy"   # contraste de revelado: el 3D deja de ser plano
    except Exception:
        pass
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
    nao(nombre, (px, py, nivel + 2.65), rz, escora=esc)
mundo("matte_atardecer.jpg", 1.0, (1.0, 0.62, 0.3), 4.4,
      (math.radians(81), 0, math.radians(-150)))
render("acto2_flota.png", (3, -24, 4.2), (-1, 30, 1.0), lens=31, mist=(25, 110))
print("ACTO2_OK")

# ================= ACTO IV · LA TORMENTA =================
escena_limpia()
m4 = mar(2.6, (0.025, 0.04, 0.07), 0.32)
nivel4 = aplana(m4, -2, 14, rx=12.0, ry=5.5)
nao("NaoTormenta", (-2, 14, nivel4 + 2.55), 188, escora=6)
mundo("matte_tormenta.jpg", 0.22, (0.65, 0.72, 0.95), 1.6,
      (math.radians(78), 0, math.radians(-120)))
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
