-- Dagobah: Swamp (Clone Wars): Payload, built on the stock dag1c_con.
--
-- No track yet, so this mission records one: start it in Instant Action, walk the route the
-- payload should take, quit, then run extract_track.py on the log and paste the result here.
-- Every setting is described in README.md.

PayloadMap("dag1c", {
	track = {
	},
	checkpoints = { { at = 0.33 }, { at = 0.66 } },
	-- initialCPs = { cp1 = "att", cp2 = "def" },
})
