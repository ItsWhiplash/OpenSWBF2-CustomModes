"""Stock looks for the generated maps, taken from the SWBF2 Mod Tools' own copy of the stock maps.

The Mod Tools ship the stock worlds' sources (assets/worlds/<CODE>: terrain, sky, effects, models,
textures and classes). Rather than guess stock file names, this reads them from there:

- terrain textures: the stock terrain (.ter) lists its texture layers. Each of our layers (sand,
  rock, snow...) takes the stock layer whose name and average colour fit it best, with its scale,
  plus the stock detail texture;
- sky and weather: the stock world's .sky (fog, sun, sky dome) and .fx (snow, dust) are copied as
  the map's own <CODE>.sky and <CODE>.fx;
- models: a stock class found by keywords in its name (such as the shield generator) replaces our
  generated stand-in.

Everything copied brings what it references with it: a class its parent class, models and
explosions; a model its textures; a sky its dome model and textures. Anything not found is left to
our generated version, and the report says so.
"""
import os
import re
import struct

ROLE_HINTS = {
    "sand": (("sand", "dune", "desert"), (200, 170, 120)),
    "dirt": (("dirt", "ground", "gravel", "mud", "path", "road"), (150, 115, 80)),
    "rock": (("rock", "cliff", "stone", "mount"), (120, 110, 100)),
    "snow": (("snow",), (236, 242, 250)),
    "packed": (("packed", "track", "path", "snow"), (205, 214, 226)),
    "ice": (("ice", "frozen", "frost"), (176, 208, 232)),
}

# names of class variants that aren't the whole, standing object
NOT_WHOLE = ("dest", "destroyed", "damaged", "debris", "chunk", "chunks", "lowrez", "lowres", "lod",
             "piece", "rubble", "ruin", "ruins", "wreck", "wreckage", "low", "broken", "part", "door",
             "interior", "shadow", "collision", "fx", "exp", "explosion")


