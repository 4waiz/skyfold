"""SKYFOLD environment kit - nature: palms, shrubs, planters' greenery, bougainvillea.

Pivot at ground centre. Palms are stylised date palms: ringed curved trunk, stiff arching fronds
with zig-zag leaflet edges (double-sided thin shells so they render from below in Unity).
"""
from env_common import *

NAT_AO = dict(ground_z=0.0, dist=1.2, rays=24, strength=0.7, floor=0.5, inset=0.08)
NAT_RENDER = dict(az=35.0, el=18.0)


def bezier(p0, p1, p2, n):
    out = []
    for i in range(n + 1):
        t = i / n
        out.append(p0 * (1 - t) ** 2 + p1 * 2 * t * (1 - t) + p2 * t * t)
    return out


def palm(a, x=0.0, y=0.0, z=0.0, height=8.0, lean=(0.0, 0.0), fronds=12, frond_len=3.3, r0=0.36, r1=0.25,
         seed=1, target=None, dates=True, frond_seg=8, trunk_seg=10, sides=7, crown_tilt=0.0, blade=0.42):
    rnd = random.Random(seed)
    base = Vector((x, y, z))
    top = base + Vector((lean[0], lean[1], height))
    ctrl = base + Vector((lean[0] * 0.15, lean[1] * 0.15, height * 0.55))
    path = bezier(base, ctrl, top, trunk_seg)
    # ringed taper (leaf-base rings)
    scales = []
    for i in range(trunk_seg + 1):
        t = i / trunk_seg
        r = (r0 * (1 - t) + r1 * t) * (1.0 + 0.35 * max(0.0, 0.25 - t) * 4)   # flared foot
        r *= 1.0 if i % 2 == 0 else 0.9
        scales.append(r)
    mb = MB()
    mb.sweep(path, circle(1.0, sides, a0=rnd.random() * 30), 'SKY_PalmTrunk', scales=scales)
    # crown bulb
    mb.sphere(r1 * 1.55, sides, 4, 'SKY_PalmTrunk', c=(top.x, top.y, top.z + 0.05), sz=1.15)
    a.part(mb, name="trunk", target=target)
    # fronds
    mbf = MB()
    golden = 137.5
    tang = (path[-1] - path[-2]).normalized()
    for k in range(fronds):
        phi = math.radians(k * golden + rnd.uniform(-12, 12))
        tier = k / max(1, fronds - 1)
        elev = math.radians(lerp(58, -5, tier) + rnd.uniform(-6, 6))
        L = frond_len * lerp(0.82, 1.05, 1 - abs(tier - 0.45)) * rnd.uniform(0.92, 1.06)
        d = Vector((math.cos(phi) * math.cos(elev), math.sin(phi) * math.cos(elev), math.sin(elev)))
        d = (d + tang * 0.25).normalized()
        start = top + Vector((0, 0, 0.12)) + Vector((d.x, d.y, 0)).normalized() * r1 * 0.9
        pts = [start]
        step = L / frond_seg
        droop = math.radians(lerp(11, 19, tier) + rnd.uniform(0, 4))
        cur = d.copy()
        side_ax = Vector((-math.sin(phi), math.cos(phi), 0.0))
        for s in range(frond_seg):
            pts.append(pts[-1] + cur * step)
            cur = (Matrix.Rotation(droop, 3, side_ax) @ cur).normalized()
        # blade cross-sections with zig-zag leaflet edges
        rings_top, rings_bot = [], []
        for i, p in enumerate(pts):
            t = i / frond_seg
            if i == 0:
                tdir = (pts[1] - pts[0]).normalized()
            elif i == frond_seg:
                tdir = (pts[-1] - pts[-2]).normalized()
            else:
                tdir = (pts[i + 1] - pts[i - 1]).normalized()
            sv = tdir.cross(Vector((0, 0, 1)))
            if sv.length < 1e-4:
                sv = side_ax.copy()
            sv.normalize()
            up = sv.cross(tdir).normalized()
            if up.z < 0:
                up = -up
            w = blade * math.sin(math.pi * min(1.0, t * 1.08) ** 0.75) + 0.02
            if 0 < i < frond_seg:
                w *= 1.3 if i % 2 else 0.55
            fold = 0.22 * w
            L_ = p + sv * w - up * fold * 0.5
            C_ = p + up * fold
            R_ = p - sv * w - up * fold * 0.5
            th = 0.025
            rings_top.append([L_, C_, R_])
            rings_bot.append([L_ - up * th, C_ - up * th, R_ - up * th])
        # assemble closed thin shell: top surface, bottom surface, side edges, end caps
        T = [[mbf.v(q) for q in ring] for ring in rings_top]
        B = [[mbf.v(q) for q in ring] for ring in rings_bot]
        fs = []
        for i in range(frond_seg):
            for j in range(2):
                fs.append(mbf.f([T[i][j], T[i + 1][j], T[i + 1][j + 1], T[i][j + 1]], 'SKY_PalmLeaf'))
                fs.append(mbf.f([B[i][j + 1], B[i + 1][j + 1], B[i + 1][j], B[i][j]], 'SKY_PalmLeaf'))
            fs.append(mbf.f([T[i][0], B[i][0], B[i + 1][0], T[i + 1][0]], 'SKY_PalmLeaf'))
            fs.append(mbf.f([T[i + 1][2], B[i + 1][2], B[i][2], T[i][2]], 'SKY_PalmLeaf'))
        for ring_i in (0, frond_seg):
            fs.append(mbf.f([T[ring_i][0], T[ring_i][1], T[ring_i][2], B[ring_i][2], B[ring_i][1], B[ring_i][0]],
                            'SKY_PalmLeaf'))
        mbf._recalc(fs)
    a.part(mbf, name="fronds", target=target)
    if dates:
        mbd = MB()
        for k in range(2):
            ang = math.radians(k * 150 + 40)
            c = top + Vector((math.cos(ang) * 0.42, math.sin(ang) * 0.42, -0.45))
            mbd.sphere(0.22, 6, 3, 'SKY_Terracotta', c=(c.x, c.y, c.z), sz=1.6)
            mbd.cyl(0.025, c.z + 0.2, top.z, 4, 'SKY_PalmTrunk', cx=c.x * 0.5 + top.x * 0.5, cy=c.y * 0.5 + top.y * 0.5)
        a.part(mbd, name="dates", target=target)
    a.set_target(target or a.name, weighted=False, smooth=70.0)
    return top


