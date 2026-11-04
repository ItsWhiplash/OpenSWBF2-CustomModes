--
-- OpenSWBF2 Payload game mode.
--
-- A vehicle (the "payload") follows a fixed track. Attackers move it by standing near it: the
-- more attackers in range, the faster it goes, up to a cap. Defenders in range stop it. Left
-- alone, it rolls back to the last checkpoint. The attackers win when it reaches the end of the
-- track. The defenders win when time runs out (overtime lasts while attackers stay on it).
--
-- Written for the engine's Lua 5.0 (no '#', no '%'; table.getn and math.mod instead), with
-- lua_Number = float. The game logic runs only where the match is hosted: in single player
-- (bot matches included) that is your own game, and in multiplayer it is the server. Clients
-- see the payload move because vehicles are networked.
--

ScriptCB_DoFile("Objective")

ObjectivePayload = Objective:New
{
	-- the track: a list of { x, y, z } points, at least two (see the recorder below)
	track = nil,
	-- checkpoints along the track: { at = 0.33 } (a fraction of the length) or { point = 7 }
	-- (a track point). Optional fields: giveCPs = { "cp3" } (command posts handed to the
	-- attackers, so their spawns move up), takeCPs = { "cp2" } (handed to the defenders),
	-- bonusTime (seconds added to the clock, default checkpointBonusTime).
	checkpoints = nil,

	-- the vehicle
	payloadClass = nil,           -- class to spawn, e.g. "imp_hover_fightertank"
	payloadName = "payload_cart", -- entity name it gets (or the name of one already in the map)
	heightOffset = 0.0,           -- metres added to the track height
	yawOffset = 0.0,              -- degrees, if the model faces sideways or backwards
	payloadMaxHealth = 100000,    -- kept topped up every tick, so it can't be destroyed

	-- pushing
	pushRadius = 8.0,             -- metres from the payload's centre (horizontal)
	pushHeight = 5.0,             -- metres above or below it that still count
	baseSpeed = 1.5,              -- metres per second with one attacker
	speedPerPusher = 0.5,         -- added per extra attacker
	maxSpeed = 3.5,               -- the cap
	maxPushers = 5,               -- attackers beyond this add nothing
	contestBlocks = true,         -- any defender in range stops it
	countVehicles = false,        -- whether soldiers in vehicles count

	-- rolling back
	rollbackDelay = 30.0,         -- seconds without attackers before it rolls back (< 0: never)
	rollbackSpeed = 0.75,         -- metres per second

	-- the clock
	timeLimit = 600,              -- seconds the attackers have (0: no limit)
	checkpointBonusTime = 120,    -- seconds a checkpoint adds
	overtimeGrace = 2.0,          -- seconds without attackers on it before overtime ends

	-- the map
	disableCapture = true,        -- command posts can't be captured (spawns follow checkpoints)
	commandPosts = nil,           -- extra command post names (the conquest ones are found)
	initialCPs = nil,             -- { cp1 = "att", cp4 = "def" } at the start
	unlimitedReinforcements = true,

	-- AI (bots)
	aiPayloadWeight = 100,        -- how strongly bots go for the payload, both teams
	aiFightWeight = 25,           -- how strongly they roam and fight instead

	-- recording: no track (or record = true) walks you through laying one down instead
	record = false,
	recordSpacing = 8.0,          -- metres between recorded points
	recordWithBots = false,

	tickInterval = 0.1,
	textATT = nil,
	textDEF = nil,
}

PAYLOAD_LOG = "OpenSWBF2 payload: "

local function Log(text)
	print(PAYLOAD_LOG .. text)
end

local function TeamFrom(value, att, def)
	if value == "att" or value == "ATT" then return att end
	if value == "def" or value == "DEF" then return def end
	return value
end

--=============================
-- Track geometry (pure Lua, no engine calls; the tests use these directly)
--=============================