class Stock:
    """One stock world's sources, such as assets/worlds/HOT."""

    def __init__(self, modtools, code):
        self.code = code.upper()
        self.root = find_world(modtools, code)
        self.index = {}
        # the world's own files first, then the shared stock sources its classes may build on
        roots = [self.root] + shared_roots(modtools) if self.root else []
        for root in roots:
            for folder, _dirs, files in os.walk(root):
                for name in files:
                    self.index.setdefault(name.lower(), os.path.join(folder, name))
        self.copied = set()
        self.missing = set()
        self.notes = []

    def __bool__(self):
        return self.root is not None

    def path(self, name):
        return self.index.get(name.lower())

    def files(self, ext):
        return sorted(p for n, p in self.index.items() if n.endswith(ext))

    # ------------------------------------------------------------ terrain

    def terrain(self):
        """The stock terrain file: world1's if there is one."""
        ters = self.files(".ter")
        if not ters:
            return None
        first = [p for p in ters if os.path.basename(os.path.dirname(p)).lower() == "world1"]
        return (first or ters)[0]

    def terrain_layers(self):
        """[(texture name, scale)] for each used layer of the stock terrain, and its detail texture."""
        path = self.terrain()
        if not path:
            return [], ""
        names, scales, detail = read_ter_textures(open(path, "rb").read())
        return [(n, s) for n, s in zip(names, scales) if n], detail

    def pick_terrain(self, roles):
        """{role: (texture name, scale)} for our terrain roles, from the stock layers."""
        layers, detail = self.terrain_layers()
        layers = [(n, s) for n, s in layers if self.path(tex_file(n))]
        if not layers:
            return {}, ""
        colours = {n: average_colour(open(self.path(tex_file(n)), "rb").read()) for n, _ in layers}
        scored = []
        for role in roles:
            keywords, colour = ROLE_HINTS[role]
            for n, s in layers:
                name = n.lower()
                hit = next((i for i, k in enumerate(keywords) if k in name), None)
                score = colour_distance(colours[n], colour) if colours[n] else 200.0
                if hit is not None:
                    score -= 400 - 20 * hit
                scored.append((score, role, n, s))
        out, used = {}, set()
        for score, role, n, s in sorted(scored):
            if role not in out and n not in used:
                out[role] = (n, s)
                used.add(n)
        for role in roles:          # more roles than stock layers: share the nearest
            if role not in out:
                out[role] = min(((sc, n, s) for sc, r, n, s in scored if r == role))[1:]
        return out, detail if self.path(tex_file(detail)) else ""

    # ------------------------------------------------------------ classes

    def odfs(self):
        return {os.path.splitext(os.path.basename(p))[0].lower(): p for p in self.files(".odf")}

    def find_class(self, wanted, joined=()):
        """The best stock class for a thing: every group in `wanted` must have a word in the
        class's name (each group is alternatives), or the name contains one of `joined`. Whole,
        standing objects only: no destroyed or low-detail variants."""
        best = None
        for name, path in self.odfs().items():
            words = re.split(r"[_\-\s]+", name)
            if any(w in NOT_WHOLE for w in words):
                continue
            alts = [a for group in wanted for a in group]
            # a word starts with the alternative, or follows another one in a joined word
            # ("shieldgenerator" has "shield" then "gen")
            ok = any(j in name for j in joined) or all(
                any(w.startswith(a) or any(w.startswith(o) and w[len(o):].startswith(a) for o in alts)
                    for w in words for a in group) for group in wanted)
            if not ok:
                continue
            text = open(path, "rb").read().decode("latin-1")
            if not re.search(r"GeometryName", text, re.I):
                continue
            key = (len(words), len(name), name)
            if best is None or key < best[0]:
                best = (key, name)
        return best[1] if best else None

    # ------------------------------------------------------------ copying

    def copy(self, name, dirs):
        """Copy a stock file by name into the map, with everything it references. `dirs` maps a
        kind ("odf", "msh", "effects", "world") to a folder."""
        path = self.path(name)
        if not path:
            self.missing.add(name)
            return False
        if name.lower() in self.copied:
            return True
        self.copied.add(name.lower())
        data = open(path, "rb").read()
        ext = os.path.splitext(name)[1].lower()
        dest = dirs["odf"] if ext == ".odf" else dirs["effects"] if ext == ".fx" else dirs["msh"]
        write(dest, os.path.basename(path), data)
        if ext == ".msh":
            option = self.path(name + ".option")
            if option:
                write(dest, os.path.basename(option), open(option, "rb").read())
            for tex in msh_textures(data):
                self.copy(tex_file(tex), dirs)
            low = self.path(name[:-4] + "_lowrez.msh")
            if low:
                self.copy(os.path.basename(low), dirs)
        elif ext in (".odf", ".fx", ".sky"):
            self.copy_refs(data.decode("latin-1"), dirs)
        return True

    def copy_refs(self, text, dirs):
        """Copy everything a text file (class, sky, effect) names that this stock world has."""
        for token in references(text):
            for candidate in candidates(token):
                if self.path(candidate):
                    self.copy(candidate, dirs)
                    break

    def copy_world_file(self, ext, new_name, dirs):
        """Copy the stock world's own .sky or .fx under our map's name (CODE.sky), with what it
        references. Prefers the one named after the stock terrain."""
        found = self.files(ext)
        if not found:
            return None
        ter_base = os.path.splitext(os.path.basename(self.terrain() or ""))[0].lower()
        named = [p for p in found if os.path.splitext(os.path.basename(p))[0].lower() == ter_base]
        path = (named or found)[0]
        text = open(path, "rb").read()
        write(dirs["world"], new_name, text)
        self.copy_refs(text.decode("latin-1"), dirs)
        return os.path.basename(path)


def child(folder, name):
    """The sub-folder `name` of `folder`, whatever its capitalisation, or None."""
    try:
        for entry in os.listdir(folder):
            if entry.lower() == name.lower() and os.path.isdir(os.path.join(folder, entry)):
                return os.path.join(folder, entry)
    except (OSError, TypeError):
        pass
    return None


