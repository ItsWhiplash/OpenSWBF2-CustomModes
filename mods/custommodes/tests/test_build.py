#!/usr/bin/env python3
"""Checks build.py's output by reading it back the way the engine does.

    python3 test_build.py OUT_DIR    (run_tests.sh passes the folder it built into)

- mission.lvl's Locl chunks: RedLocalizeDB::Read picks the one named after the game's language
  and ReadMasterLocalizeFile walks (hash, length, text) entries to a zero length; every key in
  text.py must come back with its text, by PblHash, in every language.
- --gamedata: the addon's core.lvl carries the game's own Locl chunks, then ours.
"""
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import build  # noqa: E402
import text  # noqa: E402

failures = 0


def check(cond, what):
    global failures
    if not cond:
        failures += 1
        print("FAIL [build] " + what)


def children(data, start, end):
    pos = start
    while pos + 8 <= end:
        tag = data[pos:pos + 4]
        size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
        yield tag, pos + 8, pos + 8 + size
        pos += 8 + size
        pos += -pos % 4


def read_locl(data, start, end):
    """(language, {hash: text}) as the engine reads one Locl chunk."""
    name, entries = None, {}
    for tag, a, b in children(data, start, end):
        if tag == b"NAME":
            name = data[a:b].split(b"\0")[0].decode()
        elif tag == b"BODY":
            pos = a
            while True:
                h, length = struct.unpack("<IH", data[pos:pos + 6])
                if length == 0:
                    break
                raw = data[pos + 6:pos + length]
                txt = raw.decode("utf-16-le").split("\0")[0]
                entries.setdefault(h, txt)
                pos += length
                check(length % 4 == 0, "entries are 4-byte aligned")
            check(pos < b, "the body ends with an empty entry")
    return name, entries


def top_locls(data):
    tag, a, b = next(children(data, 0, len(data)))
    check(tag == b"ucfb" and b == len(data), "a ucfb file")
    return [read_locl(data, x, y) for t, x, y in children(data, a, b) if t == b"Locl"]


def main():
    out = sys.argv[1]
    texts = text.table()
    mission = open(os.path.join(out, "CUSTOMMODES", "data", "_lvl_pc", "mission.lvl"), "rb").read()
    locls = top_locls(mission)
    check(sorted(n for n, _ in locls) == sorted(build.LANGUAGES), "one text block per language")
    for lang, entries in locls:
        check(len(entries) == len(texts), "%s: every key (%d of %d)" % (lang, len(entries), len(texts)))
        for key, value in texts.items():
            if entries.get(build.pbl_hash(key)) != value:
                check(False, "%s: %s reads back" % (lang, key))
                break
    check(build.pbl_hash("Defend") == 0x4FED19C1, "PblHash matches the engine's")
    check(not os.path.exists(os.path.join(out, "CUSTOMMODES", "data", "_lvl_pc", "core.lvl")),
          "no core.lvl without --gamedata")

    # --gamedata with a stand-in for the game's core.lvl: a font chunk and an English block
    with tempfile.TemporaryDirectory() as tmp:
        game = os.path.join(tmp, "GameData")
        os.makedirs(os.path.join(game, "data", "_lvl_pc"))
        base_body = struct.pack("<IH", build.pbl_hash("game.thing"), 20) + "Thing".encode("utf-16-le") \
            + b"\0" * 4 + b"\0" * 8
        base = build.chunk("ucfb", build.chunk("font", b"x" * 5)
                           + build.chunk("Locl", build.chunk("NAME", b"english\0") + build.chunk("BODY", base_body)))
        with open(os.path.join(game, "data", "_lvl_pc", "core.lvl"), "wb") as f:
            f.write(base)
        built = os.path.join(tmp, "out")
        subprocess.run([sys.executable, os.path.join(ROOT, "build.py"), "--out", built, "--gamedata", game,
                        "--only", "tat2g"], check=True, capture_output=True)
        core = open(os.path.join(built, "CUSTOMMODES", "data", "_lvl_pc", "core.lvl"), "rb").read()
        blocks = top_locls(core)
        check(blocks[0][0] == "english" and blocks[0][1].get(build.pbl_hash("game.thing")) == "Thing",
              "the game's text comes first")
        check(len(blocks) == 1 + len(build.LANGUAGES), "then ours, every language")
        check(b"font" not in core, "only the text is copied")

    print("build: %s" % ("ok" if not failures else "%d failed" % failures))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
