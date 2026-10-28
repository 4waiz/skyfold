"""SKYFOLD environment kit - street and airfield props (detail pass).

Pivot at ground centre unless noted. Fronts face Unity north (+Z) = Blender -Y.
Gameplay contracts (names / pivots unchanged): street_lamp LIGHT_lamp; runway_beacon 'Lens' (pivot at the
lens centre) + LIGHT_beacon; switch_box 'Lever' (pivot = hinge, modelled UP = off); cell_dock SOCKET_cell.
Chamfers on turned parts are modelled into the lathe profiles; boxes get modifier bevels (often limited to
their visible top edges by bevel weight) so triangles go to silhouettes, trims and moving parts.
"""
from env_common import *
from env_nature import ico_blob, floret_layout, bract_cluster, leaf_tet

PROP_AO = dict(ground_z=0.0, dist=0.5, rays=24, strength=0.68, floor=0.5, inset=0.04, power=1.2)
PROP_RENDER = dict(az=35.0, el=22.0)


# --------------------------------------------------------------------------- helpers

def cham_rect(w, h, c, cx=0.0, cy=0.0):
    """Rectangle (w along u, h along v) with 45-degree chamfered corners, CCW."""
    hw, hh = w / 2.0, h / 2.0
    c = max(0.0, min(c, hw * 0.45, hh * 0.45))
    if c <= 1e-6:
        return [(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)]
    return [(cx - hw + c, cy - hh), (cx + hw - c, cy - hh), (cx + hw, cy - hh + c), (cx + hw, cy + hh - c),
            (cx + hw - c, cy + hh), (cx - hw + c, cy + hh), (cx - hw, cy + hh - c), (cx - hw, cy - hh + c)]


def rot2(pts, deg, cx=0.0, cy=0.0):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca) for (x, y) in pts]


def shift(pts, dx, dy):
    return [(x + dx, y + dy) for (x, y) in pts]


def bar_x(mb, x0, x1, pts_yz, mat):
    """Extrude a (y, z) outline along X."""
    return mb.prism_frame(pts_yz, (0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), x0, x1, mat)


def plate_y(mb, pts_xz, y0, y1, mat):
    """Extrude an (x, z) outline along Y (front/back facing plates)."""
    return mb.prism_frame(pts_xz, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), y0, y1, mat)


def plate_x(mb, pts_yz, x0, x1, mat):
    return bar_x(mb, x0, x1, pts_yz, mat)


def rod(mb, path, r, sides, mat, a0=0.0, scales=None, up=Vector((0, 0, 1))):
    return mb.sweep([Vector(p) for p in path], circle(r, sides, a0=a0), mat, scales=scales, up=up)


def ring(mb, r_in, r_out, z0, z1, seg, mat, cx=0.0, cy=0.0, ch=0.0, a0=0.0, lean=False):
    """Closed annular band (washer / collar) with optional chamfered outer edges. lean=True: 4-point
    profile whose sloped top/bottom act as the chamfers (cheaper, inner faces stay hidden)."""
    if lean:
        prof = [(r_in, z0), (r_out, z0 + ch), (r_out, z1 - ch), (r_in, z1)]
    elif ch > 0:
        prof = [(r_in, z0), (r_out - ch, z0), (r_out, z0 + ch), (r_out, z1 - ch), (r_out - ch, z1), (r_in, z1)]
    else:
        prof = [(r_in, z0), (r_out, z0), (r_out, z1), (r_in, z1)]
    return mb.lathe(prof, seg, mat, cx=cx, cy=cy, a0=a0, closed=True)


def bezier3(p0, p1, p2, p3, n):
    P = [Vector(p) for p in (p0, p1, p2, p3)]
    out = []
    for i in range(n + 1):
        t = i / n
        s = 1 - t
        out.append(P[0] * s ** 3 + P[1] * 3 * s * s * t + P[2] * 3 * s * t * t + P[3] * t ** 3)
    return out


def weight_edges(mb, faces):
    """Bevel weight 1 on the creased edges of the given faces (use with part(..., weight_limit=True))."""
    bm = mb.bm
    bm.normal_update()
    bw = bm.edges.layers.float.get('bevel_weight_edge') or bm.edges.layers.float.new('bevel_weight_edge')
    for f in faces:
        for e in f.edges:
            if len(e.link_faces) == 2 and e.calc_face_angle(0.0) < math.radians(5):
                continue
            e[bw] = 1.0


def strap_leaf(mb, base, d, length, width, mat='SKY_PalmLeaf', droop=0.55):
    """Arching strap leaf in two wedges: rising blade, then a tip that bends down."""
    d = Vector(d).normalized()
    w = d.cross(Vector((0, 0, 1)))
    w = w.normalized() if w.length > 1e-4 else Vector((1, 0, 0))
    n = w.cross(d).normalized()
    if n.z < 0:
        n = -n
    L1 = length * 0.55
    leaf_tet(mb, base, d, w, n, L1, width, -width * 0.18, mat, mid=0.7)
    mid = base + d * (L1 * 0.92)
    d2 = (d - Vector((0, 0, droop))).normalized()
    n2 = w.cross(d2).normalized()
    if n2.z < 0:
        n2 = -n2
    leaf_tet(mb, mid, d2, w, n2, length * 0.5, width * 0.92, -width * 0.16, mat, mid=0.18)


def ring_prism(mb, outer, inner, z0, z1, mat, origin=(0, 0, 0), u=(1, 0, 0), v=(0, 1, 0), w=(0, 0, 1)):
    """Prism of the region between two loops with equal point counts (a frame / rim), extruded along w.
    Returns (faces, top_faces)."""
    o, U, V, W = Vector(origin), Vector(u), Vector(v), Vector(w)
    outer = ccw(list(outer))
    inner = ccw(list(inner))
    n = len(outer)
    P = lambda p, z: o + U * p[0] + V * p[1] + W * z
    ob = [mb.v(P(p, z0)) for p in outer]
    ot = [mb.v(P(p, z1)) for p in outer]
    ib = [mb.v(P(p, z0)) for p in inner]
    it = [mb.v(P(p, z1)) for p in inner]
    fs, top = [], []
    for k in range(n):
        k2 = (k + 1) % n
        fs.append(mb.f([ob[k], ob[k2], ot[k2], ot[k]], mat))
        fs.append(mb.f([ib[k2], ib[k], it[k], it[k2]], mat))
        t = mb.f([ot[k], ot[k2], it[k2], it[k]], mat)
        fs.append(t)
        top.append(t)
        fs.append(mb.f([ob[k2], ob[k], ib[k], ib[k2]], mat))
    mb._recalc(fs)
    return fs, top