def shared_roots(modtools):
    """Stock sources shared between worlds (assets/worlds/Common, assets/Common), if present."""
    assets = child(modtools, "assets")
    out = [assets and child(child(assets, "worlds") or "", "common"), assets and child(assets, "common")]
    return [p for p in out if p]


def find_world(modtools, code):
    """The stock world's source folder in the Mod Tools (assets/worlds/<CODE>), whatever the
    capitalisation, or None."""
    if not modtools or not os.path.isdir(modtools):
        return None
    worlds = child(modtools, "assets")
    worlds = worlds and child(worlds, "worlds")
    found = worlds and child(worlds, code)
    if found:
        return found
    # elsewhere (an unpacked copy of the assets): a <CODE> folder holding a terrain
    for folder, dirs, files in os.walk(modtools):
        depth = folder[len(modtools):].count(os.sep)
        if depth >= 4:
            dirs[:] = []
            continue
        if os.path.basename(folder).lower() == code.lower():
            for sub, _d, names in os.walk(folder):
                if any(n.lower().endswith(".ter") for n in names):
                    return folder
    return None


def read_ter_textures(data):
    """(texture names, texture scales, detail texture) from a terrain file's header."""
    mn, version = struct.unpack_from("<4sI", data, 0)
    assert mn == b"TERR", "not a terrain file"
    scales = list(struct.unpack_from("<16f", data, 20))
    p = 184 + (1 if version == 22 else 0)
    names, detail = [], ""
    for i in range(16):
        names.append(data[p:p + 32].split(b"\0")[0].decode("latin-1"))
        if i == 0:
            detail = data[p + 32:p + 64].split(b"\0")[0].decode("latin-1")
        p += 64
    return names, scales, detail


def tex_file(name):
    name = name.strip()
    return name if name.lower().endswith(".tga") else name + ".tga"


def msh_textures(data):
    """Texture names a .msh uses (its materials' TX0D to TX3D)."""
    out = []
    for m in re.finditer(rb"TX[0-3]D", data):
        p = m.end()
        if p + 4 > len(data):
            continue
        size = struct.unpack_from("<I", data, p)[0]
        if 0 < size < 256:
            name = data[p + 4:p + 4 + size].split(b"\0")[0].decode("latin-1").strip()
            if name and re.fullmatch(r"[\w\-. ]+", name):
                out.append(name)
    return out


def msh_radius(data):
    """How far a model reaches from its origin across the ground (from its bounding box), or
    None if it has none."""
    p = data.find(b"BBOX")
    if p < 0 or p + 8 + 44 > len(data):
        return None
    _q = struct.unpack_from("<4f", data, p + 8)
    cx, _cy, cz, ex, _ey, ez = struct.unpack_from("<6f", data, p + 24)
    return max(abs(cx) + abs(ex), abs(cz) + abs(ez))


def class_geometry(text):
    m = re.search(r'^\s*GeometryName\s*=\s*"?([^"\r\n]+?)"?\s*$', text, re.I | re.M)
    return m and m.group(1).strip()


def references(text):
    """Names a text file mentions: quoted strings, and the values of `Key = value` lines."""
    out = re.findall(r'"([^"\r\n]+)"', text)
    out += [m.strip() for m in re.findall(r"^\s*\w+\s*=\s*([^\"\r\n;/]+?)\s*$", text, re.M)]
    words = []
    for token in out:
        words += [w for w in re.split(r"[\s,]+", token) if w]
    return words


def candidates(token):
    token = token.strip()
    base, ext = os.path.splitext(token)
    if ext.lower() in (".msh", ".tga", ".odf", ".fx", ".option"):
        return [token]
    return [token + ".odf", token + ".msh", token + ".tga", token + ".fx"]


def write(folder, name, data):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), "wb") as fh:
        fh.write(data)


# ---------------------------------------------------------------- textures