-- Fills self.dist[i] (distance along the track to point i) and self.length
function ObjectivePayload:BuildTrack()
	local track = self.track
	local n = table.getn(track)
	assert(n >= 2, "payload track needs at least two points")
	self.dist = { 0 }
	local total = 0
	local i
	for i = 2, n do
		local a, b = track[i - 1], track[i]
		local dx, dy, dz = b[1] - a[1], b[2] - a[2], b[3] - a[3]
		total = total + math.sqrt(dx * dx + dy * dy + dz * dz)
		self.dist[i] = total
	end
	self.length = total
	assert(total > 0, "payload track has no length")
end

-- Point on the track at distance s: x, y, z
function ObjectivePayload:PointAt(s)
	local track, dist = self.track, self.dist
	local n = table.getn(track)
	if s <= 0 then
		return track[1][1], track[1][2], track[1][3]
	end
	if s >= self.length then
		return track[n][1], track[n][2], track[n][3]
	end
	-- the segment the payload is on rarely changes, so start from the last one
	local i = self.segHint or 2
	if i > n or dist[i - 1] > s then
		i = 2
	end
	while i < n and dist[i] < s do
		i = i + 1
	end
	self.segHint = i
	local a, b = track[i - 1], track[i]
	local span = dist[i] - dist[i - 1]
	local t = 0
	if span > 0 then
		t = (s - dist[i - 1]) / span
	end
	return a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, a[3] + (b[3] - a[3]) * t
end

-- Heading at distance s, in radians about the up axis (0 faces +z), looking a little ahead
function ObjectivePayload:YawAt(s)
	local ahead = 2.0
	local s1, s2 = s, s + ahead
	if s2 > self.length then
		s1, s2 = self.length - ahead, self.length
	end
	local x1, y1, z1 = self:PointAt(s1)
	local x2, y2, z2 = self:PointAt(s2)
	return math.atan2(x2 - x1, z2 - z1) + self.yawOffset * 3.14159265 / 180
end

-- Checkpoint distances, sorted, from fractions or point numbers
function ObjectivePayload:BuildCheckpoints()
	self.cps = {}
	local list = self.checkpoints or {}
	local i
	for i = 1, table.getn(list) do
		local cp = list[i]
		local d
		if cp.point then
			assert(self.dist[cp.point], "payload checkpoint point " .. cp.point .. " is not on the track")
			d = self.dist[cp.point]
		else
			d = (cp.at or 0) * self.length
		end
		if d > 0 and d < self.length then
			table.insert(self.cps, { distance = d, def = cp })
		end
	end
	table.sort(self.cps, function(a, b) return a.distance < b.distance end)
	self.nextCP = 1
	self.floor = 0
end

-- Speed for a number of attackers and defenders in range
function ObjectivePayload:SpeedFor(attackers, defenders)
	if attackers <= 0 then
		return 0
	end
	if self.contestBlocks and defenders > 0 then
		return 0
	end
	local n = attackers
	if n > self.maxPushers then
		n = self.maxPushers
	end
	local speed = self.baseSpeed + self.speedPerPusher * (n - 1)
	if speed > self.maxSpeed then
		speed = self.maxSpeed
	end
	return speed
end

-- One step of the rules: moves self.s and returns what happened ("end", or a checkpoint table)
function ObjectivePayload:Step(dt, attackers, defenders)
	local speed = self:SpeedFor(attackers, defenders)
	self.pushers = attackers
	self.contested = attackers > 0 and defenders > 0 and self.contestBlocks
	if attackers > 0 then
		self.idle = 0
	else
		self.idle = (self.idle or 0) + dt
	end

	if speed > 0 then
		self.s = self.s + speed * dt
	elseif attackers <= 0 and self.rollbackDelay >= 0 and self.idle >= self.rollbackDelay and self.s > self.floor then
		self.s = self.s - self.rollbackSpeed * dt
		if self.s < self.floor then
			self.s = self.floor
		end
	end

	local reached = nil
	while self.cps[self.nextCP] and self.s >= self.cps[self.nextCP].distance do
		reached = reached or {}
		table.insert(reached, self.cps[self.nextCP])
		self.floor = self.cps[self.nextCP].distance
		self.nextCP = self.nextCP + 1
	end

	if self.s >= self.length then
		self.s = self.length
		return "end", reached
	end
	return nil, reached