def stud(mb, x, y, z, r, h, mat, seg=8, axis='Z', dome=True, mats=None):
    """Small turned stud / lamp lens along +axis from (x, y, z): flat base, side, chamfer, domed top."""
    prof = [(0.0, 0.0), (r, 0.0), (r, h * 0.45), (r * 0.78, h * 0.72), (r * 0.42, h * 0.95 if dome else h),
            (0.0, h)]
    fs = mb.lathe(prof, seg, mat, mats=mats)
    M = Matrix.Identity(4)
    if axis == '-Y':
        M = Matrix.Rotation(math.radians(90), 4, 'X')
    elif axis == 'Y':
        M = Matrix.Rotation(math.radians(-90), 4, 'X')
    elif axis == 'X':
        M = Matrix.Rotation(math.radians(90), 4, 'Y')
    elif axis == '-X':
        M = Matrix.Rotation(math.radians(-90), 4, 'Y')
    mb.transform(M_tr(x, y, z) @ M, fs)
    return fs


# --------------------------------------------------------------------------- street lamp

@asset("street_lamp", "Props", "props", ao=PROP_AO, render=dict(PROP_RENDER, el=12.0))
def street_lamp(a):
    """5 m solar street lantern: octagonal pearl pedestal on a deep-sandstone step, fluted teal post with brass
    collars, teal swan-neck arm on a brass scroll bracket, octagonal brass lantern (glass panes, warm lamp
    core, crown and drip finials) hanging toward Unity north. LIGHT_lamp at the lantern centre."""
    LX, LY = 0.0, -0.92
    # step + pedestal (octagonal, flats facing the axes)
    mb = MB()
    mb.lathe([(0, 0), (0.252, 0), (0.252, 0.05), (0.238, 0.068), (0, 0.068)], 8, 'SKY_SandstoneDeep', a0=22.5)
    a.part(mb, name="step")
    mb = MB()
    prof = [(0, 0.066), (0.226, 0.066), (0.226, 0.098), (0.214, 0.114), (0.194, 0.122), (0.184, 0.14),
            (0.162, 0.79), (0.176, 0.804), (0.188, 0.826), (0.188, 0.862), (0.174, 0.876), (0.124, 0.888), (0, 0.888)]
    mb.lathe(prof, 8, 'SKY_Pearl', a0=22.5)
    ring(mb, 0.16, 0.198, 0.15, 0.19, 8, 'SKY_Brass', ch=0.01, a0=22.5, lean=True)
    a.part(mb, name="pedestal")
    # fluted post (8 flutes, tapering) with brass collars
    star = []
    for k in range(16):
        r = 1.0 if k % 2 == 0 else 0.84
        ang = 2 * math.pi * k / 16 + math.pi / 16
        star.append((r * math.cos(ang), r * math.sin(ang)))
    mb = MB()
    mb.sweep([Vector((0, 0, 0.86)), Vector((0, 0, 4.3))], star, 'SKY_Teal', scales=[0.07, 0.054])
    for (z, ro) in ((0.88, 0.092), (1.62, 0.084), (3.1, 0.076)):
        ring(mb, ro - 0.035, ro, z, z + 0.065, 8, 'SKY_Brass', ch=0.014, a0=22.5, lean=True)
    # capital + neck + finial
    mb.lathe([(0.0, 4.24), (0.058, 4.24), (0.096, 4.29), (0.104, 4.33), (0.088, 4.358), (0.05, 4.37),
              (0.05, 4.43), (0.0, 4.43)], 8, 'SKY_Brass', a0=22.5)
    mb.sphere(0.056, 8, 5, 'SKY_Brass', c=(0, 0, 4.475))
    mb.lathe([(0, 4.515), (0.026, 4.522), (0.0, 4.64)], 6, 'SKY_Brass')
    a.part(mb, name="post")
    # swan-neck arm (teal flat bar) toward Unity north, brass tip ball
    mb = MB()
    arm = bezier3((0, -0.02, 4.34), (0, -0.2, 4.98), (0, -0.62, 5.07), (0, -1.0, 4.93), 10)
    mb.sweep(arm, cham_rect(0.036, 0.052, 0.012), 'SKY_Teal')
    mb.sphere(0.034, 8, 4, 'SKY_Brass', c=(0, -1.012, 4.925))
    # hanger (arm -> lantern crown)
    rod(mb, [(LX, LY, 4.965), (LX, LY, 4.84)], 0.013, 6, 'SKY_Brass')
    mb.sphere(0.028, 6, 3, 'SKY_Brass', c=(LX, LY, 4.95))
    a.part(mb, name="arm")
    # brass scroll bracket: a log spiral hanging from the arm, its outer loop touching the post, curling in
    mb = MB()
    C2 = (0.236, 4.505)
    pts = []
    n = 20
    for i in range(n + 1):
        t = i / n
        th = math.radians(90 + 540 * t)
        r = 0.24 * (0.04 / 0.24) ** t
        pts.append(Vector((0.0, -(C2[0] + r * math.cos(th)), C2[1] + r * math.sin(th))))
    pts.insert(0, pts[0] + Vector((0.0, 0.03, 0.025)))
    mb.sweep(pts, cham_rect(0.024, 0.03, 0.0), 'SKY_Brass')
    mb.sphere(0.026, 8, 4, 'SKY_Brass', c=(0, -C2[0], C2[1]))
    a.part(mb, name="scroll")
    # lantern: ogee roof, eave, crown ball, mullions, glass panes, lamp core, bowl + drip finial
    mb = MB()
    roof = [(0.0, 4.52), (0.212, 4.52), (0.248, 4.542), (0.254, 4.566), (0.236, 4.586), (0.172, 4.64),
            (0.108, 4.7), (0.072, 4.742), (0.054, 4.776), (0.054, 4.796), (0.0, 4.796)]
    mb.lathe(roof, 8, 'SKY_Brass', cx=LX, cy=LY, a0=22.5)
    mb.sphere(0.046, 8, 4, 'SKY_Brass', c=(LX, LY, 4.836))
    bowl = [(0.0, 3.87), (0.024, 3.876), (0.034, 3.902), (0.056, 3.93), (0.124, 3.974), (0.17, 4.004),
            (0.178, 4.022), (0.178, 4.046), (0.0, 4.046)]
    mb.lathe(bowl, 8, 'SKY_Brass', cx=LX, cy=LY, a0=22.5)
    mb.sphere(0.028, 6, 3, 'SKY_Brass', c=(LX, LY, 3.852))
    for k in range(8):
        ang = math.radians(22.5 + 45 * k)
        c0 = Vector((LX + 0.163 * math.cos(ang), LY + 0.163 * math.sin(ang), 4.03))
        c1 = Vector((LX + 0.213 * math.cos(ang), LY + 0.213 * math.sin(ang), 4.53))
        mb.sweep([c0, c1], circle(0.012, 4, a0=45), 'SKY_Brass')
    a.part(mb, name="lantern")
    mb = MB()
    mb.lathe([(0, 4.036), (0.155, 4.036), (0.205, 4.524), (0, 4.524)], 8, 'SKY_Glass', cx=LX, cy=LY, a0=22.5)
    a.part(mb, name="glass")
    mb = MB()
    mb.lathe([(0, 4.04), (0.046, 4.04), (0.05, 4.1), (0.0, 4.12)], 8, 'SKY_Brass', cx=LX, cy=LY)
    mb.lathe([(0, 4.1), (0.052, 4.118), (0.088, 4.19), (0.094, 4.27), (0.077, 4.36), (0.042, 4.42), (0, 4.44)], 8,
             'SKY_Light', cx=LX, cy=LY)
    a.part(mb, name="lamp")
    # solar head: a small south-facing PV panel on a brass stem above the finial, battery pod below it
    mb = MB()
    rod(mb, [(0, 0, 4.62), (0, 0.06, 4.86)], 0.016, 6, 'SKY_Brass')
    fs = mb.box(-0.3, 0.3, -0.2, 0.2, 0.0, 0.035, 'SKY_Pearl', fm={'top': 'SKY_Solar'})
    fs += mb.box(-0.012, 0.012, -0.18, 0.18, 0.035, 0.042, 'SKY_Pearl')
    mb.transform(M_tr(0, 0.08, 4.9) @ M_rot(-24, 'X'), fs)
    mb.box(-0.05, 0.05, 0.01, 0.09, 3.28, 3.5, 'SKY_Teal')
    mb.box(-0.052, 0.052, 0.0, 0.092, 3.44, 3.46, 'SKY_TealGlow')
    a.part(mb, name="solar")
    a.empty("LIGHT_lamp", (LX, LY, 4.31))


