#!/usr/bin/env python3
"""Turns a recorded payload route into a track for a map's config.

    python mods/payload/extract_track.py BattlefrontII.log [--every 1] [--reverse]

Recording: start a Payload mission whose map has no track yet (it records instead), walk the
route from the attackers' start to the finish, then quit. The game's log has a line for every
point (run the game with -log payload.log, or look in its usual log). This prints the track
and the command posts found, ready to paste into mods/payload/maps/<map>.lua.
"""
import argparse
import re
import sys

POINT = re.compile(r"PAYLOAD_TRACK (\d+) \{ (-?[\d.]+), (-?[\d.]+), (-?[\d.]+) \}")
CP = re.compile(r"PAYLOAD_CP (\S+) team=(\d+) at \{ (-?[\d.]+), (-?[\d.]+), (-?[\d.]+) \}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("log")
    parser.add_argument("--every", type=int, default=1, help="keep every Nth point (the ends are always kept)")
    parser.add_argument("--reverse", action="store_true", help="the route was walked finish to start")
    args = parser.parse_args()

    points, cps = [], {}
    with open(args.log, "r", errors="replace") as f:
        for line in f:
            if "RECORDING" in line and "payload" in line:
                points, cps = [], {}  # keep only the last recording
            m = POINT.search(line)
            if m:
                points.append(tuple(float(v) for v in m.groups()[1:]))
                continue
            m = CP.search(line)
            if m:
                cps[m.group(1)] = (int(m.group(2)), tuple(float(v) for v in m.groups()[2:]))

    if len(points) < 2:
        sys.exit("fewer than two PAYLOAD_TRACK points in %s" % args.log)
    if args.reverse:
        points.reverse()
    if args.every > 1:
        points = points[:-1:args.every] + [points[-1]]

    print("\ttrack = {")
    for x, y, z in points:
        print("\t\t{ %.1f, %.1f, %.1f }," % (x, y, z))
    print("\t},")
    if cps:
        print("\t-- command posts (team at the start), nearest track point:")
        for name, (team, (x, y, z)) in sorted(cps.items()):
            best = min(range(len(points)),
                       key=lambda i: (points[i][0] - x) ** 2 + (points[i][2] - z) ** 2)
            print("\t--   %s team %d, near point %d of %d" % (name, team, best + 1, len(points)))


if __name__ == "__main__":
    main()
