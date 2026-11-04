"""GTS, "Ground to Space": a 2 km desert valley with a capital ship hanging 300 m overhead.

    python mods/mapgen/gts.py [--out DIR] [--code GTS] [--preview]

Writes a mod-tools map folder (data_GTS) with the world, terrain, the ship model and textures,
and the mission scripts; see README.md for building it with the SWBF2 Mod Tools.

All coordinates are the game's (file) coordinates, in metres: X east, Y up, Z north-ish.
"""
import argparse
import math
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import msh  # noqa: E402
import ter  # noqa: E402
import world  # noqa: E402

LENGTH = 256          # terrain points per side
GRID = 8.0            # metres between them: the map is 2048 m across
HSCALE = 0.05         # metres per terrain height unit (int16: up to 1638 m)
SHIP_Y = 380.0        # the hangar deck's height
SHIP_X, SHIP_Z = 0.0, 330.0   # where the ship hangs (its centre)

# command posts: (name, x, z, team, label); y comes from the terrain, or the deck for the ship
GROUND_POSTS = [
    ("cp1", 0.0, -720.0, 1, "South Landing"),
    ("cp2", -520.0, -180.0, 2, "West Mesa"),
    ("cp3", 0.0, 0.0, 0, "Canyon Bridge"),
    ("cp4", 520.0, -120.0, 2, "East Mesa"),
    ("cp5", 0.0, 200.0, 2, "Shadow of the Ship"),
]
# on the hangar deck, relative to the ship's centre
SHIP_POSTS = [
    ("cp6", -50.0, -40.0, 2, "Hangar"),
    ("cp7", 50.0, -40.0, 2, "Hangar Control"),
]


# ---------------------------------------------------------------- terrain

def smooth_noise(n, cells, rng):
    """Value noise: a coarse random grid, bicubic-smoothed up to n x n."""
    coarse = rng.random((cells + 3, cells + 3))
    xs = np.linspace(1, cells + 1, n, endpoint=False)
    i = xs.astype(int)
    t = xs - i
    def cubic(p0, p1, p2, p3, t):
        return p1 + 0.5 * t * (p2 - p0 + t * (2 * p0 - 5 * p1 + 4 * p2 - p3 + t * (3 * (p1 - p2) + p3 - p0)))
    rows = cubic(coarse[:, i - 1], coarse[:, i], coarse[:, i + 1], coarse[:, i + 2], t)
    return cubic(rows[i - 1], rows[i], rows[i + 1], rows[i + 2], t[:, None])


def grid_coords():
    """World X and Z of every terrain point, [y][x]."""
    idx = np.arange(LENGTH)
    x = (idx - LENGTH / 2) * GRID
    z = -(idx - LENGTH / 2 + 1) * GRID
    return np.meshgrid(x, z)          # X[y][x], Z[y][x]


def mesa(X, Z, cx, cz, radius, height, ramp_angle):
    """A flat-topped mesa with a ramp down one side (angle in degrees)."""
    d = np.hypot(X - cx, Z - cz)
    edge = np.clip((radius + 60 - d) / 60, 0, 1)            # 60 m cliff band
    body = height * edge ** 2 * (3 - 2 * edge)
    a = math.radians(ramp_angle)
    along = (X - cx) * math.cos(a) + (Z - cz) * math.sin(a)
    across = -(X - cx) * math.sin(a) + (Z - cz) * math.cos(a)
    # a 30 m wide ramp running 180 m out from the edge, its sides sloping away over 25 m
    ramp = height * np.clip(1 - (along - radius) / 180, 0, 1)
    ramp = np.where(along < radius, height, ramp)
    side = np.clip(1 - (np.abs(across) - 15) / 25, 0, 1)
    ramp = np.where((along > 0) & (along < radius + 180), ramp * side, 0)
    return np.maximum(body, ramp)


