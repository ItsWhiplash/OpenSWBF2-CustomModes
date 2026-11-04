--
-- A stand-in for the game's mission API, enough to run the payload scripts headless.
-- Every engine call the scripts make is either simulated (timers, entities, characters) or
-- recorded in Mock.calls for the tests to inspect. Lua 5.0, like the game.
--

Mock = {}

function Mock.Reset()
	Mock.time = 0
	Mock.timers = {}
	Mock.timerCallbacks = {}
	Mock.entities = {}
	Mock.characters = {}       -- index -> { team, human, unit = { x, y, z, alive }, vehicle }
	Mock.teams = { [1] = {}, [2] = {} }
	Mock.calls = {}
	Mock.victory = nil
	Mock.net = false
	Mock.host = true
	Mock.points = {}
	Mock.reinforcements = {}
	Mock.enterVehicle = {}
	Mock.pools = {}
	Mock.reads = {}
	Mock.stockLoaded = false
	Mock.printed = {}
	Mock.deathFns = {}
	Mock.ticketFns = {}
	Mock.defeat = nil
	Mock.cpNames = { "CP1", "cp2" }
	Mock.spawnFns = {}
	Mock.aiSpawn = { [1] = true, [2] = true }
	Mock.botsPerTeam = 20
	Mock.bonus = {}
	Mock.bleed = {}
	Mock.heroUnlocked = {}
	Mock.heroes = {}
end

function Mock.Record(name, a1, a2, a3, a4)
	table.insert(Mock.calls, { name = name, a1 = a1, a2 = a2, a3 = a3, a4 = a4 })
end

function Mock.Count(name, a1)
	local n, i = 0
	for i = 1, table.getn(Mock.calls) do
		if Mock.calls[i].name == name and (a1 == nil or Mock.calls[i].a1 == a1) then
			n = n + 1
		end
	end
	return n
end

function Mock.Find(name)
	local i
	for i = 1, table.getn(Mock.calls) do
		if Mock.calls[i].name == name then
			return Mock.calls[i]
		end
	end
end

-- scripts by name, for ScriptCB_DoFile
Mock.files = {}
Mock.ran = {}
function ScriptCB_DoFile(name)
	name = string.lower(name)
	if Mock.ran[name] then return end
	local f = Mock.files[name]
	assert(f, "ScriptCB_DoFile: no script " .. name)
	if name == "tat2g_con" then
		assert(Mock.stockLoaded, "stock mission run before its lvl was read")
	end
	Mock.ran[name] = 1
	if type(f) == "function" then f() else dofile(f) end
end

local oldPrint = print
Mock.rawprint = print
function print(...)
	local s = ""
	local i
	for i = 1, table.getn(arg) do s = s .. tostring(arg[i]) end
	table.insert(Mock.printed, s)
	if Mock.verbose then oldPrint(s) end
end

-- timers ------------------------------------------------------------------
function CreateTimer(name)
	local t = { name = name, value = 0, running = false, rate = 1 }
	Mock.timers[name] = t
	return t
end
function FindTimer(name) return Mock.timers[name] end
function DestroyTimer(t) if t then Mock.timers[t.name] = nil; t.dead = true end end
function SetTimerValue(t, v) t.value = v end
function GetTimerValue(t) return t.value end
function StartTimer(t) t.running = true end
function StopTimer(t) t.running = false end
function SetTimerRate(t, r) t.rate = r end
function ShowTimer(t) Mock.shownTimer = t end
function OnTimerElapse(fn, timer)
	local cb = { fn = fn, timer = timer }
	table.insert(Mock.timerCallbacks, cb)
	return cb
end
function ReleaseTimerElapse(cb) if cb then cb.released = true end end

-- advances the game by dt seconds in small frames
function Mock.Advance(seconds, frame, each)
	frame = frame or 0.05
	local steps = math.floor(seconds / frame + 0.5)
	local i
	for i = 1, steps do
		Mock.time = Mock.time + frame
		local name, t
		local fired = {}
		for name, t in pairs(Mock.timers) do
			if t.running and not t.dead then
				t.value = t.value - frame * t.rate
				if t.value <= 0 then
					t.running = false
					table.insert(fired, t)
				end
			end
		end
		local j, k
		for j = 1, table.getn(fired) do
			for k = 1, table.getn(Mock.timerCallbacks) do
				local cb = Mock.timerCallbacks[k]
				if not cb.released and (cb.timer == nil or cb.timer == fired[j]) then
					cb.fn(fired[j])
				end
			end
		end
		if each then each() end
	end
