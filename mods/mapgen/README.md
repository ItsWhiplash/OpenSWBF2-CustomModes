# Map generator ("maps as code")

Builds SWBF2 maps from Python instead of by hand in ZeroEditor. It writes the same source files
the SWBF2 Mod Tools build into a playable map:
- the terrain;
- the world, with its objects, command posts, regions and paths;
- the bots' navigation graph;
- custom models and textures;
- the mission scripts.

You can still open the result in ZeroEditor to polish it.

The first map is **GTS, "Ground to Space"**: a 2 km desert valley with a capital ship hanging
380 m overhead.

```bash
python mods/mapgen/gts.py --preview
```

This writes `mods/mapgen/out/data_GTS` (a mod-tools map folder), plus preview images in
`mods/mapgen/out/preview`. It needs Python 3 with numpy, and matplotlib for the previews
(`pip install numpy matplotlib`).

## The map

| | |
|---|---|
| Terrain | 256 × 256 points 8 m apart: 2048 m across, inside a ring of mountains. The boundary is a 900 m circle. |
| Valley | Sand flats with dunes. A winding canyon 28 m deep crosses the middle, with a land bridge at the centre. |
| Mesas | West (45 m), east (55 m) and a north-west lookout (70 m), each with a ramp up and cliffs banded in sandstone strata. Sandstone spires, boulders and dune ripples cover the valley floor. |
| The ship | A 690 m capital ship hanging with its hangar deck 380 m up over the north of the valley. It has a wedge hull lofted through cross-sections (bevelled sides, a raised spine), a command tower with a wide bridge, sensor domes and a mast, three engine nacelles with glowing exhausts, and turrets and plating across the top. Under the hull, a hangar pod 180 m wide is open to the valley for fighters to fly in, with light strips on its ceiling and four point lights inside. |
| Command posts | cp1 South Landing (attackers), cp2 West Mesa, cp3 Canyon Bridge (neutral), cp4 East Mesa and cp5 Shadow of the Ship on the ground. cp6 Hangar and cp7 Hangar Control are on the ship's deck. |
| Getting up | Fighters spawn at South Landing and under the ship (cp5). Fly into the hangar, or spawn on the deck once your side holds a ship post. |
| Bots | A navigation graph over the walkable valley: 573 hubs every 64 m, and about 1,000 links where the ground is gentle (soldier-only where it's steep). The deck has its own hubs. |
| Scripts | `GTSc_con.lua` and `GTSg_con.lua`: Conquest for both eras with the stock sides and heroes, fighters, `SetWorldExtents(1100)`, and fly heights up to 520 m. |

Everything the map uses that isn't stock is generated: the ship model and its prop class, the
hull plating texture, and the sand, dirt and rock terrain textures.

## The second map: HTH, "Hoth"

```bash
python mods/mapgen/hoth.py --preview
```

A 4 km frozen battlefield (512 × 512 terrain points 8 m apart), Galactic Civil War only. It has
four times the area of Ground to Space. The Empire attacks from the south, and the Rebels hold
the rest:

| | |
|---|---|
| Terrain | Rolling snowfields with drifts, rock and ice outcrops (some 20–40 m spires) for cover, a long ridge across the middle with a pass at the centre, and a frozen lake. Jagged mountains (ridged noise, up to about 540 m) ring the map and close in behind the base. The boundary is an oval about 3.4 × 3.1 km. |
| Defences | A zig-zag trench line 3.5 m deep across the north, with crossings at the centre and both ends, and six gun bunkers behind it. Further back are a shield generator (a stepped dome with a mast) and an ion cannon (a ball turret with a raised barrel). |
| The base | A long bunker set into the mountain foot, on a cleared terrace. Its 140 × 28 m hangar is open to the plain. |
| The cruiser | Ground to Space's capital ship, as an Imperial cruiser: it hangs over the Imperial landing with its deck 420 m up, turned so its lit hangar opens north, toward the battle. |
| Command posts | Eleven. On the ground: cp1 Imperial Landing (Empire), cp2 Frozen Outpost, cp3 Ice Lake, cp4 Ridge Pass, cp5 West Trench, cp6 East Trench, cp7 Shield Generator, cp8 Ion Cannon and cp9 Base Hangar (inside the hangar). On the cruiser's deck: cp10 Cruiser Hangar and cp11 Cruiser Control (Empire). In Rush, the landing and the cruiser are the Empire's base, and the other eight split into 3, 3 and 2 stages, nearest first. |
| Vehicles | Two AT-ATs and three AT-STs at the Imperial landing; two snowspeeders at the base, and tauntauns at the trenches. Fighters are the way up: TIE fighters in the cruiser's hangar and X-wings beside the base. Whoever holds a post gets their own side's fighter there, so Rebels who take the hangar fly X-wings out of it. |
| Bots | A navigation graph of about 1,300 hubs and 2,500 links over the walkable plain, with hubs in the hangar joined to the terrace outside. |
| Script | `HTHg_con.lua`: Conquest with the stock Hoth snow units, Vader and Luke, walkers (`AddWalkerType`), TIE fighters and X-wings, `SetWorldExtents(2200)`, and fly heights up to 620 m. |

The structures are generated models, like Ground to Space's ship:
- `hth_base`: a bunker under a vaulted roof, with its blast doors drawn back, a lit hangar and a
  dish antenna;
- `hth_shieldgen`: a dome on a drum with a glowing ring, a mast and a dish;
- `hth_ioncannon`: a ball turret on a pedestal, with a long raised barrel and a glowing muzzle;
- `hth_bunker`: round gun turrets.

The hangar, the shield generator and the ion cannon also have point lights, and the mountains
keep their snow except on the sheerest faces. They share a generated plating texture, and
the snow, packed snow, ice and rock terrain textures are generated too. The layout is original,
not a copy of the stock Hoth map, and it builds and installs the same way as Ground to Space
(with the code `HTH`).

## Building it with the Mod Tools (on Windows)

`install_maps.bat generate`, then munge, then `install_maps.bat copy` does this for both maps (see
[the start page](../README.md)). Step by step:

This part needs the Windows-only SWBF2 Mod Tools; the generator itself runs anywhere.

1. Install the SWBF2 Mod Tools.
2. Make a new map with the code `GTS` the usual way (Visual Munge's new-map option, which copies
   the template into `data_GTS`). That gives the folder its munge batch files, sky, sound and
   the rest.
3. Copy this generator's `out/data_GTS` over it. Your files win. That covers
   `Worlds/GTS/world1`, `Worlds/GTS/msh`, `Worlds/GTS/odf` and `Common/scripts/GTS`.
4. Munge it with Visual Munge (or the folder's `_BUILD` batch files). Then copy the result from
   `_LVL_PC` into an AddOn folder, as the Mod Tools' own instructions describe.
5. Optionally, open `Worlds/GTS/world1/GTS.wld` in ZeroEditor to look around or polish.

## Stock looks

Built with `install_maps.bat generate` (or `--stock <Mod Tools folder>`), the maps take their
looks from the Mod Tools' own copy of the stock maps, `assets\worlds\<CODE>`. `stock.py` reads
the stock files there, so no stock file name is guessed:

| | Ground to Space (from Tatooine, `TAT`) | Hoth (from Hoth, `HOT`) |
|---|---|---|
| Terrain textures | Each of our layers takes the stock layer whose name and colour fit it best (sand, dirt and rock), with the stock scale and detail texture | Snow, packed snow, ice and rock, the same way |
| Sky and weather | The stock world's `.sky` (fog, sun, sky dome) and `.fx`, as `GTS.sky` and `GTS.fx` | The same, as `HTH.sky` and `HTH.fx` |
| Models | The ship stays ours | The stock shield generator and ion cannon replace ours, if they fit their spots (40 m from the centre). The base and gun bunkers stay ours: the hangar post and the bots' paths are built around them |

Whatever is copied brings what it uses: a class its parent class, model and explosion, a model
its textures, a sky its dome. `generate` prints what it picked. Anything it can't find keeps the
generated version, so the map still builds. Choose another stock world with `--stock-world`, for
example `python mods\mapgen\gts.py --out C:\BF2_ModTools --stock C:\BF2_ModTools --stock-world GEO`
for Geonosis's red rock.

The previews (and the CI build, which has no Mod Tools) still show the generated looks.

## How the formats were made right

None of this could be munged or played in this session, so every format is ported from the
open-source SWBF2 world editor, [WorldEdit](https://github.com/PrismaticFlower/WorldEdit), and
checked against it:

- **Terrain (`ter.py`)** is a line-by-line port of WorldEdit's `terrain_io.cpp`. It reads
  WorldEdit's own sample terrain the way WorldEdit does. Our files round-trip byte for byte and
  have exactly the size its writer gives.
- **Models (`msh.py`)** port WorldEdit's `.msh` writer, shaped like its "blocks" export: a root
  node, a geometry mesh and a hidden collision mesh, plus a prop `.odf` and `.msh.option`.
  Shapes (`shapes.py`: boxes, cylinders, cones, domes, tubes and lofted hulls) are made in game
  coordinates, facing outward. The writer mirrors Z into WorldEdit's model space and reverses
  each triangle, so the result winds the same way as WorldEdit's own cube. The tests check
  both.
- **World files (`world.py`)** follow WorldEdit's `save.cpp` line for line. That includes the
  Z axis, which WorldEdit flips between its view and the files. Command posts are linked to
  their regions and spawn paths the way its post tool makes them.

`test_mapgen.py` checks all of this, plus the map's own rules: posts on the ground or the deck,
spawn points at ground level, every navigation link between real hubs, and region and path counts
that match the files. With `--luac` it also checks the mission scripts compile.

## Not checked yet

- **The munge.** The files follow WorldEdit's writers, but the Mod Tools haven't processed them
  yet. If a step complains, its log line tells us which file to fix.
- **Stock class names**, including units, heroes, fighters (`rep_fly_arc170fighter`,
  `cis_fly_droidfighter`, `all_fly_xwing`, `imp_fly_tiefighter`), `com_bldg_controlzone` and
  the vehicle spawn's `ClassXxxATK`/`ClassXxxDEF` properties. These are from memory of the
  stock assets. The munge and the game's log will name any that don't exist, and they're all in
  one place in `gts.py`.
- **Bots and the ships.** Ground bots have a navigation graph, but there are no flight paths, so
  AI pilots may not find the hangars (on either map). Bots that spawn on a deck do have hubs there.
- **Looks.** The stock looks are picked from the stock files' names and colours. If one is a poor
  fit, `--stock-world` picks another world. Our own models (the ship, the base and the bunkers)
  have one generated plating texture each, and simple glowing materials. The point lights
  follow WorldEdit's light format, but how bright they look in the game needs a look in a match.
- **The custom modes** run on both maps: `modes.py` writes their settings into
  `custommodes/maps` (Payload's tracks follow the generated terrain), and the CUSTOMMODES AddOn
  runs each map's Conquest script from the map's own AddOn. That's why the scripts load their
  world by its path in the AddOn folder (`..\..\AddOn\GTS\Data\_lvl_pc\GTS\GTS.lvl`)
  rather than `dc:`. It relies on the AddOn folders being named `GTS` and `HTH`.
