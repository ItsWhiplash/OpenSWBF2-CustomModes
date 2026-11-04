--
-- Headless tests for the payload mode, run with the game's own Lua 5.0 (see run_tests.sh).
-- They run the real objective.lua and objectiveconquest.lua from data/scripts/mission.
--

local failures, passed = 0, 0
local current = "?"

local function check(cond, what)
	if cond then
		passed = passed + 1
	else
		failures = failures + 1
		Mock.verbose = false
		print2("FAIL [" .. current .. "] " .. what)
	end
end

local function near(a, b, tol) return a and b and math.abs(a - b) <= (tol or 0.05) end

print2 = function(s) Mock.rawprint(s) end

local MISSION = "data/scripts/mission/"
local MOD = "mods/payload/scripts/"

-- what the engine does to start a mission: run the script's top level (before the mission API
-- exists), register the API, then ScriptPreInit, ScriptInit and ScriptPostLoad
local function StartMission(cfg)
	Mock.Reset()
	Mock.ran = {}
	Mock.files["objective"] = MISSION .. "objective.lua"
	Mock.files["objectiveconquest"] = MISSION .. "objectiveconquest.lua"
	Mock.files["objectivepayload"] = MOD .. "objectivepayload.lua"
	Mock.files["payload_mission"] = MOD .. "payload_mission.lua"
	__OBJECTIVE_LUA__ = nil
	ScriptPreInit, ScriptInit, ScriptPostLoad = nil, nil, nil
	ATT, DEF, RetailReadDataFile, gPayload = nil, nil, nil, nil
	ReadDataFile, SetMemoryPoolSize = nil, nil

	ScriptCB_DoFile("payload_mission")
	PayloadMap("tat2g", cfg)

	ReadDataFile = Mock.ReadDataFile
	SetMemoryPoolSize = Mock.SetMemoryPoolSize
	Mock.AddEntity("cp1", 0, 0, -20, 1)
	Mock.AddEntity("cp2", 0, 0, 60, 2)
	Mock.AddEntity("cp3", 0, 0, 120, 2)
	ScriptPreInit()
	ScriptInit()
	ScriptPostLoad()
	return gPayload
end

local STRAIGHT = { { 0, 0, 0 }, { 0, 0, 50 }, { 0, 0, 100 } }

local function Cart() return Mock.entities["payload_cart"] end

-- keeps characters standing next to the cart
local function Escort(list)
	return function()
		local i
		for i = 1, table.getn(list) do
			Mock.MoveTo(list[i], Cart().x + 1, Cart().y, Cart().z)
		end
	end
end

local function test(name, fn)
	current = name
	fn()
end

------------------------------------------------------------------------------------------
test("loading", function()
	local p = StartMission({ track = STRAIGHT })
	check(Mock.stockInitRan and Mock.stockPostLoadRan, "the stock ScriptInit and ScriptPostLoad ran")
	check(Mock.reads[1] == ".\\mission.lvl", "the stock mission.lvl was read first, not this addon's")
	-- the vehicle's side loads just before the first side the map reads
	local i, imp, side
	for i = 1, table.getn(Mock.calls) do
		local c = Mock.calls[i]
		if c.name == "ReadDataFile" and c.a1 == "SIDE\\imp.lvl" and c.a2 == "imp_hover_fightertank" then imp = i end
		if c.name == "ReadDataFile" and c.a1 == "SIDE\\imp.lvl" and c.a2 == "imp_inf_rifleman" then side = i end
	end
	check(imp and side and imp < side, "the payload vehicle's class loads before the map's sides")
	check(Mock.Count("uf_ReadDataFile") >= 3, "the game's own ReadDataFile wrapper still sees the map's reads")
	check(Mock.pools["EntityHover"] == 3, "EntityHover pool grew by one (got " .. tostring(Mock.pools["EntityHover"]) .. ")")
	check(Mock.pools["Weapon"] == 200, "other pools untouched")
	check(Mock.Count("AddDeathRegion") == 1, "the map's own post-load setup still runs")
	check(ObjectiveConquest.Start ~= nil and Mock.timers["bleed1"] == nil, "conquest never started (no bleed)")
	check(gPayloadConquestCPs[1] == "CP1" and gPayloadConquestCPs[2] == "cp2", "conquest's command posts noted")
	check(Mock.Count("SetProperty", "cp1") >= 1 and Cart().props["MaxHealth"] == 100000, "capture off, cart tough")
	check(p.teamATT == 1 and p.teamDEF == 2, "teams from the stock script's ATT and DEF")
	check(Mock.Count("CreateEntity", "imp_hover_fightertank") == 1, "one cart created")
	check(near(Cart().x, 0) and near(Cart().z, 0), "cart at the start")
	check(Mock.Find("SetNumBots") and Mock.Find("SetNumBots").a1 == 12, "bot count from the game options")
	check(Mock.Count("AddAIGoal") == 4, "bots get payload and fight goals")
	check(Mock.reinforcements[1] == -1 and Mock.reinforcements[2] == -1, "unlimited reinforcements")
end)

