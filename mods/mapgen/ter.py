"""SWBF2 terrain (.ter) files: a Python port of WorldEdit's terrain_io.cpp (PrismaticFlower/WorldEdit,
src/assets/terrain/terrain_io.cpp), the open-source SWBF2 world editor. write_ter reproduces its
save_terrain byte for byte (tests/test_mapgen.py checks against WorldEdit's own test terrain).

A terrain is a square grid of `length` points (at most 1024), `grid_scale` metres apart, centred on
the world origin. Grid (x, y) is at world X = (x - length/2) * grid_scale and world
Z = (y - length/2 + 1) * grid_scale; its height is height_map[y][x] * height_scale metres.
"""
import struct

TEXTURES = 16
CLUSTER = 4
FOLIAGE_MAP = 512
WATER_BIT = 0x10000
UNUSED_SECTIONS = 262144 + 131072


class Terrain:
    def __init__(self, length=64, height_scale=0.01, grid_scale=8.0):
        assert length % 4 == 0 and length <= 1024
        self.version = 22
        self.length = length
        self.height_scale = height_scale
        self.grid_scale = grid_scale
        self.active = (True, True, True)            # terrain, water, foliage
        self.prelit = False
        self.texture_names = [""] * TEXTURES
        self.texture_scales = [1.0] * TEXTURES
        self.texture_axes = [0] * TEXTURES
        self.detail_texture = ""
        self.water = dict(height=0.0, u_velocity=0.0, v_velocity=0.0, u_repeat=0.0, v_repeat=0.0,
                          color=0xFFFFFFFF, texture="")
        n = length
        self.height_map = [[0] * n for _ in range(n)]           # int16, [y][x]
        self.color_map = [[0xFFFFFFFF] * n for _ in range(n)]   # uint32
        self.light_map = [[0xFFFFFFFF] * n for _ in range(n)]   # uint32
        self.light_map_extra = None
        self.weights = [[[0] * n for _ in range(n)] for _ in range(TEXTURES)]  # uint8 [tex][y][x]
        self.water_map = [[False] * (n // 4) for _ in range(n // 4)]
        self.foliage_map = [[0] * (n // 2) for _ in range(n // 2)]         # 4 layer bits

    # world <-> grid
    def world_x(self, x):
        return (x - self.length / 2) * self.grid_scale

    def world_z(self, y):
        return (y - self.length / 2 + 1) * self.grid_scale

    def grid_of(self, wx, wz):
        return wx / self.grid_scale + self.length / 2, wz / self.grid_scale + self.length / 2 - 1

    def height_at(self, wx, wz):
        """Bilinear height in metres at a world position."""
        gx, gy = self.grid_of(wx, wz)
        n = self.length - 1
        gx = min(max(gx, 0), n)
        gy = min(max(gy, 0), n)
        x0, y0 = int(gx), int(gy)
        x1, y1 = min(x0 + 1, n), min(y0 + 1, n)
        fx, fy = gx - x0, gy - y0
        h = self.height_map
        top = h[y0][x0] * (1 - fx) + h[y0][x1] * fx
        bot = h[y1][x0] * (1 - fx) + h[y1][x1] * fx
        return (top * (1 - fy) + bot * fy) * self.height_scale


def _tex_string(name):
    if not name:
        return b"\0" * 32
    raw = name.encode("ascii")[:32 - 5]
    return (raw + b".tga\0").ljust(32, b"\0")


def _read_tex_string(raw):
    s = raw.split(b"\0")[0].decode("ascii", "replace")
    return s[:-4] if s.lower().endswith(".tga") else s


def _water(height=0.0, u_velocity=0.0, v_velocity=0.0, u_repeat=0.0, v_repeat=0.0, color=0, texture=""):
    return struct.pack("<f3f4fI", height, 0, 0, 0, u_velocity, v_velocity, u_repeat, v_repeat, color) \
        + _tex_string(texture)


def _cluster_flags_numpy(t, c):
    """The texture bits of every cluster (as the loop in write_ter works them out), with numpy if
    it's there: a texture counts for a cluster if it has weight anywhere in the cluster or the
    one-point border around it."""
    try:
        import numpy as np
    except ImportError:
        return None
    n = t.length
    flags = np.zeros((c, c), dtype=np.int64)
    for s in range(TEXTURES):
        wmap = np.asarray(t.weights[s]) > 0
        if not wmap.any():
            continue
        padded = np.pad(wmap, 1, mode="edge")
        # any weight in each 6x6 window starting at (y-1, x-1) for every cluster corner
        acc = np.zeros((c, c), dtype=bool)
        for dy in range(CLUSTER + 2):
            for dx in range(CLUSTER + 2):
                acc |= padded[dy:dy + n:CLUSTER, dx:dx + n:CLUSTER][:c, :c]
        flags |= acc.astype(np.int64) << s
    return flags


def write_ter(t, cuts=()):
    n = t.length
    half = n // 2
    out = bytearray()
    out += struct.pack("<4sIhhhhI", b"TERR", t.version, -half, -half, half, half, 164)
    out += struct.pack("<16f", *t.texture_scales)
    out += bytes(t.texture_axes)
    out += struct.pack("<16f", *[0.0] * 16)                      # texture rotations
    out += struct.pack("<ffiii", t.height_scale, t.grid_scale, int(t.prelit), n, 2)
    assert len(out) == 184
    if t.version == 22:
        flags = (1 if t.active[0] else 0) | (4 if t.active[2] else 0) | (2 if t.active[1] else 0)
        if t.light_map_extra is not None:
            flags |= 8
        out += bytes([flags])
    for i in range(TEXTURES):
        out += _tex_string(t.texture_names[i])
        out += _tex_string(t.detail_texture) if i == 0 else b"\0" * 32
    w = t.water
    out += _water()
    out += _water(w["height"], w["u_velocity"], w["v_velocity"], w["u_repeat"], w["v_repeat"],
                  w["color"], w["texture"])
    for _ in range(14):
        out += _water()
    out += b"\0" * 32 * 16                                       # decal names
    out += struct.pack("<iii", 0, 0, 0)                          # decal tiles, foliage clusters, models

    def write_map(m, fmt):
        for y in range(n - 1, -1, -1):
            out.extend(struct.pack("<%d%s" % (n, fmt), *m[y]))

    write_map(t.height_map, "h")
    write_map(t.color_map, "I")
    write_map(t.light_map, "I")
    if t.version == 22 and t.light_map_extra is not None:
        write_map(t.light_map_extra, "I")
    for y in range(n - 1, -1, -1):
        for x in range(n):
            out.extend(bytes(t.weights[s][y][x] for s in range(TEXTURES)))

    # cluster info: WorldEdit writes the widest possible height bounds (never culled), then flags
    c = n // CLUSTER
    mins = [[0] * c for _ in range(c)]
    maxs = [[0] * c for _ in range(c)]
    cflags = [[0] * c for _ in range(c)]
    fast = _cluster_flags_numpy(t, c)
    for y in range(0, n, CLUSTER):
        for x in range(0, n, CLUSTER):
            cy = (n - 1 - y) // CLUSTER
            mins[cy][x // CLUSTER] = -32768
            maxs[cy][x // CLUSTER] = 32767
            f = 0
            if fast is not None:
                f = int(fast[y // CLUSTER][x // CLUSTER])
                if t.water_map[y // CLUSTER][x // CLUSTER]:
                    f |= WATER_BIT
                cflags[cy][x // CLUSTER] = f
                continue
            for ly in range(-1, CLUSTER + 1):
                for lx in range(-1, CLUSTER + 1):
                    ax = min(max(x + lx, 0), n - 1)
                    ay = min(max(y + ly, 0), n - 1)
                    for s in range(TEXTURES):
                        if t.weights[s][ay][ax] > 0:
                            f |= 1 << s
            if t.water_map[y // CLUSTER][x // CLUSTER]:
                f |= WATER_BIT
            cflags[cy][x // CLUSTER] = f
    for row in mins:
        out += struct.pack("<%dh" % c, *row)
    for row in maxs:
        out += struct.pack("<%dh" % c, *row)
    for row in cflags:
        out += struct.pack("<%dI" % c, *row)

    # foliage: a 512x512 map of 4-bit cells, two to a byte, with the terrain's part in the middle
    fl = n // 2
    off = (FOLIAGE_MAP - fl) // 2
    out += b"\0" * 256 * off
    for y in range(fl):
        out += b"\0" * (off // 2)
        fy = fl - 1 - y
        for x in range(0, fl, 2):
            out.append(((t.foliage_map[fy][x] & 0xF) << 4) | (t.foliage_map[fy][x + 1] & 0xF))
        out += b"\0" * (off // 2)
    out += b"\0" * 256 * off
    out += b"\0" * UNUSED_SECTIONS

    size = 4
    for planes, bmin, bmax in cuts:
        size += 4 + 24 + 16 * len(planes)
    out += struct.pack("<II", size, len(cuts))
    for planes, bmin, bmax in cuts:
        out += struct.pack("<I", len(planes))
        out += struct.pack("<3f", bmin[0], bmin[1], -bmax[2])
        out += struct.pack("<3f", bmax[0], bmax[1], -bmin[2])
        for a, b, cc, d in planes:
            out += struct.pack("<4f", a, b, -cc, d)
    return bytes(out)


def read_ter(data):
    """The fields write_ter writes (enough to round-trip WorldEdit-written terrain)."""
    p = 0

    def take(fmt):
        nonlocal p
        v = struct.unpack_from("<" + fmt, data, p)
        p += struct.calcsize("<" + fmt)
        return v

    mn, version, left, top, right, bottom, exheader = take("4sIhhhhI")
    assert mn == b"TERR", "not a terrain file"
    assert exheader == 164
    scales = take("16f")
    axes = list(take("16B"))
    take("16f")
    height_scale, grid_scale, prelit, length, foliage_patch = take("ffiii")
    t = Terrain(right - left, height_scale, grid_scale)
    t.version, t.prelit = version, bool(prelit)
    t.texture_scales, t.texture_axes = list(scales), axes
    extra = False
    if version == 22:
        (flags,) = take("B")
        t.active = (bool(flags & 1), bool(flags & 2), bool(flags & 4))
        extra = bool(flags & 8)
    for i in range(TEXTURES):
        t.texture_names[i] = _read_tex_string(data[p:p + 32])
        p += 32
        if i == 0:
            t.detail_texture = _read_tex_string(data[p:p + 32])
        p += 32
    waters = []
    for _ in range(16):
        h, _a, _b, _c, uv, vv, ur, vr, col = take("f3f4fI")
        waters.append(dict(height=h, u_velocity=uv, v_velocity=vv, u_repeat=ur, v_repeat=vr, color=col,
                           texture=_read_tex_string(data[p:p + 32])))
        p += 32
    t.water = waters[1]
    p += 32 * 16
    (decals,) = take("i")
    p += 44 * decals
    (fc,) = take("i")
    p += 24 * fc
    (fm,) = take("i")
    p += 28 * fm
    n = t.length
    full = length                       # stock files keep the used area centred in a bigger grid
    off = (full - n) // 2

    def read_map(fmt):
        size = struct.calcsize(fmt)
        m = [None] * n
        for y in range(full - 1, -1, -1):
            nonlocal p
            p += off * size
            if off <= y < off + n:
                m[y - off] = list(take("%d%s" % (n, fmt)))
            else:
                p += n * size
            p += off * size
        return m

    t.height_map = read_map("h")
    t.color_map = read_map("I")
    t.light_map = read_map("I")
    if extra:
        t.light_map_extra = read_map("I")
    for y in range(full - 1, -1, -1):
        p += off * TEXTURES
        if off <= y < off + n:
            for x in range(n):
                row = data[p:p + TEXTURES]
                p += TEXTURES
                for s in range(TEXTURES):
                    t.weights[s][y - off][x] = row[s]
        else:
            p += n * TEXTURES
        p += off * TEXTURES
    cl, c, coff = full // CLUSTER, n // CLUSTER, off // CLUSTER
    p += cl * cl * 4
    for cy in range(cl - 1, -1, -1):
        p += coff * 4
        if coff <= cy < coff + c:
            for cx in range(c):
                (f,) = take("I")
                t.water_map[cy - coff][cx] = bool(f & WATER_BIT)
        else:
            p += c * 4
        p += coff * 4
    fmap = [[0] * FOLIAGE_MAP for _ in range(FOLIAGE_MAP)]
    for y in range(FOLIAGE_MAP - 1, -1, -1):
        for x in range(0, FOLIAGE_MAP, 2):
            b = data[p]
            p += 1
            fmap[y][x] = b >> 4
            fmap[y][x + 1] = b & 0xF
    fl = n // 2
    foff = (FOLIAGE_MAP - fl) // 2
    for y in range(fl):
        for x in range(fl):
            t.foliage_map[y][x] = fmap[y + foff][x + foff]
    return t
