--
-- Rush tests (harness.lua sets up the mission).
--

-- nine posts along z: the attackers own cp1 at the back (and cp7 in the middle), the rest are
-- the defenders' or neutral, and the names are out of order on purpose
local NINE = {
	{ "cp1", 0, -20, 1 },
	{ "cp3", 0, 10, 2 }, { "cp9", 5, 12, 2 }, { "cp4", -5, 20, 2 },
	{ "cp5", 0, 40, 0 }, { "cp6", 5, 45, 2 }, { "cp7", -5, 50, 1 },
	{ "cp8", 0, 70, 2 }, { "cp2", 5, 75, 2 },
}

local function StartRush(cfg, posts) return StartMission(cfg or {}, "RushMap", posts or NINE) end
local function Team(name) return Mock.entities[name].team end
local function Open(name) return Mock.entities[name].capturable end
local function Poll() Mock.Advance(0.5) end

-- the attackers take a post: neutralize it, then capture it, as the game does
local function Take(name)
	local ok = Mock.Capture(name, 0) and Mock.Capture(name, 1)
	Poll()
	return ok
end

test("rush: automatic stages", function()
	local r = StartRush()
	check(table.concat(r.stages[1], ",") == "cp3,cp9,cp4", "stage 1 nearest the attackers (" .. table.concat(r.stages[1], ",") .. ")")
	check(table.concat(r.stages[2], ",") == "cp5,cp6,cp7", "stage 2")
	check(table.concat(r.stages[3], ",") == "cp8,cp2", "stage 3 has two")
	check(r.base[1] == "cp1" and table.getn(r.base) == 1, "the attackers start at cp1")
	check(Team("cp7") == 2 and Team("cp5") == 2, "every stage post starts as the defenders'")
	check(Team("cp1") == 1, "the base stays the attackers'")
	check(Open("cp3") and Open("cp9") and Open("cp4"), "stage 1 is open")
	check(not Open("cp5") and not Open("cp8") and not Open("cp1"), "later stages and the base are locked")
	check(Mock.Count("SetProperty", "cp3") == 0, "stage 1 keeps the map's own capture regions")
	check(Mock.reinforcements[1] == 100 and Mock.Unlimited(2), "100 attacker lives, defenders unlimited")
end)

test("rush: stage sizes fit the map", function()
	local r = StartRush()
	local function Fit(n) return table.concat(r:FitStageSizes(n), ",") end
	check(Fit(8) == "3,3,2" and Fit(12) == "3,3,2", "3, 3, 2 when there are enough")
	check(Fit(7) == "3,2,2" and Fit(6) == "2,2,2" and Fit(5) == "2,2,1", "shrinks from the back")
	check(Fit(3) == "1,1,1" and Fit(2) == "1,1" and Fit(1) == "1", "drops empty stages")
	local small = StartRush(nil, { { "cp1", 0, 0, 1 }, { "cp2", 0, 10, 2 }, { "cp3", 0, 20, 2 }, { "cp4", 0, 30, 2 },
		{ "cp5", 0, 40, 2 }, { "cp6", 0, 50, 2 } })
	check(table.getn(small.stages) == 3 and table.concat(small.stages[3], ",") == "cp6", "a six-post map: 2, 2, 1")
	local big = StartRush({ stageSizes = { 1, 1 } })
	check(table.concat(big.rear, ",") == "cp4,cp5,cp6,cp7,cp8,cp2", "spare posts are the defenders' locked rear")
	check(not Open("cp2") and Team("cp2") == 2, "the rear is locked and the defenders'")
end)

test("rush: capturing", function()
	local r = StartRush()
	check(Take("cp3"), "stage 1 post taken")
	check(Mock.reinforcements[1] == 120, "a post earns 20 lives (" .. Mock.reinforcements[1] .. ")")
	check(Mock.Count("ShowMessageText", "custommodes.rush.taken.att") == 1, "and says so")
	check(not Open("cp3") and not Mock.Capture("cp3", 2), "the defenders can't take it back")
	check(Mock.points[1] == 1 and Mock.points[2] == 7, "score: posts taken, posts left")
	check(not Take("cp5"), "stage 2 is still locked")
	Take("cp9")
	Poll()
	check(Mock.reinforcements[1] == 140, "lives are given once per post")
	check(not Open("cp5"), "stage 2 opens only when stage 1 has fallen")
	Take("cp4")
	check(r.current == 2, "stage 2 now")
	check(Open("cp5") and Open("cp6") and Open("cp7"), "stage 2 opened")
	check(Mock.entities["cp5"].props["Radius"] == 10, "opened posts get a 10 m capture region")
	check(not Open("cp8"), "stage 3 still locked")
	Take("cp5") Take("cp6") Take("cp7")
	check(r.current == 3 and Open("cp8") and Open("cp2"), "stage 3 opened")
	check(Mock.Count("ShowMessageText", "custommodes.rush.stage.1.att") == 1 and
		Mock.Count("ShowMessageText", "custommodes.rush.final.def") == 1, "stages and the final stage announced")
	Take("cp8")
	check(Mock.victory == nil, "not over with a post left")
	Take("cp2")
	Mock.Advance(1.5)
	check(Mock.victory == 1, "the attackers win with every stage taken")
	check(Mock.reinforcements[1] == 260, "8 posts x 20 lives on top of 100")
end)

