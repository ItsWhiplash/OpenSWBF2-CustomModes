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
| Mesas | West (45 m), east (55 m) and a north-west lookout (70 m), each with a ramp up. |
| The ship | A 660 m capital ship hull made of blocks, hanging with its hangar deck 380 m up over the north of the valley. Its 160 × 30 m hangar bay is open on the south side, facing the valley, for fighters to fly in. |
| Command posts | cp1 South Landing (attackers), cp2 West Mesa, cp3 Canyon Bridge (neutral), cp4 East Mesa and cp5 Shadow of the Ship on the ground. cp6 Hangar and cp7 Hangar Control are on the ship's deck. |
| Getting up | Fighters spawn at South Landing and under the ship (cp5). Fly into the hangar, or spawn on the deck once your side holds a ship post. |
| Bots | A navigation graph over the walkable valley: 573 hubs every 64 m, and about 1,000 links where the ground is gentle (soldier-only where it's steep). The deck has its own hubs. |
| Scripts | `GTSc_con.lua` and `GTSg_con.lua`: Conquest for both eras with the stock sides and heroes, fighters, `SetWorldExtents(1100)`, and fly heights up to 520 m. |

Everything the map uses that isn't stock is generated: the ship model and its prop class, the
hull plating texture, and the sand, dirt and rock terrain textures.

## Building it with the Mod Tools (on Windows)

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

## How the formats were made right

None of this could be munged or played in this session, so every format is ported from the
open-source SWBF2 world editor, [WorldEdit](https://github.com/PrismaticFlower/WorldEdit), and
checked against it:

- **Terrain (`ter.py`)** is a line-by-line port of WorldEdit's `terrain_io.cpp`. It reads
  WorldEdit's own sample terrain the way WorldEdit does. Our files round-trip byte for byte and
  have exactly the size its writer gives.
- **Models (`msh.py`)** port WorldEdit's `.msh` writer, shaped like its "blocks" export: a root
  node, a geometry mesh and a hidden collision mesh, plus a prop `.odf` and `.msh.option`.
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
- **Bots and the ship.** Ground bots have a navigation graph, but there are no flight paths, so
  AI pilots may not find the hangar. Bots that spawn on the deck do have hubs there.
- **Looks.** The ship is a block hull with simple plating, and there are no lights inside the
  hangar yet. The terrain textures are simple generated ones, easy to swap for stock ones in
  `gts.py`.
- **The custom modes** (Payload, Rush and so on) are built on stock maps' Conquest scripts. They
  don't run on this map yet; that's a follow-up.
