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
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C
from chars_common import Vector, Matrix, Euler, Quaternion, radians, sin, cos, pi, sqrt
import bpy

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS
EXTRA = '--extra' in ARGS
OUT = os.path.join(C.MODELS, 'Characters', 'nuri.fbx')

IVORY, BRASS, INK, GLOW, TEAL = 'SKY_Ivory', 'SKY_Brass', 'SKY_Ink', 'SKY_TealGlow', 'SKY_Teal'
HOOD = INK if '--hood=teal' not in ARGS else TEAL   # falcon hood / brow / malar wedge

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


def build_body(parent):
    p = C.Part()
    shell(p, body_pt, body_center, 13, 18, lambda s, ph: s * pi, [],
          [(0.0, 0.05, 0.30, 0.86), (0.62 * pi, 0.05, 0.22, 0.88), (1.38 * pi, 0.05, 0.22, 0.88)],
          0.0012, lambda s, ph, g: INK if g > 0.3 else IVORY)
    # neck collar (brass) + dark neck core so the head can turn without gaps
    ax = (HEAD_C - NECK).normalized()
    M = Matrix.Translation(NECK) @ ax.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    p.torus(0.0225, 0.0042, 16, 4, BRASS, matrix=M @ Matrix.Translation((0, 0, -0.002)))
    p.cylinder(0.0205, 0.030, 12, INK, matrix=M @ Matrix.Translation((0, 0, -0.012)), caps=False)
    # shoulder sockets (ink cup + brass ring), both sides
    for sx in (1, -1):
        s = Vector((SHOULDER.x * sx, SHOULDER.y, SHOULDER.z))
        n = Vector((sx * 1.0, 0.0, 0.55)).normalized()
        Ms = Matrix.Translation(s - n * 0.004) @ n.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        p.lathe([(0, -0.006), (0.0120, -0.006), (0.0130, 0.0), (0.0120, 0.0018), (0, 0.0018)],
                12, INK, matrix=Ms)
    # thruster housing (ink) with a brass lip
    Mt = Matrix.Translation(THR_C)
    vr, fs = p.lathe([(0.0, 0.002), (0.0152, 0.002), (0.0156, -0.0004), (0.0190, -0.0010),
                      (0.0212, 0.0022), (0.0205, 0.0100), (0.0, 0.012)], 16, INK, matrix=Mt)
    p.assign(fs[2 * 16:3 * 16], BRASS)
    tmp = p.to_temp()
    return C.merge_to_object("Body", [tmp], pivot=(0, 0, 0), parent=parent, sharp_deg=48)


# ---------------------------------------------------------------------------- head
HEAD = dict(Rf=0.040, Rb=0.043, Rs=0.0425, Rt=0.0415, Rd=0.0385)
S_HOOD = 0.42


def theta_hood(ph):
    a = abs(((ph + pi) % (2 * pi)) - pi)          # 0 top .. pi bottom
    t = 0.24 * pi + 0.22 * pi * (1 - cos(a)) / 2 + 0.34 * pi * smoothstep(0.55 * pi, 0.95 * pi, a)
    t -= 0.19 * pi * math.exp(-((a - 0.68 * pi) / (0.115 * pi)) ** 2)   # malar wedge
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
    # brow: the hood edge lifts slightly over the lens
    brow = math.exp(-((th - 0.25 * pi) / 0.10) ** 2) * max(0.0, cos(ph)) ** 2
    d = (p - HEAD_C).normalized()
    return p + d * 0.0030 * brow


def build_head(parent):
    p = C.Part()

    def mat(s, ph, g):
        if g > 0.3:
            # spine groove on the dark hood becomes a slim brass inlay
            return BRASS if (s > S_HOOD + 0.03 and cdist(ph, 0.0) < 0.06) else INK
        return HOOD if s > S_HOOD else IVORY
    shell(p, head_pt, lambda th, ph: HEAD_C, 13, 24, head_theta, [(S_HOOD, 0.022)],
          [(0.0, 0.045, S_HOOD + 0.02, 0.86)], 0.0011, mat)
    # lens bezel (ink) around the forward (-Y) axis, brass trim on its face
    Mf = Matrix.Translation(LENS_C) @ Matrix.Rotation(radians(90), 4, 'X')  # local +Z -> -Y
    vr, fs = p.lathe([(0.0158, -0.0045), (0.0158, 0.0028), (0.0170, 0.0052), (0.0186, 0.0058),
                      (0.0202, 0.0054), (0.0216, 0.0034), (0.0221, 0.0), (0.0216, -0.0120),
                      (0.0158, -0.0120)], 20, INK, matrix=Mf)
    p.assign(fs[3 * 20:4 * 20], BRASS)
    tmp = p.to_temp()
    return C.merge_to_object("Head", [tmp], pivot=NECK, parent=parent, sharp_deg=48)


