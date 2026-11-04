--
-- OpenSWBF2 Horde game mode.
--
-- Every human is on the players' team (with their bot allies), holding one command post, the
-- last stand, against endless waves of the other side's army. Each wave is bigger and tougher;
-- every 5th brings the enemy's hero as a boss. Between waves there's a short break: everyone
-- who died comes back, and the team spends the credits its kills earned at the shop pads, the
-- map's other command posts, each offering one item that break. Standing on a pad buys it.
-- The players lose when the horde overruns the last stand (holds it with no defender near) or
-- when every defender is down at once. The score is the waves survived.
--
-- How the engine is used (see README.md):
--   * players can spawn only at a post their team owns, so the last stand is theirs in a break
--     and neutral during a wave: whoever dies in a wave waits for the break;
--   * the horde's reinforcements are the wave: bots spawn while the team has more than are
--     alive, and each death takes one, so the counter is the enemies left;
--   * Galactic Conquest's bonuses are the shop's enhancements (the engine runs one per team at
--     a time). They aren't networked, so the server puts the active one in the players' team's
--     bleed rate, which is sent to everyone and not shown while team points are, and every
--     machine turns it on locally.
--

ScriptCB_DoFile("Objective")

-- Galactic Conquest's bonuses, by the engine's name, with the tech name the game's own text
-- uses (ifs.freeform.purchase.tech.<tech>.enhancement). Their index is how they're sent.
HordeBonuses = {
	{ bonus = "bacta_tanks", tech = "bacta_refinery" },          -- health regenerates
	{ bonus = "energy_boost", tech = "adrenaline" },             -- energy regenerates 3x
	{ bonus = "combat_shielding", tech = "advanced_armor" },     -- +25% health at spawn
	{ bonus = "advanced_blasters", tech = "blaster_amplification" }, -- more damage
	{ bonus = "sensor_array", tech = "surveillance" },           -- enemies on the map
	{ bonus = "leader", tech = "leadership" },                   -- the team's hero comes back
}

