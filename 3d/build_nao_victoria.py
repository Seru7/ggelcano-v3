# Nao Victoria elaborada — carraca de 1519 en estilo cartoon (colores planos cálidos).
# Convención: proa en +X, popa en -X, flotación en z=0, eslora ~10 m. Misma escala que
# la versión anterior para reutilizar cam-hero.glb.
import bpy
import bmesh
import math

OUT = "/home/sergio/Documents/webs-premium/prototipo-ggelcano-3d/3d/"

# ---------------- utilidades ----------------
MATS = {}

def mat(nombre, hexcol):
    if nombre in MATS:
        return MATS[nombre]
    r = ((hexcol >> 16) & 255) / 255
    g = ((hexcol >> 8) & 255) / 255
    b = (hexcol & 255) / 255
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (r, g, b, 1)
    m.diffuse_color = (r, g, b, 1)  # color de viewport: lo usa el render Workbench
    m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
    MATS[nombre] = m
    return m


def obj_de_bmesh(nombre, bm, material, suave=False):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(nombre)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(nombre, me)
    o.data.materials.append(material)
    if suave:
        for p in me.polygons:
            p.use_smooth = True
    bpy.context.scene.collection.objects.link(o)
    return o


def caja(nombre, centro, dim, material, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=centro, rotation=rot)
    o = bpy.context.active_object
    o.name = nombre
    o.dimensions = dim
    o.data.materials.append(material)
    return o


def cilindro(nombre, centro, alto, radio, material, rot=(0, 0, 0), caras=16):
    bpy.ops.mesh.primitive_cylinder_add(location=centro, rotation=rot, vertices=caras)
    o = bpy.context.active_object
    o.name = nombre
    o.scale = (radio, radio, alto / 2)
    o.data.materials.append(material)
    return o


def vara(nombre, p1, p2, radio, material):
    """Cilindro entre dos puntos (jarcia, estays, obenques)."""
    d = [b - a for a, b in zip(p1, p2)]
    L = math.sqrt(sum(c * c for c in d))
    centro = [(a + b) / 2 for a, b in zip(p1, p2)]
    o = cilindro(nombre, centro, L, radio, material, caras=10)
    # orientar el eje Z del cilindro hacia p2-p1
    theta = math.acos(max(-1, min(1, d[2] / L)))
    phi = math.atan2(d[1], d[0])
    o.rotation_euler = (0, theta, phi)
    o.rotation_mode = "ZYX"
    return o

# ---------------- casco por cuadernas ----------------
def perfil_casco():
    """Estaciones a lo largo de la eslora. Por estación:
    (x, semimanga, calado, z_cubierta, z_borda). Sheer marcada: sube en popa y proa.
    Densificado ×2: se intercala el punto medio de cada par de estaciones base."""
    base = [
        (-4.9, 0.30, 0.30, 1.30, 2.05),   # espejo de popa (alto)
        (-4.4, 0.85, 0.60, 1.15, 1.90),
        (-3.6, 1.15, 0.85, 0.95, 1.55),
        (-2.4, 1.32, 1.00, 0.80, 1.30),
        (-1.0, 1.40, 1.08, 0.75, 1.20),   # cuaderna maestra
        (0.4, 1.38, 1.05, 0.75, 1.20),
        (1.8, 1.24, 0.92, 0.80, 1.30),
        (3.0, 1.00, 0.72, 0.90, 1.50),
        (4.0, 0.66, 0.48, 1.05, 1.75),
        (4.7, 0.30, 0.24, 1.20, 1.95),    # amura alta
        (5.15, 0.04, 0.06, 1.30, 2.10),   # roda
    ]
    denso = []
    for a, b in zip(base, base[1:]):
        denso.append(a)
        denso.append(tuple((p + q) / 2 for p, q in zip(a, b)))
    denso.append(base[-1])
    return denso


RING_N = 17  # puntos por cuaderna (antes 9)


