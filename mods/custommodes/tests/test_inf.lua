--
-- Infiltration tests (harness.lua sets up the mission).
--

-- six posts along z: the squad's side owns cp1, the garrison the rest
local LINE = {
	{ "cp1", 0, 0, 1 }, { "cp2", 0, 40, 2 }, { "cp3", 10, 80, 2 },
	{ "cp4", -10, 120, 2 }, { "cp5", 0, 160, 2 }, { "cp6", 5, 200, 0 },
}

local function StartInf(cfg, posts) return StartMission(cfg or {}, "InfiltrationMap", posts or LINE) end
local function Team(name) return Mock.entities[name].team end

-- a human, five bots for the squad, thirty for the garrison; nobody spawned yet
local function Populate()
	local human = Mock.AddCharacter(1, true)
	local i, list = 0, { human }
	for i = 1, 5 do table.insert(list, Mock.AddCharacter(1, false)) end
	for i = 1, 30 do table.insert(list, Mock.AddCharacter(2, false)) end
	for i = 1, table.getn(list) do Mock.Char(list[i]).unit.alive = false end
	return human
end

local function Run(seconds, each)
	Mock.Advance(seconds, 0.05, function()
		Mock.SpawnTick()
		if each then each() end
	end)
end

local function Alive(t)
	local list, i = {}
	for i = 1, table.getn(Mock.teams[t]) do
		if Mock.Char(Mock.teams[t][i]).unit.alive then table.insert(list, Mock.teams[t][i]) end
	end
	return list
end
local function Blow(i) Mock.entities["infil_target_" .. i].alive = false end
local function Insert(inf) Run(inf.spawnWindow + 0.5) end

test("infiltration: layout and targets", function()
	local inf = StartInf()
	check(inf.insertion == "cp1" and inf.extraction == "cp1", "insert and extract at the squad's post")
	check(table.getn(inf.targetNames) == 5, "five targets")
	check(Mock.Count("CreateEntity", "all_hover_combatspeeder") == 5, "the garrison's own side's tanks (all_ for an all_ hero)")
	local t1 = Mock.entities["infil_target_1"]
	check(near(t1.z, 210, 0.5) and near(t1.x, 5.25, 0.5), "parked 10 m beyond the farthest post")
	check(Team("cp6") == 2 and Team("cp1") == 1 and Team("infil_target_1") == 2, "the garrison holds every other post")
	check(Mock.entities["cp3"].capturable == false, "nothing can be captured")
	local a = Mock.AddCharacter(1, true)
	Mock.EnterVehicle(a, "infil_target_2")
	check(Mock.Count("ExitVehicle", a) == 1, "nobody drives a target away")
	local placed = StartInf({ targets = { { 1, 2, 3 }, { post = "cp2" } } })
	check(table.getn(placed.targetNames) == 2 and near(Mock.entities["infil_target_1"].z, 3), "targets by position or post")
	local cw = StartInf({ targetClass = "cis_hover_aat" })
	check(Mock.Count("CreateEntity", "cis_hover_aat") == 5, "targetClass picks the vehicle")
end)

test("infiltration: insertion and one life", function()
	local inf = StartInf()
	local human = Populate()
	Run(2)
	check(table.getn(Alive(1)) == 4, "the human and 3 bot squadmates (" .. table.getn(Alive(1)) .. ")")
	check(table.getn(Alive(2)) == 6, "a quiet garrison of 6 (" .. table.getn(Alive(2)) .. ")")
	check(Mock.aggression[2] == 0.3 and Mock.vision == 0.5, "passive and half-blind")
	Insert(inf)
	check(inf.state == "mission" and Team("cp1") == 0, "after the window the insertion post closes")
	Mock.KillChar(human, nil)
	Run(5)
	check(not Mock.Char(human).unit.alive, "death is final")
end)

test("infiltration: alarms escalate", function()
	local inf = StartInf()
	local human = Populate()
	Insert(inf)
	Blow(1)
	Run(1)
	check(inf.level == 1 and inf.alarmed, "a target blowing trips the alarm")
	check(Mock.Count("ShowMessageText", "custommodes.inf.alarm") == 1 and
		Mock.Count("ShowMessageText", "custommodes.inf.left.4") == 1, "the alarm and targets left announced")
	check(table.getn(Alive(2)) == 14 and Mock.aggression[2] == 1 and Mock.vision == 1, "14 guards, aggressive, sharp-eyed")
	check(Mock.points[1] == 1 and Mock.points[2] == 1, "score: targets down, alarm level")
	Run(61)
	check(not inf.alarmed and Mock.reinforcements[2] == 9 and Mock.aggression[2] == 0.3, "it stands down after 60 s, to 9 guards")
	Blow(2)
	Run(1)
	check(inf.level == 2 and Mock.reinforcements[2] == 18, "the second alarm: 18 guards")
	Run(70)
	check(inf.alarmed, "and lasts longer (75 s)")
	Run(6)
	check(not inf.alarmed and Mock.reinforcements[2] == 12, "then 12 when quiet")
end)

