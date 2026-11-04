// A bare Lua 5.0 interpreter built from the game's own LuaFL sources (float numbers and all),
// for running the payload tests off Windows. run_tests.sh builds it.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include "lua.h"
#include "lualib.h"
#include "lauxlib.h"
void* Lua_Red_realloc(void* b, unsigned int, unsigned int s) { return s ? realloc(b, s) : (free(b), (void*)0); }
void Lua_Red_Free(void* b, unsigned int) { free(b); }
void LuaScript_CallWARNINGF(char const* m) { if (m) fprintf(stderr, "%s\n", m); }
extern "C" int __RedCurrHeap = 0;
extern "C" int RedSetCurrentHeap(int h) { int o = __RedCurrHeap; __RedCurrHeap = h; return o; }
int main(int argc, char** argv) {
  lua_State* L = lua_open();
  luaopen_base(L); luaopen_table(L); luaopen_string(L); luaopen_math(L); luaopen_debug(L);
  int st = 0;
  for (int i = 1; i < argc && !st; ++i) {
    st = luaL_loadfile(L, argv[i]);
    if (!st) st = lua_pcall(L, 0, 0, 0);
    if (st) fprintf(stderr, "ERROR: %s\n", lua_tostring(L, -1));
  }
  return st ? 1 : 0;
}
#include "RedEngineFL/Util/RedWarning.h"
namespace RedWarning {
void SetLogData(RED_ERROR_SEVERITY) {}
void LogMessage(const char* f, ...) { va_list a; va_start(a, f); vprintf(f, a); va_end(a); }
}
