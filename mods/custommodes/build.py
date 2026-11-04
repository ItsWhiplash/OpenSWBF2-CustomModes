#!/usr/bin/env python3
"""Builds the custom modes AddOn folder for OpenSWBF2.

    python mods/custommodes/build.py [--out DIR] [--luac PATH] [--only tat2g,nab2c] [--modes pay,rush]

Each mode is a folder under maps/ (maps/pay, maps/rush, maps/horde) with one script per stock map, named by
the map and era (tat2g.lua makes tat2g_pay or tat2g_rush). Writes DIR/CUSTOMMODES (default:
mods/custommodes/out/CUSTOMMODES):
    addme.script              registers the modes on the stock maps
    data/_lvl_pc/mission.lvl  the shared scripts, and one sub-level per mission

Copy CUSTOMMODES into the game's AddOn folder (GameData/AddOn) on every machine, or into the Docker
server's addons folder (its launcher hands it to players who join).

The scripts are stored as Lua source: the game compiles them as it loads them, so this needs no
compiler. --luac (the LuaCompiler.exe this repo builds, or any Lua 5.0 luac) checks their syntax
first.
"""
import argparse
import os
import re
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "scripts")
MAPS = os.path.join(HERE, "maps")
FOLDER = "CUSTOMMODES"
SHARED = ("custommode_mission", "objectivepayload", "objectiverush", "objectivehorde")


def pbl_hash(text):
    """The engine's PblHash: FNV-1a over the lower-cased bytes."""
    value = 0x811C9DC5
    for byte in text.encode("ascii"):
        value ^= byte | 0x20
        value = (value * 0x01000193) & 0xFFFFFFFF
    return value


def chunk(tag, payload):
    if isinstance(tag, str):
        tag = tag.encode("ascii")
    out = tag + struct.pack("<I", len(payload)) + payload
    return out + b"\0" * (-len(out) % 4)


def script(name, source):
    body = chunk("NAME", name.lower().encode("ascii") + b"\0")
    body += chunk("INFO", b"\x01")
    body += chunk("BODY", source)
    return chunk("scr_", body)


def read(path):
    with open(path, "rb") as f:
        return f.read()


def missions(only, modes):
    """(map code, mode) pairs, such as ("tat2g", "rush")."""
    found = []
    for mode in sorted(os.listdir(MAPS)):
        folder = os.path.join(MAPS, mode)
        if not os.path.isdir(folder) or (modes and mode not in modes):
            continue
        found += [(f[:-4], mode) for f in sorted(os.listdir(folder)) if f.endswith(".lua")]
    if only:
        wanted = set(c.strip().lower() for c in only.split(","))
        unknown = wanted - set(code for code, _ in found)
        if unknown:
            sys.exit("no map config for: " + ", ".join(sorted(unknown)))
        found = [m for m in found if m[0] in wanted]
    return found


def map_path(code, mode):
    return os.path.join(MAPS, mode, code + ".lua")


def check_syntax(luac, sources):
    with tempfile.TemporaryDirectory() as tmp:
        for name, source in sources:
            path = os.path.join(tmp, name + ".lua")
            with open(path, "wb") as f:
                f.write(source)
            result = subprocess.run([luac, "-o", os.path.join(tmp, "out.bin"), path],
                                    capture_output=True, text=True)
            if result.returncode:
                sys.exit("syntax error in %s:\n%s" % (name, result.stderr or result.stdout))


def mission_source(code, mode):
    return b'ScriptCB_DoFile("custommode_mission")\n' + read(map_path(code, mode))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=os.path.join(HERE, "out"))
    parser.add_argument("--luac", help="a Lua 5.0 compiler, to check syntax first")
    parser.add_argument("--only", help="comma-separated map codes, such as tat2g,nab2c")
    parser.add_argument("--modes", help="comma-separated modes, such as pay,rush (default: all)")
    args = parser.parse_args()

    found = missions(args.only, args.modes and set(m.strip() for m in args.modes.split(",")))
    if not found:
        sys.exit("no maps")

    shared = [(n, read(os.path.join(SCRIPTS, n + ".lua"))) for n in SHARED]
    per_mission = [("%s_%s" % (c, m), mission_source(c, m)) for c, m in found]
    listing = "CUSTOMMODE_MISSIONS = { %s }\n" % ", ".join('{ "%s", "%s" }' % cm for cm in found)
    addme = listing.encode("ascii") + read(os.path.join(SCRIPTS, "addme.lua"))

    if args.luac:
        check_syntax(args.luac, shared + per_mission + [("addme", addme)])

    # mission.lvl: the shared scripts at the top level (read for every mission), then a lvl_
    # chunk holding one sub-level per mission, keyed by the hash of the mission's name
    top = b"".join(script(n, s) for n, s in shared)
    subs = b"".join(chunk(struct.pack("<I", pbl_hash(n)), script(n, s)) for n, s in per_mission)
    mission_lvl = chunk("ucfb", top + chunk("lvl_", subs))
    addme_script = chunk("ucfb", script("addme", addme))

    root = os.path.join(args.out, FOLDER)
    lvl_dir = os.path.join(root, "data", "_lvl_pc")
    os.makedirs(lvl_dir, exist_ok=True)
    with open(os.path.join(root, "addme.script"), "wb") as f:
        f.write(addme_script)
    with open(os.path.join(lvl_dir, "mission.lvl"), "wb") as f:
        f.write(mission_lvl)

    print("built %s with %d missions" % (root, len(found)))
    for mode in sorted(set(m for _, m in found)):
        print("  %s: %s" % (mode, ", ".join(c for c, m in found if m == mode)))
    recording = [c for c, m in found
                 if m == "pay" and re.search(rb"track\s*=\s*\{\s*\}", read(map_path(c, m)))]
    if recording:
        print("payload maps with no track yet (these record one): " + ", ".join(recording))


if __name__ == "__main__":
    main()
