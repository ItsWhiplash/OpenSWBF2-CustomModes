-- every message the modes showed must have text (text.py, dumped by run_tests.sh)
if CustomModeTextKeys then
	local key, n
	local missing, count = {}, 0
	for key, n in pairs(MockSaid) do
		count = count + 1
		if string.sub(key, 1, 12) == "custommodes." and not CustomModeTextKeys[key] then
			table.insert(missing, key)
		end
	end
	Harness.current = "text"
	check(table.getn(missing) == 0, "every message has text; missing: " .. table.concat(missing, ", "))
	check(count >= 40, "the tests saw plenty of messages (" .. count .. ")")
end
print2(string.format("%d passed, %d failed", Harness.passed, Harness.failures))
if Harness.failures > 0 then
	error("tests failed")
end
