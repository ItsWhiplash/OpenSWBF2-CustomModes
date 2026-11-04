@echo off
rem The generated maps (Ground to Space, GTS, and Hoth, HTH), around the SWBF2 Mod Tools.
rem
rem   mods\mapgen\install_maps.bat generate     writes both maps into the Mod Tools' data_GTS and
rem                                             data_HTH folders (make each there first: see below)
rem   (then munge each map in the Mod Tools' Visual Munge)
rem   mods\mapgen\install_maps.bat copy         installs the munged maps into your game's AddOn folder
rem
rem It finds the Mod Tools from SWBF2_MODTOOLS (default C:\BF2_ModTools) and the game from
rem SWBF2_GAMEDATA (default: Steam's usual folder).
setlocal
cd /d "%~dp0..\.."

set "MODTOOLS=%SWBF2_MODTOOLS%"
if "%MODTOOLS%"=="" set "MODTOOLS=C:\BF2_ModTools"
set "GAMEDATA=%SWBF2_GAMEDATA%"
if "%GAMEDATA%"=="" set "GAMEDATA=C:\Program Files (x86)\Steam\steamapps\common\Star Wars Battlefront II Classic\GameData"

if /i "%~1"=="generate" goto generate
if /i "%~1"=="copy" goto copy
echo Usage: install_maps.bat generate ^| copy
exit /b 1

:generate
if not exist "%MODTOOLS%" (
    echo Can't find the Mod Tools in "%MODTOOLS%": set SWBF2_MODTOOLS to their folder.
    exit /b 1
)
for %%M in (GTS HTH) do (
    if not exist "%MODTOOLS%\data_%%M\_BUILD" (
        echo "%MODTOOLS%\data_%%M" isn't a Mod Tools map yet. In Visual Munge, make a new map with
        echo the code %%M first ^(it adds the build files^), then run this again.
        exit /b 1
    )
)
where python >nul 2>nul
if errorlevel 1 (
    echo Python 3 is needed: install it from python.org, with numpy: pip install numpy
    exit /b 1
)
python mods\mapgen\gts.py --out "%MODTOOLS%" || exit /b 1
python mods\mapgen\hoth.py --out "%MODTOOLS%" || exit /b 1
echo.
echo Written into "%MODTOOLS%\data_GTS" and "%MODTOOLS%\data_HTH".
echo Next: munge GTS and HTH in Visual Munge, then run: install_maps.bat copy
exit /b 0

:copy
if not exist "%GAMEDATA%\data\_lvl_pc\core.lvl" (
    echo Can't find the game in "%GAMEDATA%": set SWBF2_GAMEDATA to your GameData folder.
    exit /b 1
)
for %%M in (GTS HTH) do (
    if not exist "%MODTOOLS%\data_%%M\_LVL_PC\mission.lvl" (
        echo %%M isn't munged yet: munge it in Visual Munge first.
        exit /b 1
    )
    robocopy "%MODTOOLS%\data_%%M\_LVL_PC" "%GAMEDATA%\AddOn\%%M\Data\_lvl_pc" /MIR /NFL /NDL /NJH /NJS /NP >nul
    if errorlevel 8 (
        echo Copying %%M failed. Is the game running?
        exit /b 1
    )
    copy /y "%MODTOOLS%\data_%%M\addme\addme.script" "%GAMEDATA%\AddOn\%%M\addme.script" >nul
    if errorlevel 1 (
        echo %%M's addme.script is missing: munge the map's addme in Visual Munge too.
        exit /b 1
    )
    echo Installed %%M into "%GAMEDATA%\AddOn\%%M".
)
echo Rebuild the custom modes too (mods\install.bat) so their missions on these maps are current.
exit /b 0