end

-- Overtime and the clock: returns true when the defenders have won on time
function ObjectivePayload:StepClock(dt, timeUp)
	if not timeUp then
		return false
	end
	if not self.overtime then
		if (self.pushers or 0) > 0 then
			self.overtime = true
			self.overtimeIdle = 0
			Log("overtime")
			CustomMode_Say("pay.overtime")
			return false
		end
		return true
	end
	if (self.pushers or 0) > 0 then
		self.overtimeIdle = 0
		return false
	end
	self.overtimeIdle = self.overtimeIdle + dt
	return self.overtimeIdle >= self.overtimeGrace
end

--=============================
-- Engine side
--=============================

-- Counts living attackers and defenders near the payload
function ObjectivePayload:CountNear()
	local px, py, pz = self:PointAt(self.s)
	py = py + self.heightOffset
	local r2 = self.pushRadius * self.pushRadius
	local counts = {}
	local t
	for _, t in ipairs({ self.teamATT, self.teamDEF }) do
		local n = 0
		local i
		for i = 0, GetTeamSize(t) - 1 do
			local c = GetTeamMember(t, i)
			local unit = c and GetCharacterUnit(c)
			if unit and IsObjectAlive(unit) and (self.countVehicles or not GetCharacterVehicle(c)) then
				local x, y, z = GetWorldPosition(unit)
				if x then
					local dx, dz = x - px, z - pz
					local dy = y - py
					if dx * dx + dz * dz <= r2 and dy <= self.pushHeight and dy >= -self.pushHeight then
						n = n + 1
					end
				end
			end
		end
		counts[t] = n
	end
	return counts[self.teamATT], counts[self.teamDEF]
end

function ObjectivePayload:PlacementMatrix()
	local x, y, z = self:PointAt(self.s)
	return CreateMatrix(self:YawAt(self.s), 0, 1, 0, x, y + self.heightOffset, z)
end

function ObjectivePayload:SpawnPayload()
	if GetEntityPtr(self.payloadName) then
		-- one placed in the map, or left over
		SetEntityMatrix(self.payloadName, self:PlacementMatrix())
	else
		assert(self.payloadClass, "payload: set payloadClass, or place an object named " .. self.payloadName)
		local ptr = CreateEntity(self.payloadClass, self:PlacementMatrix(), self.payloadName)
		assert(ptr, "payload: could not create a " .. self.payloadClass ..
			" (is its side loaded and its memory pool big enough?)")
	end
	SetProperty(self.payloadName, "MaxHealth", self.payloadMaxHealth)
	SetProperty(self.payloadName, "CurHealth", self.payloadMaxHealth)
end

function ObjectivePayload:PlacePayload()
	if not IsObjectAlive(self.payloadName) then
		RespawnObject(self.payloadName)
	end
	SetEntityMatrix(self.payloadName, self:PlacementMatrix())
	SetProperty(self.payloadName, "CurHealth", self.payloadMaxHealth)
end

function ObjectivePayload:SetCP(name, team)
	if GetEntityPtr(name) then
		SetObjectTeam(name, team)
	else
		Log("no command post " .. name)
	end
end

function ObjectivePayload:AllCommandPosts()
	local names, seen = {}, {}
	local lists = { self.commandPosts or {}, gCustomModeCPs or {} }
	local i, j
	for i = 1, 2 do
		for j = 1, table.getn(lists[i]) do
			local name = string.lower(lists[i][j])
			if not seen[name] then
				seen[name] = 1
				table.insert(names, name)
			end
		end
	end
	return names
end

function ObjectivePayload:UpdateScore()
	local pct = math.floor(100 * self.s / self.length)
	if pct ~= self.lastPct then
		self.lastPct = pct
		SetTeamPoints(self.teamATT, pct)
		SetTeamPoints(self.teamDEF, table.getn(self.cps) - self.nextCP + 1)
	end
end