test("rush: lives run out", function()
	local r = StartRush({ attackerTickets = 3 })
	local a = Mock.AddCharacter(1, true)
	local d = Mock.AddCharacter(2, false)
	Mock.Kill(d) Mock.Kill(d)
	check(Mock.Unlimited(2) and Mock.defeat == nil, "defenders never run out")
	Mock.Kill(a) Mock.Kill(a)
	check(Mock.defeat == nil and Mock.reinforcements[1] == 1, "a life per attacker death")
	Take("cp3")
	check(Mock.reinforcements[1] == 21, "a capture tops them up")
	local i
	for i = 1, 21 do Mock.Kill(a) end
	check(Mock.defeat == 1, "out of lives: the attackers lose")
end)

test("rush: bots and markers", function()
	local r = StartRush()
	local function Goals(kind, target)
		local n, i = 0
		for i = 1, table.getn(Mock.calls) do
			local c = Mock.calls[i]
			if c.name == "AddAIGoal" and c.a2 == kind and (target == nil or c.a4 == target) then n = n + 1 end
		end
		return n
	end
	check(Goals("Defend", "cp3") == 2 and Goals("Defend", "cp9") == 2 and Goals("Defend", "cp5") == 0,
		"both teams' bots go for the open posts")
	check(Goals("Deathmatch") == 2, "and some fight")
	check(Mock.Count("MapAddEntityMarker", "cp3") == 2 and Mock.Count("MapAddEntityMarker", "cp5") == 0, "open posts are marked")
	Take("cp3")
	check(Mock.Count("MapRemoveEntityMarker", "cp3") == 1 and Goals("Defend", "cp9") == 4, "goals move on after a capture")
	local i, banned = 0
	for i = 1, table.getn(Mock.calls) do
		local c = Mock.calls[i]
		if c.name == "AICanCaptureCP" and c.a1 == "cp5" and c.a3 == false then banned = true end
	end
	check(banned, "bots can't capture locked posts")
end)

test("rush: stages from the settings", function()
	local r = StartRush({ stages = { { "cp2", "cp3" }, { "cp4" } }, attackerBase = { "cp9" } })
	check(table.getn(r.stages) == 2 and r.base[1] == "cp9", "used as given")
	check(Team("cp9") == 1 and Team("cp2") == 2 and Open("cp2") and not Open("cp4") and not Open("cp9"), "set up from them")
end)

test("rush: time limit", function()
	local r = StartRush({ timeLimit = 30 })
	Mock.Advance(32)
	check(Mock.victory == 2, "defenders win on time when there's a limit")
end)

test("rush: clients", function()
	local savedReset = Mock.Reset
	Mock.Reset = function() savedReset() Mock.net = true Mock.host = false end
	local r = StartRush()
	Mock.Reset = savedReset
	check(Mock.Count("SetObjectTeam") == 0 and Mock.Count("AddAIGoal") == 0, "the server sets teams and bots")
	check(not Open("cp5") and Open("cp3"), "but the client locks posts the same way")
	-- the server's capture reaches the client as a team change
	Mock.entities["cp3"].team, Mock.entities["cp9"].team, Mock.entities["cp4"].team = 1, 1, 1
	Poll()
	check(Open("cp5") and not Open("cp3"), "and follows the stages from who owns the posts")
	check(Mock.Count("AddReinforcements") == 0 and Mock.victory == nil, "without giving lives or ending the match")
end)

test("rush: lockCaptured off", function()
	local r = StartRush({ lockCaptured = false })
	Take("cp3")
	check(Open("cp3") and Mock.Capture("cp3", 2), "the defenders can win a post back in the open stage")
	Poll()
	check(Mock.reinforcements[1] == 120, "and retaking it earns nothing more")
	Take("cp3") Take("cp9") Take("cp4")
	check(r.current == 2 and not Open("cp3") and not Open("cp4"), "but a fallen stage stays locked")
end)
