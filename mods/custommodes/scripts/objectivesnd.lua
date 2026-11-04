--
-- OpenSWBF2 Search & Destroy game mode.
--
-- Rounds, one life each. Two command posts are bomb sites. An attacker who stands at a site
-- for plantTime seconds plants the bomb there; it goes off after bombTime unless a defender
-- stands on it for defuseTime. Attackers win a round by the bomb going off or by killing every
-- defender; defenders win by defusing, by killing every attacker before a plant, or by running
-- out the clock. First to roundsToWin; the sides swap roles after `halftime` rounds.
--
-- How the engine is used (see README.md):
--   * a round starts with a spawn window (setupTime, longer than the 15 s the engine spawns
--     multiplayer players in): each team owns its spawn post. Then the spawn posts go neutral,
--     so nobody spawns again until the next round (players can only spawn at a post their team
--     owns);
--   * a round ends by killing everyone still alive, so the next starts fresh;
--   * a detonation destroys the site's command post, for the blast (destroySites); it comes
--     back next round.
--

ScriptCB_DoFile("Objective")

ObjectiveSnD = Objective:New
{
	-- posts: worked out unless given
	attackerSpawn = nil,          -- where the attacking side spawns (the sides swap at halftime,
	defenderSpawn = nil,          -- the spawns stay with the role)
	sites = nil,                  -- the two bomb sites (one on a three-post map)
	commandPosts = nil,

	-- the match
	roundsToWin = 4,
	halftime = 3,                 -- rounds before the sides swap roles (0: never)

	-- a round
	setupTime = 20,               -- seconds to spawn; no planting yet
	roundTime = 150,              -- seconds to plant, after setup
	plantTime = 5,
	bombTime = 40,
	defuseTime = 7,
	siteRadius = 6,
	roundEndTime = 6,             -- seconds between a round's end and the next round
	destroySites = true,

	-- AI (bots)
	aiObjectiveWeight = 100,
	aiFightWeight = 25,

	pollInterval = 0.25,
}

local function Log(text)
	print("OpenSWBF2 s&d: " .. text)
end

--=============================
-- Layout (pure Lua)
--=============================

-- posts: list of { name, x, z, team }. Fills attackerSpawn, defenderSpawn, sites.
function ObjectiveSnD:Layout(posts, attackers)
	local function Dist2(a, b)
		local dx, dz = a.x - b.x, a.z - b.z
		return dx * dx + dz * dz
	end
	local byName, i, j = {}
	for i = 1, table.getn(posts) do byName[posts[i].name] = posts[i] end

	if not (self.attackerSpawn and self.defenderSpawn) then
		-- the two posts farthest apart; the attackers get the one their side owns, if either
		local a, b = posts[1], posts[2]
		for i = 1, table.getn(posts) do
			for j = i + 1, table.getn(posts) do
				if Dist2(posts[i], posts[j]) > Dist2(a, b) then a, b = posts[i], posts[j] end
			end
		end
		if b.team == attackers and a.team ~= attackers then a, b = b, a end
		self.attackerSpawn = self.attackerSpawn or a.name
		self.defenderSpawn = self.defenderSpawn or b.name
	end
	if not self.sites then
		local home = byName[self.defenderSpawn]
		local rest = {}
		for i = 1, table.getn(posts) do
			if posts[i].name ~= self.attackerSpawn and posts[i].name ~= self.defenderSpawn then
				table.insert(rest, posts[i])
			end
		end
		table.sort(rest, function(p, q)
			local dp, dq = Dist2(p, home), Dist2(q, home)
			if dp == dq then return p.name < q.name end
			return dp < dq
		end)
		self.sites = {}
		for i = 1, math.min(2, table.getn(rest)) do table.insert(self.sites, rest[i].name) end
		if table.getn(self.sites) == 0 then self.sites = { self.defenderSpawn } end
	end
end

--=============================
-- Engine side
--=============================

function ObjectiveSnD:AllPosts()
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

-- living members of a team near a post
function ObjectiveSnD:CountNear(team, post)
	local px, py, pz = GetWorldPosition(post)
	local r2 = self.siteRadius * self.siteRadius
	local n, i = 0
	for i = 0, GetTeamSize(team) - 1 do
		local c = GetTeamMember(team, i)
		local unit = c and GetCharacterUnit(c)
		if unit and IsObjectAlive(unit) then
			local x, y, z = GetWorldPosition(unit)
			if x and (x - px) * (x - px) + (z - pz) * (z - pz) <= r2 then n = n + 1 end
		end
	end
	return n