ObjectiveHorde = Objective:New
{
	playersTeam = 1,
	hordeTeam = 2,

	-- posts: worked out unless given
	lastStand = nil,              -- the post the players hold
	hordeSpawns = nil,            -- posts the horde spawns at (default: the hordeSpawnCount farthest)
	hordeSpawnCount = 2,
	shopPads = nil,               -- posts that sell things in a break (default: the rest)
	commandPosts = nil,           -- extra post names (the conquest ones are found)

	-- waves
	firstWave = 10,               -- enemies in wave 1
	perWave = 4,                  -- more each wave
	healthPerWave = 0.10,         -- enemies' health: +10% a wave
	maxHealthMult = 4.0,
	bossEvery = 5,                -- every 5th wave brings the enemy hero (0: never)
	bossHealthMult = 3.0,         -- on top of the wave's
	breakTime = 20,               -- seconds between waves
	firstBreak = 30,              -- before wave 1

	-- losing
	overrunRadius = 12,           -- metres from the last stand
	overrunTime = 10,             -- seconds the horde must hold it with no defender near
	wipeGrace = 3,                -- seconds with nobody alive before it's over

	-- credits (the players' team score; the game can show up to 895)
	creditsPerKill = 5,
	creditsPerBoss = 100,
	startCredits = 0,
	maxCredits = 895,

	-- the shop: each break, each pad offers one item at random from this list
	shop = nil,                   -- default: HordeDefaultShop (set by HordeMap per era)
	padRadius = 6,
	buyHoldTime = 2.0,            -- seconds on a pad to buy

	-- AI (bots)
	aiObjectiveWeight = 100,      -- both teams converge on the last stand
	aiFightWeight = 25,

	pollInterval = 0.25,
}

local function Log(text)
	print("OpenSWBF2 horde: " .. text)
end

--=============================
-- Rules (pure Lua; the tests call these directly)
--=============================

function ObjectiveHorde:WaveSize(wave)
	return self.firstWave + self.perWave * (wave - 1)
end

function ObjectiveHorde:HealthMult(wave)
	local m = 1 + self.healthPerWave * (wave - 1)
	if m > self.maxHealthMult then m = self.maxHealthMult end
	return m
end

function ObjectiveHorde:IsBossWave(wave)
	return self.bossEvery > 0 and math.mod(wave, self.bossEvery) == 0
end

-- the bonus's index sent as a bleed rate: the network packs it in 5 bits over 0..8
function HordeEncodeBonus(index) return index * 8 / 31 end
function HordeDecodeBonus(rate) return math.floor((rate or 0) * 31 / 8 + 0.5) end

function HordeBonusIndex(name)
	local i
	for i = 1, table.getn(HordeBonuses) do
		if HordeBonuses[i].bonus == name then return i end
	end
end

-- posts: list of { name, x, z, team }. Fills self.lastStand, self.hordeSpawns, self.shopPads.
function ObjectiveHorde:Layout(posts)
	local function Dist2(a, b)
		local dx, dz = a.x - b.x, a.z - b.z
		return dx * dx + dz * dz
	end
	local byName, i = {}
	for i = 1, table.getn(posts) do byName[posts[i].name] = posts[i] end

	local stand = self.lastStand and byName[self.lastStand]
	if not stand then
		-- the players' post farthest from the horde's posts (any post if they have none)
		local mine, theirs = {}, {}
		for i = 1, table.getn(posts) do
			if posts[i].team == self.playersTeam then table.insert(mine, posts[i])
			elseif posts[i].team == self.hordeTeam then table.insert(theirs, posts[i]) end
		end
		if table.getn(mine) == 0 then mine = posts end
		if table.getn(theirs) == 0 then theirs = posts end
		local away = { x = 0, z = 0 }
		for i = 1, table.getn(theirs) do
			away.x = away.x + theirs[i].x / table.getn(theirs)
			away.z = away.z + theirs[i].z / table.getn(theirs)
		end
		stand = mine[1]
		for i = 2, table.getn(mine) do
			if Dist2(mine[i], away) > Dist2(stand, away) then stand = mine[i] end
		end
	end
	self.lastStand = stand.name

	local rest = {}
	for i = 1, table.getn(posts) do
		if posts[i].name ~= stand.name then table.insert(rest, posts[i]) end
	end
	-- farthest from the last stand first
	table.sort(rest, function(a, b)
		local da, db = Dist2(a, stand), Dist2(b, stand)
		if da == db then return a.name < b.name end
		return da > db
	end)

	local taken = { [stand.name] = 1 }
	if not self.hordeSpawns then
		self.hordeSpawns = {}
		-- keep at least one post for the shop when there are three or more
		local count = self.hordeSpawnCount
		if table.getn(rest) - count < 1 then count = table.getn(rest) - 1 end
		if count < 1 then count = 1 end
		for i = 1, math.min(count, table.getn(rest)) do
			table.insert(self.hordeSpawns, rest[i].name)
		end
	end
	for i = 1, table.getn(self.hordeSpawns) do taken[self.hordeSpawns[i]] = 1 end
	if not self.shopPads then
		self.shopPads = {}
		for i = 1, table.getn(rest) do
			if not taken[rest[i].name] then table.insert(self.shopPads, rest[i].name) end
		end
	end
end

-- Each pad's offer for a break: distinct items while there are enough, chosen by a small
-- deterministic generator (seeded by the wave) so every break differs. Skips the active bonus.
function ObjectiveHorde:PickOffers(wave)
	local pool, i = {}
	for i = 1, table.getn(self.shop) do
		local item = self.shop[i]
		if not (item.kind == "bonus" and item.bonus == self.activeBonus) then
			table.insert(pool, item)
		end
	end
	local seed = math.mod(wave * 7919 + 17, 65521)
	local offers = {}
	for i = 1, table.getn(self.shopPads) do
		if table.getn(pool) == 0 then break end
		seed = math.mod(seed * 75 + 74, 65537)
		local k = math.mod(seed, table.getn(pool)) + 1
		offers[self.shopPads[i]] = pool[k]
		table.remove(pool, k)
	end
	return offers
end

--=============================
-- Engine side
--=============================

function ObjectiveHorde:AllPosts()
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

function ObjectiveHorde:SetCredits(n)
	if n > self.maxCredits then n = self.maxCredits end
	self.credits = n
	SetTeamPoints(self.playersTeam, n)
end

-- turns a bonus on here; on the host, also sends it to everyone
function ObjectiveHorde:ApplyBonus(name)
	if self.activeBonus == name then return end
	if self.activeBonus then
		ActivateBonus(self.playersTeam, "team_bonus_" .. self.activeBonus, false)
	end
	self.activeBonus = name
	if name then
		ActivateBonus(self.playersTeam, "team_bonus_" .. name, true)
	end
	if self.authority then
		SetBleedRate(self.playersTeam, HordeEncodeBonus(name and HordeBonusIndex(name) or 0))
	end
end

function ObjectiveHorde:Buy(pad, item)
	self:SetCredits(self.credits - item.price)
	self.sold[pad] = true
	MapRemoveEntityMarker(pad)
	Log("bought " .. item.id .. " for " .. item.price)
	if item.kind == "bonus" then
		self:ApplyBonus(item.bonus)
	elseif item.kind == "hero" then
		UnlockHeroForTeam(self.playersTeam)
	elseif item.kind == "vehicle" then
		self.vehicles = (self.vehicles or 0) + 1
		local x, y, z = GetWorldPosition(self.lastStand)
		local a = self.vehicles * 1.3
		CreateEntity(item.class, CreateMatrix(0, 0, 1, 0, x + 10 * math.cos(a), y + 1, z + 10 * math.sin(a)),
			"horde_vehicle_" .. self.vehicles)
	end
end

-- humans on each open pad; buys after buyHoldTime
function ObjectiveHorde:ShopTick(dt)
	local pad, item
	for pad, item in pairs(self.offers) do
		if not self.sold[pad] then
			local px, py, pz = GetWorldPosition(pad)
			local someone = false
			local i
			for i = 0, GetTeamSize(self.playersTeam) - 1 do
				local c = GetTeamMember(self.playersTeam, i)
				local unit = c and GetCharacterUnit(c)
				if unit and IsCharacterHuman(c) and IsObjectAlive(unit) then
					local x, y, z = GetWorldPosition(unit)
					if x and (x - px) * (x - px) + (z - pz) * (z - pz) <= self.padRadius * self.padRadius then
						someone = true
					end
				end
			end
			if someone then
				if not self.padTime[pad] then
					self.padTime[pad] = 0
					if item.message then ShowMessageText(item.message, self.playersTeam) end
				end
				self.padTime[pad] = self.padTime[pad] + dt
				if self.padTime[pad] >= self.buyHoldTime and self.credits >= item.price then
					self:Buy(pad, item)
				end
			else
				self.padTime[pad] = nil
			end
		end
	end
end

function ObjectiveHorde:RefreshGoals()
	local i
	for i = 1, table.getn(self.AIGoals or {}) do DeleteAIGoal(self.AIGoals[i]) end
	self.AIGoals = {}
	local t
	for _, t in ipairs({ self.playersTeam, self.hordeTeam }) do
		if self.aiObjectiveWeight > 0 then
			table.insert(self.AIGoals, AddAIGoal(t, "Defend", self.aiObjectiveWeight * self.AIGoalWeight, self.lastStand))
		end
		if self.aiFightWeight > 0 then
			table.insert(self.AIGoals, AddAIGoal(t, "Deathmatch", self.aiFightWeight * self.AIGoalWeight))
		end
	end
end

function ObjectiveHorde:StartBreak(seconds)
	self.state = "break"
	self.overrun = 0
	SetObjectTeam(self.lastStand, self.playersTeam)     -- everyone can spawn again
	AllowAISpawn(self.hordeTeam, false)
	AllowAISpawn(self.playersTeam, true)
	SetTimerValue(self.clock, seconds)
	StartTimer(self.clock)
	ShowTimer(self.clock)
	self.offers = self:PickOffers(self.wave + 1)
	self.sold, self.padTime = {}, {}
	local pad, item
	for pad, item in pairs(self.offers) do
		MapAddEntityMarker(pad, "hud_objective_icon_circle", 3.0, self.playersTeam, "YELLOW", true, false, true)
	end
	Log("break before wave " .. (self.wave + 1))
end

function ObjectiveHorde:StartWave()
	self.wave = self.wave + 1
	self.state = "wave"
	self.overrun, self.wiped = 0, 0
	local pad
	for pad in pairs(self.offers or {}) do MapRemoveEntityMarker(pad) end
	self.offers = {}
	ShowTimer(nil)
	StopTimer(self.clock)
	SetObjectTeam(self.lastStand, 0)                    -- nobody respawns until the break
	SetTeamPoints(self.hordeTeam, self.wave)
	local size = self:WaveSize(self.wave)
	SetReinforcementCount(self.hordeTeam, size)
	AllowAISpawn(self.hordeTeam, true)
	if self:IsBossWave(self.wave) then
		UnlockHeroForTeam(self.hordeTeam)
	end
	Log("wave " .. self.wave .. ": " .. size .. " enemies" .. (self:IsBossWave(self.wave) and ", boss" or ""))
end

function ObjectiveHorde:CountNearStand()
	local px, py, pz = GetWorldPosition(self.lastStand)
	local r2 = self.overrunRadius * self.overrunRadius
	local counts = {}
	local t
	for _, t in ipairs({ self.playersTeam, self.hordeTeam }) do
		local n, i = 0
		for i = 0, GetTeamSize(t) - 1 do
			local c = GetTeamMember(t, i)
			local unit = c and GetCharacterUnit(c)
			if unit and IsObjectAlive(unit) then
				local x, y, z = GetWorldPosition(unit)
				if x and (x - px) * (x - px) + (z - pz) * (z - pz) <= r2 then n = n + 1 end
			end
		end
		counts[t] = n
	end
	return counts[self.playersTeam], counts[self.hordeTeam]
end

function ObjectiveHorde:Lose(why)
	Log("the last stand fell (" .. why .. ") after " .. (self.wave - 1) .. " waves")
	self:Complete(self.hordeTeam)
end

function ObjectiveHorde:Poll()
	if self.isComplete then return end
	local now = ScriptCB_GetMissionTime()
	local dt = now - (self.lastTime or now)
	self.lastTime = now

	if not self.authority then
		-- follow the server's enhancement
		local index = HordeDecodeBonus(GetBleedRate(self.playersTeam))
		self:ApplyBonus(HordeBonuses[index] and HordeBonuses[index].bonus or nil)
		return
	end

	if self.state == "break" then
		self:ShopTick(dt)
		if self.breakOver then
			self.breakOver = false
			if GetNumTeamMembersAlive(self.playersTeam) > 0 then
				self:StartWave()
			else
				-- nobody has spawned yet (a player still choosing a class): wait for them
				SetTimerValue(self.clock, 5)
				StartTimer(self.clock)
			end
		end
		return
	end

	-- a wave
	if GetReinforcementCount(self.hordeTeam) <= 0 then
		Log("wave " .. self.wave .. " cleared")
		self:StartBreak(self.breakTime)
		return
	end
	local defenders, attackers = self:CountNearStand()
	if attackers > 0 and defenders == 0 then
		self.overrun = self.overrun + dt
		if self.overrun >= self.overrunTime then return self:Lose("overrun") end
	else
		self.overrun = 0
	end
	if GetNumTeamMembersAlive(self.playersTeam) == 0 then
		self.wiped = self.wiped + dt
		if self.wiped >= self.wipeGrace then return self:Lose("everyone down") end
	else
		self.wiped = 0
	end
end

function ObjectiveHorde:Start()
	self.authority = CustomMode_IsAuthority()
	self.teamATT, self.teamDEF = self.hordeTeam, self.playersTeam
	self.shop = self.shop or {}
	self.isComplete = false
	self.bossClass = self.bossClass or (gCustomModeHeroes or {})[self.hordeTeam]
	self.wave = 0
	self.credits = 0
	self.offers, self.sold, self.padTime = {}, {}, {}
	SetFlagGameplayType("none")
	ShowTeamPoints(self.playersTeam, true)
	ShowTeamPoints(self.hordeTeam, true)
	if ScriptCB_GetCONNumBots and ScriptCB_SetNumBots then
		ScriptCB_SetNumBots(ScriptCB_GetCONNumBots())
	end

	local names = self:AllPosts()
	local posts, i = {}
	for i = 1, table.getn(names) do
		local x, y, z = GetWorldPosition(names[i])
		table.insert(posts, { name = names[i], x = x, z = z, team = GetObjectTeam(names[i]) })
	end
	assert(table.getn(posts) >= 2, "horde needs at least two command posts")
	self:Layout(posts)
	Log("last stand " .. self.lastStand .. "; horde spawns at " .. table.concat(self.hordeSpawns, ", ") ..
		"; shop pads: " .. (table.getn(self.shopPads) > 0 and table.concat(self.shopPads, ", ") or "none"))

	if not self.authority then
		local t = CreateTimer("hordePoll")
		SetTimerValue(t, self.pollInterval)
		StartTimer(t)
		OnTimerElapse(function(t) self:Poll() SetTimerValue(t, self.pollInterval) StartTimer(t) end, t)
		return
	end

	ForceHumansOntoTeam1()
	SetReinforcementCount(self.playersTeam, -1)
	SetReinforcementCount(self.hordeTeam, 0)
	for i = 1, table.getn(names) do
		SetProperty(names[i], "CaptureRegion", "")    -- nothing is captured in Horde
		AICanCaptureCP(names[i], self.playersTeam, false)
		AICanCaptureCP(names[i], self.hordeTeam, false)
		SetObjectTeam(names[i], 0)
	end
	for i = 1, table.getn(self.hordeSpawns) do SetObjectTeam(self.hordeSpawns[i], self.hordeTeam) end
	self:SetCredits(self.startCredits)
	SetTeamPoints(self.hordeTeam, 0)
	self:ApplyBonus(nil)
	self:RefreshGoals()
	MapAddEntityMarker(self.lastStand, "hud_objective_icon_circle", 4.0, self.playersTeam, "YELLOW", true, false, true)

	-- kills earn credits and use up the wave; enemies get tougher as the waves go
	OnCharacterDeath(function(character, killer)
		if self.isComplete or GetCharacterTeam(character) ~= self.hordeTeam then return end
		AddReinforcements(self.hordeTeam, -1)
		if killer and GetCharacterTeam(killer) == self.playersTeam then
			local boss = self.bossClass and self.lastBoss == character
			self:SetCredits(self.credits + (boss and self.creditsPerBoss or self.creditsPerKill))
		end
	end)
	OnCharacterSpawn(function(character)
		if GetCharacterTeam(character) ~= self.hordeTeam then return end
		local unit = GetCharacterUnit(character)
		if not unit then return end
		local mult = self:HealthMult(math.max(self.wave, 1))
		local class = GetEntityClassName(unit)
		if self.bossClass and class and string.lower(class) == string.lower(self.bossClass) then
			mult = mult * self.bossHealthMult
			self.lastBoss = character
			Log("the boss is here")
		end
		if mult ~= 1 then
			local cur, max = GetObjectHealth(unit)
			SetProperty(unit, "MaxHealth", max * mult)
			SetProperty(unit, "CurHealth", max * mult)
		end
	end)

	self.clock = CreateTimer("hordeClock")
	OnTimerElapse(function(t) self.breakOver = true end, self.clock)
	self:StartBreak(self.firstBreak)

	local poll = CreateTimer("hordePoll")
	SetTimerValue(poll, self.pollInterval)
	StartTimer(poll)
	OnTimerElapse(function(t) self:Poll() SetTimerValue(t, self.pollInterval) StartTimer(t) end, poll)
	self.pollTimer = poll
end

function ObjectiveHorde:Complete(winningTeam)
	if self.pollTimer then StopTimer(self.pollTimer) end
	if self.clock then StopTimer(self.clock) ShowTimer(nil) end
	Objective.Complete(self, winningTeam)
end
