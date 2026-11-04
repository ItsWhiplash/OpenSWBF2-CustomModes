#!/usr/bin/env python3
"""Tests for the map generator.

    python3 mods/mapgen/test_mapgen.py [--luac PATH] [--worldedit-sample FILE.TER]

--luac checks the mission scripts with a Lua 5.0 compiler (run_tests.sh builds the game's own);
--worldedit-sample reads a terrain WorldEdit wrote (its tests/data/world/test.TER).
"""
import argparse
import os
import re
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gts  # noqa: E402
import msh  # noqa: E402
import ter  # noqa: E402

failures = 0
passed = 0


def check(cond, what):
    global failures, passed
    if cond:
        passed += 1
    else:
        failures += 1
        print("FAIL [mapgen] " + what)


def test_terrain(sample):
    t = ter.Terrain(16, 0.01, 4.0)
    t.texture_names[0] = "white"
    t.height_map[3][5] = 1234
    t.weights[0][2][2] = 255
    t.foliage_map[1][2] = 5
    t.water_map[1][0] = True
    data = ter.write_ter(t)
    back = ter.read_ter(data)
    check(ter.write_ter(back) == data, "terrain round-trips byte for byte")
    check(back.height_map[3][5] == 1234 and back.weights[0][2][2] == 255, "heights and texture weights come back")
    check(back.foliage_map[1][2] == 5 and back.water_map[1][0], "foliage and water come back")
    check(data[:4] == b"TERR" and struct.unpack_from("<I", data, 4)[0] == 22, "TERR, version 22")
    check(len(data) == 184 + 1 + 32 * 32 + 68 * 16 + 32 * 16 + 12 + 16 * 16 * (2 + 4 + 4 + 16)
          + 4 * 4 * (2 + 2 + 4) + 256 * 512 + 262144 + 131072 + 8, "the size WorldEdit's writer gives")
    if sample:
        w = ter.read_ter(open(sample, "rb").read())
        hs = [v for row in w.height_map for v in row]
        check(w.length == 16 and w.texture_names[0] == "white" and min(hs) == 0 and max(hs) == 200,
              "WorldEdit's sample terrain reads as WorldEdit reads it")


def test_ship():
    materials, mesh, collision = gts.ship_mesh()
    data = msh.write_msh(materials, mesh, collision)
    tags = list(msh.read_chunks(data))
    check(len(tags) == 1 and tags[0][0] == "HEDR" and tags[0][2] == len(data), "one HEDR chunk, the whole file")
    inner = list(msh.read_chunks(data, tags[0][1], tags[0][2]))
    check([t for t, a, b in inner] == ["MSH2", "CL1L"], "MSH2 then CL1L")
    msh2 = list(msh.read_chunks(data, inner[0][1], inner[0][2]))
    check([t for t, a, b in msh2] == ["MATL", "MODL", "MODL", "MODL"], "materials, then root, geometry, collision")
    names = []
    for tag, a, b in msh2[1:]:
        kids = {t: (x, y) for t, x, y in msh.read_chunks(data, a, b)}
        names.append(data[kids["NAME"][0]:kids["NAME"][1]].split(b"\0")[0].decode())
        if "GEOM" in kids:
            for t, sa, sb in msh.read_chunks(data, *kids["GEOM"]):
                seg = {t2: (x, y) for t2, x, y in msh.read_chunks(data, sa, sb)}
                (count,) = struct.unpack_from("<i", data, seg["POSL"][0])
                (indices,) = struct.unpack_from("<i", data, seg["STRP"][0])
                idx = struct.unpack_from("<%dH" % indices, data, seg["STRP"][0] + 4)
                check(count <= 0x8000 and max(i & 0x7FFF for i in idx) < count, "indices within the segment")
    check(names == ["root", "geometry", "collision"], "node names")
    lo, hi = mesh.bounds()
    check(hi[0] - lo[0] > 600 and lo[1] < 0 < hi[1], "a ship over 600 m long, with the deck at its origin")
    files = msh.prop_files("gts_ship", materials, mesh, collision)
    check(b'ClassLabel   = "prop"' in files["gts_ship.odf"], "a prop class")


