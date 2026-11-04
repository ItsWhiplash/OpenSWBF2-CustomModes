--
-- OpenSWBF2 custom modes: adds each mode to the stock maps listed in CUSTOMMODE_MISSIONS,
-- which build.py writes in front of this script: { { "tat2g", "pay" }, { "tat2g", "rush" }, ... }.
--

-- the modes' names and icons in the menus (no localization needed)
local Modes = {
	pay = { name = "Payload", icon = "mode_icon_ctf" },
	rush = { name = "Rush", icon = "mode_icon_con" },
	horde = { name = "Horde", icon = "mode_icon_hunt" },
	snd = { name = "Search & Destroy", icon = "mode_icon_ass" },
	inf = { name = "Infiltration", icon = "mode_icon_hunt" },
}
local Id, Mode
for Id, Mode in pairs(Modes) do
	if gModeFallbackNames then gModeFallbackNames[Id] = Mode.name end
	if gModeFallbackIcons then gModeFallbackIcons[Id] = Mode.icon end
end

-- Marks a stock map's row (or a new row) as having a mode in an era
local function CustomModeAddToList(List, Map, Era, Mode)
	if not List then
		return
	end
	local Want = string.lower(Map .. "%s_%s")
	local i
	for i = 1, table.getn(List) do
		if List[i].mapluafile and string.lower(List[i].mapluafile) == Want then
			List[i]["era_" .. Era] = 1
			List[i]["mode_" .. Mode .. "_" .. Era] = 1
			return
		end
	end
	local Row = { mapluafile = Map .. "%s_%s" }
	Row["era_" .. Era] = 1
	Row["mode_" .. Mode .. "_" .. Era] = 1
	table.insert(List, Row)
end

local i
for i = 1, table.getn(CUSTOMMODE_MISSIONS) do
	local Code = CUSTOMMODE_MISSIONS[i][1]                -- "tat2g"
	local Mode = CUSTOMMODE_MISSIONS[i][2]                -- "rush"
	local Map = string.sub(Code, 1, -2)                   -- "tat2"
	local Era = string.sub(Code, -1)                      -- "g"
	CustomModeAddToList(sp_missionselect_listbox_contents, Map, Era, Mode)
	CustomModeAddToList(mp_missionselect_listbox_contents, Map, Era, Mode)
	AddDownloadableContent(Map, Code .. "_" .. Mode, 4)
end
