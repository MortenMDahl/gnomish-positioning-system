# The exported geometry as numpy arrays: positions (GPS world x east, y north, h up), triangles, per-triangle
# texture file ID, per-vertex UV and vertex colour
import json, base64, numpy as np
def arr(s, t): return np.frombuffer(base64.b64decode(s), t)
def load(name):
    d = json.load(open(f'raw/{name}.json'))
    P, UV, COL, T, TEX = [], [], [], [], []
    off = 0
    for g in d['groups']:
        p = arr(g['pos'], np.float32).reshape(-1, 3); n = len(p)
        uv = arr(g['uv'], np.float32).reshape(-1, 2) if g['uv'] else np.zeros((n, 2), np.float32)
        if len(uv) < n: uv = np.vstack([uv, np.zeros((n - len(uv), 2), np.float32)])
        col = arr(g['col'], np.uint8).reshape(-1, 4)[:n] if g['col'] else np.full((n, 4), 255, np.uint8)
        if len(col) < n: col = np.vstack([col, np.full((n - len(col), 4), 255, np.uint8)])
        t = arr(g['idx'], np.uint32).reshape(-1, 3).astype(np.int64) + off
        P.append(p); UV.append(uv); COL.append(col); T.append(t); TEX.append(arr(g['tex'], np.uint32)); off += n
    return dict(meta=d, P=np.vstack(P), UV=np.vstack(UV), COL=np.vstack(COL), T=np.vstack(T), TEX=np.concatenate(TEX))
if __name__ == '__main__':
    for n in ('stormwind', 'orgrimmar'):
        m = load(n); print(n, m['P'].shape, m['T'].shape, 'h', m['P'][:, 2].min(), m['P'][:, 2].max(), 'vertex colours not white', float((m['COL'][:, :3] < 250).any(1).mean()))
