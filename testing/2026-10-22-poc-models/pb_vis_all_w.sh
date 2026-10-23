#!/bin/sh
# finer hidden-part pass over the whole export square, 3 x 3 tiles of 174 yd (R 87)
cx=16426.67; cy=-25896.53
for j in -1 0 1; do for i in -1 0 1; do
  x=$(python3 -c "print($cx + $i * 174)"); y=$(python3 -c "print($cy + $j * 174)")
  WATER=95.0 python3 pb_vis.py $x $y 87 3072 pbvw_${i}_${j}
done; done
echo ALLDONE