def make_heights(seed=7):
    rng = np.random.default_rng(seed)
    X, Z = grid_coords()
    h = 20.0 + 6.0 * smooth_noise(LENGTH, 12, rng) + 2.5 * smooth_noise(LENGTH, 40, rng)
    # wind-blown dune ripples, running north-east
    h += 1.2 * np.sin((X * 0.7 + Z * 0.7) / 9.0 + 3 * smooth_noise(LENGTH, 8, rng)) * smooth_noise(LENGTH, 6, rng)

    # the mountain ring past about 820 m from the centre: ridged noise for sharp crests
    ridged = 1 - np.abs(2 * smooth_noise(LENGTH, 14, rng) - 1)
    ridged = 0.6 * ridged ** 2 + 0.4 * smooth_noise(LENGTH, 5, rng)
    r = np.hypot(X, Z) + 60 * (smooth_noise(LENGTH, 9, rng) - 0.5)
    ring = np.clip((r - 820) / 180, 0, 1)
    h += ring ** 1.5 * (90 + 190 * ridged)

    # three sandstone mesas, their cliffs banded in strata
    mesas = np.zeros_like(h)
    mesas = np.maximum(mesas, mesa(X, Z, -520, -180, 110, 45, 0))      # west, ramp east
    mesas = np.maximum(mesas, mesa(X, Z, 520, -120, 100, 55, 180))     # east, ramp west
    mesas = np.maximum(mesas, mesa(X, Z, -380, 420, 80, 70, -30))      # north-west lookout
    gz, gx = np.gradient(mesas, GRID)
    cliff = np.clip((np.hypot(gx, gz) - 0.4) / 0.4, 0, 1)
    banded = np.floor(mesas / 6.0) * 6.0 + 2.0 * np.clip((mesas % 6.0) - 4.0, 0, 2) / 2
    mesas = mesas * (1 - cliff) + banded * cliff
    h = np.maximum(h, 20 + mesas)

    # sandstone spires and boulders across the valley floor, clear of the posts
    for k in range(22):
        cx, cz = rng.uniform(-760, 760), rng.uniform(-760, 700)
        if min(math.hypot(cx - p[1], cz - p[2]) for p in GROUND_POSTS) < 110 or abs(cz - 60 * math.sin(cx / 260.0)) < 70:
            continue
        if math.hypot(cx, cz) > 780:
            continue
        if k % 3 == 0:
            rad, tall = rng.uniform(8, 14), rng.uniform(25, 45)
            d2 = ((X - cx) ** 2 + (Z - cz) ** 2) / (rad * rad)
            spire = tall * np.clip(1 - d2, 0, 1) ** 0.5
            h = np.maximum(h, 20 + np.floor(spire / 5.0) * 5.0)
        else:
            rad, tall = rng.uniform(12, 30), rng.uniform(4, 10)
            h += np.exp(-(((X - cx) ** 2 + (Z - cz) ** 2) / (rad * rad))) * tall

    # the canyon: a winding trench across the valley, bridged at the centre
    wiggle = 60 * np.sin(X / 260.0)
    dist = np.abs(Z - wiggle)
    depth = 28 * np.clip(1 - dist / 55, 0, 1) ** 1.5
    bridge = np.abs(X) < 14
    h -= np.where(bridge, 0, depth)

    # flat ground for the landing zone and under the ship
    for cx, cz, rad in ((0, -720, 70), (0, 200, 90)):
        d = np.hypot(X - cx, Z - cz)
        w = np.clip((rad + 40 - d) / 40, 0, 1)
        h = h * (1 - w) + 21.0 * w
    return h


def texture_weights(h):
    """sand (0) on the flats, dirt (1) on slopes, rock (2) on cliffs and mountains."""
    gz, gx = np.gradient(h, GRID)
    slope = np.hypot(gx, gz)
    rock = np.clip((slope - 0.55) / 0.3, 0, 1)
    rock = np.maximum(rock, np.clip((h - 90) / 60, 0, 1))
    dirt = np.clip((slope - 0.18) / 0.25, 0, 1) * (1 - rock)
    sand = 1 - rock - dirt
    return [np.clip(w * 255 + 0.5, 0, 255).astype(np.uint8) for w in (sand, dirt, rock)]