# --------------------------------------------------------------------------- bench

BENCH_END = [(-0.262, 0.0), (-0.168, 0.0), (-0.168, 0.026), (-0.18, 0.05), (-0.152, 0.335), (0.098, 0.335),
             (0.135, 0.05), (0.122, 0.026), (0.122, 0.0), (0.252, 0.0), (0.252, 0.026), (0.234, 0.05),
             (0.21, 0.38), (0.226, 0.47), (0.276, 0.79), (0.29, 0.836), (0.27, 0.862), (0.242, 0.85),
             (0.186, 0.53), (0.154, 0.43), (-0.214, 0.444), (-0.244, 0.425), (-0.238, 0.05), (-0.262, 0.026)]


def _seat_z(y):
    return 0.444 - 0.038 * (y + 0.214)


@asset("bench", "Props", "props", ao=PROP_AO, render=PROP_RENDER)
def bench(a):
    """2 m park bench: teal cast-iron ends (scrolled armrests, shaped legs) carrying timber seat and back
    slats with gaps. Long axis along Unity X; you sit facing Unity north (Blender -Y)."""
    XE = 0.8
    mb = MB()
    for s in (-1, 1):
        bar_x(mb, s * XE - 0.025, s * XE + 0.025, BENCH_END, 'SKY_Teal')
    a.part(mb, bevel=0.008, seg=1, angle=35.0, name="ends")
    # scrolled armrests + front supports
    mb = MB()
    arm = [(0.222, 0.64), (0.1, 0.652), (-0.06, 0.656), (-0.17, 0.652), (-0.226, 0.632), (-0.249, 0.598),
           (-0.241, 0.564), (-0.215, 0.551), (-0.195, 0.565), (-0.201, 0.586)]
    for s in (-1, 1):
        x = s * XE
        mb.sweep([Vector((x, y, z)) for (y, z) in arm], cham_rect(0.052, 0.034, 0.01), 'SKY_Teal')
        mb.sweep([Vector((x, -0.213, 0.43)), Vector((x, -0.213, 0.556))], cham_rect(0.044, 0.03, 0.009), 'SKY_Teal',
                 up=Vector((0, -1, 0)))
    a.part(mb, name="arms")
    # seat slats (5) following the seat line, with gaps
    mb = MB()
    slope = math.degrees(math.atan2(-0.038, 1.0))
    for i in range(5):
        y = -0.175 + i * 0.0738
        z = _seat_z(y) + 0.0175
        bar_x(mb, -0.985, 0.985, shift(rot2(cham_rect(0.06, 0.034, 0.009), slope), y, z), 'SKY_Wood')
    # back slats (3) on the raked back posts
    p0 = Vector((0.186, 0.53))
    d = (Vector((0.242, 0.85)) - p0).normalized()
    nrm = Vector((-d.y, d.x))
    ang = math.degrees(math.atan2(d.y, d.x))
    for s_ in (0.075, 0.172, 0.269):
        c = p0 + d * s_ + nrm * 0.016
        bar_x(mb, -0.985, 0.985, shift(rot2(cham_rect(0.078, 0.028, 0.009), ang), c.x, c.y), 'SKY_Wood')
    a.part(mb, name="slats")


# --------------------------------------------------------------------------- bollard

@asset("bollard", "Props", "props", ao=PROP_AO, render=PROP_RENDER)
def bollard(a):
    """0.95 m pearl street bollard: stepped deep-sandstone base ring, brass band, recessed teal light
    line, flared collar and a brass dome cap with a knob."""
    pts = [(0.0, 0.0), (0.165, 0.0), (0.165, 0.032), (0.153, 0.048), (0.139, 0.054),
           (0.134, 0.07), (0.127, 0.6),
           (0.137, 0.606), (0.14, 0.618), (0.14, 0.682), (0.137, 0.694), (0.126, 0.7),
           (0.124, 0.736), (0.115, 0.741), (0.115, 0.753), (0.123, 0.758),
           (0.122, 0.792), (0.138, 0.802), (0.148, 0.814), (0.148, 0.832), (0.139, 0.842),
           (0.12, 0.848), (0.106, 0.878), (0.078, 0.904), (0.044, 0.92), (0.024, 0.926), (0.026, 0.94), (0.0, 0.952)]
    D, P, B, G = 'SKY_SandstoneDeep', 'SKY_Pearl', 'SKY_Brass', 'SKY_TealGlow'
    mats = [D, D, D, D,          # base bottom, side, chamfer, step
            P, P,                # fillet, shaft
            B, B, B, B, B,       # brass band
            P, P, G, P,          # groove lip, glow face, lip
            P, P, P, P, P,       # collar
            B, B, B, B, B, B, B]
    mb = MB()
    mb.lathe(pts, 16, P, mats=mats, a0=11.25)
    a.part(mb, name="body")


# --------------------------------------------------------------------------- barrier

