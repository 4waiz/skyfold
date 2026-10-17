"""NURI - small mechanical falcon companion for SKYFOLD: The Last Flight.

Original procedural model (Awaiz Ahmed / Team Kanban), not AI-generated.
    blender -b --factory-startup -P tools/blender/chars_nuri.py [-- --no-render]

Hierarchy (pivots):
    Nuri (empty, body centre)
      Body            body centre
        Head          neck joint
          Lens        lens centre (separate mesh, SKY_TealGlow)
          Beak        beak root
        Wing_L        left shoulder joint (Blender +X = the falcon's left)
        Wing_R        right shoulder joint
        Tail          tail base
        Thruster      emissive disc centre (underside)
Faces Blender -Y (Unity +Z). Wings are modelled half-spread; a flap is a rotation about
the forward axis (Unity Z) at the shoulder pivot.

Detail pass: every wing and tail feather is its own beveled plate with a brass rim (primaries,
secondaries, three covert rows, a nine-feather tail fan); a protruding lens housing with an ink
pupil; brow ridge, cheek panels, sensor lights; a sculpted beak with cere and nostrils; chest
scale plates, seams and screws; a vaned thruster and tucked talons. The game drives the whole
Lens renderer with one emission property block, so the lens iris is built from two glass rings
with dark gaps (the socket and pupil belong to the Head) instead of material bands.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C
from chars_common import Vector, Matrix, Euler, Quaternion, radians, sin, cos, pi, sqrt
import bpy, bmesh
from mathutils.bvhtree import BVHTree

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS
EXTRA = '--extra' in ARGS
OUT = os.path.join(C.MODELS, 'Characters', 'nuri.fbx')

IVORY, BRASS, INK, GLOW, TEAL, CORAL = ('SKY_Ivory', 'SKY_Brass', 'SKY_Ink', 'SKY_TealGlow',
                                        'SKY_Teal', 'SKY_Coral')
HOOD = INK if '--hood=teal' not in ARGS else TEAL   # falcon hood / brow / malar wedge
FLIGHT = TEAL          # flight feathers (primaries, secondaries, tail)
CHEST = 'SKY_Sandstone'  # chest scale plates

# ---------------------------------------------------------------------------- layout
HEAD_C = Vector((0.0, -0.083, 0.041))     # head centre
NECK = Vector((0.0, -0.054, 0.019))       # Head pivot (neck joint)
LENS_C = Vector((0.0, -0.1205, 0.0455))   # Lens pivot
BEAK_B = Vector((0.0, -0.1170, 0.0225))   # Beak pivot (root under the lens)
SHOULDER = Vector((0.040, -0.028, 0.025)) # Wing_L pivot (Wing_R mirrored)
TAIL_P = Vector((0.0, 0.086, 0.004))      # Tail pivot
THR_C = Vector((0.0, 0.006, -0.0495))     # Thruster pivot
DIHEDRAL = 18.0
WRIST_BEND = 7.0
SWEEP = 3.0


def sp(x, e):
    return math.copysign(abs(x) ** e, x)


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def cdist(a, b):
    d = abs(a - b) % (2 * pi)
    return min(d, 2 * pi - d)


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


# ---------------------------------------------------------------------------- plates
def inset2d(pts, d, maxm=2.4):
    """Offset a CCW 2D outline inward by d (mitred, clamped)."""
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


def plate(part, outline, F, thick, mat, bevel=0.0007, rim=None, rim_w=0.0, rim_wall=True,
          under=0.0):
    """Beveled plate from a CCW 2D outline. F(x, y, h) -> world point (h = 0 at the bottom face,
    thick at the top). Rings: [under chamfer], wall, top chamfer, [rim band], top cap.
    rim: material of the top chamfer + rim band (+ wall when rim_wall)."""
    O = list(outline)
    n = len(O)
    rings = []
    if under > 0:
        rings.append((inset2d(O, under), 0.0))
        rings.append((O, under))
    else:
        rings.append((O, 0.0))
    rings.append((O, thick - bevel))
    rings.append((inset2d(O, bevel), thick))
    if rim and rim_w > 0:
        rings.append((inset2d(O, bevel + rim_w), thick))
    pts = [[F(x, y, h) for (x, y) in r] for (r, h) in rings]
    vr, faces = part.grid(pts, mat, True, 'ngon', 'ngon')
    if rim:
        nb = len(rings) - 1
        b0 = nb - (2 if rim_w > 0 else 1) - (1 if rim_wall else 0)
        part.assign(faces[b0 * n: nb * n], rim)
    return faces


def feather_outline(L, w, base_w=None, tip_len=None, ns=2, nt=5, point=0.0, shift=0.0):
    """CCW outline of a feather along +x: base (hidden) at x = 0, tip at x = L, width w.
    point 0 = round tip .. 1 = pointed; shift moves the tip toward +y (asymmetric vanes)."""
    bw = base_w if base_w is not None else w * 0.62
    tl = tip_len if tip_len is not None else w * 0.75
    xs = L - tl
    hw = [bw / 2 + (w / 2 - bw / 2) * sin(0.5 * pi * k / ns) for k in range(ns + 1)]
    right = [(xs * k / ns, -hw[k]) for k in range(ns + 1)]
    left = [(xs * k / ns, hw[k]) for k in range(ns + 1)]
    tip = []
    e = 1.0 + 1.4 * point
    for k in range(1, nt + 1):
        a = -0.5 * pi + pi * k / (nt + 1)
        y = hw[-1] * sin(a) + shift * hw[-1] * cos(a)
        x = xs + tl * (cos(a) ** (1.0 / e))
        tip.append((x, y))
    return right + tip + left[::-1]


def rounded_rect(w, h, r, n=3):
    pts = []
    for (cx, cy, a0) in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                         (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(n + 1):
            a = radians(a0 + 90 * k / n)
            pts.append((cx + r * cos(a), cy + r * sin(a)))
    return pts


# ---------------------------------------------------------------------------- projection
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
    """Closest-point / ray projection onto a reference shell with interpolated normals, so
    plates and fittings can sit flush on a curved surface."""

    def __init__(self, part):
        bm = part.bm.copy()
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


def conform(surf, to3d, base, axis=None):
    """F(x, y, h) for plate(): 2D layout point -> surface point (+ normal * (base + h)).
    to3d(x, y) gives a 3D point near the surface; axis: project along this direction by ray
    (from outside), else closest point."""
    cache = {}

    def F(x, y, h):
        k = (round(x, 8), round(y, 8))
        if k not in cache:
            p = to3d(x, y)
            if axis is not None:
                a = Vector(axis).normalized()
                cache[k] = surf.ray(p - a * 0.3, a)
            else:
                cache[k] = surf.near(p)
        loc, n = cache[k]
        return loc + n * (base + h)
    return F


def frame(n):
    n = Vector(n).normalized()
    return n.to_track_quat('Z', 'Y').to_matrix().to_4x4()


def dome(part, p, n, r, h, segs, mat, cap_mat=None, sink=0.0010):
    """Small domed fitting (screw head / light) standing on a surface point along normal n."""
    M = Matrix.Translation(p) @ frame(n)
    prof = [(0.0, h), (r * 0.62, h * 0.86), (r * 0.94, h * 0.42), (r, 0.0), (r * 0.96, -sink),
            (0.0, -sink)]
    vr, fs = part.lathe(prof, segs, mat, matrix=M)
    if cap_mat:
        nb = len(prof) - 3
        part.assign(fs[nb * segs:nb * segs + segs], cap_mat)   # top fan
        part.assign(fs[0:segs], cap_mat)
    return fs


def lathe_ring(part, prof, segs, mat, M, phase=0.0):
    """Revolve a closed (r, z) profile about local Z into a solid ring (no poles)."""
    angs = [phase + 2 * pi * k / segs for k in range(segs)]
    rings = [[M @ Vector((r * cos(a), r * sin(a), z)) for a in angs] for (r, z) in prof]
    vr, faces = part.grid(rings, mat, True, None, None, closed_v=True)
    return faces


def loft(part, path, sections, mat, up=(0, 0, 1), tip=None):
    """Sweep per-point cross-sections [(side, up), ...] (equal counts) along a polyline.
    The start is capped with a fan, the end with a pole at `tip` (or a fan)."""
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


# ---------------------------------------------------------------------------- shells
def merge_samples(n, breaks, minsep, lo=0.0, hi=1.0, closed=False):
    base = [lo + (hi - lo) * i / n for i in range(n if closed else n + 1)]
    per = hi - lo

    def dist(a, b):
        d = abs(a - b)
        return min(d, per - d) if closed else d
    keep = [b for b in base if all(dist(b, k) > minsep for k in breaks)]
    if not closed:
        keep += [lo, hi]
    allv = keep + [(b % per if closed else b) for b in breaks if closed or lo < b < hi]
    return sorted(set(round(v, 9) for v in allv))


def shell(part, fn, center_fn, n_s, n_ph, theta_of, ring_grooves, col_grooves, depth, mat_fn):
    """Watertight shell around an axis. s in [0,1] runs pole to pole, theta_of(s, ph) warps
    the rings (so a ring can follow a design line). ring_grooves [(s, w)], col_grooves
    [(ph, w, s_from, s_to)] are V grooves. mat_fn(s, ph, g) -> material."""
    s_br = []
    for (sc, w) in ring_grooves:
        s_br += [sc - w, sc, sc + w]
    ph_br = []
    for (pc, w, a, b) in col_grooves:
        ph_br += [pc - w, pc, pc + w]
    S = merge_samples(n_s, s_br, min(w for _, w in ring_grooves) * 0.7 if ring_grooves else 0)
    PH = merge_samples(n_ph, ph_br, min(c[1] for c in col_grooves) * 0.7 if col_grooves else 0,
                       0.0, 2 * pi, closed=True)

    def g(s, ph):
        v = 0.0
        for (sc, w) in ring_grooves:
            v = max(v, 1.0 - abs(s - sc) / w)
        for (pc, w, a, b) in col_grooves:
            fade = smoothstep(a, a + 0.06, s) * (1.0 - smoothstep(b - 0.06, b, s))
            v = max(v, (1.0 - cdist(ph, pc) / w) * fade)
        return max(0.0, v)

    def P(s, ph):
        th = theta_of(s, ph)
        p = fn(th, ph)
        gv = g(s, ph)
        if gv > 0:
            d = (p - center_fn(th, ph)).normalized()
            p = p - d * depth * gv
        return p
    rings = [[P(s, ph) for ph in PH] for s in S[1:-1]]
    vr, faces = part.grid(rings, IVORY, True, fn(theta_of(0.0, 0.0), 0.0),
                          fn(theta_of(1.0, 0.0), 0.0))
    n = len(PH)
    nr = len(rings)
    for i in range(nr - 1):
        sm = (S[1 + i] + S[2 + i]) / 2
        for j in range(n):
            a, b = PH[j], PH[(j + 1) % n]
            if b < a:
                b += 2 * pi
            pm = ((a + b) / 2) % (2 * pi)
            gm = g(sm, pm)
            part.assign([faces[i * n + j]], mat_fn(sm, pm, gm))
    base = (nr - 1) * n
    for j in range(n):
        pm = PH[j]
        part.assign([faces[base + j]], mat_fn(S[0] * 0.5 + S[1] * 0.5, pm, 0.0))
        part.assign([faces[base + n + j]], mat_fn(S[-1] * 0.5 + S[-2] * 0.5, pm, 0.0))
    return faces


# ---------------------------------------------------------------------------- body
BODY = dict(yc=0.0, Lf=0.078, Lb=0.094, W=0.051, Hup=0.043, Hdn=0.049)


def body_axis(th):
    c = cos(th)
    y = BODY['yc'] - sp(c, 0.9) * (BODY['Lf'] if c > 0 else BODY['Lb'])
    zc = 0.006 * c + 0.002
    return y, zc


def body_pt(th, ph):
    y, zc = body_axis(th)
    t = th / pi
    taper = 1.0 - 0.38 * smoothstep(0.40, 1.0, t)
    r = sp(sin(th), 0.80) * taper
    s, c = sin(ph), cos(ph)
    x = BODY['W'] * r * sp(s, 0.86)
    z = zc + (BODY['Hup'] if c > 0 else BODY['Hdn']) * r * sp(c, 0.86)
    return Vector((x, y, z))


def body_center(th, ph):
    y, zc = body_axis(th)
    return Vector((0.0, y, zc))


def chest_scales(p, surf):
    """Overlapping sandstone breast plates laid out in the body's own (th, ph) parameters:
    brick-bonded rows wrapping the breast, tips pointing back along the belly; the front rows
    sit on top of the ones behind like shingles."""
    rows = [(0.150 * pi, 3, 0.088 * pi, 0.0022), (0.215 * pi, 4, 0.088 * pi, 0.0016),
            (0.280 * pi, 3, 0.092 * pi, 0.0010), (0.345 * pi, 2, 0.100 * pi, 0.0004)]
    for r, (th, n, dph, base) in enumerate(rows):
        L = 0.0190 - 0.0006 * r
        w = 0.0215 - 0.0004 * r
        out = feather_outline(L, w, base_w=w * 0.96, tip_len=w * 0.55, ns=1, nt=4, point=0.30)
        for k in range(n):
            ph = pi + (k - (n - 1) / 2) * dph
            c = body_pt(th, ph)
            e = 1e-4
            t_th = (body_pt(th + e, ph) - body_pt(th - e, ph)).normalized()   # toward the tail
            t_ph = (body_pt(th, ph + e) - body_pt(th, ph - e)).normalized()   # around the body

            def to3d(x, y, c=c, t_th=t_th, t_ph=t_ph, L=L):
                return c + t_th * (x - L * 0.40) + t_ph * y
            plate(p, out, conform(surf, to3d, base), 0.0015, CHEST, bevel=0.0005)


def build_body(parent):
    p = C.Part()
    seams = [(0.0, 0.030, 0.30, 0.86), (0.62 * pi, 0.030, 0.22, 0.88),
             (1.38 * pi, 0.030, 0.22, 0.88)]
    shell(p, body_pt, body_center, 17, 28, lambda s, ph: s * pi, [], seams, 0.0012,
          lambda s, ph, g: INK if g > 0.3 else IVORY)
    ref = C.Part()
    shell(ref, body_pt, body_center, 24, 36, lambda s, ph: s * pi, [], [], 0.0,
          lambda s, ph, g: IVORY)
    surf = Surf(ref)
    ref.bm.free()
    chest_scales(p, surf)
    # neck collar (brass) + dark neck core with two ribs so the head can turn without gaps
    ax = (HEAD_C - NECK).normalized()
    M = Matrix.Translation(NECK) @ ax.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    p.torus(0.0228, 0.0044, 22, 5, BRASS, matrix=M @ Matrix.Translation((0, 0, -0.002)))
    p.lathe([(0.0, -0.016), (0.0200, -0.016), (0.0208, 0.002), (0.0196, 0.004), (0.0204, 0.008),
             (0.0192, 0.012), (0.0, 0.012)], 18, INK, matrix=M)
    # shoulder sockets (ink cup + brass ring), both sides
    for sx in (1, -1):
        s = Vector((SHOULDER.x * sx, SHOULDER.y, SHOULDER.z))
        n = Vector((sx * 1.0, 0.0, 0.55)).normalized()
        Ms = Matrix.Translation(s - n * 0.004) @ n.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        vr, fs = p.lathe([(0, -0.006), (0.0124, -0.006), (0.0134, -0.0004), (0.0138, 0.0010),
                          (0.0122, 0.0020), (0, 0.0020)], 16, INK, matrix=Ms)
        p.assign(fs[1 * 16:3 * 16], BRASS)
    # thruster housing: brass lip, ink nacelle, six vanes and a brass hub over the glow disc
    Mt = Matrix.Translation(THR_C)
    seg = 24
    vr, fs = p.lathe([(0.0, 0.0110), (0.0196, 0.0110), (0.0214, 0.0062), (0.0213, 0.0002),
                      (0.0204, -0.0034), (0.0192, -0.0050), (0.0170, -0.0047), (0.0160, -0.0030),
                      (0.0156, -0.0002), (0.0, -0.0002)], seg, INK, matrix=Mt)
    p.assign(fs[3 * seg:6 * seg], BRASS)
    for k in range(6):
        a = 2 * pi * k / 6 + pi / 6
        Mv = Mt @ Matrix.Rotation(a, 4, 'Z') @ Matrix.Rotation(radians(18), 4, 'X')
        p.box(Vector((0.0098, 0.0, -0.0030)), (0.0118, 0.0011, 0.0028), INK, matrix=Mv)
    p.lathe([(0.0, -0.0060), (0.0022, -0.0056), (0.0034, -0.0042), (0.0036, -0.0010),
             (0.0, -0.0010)], 12, BRASS, matrix=Mt)
    # vent louvres on the nacelle flanks
    for sx in (1, -1):
        for k in range(3):
            c = Vector((sx * 0.0214, THR_C.y, THR_C.z + 0.0048 - 0.0022 * k))
            p.box(c, (0.0018, 0.0070, 0.0010), BRASS)
    # tucked talons: ink tarsus folded back along the belly, brass ankle, three curled toes
    # ending in brass claws (a loose fist under the tail coverts)
    for sx in (1, -1):
        hip = Vector((sx * 0.0160, 0.026, -0.033))
        ank = Vector((sx * 0.0175, 0.050, -0.0430))
        p.tube([hip, (hip + ank) / 2 + Vector((0, 0, -0.0012)), ank], [0.0038, 0.0032, 0.0027],
               6, INK, caps='round', cap_segs=1)
        p.superellipsoid(ank, (0.0034, 0.0034, 0.0034), 1.0, 1.0, 8, 5, BRASS)
        for spread in (-22.0, 0.0, 22.0):
            R = Matrix.Rotation(radians(spread * sx), 3, 'Z')
            pts = [ank, ank + R @ Vector((0, 0.0060, -0.0016)), ank + R @ Vector((0, 0.0090, -0.0052)),
                   ank + R @ Vector((0, 0.0078, -0.0088)), ank + R @ Vector((0, 0.0050, -0.0104))]
            segs = 5
            vr, fs = p.tube(pts, [0.0020, 0.0018, 0.0015, 0.0009, 0.0003], segs, INK, caps='round',
                            cap_segs=1)
            n = len(pts)
            p.assign(fs[(n - 1) * segs:(n + 1) * segs], BRASS)          # claw
            p.assign(fs[(n + 2) * segs:(n + 3) * segs], BRASS)          # claw tip fan
    # brass screws at the seam ends and on the back plate
    for q in [(0.0, -0.020, 0.050), (0.0, 0.070, 0.035), (0.022, 0.012, 0.045), (-0.022, 0.012, 0.045),
              (0.046, 0.030, -0.012), (-0.046, 0.030, -0.012), (0.040, -0.045, -0.018),
              (-0.040, -0.045, -0.018), (0.018, 0.072, 0.022), (-0.018, 0.072, 0.022)]:
        loc, n = surf.near(Vector(q))
        dome(p, loc + n * 0.0001, n, 0.0021, 0.0012, 7, BRASS)
    tmp = p.to_temp()
    return C.merge_to_object("Body", [tmp], pivot=(0, 0, 0), parent=parent, sharp_deg=48)


# ---------------------------------------------------------------------------- head
HEAD = dict(Rf=0.040, Rb=0.043, Rs=0.0425, Rt=0.0415, Rd=0.0385)
S_HOOD = 0.42


def theta_hood(ph):
    a = abs(((ph + pi) % (2 * pi)) - pi)          # 0 top .. pi bottom
    t = 0.24 * pi + 0.22 * pi * (1 - cos(a)) / 2 + 0.34 * pi * smoothstep(0.55 * pi, 0.95 * pi, a)
    t -= 0.17 * pi * math.exp(-((a - 0.74 * pi) / (0.095 * pi)) ** 2)   # malar wedge
    return t


def head_theta(s, ph):
    th = theta_hood(ph)
    if s <= S_HOOD:
        return th * (s / S_HOOD)
    return th + (pi - th) * (s - S_HOOD) / (1 - S_HOOD)


def head_pt(th, ph):
    c, s = cos(th), sin(th)
    fw = sp(c, 0.72)
    rad = sp(s, 0.86)
    sx, cz = sp(sin(ph), 0.86), sp(cos(ph), 0.86)
    y = HEAD_C.y - fw * (HEAD['Rf'] if c > 0 else HEAD['Rb'])
    cheek = 1.0 + 0.06 * max(0.0, -cos(ph)) * smoothstep(0.15, 0.6, th / pi)
    x = HEAD['Rs'] * rad * sx * cheek
    z = HEAD_C.z + rad * cz * (HEAD['Rt'] if cz > 0 else HEAD['Rd'])
    p = Vector((x, y, z))
    # brow: the hood's front edge rises into a soft ridge over the lens housing
    th_e = theta_hood(ph) + 0.05
    brow = math.exp(-((th - th_e) / 0.075) ** 2) * max(0.0, cos(ph)) ** 1.5
    d = (p - HEAD_C).normalized()
    p = p + d * 0.0034 * brow
    # lens socket: the face is pushed back behind the protruding lens housing
    rel = p - LENS_C
    lat = sqrt(rel.x * rel.x + rel.z * rel.z)
    k = 1.0 - smoothstep(0.0165, 0.0203, lat)       # stays inside the housing wall (r 0.0212)
    if k > 0.0:
        ty = LENS_C.y + 0.0070
        if p.y < ty:
            p.y += (ty - p.y) * k
    return p


# lens housing profile (lens-local: z forward), back pole -> outer wall -> brass ring ->
# lip -> socket -> pupil pole
HOUSING = [(0.0, -0.0130), (0.0196, -0.0130), (0.0212, -0.0070), (0.0213, 0.0016),
           (0.0207, 0.0036), (0.0197, 0.0047), (0.0190, 0.0050), (0.0187, 0.0056),
           (0.0180, 0.0060), (0.0168, 0.0059), (0.0162, 0.0054), (0.0158, 0.0048),
           (0.0151, 0.0040), (0.0150, 0.0027), (0.0162, 0.0021), (0.0170, -0.0045),
           (0.0158, -0.0060), (0.0062, -0.0062), (0.0053, -0.0052), (0.0042, -0.0034),
           (0.0024, -0.0024), (0.0, -0.0021)]
HOUSING_BRASS = (5, 6, 7, 8, 9)       # band indices (between popped profile points i, i+1)


def build_head(parent):
    p = C.Part()

    def mat(s, ph, g):
        if g > 0.3:
            # spine groove on the dark hood becomes a slim brass inlay
            return BRASS if (s > S_HOOD + 0.03 and cdist(ph, 0.0) < 0.06) else INK
        return HOOD if s > S_HOOD else IVORY
    shell(p, head_pt, lambda th, ph: HEAD_C, 20, 32, head_theta, [(S_HOOD, 0.016)],
          [(0.0, 0.040, S_HOOD + 0.02, 0.86)], 0.0011, mat)
    ref = C.Part()
    shell(ref, head_pt, lambda th, ph: HEAD_C, 24, 40, head_theta, [], [], 0.0,
          lambda s, ph, g: IVORY)
    surf = Surf(ref)
    ref.bm.free()
    # lens housing (ink) with a raised brass ring, inner lip, dark socket and the pupil dome
    Mf = Matrix.Translation(LENS_C) @ Matrix.Rotation(radians(90), 4, 'X')  # local +Z -> -Y
    seg = 24
    vr, fs = p.lathe(HOUSING, seg, INK, matrix=Mf)
    for b in HOUSING_BRASS:
        p.assign(fs[b * seg:(b + 1) * seg], BRASS)
    # cheek panels: raised ivory plates on the face sides, a brass screw at the back corner
    for sx in (1, -1):
        out = rounded_rect(0.021, 0.015, 0.0060, 3)

        def to3d(x, y, sx=sx):
            return Vector((sx * 0.06, -0.1040 + x, 0.0330 + y + 0.15 * x))
        plate(p, out, conform(surf, to3d, -0.0002, axis=(-sx, 0, 0)), 0.0014, IVORY, bevel=0.0005)
        loc, n = surf.ray(Vector((sx * 0.08, -0.0960, 0.0345)), Vector((-sx, 0, 0)))
        dome(p, loc + n * 0.0011, n, 0.0016, 0.0010, 8, BRASS)
        # sensor light behind the face: brass socket + coral lens
        loc, n = surf.ray(Vector((sx * 0.08, -0.0755, 0.0470)), Vector((-sx, 0, 0)))
        M = Matrix.Translation(loc) @ frame(n)
        prof = [(0.0, 0.0034), (0.0024, 0.0031), (0.0036, 0.0022), (0.0040, 0.0016),
                (0.0054, 0.0014), (0.0060, 0.0006), (0.0060, -0.0012), (0.0, -0.0012)]
        vr, fs = p.lathe(prof, 14, BRASS, matrix=M)
        nb = len(prof) - 3                       # bands; the top fan follows them
        p.assign(fs[0:2 * 14], CORAL)
        p.assign(fs[nb * 14:(nb + 1) * 14], CORAL)
    tmp = p.to_temp()
    return C.merge_to_object("Head", [tmp], pivot=NECK, parent=parent, sharp_deg=48)


def build_lens(parent):
    """Two glowing glass rings (iris) floating in the housing's dark socket; the ink pupil and
    the dark gap between the rings belong to the Head."""
    p = C.Part()
    Mf = Matrix.Translation(LENS_C) @ Matrix.Rotation(radians(90), 4, 'X')
    inner = [(0.0058, -0.0030), (0.0058, 0.0010), (0.0066, 0.0021), (0.0086, 0.0023),
             (0.0100, 0.0014), (0.0103, -0.0030)]
    outer = [(0.0117, -0.0040), (0.0117, 0.0006), (0.0126, 0.0018), (0.0146, 0.0018),
             (0.0158, 0.0008), (0.0161, -0.0040)]
    seg = 22
    lathe_ring(p, inner, seg, GLOW, Mf)
    fs = lathe_ring(p, outer, seg, GLOW, Mf)
    p.assign(fs[0:seg], TEAL)         # inner wall of the outer ring (seen through the gap)
    tmp = p.to_temp()
    return C.merge_to_object("Lens", [tmp], pivot=LENS_C, parent=parent, sharp_deg=60)


def beak_section(w, ht, hb, n=14, ridge=0.38, e=0.80):
    out = []
    for k in range(n):
        a = 2 * pi * k / n
        c, s = cos(a), sin(a)
        x = w * sp(c, e)
        if s > 0:
            y = ht * sp(s, e)
            x *= 1.0 - ridge * s * s
        else:
            y = hb * sp(s, e)
        out.append((x, y))
    return out


def build_beak(parent):
    p = C.Part()
    b = BEAK_B
    f = Vector((0, -1, 0))
    z = Vector((0, 0, 1))
    # upper mandible: brass, hooked, culmen ridge
    up = [(-0.0060, -0.0008), (0.0020, -0.0016), (0.0080, -0.0040), (0.0136, -0.0062),
          (0.0188, -0.0094), (0.0230, -0.0134), (0.0252, -0.0180), (0.0246, -0.0222)]
    sec = [(0.0098, 0.0058, 0.0050), (0.0094, 0.0055, 0.0047), (0.0084, 0.0052, 0.0042),
           (0.0068, 0.0046, 0.0034), (0.0052, 0.0038, 0.0027), (0.0039, 0.0030, 0.0020),
           (0.0027, 0.0022, 0.0014), (0.0015, 0.0013, 0.0008)]
    path = [b + f * a + z * c for (a, c) in up]
    tip = b + f * 0.0222 + z * (-0.0252)
    vr, fs = loft(p, path, [beak_section(*s_) for s_ in sec], BRASS, up=(0, 0, 1), tip=tip)
    # cere: raised ink collar at the root with round brass-rimmed nostrils
    cp = [b + f * a + z * c for (a, c) in [(-0.0055, -0.0006), (0.0010, -0.0014), (0.0050, -0.0029)]]
    cs = [(0.0107, 0.0066, 0.0058), (0.0103, 0.0064, 0.0055), (0.0094, 0.0060, 0.0050)]
    loft(p, cp, [beak_section(*s_) for s_ in cs], INK, up=(0, 0, 1))
    for sx in (1, -1):
        c = b + f * 0.0026 + z * 0.0004 + Vector((sx * 0.0070, 0, 0))
        n = Vector((sx * 0.85, -0.35, 0.40)).normalized()
        M = Matrix.Translation(c) @ frame(n)
        vr, fs2 = p.lathe([(0.0, -0.0003), (0.0007, -0.0002), (0.0011, 0.0006), (0.0017, 0.0007),
                           (0.0021, 0.0001), (0.0021, -0.0014), (0.0, -0.0014)], 10, BRASS, matrix=M)
        p.assign(fs2[0:10], INK)
        p.assign(fs2[4 * 10:5 * 10], INK)
    # lower mandible (ink)
    lo = [(-0.0040, -0.0074), (0.0060, -0.0086), (0.0120, -0.0100), (0.0162, -0.0118)]
    ls = [(0.0074, 0.0028, 0.0032), (0.0064, 0.0024, 0.0028), (0.0046, 0.0018, 0.0020),
          (0.0026, 0.0011, 0.0011)]
    loft(p, [b + f * a + z * c for (a, c) in lo], [beak_section(*s_, ridge=0.1) for s_ in ls], INK,
         up=(0, 0, 1), tip=b + f * 0.0185 + z * (-0.0124))
    tmp = p.to_temp()
    return C.merge_to_object("Beak", [tmp], pivot=BEAK_B, parent=parent, sharp_deg=55)


# ---------------------------------------------------------------------------- wings
WRIST_X = 0.110
WING_SCALE = 0.875


def wing_matrix():
    """Wing-local -> world for the left wing. Local x = outward span, y = back, z = up."""
    R = Matrix.Rotation(radians(-DIHEDRAL), 4, 'Y') @ Matrix.Rotation(radians(SWEEP), 4, 'Z')
    return Matrix.Translation(SHOULDER) @ R @ Matrix.Diagonal((WING_SCALE,) * 3 + (1.0,))


def wrist(v):
    """Bend the outer wing (beyond the wrist) down by WRIST_BEND about the local Y axis."""
    if v.x <= WRIST_X:
        return v
    k = smoothstep(WRIST_X, WRIST_X + 0.03, v.x)
    a = radians(WRIST_BEND) * k
    dx = v.x - WRIST_X
    return Vector((WRIST_X + dx * cos(a) + v.z * sin(a), v.y, -dx * sin(a) + v.z * cos(a)))


def build_wing(name, sx, parent):
    P = C.Part()
    W = wing_matrix()

    def place(base, ang, z, roll):
        L = (Matrix.Translation((base[0], base[1], z)) @ Matrix.Rotation(radians(ang), 4, 'Z') @
             Matrix.Rotation(radians(roll), 4, 'X'))
        return lambda x, y, h: W @ wrist(L @ Vector((x, y, h)))

    def wl(v):
        return W @ wrist(Vector(v))
    # secondaries (the two innermost are ivory tertials), outer ones stacked higher
    for j in range(8):
        t = j / 7
        base = (lerp(-0.004, 0.104, t), lerp(0.010, -0.020, t))
        Lf = lerp(0.074, 0.079, t)
        out = feather_outline(Lf, 0.0250, base_w=0.0170, tip_len=0.0150, point=0.25)
        plate(P, out, place(base, lerp(97, 86, t), lerp(-0.0064, -0.0008, t), 3.0), 0.0030,
              IVORY if j < 2 else FLIGHT, bevel=0.0007, rim=BRASS, rim_w=0.0012)
    # primaries: a fan from the hand, outermost on top
    for i in range(8):
        t = i / 7
        base = (lerp(0.112, 0.200, t), lerp(-0.024, -0.016, t))
        Lf = lerp(0.085, 0.114, t)
        w = lerp(0.0245, 0.0200, t)
        out = feather_outline(Lf, w, base_w=w * 0.70, tip_len=w * 0.95, point=0.50, shift=0.18)
        plate(P, out, place(base, lerp(86, 44, t), lerp(-0.0068, -0.0012, t), 3.0), 0.0030,
              FLIGHT, bevel=0.0007, rim=BRASS, rim_w=0.0012)
    # greater coverts (ivory, brass rims)
    for k in range(6):
        t = k / 5
        base = (lerp(0.004, 0.110, t), lerp(0.012, -0.016, t))
        out = feather_outline(0.031, 0.0225, base_w=0.0205, tip_len=0.0115, ns=1, nt=5)
        plate(P, out, place(base, lerp(93, 88, t), lerp(0.0004, 0.0024, t), 2.5), 0.0032,
              IVORY, bevel=0.0007, rim=BRASS, rim_w=0.0011)
    # primary coverts over the hand
    for k in range(4):
        t = k / 3
        base = (lerp(0.118, 0.186, t), lerp(-0.030, -0.024, t))
        out = feather_outline(lerp(0.032, 0.027, t), 0.0200, base_w=0.0180, tip_len=0.0105,
                              ns=1, nt=5)
        plate(P, out, place(base, lerp(82, 54, t), lerp(0.0006, 0.0018, t), 2.5), 0.0032,
              IVORY, bevel=0.0007, rim=BRASS, rim_w=0.0011)
    # lesser coverts (ivory scales) just behind the leading edge
    for k in range(5):
        t = k / 4
        base = (lerp(0.010, 0.104, t), lerp(-0.008, -0.034, t))
        out = feather_outline(0.024, 0.0215, base_w=0.0200, tip_len=0.0105, ns=1, nt=5)
        plate(P, out, place(base, lerp(94, 88, t), lerp(0.0030, 0.0046, t), 2.0), 0.0034,
              IVORY, bevel=0.0007, rim=BRASS, rim_w=0.0011)
    # leading-edge armour (ivory spar) and the continuous brass wing edge
    spar = [(0.000, -0.012, 0.0050), (0.040, -0.030, 0.0060), (0.085, -0.040, 0.0062),
            (0.118, -0.041, 0.0056), (0.146, -0.037, 0.0042)]
    sp_pts = C.spline3(spar, 3)
    rad = C.resample([0.0094, 0.0086, 0.0074, 0.0064, 0.0044], len(sp_pts))
    P.tube([wl(v) for v in sp_pts], [r * WING_SCALE for r in rad], 12, IVORY, caps='round',
           cap_segs=2, scale_xy=(1.0, 0.58), up=W.to_3x3() @ Vector((0, 0, 1)))
    edge = [(-0.002, -0.0195, 0.0036), (0.040, -0.0372, 0.0042), (0.085, -0.0472, 0.0042),
            (0.118, -0.0478, 0.0036), (0.152, -0.0430, 0.0024), (0.186, -0.0318, 0.0014),
            (0.216, -0.0150, 0.0008), (0.244, 0.0090, 0.0004), (0.266, 0.0360, 0.0002),
            (0.281, 0.0620, 0.0000)]
    e_pts = C.spline3(edge, 3)
    erad = C.resample([0.0030, 0.0029, 0.0028, 0.0026, 0.0023, 0.0020, 0.0018, 0.0016, 0.0014,
                       0.0011], len(e_pts))
    P.tube([wl(v) for v in e_pts], [r * WING_SCALE for r in erad], 8, BRASS, caps='round',
           cap_segs=2, scale_xy=(1.0, 0.85), up=W.to_3x3() @ Vector((0, 0, 1)))
    # wrist knuckle: brass rivet hub on top of the bend
    Mw = W @ Matrix.Translation((0.117, -0.040, 0.0))
    P.lathe([(0.0, 0.0118), (0.0026, 0.0114), (0.0040, 0.0100), (0.0044, 0.0080),
             (0.0044, 0.0000), (0.0, 0.0000)], 14, BRASS, matrix=Mw)
    # shoulder pauldron: ivory dome, brass rim, coral status light in a brass bezel
    Mp = W @ Matrix.Translation((0.010, -0.006, 0.0058))
    prof = [(0.0, 0.0080), (0.0026, 0.0079), (0.0034, 0.0075), (0.0040, 0.0071), (0.0048, 0.0075),
            (0.0056, 0.0071), (0.0095, 0.0062), (0.0132, 0.0045), (0.0158, 0.0022), (0.0168, 0.0004),
            (0.0168, -0.0040), (0.0, -0.0040)]
    ps = 20
    vr, fs = P.lathe(prof, ps, IVORY, matrix=Mp)
    nb = len(prof) - 3
    P.assign(fs[nb * ps:(nb + 1) * ps], CORAL)      # light lens (top fan)
    P.assign(fs[0:1 * ps], CORAL)
    P.assign(fs[1 * ps:4 * ps], BRASS)               # light bezel
    P.assign(fs[7 * ps:9 * ps], BRASS)               # rim
    # shoulder hub (brass) seated in the body socket
    n = Vector((1.0, 0.0, 0.55)).normalized()
    Mh = Matrix.Translation(SHOULDER - n * 0.006) @ n.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    P.lathe([(0, 0.0), (0.0102, 0.0), (0.0106, 0.0055), (0.0084, 0.0088), (0.0, 0.0094)],
            16, BRASS, matrix=Mh)
    if sx < 0:
        P.mirror_x()
    temps = [P.to_temp()]
    pv = Vector((SHOULDER.x * sx, SHOULDER.y, SHOULDER.z))
    return C.merge_to_object(name, temps, pivot=pv, parent=parent, sharp_deg=50)


# ---------------------------------------------------------------------------- tail
def build_tail(parent):
    P = C.Part()
    tilt = Matrix.Rotation(radians(-9.0), 4, 'X')

    def place(ang, x0, z, roll):
        return (Matrix.Translation(TAIL_P) @ tilt @ Matrix.Rotation(radians(90 - ang), 4, 'Z') @
                Matrix.Translation((x0, 0.0, z)) @ Matrix.Rotation(radians(roll), 4, 'X'))
    # nine-feather fan, centre feather on top
    for i in range(-4, 5):
        L = 0.142 - 0.0042 * abs(i) ** 1.25
        out = feather_outline(L, 0.0300, base_w=0.0170, tip_len=0.0150, ns=2, nt=7, point=0.1)
        M = place(i * 8.6, -0.010, 0.0016 - 0.0010 * abs(i), 3.0 * (1 if i > 0 else -1 if i < 0 else 0))
        plate(P, out, lambda x, y, h, M=M: M @ Vector((x, y, h)), 0.0032, FLIGHT, bevel=0.0007,
              rim=BRASS, rim_w=0.0013)
    # upper tail coverts (ivory)
    for (ang, L, w, z) in ((-15.0, 0.050, 0.0270, 0.0036), (15.0, 0.050, 0.0270, 0.0036),
                           (0.0, 0.060, 0.0320, 0.0050)):
        out = feather_outline(L, w, base_w=w * 0.85, tip_len=w * 0.55, ns=2, nt=5)
        M = place(ang, -0.014, z, 2.0 * (1 if ang > 0 else -1 if ang < 0 else 0))
        plate(P, out, lambda x, y, h, M=M: M @ Vector((x, y, h)), 0.0032, IVORY, bevel=0.0007,
              rim=BRASS, rim_w=0.0012)
    # tail mount: rounded brass saddle
    P.superellipsoid(TAIL_P + Vector((0, -0.004, 0.0035)), (0.0175, 0.0135, 0.0078), 0.55, 0.55,
                     16, 8, BRASS)
    temps = [P.to_temp()]
    return C.merge_to_object("Tail", temps, pivot=TAIL_P, parent=parent, sharp_deg=50)


def build_thruster(parent):
    p = C.Part()
    M = Matrix.Translation(THR_C)
    p.lathe([(0.0, -0.0016), (0.0050, -0.0018), (0.0100, -0.0016), (0.0140, -0.0010),
             (0.0152, -0.0002), (0.0152, 0.0010), (0.0, 0.0010)], 24, GLOW, matrix=M)
    tmp = p.to_temp()
    return C.merge_to_object("Thruster", [tmp], pivot=THR_C, parent=parent, sharp_deg=60)


# ---------------------------------------------------------------------------- main
def build():
    C.reset_scene()
    root = C.new_empty("Nuri", None, (0, 0, 0), size=0.1)
    body = build_body(root)
    head = build_head(body)
    lens = build_lens(head)
    beak = build_beak(head)
    wl = build_wing("Wing_L", 1, body)
    wr = build_wing("Wing_R", -1, body)
    tail = build_tail(body)
    thr = build_thruster(body)
    meshes = [body, head, lens, beak, wl, wr, tail, thr]
    C.bake_ao(meshes, dist=0.03, samples=64, floor=0.40, white=[lens, thr])
    return root


if __name__ == "__main__":
    root = build()
    C.summary(root)
    C.export_fbx(root, OUT)
    if RENDER:
        C.render_previews("nuri", root, res=(960, 720), samples=128, ground_z=-0.20, lens=70,
                          margin=1.08)
        C.render_ortho("nuri", root, [("front", 0, 0), ("side", 90, 0), ("back", 180, 0)],
                       res=(800, 800), samples=96)
        if EXTRA:
            C.render_ortho("nuri_dbg", root, [("top", 0, 89.9)], res=(800, 800), samples=32,
                           out_dir=C.DEBUG_DIR)