def construye_casco():
    bm = bmesh.new()
    anillos = []
    for x, w, calado, zdeck, zborda in perfil_casco():
        ring = []
        # media sección redondeada de borda a borda pasando por la quilla
        for i in range(RING_N):
            t = i / (RING_N - 1)             # 0 = borda babor, 1 = borda estribor
            a = t * math.pi                  # ángulo sobre la "U"
            y = -math.cos(a) * w
            # panza redonda: z baja hasta -calado en el centro, con tumblehome arriba
            z = zborda - (zborda + calado) * math.sin(a) ** 0.8
            ring.append(bm.verts.new((x, y, z)))
        anillos.append(ring)
    for r1, r2 in zip(anillos, anillos[1:]):
        for i in range(RING_N - 1):
            bm.faces.new((r1[i], r1[i + 1], r2[i + 1], r2[i]))
    bm.faces.new(reversed(anillos[0]))
    bm.faces.new(anillos[-1])
    casco = obj_de_bmesh("Casco", bm, mat("CascoAlto", 0x7a5435), suave=True)

    # cinta de cubierta (tapa el hueco superior, de borda a borda)
    bm = bmesh.new()
    filas = []
    for x, w, calado, zdeck, zborda in perfil_casco():
        filas.append((bm.verts.new((x, -w * 0.94, zdeck)), bm.verts.new((x, w * 0.94, zdeck))))
    for f1, f2 in zip(filas, filas[1:]):
        bm.faces.new((f1[0], f1[1], f2[1], f2[0]))
    obj_de_bmesh("Cubierta", bm, mat("Cubierta", 0xa9854f))

    # amuradas: cinta vertical de la cubierta a la borda, a cada banda
    for lado in (-1, 1):
        bm = bmesh.new()
        abajo, arriba = [], []
        for x, w, calado, zdeck, zborda in perfil_casco():
            y = lado * w * 0.97
            abajo.append(bm.verts.new((x, y, zdeck)))
            arriba.append(bm.verts.new((x, y, zborda)))
        for i in range(len(abajo) - 1):
            bm.faces.new((abajo[i], abajo[i + 1], arriba[i + 1], arriba[i]))
        obj_de_bmesh(f"Amurada{'B' if lado < 0 else 'E'}", bm, mat("CascoAlto", 0x7a5435))

    # cintones dorados (2 bandas siguiendo la curva del casco)
    for nombre, frac in (("CintonAlto", 0.78), ("CintonBajo", 0.45)):
        bm = bmesh.new()
        a1, a2 = [], []
        for x, w, calado, zdeck, zborda in perfil_casco():
            z = -calado + (zborda + calado) * frac
            y = w * 1.015 * math.sin(math.acos(max(-1, min(1, (zborda - z) / (zborda + calado)))))
            for lado, lista in ((-1, a1), (1, a2)):
                lista.append((x, lado * max(y, 0.05), z))
        for lado, lista in ((0, a1), (1, a2)):
            bml = bmesh.new()
            v_inf = [bml.verts.new((x, y, z - 0.05)) for x, y, z in lista]
            v_sup = [bml.verts.new((x, y, z + 0.05)) for x, y, z in lista]
            for i in range(len(v_inf) - 1):
                bml.faces.new((v_inf[i], v_inf[i + 1], v_sup[i + 1], v_sup[i]))
            obj_de_bmesh(f"{nombre}{lado}", bml, mat("Oro", 0xc9b07e))
        bm.free()

    # quilla + roda + codaste (empotrada en el casco, sin huecos)
    caja("Quilla", (0.1, 0, -0.85), (8.6, 0.16, 0.55), mat("CascoBajo", 0x3e2c1c))
    vara("Roda", (4.9, 0, -0.9), (5.5, 0, 1.6), 0.09, mat("CascoBajo", 0x3e2c1c))
    vara("Codaste", (-4.85, 0, -1.0), (-4.85, 0, 0.6), 0.09, mat("CascoBajo", 0x3e2c1c))
    # timón
    caja("Timon", (-5.05, 0, -0.25), (0.32, 0.10, 1.5), mat("CascoBajo", 0x3e2c1c))
    return casco

