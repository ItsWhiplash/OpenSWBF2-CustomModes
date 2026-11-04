"""Shapes for block models: each function returns polygons (lists of 3 or 4 points), wound
counter-clockwise seen from outside, in the model's own frame (Y up). msh.Mesh.polys turns them
into model triangles, and the preview draws the very same polygons.
"""
import math


def box(lo, hi, faces="xXyYzZ"):
    return [list(reversed(p)) for p in _box_inward(lo, hi, faces)]


def _box_inward(lo, hi, faces):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    out = []
    if "x" in faces:
        out.append([(x0, y0, z1), (x0, y0, z0), (x0, y1, z0), (x0, y1, z1)])
    if "X" in faces:
        out.append([(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)])
    if "y" in faces:
        out.append([(x0, y0, z0), (x0, y0, z1), (x1, y0, z1), (x1, y0, z0)])
    if "Y" in faces:
        out.append([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)])
    if "z" in faces:
        out.append([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)])
    if "Z" in faces:
        out.append([(x1, y0, z1), (x0, y0, z1), (x0, y1, z1), (x1, y1, z1)])
    return out


def frustum(cx, cz, r0, r1, y0, y1, sides=16, top=True, bottom=False):
    """A vertical cylinder (r0 == r1) or cone section from radius r0 at y0 to r1 at y1."""
    out = []
    ring = [(math.cos(2 * math.pi * i / sides), math.sin(2 * math.pi * i / sides)) for i in range(sides)]
    for i in range(sides):
        (c0, s0), (c1, s1) = ring[i], ring[(i + 1) % sides]
        out.append([(cx + r0 * c0, y0, cz + r0 * s0), (cx + r1 * c0, y1, cz + r1 * s0),
                    (cx + r1 * c1, y1, cz + r1 * s1), (cx + r0 * c1, y0, cz + r0 * s1)])
    if top and r1 > 0:
        for i in range(sides):
            (c0, s0), (c1, s1) = ring[i], ring[(i + 1) % sides]
            out.append([(cx, y1, cz), (cx + r1 * c1, y1, cz + r1 * s1), (cx + r1 * c0, y1, cz + r1 * s0)])
    if bottom and r0 > 0:
        for i in range(sides):
            (c0, s0), (c1, s1) = ring[i], ring[(i + 1) % sides]
            out.append([(cx, y0, cz), (cx + r0 * c0, y0, cz + r0 * s0), (cx + r0 * c1, y0, cz + r0 * s1)])
    return out


def dome(cx, y0, cz, radius, rings=6, sides=16, lower=False):
    """A hemisphere on y0 (or hanging from it, lower=True)."""
    out = []
    sign = -1 if lower else 1
    for k in range(rings):
        a0 = math.pi / 2 * k / rings
        a1 = math.pi / 2 * (k + 1) / rings
        r0, r1 = radius * math.cos(a0), radius * math.cos(a1)
        h0, h1 = y0 + sign * radius * math.sin(a0), y0 + sign * radius * math.sin(a1)
        if lower:
            out += [list(reversed(p)) for p in frustum(cx, cz, r0, r1, h0, h1, sides, top=False)]
        else:
            out += frustum(cx, cz, r0, r1, h0, h1, sides, top=False)
    return out


def tube(start, end, radius, sides=12, caps=True):
    """A cylinder between two points, any direction."""
    ax = [end[i] - start[i] for i in range(3)]
    length = math.sqrt(sum(a * a for a in ax))
    d = [a / length for a in ax]
    helper = (0.0, 1.0, 0.0) if abs(d[1]) < 0.9 else (1.0, 0.0, 0.0)
    u = _norm(_cross(d, helper))
    v = _cross(d, u)
    ring = []
    for i in range(sides):
        a = 2 * math.pi * i / sides
        ring.append([radius * (math.cos(a) * u[k] + math.sin(a) * v[k]) for k in range(3)])
    out = []
    for i in range(sides):
        p0, p1 = ring[i], ring[(i + 1) % sides]
        out.append([_add(start, p0), _add(start, p1), _add(end, p1), _add(end, p0)])
    if caps:
        out += _fan([_add(end, p) for p in ring])
        out += _fan([_add(start, p) for p in reversed(ring)])
    return out


def loft(sections, cap_start=True, cap_end=True):
    """A hull through cross-sections: each is (x, [(z, y), ...]) with the same number of points,
    in order round the outline (either way round). Consecutive sections are joined by quads, and
    every face is turned to face away from the hull's centre line."""
    out = []

    def centre(pts):
        return (sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts))   # (y, z)

    for (xa, pa), (xb, pb) in zip(sections, sections[1:]):
        n = len(pa)
        ca, cb = centre(pa), centre(pb)
        for i in range(n):
            j = (i + 1) % n
            quad = [(xa, pa[i][1], pa[i][0]), (xa, pa[j][1], pa[j][0]),
                    (xb, pb[j][1], pb[j][0]), (xb, pb[i][1], pb[i][0])]
            mid = [sum(q[k] for q in quad) / 4 for k in range(3)]
            axis = (mid[0], (ca[0] + cb[0]) / 2, (ca[1] + cb[1]) / 2)
            nrm = normal(quad)
            if sum(nrm[k] * (mid[k] - axis[k]) for k in range(3)) < 0:
                quad.reverse()
            out.append(quad)
    for (x, pts), outward in ((sections[0], -1.0), (sections[-1], 1.0)):
        if (outward < 0 and not cap_start) or (outward > 0 and not cap_end):
            continue
        cap = [(x, y, z) for z, y in pts]
        if normal(cap)[0] * outward < 0:
            cap.reverse()
        out += _fan(cap)
    return out


def offset(polys, dx=0.0, dy=0.0, dz=0.0):
    return [[(p[0] + dx, p[1] + dy, p[2] + dz) for p in poly] for poly in polys]


def rotate_y(polys, yaw):
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return [[(p[0] * c + p[2] * s, p[1], -p[0] * s + p[2] * c) for p in poly] for poly in polys]


def normal(poly):
    a, b, c = poly[0], poly[1], poly[2]
    n = _cross([b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)])
    return _norm(n)


def _fan(pts):
    """A convex polygon as one quad or triangle, or a fan of triangles."""
    pts = [tuple(p) for p in pts]
    if len(pts) <= 4:
        return [pts]
    return [[pts[0], pts[i], pts[i + 1]] for i in range(1, len(pts) - 1)]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _norm(v):
    length = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / length for x in v]


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