@asset("palm_date_a", "Nature", "nature", ao=NAT_AO, render=NAT_RENDER)
def palm_date_a(a):
    palm(a, height=6.3, lean=(0.35, -0.2), fronds=12, frond_len=3.8, seed=3)


@asset("palm_date_b", "Nature", "nature", ao=NAT_AO, render=NAT_RENDER)
def palm_date_b(a):
    palm(a, height=4.6, lean=(1.1, 0.4), fronds=11, frond_len=3.2, r0=0.32, r1=0.22, seed=7)


@asset("palm_small", "Nature", "nature", ao=NAT_AO, render=NAT_RENDER)
def palm_small(a):
    palm(a, height=2.0, lean=(0.15, 0.1), fronds=10, frond_len=1.6, r0=0.2, r1=0.15, seed=11, dates=False,

         frond_seg=7, trunk_seg=8, sides=7, blade=0.26)



def blob_cluster(mb, centers, mat, seg=8, rings=5):
    for (cx, cy, cz, r, sz) in centers:
        mb.sphere(r, seg, rings, mat, c=(cx, cy, cz), sz=sz)


@asset("shrub_round", "Nature", "nature", ao=dict(NAT_AO, dist=0.6, inset=0.05), render=NAT_RENDER)
def shrub_round(a):
    mb = MB()
    blob_cluster(mb, [(0, 0, 0.55, 0.62, 0.85), (0.38, 0.18, 0.42, 0.42, 0.85), (-0.32, -0.22, 0.4, 0.44, 0.85),
                      (0.05, -0.35, 0.36, 0.38, 0.85), (-0.15, 0.33, 0.38, 0.38, 0.85)], 'SKY_PalmLeaf', seg=9, rings=6)
    a.part(mb, name="leaves")
    a.set_target(a.name, weighted=False, smooth=80.0)


@asset("bougainvillea_clump", "Nature", "p1", ao=dict(NAT_AO, dist=0.6, inset=0.05), render=NAT_RENDER)
def bougainvillea_clump(a):
    rnd = random.Random(5)
    mb = MB()
    blob_cluster(mb, [(0, 0, 0.6, 0.65, 0.9), (0.5, 0.15, 0.5, 0.45, 0.9), (-0.45, -0.1, 0.48, 0.48, 0.9),
                      (0.1, 0.45, 0.45, 0.42, 0.9), (0.05, -0.45, 0.42, 0.4, 0.9)], 'SKY_PalmLeaf', seg=9, rings=6)
    a.part(mb, name="leaves")
    mb = MB()
    for i in range(16):
        ang = rnd.uniform(0, 2 * math.pi)
        el = rnd.uniform(-0.1, 1.0)
        R = 0.62 + rnd.uniform(-0.05, 0.12)
        cx, cy = math.cos(ang) * R * math.cos(el * 1.2), math.sin(ang) * R * math.cos(el * 1.2)
        cz = 0.55 + math.sin(el * 1.2) * R * 0.85
        mb.sphere(rnd.uniform(0.12, 0.2), 6, 3, 'SKY_Flower', c=(cx, cy, cz), sz=0.8)
    a.part(mb, name="flowers")
    a.set_target(a.name, weighted=False, smooth=80.0)