def build_terrain(h, code):
    t = ter.Terrain(LENGTH, HSCALE, GRID)
    t.height_map = np.clip(np.round(h / HSCALE), -32768, 32767).astype(int).tolist()
    for i, (name, scale) in enumerate(((code.lower() + "_sand", 0.04), (code.lower() + "_dirt", 0.05),
                                       (code.lower() + "_rock", 0.03))):
        t.texture_names[i] = name
        t.texture_scales[i] = scale
    for i, w in enumerate(texture_weights(h)):
        t.weights[i] = w.tolist()
    # simple baked lighting: brighter where the ground faces the sun
    gz, gx = np.gradient(h, GRID)
    n = np.dstack((-gx, np.ones_like(h), -gz))
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    sun = np.array([0.45, 0.8, 0.4])
    sun /= np.linalg.norm(sun)
    lit = np.clip(0.45 + 0.6 * (n @ sun), 0, 1)
    v = (lit * 255).astype(np.uint32)
    t.light_map = (0xFF000000 | (v << 16) | (v << 8) | v).tolist()
    return t


def height_at(h, x, z):
    """Terrain height at a world position (bilinear)."""
    gx = x / GRID + LENGTH / 2
    gy = -z / GRID + LENGTH / 2 - 1
    gx = min(max(gx, 0), LENGTH - 1.001)
    gy = min(max(gy, 0), LENGTH - 1.001)
    x0, y0 = int(gx), int(gy)
    fx, fy = gx - x0, gy - y0
    top = h[y0][x0] * (1 - fx) + h[y0][x0 + 1] * fx
    bot = h[y0 + 1][x0] * (1 - fx) + h[y0 + 1][x0 + 1] * fx
    return top * (1 - fy) + bot * fy


# ---------------------------------------------------------------- the ship

# In the ship's own frame: X along the ship (bow at +X), Y up from the hangar deck, Z across.
# The hangar is a pod under the hull, 180 x 26 m inside, open on the -Z (south) side, 90 m deep.
HANGAR = (-90.0, 90.0)        # X extent of the bay
HANGAR_DEPTH = 70.0           # from the -Z opening in to the back wall at Z = 20 (centre at -25)

HULL = (0.66, 0.68, 0.72)
DARK = (0.36, 0.38, 0.43)
ENGINE_GLOW = (0.62, 0.86, 1.0)
LAMP = (1.0, 0.93, 0.72)


def _section(x, w, yb, yt, ridge):
    """A hull cross-section: a wide flat keel, bevelled sides and a raised spine."""
    mid = yb + 0.3 * (yt - yb)
    return (x, [(-w, mid), (-w * 0.62, yb), (w * 0.62, yb), (w, mid), (w * 0.36, yt), (0.0, yt + ridge),
                (-w * 0.36, yt)])


