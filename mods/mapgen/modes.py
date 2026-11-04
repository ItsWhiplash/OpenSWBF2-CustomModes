"""The custom modes on the generated maps, and the maps' own registration.

    python mods/mapgen/modes.py

Writes mods/custommodes/maps/<mode>/<map><era>.lua for Ground to Space (gtsc, gtsg) and Hoth
(hthg): Payload, Rush, Horde, Search & Destroy and Infiltration, each laid out for the map (Payload's
tracks follow the generated terrain). build.py then puts them in the CUSTOMMODES AddOn, beside the
stock maps' missions.

Each map is its own AddOn (AddOn\\GTS, AddOn\\HTH). A custom mission runs the map's Conquest
script from that AddOn's mission.lvl (baseLvl), and the map's scripts load its world by its path
in the AddOn folder, so they work from either AddOn. gts.py and hoth.py also write each map's
addme.lua and mission build lists with addon_files().
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
MODES_DIR = os.path.join(os.path.dirname(HERE), "custommodes", "maps")


def lua(value, indent="\t"):
    """A Python value as Lua source (dicts as tables with string keys, lists as arrays)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return ("%.1f" % value) if isinstance(value, float) else str(value)
    if isinstance(value, str):
        return '"%s"' % value.replace("\\", "\\\\")
    if isinstance(value, (list, tuple)):
        if all(isinstance(v, (int, float)) for v in value):
            return "{ %s }" % ", ".join(lua(v) for v in value)
        inner = ",\n".join(indent + "\t" + lua(v, indent + "\t") for v in value)
        return "{\n%s,\n%s}" % (inner, indent)
    if isinstance(value, dict):
        inner = ",\n".join("%s\t%s = %s" % (indent, k, lua(v, indent + "\t")) for k, v in value.items())
        return "{\n%s,\n%s}" % (inner, indent)
    raise TypeError(value)


def track(height_at, h, waypoints, step=25.0, lift=1.0):
    """A payload track through the waypoints (x, z), a point every `step` metres, on the ground."""
    pts = []
    for (x0, z0), (x1, z1) in zip(waypoints, waypoints[1:]):
        n = max(1, int(math.hypot(x1 - x0, z1 - z0) / step))
        for k in range(n):
            t = k / n
            x, z = x0 + (x1 - x0) * t, z0 + (z1 - z0) * t
            pts.append((round(x, 1), round(height_at(h, x, z) + lift, 1), round(z, 1)))
    x, z = waypoints[-1]
    pts.append((round(x, 1), round(height_at(h, x, z) + lift, 1), round(z, 1)))
    return [list(p) for p in pts]


def base_settings(code, era):
    return {"base": "%s%s_con" % (code, era),
            "baseLvl": "..\\..\\AddOn\\%s\\Data\\_lvl_pc\\mission.lvl" % code}


def gts_modes(era):
    import gts
    h = gts.make_heights()
    common = base_settings("GTS", era)
    # straight up the valley: across the canyon bridge, to the ground under the ship
    payload = dict(common, track=track(gts.height_at, h, [(0, -650), (0, -380), (0, -120), (0, 0), (0, 120), (0, 185)]),
                   checkpoints=[{"at": 0.45, "giveCPs": ["cp3"]}, {"at": 0.8, "giveCPs": ["cp2", "cp4"]}],
                   initialCPs={"cp1": "att", "cp2": "def", "cp3": "def", "cp4": "def", "cp5": "def"})
    return {
        "pay": payload,
        # automatic: the valley, then the mesas, then the ship's hangar last
        "rush": dict(common),
        # hold the landing against waves from the north (the ship's posts are out of reach on foot)
        "horde": dict(common, lastStand="cp1", hordeSpawns=["cp5", "cp4"], shopPads=["cp2", "cp3"]),
        # the two mesas are the sites
        "snd": dict(common, attackerSpawn="cp1", defenderSpawn="cp5", sites=["cp2", "cp4"]),
        "inf": dict(common, insertion="cp1", extraction="cp1",
                    targets=[{"post": "cp2"}, {"post": "cp3"}, {"post": "cp4"}, {"post": "cp5"}]),
    }


def hth_modes(era):
    import hoth
    h = hoth.make_heights()
    common = base_settings("HTH", era)
    # north from the landing: through the ridge pass, the trench's centre crossing, to the base
    payload = dict(common, track=track(hoth.height_at, h, [(0, -1330), (0, -900), (0, -400), (0, 0), (0, 120),
                                                           (0, 400), (0, 700), (0, 1000), (0, 1150)]),
                   baseSpeed=3.0, speedPerPusher=0.8, maxSpeed=6.0, timeLimit=900, checkpointBonusTime=150,
                   checkpoints=[{"at": 0.35, "giveCPs": ["cp2", "cp3", "cp4"]}, {"at": 0.7, "giveCPs": ["cp5", "cp6"]}],
                   initialCPs={"cp1": "att", "cp10": "att", "cp11": "att"})
    # the cruiser over the landing (cp10, cp11) is the Empire's, with the landing: their base
    imperial = ["cp1", "cp10", "cp11"]
    return {
        "pay": payload,
        # the outposts and ridge, the trenches and shield, then the cannon and the base
        "rush": dict(common, attackerBase=imperial),
        # the Empire holds its landing against Rebel waves from the north
        "horde": dict(common, lastStand="cp1", hordeSpawns=["cp4", "cp3"], shopPads=["cp2"]),
        # plant at the shield generator or the ion cannon
        "snd": dict(common, attackerSpawn="cp1", defenderSpawn="cp9", sites=["cp7", "cp8"]),
        "inf": hth_infiltration(common, h),
    }