@asset("barrier_coral", "Props", "props", ao=PROP_AO, render=PROP_RENDER)
def barrier_coral(a):
    """2 m road barrier: two pearl planks with inset coral chevron panels on both faces, amber reflectors,
    pearl A-frames with an H-brace and brass hinge caps, rubber foot rails and a warning lamp."""
    planks = [(0.86, 2.0, 0.26, 0.03), (0.41, 1.8, 0.2, 0.025)]     # z centre, length, height, half thickness
    mb = MB()
    for (zc, L, H, t) in planks:
        plate_y(mb, rrect(L, H, 0.05, 2, cy=zc), -t, t, 'SKY_Pearl')
    a.part(mb, bevel=0.01, seg=2, name="planks")
    # coral chevron panels: raised slanted parallelograms inside a pearl border, both faces
    mb = MB()
    for (zc, L, H, t) in planks:
        h = H - 0.06
        sl = h * 0.8
        w = 0.14
        period = 0.28
        n = int((L - 0.14 - sl - w) / period) + 1
        span = (n - 1) * period + w + sl
        x0 = -span / 2
        for k in range(n):
            xa = x0 + k * period
            base = [(xa, zc - h / 2), (xa + w, zc - h / 2), (xa + w + sl, zc + h / 2), (xa + sl, zc + h / 2)]
            inset = [(xa + 0.006, zc - h / 2 + 0.005), (xa + w - 0.003, zc - h / 2 + 0.005),
                     (xa + w + sl - 0.006, zc + h / 2 - 0.005), (xa + sl + 0.003, zc + h / 2 - 0.005)]
            for sg in (-1, 1):
                y0 = sg * (t - 0.001)
                y1 = sg * (t + 0.005)
                mb.loft([[(p[0], y0, p[1]) for p in base], [(p[0], y1, p[1]) for p in inset]], 'SKY_Coral')
    # amber reflectors at the ends of the top plank
    for sg in (-1, 1):
        for xs in (-0.93, 0.93):
            stud(mb, xs, sg * 0.03, 0.86, 0.028, 0.012, 'SKY_Brass', seg=6, axis='-Y' if sg < 0 else 'Y',
                 mats=['SKY_Brass', 'SKY_Brass', 'SKY_Light', 'SKY_Light', 'SKY_Light'])
    a.part(mb, name="panels")
    # A-frames: legs, H-brace, hinge caps
    mb = MB()
    for x in (-0.82, 0.82):
        for s in (-1, 1):
            mb.sweep([Vector((x, s * 0.31, 0.05)), Vector((x, s * 0.035, 1.03))], cham_rect(0.056, 0.042, 0.01),
                     'SKY_Pearl', up=Vector((1, 0, 0)))
        yb = 0.31 - (0.41 - 0.05) / (1.03 - 0.05) * (0.31 - 0.035)
        mb.sweep([Vector((x, -yb, 0.41)), Vector((x, yb, 0.41))], cham_rect(0.05, 0.05, 0.01), 'SKY_Pearl')
    a.part(mb, name="frames")
    mb = MB()
    for x in (-0.82, 0.82):
        mb.sweep([Vector((x - 0.05, 0, 1.035)), Vector((x + 0.05, 0, 1.035))], circle(0.036, 10), 'SKY_Brass')
    # warning lamp on the left frame
    mb.lathe([(0, 1.06), (0.046, 1.06), (0.058, 1.074), (0.058, 1.098), (0.0, 1.098)], 8, 'SKY_Brass', cx=-0.82)
    mb.lathe([(0, 1.09), (0.05, 1.09), (0.054, 1.112), (0.042, 1.14), (0.02, 1.155), (0, 1.158)], 8, 'SKY_Light',
             cx=-0.82)
    mb.cyl(0.018, 1.03, 1.065, 6, 'SKY_Brass', cx=-0.82)
    a.part(mb, name="hinges")
    # rubber foot rails
    mb = MB()
    for x in (-0.82, 0.82):
        fs = mb.prism(cham_rect(0.15, 0.84, 0.03, cx=x), 0.0, 0.06, 'SKY_Rubber')
        weight_edges(mb, [fs[1]])
    a.part(mb, bevel=0.012, seg=2, weight_limit=True, name="feet")


# --------------------------------------------------------------------------- traffic cone

@asset("traffic_cone", "Props", "props", ao=PROP_AO, render=PROP_RENDER)
def traffic_cone(a):
    """0.7 m traffic cone: rounded-square rubber base with a raised collar, coral cone with two raised
    pearl reflective bands and a rounded tip."""
    mb = MB()
    sq0 = rrect(0.42, 0.42, 0.07, 3)
    sq1 = rrect(0.4, 0.4, 0.06, 3)
    mb.loft([[(x, y, 0.0) for (x, y) in sq0], [(x, y, 0.026) for (x, y) in sq0], [(x, y, 0.036) for (x, y) in sq1]],
            'SKY_Rubber')
    a.part(mb, name="base")

    def rz(z):
        return 0.162 - 0.2052 * (z - 0.066)

    prof = [(0.0, 0.03), (0.19, 0.03), (0.19, 0.048), (0.178, 0.06), (0.163, 0.066)]
    mats = ['SKY_Rubber'] * 4
    for (z0, z1) in ((0.25, 0.34), (0.44, 0.5)):
        prof.append((rz(z0), z0)); mats.append('SKY_Coral')
        prof.append((rz(z0) + 0.0045, z0 + 0.004)); mats.append('SKY_Pearl')
        prof.append((rz(z1) + 0.0045, z1 - 0.004)); mats.append('SKY_Pearl')
        prof.append((rz(z1), z1)); mats.append('SKY_Pearl')
    prof += [(rz(0.652), 0.652), (0.028, 0.684), (0.014, 0.696), (0.0, 0.7)]
    mats += ['SKY_Coral'] * 4
    mb = MB()
    mb.lathe(prof, 16, 'SKY_Coral', mats=mats)
    a.part(mb, name="cone")


# --------------------------------------------------------------------------- runway beacon

