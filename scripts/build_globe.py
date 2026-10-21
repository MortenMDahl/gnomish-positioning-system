# Builds the planet view's art and data for GPS3D (Globe.lua):
#   prototypes/GPS3D/Globe/Land_<map>_<qx>_<qy>.tga  the continents at 16 px per ADT tile, one 512 x 512 page per
#        32 x 32-tile quarter of the map's grid that has land (32-bit TGA, bottom-left origin, like GPS's Media).
#        The open sea is transparent: a pixel is sea where the height data says sea level (World_<map>.lua,
#        heights of exactly 0.0, the sea's surface) and the image says sea (the minimap's near-black water);
#        both must agree, so dark land (Duskwood's woods) and lakes above sea level stay opaque. Land colours
#        are spread a few pixels into the transparent sea, so filtering never draws a dark fringe round coasts.
#   prototypes/GPS3D/Globe/Disc.tga, Shade.tga, Glow.tga, Cloud1-6.tga, Maelstrom.tga, MaelstromStorm.tga,
#        MaelstromBolt.tga  the planet's own art: a white disc (the ocean, tinted), the shading over it (black,
#        alpha: the side away from the light and the limb), the atmosphere's glow round the edge, six kinds of
#        cloud, the Maelstrom's whirlpool, the storm over it and a lightning flash.
#   prototypes/GPS3D/Data/Globe.lua  which tiles have land, per continent, and which pages exist.
#   tools/sandbox/site/globe/*.png  copies for the sandbox.
# Sources: the overview images (Interface/AddOns/GnomishPositioningSystem/Overview, 64 px per tile), the
# map table (Data/MapTiles.lua: atlases and each continent's main-land box) and GPS3D's height data.
# Usage: python scripts/build_globe.py   (--art: only the planet's own art; --land: only the land pages and
#        Data/Globe.lua, after the overview images changed, e.g. by scripts/fill_overview_sea.py)
import math, os, re, struct
import sys
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
GPS = os.path.join(ROOT, 'Interface', 'AddOns', 'GnomishPositioningSystem')
G3 = os.path.join(ROOT, 'prototypes', 'GPS3D')
OUT = os.path.join(G3, 'Globe')
SANDBOX = os.path.join(ROOT, 'tools', 'sandbox', 'site', 'globe')
MAPS = (0, 1)          # the continents on the planet (Eastern Kingdoms, Kalimdor)
P = 16                 # pixels per tile in the land pages
PAGE = 32              # tiles per page side (512 px)
B64 = {c: i for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/')}


def write_tga(img, path):
    a = np.asarray(img.convert('RGBA'))[::-1, :, [2, 1, 0, 3]]  # bottom-left origin, BGRA
    h, w = a.shape[:2]
    header = struct.pack('<BBBHHBHHHHBB', 0, 0, 2, 0, 0, 0, 0, 0, w, h, 32, 8)
    with open(path, 'wb') as f:
        f.write(header + a.tobytes())


def save(img, name):
    write_tga(img, os.path.join(OUT, name + '.tga'))
    if os.path.isdir(os.path.dirname(SANDBOX)):
        os.makedirs(SANDBOX, exist_ok=True)
        img.save(os.path.join(SANDBOX, name.lower() + '.png'))


def map_block(map_id):
    s = open(os.path.join(GPS, 'Data', 'MapTiles.lua')).read()
    blk = s[s.index('\t[%d] = {' % map_id):]
    blk = blk[:blk.index('\n\t},\n')]
    atl = [dict(file=m[0], x0=int(m[1]), y0=int(m[2]), cols=int(m[3]), rows=int(m[4]), w=int(m[5]), h=int(m[6]))
           for m in re.findall(r'file = "([^"]+)", x0 = (\d+), y0 = (\d+), cols = (\d+), rows = (\d+), w = (\d+), h = (\d+)', blk)]
    fit = tuple(int(re.search(r'%s = (\d+)' % k, blk).group(1)) for k in ('fitMinX', 'fitMinY', 'fitMaxX', 'fitMaxY'))
    return atl, fit


def heights(map_id):
    s = open(os.path.join(G3, 'Data', 'World_%d.lua' % map_id)).read()
    out = {}
    for key, t in re.findall(r'\[(\d+)\]\s*=\s*"([^"]+)"', s):
        base = ((B64[t[0]] * 64 + B64[t[1]]) * 64 + B64[t[2]]) - 131072
        v = np.array([B64[c] for c in t[3:3 + 33 * 33 * 2]]).reshape(-1, 2)
        out[int(key)] = ((base + v[:, 0] * 64 + v[:, 1]) * 0.5).reshape(33, 33)
    return out


def land_pages(map_id):
    atl, (fx0, fy0, fx1, fy1) = map_block(map_id)
    hts = heights(map_id)
    N = 64 * P
    # the image: overview atlases (64 px per tile) at P px per tile
    rgb = Image.new('RGB', (N, N), (8, 17, 16))
    for a in atl:
        im = Image.open(os.path.join(GPS, 'Overview', a['file'] + '.jpg')).convert('RGB')
        crop = im.crop((0, 0, a['cols'] * 64, a['rows'] * 64)).resize((a['cols'] * P, a['rows'] * P), Image.LANCZOS)
        rgb.paste(crop, (a['x0'] * P, a['y0'] * P))
    rgb = np.asarray(rgb).astype(np.float32)
    # sea by height: how much of each pixel is at sea level, the tile's 33 x 33 grid sampled at the pixel centres
    sea_h = np.ones((N, N), np.float32)
    for key, h in hts.items():
        tx, ty = key % 64, key // 64
        if not (fx0 <= tx <= fx1 and fy0 <= ty <= fy1):
            continue
        g = (np.abs(h) < 0.01).astype(np.float32)  # 33 x 33, corners shared with neighbours
        # sample the grid at the P x P pixel centres (bilinear)
        c = (np.arange(P) + 0.5) / P * 32
        i0 = np.minimum(np.floor(c).astype(int), 31)
        f = c - i0
        rows = g[i0, :] * (1 - f)[:, None] + g[i0 + 1, :] * f[:, None]
        cell = rows[:, i0] * (1 - f)[None, :] + rows[:, i0 + 1] * f[None, :]
        sea_h[ty * P:(ty + 1) * P, tx * P:(tx + 1) * P] = cell
    # sea by colour: the minimap's water is near black (#081110 and #080810 in the overview images)
    mx = rgb.max(axis=2)
    sea_c = np.clip((44.0 - mx) / 16.0, 0, 1)
    sea = sea_h * sea_c
    alpha = 1 - sea
    # outside the main-land box (the corner test squares) and tiles without terrain: no land
    mask = np.zeros((N, N), np.float32)
    for key in hts:
        tx, ty = key % 64, key // 64
        if fx0 <= tx <= fx1 and fy0 <= ty <= fy1:
            mask[ty * P:(ty + 1) * P, tx * P:(tx + 1) * P] = 1
    alpha *= mask
    alpha = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))).astype(np.float32) / 255
    alpha[alpha < 0.03] = 0
    # spread land colours into the sea (8 steps of a 3 x 3 dilation from the solid land pixels)
    have = alpha > 0.5
    out = np.where(have[..., None], rgb, 0)
    filled = have.copy()
    for _ in range(8):
        acc = np.zeros_like(rgb); cnt = np.zeros((N, N), np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                sh = np.roll(np.roll(out, dy, 0), dx, 1); sf = np.roll(np.roll(filled, dy, 0), dx, 1)
                acc += sh * sf[..., None]; cnt += sf
        new = (~filled) & (cnt > 0)
        out[new] = acc[new] / cnt[new][:, None]
        filled |= new
    out[~filled] = rgb[~filled]
    rgba = np.dstack([out, alpha * 255]).clip(0, 255).astype(np.uint8)
    pages, tiles = [], []
    for qy in range(64 // PAGE):
        for qx in range(64 // PAGE):
            sub = rgba[qy * PAGE * P:(qy + 1) * PAGE * P, qx * PAGE * P:(qx + 1) * PAGE * P]
            if sub[..., 3].max() == 0:
                continue
            save(Image.fromarray(sub, 'RGBA'), 'Land_%d_%d_%d' % (map_id, qx, qy))
            pages.append((qx, qy))
    for key in sorted(hts):
        tx, ty = key % 64, key // 64
        if alpha[ty * P:(ty + 1) * P, tx * P:(tx + 1) * P].max() >= 0.1:
            tiles.append(key)
    sea_px = float((sea > 0.5)[mask > 0].mean())
    agree = float(((sea_h > 0.5) == (sea_c > 0.5))[mask > 0].mean())
    return pages, tiles, dict(sea_share=sea_px, height_colour_agree=agree, alpha_px=int((alpha > 0).sum()))


def radial(n=256):
    y, x = np.mgrid[0:n, 0:n]
    return (x + 0.5 - n / 2) / (n / 2), (n / 2 - (y + 0.5)) / (n / 2)  # -1..1, y up


def planet_art():
    n = 256
    x, y = radial(n)
    r = np.sqrt(x * x + y * y)
    edge = np.clip((1 - r) * n / 2 + 0.5, 0, 1)  # one pixel of antialiasing at the rim
    # the ocean: a white disc, tinted with SetVertexColor
    disc = np.dstack([np.full((n, n), 255.0)] * 3 + [edge * 255])
    save(Image.fromarray(disc.astype(np.uint8), 'RGBA'), 'Disc')
    # its shading: black, alpha = how dark (light from the upper left, a little toward the viewer; the limb darker)
    z = np.sqrt(np.clip(1 - r * r, 0, 1))
    L = np.array([-0.45, 0.55, 0.70]); L = L / np.linalg.norm(L)
    lam = np.clip(x * L[0] + y * L[1] + z * L[2], 0, 1)
    dark = np.clip(1 - (0.22 + 0.9 * lam), 0, 0.82)
    shade = np.dstack([np.zeros((n, n))] * 3 + [dark * edge * 255])
    save(Image.fromarray(shade.astype(np.uint8), 'RGBA'), 'Shade')
    # the glow: the planet's rim at 0.80 of the texture's half size; haze just inside, glow fading outside
    R0 = 0.80
    inside = np.clip((r - (R0 - 0.06)) / 0.06, 0, 1) * (r <= R0)
    outside = np.exp(-np.clip(r - R0, 0, None) / 0.045) * (r > R0)
    a = np.clip(0.5 * inside + 0.6 * outside, 0, 1)
    glow = np.dstack([np.full((n, n), 120.0), np.full((n, n), 170.0), np.full((n, n), 255.0), a * 255])
    save(Image.fromarray(glow.astype(np.uint8), 'RGBA'), 'Glow')
    # clouds (2026-10-19, before: blurred round puffs): fractal noise with real clouds' spectrum (power
    # falling as 1/f^3), a soft edge (1 - e^(-k d) of the density above the cover level), thick parts white and
    # thin ones translucent: two cumulus clusters, cloud streets, a storm's spiral, a front's band, a veil
    # of cirrus
    save(make_cumulus(256, 11, 1.0, 0.5), 'Cloud1')
    save(make_cumulus(256, 12, 1.6, 0.45), 'Cloud2')
    save(make_streets(256, 13), 'Cloud3')
    save(make_cyclone(256, 14), 'Cloud4')
    save(make_band(256, 15), 'Cloud5')
    save(make_cirrus(256, 19), 'Cloud6')
    # the Maelstrom: the whirlpool (foam streaks along the inflowing water's spiral, the water darker toward
    # a dark eye), the storm over it (spiral bands of grey cloud round a clear eye) and a lightning flash
    save(make_maelstrom(512, 16), 'Maelstrom')
    save(make_storm(512, 17), 'MaelstromStorm')
    save(make_bolt(128, 18), 'MaelstromBolt')


# ---- the art's building blocks ----------------------------------------------------------------------------
def periodic_noise(h, w, rng, slope=2.0, lo=1.0):
    # fractal noise, periodic in both directions (h x w): random phases, amplitude 1/f^(slope/2) for
    # frequencies of at least lo cycles across, none below; zero mean, unit deviation
    fy = np.fft.fftfreq(h)[:, None] * h; fx = np.fft.fftfreq(w)[None, :] * w
    f = np.sqrt(fx * fx + fy * fy); f[0, 0] = 1
    amp = f ** (-slope / 2); amp[f < lo] = 0; amp[0, 0] = 0
    spec = amp * np.exp(2j * np.pi * rng.random((h, w)))
    n = np.real(np.fft.ifft2(spec))
    return (n - n.mean()) / (n.std() + 1e-9)

def fbm(n, rng, slope=2.0, lo=2.0):
    return periodic_noise(n, n, rng, slope, lo)

def warp(field, wx, wy):
    n = field.shape[0]
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    return ndimage.map_coordinates(field, [yy + wy, xx + wx], order=1, mode='wrap')

def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)

def grid(n):
    y, x = np.mgrid[0:n, 0:n]
    return (x + 0.5 - n / 2) / (n / 2), (n / 2 - (y + 0.5)) / (n / 2)

def rgba(c, a, window=True):
    c = np.clip(c, 0, 1)
    if window:
        # nothing reaches the square's edge (the quad's border must be invisible)
        n = a.shape[0]
        x, y = grid(n)
        r = np.sqrt(x * x + y * y)
        a = a * smoothstep(1.0, 0.82, np.maximum(np.abs(x), np.abs(y))) * smoothstep(1.05, 0.8, r)
    if c.ndim == 2: c = np.dstack([c, c, c])
    return Image.fromarray((np.dstack([c, np.clip(a, 0, 1)]) * 255 + 0.5).astype(np.uint8), 'RGBA')

def cloud_colour(dens, crease):
    # thick parts white, thin parts a little grey-blue (the sea shows through), creases a touch darker
    c = 0.78 + 0.22 * np.sqrt(np.clip(dens, 0, 1)) - 0.08 * np.clip(crease, 0, 1)
    return np.dstack([c * 0.975, c * 0.988, c])

def billows(n, rng, warp_px=0.012):
    # cloud noise: fractal (power falling as 1/f^3, like real cloud fields), very gently warped
    w1, w2 = fbm(n, rng, 3.6, 1.5) * n * warp_px, fbm(n, rng, 3.6, 1.5) * n * warp_px
    big = warp(fbm(n, rng, 3.6, 1.5), w1, w2)
    mid = warp(fbm(n, rng, 3.0, 3), w1, w2)
    return big, mid

def cover_alpha(d, sharp=2.6, top=0.96):
    # the classic soft cloud edge: 1 - e^(-k d) of the density above the cover level
    return (1 - np.exp(-np.clip(d, 0, None) * sharp)) * top

def make_cumulus(n, seed, stretch=1.0, cover=0.5):
    # a cluster of cumulus: big soft masses with smaller ones round them
    rng = np.random.default_rng(seed)
    x, y = grid(n)
    big, mid = billows(n, rng)
    r = np.sqrt((x / stretch) ** 2 + y * y)
    env = smoothstep(1.05, 0.15, r + 0.2 * big)
    noise = 0.65 * big + 0.45 * mid
    d = env * (noise + 1.7) - 2.0 * (1 - cover) - 0.1
    a = cover_alpha(d, 2.2)
    return rgba(cloud_colour(np.clip(d, 0, 1), smoothstep(0.3, 1.8, -mid)), a)

def make_streets(n, seed):
    # cloud streets: rows of small cumulus lined up with the wind, in a patch
    rng = np.random.default_rng(seed)
    x, y = grid(n)
    big, mid = billows(n, rng)
    rows = 0.5 + 0.5 * np.cos((y + 0.06 * big) * np.pi * 6.5)
    env = smoothstep(1.0, 0.4, np.sqrt(x * x + (y / 0.85) ** 2) + 0.2 * big)
    d = env * (1.4 * rows + 0.5 * mid + 0.2 * big) - 0.95
    a = cover_alpha(d, 2.4, 0.92)
    return rgba(cloud_colour(np.clip(d, 0, 1), smoothstep(0.3, 1.8, -mid)), a)

def make_cyclone(n, seed, turns=2.4):
    # a storm's spiral: one main arm and a weaker second wrapped round a dense middle with a small eye
    rng = np.random.default_rng(seed)
    x, y = grid(n)
    r = np.sqrt(x * x + y * y) + 1e-6
    th = np.arctan2(y, x)
    big, mid = billows(n, rng)
    s = th + turns * np.log(r)
    arm = np.clip(0.5 + 0.5 * np.cos(s + 0.3 * big) + 0.15 * np.cos(2 * s + 1.3), 0, 1.2) ** 1.5
    env = smoothstep(0.98, 0.4, r + 0.08 * big) * smoothstep(0.03, 0.07, r)
    core = smoothstep(0.26, 0.06, r)
    d = env * (1.5 * arm + 1.0 * core + 0.35 * mid) - 0.55
    a = cover_alpha(d, 2.5)
    return rgba(cloud_colour(np.clip(d, 0, 1), smoothstep(0.3, 1.8, -mid)), a)

def make_band(n, seed):
    # a front: a long curved band of cloud, thicker in its middle, broken at its ends
    rng = np.random.default_rng(seed)
    x, y = grid(n)
    big, mid = billows(n, rng)
    curve = 0.30 * np.sin(x * 1.6 + 0.4) - 0.1 * x + 0.05 * big
    width = 0.22 * (1 - 0.6 * x * x) + 0.03
    dist = np.abs(y - curve)
    d = smoothstep(width * 1.3, width * 0.1, dist) * smoothstep(1.0, 0.5, np.abs(x) + 0.12 * big) * (1.3 + 0.45 * mid) - 0.45
    a = cover_alpha(d, 2.6, 0.95)
    return rgba(cloud_colour(np.clip(d, 0, 1), smoothstep(0.3, 1.8, -mid)), a)

def polar_noise(nu, nv, rng, slope=1.6, lo=3):
    return periodic_noise(nv, nu, rng, slope, lo)

def make_maelstrom(n, seed, K=2.2):
    # the whirlpool: water swirling in (streamlines theta + K ln r = const), foam streaks along them, the water
    # darker and steeper toward a dark eye with a faint glow at its lip; the outer water clear (the sea shows)
    rng = np.random.default_rng(seed)
    x, y = grid(n)
    r = np.sqrt(x * x + y * y) + 1e-6
    th = np.arctan2(y, x)
    s = (th + K * np.log(r)) % (2 * np.pi)
    lr = -np.log(r)  # 0 at the edge, grows inward
    NU, NV = 1024, 128
    foamN = polar_noise(NU, NV, rng, 1.5, 4)
    # sample: u across the streamlines (fast), v along them (slow)
    u = s / (2 * np.pi) * NU
    v = np.clip(lr / 9.0, 0, 1) * (NV - 1)
    f = ndimage.map_coordinates(foamN, [v, u], order=1, mode='wrap')
    f2 = ndimage.map_coordinates(polar_noise(NU // 2, NV, rng, 1.8, 2), [v, u / 2], order=1, mode='wrap')
    turb = fbm(n, rng, 2.6, 4)
    foam = smoothstep(0.6, 2.2, f + 0.5 * f2 + 0.35 * turb) * smoothstep(0.98, 0.55, r) * smoothstep(0.06, 0.22, r)
    # the water: from the sea outside (transparent) to deep and dark inward
    depth = smoothstep(0.92, 0.12, r)
    eye = smoothstep(0.11, 0.0, r)
    lip = np.exp(-((r - 0.12) / 0.035) ** 2)
    water = np.dstack([0.05 + 0.10 * (1 - depth), 0.12 + 0.16 * (1 - depth), 0.20 + 0.22 * (1 - depth)])
    water = water * (1 - 0.85 * eye[..., None])
    bands = 0.5 + 0.5 * np.tanh(f2 * 1.2)  # darker and lighter lanes of water
    water = water * (0.8 + 0.35 * bands[..., None])
    water += lip[..., None] * np.array([0.05, 0.22, 0.22]) * 0.6  # a faint sea-green glint at the eye's lip
    c = water * (1 - foam[..., None]) + foam[..., None] * np.array([0.88, 0.94, 0.96])
    a = np.clip(0.92 * depth + foam * 0.95 + eye, 0, 1)
    edge = smoothstep(1.0, 0.8, r + 0.06 * turb)
    return rgba(c, a * edge, False)

def make_storm(n, seed, K=1.6):
    # the storm over the Maelstrom: spiral bands of dark grey cloud wound round a clear eye (the whirlpool
    # shows through), thinning outward
    rng = np.random.default_rng(seed)
    x, y = grid(n)
    r = np.sqrt(x * x + y * y) + 1e-6
    th = np.arctan2(y, x)
    big, mid = billows(n, rng)
    s = th + K * np.log(r)
    arms = np.clip(0.5 + 0.5 * np.cos(4 * s + 0.5 * big), 0, 1) ** 2.2
    env = smoothstep(1.0, 0.5, r + 0.08 * big) * smoothstep(0.24, 0.40, r)
    d = env * (1.6 * arms + 0.45 * mid + 0.25) - 0.55
    a = cover_alpha(d, 2.4, 0.88)
    g = 0.52 + 0.33 * np.sqrt(np.clip(d, 0, 1)) - 0.10 * smoothstep(0.3, 1.8, -mid)
    c = np.dstack([g * 0.92, g * 0.95, g * 1.02])
    return rgba(c, a, False)

def make_cirrus(n, seed):
    # a veil of cirrus: thin streaks drawn out by high winds, translucent
    rng = np.random.default_rng(seed)
    x, y = grid(n)
    sm = periodic_noise(n, n // 8, rng, 2.2, 5)  # stretched 8 x along x
    streak = np.asarray(Image.fromarray(sm.astype(np.float32), 'F').resize((n, n), Image.BICUBIC))
    big, mid = billows(n, rng)
    env = smoothstep(1.0, 0.3, np.sqrt(x * x + (y / 0.7) ** 2) + 0.2 * big)
    fine = np.asarray(Image.fromarray(periodic_noise(n, n // 16, rng, 2.4, 4).astype(np.float32), 'F').resize((n, n), Image.BICUBIC))
    d = env * (0.9 * streak + 0.35 * fine + 0.25 * big + 0.75) - 0.8
    a = cover_alpha(d, 1.8, 0.6)
    return rgba(np.dstack([np.full((n, n), 0.96), np.full((n, n), 0.98), np.ones((n, n))]), a)

def make_bolt(n, seed):
    # a lightning flash: a jagged branching line with a glow round it
    rng = np.random.default_rng(seed)
    img = np.zeros((n, n), np.float32)
    def seg(x0, y0, ang, length, width, depth):
        x, y = x0, y0
        steps = int(length / 2)
        for i in range(steps):
            ang += rng.normal(0, 0.35)
            x += np.cos(ang) * 2; y += np.sin(ang) * 2
            xi, yi = int(x), int(y)
            if 0 <= xi < n and 0 <= yi < n: img[yi, xi] = max(img[yi, xi], width)
            if depth < 2 and rng.random() < 0.06:
                seg(x, y, ang + rng.choice([-1, 1]) * rng.uniform(0.4, 0.9), length * 0.4, width * 0.6, depth + 1)
    seg(n * 0.5, n * 0.08, np.pi / 2, n * 0.85, 1.0, 0)
    core = ndimage.gaussian_filter(img, 0.8) * 3
    glow = ndimage.gaussian_filter(img, 6) * 25
    a = np.clip(core + glow * 0.5, 0, 1)
    c = np.dstack([0.75 + 0.25 * np.clip(core, 0, 1), 0.85 + 0.15 * np.clip(core, 0, 1), np.ones((n, n))])
    return rgba(c, a, False)


def main():
    os.makedirs(OUT, exist_ok=True)
    if '--art' in sys.argv:  # only the planet's own art (Disc, Shade, Glow, clouds, Maelstrom)
        planet_art()
        print('wrote the art in', OUT)
        return
    lines = ['-- Generated by scripts/build_globe.py: which ADT tiles of each continent have land (drawn on the planet),',
             '-- and which land pages exist (Globe\\Land_<map>_<qx>_<qy>.tga, 32 x 32 tiles each, %d px per tile).' % P,
             'local _, ns = ...', 'ns.GlobeData = { px = %d, page = %d, maps = {' % (P, PAGE)]
    for m in MAPS:
        pages, tiles, st = land_pages(m)
        print('map %d: %d pages %s, %d land tiles, sea share %.3f, height and colour agree on %.3f of the pixels' % (m, len(pages), pages, len(tiles), st['sea_share'], st['height_colour_agree']))
        lines.append('\t[%d] = {' % m)
        lines.append('\t\tpages = { %s },' % ', '.join('"%d_%d"' % p for p in pages))
        body = ', '.join(str(k) for k in tiles)
        lines.append('\t\ttiles = { %s },' % body)
        lines.append('\t},')
    lines.append('} }')
    open(os.path.join(G3, 'Data', 'Globe.lua'), 'w', newline='\n').write('\n'.join(lines) + '\n')
    if '--land' in sys.argv:
        print('wrote the land pages and Data/Globe.lua')
        return
    planet_art()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