def read_tga(data):
    """(width, height, [(r, g, b)]) for the TGA kinds stock textures use: true colour or grey,
    plain or run-length encoded."""
    idlen, cmtype, itype = data[0], data[1], data[2]
    width, height, bpp = struct.unpack_from("<HHB", data, 12)
    if cmtype or itype not in (2, 3, 10, 11):
        raise ValueError("unsupported TGA type %d" % itype)
    size = bpp // 8
    p = 18 + idlen
    count = width * height
    raw = bytearray()
    if itype in (2, 3):
        raw = data[p:p + count * size]
    else:
        while len(raw) < count * size:
            head = data[p]
            p += 1
            n = (head & 0x7F) + 1
            if head & 0x80:
                raw += data[p:p + size] * n
                p += size
            else:
                raw += data[p:p + size * n]
                p += size * n
    pixels = []
    for i in range(0, count * size, size):
        if size == 1:
            pixels.append((raw[i],) * 3)
        else:
            pixels.append((raw[i + 2], raw[i + 1], raw[i]))
    return width, height, pixels


def average_colour(data):
    try:
        _w, _h, pixels = read_tga(data)
    except (ValueError, IndexError, struct.error):
        return None
    step = max(1, len(pixels) // 4096)
    sample = pixels[::step]
    return tuple(sum(c[k] for c in sample) / len(sample) for k in range(3))


def colour_distance(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


# ---------------------------------------------------------------- for the maps

def apply(modtools, stock_code, root, code, roles, terrain, classes=None):
    """Give a generated map (`root` is its data_<CODE> folder) stock looks from the stock world
    `stock_code`. `roles` are our terrain layers' roles, in order; `terrain` is our Terrain, whose
    texture names and scales are replaced. `classes` maps our class names to stock-name keywords
    and room (`(wanted, joined, metres from its centre it may reach)`): {our class: stock class} comes back for the ones found.
    Returns (replacements, report lines)."""
    stock = Stock(modtools, stock_code)
    report = []
    if not stock:
        return {}, ["stock %s: not found in %s (assets\\worlds\\%s): using the generated looks"
                    % (stock_code, modtools, stock_code)]
    world_dir = os.path.join(root, "Worlds", code, "world1")
    dirs = {"world": world_dir,
            "msh": os.path.join(root, "Worlds", code, "msh"),
            "odf": os.path.join(root, "Worlds", code, "odf"),
            "effects": os.path.join(root, "Worlds", code, "effects")}

    picks, detail = stock.pick_terrain(roles)
    for i, role in enumerate(roles):
        if role in picks:
            name, scale = picks[role]
            terrain.texture_names[i] = os.path.splitext(name)[0]
            terrain.texture_scales[i] = scale
            stock.copy(tex_file(name), dirs)
            report.append("terrain %-6s -> %s" % (role, name))
    if detail:
        terrain.detail_texture = os.path.splitext(detail)[0]
        stock.copy(tex_file(detail), dirs)
        report.append("terrain detail -> %s" % detail)
    if not picks:
        report.append("terrain: no stock terrain textures found: keeping the generated ones")

    for ext in (".sky", ".fx"):
        used = stock.copy_world_file(ext, code + ext, dirs)
        report.append("%s -> %s" % (ext[1:], "%s%s from %s" % (code, ext, used) if used else "none found"))

    replaced = {}
    for ours, (wanted, joined, room) in (classes or {}).items():
        found = stock.find_class(wanted, joined)
        if not found:
            report.append("model %s: no stock class found, keeping ours" % ours)
            continue
        odf = stock.odfs()[found]
        geometry = class_geometry(open(odf, "rb").read().decode("latin-1")) or ""
        model = stock.path(geometry if geometry.lower().endswith(".msh") else geometry + ".msh")
        radius = msh_radius(open(model, "rb").read()) if model else None
        if radius is not None and radius > room:
            report.append("model %s: stock %s is %.0f m across, too big for its spot (%.0f m): keeping ours"
                          % (ours, found, 2 * radius, 2 * room))
            continue
        stock.copy(os.path.basename(odf), dirs)
        replaced[ours] = found
        report.append("model %s -> stock %s" % (ours, found))
    if stock.missing:
        report.append("referenced but not in %s (the munge log will say if they matter): %s"
                      % (stock.root, ", ".join(sorted(stock.missing))))
    return replaced, ["stock %s (%s)" % (stock_code, stock.root)] + report