# ---------------- castillos ----------------
def construye_castillos():
    oscuro = mat("CascoAlto", 0x7a5435)
    claro = mat("Cubierta", 0xa9854f)
    oro = mat("Oro", 0xc9b07e)

    # alcázar (media popa) y toldilla (nivel superior, más corta)
    caja("Alcazar", (-3.3, 0, 1.78), (2.6, 2.25, 0.95), oscuro)
    caja("AlcazarCubierta", (-3.3, 0, 2.28), (2.7, 2.35, 0.08), claro)
    caja("Toldilla", (-4.15, 0, 2.72), (1.5, 1.95, 0.85), oscuro)
    caja("ToldillaCubierta", (-4.15, 0, 3.17), (1.6, 2.05, 0.08), claro)

    # ventanas doradas del espejo de popa (2 niveles)
    for i, y in enumerate((-0.62, 0, 0.62)):
        caja(f"VentanaPopa{i}", (-4.93, y, 1.85), (0.06, 0.34, 0.4), oro)
    for i, y in enumerate((-0.4, 0.4)):
        caja(f"VentanaToldilla{i}", (-4.93, y, 2.8), (0.06, 0.3, 0.34), oro)

    # castillo de proa con plataforma volada
    caja("CastilloProa", (3.55, 0, 1.95), (1.7, 1.8, 0.75), oscuro)
    caja("CastilloProaCubierta", (3.55, 0, 2.36), (1.9, 2.0, 0.08), claro)

    # barandillas con balaustres (popa y proa)
    def barandilla(prefijo, x0, x1, y, z):
        vara(f"{prefijo}Pasamanos", (x0, y, z + 0.3), (x1, y, z + 0.3), 0.035, oro)
        n = max(3, int(abs(x1 - x0) / 0.28))
        for i in range(n + 1):
            x = x0 + (x1 - x0) * i / n
            vara(f"{prefijo}Bal{i}", (x, y, z), (x, y, z + 0.3), 0.022, oscuro)

    for lado in (-1, 1):
        barandilla(f"BarAlcazar{lado}", -4.55, -2.1, lado * 1.10, 2.32)
        barandilla(f"BarToldilla{lado}", -4.85, -3.45, lado * 0.95, 3.21)
        barandilla(f"BarProa{lado}", 2.7, 4.4, lado * 0.95, 2.40)

    # fanal de popa (farol dorado sobre la toldilla)
    vara("FanalPie", (-4.7, 0, 3.2), (-4.7, 0, 3.6), 0.03, oscuro)
    bpy.ops.mesh.primitive_uv_sphere_add(location=(-4.7, 0, 3.75), segments=12, ring_count=8)
    fanal = bpy.context.active_object
    fanal.name = "Fanal"
    fanal.scale = (0.16, 0.16, 0.2)
    fanal.data.materials.append(mat("Farol", 0xe8c97a))

    # espolón del beakhead bajo el bauprés
    vara("Espolon", (5.0, 0, 1.1), (5.95, 0, 1.6), 0.09, oscuro)
    for lado in (-1, 1):
        vara(f"EspolonRefuerzo{lado}", (4.7, lado * 0.45, 1.85), (5.9, 0, 1.62), 0.035, oro)

    # detalle de cubierta: escotilla con brazola, cabestrante, barriles y bitas
    caja("EscotillaBrazola", (1.3, 0, 0.84), (1.25, 1.0, 0.16), oscuro)
    caja("EscotillaReja", (1.3, 0, 0.93), (1.05, 0.8, 0.05), mat("CascoBajo", 0x3e2c1c))
    cilindro("Cabestrante", (-1.5, 0, 1.02), 0.55, 0.17, oscuro, caras=12)
    cilindro("CabestranteCorona", (-1.5, 0, 1.28), 0.10, 0.23, claro, caras=12)
    for i in range(4):
        a = i / 4 * math.pi
        vara(f"CabestranteBarra{i}",
             (-1.5 - math.cos(a) * 0.42, -math.sin(a) * 0.42, 1.24),
             (-1.5 + math.cos(a) * 0.42, math.sin(a) * 0.42, 1.24), 0.025, claro)
    for i, (bx, by) in enumerate(((2.15, -0.72), (2.15, 0.72), (-0.2, -0.85))):
        cilindro(f"Barril{i}", (bx, by, 0.99), 0.46, 0.20, claro, caras=12)
        for z in (0.85, 1.12):
            bpy.ops.mesh.primitive_torus_add(location=(bx, by, z),
                                             major_radius=0.20, minor_radius=0.018,
                                             major_segments=16, minor_segments=6)
            flej = bpy.context.active_object
            flej.name = f"BarrilAro{i}{int(z * 100)}"
            flej.data.materials.append(mat("CascoBajo", 0x3e2c1c))
    for lado in (-1, 1):
        caja(f"Bita{'B' if lado < 0 else 'E'}", (2.85, lado * 0.55, 1.05), (0.14, 0.14, 0.5), oscuro)

    # cañones asomando por las amuradas (3 por banda)
    bronce = mat("Bronce", 0x6f5a33)
    for lado in (-1, 1):
        for i, cx in enumerate((-2.1, -0.6, 0.9)):
            cilindro(f"Canon{'B' if lado < 0 else 'E'}{i}",
                     (cx, lado * 1.28, 1.02), 0.95, 0.065, bronce,
                     rot=(math.radians(90 - lado * 4), 0, 0), caras=12)

    # ancla estilizada a babor
    ancla = mat("CascoBajo", 0x3e2c1c)
    vara("AnclaCana", (3.9, -1.15, 0.2), (3.9, -1.15, 1.5), 0.05, ancla)
    for lado in (-1, 1):
        vara(f"AnclaBrazo{'B' if lado < 0 else 'E'}",
             (3.9 + lado * 0.02, -1.15, 0.2), (3.9 + lado * 0.36, -1.15, 0.5), 0.045, ancla)
        bpy.ops.mesh.primitive_cone_add(location=(3.9 + lado * 0.40, -1.15, 0.56),
                                        rotation=(0, lado * math.radians(35), 0),
                                        radius1=0.09, depth=0.2, vertices=6)
        una = bpy.context.active_object
        una.name = f"AnclaUna{'B' if lado < 0 else 'E'}"
        una.data.materials.append(ancla)
    vara("AnclaCepo", (3.9, -1.15, 1.35), (3.9, -1.45, 1.35), 0.04, ancla)
    bpy.ops.mesh.primitive_torus_add(location=(3.9, -1.15, 1.55), rotation=(math.pi / 2, 0, 0),
                                     major_radius=0.09, minor_radius=0.03)
    arg = bpy.context.active_object
    arg.name = "AnclaArganeo"
    arg.data.materials.append(mat("Oro", 0xc9b07e))

