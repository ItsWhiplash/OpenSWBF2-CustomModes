"""HTH, "Hoth": a 4 km frozen battlefield, Galactic Civil War.

    python mods/mapgen/hoth.py [--out DIR] [--code HTH] [--preview]

The Empire lands in the south and pushes north across snowfields, an ice lake and a ridge pass,
to a zig-zag trench line with gun bunkers, a shield generator and an ion cannon, and finally the
Rebel base: a bunker dug into the northern mountains, its hangar open to the plain. Nine command
posts: the Imperial landing, then eight Rebel ones, nearest first, which is Rush's 3, 3 and 2.

Writes a mod-tools map folder (data_HTH): see README.md. Coordinates are the game's, in metres:
X east, Y up, Z north.
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import msh  # noqa: E402
import ter  # noqa: E402
import world  # noqa: E402
from gts import smooth_noise, tga  # noqa: E402

LENGTH = 512          # terrain points per side
GRID = 8.0            # 4096 m across
HSCALE = 0.05

# command posts: (name, x, z, team, label); team 1 is the Empire (attacking), 2 the Rebels
POSTS = [
    ("cp1", 0.0, -1400.0, 1, "Imperial Landing"),
    ("cp2", -900.0, -520.0, 2, "Frozen Outpost"),
    ("cp3", 820.0, -380.0, 2, "Ice Lake"),
    ("cp4", 0.0, 120.0, 2, "Ridge Pass"),
    ("cp5", -430.0, 690.0, 2, "West Trench"),
    ("cp6", 430.0, 690.0, 2, "East Trench"),
    ("cp7", -620.0, 980.0, 2, "Shield Generator"),
    ("cp8", 700.0, 1020.0, 2, "Ion Cannon"),
    ("cp9", 0.0, 1260.0, 2, "Base Hangar"),
]

BASE = (0.0, 1290.0)          # the bunker's hangar centre (X, Z); its floor is at FLOOR
FLOOR = 40.0
TRENCH_Z = 700.0


def grid_coords():
    idx = np.arange(LENGTH)
    x = (idx - LENGTH / 2) * GRID
    z = -(idx - LENGTH / 2 + 1) * GRID
    return np.meshgrid(x, z)


def height_at(h, x, z):
    gx = min(max(x / GRID + LENGTH / 2, 0), LENGTH - 1.001)
    gy = min(max(-z / GRID + LENGTH / 2 - 1, 0), LENGTH - 1.001)
    x0, y0 = int(gx), int(gy)
    fx, fy = gx - x0, gy - y0
    top = h[y0][x0] * (1 - fx) + h[y0][x0 + 1] * fx
    bot = h[y0 + 1][x0] * (1 - fx) + h[y0 + 1][x0 + 1] * fx
    return top * (1 - fy) + bot * fy


def trench_line(X, Z):
    """Distance to the zig-zag trench running east-west at TRENCH_Z (with gaps)."""
    zig = TRENCH_Z + 25 * np.abs(((X / 60.0) % 2) - 1) * 2 - 25
    d = np.abs(Z - zig)
    gap = (np.abs(X) < 30) | (np.abs(np.abs(X) - 700) < 25)      # crossings at the centre and ends
    within = np.abs(X) < 1000
    return np.where(within & ~gap, d, 1e9)


def make_heights(seed=21):
    rng = np.random.default_rng(seed)
    X, Z = grid_coords()
    # rolling snowfields, with drifts
    h = 30.0 + 22.0 * smooth_noise(LENGTH, 8, rng) + 7.0 * smooth_noise(LENGTH, 30, rng) \
        + 2.0 * smooth_noise(LENGTH, 90, rng)

    # mountains: ridged noise (sharp crests), rising past a ragged edge all round, and closer in
    # behind the base in the north
    ridged = 1 - np.abs(2 * smooth_noise(LENGTH, 18, rng) - 1)
    ridged = 0.55 * ridged ** 2 + 0.3 * (1 - np.abs(2 * smooth_noise(LENGTH, 40, rng) - 1)) ** 2 \
        + 0.15 * smooth_noise(LENGTH, 6, rng)
    wobble = 0.06 * (smooth_noise(LENGTH, 9, rng) - 0.5)
    r_ell = np.hypot(X / 1800.0, (Z + 30) / 1650.0) + wobble
    ring = np.clip((r_ell - 0.95) / 0.14, 0, 1)
    north = np.clip((Z - 1330 - 70 * (smooth_noise(LENGTH, 11, rng) - 0.5)) / 220, 0, 1)
    rise = np.maximum(ring, north * np.clip((1250 - np.abs(X)) / 250, 0.6, 1))
    h += rise ** 1.6 * (140 + 360 * ridged)

    # the ridge across the middle, with a pass at the centre
    ridge = np.exp(-((Z - 120 - 80 * np.sin(X / 400.0)) / 90.0) ** 2) * 55
    ridge *= np.clip(np.abs(X) / 140.0, 0, 1) ** 2               # the pass
    ridge *= np.clip((1500 - np.abs(X)) / 300.0, 0, 1)
    h += ridge

    # rock and ice outcrops for cover across the plain: low mounds, and some tall spires
    for k in range(40):
        cx, cz = rng.uniform(-1500, 1500), rng.uniform(-1400, 520)
        if min(math.hypot(cx - p[1], cz - p[2]) for p in POSTS) < 140 or abs(cz - TRENCH_Z) < 80:
            continue
        if k % 4 == 0:
            r, tall = rng.uniform(10, 18), rng.uniform(22, 40)       # a spire
            d2 = ((X - cx) ** 2 + (Z - cz) ** 2) / (r * r)
            h += tall * np.clip(1 - d2, 0, 1) ** 0.6
        else:
            r, tall = rng.uniform(18, 45), rng.uniform(6, 16)
            h += np.exp(-(((X - cx) ** 2 + (Z - cz) ** 2) / (r * r))) * tall

    # flat ground: the landing zone, the lake (frozen flat), the outpost knoll
    def flatten(cx, cz, rad, level, blend=60.0):
        nonlocal h
        d = np.hypot(X - cx, Z - cz)
        w = np.clip((rad + blend - d) / blend, 0, 1)
        h = h * (1 - w) + level * w
    flatten(0, -1400, 130, 30)
    flatten(820, -380, 200, 26, 80)
    flatten(-900, -520, 70, 44, 50)
    for _name, x, z, *_ in POSTS[3:8]:
        flatten(x, z, 45, height_level(h, X, Z, x, z), 40)

    # the base: a terrace cut into the mountain foot for the bunker, and a flat apron before it
    bx, bz = BASE
    apron = (np.abs(X - bx) < 260) & (Z > bz - 260) & (Z < bz + 90)
    h = np.where(apron, FLOOR, h)
    d = np.maximum(np.abs(X - bx) - 260, np.maximum((bz - 260) - Z, 0))
    h = np.where(~apron & (d < 60) & (Z < bz + 90), h * (d / 60) + FLOOR * (1 - d / 60), h)

    # the trench: 3.5 m deep, 6 m wide
    t = trench_line(X, Z)
    h -= 3.5 * np.clip(1 - (t - 3) / 2, 0, 1)
    return h


def height_level(h, X, Z, x, z):
    gx = int(x / GRID + LENGTH / 2)
    gy = int(-z / GRID + LENGTH / 2 - 1)
    return float(h[gy][gx])


def texture_weights(h):
    """snow (0) on the flats, packed snow (1) on slopes and the trench, ice (2) on the lake,
    rock (3) on cliffs and the high mountains."""
    X, Z = grid_coords()
    gz, gx = np.gradient(h, GRID)
    slope = np.hypot(gx, gz)
    # snow holds wherever the slope is gentle, even high up: rock only on steep faces
    rock = np.clip((slope - 0.95) / 0.4, 0, 1)
    lake = np.clip((210 - np.hypot(X - 820, Z + 380)) / 30, 0, 1) * (1 - rock)
    packed = np.clip((slope - 0.15) / 0.25, 0, 1)
    packed = np.maximum(packed, np.clip(1 - (trench_line(X, Z) - 4) / 4, 0, 1))
    apron = (np.abs(X - BASE[0]) < 260) & (Z > BASE[1] - 260) & (Z < BASE[1] + 90)
    packed = np.where(apron, 1.0, packed) * (1 - rock) * (1 - lake)
    snow = np.clip(1 - rock - lake - packed, 0, 1)
    return [np.clip(w * 255 + 0.5, 0, 255).astype(np.uint8) for w in (snow, packed, lake, rock)]


def build_terrain(h, code):
    t = ter.Terrain(LENGTH, HSCALE, GRID)
    t.height_map = np.clip(np.round(h / HSCALE), -32768, 32767).astype(int).tolist()
    names = ("snow", "packed", "ice", "rock")
    scales = (0.03, 0.04, 0.02, 0.03)
    for i, (name, scale) in enumerate(zip(names, scales)):
        t.texture_names[i] = "%s_%s" % (code.lower(), name)
        t.texture_scales[i] = scale
    for i, w in enumerate(texture_weights(h)):
        t.weights[i] = w.tolist()
    gz, gx = np.gradient(h, GRID)
    n = np.dstack((-gx, np.ones_like(h), -gz))
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    sun = np.array([0.35, 0.55, 0.5])
    sun /= np.linalg.norm(sun)
    lit = np.clip(0.55 + 0.5 * (n @ sun), 0, 1)
    v = (lit * 255).astype(np.uint32)
    t.light_map = (0xFF000000 | (v << 16) | (v << 8) | np.minimum(v + 12, 255)).tolist()
    return t


# ---------------------------------------------------------------- structures (block models)
# Each structure is parts: (name, polygons, material, colour, glows, collides), in its own frame
# (Y up from its base, its front facing -Z). Material 0 is the plating, 1 the glowing lights.

WALL = (0.80, 0.82, 0.86)
TRIM = (0.55, 0.58, 0.63)
LAMP = (1.0, 0.94, 0.78)
SHIELD_GLOW = (0.55, 0.85, 1.0)


def base_bunker():
    """The Rebel base: a bunker under a vaulted roof, its 140 x 28 m hangar open to the south."""
    import math
    import shapes as sh
    shell = []
    shell += sh.box((-150, 0, 0), (-70, 46, 120), faces="xyYzZ")      # west block
    shell += sh.box((70, 0, 0), (150, 46, 120), faces="XyYzZ")        # east block
    shell += sh.box((-70, 28, 0), (70, 46, 120), faces="YzZ")         # over the hangar
    shell += sh.box((-70, 0, 60), (70, 28, 120), faces="Z")           # the hangar's back
    shell += sh.box((-70, -2, 0), (70, 0, 60), faces="z")             # the floor's edge
    # a vaulted roof along the bunker: half-round sections
    arch = [(70 + 34 * math.cos(math.pi * k / 10), 46 + 22 * math.sin(math.pi * k / 10)) for k in range(11)]
    shell += sh.loft([(-140, arch), (140, arch)])
    shell += sh.box((-160, 0, 10), (-150, 30, 110))                   # buttresses
    shell += sh.box((150, 0, 10), (160, 30, 110))
    parts = [("shell", shell, 0, WALL, False, True)]
    # the blast doors, drawn back to either side of the opening, and the frame
    trim = sh.box((-76, 0, -6), (-70, 46, 4)) + sh.box((70, 0, -6), (76, 46, 4)) + sh.box((-76, 28, -6), (76, 34, 4))
    trim += sh.box((-90, 0, -4), (-76, 28, 2)) + sh.box((76, 0, -4), (90, 28, 2))
    parts.append(("trim", trim, 0, TRIM, False, True))
    # inside: the lit floor, walls and back, a darker ceiling
    bay = sh.box((-70, -2, 0), (70, 0, 60), faces="Y") + sh.box((-70, 0, 60), (70, 28, 120), faces="z")
    bay += sh.box((-150, 0, 0), (-70, 28, 60), faces="X") + sh.box((70, 0, 0), (150, 28, 60), faces="x")
    parts.append(("bay", bay, 0, (0.70, 0.66, 0.58), True, True))
    parts.append(("bay ceiling", sh.box((-70, 28, 0), (70, 30, 60), faces="y"), 0, (0.34, 0.34, 0.36), True, True))
    lamps = []
    for k in range(4):
        lamps += sh.box((-64, 27.4, 6 + k * 14), (64, 28, 8 + k * 14), faces="y")
    lamps += sh.box((-70, 34, -6.4), (70, 35.2, -6), faces="z")
    parts.append(("lamps", lamps, 1, LAMP, True, False))
    # a dish antenna on the roof
    dish = sh.frustum(-110, 60, 3, 2, 46, 62, sides=8) + sh.dome(-110, 70, 60, 10, rings=3, sides=14, lower=True)
    parts.append(("dish", dish, 0, TRIM, False, False))
    return parts


def shield_generator():
    """A dome on a drum, a glowing ring round its waist, and a mast with a dish."""
    import shapes as sh
    body = sh.frustum(0, 0, 26, 24, 0, 6, sides=24) + sh.frustum(0, 0, 21, 21, 6, 10, sides=24, top=False)
    body += sh.dome(0, 10, 0, 21, rings=7, sides=24)
    body += sh.frustum(0, 0, 2.2, 1.4, 30, 58, sides=8)
    dish = sh.dome(0, 62, 0, 7, rings=3, sides=12, lower=True)
    ring = sh.frustum(0, 0, 21.6, 21.6, 9.2, 10.6, sides=24, top=False)
    return [("body", body, 0, WALL, False, True), ("dish", dish, 0, TRIM, False, False),
            ("ring", ring, 1, SHIELD_GLOW, True, False)]


def ion_cannon():
    """A ball turret on a pedestal, its barrel raised to the sky."""
    import shapes as sh
    base = sh.frustum(0, 0, 22, 15, 0, 12, sides=20) + sh.frustum(0, 0, 9, 9, 12, 16, sides=16, top=False)
    ball = sh.dome(0, 30, 0, 17, rings=6, sides=20) + sh.dome(0, 30, 0, 17, rings=6, sides=20, lower=True)
    barrel = sh.tube((0, 34, -8), (0, 72, -48), 4.0, sides=12) + sh.tube((0, 72, -48), (0, 76, -52), 5.0, sides=12)
    muzzle = sh.tube((0, 76, -52), (0, 76.3, -52.3), 3.5, sides=12)
    return [("base", base, 0, TRIM, False, True), ("ball", ball, 0, WALL, False, True),
            ("barrel", barrel, 0, TRIM, False, True), ("muzzle", muzzle, 1, SHIELD_GLOW, True, False)]


def gun_bunker():
    """A round turret behind the trench, its gun facing the plain."""
    import shapes as sh
    body = sh.frustum(0, 0, 9, 7, 0, 4, sides=16) + sh.dome(0, 4, 0, 6, rings=3, sides=16)
    gun = sh.tube((0, 6.5, -4), (0, 7, -14), 0.8, sides=8) + sh.tube((2, 6.5, -4), (2, 7, -14), 0.8, sides=8)
    return [("body", body, 0, WALL, False, True), ("guns", gun, 0, TRIM, False, False)]


STRUCTURES = {
    "base": (base_bunker, "metal"),
    "shieldgen": (shield_generator, "metal"),
    "ioncannon": (ion_cannon, "metal"),
    "bunker": (gun_bunker, "stone"),
}


def structure_model(fn, texture):
    mesh, collision = msh.Mesh(), msh.Mesh()
    for name, polys, material, colour, glows, collides in fn():
        mesh.polys(material, polys, uv_scale=1 / 16.0)
        if collides:
            collision.polys(0, polys)
    return [msh.Material("plating", texture=texture), msh.Material("lights", texture="hth_glow", glow=True)], mesh, collision


def placements(h):
    """(structure, x, z, yaw) for every structure."""
    out = [("base", BASE[0], BASE[1] - 60, 0.0),
           ("shieldgen", -620.0, 1040.0, 0.0),
           ("ioncannon", 700.0, 1080.0, 0.0)]
    # gun bunkers behind the trench
    for x in (-900, -560, -260, 260, 560, 900):
        out.append(("bunker", float(x), TRENCH_Z + 40.0, 0.0))
    return out


def world_parts(h):
    """Every structure's parts in world space, for the preview."""
    import shapes as sh
    out = []
    for kind, x, z, yaw in placements(h):
        y = FLOOR if kind == "base" else height_at(h, x, z)
        for name, polys, material, colour, glows, collides in STRUCTURES[kind][0]():
            out.append((sh.offset(sh.rotate_y(polys, yaw), x, y, z), colour, glows))
    return out


