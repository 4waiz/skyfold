"""Passenger figures (passenger_a/b/c) for the SKYFOLD terminal queue.

Original procedural models (Awaiz Ahmed / Team Kanban), not AI-generated. Stylised, friendly,
non-specific people: no likeness of any real person, no brand clothing, no text.
    blender -b --factory-startup -P tools/blender/chars_passengers.py [-- --no-render]

Each FBX:  passenger_x (empty, ground between the feet) > Body (single mesh).
Facing Blender -Y (Unity +Z). ~1.6-1.75 m tall. Palette materials only.

Detail pass: sculpted heads with eyes (catch-lights), brows, nose, smile and ears; hair, cap
and beard built as closed shells whose rings run out to an explicit hairline / beard line and
then dive under the skin (crisp, smooth edges); hands with a thumb and four fingers; collars,
cuffs, zips, buttons, belts, pockets; shoes with soles, toe caps and laces.
passenger_a: hooded zip jacket, joggers, sneakers, quiff, backpack.
passenger_b: shirt with collar and pocket, belt, flat cap, grey hair and beard, upright
             rolling suitcase with wheels and an extended telescopic handle in his hand.
passenger_c: belted double-breasted long coat, scarf, auburn bun, round glasses, shoulder bag.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C
from chars_common import Vector, Matrix, radians, degrees, sin, cos, pi, sqrt, atan2
import bmesh
from mathutils.bvhtree import BVHTree

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS

INK, PEARL, BRASS, RUBBER, METAL = 'SKY_Ink', 'SKY_Pearl', 'SKY_Brass', 'SKY_Rubber', 'SKY_Metal'

VARIANTS = {
    # target height, body build, clothing / skin / hair, accessory
    'passenger_a': dict(H=1.70, sh=0.182, hip=0.156, waist=0.140, chest=0.116, belly=0.0,
                        top='SKY_Teal', trim=INK, pants=INK, skin='SKY_SandstoneDeep',
                        hair=INK, style='quiff', shoe=PEARL, shoe2='SKY_Coral',
                        acc='backpack', acc_mat='SKY_Coral'),
    'passenger_b': dict(H=1.74, sh=0.196, hip=0.164, waist=0.158, chest=0.128, belly=0.016,
                        top='SKY_Coral', trim=PEARL, pants=INK, skin='SKY_Wood',
                        hair=METAL, style='cap', shoe='SKY_Wood', shoe2=INK,
                        acc='suitcase', acc_mat='SKY_Teal'),
    'passenger_c': dict(H=1.63, sh=0.170, hip=0.160, waist=0.134, chest=0.112, belly=0.0,
                        top=PEARL, trim='SKY_TealLight', pants='SKY_Teal',
                        skin='SKY_Sandstone', hair='SKY_Terracotta', style='bun', shoe=INK,
                        shoe2=INK, acc='coat', acc_mat='SKY_TealLight'),
}


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


def ccw(pts):
    """Return the outline counter-clockwise (the inset helper assumes CCW)."""
    n = len(pts)
    a = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
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


def plate(part, outline, F, thick, mat, bevel=0.002, fill=0, fill_to=0.0):
    """Beveled plate from a CCW 2D outline; F(x, y, h) -> world point (h = 0 .. thick).
    fill adds concentric top rings so a plate wrapped on a curved surface stays on it."""
    O = list(outline)
    rings = [(O, 0.0), (O, thick - bevel), (inset2d(O, bevel), thick)]
    for k in range(1, fill + 1):
        rings.append((inset2d(O, bevel + (fill_to - bevel) * k / fill), thick))
    pts = [[F(x, y, h) for (x, y) in r] for (r, h) in rings]
    vr, faces = part.grid(pts, mat, True, 'ngon', 'ngon')
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

    def ray(self, o, d, fallback=None):
        """First hit along d from o; on a miss, the closest point to `fallback` (or to o)."""
        loc, nrm, idx, dist = self.bvh.ray_cast(Vector(o), Vector(d).normalized())
        if loc is None:
            return self.near(o if fallback is None else fallback)
        return loc, self._n(loc, idx)


def conform(surf, to3d, base, axis):
    """F(x, y, h): layout point -> surface hit along axis (+ normal * (base + h))."""
    cache = {}
    a = Vector(axis).normalized()

    def F(x, y, h):
        k = (round(x, 8), round(y, 8))
        if k not in cache:
            cache[k] = surf.ray(to3d(x, y) - a * 0.5, a, to3d(x, y))
        loc, n = cache[k]
        return loc + n * (base + h)
    return F


def frame(n, up=(0, 0, 1)):
    """Rotation whose local Z is n and local Y leans toward `up`."""
    n = Vector(n).normalized()
    u = Vector(up)
    u = u - n * u.dot(n)
    if u.length < 1e-6:
        u = Vector((0, 1, 0)) - n * n.y
    u.normalize()
    x = u.cross(n).normalized()
    return Matrix((x, u, n)).transposed().to_4x4()


def dome(part, p, n, r, h, segs, mat, sink=0.002):
    M = Matrix.Translation(p) @ frame(n)
    prof = [(0.0, h), (r * 0.72, h * 0.80), (r, 0.0), (r * 0.92, -sink), (0.0, -sink)]
    return part.lathe(prof, segs, mat, matrix=M)


def loft(part, path, sections, mat, up=(0, 0, 1), tip=None):
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


def arch(w, h, n=6, e=0.85):
    """Closed D-section: rounded top arch of half-width w and height h on a flat base."""
    pts = [(w * math.copysign(abs(cos(pi * k / n)) ** e, cos(pi * k / n)),
            h * abs(sin(pi * k / n)) ** e) for k in range(n + 1)]
    pts += [(-w * 0.9, 0.0), (w * 0.9, 0.0)]
    return pts[::-1]


def table(pts):
    """Periodic piecewise-linear function of an azimuth (radians) from [(deg, value), ...]."""
    pts = sorted(pts)

    def f(t):
        d = (degrees(t) + 180.0) % 360.0 - 180.0
        ext = [(pts[-1][0] - 360.0, pts[-1][1])] + pts + [(pts[0][0] + 360.0, pts[0][1])]
        for (a, va), (b, vb) in zip(ext, ext[1:]):
            if a <= d <= b:
                return radians(va + (vb - va) * (d - a) / (b - a))
        return radians(pts[0][1])
    return f


def sph(alpha, theta):
    """Unit direction: alpha from +Z (crown), theta azimuth (0 = front (-Y), +90 = +X)."""
    return Vector((sin(alpha) * sin(theta), -sin(alpha) * cos(theta), cos(alpha)))


def cap_shell(p, surf, hc, edge, thick, mat, nth=28, ns=6, pole='top', dive=(0.035, 0.11),
              sink=(0.003, 0.012), nudge=None):
    """Hair / cap / beard mass as a closed shell: rings run from a pole out to the edge line
    edge(theta) (angle from the pole), offset off the head by thick(a, theta, s); two rings past
    the edge dive under the skin so the mass ends on a crisp, smooth edge."""
    def P(a, t, off):
        d = sph(a if pole == 'top' else pi - a, t)
        loc, n = surf.ray(hc + d * 0.5, -d)
        q = loc + n * off
        return nudge(q, a, t) if nudge else q
    TH = [2 * pi * j / nth for j in range(nth)]
    rings = []
    for k in range(1, ns + 1):
        s = k / ns
        rings.append([P(edge(t) * s, t, thick(edge(t) * s, t, s)) for t in TH])
    for (da, dz) in zip(dive, sink):
        rings.append([P(edge(t) + da, t, -dz) for t in TH])
    top = P(0.0, 0.0, thick(0.0, 0.0, 0.0))
    return p.grid(rings, mat, True, top, hc.copy())


# ---------------------------------------------------------------------------- figure
class Fig:
    """Landmarks of a nominal 1.70 m figure; the whole figure is scaled to H afterwards."""

    def __init__(self, v):
        self.v = v
        self.p = C.Part()
        sh = v['sh']
        self.head_c = Vector((0.0, 0.006, 1.588))
        self.head_r = (0.079, 0.091, 0.108)
        self.shoulder = [Vector((sx * (sh - 0.020), 0.004, 1.366)) for sx in (1, -1)]
        self.elbow = [Vector((sx * (sh + 0.026), 0.030, 1.102)) for sx in (1, -1)]
        self.wrist = [Vector((sx * (sh + 0.036), -0.004, 0.862)) for sx in (1, -1)]
        self.hipj = [Vector((sx * 0.086, 0.0, 0.880)) for sx in (1, -1)]
        self.knee = [Vector((sx * 0.092, -0.014, 0.482)) for sx in (1, -1)]
        self.ankle = [Vector((sx * 0.097, 0.006, 0.104)) for sx in (1, -1)]


def torso_sections(f, coat=False):
    v = f.v
    sh, hip, waist, chest, belly = v['sh'], v['hip'], v['waist'], v['chest'], v['belly']
    secs = [(0.790, -0.080, 0.088, hip * 0.88), (0.860, -0.098, 0.102, hip),
            (0.905, -0.101 - belly * 0.4, 0.099, lerp(hip, waist * 1.04, 0.5)),
            (0.950, -0.102 - belly * 0.7, 0.097, waist * 1.03),
            (1.020, -0.100 - belly, 0.094, waist), (1.100, -0.106 - belly * 0.7, 0.098, waist * 1.07),
            (1.200, -chest, 0.104, sh * 0.93), (1.300, -chest * 0.95, 0.102, sh * 0.99),
            (1.368, -0.098, 0.090, sh), (1.412, -0.076, 0.072, sh * 0.80),
            (1.442, -0.054, 0.052, 0.066), (1.458, -0.047, 0.046, 0.054)]
    if coat:
        # long coat: flares down to just below the knee
        secs = [(0.540, -0.124, 0.120, hip * 1.20), (0.650, -0.118, 0.115, hip * 1.13),
                (0.760, -0.112, 0.110, hip * 1.06)] + secs[1:]
    return secs


def build_torso(f, coat=False):
    v = f.v
    tp = C.Part()
    secs = torso_sections(f, coat)
    nu = 22
    faces = C.loft_z(tp, secs, nu, v['top'], n=2.5)
    if not coat:
        tp.assign(faces[0:2 * nu], v['pants'])
        tp.assign(faces[2 * nu:3 * nu], v['trim'] if v['style'] == 'quiff' else v['pants'])
    else:
        tp.assign(faces[0:nu], v['top'])
    return tp, secs


def build_legs(f, coat=False):
    p = f.p
    v = f.v
    for i, sx in enumerate((1, -1)):
        H, K, A = f.hipj[i], f.knee[i], f.ankle[i]
        top = H + Vector((0, 0, 0.030)) if not coat else H.lerp(K, 0.55)
        pts = C.spline3([top, H.lerp(K, 0.5) + Vector((0, -0.004, 0)) if not coat else H.lerp(K, 0.78), K,
                         K.lerp(A, 0.45) + Vector((0, 0.008, 0)), A + Vector((0, 0, 0.022))], 2)
        rad = C.resample([0.088 if not coat else 0.068, 0.068, 0.059, 0.061, 0.054], len(pts))
        p.tube(pts, rad, 9, v['pants'], caps='round', cap_segs=1, scale_xy=(1.0, 0.94),
               up=(0, -1, 0))
        Mh = Matrix.Translation(A + Vector((0, 0, 0.030)))
        if v['style'] == 'quiff':     # ribbed jogger cuff
            p.lathe([(0.0, -0.008), (0.052, -0.008), (0.053, 0.014), (0.0, 0.018)], 9, v['trim'],
                    matrix=Mh)
        else:                         # turned-up hem
            p.torus(0.0555, 0.0055, 10, 3, v['pants'], matrix=Mh @ Matrix.Translation((0, 0, -0.002)))


def build_shoes(f):
    p = f.p
    v = f.v
    for i, sx in enumerate((1, -1)):
        A = f.ankle[i]
        cx, cy = A.x + sx * 0.004, A.y
        # sole (rubber), foot-shaped outline
        ol = catmull([(0.0, 0.070), (-0.030, 0.060), (-0.040, 0.020), (-0.043, -0.060),
                      (-0.048, -0.125), (-0.036, -0.182), (0.0, -0.206), (0.034, -0.190),
                      (0.050, -0.128), (0.046, -0.060), (0.040, 0.020), (0.030, 0.060)], 1)
        ol = ccw([(x * sx, y) for (x, y) in ol])
        plate(p, ol, lambda x, y, h, cx=cx, cy=cy: Vector((cx + x, cy + y, h)), 0.026,
              RUBBER, bevel=0.006)
        # upper: lofted from heel to toe, contrasting toe cap
        prof = [(0.060, 0.032, 0.074), (0.024, 0.042, 0.102), (-0.040, 0.046, 0.090),
                (-0.100, 0.049, 0.066), (-0.150, 0.045, 0.052), (-0.188, 0.030, 0.038)]
        path = [Vector((cx + sx * 0.003, cy + yy, 0.022)) for (yy, w, h) in prof]
        secs = [arch(w, h, 6, 0.85) for (yy, w, h) in prof]
        vr, fs = loft(p, path, secs, v['shoe'], up=(0, 0, 1),
                      tip=Vector((cx + sx * 0.003, cy - 0.200, 0.035)))
        nsec = len(secs[0])
        p.assign(fs[3 * nsec:5 * nsec], v['shoe2'])        # toe cap
        p.assign(fs[6 * nsec:7 * nsec], v['shoe2'])        # toe tip fan

        def top_h(yy):
            for (y0, w0, h0), (y1, w1, h1) in zip(prof, prof[1:]):
                if y1 <= yy <= y0:
                    return h0 + (h1 - h0) * (y0 - yy) / (y0 - y1)
            return prof[-1][2]
        lace = v['shoe2'] if v['shoe2'] != v['shoe'] else PEARL
        for k, yy in enumerate((-0.026, -0.050, -0.074)):
            z = 0.022 + top_h(yy) - 0.0010
            M = Matrix.Translation((cx + sx * 0.003, cy + yy, z)) @ Matrix.Rotation(radians(-16), 4, 'X')
            p.box(Vector((0, 0, 0)), (0.040, 0.007, 0.005), lace, matrix=M)
        p.box(Vector((cx + sx * 0.003, cy + 0.066, 0.070)), (0.020, 0.008, 0.030), v['shoe2'])


def build_arms(f, hold=None):
    """Sleeves with cuffs; returns the hand frames (wrist point, down, palm normal, side)."""
    p = f.p
    v = f.v
    hands = []
    for i, sx in enumerate((1, -1)):
        S, E, W = f.shoulder[i], f.elbow[i], f.wrist[i]
        if hold is not None and sx == hold['side']:
            E = E + hold.get('elbow', Vector())
            W = hold['wrist']
        pts = C.spline3([S + Vector((-sx * 0.012, 0, -0.004)), S.lerp(E, 0.5) + Vector((sx * 0.004, 0, 0)),
                         E, E.lerp(W, 0.5), W + (W - E).normalized() * 0.010], 2)
        rad = C.resample([0.057, 0.053, 0.048, 0.045, 0.042], len(pts))
        p.tube(pts, rad, 10, v['top'], caps='round', cap_segs=1, up=(0, -1, 0))
        d = (W - E).normalized()
        Mc = Matrix.Translation(W - d * 0.004) @ d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        p.lathe([(0.0, -0.020), (0.044, -0.020), (0.046, 0.004), (0.0, 0.010)], 10, v['trim'],
                matrix=Mc)
        hands.append((W + d * 0.012, d, Vector((-sx, 0, 0)), sx))
    return hands


def hand_frame(wrist, down, palm_n):
    z = down.normalized()
    xn = (palm_n - z * palm_n.dot(z)).normalized()          # palm normal (inward)
    yv = z.cross(xn).normalized()                             # across the knuckles
    if yv.y > 0:
        yv = -yv                                              # index finger toward the front
    return xn, yv, z


def build_hand(p, wrist, down, palm_n, skin, fist=False):
    """Palm block, four fingers and a thumb; palm faces palm_n, fingers hang along `down`."""
    xn, yv, z = hand_frame(wrist, down, palm_n)

    def W(a, b, c):
        return wrist + xn * a + yv * b + z * c
    M = Matrix((xn, yv, z)).transposed().to_4x4()
    M.translation = W(-0.004, 0.002, 0.042)
    p.superellipsoid(Vector((0, 0, 0)), (0.017, 0.040, 0.046), 0.7, 0.7, 8, 6, skin, matrix=M)
    for k, (yy, L) in enumerate(((0.026, 0.066), (0.009, 0.072), (-0.008, 0.068), (-0.024, 0.056))):
        base = W(0.000, yy, 0.080)
        if fist:
            pts = [base, W(0.016, yy, 0.100), W(0.034, yy, 0.086), W(0.034, yy * 0.95, 0.066)]
        else:
            pts = [base, W(0.006, yy * 1.05, 0.080 + L * 0.5), W(0.018, yy * 1.08, 0.078 + L * 0.95)]
        p.tube(pts, 0.0090 if k < 3 else 0.0080, 5, skin, caps='round', cap_segs=1,
               scale_xy=(1.0, 0.86), up=tuple(xn))
    tb = [W(0.008, 0.034, 0.030), W(0.020, 0.048, 0.058), W(0.026 if fist else 0.024, 0.046, 0.082)]
    p.tube(tb, 0.0105, 5, skin, caps='round', cap_segs=1, up=tuple(xn))


# ---------------------------------------------------------------------------- head
def build_head(f):
    v = f.v
    hc = f.head_c
    rx, ry, rz = f.head_r

    def shape(q):
        # relative to the head centre: narrower jaw, chin a touch forward, flatter face
        t = smoothstep(0.01, -0.10, q.z)
        q = Vector((q.x * (1.0 - 0.20 * t), q.y, q.z))
        if q.y < 0:
            q.y = q.y * (1.0 - 0.06 * smoothstep(0.03, -0.06, q.z)) - 0.006 * t
        return q
    hp = C.Part()
    hp.superellipsoid(Vector((0, 0, 0)), (rx, ry, rz), 0.92, 0.95, 20, 15, v['skin'],
                      matrix=Matrix.Translation(hc), deform=shape)
    return hp, Surf(hp.bm)


def face(f, surf):
    v = f.v
    p = f.p
    hc = f.head_c
    ey = hc.z - 0.006
    up = Vector((0, 0, 1))
    for sx in (1, -1):
        # eyes: glossy ink beans with a pearl catch-light
        loc, n = surf.ray(Vector((sx * 0.031, -0.4, ey)), Vector((0, 1, 0)))
        M = Matrix.Translation(loc - n * 0.0012) @ frame(n)
        p.superellipsoid(Vector((0, 0, 0)), (0.0088, 0.0128, 0.0052), 0.9, 0.9, 8, 5, INK, matrix=M)
        side = n.cross(up).normalized()
        cl = loc + n * 0.0030 + up * 0.0040 - side * sx * 0.0024
        p.superellipsoid(Vector((0, 0, 0)), (0.0024, 0.0026, 0.0013), 1.0, 1.0, 6, 4, PEARL,
                         matrix=Matrix.Translation(cl) @ frame(n))
        # brows
        bp = []
        for (bx, bz) in ((0.017, 0.023), (0.031, 0.029), (0.045, 0.024)):
            l2, n2 = surf.ray(Vector((sx * bx, -0.4, ey + bz)), Vector((0, 1, 0)))
            bp.append(l2 + n2 * 0.0016)
        p.tube(bp, 0.0030, 5, v['hair'], caps='round', cap_segs=1, scale_xy=(0.65, 1.0),
               up=(0, -1, 0))
        # ears with an inner fold
        loc, n = surf.ray(Vector((sx * 0.3, 0.012, hc.z - 0.016)), Vector((-sx, 0, 0)))
        M = Matrix.Translation(loc + n * 0.003) @ frame(n, (0, 0.25, 1))
        p.superellipsoid(Vector((0, 0, 0)), (0.0135, 0.0255, 0.0085), 0.9, 0.9, 8, 5, v['skin'],
                         matrix=M)
        p.superellipsoid(Vector((0.0015, 0.0, 0.0040)), (0.0070, 0.0150, 0.0040), 0.9, 0.9, 6, 3,
                         v['skin'], matrix=M)
    # button nose
    loc, n = surf.ray(Vector((0, -0.4, hc.z - 0.034)), Vector((0, 1, 0)))
    M = Matrix.Translation(loc + n * 0.004) @ frame(n)
    p.superellipsoid(Vector((0, 0, 0)), (0.0115, 0.0130, 0.0120), 0.85, 0.85, 7, 5, v['skin'],
                     matrix=M)
    # smile
    mp = []
    for (mx, mz) in ((-0.015, 0.004), (-0.008, -0.0005), (0.0, -0.0018), (0.008, -0.0005),
                     (0.015, 0.004)):
        l2, n2 = surf.ray(Vector((mx, -0.4, hc.z - 0.064 + mz)), Vector((0, 1, 0)))
        mp.append(l2 + n2 * 0.0008)
    p.tube(mp, 0.0019, 5, 'SKY_Terracotta', caps='round', cap_segs=1)


def build_hair(f, surf):
    v = f.v
    p = f.p
    hc = f.head_c
    st = v['style']
    if st == 'quiff':
        edge = table([(0, 56), (35, 64), (60, 82), (90, 96), (130, 112), (180, 122),
                      (-130, 112), (-90, 96), (-60, 82), (-35, 64)])

        def thick(a, t, s):
            front = math.exp(-((t - 0.15) / 0.62) ** 2)
            quiff = 0.026 * front * smoothstep(0.30, 0.92, s)
            return 0.0080 + quiff + 0.004 * (1.0 - s) ** 2

        def nudge(q, a, t):
            front = math.exp(-((t - 0.15) / 0.62) ** 2)
            lift = 0.010 * front * smoothstep(0.55, 1.0, a / max(edge(t), 1e-3))
            return q + Vector((0, 0, lift))
        cap_shell(p, surf, hc, edge, thick, v['hair'], nth=26, ns=6, nudge=nudge)
    elif st == 'bun':
        # side parting on the figure's right, the larger side sweeps across the forehead
        edge = table([(0, 54), (-25, 66), (-60, 84), (35, 60), (60, 80), (90, 98), (130, 112),
                      (180, 120), (-130, 112), (-90, 98)])

        def thick(a, t, s):
            part = math.exp(-((t - radians(-20)) / 0.18) ** 2) * smoothstep(0.1, 0.5, a)
            sweep = 0.005 * math.exp(-((t - radians(20)) / 0.7) ** 2) * smoothstep(0.3, 0.9, s)
            return 0.0085 + sweep - 0.004 * part
        cap_shell(p, surf, hc, edge, thick, v['hair'], nth=26, ns=6)
        bc = hc + Vector((0.0, 0.080, 0.064))
        p.superellipsoid(bc, (0.046, 0.042, 0.044), 0.9, 0.9, 10, 7, v['hair'])
        Mt = Matrix.Translation(hc + Vector((0, 0.060, 0.056))) @ Matrix.Rotation(radians(62), 4, 'X')
        p.torus(0.033, 0.0055, 12, 3, v['trim'], matrix=Mt)
    elif st == 'cap':
        # short grey hair round the sides and back (the cap covers the top)
        edge = table([(0, 56), (35, 62), (60, 90), (90, 100), (130, 110), (180, 118), (-130, 110),
                      (-90, 100), (-60, 90), (-35, 62)])
        cap_shell(p, surf, hc, edge, lambda a, t, s: 0.0055, v['hair'], nth=24, ns=3)
        # short beard along the jaw (below the lip, up to the sideburns), from the chin pole
        bedge = table([(0, 49), (35, 60), (70, 78), (95, 86), (125, 40), (180, 12),
                       (-125, 40), (-95, 86), (-70, 78), (-35, 60)])
        cap_shell(p, surf, hc, bedge, lambda a, t, s: 0.0055 + 0.0030 * (1.0 - s),
                  v['hair'], nth=24, ns=3, pole='bottom', dive=(0.035, 0.10))
        mp = []
        for (mx, mz) in ((-0.022, -0.006), (-0.011, 0.0), (0.0, 0.0015), (0.011, 0.0), (0.022, -0.006)):
            l2, n2 = surf.ray(Vector((mx, -0.4, hc.z - 0.049 + mz)), Vector((0, 1, 0)))
            mp.append(l2 + n2 * 0.0035)
        p.tube(mp, [0.0036, 0.0050, 0.0054, 0.0050, 0.0036], 5, v['hair'], caps='round',
               cap_segs=1, scale_xy=(1.0, 0.75), up=(0, -1, 0.3))
        # flat cap: crown, brim, top button
        cedge = table([(0, 64), (60, 70), (90, 76), (135, 84), (180, 88), (-135, 84), (-90, 76),
                       (-60, 70)])

        def cthick(a, t, s):
            return 0.0125 - 0.0045 * smoothstep(0.65, 0.0, s) + 0.004 * math.exp(-(t / 0.8) ** 2) * s

        def cnudge(q, a, t):
            return q + Vector((0, -0.010 * math.exp(-(t / 1.0) ** 2) * smoothstep(0.2, 0.9, a), 0))
        cap_shell(p, surf, hc, cedge, cthick, INK, nth=24, ns=5, nudge=cnudge)
        brim = catmull([(-0.076, 0.000), (-0.058, -0.040), (0.0, -0.056), (0.058, -0.040),
                        (0.076, 0.000), (0.0, 0.012)], 3)
        Mb = Matrix.Translation(hc + Vector((0, -0.066, 0.050))) @ Matrix.Rotation(radians(12), 4, 'X')
        plate(p, brim, lambda x, y, h, Mb=Mb: Mb @ Vector((x, y, h)), 0.007, INK, bevel=0.0025)
        loc, n = surf.ray(hc + Vector((0, 0, 0.5)), Vector((0, 0, -1)))
        p.superellipsoid(loc + n * 0.0115, (0.010, 0.010, 0.0055), 1.0, 1.0, 8, 4, INK)


# ---------------------------------------------------------------------------- clothing details
def jacket_details(f, tsurf):
    """passenger_a: hood rolled behind the neck, zip, drawstrings, kangaroo pocket."""
    v = f.v
    p = f.p
    top = v['top']
    Mh = Matrix.Translation((0, 0.024, 1.426)) @ Matrix.Rotation(radians(14), 4, 'X')
    p.torus(0.080, 0.029, 18, 6, top, matrix=Mh, scale_minor=(1.0, 0.9))
    zp = []
    for z in (1.415, 1.32, 1.20, 1.08, 0.96, 0.912):
        loc, n = tsurf.ray(Vector((0.0, -0.5, z)), Vector((0, 1, 0)))
        zp.append(loc + n * 0.003)
    p.tube(zp, 0.0040, 4, v['trim'], caps='flat')
    loc, n = tsurf.ray(Vector((0.0, -0.5, 1.385)), Vector((0, 1, 0)))
    p.box(loc + n * 0.008 - Vector((0, 0, 0.012)), (0.010, 0.005, 0.024), BRASS)
    for sx in (1, -1):
        loc, n = tsurf.ray(Vector((sx * 0.040, -0.5, 1.400)), Vector((0, 1, 0)))
        a = loc + n * 0.006
        p.tube([a, a + Vector((sx * 0.004, -0.004, -0.060)), a + Vector((sx * 0.006, -0.006, -0.110))],
               0.0040, 5, PEARL, caps='round', cap_segs=1)
        p.superellipsoid(a + Vector((sx * 0.006, -0.008, -0.116)), (0.0065, 0.0065, 0.010), 1.0, 1.0,
                         6, 4, BRASS)
    out = densify([(-0.085, 0.0), (0.085, 0.0), (0.072, 0.100), (-0.072, 0.100)], 0.025)
    plate(p, out, conform(tsurf, lambda x, y: Vector((x, -0.5, 0.960 + y)), -0.001, (0, 1, 0)),
          0.006, top, bevel=0.0025, fill=1, fill_to=0.02)


def shirt_details(f, tsurf):
    """passenger_b: pearl collar, button placket, chest pocket with a flap."""
    v = f.v
    p = f.p
    for sx in (1, -1):
        out = ccw([(0.0, 0.0), (sx * 0.060, 0.010), (sx * 0.074, -0.030), (sx * 0.010, -0.058)])
        F = conform(tsurf, lambda x, y: Vector((x, -0.5, 1.448 + y)), 0.001, (0, 1, 0.55))
        plate(p, out, F, 0.006, v['trim'], bevel=0.0022)
    pl = densify(rounded_rect(0.028, 0.30, 0.006, 1), 0.06)
    plate(p, pl, conform(tsurf, lambda x, y: Vector((x, -0.5, 1.250 + y)), -0.001, (0, 1, 0)),
          0.004, v['top'], bevel=0.0018, fill=1, fill_to=0.008)
    for z in (1.360, 1.270, 1.180, 1.090):
        loc, n = tsurf.ray(Vector((0.0, -0.5, z)), Vector((0, 1, 0)))
        dome(p, loc + n * 0.004, n, 0.0060, 0.0030, 6, PEARL)
    out = densify(rounded_rect(0.070, 0.080, 0.008, 2), 0.03)
    Fp = conform(tsurf, lambda x, y: Vector((0.082 + x, -0.5, 1.255 + y)), -0.001, (0, 1, 0))
    plate(p, out, Fp, 0.004, v['top'], bevel=0.0018, fill=1, fill_to=0.015)
    out = densify([(-0.038, -0.012), (0.038, -0.012), (0.038, 0.008), (-0.038, 0.008)], 0.03)
    Ff = conform(tsurf, lambda x, y: Vector((0.082 + x, -0.5, 1.290 + y)), 0.003, (0, 1, 0))
    plate(p, out, Ff, 0.005, v['top'], bevel=0.0018)


def belt(f, tsurf, z, mat, buckle=BRASS, coat=False):
    p = f.p
    s0 = torso_sections(f, coat)

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
    C.loft_z(p, bands, 22, mat, n=2.5)
    loc, n = tsurf.ray(Vector((0.0, -0.5, z)), Vector((0, 1, 0)))
    M = Matrix.Translation(loc + n * 0.008) @ frame(n)
    p.rbox(Vector((0, 0, 0)), (0.058, 0.040, 0.008), 0.0025, 1, buckle, matrix=M)
    p.box(Vector((0, 0, 0.0035)), (0.040, 0.022, 0.004), mat, matrix=M)


def coat_details(f, tsurf):
    """passenger_c: lapels, double row of brass buttons, belt, flap pockets."""
    v = f.v
    p = f.p
    for sx in (1, -1):
        out = densify(ccw([(0.0, 0.0), (sx * 0.070, -0.010), (sx * 0.090, -0.060),
                           (sx * 0.030, -0.200)]), 0.03)
        F = conform(tsurf, lambda x, y: Vector((x, -0.5, 1.430 + y)), 0.0005, (0, 1, 0.25))
        plate(p, out, F, 0.006, v['top'], bevel=0.0018)
        for z in (1.170, 1.075, 0.740):
            loc, n = tsurf.ray(Vector((sx * 0.050, -0.5, z)), Vector((0, 1, 0)))
            dome(p, loc + n * 0.002, n, 0.0085, 0.0040, 6, BRASS)
        out = densify([(-0.050, -0.010), (0.050, -0.010), (0.046, 0.012), (-0.046, 0.012)], 0.025)
        Fp = conform(tsurf, lambda x, y: Vector((sx * 0.100 + x, -0.5, 0.820 + y)), 0.0005, (0, 1, 0))
        plate(p, out, Fp, 0.006, v['top'], bevel=0.0022)
    belt(f, tsurf, 1.000, v['trim'], buckle=BRASS, coat=True)


# ---------------------------------------------------------------------------- accessories
def backpack(f, tsurf):
    v = f.v
    p = f.p
    m = v['acc_mat']
    M = Matrix.Translation((0.0, 0.166, 1.120)) @ Matrix.Rotation(radians(6), 4, 'X')
    p.rbox(Vector((0, 0, 0)), (0.270, 0.130, 0.380), 0.050, 2, m, matrix=M)
    p.rbox(Vector((0.0, 0.004, 0.170)), (0.262, 0.138, 0.060), 0.026, 1, m, matrix=M)   # lid
    p.rbox(Vector((0.0, 0.070, -0.075)), (0.200, 0.040, 0.160), 0.030, 2, m, matrix=M)  # pocket
    p.box(Vector((0.0, 0.091, -0.012)), (0.150, 0.004, 0.006), INK, matrix=M)            # zip
    p.box(Vector((0.055, 0.094, -0.022)), (0.010, 0.004, 0.022), BRASS, matrix=M)        # pull
    for sx in (1, -1):
        p.rbox(Vector((sx * 0.140, 0.010, -0.090)), (0.030, 0.090, 0.150), 0.014, 1, m, matrix=M)
    p.tube([M @ Vector((-0.040, -0.030, 0.196)), M @ Vector((0.0, -0.032, 0.226)),
            M @ Vector((0.040, -0.030, 0.196))], 0.008, 6, INK, caps='round', cap_segs=1)

    def on(x, z, front, off):
        loc, n = tsurf.ray(Vector((x, -0.5 if front else 0.5, z)), Vector((0, 1 if front else -1, 0)))
        return loc + n * off
    for sx in (1, -1):
        pts = [M @ Vector((sx * 0.100, -0.036, 0.190)), Vector((sx * 0.112, 0.060, 1.426)),
               on(sx * 0.118, 1.380, True, 0.007), on(sx * 0.124, 1.250, True, 0.007),
               on(sx * 0.128, 1.110, True, 0.007), on(sx * 0.132, 1.000, True, 0.006),
               Vector((sx * 0.140, 0.010, 0.955)), M @ Vector((sx * 0.112, -0.066, -0.170))]
        p.tube(C.spline3(pts, 2), 0.012, 6, INK, caps='round', cap_segs=1, scale_xy=(2.0, 0.55),
               up=(0, 0, 1))
        b = on(sx * 0.126, 1.150, True, 0.013)
        p.box(b, (0.036, 0.010, 0.016), BRASS)
    a, c = on(-0.120, 1.240, True, 0.010), on(0.120, 1.240, True, 0.010)
    mid = on(0.0, 1.244, True, 0.010)
    p.tube([a, mid, c], 0.007, 5, INK, caps='round', cap_segs=1, scale_xy=(2.0, 0.6), up=(0, -1, 0))
    p.rbox(mid + Vector((0, -0.006, 0)), (0.038, 0.012, 0.024), 0.004, 1, BRASS)


def suitcase(f, hand_pt):
    """Teal upright rolling case beside the right leg, telescopic handle up into the fist."""
    v = f.v
    p = f.p
    m = v['acc_mat']
    W, D, Hh = 0.200, 0.380, 0.560                      # thickness (x), width (y), height (z)
    lean = radians(6.0)                                  # leans toward the figure
    dirv = Vector((sin(lean), 0.0, cos(lean)))
    base = hand_pt - dirv * (hand_pt.z / cos(lean))
    base.z = 0.0
    M = Matrix.Translation(base + Vector((0, 0, 0.034))) @ Matrix.Rotation(lean, 4, 'Y')
    p.rbox(Vector((0, 0, Hh / 2)), (W, D, Hh), 0.045, 2, m, matrix=M)
    for yy in (-0.110, -0.036, 0.036, 0.110):            # ribs on the outer face
        p.box(Vector((-W / 2 - 0.003, yy, Hh / 2)), (0.008, 0.022, Hh - 0.090), m, matrix=M)
    p.box(Vector((0, 0, Hh / 2)), (W + 0.004, D + 0.004, 0.010), INK, matrix=M)            # zip seam
    for sy in (-1, 1):
        for sz in (0, 1):
            p.box(Vector((0, sy * (D / 2 - 0.016), 0.018 + sz * (Hh - 0.036))), (W + 0.010, 0.040, 0.040),
                  INK, matrix=M)                                                               # corners
    for sy in (-1, 1):                                    # wheels with metal hubs
        Mw = M @ Matrix.Translation((-0.050, sy * (D / 2 - 0.040), -0.002)) @ \
            Matrix.Rotation(radians(90), 4, 'X')
        p.lathe([(0.0, -0.014), (0.028, -0.014), (0.032, 0.0), (0.028, 0.014), (0.0, 0.014)], 10,
                RUBBER, matrix=Mw)
        p.cylinder(0.011, 0.032, 6, METAL, matrix=Mw @ Matrix.Translation((0, 0, -0.016)))
    # telescopic handle: twin outer tubes, slimmer inner stage, grip bar through the fist
    Mi = M.inverted()
    top = Mi @ hand_pt
    for sy in (-1, 1):
        a = Vector((0.0, sy * 0.068, Hh - 0.040))
        b = Vector((0.0, sy * 0.068, Hh + 0.090))
        c = Vector((0.0, sy * 0.068, top.z))
        p.tube([M @ a, M @ b], 0.0095, 8, METAL, caps='flat')
        p.tube([M @ b, M @ c], 0.0072, 8, METAL, caps='flat')
        p.torus(0.0105, 0.0030, 8, 4, INK, matrix=M @ Matrix.Translation(b))
    p.tube([M @ Vector((0.0, -0.084, top.z)), M @ Vector((0.0, 0.084, top.z))], 0.0140, 8, INK,
           caps='round', cap_segs=2)


def scarf(f):
    v = f.v
    p = f.p
    m = v['acc_mat']
    Mt = Matrix.Translation((0.0, 0.002, 1.445)) @ Matrix.Rotation(radians(-8), 4, 'X')
    p.torus(0.070, 0.026, 16, 6, m, matrix=Mt, scale_minor=(1.0, 1.15))
    p.torus(0.060, 0.020, 16, 5, m, matrix=Matrix.Translation((0.0, -0.002, 1.478)) @
            Matrix.Rotation(radians(-14), 4, 'X'))
    for (x0, L) in ((0.030, 0.230), (0.058, 0.180)):
        pts = [Vector((x0, -0.070, 1.430)), Vector((x0 + 0.006, -0.112, 1.350)),
               Vector((x0 + 0.010, -0.122, 1.430 - L * 0.75)), Vector((x0 + 0.012, -0.118, 1.430 - L))]
        p.tube(pts, 0.024, 8, m, caps='flat', scale_xy=(1.5, 0.45), up=(0, -1, 0))
        for k in range(3):
            xx = x0 + 0.012 + (k - 1.0) * 0.012
            p.tube([Vector((xx, -0.118, 1.432 - L)), Vector((xx, -0.118, 1.410 - L))], 0.0032, 4, m,
                   caps='round', cap_segs=1)


def glasses(f, surf):
    p = f.p
    hc = f.head_c
    ey = hc.z - 0.006
    rims = []
    for sx in (1, -1):
        loc, n = surf.ray(Vector((sx * 0.031, -0.4, ey)), Vector((0, 1, 0)))
        c = loc + n * 0.013
        p.torus(0.0185, 0.0018, 14, 3, BRASS, matrix=Matrix.Translation(c) @ frame(n))
        rims.append(c)
        l2, n2 = surf.ray(Vector((sx * 0.3, 0.000, ey + 0.002)), Vector((-sx, 0, 0)))
        p.tube([c + Vector((sx * 0.0185, 0, 0)), l2 + n2 * 0.007 + Vector((0, -0.020, 0)),
                l2 + n2 * 0.005 + Vector((0, 0.010, -0.010))], 0.0016, 4, BRASS, caps='round',
               cap_segs=1)
    c0, c1 = rims
    mid = (c0 + c1) / 2 + Vector((0, -0.002, 0.004))
    p.tube([c0 + Vector((-0.0185, 0, 0.002)), mid, c1 + Vector((0.0185, 0, 0.002))], 0.0016, 4, BRASS,
           caps='round', cap_segs=1)


def shoulder_bag(f, tsurf):
    p = f.p
    m = 'SKY_Coral'
    M = Matrix.Translation((0.205, -0.020, 0.900)) @ Matrix.Rotation(radians(-8), 4, 'Y')
    p.rbox(Vector((0, 0, 0)), (0.070, 0.240, 0.180), 0.040, 2, m, matrix=M)
    p.rbox(Vector((0.020, 0.0, 0.040)), (0.040, 0.244, 0.110), 0.030, 2, m, matrix=M)    # flap
    p.rbox(Vector((0.041, 0.0, -0.004)), (0.006, 0.040, 0.026), 0.0018, 1, BRASS, matrix=M)

    def on(x, z, front, off=0.012):
        loc, n = tsurf.ray(Vector((x, -0.5 if front else 0.5, z)), Vector((0, 1 if front else -1, 0)))
        return loc + n * off
    pts = [M @ Vector((-0.004, -0.112, 0.080)), M @ Vector((-0.010, -0.118, 0.150)),
           on(0.130, 1.090, True), on(0.030, 1.250, True), on(-0.090, 1.385, True, 0.013),
           Vector((-0.126, 0.006, 1.436)), on(-0.070, 1.330, False), on(0.120, 1.070, False),
           M @ Vector((-0.010, 0.118, 0.150)), M @ Vector((-0.004, 0.112, 0.080))]
    p.tube(C.spline3(pts, 1), 0.010, 5, m, caps='round', cap_segs=1, scale_xy=(1.9, 0.55),
           up=(0, -1, 0))


# ---------------------------------------------------------------------------- assemble
def figure(name):
    v = VARIANTS[name]
    f = Fig(v)
    p = f.p
    coat = v['acc'] == 'coat'
    tp, secs = build_torso(f, coat)
    tsurf = Surf(tp.bm)
    build_legs(f, coat)
    build_shoes(f)
    hold = None
    if v['acc'] == 'suitcase':
        hold = dict(side=-1, wrist=Vector((-0.240, 0.050, 0.905)), elbow=Vector((-0.008, 0.024, 0.0)))
    hands = build_arms(f, hold)
    for (w, d, pn, sx) in hands:
        build_hand(p, w, d, pn, v['skin'], fist=hold is not None and sx == hold['side'])
    p.lathe([(0.0, 1.400), (0.050, 1.400), (0.048, 1.470), (0.046, 1.540), (0.0, 1.540)], 12,
            v['skin'], matrix=Matrix.Translation((0, 0.012, 0)))                    # neck
    hp, hsurf = build_head(f)
    face(f, hsurf)
    build_hair(f, hsurf)
    if v['acc'] == 'backpack':
        jacket_details(f, tsurf)
        backpack(f, tsurf)
    elif v['acc'] == 'suitcase':
        shirt_details(f, tsurf)
        belt(f, tsurf, 0.958, 'SKY_Wood')
        (w, d, pn, sx) = hands[1]
        xn, yv, z = hand_frame(w, d, pn)
        suitcase(f, w + xn * 0.018 + z * 0.088)
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