def ship_parts():
    """(name, polygons, material, colour, glows, collides) for every part of the ship."""
    import random
    import shapes as sh
    parts = []
    sections = [_section(-300, 112, 30, 72, 12), _section(-160, 104, 28, 68, 14), _section(0, 86, 28, 62, 14),
                _section(150, 60, 30, 54, 10), _section(270, 30, 32, 45, 6), _section(345, 4, 36, 40, 1)]
    parts.append(("hull", sh.loft(sections), 0, HULL, False, True))

    # the hangar pod under the hull
    pod = []
    pod += sh.box((-96, -14, -70), (96, 0, 70), faces="xXyzZ")       # floor slab (its top is the deck, below)
    pod += sh.box((-96, 26, -70), (96, 30, 70), faces="xXYzZ")        # ceiling slab (underside below)
    pod += sh.box((-90, 0, 20), (90, 26, 70), faces="xXYZ")           # back wall (its face below)
    pod += sh.box((-96, 0, -70), (-90, 26, 70), faces="xyYzZ")        # end walls (inner faces below)
    pod += sh.box((90, 0, -70), (96, 26, 70), faces="XyYzZ")
    pod += sh.loft([(-96, [(-70, -14), (70, -14), (55, -26), (-55, -26)]),
                    (96, [(-70, -14), (70, -14), (55, -26), (-55, -26)])])   # bevelled keel
    parts.append(("pod", pod, 0, HULL, False, True))
    # the bay's inside: the deck, back wall and end walls lit by its lamps, a darker ceiling
    bay = sh.box((-96, -14, -70), (96, 0, 20), faces="Y")             # the deck (up to the back wall)
    bay += sh.box((-90, 0, 20), (90, 26, 70), faces="z")              # the back wall
    bay += sh.box((-96, 0, -70), (-90, 26, 20), faces="X")            # the end walls' inner faces
    bay += sh.box((90, 0, -70), (96, 26, 20), faces="x")
    parts.append(("bay", bay, 0, (0.62, 0.56, 0.46), True, True))
    parts.append(("bay ceiling", sh.box((-96, 26, -70), (96, 30, 20), faces="y"), 0, (0.30, 0.29, 0.28), True, True))
    # lamp strips across the bay's ceiling, and a lit doorway frame
    lamps = []
    for k in range(5):
        z = -60 + k * 18
        lamps += sh.box((-84, 25.2, z), (84, 25.8, z + 2), faces="y")
    lamps += sh.box((-96, 26, -71), (96, 27.2, -70), faces="z")
    parts.append(("lamps", lamps, 1, LAMP, True, False))

    # the command tower and bridge, at the stern
    tower = sh.loft([(-262, [(-34, 70), (34, 70), (24, 112), (-24, 112)]),
                     (-188, [(-26, 70), (26, 70), (18, 108), (-18, 108)])])
    tower += sh.box((-256, 112, -58), (-214, 124, 58))     # the bridge
    tower += sh.box((-252, 124, -20), (-220, 130, 20))
    tower += sh.dome(-236, 130, -42, 9, rings=4, sides=12)
    tower += sh.dome(-236, 130, 42, 9, rings=4, sides=12)
    tower += sh.frustum(-236, 0, 3, 1, 130, 150, sides=8)  # a mast
    parts.append(("tower", tower, 0, HULL, False, True))
    windows = sh.box((-256.2, 116, -56), (-256, 120, 56), faces="x") + sh.box((-214, 116, -56), (-213.8, 120, 56), faces="X")
    parts.append(("windows", windows, 1, (0.85, 0.95, 1.0), True, False))

    # engines: three nacelles, and their glow
    engines, glow = [], []
    for z, r in ((-62, 17), (0, 21), (62, 17)):
        engines += sh.tube((-290, 50, z), (-336, 50, z), r, sides=16)
        engines += sh.tube((-336, 50, z), (-342, 50, z), r * 0.8, sides=16, caps=False)
        glow += sh.frustum(0, 0, r * 0.78, r * 0.78, 0, 0.2, sides=16)[:0]
        disc = sh.tube((-342.0, 50, z), (-342.6, 50, z), r * 0.78, sides=16)
        glow += disc
    parts.append(("engines", engines, 0, DARK, False, True))
    parts.append(("engine glow", glow, 1, ENGINE_GLOW, True, False))

    # surface detail along the top: plating blocks and turrets (fixed seed)
    rng = random.Random(11)
    detail = []
    for _ in range(60):
        x = rng.uniform(-150, 260)
        # the top deck's height and half width at x, between the sections either side
        for (xa, pa), (xb, pb) in zip(sections, sections[1:]):
            if xa <= x <= xb:
                t = (x - xa) / (xb - xa)
                top = pa[4][1] * (1 - t) + pb[4][1] * t
                half = pa[4][0] * (1 - t) + pb[4][0] * t
                break
        z = rng.uniform(-half * 0.8, half * 0.8)
        size = rng.choice((5, 7, 9, 12))
        if rng.random() < 0.3:
            detail += sh.frustum(x, z, size * 0.5, size * 0.4, top, top + 3, sides=10)
            detail += sh.dome(x, top + 3, z, size * 0.4, rings=3, sides=10)
        else:
            detail += sh.box((x, top, z), (x + size, top + rng.choice((1.5, 2.5, 4)), z + size * rng.uniform(0.6, 1.4)))
    parts.append(("detail", detail, 0, DARK, False, False))
    return parts


def ship_mesh(hull_texture="gts_hull", glow_texture="gts_glow"):
    hull = msh.Material("hull", texture=hull_texture)
    lights = msh.Material("lights", texture=glow_texture, glow=True)
    mesh, collision = msh.Mesh(), msh.Mesh()
    for name, polys, material, colour, glows, collides in ship_parts():
        mesh.polys(material, polys, uv_scale=1 / 32.0)
        if collides:
            collision.polys(0, polys)
    return [hull, lights], mesh, collision


