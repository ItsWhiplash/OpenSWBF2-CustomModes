"""Preview images of a generated map: a top-down relief map (command posts, vehicles, structures,
boundary and bot graph) and perspective views drawn from the map's own data: the terrain heights
and the very polygons its models are made of, painted back to front."""
import math
import os

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402

import shapes  # noqa: E402

TEAM_COLOURS = {0: "#d9d9d9", 1: "#3b82f6", 2: "#ef4444"}

SAND = np.array([0.80, 0.68, 0.48])
DIRT = np.array([0.60, 0.46, 0.32])
ROCK = np.array([0.48, 0.44, 0.40])
# the three ground colours (flat, slope, cliff); a map can set its own, such as snow
PALETTE = [SAND, DIRT, ROCK]
# heights above which the ground turns to rock (start, over)
ROCK_HEIGHT = (90.0, 60.0)
# slopes past which it turns to rock (start, over)
ROCK_SLOPE = (0.55, 0.3)
SKY_TOP = np.array([0.36, 0.55, 0.82])
SKY_HORIZON = np.array([0.80, 0.86, 0.93])
SUN = np.array([0.45, 0.8, 0.4]) / np.linalg.norm([0.45, 0.8, 0.4])


def ground_at(h, grid, x, z):
    n = h.shape[0]
    gx = min(max(int(round(x / grid + n / 2)), 0), n - 1)
    gy = min(max(int(round(-z / grid + n / 2 - 1)), 0), n - 1)
    return h[gy][gx]


def hillshade(h, grid, azimuth=315, altitude=40):
    gz, gx = np.gradient(h, grid)
    slope = np.arctan(np.hypot(gx, gz))
    aspect = np.arctan2(-gx, gz)
    az, alt = math.radians(azimuth), math.radians(altitude)
    return np.clip(np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect), 0, 1)


def ground_colours(h, grid):
    """The terrain's colours, from the same slope and height rules as its textures."""
    gz, gx = np.gradient(h, grid)
    slope = np.hypot(gx, gz)
    rock = np.clip((slope - ROCK_SLOPE[0]) / ROCK_SLOPE[1], 0, 1)
    rock = np.maximum(rock, np.clip((h - ROCK_HEIGHT[0]) / ROCK_HEIGHT[1], 0, 1))
    dirt = np.clip((slope - 0.18) / 0.25, 0, 1) * (1 - rock)
    sand = 1 - rock - dirt
    return sand[..., None] * PALETTE[0] + dirt[..., None] * PALETTE[1] + rock[..., None] * PALETTE[2]


def render(h, w, out_dir, parts, views, grid=8.0, map_name="Map"):
    """parts: (polygons in world space, colour, glows) for every model; views: (file name, eye,
    target, title, show markers) for the perspective images."""
    os.makedirs(out_dir, exist_ok=True)
    paths = [top_down(h, w, out_dir, parts, grid, map_name)]
    for fname, eye, target, title, markers in views:
        path = os.path.join(out_dir, fname)
        perspective(h, grid, parts, w, path, eye, target, title, markers)
        paths.append(path)
    return paths