test("speed", function()
	local p = StartMission({ track = STRAIGHT, timeLimit = 0 })
	Mock.Advance(10)
	check(near(p.s, 0), "nobody near: it stays put")
	local a1 = Mock.AddCharacter(1, true)
	Mock.Advance(10, 0.05, Escort({ a1 }))
	check(near(p.s, 15, 0.6), "one attacker: 1.5 m/s (got " .. p.s .. ")")
	local list = { a1 }
	local i
	for i = 1, 7 do table.insert(list, Mock.AddCharacter(1, false)) end -- bots count too
	local before = p.s
	Mock.Advance(4, 0.05, Escort(list))
	check(near(p.s - before, 14, 0.6), "eight attackers: capped at 3.5 m/s (got " .. (p.s - before) / 4 .. ")")
	check(near(Cart().z, p.s, 0.5), "the cart is where the track says")
	check(Mock.points[1] == math.floor(100 * p.s / p.length), "attackers' score is the percentage")
end)

test("speed table", function()
	local p = StartMission({ track = STRAIGHT })
	check(p:SpeedFor(1, 0) == 1.5 and p:SpeedFor(2, 0) == 2.0 and p:SpeedFor(5, 0) == 3.5 and p:SpeedFor(9, 0) == 3.5,
		"1.5, 2.0 ... 3.5 cap")
	check(p:SpeedFor(3, 1) == 0, "contested: stopped")
	check(p:SpeedFor(0, 0) == 0, "empty: stopped")
end)

test("contest and rollback", function()
	local p = StartMission({ track = STRAIGHT, timeLimit = 0, checkpoints = { { at = 0.2 } } })
	local a = Mock.AddCharacter(1, true)
	local d = Mock.AddCharacter(2, false)
	Mock.Advance(20, 0.05, Escort({ a }))          -- 30 m, past the checkpoint at 20 m
	local s = p.s
	Mock.Advance(5, 0.05, Escort({ a, d }))
	check(near(p.s, s, 0.01), "a defender on it stops it")
	Mock.MoveTo(a, 500, 0, 500)
	Mock.MoveTo(d, 500, 0, 500)
	Mock.Advance(29)
	check(near(p.s, s, 0.01), "no rollback before 30 s")
	Mock.Advance(60)
	check(near(p.s, 20, 0.01), "rolls back, but not past the checkpoint (got " .. p.s .. ")")
end)

test("checkpoints and delivery", function()
	local p = StartMission({ track = STRAIGHT, timeLimit = 100,
		checkpoints = { { at = 0.5, giveCPs = { "cp2" } } } })
	local a = Mock.AddCharacter(1, true)
	Mock.Advance(10, 0.05, Escort({ a }))
	local before = GetTimerValue(p.clock)
	Mock.Advance(25, 0.05, Escort({ a }))          -- past 50 m
	check(Mock.entities["cp2"].team == 1, "cp2 handed to the attackers")
	check(GetTimerValue(p.clock) > before, "checkpoint added time")
	check(Mock.points[2] == 0, "defenders' score: no checkpoints left")
	Mock.Advance(40, 0.05, Escort({ a }))
	check(Mock.victory == 1, "attackers win at the end (victory " .. tostring(Mock.victory) .. ")")
end)

test("time runs out", function()
	local p = StartMission({ track = STRAIGHT, timeLimit = 20 })
	Mock.Advance(25)
	check(Mock.victory == 2, "defenders win on time")
end)

test("overtime", function()
	local p = StartMission({ track = STRAIGHT, timeLimit = 10 })
	local a = Mock.AddCharacter(1, true)
	Mock.Advance(15, 0.05, Escort({ a }))
	check(Mock.victory == nil and p.overtime, "overtime while attackers are on it")
	Mock.MoveTo(a, 500, 0, 500)
	Mock.Advance(1)
	check(Mock.victory == nil, "a short grace in overtime")
	Mock.Advance(3)
	check(Mock.victory == 2, "defenders win once overtime ends")
end)

test("can't drive or destroy it", function()
	local p = StartMission({ track = STRAIGHT })
	local a = Mock.AddCharacter(1, true)
	Mock.EnterVehicle(a, "payload_cart")
	check(Mock.Count("ExitVehicle", a) == 1, "thrown out of the payload")
	Cart().props["CurHealth"] = 5
	Cart().alive = false
	Mock.Advance(0.5)
	check(Cart().alive and Cart().props["CurHealth"] == 100000, "respawned and healed")
	Mock.EnterVehicle(a, Mock.AddEntity("speeder", 0, 0, 0))
	check(Mock.Count("ExitVehicle", a) == 1, "other vehicles are fine")
end)