def ship_world_parts():
    """The ship's parts in world space, for the preview."""
    import shapes as sh
    return [(sh.offset(polys, SHIP_X, SHIP_Y, SHIP_Z), colour, glows)
            for name, polys, material, colour, glows, collides in ship_parts()]


# ---------------------------------------------------------------- textures

def tga(width, height, pixels):
    """An uncompressed 24-bit TGA from rows of (r, g, b), top row first."""
    head = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, width, height, 24, 0x20)
    body = bytearray()
    for row in pixels:
        for r, g, b in row:
            body += bytes((b, g, r))
    return head + bytes(body)


def make_textures(code, seed=3):
    rng = np.random.default_rng(seed)
    n = 128
    def noisy(base, amount, cells=16):
        v = smooth_noise(n, cells, rng) * amount + rng.random((n, n)) * amount * 0.4
        return [[tuple(int(np.clip(c + v[y][x] * 255 - amount * 128, 0, 255)) for c in base)
                 for x in range(n)] for y in range(n)]
    out = {
        code.lower() + "_sand.tga": tga(n, n, noisy((200, 170, 120), 0.25)),
        code.lower() + "_dirt.tga": tga(n, n, noisy((150, 115, 80), 0.35)),
        code.lower() + "_rock.tga": tga(n, n, noisy((120, 110, 100), 0.5, 24)),
    }
    # hull plating: panels with seams
    hull = []
    for y in range(n):
        row = []
        for x in range(n):
            seam = (x % 32 in (0, 1)) or (y % 16 in (0, 1))
            g = 150 + int(rng.random() * 12) - (45 if seam else 0)
            row.append((g, g, g + 6))
        hull.append(row)
    out["gts_hull.tga"] = tga(n, n, hull)
    out["gts_glow.tga"] = tga(8, 8, [[(255, 255, 255)] * 8 for _ in range(8)])
    return out


# ---------------------------------------------------------------- the world

def build_world(code, h):
    w = world.World(code)
    conquest = w.layer("conquest", modes=("conquest",))

    for name, x, z, team, label in GROUND_POSTS:
        y = height_at(h, x, z)
        w.command_post(name, (x, y, z), team, layer=conquest, label=label)
    for name, dx, dz, team, label in SHIP_POSTS:
        pos = (SHIP_X + dx, SHIP_Y, SHIP_Z + dz)
        spawn = [(pos[0] + 6 * math.cos(a), SHIP_Y, pos[2] + 6 * math.sin(a))
                 for a in [i * math.pi / 4 for i in range(8)]]
        w.command_post(name, pos, team, layer=conquest, label=label, spawn=spawn, control_height=12)

    # the ship, in the base layer so every mode has it, and lights in its hangar
    w.object(code.lower() + "_ship", "ship", (SHIP_X, SHIP_Y, SHIP_Z))
    for k, dx in enumerate((-60.0, -20.0, 20.0, 60.0)):
        w.light("hangar%d" % (k + 1), (SHIP_X + dx, SHIP_Y + 22.0, SHIP_Z - 25.0), (1.0, 0.92, 0.75), 38.0)

    # fighters for both sides at the landing zone and under the ship (classes set in the scripts'
    # sides; ClassXxxATK / ClassXxxDEF name what spawns for each era and role)
    for i, (x, z, cp) in enumerate(((-60, -700, "cp1"), (60, -700, "cp1"), (-70, 180, "cp5"), (70, 180, "cp5"))):
        y = height_at(h, x, z)
        props = [("ControlZone", cp), ("SpawnTime", "15.0"), ("ExpireTimeEnemy", "20.0"), ("ExpireTimeField", "30.0"),
                 ("ClassRepATK", "rep_fly_arc170fighter"), ("ClassRepDEF", "rep_fly_arc170fighter"),
                 ("ClassCISATK", "cis_fly_droidfighter"), ("ClassCISDEF", "cis_fly_droidfighter"),
                 ("ClassAllATK", "all_fly_xwing"), ("ClassAllDEF", "all_fly_xwing"),
                 ("ClassImpATK", "imp_fly_tiefighter"), ("ClassImpDEF", "imp_fly_tiefighter")]
        w.object("com_item_vehicle_spawn", "fighters%d" % (i + 1), (x, y + 1, z), props=props, layer=conquest)

    # the boundary, inside the mountains
    w.boundary = [(900 * math.cos(a), 900 * math.sin(a)) for a in [i * math.pi / 12 for i in range(24)]]

    build_planning(w, h)
    return w


