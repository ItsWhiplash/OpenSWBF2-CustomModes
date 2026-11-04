@echo off
rem Builds the custom modes AddOn (Payload, Rush, Horde, Search & Destroy, Infiltration) and
rem installs it into your game.
rem
rem   mods\install.bat           a normal build
rem   mods\install.bat quick     a quick-test build: every mode shrunk (see mods\PLAYTEST.md)
rem
rem It finds your game's GameData folder from SWBF2_GAMEDATA, or Steam's usual folder. For GOG:
rem   set SWBF2_GAMEDATA=C:\GOG Games\Star Wars - Battlefront 2\GameData
setlocal
cd /d "%~dp0.."

set "GAMEDATA=%SWBF2_GAMEDATA%"
if "%GAMEDATA%"=="" set "GAMEDATA=C:\Program Files (x86)\Steam\steamapps\common\Star Wars Battlefront II Classic\GameData"
if not exist "%GAMEDATA%\data\_lvl_pc\core.lvl" (
    echo Can't find the game in "%GAMEDATA%".
    echo Set SWBF2_GAMEDATA to your GameData folder, for example:
    echo   set SWBF2_GAMEDATA=C:\GOG Games\Star Wars - Battlefront 2\GameData
    exit /b 1
)
where python >nul 2>nul
if errorlevel 1 (
    echo Python 3 is needed: install it from python.org, ticking "Add python.exe to PATH".
    exit /b 1
)

set "QUICK="
if /i "%~1"=="quick" set "QUICK=--quick"

echo Building the custom modes %QUICK% ...
python mods\custommodes\build.py --gamedata "%GAMEDATA%" %QUICK%
if errorlevel 1 (
    echo The build failed: see above.
    exit /b 1
)

if exist "%GAMEDATA%\AddOn\PAYLOAD" (
    echo Removing the old PAYLOAD AddOn: CUSTOMMODES replaces it.
    rmdir /s /q "%GAMEDATA%\AddOn\PAYLOAD"
)
robocopy "mods\custommodes\out\CUSTOMMODES" "%GAMEDATA%\AddOn\CUSTOMMODES" /MIR /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
    echo Copying into "%GAMEDATA%\AddOn" failed. Is the game running?
    exit /b 1
)
echo.
echo Installed into "%GAMEDATA%\AddOn\CUSTOMMODES".
if defined QUICK echo This is the QUICK TEST build: run mods\install.bat again for the normal one.
echo For a server, copy that folder into its AddOn folder (or the Docker server's addons folder) too.
