"""Preview images of a generated map: a top-down relief map with the command posts, ship,
boundary and bot graph, and a 3D view from the south."""
import math
import os

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

TEAM_COLOURS = {0: "#d9d9d9", 1: "#3b82f6", 2: "#ef4444"}


def hillshade(h, grid, azimuth=315, altitude=40):
    gz, gx = np.gradient(h, grid)
    slope = np.arctan(np.hypot(gx, gz))
    aspect = np.arctan2(-gx, gz)
    az, alt = math.radians(azimuth), math.radians(altitude)
    return np.clip(np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect), 0, 1)


def render(h, w, out_dir, ship_boxes, ship_pos, grid=8.0):
    os.makedirs(out_dir, exist_ok=True)
    n = h.shape[0]
    half = n * grid / 2
    # rows run north to south in file Z (row 0 is +Z), which is the image's top
    extent = (-half, half, -half + grid, half + grid)
    paths = []

    # --- top-down
    fig, ax = plt.subplots(figsize=(10, 10), dpi=110)
    shade = hillshade(h, grid)
    rgb = ground_colours(h, grid) * (0.35 + 0.65 * shade[..., None])
    ax.imshow(rgb, extent=extent, origin="upper")
    # bot graph
    hubs = {name: pos for name, pos, r in w.hubs}
    for name, a, b, flags in w.connections:
        pa, pb = hubs[a], hubs[b]
        ax.plot([pa[0], pb[0]], [pa[2], pb[2]], color="#22c55e" if flags == 63 else "#a3e635",
                lw=0.6, alpha=0.6)
    # boundary
    bx = [p[0] for p in w.boundary] + [w.boundary[0][0]]
    bz = [p[1] for p in w.boundary] + [w.boundary[0][1]]
    ax.plot(bx, bz, "--", color="white", lw=1)
    # ship outline
    sx, sy, sz = ship_pos
    for lo, hi in ship_boxes:
        ax.add_patch(plt.Rectangle((sx + lo[0], sz + lo[2]), hi[0] - lo[0], hi[2] - lo[2],
                                   fill=True, facecolor="#94a3b8", edgecolor="#1e293b", alpha=0.35, lw=0.6))
    # command posts
    for layer, cls, name, pos, rot, team, props in w.objects:
        if cls == "com_bldg_controlzone":
            label = dict(props).get("Label", name)
            on_ship = pos[1] > 200
            ax.scatter([pos[0]], [pos[2]], s=120, c=TEAM_COLOURS[team], edgecolors="black",
                       marker="^" if on_ship else "o", zorder=5)
            ax.annotate("%s %s%s" % (name, label, " (ship)" if on_ship else ""), (pos[0], pos[2]),
                        xytext=(8, 6), textcoords="offset points", fontsize=8, color="white",
                        bbox=dict(boxstyle="round,pad=0.2", fc="black", alpha=0.55, lw=0))
        elif cls == "com_item_vehicle_spawn":
            ax.scatter([pos[0]], [pos[2]], s=40, c="#facc15", marker="s", edgecolors="black", zorder=5)
    ax.set_title("Ground to Space: top-down (circles: posts, triangles: posts on the ship deck, "
                 "squares: fighters)", fontsize=9)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Z (m)")
    path = os.path.join(out_dir, "top_down.png")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    paths.append(path)

    # --- a perspective view from the south, drawn back to front
    path = os.path.join(out_dir, "view_3d.png")
    perspective(h, grid, ship_boxes, ship_pos, w, path,
                title="Ground to Space: from the south-east, the ship %d m over the valley" % ship_pos[1])
    paths.append(path)
    path = os.path.join(out_dir, "view_hangar.png")
    sx, sy, sz = ship_pos
    perspective(h, grid, ship_boxes, ship_pos, w, path, eye=(sx + 230.0, sy - 25.0, sz - 470.0),
                target=(sx, sy + 12.0, sz - 40.0),
                title="Ground to Space: a fighter's approach to the hangar's open side")
    paths.append(path)
    return paths


SAND = np.array([0.80, 0.68, 0.48])
DIRT = np.array([0.60, 0.46, 0.32])
ROCK = np.array([0.48, 0.44, 0.40])


def ground_colours(h, grid):
    """The terrain's colours, from the same slope and height rules as its textures."""
    gz, gx = np.gradient(h, grid)
    slope = np.hypot(gx, gz)
    rock = np.clip((slope - 0.55) / 0.3, 0, 1)
    rock = np.maximum(rock, np.clip((h - 90) / 60, 0, 1))
    dirt = np.clip((slope - 0.18) / 0.25, 0, 1) * (1 - rock)
    sand = 1 - rock - dirt
    return sand[..., None] * SAND + dirt[..., None] * DIRT + rock[..., None] * ROCK