end

function ScriptCB_GetMissionTime() return Mock.time end
function ScriptCB_InNetGame() return Mock.net end
function ScriptCB_GetAmHost() return Mock.host end
function ScriptCB_GetCONNumBots() return 12 end
function ScriptCB_SetNumBots(n) Mock.Record("SetNumBots", n) end
function ScriptCB_GetCONMaxTimeLimit() return 0 end

-- matrices and entities -------------------------------------------------------
function CreateMatrix(angle, ax, ay, az, x, y, z)
	return { yaw = angle, x = x, y = y, z = z }
end

local function Ent(e)
	if type(e) == "string" then return Mock.entities[string.lower(e)] end
	return e
end

function Mock.AddEntity(name, x, y, z, team)
	local e = { name = string.lower(name), x = x, y = y, z = z, team = team or 0, alive = true, props = {}, capturable = true }
	if string.find(e.name, "^cp") then e.isPost = true end
	Mock.entities[e.name] = e
	return e
end

function CreateEntity(class, m, name)
	Mock.Record("CreateEntity", class, name)
	local e = Mock.AddEntity(name or "unnamed", m.x, m.y, m.z)
	e.class = class
	e.yaw = m.yaw
	return e
end
function GetEntityPtr(e) return Ent(e) end
function GetObjectPtr(e) return Ent(e) end
function GetEntityName(e) e = Ent(e) return e and e.name end
function SetEntityMatrix(e, m)
	e = Ent(e)
	e.x, e.y, e.z, e.yaw = m.x, m.y, m.z, m.yaw
	Mock.placements = (Mock.placements or 0) + 1
end
function GetWorldPosition(e)
	e = Ent(e)
	if not e then return end
	return e.x, e.y, e.z
end
function IsObjectAlive(e)
	e = Ent(e)
	if not e then return nil end
	return e.alive
end
function RespawnObject(e) e = Ent(e) e.alive = true Mock.Record("RespawnObject", e.name) end
function KillObject(e)
	e = Ent(e)
	if e.char then Mock.KillChar(e.char) else e.alive = false end
	Mock.Record("KillObject", e.name or e.char)
end
function SetProperty(e, k, v)
	local x = Ent(e)
	if x then
		x.props[k] = v
		-- like CommandPost::SetProperty: no capture region, or (Radius) a new one when it has none
		if k == "CaptureRegion" and v == "" then x.capturable = false end
		if k == "Radius" and not x.capturable then x.capturable = true end
	end
	Mock.Record("SetProperty", type(e) == "string" and string.lower(e) or (x and x.name), k, v)
end
function SetObjectTeam(e, t) Ent(e).team = t Mock.Record("SetObjectTeam", string.lower(e), t) end
function AICanCaptureCP(name, team, b) Mock.Record("AICanCaptureCP", string.lower(name), team, b) end
-- a team stands on a post until it's theirs; false when the post has no capture region
function Mock.Capture(name, team)
	local e = Ent(name)
	if not e.capturable then return false end
	e.team = team
	return true
end
function GetObjectTeam(e) e = Ent(e) return e and e.team end

-- characters --------------------------------------------------------------------
function Mock.AddCharacter(team, human, x, y, z)
	local c = table.getn(Mock.characters)
	local ch = { team = team, human = human, unit = { x = x or 1000, y = y or 0, z = z or 1000, alive = true, props = {}, char = c } }
	Mock.characters[c + 1] = ch
	table.insert(Mock.teams[team], c)
	return c
end
function Mock.Char(c) return Mock.characters[c + 1] end
function Mock.MoveTo(c, x, y, z) local u = Mock.Char(c).unit u.x, u.y, u.z = x, y, z end
function GetTeamSize(t) return table.getn(Mock.teams[t] or {}) end
function GetTeamMember(t, i) return Mock.teams[t][i + 1] end
function GetCharacterUnit(c) local ch = Mock.Char(c) return ch and ch.unit end
function GetCharacterVehicle(c) return Mock.Char(c).vehicle end
function IsCharacterHuman(c) return Mock.Char(c).human end
function GetCharacterTeam(c) return Mock.Char(c).team end
function ExitVehicle(c) Mock.Record("ExitVehicle", c) Mock.Char(c).vehicle = nil end
function OnCharacterEnterVehicle(fn) table.insert(Mock.enterVehicle, fn) end
function Mock.EnterVehicle(c, vehicle)
	Mock.Char(c).vehicle = Ent(vehicle)
	local i
	for i = 1, table.getn(Mock.enterVehicle) do Mock.enterVehicle[i](c, Ent(vehicle)) end