def test_world(out, luac):
    h, t, w, root = gts.build(out)
    world_dir = os.path.join(root, "Worlds", "GTS", "world1")
    files = {n: open(os.path.join(world_dir, n), "rb").read().decode() for n in os.listdir(world_dir)
             if not n.endswith(".ter")}
    for name in ("GTS.wld", "GTS.LDX", "GTS.PLN", "GTS.req", "GTS_conquest.lyr", "GTS_conquest.mrq"):
        check(name in files, name + " written")

    # every post's regions and spawn path exist, in its layer
    lyr = files["GTS_conquest.lyr"]
    rgn = files["GTS_conquest.RGN"]
    pth = files["GTS_conquest.PTH"]
    posts = re.findall(r'Object\("(cp\d)", "com_bldg_controlzone"', lyr)
    check(len(posts) == 7, "seven command posts (%d)" % len(posts))
    for cp in posts:
        check('Name("%s_capture")' % cp in rgn and 'Name("%s_control")' % cp in rgn, cp + " has its regions")
        check('Path("%s_spawn")' % cp in pth, cp + " has its spawn path")
        check('CaptureRegion("%s_capture")' % cp in lyr, cp + " points at its capture region")
    check("RegionCount(%d)" % rgn.count("Region(\"") in rgn, "RegionCount matches")
    check("PathCount(%d)" % pth.count("Path(\"") in pth, "PathCount matches")
    base = files["GTS.PTH"]
    check("PathCount(1)" in base and 'Path("boundary")' in base, "the boundary path")
    check('Object("ship", "gts_ship"' in files["GTS.wld"], "the ship is in the base layer")
    check('GameMode("conquest")\n{\n\tLayer(1);' in files["GTS.LDX"], "conquest uses its layer")

    # the bots' graph links real hubs
    pln = files["GTS.PLN"]
    hubs = set(re.findall(r'Hub\("([^"]+)"\)', pln))
    links = re.findall(r'Start\("([^"]+)"\);\s*End\("([^"]+)"\)', pln)
    check(len(hubs) > 300 and len(links) > 500, "a graph covering the valley (%d hubs, %d links)" % (len(hubs), len(links)))
    check(all(a in hubs and b in hubs for a, b in links), "every link joins two hubs")

    # posts stand on the ground, or on the deck
    for name, x, z, team, label in gts.GROUND_POSTS:
        y = gts.height_at(h, x, z)
        check(15 < y < 120, "%s on the valley floor or a mesa (%.0f m)" % (name, y))
    for obj in w.objects:
        if obj[2] in ("cp6", "cp7"):
            check(obj[3][1] == gts.SHIP_Y, obj[2] + " on the hangar deck")
    for layer, name, nodes, spline in w.paths:
        if name.endswith("_spawn") and not name.startswith(("cp6", "cp7")):
            for x, y, z in nodes:
                check(abs(gts.height_at(h, x, z) - y) < 6, "%s spawn point near the ground" % name)
                break

    # the hangar: the deck posts are inside the bay, under its ceiling
    for name, dx, dz, team, label in gts.SHIP_POSTS:
        check(gts.HANGAR[0] < dx < gts.HANGAR[1] and -gts.HANGAR_DEPTH < dz < 0, name + " inside the bay")

    # terrain matches its heights
    back = ter.read_ter(open(os.path.join(world_dir, "GTS.ter"), "rb").read())
    check(back.length == 256 and abs(back.height_map[128][128] * back.height_scale - h[128][128]) < 0.1,
          "the terrain file holds the heights")

    scripts = os.path.join(root, "Common", "scripts", "GTS")
    for era in ("c", "g"):
        path = os.path.join(scripts, "GTS%s_con.lua" % era)
        text = open(path).read()
        check('ReadDataFile("dc:GTS\\\\GTS.lvl", "GTS_conquest")' in text, "GTS%s_con loads the world" % era)
        check(all('name = "%s"' % p[0] in text for p in gts.GROUND_POSTS + gts.SHIP_POSTS), "every post in conquest")
        if luac:
            r = subprocess.run([luac, "-o", os.devnull, path], capture_output=True, text=True)
            check(r.returncode == 0, "GTS%s_con.lua compiles: %s" % (era, r.stderr.strip()))
    for tex in ("gts_sand.tga", "gts_dirt.tga", "gts_rock.tga", "gts_hull.tga"):
        data = open(os.path.join(root, "Worlds", "GTS", "msh", tex), "rb").read()
        check(data[2] == 2 and struct.unpack_from("<HH", data, 12) == (128, 128), tex + " is a 128x128 TGA")


