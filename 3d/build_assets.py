# Assets 3D del prototipo ggelcano.com — basado en cam_path_template.py de la skill blender-web3d
# Tres pasadas: nao Victoria estilizada (ship.glb), cámara hero (cam-hero.glb), cámara globo (cam-globe.glb)
import bpy
import bmesh
import math

OUT = "/home/sergio/Documents/webs-premium/prototipo-ggelcano-3d/3d/"


def escena_limpia(fps=30, fin=90):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.fps = fps
    s.frame_start = 1
    s.frame_end = fin
    return s


def material(nombre, rgba):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = rgba
    return m


def vincula(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


# ---------- PASADA A: la nao ----------
def construye_nao():
    escena_limpia()
    mat_casco = material("Casco", (0.045, 0.075, 0.18, 1))
    mat_madera = material("Madera", (0.30, 0.21, 0.10, 1))
    mat_vela = material("Vela", (0.92, 0.89, 0.80, 1))

    # Casco por secciones transversales unidas (proa en +X, popa en -X, flotación en z=0)
    # (x, semianchura, fondo bajo el agua, altura de borda)
    secciones = [
        (-4.6, 0.55, 0.45, 1.55),  # espejo de popa (alto: castillo)
        (-3.0, 1.05, 0.80, 1.15),
        (-0.8, 1.25, 0.95, 0.95),
        (1.6, 1.10, 0.85, 1.00),
        (3.6, 0.65, 0.55, 1.25),   # amura
        (4.9, 0.06, 0.10, 1.45),   # roda (proa casi en punta, levantada)
    ]
    bm = bmesh.new()
    anillos = []
    for x, w, fondo, borda in secciones:
        anillo = [
            bm.verts.new((x, -w, borda)),
            bm.verts.new((x, -w * 0.92, -fondo * 0.55)),
            bm.verts.new((x, 0.0, -fondo)),
            bm.verts.new((x, w * 0.92, -fondo * 0.55)),
            bm.verts.new((x, w, borda)),
        ]
        anillos.append(anillo)
    for a, b in zip(anillos, anillos[1:]):
        for i in range(4):
            bm.faces.new((a[i], a[i + 1], b[i + 1], b[i]))
    bm.faces.new(reversed(anillos[0]))   # tapa de popa
    bm.faces.new(anillos[-1])            # tapa de proa
    # Cubierta
    for a, b in zip(anillos, anillos[1:]):
        bm.faces.new((a[4], a[0], b[0], b[4]))
    me = bpy.data.meshes.new("Casco")
    bm.to_mesh(me)
    bm.free()
    casco = vincula(bpy.data.objects.new("Casco", me))
    casco.data.materials.append(mat_casco)

    # Castillo de popa (alcázar) y castillo de proa
    def caja(nombre, loc, dim, mat):
        bpy.ops.mesh.primitive_cube_add(location=loc)
        o = bpy.context.active_object
        o.name = nombre
        o.dimensions = dim
        o.data.materials.append(mat)
        return o

    caja("Alcazar", (-3.6, 0, 1.55), (2.0, 1.7, 0.85), mat_casco)
    caja("CastilloProa", (3.4, 0, 1.45), (1.3, 1.0, 0.55), mat_casco)

    # Mástiles: trinquete (proa), mayor, mesana (popa) + bauprés
    def cilindro(nombre, loc, alto, radio, mat, rot=(0, 0, 0)):
        bpy.ops.mesh.primitive_cylinder_add(location=loc, rotation=rot, vertices=8)
        o = bpy.context.active_object
        o.name = nombre
        o.scale = (radio, radio, alto / 2)
        o.data.materials.append(mat)
        return o

    cilindro("MastilMayor", (0.2, 0, 4.2), 7.6, 0.09, mat_madera)
    cilindro("MastilTrinquete", (2.9, 0, 3.6), 5.4, 0.07, mat_madera)
    cilindro("MastilMesana", (-3.4, 0, 3.5), 4.2, 0.06, mat_madera)
    cilindro("Baupres", (5.4, 0, 1.9), 2.6, 0.05, mat_madera, rot=(0, math.radians(58), 0))
    # Vergas (palos horizontales de las velas cuadradas)
    cilindro("VergaMayor", (0.2, 0, 6.6), 3.6, 0.045, mat_madera, rot=(math.radians(90), 0, 0))
    cilindro("VergaTrinquete", (2.9, 0, 5.3), 2.8, 0.04, mat_madera, rot=(math.radians(90), 0, 0))

    # Velas cuadradas: rejilla curvada hacia proa (viento de popa)
    def vela(nombre, cx, cz, ancho, alto):
        bm = bmesh.new()
        filas, cols = 5, 7
        verts = []
        for i in range(filas):
            fila = []
            for j in range(cols):
                y = (j / (cols - 1) - 0.5) * ancho
                z = cz - (i / (filas - 1)) * alto
                # vientre de la vela: máximo en el centro
                v_y = 1 - abs(j / (cols - 1) - 0.5) * 2
                v_z = 1 - abs(i / (filas - 1) - 0.5) * 2
                x = cx + 0.55 * v_y * v_z + 0.18 * v_z
                fila.append(bm.verts.new((x, y, z)))
            verts.append(fila)
        for i in range(filas - 1):
            for j in range(cols - 1):
                bm.faces.new((verts[i][j], verts[i][j + 1], verts[i + 1][j + 1], verts[i + 1][j]))
        me = bpy.data.meshes.new(nombre)
        bm.to_mesh(me)
        bm.free()
        o = vincula(bpy.data.objects.new(nombre, me))
        o.data.materials.append(mat_vela)
        return o

    vela("VelaMayor", 0.25, 6.5, 3.4, 3.4)
    vela("VelaTrinquete", 2.95, 5.2, 2.6, 2.5)

    # Vela latina de mesana (triángulo)
    bm = bmesh.new()
    v1 = bm.verts.new((-2.2, 0, 5.4))
    v2 = bm.verts.new((-4.9, 0, 4.6))
    v3 = bm.verts.new((-4.6, 0, 2.2))
    bm.faces.new((v1, v2, v3))
    me = bpy.data.meshes.new("VelaMesana")
    bm.to_mesh(me)
    bm.free()
    vincula(bpy.data.objects.new("VelaMesana", me)).data.materials.append(mat_vela)

    # Grímpola dorada en el palo mayor
    bm = bmesh.new()
    v1 = bm.verts.new((0.2, 0, 8.05))
    v2 = bm.verts.new((0.2, 0, 7.75))
    v3 = bm.verts.new((-0.9, 0, 7.9))
    bm.faces.new((v1, v2, v3))
    me = bpy.data.meshes.new("Grimpola")
    bm.to_mesh(me)
    bm.free()
    vincula(bpy.data.objects.new("Grimpola", me)).data.materials.append(
        material("Oro", (0.69, 0.55, 0.34, 1))
    )

    bpy.ops.export_scene.gltf(
        filepath=OUT + "ship.glb",
        export_format="GLB",
        export_animations=False,
        export_cameras=False,
        export_yup=True,
    )
    print("SHIP_OK")


# ---------- Cámaras (patrón del template: TRACK_TO + bake + export) ----------
def construye_camara(nombre_glb, fin, lente, waypoints, targets):
    """waypoints/targets: lista de (frame, (x,y,z)). Exporta SOLO cámara+target."""
    escena_limpia(fin=fin)
    bpy.ops.object.empty_add(location=targets[0][1])
    target = bpy.context.active_object
    target.name = "CamTarget"

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = lente
    cam = vincula(bpy.data.objects.new("Camera", cam_data))
    bpy.context.scene.camera = cam

    track = cam.constraints.new(type="TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"

    for f, loc in waypoints:
        cam.location = loc
        cam.keyframe_insert(data_path="location", frame=f)
    for f, loc in targets:
        target.location = loc
        target.keyframe_insert(data_path="location", frame=f)

    # Hornear el TRACK_TO (los GLB no exportan constraints)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = cam
    cam.select_set(True)
    bpy.ops.nla.bake(
        frame_start=1, frame_end=fin, step=1,
        only_selected=True, visual_keying=True, clear_constraints=True,
        bake_types={"OBJECT"},
    )
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=OUT + nombre_glb,
        export_format="GLB",
        export_animations=True,
        export_cameras=True,
        export_yup=True,
    )
    print("CAM_OK", nombre_glb)


# Hero: 3 s (pin de ~250%). Arco desde lejos a ras de agua hasta 3/4 elevado junto a proa.
def camara_hero():
    wp = []
    for f in range(1, 91, 6):
        t = (f - 1) / 89.0
        ang = math.radians(205 - t * 160)       # de popa-babor (niebla) a 3/4 de proa (cruz)
        radio = 32 - 15.5 * (1 - (1 - t) ** 2)  # 32 → 16.5: la nao entera con aire
        z = 0.7 + 4.3 * t * t                   # pegado al agua → elevado
        wp.append((f, (math.cos(ang) * radio, math.sin(ang) * radio, z)))
    tg = [(1, (0, 0, 1.4)), (90, (0.3, 0, 3.3))]
    construye_camara("cam-hero.glb", 90, 32, wp, tg)


# Globo: 4 s. Órbita que sigue la ruta (oeste) descendiendo y alejándose al final.
def camara_globo():
    wp = []
    for f in range(1, 121, 6):
        t = (f - 1) / 119.0
        ang = math.radians(20 - t * 280)        # hacia el oeste, casi vuelta entera
        radio = 4.0 + 0.8 * t
        z = 1.8 - 1.4 * math.sin(t * math.pi)   # baja al ecuador y remonta
        wp.append((f, (math.cos(ang) * radio, math.sin(ang) * radio, z)))
    tg = [(1, (0, 0, 0.15)), (120, (0, 0, 0))]
    construye_camara("cam-globe.glb", 120, 30, wp, tg)


if __name__ == "__main__":
    # la nao ahora la genera build_nao_victoria.py (versión elaborada); aquí solo cámaras
    camara_hero()
    camara_globo()
    print("TODO_OK")
