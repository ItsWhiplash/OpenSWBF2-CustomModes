print2(string.format("%d passed, %d failed", Harness.passed, Harness.failures))
if Harness.failures > 0 then
	error("tests failed")
end
