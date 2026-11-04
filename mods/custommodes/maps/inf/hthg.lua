-- Hoth (Galactic Civil War): Infiltration, made by mods/mapgen/modes.py from the generated map. Rerun it
-- after changing the map; edit this file only to try something.

InfiltrationMap("hthg", {
	base = "HTHg_con",
	baseLvl = "..\\..\\AddOn\\HTH\\Data\\_lvl_pc\\mission.lvl",
	insertion = "cp10",
	extraction = "cp11",
	squadBots = 0,
	rideClass = "imp_fly_tiefighter",
	rides = {
		{ 75.0, 421.5, -1260.0 },
		{ 45.0, 421.5, -1260.0 },
		{ 15.0, 421.5, -1260.0 },
		{ -15.0, 421.5, -1260.0 },
		{ -45.0, 421.5, -1260.0 },
		{ -75.0, 421.5, -1260.0 },
	},
	escapeRides = {
		{ -430, 47.4, 560 },
		{ 430, 50.0, 560 },
		{ -620, 40.4, 880 },
		{ 700, 41.0, 900 },
		{ 0, 48.6, 980 },
	},
	extractRadius = 20.0,
	extractHeight = 15.0,
	targetClass = "all_fly_snowspeeder",
	memoryPools = {
		EntityFlyer = 16,
	},
	targets = {
		{
			post = "cp5",
		},
		{
			post = "cp6",
		},
		{
			post = "cp7",
		},
		{
			post = "cp8",
		},
		{ 0, 41.5, 1100 },
	},
})