@asset("runway_beacon", "Props", "props", ao=PROP_AO, render=dict(PROP_RENDER, el=26.0))
def runway_beacon(a):
    """Runway edge light: bolted ink base plate, frangible metal post with a coral break-coupling, brass
    lamp housing with a wire guard, and a separate fresnel-ringed 'Lens' (pivot at the lens centre)."""
    mb = MB()
    mb.lathe([(0, 0), (0.2, 0), (0.2, 0.026), (0.19, 0.04), (0.166, 0.047), (0.072, 0.056), (0.062, 0.07),
              (0, 0.07)], 16, 'SKY_Ink')
    a.part(mb, name="plate")
    mb = MB()
    for k in range(6):
        ang = 2 * math.pi * k / 6 + math.pi / 6
        bx, by = 0.15 * math.cos(ang), 0.15 * math.sin(ang)
        fs = mb.lathe([(0, 0.04), (0.017, 0.04), (0.017, 0.058), (0.011, 0.064), (0, 0.064)], 6, 'SKY_Metal',
                      cx=bx, cy=by, a0=math.degrees(ang))
    a.part(mb, name="bolts")
    mb = MB()
    M_, C_ = 'SKY_Metal', 'SKY_Coral'
    mb.lathe([(0, 0.06), (0.036, 0.06), (0.036, 0.128), (0.047, 0.136), (0.047, 0.152), (0.036, 0.158),
              (0.036, 0.162), (0.047, 0.168), (0.047, 0.184), (0.036, 0.192), (0.034, 0.272), (0, 0.272)], 12, M_,
             mats=[M_, M_, C_, C_, C_, M_, C_, C_, C_, M_, M_])
    mb.lathe([(0, 0.262), (0.04, 0.262), (0.052, 0.276), (0.086, 0.31), (0.1, 0.334), (0.104, 0.35), (0.098, 0.358),
              (0, 0.358)], 16, 'SKY_Brass')
    a.part(mb, name="post")
    # wire guard: two crossed hoops over the lens
    mb = MB()
    for phi in (math.radians(45), math.radians(135)):
        c, s_ = math.cos(phi), math.sin(phi)
        path = []
        for i in range(11):
            th = math.pi * i / 10
            x = 0.104 * math.cos(th)
            z = 0.342 + 0.15 * math.sin(th)
            path.append(Vector((c * x, s_ * x, z)))
        mb.sweep(path, circle(0.007, 4), 'SKY_Metal')
    ring(mb, 0.098, 0.11, 0.338, 0.35, 12, 'SKY_Metal')
    a.part(mb, name="guard")
    mb = MB()
    mb.lathe([(0, 0.352), (0.09, 0.352), (0.09, 0.382), (0.073, 0.397), (0.073, 0.418), (0.055, 0.431),
              (0.055, 0.446), (0.032, 0.458), (0, 0.465)], 16, 'SKY_Light')
    a.part(mb, target="Lens", name="lens")
    a.set_target("Lens", pivot=(0, 0, 0.4))
    a.empty("LIGHT_beacon", (0, 0, 0.42))


# --------------------------------------------------------------------------- switch box

@asset("switch_box", "Props", "props", ao=PROP_AO, render=dict(PROP_RENDER, el=16.0))
def switch_box(a):
    """Beacon switch pedestal ~1.1 m: pearl cabinet with a hinged service door (brass hinges, latch, coral
    hazard chevrons), louvred side vent, teal control plate with three indicator lights and a dial, brass
    cap, rear cable conduit. 'Lever' is a separate object pivoting at its hinge between two brass cheek
    plates on the north face; modelled UP (= off). Rotate about the lever's local X (+160 deg in Unity
    swings it out toward Unity north and down) for ON."""
    hz, hy = 0.72, -0.235
    mb = MB()
    fs = mb.prism(rrect(0.56, 0.44, 0.07, 2), 0.0, 0.08, 'SKY_SandstoneDeep')
    weight_edges(mb, [fs[1]])
    a.part(mb, bevel=0.012, seg=2, weight_limit=True, name="foot")
    mb = MB()
    fs = mb.prism(rrect(0.42, 0.32, 0.05, 2), 0.075, 0.995, 'SKY_Pearl')
    weight_edges(mb, [fs[1]])
    a.part(mb, bevel=0.012, seg=2, weight_limit=True, name="body")
    mb = MB()
    fs = mb.prism(rrect(0.48, 0.38, 0.07, 2), 0.99, 1.04, 'SKY_Brass')
    fs2 = mb.prism(rrect(0.36, 0.26, 0.05, 2), 1.035, 1.062, 'SKY_Brass')
    weight_edges(mb, [fs[1], fs2[1]])
    a.part(mb, bevel=0.01, seg=2, weight_limit=True, name="cap")
    # front: service door, hinges, latch, hazard chevrons
    mb = MB()
    plate_y(mb, cham_rect(0.3, 0.42, 0.014, cy=0.36), -0.158, -0.166, 'SKY_Pearl')
    for zc in (0.215, 0.505):
        mb.lathe([(0, zc - 0.03), (0.011, zc - 0.03), (0.011, zc + 0.03), (0, zc + 0.03)], 6, 'SKY_Brass',
                 cx=-0.158, cy=-0.168)
    stud(mb, 0.112, -0.165, 0.405, 0.02, 0.008, 'SKY_Brass', seg=8, axis='-Y')
    mb.box(0.106, 0.118, -0.18, -0.164, 0.34, 0.402, 'SKY_Brass')
    for k in range(3):
        xa = -0.11 + k * 0.075
        base = [(xa, 0.19), (xa + 0.035, 0.19), (xa + 0.075, 0.25), (xa + 0.04, 0.25)]
        mb.loft([[(p[0], -0.165, p[1]) for p in base],
                 [(p[0] + (0.003 if j in (0, 3) else -0.003), -0.171, p[1] + (0.003 if j < 2 else -0.003))
                  for j, p in enumerate(base)]], 'SKY_Coral')
    a.part(mb, name="door")
    # control plate, hinge block, cheek plates, pin, indicator lights, dial
    mb = MB()
    plate_y(mb, cham_rect(0.34, 0.33, 0.02, cy=0.785), -0.158, -0.168, 'SKY_Teal')
    mb.box(-0.052, 0.052, -0.2, -0.166, hz - 0.045, hz + 0.045, 'SKY_Brass')
    tongue = [(-0.172, hz - 0.04), (hy, hz - 0.04)]
    for i in range(1, 8):
        th = math.radians(270 - 180 * i / 8)
        tongue.append((hy + 0.04 * math.cos(th), hz + 0.04 * math.sin(th)))
    tongue += [(hy, hz + 0.04), (-0.172, hz + 0.04)]
    for s in (-1, 1):
        plate_x(mb, tongue, s * 0.038, s * 0.05, 'SKY_Brass')
    mb.sweep([Vector((-0.058, hy, hz)), Vector((0.058, hy, hz))], circle(0.01, 6), 'SKY_Brass')
    for (zc, m) in ((0.68, 'SKY_TealGlow'), (0.765, 'SKY_Light'), (0.85, 'SKY_Coral')):
        stud(mb, -0.118, -0.166, zc, 0.02, 0.014, 'SKY_Brass', seg=6, axis='-Y',
             mats=['SKY_Brass', 'SKY_Brass', m, m, m])
    stud(mb, 0.112, -0.166, 0.83, 0.034, 0.008, 'SKY_Brass', seg=8, axis='-Y',
         mats=['SKY_Brass', 'SKY_Brass', 'SKY_Brass', 'SKY_Pearl', 'SKY_Pearl'])
    nd = rot2([(0.0, -0.003), (0.024, -0.002), (0.024, 0.002), (0.0, 0.003)], 50)
    plate_y(mb, shift(nd, 0.112, 0.83), -0.172, -0.176, 'SKY_Ink')
    a.part(mb, name="controls")
    # louvred vent on the east side (Blender -X), cable conduit at the back
    mb = MB()
    for sx in (-1, 1):
        ring_prism(mb, cham_rect(0.17, 0.24, 0.0), cham_rect(0.136, 0.206, 0.0), 0.207 * sx, 0.217 * sx, 'SKY_Brass',
                   origin=(0, 0, 0.74), u=(0, 1, 0), v=(0, 0, 1), w=(1, 0, 0))
        for k in range(4):
            zc = 0.66 + k * 0.05
            blade = shift(rot2(cham_rect(0.006, 0.05, 0.0), -40 * sx), 0.212 * sx, zc)
            mb.prism_frame(blade, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), -0.066, 0.066, 'SKY_Pearl')
    conduit = [Vector((0, 0.15, 0.3)), Vector((0, 0.19, 0.3)), Vector((0, 0.212, 0.278)), Vector((0, 0.214, 0.2)),
               Vector((0, 0.214, 0.07))]
    mb.sweep(conduit, circle(0.022, 6), 'SKY_Ink')
    mb.sweep([Vector((0, 0.156, 0.3)), Vector((0, 0.18, 0.3))], circle(0.032, 8), 'SKY_Brass')
    a.part(mb, name="sides")
    # the lever (separate object, pivot = hinge axis)
    mb = MB()
    mb.sweep([Vector((-0.034, hy, hz)), Vector((0.034, hy, hz))], circle(0.026, 10), 'SKY_Brass')
    mb.lathe([(0, hz + 0.015), (0.014, hz + 0.015), (0.014, hz + 0.2), (0.0195, hz + 0.206), (0.0195, hz + 0.284),
              (0.014, hz + 0.29), (0.014, hz + 0.31), (0, hz + 0.31)], 8, 'SKY_Brass', cx=0, cy=hy,
             mats=['SKY_Brass', 'SKY_Brass', 'SKY_Rubber', 'SKY_Rubber', 'SKY_Rubber', 'SKY_Brass', 'SKY_Brass'])
    mb.sphere(0.042, 10, 6, 'SKY_Coral', c=(0, hy, hz + 0.33))
    a.part(mb, target="Lever", name="lever")
    a.set_target("Lever", pivot=(0, hy, hz))
    a.notes.append("Lever pivot = hinge (Blender (0,-0.235,0.72)); modelled up = OFF.")