test("in-vehicle soldiers don't push", function()
	local p = StartMission({ track = STRAIGHT, timeLimit = 0 })
	local a = Mock.AddCharacter(1, true)
	Mock.Char(a).vehicle = Mock.AddEntity("speeder", 0, 0, 0)
	Mock.Advance(5, 0.05, Escort({ a }))
	check(near(p.s, 0), "a soldier in a vehicle doesn't count")
end)

test("curved track", function()
	local p = StartMission({ track = { { 0, 0, 0 }, { 30, 0, 0 }, { 30, 5, 40 } } })
	check(near(p.length, 30 + math.sqrt(25 + 1600), 0.01), "length")
	local x, y, z = p:PointAt(30 + p.length * 0 + 20.155)
	check(near(x, 30) and near(y, 2.5, 0.05) and near(z, 20, 0.1), "point on the second leg")
	check(near(p:YawAt(5), math.atan2(1, 0), 0.01), "faces +x on the first leg")
	check(near(p:YawAt(p.length), 0, 0.15), "faces +z at the end")
end)

test("recorder", function()
	local p = StartMission({ track = {} })
	check(Mock.Count("CreateEntity") == 0, "no cart while recording")
	check(Mock.Count("AllowAISpawn") == 2, "no bots while recording")
	local h = Mock.AddCharacter(1, true, 0, 0, 0)
	Mock.Advance(1)
	Mock.MoveTo(h, 0, 0, 5)
	Mock.Advance(1)
	Mock.MoveTo(h, 0, 0, 9)
	Mock.Advance(1)
	check(table.getn(p.recorded) == 2, "a point every 8 m (got " .. table.getn(p.recorded) .. ")")
	local found = 0
	local i
	for i = 1, table.getn(Mock.printed) do
		if string.find(Mock.printed[i], "PAYLOAD_TRACK 2 { 0.0, 0.0, 9.0 },", 1, 1) then found = found + 1 end
		if string.find(Mock.printed[i], "PAYLOAD_CP cp1 team=1", 1, 1) then found = found + 1 end
	end
	check(found == 2, "points and command posts logged")
end)

test("clients only watch", function()
	-- a client runs the same script, but the server moves the payload
	Mock.Reset()
	local savedReset = Mock.Reset
	Mock.Reset = function() savedReset() Mock.net = true Mock.host = false end
	StartMission({ track = STRAIGHT })
	Mock.Reset = savedReset
	check(Mock.Count("CreateEntity") == 0, "no second cart on a client")
	check(Mock.timers["payloadTick"] == nil, "no payload logic on a client")
end)

test("attackers swapped", function()
	local p = StartMission({ track = STRAIGHT, attackers = "def", initialCPs = { cp3 = "att" } })
	check(p.teamATT == 2 and p.teamDEF == 1, "attackers = \"def\" swaps the teams")
	check(Mock.entities["cp3"].team == 2, "initialCPs uses att/def")
end)

test("addme", function()
	sp_missionselect_listbox_contents = { { mapluafile = "tat2%s_%s", era_g = 1, era_c = 1, mode_con_g = 1 } }
	mp_missionselect_listbox_contents = { { mapluafile = "TAT2%s_%s", era_g = 1, mode_con_g = 1 } }
	gModeFallbackNames, gModeFallbackIcons = {}, {}
	local added = {}
	AddDownloadableContent = function(map, mission, mem) table.insert(added, map .. ":" .. mission) end
	PAYLOAD_MISSIONS = { "tat2g", "tat2c", "zzz1g" }
	dofile(MOD .. "addme.lua")
	local sp, mp = sp_missionselect_listbox_contents, mp_missionselect_listbox_contents
	check(sp[1].mode_pay_g == 1 and sp[1].mode_pay_c == 1 and sp[1].mode_con_g == 1, "stock row gains Payload, keeps conquest")
	check(mp[1].mode_pay_g == 1 and mp[1].era_c == 1, "matched case-insensitively")
	check(table.getn(sp) == 2 and sp[2].mapluafile == "zzz1%s_%s" and sp[2].era_g == 1, "unknown map gets its own row")
	check(added[1] == "tat2:tat2g_pay" and table.getn(added) == 3, "missions registered as add-on content")
	check(gModeFallbackNames.pay == "Payload", "the mode is named Payload")
end)

print2(string.format("%d passed, %d failed", passed, failures))
if failures > 0 then
	error("tests failed")
end
