"""Courier car - single-seat electric courier buggy for SKYFOLD: The Last Flight.

Original procedural model (Awaiz Ahmed / Team Kanban), not AI-generated.
    blender -b --factory-startup -P tools/blender/veh_courier_car.py [-- --no-render]

~3.3 m long x 1.6 m wide x 1.66 m tall. Faces Blender -Y (Unity +Z); car's left = Blender +X.
Hierarchy (pivots):
    courier_car (empty)       ground level, centred between the axles
      Body                    same as root - pods, open cabin, seat, dash, canopy, cargo deck
        SteeringWheel         hub centre; local Unity Z (Blender -Y) runs down the column,
                              tilted 35 deg (spin it about its local Z axis)
        ANCHOR_driver_eye     seated driver eye point (1.15 m)
        ANCHOR_door           left-side boarding interaction point
        SOCKET_cargo          bottom centre of the upright 0.35 m power cell in the cradle
      Wheel_FL/FR/RL/RR       hub centres (r = 0.32 m), spin about local X
      ANCHOR_exit_left/right  1.4 m to each side at ground level
Detail pass: smooth monotone-cubic pod lofts with a raised teal stripe and real panel grooves,
flared fenders with rubber lips and bolts, projector headlights, tail-light clusters, grille,
rubber-stripped bumpers, blank plate recess, charge port, pleated bucket seat, dash with gauge
binnacle / switches / vents / nav display, column stalks, pedals, framed windscreen with wiper
and mirror, side mirrors, padded roll bar, solar roof, cargo deck rails and a brass cradle;
wheels with chevron tread, ridged 5-spoke rims, lug nuts, brake discs and callipers.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C
import veh_common as V
from veh_common import (PEARL, TEAL, TEAL_L, CORAL, LIGHT, INK, RUBBER, BRASS, GLASS, GLOW,
                        METAL, IVORY, frame, rot_x, rot_z, T, sweep, slab, lathe_m, rr_lathe,
                        bolt, tile)
from chars_common import Vector, Matrix, Euler, radians, sin, cos, pi
import bpy

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS
OUT = os.path.join(C.MODELS, 'Vehicles', 'courier_car.fbx')

AXLE_Y = 1.10
TRACK_X = 0.665
WHEEL_R = 0.32
EYE = Vector((0.0, 0.10, 1.15))
HUB = Vector((0.0, -0.27, 0.90))
COLUMN_TILT = 35.0
CARGO = Vector((0.0, 1.12, 0.875))
STRIPE = (0.465, 0.530)
X = Vector((1, 0, 0))
Y = Vector((0, 1, 0))
Z = Vector((0, 0, 1))

# pod keys (z, y_front, y_back, half_width), bottom -> top; samples per key interval
NOSE = [(0.24, -1.45, -0.50, 0.55), (0.30, -1.51, -0.50, 0.575), (0.40, -1.530, -0.50, 0.584),
        (0.62, -1.535, -0.50, 0.585), (0.72, -1.522, -0.50, 0.579), (0.79, -1.47, -0.50, 0.565),
        (0.86, -1.36, -0.50, 0.54), (0.905, -1.19, -0.505, 0.50), (0.935, -0.97, -0.52, 0.42)]
NOSE_STEPS = [1, 1, 1, 1, 1, 1, 2, 2]
REAR = [(0.24, 0.66, 1.52, 0.55), (0.30, 0.64, 1.58, 0.575), (0.40, 0.64, 1.600, 0.584),
        (0.62, 0.64, 1.605, 0.585), (0.72, 0.64, 1.595, 0.58), (0.80, 0.645, 1.56, 0.56),
        (0.845, 0.66, 1.49, 0.52), (0.865, 0.70, 1.40, 0.46)]
REAR_STEPS = [1, 1, 1, 1, 1, 2, 2]


def spline(pts, n=3):
    return C.spline3([Vector(p) for p in pts], n)


def ellipse(w, h, n=12):
    return [(w / 2 * cos(2 * pi * k / n), h / 2 * sin(2 * pi * k / n)) for k in range(n)]


# ---------------------------------------------------------------------------- body: shell
def pods(shell):
    nose = V.Pod(NOSE, n=3.4, step=NOSE_STEPS)
    nose.build(shell, 32, PEARL, ribs=[(STRIPE[0], STRIPE[1], 0.004)],
               bands=[(STRIPE[0], STRIPE[1], TEAL)], grooves=[(0.835, 0.0045, 0.003)],
               crown=0.008, fill=2, cap_bottom=False)
    rear = V.Pod(REAR, n=3.6, step=REAR_STEPS)
    rear.build(shell, 32, PEARL, ribs=[(STRIPE[0], STRIPE[1], 0.004)],
               bands=[(STRIPE[0], STRIPE[1], TEAL)], grooves=[(0.775, 0.0045, 0.003)],
               crown=0.006, fill=2, cap_bottom=False)
    return nose, rear


def chassis(shell, sym):
    # dark tub: underbody and cabin floor (top at z 0.40)
    slab(shell, 1.10, 2.90, 0.17, 0.12, 0.045, INK, M=T(0, 0.05, 0.315), nc=2, ne=1)
    # teal sills along the open cabin (ends buried in the pods)
    sec = V.section_rrect(0.13, 0.15, 0.045, 3)
    sweep(sym, [(0.535, -0.62, 0.47), (0.535, 0.72, 0.47)], sec, TEAL, up=(0, 0, 1), caps=False)
    # rubber step pad on the left (boarding) sill
    slab(shell, 0.085, 0.44, 0.010, 0.02, 0.004, RUBBER, M=T(0.535, 0.08, 0.546), nc=2, ne=1)
    for k in range(6):
        tile(shell, (0.535, -0.10 + k * 0.072, 0.551), 0.07, 0.016, 0.004, RUBBER)
    # ribbed rubber floor mat in the footwell
    slab(shell, 0.62, 0.40, 0.008, 0.04, 0.003, RUBBER, M=T(0, -0.285, 0.401), nc=2, ne=1)
    for k in range(6):
        tile(shell, (0, -0.44 + k * 0.062, 0.405), 0.55, 0.014, 0.004, RUBBER)


def fenders(sym):
    """Flared arches over each (left) wheel: pearl top, ink underside and rubber lip, bolts."""
    sec = [(-0.170, -0.018), (0.112, -0.014), (0.121, -0.044), (0.137, -0.050), (0.148, -0.024),
           (0.146, 0.006), (0.128, 0.022), (0.020, 0.028), (-0.170, 0.014)]
    smats = [INK, INK, RUBBER, PEARL, PEARL, PEARL, PEARL, PEARL, INK]
    R0 = 0.405
    for sy in (-1, 1):
        c = Vector((TRACK_X, sy * AXLE_Y, WHEEL_R))
        n = 12
        angs = [radians(-6 + 192 * k / n) for k in range(n + 1)]
        path = [c + Vector((0, cos(a) * R0, sin(a) * R0)) for a in angs]
        up = (path[0] - c).normalized()
        sc = []
        for k in range(n + 1):
            e = min(k, n - k)
            f = 1.0 if e >= 1 else 0.82
            sc.append((1.0, f))
        sweep(sym, path, sec, PEARL, up=up, scales=sc, sec_mats=smats, cap_mat=PEARL)
        for a in (radians(48), radians(132)):
            rad = Vector((0, cos(a), sin(a)))
            p = c + rad * (R0 + 0.026) + X * 0.103
            bolt(sym, p, rad, 0.012, 0.008, BRASS, segs=6, up=X)


def bumpers(shell, nose, rear):
    sec = V.section_rrect(0.075, 0.12, 0.03, 2)
    strip = [(x - 0.040, y) for (x, y) in V.ccw([(0.010, -0.016), (0.010, 0.016), (0.0, 0.021),
                                                 (-0.010, 0.016), (-0.010, -0.016), (0.0, -0.021)])]
    for (pod, base, zb, sgn) in ((nose, -pi / 2, 0.36, -1), (rear, pi / 2, 0.36, 1)):
        ts = [base - 0.75 + 1.5 * k / 8 for k in range(9)]   # path runs so 'side' faces the car
        pts = [pod.point(t, zb, 0.045) for t in ts]
        a, b = pts[0], pts[-1]
        ea = a + Vector((-math.copysign(0.03, a.x), -sgn * 0.065, 0))
        eb = b + Vector((-math.copysign(0.03, b.x), -sgn * 0.065, 0))
        path = [ea] + pts + [eb]
        scl = [(0.80, 0.78)] + [(1.0, 1.0)] * len(pts) + [(0.80, 0.78)]
        sweep(shell, path, sec, CORAL, up=(0, 0, 1), scales=scl)
        sweep(shell, pts[1:-1], strip, RUBBER, up=(0, 0, 1))
        # mounting brackets to the chassis
        for sx in (-1, 1):
            p = pod.point(base + sx * sgn * -0.32, 0.31, -0.02)
            shell.box(Vector((p.x, p.y + sgn * 0.02, 0.315)), (0.045, 0.13, 0.032), INK)


def front_face(shell, nose):
    # projector headlights
    for sx in (1, -1):
        z = 0.68
        t = nose.t_of_x(sx * 0.31, z, -1)
        p = nose.point(t, z)
        n = (nose.normal(t, z) + Vector((0, -0.7, 0.0))).normalized()
        V.lamp_round(shell, p, n, 0.098, segs=20, depth=0.04)
        # indicators on the front corners
        z2 = 0.585
        t2 = nose.t_of_x(sx * 0.505, z2, -1)
        p2 = nose.point(t2, z2)
        n2 = nose.normal(t2, z2)
        V.lamp_round(shell, p2, n2, 0.026, body=PEARL, bezel=BRASS, gap=INK, lens=LIGHT,
                     segs=10, depth=0.02, proud=0.7, simple=True)
    # grille between the headlights: brass frame, dark recess, pearl slats
    z = 0.672
    t = -pi / 2
    p = nose.point(t, z)
    n = nose.normal(t, z)
    M = frame(p, n, (0, 0, 1))
    prof = [(0.014, -0.03), (0.014, 0.004), (0.009, 0.011), (0.002, 0.012), (-0.004, 0.006),
            (-0.006, -0.012), (-0.008, -0.014)]
    rr_lathe(shell, 0.25, 0.115, 0.035, prof, [PEARL, PEARL, BRASS, BRASS, INK, INK, INK], M=M,
             nc=2)
    for k in range(4):
        yk = -0.041 + k * 0.0273
        tile(shell, (0, yk, -0.014), 0.226, 0.013, 0.018, PEARL, M=M, ch=0.0035)
    # small brass badge with a teal enamel centre (no text)
    zb = 0.775
    pb = nose.point(-pi / 2, zb)
    nb = nose.normal(-pi / 2, zb)
    Mb = frame(pb, nb, (0, 0, 1))
    lathe_m(shell, [(0.026, -0.01), (0.026, 0.004), (0.022, 0.008), (0.016, 0.007),
                    (0.0, 0.010)], 12, [BRASS, BRASS, BRASS, TEAL], M=Mb)


def rear_face(shell, rear):
    for sx in (1, -1):
        z = 0.665
        t = rear.t_of_x(sx * 0.355, z, 1)
        p = rear.point(t, z)
        n = (rear.normal(t, z) + Vector((0, 0.6, 0))).normalized()
        w, h = 0.16, 0.095
        M = V.lamp_rrect(shell, p, n, w, h, 0.03, body=PEARL, bezel=BRASS, lens=CORAL,
                         depth=0.035, nc=2)
        # local +x points to world -X here; reverse lamp toward the centre, lens ribs outside
        ix = sx * 0.047
        slab(shell, 0.034, 0.062, 0.008, 0.010, 0.003, LIGHT, M=M @ T(ix, 0, 0.012), nc=1, ne=1,
             cap_bottom=False)
        for k in range(2):
            yk = -0.016 + 0.032 * k
            tile(shell, (-sx * 0.020, yk, 0.010), 0.072, 0.008, 0.0045, CORAL, M=M, ch=0.002)
    # blank plate recess between the tail lights
    z = 0.668
    p = rear.point(pi / 2, z)
    n = rear.normal(pi / 2, z)
    V.plate_recess(shell, p, n, 0.235, 0.105)
    # charge port on the left rear flank: flush gasket, pearl flap, glowing status dot
    z = 0.755
    t = rear.t_of_y(1.30, z, 1)
    p = rear.point(t, z)
    n = rear.normal(t, z)
    Mp = frame(p, n, (0, 0, 1))
    rr_lathe(shell, 0.09, 0.07, 0.016, [(0.004, -0.02), (0.004, 0.001), (0.0, 0.002)],
             [INK, INK, INK], M=Mp, nc=2)
    slab(shell, 0.084, 0.064, 0.008, 0.014, 0.003, PEARL, M=Mp @ T(0, 0, 0.005), nc=2, ne=1,
         cap_bottom=False)
    lathe_m(shell, [(0.007, -0.004), (0.007, 0.006), (0.0, 0.010)], 10, [GLOW, GLOW],
            M=Mp @ T(-0.062, 0.018, 0))
    # tow loop under the rear bumper
    slab(shell, 0.07, 0.05, 0.03, 0.012, 0.008, INK, M=T(0, 1.635, 0.285), nc=1, ne=1)
    shell.torus(0.026, 0.0075, 12, 5, BRASS, matrix=T(0, 1.672, 0.262) @ V.rot_y(90))


# ---------------------------------------------------------------------------- body: cabin
def seat(shell):
    # base frame on slide rails
    slab(shell, 0.36, 0.34, 0.05, 0.03, 0.012, INK, M=T(0, 0.20, 0.428), nc=2, ne=1)
    for sx in (-1, 1):
        tile(shell, (sx * 0.12, 0.20, 0.401), 0.03, 0.40, 0.006, METAL)
    # cushion: base, side bolsters, three pleats
    slab(shell, 0.50, 0.46, 0.08, 0.06, 0.03, TEAL, M=T(0, 0.17, 0.488), nc=2, ne=2)
    for sx in (-1, 1):
        shell.rbox(Vector((sx * 0.207, 0.165, 0.540)), (0.086, 0.44, 0.068), 0.032, 2, TEAL)
    for k in (-1, 0, 1):
        shell.rbox(Vector((k * 0.105, 0.17, 0.533)), (0.098, 0.40, 0.034), 0.015, 1, TEAL)
    # backrest (leans back 12 deg): board, pearl shell, bolsters, five pleats, top roll
    Mb = T(0, 0.435, 0.80) @ rot_x(-12)
    shell.rbox(Vector((0, 0, 0)), (0.50, 0.10, 0.58), 0.04, 2, TEAL, matrix=Mb)
    shell.rbox(Vector((0, 0.046, 0.005)), (0.52, 0.035, 0.60), 0.016, 1, PEARL, matrix=Mb)
    for sx in (-1, 1):
        shell.rbox(Vector((sx * 0.21, -0.04, -0.02)), (0.09, 0.09, 0.52), 0.04, 1, TEAL,
                   matrix=Mb)
    for k in range(4):
        shell.rbox(Vector((0, -0.058, -0.18 + k * 0.115)), (0.32, 0.03, 0.105), 0.013, 1, TEAL,
                   matrix=Mb)
    shell.rbox(Vector((0, -0.02, 0.272)), (0.40, 0.10, 0.07), 0.032, 2, TEAL, matrix=Mb)
    # headrest on brass posts
    Mh = T(0, 0.505, 1.178) @ rot_x(-12)
    shell.rbox(Vector((0, 0, 0)), (0.26, 0.085, 0.13), 0.038, 2, TEAL, matrix=Mh)
    for sx in (-1, 1):
        a = Mh @ Vector((sx * 0.07, 0.0, -0.05))
        b = Mh @ Vector((sx * 0.07, 0.0, -0.13))
        shell.tube([a, b], 0.0075, 6, BRASS, caps='flat')


def gauge(part, M, R, needle_deg):
    """Round gauge in local frame M (face toward local +Z): brass bezel, dark face, segmented
    glowing arc (no text), coral needle, brass centre cap."""
    segs = 16
    prof = [(1.26 * R, -0.006), (1.18 * R, 0.009), (1.07 * R, 0.010), (0.99 * R, 0.003),
            (0.92 * R, -0.004), (0.74 * R, -0.004), (0.0, -0.004)]
    vr, fs = lathe_m(part, prof, segs, [BRASS, BRASS, BRASS, INK, INK, INK], M=M,
                     phase=-pi / 2)
    band = fs[4 * segs:5 * segs]
    for j, f in enumerate(band):
        ang = (-90 + 360 * (j + 0.5) / segs) % 360        # 0 = +x, 90 = up
        rel = (ang - 90) % 360                             # from 12 o'clock, ccw
        in_arc = not (135 < rel < 225)
        if in_arc and j % 2 == 0:
            part.assign([f], GLOW)
    a = radians(90 + needle_deg)
    d = Vector((cos(a), sin(a), 0))
    s = Vector((-sin(a), cos(a), 0))
    Mn = M @ Matrix(((d.x, s.x, 0, d.x * 0.38 * R), (d.y, s.y, 0, d.y * 0.38 * R),
                     (0, 0, 1, -0.0025), (0, 0, 0, 1)))
    tile(part, (0, 0, 0), 0.80 * R, 0.006, 0.003, CORAL, M=Mn, ch=0.001, sunk=0.0)
    lathe_m(part, [(0.16 * R, -0.003), (0.16 * R, 0.002), (0.0, 0.005)], 8, [BRASS, BRASS],
            M=M)


def dashboard(shell, sym):
    # main dash: swept section along X with rounded ends (teal top pad, pearl fascia)
    sec = [(-0.585, 0.765), (-0.380, 0.745), (-0.345, 0.760), (-0.333, 0.785), (-0.342, 0.860),
           (-0.350, 0.900), (-0.336, 0.915), (-0.322, 0.932), (-0.330, 0.950), (-0.380, 0.960),
           (-0.480, 0.960), (-0.560, 0.952), (-0.592, 0.925), (-0.600, 0.850)]
    sec = [(y, z) for (y, z) in sec]
    smats = [INK, INK, PEARL, PEARL, PEARL, TEAL, TEAL, TEAL, TEAL, TEAL, TEAL, TEAL, PEARL, PEARL]
    xs = [-0.50, -0.490, -0.465, 0.0, 0.465, 0.490, 0.50]
    scl = [(0.80, 0.86), (0.94, 0.96), (1.0, 1.0), (1.0, 1.0), (1.0, 1.0), (0.94, 0.96),
           (0.80, 0.86)]
    # section is given in absolute (y, z); sweep along +X: side = +Y, up = +Z
    cy, cz = -0.46, 0.855
    loc = [(y - cy, z - cz) for (y, z) in sec]
    sweep(shell, [(x, cy, cz) for x in xs], loc, PEARL, up=(0, 0, 1), scales=scl,
          sec_mats=smats, cap_mat=PEARL)
    # gauge binnacle on top, facing the driver (seen through the wheel's upper opening)
    bc = Vector((0, -0.405, 0.992))
    bn = (EYE - bc)
    bn.z *= 0.6
    bn.normalize()
    Mb = frame(bc, bn, (0, 0, 1))
    slab(shell, 0.255, 0.090, 0.070, 0.035, 0.022, TEAL, M=Mb, nc=3, ne=2)
    for sx, nd in ((1, -55), (-1, 35)):
        gauge(shell, Mb @ T(sx * 0.058, -0.006, 0.036), 0.035, nd)
    # fascia frame helper: fascia face ~ (y -0.342, z 0.84), normal toward the driver
    fn = Vector((0, 0.989, 0.146))

    def fascia(x, z, off=0.0):
        y = -0.333 - (z - 0.785) * (0.017 / 0.115)
        return Vector((x, y, z)) + fn * off
    # switch panel (left of the column): ink plate, four brass toggles, two push buttons
    Ms = frame(fascia(0.27, 0.845, 0.002), fn, (0, 0, 1))
    slab(shell, 0.20, 0.072, 0.010, 0.014, 0.004, INK, M=Ms, nc=2, ne=1)
    for k in range(4):
        x = -0.075 + k * 0.034
        bolt(shell, Ms @ Vector((x, -0.010, 0.004)), fn, 0.0075, 0.005, METAL, segs=6)
        lv = Ms @ Vector((x, -0.010, 0.008))
        tip = Ms @ Vector((x, 0.006, 0.026))
        shell.tube([lv, tip], 0.0028, 5, BRASS, caps='round', cap_segs=1)
    for k, m in enumerate((CORAL, TEAL_L)):
        lathe_m(shell, [(0.010, -0.002), (0.010, 0.006), (0.006, 0.010), (0.0, 0.011)], 10,
                [INK, m, m], M=Ms @ T(0.062, -0.016 + k * 0.032, 0.004))
    # nav display (right of the column): dark screen, glowing route line + destination dot
    Mn = frame(fascia(-0.27, 0.845, 0.002), fn, (0, 0, 1))
    g = slab(shell, 0.19, 0.082, 0.012, 0.014, 0.005, INK, M=Mn, nc=2, ne=1)
    shell.assign(g['top'][-12:], TEAL)
    route = [(-0.070, -0.020), (-0.035, -0.020), (-0.020, 0.012), (0.025, 0.012), (0.040, -0.008),
             (0.062, -0.008)]
    for (a, b) in zip(route, route[1:]):
        a, b = Vector((a[0], a[1], 0)), Vector((b[0], b[1], 0))
        d = b - a
        L = d.length
        d.normalize()
        s = Vector((-d.y, d.x, 0))
        mid = (a + b) / 2
        Mr = Mn @ Matrix(((d.x, s.x, 0, mid.x), (d.y, s.y, 0, mid.y), (0, 0, 1, 0.0060),
                          (0, 0, 0, 1)))
        tile(shell, (0, 0, 0), L + 0.004, 0.0045, 0.0015, GLOW, M=Mr, ch=0.0005, sunk=0.0)
    lathe_m(shell, [(0.0065, 0.0055), (0.0065, 0.0075), (0.0, 0.009)], 10, [GLOW, GLOW],
            M=Mn @ T(0.062, -0.008, 0))
    # round eyeball vents at both ends
    for sx in (1, -1):
        Mv = frame(fascia(sx * 0.425, 0.845, 0.0), fn, (0, 0, 1))
        lathe_m(shell, [(0.040, -0.01), (0.040, 0.004), (0.036, 0.009), (0.030, 0.008),
                        (0.027, -0.002), (0.0, -0.002)], 10, [PEARL, BRASS, BRASS, INK, INK],
                M=Mv)
        for k in range(3):
            tile(shell, (0, -0.014 + k * 0.014, -0.002), 0.048, 0.004, 0.006, PEARL, M=Mv,
                 ch=0.001, sunk=0.0)
    # steering column shroud (static) with indicator / wiper stalks
    d = Vector((0, cos(radians(COLUMN_TILT)), sin(radians(COLUMN_TILT))))
    Mc = frame(HUB, d, (0, 0, 1))
    lathe_m(shell, [(0.036, -0.23), (0.036, -0.105), (0.032, -0.068), (0.025, -0.052),
                    (0.0, -0.050)], 12, [INK, INK, INK, INK], M=Mc)
    for sx in (1, -1):
        a = HUB - d * 0.082 + X * (sx * 0.028)
        b = HUB - d * 0.092 + X * (sx * 0.112) - Z * 0.018
        shell.tube([a, b], 0.0065, 6, INK, caps='flat')
        shell.tube([b, b + (b - a).normalized() * 0.022], 0.0095, 6,
                   BRASS if sx > 0 else PEARL, caps='round', cap_segs=1)


def pedals(shell):
    # brake (hanging) and accelerator (floor hinged): metal pads with rubber grip ribs
    for (x, top, pad_c, pad_n, w, h) in ((0.075, (0.075, -0.45, 0.745), (0.075, -0.405, 0.525),
                                          (0, 0.80, 0.60), 0.075, 0.055),
                                         (-0.11, None, (-0.11, -0.44, 0.49), (0, 0.88, 0.47),
                                          0.058, 0.15)):
        c = Vector(pad_c)
        n = Vector(pad_n).normalized()
        M = frame(c, n, (0, 0, 1))
        slab(shell, w, h, 0.010, 0.010, 0.003, METAL, M=M, nc=1, ne=1)
        k = 3 if h < 0.1 else 5
        for i in range(k):
            yy = -h / 2 + 0.012 + (h - 0.024) * (i + 0.5) / k
            tile(shell, (0, yy, 0.004), w - 0.014, 0.006, 0.004, RUBBER, M=M, ch=0.001)
        if top:
            arm = [Vector(top), (Vector(top) + c) / 2 + Vector((0, -0.03, 0)), c - n * 0.004]
            shell.tube(spline(arm, 2), 0.0075, 6, METAL, caps='flat')
        else:
            shell.tube([c - (M.to_3x3() @ Y) * (h / 2 - 0.004) - n * 0.006,
                        c - (M.to_3x3() @ Y) * (h / 2 + 0.02) - n * 0.02], 0.010, 8, INK,
                       caps='round', cap_segs=1)
    # dead pedal / footrest on the left
    M = frame(Vector((0.225, -0.435, 0.47)), Vector((0, 0.88, 0.47)), (0, 0, 1))
    slab(shell, 0.085, 0.15, 0.010, 0.012, 0.003, RUBBER, M=M, nc=1, ne=1)


def windscreen(shell, sym):
    def ws(x, zr, lz=0.0):
        z = 1.088 + zr
        return Vector((x, -0.585 - lz - 0.07 * (x / 0.46) ** 2 + 0.30 * (z - 0.938), z))

    def deform(v):
        # v is in local (x, zr, lz) packing: x, y = zr, z = lz
        return ws(v.x, v.y, v.z)
    outline = V.rrect_dense(0.92, 0.30, 0.05, 3, max_seg=0.12)
    V.pane(shell, outline, 0.012, GLASS, deform=deform, scales=(1.0, 0.5))
    # frame tube around the glass edge
    frame_pts = [ws(x, y) for (x, y) in V.rrect_dense(0.928, 0.308, 0.054, 3, max_seg=0.12)]
    sweep(shell, frame_pts, V.circle2(0.0125, 6), INK, closed=True)
    # mounting brackets at the bottom corners
    for sx in (-1, 1):
        p = ws(sx * 0.40, -0.152)
        shell.box(Vector((p.x, p.y + 0.015, p.z - 0.008)), (0.05, 0.035, 0.025), INK)
    # wiper parked along the bottom edge (outside face): pivot, arm, rubber blade
    piv = ws(0.27, -0.155, 0.018)
    lathe_m(shell, [(0.014, -0.01), (0.014, 0.008), (0.009, 0.014), (0.0, 0.016)], 8,
            [INK, INK, INK], M=frame(piv, (0, -0.3, 1), (0, 1, 0)))
    arm = [ws(0.27, -0.140, 0.024), ws(0.05, -0.128, 0.020), ws(-0.20, -0.122, 0.017)]
    sweep(shell, spline(arm, 2), V.section_rrect(0.010, 0.007, 0.002, 1), INK, up=(0, -1, 0.3))
    blade = [ws(0.15, -0.118, 0.011), ws(-0.24, -0.112, 0.010)]
    sweep(shell, spline(blade, 3), V.section_rrect(0.006, 0.012, 0.002, 1), RUBBER,
          up=(0, -1, 0.3))
    # rear-view mirror on the frame top centre
    top = ws(0.0, 0.154, -0.004)
    mp = Vector((0, top.y + 0.040, 1.198))
    shell.tube([top + Vector((0, 0.004, -0.004)), mp + Vector((0, -0.006, 0.012))], 0.0065, 6, INK,
               caps='flat')
    Mm = frame(mp, (0, 1, -0.18), (0, 0, 1))
    g = slab(shell, 0.17, 0.048, 0.026, 0.020, 0.008, INK, M=Mm, nc=2, ne=2)
    shell.assign(g['top'][-12:], METAL)


def canopy(shell, sym):
    a_path = spline([(0.505, -0.56, 0.86), (0.49, -0.47, 1.25), (0.47, -0.40, 1.578)], 3)
    r_path = spline([(0.50, 0.70, 0.84), (0.485, 0.62, 1.25), (0.47, 0.56, 1.578)], 3)
    sec = ellipse(0.042, 0.054, 8)
    for path in (a_path, r_path):
        sweep(sym, path, sec, INK, up=(0, -1, 0), caps=False)
    # brass collars where the pillars leave the pods
    for (path, zc) in ((a_path, 0.918),):
        k = min(range(len(path) - 1), key=lambda i: abs(path[i].z - zc))
        p0, p1 = path[k], path[k + 1]
        f = (zc - p0.z) / (p1.z - p0.z)
        p = p0 + (p1 - p0) * f
        sym.torus(0.029, 0.0060, 10, 4, BRASS, matrix=frame(p, (p1 - p0).normalized(), (0, -1, 0)))
    # grab handle on the left A-pillar (boarding side)
    h0 = Vector((0.452, -0.478, 1.05))
    h1 = Vector((0.441, -0.418, 1.33))
    shell.tube(spline([h0, (h0 + h1) / 2 + Vector((-0.012, 0.004, 0)), h1], 2), 0.010, 6, BRASS,
               caps='round', cap_segs=1)
    for (h, z) in ((h0, 1.05), (h1, 1.33)):
        pz = (z - 0.86) / (1.578 - 0.86)
        pil = Vector((0.505 + (0.47 - 0.505) * pz, -0.56 + (-0.40 + 0.56) * pz, z))
        shell.tube([h, pil], 0.0075, 6, BRASS, caps='flat')
    # side mirrors on stalks from the A-pillars, mirror glass facing the driver
    st0 = Vector((0.497, -0.515, 1.03))
    hc = Vector((0.660, -0.585, 1.045))
    sweep(sym, spline([st0, Vector((0.585, -0.56, 1.02)), hc + Vector((-0.04, 0.005, -0.006))],
                      2), V.circle2(0.011, 6), INK, up=(0, 0, 1))
    Mm = frame(hc, (0.12, 1, 0), (0, 0, 1))
    g = slab(sym, 0.135, 0.090, 0.050, 0.038, 0.020, PEARL, M=Mm, nc=2, ne=2, bottom=TEAL)
    sym.assign(g['top'][-12:], METAL)
    # padded roll bar behind the headrest
    rb_l = Vector((0.483, 0.622, 1.25))
    shell.tube([rb_l, Vector((-0.483, 0.622, 1.25))], 0.021, 12, INK, caps='flat')
    shell.tube([Vector((0.30, 0.622, 1.25)), Vector((-0.30, 0.622, 1.25))], 0.040, 12, RUBBER,
               caps='round', cap_segs=2)
    for x in (-0.20, 0.0, 0.20):
        shell.torus(0.0410, 0.0042, 12, 3, INK, matrix=T(x, 0.622, 1.25) @ V.rot_y(90))
    # roof: rounded slab, teal edge band and underside, solar panel inset on top
    roof = V.Pod([(1.556, -0.430, 0.590, 0.515), (1.566, -0.470, 0.630, 0.553),
                  (1.584, -0.484, 0.644, 0.566), (1.610, -0.481, 0.641, 0.563),
                  (1.628, -0.465, 0.625, 0.548), (1.640, -0.440, 0.600, 0.523)], n=3.0,
                 step=[1, 1, 1, 1, 1])
    roof.build(shell, 32, PEARL, bands=[(1.50, 1.617, TEAL)], crown=0.008, fill=2,
               bottom_mat=TEAL)
    slab(shell, 0.80, 0.84, 0.016, 0.06, 0.004, INK, M=T(0, 0.08, 1.6495), nc=2, ne=1,
         cap_bottom=False)
    for i in range(4):
        for j in range(5):
            x = -0.279 + i * 0.186
            y = 0.08 - 0.328 + j * 0.164
            tile(shell, (x, y, 1.6575), 0.172, 0.150, 0.003, TEAL, ch=0.002, sunk=0.001)
    # interior dome light above the driver
    slab(shell, 0.15, 0.065, 0.014, 0.022, 0.005, LIGHT, M=T(0, 0.06, 1.553), nc=1, ne=1)
    slab(shell, 0.17, 0.085, 0.010, 0.030, 0.004, PEARL, M=T(0, 0.06, 1.557), nc=1, ne=1)


def cargo_deck(shell, sym):
    # tie-down rails on short posts along both deck edges
    for sx in (1,):
        x = sx * 0.39
        for y in (0.78, 1.06, 1.34):
            lathe_m(sym, [(0.016, 0.855), (0.016, 0.868), (0.010, 0.874), (0.010, 0.900)], 8,
                    [BRASS, BRASS, INK], M=T(x, y, 0))
        sym.tube([Vector((x, 0.76, 0.905)), Vector((x, 1.36, 0.905))], 0.011, 8, BRASS,
                 caps='round', cap_segs=2)
        for xs in (0.17, 0.235, 0.30):
            tile(sym, (xs, 1.06, 0.8668), 0.022, 0.56, 0.0042, RUBBER, sunk=0.003)
    # cradle for the power cell (SOCKET_cargo = bottom centre of the cell)
    c = CARGO
    lathe_m(shell, [(0.138, -0.024), (0.138, -0.010), (0.131, -0.002), (0.118, 0.0),
                    (0.036, 0.0), (0.0, 0.0)], 16, [INK, INK, INK, INK, BRASS],
            M=T(c.x, c.y, c.z))
    shell.torus(0.098, 0.0055, 24, 4, GLOW, matrix=T(c.x, c.y, c.z + 0.002))
    for k in range(4):
        a = radians(45 + 90 * k)
        rad = Vector((cos(a), sin(a), 0))
        p0 = c + rad * 0.106 + Vector((0, 0, -0.008))
        shell.tube([p0, p0 + Vector((0, 0, 0.205))], 0.0105, 8, BRASS, caps='flat')
        Mp = frame(c + rad * 0.096 + Vector((0, 0, 0.11)), -rad, (0, 0, 1))
        tile(shell, (0, 0, 0), 0.030, 0.060, 0.010, RUBBER, M=Mp, ch=0.003)
        b = radians(90 * k)
        bolt(shell, c + Vector((cos(b) * 0.113, sin(b) * 0.113, 0.0)), (0, 0, 1), 0.0068, 0.005,
             BRASS, segs=6, up=(cos(b), sin(b), 0))
    shell.torus(0.106, 0.0115, 24, 6, BRASS, matrix=T(c.x, c.y, c.z + 0.200))


def build_body(root):
    shell = C.Part()     # smooth / pre-rounded parts (no bevel modifier)
    sym = C.Part()       # left-side parts, mirrored to the right
    nose, rear = pods(shell)
    chassis(shell, sym)
    fenders(sym)
    bumpers(shell, nose, rear)
    front_face(shell, nose)
    rear_face(shell, rear)
    seat(shell)
    dashboard(shell, sym)
    pedals(shell)
    windscreen(shell, sym)
    canopy(shell, sym)
    cargo_deck(shell, sym)
    V.add_mirror_x(sym)
    temps = [shell.to_temp(), sym.to_temp()]
    return C.merge_to_object("Body", temps, pivot=(0, 0, 0), parent=root, sharp_deg=50)


# ---------------------------------------------------------------------------- steering wheel
def build_steering(body):
    """Rim in the local XZ plane (axis = local Y, toward the driver): oval-section ink rim with
    thumb grips at 9 and 3 o'clock and a coral 12 o'clock band, three ridged pearl spokes,
    dished pearl hub pad with a brass/teal emblem, inner column shaft."""
    p = C.Part()
    W = T(HUB) @ rot_x(COLUMN_TILT)
    bm = p.bm
    Rm, r0 = 0.165, 0.0195
    nu, nv = 32, 8
    rings = []
    for i in range(nu):
        ph = 2 * pi * i / nu                       # 0 = +x (driver's right... local +x)
        grip = 0.0
        for c in (0.0, pi):
            d = math.atan2(sin(ph - c), cos(ph - c))
            grip += 0.20 * math.exp(-(d / 0.26) ** 2)
        r = r0 * (1 + grip)
        rad = Vector((cos(ph), 0, sin(ph)))
        ring = []
        for j in range(nv):
            th = 2 * pi * j / nv
            v = rad * (Rm + r * cos(th)) + Vector((0, 1, 0)) * (r * 1.18 * sin(th))
            ring.append(W @ v)
        rings.append(ring)
    vr = [[bm.verts.new(q) for q in ring] for ring in rings]
    fs = []
    for i in range(nu):
        a, b = vr[i], vr[(i + 1) % nu]
        for j in range(nv):
            j2 = (j + 1) % nv
            fs.append(bm.faces.new((a[j], a[j2], b[j2], b[j])))
    p.assign(fs, INK)
    for i in range(nu):
        ph = 2 * pi * (i + 0.5) / nu
        if abs(math.atan2(sin(ph - pi / 2), cos(ph - pi / 2))) < 0.17:
            p.assign(fs[i * nv:(i + 1) * nv], CORAL)
    # spokes: 9, 3 and 6 o'clock, dished toward the column
    sw, sd = 0.044 / 2, 0.016 / 2
    sec = [(sw, -sd), (sw, sd * 0.4), (0.0, sd), (-sw, sd * 0.4), (-sw, -sd), (0.0, -sd * 1.1)]
    for ang in (0.0, 180.0, 270.0):
        a = radians(ang)
        rad = Vector((cos(a), 0, sin(a)))
        path = [W @ (rad * 0.040 + Vector((0, -0.018, 0))), W @ (rad * 0.095 + Vector((0, -0.010, 0))),
                W @ (rad * 0.152)]
        sweep(p, path, sec, PEARL, up=W.to_3x3() @ Vector((0, 1, 0)),
              scales=[(1.15, 1.0), (1.0, 1.0), (0.80, 0.9)])
    # hub pad + emblem facing the driver (local +Y)
    Mh = W @ rot_x(-90)
    lathe_m(p, [(0.0, -0.040), (0.056, -0.040), (0.056, -0.012), (0.052, 0.000), (0.042, 0.007),
                (0.022, 0.009), (0.019, 0.011), (0.0, 0.015)], 20,
            [INK, PEARL, PEARL, PEARL, PEARL, BRASS, BRASS], M=Mh @ T(0, 0, -0.012))
    lathe_m(p, [(0.0115, 0.0), (0.0115, 0.002), (0.0, 0.006)], 12, [TEAL, TEAL],
            M=Mh @ T(0, 0, 0.0025))
    # column shaft into the dash (inside the static shroud)
    p.cylinder(0.021, 0.20, 12, INK, matrix=W @ rot_x(90) @ T(0, 0, 0.045), caps=False)
    temp = p.to_temp()
    return C.merge_to_object("SteeringWheel", [temp], pivot=HUB,
                             rot=Euler((radians(COLUMN_TILT), 0, 0)), parent=body, sharp_deg=45)


# ---------------------------------------------------------------------------- wheels
def build_wheels(root):
    out = []
    for name, sx, sy in (("Wheel_FL", 1, -1), ("Wheel_FR", -1, -1), ("Wheel_RL", 1, 1),
                         ("Wheel_RR", -1, 1)):
        p = V.wheel_hq(WHEEL_R, 0.26, sx, seg=32, rim_r=0.62, lugs=14, lug_h=0.010)
        c = Vector((sx * TRACK_X, sy * AXLE_Y, WHEEL_R))
        p.transform(p.bm.verts, Matrix.Translation(c))
        out.append(C.merge_to_object(name, [p.to_temp()], pivot=c, parent=root, sharp_deg=40))
    return out


def build():
    C.reset_scene()
    root = C.new_empty("courier_car", None, (0, 0, 0), size=0.5)
    body = build_body(root)
    sw = build_steering(body)
    wheels = build_wheels(root)
    C.new_empty("ANCHOR_driver_eye", body, EYE, size=0.15)
    C.new_empty("ANCHOR_door", body, (0.64, 0.05, 0.90), size=0.15)
    C.new_empty("SOCKET_cargo", body, CARGO, size=0.15)
    C.new_empty("ANCHOR_exit_left", root, (1.40, 0.10, 0.0), size=0.2)
    C.new_empty("ANCHOR_exit_right", root, (-1.40, 0.10, 0.0), size=0.2)
    C.bake_ao([body, sw] + wheels, dist=0.30, samples=48, floor=0.38, ground_z=0.0)
    return root


if __name__ == "__main__":
    root = build()
    C.summary(root)
    C.export_fbx(root, OUT)
    if RENDER:
        C.render_previews("courier_car", root, res=(960, 720), samples=128, ground_z=0.0,
                          lens=50, margin=1.08)