# ---------------------------------------------------------------- textures

def make_textures(code, seed=5):
    rng = np.random.default_rng(seed)
    n = 128

    def noisy(base, amount, cells=16):
        v = smooth_noise(n, cells, rng) * amount + rng.random((n, n)) * amount * 0.3
        return [[tuple(int(np.clip(c + v[y][x] * 255 - amount * 128, 0, 255)) for c in base)
                 for x in range(n)] for y in range(n)]
    c = code.lower()
    out = {
        c + "_snow.tga": tga(n, n, noisy((236, 242, 250), 0.08)),
        c + "_packed.tga": tga(n, n, noisy((205, 214, 226), 0.14)),
        c + "_ice.tga": tga(n, n, noisy((176, 208, 232), 0.12, 6)),
        c + "_rock.tga": tga(n, n, noisy((100, 104, 112), 0.45, 24)),
    }
    plating = []
    for y in range(n):
        row = []
        for x in range(n):
            seam = (x % 32 in (0, 1)) or (y % 32 in (0, 1))
            g = 196 + int(rng.random() * 10) - (50 if seam else 0)
            row.append((g, g + 2, g + 8))
        plating.append(row)
    out[c + "_plating.tga"] = tga(n, n, plating)
    out[c + "_glow.tga"] = tga(8, 8, [[(255, 255, 255)] * 8 for _ in range(8)])
    return out


