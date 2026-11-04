--
-- OpenSWBF2 Payload: turns a stock map into a payload mission.
--
-- A payload mission (tat2g_pay, say) is a tiny script that calls PayloadMission{ ... } with
-- the map's settings. Instead of copying the stock map's loading code, it reads the stock
-- conquest mission (tat2g_con) from the game's own mission.lvl and runs it, with three changes:
--   * ScriptInit also loads the payload vehicle's class and makes room for it;
--   * in ScriptPostLoad, conquest is created but never started (the map's other setup, such as
--     death regions, doors and hero rules, still runs), and its command posts are noted;
--   * then the payload objective starts.
-- Every machine runs this the same way, so clients load what the server loads.
--

function PayloadMission(cfg)
	gPayloadConfig = cfg
	local base = cfg.base
	assert(base, "PayloadMission needs base, the stock mission to build on (e.g. \"tat2g_con\")")

	local baseFns = {}
	local ours = {}

	-- Hooks for the stock ScriptInit. They stay installed (the game wraps ReadDataFile itself
	-- once ingame.lvl loads, around whatever is installed then) and pass through when inactive.
	local hooking = false
	local injected = false
	-- the engine registers these after this script's top level runs, so they're taken in ScriptInit
	local RealReadDataFile, RealSetMemoryPoolSize

	local function Inject()
		if injected then return end
		injected = true
		local i
		for i = 1, table.getn(cfg.extraData or {}) do
			print("OpenSWBF2 payload: loading " .. cfg.extraData[i][1])
			RealReadDataFile(unpack(cfg.extraData[i]))
		end
	end

	local function ReadDataFileHook(...)
		if hooking and not injected and type(arg[1]) == "string" then
			-- just before the first side: the vehicle's class loads with the teams' classes
			local File = string.lower(arg[1])
			if string.sub(File, 1, 5) == "side\\" or string.sub(File, 1, 8) == "dc:side\\" then
				Inject()
			end
		end
		return RealReadDataFile(unpack(arg))
	end

	local function SetMemoryPoolSizeHook(...)
		if hooking and type(arg[1]) == "string" and type(arg[2]) == "number" then
			local extra = (cfg.memoryPools or {})[arg[1]]
			if extra then
				arg[2] = arg[2] + extra
			end
		end
		return RealSetMemoryPoolSize(unpack(arg))
	end

	function ours.ScriptPreInit()
		-- ".\\mission.lvl" is the game's own mission.lvl: plain "mission.lvl" means this
		-- addon's while one of its missions is loading
		ReadDataFile(".\\mission.lvl", base)
		ScriptCB_DoFile(base)
		baseFns.ScriptPreInit = ScriptPreInit
		baseFns.ScriptInit = ScriptInit
		baseFns.ScriptPostLoad = ScriptPostLoad
		ScriptPreInit = ours.ScriptPreInit
		ScriptInit = ours.ScriptInit
		ScriptPostLoad = ours.ScriptPostLoad
		assert(baseFns.ScriptInit ~= ours.ScriptInit, "payload: stock mission " .. base .. " was not found")
		ScriptCB_DoFile("ObjectivePayload")
		if baseFns.ScriptPreInit and baseFns.ScriptPreInit ~= ours.ScriptPreInit then
			baseFns.ScriptPreInit()
		end
	end

	function ours.ScriptInit()
		RealReadDataFile = RealReadDataFile or ReadDataFile
		RealSetMemoryPoolSize = RealSetMemoryPoolSize or SetMemoryPoolSize
		local pool, extra
		for pool, extra in pairs(cfg.memoryPools or {}) do
			RealSetMemoryPoolSize(pool, extra) -- in case the map never sets it
		end
		ReadDataFile = ReadDataFileHook
		SetMemoryPoolSize = SetMemoryPoolSizeHook
		hooking = true
		baseFns.ScriptInit()
		hooking = false
		Inject() -- a map that loads no sides
		if SetMemoryPoolSize == SetMemoryPoolSizeHook then
			SetMemoryPoolSize = RealSetMemoryPoolSize
		end
	end

	function ours.ScriptPostLoad()
		gPayloadConquestCPs = {}
		local savedStart, savedAdd
		if ObjectiveConquest then
			savedStart = ObjectiveConquest.Start
			savedAdd = ObjectiveConquest.AddCommandPost
			ObjectiveConquest.Start = function(self) end
			ObjectiveConquest.AddCommandPost = function(self, cp)
				if cp and cp.name then
					table.insert(gPayloadConquestCPs, cp.name)
				end
			end
		end
		if baseFns.ScriptPostLoad then
			baseFns.ScriptPostLoad()
		end
		if ObjectiveConquest then
			ObjectiveConquest.Start = savedStart
			ObjectiveConquest.AddCommandPost = savedAdd
		end

		-- the stock script's ATT and DEF, unless the map's settings swap them
		local att, def = ATT or 1, DEF or 2
		if cfg.attackers == "def" then
			att, def = def, att
		end

		local o = { teamATT = att, teamDEF = def, multiplayerRules = true }
		local k, v
		for k, v in pairs(cfg) do
			if k ~= "base" and k ~= "extraData" and k ~= "memoryPools" and k ~= "attackers" then
				o[k] = v
			end
		end
		gPayload = ObjectivePayload:New(o)
		gPayload:Start()
	end

	ScriptPreInit = ours.ScriptPreInit
	ScriptInit = ours.ScriptInit
	ScriptPostLoad = ours.ScriptPostLoad
end

-- The vehicle each era uses unless a map says otherwise
PayloadEraDefaults = {
	g = { payloadClass = "imp_hover_fightertank", extraData = { { "SIDE\\imp.lvl", "imp_hover_fightertank" } } },
	c = { payloadClass = "rep_hover_fightertank", extraData = { { "SIDE\\rep.lvl", "rep_hover_fightertank" } } },
}

-- PayloadMission with the era's vehicle filled in: PayloadMap("tat2g", { ...settings... })
function PayloadMap(code, cfg)
	local era = string.sub(code, -1)
	local defaults = PayloadEraDefaults[era] or PayloadEraDefaults.g
	cfg.base = cfg.base or (code .. "_con")
	cfg.payloadClass = cfg.payloadClass or defaults.payloadClass
	cfg.extraData = cfg.extraData or defaults.extraData
	cfg.memoryPools = cfg.memoryPools or { EntityHover = 1 }
	PayloadMission(cfg)
end
