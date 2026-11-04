#!/usr/bin/env bash
# Runs the custom mode tests with the game's own Lua 5.0 (built from src/LuaFL), and checks every
# script's syntax with the game's compiler. Linux, macOS or WSL, with g++ or clang++.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
BIN=${TMPDIR:-/tmp}/openswbf2-custommodes-tests
mkdir -p "$BIN"
CXX=${CXX:-g++}
FLAGS=(-w -O1 -fpermissive -include stdint.h -D__cdecl= -D__stdcall= -I"$ROOT/src" -I"$ROOT/src/LuaFL/include" -I"$ROOT/src/LuaFL/src")
cd "$ROOT"
if [ ! -x "$BIN/lua" ]; then
	"$CXX" "${FLAGS[@]}" src/LuaFL/src/*.cpp src/LuaFL/src/lib/*.cpp mods/custommodes/tests/lua_runner.cpp -o "$BIN/lua"
fi
if [ ! -x "$BIN/luac" ]; then
	printf 'int build_lvls(int, char**) { return 1; }\nint stage_gamedata(int, char**) { return 1; }\n' > "$BIN/stubs.cpp"
	"$CXX" "${FLAGS[@]}" -DLUA_OPNAMES src/LuaFL/src/*.cpp tools/luac_host.cpp "$BIN/stubs.cpp" -o "$BIN/luac"
fi
python3 mods/custommodes/build.py --luac "$BIN/luac" --out "$BIN/out" > /dev/null
echo "syntax: ok"
python3 mods/custommodes/tests/test_build.py "$BIN/out"
python3 mods/custommodes/build.py --dump-keys > "$BIN/text_keys.lua"
if python3 -c "import numpy" 2>/dev/null; then
	python3 mods/mapgen/export_posts.py > "$BIN/mapgen_posts.lua"
else
	echo "-- numpy missing: the generated maps' modes are skipped" > "$BIN/mapgen_posts.lua"
fi
if python3 -c "import numpy, matplotlib" 2>/dev/null; then
	python3 mods/mapgen/test_mapgen.py --luac "$BIN/luac"
else
	echo "mapgen: skipped (needs numpy and matplotlib)"
fi
"$BIN/lua" mods/custommodes/tests/mock_engine.lua mods/custommodes/tests/harness.lua mods/custommodes/tests/test_payload.lua mods/custommodes/tests/test_rush.lua mods/custommodes/tests/test_horde.lua mods/custommodes/tests/test_snd.lua mods/custommodes/tests/test_inf.lua "$BIN/mapgen_posts.lua" mods/custommodes/tests/test_generated.lua "$BIN/text_keys.lua" mods/custommodes/tests/summary.lua
