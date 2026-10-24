# Holes (a view seeing into a shell: back faces in red) in back-face check renders: red pixels left after removing
# 1-px edge lines (opening 2x2), as connected spots
import sys, numpy as np
from PIL import Image
from scipy import ndimage
for fn in sys.argv[1:]:
    a = np.asarray(Image.open(fn).convert('RGB')).astype(int)
    red = (a[..., 0] > 200) & (a[..., 1] < 40) & (a[..., 2] < 40); bg = a.sum(-1) < 60
    op = ndimage.binary_opening(red, structure=np.ones((2, 2)))
    lab, n = ndimage.label(op)
    print(fn, 'red px', int(red.sum()), 'after opening', int(op.sum()), 'spots', n, 'share of drawn', round(op.sum() / max((~bg).sum(), 1), 6))
