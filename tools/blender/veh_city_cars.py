"""Ambient city traffic for SKYFOLD: The Last Flight.

Original procedural models (Awaiz Ahmed / Team Kanban), not AI-generated.
    blender -b --factory-startup -P tools/blender/veh_city_cars.py [-- --no-render]

city_car_a.fbx  compact hatch, SKY_Sandstone body, pearl roof,       ~3.8 m
city_car_b.fbx  small van,     SKY_Teal body, pearl roof and belt,   ~3.8 m
Same family as the courier car / shuttle: pearl trim, round SKY_Light headlights, coral tail
lights, glass set into dark recesses so cabins never read see-through.
Detail pass: smooth monotone-cubic body lofts unioned into one shell, boolean wheel arches with
ink liners, recessed windows with inset glass, door / hatch / bonnet / fuel-flap seams cut as
real grooves, grille, bumpers with rubber strips, door handles, mirrors, wipers, roof rails or
rack, blank plate recess, exhaust tip, spoked rims. Traffic budget ~7k tris (< 12k ceiling).
Hierarchy (pivots):
    city_car_a | city_car_b (empty)   ground level, centred between the axles
      Body
      Wheel_FL/FR/RL/RR               hub centres, spin about local X
Faces Blender -Y (Unity +Z).
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C
import veh_common as V
from veh_common import (PEARL, TEAL, CORAL, LIGHT, INK, RUBBER, BRASS, GLASS, METAL, SAND,
                        frame, T, sweep, slab, lathe_m, tile)
from chars_common import Vector, Matrix, radians, sin, cos, pi

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS


# ---------------------------------------------------------------------------- shared helpers
class Shell:
    """Two Pods (lower body + cabin) treated as one surface: picks whichever is outermost."""

    def __init__(self, lower, cabin, z_split):
        self.lo, self.ca, self.zs = lower, cabin, z_split

    def _pods(self, z):
        out = []
        if z <= self.lo.s[-1][0]:
            out.append(self.lo)
        if z >= self.ca.s[0][0]:
            out.append(self.ca)
        return out or [self.lo]

    def flank(self, y, z, side, off=0.0):
        best = None
        for p in self._pods(z):
            q, n = p.flank(y, z, side)
            if best is None or abs(q.x) > abs(best[0].x):
                best = (q, n)
        return best[0] + best[1] * off, best[1]

    def face(self, x, z, face, off=0.0):
        best = None
        for p in self._pods(z):
            q, n = p.face(x, z, face)
            if best is None or q.y * face > best[0].y * face:
                best = (q, n)
        return best[0] + best[1] * off, best[1]

    def top(self, x, y):
        a = self.lo.top(x, y)
        b = self.ca.top(x, y)
        if a is None:
            return b
        if b is None:
            return a
        return a if a[0].z > b[0].z else b


def poly_path(pts, r=0.04, n=3):
    """Rounded polyline corners (open path) -> dense 2D points."""
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[i + 1])
        d1, d2 = (a - b).normalized(), (c - b).normalized()
        rr = min(r, (a - b).length * 0.45, (c - b).length * 0.45)
        p0, p1 = b + d1 * rr, b + d2 * rr
        for k in range(n + 1):
            t = k / n
            q = p0 * (1 - t) ** 2 + b * 2 * t * (1 - t) + p1 * t * t
            out.append((q.x, q.y))
    out.append(pts[-1])
    return out


def poly_loop(pts, r=0.05, n=3):
    """Closed rounded polygon (CCW input) -> dense 2D points."""
    m = len(pts)
    out = []
    for i in range(m):
        a, b, c = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[(i + 1) % m])
        d1, d2 = (a - b).normalized(), (c - b).normalized()
        rr = min(r, (a - b).length * 0.45, (c - b).length * 0.45)
        p0, p1 = b + d1 * rr, b + d2 * rr
        for k in range(n + 1):
            t = k / n
            q = p0 * (1 - t) ** 2 + b * 2 * t * (1 - t) + p1 * t * t
            out.append((q.x, q.y))
    return out


def densify2(pts, step, closed=False):
    out = []
    m = len(pts)
    rng = range(m) if closed else range(m - 1)
    for i in rng:
        a, b = Vector(pts[i]), Vector(pts[(i + 1) % m])
        k = max(1, int((b - a).length / step))
        for s in range(k):
            q = a + (b - a) * (s / k)
            out.append((q.x, q.y))
    if not closed:
        out.append(pts[-1])
    return out


def seam(cut, shell, kind, pts2d, closed=False, side=1, width=0.0055, step=0.05):
    """Ribbon cutter along a surface curve. kind: 'flank' (u=y, v=z), 'back'/'front'
    (u=x, v=z) or 'top' (u=x, v=y)."""
    d = densify2(pts2d, step, closed)
    P, N = [], []
    for (u, v) in d:
        if kind == 'flank':
            p, n = shell.flank(u, v, side)
        elif kind == 'top':
            p, n = shell.top(u, v)
        else:
            p, n = shell.face(u, v, 1 if kind == 'back' else -1)
        P.append(p)
        N.append(n)
    V.ribbon(cut, P, N, width, 0.010, 0.012, INK, closed=closed)


def mapper(shell, kind, side=1, off=0.0):
    if kind == 'flank':
        return lambda u, v: shell.flank(u, v, side, off)
    if kind == 'top':
        return lambda u, v: shell.top(u, v)
    f = 1 if kind == 'back' else -1
    return lambda u, v: shell.face(u, v, f, off)


def window(cut, glass, shell, kind, outline, side=1, inset=0.016, depth=0.014):
    """Recess cutter (ink walls) + glass pane set 5 mm below the body surface."""
    loop = poly_loop(outline, 0.05, 3)
    loop = densify2(loop, 0.09, closed=True)
    loop = V.ccw(loop)
    m = mapper(shell, kind, side)
    V.surface_patch(cut, loop, m, depth, 0.03, INK)
    cx = sum(p[0] for p in loop) / len(loop)
    cy = sum(p[1] for p in loop) / len(loop)
    small = []
    for (u, v) in loop:
        du, dv = u - cx, v - cy
        L = math.hypot(du, dv)
        k = max(0.0, (L - inset)) / L if L > 1e-9 else 0.0
        small.append((cx + du * k, cy + dv * k))
    # glass: thin pane hugging the surface 4-8 mm below it
    def deform(v, m=m):
        p, n = m(v.x, v.y)
        return p + n * (-0.004 if v.z > 0 else -0.008)
    V.pane(glass, small, 2.0, GLASS, deform=deform, scales=(1.0, 0.5))


def arches(cut, axle, track, r_arch, z_hub, x_in=0.47):
    for sx in (1, -1):
        for sy in (1, -1):
            M = T(0, sy * axle, z_hub)
            p = C.Part()
            lathe_m(p, [(0.0, x_in), (r_arch, x_in), (r_arch, 1.2), (0.0, 1.2)], 28, INK,
                    M=M, axis='X')
            if sx < 0:
                p.mirror_x()
            V.part_add(cut, p)


def bumper(part, shell, face, z, sec_w, sec_h, mat, strip_mat=RUBBER, span=0.78, n=9,
           off=0.032):
    base = -pi / 2 if face < 0 else pi / 2
    pod = shell.lo
    ts = [base - span + 2 * span * k / (n - 1) for k in range(n)]
    pts = [pod.point(t, z, off) for t in ts]
    a, b = pts[0], pts[-1]
    ea = a + Vector((-math.copysign(0.025, a.x), -face * 0.06, 0))
    eb = b + Vector((-math.copysign(0.025, b.x), -face * 0.06, 0))
    sec = V.section_rrect(sec_w, sec_h, min(sec_w, sec_h) * 0.42, 2)
    scl = [(0.78, 0.76)] + [(1.0, 1.0)] * len(pts) + [(0.78, 0.76)]
    sweep(part, [ea] + pts + [eb], sec, mat, up=(0, 0, 1), scales=scl)
    if strip_mat:
        st = [(x - sec_w / 2 - 0.002, y) for (x, y) in
              V.ccw([(0.008, -0.014), (0.008, 0.014), (0.0, 0.018), (-0.008, 0.014),
                     (-0.008, -0.014), (0.0, -0.018)])]
        sweep(part, pts[1:-1], st, strip_mat, up=(0, 0, 1))


def wheels(root, axle, track, r, width, spokes, hub_mat=PEARL):
    out = []
    for name, sx, sy in (("Wheel_FL", 1, -1), ("Wheel_FR", -1, -1), ("Wheel_RL", 1, 1),
                         ("Wheel_RR", -1, 1)):
        c = Vector((sx * track, sy * axle, r))
        p = V.wheel_hq(r, width, sx, seg=18, lugs=0, grooves=1, spokes=spokes, spoke_w=0.12,
                       spoke_d=0.07, disc=False, caliper=False, nuts=0, hub_seg=10, valve=None,
                       lip=PEARL, spoke=hub_mat, hub=hub_mat, cap=BRASS, rim_r=0.60)
        p.transform(p.bm.verts, Matrix.Translation(c))
        out.append(C.merge_to_object(name, [p.to_temp()], pivot=c, parent=root, sharp_deg=40))
    return out


def mirror_unit(part, shell, y, z, side, body_mat, reach=0.10):
    p, n = shell.flank(y, z, side)
    hc = p + Vector((side * reach, 0.02, 0.03))
    part.tube([p - Vector((side * 0.01, 0, 0)), hc - Vector((side * 0.03, 0, 0.01))], 0.010, 6,
              INK, caps='flat')
    M = frame(hc, (-side * 0.25, 1, 0.05), (0, 0, 1))
    g = slab(part, 0.085, 0.060, 0.040, 0.024, 0.014, body_mat, M=M, nc=2, ne=1)
    part.assign(g['top'][-12:], METAL)


def wiper(part, shell, x0, x1, z):
    pts = []
    for k in range(4):
        x = x0 + (x1 - x0) * k / 3
        p, n = shell.face(x, z + 0.012 * k / 3, -1, 0.006)
        pts.append(p)
    sweep(part, pts, V.section_rrect(0.010, 0.007, 0.002, 1), INK, up=(0, -0.6, 1))


# ---------------------------------------------------------------------------- city_car_a
LB_A = [(0.26, -1.66, 1.70, 0.74), (0.32, -1.80, 1.84, 0.815), (0.42, -1.875, 1.895, 0.845),
        (0.60, -1.90, 1.90, 0.85), (0.76, -1.885, 1.895, 0.85), (0.86, -1.83, 1.865, 0.84),
        (0.92, -1.72, 1.82, 0.82), (0.955, -1.55, 1.76, 0.79)]
CB_A = [(0.90, -1.00, 1.74, 0.80), (0.96, -0.96, 1.72, 0.795), (1.06, -0.80, 1.66, 0.775),
        (1.20, -0.56, 1.56, 0.73), (1.32, -0.36, 1.44, 0.68), (1.41, -0.20, 1.33, 0.635),
        (1.47, -0.07, 1.21, 0.585), (1.50, 0.04, 1.08, 0.53)]


def build_a():
    """Compact hatch: low bonnet, raked screen, short sloping hatch, two-tone pearl roof."""
    C.reset_scene()
    root = C.new_empty("city_car_a", None, (0, 0, 0), size=0.5)
    axle, track, r = 1.225, 0.70, 0.31
    paint = SAND
    lo = V.Pod(LB_A, n=3.6, step=[1, 1, 2, 1, 1, 1, 1])
    ca = V.Pod(CB_A, n=3.2, step=[1, 1, 1, 1, 1, 1, 1])
    sh = Shell(lo, ca, 0.955)
    pb, pc = C.Part(), C.Part()
    lo.build(pb, 32, paint, crown=0.010, fill=2, bottom_mat=INK)
    ca.build(pc, 32, paint, bands=[(1.405, 2.0, PEARL)], crown=0.010, fill=2)
    body = pb.to_temp(name="lo")
    V.boolean(body, [pc.to_temp(name="ca")], op='UNION')
    # cutters: arches, window recesses, seams
    cut, glass = C.Part(), C.Part()
    arches(cut, axle, track, 0.375, r)
    window(cut, glass, sh, 'front', [(-0.57, 1.005), (0.57, 1.005), (0.46, 1.345), (-0.46, 1.345)])
    window(cut, glass, sh, 'back', [(-0.53, 1.03), (0.53, 1.03), (0.43, 1.33), (-0.43, 1.33)])
    for side in (1, -1):
        door = [(-0.60, 1.005), (0.33, 1.005), (0.33, 1.335), (-0.12, 1.335)]
        quarter = [(0.45, 1.005), (1.28, 1.005), (0.98, 1.33), (0.45, 1.33)]
        if side < 0:
            door, quarter = door[::-1], quarter[::-1]
        window(cut, glass, sh, 'flank', door, side=side)
        window(cut, glass, sh, 'flank', quarter, side=side)
        u = poly_path([(-0.66, 1.0), (-0.66, 0.40), (0.39, 0.40), (0.39, 1.0)], 0.05)
        seam(cut, sh, 'flank', u, side=side)
    seam(cut, sh, 'back', poly_loop([(-0.62, 0.60), (0.62, 0.60), (0.56, 1.37), (-0.56, 1.37)],
                                    0.07), closed=True)
    seam(cut, sh, 'top', poly_path([(0.66, -1.01), (0.68, -1.64), (-0.68, -1.64), (-0.66, -1.01)],
                                   0.10), step=0.06)
    seam(cut, sh, 'flank', poly_loop([(1.24, 0.78), (1.33, 0.78), (1.33, 0.87), (1.24, 0.87)][::-1],
                                     0.02), closed=True, side=-1, step=0.03)
    V.boolean(body, [cut.to_temp(name="cut")])
    # ---- details
    d = C.Part()
    for sx in (1, -1):
        p, n = sh.face(sx * 0.56, 0.74, -1)
        V.lamp_round(d, p, (n + Vector((0, -0.5, 0))).normalized(), 0.082, body=paint,
                     bezel=PEARL, segs=16, rings=0, depth=0.04)
        p, n = sh.face(sx * 0.70, 0.60, -1)
        V.lamp_round(d, p, n, 0.024, body=paint, bezel=PEARL, lens=LIGHT, segs=8, simple=True,
                     proud=0.7, depth=0.02)
        p, n = sh.face(sx * 0.66, 0.76, 1)
        M = V.lamp_rrect(d, p, (n + Vector((0, 0.4, 0))).normalized(), 0.085, 0.17, 0.03,
                         body=paint, bezel=PEARL, lens=CORAL, depth=0.035, nc=2)
        tile(d, (0, -0.045, 0.010), 0.050, 0.035, 0.004, LIGHT, M=M, ch=0.003)
        # door handle near the rear edge of each door
        p, n = sh.flank(0.27, 0.83, sx)
        slab(d, 0.11, 0.026, 0.016, 0.012, 0.006, PEARL, M=frame(p, n, (0, 0, 1)), nc=2, ne=1)
        mirror_unit(d, sh, -0.66, 1.05, sx, paint)
        # roof rails on two feet
        rail = []
        for y in (-0.02, 0.50, 1.00):
            q = sh.top(sx * 0.47, y)[0]
            rail.append(q + Vector((0, 0, 0.045)))
            lathe_m(d, [(0.016, -0.02), (0.016, 0.012), (0.010, 0.040), (0.0, 0.046)], 8,
                    [INK, INK, INK], M=T(q))
        d.tube(C.spline3(rail, 3), 0.013, 8, PEARL, caps='round', cap_segs=1)
    # grille: recess with pearl slats + brass badge
    gp, gn = sh.face(0.0, 0.60, -1)
    Mg = frame(gp, gn, (0, 0, 1))
    V.rr_lathe(d, 0.46, 0.10, 0.04, [(0.010, -0.025), (0.010, 0.004), (0.004, 0.008),
                                      (-0.003, 0.004), (-0.005, -0.010), (-0.006, -0.012)],
               [PEARL, PEARL, PEARL, INK, INK, INK], M=Mg, nc=2)
    for k in range(3):
        tile(d, (0, -0.028 + 0.028 * k, -0.012), 0.43, 0.012, 0.014, PEARL, M=Mg, ch=0.003)
    bp, bn = sh.face(0.0, 0.80, -1)
    lathe_m(d, [(0.024, -0.01), (0.024, 0.004), (0.018, 0.008), (0.0, 0.009)], 12,
            [BRASS, BRASS, BRASS], M=frame(bp, bn))
    # bumpers, plate, exhaust, wipers
    bumper(d, sh, -1, 0.42, 0.075, 0.11, PEARL)
    bumper(d, sh, 1, 0.42, 0.075, 0.11, PEARL)
    pp, pn = sh.face(0.0, 0.64, 1)
    V.plate_recess(d, pp, pn, 0.30, 0.10, frame_mat=PEARL)
    ex = Vector((-0.42, 1.80, 0.30))
    lathe_m(d, [(0.026, -0.10), (0.026, 0.06), (0.020, 0.064), (0.020, 0.0)], 10,
            [METAL, METAL, INK], M=frame(ex, (0, 1, -0.05)))
    for (a, b) in ((0.48, -0.02), (-0.04, -0.54)):
        wiper(d, sh, a, b, 1.02)
    temps = [body, d.to_temp(), glass.to_temp(recalc=False)]
    bodyob = C.merge_to_object("Body", temps, pivot=(0, 0, 0), parent=root, sharp_deg=50)
    ws = wheels(root, axle, track, r, 0.21, 6)
    C.bake_ao([bodyob] + ws, dist=0.35, samples=40, floor=0.38, ground_z=0.0)
    return root


# ---------------------------------------------------------------------------- city_car_b
LB_B = [(0.26, -1.66, 1.74, 0.74), (0.32, -1.80, 1.86, 0.815), (0.42, -1.875, 1.895, 0.845),
        (0.62, -1.905, 1.905, 0.85), (0.84, -1.895, 1.905, 0.852), (0.96, -1.85, 1.905, 0.85),
        (1.02, -1.70, 1.905, 0.85)]
CB_B = [(0.98, -1.72, 1.905, 0.85), (1.06, -1.60, 1.905, 0.85), (1.30, -1.32, 1.900, 0.845),
        (1.56, -1.16, 1.89, 0.84), (1.70, -1.04, 1.86, 0.80), (1.80, -0.86, 1.76, 0.71),
        (1.85, -0.70, 1.62, 0.60)]


def build_b():
    """Small van: short nose, tall boxy body, cab windows only, sliding door, split rear
    doors, pearl roof with a roof rack."""
    C.reset_scene()
    root = C.new_empty("city_car_b", None, (0, 0, 0), size=0.5)
    axle, track, r = 1.20, 0.70, 0.30
    paint = TEAL
    lo = V.Pod(LB_B, n=4.4, step=[1, 1, 2, 1, 1, 1])
    ca = V.Pod(CB_B, n=4.4, step=[1, 2, 2, 1, 1, 1])
    sh = Shell(lo, ca, 1.02)
    pb, pc = C.Part(), C.Part()
    lo.build(pb, 32, paint, bands=[(0.80, 0.86, PEARL)], ribs=[(0.80, 0.86, 0.004)],
             crown=0.008, fill=2, bottom_mat=INK)
    ca.build(pc, 32, paint, bands=[(1.67, 2.0, PEARL)], crown=0.010, fill=2)
    body = pb.to_temp(name="lo")
    V.boolean(body, [pc.to_temp(name="ca")], op='UNION')
    cut, glass = C.Part(), C.Part()
    arches(cut, axle, track, 0.36, r)
    window(cut, glass, sh, 'front', [(-0.66, 1.10), (0.66, 1.10), (0.60, 1.50), (-0.60, 1.50)])
    for side in (1, -1):
        cab = [(-1.18, 1.10), (-0.50, 1.10), (-0.50, 1.53), (-0.98, 1.53)]
        if side < 0:
            cab = cab[::-1]
        window(cut, glass, sh, 'flank', cab, side=side)
        # cab door seam and the sliding door seam with its track groove
        seam(cut, sh, 'flank', poly_path([(-1.24, 1.56), (-1.24, 0.42), (-0.44, 0.42),
                                          (-0.44, 1.58)], 0.05), side=side)
        seam(cut, sh, 'flank', poly_loop([(-0.36, 0.40), (0.62, 0.40), (0.62, 1.58),
                                          (-0.36, 1.58)][::side], 0.05), closed=True, side=side)
        seam(cut, sh, 'flank', [(0.66, 1.42), (1.70, 1.42)], side=side, width=0.008)
    seam(cut, sh, 'back', poly_loop([(-0.70, 0.40), (0.70, 0.40), (0.70, 1.62), (-0.70, 1.62)],
                                    0.06), closed=True)
    seam(cut, sh, 'back', [(0.0, 0.40), (0.0, 1.62)])
    window(cut, glass, sh, 'back', [(-0.62, 1.20), (-0.06, 1.20), (-0.06, 1.55), (-0.62, 1.55)])
    window(cut, glass, sh, 'back', [(0.06, 1.20), (0.62, 1.20), (0.62, 1.55), (0.06, 1.55)])
    seam(cut, sh, 'top', poly_path([(0.70, -1.30), (0.72, -1.62), (-0.72, -1.62), (-0.70, -1.30)],
                                   0.08), step=0.06)
    V.boolean(body, [cut.to_temp(name="cut")])
    d = C.Part()
    for sx in (1, -1):
        p, n = sh.face(sx * 0.58, 0.76, -1)
        V.lamp_round(d, p, (n + Vector((0, -0.5, 0))).normalized(), 0.085, body=paint,
                     bezel=PEARL, segs=16, rings=0, depth=0.04)
        p, n = sh.face(sx * 0.72, 0.62, -1)
        V.lamp_round(d, p, n, 0.024, body=paint, bezel=PEARL, lens=LIGHT, segs=8, simple=True,
                     proud=0.7, depth=0.02)
        p, n = sh.face(sx * 0.80, 0.80, 1)
        M = V.lamp_rrect(d, p, n, 0.075, 0.24, 0.03, body=paint, bezel=PEARL, lens=CORAL,
                         depth=0.035, nc=2)
        tile(d, (0, -0.075, 0.010), 0.045, 0.045, 0.004, LIGHT, M=M, ch=0.003)
        # cab door handle, sliding door handle
        for (y, z) in ((-0.56, 0.90), (-0.28, 0.90)):
            p, n = sh.flank(y, z, sx)
            slab(d, 0.11, 0.026, 0.016, 0.012, 0.006, PEARL, M=frame(p, n, (0, 0, 1)), nc=2,
                 ne=1)
        mirror_unit(d, sh, -1.16, 1.14, sx, paint, reach=0.08)
    # rear door handles + roof rack
    for x in (-0.10, 0.10):
        p, n = sh.face(x, 0.98, 1)
        slab(d, 0.026, 0.10, 0.016, 0.012, 0.006, PEARL, M=frame(p, n, (0, 0, 1)), nc=2, ne=1)
    for sx in (1, -1):
        rail = []
        for y in (-0.62, 0.30, 1.30):
            q = sh.top(sx * 0.56, y)[0]
            rail.append(q + Vector((0, 0, 0.06)))
            lathe_m(d, [(0.018, -0.02), (0.018, 0.015), (0.011, 0.055), (0.0, 0.062)], 8,
                    [INK, INK, INK], M=T(q))
        d.tube(C.spline3(rail, 2), 0.014, 8, PEARL, caps='round', cap_segs=1)
    for y in (-0.40, 0.30, 1.00):
        q = sh.top(0.0, y)[0]
        d.tube([Vector((0.56, y, q.z + 0.06)), Vector((-0.56, y, q.z + 0.06))], 0.011, 6, PEARL,
               caps='flat')
    # grille, badge, bumpers, plate, exhaust, wipers
    gp, gn = sh.face(0.0, 0.62, -1)
    Mg = frame(gp, gn, (0, 0, 1))
    V.rr_lathe(d, 0.56, 0.12, 0.04, [(0.010, -0.025), (0.010, 0.004), (0.004, 0.008),
                                      (-0.003, 0.004), (-0.005, -0.010), (-0.006, -0.012)],
               [PEARL, PEARL, PEARL, INK, INK, INK], M=Mg, nc=2)
    for k in range(4):
        tile(d, (0, -0.042 + 0.028 * k, -0.012), 0.53, 0.012, 0.014, PEARL, M=Mg, ch=0.003)
    bp, bn = sh.face(0.0, 0.84, -1)
    lathe_m(d, [(0.026, -0.01), (0.026, 0.004), (0.020, 0.008), (0.0, 0.009)], 12,
            [BRASS, BRASS, BRASS], M=frame(bp, bn))
    bumper(d, sh, -1, 0.42, 0.075, 0.11, PEARL)
    bumper(d, sh, 1, 0.42, 0.075, 0.11, PEARL)
    pp, pn = sh.face(0.0, 0.62, 1)
    V.plate_recess(d, pp, pn, 0.30, 0.10, frame_mat=PEARL)
    ex = Vector((-0.45, 1.82, 0.30))
    lathe_m(d, [(0.026, -0.10), (0.026, 0.06), (0.020, 0.064), (0.020, 0.0)], 10,
            [METAL, METAL, INK], M=frame(ex, (0, 1, -0.05)))
    for (a, b) in ((0.55, -0.02), (-0.05, -0.60)):
        wiper(d, sh, a, b, 1.12)
    temps = [body, d.to_temp(), glass.to_temp(recalc=False)]
    bodyob = C.merge_to_object("Body", temps, pivot=(0, 0, 0), parent=root, sharp_deg=50)
    ws = wheels(root, axle, track, r, 0.21, 5, hub_mat=PEARL)
    C.bake_ao([bodyob] + ws, dist=0.35, samples=40, floor=0.38, ground_z=0.0)
    return root


if __name__ == "__main__":
    for name, fn in (("city_car_a", build_a), ("city_car_b", build_b)):
        root = fn()
        C.summary(root)
        C.export_fbx(root, os.path.join(C.MODELS, 'Vehicles', name + '.fbx'))
        if RENDER:
            C.render_previews(name, root, res=(960, 720), samples=112, ground_z=0.0, lens=50,
                              margin=1.08)
