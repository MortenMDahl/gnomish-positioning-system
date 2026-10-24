#!/bin/bash
# S1 shells: the whole pipeline for the three levels (build, visibility, bake frames, bake, fill)
set -e
PPY0=${PPY0:-3}; PPY1=${PPY1:-2}; PPY2=${PPY2:-2}
for L in 0 1 2; do
  python3 sh_build2.py $L | tail -1
  python3 sh_vis.py $L 3072
done
python3 sh_bakeprep.py 0 $PPY0; python3 sh_bakeprep.py 1 $PPY1; python3 sh_bakeprep.py 2 $PPY2
for L in 0 1 2; do python3 sh_bake.py $L | tail -1; python3 sh_fill.py $L shells_out; done