# ---------------- arboladura ----------------
def construye_arboladura():
    madera = mat("Madera", 0x8a6242)
    oscuro = mat("CascoBajo", 0x3e2c1c)

    # palo mayor con mastelero, cofa y verga
    cilindro("PaloMayor", (0.0, 0, 3.9), 6.4, 0.11, madera)
    cilindro("MasteleroMayor", (0.0, 0, 8.0), 2.6, 0.06, madera)
    cofa("CofaMayor", (0.0, 0, 7.0))
    cilindro("VergaMayor", (0.0, 0, 6.3), 4.6, 0.055, madera, rot=(math.pi / 2, 0, 0))
    cilindro("VergaMayorAlta", (0.0, 0, 8.4), 2.2, 0.04, madera, rot=(math.pi / 2, 0, 0))

    # trinquete con cofa
    cilindro("PaloTrinquete", (3.1, 0, 3.4), 4.6, 0.085, madera)
    cofa("CofaTrinquete", (3.1, 0, 5.3), escala=0.75)
    cilindro("VergaTrinquete", (3.1, 0, 4.9), 3.2, 0.045, madera, rot=(math.pi / 2, 0, 0))

    # mesana inclinada hacia popa con entena latina
    cilindro("PaloMesana", (-3.6, 0, 4.3), 3.6, 0.07, madera, rot=(0, math.radians(-8), 0))
    cilindro("EntenaMesana", (-4.1, 0, 5.2), 4.4, 0.04, madera, rot=(0, math.radians(52), 0))

    # bauprés con verga de cebadera
    cilindro("Baupres", (5.7, 0, 2.5), 3.4, 0.075, madera, rot=(0, math.radians(55), 0))
    cilindro("VergaCebadera", (5.95, 0, 2.62), 1.8, 0.035, madera, rot=(math.pi / 2, 0, 0))

    # jarcia firme: estays y obenques con flechastes sugeridos
    cuerda = 0.018
    vara("EstayMayor", (0.0, 0, 7.0), (3.1, 0, 5.3), cuerda, oscuro)
    vara("EstayTrinquete", (3.1, 0, 5.3), (5.9, 0, 2.65), cuerda, oscuro)
    vara("EstayProa", (5.0, 0, 1.9), (3.05, 0, 5.25), cuerda, oscuro)
    vara("Bobstay", (5.2, 0, 0.4), (6.6, 0, 3.0), cuerda, oscuro)
    vara("EstayMesana", (-3.6, 0, 6.0), (-0.05, 0, 6.95), cuerda, oscuro)
    for lado in (-1, 1):
        for i, (dx, top) in enumerate(((-0.5, 6.9), (0.0, 6.95), (0.5, 6.9))):
            vara(f"ObenqueMayor{lado}{i}", (dx, lado * 1.25, 1.2), (0.0, lado * 0.28, top), cuerda, oscuro)
        for i, (dx, top) in enumerate(((2.7, 5.2), (3.5, 5.2))):
            vara(f"ObenqueTrinq{lado}{i}", (dx, lado * 1.05, 1.4), (3.1, lado * 0.22, top), cuerda, oscuro)
        # flechastes (7 travesaños en los obenques mayores)
        for j, z in enumerate((2.0, 2.6, 3.2, 3.8, 4.4, 5.0, 5.6)):
            f = (z - 1.2) / (6.92 - 1.2)
            y1 = lado * (1.25 + (0.28 - 1.25) * f)
            x1 = -0.5 + 0.5 * f
            x2 = 0.5 - 0.5 * f
            vara(f"Flechaste{lado}{j}", (x1, y1, z), (x2, y1, z), 0.012, oscuro)
        # flechastes del trinquete (4 travesaños)
        for j, z in enumerate((2.2, 2.9, 3.6, 4.3)):
            f = (z - 1.4) / (5.2 - 1.4)
            y1 = lado * (1.05 + (0.22 - 1.05) * f)
            x1 = 2.7 + 0.4 * f
            x2 = 3.5 - 0.4 * f
            vara(f"FlechasteTr{lado}{j}", (x1, y1, z), (x2, y1, z), 0.011, oscuro)
        # vigotas en la base de los obenques (motones redondos sobre la borda)
        for j, dx in enumerate((-0.5, 0.0, 0.5)):
            bpy.ops.mesh.primitive_uv_sphere_add(location=(dx, lado * 1.27, 1.16),
                                                 segments=10, ring_count=7)
            vg = bpy.context.active_object
            vg.name = f"VigotaAro{lado}{j}"
            vg.scale = (0.055, 0.04, 0.055)
            vg.data.materials.append(oscuro)
        # brazas de la verga mayor hacia popa
        vara(f"Braza{lado}", (0.0, lado * 2.28, 6.3), (-3.3, lado * 0.9, 2.4), cuerda, oscuro)