end

-- teams, objectives, HUD --------------------------------------------------------------
function SetTeamPoints(t, p) Mock.points[t] = p end
function GetTeamPoints(t) return Mock.points[t] or 0 end
function AddTeamPoints(t, p) Mock.points[t] = (Mock.points[t] or 0) + p end
function ShowTeamPoints(t, b) Mock.Record("ShowTeamPoints", t, b) end
local function TicketsChanged(t)
	local i
	for i = 1, table.getn(Mock.ticketFns) do Mock.ticketFns[i](t, Mock.reinforcements[t]) end
end
-- like the engine: a negative count is stored as 0x7fffffff (unlimited)
function SetReinforcementCount(t, n)
	if n < 0 then n = 2147483647 end
	Mock.reinforcements[t] = n
	TicketsChanged(t)
end
function Mock.Unlimited(t) return (Mock.reinforcements[t] or 0) > 1000000 end
function GetReinforcementCount(t) return Mock.reinforcements[t] or 0 end
function AddReinforcements(t, n)
	Mock.reinforcements[t] = (Mock.reinforcements[t] or 0) + n
	Mock.Record("AddReinforcements", t, n)
	TicketsChanged(t)
end
function MissionVictory(t) Mock.victory = t Mock.Record("MissionVictory", t) end
function MissionDefeat(t) Mock.defeat = t Mock.Record("MissionDefeat", t) end
function Mock.Kill(c)
	local i
	for i = 1, table.getn(Mock.deathFns) do Mock.deathFns[i](c, nil) end
end
function AddAIGoal(team, kind, weight, target)
	Mock.Record("AddAIGoal", team, kind, weight, target)
	return { team = team, kind = kind }
end
function ClearAIGoals(t) Mock.Record("ClearAIGoals", t) end
function DeleteAIGoal(g) Mock.Record("DeleteAIGoal", g) end
function AllowAISpawn(t, b) Mock.aiSpawn[t] = b Mock.Record("AllowAISpawn", t, b) end
function OnCharacterSpawn(fn) table.insert(Mock.spawnFns, fn) end
function GetNumTeamMembersAlive(t)
	local n, i = 0
	for i = 1, table.getn(Mock.teams[t] or {}) do
		local ch = Mock.Char(Mock.teams[t][i])
		if ch.unit.alive then n = n + 1 end
	end
	return n
end
function GetEntityClassName(e) e = Ent(e) return e and e.class end
function GetObjectHealth(e)
	e = Ent(e)
	local max = e.props["MaxHealth"] or e.baseHealth or 300
	return e.props["CurHealth"] or max, max
end
function ActivateBonus(t, name, on)
	if on == nil then on = true end
	Mock.bonus[t] = on and name or (Mock.bonus[t] == name and nil or Mock.bonus[t])
	Mock.Record("ActivateBonus", t, name, on)
end
-- the network sends a bleed rate in 5 bits over 0..8
function SetBleedRate(t, r) Mock.bleed[t] = math.floor(r * 31 / 8 + 0.5) * 8 / 31 end
function GetBleedRate(t) return Mock.bleed[t] or 0 end
function UnlockHeroForTeam(t) Mock.heroUnlocked[t] = true Mock.Record("UnlockHeroForTeam", t) end
function SetTeamAggressiveness(t, v) Mock.aggression = Mock.aggression or {} Mock.aggression[t] = v end
function SetAIViewMultiplier(v) Mock.vision = v end
function ForceHumansOntoTeam1() Mock.Record("ForceHumansOntoTeam1") end
function Mock.SetHeroClass(t, c) Mock.heroes[t] = c end

local function PostOf(t)
	local name, e
	for name, e in pairs(Mock.entities) do
		if e.team == t and e.isPost then return e end
	end
end

-- a unit appears, as the engine spawns one
function Mock.Spawn(c)
	local ch = Mock.Char(c)
	local post = PostOf(ch.team)
	ch.unit = { x = post and post.x or 0, y = 0, z = post and post.z or 0, alive = true, props = {},
		class = ch.class, baseHealth = 300, char = c }
	local i
	for i = 1, table.getn(Mock.spawnFns) do Mock.spawnFns[i](c) end
