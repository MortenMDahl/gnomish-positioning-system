#!/bin/bash
# S1 shells, coverage build: all five levels, visibility, bake, fill, data addon
set -e
for L in 0 1 2 3 4; do python3 sh_build3.py $L 2>&1 | tail -1; python3 sh_vis.py $L 3072; done
python3 sh_bakeprep.py 0 3; python3 sh_bakeprep.py 1 2; python3 sh_bakeprep.py 2 2; python3 sh_bakeprep.py 3 1; python3 sh_bakeprep.py 4 0.75
for L in 0 1 2 3 4; do python3 sh_bake.py $L | tail -1; python3 sh_fill.py $L shells_out; done
python3 sh_tolua.py /home/claude/wt/poc/prototypes/GPS3D_City_Stormwind /home/claude/wt/poc/tools/sandbox/site Stormwind
cp /home/claude/wt/poc/prototypes/GPS3D_City_Stormwind/Shells_Stormwind.lua /home/claude/wt/poc/tools/sandbox/site/addons/GPS3D_City_Stormwind/