def cofa(nombre, centro, escala=1.0):
    """Plataforma de vigía: suelo + anillo de balaustres."""
    x, y, z = centro
    madera = mat("Madera", 0x8a6242)
    oscuro = mat("CascoBajo", 0x3e2c1c)
    cilindro(nombre + "Suelo", (x, y, z), 0.08, 0.42 * escala, madera, caras=20)
    bpy.ops.mesh.primitive_torus_add(location=(x, y, z + 0.3 * escala),
                                     major_radius=0.40 * escala, minor_radius=0.025,
                                     major_segments=24, minor_segments=8)
    aro = bpy.context.active_object
    aro.name = nombre + "Aro"
    aro.data.materials.append(oscuro)
    for i in range(12):
        a = i / 12 * math.pi * 2
        px, py = x + math.cos(a) * 0.4 * escala, y + math.sin(a) * 0.4 * escala
        vara(f"{nombre}Bal{i}", (px, py, z), (px, py, z + 0.3 * escala), 0.015, oscuro)

# ---------------- velamen ----------------
def vela_cuadra(nombre, cx, cz, ancho, alto, vientre, material, cruz=False):
    """Vela cuadrada hinchada hacia proa (+X). Si cruz=True añade la cruz de Santiago.
    Malla densa: el viento del lado web desplaza vértices y necesita resolución."""
    filas, cols = 17, 25

    def punto(i, j):
        u, v = j / (cols - 1), i / (filas - 1)
        y = (u - 0.5) * ancho
        z = cz - v * alto
        # vientre máximo en el centro, caída natural hacia abajo
        belly = math.sin(u * math.pi) * math.sin(min(1.0, v * 1.25) * math.pi)
        x = cx + vientre * belly + 0.12 * math.sin(v * math.pi)
        return (x, y, z)

    bm = bmesh.new()
    verts = [[bm.verts.new(punto(i, j)) for j in range(cols)] for i in range(filas)]
    for i in range(filas - 1):
        for j in range(cols - 1):
            bm.faces.new((verts[i][j], verts[i][j + 1], verts[i + 1][j + 1], verts[i + 1][j]))
    obj_de_bmesh(nombre, bm, material, suave=True)

    if cruz:
        rojo = mat("Rojo", 0xa33b2e)
        eps = 0.035  # por delante de la tela
        # brazo vertical y brazos horizontales de la cruz, siguiendo la curva de la vela
        def banda(nombre2, u0, u1, v0, v1):
            """Parche rojo que sigue la curvatura de la tela (malla completa, no un quad)."""
            bmc = bmesh.new()
            n, m = 13, 13
            vs = []
            for a in range(m):
                fila_v = []
                v = v0 + (v1 - v0) * a / (m - 1)
                for k in range(n):
                    u = u0 + (u1 - u0) * k / (n - 1)
                    x, y, z = punto(v * (filas - 1), u * (cols - 1))
                    fila_v.append(bmc.verts.new((x + eps, y, z)))
                vs.append(fila_v)
            for a in range(m - 1):
                for k in range(n - 1):
                    bmc.faces.new((vs[a][k], vs[a][k + 1], vs[a + 1][k + 1], vs[a + 1][k]))
            obj_de_bmesh(nombre2, bmc, rojo, suave=True)

        banda("CruzVertical", 0.43, 0.57, 0.10, 0.90)
        banda("CruzHorizontal", 0.18, 0.82, 0.32, 0.50)

    return nombre