# ---------------------------------------------------------------- the world

def build_world(code, h):
    w = world.World(code)
    conquest = w.layer("conquest", modes=("conquest",))
    c = code.lower()

    for name, x, z, team, label in POSTS:
        y = FLOOR if name == "cp9" else height_at(h, x, z)
        w.command_post(name, (x, y, z), team, layer=conquest, label=label, capture=10.0, control=20.0)

    for i, (kind, x, z, yaw) in enumerate(placements(h)):
        y = FLOOR if kind == "base" else height_at(h, x, z)
        w.object("%s_%s" % (c, kind), "%s%d" % (kind, i + 1), (x, y, z), yaw=yaw)
    # lights in the base hangar, and at the shield generator and ion cannon
    bx, bz = BASE
    for k, dx in enumerate((-45.0, 0.0, 45.0)):
        w.light("hangar%d" % (k + 1), (bx + dx, FLOOR + 24.0, bz - 30.0), (1.0, 0.94, 0.80), 34.0)
    w.light("shieldgen", (-620.0, height_at(h, -620, 1040) + 14.0, 1040.0), (0.55, 0.85, 1.0), 40.0)
    w.light("ioncannon", (700.0, height_at(h, 700, 1080) + 20.0, 1080.0), (0.55, 0.85, 1.0), 30.0)

    # vehicles: walkers for the Empire at the landing, speeders and tauntauns for the Rebels
    def spawn(name, x, z, cp, imp="", all_=""):
        props = [("ControlZone", cp), ("SpawnTime", "20.0"), ("ExpireTimeEnemy", "25.0"),
                 ("ExpireTimeField", "40.0"), ("ClassImpATK", imp), ("ClassImpDEF", imp),
                 ("ClassAllATK", all_), ("ClassAllDEF", all_)]
        w.object("com_item_vehicle_spawn", name, (x, height_at(h, x, z) + 1, z), props=props, layer=conquest)
    spawn("atat1", -120, -1330, "cp1", imp="imp_walk_atat")
    spawn("atat2", 120, -1330, "cp1", imp="imp_walk_atat")
    for i, x in enumerate((-220, 220, 0)):
        spawn("atst%d" % (i + 1), x, -1250, "cp1", imp="imp_walk_atst")
    spawn("speeder1", -90, 1120, "cp9", all_="all_fly_snowspeeder")
    spawn("speeder2", 90, 1120, "cp9", all_="all_fly_snowspeeder")
    spawn("tauntaun1", -430, 760, "cp5", all_="all_walk_tauntaun")
    spawn("tauntaun2", 430, 760, "cp6", all_="all_walk_tauntaun")

    w.boundary = [(1700 * math.cos(a), 1550 * math.sin(a) - 30) for a in [i * math.pi / 16 for i in range(32)]]
    build_planning(w, h)
    return w


