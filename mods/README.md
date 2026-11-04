# Custom modes and maps for OpenSWBF2: start here

| Folder | What it is |
|---|---|
| [`custommodes/`](custommodes/README.md) | Five new game modes, in one AddOn: **Payload**, **Rush**, **Horde**, **Search & Destroy** and **Infiltration**. They run on every stock map and on the generated maps, with on-screen text. |
| [`mapgen/`](mapgen/README.md) | The map generator, and two maps: **Ground to Space** (a desert valley with a capital ship overhead) and **Hoth** (a 4 km frozen battlefield, with an Imperial cruiser over the Empire's landing). |
| [`PLAYTEST.md`](PLAYTEST.md) | What to check first, mode by mode, with the quick-test build. |

All of it is Lua, data and Python: nothing here changes `BattlefrontII.exe`, so it works with the
OpenSWBF2 build you already have.

## What you need

- OpenSWBF2 and your game (Steam or GOG).
- [Python 3](https://www.python.org/downloads/) with "Add python.exe to PATH" ticked, plus
  numpy for the maps: `pip install numpy` (and `matplotlib` for the map previews).
- For the maps only: the SWBF2 Mod Tools.

## 1. The game modes

```bat
mods\install.bat
```

That builds the AddOn and copies it into your game's `AddOn\CUSTOMMODES`. It finds GameData in
Steam's usual folder; for GOG or elsewhere, first run
`set SWBF2_GAMEDATA=C:\GOG Games\Star Wars - Battlefront 2\GameData`. It also copies your game's
own text in, so no stock text shows `[NULL]` in these missions, and it removes the old `PAYLOAD`
AddOn if you have it.

The modes then appear in Instant Action and in multiplayer for every stock map (Payload needs a
track recorded first: see the custom modes README).

**For a first look, use the quick-test build** (`mods\install.bat quick`) and
[PLAYTEST.md](PLAYTEST.md).

## 2. The maps

1. In the Mod Tools' Visual Munge, make two new maps with the codes `GTS` and `HTH`. This only
   adds their build files.
2. Run `mods\mapgen\install_maps.bat generate`. It writes both maps into the Mod Tools folder (set
   `SWBF2_MODTOOLS` if they aren't in `C:\BF2_ModTools`). It also gives them stock looks from the
   Mod Tools' copy of the stock maps: Tatooine's ground, sky and weather for Ground to Space, and
   Hoth's for Hoth, with its shield generator and ion cannon. It lists what it used.
3. Munge `GTS` and `HTH` in Visual Munge.
4. Run `mods\mapgen\install_maps.bat copy`. It installs both into your game's `AddOn` folder.
5. Run `mods\install.bat` again: the custom modes on these maps come from the CUSTOMMODES AddOn.

Ground to Space has Conquest in both eras, and Hoth in the Galactic Civil War. Each also has all
five custom modes, laid out for the map:

| | Ground to Space | Hoth |
|---|---|---|
| Payload | Up the valley, over the canyon bridge, to the ground under the ship | From the Imperial landing, through the ridge pass and the trench, to the base |
| Rush | The valley, then the mesas, and last the ship's hangar | The outposts and ridge, then the trenches and shield, and last the cannon and base |
| Horde | Hold South Landing | The Empire holds its landing |
| Search & Destroy | The two mesas are the sites | The shield generator and the ion cannon are the sites |
| Infiltration | Four tanks by the valley posts | Tanks by the trenches, shield, cannon and the base |

## 3. A server

Copy `AddOn\CUSTOMMODES`, and `AddOn\GTS` and `AddOn\HTH` if you use them, into the server's
`AddOn` folder. For the Docker server, use its `addons` folder, and players who join with the
OpenBattlefront launcher download them automatically. Add missions to the rotation by name, such
as `tat2g_rush`, `hthg_rush` or `gtsc_pay`.

## Tests and builds

`custommodes/tests/run_tests.sh` (Linux, macOS or WSL) runs everything:
- the modes against a mock of the engine, built from the game's own Lua;
- every custom mode on the generated maps, with their real command posts;
- the map formats, checked against WorldEdit's.

On GitHub, every push also builds the AddOn and both maps as downloads (the **Actions** tab, the
latest "custom modes" run).
