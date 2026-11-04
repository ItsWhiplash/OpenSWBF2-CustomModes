# Playtest checklist

Nothing here has been played in the game yet, so the first session is for finding out what
works. Work through it with the **quick-test build**, which shrinks every mode so each takes a few
minutes:

```bat
mods\install.bat quick
```

Run the game with a log, so the modes' own lines are recorded:

```bat
BattlefrontII.exe -console -log playtest.log
```

Each mode writes lines starting `OpenSWBF2 payload:`, `OpenSWBF2 rush:`, `OpenSWBF2 horde:`,
`OpenSWBF2 s&d:`, `OpenSWBF2 infiltration:` or `OpenSWBF2 custom mode:`. When something's off,
send me the log (or those lines), the map and mode, and what you saw. A screenshot helps.

When you're done, run `mods\install.bat` again for the normal build.

## Quick-test settings

| Mode | Quick test |
|---|---|
| Payload | 3 minute clock, the cart moves 4–8 m/s, it rolls back after 10 s alone |
| Rush | 30 attacker lives, 10 more per post |
| Horde | Wave 1 has 4 enemies (+2 a wave), boss every 2nd wave, 10 s first break and 8 s breaks, 300 credits to start |
| Search & Destroy | 16 s setup, 60 s rounds, 3 s plant, 15 s bomb, 4 s defuse, first to 2, swap after round 1 |
| Infiltration | 16 s spawn window, 2 targets, 3 quiet guards and 6 in an alarm, 20 s alarms |

## Everything

- [ ] The modes appear in Instant Action's mode list as **Payload, Rush, Horde, Search &
      Destroy, Infiltration**, on the stock maps.
- [ ] A mission loads (try Rush on Mos Eisley).
- [ ] On-screen messages show real text, not `[NULL]`, for example "Post captured! Lives added."
- [ ] Stock text (class names, HUD labels) isn't `[NULL]`. If it is, the install's `--gamedata`
      text copy should have fixed it: tell me.

## Payload (try Mos Eisley: a track has to be recorded first)

- [ ] With no track, the mission records one: walk a route, quit, run `extract_track.py` on the
      log, paste the track into `mods/custommodes/maps/pay/tat2g.lua`, and reinstall.
- [ ] The cart moves only with attackers near it, faster with more (up to the cap), and stops
      when a defender is near.
- [ ] Alone for 10 s, it rolls back, but never past a checkpoint.
- [ ] Nobody can climb in, and it can't be destroyed.
- [ ] **Watch:** does it bob or sink as it moves? (`heightOffset` adjusts it.)

## Rush (any stock map)

- [ ] Only the current stage's posts can be captured. A captured post can't be retaken.
- [ ] Attacker lives drop per death and rise by 10 per post. Out of lives, the attackers lose.
- [ ] **Watch:** posts opened after stage 1 use a round capture area. Does the capture ring on
      the HUD look right?

## Horde (any stock map)

- [ ] Waves come and grow, the boss comes every 2nd wave, and the dead come back in the break.
- [ ] **Watch:** during a wave, does the spawn screen keep you out (no post to pick)?
- [ ] Standing on a shop pad shows its item and price, and buys it after 2 s.
- [ ] An enhancement works (try Bacta Refinery). In multiplayer, does it work for a joined
      player too?

## Search & Destroy (any stock map)

- [ ] 16 s to spawn, then no respawns. Planting takes 3 s on a site, and defusing 4 s.
- [ ] The bomb destroys the site's post, and it's back next round. The sides swap after round 1.

## Infiltration (any stock map)

- [ ] One life: the insertion post closes after 16 s.
- [ ] Both targets appear (enemy tanks by posts), and nobody can drive them.
- [ ] Destroying one sounds the alarm: more guards, aggressive. It calms down, then the next
      alarm is bigger.
- [ ] With both destroyed, standing at the insertion post for 5 s wins.

## The generated maps (see mods/mapgen/README.md to build them)

**Ground to Space (GTS):**

- [ ] The map loads, and the ship hangs over the north of the valley with the hangar facing
      you. (If the ship is invisible, or the hangar faces north, the model orientation is
      wrong: tell me.)
- [ ] Fighters spawn at South Landing and under the ship, and you can fly into the hangar.
- [ ] The hangar's lights and light strips glow.
- [ ] Bots move around the valley.
- [ ] Every custom mode runs here too (for example Rush ends on the ship).

**Hoth (HTH):**

- [ ] The base, the stock shield generator and ion cannon, and the turrets look right, and the walkers and
      speeders spawn.
- [ ] Rush on Hoth plays as a push from the south up to the base hangar.
- [ ] Payload drives the cart up the middle, through the ridge pass and the trench.

**Both:**

- [ ] The ground, sky and weather are the stock ones (Tatooine's on Ground to Space, Hoth's on
      Hoth). If a texture looks wrong (say, cliff rock on the flats), send me what
      `install_maps.bat generate` printed.

- [ ] **Watch:** the munge's log. Any missing class names (units, vehicles) are easy to fix in
      `gts.py` and `hoth.py`.