# --------------------------------------------------------------------------- cell dock

@asset("cell_dock", "Props", "props", ao=PROP_AO, render=dict(PROP_RENDER, el=24.0))
def cell_dock(a):
    """Power-cell charging dock ~0.62 m: tulip-shaped pearl pedestal with a glowing teal waist groove and
    top band, brass seat with a glowing contact pad, three teal clamp claws with rubber pads, and a
    rubber charge cable running to a ground junction box. SOCKET_cell at the seat point (pad centre)."""
    D, P, B, G = 'SKY_SandstoneDeep', 'SKY_Pearl', 'SKY_Brass', 'SKY_TealGlow'
    pts = [(0, 0), (0.3, 0), (0.3, 0.032), (0.29, 0.046), (0.268, 0.052),
           (0.255, 0.066), (0.228, 0.15), (0.206, 0.212), (0.2, 0.218), (0.19, 0.222), (0.19, 0.238), (0.2, 0.242),
           (0.205, 0.25), (0.222, 0.318), (0.244, 0.35), (0.25, 0.364), (0.25, 0.386), (0.24, 0.398), (0, 0.398)]
    mats = [D, D, D, D,
            P, P, P, P, P, G, P,
            P, P, P, G, G, P, P]
    mb = MB()
    mb.lathe(pts, 16, P, mats=mats)
    a.part(mb, name="pedestal")
    mb = MB()
    mb.lathe([(0, 0.394), (0.168, 0.394), (0.17, 0.422), (0.162, 0.434), (0.07, 0.438), (0.058, 0.438),
              (0.052, 0.441), (0, 0.441)], 16, B,
             mats=[B, B, B, B, B, G, G])
    a.part(mb, name="seat")
    # clamp claws (sized for the 0.14 m courier power cell; pads clear it by ~5 mm)
    mb = MB()
    for k in range(3):
        ang = math.radians(90 + 120 * k)
        c, s = math.cos(ang), math.sin(ang)
        rp = [(0.132, 0.41), (0.146, 0.47), (0.126, 0.545), (0.1, 0.6), (0.09, 0.628)]
        path = [Vector((r * c, r * s, z)) for (r, z) in rp]
        mb.sweep(path, cham_rect(0.046, 0.024, 0.007), 'SKY_Teal', up=Vector((c, s, 0)))
    a.part(mb, name="claws")
    mb = MB()
    for k in range(3):
        ang = 90 + 120 * k
        fs = mb.cbox(0.0, 0.0, 0.0, 0.022, 0.036, 0.05, 'SKY_Rubber')
        mb.transform(M_tr(0.086 * math.cos(math.radians(ang)), 0.086 * math.sin(math.radians(ang)), 0.585)
                     @ M_rot(ang), fs)
    a.part(mb, name="pads")
    # charge cable + junction box behind (Blender +Y = Unity south)
    mb = MB()
    cable = [Vector((0.0, 0.2, 0.13)), Vector((0.0, 0.252, 0.118)), Vector((0.022, 0.282, 0.07)),
             Vector((0.07, 0.29, 0.024)), Vector((0.14, 0.275, 0.019)), Vector((0.192, 0.24, 0.019)),
             Vector((0.21, 0.215, 0.012)), Vector((0.215, 0.208, -0.01))]
    mb.sweep(cable, circle(0.017, 6), 'SKY_Rubber')
    mb.sweep([Vector((0.0, 0.19, 0.133)), Vector((0.0, 0.252, 0.124))], circle(0.027, 8), 'SKY_Brass')
    mb.lathe([(0, 0.0), (0.042, 0.0), (0.042, 0.01), (0.032, 0.016), (0.0, 0.016)], 10, 'SKY_Brass', cx=0.215,
             cy=0.208)
    a.part(mb, name="cable")
    a.empty("SOCKET_cell", (0.0, 0.0, 0.44))


# --------------------------------------------------------------------------- awning

