--
-- Horde tests (harness.lua sets up the mission).
--

-- six posts: the players own cp1 and cp2, the horde cp5 and cp6, cp3 and cp4 are neutral
local SIX = {
	{ "cp1", 0, 0, 1 }, { "cp2", 10, 20, 1 }, { "cp3", -20, 40, 0 },
	{ "cp4", 20, 60, 0 }, { "cp5", 0, 100, 2 }, { "cp6", 15, 110, 2 },
}

local function StartHorde(cfg, posts) return StartMission(cfg or {}, "HordeMap", posts or SIX) end
local function Team(name) return Mock.entities[name].team end

-- a human, some bot allies, and a pool of horde bots (plus their hero), none spawned yet
local function Populate(allies, horde)
	local human = Mock.AddCharacter(1, true)
	Mock.Char(human).unit.alive = false
	local i
	for i = 1, allies or 0 do
		local c = Mock.AddCharacter(1, false)
		Mock.Char(c).unit.alive = false
	end
	for i = 1, horde or 30 do
		local c = Mock.AddCharacter(2, false)
		Mock.Char(c).unit.alive = false
		Mock.Char(c).class = "all_inf_rifleman"
	end
	local boss = Mock.AddCharacter(2, false)
	Mock.Char(boss).unit.alive = false
	Mock.Char(boss).class = "all_hero_hansolo"
	Mock.Char(boss).hero = true
	return human, boss
end

-- runs the game: the engine's spawn rules every frame
local function Run(seconds, each)
	Mock.Advance(seconds, 0.05, function()
		Mock.SpawnTick()
		if each then each() end
	end)
end

local function AliveOf(t)
	local list, i = {}
	for i = 1, table.getn(Mock.teams[t]) do
		local c = Mock.teams[t][i]
		if Mock.Char(c).unit.alive then table.insert(list, c) end
	end
	return list
end

-- the player kills every enemy alive
local function KillHorde(by)
	local list = AliveOf(2)
	local i
	for i = 1, table.getn(list) do Mock.KillChar(list[i], by) end
	return table.getn(list)
end

local function ClearWave(human)
	local guard = 0
	while GetReinforcementCount(2) > 0 and guard < 50 do
		Run(0.3)
		KillHorde(human)
		guard = guard + 1
	end
	Run(0.5)
end

test("horde: layout", function()
	local h = StartHorde()
	check(h.lastStand == "cp1", "last stand: the players' post farthest from the horde (" .. h.lastStand .. ")")
	check(table.concat(h.hordeSpawns, ",") == "cp6,cp5", "horde spawns: the two farthest")
	check(table.concat(h.shopPads, ",") == "cp4,cp3,cp2", "the rest are shop pads")
	check(Team("cp6") == 2 and Team("cp1") == 1 and Team("cp2") == 0 and Team("cp3") == 0, "pads neutral, posts set")
	check(Mock.entities["cp1"].capturable == false and Mock.entities["cp3"].capturable == false, "nothing can be captured")
	check(Mock.Find("ForceHumansOntoTeam1") ~= nil, "humans all on team 1")
	check(h.bossClass == "all_hero_hansolo", "the boss is the horde's hero class")
	local small = StartHorde(nil, { { "cp1", 0, 0, 1 }, { "cp2", 0, 50, 2 }, { "cp3", 0, 80, 2 } })
	check(table.getn(small.hordeSpawns) == 1 and small.shopPads[1] == "cp2", "three posts: one horde spawn, one pad")
end)

test("horde: wave rules", function()
	local h = StartHorde()
	check(h:WaveSize(1) == 10 and h:WaveSize(5) == 26, "10 enemies, 4 more each wave")
	check(near(h:HealthMult(1), 1) and near(h:HealthMult(11), 2) and h:HealthMult(100) == 4, "health +10% a wave, capped at 4x")
	check(h:IsBossWave(5) and h:IsBossWave(10) and not h:IsBossWave(4), "a boss every 5th wave")
	local i, ok = 0, true
	for i = 0, 6 do
		if HordeDecodeBonus(GetBleedRate(1) * 0 + HordeEncodeBonus(i)) ~= i then ok = false end
		-- through the network's 5 bits
		SetBleedRate(1, HordeEncodeBonus(i))
		if HordeDecodeBonus(GetBleedRate(1)) ~= i then ok = false end
	end
	check(ok, "a bonus survives the trip through the bleed rate")
end)

