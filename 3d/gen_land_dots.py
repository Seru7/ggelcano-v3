# Genera land-dots.js: matriz de puntos (lat,lon) de tierra emergida para el globo 3D.
# Fuente: world-atlas land-110m.json (TopoJSON de Natural Earth, dominio público).
# Método: decodifica los arcos, junta los anillos y hace scanline por cada latitud
# de la rejilla (cruces de paridad par/impar = dentro). Densidad uniforme en la
# esfera: el paso de longitud crece con 1/cos(lat). Jitter determinista para que
# no se vea la rejilla.
import json
import math

SRC = "/tmp/land-110m.json"
OUT = "/home/sergio/Documents/webs-premium/prototipo-ggelcano-3d/3d/land-dots.js"
PASO_LAT = 1.7
PASO_LON_BASE = 1.7

topo = json.load(open(SRC))
sc = topo["transform"]["scale"]
tr = topo["transform"]["translate"]

# decodificar arcos (delta-encoded, cuantizados)
arcos = []
for arc in topo["arcs"]:
    x = y = 0
    pts = []
    for dx, dy in arc:
        x += dx
        y += dy
        pts.append((x * sc[0] + tr[0], y * sc[1] + tr[1]))  # (lon, lat)
    arcos.append(pts)


def anillo(indices):
    pts = []
    for i in indices:
        a = arcos[i] if i >= 0 else list(reversed(arcos[~i]))
        pts.extend(a if not pts else a[1:])
    return pts


anillos = []
for geom in topo["objects"]["land"]["geometries"]:
    polys = geom["arcs"] if geom["type"] == "MultiPolygon" else [geom["arcs"]]
    for poly in polys:
        for ring in poly:
            anillos.append(anillo(ring))

# scanline: para cada latitud, longitudes de cruce de todos los segmentos
def hash01(i, j):
    h = (i * 374761393 + j * 668265263) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((h ^ (h >> 16)) % 10000) / 10000.0


dots = []
fila = 0
lat = -85.0
while lat <= 85.0:
    cruces = []
    for ring in anillos:
        for (lon1, la1), (lon2, la2) in zip(ring, ring[1:]):
            if (la1 > lat) != (la2 > lat):
                t = (lat - la1) / (la2 - la1)
                # saltos antimeridiano: descartar segmentos absurdamente largos
                if abs(lon2 - lon1) > 180:
                    continue
                cruces.append(lon1 + t * (lon2 - lon1))
    cruces.sort()
    paso_lon = PASO_LON_BASE / max(0.18, math.cos(math.radians(lat)))
    col = 0
    lon = -180.0
    while lon < 180.0:
        # paridad: nº de cruces a la izquierda impar = tierra
        import bisect
        if bisect.bisect_left(cruces, lon) % 2 == 1:
            jla = (hash01(fila, col) - 0.5) * PASO_LAT * 0.8
            jlo = (hash01(col, fila) - 0.5) * paso_lon * 0.8
            dots.append((round(lat + jla, 1), round(lon + jlo, 1)))
        lon += paso_lon
        col += 1
    lat += PASO_LAT
    fila += 1

flat = []
for la, lo in dots:
    flat.append(str(la))
    flat.append(str(lo))

with open(OUT, "w") as f:
    f.write("// Puntos de tierra (lat,lon) generados por gen_land_dots.py — NO editar a mano.\n")
    f.write("export default new Float32Array([" + ",".join(flat) + "]);\n")

print(f"DOTS_OK:{len(dots)}")
