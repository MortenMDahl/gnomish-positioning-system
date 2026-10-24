# S1 shells (2026-10-23): the Trade District's visible game triangles per building unit, saved flat for fast iteration.
import os, numpy as np
os.environ['RANK'] = 'value'; os.environ.setdefault('VISTAG', 'pbvw')
src = open('pb_city.py').read(); exec(compile(src[:src.index('cells = {}')], 'pb_city_part', 'exec'))
z = np.load('pb_buildings.npz'); bld, st = z['bld'], z['street']
UV3 = UVc.reshape(-1, 3, 2) if UVc.ndim == 2 else UVc
np.savez_compressed('sh_in.npz', tri=V[T2].astype(np.float32), uv=UV3.astype(np.float32), fd=FD.astype(np.int64), both=BF.astype(np.int8), bld=bld, street=st, piece=PC)
print('parts', len(T2), 'units', len(np.unique(bld[~st])), 'street parts', int(st.sum()))
