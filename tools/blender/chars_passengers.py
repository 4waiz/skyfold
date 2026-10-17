"""Passenger figures (passenger_a/b/c) for the SKYFOLD terminal queue.

Original procedural models (Awaiz Ahmed / Team Kanban), not AI-generated. Stylised, friendly,
non-specific people: no likeness of any real person, no brand clothing, no text.
    blender -b --factory-startup -P tools/blender/chars_passengers.py [-- --no-render]

Each FBX:  passenger_x (empty, ground between the feet) > Body (single mesh).
Facing Blender -Y (Unity +Z). ~1.6-1.75 m tall. Palette materials only.

Detail pass: sculpted heads with eyes (catch-lights), brows, nose, smile and ears; three hair
styles built as closed shells that dive under the scalp at the hairline; hands with a thumb and
four fingers; collars, cuffs, zips, buttons, belts, pockets; shoes with soles, toe caps and
laces. passenger_a: hooded zip jacket, joggers, backpack. passenger_b: shirt, belt, flat cap,
grey hair and beard, rolling suitcase with wheels and a telescopic handle. passenger_c: belted
long coat, scarf, bun, round glasses, shoulder bag.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C
from chars_common import Vector, Matrix, radians, sin, cos, pi, sqrt, atan2
import bmesh
from mathutils.bvhtree import BVHTree

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS

INK, PEARL, BRASS, RUBBER, METAL = 'SKY_Ink', 'SKY_Pearl', 'SKY_Brass', 'SKY_Rubber', 'SKY_Metal'

VARIANTS = {
    # target height, body build, clothing / skin / hair, accessory
    'passenger_a': dict(H=1.70, sh=0.182, hip=0.158, waist=0.142, chest=0.118, belly=0.0,
                        top='SKY_Teal', trim=INK, pants=INK, skin='SKY_SandstoneDeep',
                        hair=INK, style='quiff', shoe='SKY_Pearl', shoe2='SKY_Coral',
                        acc='backpack', acc_mat='SKY_Coral'),
    'passenger_b': dict(H=1.74, sh=0.196, hip=0.165, waist=0.158, chest=0.128, belly=0.016,
                        top='SKY_Coral', trim=PEARL, pants=INK, skin='SKY_Wood',
                        hair=METAL, style='cap', shoe='SKY_Wood', shoe2=INK,
                        acc='suitcase', acc_mat='SKY_Teal'),
    'passenger_c': dict(H=1.63, sh=0.170, hip=0.162, waist=0.136, chest=0.114, belly=0.0,
                        top='SKY_Pearl', trim='SKY_TealLight', pants='SKY_Teal',
                        skin='SKY_Sandstone', hair='SKY_Terracotta', style='bun', shoe=INK,
                        shoe2=INK, acc='coat', acc_mat='SKY_TealLight'),
}
NOMINAL = 1.70           # figures are built at this height, then scaled to H


def smoothstep(a, b, x):
    if a == b:
        return 1.0 if x >= b else 0.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def rounded_rect(w, h, r, n=3):
    pts = []
    for (cx, cy, a0) in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                         (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(n + 1):
            a = radians(a0 + 90 * k / n)
            pts.append((cx + r * cos(a), cy + r * sin(a)))
    return pts


def catmull(points, n_per, closed=True):
    P = [Vector((p[0], p[1], 0.0)) for p in points]
    m = len(P)
    out = []
    for i in (range(m) if closed else range(m - 1)):
        p0, p1, p2, p3 = P[(i - 1) % m], P[i], P[(i + 1) % m], P[(i + 2) % m]
        for k in range(n_per):
            t = k / n_per
            v = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                       (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t)
            out.append((v.x, v.y))
    return out


# ---------------------------------------------------------------------------- geometry helpers
def inset2d(pts, d, maxm=2.4):
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2 = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[(i + 1) % n])
        e0, e1 = p1 - p0, p2 - p1
        if e0.length < 1e-12 or e1.length < 1e-12:
            out.append((p1.x, p1.y))
            continue
        e0.normalize()
        e1.normalize()
        n0, n1 = Vector((-e0.y, e0.x)), Vector((-e1.y, e1.x))
        m = n0 + n1
        if m.length < 1e-9:
            m = n0.copy()
        m.normalize()
        c = max(m.dot(n0), 1.0 / maxm)
        q = p1 + m * (d / c)
        out.append((q.x, q.y))
    return out


def ccw(pts):
    """Return the outline counter-clockwise (the inset helper assumes CCW)."""
    a = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
            for i in range(len(pts)))
    return list(pts) if a > 0 else list(pts)[::-1]


def densify(pts, max_len):
    out = []
    n = len(pts)
    for i in range(n):
        a, b = Vector(pts[i]), Vector(pts[(i + 1) % n])
        k = max(1, int(math.ceil((b - a).length / max_len)))
        for j in range(k):
            q = a.lerp(b, j / k)
            out.append((q.x, q.y))
    return out


def plate(part, outline, F, thick, mat, bevel=0.002, rim=None, rim_w=0.0, fill=0, fill_to=0.0):
    """Beveled plate from a CCW 2D outline; F(x, y, h) -> world point (h = 0 .. thick)."""
    O = list(outline)
    n = len(O)
    rings = [(O, 0.0), (O, thick - bevel), (inset2d(O, bevel), thick)]
    if rim and rim_w > 0:
        rings.append((inset2d(O, bevel + rim_w), thick))
    nrim = len(rings) - 1
    d0 = bevel + (rim_w if rim else 0.0)
    for k in range(1, fill + 1):
        rings.append((inset2d(O, d0 + (fill_to - d0) * k / fill), thick))
    pts = [[F(x, y, h) for (x, y) in r] for (r, h) in rings]
    vr, faces = part.grid(pts, mat, True, 'ngon', 'ngon')
    if rim:
        part.assign(faces[(nrim - 3) * n: nrim * n], rim)
    return faces


def barycentric(p, a, b, c):
    v0, v1, v2 = b - a, c - a, p - a
    d00, d01, d11 = v0.dot(v0), v0.dot(v1), v1.dot(v1)
    d20, d21 = v2.dot(v0), v2.dot(v1)
    den = d00 * d11 - d01 * d01
    if abs(den) < 1e-24:
        return (1 / 3, 1 / 3, 1 / 3)
    v = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    return (1 - v - w, v, w)


class Surf:
    """Ray / closest-point projection onto a reference shell with interpolated normals."""

    def __init__(self, bm_src):
        bm = bm_src.copy()
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.normal_update()
        bm.verts.ensure_lookup_table()
        self.V = [v.co.copy() for v in bm.verts]
        self.N = [v.normal.copy() for v in bm.verts]
        self.T = [tuple(v.index for v in f.verts) for f in bm.faces]
        bm.free()
        self.bvh = BVHTree.FromPolygons(self.V, self.T, all_triangles=True)

    def _n(self, loc, idx):
        a, b, c = self.T[idx]
        w = barycentric(loc, self.V[a], self.V[b], self.V[c])
        return (self.N[a] * w[0] + self.N[b] * w[1] + self.N[c] * w[2]).normalized()

    def near(self, p):
        loc, nrm, idx, d = self.bvh.find_nearest(Vector(p))
        return loc, self._n(loc, idx)

    def ray(self, o, d):
        loc, nrm, idx, dist = self.bvh.ray_cast(Vector(o), Vector(d).normalized())
        if loc is None:
            return self.near(o)
        return loc, self._n(loc, idx)


def conform(surf, to3d, base, axis):
    """F(x, y, h): layout point -> surface hit along axis (+ normal * (base + h))."""
    cache = {}
    a = Vector(axis).normalized()

    def F(x, y, h):
        k = (round(x, 8), round(y, 8))
        if k not in cache:
            cache[k] = surf.ray(to3d(x, y) - a * 0.5, a)
        loc, n = cache[k]
        return loc + n * (base + h)
    return F


def frame(n, up=(0, 0, 1)):
    """Rotation whose local Z is n and local Y leans toward `up`."""
    n = Vector(n).normalized()
    u = Vector(up)
    u = (u - n * u.dot(n))
    if u.length < 1e-6:
        u = Vector((0, 1, 0)) - n * n.y
    u.normalize()
    x = u.cross(n).normalized()
    return Matrix((x, u, n)).transposed().to_4x4()


def dome(part, p, n, r, h, segs, mat, sink=0.002):
    M = Matrix.Translation(p) @ frame(n)
    prof = [(0.0, h), (r * 0.72, h * 0.80), (r, 0.0), (r * 0.92, -sink), (0.0, -sink)]
    return part.lathe(prof, segs, mat, matrix=M)


def loft(part, path, sections, mat, up=(0, 0, 1), cap0=True, tip=None):
    """Sweep per-point cross-sections [(side, up), ...] along a polyline; fan / pole caps."""
    P = [Vector(p) for p in path]
    n = len(P)
    T = []
    for i in range(n):
        if i == 0:
            d = P[1] - P[0]
        elif i == n - 1:
            d = P[-1] - P[-2]
        else:
            d = (P[i + 1] - P[i]).normalized() + (P[i] - P[i - 1]).normalized()
        T.append(d.normalized())
    u0 = Vector(up)
    u0 = (u0 - T[0] * u0.dot(T[0])).normalized()
    U = [u0]
    for i in range(1, n):
        u = U[-1] - T[i] * U[-1].dot(T[i])
        U.append(u.normalized())
    rings = []
    for i in range(n):
        t, u = T[i], U[i]
        s = u.cross(t).normalized()
        rings.append([P[i] + s * a + u * b for (a, b) in sections[i]])
    c0 = sum(rings[0], Vector()) / len(rings[0])
    c1 = Vector(tip) if tip is not None else sum(rings[-1], Vector()) / len(rings[-1])
    return part.grid(rings, mat, True, c0, c1)


def arch(w, h, n=8, flat=0.0, e=0.8):
    """Closed D-section: rounded top arch of half-width w, height h, flat-ish bottom."""
    pts = []
    for k in range(n + 1):
        a = pi * k / n
        c, s = cos(a), sin(a)
        pts.append((w * math.copysign(abs(c) ** e, c), h * (abs(s) ** e)))
    pts.append((-w * 0.92, -flat))
    pts.append((w * 0.92, -flat))
    return pts[::-1]


def ell(w, h, n=10, e=0.9, y0=0.0):
    out = []
    for k in range(n):
        a = 2 * pi * k / n
        c, s = cos(a), sin(a)
        out.append((w * math.copysign(abs(c) ** e, c), y0 + h * math.copysign(abs(s) ** e, s)))
    return out


# ---------------------------------------------------------------------------- figure
class Fig:
    """Landmarks of a nominal 1.70 m figure; everything is scaled to the target height after."""

    def __init__(self, v):
        self.v = v
        self.p = C.Part()
        sh = v['sh']
        self.head_c = Vector((0.0, 0.006, 1.588))
        self.head_r = (0.079, 0.091, 0.108)
        self.shoulder = [Vector((sx * (sh - 0.016), 0.004, 1.372)) for sx in (1, -1)]
        self.elbow = [Vector((sx * (sh + 0.026), 0.030, 1.102)) for sx in (1, -1)]
        self.wrist = [Vector((sx * (sh + 0.036), -0.004, 0.862)) for sx in (1, -1)]
        self.hipj = [Vector((sx * 0.086, 0.0, 0.880)) for sx in (1, -1)]
        self.knee = [Vector((sx * 0.092, -0.014, 0.482)) for sx in (1, -1)]
        self.ankle = [Vector((sx * 0.097, 0.006, 0.104)) for sx in (1, -1)]


def torso_sections(f, coat=False):
    v = f.v
    sh, hip, waist, chest, belly = v['sh'], v['hip'], v['waist'], v['chest'], v['belly']

    def sl(z, yf, yb, hw):
        return (z, yf, yb, hw)
    secs = [sl(0.790, -0.098, 0.096, hip * 0.97), sl(0.860, -0.106, 0.104, hip),
            sl(0.945, -0.102 - belly * 0.6, 0.098, waist * 1.04),
            sl(1.020, -0.100 - belly, 0.094, waist), sl(1.100, -0.106 - belly * 0.7, 0.098, waist * 1.07),
            sl(1.200, -chest, 0.104, sh * 0.93), sl(1.300, -chest * 0.95, 0.102, sh * 0.99),
            sl(1.368, -0.098, 0.090, sh), sl(1.412, -0.076, 0.072, sh * 0.80),
            sl(1.442, -0.054, 0.052, 0.066), sl(1.458, -0.047, 0.046, 0.054)]
    if coat:
        # long coat: flares down to the knee
        secs = [sl(0.560, -0.122, 0.118, hip * 1.20), sl(0.660, -0.116, 0.114, hip * 1.13),
                sl(0.760, -0.110, 0.108, hip * 1.05)] + secs[1:]
    return secs


def build_torso(f, coat=False):
    """Torso loft: trousers below the waist, top above. Returns (faces, sections)."""
    v = f.v
    tp = C.Part()
    secs = torso_sections(f, coat)
    nu = 26
    faces = C.loft_z(tp, secs, nu, v['top'], n=2.5)
    if not coat:
        tp.assign(faces[0:2 * nu], v['pants'])
        if v['style'] == 'quiff':
            tp.assign(faces[nu:2 * nu], v['trim'])          # ribbed jacket hem band
    return tp, secs


def build_legs(f):
    p = f.p
    v = f.v
    for i, sx in enumerate((1, -1)):
        H, K, A = f.hipj[i], f.knee[i], f.ankle[i]
        pts = C.spline3([H + Vector((0, 0, 0.03)), H.lerp(K, 0.5) + Vector((0, -0.004, 0)), K,
                         K.lerp(A, 0.45) + Vector((0, 0.008, 0)), A + Vector((0, 0, 0.022))], 2)
        rad = C.resample([0.082, 0.068, 0.059, 0.061, 0.054], len(pts))
        p.tube(pts, rad, 12, v['pants'], caps='round', cap_segs=1, scale_xy=(1.0, 0.94),
               up=(0, -1, 0))
        # trouser hem / jogger cuff
        Mh = Matrix.Translation(A + Vector((0, 0, 0.030)))
        if v['style'] == 'quiff':
            p.lathe([(0.0, -0.008), (0.050, -0.008), (0.053, -0.004), (0.053, 0.014),
                     (0.050, 0.018), (0.0, 0.018)], 12, v['trim'], matrix=Mh)
        else:
            p.torus(0.055, 0.005, 12, 4, v['pants'], matrix=Mh @ Matrix.Translation((0, 0, -0.004)))


def build_shoes(f):
    p = f.p
    v = f.v
    for i, sx in enumerate((1, -1)):
        A = f.ankle[i]
        cx, cy = A.x + sx * 0.004, A.y
        # sole (rubber), foot-shaped outline
        ol = catmull([(0.0, 0.070), (-0.036, 0.052), (-0.042, -0.040), (-0.048, -0.120),
                      (-0.036, -0.185), (0.0, -0.205), (0.034, -0.190), (0.050, -0.125),
                      (0.044, -0.040), (0.036, 0.052)], 2)
        ol = [(x * sx, y) for (x, y) in ol]
        if sx < 0:
            ol = ol[::-1]
        plate(p, ol, lambda x, y, h, cx=cx, cy=cy: Vector((cx + x, cy + y, h)), 0.026,
              RUBBER, bevel=0.006)
        # upper: lofted from heel to toe
        path, secs = [], []
        for (yy, w, h) in ((0.062, 0.030, 0.070), (0.040, 0.040, 0.096), (0.004, 0.043, 0.104),
                           (-0.040, 0.046, 0.090), (-0.090, 0.049, 0.070), (-0.135, 0.047, 0.056),
                           (-0.170, 0.040, 0.046), (-0.192, 0.026, 0.036)):
            path.append(Vector((cx + sx * 0.003, cy + yy, 0.022)))
            secs.append(arch(w, h, 8, 0.0, 0.85))
        vr, fs = loft(p, path, secs, v['shoe'], up=(0, 0, 1),
                      tip=Vector((cx + sx * 0.003, cy - 0.200, 0.035)))
        nsec = len(secs[0])
        p.assign(fs[5 * nsec:7 * nsec], v['shoe2'])        # toe cap
        p.assign(fs[7 * nsec + nsec:], v['shoe2'])          # toe tip fan
        # laces: three bars across the instep, plus a heel tab
        prof = [(0.004, 0.104), (-0.040, 0.090), (-0.090, 0.070), (-0.135, 0.056)]

        def top_h(yy):
            for (y0, h0), (y1, h1) in zip(prof, prof[1:]):
                if y1 <= yy <= y0:
                    return h0 + (h1 - h0) * (y0 - yy) / (y0 - y1)
            return prof[-1][1]
        for k, yy in enumerate((-0.026, -0.050, -0.074)):
            z = 0.022 + top_h(yy) - 0.0008
            M = Matrix.Translation((cx + sx * 0.003, cy + yy, z)) @ Matrix.Rotation(radians(-16), 4, 'X')
            p.box(Vector((0, 0, 0)), (0.040, 0.007, 0.005), v['shoe2'] if v['shoe2'] != v['shoe'] else PEARL,
                  matrix=M)
        p.box(Vector((cx + sx * 0.003, cy + 0.066, 0.070)), (0.020, 0.008, 0.030), v['shoe2'])


def build_arms(f, hold=None):
    """Sleeves with cuffs; returns the hand frames (wrist point, down, palm normal)."""
    p = f.p
    v = f.v
    hands = []
    for i, sx in enumerate((1, -1)):
        S, E, W = f.shoulder[i], f.elbow[i], f.wrist[i]
        if hold is not None and sx == hold['side']:
            E = E + hold.get('elbow', Vector())
            W = hold['wrist']
        pts = C.spline3([S + Vector((-sx * 0.010, 0, 0.012)), S.lerp(E, 0.5) + Vector((sx * 0.004, 0, 0)),
                         E, E.lerp(W, 0.5), W + (W - E).normalized() * 0.010], 2)
        rad = C.resample([0.060, 0.054, 0.048, 0.045, 0.042], len(pts))
        p.tube(pts, rad, 12, v['top'], caps='round', cap_segs=1, up=(0, -1, 0))
        # cuff
        d = (W - E).normalized()
        Mc = Matrix.Translation(W - d * 0.004) @ d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        p.lathe([(0.0, -0.020), (0.043, -0.020), (0.046, -0.016), (0.046, 0.006), (0.043, 0.010),
                 (0.0, 0.010)], 12, v['trim'], matrix=Mc)
        hands.append((W + d * 0.012, d, Vector((-sx, 0, 0)), sx))
    return hands


def build_hand(p, wrist, down, palm_n, sx, skin, fist=False):
    """Palm block, four fingers and a thumb; palm faces palm_n, fingers hang along `down`."""
    z = down.normalized()
    xn = (palm_n - z * palm_n.dot(z)).normalized()          # palm normal (inward)
    yv = z.cross(xn).normalized()                             # across the knuckles
    if yv.y > 0:
        yv = -yv                                              # index finger toward the front

    def W(a, b, c):
        return wrist + xn * a + yv * b + z * c
    M = Matrix((xn, yv, z)).transposed().to_4x4()
    M.translation = W(-0.004, 0.002, 0.042)
    p.superellipsoid(Vector((0, 0, 0)), (0.017, 0.040, 0.046), 0.7, 0.7, 10, 8, skin, matrix=M)
    for k, (yy, L) in enumerate(((0.026, 0.066), (0.009, 0.072), (-0.008, 0.068), (-0.024, 0.056))):
        base = W(0.000, yy, 0.080)
        if fist:
            pts = [base, W(0.016, yy, 0.098), W(0.034, yy, 0.084), W(0.034, yy * 0.95, 0.064)]
        else:
            pts = [base, W(0.006, yy * 1.05, 0.080 + L * 0.5), W(0.018, yy * 1.08, 0.078 + L * 0.95)]
        p.tube(pts, 0.0090 if k < 3 else 0.0080, 7, skin, caps='round', cap_segs=1,
               scale_xy=(1.0, 0.86), up=tuple(xn))
    tb = [W(0.008, 0.034, 0.030), W(0.020, 0.048, 0.058), W(0.026 if fist else 0.024, 0.046, 0.082)]
    p.tube(tb, 0.0105, 7, skin, caps='round', cap_segs=1, up=tuple(xn))


# ---------------------------------------------------------------------------- head
def build_head(f):
    v = f.v
    p = f.p
    hc = f.head_c
    rx, ry, rz = f.head_r

    def shape(q):
        # q is relative to the head centre: narrow jaw, chin forward, flatter face
        t = smoothstep(0.01, -0.10, q.z)
        q = Vector((q.x * (1.0 - 0.20 * t), q.y, q.z))
        if q.y < 0:
            q.y = q.y * (1.0 - 0.06 * smoothstep(0.03, -0.06, q.z)) - 0.006 * t
        return q
    hp = C.Part()
    hp.superellipsoid(Vector((0, 0, 0)), (rx, ry, rz), 0.92, 0.95, 24, 18, v['skin'],
                      matrix=Matrix.Translation(hc), deform=shape)
    surf = Surf(hp.bm)
    f.head_shape = shape
    return hp, surf


def face(f, surf, mouth=True):
    v = f.v
    p = f.p
    hc = f.head_c
    ey = hc.z - 0.006
    up = Vector((0, 0, 1))
    for sx in (1, -1):
        loc, n = surf.ray(Vector((sx * 0.031, -0.4, ey)), Vector((0, 1, 0)))
        M = Matrix.Translation(loc - n * 0.0012) @ frame(n)
        p.superellipsoid(Vector((0, 0, 0)), (0.0088, 0.0128, 0.0052), 0.9, 0.9, 10, 6, INK, matrix=M)
        side = n.cross(up).normalized()
        cl = loc + n * 0.0030 + up * 0.0040 - side * sx * 0.0024
        p.superellipsoid(Vector((0, 0, 0)), (0.0024, 0.0026, 0.0013), 1.0, 1.0, 6, 4, PEARL,
                         matrix=Matrix.Translation(cl) @ frame(n))
        # brows
        bp = []
        for (bx, bz) in ((0.017, 0.023), (0.031, 0.029), (0.045, 0.024)):
            l2, n2 = surf.ray(Vector((sx * bx, -0.4, ey + bz)), Vector((0, 1, 0)))
            bp.append(l2 + n2 * 0.0016)
        p.tube(bp, 0.0030, 6, v['hair'], caps='round', cap_segs=1, scale_xy=(0.65, 1.0),
               up=(0, -1, 0))
        # ears
        loc, n = surf.ray(Vector((sx * 0.3, 0.012, hc.z - 0.016)), Vector((-sx, 0, 0)))
        M = Matrix.Translation(loc + n * 0.003) @ frame(n, (0, 0.25, 1))
        p.superellipsoid(Vector((0, 0, 0)), (0.0135, 0.0255, 0.0085), 0.9, 0.9, 10, 6, v['skin'],
                         matrix=M)
        p.superellipsoid(Vector((0.0015, 0.0, 0.0040)), (0.0070, 0.0150, 0.0040), 0.9, 0.9, 8, 4,
                         v['skin'], matrix=M)
    # nose
    loc, n = surf.ray(Vector((0, -0.4, hc.z - 0.034)), Vector((0, 1, 0)))
    M = Matrix.Translation(loc + n * 0.004) @ frame(n)
    p.superellipsoid(Vector((0, 0, 0)), (0.0115, 0.0130, 0.0120), 0.85, 0.85, 10, 7, v['skin'],
                     matrix=M)
    if mouth:
        mp = []
        for (mx, mz) in ((-0.015, 0.004), (-0.008, -0.0005), (0.0, -0.0018), (0.008, -0.0005),
                         (0.015, 0.004)):
            l2, n2 = surf.ray(Vector((mx, -0.4, hc.z - 0.064 + mz)), Vector((0, 1, 0)))
            mp.append(l2 + n2 * 0.0008)
        p.tube(mp, 0.0019, 5, 'SKY_Terracotta', caps='round', cap_segs=1)


def hair_shell(p, hc, radii, thick, region, mat, nu=24, nv=18, extra=None, shape=None):
    """Closed shell a little bigger than the head; outside `region` (weight 0..1 of a unit
    direction) it shrinks under the scalp, so the visible hair ends on a clean hairline."""
    rx, ry, rz = radii

    def dfm(q):
        u = Vector((q.x / (rx + thick), q.y / (ry + thick), q.z / (rz + thick)))
        if shape is not None:
            q = shape(q)
        w = region(u)
        k = lerp(0.84, 1.0, w)
        q = q * k
        if extra:
            q = extra(q, u, w)
        return q
    return p.superellipsoid(Vector((0, 0, 0)), (rx + thick, ry + thick, rz + thick), 0.92, 0.95,
                            nu, nv, mat, matrix=Matrix.Translation(hc), deform=dfm)


def hairline(front, side, back, soft=0.06):
    def region(u):
        th = atan2(u.x, -u.y)                 # 0 front .. pi back
        c = cos(th)
        h = side + (front - side) * max(0.0, c) + (back - side) * max(0.0, -c)
        return smoothstep(h - soft, h + soft, u.z)
    return region


def build_hair(f, surf):
    v = f.v
    p = f.p
    hc = f.head_c
    r = f.head_r
    st = v['style']
    if st == 'quiff':
        def extra(q, u, w):
            # volume on top, swept up at the front
            lift = w * smoothstep(0.2, 0.9, u.z) * 0.010
            fr = w * smoothstep(-0.2, -0.85, u.y) * smoothstep(0.25, 0.75, u.z) * 0.012
            return q + Vector((0, -fr * 0.4, lift + fr))
        hair_shell(p, hc, r, 0.0085, hairline(0.40, -0.02, -0.52), v['hair'], extra=extra,
                   shape=f.head_shape)
        # quiff tufts swept up and back from the front hairline
        for k, (x, s_) in enumerate(((-0.030, 0.85), (-0.004, 1.0), (0.022, 0.92))):
            c = hc + Vector((x, -0.058, 0.084))
            M = Matrix.Translation(c) @ Matrix.Rotation(radians(-32), 4, 'X') @ \
                Matrix.Rotation(radians(x * 260), 4, 'Y')
            p.superellipsoid(Vector((0, 0, 0)), (0.024 * s_, 0.034 * s_, 0.017 * s_), 0.8, 0.8,
                             10, 7, v['hair'], matrix=M)
    elif st == 'bun':
        def extra(q, u, w):
            # soft centre part + volume at the sides
            part = w * math.exp(-(u.x / 0.06) ** 2) * smoothstep(0.3, 0.9, u.z) * smoothstep(0.2, -0.6, u.y)
            side = w * smoothstep(0.5, 0.95, abs(u.x)) * smoothstep(-0.3, 0.3, u.z) * 0.006
            return q * (1.0 - 0.020 * part) + Vector((math.copysign(side, u.x), 0, 0))
        hair_shell(p, hc, r, 0.0090, hairline(0.44, -0.08, -0.48), v['hair'], extra=extra,
                   shape=f.head_shape)
        bc = hc + Vector((0.0, 0.078, 0.070))
        p.superellipsoid(bc, (0.046, 0.042, 0.044), 0.9, 0.9, 14, 10, v['hair'])
        Mt = Matrix.Translation(hc + Vector((0, 0.058, 0.060))) @ Matrix.Rotation(radians(62), 4, 'X')
        p.torus(0.033, 0.0055, 16, 5, v['trim'], matrix=Mt)
        # side-swept fringe locks
        for sx in (1, -1):
            c = hc + Vector((sx * 0.050, -0.060, 0.060))
            M = Matrix.Translation(c) @ Matrix.Rotation(radians(sx * 28), 4, 'Y') @ \
                Matrix.Rotation(radians(-20), 4, 'X')
            p.superellipsoid(Vector((0, 0, 0)), (0.028, 0.018, 0.020), 0.85, 0.85, 10, 6,
                             v['hair'], matrix=M)
    elif st == 'cap':
        # short grey hair round the sides and back, under the cap
        hair_shell(p, hc, r, 0.0055, hairline(0.30, -0.06, -0.50), v['hair'], shape=f.head_shape)
        # short beard along the jaw, rising to the sideburns, and a moustache
        def beard(u):
            th = abs(atan2(u.x, -u.y))
            b = -0.66 + 0.58 * (1.0 - cos(min(th, pi / 2)))
            return smoothstep(b + 0.05, b - 0.05, u.z) * smoothstep(1.95, 1.60, th)

        def bextra(q, u, w):
            return q + Vector((0, -0.003 * w, -0.005 * w * smoothstep(-0.7, -0.95, u.z)))
        hair_shell(p, hc, r, 0.0068, beard, v['hair'], extra=bextra, shape=f.head_shape)
        mp = []
        for (mx, mz) in ((-0.022, -0.006), (-0.011, 0.0), (0.0, 0.0015), (0.011, 0.0), (0.022, -0.006)):
            l2, n2 = surf.ray(Vector((mx, -0.4, hc.z - 0.049 + mz)), Vector((0, 1, 0)))
            mp.append(l2 + n2 * 0.0035)
        p.tube(mp, [0.0036, 0.0050, 0.0054, 0.0050, 0.0036], 7, v['hair'], caps='round',
               cap_segs=1, scale_xy=(1.0, 0.75), up=(0, -1, 0.3))
        # flat cap: crown dome, brim, top button
        def capreg(u):
            return smoothstep(0.18, 0.32, u.z + 0.25 * max(0.0, -u.y) * 0.0)

        def cextra(q, u, w):
            # flatten the crown and push it slightly forward
            return Vector((q.x * 1.02, q.y - 0.006 * w, q.z * (1.0 - 0.10 * w * smoothstep(0.5, 1.0, u.z))))
        hair_shell(p, hc + Vector((0, 0.004, 0.010)), r, 0.0130, capreg, INK, extra=cextra,
                   shape=f.head_shape)
        brim = catmull([(-0.078, 0.000), (-0.060, -0.040), (0.0, -0.058), (0.060, -0.040),
                        (0.078, 0.000), (0.0, 0.012)], 3)
        Mb = Matrix.Translation(hc + Vector((0, -0.062, 0.048))) @ Matrix.Rotation(radians(10), 4, 'X')
        plate(p, brim, lambda x, y, h, Mb=Mb: Mb @ Vector((x, y, h)), 0.007, INK, bevel=0.0025)
        p.superellipsoid(hc + Vector((0, 0.004, 0.112)), (0.010, 0.010, 0.006), 1.0, 1.0, 8, 4, INK)


# ---------------------------------------------------------------------------- clothing details
def jacket_details(f, tsurf):
    """passenger_a: hood rolled behind the neck, zip, drawstrings, kangaroo pocket, hem band."""
    v = f.v
    p = f.p
    top = v['top']
    # hood: a soft roll round the back of the neck
    Mh = Matrix.Translation((0, 0.020, 1.425)) @ Matrix.Rotation(radians(-12), 4, 'X')
    vr, fs = p.torus(0.080, 0.028, 18, 8, top, matrix=Mh, scale_minor=(1.0, 0.9))
    # zip line + pull
    zp = []
    for z in (1.415, 1.32, 1.20, 1.08, 0.96, 0.905):
        loc, n = tsurf.ray(Vector((0.0, -0.5, z)), Vector((0, 1, 0)))
        zp.append(loc + n * 0.003)
    p.tube(zp, 0.0040, 4, v['trim'], caps='flat')
    loc, n = tsurf.ray(Vector((0.0, -0.5, 1.385)), Vector((0, 1, 0)))
    p.box(loc + n * 0.008 - Vector((0, 0, 0.012)), (0.010, 0.005, 0.024), BRASS)
    # drawstrings
    for sx in (1, -1):
        loc, n = tsurf.ray(Vector((sx * 0.040, -0.5, 1.400)), Vector((0, 1, 0)))
        a = loc + n * 0.006
        p.tube([a, a + Vector((sx * 0.004, -0.004, -0.060)), a + Vector((sx * 0.006, -0.006, -0.110))],
               0.0040, 5, PEARL, caps='round', cap_segs=1)
        p.superellipsoid(a + Vector((sx * 0.006, -0.008, -0.116)), (0.0065, 0.0065, 0.010), 1.0, 1.0,
                         6, 4, BRASS)
    # kangaroo pocket
    out = [(-0.085, 0.0), (0.085, 0.0), (0.072, 0.105), (-0.072, 0.105)]
    out = densify(out, 0.02)
    plate(p, out, conform(tsurf, lambda x, y: Vector((x, -0.5, 0.955 + y)), -0.001, (0, 1, 0)),
          0.006, top, bevel=0.0025, fill=1, fill_to=0.02)


def shirt_details(f, tsurf):
    """passenger_b: pearl collar, button placket, chest pocket, belt with brass buckle."""
    v = f.v
    p = f.p
    for sx in (1, -1):
        out = ccw([(0.0, 0.0), (sx * 0.060, 0.010), (sx * 0.074, -0.030), (sx * 0.010, -0.058)])
        F = conform(tsurf, lambda x, y: Vector((x, -0.5, 1.448 + y)), 0.001, (0, 1, 0.55))
        plate(p, out, F, 0.006, v['trim'], bevel=0.0022)
    # placket + buttons
    pl = densify(rounded_rect(0.028, 0.30, 0.006, 2), 0.04)
    plate(p, pl, conform(tsurf, lambda x, y: Vector((x, -0.5, 1.250 + y)), -0.001, (0, 1, 0)),
          0.004, v['top'], bevel=0.0018, fill=1, fill_to=0.008)
    for z in (1.360, 1.270, 1.180, 1.090):
        loc, n = tsurf.ray(Vector((0.0, -0.5, z)), Vector((0, 1, 0)))
        dome(p, loc + n * 0.004, n, 0.0060, 0.0030, 8, PEARL)
    # chest pocket with a flap
    out = densify(rounded_rect(0.070, 0.080, 0.008, 2), 0.03)
    Fp = conform(tsurf, lambda x, y: Vector((0.082 + x, -0.5, 1.255 + y)), -0.001, (0, 1, 0))
    plate(p, out, Fp, 0.004, v['top'], bevel=0.0018, fill=1, fill_to=0.015)
    out = densify([(-0.038, -0.012), (0.038, -0.012), (0.038, 0.008), (-0.038, 0.008)], 0.03)
    Ff = conform(tsurf, lambda x, y: Vector((0.082 + x, -0.5, 1.290 + y)), 0.003, (0, 1, 0))
    plate(p, out, Ff, 0.005, v['top'], bevel=0.0018)


def belt(f, tsurf, z, mat, buckle=BRASS):
    p = f.p
    s0 = torso_sections(f)
    # belt band: a slightly inflated slice of the torso round z

    def at(zz):
        for a, b in zip(s0, s0[1:]):
            if a[0] <= zz <= b[0]:
                t = (zz - a[0]) / (b[0] - a[0])
                return tuple(lerp(a[i], b[i], t) for i in range(4))
        return s0[0]
    bands = []
    for (zz, grow) in ((z - 0.022, 0.003), (z - 0.018, 0.007), (z + 0.018, 0.007), (z + 0.022, 0.003)):
        zz_, yf, yb, hw = at(zz)
        bands.append((zz, yf - grow, yb + grow, hw + grow))
    C.loft_z(p, bands, 26, mat, n=2.5)
    loc, n = tsurf.ray(Vector((0.0, -0.5, z)), Vector((0, 1, 0)))
    M = Matrix.Translation(loc + n * 0.008) @ frame(n)
    p.rbox(Vector((0, 0, 0)), (0.058, 0.040, 0.008), 0.004, 1, buckle, matrix=M)
    p.box(Vector((0, 0, 0.0035)), (0.040, 0.022, 0.004), mat, matrix=M)


def coat_details(f, tsurf):
    """passenger_c: lapels, double row of brass buttons, belt with buckle, flap pockets."""
    v = f.v
    p = f.p
    for sx in (1, -1):
        out = densify(ccw([(0.0, 0.0), (sx * 0.070, -0.010), (sx * 0.090, -0.060),
                           (sx * 0.030, -0.200)]), 0.03)
        F = conform(tsurf, lambda x, y: Vector((x, -0.5, 1.430 + y)), 0.0005, (0, 1, 0.25))
        plate(p, out, F, 0.006, v['top'], bevel=0.0024, fill=1, fill_to=0.010)
        for z in (1.180, 1.080, 0.760, 0.680):
            loc, n = tsurf.ray(Vector((sx * 0.050, -0.5, z)), Vector((0, 1, 0)))
            dome(p, loc + n * 0.002, n, 0.0085, 0.0040, 8, BRASS)
        # flap pockets on the skirt of the coat
        out = densify([(-0.050, -0.010), (0.050, -0.010), (0.046, 0.012), (-0.046, 0.012)], 0.025)
        Fp = conform(tsurf, lambda x, y: Vector((sx * 0.100 + x, -0.5, 0.820 + y)), 0.0005, (0, 1, 0))
        plate(p, out, Fp, 0.006, v['top'], bevel=0.0022)
    belt(f, tsurf, 1.000, v['trim'], buckle=BRASS)


# ---------------------------------------------------------------------------- accessories
def backpack(f):
    v = f.v
    p = f.p
    m = v['acc_mat']
    c = Vector((0.0, 0.166, 1.120))
    tilt = Matrix.Rotation(radians(6), 4, 'X')
    M = Matrix.Translation(c) @ tilt
    p.rbox(Vector((0, 0, 0)), (0.270, 0.130, 0.380), 0.050, 3, m, matrix=M)
    # top flap / lid
    p.rbox(Vector((0.0, 0.004, 0.170)), (0.262, 0.138, 0.060), 0.030, 2, m, matrix=M)
    # front pocket with zip
    p.rbox(Vector((0.0, 0.070, -0.075)), (0.200, 0.040, 0.160), 0.030, 2, m, matrix=M)
    p.box(Vector((0.0, 0.091, -0.012)), (0.150, 0.004, 0.006), INK, matrix=M)
    p.box(Vector((0.055, 0.094, -0.022)), (0.010, 0.004, 0.022), BRASS, matrix=M)
    # side pockets
    for sx in (1, -1):
        p.rbox(Vector((sx * 0.140, 0.010, -0.090)), (0.030, 0.090, 0.150), 0.014, 2, m, matrix=M)
    # grab handle
    p.tube([M @ Vector((-0.040, -0.030, 0.196)), M @ Vector((0.0, -0.032, 0.226)),
            M @ Vector((0.040, -0.030, 0.196))], 0.008, 6, INK, caps='round', cap_segs=1)
    # shoulder straps with sliders + chest strap with a buckle
    for sx in (1, -1):
        pts = [Vector((sx * 0.100, 0.130, 1.310)), Vector((sx * 0.112, 0.060, 1.428)),
               Vector((sx * 0.120, -0.040, 1.420)), Vector((sx * 0.124, -0.118, 1.330)),
               Vector((sx * 0.128, -0.132, 1.200)), Vector((sx * 0.130, -0.122, 1.060)),
               Vector((sx * 0.132, 0.020, 0.960)), Vector((sx * 0.112, 0.120, 0.960))]
        p.tube(C.spline3(pts, 2), 0.012, 6, INK, caps='round', cap_segs=1, scale_xy=(2.0, 0.55),
               up=(0, 0, 1))
        p.box(Vector((sx * 0.129, -0.132, 1.150)), (0.036, 0.012, 0.016), BRASS)
    p.tube([Vector((-0.120, -0.136, 1.240)), Vector((0.0, -0.144, 1.244)), Vector((0.120, -0.136, 1.240))],
           0.007, 5, INK, caps='round', cap_segs=1, scale_xy=(2.0, 0.6), up=(0, -1, 0))
    p.rbox(Vector((0.0, -0.148, 1.244)), (0.038, 0.012, 0.024), 0.004, 1, BRASS)


def suitcase(f, hand_pt):
    """Teal rolling case beside the right hip, tilted onto its wheels, handle in the hand."""
    v = f.v
    p = f.p
    m = v['acc_mat']
    wheel_base = Vector((-0.300, 0.150, 0.0))
    tilt = radians(-24)                                 # leans toward the figure's hand
    W, D, Hh = 0.200, 0.380, 0.560                      # thickness (x), width (y), height (z)
    M = Matrix.Translation(wheel_base + Vector((0, 0, 0.032))) @ Matrix.Rotation(tilt, 4, 'Y')
    # shell with ribs, corner guards and a zip seam
    p.rbox(Vector((0, 0, Hh / 2 + 0.010)), (W, D, Hh), 0.045, 3, m, matrix=M)
    for yy in (-0.110, -0.036, 0.036, 0.110):
        p.rbox(Vector((-W / 2 - 0.002, yy, Hh / 2 + 0.010)), (0.012, 0.024, Hh - 0.090), 0.006, 1, m,
               matrix=M)
        p.rbox(Vector((W / 2 + 0.002, yy, Hh / 2 + 0.010)), (0.012, 0.024, Hh - 0.090), 0.006, 1, m,
               matrix=M)
    p.box(Vector((0, 0, Hh / 2 + 0.010)), (W + 0.004, D + 0.004, 0.010), INK, matrix=M)
    for sy in (-1, 1):
        for sz in (0, 1):
            p.rbox(Vector((0, sy * (D / 2 - 0.018), 0.030 + sz * (Hh - 0.040))), (W + 0.010, 0.044, 0.044),
                   0.012, 1, INK, matrix=M)
    # wheels (rubber) with metal hubs on the back edge
    for sy in (-1, 1):
        Mw = M @ Matrix.Translation((0.0, sy * (D / 2 - 0.040), 0.000)) @ Matrix.Rotation(radians(90), 4, 'Y')
        vr, fs = p.lathe([(0.0, -0.016), (0.026, -0.016), (0.032, -0.010), (0.032, 0.010),
                          (0.026, 0.016), (0.0, 0.016)], 14, RUBBER, matrix=Mw)
        p.cylinder(0.012, 0.036, 8, METAL, matrix=Mw @ Matrix.Translation((0, 0, -0.018)))
    # telescopic handle: two stages of twin tubes up to a grip bar in the hand
    top_local = M.inverted() @ hand_pt
    for sy in (-1, 1):
        y = sy * 0.070
        a = Vector((0.0, y, Hh - 0.040))
        b = Vector((0.0, y, Hh + 0.120))
        c = Vector((top_local.x, y, top_local.z - 0.010))
        p.tube([M @ a, M @ b], 0.0095, 8, METAL, caps='flat')
        p.tube([M @ b, M @ c], 0.0075, 8, METAL, caps='flat')
        p.torus(0.0105, 0.0030, 8, 4, INK, matrix=M @ Matrix.Translation(b))
    gl = Vector((top_local.x, -0.080, top_local.z))
    gr = Vector((top_local.x, 0.080, top_local.z))
    p.tube([M @ gl, M @ gr], 0.0140, 10, INK, caps='round', cap_segs=2)
    # carry handle on top
    p.tube([M @ Vector((0.0, -0.060, Hh + 0.012)), M @ Vector((0.0, -0.040, Hh + 0.040)),
            M @ Vector((0.0, 0.040, Hh + 0.040)), M @ Vector((0.0, 0.060, Hh + 0.012))],
           0.0090, 6, INK, caps='round', cap_segs=1)
    return M


def scarf(f):
    v = f.v
    p = f.p
    m = v['acc_mat']
    Mt = Matrix.Translation((0.0, 0.002, 1.445)) @ Matrix.Rotation(radians(-8), 4, 'X')
    p.torus(0.070, 0.026, 20, 8, m, matrix=Mt, scale_minor=(1.0, 1.15))
    p.torus(0.060, 0.020, 20, 7, m, matrix=Matrix.Translation((0.0, -0.002, 1.478)) @
            Matrix.Rotation(radians(-14), 4, 'X'))
    for (x0, L, tw) in ((0.030, 0.230, 6.0), (0.058, 0.180, -8.0)):
        pts = [Vector((x0, -0.070, 1.430)), Vector((x0 + 0.006, -0.112, 1.350)),
               Vector((x0 + 0.010, -0.122, 1.430 - L * 0.75)), Vector((x0 + 0.012, -0.118, 1.430 - L))]
        vr, fs = p.tube(pts, 0.024, 8, m, caps='flat', scale_xy=(1.5, 0.45), up=(0, -1, 0))
        # fringe at the end
        for k in range(5):
            xx = x0 + 0.012 + (k - 2) * 0.0085
            p.tube([Vector((xx, -0.118, 1.432 - L)), Vector((xx, -0.118, 1.410 - L))], 0.0028, 4, m,
                   caps='round', cap_segs=1)


def glasses(f, surf):
    p = f.p
    hc = f.head_c
    ey = hc.z - 0.006
    rims = []
    for sx in (1, -1):
        loc, n = surf.ray(Vector((sx * 0.031, -0.4, ey)), Vector((0, 1, 0)))
        c = loc + n * 0.013
        M = Matrix.Translation(c) @ frame(n)
        p.torus(0.0185, 0.0018, 18, 4, BRASS, matrix=M)
        rims.append((c, n))
        # temple arm back to the ear
        l2, n2 = surf.ray(Vector((sx * 0.3, 0.000, ey + 0.002)), Vector((-sx, 0, 0)))
        p.tube([c + Vector((sx * 0.0185, 0, 0)), l2 + n2 * 0.006 + Vector((0, -0.020, 0)),
                l2 + n2 * 0.004 + Vector((0, 0.010, -0.010))], 0.0016, 4, BRASS, caps='round',
               cap_segs=1)
    (c0, n0), (c1, n1) = rims
    mid = (c0 + c1) / 2 + Vector((0, -0.002, 0.004))
    p.tube([c0 + Vector((-0.0185, 0, 0.002)), mid, c1 + Vector((0.0185, 0, 0.002))], 0.0016, 4, BRASS,
           caps='round', cap_segs=1)


def shoulder_bag(f, tsurf):
    v = f.v
    p = f.p
    m = 'SKY_Coral'
    c = Vector((0.205, -0.020, 0.900))
    M = Matrix.Translation(c) @ Matrix.Rotation(radians(-8), 4, 'Y')
    p.rbox(Vector((0, 0, 0)), (0.070, 0.240, 0.180), 0.040, 3, m, matrix=M)
    p.rbox(Vector((0.020, 0.0, 0.040)), (0.040, 0.244, 0.110), 0.030, 2, m, matrix=M)
    p.rbox(Vector((0.041, 0.0, -0.004)), (0.006, 0.040, 0.026), 0.003, 1, BRASS, matrix=M)
    # strap across the body from the right shoulder to the bag
    def on(x, z, front, off=0.010):
        loc, n = tsurf.ray(Vector((x, -0.5 if front else 0.5, z)), Vector((0, 1 if front else -1, 0)))
        return loc + n * off
    pts = [M @ Vector((0.0, -0.100, 0.085)), on(0.140, 1.080, True), on(0.030, 1.250, True),
           on(-0.090, 1.390, True, 0.012), Vector((-0.128, 0.004, 1.438)),
           on(-0.070, 1.330, False), on(0.120, 1.060, False), M @ Vector((0.0, 0.100, 0.085))]
    p.tube(C.spline3(pts, 2), 0.010, 5, m, caps='round', cap_segs=1, scale_xy=(1.9, 0.55),
           up=(0, -1, 0))


# ---------------------------------------------------------------------------- assemble
def figure(name):
    v = VARIANTS[name]
    f = Fig(v)
    p = f.p
    coat = v['acc'] == 'coat'
    tp, secs = build_torso(f, coat)
    tsurf = Surf(tp.bm)
    build_legs(f)
    build_shoes(f)
    hold = None
    if v['acc'] == 'suitcase':
        hold = dict(side=-1, wrist=Vector((-0.255, 0.060, 0.905)), elbow=Vector((-0.010, 0.030, 0.0)))
    hands = build_arms(f, hold)
    for (w, d, pn, sx) in hands:
        fist = hold is not None and sx == hold['side']
        build_hand(p, w, d, pn, sx, v['skin'], fist=fist)
    # neck
    p.lathe([(0.0, 1.400), (0.050, 1.400), (0.048, 1.470), (0.046, 1.540), (0.0, 1.540)], 14,
            v['skin'], matrix=Matrix.Translation((0, 0.012, 0)))
    hp, hsurf = build_head(f)
    face(f, hsurf, mouth=True)
    build_hair(f, hsurf)
    if v['acc'] == 'backpack':
        jacket_details(f, tsurf)
        backpack(f)
    elif v['acc'] == 'suitcase':
        shirt_details(f, tsurf)
        belt(f, tsurf, 0.960, 'SKY_Wood')
        (w, d, pn, sx) = hands[1]
        suitcase(f, w + d * 0.090 + pn * 0.018)
    else:
        coat_details(f, tsurf)
        scarf(f)
        glasses(f, hsurf)
        shoulder_bag(f, tsurf)
    return f, [tp, hp]


def build(name):
    C.reset_scene()
    root = C.new_empty(name, None, (0, 0, 0), size=0.3)
    f, extra = figure(name)
    parts = [f.p] + extra
    # scale the nominal figure to its target height (ground stays at Z 0)
    zmax = max(vv.co.z for prt in parts for vv in prt.bm.verts)
    k = VARIANTS[name]['H'] / zmax
    for prt in parts:
        bmesh.ops.transform(prt.bm, matrix=Matrix.Diagonal((k, k, k, 1.0)), verts=prt.bm.verts)
    temps = [prt.to_temp() for prt in parts]
    body = C.merge_to_object("Body", temps, pivot=(0, 0, 0), parent=root, sharp_deg=50)
    C.bake_ao([body], dist=0.12, samples=40, floor=0.45, ground_z=0.0)
    return root


if __name__ == "__main__":
    for name in VARIANTS:
        root = build(name)
        C.summary(root)
        C.export_fbx(root, os.path.join(C.MODELS, 'Characters', name + '.fbx'))
        if RENDER:
            C.render_previews(name, root, res=(720, 900), samples=96, ground_z=0.0, lens=60,
                              margin=1.15, views=(("fl", 38, 12), ("br", -142, 14)))
