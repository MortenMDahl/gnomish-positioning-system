# Renders shells (flat grey by facing, or later baked) and the game's own geometry with a z-buffer (pb_view.html)
import sys, json, base64, pickle, numpy as np
def tris_of_faces(faces):
    out = []
    for f in faces:
        c = f['c']
        out.append(c[[0, 1, 2]])
        if len(c) == 4: out.append(c[[0, 2, 3]])
    return np.array(out)
def gl(t): return np.stack([t[..., 0], t[..., 2], -t[..., 1]], -1).astype(np.float32)
def write_grey(name, tris, grey=0.85):
    json.dump([{'pos': base64.b64encode(gl(tris).tobytes()).decode(), 'f': 0, 'grey': grey}], open(name, 'w'))
def cam(tx, ty, th, dist, az, el):
    az, el = np.radians(az), np.radians(el)
    d = np.array([np.sin(az) * np.cos(el), np.cos(az) * np.cos(el), -np.sin(el)])   # looking direction (x east, y north, h)
    p = np.array([tx, ty, th]) - d * dist
    return [float(p[0]), float(p[1]), float(p[2]), float(d[0]), float(d[1]), float(d[2])]
if __name__ == '__main__':
    lods = sys.argv[1].split(',')
    d = np.load('sh_in.npz'); write_grey('shv_game.json', d['tri'][~d['street']].astype(float)); write_grey('shv_street.json', d['tri'][d['street']].astype(float), 0.7)
    for L in lods:
        R = pickle.load(open(f'sh_shells_{L}.pkl', 'rb'))
        write_grey(f'shv_l{L}.json', tris_of_faces([f for U in R for f in U['faces']]))
    views = {'v200': cam(16426, -25896, 110, 200, 200, 45), 'v90': cam(16400, -25880, 110, 90, 200, 40), 'v420': cam(16426, -25896, 110, 420, 200, 55)}
    jobs = []
    for vn, c in views.items():
        jobs.append({'m': 'shv_game.json,shv_street.json', 'cam': c, 'out': f'shv_{vn}_game.png', 'cull': 1})
        for L in lods: jobs.append({'m': f'shv_l{L}.json', 'cam': c, 'out': f'shv_{vn}_l{L}.png', 'cull': 1})
    json.dump(jobs, open('shv_jobs.json', 'w'))
