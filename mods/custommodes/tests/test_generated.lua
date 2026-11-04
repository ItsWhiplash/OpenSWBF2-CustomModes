--
-- The custom modes on the generated maps (mods/mapgen): every settings file mods/mapgen/modes.py
-- wrote runs through the mock engine, with the map's real command posts (MapgenPosts, which
-- run_tests.sh exports from the map generator).
--

if MapgenPosts then

-- like StartMission, but runs a settings file as the game would
local function StartGenerated(mode, code)
	Mock.Reset()
	Mock.ran = {}
	Mock.files["objective"] = MISSION .. "objective.lua"
	Mock.files["objectiveconquest"] = MISSION .. "objectiveconquest.lua"
	Mock.files["objectivepayload"] = MOD .. "objectivepayload.lua"
	Mock.files["objectiverush"] = MOD .. "objectiverush.lua"
	Mock.files["objectivehorde"] = MOD .. "objectivehorde.lua"
	Mock.files["objectivesnd"] = MOD .. "objectivesnd.lua"
	Mock.files["objectiveinfiltration"] = MOD .. "objectiveinfiltration.lua"
	Mock.files["custommode_mission"] = MOD .. "custommode_mission.lua"
	Mock.files[code .. "_con"] = Mock.files["tat2g_con"]
	__OBJECTIVE_LUA__ = nil
	ScriptPreInit, ScriptInit, ScriptPostLoad = nil, nil, nil
	ATT, DEF, RetailReadDataFile, gCustomMode = nil, nil, nil, nil
	ReadDataFile, SetMemoryPoolSize, SetHeroClass = nil, nil, nil
	ScriptCB_DoFile("custommode_mission")
	dofile("mods/custommodes/maps/" .. mode .. "/" .. code .. ".lua")
	ReadDataFile = Mock.ReadDataFile
	SetMemoryPoolSize = Mock.SetMemoryPoolSize
	SetHeroClass = Mock.SetHeroClass
	local posts = MapgenPosts[code]
	Mock.cpNames = {}
	local i
	for i = 1, table.getn(posts) do
		local p = posts[i]
		local e = Mock.AddEntity(p[1], p[2], p[3], p[4], p[5])
		table.insert(Mock.cpNames, p[1])
	end
	ScriptPreInit()
	ScriptInit()
	ScriptPostLoad()
	return gCustomMode
end

local function Near(name, x, z, within)
	local e = Mock.entities[name]
	return e and math.abs(e.x - x) < within and math.abs(e.z - z) < within
end

local code
for _, code in ipairs({ "gtsc", "gtsg", "hthg" }) do
	local map = string.upper(string.sub(code, 1, 3))

	test("generated " .. code .. ": every mode loads the map's own Conquest", function()
		local mode
		for _, mode in ipairs({ "pay", "rush", "horde", "snd", "inf" }) do
			local m = StartGenerated(mode, code)
			check(m ~= nil, mode .. " started")
			check(Mock.missionLvl == "..\\..\\AddOn\\" .. map .. "\\Data\\_lvl_pc\\mission.lvl",
				mode .. ": the Conquest script comes from the map's AddOn (" .. tostring(Mock.missionLvl) .. ")")
		end
	end)

	test("generated " .. code .. ": layouts", function()
		local p = StartGenerated("pay", code)
		local cp1 = Mock.entities["cp1"]
		local start = p.track[1]
		check(math.abs(start[1] - cp1.x) < 120 and math.abs(start[3] - cp1.z) < 120, "the payload starts by the landing")
		check(Mock.Count("CreateEntity") == 1, "the payload is made")

		local r = StartGenerated("rush", code)
		local last = r.stages[table.getn(r.stages)]
		local total, s = 0
		for s = 1, table.getn(r.stages) do total = total + table.getn(r.stages[s]) end
		check(r.base[1] == "cp1" and total == table.getn(MapgenPosts[code]) - 1, "Rush: every post but the landing in a stage")
		if map == "GTS" then
			check(table.concat(last, ",") == "cp6,cp7" or table.concat(last, ",") == "cp7,cp6", "Rush on GTS ends on the ship")
		else
			local hasBase = false
			for s = 1, table.getn(last) do hasBase = hasBase or last[s] == "cp9" end
			check(hasBase, "Rush on Hoth ends at the base hangar")
		end

		local h = StartGenerated("horde", code)
		check(h.lastStand == "cp1" and Mock.entities["cp5"] ~= nil, "Horde: the landing is the last stand")

		local d = StartGenerated("snd", code)
		check(Mock.entities[d.sites[1]] ~= nil and Mock.entities[d.sites[2]] ~= nil, "S&D: both sites are real posts")

		local f = StartGenerated("inf", code)
		check(table.getn(f.targetNames) == table.getn(f.targetSpots) and table.getn(f.targetNames) >= 4, "Infiltration: every target made")
	end)
end

end
