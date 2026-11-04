#!/usr/bin/env python3
"""Prints the generated maps' command posts as Lua (MapgenPosts), for the custom mode tests:
{ name, x, y, z, team } for each, by map and era code."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gts  # noqa: E402
import hoth  # noqa: E402


def main():
    out = ["MapgenPosts = {"]
    hg = gts.make_heights()
    gpost = [(n, x, gts.height_at(hg, x, z), z, t) for n, x, z, t, label in gts.GROUND_POSTS]
    gpost += [(n, gts.SHIP_X + dx, gts.SHIP_Y, gts.SHIP_Z + dz, t) for n, dx, dz, t, label in gts.SHIP_POSTS]
    hh = hoth.make_heights()
    hpost = [(n, x, hoth.FLOOR if n == "cp9" else hoth.height_at(hh, x, z), z, t) for n, x, z, t, label in hoth.POSTS]
    for code, posts in (("gtsc", gpost), ("gtsg", gpost), ("hthg", hpost)):
        out.append("\t%s = {" % code)
        for n, x, y, z, t in posts:
            out.append('\t\t{ "%s", %.1f, %.1f, %.1f, %d },' % (n, x, y, z, t))
        out.append("\t},")
    out.append("}")
    print("\n".join(out))


if __name__ == "__main__":
    main()
