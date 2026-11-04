#!/usr/bin/env python3
"""Builds the Payload AddOn folder for OpenSWBF2.

    python mods/payload/build.py [--out DIR] [--luac PATH] [--only tat2g,nab2c]

Writes DIR/PAYLOAD (default: mods/payload/out/PAYLOAD):
    addme.script           registers the Payload mode on the stock maps
    data/_lvl_pc/mission.lvl  the shared payload scripts, and one sub-level per mission

Copy PAYLOAD into the game's AddOn folder (GameData/AddOn) on every machine, or into the Docker
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
FOLDER = "PAYLOAD"


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


def missions(only):
    codes = sorted(f[:-4] for f in os.listdir(MAPS) if f.endswith(".lua"))
    if only:
        wanted = set(c.strip().lower() for c in only.split(","))
        unknown = wanted - set(codes)
        if unknown:
            sys.exit("no map config for: " + ", ".join(sorted(unknown)))
        codes = [c for c in codes if c in wanted]
    return codes


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


def mission_source(code):
    return (b'ScriptCB_DoFile("payload_mission")\n' + read(os.path.join(MAPS, code + ".lua")))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=os.path.join(HERE, "out"))
    parser.add_argument("--luac", help="a Lua 5.0 compiler, to check syntax first")
    parser.add_argument("--only", help="comma-separated map codes, such as tat2g,nab2c")
    args = parser.parse_args()

    codes = missions(args.only)
    if not codes:
        sys.exit("no maps")

    shared = [(n, read(os.path.join(SCRIPTS, n + ".lua"))) for n in ("objectivepayload", "payload_mission")]
    per_mission = [(c + "_pay", mission_source(c)) for c in codes]
    listing = "PAYLOAD_MISSIONS = { %s }\n" % ", ".join('"%s"' % c for c in codes)
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

    recording = [c for c in codes if re.search(rb"track\s*=\s*\{\s*\}", read(os.path.join(MAPS, c + ".lua")))]
    print("built %s with %d missions: %s" % (root, len(codes), ", ".join(c + "_pay" for c in codes)))
    if recording:
        print("no track yet (these record one): " + ", ".join(recording))


if __name__ == "__main__":
    main()
