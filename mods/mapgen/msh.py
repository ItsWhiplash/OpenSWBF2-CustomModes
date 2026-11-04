"""SWBF2 model (.msh) files: a Python port of WorldEdit's msh writer (PrismaticFlower/WorldEdit,
src/assets/msh/scene_io_save.cpp), shaped the way its "blocks" export them: a null "root" node,
a "geometry" static mesh, and a hidden "collision" mesh, plus a prop .odf and a .msh.option.
The mod tools' modelmunge turns these into game models.

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
    def __init__(self, name, texture="", specular=False, color=(1.0, 1.0, 1.0, 1.0)):
        self.name = name
        self.texture = texture          # a .tga the munge can find, without the extension
        self.flags = 128 if specular else 0
        self.color = color


class Mesh:
    """Triangles in segments of one material each, with normals and texture coordinates."""

    def __init__(self):
        self.segments = {}              # material index -> (positions, normals, uvs, triangles)

    def _segment(self, material):
        return self.segments.setdefault(material, ([], [], [], []))

    def quad(self, material, a, b, c, d, uv_scale=0.1):
        """A flat quad a-b-c-d (counter-clockwise seen from the front)."""
        pos, nrm, uv, tri = self._segment(material)
        n = _normal(a, b, c)
        base = len(pos)
        u_axis = _sub(b, a)
        v_axis = _sub(d, a)
        lu = _len(u_axis) * uv_scale
        lv = _len(v_axis) * uv_scale
        for p, (s, t) in zip((a, b, c, d), ((0, 0), (lu, 0), (lu, lv), (0, lv))):
            pos.append(p)
            nrm.append(n)
            uv.append((s, t))
        tri.append((base, base + 1, base + 2))
        tri.append((base, base + 2, base + 3))

    def box(self, material, lo, hi, faces="xXyYzZ", uv_scale=0.1):
        """An axis-aligned box from corner lo to corner hi; faces picks which sides to make
        (x/X: -x/+x, y/Y: bottom/top, z/Z: -z/+z), outward-facing."""
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        if "x" in faces:
            self.quad(material, (x0, y0, z1), (x0, y0, z0), (x0, y1, z0), (x0, y1, z1), uv_scale)
        if "X" in faces:
            self.quad(material, (x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0), uv_scale)
        if "y" in faces:
            self.quad(material, (x0, y0, z0), (x0, y0, z1), (x1, y0, z1), (x1, y0, z0), uv_scale)
        if "Y" in faces:
            self.quad(material, (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1), uv_scale)
        if "z" in faces:
            self.quad(material, (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), uv_scale)
        if "Z" in faces:
            self.quad(material, (x1, y0, z1), (x0, y0, z1), (x0, y1, z1), (x1, y1, z1), uv_scale)

    def triangle_count(self):
        return sum(len(s[3]) for s in self.segments.values())

    def bounds(self):
        pts = [p for s in self.segments.values() for p in s[0]]
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
