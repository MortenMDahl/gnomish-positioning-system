#!/bin/bash
# S1 shells, coverage build: the levels, visibility, bake, fill, data addon.
# Since 2026-10-24 (sharper near buildings): no level 0 in the data (its 21 M px of pictures went to levels 1-3),
# pictures 5 / 4 / 2.5 / 0.75 px a yard for levels 1-4, packed by place (PACK=hilbert). The first recipe, kept for the record:
#   sh_bakeprep.py 0 3; 1 2; 2 2; 3 1; 4 0.75 (all four unit levels, tallest-first packing), sh_tolua.py with LEVELS=0,1,2,3.
set -e
for L in 1 2 3 4; do python3 sh_build3.py $L 2>&1 | tail -1; python3 sh_vis.py $L 3072; done
export VAR=e_ PACK=hilbert
python3 sh_bakeprep.py 1 5; python3 sh_bakeprep.py 2 4; python3 sh_bakeprep.py 3 2.5; python3 sh_bakeprep.py 4 0.75
for L in 1 2 3 4; do python3 sh_bake.py $L | tail -1; python3 sh_fill.py $L shells_oute_; done
LEVELS=1,2,3 python3 sh_tolua.py /home/claude/wt/poc/prototypes/GPS3D_City_Stormwind /home/claude/wt/poc/tools/sandbox/site Stormwind
cp /home/claude/wt/poc/prototypes/GPS3D_City_Stormwind/Shells_Stormwind.lua /home/claude/wt/poc/tools/sandbox/site/addons/GPS3D_City_Stormwind/
