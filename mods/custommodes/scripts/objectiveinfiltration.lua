--
-- OpenSWBF2 Infiltration game mode (co-op).
--
-- Every human is on the squad, with optional bot squadmates, and gets one life. The squad
-- inserts at one command post, open for a short spawn window and then closed, and must destroy
-- every target (enemy vehicles parked across the map as depots), then get a survivor back to the
-- extraction point. If the whole squad is down, the mission fails.
--
-- The garrison is bots with unlimited lives. It starts quiet: few of them, passive, half-blind.
-- Destroying a target, or killing too many guards too quickly, trips the alarm. Reinforcements
-- pour in and turn aggressive for a while, then it settles back down, but every alarm leaves the
-- garrison bigger and makes the next alarm worse.
--
-- How the engine is used (see README.md):
--   * players spawn only at a post their team owns, so the insertion post is the squad's for
--     the spawn window and neutral after: death is final;
--   * the engine never takes a ticket on a death (scripts do, and this one doesn't), and bots
--     spawn while their team has more tickets than members alive, so the garrison's ticket count
--     is how many guards are alive at once;
--   * targets are vehicles made with CreateEntity, like Payload's cart: real, networked objects
--     destroyed with weapons and explosives. Anyone who gets in one is put out.
--

ScriptCB_DoFile("Objective")

ObjectiveInfiltration = Objective:New
{
	squadTeam = 1,
	garrisonTeam = 2,

	-- posts and targets: worked out unless given
	insertion = nil,              -- the squad's post (default: its post farthest from the enemy)
	extraction = nil,             -- where to get out (default: the insertion post)
	idlePosts = nil,              -- { "cp10", ... }: posts out of play (such as a ship's), nobody's
	targets = nil,                -- { { x, y, z }, ... } or { { post = "cp3" }, ... }
	targetCount = 5,              -- for the automatic layout: one beside each of the farthest posts
	targetOffset = 10,            -- metres from a post a target is parked
	targetClass = nil,            -- default: the garrison's side's tank, from targetClasses
	targetClasses = nil,          -- { imp = "...", all = "...", ... } by side (InfiltrationMap fills it)
	commandPosts = nil,

	-- rides: vehicles made for the squad (to start on a ship, say, and fly down)
	rides = nil,                  -- { { x, y, z }, ... }: made at the start, by the insertion
	escapeRides = nil,            -- { { x, y, z }, ... }: when the targets are down, one per survivor
	                              -- at the spot nearest them, to get back to extraction
	rideClass = nil,              -- the rides' vehicle
	rideSpacing = 12,             -- metres between rides at one spot

	-- the squad
	spawnWindow = 20,             -- seconds to spawn (longer than the engine's 15 s multiplayer cycle)
	squadBots = 3,                -- bot squadmates on top of the humans
	extractRadius = 8,
	extractTime = 5,              -- seconds a survivor must stay at extraction
	extractHeight = nil,          -- metres above or below the point that count (nil: any height;
	                              -- set it when the point is on a ship, over the ground)
	wipeGrace = 2,

	-- the garrison and the alarm (level = alarms so far)
	quietGarrison = 6,            -- guards alive when quiet
	quietPerLevel = 3,            -- more after each alarm
	alarmGarrison = 14,           -- guards alive during an alarm
	alarmPerLevel = 4,            -- more for each later alarm
	alarmTime = 60,               -- seconds an alarm lasts
	alarmTimePerLevel = 15,       -- longer for each later alarm
	noiseKills = 4,               -- guards killed within noiseWindow seconds trips the alarm
	noiseWindow = 20,
	quietAggression = 0.3,
	alarmAggression = 1.0,
	quietVision = 0.5,            -- the AI's sight (all bots: the engine has one setting), 0.1 to 1
	alarmVision = 1.0,

	-- AI goals
	aiTargetWeight = 100,
	aiHuntWeight = 60,            -- the garrison's hunting during an alarm

	pollInterval = 0.25,
}

local function Log(text)
	print("OpenSWBF2 infiltration: " .. text)
end

--=============================
-- Rules (pure Lua; the tests call these directly)
--=============================

function ObjectiveInfiltration:GarrisonSize(level, alarmed)
	if alarmed then
		return self.alarmGarrison + self.alarmPerLevel * (level - 1)
	end
	return self.quietGarrison + self.quietPerLevel * level
end

function ObjectiveInfiltration:AlarmLength(level)
	return self.alarmTime + self.alarmTimePerLevel * (level - 1)
end

-- posts: list of { name, x, y, z, team }. Fills insertion, extraction, targetSpots.
function ObjectiveInfiltration:Layout(posts)
	local function Dist2(a, b)
		local dx, dz = a.x - b.x, a.z - b.z
		return dx * dx + dz * dz
	end
	local byName, i = {}
	for i = 1, table.getn(posts) do byName[posts[i].name] = posts[i] end

	local home = self.insertion and byName[self.insertion]
	if not home then
		local mine, theirs = {}, {}
		for i = 1, table.getn(posts) do
			if posts[i].team == self.squadTeam then table.insert(mine, posts[i])
			else table.insert(theirs, posts[i]) end
		end
		if table.getn(mine) == 0 then mine = posts end
		if table.getn(theirs) == 0 then theirs = posts end
		local away = { x = 0, z = 0 }
		for i = 1, table.getn(theirs) do
			away.x = away.x + theirs[i].x / table.getn(theirs)
			away.z = away.z + theirs[i].z / table.getn(theirs)
		end
		home = mine[1]
		for i = 2, table.getn(mine) do
			if Dist2(mine[i], away) > Dist2(home, away) then home = mine[i] end
		end
	end
	self.insertion = home.name
	self.extraction = self.extraction or home.name

	-- the garrison's posts, farthest from the insertion first
	self.garrisonPosts = {}
	for i = 1, table.getn(posts) do
		if posts[i].name ~= home.name then table.insert(self.garrisonPosts, posts[i]) end
	end
	table.sort(self.garrisonPosts, function(a, b)
		local da, db = Dist2(a, home), Dist2(b, home)
		if da == db then return a.name < b.name end
		return da > db
	end)

	self.targetSpots = {}
	local list = self.targets
	if not list then
		list = {}
		for i = 1, math.min(self.targetCount, table.getn(self.garrisonPosts)) do
			table.insert(list, { post = self.garrisonPosts[i].name })
		end
	end
	for i = 1, table.getn(list) do
		local t = list[i]
		if t.post then
			local p = byName[string.lower(t.post)]
			if p then
				-- beside the post, on the side away from the insertion
				local dx, dz = p.x - home.x, p.z - home.z
				local len = math.sqrt(dx * dx + dz * dz)
				if len < 1 then dx, dz, len = 1, 0, 1 end
				table.insert(self.targetSpots, { p.x + dx / len * self.targetOffset, (p.y or 0) + 1,
					p.z + dz / len * self.targetOffset })
			end
		else
			table.insert(self.targetSpots, { t[1], t[2], t[3] })
		end
	end
	for i = 1, table.getn(self.garrisonPosts) do self.garrisonPosts[i] = self.garrisonPosts[i].name end
end

--=============================
-- Engine side
--=============================

-- positions: { { x, y, z }, ... } of the survivors. The escape rides' spots: for each survivor
-- the nearest of escapeRides, the second and later ones at a spot set out rideSpacing apart.
function ObjectiveInfiltration:EscapePlan(positions)
	local spots, out, used = self.escapeRides or {}, {}, {}
	if table.getn(spots) == 0 then return out end
	local i, j
	for i = 1, table.getn(positions) do
		local p, best, bestD = positions[i], 1
		for j = 1, table.getn(spots) do
			local dx, dz = spots[j][1] - p[1], spots[j][3] - p[3]
			local d = dx * dx + dz * dz
			if not bestD or d < bestD then best, bestD = j, d end
		end
		local k = used[best] or 0
		used[best] = k + 1
		local s = spots[best]
		table.insert(out, { s[1] + k * self.rideSpacing, s[2], s[3] })
	end
	return out
end

-- Where a squad member is: their vehicle's position when they're in one.
local function MemberPosition(c)
	local vehicle = GetCharacterVehicle and GetCharacterVehicle(c)
	if vehicle then return GetWorldPosition(vehicle) end
	local unit = GetCharacterUnit(c)
	if unit and IsObjectAlive(unit) then return GetWorldPosition(unit) end
end

function ObjectiveInfiltration:MakeRides(spots)
	local i
	for i = 1, table.getn(spots) do
		self.rideCount = (self.rideCount or 0) + 1
		local p, name = spots[i], "infil_ride_" .. self.rideCount
		if CreateEntity(self.rideClass, CreateMatrix(0, 0, 1, 0, p[1], p[2], p[3]), name) then
			SetObjectTeam(name, self.squadTeam)
		else
			Log("could not create ride " .. self.rideCount .. " (" .. tostring(self.rideClass) .. ")")
		end
	end
end

function ObjectiveInfiltration:AllPosts()
	local names, seen = {}, {}
	local lists = { self.commandPosts or {}, gCustomModeCPs or {} }
	local i, j
	for i = 1, 2 do
		for j = 1, table.getn(lists[i]) do
			local name = string.lower(lists[i][j])
			if not seen[name] and GetEntityPtr(name) then
				seen[name] = 1
				table.insert(names, name)
			end
		end
	end
	return names
end

function ObjectiveInfiltration:SetPosture(alarmed)
	SetReinforcementCount(self.garrisonTeam, self:GarrisonSize(self.level, alarmed))
	SetTeamAggressiveness(self.garrisonTeam, alarmed and self.alarmAggression or self.quietAggression)
	SetAIViewMultiplier(alarmed and self.alarmVision or self.quietVision)

	local i
	for i = 1, table.getn(self.AIGoals or {}) do DeleteAIGoal(self.AIGoals[i]) end
	self.AIGoals = {}
	local live = self:LiveTargets()
	for i = 1, table.getn(live) do
		table.insert(self.AIGoals, AddAIGoal(self.squadTeam, "Destroy", self.aiTargetWeight / table.getn(live), live[i]))
		table.insert(self.AIGoals, AddAIGoal(self.garrisonTeam, "Defend", self.aiTargetWeight / table.getn(live), live[i]))
	end
	if self.extractOpen then
		table.insert(self.AIGoals, AddAIGoal(self.squadTeam, "Defend", self.aiTargetWeight, self.extraction))
	end
	if alarmed then
		table.insert(self.AIGoals, AddAIGoal(self.garrisonTeam, "Deathmatch", self.aiHuntWeight))
	end
end

function ObjectiveInfiltration:LiveTargets()
	local live, i = {}
	for i = 1, table.getn(self.targetNames) do
		if not self.destroyed[self.targetNames[i]] then table.insert(live, self.targetNames[i]) end
	end
	return live
end

function ObjectiveInfiltration:Alarm(why)
	self.level = self.level + 1
	self.alarmed = true
	SetTimerValue(self.clock, self:AlarmLength(self.level))
	StartTimer(self.clock)
	ShowTimer(self.clock)
	self.clockUp = false
	SetTeamPoints(self.garrisonTeam, self.level)
	self:SetPosture(true)
	CustomMode_Say("inf.alarm")
	Log("ALARM " .. self.level .. " (" .. why .. "): " .. self:GarrisonSize(self.level, true) .. " guards")
end

function ObjectiveInfiltration:Calm()
	self.alarmed = false
	ShowTimer(nil)
	self:SetPosture(false)
	CustomMode_Say("inf.calm")
	Log("the garrison stands down (" .. self:GarrisonSize(self.level, false) .. " guards)")
end

function ObjectiveInfiltration:SquadAlive()
	return GetNumTeamMembersAlive(self.squadTeam)
end

function ObjectiveInfiltration:Poll()
	if self.isComplete then return end
	local now = ScriptCB_GetMissionTime()
	local dt = now - (self.lastTime or now)
	self.lastTime = now

	if self.state == "insert" then
		-- bot squadmates: as many alive as the humans plus squadBots
		local humans, i = 0
		for i = 0, GetTeamSize(self.squadTeam) - 1 do
			local c = GetTeamMember(self.squadTeam, i)
			if c and IsCharacterHuman(c) and GetCharacterUnit(c) then humans = humans + 1 end
		end
		SetReinforcementCount(self.squadTeam, humans + self.squadBots)
		if self.windowUp then
			if self:SquadAlive() > 0 then
				self.state = "mission"
				SetObjectTeam(self.insertion, 0)         -- nobody spawns again
				AllowAISpawn(self.squadTeam, false)
				ShowTimer(nil)
				Log("the squad is in")
				CustomMode_Say("inf.in", self.squadTeam)
			else
				SetTimerValue(self.clock, 5)              -- nobody in yet: wait
				StartTimer(self.clock)
				self.windowUp = false
			end
		end
		return
	end

	-- a squad wipe
	if self:SquadAlive() == 0 then
		self.wiped = self.wiped + dt
		if self.wiped >= self.wipeGrace then
			Log("squad wiped with " .. table.getn(self:LiveTargets()) .. " targets left")
			return self:Complete(self.garrisonTeam)
		end
	else
		self.wiped = 0
	end

	-- targets
	local i
	for i = 1, table.getn(self.targetNames) do
		local name = self.targetNames[i]
		if not self.destroyed[name] and not IsObjectAlive(name) then
			self.destroyed[name] = true
			MapRemoveEntityMarker(name)
			self.destroyedCount = self.destroyedCount + 1
			SetTeamPoints(self.squadTeam, self.destroyedCount)
			Log("target destroyed (" .. self.destroyedCount .. "/" .. table.getn(self.targetNames) .. ")")
			local left = table.getn(self.targetNames) - self.destroyedCount
			if left > 0 then CustomMode_Say("inf.left." .. math.min(left, 20), self.squadTeam) end
			if self.destroyedCount == table.getn(self.targetNames) then
				self.extractOpen = true
				MapAddEntityMarker(self.extraction, "hud_objective_icon_circle", 4.0, self.squadTeam, "YELLOW", true, true, true)
				Log("all targets down: get to " .. self.extraction)
				if self.escapeRides and self.rideClass then
					local where, j = {}
					for j = 0, GetTeamSize(self.squadTeam) - 1 do
						local x, y, z = MemberPosition(GetTeamMember(self.squadTeam, j))
						if x then table.insert(where, { x, y, z }) end
					end
					self:MakeRides(self:EscapePlan(where))
					CustomMode_Say("inf.extract.ride", self.squadTeam)
				else
					CustomMode_Say("inf.extract", self.squadTeam)
				end
			end
			self:Alarm("a target blew")
		end
	end

	-- noise: guards dying fast
	while self.kills[1] and now - self.kills[1] > self.noiseWindow do table.remove(self.kills, 1) end
	if not self.alarmed and table.getn(self.kills) >= self.noiseKills then
		self.kills = {}
		self:Alarm("too many guards down")
	end

	if self.alarmed and self.clockUp then
		self:Calm()
	end

	-- extraction
	if self.extractOpen then
		local px, py, pz = GetWorldPosition(self.extraction)
		local r2, there = self.extractRadius * self.extractRadius, false
		for i = 0, GetTeamSize(self.squadTeam) - 1 do
			local c = GetTeamMember(self.squadTeam, i)
			local unit = c and GetCharacterUnit(c)
			if unit and IsObjectAlive(unit) then
				local x, y, z = MemberPosition(c)
				if x and (x - px) * (x - px) + (z - pz) * (z - pz) <= r2
					and (not self.extractHeight or math.abs(y - py) <= self.extractHeight) then
					there = true
				end
			end
		end
		if there then
			if self.extracting == 0 then CustomMode_Say("inf.extracting", self.squadTeam) end
			self.extracting = self.extracting + dt
			if self.extracting >= self.extractTime then
				Log("extracted")
				return self:Complete(self.squadTeam)
			end
		else
			self.extracting = 0
		end
	end
end

function ObjectiveInfiltration:Start()
	self.authority = CustomMode_IsAuthority()
	self.isComplete = false
	self.teamATT, self.teamDEF = self.squadTeam, self.garrisonTeam
	SetFlagGameplayType("none")
	ShowTeamPoints(self.squadTeam, true)
	ShowTeamPoints(self.garrisonTeam, true)

	local names = self:AllPosts()
	local posts, i = {}
	for i = 1, table.getn(names) do
		local x, y, z = GetWorldPosition(names[i])
		table.insert(posts, { name = names[i], x = x, y = y, z = z, team = GetObjectTeam(names[i]) })
	end
	assert(table.getn(posts) >= 2, "infiltration needs at least two command posts")
	self:Layout(posts)
	Log("insertion " .. self.insertion .. ", extraction " .. self.extraction .. ", " ..
		table.getn(self.targetSpots) .. " targets")

	if not self.authority then return end

	ForceHumansOntoTeam1()
	self.level, self.alarmed, self.wiped, self.extracting = 0, false, 0, 0
	self.destroyed, self.destroyedCount, self.kills = {}, 0, {}
	self.state = "insert"
	SetTeamPoints(self.squadTeam, 0)
	SetTeamPoints(self.garrisonTeam, 0)

	for i = 1, table.getn(names) do
		SetProperty(names[i], "CaptureRegion", "")
		AICanCaptureCP(names[i], self.squadTeam, false)
		AICanCaptureCP(names[i], self.garrisonTeam, false)
		SetObjectTeam(names[i], self.garrisonTeam)
	end
	for i = 1, table.getn(self.idlePosts or {}) do SetObjectTeam(self.idlePosts[i], 0) end
	SetObjectTeam(self.insertion, self.squadTeam)
	if self.extraction ~= self.insertion then SetObjectTeam(self.extraction, 0) end

	-- the targets: the garrison's own side's vehicles, told by its hero class's prefix
	local class = self.targetClass
	if not class and self.targetClasses then
		local hero = (gCustomModeHeroes or {})[self.garrisonTeam]
		class = hero and self.targetClasses[string.sub(string.lower(hero), 1, 3)]
		if not class then
			local side, c
			for side, c in pairs(self.targetClasses) do class = class or c end
		end
	end
	self.targetNames = {}
	for i = 1, table.getn(self.targetSpots) do
		local p = self.targetSpots[i]
		local name = "infil_target_" .. i
		local ptr = CreateEntity(class, CreateMatrix(0, 0, 1, 0, p[1], p[2], p[3]), name)
		if ptr then
			SetObjectTeam(name, self.garrisonTeam)
			table.insert(self.targetNames, name)
			MapAddEntityMarker(name, "hud_objective_icon_circle", 3.0, self.squadTeam, "YELLOW", true, false, false)
		else
			Log("could not create target " .. i .. " (" .. tostring(class) .. ")")
		end
	end
	assert(table.getn(self.targetNames) > 0, "infiltration: no targets could be created")
	if self.rides and self.rideClass then self:MakeRides(self.rides) end
	OnCharacterEnterVehicle(function(character, vehicle)
		local name = GetEntityName(vehicle)
		if name and string.sub(name, 1, 13) == "infil_target_" then ExitVehicle(character) end
	end)
	OnCharacterDeath(function(character, killer)
		if GetCharacterTeam(character) == self.garrisonTeam then
			table.insert(self.kills, ScriptCB_GetMissionTime())
		end
	end)

	self.clock = CreateTimer("infilClock")
	OnTimerElapse(function(t)
		if self.state == "insert" then self.windowUp = true else self.clockUp = true end
	end, self.clock)
	SetTimerValue(self.clock, self.spawnWindow)
	StartTimer(self.clock)
	ShowTimer(self.clock)
	self:SetPosture(false)
	CustomMode_Say(self.rides and self.rideClass and "inf.insert.ride" or "inf.insert", self.squadTeam)

	local poll = CreateTimer("infilPoll")
	SetTimerValue(poll, self.pollInterval)
	StartTimer(poll)
	OnTimerElapse(function(t) self:Poll() SetTimerValue(t, self.pollInterval) StartTimer(t) end, poll)
	self.pollTimer = poll
end

function ObjectiveInfiltration:Complete(winningTeam)
	if self.pollTimer then StopTimer(self.pollTimer) end
	if self.clock then StopTimer(self.clock) ShowTimer(nil) end
	Objective.Complete(self, winningTeam)
end