end

-- the engine's spawn rules, once: bots while their team has more tickets than members alive
-- (and fewer than the bot limit alive), and only at a post the team owns; humans likewise
function Mock.SpawnTick()
	local t
	for t = 1, 2 do
		local i
		for i = 1, table.getn(Mock.teams[t]) do
			local c = Mock.teams[t][i]
			local ch = Mock.Char(c)
			if not ch.unit.alive and PostOf(t) then
				local alive = GetNumTeamMembersAlive(t)
				if ch.human then
					Mock.Spawn(c)
				elseif ch.hero then
					-- a hero isn't counted against the bots (Character::Spawn skips mMemberActive)
					if Mock.heroUnlocked[t] then Mock.heroUnlocked[t] = false Mock.Spawn(c) end
				elseif Mock.aiSpawn[t] and (Mock.reinforcements[t] or 0) > alive and alive < Mock.botsPerTeam then
					Mock.Spawn(c)
				end
			end
		end
	end
end

function Mock.KillChar(c, killer)
	Mock.Char(c).unit.alive = false
	local i
	for i = 1, table.getn(Mock.deathFns) do Mock.deathFns[i](c, killer) end
end
function MapAddEntityMarker(e, ...) Mock.Record("MapAddEntityMarker", e, arg[3]) end
function MapRemoveEntityMarker(e) Mock.Record("MapRemoveEntityMarker", e) end
function MapHideCommandPosts() end
function ShowMessageText(k, t) Mock.Record("ShowMessageText", k, t) end
function SetFlagGameplayType(t) end
function AddMissionObjective() end
function ActivateObjective() end
function CompleteObjective() end
function BroadcastVoiceOver() end
function ShowObjectiveTextPopup() end
function AddMissionHint() end
function OnCharacterDeath(fn) table.insert(Mock.deathFns, fn) end
function OnTicketCountChange(fn) table.insert(Mock.ticketFns, fn) end
function AddDeathRegion(r) Mock.Record("AddDeathRegion", r) end

-- loading --------------------------------------------------------------------------
function Mock.ReadDataFile(file, ...)
	table.insert(Mock.reads, file)
	Mock.Record("ReadDataFile", file, arg[1])
	if file == ".\\mission.lvl" and arg[1] == "tat2g_con" then
		Mock.stockLoaded = true
	end
	-- like game_interface.lua: once ingame.lvl loads, ReadDataFile is wrapped
	if file == "ingame.lvl" and not RetailReadDataFile then
		RetailReadDataFile = ReadDataFile
		ReadDataFile = function(...) Mock.Record("uf_ReadDataFile", arg[1]) return RetailReadDataFile(unpack(arg)) end
	end
end
function Mock.SetMemoryPoolSize(pool, n) Mock.pools[pool] = n end

-- A stand-in for a stock conquest mission, shaped like Pandemic's
Mock.files["tat2g_con"] = function()
	ScriptCB_DoFile("ObjectiveConquest")
	IMP = 1
	ALL = 2
	ATT = IMP
	DEF = ALL
	function ScriptPostLoad()
		conquest = ObjectiveConquest:New{ teamATT = ATT, teamDEF = DEF, textATT = "game.modes.con", multiplayerRules = true }
		local i
		for i = 1, table.getn(Mock.cpNames) do
			conquest:AddCommandPost(CommandPost:New{ name = Mock.cpNames[i] })
		end
		conquest:Start()
		AddDeathRegion("deathregion")
		Mock.stockPostLoadRan = true
	end
	function ScriptInit()
		ReadDataFile("ingame.lvl")
		ReadDataFile("sound\\tat.lvl;tat2gcw")
		ReadDataFile("SIDE\\imp.lvl", "imp_inf_rifleman")
		SetHeroClass(IMP, "imp_hero_darthvader")
		SetHeroClass(ALL, "all_hero_hansolo")
		ReadDataFile("SIDE\\all.lvl", "all_inf_rifleman")
		SetMemoryPoolSize("EntityHover", 2)
		SetMemoryPoolSize("Weapon", 200)
		ReadDataFile("tat\\tat2.lvl", "tat2_con")
		Mock.stockInitRan = true
	end
end
