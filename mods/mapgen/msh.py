"""SWBF2 model (.msh) files: a Python port of WorldEdit's msh writer (PrismaticFlower/WorldEdit,
src/assets/msh/scene_io_save.cpp), shaped the way its "blocks" export them: a null "root" node,
a "geometry" static mesh, and a hidden "collision" mesh, plus a prop .odf and a .msh.option.
The mod tools' modelmunge turns these into game models.

Geometry comes in as polygons in the game's (world file) coordinates, wound counter-clockwise
seen from outside (shapes.py). A .msh is in WorldEdit's own space, which mirrors Z: its blocks are
exported from there unchanged, and its cube is wound so the right-hand normal points out. So
every point is written as (x, y, -z), with the order of each polygon reversed to keep it facing
out after the mirror.

Chunks are tag, size, payload; every size includes padding to 4 bytes; strings end in NUL.
"""
import math
import struct


def _chunk(tag, payload):
    payload += b"\0" * (-len(payload) % 4)
    return tag.encode("ascii") + struct.pack("<I", len(payload)) + payload


def _string(s):
    return s.encode("ascii") + b"\0"


class Material:
    def __init__(self, name, texture="", specular=False, glow=False, color=(1.0, 1.0, 1.0, 1.0)):
        self.name = name
        self.texture = texture          # a .tga the munge can find, without the extension
        # material flags as WorldEdit's material.hpp has them: glow 2, specular 128
        self.flags = (128 if specular else 0) | (2 if glow else 0)
        self.color = color


