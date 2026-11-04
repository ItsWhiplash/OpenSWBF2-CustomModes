--
-- Search & Destroy tests (harness.lua sets up the mission).
--

-- five posts in a line: team 1 (the stock ATT) owns cp1, team 2 owns cp5
local LINE = {
	{ "cp1", 0, 0, 1 }, { "cp2", 0, 40, 0 }, { "cp3", 5, 80, 0 }, { "cp4", -5, 90, 2 }, { "cp5", 0, 120, 2 },
}

local function StartSnD(cfg, posts) return StartMission(cfg or {}, "SnDMap", posts or LINE) end
local function Team(name) return Mock.entities[name].team end

-- a human and two bots on team 1, three bots on team 2; nobody spawned yet
local function Populate()
	local human = Mock.AddCharacter(1, true)
	local list = { human }
	local i
	for i = 1, 2 do table.insert(list, Mock.AddCharacter(1, false)) end
	for i = 1, 3 do table.insert(list, Mock.AddCharacter(2, false)) end
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
local function KillTeam(t)
	local list, i = Alive(t)
	for i = 1, table.getn(list) do Mock.KillChar(list[i], nil) end
end
local function Hold(c, post)
	return function() local e = Mock.entities[post] Mock.MoveTo(c, e.x + 1, 0, e.z) end
end
-- everyone away from the sites
local function Scatter()
	local t, i
	for t = 1, 2 do
		for i = 1, table.getn(Mock.teams[t]) do Mock.MoveTo(Mock.teams[t][i], 500 * t, 0, -500) end
	end
end
-- through setup into a live round
local function GoLive(s) Run(s.setupTime + 0.5) Scatter() end

test("s&d: layout and setup", function()
	local s = StartSnD()
	check(s.attackerSpawn == "cp1" and s.defenderSpawn == "cp5", "spawns at the two ends, the attackers' own")
	check(table.concat(s.sites, ",") == "cp4,cp3", "the two posts nearest the defenders are the sites")
	check(Team("cp1") == 1 and Team("cp5") == 2 and Team("cp3") == 0 and Team("cp2") == 0, "setup: each side owns its spawn")
	check(Mock.entities["cp4"].capturable == false, "nothing can be captured")
	local small = StartSnD(nil, { { "cp1", 0, 0, 1 }, { "cp2", 0, 50, 0 }, { "cp3", 0, 100, 2 } })
	check(table.getn(small.sites) == 1 and small.sites[1] == "cp2", "three posts: one site")
end)

test("s&d: one life", function()
	local s = StartSnD()
	local human = Populate()
	Run(1)
	check(table.getn(Alive(1)) == 3 and table.getn(Alive(2)) == 3, "everyone spawns in setup")
	Mock.KillChar(human, nil)
	Run(1)
	check(Mock.Char(human).unit.alive, "deaths in setup respawn")
	GoLive(s)
	check(s.state == "live" and Team("cp1") == 0 and Team("cp5") == 0, "live: the spawns go neutral")
	Mock.KillChar(human, nil)
	Run(5)
	check(not Mock.Char(human).unit.alive, "a death in a live round is final")
end)

test("s&d: plant and detonate", function()
	local s = StartSnD()
	local human = Populate()
	GoLive(s)
	Run(3, Hold(human, "cp4"))
	Scatter()
	Run(0.5)
	Run(3, Hold(human, "cp4"))
	check(not s.planted, "stepping off resets the plant")
	Run(3, Hold(human, "cp4"))
	check(s.planted == "cp4", "planted after 5 s on the site")
	Scatter()
	KillTeam(1)
	Run(1)
	check(s.state == "live", "the attackers dying after a plant doesn't end the round")
	Run(40)
	check(s.wins[1] == 1 and Mock.points[1] == 1, "the bomb went off: the attackers' round")
	check(Mock.entities["cp4"].alive == false, "and the site is destroyed")
	Run(7)
	check(s.round == 2 and s.state == "setup", "the next round starts")
	check(Mock.entities["cp4"].alive, "with the site back")
	check(table.getn(Alive(1)) == 3 and table.getn(Alive(2)) == 3, "and everyone fresh")
end)

test("s&d: defuse", function()
	local s = StartSnD()
	local human = Populate()
	GoLive(s)
	Run(6, Hold(human, "cp3"))
	check(s.planted == "cp3", "planted at the other site")
	Scatter()
	local d = Alive(2)[1]
	Run(4, Hold(d, "cp3"))
	Scatter()
	Run(0.5)
	check(s.state == "live", "stepping off a defuse resets it")
	Run(8, Hold(d, "cp3"))
	check(s.wins[2] == 1, "defused: the defenders' round")
end)

test("s&d: elimination and time", function()
	local s = StartSnD({ roundTime = 30 })
	local human = Populate()
	GoLive(s)
	KillTeam(2)
	Run(1)
	check(s.wins[1] == 1, "defenders eliminated: attackers' round")
	Run(7)
	GoLive(s)
	KillTeam(1)
	Run(1)
	check(s.wins[2] == 1, "attackers eliminated before a plant: defenders' round")
	Run(7)
	GoLive(s)
	Run(31)
	check(s.wins[2] == 2, "time runs out with no plant: defenders' round")
end)

test("s&d: halftime and the match", function()
	local s = StartSnD()
	local human = Populate()
	local r
	for r = 1, 3 do
		GoLive(s)
		KillTeam(2)
		Run(7)
	end
	check(s.wins[1] == 3, "team 1 won the first half")
	check(s.att == 2 and s.def == 1, "halftime: team 2 attacks")
	check(Team("cp1") == 2 and Team("cp5") == 1, "and takes the attackers' spawn")
	GoLive(s)
	KillTeam(1)
	Run(7)
	check(s.wins[2] == 1, "round 4 to team 2")
	GoLive(s)
	KillTeam(2)
	Run(2)
	check(Mock.victory == 1 and s.wins[1] == 4, "first to 4 wins the match")
end)

test("s&d: waits for a side to spawn", function()
	local s = StartSnD()
	Mock.AddCharacter(1, true)
	Run(30)
	check(s.state == "setup", "no round goes live with a side empty")
end)

test("s&d: clients", function()
	local savedReset = Mock.Reset
	Mock.Reset = function() savedReset() Mock.net = true Mock.host = false end
	local s = StartSnD()
	Mock.Reset = savedReset
	check(Mock.Count("SetObjectTeam") == 0 and Mock.timers["sndPoll"] == nil, "the server runs the rounds")
end)
