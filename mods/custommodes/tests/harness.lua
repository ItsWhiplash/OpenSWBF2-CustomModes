--
-- Shared by the mode tests, run with the game's own Lua 5.0 (see run_tests.sh). They run the
-- real objective.lua and objectiveconquest.lua from data/scripts/mission.
--

Harness = { failures = 0, passed = 0, current = "?" }

function check(cond, what)
	if cond then
		Harness.passed = Harness.passed + 1
	else
		Harness.failures = Harness.failures + 1
		Mock.verbose = false
		print2("FAIL [" .. Harness.current .. "] " .. what)
	end
end

function near(a, b, tol) return a and b and math.abs(a - b) <= (tol or 0.05) end

function print2(s) Mock.rawprint(s) end

function test(name, fn)
	Harness.current = name
	fn()
end

MISSION = "data/scripts/mission/"
MOD = "mods/custommodes/scripts/"

-- What the engine does to start a mission: run the script's top level (before the mission API
-- exists), register the API, then ScriptPreInit, ScriptInit and ScriptPostLoad.
-- mapFn is "PayloadMap" or "RushMap"; posts are { name, x, z, team } (default: three), and
-- the stock script lists them all to conquest unless conquestPosts says otherwise.
function StartMission(cfg, mapFn, posts, conquestPosts)
	Mock.Reset()
	Mock.ran = {}
	Mock.files["objective"] = MISSION .. "objective.lua"
	Mock.files["objectiveconquest"] = MISSION .. "objectiveconquest.lua"
	Mock.files["objectivepayload"] = MOD .. "objectivepayload.lua"
	Mock.files["objectiverush"] = MOD .. "objectiverush.lua"
	Mock.files["objectivehorde"] = MOD .. "objectivehorde.lua"
	Mock.files["custommode_mission"] = MOD .. "custommode_mission.lua"
	__OBJECTIVE_LUA__ = nil
	ScriptPreInit, ScriptInit, ScriptPostLoad = nil, nil, nil
	ATT, DEF, RetailReadDataFile, gCustomMode = nil, nil, nil, nil
	ReadDataFile, SetMemoryPoolSize, SetHeroClass = nil, nil, nil

	ScriptCB_DoFile("custommode_mission")
	_G[mapFn or "PayloadMap"]("tat2g", cfg)

	ReadDataFile = Mock.ReadDataFile
	SetMemoryPoolSize = Mock.SetMemoryPoolSize
	SetHeroClass = Mock.SetHeroClass
	posts = posts or { { "cp1", 0, -20, 1 }, { "cp2", 0, 60, 2 }, { "cp3", 0, 120, 2 } }
	Mock.cpNames = {}
	local i
	for i = 1, table.getn(posts) do
		Mock.AddEntity(posts[i][1], posts[i][2], 0, posts[i][3], posts[i][4])
		table.insert(Mock.cpNames, posts[i][1])
	end
	Mock.cpNames = conquestPosts or Mock.cpNames
	ScriptPreInit()
	ScriptInit()
	ScriptPostLoad()
	return gCustomMode
end
