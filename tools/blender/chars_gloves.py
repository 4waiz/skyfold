"""Courier glove pair (glove_L / glove_R) for SKYFOLD: The Last Flight.

Original procedural model (Awaiz Ahmed / Team Kanban), not AI-generated.
    blender -b --factory-startup -P tools/blender/chars_gloves.py [-- --no-render]

Each FBX:
    glove_L (empty)  = controller grip point (centre of the palm where a Quest controller
                       handle sits; the handle axis runs along Unity Y through it)
      Open           relaxed, slightly curled fingers   (pivot = grip point)
      Grip           fingers closed around the handle   (pivot = grip point)
      ANCHOR_wristui (glove_L only) centre of the bracer face; local Unity -Z points out of
                     the face, local +X toward the fingertips, local +Y toward the little finger
Only one of Open / Grip should be visible at a time. glove_L carries the brass-and-teal
folding-city bracer in both meshes.
Fingers point Blender -Y (Unity +Z). Left palm faces Blender -X (Unity +X); the right glove
is the mirror image (palm faces Unity -X). Thumb up (+Z).

Detail pass: segmented fingers with joint creases, teal knuckle pads and sandstone grip tips;
a teal knuckle guard with brass rivets and a brass-rimmed pearl back plate edged with raised
stitching; a stitched sandstone palm pad; a cuff with brass trim. glove_L's bracer: teal
housing, raised brass bezel round a dark screen with a glowing border, side buttons, status
lights, a glowing edge strip, hinged fold plates and two brass straps. glove_R carries a
leather strap with a brass buckle instead. Open and Grip share everything except the finger and
thumb pose and the cupped palm.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C
from chars_common import Vector, Matrix, radians, sin, cos, pi, sqrt, atan2
import bpy, bmesh
from mathutils.bvhtree import BVHTree

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS

IVORY, TEAL, BRASS, INK, GLOW, SAND, PEARL = ('SKY_Ivory', 'SKY_Teal', 'SKY_Brass', 'SKY_Ink',
                                              'SKY_TealGlow', 'SKY_Sandstone', 'SKY_Pearl')

# name, MCP root (x, y, z), phalanx lengths, radius, open curl (MCP, PIP, DIP deg), spread (+ = toward thumb)
FINGERS = [
    ('index', (0.031, -0.014, 0.0250), (0.032, 0.021, 0.017), 0.0093, (16, 24, 12), 4),
    ('middle', (0.031, -0.012, 0.0085), (0.035, 0.023, 0.018), 0.0096, (19, 28, 14), 0),
    ('ring', (0.030, -0.008, -0.0075), (0.033, 0.022, 0.017), 0.0091, (23, 32, 16), -3),
    ('pinky', (0.028, -0.002, -0.0225), (0.026, 0.017, 0.015), 0.0082, (28, 36, 18), -7),
]
R_WRAP = 0.0288          # finger centre-line radius around the handle in the grip pose
PALM_C = Vector((0.032, 0.024, 0.0))
PALM_R = (0.0145, 0.040, 0.037)
CUFF_C = Vector((0.032, 0.0, 0.0))
CUFF_SCALE = (0.80, 1.0, 1.10)
DEVICE_Y = 0.081
FINGER_SXY = (1.08, 0.92)
# cuff outer profile (radius before CUFF_SCALE, y) from the wrist to the rolled lip
CUFF_PROFILE = [(0.0290, 0.050), (0.0306, 0.058), (0.0322, 0.080), (0.0340, 0.098),
                (0.0358, 0.1035), (0.0352, 0.1070), (0.0328, 0.1078), (0.0310, 0.1060),
                (0.0302, 0.0960)]


def cuff_r(y):
    """Outer cuff radius (before CUFF_SCALE) at height y along the wrist."""
    pts = CUFF_PROFILE[:5]
    if y <= pts[0][1]:
        return pts[0][0]
    for (r0, y0), (r1, y1) in zip(pts, pts[1:]):
        if y0 <= y <= y1:
            return r0 + (r1 - r0) * (y - y0) / (y1 - y0)
    return pts[-1][0]


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def rounded_rect(w, h, r, n=3):
    pts = []
    for (cx, cy, a0) in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                         (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(n + 1):
            a = radians(a0 + 90 * k / n)
            pts.append((cx + r * cos(a), cy + r * sin(a)))
    return pts


def back_matrix(x, y, z):
    """Local XY plane -> world (Y, Z) plane, local +Z -> world +X."""
    return Matrix(((0, 0, 1, x), (1, 0, 0, y), (0, 1, 0, z), (0, 0, 0, 1)))


def cup(v):
    """Grip pose: the palm cups (both edges come toward the palm side, -X)."""
    return v - Vector((0.0050 * ((v.z - PALM_C.z) / PALM_R[2]) ** 2, 0, 0))


def chain_open(root, lens, curls, spread):
    S = Matrix.Rotation(radians(-spread), 3, 'X')
    A = S @ Vector((0, 0, 1))
    d0 = S @ Vector((0, -1, 0))
    pts = [Vector(root)]
    ang = 0.0
    p = Vector(root)
    for l, c in zip(lens, curls):
        ang += c
        p = p + (Matrix.Rotation(radians(-ang), 3, A) @ d0) * l
        pts.append(p.copy())
    return pts, d0


def chain_grip(root, lens):
    z = root[2]
    K = Vector((root[0], root[1]))
    phi = atan2(K.y, K.x)
    out = [Vector((K.x, K.y, z))]
    X = K
    for l in lens:
        f = phi
        Q = X
        for _ in range(4000):
            f -= 0.001
            Q = Vector((R_WRAP * cos(f), R_WRAP * sin(f)))
            if (Q - X).length >= l:
                break
        out.append(Vector((Q.x, Q.y, z)))
        X, phi = Q, f
    return out, Vector((0, -1, 0))


def keyed(keys, n):
    """Piecewise-linear profile over spline sample indices: keys = [(index, value), ...]."""
    out = []
    for i in range(n):
        for (a, va), (b, vb) in zip(keys, keys[1:]):
            if a <= i <= b:
                t = (i - a) / (b - a) if b > a else 0
                out.append(va * (1 - t) + vb * t)
                break
        else:
            out.append(keys[-1][1])
    return out


# ---------------------------------------------------------------------------- plates
def densify(pts, max_len):
    """Insert points along a closed outline so no edge is longer than max_len (lets a plate
    wrap a curved surface instead of cutting chords through it)."""
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


def plate(part, outline, F, thick, mat, bevel=0.0005, rim=None, rim_w=0.0, rim_wall=True,
          fill=0, fill_to=0.0):
    """Beveled plate from a CCW 2D outline; F(x, y, h) -> world point (h = 0 bottom .. thick).
    fill adds concentric top rings (inset up to fill_to) so a plate wrapped on a curved surface
    keeps its top on the curve instead of a flat cap cutting under it."""
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
        b0 = nrim - (2 if rim_w > 0 else 1) - (1 if rim_wall else 0)
        part.assign(faces[b0 * n: nrim * n], rim)
    return faces


def planar_ring(part, outline, section, origin, au, av, an, mat):
    """Sweep a closed section [(a, b)] (a = outward offset in the plane, b = height along an)
    round a closed CCW outline lying in the plane origin + u * au + v * av."""
    n = len(outline)
    offs = []
    for i in range(n):
        p0, p1, p2 = Vector(outline[i - 1]), Vector(outline[i]), Vector(outline[(i + 1) % n])
        e0, e1 = (p1 - p0).normalized(), (p2 - p1).normalized()
        n0, n1 = Vector((e0.y, -e0.x)), Vector((e1.y, -e1.x))
        m = (n0 + n1).normalized()
        offs.append(m / max(m.dot(n0), 0.4))
    rings = []
    for (a, b) in section:
        ring = []
        for i in range(n):
            q = Vector(outline[i]) + offs[i] * a
            ring.append(origin + au * q.x + av * q.y + an * b)
        rings.append(ring)
    vr, faces = part.grid(rings, mat, True, None, None, closed_v=True)
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

    def ray(self, o, d, fallback=None):
        """First hit along d from o; on a miss, the closest point to `fallback` (or to o)."""
        loc, nrm, idx, dist = self.bvh.ray_cast(Vector(o), Vector(d).normalized())
        if loc is None:
            return self.near(o if fallback is None else fallback)
        return loc, self._n(loc, idx)


def conform(surf, to3d, base, axis=None):
    """F(x, y, h) for plate(): layout point -> surface point (+ normal * (base + h))."""
    cache = {}

    def F(x, y, h):
        k = (round(x, 8), round(y, 8))
        if k not in cache:
            p = to3d(x, y)
            if axis is not None:
                a = Vector(axis).normalized()
                cache[k] = surf.ray(p - a * 0.2, a, p)
            else:
                cache[k] = surf.near(p)
        loc, n = cache[k]
        return loc + n * (base + h)
    return F


def frame(n, up=(0, 0, 1)):
    n = Vector(n).normalized()
    return n.to_track_quat('Z', 'Y').to_matrix().to_4x4()


def dome(part, p, n, r, h, segs, mat, cap_mat=None, sink=0.0008):
    """Small domed fitting (rivet / button / light) standing on a surface point along n."""
    M = Matrix.Translation(p) @ frame(n)
    prof = [(0.0, h), (r * 0.72, h * 0.80), (r, 0.0), (r * 0.92, -sink), (0.0, -sink)]
    vr, fs = part.lathe(prof, segs, mat, matrix=M)
    if cap_mat:
        part.assign(fs[0:segs], cap_mat)
        part.assign(fs[2 * segs:3 * segs], cap_mat)      # top fan
    return fs


def stitches(part, F, outline, h, mat, dash=0.0027, gap=0.0019, w=0.0010, t=0.0006):
    """Raised stitch dashes along a closed CCW layout outline mapped by F at height h."""
    pts = [F(x, y, h) for (x, y) in outline]
    nrm = [(F(x, y, h + 0.001) - F(x, y, h)).normalized() for (x, y) in outline]
    n = len(pts)
    seg = []
    total = 0.0
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        seg.append((a, b, nrm[i], nrm[(i + 1) % n], total))
        total += (b - a).length
    k = max(1, int(total / (dash + gap)))
    step = total / k
    for j in range(k):
        s = j * step + step * 0.5
        for (a, b, na, nb, s0) in seg:
            L = (b - a).length
            if s0 <= s <= s0 + L and L > 1e-9:
                u = (s - s0) / L
                p = a + (b - a) * u
                nn = (na + (nb - na) * u).normalized()
                d = (b - a).normalized()
                side = nn.cross(d).normalized()
                d = side.cross(nn).normalized()
                q0, q1 = p - d * dash * 0.5, p + d * dash * 0.5
                base = -nn * t * 0.4
                tri = [side * (w * 0.5) + base, -side * (w * 0.5) + base, nn * t]
                bm = part.bm
                va = [bm.verts.new(q0 + o) for o in tri]
                vb = [bm.verts.new(q1 + o) for o in tri]
                fs = [bm.faces.new((va[0], va[1], va[2])), bm.faces.new((vb[2], vb[1], vb[0]))]
                for i in range(3):
                    j = (i + 1) % 3
                    fs.append(bm.faces.new((va[i], vb[i], vb[j], va[j])))
                part.assign(fs, mat)
                break


# ---------------------------------------------------------------------------- tubes
def frames(pts, up):
    """Tangents and parallel-transported up vectors along a polyline (as Part.tube)."""
    P = [Vector(p) for p in pts]
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
    return T, U


class TubeLine:
    """The surface of a Part.tube (elliptical section, parallel-transported frame), so pads can
    be wrapped round a finger exactly."""

    def __init__(self, pts, radii, up, sxy=FINGER_SXY):
        self.P = [Vector(p) for p in pts]
        self.R = list(radii)
        self.T, self.U = frames(self.P, up)
        self.sx, self.sy = sxy
        self.cum = [0.0]
        for a, b in zip(self.P, self.P[1:]):
            self.cum.append(self.cum[-1] + (b - a).length)

    def at(self, x):
        c = self.cum
        x = max(0.0, min(c[-1], x))
        i = 0
        while i < len(c) - 2 and x > c[i + 1]:
            i += 1
        t = (x - c[i]) / max(1e-12, c[i + 1] - c[i])
        P = self.P[i].lerp(self.P[i + 1], t)
        T = self.T[i].lerp(self.T[i + 1], t).normalized()
        U = self.U[i].lerp(self.U[i + 1], t)
        U = (U - T * U.dot(T)).normalized()
        S = U.cross(T).normalized()
        R = self.R[i] + (self.R[i + 1] - self.R[i]) * t
        return P, T, U, S, R

    def point(self, x, a, off):
        P, T, U, S, R = self.at(x)
        A, B = self.sx * R, self.sy * R
        p = P + S * (A * cos(a)) + U * (B * sin(a))
        n = (S * (B * cos(a)) + U * (A * sin(a))).normalized()
        return p + n * off

    def pad_F(self, x0, base, a0=pi / 2):
        def F(x, y, h):
            R = self.at(x0 + x)[4]
            a = a0 + y / (0.5 * (self.sx + self.sy) * R)
            return self.point(x0 + x, a, base + h)
        return F


def finger(soft, pads, joints, d0, r, curl_axis):
    root_in = joints[0] - d0 * 0.016
    pts = C.spline3([root_in] + joints, 3)        # samples: 3 MCP, 6 PIP, 9 DIP, 12 tip
    prof = keyed([(0, 1.0), (3, 1.05), (4.5, 0.95), (5.4, 0.97), (6, 0.915), (6.6, 0.96),
                  (7.5, 0.905), (8.4, 0.91), (9, 0.855), (9.6, 0.90), (10, 0.93), (10.5, 0.92),
                  (12, 0.80)], len(pts))
    rad = [r * k for k in prof]
    segs = 10
    vr, fs = soft.tube(pts, rad, segs, IVORY, caps='round', cap_segs=2, scale_xy=FINGER_SXY,
                       up=(1, 0, 0))
    nb = len(pts) + 2 * 2 - 1                      # bands incl. the two cap rings each end
    soft.assign(fs[(2 + 10) * segs:nb * segs], SAND)          # grip tip
    soft.assign(fs[(nb + 1) * segs:(nb + 2) * segs], SAND)    # tip fan
    line = TubeLine(pts, rad, (1, 0, 0))
    # teal knuckle pad on the back of the proximal phalanx
    x0, x1 = line.cum[3], line.cum[6]
    L, wk = (x1 - x0) * 0.74, 0.0128
    out = rounded_rect(L, wk, min(L, wk) * 0.40, 2)
    plate(pads, out, line.pad_F((x0 + x1) * 0.5, -0.0002), 0.0017, TEAL, bevel=0.0005, fill=2,
          fill_to=min(L, wk) * 0.36)


def thumb(soft, pads, grip):
    if grip:
        ctrl = [(0.029, 0.030, 0.024), (0.016, 0.012, 0.035), (0.000, -0.003, 0.039),
                (-0.013, -0.013, 0.039)]
    else:
        ctrl = [(0.029, 0.030, 0.024), (0.018, 0.010, 0.035), (0.007, -0.006, 0.041),
                (0.001, -0.019, 0.042)]
    pts = C.spline3(ctrl, 3)                       # samples: 3 MCP, 6 IP, 9 tip
    prof = keyed([(0, 1.0), (3, 0.97), (5.4, 0.93), (6, 0.88), (6.6, 0.92), (7, 0.94),
                  (7.6, 0.92), (9, 0.78)], len(pts))
    rad = [0.0106 * k for k in prof]
    segs = 10
    up = (1, 0, 0.4)
    vr, fs = soft.tube(pts, rad, segs, IVORY, caps='round', cap_segs=2, scale_xy=(1.06, 0.94),
                       up=up)
    nb = len(pts) + 2 * 2 - 1
    soft.assign(fs[(2 + 7) * segs:nb * segs], SAND)
    soft.assign(fs[(nb + 1) * segs:(nb + 2) * segs], SAND)
    line = TubeLine(pts, rad, up, (1.06, 0.94))
    x0, x1 = line.cum[3], line.cum[6]
    L = (x1 - x0) * 0.66
    out = rounded_rect(L, 0.0132, min(L, 0.0132) * 0.40, 2)
    plate(pads, out, line.pad_F((x0 + x1) * 0.5, -0.0002), 0.0017, TEAL, bevel=0.0005, fill=2,
          fill_to=min(L, 0.0132) * 0.36)


# ---------------------------------------------------------------------------- hand
def build_hand(name, grip, device, parent, mirror=False):
    palm = C.Part()      # palm block (also the reference surface for plates)
    soft = C.Part()      # fingers, thumb, cuff
    pads = C.Part()      # plates, pads, fittings

    # palm block: rounded, tapering toward the wrist (cupped when gripping)
    vs, fs = palm.superellipsoid(PALM_C, PALM_R, 0.62, 0.62, 22, 12, IVORY, pole_axis='Y')
    vs = list({v for f in fs for v in f.verts})

    def taper(v):
        k = 1.0 - 0.14 * smoothstep(-0.005, 0.064, v.y)
        kx = 1.0 - 0.06 * smoothstep(0.0, 0.064, v.y)
        return Vector((PALM_C.x + (v.x - PALM_C.x) * kx, v.y, PALM_C.z + (v.z - PALM_C.z) * k))
    palm.deform(vs, taper)
    if grip:
        palm.deform(vs, cup)
    surf = Surf(palm)
    # thenar (thumb root) pad
    soft.superellipsoid(Vector((0.025, 0.024, 0.022)), (0.0125, 0.022, 0.0145), 0.8, 0.8, 12, 8,
                        IVORY)
    for (nm, root, lens, r, curls, spread) in FINGERS:
        if grip:
            joints, d0 = chain_grip(root, lens)
            A = Vector((0, 0, 1))
        else:
            joints, d0 = chain_open(root, lens, curls, spread)
            A = Matrix.Rotation(radians(-spread), 3, 'X') @ Vector((0, 0, 1))
        finger(soft, pads, joints, d0, r, A)
    thumb(soft, pads, grip)

    # back of the hand: pearl shield with a brass rim, stitched to the glove, two rivets
    def back3d(x, y):
        return Vector((0.10, 0.025 + x, y))
    out = rounded_rect(0.046, 0.050, 0.0125, 3)
    Fb = conform(surf, back3d, -0.0002, axis=(-1, 0, 0))
    plate(pads, out, Fb, 0.0017, PEARL, bevel=0.0006, rim=BRASS, rim_w=0.0012, fill=1,
          fill_to=0.010)
    stitches(pads, conform(surf, back3d, 0.0, axis=(-1, 0, 0)),
             [(x * 1.16, y * 1.12) for (x, y) in rounded_rect(0.046, 0.050, 0.0125, 3)], 0.0, PEARL)
    for zz in (0.012, -0.012):
        loc, n = surf.ray(Vector((0.10, 0.044, zz)), Vector((-1, 0, 0)))
        dome(pads, loc + n * 0.0015, n, 0.0019, 0.0011, 8, BRASS)
    # knuckle guard: teal bridge over the MCP joints with a brass rivet per knuckle
    def kn3d(x, y):
        return Vector((0.10, -0.0045 + x, y - 0.0005))
    out = rounded_rect(0.0125, 0.060, 0.0055, 3)
    plate(pads, out, conform(surf, kn3d, -0.0003, axis=(-1, 0, 0)), 0.0026, TEAL, bevel=0.0007,
          rim=BRASS, rim_w=0.0008, fill=1, fill_to=0.0036)
    for (nm, root, lens, r, curls, spread) in FINGERS:
        loc, n = surf.ray(Vector((0.10, -0.0045, root[2] - 0.0005)), Vector((-1, 0, 0)))
        dome(pads, loc + n * 0.0022, n, 0.0020, 0.0012, 8, BRASS)
    # palm grip pad (sandstone) with stitching
    def palm3d(x, y):
        return Vector((-0.05, 0.023 + x, y - 0.001))
    out = rounded_rect(0.048, 0.054, 0.014, 3)
    Fp = conform(surf, palm3d, -0.0002, axis=(1, 0, 0))
    plate(pads, out, Fp, 0.0020, SAND, bevel=0.0006, fill=1, fill_to=0.0045)
    stitches(pads, Fp, inset2d(out, 0.0026), 0.0020, PEARL)

    # cuff (deep teal), elliptical, rolled lip, recessed dark wrist opening
    cuff = C.Part()
    S = Matrix.Diagonal((*CUFF_SCALE, 1.0))
    Mc = Matrix.Translation(CUFF_C) @ S
    prof = [(0.0, 0.050)] + CUFF_PROFILE + [(0.0, 0.0960)]
    seg = 24
    vr, cf = cuff.lathe(prof, seg, TEAL, matrix=Mc, axis='Y')
    nb = len(prof) - 3
    cuff.assign(cf[(nb + 1) * seg:(nb + 2) * seg], INK)      # wrist opening (dark, recessed)
    cuff.assign(cf[(nb - 1) * seg:nb * seg], INK)            # inner wall of the lip
    csurf = Surf(cuff)
    # brass trim ring where the cuff meets the hand
    Mr = Matrix.Translation(CUFF_C + Vector((0, 0.0575, 0))) @ S @ \
        Matrix.Rotation(radians(90), 4, 'X')
    soft.torus(0.0310, 0.0023, seg, 5, BRASS, matrix=Mr)
    if device:
        bracer(pads, soft, csurf, S)
    else:
        strap(pads, csurf, S, side=1)
    if mirror:
        for prt in (palm, soft, pads, cuff):
            prt.mirror_x()
    temps = [palm.to_temp(), soft.to_temp(), pads.to_temp(), cuff.to_temp()]
    return C.merge_to_object(name, temps, pivot=(0, 0, 0), parent=parent, sharp_deg=50)


def cuff_F(csurf, S, y0, a0, base):
    """Layout on the cuff: x along the wrist (Blender +Y from y0), y = arc length round the
    cuff starting at angle a0 (0 = back of the wrist, +X)."""
    def to3d(x, y):
        a = a0 + y / 0.030
        d = S @ Vector((cos(a), 0.0, sin(a)))
        return CUFF_C + Vector((0, y0 + x, 0)) + d * 0.030
    cen = CUFF_C

    def F(x, y, h):
        p = to3d(x, y)
        loc, n = csurf.ray(p + (p - Vector((cen.x, p.y, cen.z))).normalized() * 0.03,
                           -(p - Vector((cen.x, p.y, cen.z))).normalized())
        return loc + n * (base + h)
    return F


def bracer(pads, soft, csurf, S):
    """Folding-city bracer on the back of the left wrist; its screen face is ANCHOR_wristui."""
    fx = face_x()
    top = fx - 0.0027                       # housing top (screen glass sits just below the face)
    hx0 = 0.0555
    # two brass straps round the cuff, under the housing ends
    for y in (DEVICE_Y - 0.0190, DEVICE_Y + 0.0190):
        Mb = Matrix.Translation(CUFF_C + Vector((0, y, 0))) @ S @ Matrix.Rotation(radians(90), 4, 'X')
        soft.torus(cuff_r(y) + 0.0004, 0.0021, 22, 4, BRASS, matrix=Mb, scale_minor=(0.7, 1.7))
    # housing (teal, rounded)
    pads.rbox(Vector(((hx0 + top) / 2, DEVICE_Y, 0.0)), (top - hx0, 0.050, 0.0380), 0.0036, 2, TEAL)
    # raised brass bezel round the screen opening
    sw, sh, sr = 0.0300, 0.0270, 0.0052
    opening = rounded_rect(sw, sh, sr, 4)
    planar_ring(pads, opening, [(0.0, -0.0010), (0.0, 0.0022), (0.0007, 0.0030), (0.0024, 0.0030),
                                (0.0032, 0.0022), (0.0032, -0.0010)],
                Vector((top, DEVICE_Y, 0.0)), Vector((0, 1, 0)), Vector((0, 0, 1)),
                Vector((1, 0, 0)), BRASS)
    # dark screen glass just under the anchor face, with a thin glowing border
    glass = rounded_rect(sw + 0.0008, sh + 0.0008, sr + 0.0004, 4)
    plate(pads, glass, lambda x, y, h: Vector((top - 0.0006 + h, DEVICE_Y + x, y)), 0.0024, INK,
          bevel=0.0004)
    planar_ring(pads, rounded_rect(sw - 0.0036, sh - 0.0036, sr - 0.0018, 4),
                [(0.0, 0.0), (0.0007, 0.0), (0.00035, 0.0003)],
                Vector((top + 0.0018, DEVICE_Y, 0.0)), Vector((0, 1, 0)), Vector((0, 0, 1)),
                Vector((1, 0, 0)), GLOW)
    # status lights on the elbow end of the housing top, glow strip on the fingertip end face
    for zz in (-0.0075, 0.0, 0.0075):
        dome(pads, Vector((top, DEVICE_Y + 0.0215, zz)), Vector((1, 0, 0)), 0.0015, 0.0009, 8, GLOW)
    pads.rbox(Vector(((hx0 + top) / 2 + 0.0008, DEVICE_Y - 0.0251, 0.0)), (0.0040, 0.0016, 0.020),
              0.0006, 1, GLOW)
    # side buttons (thumb side: two round, little-finger side: one long)
    zc = 0.0190
    for yy in (DEVICE_Y - 0.007, DEVICE_Y + 0.007):
        dome(pads, Vector(((hx0 + top) / 2 + 0.0010, yy, zc)), Vector((0, 0, 1)), 0.0024, 0.0013, 10,
             BRASS)
    pads.rbox(Vector(((hx0 + top) / 2 + 0.0010, DEVICE_Y, -zc - 0.0006)), (0.0034, 0.016, 0.0024),
              0.0010, 1, BRASS)
    # hinged fold plates (pearl) lying on the cuff either side of the housing, brass hinge pins
    for sgn in (1, -1):
        for k, (yy, wd) in enumerate(((DEVICE_Y - 0.0105, 0.020), (DEVICE_Y + 0.0105, 0.020))):
            a0 = sgn * radians(36.0)
            F = cuff_F(csurf, S, yy, a0, -0.0003 + 0.0006 * k)
            out = rounded_rect(wd, 0.0105, 0.0030, 1)
            plate(pads, out, F, 0.0016, PEARL, bevel=0.0005, rim=BRASS, rim_w=0.0007, fill=1,
                  fill_to=0.0035)
        hy = Vector((top - 0.0030, DEVICE_Y, sgn * 0.0192))
        M = Matrix.Translation(hy) @ Matrix.Rotation(radians(90), 4, 'X')
        pads.cylinder(0.0014, 0.040, 8, BRASS,
                      matrix=Matrix.Translation(hy + Vector((0, -0.020, 0))) @
                      Matrix.Rotation(radians(-90), 4, 'X'))


def strap(pads, csurf, S, side=1):
    """Leather strap with a brass buckle across the back of the wrist (glove_R)."""
    F = cuff_F(csurf, S, DEVICE_Y - 0.0075, -0.95, -0.0003)
    out = densify(rounded_rect(0.015, 0.060, 0.0035, 2), 0.0045)
    out = [(x + 0.0075, y + 0.030) for (x, y) in out]
    plate(pads, out, F, 0.0018, SAND, bevel=0.0005, fill=1, fill_to=0.0050)
    stitches(pads, F, inset2d(out, 0.0019), 0.0018, PEARL, dash=0.0022, gap=0.0016)
    # buckle: brass frame + tongue bar on the back of the wrist
    Fb = cuff_F(csurf, S, DEVICE_Y, 0.0, 0.0012)
    o = Fb(0.0, 0.0, 0.0)
    n = (Fb(0.0, 0.0, 0.001) - o).normalized()
    au = Vector((0, 1, 0))
    av = n.cross(au).normalized()
    planar_ring(pads, rounded_rect(0.0110, 0.0150, 0.0026, 3),
                [(0.0, -0.0010), (0.0, 0.0018), (0.0006, 0.0024), (0.0020, 0.0024), (0.0026, 0.0018),
                 (0.0026, -0.0010)], o, au, av, n, BRASS)
    pads.rbox(Vector((0, 0, 0)), (0.0020, 0.0016, 0.016), 0.0006, 1, BRASS,
              matrix=Matrix.Translation(o + n * 0.0012) @ Matrix((au, n, av)).transposed().to_4x4())


def face_x():
    return CUFF_C.x + 0.0334 * CUFF_SCALE[0] + 0.0040 + 0.0060 + 0.0008


def build(side):
    C.reset_scene()
    root = C.new_empty("glove_%s" % side, None, (0, 0, 0), size=0.04)
    left = side == 'L'
    # the right glove is the mirrored left build (x -> -x: palm faces Blender +X = Unity -X)
    op = build_hand("Open", False, left, root, mirror=not left)
    gp = build_hand("Grip", True, left, root, mirror=not left)
    if left:
        R = Matrix(((0, 1, 0), (1, 0, 0), (0, 0, -1)))   # local X=+Y, Y=+X, Z=-Z (Blender)
        C.new_empty("ANCHOR_wristui", root, (face_x(), DEVICE_Y, CUFF_C.z), rot=R, size=0.02,
                    kind='ARROWS')

    C.bake_ao([op], dist=0.03, samples=64, floor=0.42)
    C.bake_ao([gp], dist=0.03, samples=64, floor=0.42)
    return root, op, gp


if __name__ == "__main__":
    for side in ('L', 'R'):
        root, op, gp = build(side)
        C.summary(root)
        C.export_fbx(root, os.path.join(C.MODELS, 'Characters', 'glove_%s.fbx' % side))
        if RENDER:
            # preview: Open on the left, Grip shifted beside it (render only, not exported)
            gp.location.z += 0.12
            bpy.context.view_layer.update()
            C.render_previews("glove_%s" % side, root, res=(960, 720), samples=128,
                              ground_z=-0.06, lens=70, margin=1.12,
                              views=(("fl", 38, 22), ("br", -142, 24)))