def build_lens(parent):
    p = C.Part()
    Mf = Matrix.Translation(LENS_C) @ Matrix.Rotation(radians(90), 4, 'X')
    prof = [(0.0, 0.0024), (0.0034, 0.00232), (0.0058, 0.0022),     # pupil (deep teal)
            (0.0064, 0.00215), (0.0088, 0.0019),                     # glowing iris ring
            (0.0094, 0.00185), (0.0104, 0.0017),                     # thin dark ring
            (0.0110, 0.0016), (0.0134, 0.0009), (0.0151, 0.0000),    # lens body (glow)
            (0.0156, -0.0014), (0.0156, -0.0040), (0.0, -0.0040)]
    seg = 18
    vr, faces = p.lathe(prof, seg, GLOW, matrix=Mf)
    for b in (0, 1, 4, 5):          # band b = between profile points b+1 and b+2
        p.assign(faces[b * seg:(b + 1) * seg], TEAL)
    nb = len(prof) - 3
    p.assign(faces[nb * seg:nb * seg + seg], TEAL)   # front pole fan
    tmp = p.to_temp()
    return C.merge_to_object("Lens", [tmp], pivot=LENS_C, parent=parent, sharp_deg=60)


def build_beak(parent):
    p = C.Part()
    f = Vector((0, -1, 0))
    z = Vector((0, 0, 1))
    b = BEAK_B
    pts = [b - f * 0.005 + z * 0.002, b + f * 0.007 + z * 0.0012, b + f * 0.0170 - z * 0.0018,
           b + f * 0.0258 - z * 0.0085, b + f * 0.0280 - z * 0.0155, b + f * 0.0252 - z * 0.0212]
    rad = [0.0100, 0.0090, 0.0072, 0.0050, 0.0030, 0.0012]
    sc = [(0.80, 1.0), (0.78, 1.0), (0.72, 1.0), (0.66, 1.0), (0.62, 1.0), (0.6, 1.0)]
    p.tube(pts, rad, 8, BRASS, caps='round', cap_segs=2, scale_xy=sc, up=(0, 0, 1))
    lp = [b - f * 0.002 - z * 0.0068, b + f * 0.0072 - z * 0.0094, b + f * 0.0130 - z * 0.0118]
    p.tube(lp, [0.0050, 0.0038, 0.0018], 8, INK, caps='round', cap_segs=2,
           scale_xy=(0.9, 0.7), up=(0, 0, 1))
    tmp = p.to_temp()
    return C.merge_to_object("Beak", [tmp], pivot=BEAK_B, parent=parent, sharp_deg=55)


# ---------------------------------------------------------------------------- wings
# Wing-local top-view outlines (x = outward from the shoulder, y = backward), metres.
COVERTS = [(-0.006, -0.010), (0.045, -0.032), (0.090, -0.046), (0.125, -0.042),
           (0.141, -0.026), (0.132, 0.004), (0.095, 0.021), (0.055, 0.031), (0.012, 0.033),
           (-0.008, 0.012)]
SECONDARIES = [(-0.004, -0.004), (0.050, -0.024), (0.095, -0.037), (0.128, -0.030),
               (0.134, 0.020), (0.126, 0.064), (0.112, 0.080), (0.096, 0.076), (0.078, 0.086),
               (0.058, 0.081), (0.036, 0.089), (0.014, 0.084), (-0.004, 0.060)]
PRIMARIES = [(0.080, -0.040), (0.120, -0.047), (0.165, -0.038), (0.205, -0.018), (0.240, 0.010),
             (0.265, 0.039), (0.283, 0.067), (0.263, 0.064), (0.250, 0.057), (0.238, 0.070),
             (0.222, 0.063), (0.210, 0.076), (0.193, 0.069), (0.180, 0.082), (0.155, 0.084),
             (0.125, 0.084), (0.092, 0.064)]
