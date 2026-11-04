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

    # the mountain ring past 820 m from the centre
    r = np.hypot(X, Z)
    ring = np.clip((r - 820) / 180, 0, 1)
    h += ring ** 1.5 * (110 + 90 * smooth_noise(LENGTH, 10, rng))

    # three mesas
    h = np.maximum(h, 20 + mesa(X, Z, -520, -180, 110, 45, 0))      # west, ramp east
    h = np.maximum(h, 20 + mesa(X, Z, 520, -120, 100, 55, 180))     # east, ramp west
    h = np.maximum(h, 20 + mesa(X, Z, -380, 420, 80, 70, -30))      # north-west lookout

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

# The hull, from boxes, in the ship's own frame: X along the ship (bow at +X), Y up from the deck,
# Z across. The hangar is a 160 x 30 m bay open on the -Z (south) side: deck at Y 0, ceiling at 30.
HANGAR = (-80.0, 80.0)        # X extent
HANGAR_DEPTH = 80.0           # from the -Z side in to Z = 0


def ship_boxes():
    boxes = []
    # hull segments, wide at the stern, narrowing to the bow: (x0, x1, half width, bottom, top)
    segments = [(-300, -160, 90, -25, 45), (-160, -80, 85, -25, 42), (80, 180, 70, -22, 36),
                (180, 260, 45, -18, 28), (260, 320, 20, -12, 18)]
    for x0, x1, w, y0, y1 in segments:
        boxes.append(((x0, y0, -w), (x1, y1, w)))
    # the hangar section: full hull behind the bay, a slab under the deck, a slab over the ceiling
    hx0, hx1 = HANGAR
    boxes.append(((hx0, -25, 0), (hx1, 40, 85)))
    boxes.append(((hx0, -25, -85), (hx1, 0, 0)))          # floor: its top face is the deck
    boxes.append(((hx0, 30, -85), (hx1, 40, 0)))          # ceiling slab
    # superstructure and bridge
    boxes.append(((-240, 45, -28), (-150, 95, 28)))
    boxes.append(((-225, 95, -45), (-185, 112, 45)))
    # engines
    for z in (-55, 0, 55):
        boxes.append(((-335, -10, z - 22), (-300, 30, z + 22)))
    # surface detail: plating blocks, turrets and antennae on the upper hull (fixed seed)
    import random
    rng = random.Random(11)
    for x0, x1, w, y0, y1 in segments + [(hx0, hx1, 85, -25, 40)]:
        for _ in range(int((x1 - x0) / 14)):
            bx = rng.uniform(x0 + 4, x1 - 14)
            bz = rng.uniform(-w + 6, w - 14)
            size = rng.choice((6, 8, 10, 14))
            tall = rng.choice((2, 3, 4, 6, 10))
            boxes.append(((bx, y1, bz), (bx + size, y1 + tall, bz + size * rng.uniform(0.5, 1.5))))
    return boxes


def ship_mesh():
    hull = msh.Material("hull", texture="gts_hull")
    mesh = msh.Mesh()
    collision = msh.Mesh()
    for lo, hi in ship_boxes():
        mesh.box(0, lo, hi, uv_scale=1 / 32.0)
        collision.box(0, lo, hi)
    return [hull], mesh, collision


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

    # the ship, in the base layer so every mode has it
    w.object(code.lower() + "_ship", "ship", (SHIP_X, SHIP_Y, SHIP_Z))

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

	ReadDataFile("dc:{code}\\\\{code}.lvl", "{code}_conquest")
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

def build(out_dir, code="GTS"):
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

    materials, mesh, collision = ship_mesh()
    for name, data in msh.prop_files(code.lower() + "_ship", materials, mesh, collision).items():
        put(odf_dir if name.endswith(".odf") else msh_dir, name, data)
    for name, data in make_textures(code).items():
        put(msh_dir, name, data)
    for era in ("c", "g"):
        put(script_dir, "%s%s_con.lua" % (code, era), mission_script(code, era))
    return h, t, w, root


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=os.path.join(HERE, "out"))
    parser.add_argument("--code", default="GTS", help="the map's three-letter code")
    parser.add_argument("--preview", action="store_true", help="also render preview images")
    args = parser.parse_args()
    h, t, w, root = build(args.out, args.code.upper())
    print("wrote %s" % root)
    print("  terrain %d x %d at %.0f m (%.0f m across), heights %.0f to %.0f m"
          % (LENGTH, LENGTH, GRID, LENGTH * GRID, h.min(), h.max()))
    print("  %d objects, %d regions, %d paths, %d bot hubs, %d links"
          % (len(w.objects), len(w.regions), len(w.paths), len(w.hubs), len(w.connections)))
    if args.preview:
        import preview
        for path in preview.render(h, w, os.path.join(args.out, "preview"), ship_boxes(), (SHIP_X, SHIP_Y, SHIP_Z)):
            print("  preview: %s" % path)


if __name__ == "__main__":
    main()
