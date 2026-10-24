#!/bin/bash
# S1d (2026-10-24): the nine baked sets the five levels of detail choose from, the city's floor cells and picture, the
# data addon. Run in this folder after sh_all3.sh's coverage builds (sh_build3.py, sh_vis.py for levels 0-4).
# A set: VAR (variant name), PACK, level, pixels a yard; OWN=1 (default): a roof's picture shows only its own building.
set -e
run(){ VAR=$1 PACK=$2 python3 sh_bakeprep.py $3 $4 | tail -1; VAR=$1 python3 sh_bake.py $3 | tail -1; VAR=$1 python3 sh_fill.py $3 shells_out$1 | tail -1; }
run f_ hilbert 0 5
run "" "" 0 3; run "" "" 1 2; run "" "" 2 2; run "" "" 3 1; run "" "" 4 0.75
run e_ hilbert 1 5; run e_ hilbert 2 4; run e_ hilbert 3 2.5; run e_ hilbert 4 0.75
VAR=e_ python3 sh_floorcells.py                       # the ground cells under the shells' tops (sh_floorcells.json)
# the ground's heights over the box (after scripts/build_city_floor.py), then the floor picture (sh_floorimg.json: its box)
(cd ../../tools/sandbox && X0=16154 X1=16702 Y0=-26172 Y1=-25624 OUT=$OLDPWD/floor_ground.npy python3 $OLDPWD/sh_grounddump.py)
python3 sh_floorimg.py ../../tools/sandbox/site/minimap floor.jpg sh_floorimg.json
python3 sh_tolua_sets.py sets.json ../../prototypes/GPS3D_City_Stormwind ../../tools/sandbox/site Stormwind
cp ../../tools/sandbox/site/shells_sets/*.jpg ../../tools/sandbox/site/shells/