def perspective(h, grid, ship_boxes, ship_pos, w, path, eye=(520.0, 620.0, -1180.0), target=(-40.0, 120.0, 220.0),
                title="Ground to Space", bay=(-80.0, 80.0, -85.0, 30.0)):
    from matplotlib.collections import PolyCollection
    n = h.shape[0]
    eye = np.array(eye)
    fwd = np.array(target) - eye
    fwd /= np.linalg.norm(fwd)
    right = np.cross([0.0, 1.0, 0.0], fwd)
    right /= np.linalg.norm(right)
    up = np.cross(fwd, right)
    sun = np.array([0.45, 0.8, 0.4])
    sun /= np.linalg.norm(sun)
    focal = 1.25
    polys, colours, depths = [], [], []

    def add(quad, colour, normal):
        rel = np.asarray(quad) - eye
        z = rel @ fwd
        if np.any(z < 5):
            return
        sx = (rel @ right) / z * focal
        sy = (rel @ up) / z * focal
        if np.all(np.abs(sx) > 1.8) or np.all(np.abs(sy) > 1.2):
            return
        light = 0.45 + 0.7 * max(0.0, float(np.dot(normal, sun)))
        # haze with distance
        haze = min(1.0, float(z.mean()) / 3400.0)
        c = np.clip(np.asarray(colour) * light * (1 - haze * 0.55) + np.array([0.70, 0.78, 0.88]) * haze * 0.55, 0, 1)
        polys.append(np.column_stack((sx, sy)))
        colours.append(c)
        depths.append(float(z.mean()))

    step = 2
    col = ground_colours(h, grid)
    for y in range(0, n - step, step):
        for x in range(0, n - step, step):
            pts = []
            for yy, xx in ((y, x), (y, x + step), (y + step, x + step), (y + step, x)):
                pts.append(((xx - n / 2) * grid, h[yy][xx], -(yy - n / 2 + 1) * grid))
            a, b, c = np.array(pts[0]), np.array(pts[1]), np.array(pts[3])
            normal = np.cross(c - a, b - a)
            normal /= np.linalg.norm(normal) or 1.0
            if normal[1] < 0:
                normal = -normal
            add(pts, col[y][x], normal)

    sx0, sy0, sz0 = ship_pos
    hull = np.array([0.62, 0.64, 0.68])
    for lo, hi in ship_boxes:
        x0, y0, z0 = sx0 + lo[0], sy0 + lo[1], sz0 + lo[2]
        x1, y1, z1 = sx0 + hi[0], sy0 + hi[1], sz0 + hi[2]
        faces = [
            ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0)),
            ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)),
            ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1)),
            ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)),
            ([(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)], (-1, 0, 0)),
            ([(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)], (1, 0, 0)),
        ]
        for quad, normal in faces:
            normal = np.array(normal, float)
            centre = np.mean(quad, axis=0)
            if np.dot(normal, centre - eye) >= 0:
                continue                      # facing away
            # inside the hangar bay: lit warmer, as its lights would
            local = centre - np.array(ship_pos)
            inside = bay and bay[0] <= local[0] <= bay[1] and bay[2] <= local[2] <= 0.5 and -0.5 <= local[1] <= bay[3] + 0.5
            add(quad, np.array([0.95, 0.80, 0.45]) if inside else hull, normal if not inside else -normal * 0 + sun)

    order = np.argsort(depths)[::-1]
    fig, ax = plt.subplots(figsize=(14, 8), dpi=110)
    fig.patch.set_facecolor((0.58, 0.70, 0.86))
    ax.set_facecolor((0.58, 0.70, 0.86))
    ax.add_collection(PolyCollection([polys[i] for i in order], facecolors=[colours[i] for i in order],
                                     edgecolors="none", antialiased=False))
    for layer, cls, name, pos, rot, team, props in w.objects:
        if cls == "com_bldg_controlzone":
            rel = np.array(pos) + np.array([0, 4, 0]) - eye
            z = rel @ fwd
            if z > 5:
                ax.scatter([(rel @ right) / z * focal], [(rel @ up) / z * focal], s=50,
                           c=TEAM_COLOURS[team], edgecolors="black", zorder=5)
                ax.annotate(name, ((rel @ right) / z * focal, (rel @ up) / z * focal), xytext=(5, 5),
                            textcoords="offset points", fontsize=8, color="white", zorder=6)
    ax.set_xlim(-1.6, 1.6)
    ax.set_ylim(-0.9, 0.9)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