test("horde: a wave", function()
	local h = StartHorde()
	local human = Populate(2, 30)
	Run(1)
	check(h.state == "break" and Mock.Char(human).unit.alive, "a break first, and the player spawns")
	check(table.getn(AliveOf(2)) == 0, "no enemies in the break")
	Run(30)
	check(h.state == "wave" and h.wave == 1, "wave 1 starts after the first break")
	check(Team("cp1") == 0, "the last stand is neutral during a wave")
	Run(1)
	check(table.getn(AliveOf(2)) == 10, "ten enemies (" .. table.getn(AliveOf(2)) .. ")")
	check(Mock.reinforcements[2] == 10 and Mock.points[2] == 1, "the counter shows them, the score the wave")
	-- an ally dies and stays down
	local ally = Mock.teams[1][2]
	Mock.KillChar(ally, nil)
	Run(2)
	check(not Mock.Char(ally).unit.alive, "the dead stay down during a wave")
	KillHorde(human)
	check(Mock.points[1] == 50, "5 credits a kill (" .. tostring(Mock.points[1]) .. ")")
	Run(0.5)
	check(h.state == "break" and h.wave == 1, "wave cleared: a break")
	check(Team("cp1") == 1, "the last stand is the players' again")
	Run(1)
	check(Mock.Char(ally).unit.alive, "and the dead come back")
	Run(21)
	check(h.wave == 2 and Mock.reinforcements[2] == 14, "wave 2 has 14")
	check(Mock.Count("ShowMessageText", "custommodes.horde.wave.1") == 1 and
		Mock.Count("ShowMessageText", "custommodes.horde.cleared.1") == 1 and
		Mock.Count("ShowMessageText", "custommodes.horde.wave.2") == 1, "waves are announced")
end)

test("horde: tougher enemies and the boss", function()
	local h = StartHorde({ firstBreak = 1, breakTime = 1 })
	local human, boss = Populate(0, 40)
	Run(2)
	local i
	for i = 1, 3 do ClearWave(human) Run(1.5) end
	check(h.wave == 4, "on wave 4 (" .. h.wave .. ")")
	Run(0.5)
	local e = AliveOf(2)[1]
	check(e and near(Mock.Char(e).unit.props["MaxHealth"], 300 * 1.3), "wave 4 enemies have 130% health")
	ClearWave(human)
	Run(1.5)
	check(h.wave == 5 and Mock.Count("UnlockHeroForTeam", 2) == 1, "wave 5 unlocks the enemy hero")
	Run(0.5)
	check(Mock.Char(boss).unit.alive and near(Mock.Char(boss).unit.props["MaxHealth"], 300 * 1.4 * 3), "the boss has 3x health on top")
	local before = h.credits
	Mock.KillChar(boss, human)
	check(h.credits == before + 100, "the boss is worth 100 credits")
end)

test("horde: the shop", function()
	local h = StartHorde({ startCredits = 400, firstBreak = 60 })
	local human = Populate(0, 30)
	Run(1)
	local pad, item, p, o
	for p, o in pairs(h.offers) do
		if o.kind == "bonus" and o.price <= 400 then pad, item = p, o end
	end
	check(pad and item, "a pad is offering an enhancement")
	-- the offers differ between pads
	local seen, distinct, k, v = {}, true
	for k, v in pairs(h.offers) do
		if seen[v.id] then distinct = false end
		seen[v.id] = true
	end
	check(distinct, "every pad offers something different")
	local function StandOn(name)
		local e = Mock.entities[name]
		Mock.MoveTo(human, e.x + 1, 0, e.z)
	end
	StandOn(pad)
	Run(1)
	check(Mock.Count("ShowMessageText", "custommodes.horde.item." .. item.id) == 1, "stepping on a pad shows what it sells")
	check(h.credits == 400, "not bought yet")
	Run(1.5)
	check(h.credits == 400 - item.price, "bought after standing on it")
	check(Mock.Count("ShowMessageText", "custommodes.horde.bought." .. item.id) == 1, "and says so")
	check(Mock.bonus[1] == "team_bonus_" .. item.bonus, "the enhancement is on")
	check(HordeDecodeBonus(GetBleedRate(1)) == HordeBonusIndex(item.bonus), "and sent to everyone")
	Run(3)
	check(h.credits == 400 - item.price, "a pad sells once a break")
	local offers = h:PickOffers(2)
	local p, o, again = nil, nil, false
	for p, o in pairs(offers) do if o.kind == "bonus" and o.bonus == item.bonus then again = true end end
	check(not again, "the active enhancement isn't offered again")
end)