def test_hoth(out, luac):
    import hoth
    h, t, w, root = hoth.build(out)
    world_dir = os.path.join(root, "Worlds", "HTH", "world1")
    lyr = open(os.path.join(world_dir, "HTH_conquest.lyr")).read()
    rgn = open(os.path.join(world_dir, "HTH_conquest.RGN")).read()
    pth = open(os.path.join(world_dir, "HTH_conquest.PTH")).read()
    posts = re.findall(r'Object\("(cp\d)", "com_bldg_controlzone"', lyr)
    check(posts == ["cp%d" % i for i in range(1, 10)], "Hoth: nine command posts")
    check(all('Name("%s_capture")' % cp in rgn and 'Path("%s_spawn")' % cp in pth for cp in posts),
          "Hoth: every post has its regions and spawn path")
    check(t.length == 512 and t.grid_scale * t.length == 4096, "Hoth: 4 km of terrain")
    # the hangar post is inside the bay: the bunker's front 60 m, between its side blocks
    bx, bz = hoth.BASE
    cp9 = [p for p in hoth.POSTS if p[0] == "cp9"][0]
    front = bz - 60
    check(abs(cp9[1] - bx) < 70 and front < cp9[2] < front + 60, "Hoth: cp9 is inside the hangar")
    check(all(abs(h[y][x] - hoth.FLOOR) < 0.01 for x, y in ((256, 95), (240, 98))), "Hoth: the base terrace is flat")
    for kind, x, z, yaw in hoth.placements(h):
        y = hoth.FLOOR if kind == "base" else hoth.height_at(h, x, z)
        check(20 < y < 120, "Hoth: %s at %.0f m stands on the plain" % (kind, y))
    for name, x, z, team, label in hoth.POSTS:
        y = hoth.FLOOR if name == "cp9" else hoth.height_at(h, x, z)
        check(20 < y < 120, "Hoth: %s on the plain (%.0f m)" % (name, y))
    spawns = re.findall(r'ControlZone\("(cp\d)"\)', lyr)
    check(len(spawns) == 9 and all(cp in posts for cp in spawns), "Hoth: vehicle spawns name real posts")
    pln = open(os.path.join(world_dir, "HTH.PLN")).read()
    hubs = set(re.findall(r'Hub\("([^"]+)"\)', pln))
    links = re.findall(r'Start\("([^"]+)"\);\s*End\("([^"]+)"\)', pln)
    check(all(a in hubs and b in hubs for a, b in links), "Hoth: every link joins two hubs")
    check(any("Hangar1" in (a, b) and not b.startswith("Hangar") for a, b in links), "Hoth: the hangar links to the plain")
    script = os.path.join(root, "Common", "scripts", "HTH", "HTHg_con.lua")
    text = open(script).read()
    check(all('name = "%s"' % p[0] in text for p in hoth.POSTS), "Hoth: every post in conquest")
    if luac:
        r = subprocess.run([luac, "-o", os.devnull, script], capture_output=True, text=True)
        check(r.returncode == 0, "Hoth: HTHg_con.lua compiles: %s" % r.stderr.strip())
    for kind in hoth.STRUCTURES:
        check(os.path.exists(os.path.join(root, "Worlds", "HTH", "msh", "hth_%s.msh" % kind)) and
              os.path.exists(os.path.join(root, "Worlds", "HTH", "odf", "hth_%s.odf" % kind)), "Hoth: %s model" % kind)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--luac")
    parser.add_argument("--worldedit-sample")
    args = parser.parse_args()
    test_terrain(args.worldedit_sample)
    test_ship()
    with tempfile.TemporaryDirectory() as tmp:
        test_world(tmp, args.luac)
    with tempfile.TemporaryDirectory() as tmp:
        test_hoth(tmp, args.luac)
    print("mapgen: %d passed, %d failed" % (passed, failures))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
