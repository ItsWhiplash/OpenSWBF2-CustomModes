--
-- OpenSWBF2 Rush game mode.
--
-- The map's command posts are split into stages (by default 3, 3 and 2 posts). The attackers
-- must capture every post in the current stage to open the next one, and win by taking the
-- last stage. Posts in later stages are locked, and so are posts the attackers have taken, so
-- the defenders can't win them back. The attackers have a limited number of lives (tickets) and
-- earn more for every post they take; the defenders have unlimited lives. When the attackers run
-- out, the defenders win.
--
-- Locking a post removes its capture region; unlocking it gives it a round one (captureRadius)
-- around the post. Stage 1's posts are never locked, so they keep the map's own regions.
--
-- Every machine works out the stage from who owns the posts, and locks them the same way, so a
-- client's HUD never shows a locked post being captured. Tickets, bots, markers and the result
-- are the host's (in single player, your own game's).
--

ScriptCB_DoFile("Objective")

ObjectiveRush = Objective:New
{
	-- stages: { { "cp2", "cp3", "cp4" }, { "cp5", "cp6", "cp7" }, { "cp8", "cp9" } }. Left out,
	-- they are worked out from where the posts are (see AutoLayout)
	stages = nil,
	stageSizes = { 3, 3, 2 },     -- for the automatic layout; shrunk to fit the map's posts
	attackerBase = nil,           -- posts the attackers spawn at, locked (default: worked out)
	commandPosts = nil,           -- extra post names (the conquest ones are found)

	-- lives
	attackerTickets = 100,
	ticketsPerCapture = 20,       -- added for each post the attackers take
	stageClearTickets = 0,        -- added when a stage falls

	-- posts
	captureRadius = 10,           -- metres, for posts unlocked after stage 1
	lockCaptured = true,          -- posts the attackers take can't be taken back

	-- the clock (0: none; the attackers' tickets are the limit)
	timeLimit = 0,
	stageBonusTime = 0,           -- seconds added when a stage falls

	-- AI (bots)
	aiObjectiveWeight = 100,      -- how strongly bots go for the open posts, both teams
	aiFightWeight = 25,           -- how strongly they roam and fight instead

	pollInterval = 0.25,
}

local function Log(text)
	print("OpenSWBF2 rush: " .. text)
end

--=============================
-- Layout (pure Lua; the tests call these directly)
--=============================

-- posts: list of { name, x, z, team }. Fills self.stages, self.base and self.rear.
function ObjectiveRush:AutoLayout(posts)
	local att = self.teamATT
	local function Dist2(a, b)
		local dx, dz = a.x - b.x, a.z - b.z
		return dx * dx + dz * dz
	end
	local function Centroid(list)
		local c, i = { x = 0, z = 0 }
		for i = 1, table.getn(list) do
			c.x = c.x + list[i].x / table.getn(list)
			c.z = c.z + list[i].z / table.getn(list)
		end
		return c
	end

	local byName, i = {}
	for i = 1, table.getn(posts) do byName[posts[i].name] = posts[i] end

	-- the attackers' base: given, or the attackers' post farthest from the defenders' side
	local base = {}
	if self.attackerBase then
		for i = 1, table.getn(self.attackerBase) do
			if byName[self.attackerBase[i]] then table.insert(base, byName[self.attackerBase[i]]) end
		end
	end
	if table.getn(base) == 0 then
		local theirs, ours = {}, {}
		for i = 1, table.getn(posts) do
			if posts[i].team == att then table.insert(ours, posts[i]) else table.insert(theirs, posts[i]) end
		end
		if table.getn(theirs) == 0 then theirs = posts end
		if table.getn(ours) == 0 then ours = posts end
		local away = Centroid(theirs)
		local best = ours[1]
		for i = 2, table.getn(ours) do
			if Dist2(ours[i], away) > Dist2(best, away) then best = ours[i] end
		end
		base = { best }
	end
	local isBase = {}
	for i = 1, table.getn(base) do isBase[base[i].name] = 1 end

	-- the rest, nearest the base first
	local rest = {}
	for i = 1, table.getn(posts) do
		if not isBase[posts[i].name] then table.insert(rest, posts[i]) end
	end
	local home = Centroid(base)
	table.sort(rest, function(a, b)
		local da, db = Dist2(a, home), Dist2(b, home)
		if da == db then return a.name < b.name end
		return da < db
	end)

	local sizes = self:FitStageSizes(table.getn(rest))
	self.stages, self.rear = {}, {}
	local n = 1
	local s, k
	for s = 1, table.getn(sizes) do
		local stage = {}
		for k = 1, sizes[s] do
			table.insert(stage, rest[n].name)
			n = n + 1
		end
		table.insert(self.stages, stage)
	end
	while rest[n] do
		table.insert(self.rear, rest[n].name)
		n = n + 1
	end
	self.base = {}
	for i = 1, table.getn(base) do table.insert(self.base, base[i].name) end
end

-- stageSizes shrunk to fit count posts: the biggest (latest on a tie) loses one at a time, and a
-- stage left empty goes
function ObjectiveRush:FitStageSizes(count)
	local sizes, i = {}
	for i = 1, table.getn(self.stageSizes) do sizes[i] = self.stageSizes[i] end
	local function Sum()
		local t, j = 0
		for j = 1, table.getn(sizes) do t = t + sizes[j] end
		return t
	end
	while Sum() > count do
		local big = 1
		for i = 2, table.getn(sizes) do
			if sizes[i] >= sizes[big] then big = i end
		end
		sizes[big] = sizes[big] - 1
		if sizes[big] == 0 then table.remove(sizes, big) end
	end
	return sizes
end

-- From who owns the posts: the current stage (table.getn(stages) + 1 when all are taken), and
-- for each stage post whether it is locked
function ObjectiveRush:Evaluate(owner)
	local current = table.getn(self.stages) + 1
	local s, i
	for s = 1, table.getn(self.stages) do
		for i = 1, table.getn(self.stages[s]) do
			if owner[self.stages[s][i]] ~= self.teamATT then
				current = s
				break
			end
		end
		if current == s then break end
	end
	local locked = {}
	for s = 1, table.getn(self.stages) do
		for i = 1, table.getn(self.stages[s]) do
			local name = self.stages[s][i]
			locked[name] = (s ~= current) or (self.lockCaptured and owner[name] == self.teamATT)
		end
	end
	for i = 1, table.getn(self.base) do locked[self.base[i]] = true end
	for i = 1, table.getn(self.rear) do locked[self.rear[i]] = true end
	return current, locked
end

--=============================
-- Engine side
--=============================

function ObjectiveRush:AllPosts()
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

function ObjectiveRush:SetLocked(name, lock)
	if lock then
		SetProperty(name, "CaptureRegion", "")
	elseif self.locked[name] then
		-- a locked post has no capture region; Radius gives it a new one around the post
		SetProperty(name, "Radius", self.captureRadius)
	end
	AICanCaptureCP(name, self.teamATT, not lock)
	AICanCaptureCP(name, self.teamDEF, not lock)
	self.locked[name] = lock
end

function ObjectiveRush:Owners()
	local owner, i = {}
	for i = 1, table.getn(self.posts) do
		owner[self.posts[i]] = GetObjectTeam(self.posts[i])
	end
	return owner
end

function ObjectiveRush:OpenPosts()
	local open, i = {}
	local stage = self.stages[self.current]
	if not stage then return open end
	for i = 1, table.getn(stage) do
		if not self.locked[stage[i]] and GetObjectTeam(stage[i]) ~= self.teamATT then
			table.insert(open, stage[i])
		end
	end
	return open
end

-- bots: both teams go for the open posts; markers show them
function ObjectiveRush:RefreshGoals()
	local i
	for i = 1, table.getn(self.AIGoals or {}) do
		DeleteAIGoal(self.AIGoals[i])
	end
	self.AIGoals = {}
	for i = 1, table.getn(self.markers or {}) do
		MapRemoveEntityMarker(self.markers[i])
	end
	self.markers = {}

	local open = self:OpenPosts()
	local w = self.aiObjectiveWeight * self.AIGoalWeight / math.max(1, table.getn(open))
	for i = 1, table.getn(open) do
		if w > 0 then
			table.insert(self.AIGoals, AddAIGoal(self.teamATT, "Defend", w, open[i]))
			table.insert(self.AIGoals, AddAIGoal(self.teamDEF, "Defend", w, open[i]))
		end
		MapAddEntityMarker(open[i], "hud_objective_icon_circle", 3.0, self.teamATT, "YELLOW", true, false, true)
		MapAddEntityMarker(open[i], "hud_objective_icon_circle", 3.0, self.teamDEF, "YELLOW", true, false, true)
		table.insert(self.markers, open[i])
	end
	if self.aiFightWeight > 0 then
		table.insert(self.AIGoals, AddAIGoal(self.teamATT, "Deathmatch", self.aiFightWeight * self.AIGoalWeight))
		table.insert(self.AIGoals, AddAIGoal(self.teamDEF, "Deathmatch", self.aiFightWeight * self.AIGoalWeight))
	end
	self.openKey = table.concat(open, ",")
end

function ObjectiveRush:Poll()
	if self.isComplete then
		return
	end
	local owner = self:Owners()
	local current, locked = self:Evaluate(owner)
	local name, lock
	for name, lock in pairs(locked) do
		if lock ~= self.locked[name] and (lock or self.locked[name] ~= nil) then
			self:SetLocked(name, lock)
		end
	end

	if not self.authority then
		self.current = current
		return
	end

	-- lives for every post taken (once each)
	local captured, s, i = 0
	for s = 1, table.getn(self.stages) do
		for i = 1, table.getn(self.stages[s]) do
			local post = self.stages[s][i]
			if owner[post] == self.teamATT then
				captured = captured + 1
				if not self.rewarded[post] then
					self.rewarded[post] = true
					AddReinforcements(self.teamATT, self.ticketsPerCapture)
					Log("attackers took " .. post .. " (+" .. self.ticketsPerCapture .. " lives)")
					CustomMode_Say("rush.taken.att", self.teamATT)
					CustomMode_Say("rush.taken.def", self.teamDEF)
				end
			end
		end
	end
	SetTeamPoints(self.teamATT, captured)
	SetTeamPoints(self.teamDEF, self.totalPosts - captured)

	if current > self.current then
		local fallen
		for fallen = self.current, current - 1 do
			Log("stage " .. fallen .. " fell")
			if fallen < table.getn(self.stages) and fallen <= 9 then
				CustomMode_Say("rush.stage." .. fallen .. ".att", self.teamATT)
				CustomMode_Say("rush.stage." .. fallen .. ".def", self.teamDEF)
			end
			if self.stageClearTickets > 0 then
				AddReinforcements(self.teamATT, self.stageClearTickets)
			end
			if self.clock and self.stageBonusTime > 0 then
				SetTimerValue(self.clock, GetTimerValue(self.clock) + self.stageBonusTime)
			end
		end
		self.current = current
		if current == table.getn(self.stages) and current > 1 then
			CustomMode_Say("rush.final.att", self.teamATT)
			CustomMode_Say("rush.final.def", self.teamDEF)
		end
	end

	if current > table.getn(self.stages) then
		Log("every stage taken")
		self:Complete(self.teamATT)
		return
	end

	local open = table.concat(self:OpenPosts(), ",")
	if open ~= self.openKey then
		self:RefreshGoals()
	end
end

function ObjectiveRush:Start()
	self.timeLimitWinningTeam = self.teamDEF
	local timeLimit = self.timeLimit
	self.timeLimit = 0
	self.authority = CustomMode_IsAuthority()

	if ScriptCB_GetCONNumBots and ScriptCB_SetNumBots then
		ScriptCB_SetNumBots(ScriptCB_GetCONNumBots())
	end

	-- the base Objective takes a life per death and ends the match when a team has none left
	Objective.Start(self)
	SetReinforcementCount(self.teamATT, self.attackerTickets)
	SetReinforcementCount(self.teamDEF, -1)
	ShowTeamPoints(self.teamATT, true)
	ShowTeamPoints(self.teamDEF, true)

	self.posts = self:AllPosts()
	if self.stages then
		self.base, self.rear = self.attackerBase or {}, {}
	else
		local posts, i = {}
		for i = 1, table.getn(self.posts) do
			local x, y, z = GetWorldPosition(self.posts[i])
			table.insert(posts, { name = self.posts[i], x = x, z = z, team = GetObjectTeam(self.posts[i]) })
		end
		assert(table.getn(posts) >= 2, "rush needs at least two command posts")
		self:AutoLayout(posts)
	end
	self.totalPosts = 0
	local s
	for s = 1, table.getn(self.stages) do
		self.totalPosts = self.totalPosts + table.getn(self.stages[s])
		Log("stage " .. s .. ": " .. table.concat(self.stages[s], ", "))
	end
	Log("attackers (team " .. self.teamATT .. ") start at " .. table.concat(self.base, ", ") ..
		(table.getn(self.rear) > 0 and ("; defenders' rear: " .. table.concat(self.rear, ", ")) or ""))

	self.locked = {}
	self.rewarded = {}
	self.current = 1

	if self.authority then
		local i
		for i = 1, table.getn(self.base) do SetObjectTeam(self.base[i], self.teamATT) end
		for i = 1, table.getn(self.rear) do SetObjectTeam(self.rear[i], self.teamDEF) end
		for s = 1, table.getn(self.stages) do
			for i = 1, table.getn(self.stages[s]) do SetObjectTeam(self.stages[s][i], self.teamDEF) end
		end
		if timeLimit and timeLimit > 0 then
			self.clock = CreateTimer("rushClock")
			SetTimerValue(self.clock, timeLimit)
			StartTimer(self.clock)
			ShowTimer(self.clock)
			OnTimerElapse(function(t)
				if not self.isComplete then
					Log("time is up")
					self:Complete(self.teamDEF)
				end
			end, self.clock)
		end
	end

	CustomMode_Say("rush.start.att", self.teamATT)
	CustomMode_Say("rush.start.def", self.teamDEF)
	self:Poll()

	local timer = CreateTimer("rushPoll")
	SetTimerValue(timer, self.pollInterval)
	StartTimer(timer)
	OnTimerElapse(function(t)
		self:Poll()
		SetTimerValue(t, self.pollInterval)
		StartTimer(t)
	end, timer)
	self.pollTimer = timer
end

function ObjectiveRush:Complete(winningTeam)
	if self.pollTimer then
		StopTimer(self.pollTimer)
	end
	if self.clock then
		StopTimer(self.clock)
		ShowTimer(nil)
	end
	Objective.Complete(self, winningTeam)
end