test("infiltration: noise", function()
	local inf = StartInf()
	local human = Populate()
	Insert(inf)
	local guards, i = Alive(2)
	for i = 1, 3 do Mock.KillChar(guards[i], human) end
	Run(1)
	check(not inf.alarmed, "three quick kills: still quiet")
	Run(25)
	Mock.KillChar(Alive(2)[1], human)
	Run(1)
	check(not inf.alarmed, "kills spread out don't count together")
	local g = Alive(2)
	for i = 1, 3 do Mock.KillChar(g[i], human) end
	Run(1)
	check(inf.alarmed and inf.level == 1, "four within 20 s: alarm")
end)

test("infiltration: extraction", function()
	local inf = StartInf()
	local human = Populate()
	Insert(inf)
	Mock.MoveTo(human, 500, 0, 500)
	local i
	for i = 1, 4 do Blow(i) end
	Run(1)
	check(not inf.extractOpen, "extraction stays shut with a target left")
	Blow(5)
	Run(1)
	check(inf.extractOpen and inf.level == 5, "all down: extraction opens (and every blast was an alarm)")
	local function Stay() Mock.MoveTo(human, 1, 0, 0) end
	local squad, j = Alive(1)
	for j = 1, table.getn(squad) do if squad[j] ~= human then Mock.KillChar(squad[j], nil) end end
	Run(3, Stay)
	check(Mock.victory == nil, "not out yet")
	Run(3, Stay)
	check(Mock.victory == 1, "a survivor at extraction for 5 s: mission complete")
end)

test("infiltration: rides and extraction height", function()
	local inf = StartInf({ rideClass = "imp_fly_tiefighter", rides = { { 0, 0, -5 }, { 6, 0, -5 } },
		escapeRides = { { 0, 0, 100 }, { 0, 0, 300 } }, extraction = "cp6", extractHeight = 10 })
	check(Mock.Count("CreateEntity", "imp_fly_tiefighter") == 2 and Team("infil_ride_1") == 1,
		"rides are made for the squad at the start")
	local plan = inf:EscapePlan({ { 0, 0, 90 }, { 2, 0, 110 }, { 0, 0, 280 } })
	check(table.getn(plan) == 3 and plan[1][3] == 100 and plan[2][1] == 12 and plan[3][3] == 300,
		"escape rides: one per survivor at the nearest spot, set out apart")
	local human = Populate()
	Insert(inf)
	local squad, j = Alive(1)
	for j = 1, table.getn(squad) do if squad[j] ~= human then Mock.KillChar(squad[j], nil) end end
	Mock.MoveTo(human, 0, 0, 290)
	for j = 1, 5 do Blow(j) end
	Run(1)
	local ride = Mock.entities["infil_ride_3"]
	check(ride and ride.z == 300 and Mock.entities["infil_ride_4"] == nil and Team("infil_ride_3") == 1,
		"when the targets are down, a ride appears by the survivor")
	local cp6 = Mock.entities["cp6"]
	local function Under() Mock.MoveTo(human, cp6.x, cp6.y + 50, cp6.z) end
	Run(7, Under)
	check(Mock.victory == nil, "under or over the extraction point doesn't count, with extractHeight")
	Mock.EnterVehicle(human, "infil_ride_3")
	ride.x, ride.y, ride.z = cp6.x, cp6.y + 4, cp6.z
	Run(8)
	check(Mock.victory == 1, "landing the ride at extraction counts (its position, not the pilot's)")
end)

test("infiltration: squad wipe", function()
	local inf = StartInf()
	local human = Populate()
	Insert(inf)
	local squad, i = Alive(1)
	for i = 1, table.getn(squad) do Mock.KillChar(squad[i], nil) end
	Run(3)
	check(Mock.victory == 2, "the whole squad down: mission failed")
end)

test("infiltration: waits for the squad", function()
	local inf = StartInf()
	Run(40)
	check(inf.state == "insert", "the window stays open until someone's in")
end)

test("infiltration: clients", function()
	local savedReset = Mock.Reset
	Mock.Reset = function() savedReset() Mock.net = true Mock.host = false end
	local inf = StartInf()
	Mock.Reset = savedReset
	check(Mock.Count("CreateEntity") == 0 and Mock.timers["infilPoll"] == nil, "the server runs the mission")
end)