class Mesh:
    """Triangles in segments of one material each, with normals and texture coordinates."""

    def __init__(self):
        self.segments = {}              # material index -> (positions, normals, uvs, triangles)

    def _segment(self, material):
        return self.segments.setdefault(material, ([], [], [], []))

    def polys(self, material, polys, uv_scale=0.1):
        """Polygons from shapes.py (triangles or quads in game coordinates, counter-clockwise
        seen from outside), textured by projecting onto the plane they face most."""
        for poly in polys:
            pos, nrm, uv, tri = self._segment(material)
            poly = [(p[0], p[1], -p[2]) for p in reversed(poly)]      # into .msh space
            n = _normal(*poly[:3])
            ax = max(range(3), key=lambda i: abs(n[i]))
            u_i, v_i = [(2, 1), (0, 2), (0, 1)][ax]
            base = len(pos)
            for p in poly:
                pos.append(tuple(p))
                nrm.append(n)
                uv.append((p[u_i] * uv_scale, p[v_i] * uv_scale))
            for k in range(1, len(poly) - 1):
                tri.append((base, base + k, base + k + 1))

    def box(self, material, lo, hi, faces="xXyYzZ", uv_scale=0.1):
        import shapes
        self.polys(material, shapes.box(lo, hi, faces), uv_scale)

    def triangle_count(self):
        return sum(len(s[3]) for s in self.segments.values())

    def bounds(self):
        """In game coordinates."""
        pts = [(p[0], p[1], -p[2]) for s in self.segments.values() for p in s[0]]
        return tuple(min(p[i] for p in pts) for i in range(3)), tuple(max(p[i] for p in pts) for i in range(3))


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _len(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _normal(a, b, c):
    u, v = _sub(b, a), _sub(c, a)
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    length = _len(n) or 1.0
    return (n[0] / length, n[1] / length, n[2] / length)


def _segments(mesh, with_material=True):
    """SEGM chunks, splitting any segment past the format's 32768 vertices."""
    out = b""
    for material, (pos, nrm, uv, tri) in sorted(mesh.segments.items()):
        start = 0
        while start < len(tri):
            chunk_tris, used, remap = [], [], {}
            while start < len(tri) and len(used) + 3 <= 0x8000:
                t = tri[start]
                mapped = []
                for i in t:
                    if i not in remap:
                        remap[i] = len(used)
                        used.append(i)
                    mapped.append(remap[i])
                chunk_tris.append(mapped)
                start += 1
            body = _chunk("MATI", struct.pack("<i", material if with_material else 0))
            body += _chunk("POSL", struct.pack("<i", len(used)) + b"".join(struct.pack("<3f", *pos[i]) for i in used))
            if with_material:
                body += _chunk("NRML", struct.pack("<i", len(used)) + b"".join(struct.pack("<3f", *nrm[i]) for i in used))
                body += _chunk("UV0L", struct.pack("<i", len(used)) + b"".join(
                    struct.pack("<2f", uv[i][0], 1.0 - uv[i][1]) for i in used))
            strip = struct.pack("<i", len(chunk_tris) * 3)
            for a, b, c in chunk_tris:
                strip += struct.pack("<3H", a | 0x8000, b | 0x8000, c)
            body += _chunk("STRP", strip)
            out += _chunk("SEGM", body)
    return out


def _modl(name, index, node_type, parent=None, hidden=False, geom=b""):
    body = _chunk("MTYP", struct.pack("<i", node_type))
    body += _chunk("MNDX", struct.pack("<I", index))
    body += _chunk("NAME", _string(name))
    if parent:
        body += _chunk("PRNT", _string(parent))
    body += _chunk("FLGS", struct.pack("<I", 1 if hidden else 0))
    if parent:
        body += _chunk("TRAN", struct.pack("<3f4f3f", 1, 1, 1, 0, 0, 0, 1, 0, 0, 0))
    body += _chunk("GEOM", geom)
    return _chunk("MODL", body)


def write_msh(materials, mesh, collision=None):
    """A model: the visible mesh, and (optionally) a separate collision mesh."""
    matl = struct.pack("<i", len(materials))
    for m in materials:
        md = _chunk("NAME", _string(m.name))
        # as WorldEdit writes it: zero diffuse, the specular colour, zero ambient, exponent 50
        md += _chunk("DATA", struct.pack("<4f", 0, 0, 0, 0) + struct.pack("<4f", *m.color) + struct.pack("<f", 0)
                     + struct.pack("<4f", 0, 0, 0, 0) + struct.pack("<f", 50.0))
        md += _chunk("ATRB", struct.pack("<BBbb", m.flags, 0, 0, 0))
        if m.texture:
            md += _chunk("TX0D", m.texture.encode("ascii") + b".TGA\0")
        matl += _chunk("MATD", md)
    msh2 = _chunk("MATL", matl)
    msh2 += _modl("root", 0, 0)
    msh2 += _modl("geometry", 1, 4, parent="root", geom=_segments(mesh))
    if collision is not None:
        msh2 += _modl("collision", 2, 4, parent="root", hidden=True, geom=_segments(collision, with_material=False))
    return _chunk("HEDR", _chunk("MSH2", msh2) + _chunk("CL1L", b""))


def prop_files(name, materials, mesh, collision=None, foley="metal"):
    """{filename: bytes} for a placeable prop class: name.msh, name.msh.option, name.odf."""
    option = "-donotmergecollision" + ("" if collision is not None else " -nocollision")
    odf = "\r\n".join([
        "[GameObjectClass]", "",
        'ClassLabel   = "prop"',
        'GeometryName = "%s.msh"' % name, "",
        "[Properties]", "",
        'GeometryName = "%s"' % name,
        'FoleyFXGroup = "%s_foley"' % foley, "",
    ])
    return {name + ".msh": write_msh(materials, mesh, collision),
            name + ".msh.option": option.encode("ascii"),
            name + ".odf": odf.encode("ascii")}


def read_chunks(data, start=0, end=None):
    """(tag, payload start, payload end) for each chunk, for the tests."""
    end = len(data) if end is None else end
    p = start
    while p + 8 <= end:
        tag = data[p:p + 4].decode("ascii")
        size = struct.unpack_from("<I", data, p + 4)[0]
        yield tag, p + 8, p + 8 + size
        p += 8 + size