def top_down(h, w, out_dir, parts, grid, map_name):
    n = h.shape[0]
    half = n * grid / 2
    extent = (-half, half, -half + grid, half + grid)    # row 0 is the far +Z edge
    fig, ax = plt.subplots(figsize=(10, 10), dpi=110)
    shade = hillshade(h, grid)
    ax.imshow(ground_colours(h, grid) * (0.35 + 0.65 * shade[..., None]), extent=extent, origin="upper")
    hubs = {name: pos for name, pos, r in w.hubs}
    for name, a, b, flags in w.connections:
        pa, pb = hubs[a], hubs[b]
        ax.plot([pa[0], pb[0]], [pa[2], pb[2]], color="#22c55e" if flags == 63 else "#a3e635", lw=0.5, alpha=0.45)
    if w.boundary:
        bx = [p[0] for p in w.boundary] + [w.boundary[0][0]]
        bz = [p[1] for p in w.boundary] + [w.boundary[0][1]]
        ax.plot(bx, bz, "--", color="white", lw=1)
    # structures: their upward faces, seen from above
    tops = []
    for polys, colour, glows in parts:
        for poly in polys:
            if shapes.normal(poly)[1] > 0.2:
                tops.append([(p[0], p[2]) for p in poly])
    ax.add_collection(PolyCollection(tops, facecolors="#cbd5e1", edgecolors="#334155", linewidths=0.2, alpha=0.9))
    for layer, cls, name, pos, rot, team, props in w.objects:
        if cls == "com_bldg_controlzone":
            label = dict(props).get("Label", name)
            raised = pos[1] - ground_at(h, grid, pos[0], pos[2]) > 15
            ax.scatter([pos[0]], [pos[2]], s=120, c=TEAM_COLOURS[team], edgecolors="black",
                       marker="^" if raised else "o", zorder=5)
            ax.annotate("%s %s" % (name, label), (pos[0], pos[2]), xytext=(8, 6), textcoords="offset points",
                        fontsize=8, color="white", bbox=dict(boxstyle="round,pad=0.2", fc="black", alpha=0.55, lw=0))
        elif cls == "com_item_vehicle_spawn":
            ax.scatter([pos[0]], [pos[2]], s=40, c="#facc15", marker="s", edgecolors="black", zorder=5)
    ax.set_xlim(-half, half)
    ax.set_ylim(-half + grid, half + grid)
    ax.set_title("%s: top-down (circles: posts, triangles: raised posts, squares: vehicles)" % map_name, fontsize=9)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Z (m)")
    path = os.path.join(out_dir, "top_down.png")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def perspective(h, grid, parts, w, path, eye, target, title, markers=True):
    n = h.shape[0]
    eye = np.array(eye, float)
    fwd = np.array(target, float) - eye
    fwd /= np.linalg.norm(fwd)
    right = np.cross([0.0, 1.0, 0.0], fwd)
    right /= np.linalg.norm(right)
    up = np.cross(fwd, right)
    focal = 1.25
    far = 1.6 * n * grid
    polys, colours, depths = [], [], []

    def add(pts, colour, nrm, glows=False):
        rel = np.asarray(pts, float) - eye
        z = rel @ fwd
        if np.any(z < 2):
            return
        sx = (rel @ right) / z * focal
        sy = (rel @ up) / z * focal
        if np.all(np.abs(sx) > 1.8) or np.all(np.abs(sy) > 1.1):
            return
        if glows:
            c = np.asarray(colour, float)
        else:
            light = 0.42 + 0.68 * max(0.0, float(np.dot(nrm, SUN)))
            c = np.asarray(colour, float) * light
        haze = min(1.0, float(z.mean()) / far) * 0.6
        c = np.clip(c * (1 - haze) + SKY_HORIZON * haze, 0, 1)
        polys.append(np.column_stack((sx, sy)))
        colours.append(c)
        depths.append(float(z.mean()))

    step = max(1, n // 256)
    col = ground_colours(h, grid)
    for y in range(0, n - step, step):
        for x in range(0, n - step, step):
            pts = [((xx - n / 2) * grid, h[yy][xx], -(yy - n / 2 + 1) * grid)
                   for yy, xx in ((y, x), (y, x + step), (y + step, x + step), (y + step, x))]
            a, b, c = np.array(pts[0]), np.array(pts[1]), np.array(pts[3])
            nrm = np.cross(c - a, b - a)
            nrm /= np.linalg.norm(nrm) or 1.0
            if nrm[1] < 0:
                nrm = -nrm
            add(pts, col[y][x], nrm)

    for model, colour, glows in parts:
        for poly in model:
            nrm = np.array(shapes.normal(poly))
            centre = np.mean(poly, axis=0)
            if np.dot(nrm, centre - eye) >= 0:
                continue                          # facing away
            add(poly, colour, nrm, glows)

    order = np.argsort(depths)[::-1]
    fig, ax = plt.subplots(figsize=(14, 8), dpi=110)
    # sky: horizon colour low, deeper blue overhead
    grad = np.linspace(0, 1, 256)[:, None]
    sky = SKY_HORIZON * (1 - grad[..., None]) + SKY_TOP * grad[..., None]
    ax.imshow(np.repeat(sky, 2, axis=1), extent=(-1.6, 1.6, -0.9, 0.9), origin="lower", aspect="auto", zorder=0)
    ax.add_collection(PolyCollection([polys[i] for i in order], facecolors=[colours[i] for i in order],
                                     edgecolors=[colours[i] for i in order], linewidths=0.15, zorder=1))
    if markers:
        for layer, cls, name, pos, rot, team, props in w.objects:
            if cls == "com_bldg_controlzone":
                rel = np.array(pos) + np.array([0, 4, 0]) - eye
                z = rel @ fwd
                if z > 5:
                    px, py = (rel @ right) / z * focal, (rel @ up) / z * focal
                    ax.scatter([px], [py], s=45, c=TEAM_COLOURS[team], edgecolors="black", zorder=5)
                    ax.annotate(name, (px, py), xytext=(5, 5), textcoords="offset points", fontsize=8,
                                color="white", zorder=6)
    ax.set_xlim(-1.6, 1.6)
    ax.set_ylim(-0.9, 0.9)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
