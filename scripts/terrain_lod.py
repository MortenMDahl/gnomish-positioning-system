"""The right-triangle bintree (4-8 mesh) on a tile's 33 x 33 height grid, shared by
scripts/terrain_lod_study.py (the offline study) and scripts/build_terrain_lod.py (the add-on's data).

A tile is two right triangles split along its north-west to south-east diagonal. A triangle splits at the
middle of its long side (its hypotenuse) into two halves, whose long sides are its short ones; ten rounds of
that reach the full grid (2048 triangles, every grid point a vertex). Every grid point but the four corners
is the middle of exactly one long side: its two ends are the point's morph parents (a coarser mesh draws it
half way between them), and the right-angle corners of the one or two triangles on that side are the points
it depends on (they must be in the mesh before it, or the mesh would crack: a restricted quadtree).
Grid point p = j * 33 + i (i east, j south, from the north-west corner), 0-based here.
"""
import numpy as np

B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
VAL = {c: i for i, c in enumerate(B64)}
GRID, CELLS = 33, 32
NP = GRID * GRID
CORNERS = (0, CELLS, CELLS * GRID, GRID * GRID - 1)


def decode(s):
    base = (VAL[s[0]] * 64 + VAL[s[1]]) * 64 + VAL[s[2]] - 131072
    return [(base + VAL[s[3 + i * 2]] * 64 + VAL[s[4 + i * 2]]) * 0.5 for i in range(NP)]


def _corner(world, i, j):
    """a tile corner's height as GPS3D and the planet view take it: the tile south-east of it first"""
    for (tx, ty, p) in ((i, j, 0), (i - 1, j, CELLS), (i, j - 1, CELLS * GRID), (i - 1, j - 1, NP - 1)):
        if 0 <= tx < 64 and 0 <= ty < 64 and (ty * 64 + tx) in world:
            return world[ty * 64 + tx][p]
    return 0.0


def canon(world, tx, ty):
    """the heights a tile is drawn with: GPS3D.lua's Canon (shared edges from the tile to the east and
    south, corners as above), so both tiles at an edge draw the same heights"""
    h = list(world[ty * 64 + tx])
    e = world.get(ty * 64 + tx + 1) if tx < 63 else None
    if e:
        for j in range(GRID):
            h[j * GRID + CELLS] = e[j * GRID]
    s = world.get((ty + 1) * 64 + tx) if ty < 63 else None
    if s:
        for i in range(GRID):
            h[CELLS * GRID + i] = s[i]
    h[0], h[CELLS] = _corner(world, tx, ty), _corner(world, tx + 1, ty)
    h[CELLS * GRID], h[NP - 1] = _corner(world, tx, ty + 1), _corner(world, tx + 1, ty + 1)
    return np.array(h, float)