test("horde: shop items", function()
	local h = StartHorde({ startCredits = 800 })
	local human = Populate(0, 30)
	Run(1)
	h:Buy("cp2", { id = "tank", kind = "vehicle", class = "imp_hover_fightertank", price = 200 })
	check(Mock.Count("CreateEntity", "imp_hover_fightertank") == 1, "a vehicle appears by the last stand")
	h:Buy("cp3", { id = "hero", kind = "hero", price = 250 })
	check(Mock.Count("UnlockHeroForTeam", 1) == 1, "the hero is unlocked for the players")
	h:ApplyBonus("bacta_tanks")
	h:ApplyBonus("energy_boost")
	check(Mock.bonus[1] == "team_bonus_energy_boost", "one enhancement at a time: the new one replaces the old")
	check(h.credits == 350, "credits spent")
	h:SetCredits(5000)
	check(Mock.points[1] == 895, "credits stop at what the score can show")
end)

test("horde: overrun", function()
	local h = StartHorde({ firstBreak = 1 })
	local human = Populate(0, 30)
	Run(2)
	-- the player wanders off; an enemy stands on the last stand
	Mock.MoveTo(human, 500, 0, 500)
	local stand = Mock.entities["cp1"]
	local function Hold() local e = AliveOf(2)[1] if e then Mock.MoveTo(e, stand.x, 0, stand.z) end end
	Run(5, Hold)
	check(Mock.victory == nil, "not yet")
	Mock.MoveTo(human, stand.x + 2, 0, stand.z)
	Run(8, Hold)
	check(Mock.victory == nil, "a defender on it holds it")
	Mock.MoveTo(human, 500, 0, 500)
	Run(12, Hold)
	check(Mock.victory == 2, "held by the horde for 10 s: lost")
end)

test("horde: everyone down", function()
	local h = StartHorde({ firstBreak = 1 })
	local human = Populate(1, 30)
	Run(2)
	Mock.KillChar(human, nil)
	Mock.KillChar(Mock.teams[1][2], nil)
	Run(1)
	check(Mock.victory == nil, "a moment's grace")
	Run(3)
	check(Mock.victory == 2, "nobody left: lost")
end)

test("horde: waits for a player to spawn", function()
	local h = StartHorde({ firstBreak = 1 })
	-- nobody on the players' team at all
	Run(3)
	check(h.state == "break" and h.wave == 0, "no wave starts with nobody alive")
end)

test("horde: clients", function()
	local savedReset = Mock.Reset
	Mock.Reset = function() savedReset() Mock.net = true Mock.host = false end
	local h = StartHorde()
	Mock.Reset = savedReset
	check(Mock.Count("SetObjectTeam") == 0 and Mock.Count("AddAIGoal") == 0, "the server runs the match")
	SetBleedRate(1, HordeEncodeBonus(HordeBonusIndex("advanced_blasters")))
	Mock.Advance(0.5)
	check(Mock.bonus[1] == "team_bonus_advanced_blasters", "the client turns on the server's enhancement")
	SetBleedRate(1, HordeEncodeBonus(HordeBonusIndex("bacta_tanks")))
	Mock.Advance(0.5)
	check(Mock.bonus[1] == "team_bonus_bacta_tanks", "and follows when it changes")
end)
