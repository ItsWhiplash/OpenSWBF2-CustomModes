"""The custom modes' on-screen text, by key (the scripts say "custommodes.<key>").

The game shows text only by key (ShowMessageText sends a key's hash to every player), so a
message with a number in it has a key per number: horde.wave.1, horde.wave.2, and so on.
build.py writes these into mission.lvl, in English, under every language the game supports.
"""

MAX_N = 99


def table():
    t = {}

    # mode names in the menus (the shell's missionlist looks up modename.name.<id>)
    for mode, name, desc in (
        ("pay", "Payload", "Escort the payload to the end of the track, or stop it."),
        ("rush", "Rush", "Capture the command posts stage by stage on limited lives, or hold them."),
        ("horde", "Horde", "Hold the last stand against endless waves; spend credits between them."),
        ("snd", "Search & Destroy", "One life per round: plant the bomb at a site, or stop it."),
        ("inf", "Infiltration", "Co-op: destroy every target with one life each, then extract."),
    ):
        t["modename.name." + mode] = name
        t["modename.description." + mode] = desc

    # Payload
    t["custommodes.pay.start.att"] = "Escort the payload! Stay near it to move it."
    t["custommodes.pay.start.def"] = "Stop the payload! Stand near it to block it."
    t["custommodes.pay.checkpoint.att"] = "Checkpoint reached! More time added."
    t["custommodes.pay.checkpoint.def"] = "Checkpoint lost! Fall back."
    t["custommodes.pay.rollback"] = "The payload is rolling back."
    t["custommodes.pay.overtime"] = "OVERTIME!"
    t["custommodes.pay.recording"] = "Recording a track: walk the payload's route, then quit."

    # Rush
    t["custommodes.rush.start.att"] = "Capture every post in the stage to unlock the next."
    t["custommodes.rush.start.def"] = "Hold the posts! The attackers have limited lives."
    t["custommodes.rush.taken.att"] = "Post captured! Lives added."
    t["custommodes.rush.taken.def"] = "A post has fallen!"
    for n in range(1, 10):
        t["custommodes.rush.stage.%d.att" % n] = "Stage %d cleared! The next stage is unlocked." % n
        t["custommodes.rush.stage.%d.def" % n] = "Stage %d lost! Fall back to the next posts." % n
    t["custommodes.rush.final.att"] = "Final stage!"
    t["custommodes.rush.final.def"] = "Final stage: hold at all costs!"

    # Horde
    for n in range(1, MAX_N + 1):
        t["custommodes.horde.wave.%d" % n] = "Wave %d!" % n
        t["custommodes.horde.next.%d" % n] = "Wave %d is coming. Visit the shop pads." % n
        t["custommodes.horde.cleared.%d" % n] = "Wave %d cleared!" % n
    t["custommodes.horde.boss"] = "BOSS WAVE!"
    t["custommodes.horde.bossdown"] = "The boss is down!"
    t["custommodes.horde.overrun"] = "The last stand is being overrun!"
    t["custommodes.horde.start"] = "Hold the last stand. Stand on a shop pad between waves to buy."
    t["custommodes.horde.poor"] = "Not enough credits."
    for item, name, price in (
        ("sensor_array", "Surveillance: enemies on the map", 75),
        ("energy_boost", "Adrenaline: faster energy", 100),
        ("bacta_tanks", "Bacta Refinery: health regenerates", 150),
        ("combat_shielding", "Advanced Armor: extra health", 150),
        ("advanced_blasters", "Blaster Amplification: more damage", 250),
        ("leader", "Leadership: your hero returns", 300),
        ("hero", "Hero: unlock your side's hero", 250),
        ("bike", "Speeder bike", 80),
        ("tank", "Hover tank", 200),
    ):
        t["custommodes.horde.item.%s" % item] = "%s (%d credits)" % (name, price)
        t["custommodes.horde.bought.%s" % item] = "Bought: %s" % name.split(":")[0]

    # Search & Destroy
    t["custommodes.snd.round.att"] = "Attack: plant the bomb at site A or B."
    t["custommodes.snd.round.def"] = "Defend sites A and B."
    t["custommodes.snd.live"] = "Go! No more respawns this round."
    for site in ("a", "b"):
        t["custommodes.snd.planted.%s" % site] = "Bomb planted at site %s!" % site.upper()
    t["custommodes.snd.defused"] = "Bomb defused!"
    t["custommodes.snd.detonated"] = "The bomb went off!"
    t["custommodes.snd.won"] = "Round won!"
    t["custommodes.snd.lost"] = "Round lost."
    t["custommodes.snd.halftime"] = "Halftime: switching sides."
    t["custommodes.snd.matchpoint"] = "Match point!"

    # Infiltration
    t["custommodes.inf.insert"] = "Insert now: one life each. Destroy every target."
    t["custommodes.inf.insert.ride"] = "Insert now: take a vehicle in. One life each. Destroy every target."
    t["custommodes.inf.in"] = "The squad is in. Stay quiet."
    t["custommodes.inf.alarm"] = "ALARM! Reinforcements inbound!"
    t["custommodes.inf.calm"] = "The garrison is standing down."
    for n in range(0, 21):
        t["custommodes.inf.left.%d" % n] = "Target destroyed: %d left." % n
    t["custommodes.inf.extract"] = "All targets destroyed! Get to the extraction point."
    t["custommodes.inf.extract.ride"] = "All targets destroyed! Vehicles are waiting nearby: get back to extraction."
    t["custommodes.inf.extracting"] = "Extracting... hold the point."
    return t
