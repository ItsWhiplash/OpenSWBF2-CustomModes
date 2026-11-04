# Custom game modes for OpenSWBF2

New game modes for the stock maps, packed as one AddOn folder:

- **[Payload](#payload)** (`_pay`): the attackers escort a vehicle along a track to the end of the
  map.
- **[Rush](#rush)** (`_rush`): the attackers capture command posts stage by stage, on limited
  lives.
- **[Horde](#horde)** (`_horde`): every player holds one post together against endless, growing
  waves, and spends kill credits at shop pads between waves.
- **[Search & Destroy](#search--destroy)** (`_snd`): rounds with one life each; the attackers
  plant a bomb at one of two sites, and the defenders stop or defuse it.

Both modes work in single player with bots, and on a server where anyone who joins can play.

## How it works

Everything is Lua inside an ordinary AddOn folder, so it doesn't change `BattlefrontII.exe`. It
works with the build you already have, on Windows or the Docker server.

- `CUSTOMMODES/addme.script` adds the modes to each stock map's mode list, in both eras where the
  map has them.
- `CUSTOMMODES/data/_lvl_pc/mission.lvl` holds:
  - the modes: `scripts/objectivepayload.lua`, `scripts/objectiverush.lua`,
    `scripts/objectivehorde.lua` and `scripts/objectivesnd.lua`;
  - the shared loader: `scripts/custommode_mission.lua`;
  - one small mission per map and mode: `maps/<mode>/<map><era>.lua`, for example
    `maps/rush/tat2g.lua` for `tat2g_rush`.

A custom mission doesn't copy the map's loading code. It reads the stock Conquest mission (for
example `tat2g_con`) from your game's own `mission.lvl` and runs it, with three changes:

1. It loads anything extra the mode needs, such as Payload's vehicle class.
2. It creates Conquest's objective without running it. The rest of the map's setup still runs:
   death regions, doors, hero rules and the command posts.
3. It starts the custom mode instead.

The rules run only where the match is hosted: on your own PC in single player (bot matches
included), or on the server in multiplayer. Players who join don't need to run anything
themselves.

## Install

Build the AddOn folder (Python 3, any OS):

```bash
python mods/custommodes/build.py
```

That writes `mods/custommodes/out/CUSTOMMODES`. Copy that folder:

- **Your PC:** into `GameData\AddOn\` (create `AddOn` if it doesn't exist).
- **Docker server:** into `addons/` next to `compose.yaml`, then restart. Players who join with the
  OpenBattlefront launcher get the folder from the server automatically (*Mod downloads* in
  `docker/README.md`). Admins can also upload it from the launcher.
- **Windows dedicated server:** into its `GameData\AddOn\`. Each player also needs it in their
  own `AddOn` folder. The game refuses a player who lacks a mission in the server's rotation (the
  log says `join refused missing=...`).

If you installed the earlier `PAYLOAD` folder, delete it: `CUSTOMMODES` replaces it, and both
would register the same Payload missions.

The modes appear in the map and mode lists. On a server, you can add them to the rotation by
name, for example `BattlefrontII.exe -dedicated tat2g_pay nab2c_rush`. Use `--modes rush` or
`--only tat2g,nab2c` to build only some modes or maps.

## Payload

The attackers escort a vehicle along a fixed track to the end of the map, and the defenders try
to stop it.

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

### Making a map playable: record its track

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
   python mods/custommodes/extract_track.py payload.log
   ```

   This prints a `track = { ... }` block, and each command post with the track point nearest to
   it. Use `--reverse` if you walked from the finish to the start, and `--every 2` to thin the
   points out.
5. Paste the block into `mods/custommodes/maps/pay/<map><era>.lua`, set the checkpoints and
   command posts (see below), and rebuild. To record again, set `record = true`.

### Payload settings

Each `maps/pay/<map><era>.lua` calls `PayloadMap` with the map's settings. Anything you leave
out uses the default.

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

## Rush

The map's command posts are split into stages, 3, 3 and 2 by default. The attackers must capture
every post in a stage to open the next, and they win by taking the last stage.

- Only the current stage's posts can be captured. Later stages are locked until the stage
  before them falls.
- Posts the attackers take are locked to them, so the defenders can't win them back. Each one
  becomes an attacker spawn, so the front moves forward.
- The attackers have limited lives, 100 by default. Every death costs one, and every post they
  take adds 20. When they run out, the defenders win.
- The defenders have unlimited lives, and spawn at the posts they still hold.
- On the scoreboard, the attackers' score is posts taken and the defenders' is posts left. The
  open posts are marked on the HUD.

Bots play it too: both teams' AI go for the open posts (the attackers to take them, the
defenders to hold them), and some roam and fight. The bot count comes from your Instant Action or
server settings.

Every map works straight away, with no recording. With no stages listed, the attackers start at
their post farthest from the defenders. The other posts are taken nearest-first from there and
grouped into stages. Stock maps have fewer than the 9 posts that 3/3/2 needs, so the stages
shrink from the back (7 posts: 3/2/2; 6: 2/2/2; 5: 2/2/1). The log shows the layout chosen, in
lines like `OpenSWBF2 rush: stage 1: cp3, cp4, cp2`. To choose your own, list the stages in
`maps/rush/<map><era>.lua`. Posts in no stage stay locked as the defenders' rear spawns.

### Rush settings

```lua
RushMap("tat2g", {
	stages = { { "cp2", "cp3", "cp4" }, { "cp5", "cp6", "cp7" }, { "cp8", "cp9" } },
	attackerBase = { "cp1" },
	attackerTickets = 75,
})
```

| Setting | Default | |
|---|---|---|
| `stages` | worked out | Lists of post names, first stage first. |
| `attackerBase` | worked out | Posts the attackers start with (locked). |
| `stageSizes` | `{ 3, 3, 2 }` | Stage sizes for the automatic layout, shrunk to fit the map. |
| `attackerTickets` | `100` | The attackers' lives at the start. |
| `ticketsPerCapture` | `20` | Lives added for each post taken (once per post). |
| `stageClearTickets` | `0` | Extra lives when a stage falls. |
| `lockCaptured` | `true` | Taken posts can't be won back. Even with `false`, a fallen stage stays locked. |
| `captureRadius` | `10` | Metres. Posts opened after stage 1 get a round capture region this size (stage 1 keeps the map's own). |
| `timeLimit` / `stageBonusTime` | `0` / `0` | A clock (none by default: lives are the limit), and seconds added when a stage falls. |
| `aiObjectiveWeight` / `aiFightWeight` | `100` / `25` | How strongly bots go for the open posts, and how strongly they roam and fight instead. |
| `attackers` | stock `ATT` | `"def"` swaps which side attacks. |

## Horde

Every human player is on one team, with their bot allies, holding one command post (the last
stand) against endless waves of the other side's army.

- **Waves.** Wave 1 has 10 enemies, and each wave after has 4 more. The enemy counter on the HUD
  shows how many are left, and the other team's score shows the wave number. How many are alive
  at once follows the bot count in your Instant Action or server settings.
- **Tougher enemies.** Enemy health rises 10% a wave, up to 4×.
- **Bosses.** Every 5th wave, the enemy side's hero (whoever the map loads) joins as a boss with
  3× health on top of the wave's. It's worth 100 credits.
- **Deaths.** Anyone who dies in a wave is out until the break. Between waves there's a 20 s
  break (30 s before the first wave), and everyone comes back. A wave doesn't start until
  someone on your team is alive, so solo players can take their time on the spawn screen.
- **Losing.** You lose if the horde overruns the last stand (stands on it for 10 s with none of
  you near), or if every defender is down at once. The score is how many waves you survived.

### The shop

Each kill earns 5 credits for the whole team, shown as your team's score. In each break, the
map's spare command posts become **shop pads**, marked on the HUD, each offering one item. A
human standing on a pad for 2 s buys its item if the team can afford it. A pad sells once a
break, and the offers change every break.

| Item | Credits | |
|---|---|---|
| Surveillance | 75 | Enemies show on the map. |
| Adrenaline | 100 | Energy regenerates 3× faster. |
| Bacta Refinery | 150 | Health regenerates. |
| Advanced Armor | 150 | 25% extra health on spawning. |
| Blaster Amplification | 250 | More damage. |
| Leadership | 300 | Your team's hero comes back. |
| Hero | 250 | Unlocks your side's hero for the team. Someone picks it on the spawn screen. |
| Speeder bike | 80 | Appears next to the last stand. |
| Hover tank | 200 | Appears next to the last stand. |

The first six are Galactic Conquest's enhancements, which the engine runs one per team at a
time: buying one replaces the one you have, and the one you have isn't offered. Stepping on a pad
shows the enhancement's name, using the game's own Galactic Conquest text. The hero and vehicle
pads don't show a name.

Every map works straight away. The last stand is the players' post farthest from the enemy's.
The horde spawns at the two posts farthest from it (one on a three-post map). Every other post
is a shop pad. The log says which, in a line starting `OpenSWBF2 horde: last stand`. Nothing can
be captured in Horde.

### Horde settings

```lua
HordeMap("tat2g", {
	lastStand = "cp1",
	hordeSpawns = { "cp5", "cp6" },
	shopPads = { "cp2", "cp3", "cp4" },
	firstWave = 15,
	creditsPerKill = 10,
})
```

| Setting | Default | |
|---|---|---|
| `lastStand` / `hordeSpawns` / `shopPads` | worked out | Post names. |
| `hordeSpawnCount` | `2` | For the automatic layout. |
| `firstWave` / `perWave` | `10` / `4` | Enemies in wave 1, and how many more each wave. |
| `healthPerWave` / `maxHealthMult` | `0.10` / `4.0` | Enemy health growth per wave, and its cap. |
| `bossEvery` / `bossHealthMult` | `5` / `3.0` | A boss every Nth wave (`0`: never), and its extra health. |
| `breakTime` / `firstBreak` | `20` / `30` | Seconds between waves, and before the first. |
| `overrunRadius` / `overrunTime` | `12` / `10` | How close, and for how long, the horde must hold the last stand with no defender near. |
| `wipeGrace` | `3` | Seconds with every defender down before it's over. |
| `creditsPerKill` / `creditsPerBoss` / `startCredits` | `5` / `100` / `0` | Credits (the score shows up to 895). |
| `shop` | per era | The items: `{ id, kind = "bonus" \| "hero" \| "vehicle", price, bonus, class, message }`. `HordeShop("g")` is the default. |
| `padRadius` / `buyHoldTime` | `6` / `2` | How close to a pad, and for how long, to buy. |
| `playersTeam` / `hordeTeam` | `1` / `2` | The humans' team (all humans are put on team 1). |
| `aiObjectiveWeight` / `aiFightWeight` | `100` / `25` | How strongly bots on both sides go for the last stand, and how strongly they roam and fight instead. |

## Search & Destroy

Rounds, with one life each. Two command posts are bomb sites, marked on the HUD.

- **Setup.** Each round starts with 20 s to spawn. Your team owns its spawn post, and no bomb can
  be planted yet. Then both spawn posts go neutral, and nobody spawns again until the next round.
  The 20 s covers the 15 s cycle the engine spawns multiplayer players in. A round doesn't start
  while a side has nobody alive, so a solo player can take their time choosing a class.
- **Planting.** An attacker standing at a site for 5 s plants the bomb. Stepping off restarts the
  plant, so the only way to stop it is to kill them. The round clock (2:30) becomes the bomb's
  40 s, and only that site's marker stays, pulsing.
- **Defusing.** A defender standing on the armed site for 7 s defuses it. Stepping off restarts
  the defuse.
- **Winning a round.** The attackers win when the bomb goes off (destroying the site's post, for
  the blast), or when every defender is dead. The defenders win by defusing, by killing every
  attacker before a plant, or when the clock runs out with no plant. After a plant, only the
  bomb or a defuse decides it.
- **The match.** First to 4 round wins. The sides swap roles after round 3, so the attackers'
  spawn and the sites change hands. Each team's score is its rounds won.
- **Between rounds.** After 6 s, anyone still alive is killed, so the next round starts fresh.
  Those deaths show in the stats.

Bots play it too: both sides go for the sites, then for the armed one. An attacker bot on a site
plants, and a defender bot on an armed site defuses.

Every map works straight away. The two posts farthest apart are the spawns, and the attackers
get the one their side owns. The two posts nearest the defenders' spawn are the sites, or one
on a three-post map. The log says which, in a line starting `OpenSWBF2 s&d: attackers spawn`.
Nothing can be captured.

### Search & Destroy settings

```lua
SnDMap("tat2g", {
	attackerSpawn = "cp1",
	defenderSpawn = "cp6",
	sites = { "cp4", "cp5" },
	roundsToWin = 6,
	halftime = 5,
})
```

| Setting | Default | |
|---|---|---|
| `attackerSpawn` / `defenderSpawn` / `sites` | worked out | Post names. The spawns stay with the role when the sides swap. |
| `roundsToWin` / `halftime` | `4` / `3` | Round wins for the match, and rounds before the sides swap (`0`: never). |
| `setupTime` / `roundTime` | `20` / `150` | Seconds to spawn, and to plant. |
| `plantTime` / `bombTime` / `defuseTime` | `5` / `40` / `7` | Seconds. |
| `siteRadius` | `6` | Metres from a site's post to plant or defuse. |
| `roundEndTime` | `6` | Seconds between a round's end and the next. |
| `destroySites` | `true` | A detonation destroys the site's post (it comes back next round). |
| `attackers` | stock `ATT` | `"def"` swaps which side attacks first. |
| `aiObjectiveWeight` / `aiFightWeight` | `100` / `25` | How strongly bots go for the sites, and how strongly they roam and fight instead. |

## Tests

`mods/custommodes/tests/run_tests.sh` (Linux, macOS or WSL, with g++) builds the game's own
Lua 5.0 from `src/LuaFL`. It then checks every script's syntax with the game's compiler, and runs
both modes against a mock of the engine together with the real `objective.lua` and
`objectiveconquest.lua`.

- **Payload:** pushing speed and the cap, contesting, rollback to a checkpoint, checkpoints,
  delivery, time-out, overtime, the vehicle lock, respawning, recording.
- **Rush:** the automatic layout and stage sizes, locking and unlocking, lives per death and per
  capture, defeat, victory, bots and markers, set stages, the clock, `lockCaptured` off.
- **Horde:** the layout, wave sizes and enemy health, the dead staying down until the break,
  credits, the boss, the shop pads and their items, one enhancement at a time, the
  enhancement reaching clients, overrun, everyone down, and waiting for a player to spawn.
- **Search & Destroy:** the layout, one life per round, planting and its reset, detonation and
  the site coming back, defusing, elimination before and after a plant, time running out,
  halftime, the match, and waiting for a side to spawn.
- **All modes:** the client side, the loading hooks and the menu entries.

## Not tested in the game yet

These modes were written without the game, so these points have only been checked against the
source and the mock engine, not in a real match.

**Payload:**

- **How the vehicle moves.** The payload is moved by setting its position 10 times a second.
  The hover physics may make it bob, or sink at a different height. If it does, adjust
  `heightOffset`, or try another `payloadClass`.
- **Vehicle class names.** `imp_hover_fightertank` and `rep_hover_fightertank` must exist in the
  stock `SIDE\imp.lvl` and `SIDE\rep.lvl`. If a mission stops with "could not create", pick
  another hover class from that side.
- **Bot behavior.** The AI's Defend goal makes bots gather around the payload, but how closely
  they follow it while it moves still needs checking in a match.

**Rush:**

- **Locking.** A post is locked by removing its capture region, and opened with a new round one
  (the engine's `Radius` property). Both follow the engine source. Whether the capture ring on
  the HUD matches the new region still needs checking.
- **Automatic stages.** The automatic split follows straight-line distance from the attackers'
  base, which may not match how a map plays. Check the log and list the stages if it doesn't.

**Horde:**

- **Keeping the dead out.** Players can only spawn at a post their team owns. That is how the
  engine's spawn code reads, but the spawn screen with no post to pick hasn't been seen.
- **Enhancements in multiplayer.** The engine doesn't network them, so the server sends the
  active one in a team value that isn't shown on the HUD while team points are, and every
  machine switches it on itself. That follows the engine source.
- **Bosses.** Every 5th wave unlocks the enemy hero. Whether a bot takes it depends on the hero
  settings: OpenSWBF2's AI heroes option, or single player's hero rules.
- **Vehicles.** `imp_hover_speederbike` and `rep_hover_barcspeeder`, like Payload's tanks, need
  to exist in the stock sides. Change `shop` if one doesn't.
- **Text.** Pads use the game's Galactic Conquest text for names, so they only show if those
  strings are loaded in a battle.

**Search & Destroy:**

- **Destroying and restoring a site.** Destroying a post and bringing it back next round follows
  the engine source (`KillObject` / `RespawnObject`). How the destroyed post looks in the game,
  and whether the blast plays, hasn't been seen.
- **Clearing the field.** Survivors are killed between rounds. It's a plain kill, so it counts in
  the death stats, and some maps may show kill messages for it.

**All modes:**

- **Messages.** The game shows only localized text, so there are no custom on-screen messages.
  Progress shows in the score, the timer and the HUD markers.