end

function ObjectiveSnD:Clock(seconds)
	SetTimerValue(self.clock, seconds)
	StartTimer(self.clock)
	ShowTimer(self.clock)
	self.clockUp = false
end

function ObjectiveSnD:Markers(pulseSite)
	local i, t
	for i = 1, table.getn(self.sites) do
		MapRemoveEntityMarker(self.sites[i])
		if not pulseSite or pulseSite == self.sites[i] then
			for _, t in ipairs({ 1, 2 }) do
				MapAddEntityMarker(self.sites[i], "hud_objective_icon_circle", 3.0, t, "YELLOW", true,
					pulseSite ~= nil, pulseSite ~= nil)
			end
		end
	end
end

function ObjectiveSnD:Goals(targets)
	local i, j, t
	for i = 1, table.getn(self.AIGoals or {}) do DeleteAIGoal(self.AIGoals[i]) end
	self.AIGoals = {}
	for _, t in ipairs({ self.att, self.def }) do
		for j = 1, table.getn(targets) do
			table.insert(self.AIGoals, AddAIGoal(t, "Defend", self.aiObjectiveWeight / table.getn(targets), targets[j]))
		end
		if self.aiFightWeight > 0 then
			table.insert(self.AIGoals, AddAIGoal(t, "Deathmatch", self.aiFightWeight))
		end
	end
end

function ObjectiveSnD:StartRound()
	self.round = self.round + 1
	if self.halftime > 0 and self.round == self.halftime + 1 then
		self.att, self.def = self.def, self.att
		Log("halftime: team " .. self.att .. " attacks now")
		CustomMode_Say("snd.halftime")
	end
	self.state = "setup"
	self.planted, self.progress = nil, 0
	local i
	for i = 1, table.getn(self.sites) do
		if not IsObjectAlive(self.sites[i]) then RespawnObject(self.sites[i]) end
		SetObjectTeam(self.sites[i], 0)
	end
	SetObjectTeam(self.attackerSpawn, self.att)
	SetObjectTeam(self.defenderSpawn, self.def)
	AllowAISpawn(1, true)
	AllowAISpawn(2, true)
	self:Markers(nil)
	self:Goals(self.sites)
	self:Clock(self.setupTime)
	Log("round " .. self.round .. ": team " .. self.att .. " attacks " .. table.concat(self.sites, " and "))
	CustomMode_Say("snd.round.att", self.att)
	CustomMode_Say("snd.round.def", self.def)
end

function ObjectiveSnD:GoLive()
	self.state = "live"
	-- nobody spawns again this round
	SetObjectTeam(self.attackerSpawn, 0)
	SetObjectTeam(self.defenderSpawn, 0)
	AllowAISpawn(1, false)
	AllowAISpawn(2, false)
	self:Clock(self.roundTime)
	CustomMode_Say("snd.live")
end

function ObjectiveSnD:EndRound(winner, why)
	self.state = "over"
	self.wins[winner] = self.wins[winner] + 1
	SetTeamPoints(winner, self.wins[winner])
	Log("round " .. self.round .. " to team " .. winner .. " (" .. why .. "), " .. self.wins[1] .. "-" .. self.wins[2])
	StopTimer(self.clock)
	ShowTimer(nil)
	CustomMode_Say("snd.won", winner)
	CustomMode_Say("snd.lost", 3 - winner)
	if self.wins[winner] >= self.roundsToWin then
		return self:Complete(winner)
	end
	if self.wins[1] == self.roundsToWin - 1 or self.wins[2] == self.roundsToWin - 1 then
		CustomMode_Say("snd.matchpoint")
	end
	self.overFor = 0
end

-- kills everyone still standing, so the next round starts fresh
function ObjectiveSnD:ClearField()
	local t, i
	for _, t in ipairs({ 1, 2 }) do
		for i = 0, GetTeamSize(t) - 1 do
			local c = GetTeamMember(t, i)
			local unit = c and GetCharacterUnit(c)
			if unit and IsObjectAlive(unit) then KillObject(unit) end
		end
	end
end