def _build():
    """depth (1..10, 0 at the corners), morph parents A, B, dependencies (apexes), the triangles of every
    split (for the area each vertex changes) and the points of each depth"""
    P = lambda i, j: j * GRID + i  # noqa: E731
    depth = np.zeros(NP, int)
    A, B = np.full(NP, -1), np.full(NP, -1)
    deps = [[] for _ in range(NP)]
    kids = [[] for _ in range(NP)]
    apexes = [[] for _ in range(NP)]  # the right-angle corners of the triangles whose long side v halves
    level = [((32, 0), (0, 0), (32, 32)), ((0, 32), (32, 32), (0, 0))]  # (apex, left, right): long side left-right
    for d in range(1, 11):
        nxt = []
        for apex, l, r in level:
            m = ((l[0] + r[0]) // 2, (l[1] + r[1]) // 2)
            v = P(*m)
            if depth[v] == 0:
                depth[v] = d
                A[v], B[v] = P(*l), P(*r)
            pa = P(*apex)
            if pa not in deps[v]:
                deps[v].append(pa)
                apexes[v].append(apex)
                if pa not in CORNERS:
                    kids[pa].append(v)
            nxt.append((m, l, apex))
            nxt.append((m, apex, r))
        level = nxt
    by_depth = [np.array([p for p in range(NP) if depth[p] == d], int) for d in range(11)]
    return depth, A, B, deps, kids, apexes, by_depth


DEPTH, PA, PB, DEPS, KIDS, APEXES, BY_DEPTH = _build()
BOUNDARY = np.array([(p % GRID in (0, CELLS)) or (p // GRID in (0, CELLS)) for p in range(NP)])


def _diamond_points():
    """per vertex: the grid points in the triangles on its long side, with their linear weights before
    the split (the triangle apex, a, b) and after (the half they fall in)"""
    out = [None] * NP
    for v in range(NP):
        if DEPTH[v] == 0:
            continue
        a, b = PA[v], PB[v]
        ax, ay, bx, by = a % GRID, a // GRID, b % GRID, b // GRID
        vx, vy = v % GRID, v // GRID
        idx, before, after = [], [], []
        for (px_, py_) in APEXES[v]:
            pc = py_ * GRID + px_
            xs = range(min(ax, bx, px_), max(ax, bx, px_) + 1)
            ys = range(min(ay, by, py_), max(ay, by, py_) + 1)
            for y in ys:
                for x in xs:
                    w = _bary((x, y), (px_, py_), (ax, ay), (bx, by))
                    if w is None:
                        continue
                    p = y * GRID + x
                    # after: the half (v, a, apex) or (v, apex, b)
                    w1 = _bary((x, y), (vx, vy), (ax, ay), (px_, py_))
                    if w1 is not None:
                        aft = ((v, w1[0]), (a, w1[1]), (pc, w1[2]))
                    else:
                        w2 = _bary((x, y), (vx, vy), (px_, py_), (bx, by))
                        aft = ((v, w2[0]), (pc, w2[1]), (b, w2[2]))
                    idx.append(p)
                    before.append(((pc, w[0]), (a, w[1]), (b, w[2])))
                    after.append(aft)
        out[v] = (idx, before, after)
    return out


def _bary(p, a, b, c):
    det = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
    l1 = ((b[0] - p[0]) * (c[1] - p[1]) - (c[0] - p[0]) * (b[1] - p[1])) / det
    l2 = ((c[0] - p[0]) * (a[1] - p[1]) - (a[0] - p[0]) * (c[1] - p[1])) / det
    l3 = 1 - l1 - l2
    if min(l1, l2, l3) < -1e-9:
        return None
    return (l1, l2, l3)


_DIAMONDS = None


def _gain_arrays():
    global _DIAMONDS
    if _DIAMONDS is None:
        D = _diamond_points()
        rows = []
        for v in range(NP):
            if D[v] is None:
                continue
            idx, before, after = D[v]
            for p, bw, aw in zip(idx, before, after):
                rows.append((v, p) + tuple(x for pw in bw for x in pw) + tuple(x for pw in aw for x in pw))
        R = np.array(rows, float)
        _DIAMONDS = (R[:, 0].astype(int), R[:, 1].astype(int), R[:, [2, 4, 6]].astype(int), R[:, [3, 5, 7]], R[:, [8, 10, 12]].astype(int), R[:, [9, 11, 13]])
    return _DIAMONDS


def own_errors(c, key):
    """per vertex: 'max' its height's distance from the middle of its parents; 'area' the error summed
    over the grid points of its diamond that splitting there takes off"""
    e = np.zeros(NP)
    nz = DEPTH > 0
    if key == 'max':
        e[nz] = np.abs(c[nz] - (c[PA[nz]] + c[PB[nz]]) * 0.5)
        return e
    vv, pp, bi, bw, ai, aw = _gain_arrays()
    before = np.abs((c[bi] * bw).sum(1) - c[pp])
    after = np.abs((c[ai] * aw).sum(1) - c[pp])
    np.add.at(e, vv, before - after)
    return np.maximum(e, 0)


def saturate(e):
    """each vertex at least as important as any vertex that depends on it (deepest first)"""
    s = e.copy()
    for d in range(10, 0, -1):
        for v in BY_DEPTH[d]:
            for p in DEPS[v]:
                if s[v] > s[p]:
                    s[p] = s[v]
    return s


def order(c, key='area', extra=None):
    """the order vertices join the mesh (corners first; every prefix a valid mesh) and the triangle count
    of each prefix (ntris[k]: the first k + 1 vertices). extra: added to the vertices' own errors (the
    neighbours' halves of the edge points' diamonds, edge_errors)"""
    e = own_errors(c, key)
    if extra is not None:
        e = e + extra
    s = saturate(e)
    rest = [p for p in range(NP) if DEPTH[p] > 0]
    rest.sort(key=lambda p: (-s[p], DEPTH[p], p))
    seq = list(CORNERS) + rest
    nb = np.cumsum(BOUNDARY[seq])
    ntris = 2 * np.arange(1, NP + 1) - nb - 2
    return np.array(seq, int), ntris


def active_set(seq, n):
    a = np.zeros(NP, bool)
    a[seq[:n]] = True
    return a


def surface(c, active):
    """the drawn heights at every grid point of the mesh of these vertices (the rest half way between
    their parents, coarse to fine)"""
    d = c.copy()
    for k in range(1, 11):
        v = BY_DEPTH[k]
        off = v[~active[v]]
        d[off] = (d[PA[off]] + d[PB[off]]) * 0.5
    return d


def sample_counts(n):
    out = list(range(4, min(n, 64) + 1))
    out += list(range(66, min(n, 160) + 1, 2))
    out += list(range(168, min(n, 520) + 1, 8))
    out += list(range(552, n + 1, 32))
    if out[-1] != n:
        out.append(n)
    return out


LADDERS = [2, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512, 768, 1024, 1536, 2048]


def ladder_marks(ntris, ladder=None):
    """vertex counts of the nested levels: for each triangle count of LADDERS the largest prefix within it"""
    marks = set()
    for L in (ladder or LADDERS):
        k = int(np.searchsorted(ntris, L, side='right'))  # prefixes 1..k have at most L triangles
        if k >= 4:
            marks.add(k)
    return marks


# ---- the levels the add-on ships (scripts/build_terrain_lod.py, GPS3D's Terrain.lua) -------------------
LEVELS = 11  # level j = 0 (finest: 2048 triangles, every grid point) .. 10 (coarsest: the two root triangles)
LEVEL_TRIS = [2 ** (11 - j) for j in range(LEVELS)]  # at most this many triangles at level j


def leaves(active):
    """the triangles of the mesh of a valid vertex set: (apex, left, right, depth) with the corners in the
    order GPS3D draws them (counter-clockwise seen from above: negative cross product in grid i, j)"""
    out = []
    stack = [((32, 0), (0, 0), (32, 32), 0), ((0, 32), (32, 32), (0, 0), 0)]
    while stack:
        apex, l, r, d = stack.pop()
        if (l[0] + r[0]) % 2 == 0 and (l[1] + r[1]) % 2 == 0:
            m = ((l[0] + r[0]) // 2, (l[1] + r[1]) // 2)
            if active[m[1] * GRID + m[0]]:
                stack.append((m, l, apex, d + 1))
                stack.append((m, apex, r, d + 1))
                continue
        out.append((apex, l, r, d))
    return out


def mirror(p, side):
    """the same point in the next tile across an edge (side 1 north, 2 east, 3 south, 4 west)"""
    return {1: p + CELLS * GRID, 2: p - CELLS, 3: p - CELLS * GRID, 4: p + CELLS}[side]


def edge_errors(world, tx, ty):
    """per edge point of a tile: the error the next tile's half of its diamond takes off (that tile's own
    error for it), so both tiles rank a shared edge point by its whole diamond"""
    extra = np.zeros(NP)
    for side, (dx, dy) in ((1, (0, -1)), (2, (1, 0)), (3, (0, 1)), (4, (-1, 0))):
        nx, ny = tx + dx, ty + dy
        if not (0 <= nx < 64 and 0 <= ny < 64 and (ny * 64 + nx) in world):
            continue
        e = own_errors(canon(world, nx, ny), 'area')
        for p in range(NP):
            if DEPTH[p] > 0 and _side(p) == side:
                extra[p] = e[mirror(p, side)]
    return extra


def _side(p):
    i, j = p % GRID, p // GRID
    return 1 if j == 0 else 2 if i == CELLS else 3 if j == CELLS else 4 if i == 0 else 0


def levels(c, extra=None):
    """the shipped levels of a tile with heights c: per grid point the coarsest level that has it (lv), and
    per level its triangle count, its mean height error against c at the grid points and the depth of its
    largest triangles"""
    seq, ntris = order(c, 'area', extra)
    lv = np.zeros(NP, int)
    T, E, D = [], [], []
    for j in range(LEVELS):
        k = int(np.searchsorted(ntris, LEVEL_TRIS[j], side='right'))  # the largest prefix within the count
        act = active_set(seq, k)
        lv[act] = j
        T.append(int(ntris[k - 1]))
        E.append(float(np.abs(surface(c, act) - c).mean()))
        D.append(min(t[3] for t in leaves(act)))
    lv[list(CORNERS)] = LEVELS - 1
    return lv, T, E, D


def flat_levels():
    """a flat tile's levels (no string is shipped for it): the even bintree, every point by its depth"""
    lv = np.array([LEVELS - 1 - DEPTH[p] for p in range(NP)])
    return lv, list(LEVEL_TRIS), [0.0] * LEVELS, [LEVELS - 1 - j for j in range(LEVELS)]


def b64n(v, n):
    s = ''
    for _ in range(n):
        s = B64[v % 64] + s
        v //= 64
    return s


COARSE = 4  # levels 4 to 10 (at most 128 triangles) also list their points, so building them reads only those


def encode(lv, T, E, D):
    """per level (finest first): triangles (2 characters), mean error in 1/64 yd (3), largest triangles'
    depth (1); then the 1089 grid points' levels, 4 bits each, three to two characters (point p + 1 the
    lowest bits); then for levels COARSE..10 how many points they have (2 each) and those points (2 each:
    the grid index), coarsest level first and by depth within a level (every point after its parents)"""
    s = ''.join(b64n(T[j], 2) + b64n(min(int(round(E[j] * 64)), 64 ** 3 - 1), 3) + b64n(D[j], 1) for j in range(LEVELS))
    v = list(lv) + [0, 0]
    for g in range(0, NP, 3):
        s += b64n(v[g] + v[g + 1] * 16 + v[g + 2] * 256, 2)
    pts = sorted((p for p in range(NP) if lv[p] >= COARSE), key=lambda p: (-lv[p], DEPTH[p], p))
    s += ''.join(b64n(sum(1 for p in pts if lv[p] >= j), 2) for j in range(COARSE, LEVELS))
    s += ''.join(b64n(p, 2) for p in pts)
    return s


def decode_levels(s):
    num = lambda a, b: sum(VAL[ch] * 64 ** (b - a - 1 - k) for k, ch in enumerate(s[a:b]))  # noqa: E731
    T = [num(6 * j, 6 * j + 2) for j in range(LEVELS)]
    E = [num(6 * j + 2, 6 * j + 5) / 64 for j in range(LEVELS)]
    D = [num(6 * j + 5, 6 * j + 6) for j in range(LEVELS)]
    lv = []
    p0 = 6 * LEVELS
    for g in range(0, NP, 3):
        v = num(p0 + 2 * (g // 3), p0 + 2 * (g // 3) + 2)
        lv += [v % 16, v // 16 % 16, v // 256]
    p0 += 2 * (NP // 3)
    cnt = [num(p0 + 2 * k, p0 + 2 * k + 2) for k in range(LEVELS - COARSE)]
    p0 += 2 * (LEVELS - COARSE)
    pts = [num(p0 + 2 * k, p0 + 2 * k + 2) for k in range(cnt[0])]
    assert p0 + 2 * cnt[0] == len(s), 'length'
    lv = np.array(lv[:NP])
    for k, j in enumerate(range(COARSE, LEVELS)):  # the list: each level's points first, in a valid order
        assert sorted(pts[:cnt[k]]) == sorted(int(p) for p in np.nonzero(lv >= j)[0]), ('list', j)
    seen = set(CORNERS)
    for p in pts:
        assert DEPTH[p] == 0 or (PA[p] in seen and PB[p] in seen and all(q in seen for q in DEPS[p])), ('order', p)
        seen.add(p)
    return lv, T, E, D