def construye_velamen():
    vela = mat("Vela", 0xf6efdc)
    rojo = mat("Rojo", 0xa33b2e)
    oro = mat("Oro", 0xc9b07e)

    vela_cuadra("VelaMayor", 0.18, 6.2, 4.3, 3.9, 0.95, vela, cruz=True)
    vela_cuadra("GaviaMayor", 0.12, 8.35, 2.0, 1.5, 0.4, vela)
    vela_cuadra("VelaTrinquete", 3.25, 4.85, 3.0, 2.6, 0.6, vela)
    vela_cuadra("Cebadera", 5.95, 2.55, 1.5, 1.0, 0.25, vela)

    # vela latina de mesana: triángulo curvado que cuelga de la entena hacia la escota
    bm = bmesh.new()
    n, m = 17, 13
    pico = (-2.95, 0, 5.85)     # punta alta de la entena
    puno = (-5.35, 0, 3.65)     # punta baja de la entena
    escota = (-4.55, 0, 2.45)   # vértice inferior de la vela
    rejilla = []
    for a in range(m):
        s = a / (m - 1)
        fila_v = []
        for k in range(n):
            t = k / (n - 1)
            # borde superior: la entena; todo converge hacia la escota al bajar
            ex = pico[0] + (puno[0] - pico[0]) * t
            ez = pico[2] + (puno[2] - pico[2]) * t
            x = ex + (escota[0] - ex) * s
            z = ez + (escota[2] - ez) * s
            y = -0.30 * math.sin(t * math.pi) * math.sin(s * math.pi)  # vientre a babor
            fila_v.append(bm.verts.new((x, y, z)))
        rejilla.append(fila_v)
    for a in range(m - 1):
        for k in range(n - 1):
            bm.faces.new((rejilla[a][k], rejilla[a][k + 1], rejilla[a + 1][k + 1], rejilla[a + 1][k]))
    obj_de_bmesh("VelaMesana", bm, vela, suave=True)

    # grímpola larga de dos puntas en el mastelero mayor + banderas
    def grimpola(nombre, base, largo, material, caida=0.35):
        bmg = bmesh.new()
        n = 18
        sup, inf = [], []
        for k in range(n):
            t = k / (n - 1)
            x = base[0] - largo * t
            z = base[2] - caida * t * t + 0.08 * math.sin(t * 6.0)
            alto = 0.22 * (1 - t * 0.55)
            sup.append(bmg.verts.new((x, base[1], z)))
            inf.append(bmg.verts.new((x, base[1], z - alto)))
        for k in range(n - 1):
            if k == n - 2:  # corte de cola de golondrina
                continue
            bmg.faces.new((sup[k], sup[k + 1], inf[k + 1], inf[k]))
        obj_de_bmesh(nombre, bmg, material, suave=True)

    grimpola("GrimpolaMayor", (0.0, 0, 9.25), 2.4, rojo)
    grimpola("BanderaTrinquete", (3.1, 0, 5.75), 1.1, oro, caida=0.2)
    grimpola("BanderaMesana", (-3.85, 0, 6.2), 1.0, rojo, caida=0.2)

