--
-- OpenSWBF2 custom modes: turns a stock map into a mission of another mode.
--
-- A custom mission (tat2g_pay, tat2g_rush, ...) is a tiny script that calls PayloadMap or
-- RushMap with the map's settings. Instead of copying the stock map's loading code, it reads the
-- stock conquest mission (tat2g_con) from the game's own mission.lvl and runs it, with changes:
--   * ScriptInit can also load extra classes (the payload's vehicle) and make room for them;
--   * in ScriptPostLoad, conquest is created but never started (the map's other setup, such as
--     death regions, doors and hero rules, still runs), and its command posts are noted in
--     gCustomModeCPs;
--   * then the mode's objective starts.
-- Every machine runs this the same way, so clients load what the server loads.
--

-- true where the game is simulated: single player, or the multiplayer host
function CustomMode_IsAuthority()
	if ScriptCB_InNetGame and ScriptCB_InNetGame() then
		return ScriptCB_GetAmHost() and true or false
	end
	return true
end

-- settings the loader uses itself; the rest go to the objective
local LoaderKeys = { base = 1, extraData = 1, memoryPools = 1, attackers = 1, objectiveScript = 1, objectiveClass = 1 }

function CustomModeMission(cfg)
	gCustomModeConfig = cfg
	local base = cfg.base
	assert(base, "CustomModeMission needs base, the stock mission to build on (e.g. \"tat2g_con\")")
	assert(cfg.objectiveScript and cfg.objectiveClass, "CustomModeMission needs objectiveScript and objectiveClass")

	local baseFns = {}
	local ours = {}

	-- Hooks for the stock ScriptInit. They stay installed (the game wraps ReadDataFile itself
	-- once ingame.lvl loads, around whatever is installed then) and pass through when inactive.
	local hooking = false
	local injected = false
	-- the engine registers these after this script's top level runs, so they're taken in ScriptInit
	local RealReadDataFile, RealSetMemoryPoolSize, RealSetHeroClass

	local function Inject()
		if injected then return end
		injected = true
		local i
		for i = 1, table.getn(cfg.extraData or {}) do
			print("OpenSWBF2 custom mode: loading " .. cfg.extraData[i][1])
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

	-- notes each team's hero class (Horde's boss) in gCustomModeHeroes
	local function SetHeroClassHook(...)
		if type(arg[1]) == "number" and type(arg[2]) == "string" then
			gCustomModeHeroes[arg[1]] = arg[2]
		end
		return RealSetHeroClass(unpack(arg))
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
		assert(baseFns.ScriptInit ~= ours.ScriptInit, "custom mode: stock mission " .. base .. " was not found")
		ScriptCB_DoFile(cfg.objectiveScript)
		if baseFns.ScriptPreInit and baseFns.ScriptPreInit ~= ours.ScriptPreInit then
			baseFns.ScriptPreInit()
		end
	end

	function ours.ScriptInit()
		RealReadDataFile = RealReadDataFile or ReadDataFile
		RealSetMemoryPoolSize = RealSetMemoryPoolSize or SetMemoryPoolSize
		RealSetHeroClass = RealSetHeroClass or SetHeroClass
		gCustomModeHeroes = {}
		local pool, extra
		for pool, extra in pairs(cfg.memoryPools or {}) do
			RealSetMemoryPoolSize(pool, extra) -- in case the map never sets it
		end
		ReadDataFile = ReadDataFileHook
		SetMemoryPoolSize = SetMemoryPoolSizeHook
		if RealSetHeroClass then SetHeroClass = SetHeroClassHook end
		hooking = true
		baseFns.ScriptInit()
		hooking = false
		Inject() -- a map that loads no sides
		if SetMemoryPoolSize == SetMemoryPoolSizeHook then
			SetMemoryPoolSize = RealSetMemoryPoolSize
		end
	end

	function ours.ScriptPostLoad()
		gCustomModeCPs = {}
		local savedStart, savedAdd
		if ObjectiveConquest then
			savedStart = ObjectiveConquest.Start
			savedAdd = ObjectiveConquest.AddCommandPost
			ObjectiveConquest.Start = function(self) end
			ObjectiveConquest.AddCommandPost = function(self, cp)
				if cp and cp.name then
					table.insert(gCustomModeCPs, cp.name)
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
			if not LoaderKeys[k] then
				o[k] = v
			end
		end
		local Class = _G[cfg.objectiveClass]
		assert(Class, "custom mode: no objective " .. cfg.objectiveClass)
		gCustomMode = Class:New(o)
		gCustomMode:Start()
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