def build_planning(w, h, spacing=80.0):
    hubs = {}
    steps = int(3400 / spacing)
    for i in range(-steps // 2, steps // 2 + 1):
        for j in range(-steps // 2, steps // 2 + 1):
            x, z = i * spacing, j * spacing
            if (x / 1700) ** 2 + ((z + 30) / 1550) ** 2 > 1:
                continue
            y = height_at(h, x, z)
            if y > 150:
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
            worst, prev = 0.0, y
            for k in range(1, 11):
                t = k / 10
                hy = height_at(h, x + (ox - x) * t, z + (oz - z) * t)
                worst = max(worst, abs(hy - prev) / (spacing / 10))
                prev = hy
            if worst < 0.4:
                w.connect(name, other[0], world.AI_ALL)
            elif worst < 0.85:
                w.connect(name, other[0], world.AI_SOLDIER)
    # the hangar floor, linked to the apron in front
    bx, bz = BASE
    inside = []
    for k, dx in enumerate((-45.0, 0.0, 45.0)):
        name = "Hangar%d" % k
        w.hub(name, (bx + dx, FLOOR, bz - 30), 14.0)
        inside.append(name)
    for a, b in zip(inside, inside[1:]):
        w.connect(a, b, world.AI_SOLDIER)
    apron = min(hubs.values(), key=lambda v: math.hypot(v[1][0] - bx, v[1][2] - (bz - 120)))
    w.connect(inside[1], apron[0], world.AI_SOLDIER)


# ---------------------------------------------------------------- the mission script

SCRIPT = '''--
-- {code}g_con: Conquest on "Hoth", made by mods/mapgen/hoth.py. The Empire attacks.
-- The side, unit and vehicle class names are the stock Hoth ones; change them here if the munge
-- or the game's log says one doesn't exist.
--

ScriptCB_DoFile("setup_teams")
ScriptCB_DoFile("ObjectiveConquest")

IMP = 1
ALL = 2
ATT = IMP
DEF = ALL

function ScriptPostLoad()
	conquest = ObjectiveConquest:New{{ teamATT = ATT, teamDEF = DEF, textATT = "game.modes.con",
		textDEF = "game.modes.con2", multiplayerRules = true }}
{posts}
	conquest:Start()
	EnableSPHeroRules()
end

function ScriptPreInit()
	SetWorldExtents(2200)
end

function ScriptInit()
	ReadDataFile("ingame.lvl")
	SetMaxFlyHeight(400)
	SetMaxPlayerFlyHeight(400)
	SetMemoryPoolSize("Music", 40)

	ReadDataFile("sound\\\\hot.lvl;hot1gcw")
	ReadDataFile("SIDE\\\\imp.lvl", "imp_inf_rifleman_snow", "imp_inf_rocketeer_snow", "imp_inf_engineer_snow",
		"imp_inf_sniper_snow", "imp_inf_officer", "imp_inf_dark_trooper", "imp_hero_darthvader",
		"imp_walk_atat", "imp_walk_atst")
	ReadDataFile("SIDE\\\\all.lvl", "all_inf_rifleman_snow", "all_inf_rocketeer_snow", "all_inf_engineer_snow",
		"all_inf_sniper_snow", "all_inf_officer_snow", "all_inf_wookiee_snow", "all_hero_luke_pilot",
		"all_fly_snowspeeder", "all_walk_tauntaun")

	SetupTeams{{
		imp = {{ team = IMP, units = 40, reinforcements = 300,
			soldier = {{ "imp_inf_rifleman_snow", 9, 25 }}, assault = {{ "imp_inf_rocketeer_snow", 1, 4 }},
			engineer = {{ "imp_inf_engineer_snow", 1, 4 }}, sniper = {{ "imp_inf_sniper_snow", 1, 4 }},
			officer = {{ "imp_inf_officer", 1, 4 }}, special = {{ "imp_inf_dark_trooper", 1, 4 }} }},
		all = {{ team = ALL, units = 40, reinforcements = 300,
			soldier = {{ "all_inf_rifleman_snow", 9, 25 }}, assault = {{ "all_inf_rocketeer_snow", 1, 4 }},
			engineer = {{ "all_inf_engineer_snow", 1, 4 }}, sniper = {{ "all_inf_sniper_snow", 1, 4 }},
			officer = {{ "all_inf_officer_snow", 1, 4 }}, special = {{ "all_inf_wookiee_snow", 1, 4 }} }},
	}}
	SetHeroClass(IMP, "imp_hero_darthvader")
	SetHeroClass(ALL, "all_hero_luke_pilot")

	ClearWalkers()
	AddWalkerType(1, 3)     -- AT-STs: one pair of legs
	AddWalkerType(2, 2)     -- AT-ATs: two pairs
	SetMemoryPoolSize("EntityWalker", 6)
	SetMemoryPoolSize("EntityFlyer", 6)
	SetMemoryPoolSize("CommandWalker", 2)
	SetMemoryPoolSize("Obstacle", 900)
	SetMemoryPoolSize("PathNode", 1024)
	SetMemoryPoolSize("TreeGridStack", 2048)
	SetMemoryPoolSize("AmmoCounter", 400)
	SetMemoryPoolSize("EnergyBar", 400)
	SetSpawnDelay(10.0, 0.25)

	ReadDataFile("dc:{code}\\\\{code}.lvl", "{code}_conquest")
	SetDenseEnvironment("false")

	SetAttackingTeam(ATT)
	AddCameraShot(0.95, -0.20, 0.20, 0.04, 0.0, 120.0, -1500.0)
	AddCameraShot(0.90, -0.15, -0.40, -0.06, 300.0, 140.0, 900.0)
end
'''


def mission_script(code):
    posts = "\n".join('\tconquest:AddCommandPost(CommandPost:New{ name = "%s" })' % p[0] for p in POSTS)
    return SCRIPT.format(code=code, posts=posts)


# ---------------------------------------------------------------- output

def build(out_dir, code="HTH"):
    h = make_heights()
    t = build_terrain(h, code)
    w = build_world(code, h)
    root = os.path.join(out_dir, "data_" + code)
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
    for kind, (fn, foley) in STRUCTURES.items():
        materials, mesh, collision = structure_model(fn, code.lower() + "_plating")
        for name, data in msh.prop_files("%s_%s" % (code.lower(), kind), materials, mesh, collision, foley).items():
            put(odf_dir if name.endswith(".odf") else msh_dir, name, data)
    for name, data in make_textures(code).items():
        put(msh_dir, name, data)
    put(script_dir, "%sg_con.lua" % code, mission_script(code))
    return h, t, w, root


def render(h, w, out_dir):
    import preview
    preview.PALETTE = [np.array([0.93, 0.95, 0.98]), np.array([0.80, 0.84, 0.90]), np.array([0.40, 0.42, 0.46])]
    preview.ROCK_HEIGHT = (100000.0, 1.0)
    preview.ROCK_SLOPE = (0.95, 0.4)
    preview.SUN = np.array([-0.35, 0.75, -0.55]) / np.linalg.norm([-0.35, 0.75, -0.55])   # low, from the south-west
    bx, bz = BASE
    bx, bz = BASE
    views = [
        ("view_3d.png", (900.0, 900.0, -2300.0), (-80.0, 60.0, 300.0),
         "Hoth: the whole battlefield from the Imperial side", True),
        ("shot_trench.png", (420.0, 70.0, 470.0), (0.0, 55.0, 1180.0),
         "Hoth: the trench line, with the shield generator, ion cannon and base beyond", False),
        ("shot_base.png", (bx + 150.0, FLOOR + 30.0, bz - 330.0), (bx, FLOOR + 22.0, bz - 40.0),
         "Hoth: the base hangar under the mountains", False),
        ("shot_shield.png", (-560.0, 70.0, 930.0), (-620.0, 45.0, 1040.0),
         "Hoth: the shield generator", False),
        ("shot_cannon.png", (760.0, 60.0, 980.0), (700.0, 70.0, 1080.0),
         "Hoth: the ion cannon", False),
        ("shot_landing.png", (120.0, 60.0, -1480.0), (-60.0, 50.0, -300.0),
         "Hoth: from the Imperial landing, the long march north", False),
    ]
    return preview.render(h, w, out_dir, world_parts(h), views, grid=GRID, map_name="Hoth")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=os.path.join(HERE, "out"))
    parser.add_argument("--code", default="HTH", help="the map's three-letter code")
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    h, t, w, root = build(args.out, args.code.upper())
    print("wrote %s" % root)
    print("  terrain %d x %d at %.0f m (%.0f m across), heights %.0f to %.0f m"
          % (LENGTH, LENGTH, GRID, LENGTH * GRID, h.min(), h.max()))
    print("  %d objects, %d regions, %d paths, %d bot hubs, %d links"
          % (len(w.objects), len(w.regions), len(w.paths), len(w.hubs), len(w.connections)))
    if args.preview:
        for path in render(h, w, os.path.join(args.out, "preview_" + args.code.lower())):
            print("  preview: %s" % path)


if __name__ == "__main__":
    main()