function ObjectivePayload:OnCheckpoint(cp)
	local def = cp.def
	Log(string.format("checkpoint at %.0f m", cp.distance))
	CustomMode_Say("pay.checkpoint.att", self.teamATT)
	CustomMode_Say("pay.checkpoint.def", self.teamDEF)
	local i
	for i = 1, table.getn(def.giveCPs or {}) do
		self:SetCP(def.giveCPs[i], self.teamATT)
	end
	for i = 1, table.getn(def.takeCPs or {}) do
		self:SetCP(def.takeCPs[i], self.teamDEF)
	end
	local bonus = def.bonusTime or self.checkpointBonusTime
	if self.clock and bonus > 0 and not self.overtime then
		SetTimerValue(self.clock, GetTimerValue(self.clock) + bonus)
	end
	if def.message then
		ShowMessageText(def.message)
	end
end

function ObjectivePayload:Tick()
	if self.isComplete then
		return
	end
	local now = ScriptCB_GetMissionTime()
	local dt = now - (self.lastTime or now)
	self.lastTime = now
	if dt < 0 then dt = 0 end
	if dt > 0.5 then dt = 0.5 end

	local att, def = self:CountNear()
	local before = self.s
	local result, reached = self:Step(dt, att, def)
	if self.s < before and not self.rolling then
		self.rolling = true
		CustomMode_Say("pay.rollback")
	elseif self.s >= before then
		self.rolling = false
	end
	if reached then
		local i
		for i = 1, table.getn(reached) do
			self:OnCheckpoint(reached[i])
		end
	end
	self:PlacePayload()
	self:UpdateScore()

	if result == "end" then
		Log("delivered")
		self:Complete(self.teamATT)
		return
	end
	if self:StepClock(dt, self.timeUp) then
		Log("time is up")
		self:Complete(self.teamDEF)
	end
end

function ObjectivePayload:StartTicking(fn, interval)
	local timer = CreateTimer("payloadTick")
	SetTimerValue(timer, interval)
	StartTimer(timer)
	OnTimerElapse(
		function(t)
			fn()
			SetTimerValue(t, interval)
			StartTimer(t)
		end,
		timer)
	return timer
end

