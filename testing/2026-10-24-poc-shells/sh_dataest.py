# estimate of the pictures' pixels and pages for a set of densities (px a yard per level), from the current layout
import pickle, sys, math, json
P = [float(v) for v in sys.argv[1].split(',')]
out = {}; tot = 0; pages = 0
for L in range(5):
    S = pickle.load(open(f'sh_faces_{L}.pkl', 'rb')); old = S['ppy']
    px = 0
    for p in S['pics']:
        w = max(2, math.ceil(p['w'] / old * P[L] - 1e-6)); h = max(2, math.ceil(p['h'] / old * P[L] - 1e-6)); px += (w + 4) * (h + 4)
    n = math.ceil(px / (2048 * 2048 * 0.93)); out[L] = (round(px / 1e6, 1), n); tot += px; pages += n
print(json.dumps({'ppy': P, 'per_level_Mpx_pages': out, 'Mpx': round(tot / 1e6, 1), 'pages': pages, 'dxt1_MB': round(pages * 2048 * 2048 * 0.5 * 4 / 3 / 1e6, 1)}))
