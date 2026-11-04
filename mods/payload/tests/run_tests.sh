#!/usr/bin/env bash
# Runs the payload tests with the game's own Lua 5.0 (built from src/LuaFL), and checks every
# script's syntax with the game's compiler. Linux, macOS or WSL, with g++ or clang++.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
BIN=${TMPDIR:-/tmp}/openswbf2-payload-tests
mkdir -p "$BIN"
CXX=${CXX:-g++}
FLAGS=(-w -O1 -fpermissive -include stdint.h -D__cdecl= -D__stdcall= -I"$ROOT/src" -I"$ROOT/src/LuaFL/include" -I"$ROOT/src/LuaFL/src")
cd "$ROOT"
if [ ! -x "$BIN/lua" ]; then
	"$CXX" "${FLAGS[@]}" src/LuaFL/src/*.cpp src/LuaFL/src/lib/*.cpp mods/payload/tests/lua_runner.cpp -o "$BIN/lua"
fi
if [ ! -x "$BIN/luac" ]; then
	printf 'int build_lvls(int, char**) { return 1; }\nint stage_gamedata(int, char**) { return 1; }\n' > "$BIN/stubs.cpp"
	"$CXX" "${FLAGS[@]}" -DLUA_OPNAMES src/LuaFL/src/*.cpp tools/luac_host.cpp "$BIN/stubs.cpp" -o "$BIN/luac"
fi
python3 mods/payload/build.py --luac "$BIN/luac" --out "$BIN/out" > /dev/null
echo "syntax: ok"
"$BIN/lua" mods/payload/tests/mock_engine.lua mods/payload/tests/test_payload.lua