# ---------------- preview con cámara fija ----------------
def render_previews():
    s = bpy.context.scene
    s.render.engine = "BLENDER_WORKBENCH"
    s.display.shading.light = "STUDIO"
    s.display.shading.color_type = "MATERIAL"
    s.display.shading.show_cavity = True
    s.render.resolution_x = 1000
    s.render.resolution_y = 700
    cam_data = bpy.data.cameras.new("PrevCam")
    cam = bpy.data.objects.new("PrevCam", cam_data)
    s.collection.objects.link(cam)
    s.camera = cam
    for nombre, loc in (("3q", (16, -13, 7)), ("perfil", (0.5, -20, 4)), ("proa", (20, 5, 5))):
        cam.location = loc
        d = math.sqrt(sum(c * c for c in loc))
        # apuntar al centro del barco (0,0,2.5)
        dx, dy, dz = -loc[0], -loc[1], 2.5 - loc[2]
        cam.rotation_euler = (math.atan2(math.hypot(dx, dy), -dz), 0, math.atan2(dy, dx) - math.pi / 2)
        cam.rotation_mode = "XYZ"
        # corrección: usar track simple vía matriz
        import mathutils
        direccion = mathutils.Vector((dx, dy, dz))
        cam.rotation_euler = direccion.to_track_quat("-Z", "Y").to_euler()
        s.render.filepath = OUT + f"preview_{nombre}.png"
        bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)
    print("PREVIEWS_OK")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    construye_casco()
    construye_castillos()
    construye_arboladura()
    construye_velamen()
    total = 0
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            o.data.calc_loop_triangles()
            total += len(o.data.loop_triangles)
    print(f"TRIS_TOTALES:{total}")
    render_previews()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=OUT + "ship.glb",
        export_format="GLB",
        export_animations=False,
        export_cameras=False,
        export_yup=True,
    )
    print("SHIP_OK")


if __name__ == "__main__":
    main()