def hth_infiltration(common, h):
    """Infiltration on Hoth: an Imperial squad starts on the cruiser's deck, flies TIE fighters
    down, destroys the Rebels' parked snowspeeders, and flies back up to hold Cruiser Control.
    No bot squadmates: bots can't fly, so they'd be stuck on the deck."""
    import hoth

    def ground(x, z, lift=1.5):
        return [round(x, 1), round(hoth.height_at(h, x, z) + lift, 1), round(z, 1)]
    # TIEs along the back of the hangar, clear of its fighter spawns and posts
    rides = [[round(v, 1) for v in hoth.ship_point(dx, 1.5, 0.0)] for dx in (-75.0, -45.0, -15.0, 15.0, 45.0, 75.0)]
    # when the speeders are down: TIEs on open snow south of the trench and near the shield
    # generator, ion cannon and base, nearest the survivors
    escape = [ground(-430, 560), ground(430, 560), ground(-620, 880), ground(700, 900), ground(0, 980)]
    return dict(common, insertion="cp10", extraction="cp11", squadBots=0,
                rideClass="imp_fly_tiefighter", rides=rides, escapeRides=escape,
                extractRadius=20.0, extractHeight=15.0,
                targetClass="all_fly_snowspeeder", memoryPools={"EntityFlyer": 16},
                targets=[{"post": "cp5"}, {"post": "cp6"}, {"post": "cp7"}, {"post": "cp8"}, ground(0, 1100)])


MAP_FN = {"pay": "PayloadMap", "rush": "RushMap", "horde": "HordeMap", "snd": "SnDMap", "inf": "InfiltrationMap"}
NAMES = {"gts": "Ground to Space", "hth": "Hoth"}


def mode_configs():
    """{(mode, code): Lua source} for every mode on every generated map."""
    out = {}
    for code, eras, fn in (("gts", "cg", gts_modes), ("hth", "g", hth_modes)):
        for era in eras:
            for mode, cfg in fn(era).items():
                header = ("-- %s (%s): %s, made by mods/mapgen/modes.py from the generated map. Rerun it\n"
                          "-- after changing the map; edit this file only to try something.\n\n"
                          % (NAMES[code], "Clone Wars" if era == "c" else "Galactic Civil War", MAP_FN[mode][:-3]))
                out[(mode, code + era)] = header + '%s("%s%s", %s)\n' % (MAP_FN[mode], code, era, lua(cfg, ""))
    return out


def write_mode_configs(maps_dir=MODES_DIR):
    written = []
    for (mode, code), text in mode_configs().items():
        path = os.path.join(maps_dir, mode, code + ".lua")
        with open(path, "w") as f:
            f.write(text)
        written.append(path)
    return written


# ---------------------------------------------------------------- the map AddOns' own files

ADDME = '''--
-- {code}: registers "{name}" (made by mods/mapgen). Its custom modes (Payload, Rush and so on) are
-- registered by the CUSTOMMODES AddOn; this adds Conquest to the same row of the map lists.
--

local function AddToList(List, Map, Era, Mode)
	if not List then return end
	local Want = string.lower(Map .. "%s_%s")
	local i
	for i = 1, table.getn(List) do
		if List[i].mapluafile and string.lower(List[i].mapluafile) == Want then
			List[i]["era_" .. Era] = 1
			List[i]["mode_" .. Mode .. "_" .. Era] = 1
			return
		end
	end
	local Row = {{ mapluafile = Map .. "%s_%s" }}
	Row["era_" .. Era] = 1
	Row["mode_" .. Mode .. "_" .. Era] = 1
	table.insert(List, Row)
end

{entries}
'''


def addon_files(code, eras, name):
    """{relative path: text} for a map's data folder: addme/addme.lua, Common/mission.req and a
    Common/mission/<mission>.req for each Conquest mission."""
    missions = ["%s%s_con" % (code, era) for era in eras]
    entries = []
    for era in eras:
        entries.append('AddToList(sp_missionselect_listbox_contents, "%s", "%s", "con")' % (code, era))
        entries.append('AddToList(mp_missionselect_listbox_contents, "%s", "%s", "con")' % (code, era))
        entries.append('AddDownloadableContent("%s", "%s%s_con", 4)' % (code, code, era))
    out = {os.path.join("addme", "addme.lua"): ADDME.format(code=code, name=name, entries="\n".join(entries))}
    out[os.path.join("Common", "mission.req")] = ("ucft\n{\n\tREQN\n\t{\n\t\t\"lvl\"\n%s\n\t}\n}\n"
                                                  % "\n".join('\t\t"%s"' % m for m in missions))
    for m in missions:
        out[os.path.join("Common", "mission", m + ".req")] = ("ucft\n{\n\tREQN\n\t{\n\t\t\"script\"\n\t\t\"%s\"\n\t}\n}\n" % m)
    return out


def main():
    for path in write_mode_configs():
        print("wrote %s" % os.path.relpath(path, os.path.dirname(os.path.dirname(HERE))))


if __name__ == "__main__":
    main()