function ObjectiveSnD:Poll()
	if self.isComplete then return end
	local now = ScriptCB_GetMissionTime()
	local dt = now - (self.lastTime or now)
	self.lastTime = now

	if self.state == "over" then
		self.overFor = self.overFor + dt
		if self.overFor >= self.roundEndTime then
			self:ClearField()
			self:StartRound()
		end
		return
	end

	if self.state == "setup" then
		if self.clockUp then
			if GetNumTeamMembersAlive(self.att) > 0 and GetNumTeamMembersAlive(self.def) > 0 then
				self:GoLive()
			else
				self:Clock(5) -- a side has nobody in yet (a player still choosing a class): wait
			end
		end
		return
	end

	local attAlive = GetNumTeamMembersAlive(self.att)
	local defAlive = GetNumTeamMembersAlive(self.def)

	if not self.planted then
		if attAlive == 0 then return self:EndRound(self.def, "attackers eliminated") end
		if defAlive == 0 then return self:EndRound(self.att, "defenders eliminated") end
		if self.clockUp then return self:EndRound(self.def, "time") end
		-- planting: an attacker on a site, uninterrupted
		local site, i
		for i = 1, table.getn(self.sites) do
			if self:CountNear(self.att, self.sites[i]) > 0 then site = self.sites[i] end
		end
		if site and site == self.planting then
			self.progress = self.progress + dt
		else
			self.planting, self.progress = site, 0
		end
		if site and self.progress >= self.plantTime then
			self.planted, self.progress = site, 0
			self:Clock(self.bombTime)
			self:Markers(site)
			self:Goals({ site })
			Log("bomb planted at " .. site)
			CustomMode_Say("snd.planted." .. (site == self.sites[2] and "b" or "a"))
		end
		return
	end

	-- the bomb is armed: the attackers win if it goes off or no defender is left to defuse
	if self.clockUp then
		if self.destroySites then KillObject(self.planted) end
		CustomMode_Say("snd.detonated")
		return self:EndRound(self.att, "the bomb went off")
	end
	if defAlive == 0 then return self:EndRound(self.att, "defenders eliminated") end
	if self:CountNear(self.def, self.planted) > 0 then
		self.progress = self.progress + dt
		if self.progress >= self.defuseTime then
			CustomMode_Say("snd.defused")
			return self:EndRound(self.def, "defused")
		end
	else
		self.progress = 0
	end
end

function ObjectiveSnD:Start()
	self.authority = CustomMode_IsAuthority()
	self.isComplete = false
	self.att, self.def = self.teamATT, self.teamDEF
	self.wins = { [1] = 0, [2] = 0 }
	self.round = 0
	SetFlagGameplayType("none")
	ShowTeamPoints(1, true)
	ShowTeamPoints(2, true)
	if ScriptCB_GetCONNumBots and ScriptCB_SetNumBots then
		ScriptCB_SetNumBots(ScriptCB_GetCONNumBots())
	end

	local names = self:AllPosts()
	local posts, i = {}
	for i = 1, table.getn(names) do
		local x, y, z = GetWorldPosition(names[i])
		table.insert(posts, { name = names[i], x = x, z = z, team = GetObjectTeam(names[i]) })
	end
	assert(table.getn(posts) >= 2, "search & destroy needs at least two command posts")
	self:Layout(posts, self.att)
	Log("attackers spawn at " .. self.attackerSpawn .. ", defenders at " .. self.defenderSpawn ..
		"; sites " .. table.concat(self.sites, ", "))

	if not self.authority then return end

	SetReinforcementCount(1, -1)
	SetReinforcementCount(2, -1)
	for i = 1, table.getn(names) do
		SetProperty(names[i], "CaptureRegion", "")
		AICanCaptureCP(names[i], 1, false)
		AICanCaptureCP(names[i], 2, false)
		SetObjectTeam(names[i], 0)
	end
	SetTeamPoints(1, 0)
	SetTeamPoints(2, 0)

	self.clock = CreateTimer("sndClock")
	OnTimerElapse(function(t) self.clockUp = true end, self.clock)
	self:StartRound()

	local poll = CreateTimer("sndPoll")
	SetTimerValue(poll, self.pollInterval)
	StartTimer(poll)
	OnTimerElapse(function(t) self:Poll() SetTimerValue(t, self.pollInterval) StartTimer(t) end, poll)
	self.pollTimer = poll
end

function ObjectiveSnD:Complete(winningTeam)
	if self.pollTimer then StopTimer(self.pollTimer) end
	if self.clock then StopTimer(self.clock) ShowTimer(nil) end
	Objective.Complete(self, winningTeam)
end