def build_planning(w, h, spacing=64.0):
    """The bots' map: hubs on a grid over walkable ground (and on the hangar deck), joined where
    the ground between them is gentle. Steeper links are for soldiers only."""
    hubs = {}
    steps = int(1800 / spacing)
    for i in range(-steps // 2, steps // 2 + 1):
        for j in range(-steps // 2, steps // 2 + 1):
            x, z = i * spacing, j * spacing
            if math.hypot(x, z) > 860:
                continue
            y = height_at(h, x, z)
            if y > 120:
                continue
            name = "Hub%d_%d" % (i + 50, j + 50)
            hubs[(i, j)] = (name, (x, y, z))
            w.hub(name, (x, y, z), spacing * 0.35)
    for (i, j), (name, (x, y, z)) in hubs.items():
        for di, dj in ((1, 0), (0, 1)):
            other = hubs.get((i + di, j + dj))
            if not other:
                continue
            ox, oy, oz = other[1]
            # the worst slope along the way
            worst = 0.0
            prev = y
            for k in range(1, 9):
                t = k / 8
                hy = height_at(h, x + (ox - x) * t, z + (oz - z) * t)
                worst = max(worst, abs(hy - prev) / (spacing / 8))
                prev = hy
            if worst < 0.45:
                w.connect(name, other[0], world.AI_ALL)
            elif worst < 0.9:
                w.connect(name, other[0], world.AI_SOLDIER)
    # the hangar deck: a row of hubs along the bay
    deck = []
    for k, dx in enumerate((-60.0, -20.0, 20.0, 60.0)):
        name = "Deck%d" % k
        w.hub(name, (SHIP_X + dx, SHIP_Y, SHIP_Z - 40.0), 14.0)
        deck.append(name)
    for a, b in zip(deck, deck[1:]):
        w.connect(a, b, world.AI_SOLDIER)


# ---------------------------------------------------------------- mission scripts

SIDES = {
    "c": dict(att="rep", deff="cis", lvl_att="SIDE\\\\rep.lvl", lvl_def="SIDE\\\\cis.lvl",
              att_units=["rep_inf_ep3_rifleman", "rep_inf_ep3_rocketeer", "rep_inf_ep3_engineer",
                         "rep_inf_ep3_sniper", "rep_inf_ep3_officer", "rep_inf_ep3_jettrooper"],
              def_units=["cis_inf_rifleman", "cis_inf_rocketeer", "cis_inf_engineer", "cis_inf_sniper",
                         "cis_inf_officer", "cis_inf_droideka"],
              att_hero="rep_hero_anakin", def_hero="cis_hero_grievous",
              att_fly="rep_fly_arc170fighter", def_fly="cis_fly_droidfighter"),
    "g": dict(att="all", deff="imp", lvl_att="SIDE\\\\all.lvl", lvl_def="SIDE\\\\imp.lvl",
              att_units=["all_inf_rifleman", "all_inf_rocketeer", "all_inf_engineer", "all_inf_sniper",
                         "all_inf_officer", "all_inf_wookiee"],
              def_units=["imp_inf_rifleman", "imp_inf_rocketeer", "imp_inf_engineer", "imp_inf_sniper",
                         "imp_inf_officer", "imp_inf_dark_trooper"],
              att_hero="all_hero_hansolo_tat", def_hero="imp_hero_bobafett",
              att_fly="all_fly_xwing", def_fly="imp_fly_tiefighter"),
}

SCRIPT = '''--
-- {code}{era}_con: Conquest on "Ground to Space", made by mods/mapgen/gts.py.
-- The side, unit and vehicle class names are the stock ones; change them here if the munge or
-- the game's log says one doesn't exist.
--

ScriptCB_DoFile("setup_teams")
ScriptCB_DoFile("ObjectiveConquest")

ATT = 1
DEF = 2

function ScriptPostLoad()
	conquest = ObjectiveConquest:New{{ teamATT = ATT, teamDEF = DEF, textATT = "game.modes.con",
		textDEF = "game.modes.con2", multiplayerRules = true }}
{posts}
	conquest:Start()
	EnableSPHeroRules()
end

function ScriptPreInit()
	SetWorldExtents(1100)
end

function ScriptInit()
	ReadDataFile("ingame.lvl")
	SetMaxFlyHeight(520)
	SetMaxPlayerFlyHeight(520)
	SetMemoryPoolSize("Music", 40)

	ReadDataFile("sound\\\\tat.lvl;tat2gcw")
	ReadDataFile("{lvl_att}", {att_list})
	ReadDataFile("{lvl_def}", {def_list})

	SetupTeams{{
		{att} = {{ team = ATT, units = 32, reinforcements = 250,
			soldier = {{ "{au0}", 9, 25 }}, assault = {{ "{au1}", 1, 4 }}, engineer = {{ "{au2}", 1, 4 }},
			sniper = {{ "{au3}", 1, 4 }}, officer = {{ "{au4}", 1, 4 }}, special = {{ "{au5}", 1, 4 }} }},
		{deff} = {{ team = DEF, units = 32, reinforcements = 250,
			soldier = {{ "{du0}", 9, 25 }}, assault = {{ "{du1}", 1, 4 }}, engineer = {{ "{du2}", 1, 4 }},
			sniper = {{ "{du3}", 1, 4 }}, officer = {{ "{du4}", 1, 4 }}, special = {{ "{du5}", 1, 4 }} }},
	}}
	SetHeroClass(ATT, "{att_hero}")
	SetHeroClass(DEF, "{def_hero}")

	SetMemoryPoolSize("EntityFlyer", 12)
	SetMemoryPoolSize("CommandFlyer", 2)
	SetMemoryPoolSize("Obstacle", 600)
	SetMemoryPoolSize("PathNode", 512)
	SetMemoryPoolSize("TreeGridStack", 1024)
	SetMemoryPoolSize("AmmoCounter", 300)
	SetMemoryPoolSize("EnergyBar", 300)
	SetSpawnDelay(10.0, 0.25)

	-- the world, by its path in the AddOn folder rather than "dc:", so the custom modes
	-- (another AddOn) can run this script too
	ReadDataFile("..\\\\..\\\\AddOn\\\\{code}\\\\Data\\\\_lvl_pc\\\\{code}\\\\{code}.lvl", "{code}_conquest")
	SetDenseEnvironment("false")
	AddDeathRegion("deathregion")

	SetAttackingTeam(ATT)
	AddCameraShot(0.95, -0.25, 0.15, 0.04, 0.0, 180.0, -760.0)
	AddCameraShot(0.90, -0.10, 0.40, 0.05, -300.0, 260.0, 300.0)
end
'''


def mission_script(code, era):
    s = SIDES[era]
    posts = "\n".join('\tconquest:AddCommandPost(CommandPost:New{ name = "%s" })' % p[0]
                      for p in GROUND_POSTS + SHIP_POSTS)
    def listing(units, hero, fly):
        return ", ".join('"%s"' % u for u in units + [hero, fly])
    return SCRIPT.format(code=code, era=era, posts=posts, lvl_att=s["lvl_att"], lvl_def=s["lvl_def"],
                         att_list=listing(s["att_units"], s["att_hero"], s["att_fly"]),
                         def_list=listing(s["def_units"], s["def_hero"], s["def_fly"]),
                         att=s["att"], deff=s["deff"], att_hero=s["att_hero"], def_hero=s["def_hero"],
                         **{"au%d" % i: u for i, u in enumerate(s["att_units"])},
                         **{"du%d" % i: u for i, u in enumerate(s["def_units"])})


# ---------------------------------------------------------------- output

STOCK_WORLD = "TAT"     # the stock world whose terrain textures, sky and weather suit the valley


def build(out_dir, code="GTS", modtools=None, stock_world=STOCK_WORLD):
    """Write the map. With `modtools` (the Mod Tools folder), it takes its terrain textures, sky
    and weather from the stock world `stock_world` there (see stock.py)."""
    h = make_heights()
    t = build_terrain(h, code)
    w = build_world(code, h)
    root = os.path.join(out_dir, "data_" + code)
    report = []
    if modtools:
        import stock
        _replaced, report = stock.apply(modtools, stock_world, root, code, ("sand", "dirt", "rock"), t)
    world_dir = os.path.join(root, "Worlds", code, "world1")
    msh_dir = os.path.join(root, "Worlds", code, "msh")
    odf_dir = os.path.join(root, "Worlds", code, "odf")
    script_dir = os.path.join(root, "Common", "scripts", code)
    for d in (world_dir, msh_dir, odf_dir, script_dir):
        os.makedirs(d, exist_ok=True)

    def put(folder, name, data):
        with open(os.path.join(folder, name), "wb") as fh:
            fh.write(data if isinstance(data, bytes) else data.encode("ascii"))

    for name, text in w.files().items():
        put(world_dir, name, text)
    put(world_dir, code + ".ter", ter.write_ter(t))

    materials, mesh, collision = ship_mesh()
    for name, data in msh.prop_files(code.lower() + "_ship", materials, mesh, collision).items():
        put(odf_dir if name.endswith(".odf") else msh_dir, name, data)
    for name, data in make_textures(code).items():
        put(msh_dir, name, data)
    for era in ("c", "g"):
        put(script_dir, "%s%s_con.lua" % (code, era), mission_script(code, era))
    import modes
    for rel, text in modes.addon_files(code, "cg", "Ground to Space").items():
        os.makedirs(os.path.join(root, os.path.dirname(rel)), exist_ok=True)
        put(root, rel, text)
    build.report = report
    return h, t, w, root


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=os.path.join(HERE, "out"))
    parser.add_argument("--code", default="GTS", help="the map's three-letter code")
    parser.add_argument("--preview", action="store_true", help="also render preview images")
    parser.add_argument("--stock", metavar="MODTOOLS", help="use stock looks from the Mod Tools in this folder")
    parser.add_argument("--stock-world", default=STOCK_WORLD, help="which stock world (default %(default)s)")
    args = parser.parse_args()
    h, t, w, root = build(args.out, args.code.upper(), args.stock, args.stock_world.upper())
    print("wrote %s" % root)
    for line in build.report:
        print("  " + line)
    print("  terrain %d x %d at %.0f m (%.0f m across), heights %.0f to %.0f m"
          % (LENGTH, LENGTH, GRID, LENGTH * GRID, h.min(), h.max()))
    print("  %d objects, %d regions, %d paths, %d bot hubs, %d links"
          % (len(w.objects), len(w.regions), len(w.paths), len(w.hubs), len(w.connections)))
    if args.preview:
        for path in render(h, w, os.path.join(args.out, "preview")):
            print("  preview: %s" % path)


def render(h, w, out_dir):
    import preview
    preview.PALETTE = [preview.SAND, preview.DIRT, preview.ROCK]
    preview.ROCK_HEIGHT = (90.0, 60.0)
    preview.ROCK_SLOPE = (0.55, 0.3)
    preview.SUN = np.array([0.45, 0.8, 0.4]) / np.linalg.norm([0.45, 0.8, 0.4])
    sx, sy, sz = SHIP_X, SHIP_Y, SHIP_Z
    views = [
        ("view_3d.png", (520.0, 620.0, -1180.0), (-40.0, 140.0, 220.0),
         "Ground to Space: the valley, and the ship %d m above it" % sy, True),
        ("shot_valley.png", (260.0, 90.0, -640.0), (0.0, 240.0, 330.0),
         "Ground to Space: from the South Landing, looking up the valley", False),
        ("shot_hangar.png", (sx + 260.0, sy - 30.0, sz - 430.0), (sx - 20.0, sy + 20.0, sz - 30.0),
         "Ground to Space: a fighter's approach to the hangar", False),
        ("shot_stern.png", (sx - 620.0, sy + 90.0, sz - 260.0), (sx - 120.0, sy + 40.0, sz),
         "Ground to Space: the ship's stern, tower and engines", False),
        ("shot_mesa.png", (-300.0, 75.0, -330.0), (-560.0, 60.0, -160.0),
         "Ground to Space: the West Mesa's strata", False),
    ]
    return preview.render(h, w, out_dir, ship_world_parts(), views, grid=GRID, map_name="Ground to Space")


if __name__ == "__main__":
    main()
