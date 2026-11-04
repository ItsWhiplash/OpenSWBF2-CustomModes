# Payload for OpenSWBF2

A new game mode for the stock maps. The attackers escort a vehicle along a fixed track to the
end of the map, and the defenders try to stop it.

- The payload moves only while attackers are within 8 m of it. One attacker moves it at
  1.5 m/s, and each extra attacker adds 0.5 m/s, up to 3.5 m/s with five.
- If any defender is within range, the payload stops (it's contested).
- If no attackers are near it for 30 s, it rolls back slowly, but never past the last
  checkpoint it reached.
- It can't be destroyed or driven. Anyone who gets in is put straight back out.
- Checkpoints add time to the clock and can hand command posts to the attackers, so their spawns
  move up behind the payload.
- The attackers win when the payload reaches the end. The defenders win when time runs out. If
  attackers are on the payload when the clock hits zero, overtime lasts until they leave it.
- On the scoreboard, the attackers' score is the percentage of the track covered. The defenders'
  score is the number of checkpoints still ahead.

Bots play it too: both teams' AI head for the payload, so the attackers escort it and the
defenders hold it, and some bots roam and fight. The bot count comes from your Instant Action
or server settings, the same as in Conquest.

## How it works

Everything is Lua inside an ordinary AddOn folder, so it doesn't change `BattlefrontII.exe`. It
works with the build you already have, on Windows or the Docker server.

- `PAYLOAD/addme.script` adds **Payload** to each stock map's mode list, in both eras where the
  map has them.
- `PAYLOAD/data/_lvl_pc/mission.lvl` holds the mode (`scripts/objectivepayload.lua`), the loader
  (`scripts/payload_mission.lua`), and one small mission per map (`maps/<map><era>.lua`, such as
  `tat2g.lua` for `tat2g_pay`).

A payload mission doesn't copy the map's loading code. It reads the stock Conquest mission (for
example `tat2g_con`) from your game's own `mission.lvl` and runs it, with three changes:

1. It also loads the payload vehicle's class.
2. It starts Conquest's objective without running it. The rest of the map's setup still runs:
   death regions, doors, hero rules and the command posts.
3. It starts Payload instead.

The rules run only where the match is hosted: on your own PC in single player (bot matches
included), or on the server in multiplayer. The payload is a real vehicle, so the netcode moves
it on every player's screen. Players who join don't need to run anything themselves.

## Install

Build the AddOn folder (Python 3, any OS):

```bash
python mods/payload/build.py
```

That writes `mods/payload/out/PAYLOAD`. Copy that folder:

- **Your PC:** into `GameData\AddOn\` (create `AddOn` if it doesn't exist).
- **Docker server:** into `addons/` next to `compose.yaml`, then restart. Players who join with the
  OpenBattlefront launcher get the folder from the server automatically (*Mod downloads* in
  `docker/README.md`). Admins can also upload it from the launcher.
- **Windows dedicated server:** into its `GameData\AddOn\`. Each player also needs it in their
  own `AddOn` folder. The game refuses a player who lacks a mission in the server's rotation (the
  log says `join refused missing=...`).

Payload appears in the map and mode lists, and on a server you can add it to the rotation by
name, for example `BattlefrontII.exe -dedicated tat2g_pay nab2c_pay`.

## Making a map playable: record its track

The maps come without tracks, because a track has to be walked in the game. When a map has no
track, its Payload mission records one instead:

1. Run the game with a log, for example `BattlefrontII.exe -console -log payload.log`.
2. In **Instant Action**, start Payload on the map. Bots are switched off while recording. Every
   command post's name and team is written to the log.
3. Spawn where the attackers should start, then walk (don't fly) the route the payload should
   take, all the way to its end point. A point is logged every 8 m. Keep to ground a hover tank
   can cover, and make the turns wide.
4. Quit, then turn the log into a track:

   ```bash
   python mods/payload/extract_track.py payload.log
   ```

   This prints a `track = { ... }` block, and each command post with the track point nearest to
   it. Use `--reverse` if you walked from the finish to the start, and `--every 2` to thin the
   points out.
5. Paste the block into `mods/payload/maps/<map><era>.lua`, set the checkpoints and command
   posts (see below), and rebuild. To record again, set `record = true`.

## Map settings

Each `maps/<map><era>.lua` calls `PayloadMap` with the map's settings. Anything you leave out
uses the default.

```lua
PayloadMap("tat2g", {
	track = { { 12.0, 3.1, -140.5 }, { 14.2, 3.0, -132.0 }, ... },
	checkpoints = {
		{ at = 0.33, giveCPs = { "cp2" } },     -- a third of the way: attackers get cp2
		{ point = 31, giveCPs = { "cp3" }, takeCPs = { "cp5" }, bonusTime = 90 },
	},
	initialCPs = { cp1 = "att", cp2 = "def", cp3 = "def" },
	attackers = "def",       -- swap which side attacks (default: the stock script's ATT)
})
```

| Setting | Default | |
|---|---|---|
| `track` | none | Points `{ x, y, z }` from start to end. Fewer than two points records a track instead. |
| `checkpoints` | none | `{ at = fraction }` or `{ point = n }`, with optional `giveCPs`, `takeCPs`, `bonusTime` and `message` (a localization key). |
| `initialCPs` | none | Command post owners at the start: `"att"` or `"def"`. |
| `disableCapture` | `true` | Command posts can't be captured, so spawns move only at checkpoints. |
| `pushRadius` / `pushHeight` | `8` / `5` | Metres (horizontal / vertical) within which a soldier counts as near the payload. |
| `baseSpeed` / `speedPerPusher` / `maxSpeed` / `maxPushers` | `1.5` / `0.5` / `3.5` / `5` | Speed in m/s with one attacker, extra per attacker, cap, and the most attackers that count. |
| `contestBlocks` | `true` | Any defender within range stops the payload. |
| `countVehicles` | `false` | Whether soldiers in vehicles count. |
| `rollbackDelay` / `rollbackSpeed` | `30` / `0.75` | Seconds without attackers before it rolls back (`-1`: never), and how fast it rolls back. |
| `timeLimit` / `checkpointBonusTime` | `600` / `120` | Seconds on the clock, and seconds each checkpoint adds. |
| `overtimeGrace` | `2` | Seconds in overtime without attackers before the defenders win. |
| `unlimitedReinforcements` | `true` | No tickets on either side. |
| `aiPayloadWeight` / `aiFightWeight` | `100` / `25` | How strongly bots go for the payload, and how strongly they roam and fight instead. |
| `payloadClass` | era tank | `imp_hover_fightertank` (GCW) or `rep_hover_fightertank` (CW). If you change it, also set `extraData = { { "SIDE\\xxx.lvl", "class" } }` so the class is loaded. |
| `heightOffset` / `yawOffset` | `0` / `0` | Metres to raise the payload, and degrees to turn it if the model faces the wrong way. |
| `recordSpacing` / `recordWithBots` | `8` / `false` | For recording. |

## Tests

`mods/payload/tests/run_tests.sh` (Linux, macOS or WSL, with g++) builds the game's own Lua 5.0
from `src/LuaFL`. It then checks every script's syntax with the game's compiler, and runs the
mode against a mock of the engine together with the real `objective.lua` and
`objectiveconquest.lua`. The tests cover pushing speed and the cap, contesting, rollback to a
checkpoint, checkpoints, delivery, time-out, overtime, the vehicle lock, respawning, recording,
the client side, the loading hooks and the menu entries.

## Not tested in the game yet

This was written without the game, so these points have only been checked against the source
and the mock engine, not in a real match:

- **How the vehicle moves.** The payload is moved by setting its position 10 times a second.
  The hover physics may make it bob, or sink at a different height. If it does, adjust
  `heightOffset`, or try another `payloadClass`.
- **Vehicle class names.** `imp_hover_fightertank` and `rep_hover_fightertank` must exist in the
  stock `SIDE\imp.lvl` and `SIDE\rep.lvl`. If a mission stops with "could not create", pick
  another hover class from that side.
- **Messages.** The game shows only localized text, so checkpoint messages aren't shown unless
  you give a `message` key. Progress shows in the score, the timer and the marker over the
  payload.
- **Bot behavior.** The AI's Defend goal makes bots gather around the payload, but how closely
  they follow it while it moves still needs checking in a match.