EDGE = [(-0.003, -0.008, 0.0062), (0.045, -0.034, 0.0082), (0.090, -0.048, 0.0082),
        (0.125, -0.047, 0.0062), (0.165, -0.039, 0.0035), (0.205, -0.019, 0.0012),
        (0.240, 0.009, -0.0004), (0.265, 0.038, -0.0012), (0.281, 0.064, -0.0018)]
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
    plates = C.Part()
    trim = C.Part()
    W = wing_matrix()

    def plate(outline, n_per, thick, z, pitch, mat):
        pts = catmull(outline, n_per)
        L = Matrix.Translation((0, 0, z)) @ Matrix.Rotation(radians(pitch), 4, 'X')
        vs, fs = plates.prism(pts, thick, mat, matrix=L)
        plates.deform(vs, lambda v: W @ wrist(v))
    plate(PRIMARIES, 2, 0.0058, -0.0048, -3.0, IVORY)
    plate(SECONDARIES, 2, 0.0062, -0.0004, -5.0, IVORY)
    plate(COVERTS, 2, 0.0070, 0.0048, -1.5, IVORY)
    path = [W @ wrist(Vector((x, y, 0.0035 + zz))) for (x, y, zz) in EDGE]
    rad = [0.0080, 0.0075, 0.0068, 0.0060, 0.0050, 0.0040, 0.0030, 0.0020, 0.0013]
    trim.tube(path, rad, 7, BRASS, caps='round', cap_segs=2, scale_xy=(1.0, 0.8), up=(0, 0, 1))
    # shoulder hub (brass) seated in the body socket
    n = Vector((1.0, 0.0, 0.55)).normalized()
    Mh = Matrix.Translation(SHOULDER - n * 0.006) @ n.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    trim.lathe([(0, 0.0), (0.0100, 0.0), (0.0104, 0.0055), (0.0082, 0.0085), (0.0, 0.0090)],
               12, BRASS, matrix=Mh)
    if sx < 0:
        plates.mirror_x()
        trim.mirror_x()
    temps = [plates.to_temp(bevel=(0.0013, 1, 40)), trim.to_temp()]
    pv = Vector((SHOULDER.x * sx, SHOULDER.y, SHOULDER.z))
    return C.merge_to_object(name, temps, pivot=pv, parent=parent, sharp_deg=46)


# ---------------------------------------------------------------------------- tail
def feather(L, w):
    return catmull([(-0.40 * w, 0.0), (-0.50 * w, 0.40 * L), (-0.46 * w, 0.86 * L),
                    (-0.26 * w, 0.99 * L), (0.26 * w, 0.99 * L), (0.46 * w, 0.86 * L),
                    (0.50 * w, 0.40 * L), (0.40 * w, 0.0)], 2)


def build_tail(parent):
    plates = C.Part()
    trim = C.Part()
    fans = [(-30, 0.134, -0.0036), (-15, 0.144, 0.0002), (0, 0.151, 0.0040),
            (15, 0.144, 0.0002), (30, 0.134, -0.0036)]
    tilt = Matrix.Rotation(radians(-9.0), 4, 'X')
    W = 0.042
    for ang, L, z in fans:
        R = Matrix.Rotation(radians(ang), 4, 'Z')
        roll = Matrix.Rotation(radians(-ang * 0.30), 4, 'Y')
        M = Matrix.Translation(TAIL_P) @ tilt @ R @ Matrix.Translation((0, -0.008, z)) @ roll
        plates.prism(feather(L, W), 0.0068, IVORY, matrix=M)
        # brass tip band
        tip = [(-0.47 * W, 0.90 * L), (-0.40 * W, 0.965 * L), (-0.20 * W, 1.0 * L + 0.0012),
               (0.20 * W, 1.0 * L + 0.0012), (0.40 * W, 0.965 * L), (0.47 * W, 0.90 * L)]
        trim.prism(tip, 0.0078, BRASS, matrix=M @ Matrix.Translation((0, 0, 0.0002)))
    # tail mount: rounded brass clamp
    trim.superellipsoid(TAIL_P + Vector((0, -0.003, 0.002)), (0.021, 0.016, 0.0092), 0.6, 0.6,
                        10, 5, BRASS)
    temps = [plates.to_temp(bevel=(0.0013, 1, 40)), trim.to_temp(bevel=(0.0008, 1, 40))]
    return C.merge_to_object("Tail", temps, pivot=TAIL_P, parent=parent, sharp_deg=46)


def build_thruster(parent):
    p = C.Part()
    M = Matrix.Translation(THR_C)
    p.lathe([(0.0, -0.0045), (0.0065, -0.0042), (0.0115, -0.0030), (0.0148, -0.0008),
             (0.0152, 0.0020), (0.0, 0.0020)], 16, GLOW, matrix=M)
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
