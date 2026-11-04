--
-- OpenSWBF2 Payload: adds the Payload mode ("pay") to the stock maps listed in
-- PAYLOAD_MISSIONS, which build.py writes in front of this script.
--

-- the mode's name and icon in the menus (no localization needed)
if gModeFallbackNames then
	gModeFallbackNames.pay = "Payload"
end
if gModeFallbackIcons then
	gModeFallbackIcons.pay = "mode_icon_ctf"
end

-- Marks a stock map's row (or a new row) as having Payload in an era
local function PayloadAddToList(List, Map, Era)
	if not List then
		return
	end
	local Want = string.lower(Map .. "%s_%s")
	local i
	for i = 1, table.getn(List) do
		if List[i].mapluafile and string.lower(List[i].mapluafile) == Want then
			List[i]["era_" .. Era] = 1
			List[i]["mode_pay_" .. Era] = 1
			return
		end
	end
	local Row = { mapluafile = Map .. "%s_%s" }
	Row["era_" .. Era] = 1
	Row["mode_pay_" .. Era] = 1
	table.insert(List, Row)
end

local i
for i = 1, table.getn(PAYLOAD_MISSIONS) do
	local Code = PAYLOAD_MISSIONS[i]                      -- "tat2g"
	local Map = string.sub(Code, 1, -2)                   -- "tat2"
	local Era = string.sub(Code, -1)                      -- "g"
	PayloadAddToList(sp_missionselect_listbox_contents, Map, Era)
	PayloadAddToList(mp_missionselect_listbox_contents, Map, Era)
	AddDownloadableContent(Map, Code .. "_pay", 4)
end