@asset("awning_striped", "Props", "props", ao=PROP_AO, render=dict(PROP_RENDER, el=20.0))
def awning_striped(a):
    """Wall-mounted striped awning 2.4 m wide: gently domed coral/pearl canvas (coral strips sit proud),
    scalloped valance, brass wall rail, front bar with finials and two folding arms. Pivot = wall attachment
    (top back edge centre); projects toward Unity north (Blender -Y) and slopes down."""
    w, depth, drop, t = 2.4, 1.05, 0.5, 0.028
    n = 10
    curve = []
    for i in range(7):
        s = i / 6
        curve.append((-depth * s, -drop * (s ** 1.35)))
    # offset curve (thickness) toward the underside
    under = []
    for i, (y, z) in enumerate(curve):
        if i == 0:
            ty, tz = curve[1][0] - y, curve[1][1] - z
        elif i == len(curve) - 1:
            ty, tz = y - curve[i - 1][0], z - curve[i - 1][1]
        else:
            ty, tz = curve[i + 1][0] - curve[i - 1][0], curve[i + 1][1] - curve[i - 1][1]
        L = math.hypot(ty, tz)
        ny, nz = tz / L, -ty / L          # left normal of a -Y heading path (points down/back)
        if nz > 0:
            ny, nz = -ny, -nz
        under.append((y + ny * t, z + nz * t))
    prof = curve + list(reversed(under))
    zf = curve[-1][1]
    mb = MB()
    for i in range(n):
        x0 = -w / 2 + w * i / n
        x1 = -w / 2 + w * (i + 1) / n
        coral = i % 2 == 0
        p = shift(prof, 0.0, 0.004) if coral else prof
        mb.prism_frame(p, (0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), x0, x1, 'SKY_Coral' if coral else 'SKY_Pearl')
        # scalloped valance tongue
        xc = (x0 + x1) / 2
        rr = (x1 - x0) / 2
        out = [(x0, zf + 0.014), (x1, zf + 0.014), (x1, zf - 0.15)]
        for k in range(1, 6):
            th = math.radians(-180 * k / 6)
            out.append((xc + rr * math.cos(th), zf - 0.15 + rr * math.sin(th) * 0.95))
        out.append((x0, zf - 0.15))
        yv = -depth - (0.004 if coral else 0.0)
        mb.prism_frame(out, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), yv - 0.004, yv + 0.016,
                       'SKY_Coral' if coral else 'SKY_Pearl')
    a.part(mb, name="canvas")
    mb = MB()
    bar_x(mb, -w / 2 - 0.04, w / 2 + 0.04, cham_rect(0.05, 0.07, 0.012, cx=-0.025, cy=0.0), 'SKY_Brass')
    yb, zb = -depth + 0.035, zf - 0.035
    mb.sweep([Vector((-w / 2 + 0.02, yb, zb)), Vector((w / 2 - 0.02, yb, zb))], circle(0.018, 8), 'SKY_Brass')
    for s in (-1, 1):
        mb.sphere(0.03, 8, 4, 'SKY_Brass', c=(s * (w / 2 - 0.0), yb, zb))
        xa = s * 1.02
        mb.sweep([Vector((xa, -0.03, -0.62)), Vector((xa, yb + 0.02, zb - 0.01))], circle(0.016, 6), 'SKY_Brass')
        mb.sphere(0.026, 8, 4, 'SKY_Brass', c=(xa, yb + 0.02, zb - 0.01))
        mb.box(xa - 0.04, xa + 0.04, -0.02, 0.0, -0.68, -0.56, 'SKY_Brass')
    a.part(mb, name="frame")


# --------------------------------------------------------------------------- shade sail

def sail_curved(mb, corners, mat='SKY_Fabric', sag=0.25, curve=0.1, n=8, t=0.03, band=None):
    """Tensioned triangular sail with concave (catenary-cut) edges and a sagging belly; closed thin shell.
    Returns the three edge polylines (top surface, mid-thickness) for hems."""
    C = [Vector(c) for c in corners]
    nrm = (C[1] - C[0]).cross(C[2] - C[0]).normalized()
    if nrm.z < 0:
        nrm = -nrm
    cen = (C[0] + C[1] + C[2]) / 3
    pts = {}
    for i in range(n + 1):
        for j in range(n + 1 - i):
            u, v = i / n, j / n
            w_ = 1 - u - v
            p = C[0] * w_ + C[1] * u + C[2] * v
            # pull edges in toward the centre: edge v=0 (C0-C1), u=0 (C0-C2), w=0 (C1-C2)
            d = Vector((0, 0, 0))
            for (bk, b1, b2, ea, eb) in ((v, w_, u, 0, 1), (u, w_, v, 0, 2), (w_, u, v, 1, 2)):
                if b1 + b2 > 1e-6:
                    sp = b2 / (b1 + b2)
                    mid = (C[ea] + C[eb]) / 2
                    dirn = (cen - mid)
                    dirn = dirn - nrm * dirn.dot(nrm)
                    d += dirn * (curve * 4 * sp * (1 - sp) * (1 - bk) ** 3)
            p = p + d - nrm * (sag * 27 * u * v * w_)
            pts[(i, j)] = p
    faces = []
    for i in range(n):
        for j in range(n - i):
            faces.append([(i, j), (i + 1, j), (i, j + 1)])
            if i + j + 2 <= n:
                faces.append([(i + 1, j), (i + 1, j + 1), (i, j + 1)])
    T = {k: mb.v(p) for k, p in pts.items()}
    B = {k: mb.v(p - nrm * t) for k, p in pts.items()}
    fs = []
    cnt = {}
    for f in faces:
        dists = [min(k[0], k[1], n - k[0] - k[1]) for k in f]
        m = band if band and max(dists) <= 1 and min(dists) == 0 else mat     # outermost strip only
        fs.append(mb.f([T[k] for k in f], m))
        fs.append(mb.f([B[k] for k in reversed(f)], m))
        for k in range(3):
            key = tuple(sorted((f[k], f[(k + 1) % 3])))
            cnt[key] = cnt.get(key, 0) + 1
    for f in faces:
        for k in range(3):
            a_, b_ = f[k], f[(k + 1) % 3]
            if cnt[tuple(sorted((a_, b_)))] == 1:
                fs.append(mb.f([T[b_], T[a_], B[a_], B[b_]], mat))
    mb._recalc(fs)
    half = nrm * (t * 0.5)
    e01 = [pts[(i, 0)] - half for i in range(n + 1)]
    e12 = [pts[(n - j, j)] - half for j in range(n + 1)]
    e20 = [pts[(0, n - j)] - half for j in range(n + 1)]
    return [e01, e12, e20], nrm