function ObjectivePayload:Start()
	self.timeLimitWinningTeam = self.teamDEF
	local timeLimit = self.timeLimit
	self.timeLimit = 0 -- the payload keeps its own clock (overtime, checkpoint bonuses)
	local recording = self.record or not self.track or table.getn(self.track) < 2

	if recording then
		Objective.Start(self)
		self:StartRecorder()
		return
	end

	self:BuildTrack()
	self:BuildCheckpoints()
	self.s = 0
	self.idle = 0
	self.showTeamPoints = true

	-- the bot count from the game options (Instant Action or the server's), as conquest does
	if ScriptCB_GetCONNumBots and ScriptCB_SetNumBots then
		ScriptCB_SetNumBots(ScriptCB_GetCONNumBots())
	end

	Objective.Start(self)

	if self.unlimitedReinforcements then
		SetReinforcementCount(self.teamATT, -1)
		SetReinforcementCount(self.teamDEF, -1)
	end

	if not CustomMode_IsAuthority() then
		return
	end

	local cps = self:AllCommandPosts()
	local i
	for i = 1, table.getn(cps) do
		if self.disableCapture and GetEntityPtr(cps[i]) then
			SetProperty(cps[i], "CaptureRegion", "")
		end
	end
	local name, side
	for name, side in pairs(self.initialCPs or {}) do
		self:SetCP(name, TeamFrom(side, self.teamATT, self.teamDEF))
	end

	self:SpawnPayload()
	CustomMode_Say("pay.start.att", self.teamATT)
	CustomMode_Say("pay.start.def", self.teamDEF)
	MapAddEntityMarker(self.payloadName, "hud_objective_icon_circle", 4.0, self.teamATT, "YELLOW", true, false, true)
	MapAddEntityMarker(self.payloadName, "hud_objective_icon_circle", 4.0, self.teamDEF, "YELLOW", true, false, true)

	-- bots: both teams converge on the payload (attackers escort it, defenders hold it), and
	-- some roam and fight
	self.AIGoals = {}
	if self.aiPayloadWeight > 0 then
		table.insert(self.AIGoals, AddAIGoal(self.teamATT, "Defend", self.aiPayloadWeight * self.AIGoalWeight, self.payloadName))
		table.insert(self.AIGoals, AddAIGoal(self.teamDEF, "Defend", self.aiPayloadWeight * self.AIGoalWeight, self.payloadName))
	end
	if self.aiFightWeight > 0 then
		table.insert(self.AIGoals, AddAIGoal(self.teamATT, "Deathmatch", self.aiFightWeight * self.AIGoalWeight))
		table.insert(self.AIGoals, AddAIGoal(self.teamDEF, "Deathmatch", self.aiFightWeight * self.AIGoalWeight))
	end

	-- nobody drives the payload
	OnCharacterEnterVehicle(
		function(character, vehicle)
			if GetEntityName(vehicle) == self.payloadName then
				ExitVehicle(character)
			end
		end)

	if timeLimit and timeLimit > 0 then
		self.clock = CreateTimer("payloadClock")
		SetTimerValue(self.clock, timeLimit)
		StartTimer(self.clock)
		ShowTimer(self.clock)
		OnTimerElapse(function(t) self.timeUp = true end, self.clock)
	end

	self:UpdateScore()
	self.lastTime = ScriptCB_GetMissionTime()
	self.tickTimer = self:StartTicking(function() self:Tick() end, self.tickInterval)
	Log(string.format("track %.0f m, %d checkpoints, attackers are team %d",
		self.length, table.getn(self.cps), self.teamATT))
end

function ObjectivePayload:Complete(winningTeam)
	if self.tickTimer then
		StopTimer(self.tickTimer)
	end
	if self.clock then
		StopTimer(self.clock)
		ShowTimer(nil)
	end
	Objective.Complete(self, winningTeam)
end

--=============================
-- Track recorder: walk the route the payload should take; the log gets the points
--=============================

function ObjectivePayload:StartRecorder()
	if not CustomMode_IsAuthority() then
		return
	end
	SetReinforcementCount(self.teamATT, -1)
	SetReinforcementCount(self.teamDEF, -1)
	if not self.recordWithBots then
		AllowAISpawn(self.teamATT, false)
		AllowAISpawn(self.teamDEF, false)
	end
	CustomMode_Say("pay.recording")
	Log("RECORDING. Walk the payload's route from start to finish; a point is logged every " ..
		self.recordSpacing .. " m. Then quit and run extract_track.py on the log.")
	local cps = self:AllCommandPosts()
	local i
	for i = 1, table.getn(cps) do
		local x, y, z = GetWorldPosition(cps[i])
		if x then
			Log(string.format("PAYLOAD_CP %s team=%d at { %.1f, %.1f, %.1f }", cps[i], GetObjectTeam(cps[i]) or 0, x, y, z))
		end
	end
	self.recorded = {}
	self:StartTicking(function() self:RecordTick() end, 0.25)
end

function ObjectivePayload:RecordTick()
	local t, i
	for _, t in ipairs({ 1, 2 }) do
		for i = 0, GetTeamSize(t) - 1 do
			local c = GetTeamMember(t, i)
			if c and IsCharacterHuman(c) then
				local unit = GetCharacterUnit(c)
				if unit and IsObjectAlive(unit) then
					local x, y, z = GetWorldPosition(unit)
					if x then
						self:RecordPoint(x, y, z)
					end
					return
				end
			end
		end
	end
end

function ObjectivePayload:RecordPoint(x, y, z)
	local n = table.getn(self.recorded)
	local last = self.recorded[n]
	if last then
		local dx, dy, dz = x - last[1], y - last[2], z - last[3]
		if dx * dx + dy * dy + dz * dz < self.recordSpacing * self.recordSpacing then
			return false
		end
	end
	table.insert(self.recorded, { x, y, z })
	Log(string.format("PAYLOAD_TRACK %d { %.1f, %.1f, %.1f },", n + 1, x, y, z))
	return true
end
