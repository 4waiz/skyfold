"""NURI - small mechanical falcon companion for SKYFOLD: The Last Flight.

Original procedural model (Awaiz Ahmed / Team Kanban), not AI-generated.
    blender -b --factory-startup -P tools/blender/chars_nuri.py [-- --no-render]

Hierarchy (pivots):
    Nuri (empty, body centre)
      Body            body centre
        Head          neck joint
          Lens        lens centre (separate mesh, SKY_TealGlow)
          Beak        beak root
        Wing_L        left shoulder joint  (+X Blender = Unity -X ... asset's left)
        Wing_R        right shoulder joint
        Tail          tail base
        Thruster      emissive disc centre (underside)
Faces Blender -Y (Unity +Z). Wings are modelled half-spread; flap = rotate about the
forward axis (Unity Z) at the shoulder.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C
from chars_common import Vector, Matrix, Euler, Quaternion, radians, sin, cos, pi, sqrt
import bpy

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS
OUT = os.path.join(C.MODELS, 'Characters', 'nuri.fbx')

IVORY, BRASS, INK, GLOW, TEAL = 'SKY_Ivory', 'SKY_Brass', 'SKY_Ink', 'SKY_TealGlow', 'SKY_Teal'

# ---------------------------------------------------------------------------- layout
HEAD_C = Vector((0.0, -0.084, 0.064))     # head centre
NECK = Vector((0.0, -0.056, 0.036))       # Head pivot (neck joint)
LENS_C = Vector((0.0, -0.1275, 0.068))    # Lens pivot
SHOULDER = Vector((0.041, -0.020, 0.030)) # Wing_L pivot (mirror for Wing_R)
TAIL_P = Vector((0.0, 0.080, 0.006))      # Tail pivot
THR_C = Vector((0.0, 0.010, -0.060))      # Thruster pivot
WING_SCALE = 0.93
DIHEDRAL = 13.0


def sp(x, e):
    return math.copysign(abs(x) ** e, x)


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def gval(x, centers, w, period=None):
    g = 0.0
    for c in centers:
        d = abs(x - c)
        if period:
            d = min(d, period - d)
        if d <= w / 3:
            return 1.0
        if d < w:
            g = max(g, (w - d) / (w * 2 / 3))
    return g


def samples(lo, hi, n, centers, w, closed=False):
    brk = []
    for c in centers:
        brk += [c - w, c - w / 3, c + w / 3, c + w]
    if closed:
        brk = [b % (hi - lo) for b in brk]
    base = [lo + (hi - lo) * i / n for i in range(n if closed else n + 1)]

    def far(b):
        for k in brk:
            d = abs(b - k)
            if closed:
                d = min(d, (hi - lo) - d)
            if d < w * 0.7:
                return False
        return True
    keep = [b for b in base if far(b)]
    if not closed:
        keep = sorted(set(keep + [lo, hi]))
    return sorted(set(round(v, 9) for v in keep + [b for b in brk if lo <= b <= hi]))


def grooved_shell(part, fn, center_fn, n_th, n_ph, th_seams, th_w, ph_seams, ph_w,
                  ph_cond, depth, seam_mat=INK, mat=IVORY):
    """Watertight shell from fn(theta, phi) with V/U grooves along constant-theta rings and
    constant-phi lines. Groove floors get seam_mat."""
    ths = samples(0.0, pi, n_th, th_seams, th_w)
    phs = samples(0.0, 2 * pi, n_ph, ph_seams, ph_w, closed=True)

    def g(th, ph):
        a = gval(th, th_seams, th_w)
        b = gval(ph, ph_seams, ph_w, 2 * pi) if ph_cond(th, ph) else 0.0
        return max(a, b)

    def P(th, ph):
        p = fn(th, ph)
        gv = g(th, ph)
        if gv > 0:
            d = (p - center_fn(th, ph)).normalized()
            p = p - d * depth * gv
        return p
    rings = [[P(th, ph) for ph in phs] for th in ths[1:-1]]
    vr, faces = part.grid(rings, mat, True, fn(0.0, 0.0), fn(pi, 0.0))
    n = len(phs)
    for i in range(len(rings) - 1):
        th_m = (ths[1 + i] + ths[2 + i]) / 2
        for j in range(n):
            a, b = phs[j], phs[(j + 1) % n]
            if b < a:
                b += 2 * pi
            if g(th_m, ((a + b) / 2) % (2 * pi)) > 0.99:
                part.assign([faces[i * n + j]], seam_mat)
    return vr, faces


def catmull(points, n_per, closed=True):
    P = [Vector((p[0], p[1], 0.0)) for p in points]
    m = len(P)
    out = []
    rng = range(m) if closed else range(m - 1)
    for i in rng:
        p0, p1, p2, p3 = P[(i - 1) % m], P[i], P[(i + 1) % m], P[(i + 2) % m]
        if not closed:
            p0 = P[max(i - 1, 0)]
            p3 = P[min(i + 2, m - 1)]
        for k in range(n_per):
            t = k / n_per
            t2, t3 = t * t, t * t * t
            v = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                       (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append((v.x, v.y))
    if not closed:
        out.append((P[-1].x, P[-1].y))
    return out


# ---------------------------------------------------------------------------- body
BODY = dict(yc=0.004, Lf=0.074, Lb=0.090, W=0.053, Hup=0.052, Hdn=0.057)


def body_axis(th):
    c = cos(th)
    y = BODY['yc'] - sp(c, 0.9) * (BODY['Lf'] if c > 0 else BODY['Lb'])
    zc = 0.006 * c + 0.004
    return y, zc


def body_pt(th, ph):
    y, zc = body_axis(th)
    t = th / pi
    taper = 1.0 - 0.34 * smoothstep(0.42, 1.0, t)
    r = sp(sin(th), 0.82) * taper
    s, c = sin(ph), cos(ph)
    x = BODY['W'] * r * sp(s, 0.88)
    z = zc + (BODY['Hup'] if c > 0 else BODY['Hdn']) * r * sp(c, 0.88)
    return Vector((x, y, z))


def body_center(th, ph):
    y, zc = body_axis(th)
    return Vector((0.0, y, zc))


def build_body(parent):
    p = C.Part()
    ring_th = 0.53 * pi
    grooved_shell(p, body_pt, body_center, 18, 26, [ring_th], 0.036, [0.0], 0.032,
                  lambda th, ph: ring_th <= th <= 0.86 * pi, 0.0013)
    # neck collar (brass) + dark neck core so the head can turn without gaps
    ax = (HEAD_C - NECK).normalized()
    q = ax.to_track_quat('Z', 'Y')
    M = Matrix.Translation(NECK + ax * 0.003) @ q.to_matrix().to_4x4()
    p.torus(0.0215, 0.0048, 28, 8, BRASS, matrix=M)
    p.cylinder(0.0195, 0.034, 20, INK, matrix=M @ Matrix.Translation((0, 0, -0.012)))
    # shoulder sockets (ink cup + brass ring), both sides
    for sx in (1, -1):
        s = Vector((SHOULDER.x * sx, SHOULDER.y, SHOULDER.z))
        n = (s - body_center(0.45 * pi, 0)).normalized()
        n = Vector((sx * 1.0, 0.0, 0.25)).normalized()
        Ms = Matrix.Translation(s - n * 0.002) @ n.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        p.lathe([(0, -0.006), (0.0135, -0.006), (0.0145, 0.0), (0.0128, 0.0018), (0, 0.0018)],
                20, INK, matrix=Ms)
        p.torus(0.0138, 0.0021, 22, 6, BRASS, matrix=Ms @ Matrix.Translation((0, 0, 0.0005)))
    # thruster housing (ink) with a brass rim
    Mt = Matrix.Translation(THR_C)
    p.lathe([(0.0, 0.002), (0.0185, 0.002), (0.019, -0.001), (0.0245, 0.0005),
             (0.0265, 0.006), (0.024, 0.014), (0.0, 0.016)], 24, INK, matrix=Mt)
    p.torus(0.0232, 0.0022, 24, 6, BRASS, matrix=Mt @ Matrix.Translation((0, 0, 0.0012)))
    tmp = p.to_temp(bevel=(0.0008, 1, 50))
    return C.merge_to_object("Body", [tmp], pivot=(0, 0, 0), parent=parent, sharp_deg=42)


# ---------------------------------------------------------------------------- head
HEAD = dict(Rf=0.044, Rb=0.045, Rs=0.0445, Rt=0.0445, Rd=0.041)


def head_pt(th, ph):
    c, s = cos(th), sin(th)
    fw = sp(c, 0.72)
    rad = sp(s, 0.86)
    sx, cz = sp(sin(ph), 0.86), sp(cos(ph), 0.86)
    y = HEAD_C.y - fw * (HEAD['Rf'] if c > 0 else HEAD['Rb'])
    cheek = 1.0 + 0.07 * max(0.0, -cos(ph)) * smoothstep(0.15, 0.6, th / pi)
    x = HEAD['Rs'] * rad * sx * cheek
    z = HEAD_C.z + rad * cz * (HEAD['Rt'] if cz > 0 else HEAD['Rd'])
    # brow: a soft ridge over the lens
    brow = math.exp(-((th - 0.30 * pi) / 0.11) ** 2) * max(0.0, cos(ph)) ** 2
    p = Vector((x, y, z))
    d = (p - HEAD_C).normalized()
    return p + d * 0.0035 * brow


def head_center(th, ph):
    return HEAD_C.copy()


def build_head(parent):
    p = C.Part()
    face_th = 0.40 * pi
    grooved_shell(p, head_pt, head_center, 16, 26, [face_th], 0.034, [0.0], 0.03,
                  lambda th, ph: face_th <= th <= 0.80 * pi, 0.0012)
    # lens bezel (ink) around the forward (-Y) axis
    Mf = Matrix.Translation(LENS_C) @ Matrix.Rotation(radians(90), 4, 'X')  # local +Z -> -Y
    p.lathe([(0.0156, -0.0045), (0.0156, 0.0028), (0.0168, 0.0052), (0.0196, 0.0056),
             (0.0214, 0.0036), (0.0219, 0.0), (0.0214, -0.0110), (0.0156, -0.0110)],
            32, INK, matrix=Mf)
    # thin brass trim ring set into the bezel face
    p.torus(0.0182, 0.0011, 32, 5, BRASS, matrix=Mf @ Matrix.Translation((0, 0, 0.0057)))
    # malar 'tear' stripes - the falcon moustache, in ink, embossed on the cheeks
    for sx in (1, -1):
        pts = []
        for k in range(7):
            t = k / 6
            th = 0.20 * pi + t * 0.26 * pi
            ph = sx * (0.60 * pi + t * 0.16 * pi)
            q = head_pt(th, ph)
            d = (q - HEAD_C).normalized()
            pts.append(q - d * 0.0006)
        rad = [0.0042 - 0.0026 * (k / 6) ** 1.3 for k in range(7)]
        n0 = (pts[0] - HEAD_C).normalized()
        p.tube(pts, rad, 10, INK, caps='round', cap_segs=2, scale_xy=(1.0, 0.34), up=n0)
    tmp = p.to_temp(bevel=(0.0006, 1, 50))
    return C.merge_to_object("Head", [tmp], pivot=NECK, parent=parent, sharp_deg=42)


def build_lens(parent):
    p = C.Part()
    Mf = Matrix.Translation(LENS_C) @ Matrix.Rotation(radians(90), 4, 'X')
    prof = [(0.0, 0.0024), (0.0030, 0.00235), (0.0056, 0.0022),     # pupil (deep teal)
            (0.0062, 0.00215), (0.0084, 0.0019),                     # glowing iris ring
            (0.0090, 0.00185), (0.0102, 0.0017),                     # thin dark ring
            (0.0108, 0.0016), (0.0130, 0.0010), (0.0150, 0.0001),    # lens body (glow)
            (0.0155, -0.0012), (0.0155, -0.0040), (0.0, -0.0040)]
    vr, faces = p.lathe(prof, 32, GLOW, matrix=Mf)
    # rings: band k between profile points k and k+1 (pole fan first -> handled by index)
    seg = 32
    # grid faces are created ring by ring: profile without poles -> rings 0..n-1
    # bands: ring i -> ring i+1 ; prof[1] is ring 0
    band_mats = {0: TEAL, 1: TEAL, 4: TEAL, 5: TEAL}
    for b, m in band_mats.items():
        p.assign(faces[b * seg:(b + 1) * seg], m)
    # pole fan at the front (faces after the bands) = pupil centre
    nb = (len(prof) - 2 - 1)
    p.assign(faces[nb * seg:nb * seg + seg], TEAL)
    tmp = p.to_temp()
    return C.merge_to_object("Lens", [tmp], pivot=LENS_C, parent=parent, sharp_deg=60)


def build_beak(parent):
    p = C.Part()
    f = Vector((0, -1, 0))
    z = Vector((0, 0, 1))
    base = Vector((0.0, -0.1225, 0.0455))
    pts = [base - f * 0.004 + z * 0.002, base + f * 0.006 + z * 0.0005,
           base + f * 0.0135 - z * 0.0028, base + f * 0.0185 - z * 0.0090,
           base + f * 0.0192 - z * 0.0150, base + f * 0.0160 - z * 0.0195]
    rad = [0.0088, 0.0080, 0.0063, 0.0044, 0.0027, 0.0012]
    sc = [(0.82, 1.0), (0.80, 1.0), (0.74, 1.0), (0.66, 1.0), (0.6, 1.0), (0.6, 1.0)]
    p.tube(pts, rad, 12, BRASS, caps='round', cap_segs=2, scale_xy=sc, up=(0, 0, 1))
    # lower mandible (ink)
    lp = [base - f * 0.002 - z * 0.0062, base + f * 0.0070 - z * 0.0085,
          base + f * 0.0120 - z * 0.0110]
    p.tube(lp, [0.0048, 0.0036, 0.0018], 10, INK, caps='round', cap_segs=2,
           scale_xy=(0.9, 0.7), up=(0, 0, 1))
    tmp = p.to_temp(bevel=(0.0005, 1, 50))
    return C.merge_to_object("Beak", [tmp], pivot=base, parent=parent, sharp_deg=55)


# ---------------------------------------------------------------------------- wings
COVERTS = [(0.000, -0.012), (0.040, -0.021), (0.090, -0.023), (0.132, -0.016), (0.147, 0.000),
           (0.141, 0.020), (0.124, 0.022), (0.110, 0.036), (0.090, 0.030), (0.074, 0.044),
           (0.052, 0.037), (0.034, 0.048), (0.012, 0.042), (-0.004, 0.026)]
SECONDARIES = [(0.000, 0.000), (0.060, -0.006), (0.118, -0.008), (0.150, 0.010), (0.153, 0.040),
               (0.145, 0.070), (0.130, 0.066), (0.116, 0.085), (0.098, 0.075), (0.082, 0.091),
               (0.064, 0.081), (0.046, 0.093), (0.028, 0.083), (0.010, 0.089), (-0.004, 0.058)]
PRIMARIES = [(0.098, -0.010), (0.158, -0.017), (0.204, -0.002), (0.238, 0.036), (0.254, 0.080),
             (0.244, 0.090), (0.226, 0.070), (0.217, 0.094), (0.200, 0.074), (0.190, 0.098),
             (0.173, 0.078), (0.160, 0.095), (0.140, 0.074), (0.112, 0.056)]
EDGE = [(0.000, -0.006, 0.0045), (0.045, -0.022, 0.0058), (0.100, -0.026, 0.0058),
        (0.152, -0.017, 0.0045), (0.200, 0.002, 0.003), (0.236, 0.040, 0.0012),
        (0.252, 0.078, -0.0008)]


def wing_matrix(sx):
    """Wing-local -> world. Local x = outward span, y = back, z = up (before dihedral)."""
    piv = Vector((SHOULDER.x * sx, SHOULDER.y, SHOULDER.z))
    R = Matrix.Rotation(radians(-DIHEDRAL * sx), 4, 'Y')
    S = Matrix.Diagonal((sx * WING_SCALE, WING_SCALE, WING_SCALE, 1.0))
    return Matrix.Translation(piv) @ R @ S, piv


def build_wing(name, sx, parent):
    p = C.Part()
    W, piv = wing_matrix(1)

    def plate(outline, thick, z, pitch, mat, npts=4):
        pts = catmull(outline, npts)
        M = W @ Matrix.Translation((0, 0, z)) @ Matrix.Rotation(radians(pitch), 4, 'X')
        return p.prism(pts, thick, mat, matrix=M)
    plate(PRIMARIES, 0.0042, -0.0030, -3.0, IVORY)
    plate(SECONDARIES, 0.0044, -0.0005, -5.0, IVORY)
    plate(COVERTS, 0.0050, 0.0030, -1.5, IVORY)
    # brass leading edge (wing-local path, radius tapering)
    path = [W @ Vector((x, y, 0.0040 + zz)) for (x, y, zz) in EDGE]
    rad = [0.0068, 0.0062, 0.0055, 0.0045, 0.0034, 0.0024, 0.0015]
    p.tube(path, rad, 10, BRASS, caps='round', cap_segs=2, scale_xy=(1.0, 0.8), up=(0, 0, 1))
    # shoulder hub (brass) sitting in the body socket
    n = Vector((1.0, 0.0, 0.25)).normalized()
    Mh = Matrix.Translation(piv - n * 0.004) @ n.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    p.lathe([(0, 0.0), (0.0105, 0.0), (0.0110, 0.0060), (0.0090, 0.0095), (0.0, 0.0100)],
            18, BRASS, matrix=Mh)
    p.cylinder(0.0045, 0.0115, 12, INK, matrix=Mh)
    if sx < 0:
        p.mirror_x()
    tmp = p.to_temp(bevel=(0.0011, 2, 40))
    pv = Vector((piv.x * sx, piv.y, piv.z))
    return C.merge_to_object(name, [tmp], pivot=pv, parent=parent, sharp_deg=45)


# ---------------------------------------------------------------------------- tail
def feather(L, w):
    return catmull([(-0.40 * w, 0.0), (-0.50 * w, 0.30 * L), (-0.50 * w, 0.78 * L),
                    (-0.36 * w, 0.96 * L), (0.0, 1.0 * L), (0.36 * w, 0.96 * L),
                    (0.50 * w, 0.78 * L), (0.50 * w, 0.30 * L), (0.40 * w, 0.0)], 3)


def build_tail(parent):
    p = C.Part()
    fans = [(-24, 0.128, -0.0026), (-12, 0.140, 0.0004), (0, 0.148, 0.0034),
            (12, 0.140, 0.0004), (24, 0.128, -0.0026)]
    base_tilt = Matrix.Rotation(radians(-7.0), 4, 'X')   # trailing end slightly down
    for ang, L, z in fans:
        R = Matrix.Rotation(radians(ang), 4, 'Z')
        roll = Matrix.Rotation(radians(-ang * 0.25), 4, 'Y')
        M = Matrix.Translation(TAIL_P) @ base_tilt @ R @ Matrix.Translation((0, -0.006, z)) @ roll
        p.prism(feather(L, 0.034), 0.0042, IVORY, matrix=M)
        # brass tip cap
        tip = [(x, y) for (x, y) in feather(L, 0.034) if y > 0.80 * L]   # left -> right
        cap = [(-0.5 * 0.036, 0.80 * L)] + [(x * 1.05, y + 0.0012) for (x, y) in tip] + \
              [(0.5 * 0.036, 0.80 * L)]
        p.prism(cap, 0.0054, BRASS, matrix=M @ Matrix.Translation((0, 0, 0.0002)))
    # tail mount: a rounded brass clamp + ink root block
    p.superellipsoid(TAIL_P + Vector((0, -0.002, 0.0015)), (0.022, 0.016, 0.0085), 0.6, 0.6, 18,
                     8, BRASS)
    tmp = p.to_temp(bevel=(0.0010, 2, 40))
    return C.merge_to_object("Tail", [tmp], pivot=TAIL_P, parent=parent, sharp_deg=45)


def build_thruster(parent):
    p = C.Part()
    M = Matrix.Translation(THR_C)
    p.lathe([(0.0, -0.0052), (0.0070, -0.0048), (0.0130, -0.0034), (0.0178, -0.0008),
             (0.0182, 0.0030), (0.0, 0.0030)], 24, GLOW, matrix=M)
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
    C.bake_ao(meshes, dist=0.035, samples=64, floor=0.38, white=[lens, thr])
    return root


if __name__ == "__main__":
    root = build()
    C.summary(root)
    C.export_fbx(root, OUT)
    if RENDER:
        C.render_previews("nuri", root, res=(960, 720), samples=128, ground_z=-0.22, lens=70)
        C.render_ortho("nuri", root, [("front", 0, 0), ("side", 90, 0), ("back", 180, 0)],
                       res=(800, 800), samples=96)