-- Payload on a stock map, with the era's vehicle filled in: PayloadMap("tat2g", { ... })
function PayloadMap(code, cfg)
	local era = string.sub(code, -1)
	local defaults = PayloadEraDefaults[era] or PayloadEraDefaults.g
	cfg.base = cfg.base or (code .. "_con")
	cfg.payloadClass = cfg.payloadClass or defaults.payloadClass
	cfg.extraData = cfg.extraData or defaults.extraData
	cfg.memoryPools = cfg.memoryPools or { EntityHover = 1 }
	cfg.objectiveScript = "ObjectivePayload"
	cfg.objectiveClass = "ObjectivePayload"
	CustomModeMission(cfg)
end

-- Horde's shop for an era: Galactic Conquest's enhancements, the team's hero, and two vehicles.
-- Bonus items show the game's own name for them when someone steps on the pad.
function HordeShop(era)
	local function Bonus(bonus, tech, price)
		return { id = bonus, kind = "bonus", bonus = bonus, price = price,
			message = "ifs.freeform.purchase.tech." .. tech .. ".enhancement" }
	end
	local vehicles = HordeEraVehicles[era] or HordeEraVehicles.g
	return {
		Bonus("sensor_array", "surveillance", 75),
		Bonus("energy_boost", "adrenaline", 100),
		Bonus("bacta_tanks", "bacta_refinery", 150),
		Bonus("combat_shielding", "advanced_armor", 150),
		Bonus("advanced_blasters", "blaster_amplification", 250),
		Bonus("leader", "leadership", 300),
		{ id = "hero", kind = "hero", price = 250 },
		{ id = "bike", kind = "vehicle", class = vehicles.bike, price = 80 },
		{ id = "tank", kind = "vehicle", class = vehicles.tank, price = 200 },
	}
end

HordeEraVehicles = {
	g = { side = "SIDE\\imp.lvl", tank = "imp_hover_fightertank", bike = "imp_hover_speederbike" },
	c = { side = "SIDE\\rep.lvl", tank = "rep_hover_fightertank", bike = "rep_hover_barcspeeder" },
}

-- Horde on a stock map: HordeMap("tat2g", { ... })
function HordeMap(code, cfg)
	local era = string.sub(code, -1)
	local vehicles = HordeEraVehicles[era] or HordeEraVehicles.g
	cfg.base = cfg.base or (code .. "_con")
	cfg.shop = cfg.shop or HordeShop(era)
	cfg.extraData = cfg.extraData or { { vehicles.side, vehicles.tank, vehicles.bike } }
	cfg.memoryPools = cfg.memoryPools or { EntityHover = 4 }
	cfg.objectiveScript = "ObjectiveHorde"
	cfg.objectiveClass = "ObjectiveHorde"
	CustomModeMission(cfg)
end

-- Infiltration's targets for an era: each side's tank, both loaded, so the garrison gets its own
InfiltrationEraTargets = {
	g = { { "SIDE\\imp.lvl", "imp_hover_fightertank" }, { "SIDE\\all.lvl", "all_hover_combatspeeder" } },
	c = { { "SIDE\\rep.lvl", "rep_hover_fightertank" }, { "SIDE\\cis.lvl", "cis_hover_aat" } },
}

-- Infiltration on a stock map: InfiltrationMap("tat2g", { ... })
function InfiltrationMap(code, cfg)
	local era = string.sub(code, -1)
	local targets = InfiltrationEraTargets[era] or InfiltrationEraTargets.g
	cfg.base = cfg.base or (code .. "_con")
	if not cfg.targetClass and not cfg.targetClasses then
		cfg.targetClasses = {}
		local i
		for i = 1, table.getn(targets) do
			cfg.targetClasses[string.sub(targets[i][2], 1, 3)] = targets[i][2]
		end
		cfg.extraData = cfg.extraData or targets
	end
	cfg.memoryPools = cfg.memoryPools or { EntityHover = 8 }
	cfg.objectiveScript = "ObjectiveInfiltration"
	cfg.objectiveClass = "ObjectiveInfiltration"
	CustomModeMission(cfg)
end

-- Search & Destroy on a stock map: SnDMap("tat2g", { ... })
function SnDMap(code, cfg)
	cfg.base = cfg.base or (code .. "_con")
	cfg.objectiveScript = "ObjectiveSnD"
	cfg.objectiveClass = "ObjectiveSnD"
	CustomModeMission(cfg)
end

-- Rush on a stock map: RushMap("tat2g", { ... })
function RushMap(code, cfg)
	cfg.base = cfg.base or (code .. "_con")
	cfg.objectiveScript = "ObjectiveRush"
	cfg.objectiveClass = "ObjectiveRush"
	CustomModeMission(cfg)
end
