"""SWBF2 world source files (what ZeroEditor and the mod tools read), written the way WorldEdit
(PrismaticFlower/WorldEdit, src/world/io/save.cpp) writes them.

Everything here is in file coordinates, the game's: WorldEdit flips Z when it loads and saves
(flip_position), so a terrain row y sits at Z = -(y - length/2 + 1) * grid_scale here. Rotations
are written w, x, y, z; a turn of `yaw` degrees about the vertical axis is (cos, 0, sin, 0) of
half the angle.
"""
import math

SHAPE = {"box": 0, "sphere": 1, "cylinder": 2}
AI_ALL = 63           # soldier, hover, small, medium, huge, flyer
AI_SOLDIER = 1
AI_FLYER = 32


def yaw_rotation(yaw):
    a = math.radians(yaw) / 2
    return (math.cos(a), 0.0, math.sin(a), 0.0)


def f(v):
    return "%f" % v


class World:
    def __init__(self, name):
        self.name = name                    # the map's three-letter code, such as "GTS"
        self.layers = ["[Base]"]            # layer 0; game modes list the layers they use
        self.game_modes = {"Common": [0]}
        self.objects = []                   # (layer, class, name, pos, rot, team, props)
        self.regions = []                   # (layer, type, name, shape, pos, rot, size)
        self.paths = []                     # (layer, name, nodes, spline)
        self.boundary = None                # list of (x, z)
        self.hubs = []                      # (name, pos, radius)
        self.connections = []               # (name, start, end, flags)
        self.lights = []                    # (name, pos, colour, range): point lights
        self.terrain_name = name

    def layer(self, name, modes=()):
        self.layers.append(name)
        index = len(self.layers) - 1
        for mode in modes:
            self.game_modes.setdefault(mode, []).append(index)
        return index

    def object(self, cls, name, pos, yaw=0.0, team=0, props=(), layer=0):
        self.objects.append((layer, cls, name, pos, yaw_rotation(yaw), team, list(props)))

    def region(self, rtype, name, shape, pos, size, yaw=0.0, layer=0):
        self.regions.append((layer, rtype, name, SHAPE[shape], pos, yaw_rotation(yaw), size))

    def path(self, name, nodes, layer=0, spline="None"):
        self.paths.append((layer, name, list(nodes), spline))

    def command_post(self, name, pos, team, layer=0, capture=8.0, control=16.0, control_height=8.0,
                     spawn=None, label=None):
        """A command post as WorldEdit makes one: the post, a sphere capture region, a cylinder
        control region and a spawn path (points around it unless given)."""
        cap = math.sqrt(capture * capture / 3)
        con = math.sqrt(control * control / 2)
        self.region(name + "_capture", name + "_capture", "sphere", pos, (cap, cap, cap), layer=layer)
        self.region(name + "_control", name + "_control", "cylinder", pos, (con, control_height, con), layer=layer)
        if spawn is None:
            spawn = [(pos[0] + 8 * math.cos(a), pos[1], pos[2] + 8 * math.sin(a))
                     for a in [i * math.pi / 4 for i in range(8)]]
        self.path(name + "_spawn", spawn, layer=layer)
        props = [("Label", label or ""), ("CaptureRegion", name + "_capture"),
                 ("ControlRegion", name + "_control"), ("SpawnPath", name + "_spawn")]
        self.object("com_bldg_controlzone", name, pos, team=team, props=props, layer=layer)

    def light(self, name, pos, colour=(1.0, 0.9, 0.7), range_=20.0):
        """A static point light, such as inside a hangar."""
        self.lights.append((name, pos, colour, range_))

    def hub(self, name, pos, radius):
        self.hubs.append((name, pos, radius))

    def connect(self, a, b, flags=AI_ALL):
        self.connections.append(("Connection%d" % len(self.connections), a, b, flags))

    # --- writing ---

    def _header(self, out, light, terrain=True):
        out.append("Version(3);")
        out.append("SaveType(0);")
        out.append("")
        out.append('LightName("%s.LGT");' % light)
        if terrain:
            out.append('TerrainName("%s.ter");' % self.terrain_name)
            out.append('SkyName("%s.sky");' % self.name)
            out.append("")
        out.append("NextSequence(%d);" % len(self.objects))
        out.append("")

    def _objects(self, layer):
        out = []
        self._header(out, self.name if layer == 0 else "%s_%s" % (self.name, self.layers[layer]), layer == 0)
        for seq, (ol, cls, name, pos, rot, team, props) in enumerate(self.objects):
            if ol != layer:
                continue
            out.append('Object("%s", "%s", %d)' % (name, cls, seq))
            out.append("{")
            out.append("\tChildRotation(%s, %s, %s, %s);" % tuple(f(v) for v in rot))
            out.append("\tChildPosition(%s, %s, %s);" % tuple(f(v) for v in pos))
            out.append("\tTeam(%d);" % team)
            out.append("\tNetworkId(-1);")
            if layer:
                out.append("\tLayer(%d);" % layer)
            for k, v in props:
                out.append('\t%s("%s");' % (k, v))
            out.append("}")
            out.append("")
        return "\n".join(out) + "\n"

    def _regions(self, layer):
        mine = [r for r in self.regions if r[0] == layer]
        out = ["Version(1);", "RegionCount(%d);" % len(mine), ""]
        for rl, rtype, name, shape, pos, rot, size in mine:
            out.append('Region("%s", %d)' % (rtype, shape))
            out.append("{")
            if layer:
                out.append("\tLayer(%d);" % layer)
            out.append("\tPosition(%s, %s, %s);" % tuple(f(v) for v in pos))
            out.append("\tRotation(%s, %s, %s, %s);" % tuple(f(v) for v in rot))
            out.append("\tSize(%s, %s, %s);" % tuple(f(v) for v in size))
            out.append('\tName("%s");' % name)
            out.append("}")
            out.append("")
        return "\n".join(out) + "\n"

    def _paths(self, layer):
        mine = [p for p in self.paths if p[0] == layer]
        count = len(mine) + (1 if layer == 0 and self.boundary else 0)
        out = ["Version(10);", "PathCount(%d);" % count, ""]
        for pl, name, nodes, spline in mine:
            out += self._path(name, nodes, spline, data=1, layer=layer)
        if layer == 0 and self.boundary:
            out += self._path("boundary", [(x, 0.0, z) for x, z in self.boundary], "Hermite", data=0)
        return "\n".join(out) + "\n"

    def _path(self, name, nodes, spline, data, layer=0):
        out = ['Path("%s")' % name, "{", "\tData(%d);" % data, "\tPathType(0);", "\tPathSpeedType(0);",
               "\tPathTime(0.000000);", "\tOffsetPath(0);"]
        if layer:
            out.append("\tLayer(%d);" % layer)
        out += ['\tSplineType("%s");' % spline, "", "\tProperties(0)", "\t{", "\t}", "",
                "\tNodes(%d)" % len(nodes), "\t{"]
        for n in nodes:
            out += ["\t\tNode()", "\t\t{",
                    "\t\t\tPosition(%s, %s, %s);" % tuple(f(v) for v in n),
                    "\t\t\tKnot(0.000000);", "\t\t\tData(%d);" % data, "\t\t\tTime(1.000000);",
                    "\t\t\tPauseTime(0.000000);", "\t\t\tRotation(1.000000, 0.000000, 0.000000, 0.000000);",
                    "\t\t\tProperties(0)", "\t\t\t{", "\t\t\t}", "\t\t}", ""]
        out += ["\t}", "}", ""]
        return out

    def _planning(self):
        out = []
        for name, pos, radius in self.hubs:
            out += ["", 'Hub("%s")' % name, "{", "\tPos(%s, %s, %s);" % tuple(f(v) for v in pos),
                    "\tRadius(%s);" % f(radius), "}"]
        for name, a, b, flags in self.connections:
            out += ["", 'Connection("%s")' % name, "{", '\tStart("%s");' % a, '\tEnd("%s");' % b,
                    "\tFlag(%d);" % flags, "}"]
        return "\n".join(out) + "\n"

    def _ldx(self):
        out = ["Version(1);", "NextID(%d);" % len(self.layers), ""]
        for i, name in enumerate(self.layers):
            out += ['Layer("%s", %d, %d)' % (name, i, 8 if i == 0 else 0), "{", '\tDescription("");', "}", ""]
        out.append("")
        for mode, layers in self.game_modes.items():
            out += ['GameMode("%s")' % mode, "{"] + ["\tLayer(%d);" % i for i in layers] + ["}", ""]
        return "\n".join(out) + "\n"

    def _lights(self, sun_yaw=35.0, sun_pitch=50.0):
        a = math.radians(sun_yaw) / 2
        b = math.radians(sun_pitch) / 2
        # pitch then yaw
        w = math.cos(a) * math.cos(b)
        x = math.cos(a) * math.sin(b)
        y = math.sin(a) * math.cos(b)
        z = -math.sin(a) * math.sin(b)
        return "\n".join([
            "", 'Light("sun", 0)', "{", "\tRotation(%s, %s, %s, %s);" % (f(w), f(x), f(y), f(z)),
            "\tPosition(0.000000, 400.000000, 0.000000);", "\tType(1);",
            "\tColor(1.000000, 0.952941, 0.878431);", "\tCastShadow();", "\tStatic();",
            "\tCastSpecular(1);", "\tPS2BlendMode(0);", "\tTileUV(1.000000,1.000000);",
            "\tOffsetUV(0.000000,0.000000);", "}", ""] + self._point_lights() + [
            "GlobalLights()", "{", "\tEditorGlobalDirIconSize(10);", '\tLight1("sun");', '\tLight2("");',
            "\tTop(120, 125, 140);", "\tBottom(70, 65, 60);", "}", ""]) + "\n"

    def _point_lights(self):
        out = []
        for i, (name, pos, colour, range_) in enumerate(self.lights, start=1):
            out += ['Light("%s", %d)' % (name, i), "{", "\tRotation(1.000000, 0.000000, 0.000000, 0.000000);",
                    "\tPosition(%s, %s, %s);" % tuple(f(v) for v in pos), "\tType(2);",
                    "\tColor(%s, %s, %s);" % tuple(f(v) for v in colour), "\tStatic();",
                    "\tCastSpecular(1);", "\tRange(%s);" % f(range_), "}", ""]
        return out

    def _req(self):
        out = ["ucft", "{"]
        for kind in ("path", "congraph", "envfx", "world", "prop", "povs"):
            out += ["\tREQN", "\t{", '\t\t"%s"' % kind, '\t\t"%s"' % self.name, "\t}"]
        modes = [m for m in self.game_modes if m != "Common"]
        if modes:
            out += ["\tREQN", "\t{", '\t\t"lvl"'] + ['\t\t"%s_%s"' % (self.name, m) for m in modes] + ["\t}"]
        out.append("}")
        return "\n".join(out) + "\n"

    def files(self):
        """{filename: text} for the world folder (Worlds/<code>/world1)."""
        n = self.name
        out = {
            n + ".wld": self._objects(0),
            n + ".RGN": self._regions(0),
            n + ".PTH": self._paths(0),
            n + ".PLN": self._planning(),
            n + ".LDX": self._ldx(),
            n + ".LGT": self._lights(),
            n + ".BND": 'Boundary()\n{\n\tPath("boundary");\n}\n\n' if self.boundary else "",
            n + ".BAR": "BarrierCount(0);\n\n",
            n + ".HNT": "",
            n + ".req": self._req(),
        }
        for i, layer in enumerate(self.layers[1:], start=1):
            base = "%s_%s" % (n, layer)
            out[base + ".lyr"] = self._objects(i)
            out[base + ".RGN"] = self._regions(i)
            out[base + ".PTH"] = self._paths(i)
            out[base + ".LGT"] = ""
            out[base + ".HNT"] = ""
        for mode in self.game_modes:
            if mode != "Common":
                out["%s_%s.mrq" % (n, mode)] = 'ucft\n{\n\tREQN\n\t{\n\t\t"world"\n\t\t"%s_%s"\n\t}\n}\n' % (n, mode)
        return out