@asset("shade_sail", "Props", "props", ao=dict(PROP_AO, dist=0.8), render=dict(PROP_RENDER, el=28.0))
def shade_sail(a):
    """Free-standing triangular shade sail (~4.6 m span): catenary-cut fabric with a teal border band and
    cable hem, brass corner plates and tension cables to three tapered teal masts (brass collars and
    finials) on pearl footings."""
    pts = [(-2.3, -1.3, 3.2), (2.3, -1.3, 2.7), (0.0, 2.6, 3.4)]
    mbm = MB(); mbf = MB(); mbc = MB()
    tops = []
    for (x, y, z) in pts:
        mx, my = x * 1.08, y * 1.08
        ztop = z + 0.26
        T_, B_ = 'SKY_Teal', 'SKY_Brass'
        r_at = lambda z_: 0.072 - 0.022 * (z_ - 0.12) / (ztop - 0.12)
        mbm.lathe([(0, 0.12), (0.072, 0.12), (r_at(0.6), 0.6), (0.088, 0.614), (0.088, 0.666), (r_at(0.68), 0.68),
                   (r_at(ztop - 0.11), ztop - 0.11), (0.07, ztop - 0.098), (0.07, ztop - 0.052), (0.05, ztop - 0.04),
                   (0.05, ztop), (0, ztop)], 8, T_,
                  mats=[T_, T_, B_, B_, B_, T_, B_, B_, B_, T_, T_], cx=mx, cy=my)
        mbm.sphere(0.062, 8, 4, 'SKY_Brass', c=(mx, my, ztop + 0.03))
        mbm.lathe([(0, ztop + 0.08), (0.022, ztop + 0.085), (0, ztop + 0.15)], 6, 'SKY_Brass', cx=mx, cy=my)
        P_ = 'SKY_Pearl'
        mbf.lathe([(0, 0), (0.25, 0), (0.25, 0.07), (0.225, 0.1), (0.13, 0.122), (0.11, 0.124), (0.11, 0.138),
                   (0.08, 0.146), (0, 0.146)], 8, P_, mats=[P_, P_, P_, P_, P_, B_, B_, B_], cx=mx, cy=my)
        tops.append(Vector((mx, my, ztop - 0.07)))
    a.part(mbm, name="masts")
    a.part(mbf, name="footings")
    mb = MB()
    edges, nrm = sail_curved(mb, pts, sag=0.3, curve=0.11, n=8, t=0.03, band='SKY_TealLight')
    a.part(mb, name="sail")
    # hem cable along the curved edges, corner plates, tension cables to the masts
    for e in edges:
        mbc.sweep(e[::2] if len(e) % 2 else e, circle(0.019, 4, a0=45), 'SKY_Teal')
    cen = sum((Vector(p) for p in pts), Vector()) / 3
    for k, (x, y, z) in enumerate(pts):
        c = Vector((x, y, z)) - nrm * 0.015
        inward = (cen - c)
        inward = (inward - nrm * inward.dot(nrm)).normalized()
        side = nrm.cross(inward).normalized()
        tri = [c - inward * 0.04, c + inward * 0.2 + side * 0.09, c + inward * 0.2 - side * 0.09]
        lo = [p - nrm * 0.022 for p in tri]
        hi = [p + nrm * 0.022 for p in tri]
        mbc.loft([lo, hi], 'SKY_Brass')
        mbc.sweep([c - inward * 0.02, tops[k]], circle(0.011, 5), 'SKY_Metal')
        mbc.sweep([c.lerp(tops[k], 0.35), c.lerp(tops[k], 0.6)], circle(0.02, 6), 'SKY_Brass')
    a.part(mbc, name="rigging")


# --------------------------------------------------------------------------- planter

@asset("planter_box", "Props", "props", ao=PROP_AO, render=PROP_RENDER)
def planter_box(a):
    """Stone planter 1.3 x 0.7 m: deep plinth, tapered sandstone trough with raised pearl panel mouldings, an
    overhanging pearl rim; planted with a clipped leaf dome, arching strap leaves and bougainvillea bracts."""
    mb = MB()
    fs = mb.prism(rrect(1.24, 0.64, 0.05, 2), 0.0, 0.07, 'SKY_SandstoneDeep')
    weight_edges(mb, [fs[1]])
    a.part(mb, bevel=0.012, seg=2, weight_limit=True, name="plinth")
    mb = MB()
    r0 = rrect(1.12, 0.52, 0.05, 2)
    r1 = rrect(1.2, 0.6, 0.06, 2)
    mb.loft([[(x, y, 0.068) for (x, y) in r0], [(x, y, 0.495) for (x, y) in r1]], 'SKY_Sandstone')
    # raised panel mouldings on the four tapered faces
    for (axis, sg, half_len, h0, h1) in (('Y', -1, 0.44, 0.26, 0.3), ('Y', 1, 0.44, 0.26, 0.3),
                                          ('X', -1, 0.17, 0.56, 0.6), ('X', 1, 0.17, 0.56, 0.6)):
        # face plane: from (h0 at z 0.068) to (h1 at z 0.495)
        zc = 0.29
        hc = h0 + (h1 - h0) * (zc - 0.068) / (0.495 - 0.068)
        dz, dh = 0.427, h1 - h0
        L_ = math.hypot(dz, dh)
        if axis == 'Y':
            upv = Vector((0, sg * dh, dz)) / L_
            out = Vector((0, sg * dz, -dh)) / L_
            origin = Vector((0, sg * hc, zc))
            u = Vector((1, 0, 0))
        else:
            upv = Vector((sg * dh, 0, dz)) / L_
            out = Vector((sg * dz, 0, -dh)) / L_
            origin = Vector((sg * hc, 0, zc))
            u = Vector((0, 1, 0))
        L = half_len * 2
        ring_prism(mb, cham_rect(L, 0.3, 0.0), cham_rect(L - 0.07, 0.23, 0.0), -0.002, 0.012, 'SKY_Pearl',
                   origin=origin, u=u, v=upv, w=out)
    a.part(mb, name="body")
    mb = MB()
    fs, top = ring_prism(mb, rrect(1.3, 0.7, 0.07, 2), rrect(1.1, 0.5, 0.035, 2), 0.49, 0.56, 'SKY_Pearl')
    weight_edges(mb, top)
    a.part(mb, bevel=0.01, seg=2, weight_limit=True, name="rim")
    mb = MB()
    mb.prism(rrect(1.12, 0.52, 0.04, 2), 0.44, 0.535, 'SKY_PalmTrunk')
    a.part(mb, name="soil")
    # planting: clipped dome of florets, strap leaves spilling over the rim, a few bract heads
    mb = MB()
    for xc in (-0.26, 0.26):
        ico_blob(mb, (xc, 0.0, 0.62), 0.3, 'SKY_PalmLeaf', level=2, sz=0.95, noise=0.1, seed=3, flat_z=0.53)
    for i, (c, r, sz) in enumerate(floret_layout(9, 7, 0.6, 0.3, 1.0, 0.15, 0.21, zbase=0.62, sz=0.85)):
        ico_blob(mb, (c[0], c[1], c[2]), r, 'SKY_PalmLeaf', level=2, sz=sz, noise=0.15, seed=20 + i, flat_z=0.53,
                 lobes=4)
    a.part(mb, name="dome")
    mb = MB()
    rnd = random.Random(12)
    for k in range(14):
        ang = 2 * math.pi * k / 14 + rnd.uniform(-0.15, 0.15)
        bx, by = 0.42 * math.cos(ang), 0.15 * math.sin(ang)
        d = Vector((math.cos(ang) * 0.45, math.sin(ang) * 0.45, rnd.uniform(1.1, 1.4))).normalized()
        strap_leaf(mb, Vector((bx, by, 0.53)), d, rnd.uniform(0.28, 0.34), rnd.uniform(0.075, 0.09), droop=0.55)
    for k in range(5):
        ang = 2 * math.pi * k / 5 + 0.4
        c = Vector((0.36 * math.cos(ang), 0.17 * math.sin(ang), 0.8 + 0.06 * math.sin(k * 1.7)))
        nd = (c - Vector((0, 0, 0.5))).normalized()
        bract_cluster(mb, c, nd, 0.1, seed=k, petals=5, open_=0.4)
    a.part(mb, name="leaves")
