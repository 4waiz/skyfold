"""Courier car - single-seat electric courier buggy for SKYFOLD: The Last Flight.

Original procedural model (Awaiz Ahmed / Team Kanban), not AI-generated.
    blender -b --factory-startup -P tools/blender/veh_courier_car.py [-- --no-render]

~3.3 m long x 1.6 m wide x 1.65 m tall. Faces Blender -Y (Unity +Z); car's left = Blender +X.
Hierarchy (pivots):
    courier_car (empty)       ground level, centred between the axles
      Body                    same as root - pod body, open cabin, seat, dash, canopy, cradle
        SteeringWheel         hub centre; local Unity Z (Blender -Y) runs down the column,
                              tilted 35 deg (spin it about its local Z axis)
        ANCHOR_driver_eye     seated driver eye point (1.15 m)
        ANCHOR_door           left-side boarding interaction point
        SOCKET_cargo          bottom centre of the upright 0.35 m power cell in the cradle
      Wheel_FL/FR/RL/RR       hub centres (r = 0.32 m), spin about local X
      ANCHOR_exit_left/right  1.4 m to each side at ground level
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C
from chars_common import Vector, Matrix, Euler, radians, sin, cos, pi
import bpy

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS
OUT = os.path.join(C.MODELS, 'Vehicles', 'courier_car.fbx')

PEARL, TEAL, CORAL, LIGHT, INK, RUBBER, BRASS, GLASS, GLOW = (
    'SKY_Pearl', 'SKY_Teal', 'SKY_Coral', 'SKY_Light', 'SKY_Ink', 'SKY_Rubber', 'SKY_Brass',
    'SKY_Glass', 'SKY_TealGlow')

AXLE_Y = 1.10
TRACK_X = 0.665
WHEEL_R = 0.32
STRIPE = (0.50, 0.57)
EYE = Vector((0.0, 0.10, 1.15))
HUB = Vector((0.0, -0.27, 0.90))
COLUMN_TILT = 35.0
CARGO = Vector((0.0, 1.12, 0.875))


def rounded_rect(w, h, r, n=3):
    pts = []
    for (cx, cy, a0) in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                         (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(n + 1):
            a = radians(a0 + 90 * k / n)
            pts.append((cx + r * cos(a), cy + r * sin(a)))
    return pts


def lamp(part, center, normal, r, lens_mat, bezel=BRASS, depth=0.05, segs=16):
    """Round lamp: bezel ring + dark gap + slightly domed emissive lens, facing `normal`."""
    n = Vector(normal).normalized()
    M = Matrix.Translation(center) @ n.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    prof = [(0.0, depth * 0.55), (r * 0.55, depth * 0.50), (r * 0.86, depth * 0.38),
            (r * 0.88, depth * 0.30), (r * 1.0, depth * 0.42), (r * 1.18, depth * 0.30),
            (r * 1.20, -depth), (0.0, -depth)]
    vr, fs = part.lathe(prof, segs, lens_mat, matrix=M)
    # bands: 0,1 lens | 2 dark gap | 3,4 bezel ; then front pole (lens) + back pole
    part.assign(fs[2 * segs:3 * segs], INK)
    part.assign(fs[3 * segs:5 * segs], bezel)
    nb = len(prof) - 3
    part.assign(fs[(nb + 1) * segs:(nb + 2) * segs], INK)
    return fs


# ---------------------------------------------------------------------------- body
def build_body(root):
    shell = C.Part()     # smooth pods, tubes and pre-rounded boxes (no bevel modifier)
    plates = C.Part()    # flat-faced parts that get a small bevel
    nu = 20
    # nose pod: rounded friendly front with a sloping bonnet
    nose = [(0.24, -1.50, -0.50, 0.55), (0.30, -1.56, -0.50, 0.575), (STRIPE[0], -1.585, -0.50, 0.585),
            (STRIPE[1], -1.585, -0.50, 0.585), (0.70, -1.575, -0.50, 0.58), (0.79, -1.52, -0.50, 0.565),
            (0.86, -1.40, -0.50, 0.54), (0.905, -1.22, -0.505, 0.50), (0.935, -0.98, -0.52, 0.42)]
    C.loft_z(shell, nose, nu, PEARL, n=3.4, band_mats={2: TEAL})
    # rear pod with a flat deck for the cargo cradle
    rear = [(0.24, 0.66, 1.58, 0.55), (0.30, 0.64, 1.64, 0.575), (STRIPE[0], 0.64, 1.665, 0.585),
            (STRIPE[1], 0.64, 1.665, 0.585), (0.72, 0.64, 1.655, 0.58), (0.80, 0.645, 1.62, 0.56),
            (0.845, 0.66, 1.55, 0.52), (0.865, 0.70, 1.46, 0.46)]
    C.loft_z(shell, rear, nu, PEARL, n=3.6, band_mats={2: TEAL})
    # chassis tub (dark underbody + cabin floor)
    shell.rbox(Vector((0, 0.06, 0.315)), (1.10, 3.0, 0.17), 0.07, 2, INK)
    # teal sills along the open cabin (the stripe continues between the pods)
    for sx in (1, -1):
        shell.tube([Vector((sx * 0.535, -0.62, 0.468)), Vector((sx * 0.545, 0.05, 0.47)),
                    Vector((sx * 0.535, 0.72, 0.468))], 0.072, 10, TEAL, caps='flat')
    # fenders: flying arches over each wheel (pearl), flattened section
    for sy in (-1, 1):
        for sx in (1, -1):
            c = Vector((sx * TRACK_X, sy * AXLE_Y, WHEEL_R))
            path = []
            for k in range(7):
                a = radians(-18 + 216 * k / 6)          # from rear-low over the top to front-low
                path.append(c + Vector((0, cos(a) * 0.408, sin(a) * 0.408)))
            up = (path[0] - c).normalized()
            shell.tube(C.spline3(path, 2), 0.152, 8, PEARL, caps='round', cap_segs=1,
                       scale_xy=(1.0, 0.21), up=up)
    # bumpers (coral) wrapping the nose and the tail
    fb = [Vector((0.47, -1.30, 0.355)), Vector((0.56, -1.47, 0.36)), Vector((0.36, -1.625, 0.36)),
          Vector((-0.36, -1.625, 0.36)), Vector((-0.56, -1.47, 0.36)), Vector((-0.47, -1.30, 0.355))]
    shell.tube(C.spline3(fb, 2), 0.075, 10, CORAL, caps='round', cap_segs=2, scale_xy=(1.0, 1.15))
    rb = [Vector((0.47, 1.40, 0.355)), Vector((0.56, 1.56, 0.36)), Vector((0.36, 1.70, 0.36)),
          Vector((-0.36, 1.70, 0.36)), Vector((-0.56, 1.56, 0.36)), Vector((-0.47, 1.40, 0.355))]
    shell.tube(C.spline3(rb, 2), 0.075, 10, CORAL, caps='round', cap_segs=2, scale_xy=(1.0, 1.15))
    # big round headlights + small coral tail lights
    for sx in (1, -1):
        lamp(shell, Vector((sx * 0.31, -1.585, 0.675)), (sx * 0.22, -1, 0.05), 0.112, LIGHT,
             depth=0.045, segs=16)
        lamp(shell, Vector((sx * 0.37, 1.668, 0.68)), (sx * 0.15, 1, 0.0), 0.058, CORAL,
             bezel=PEARL, depth=0.03, segs=10)
    # seat: teal cushions on an ink pedestal
    shell.rbox(Vector((0, 0.20, 0.405)), (0.34, 0.34, 0.07), 0.02, 1, INK)
    shell.rbox(Vector((0, 0.17, 0.485)), (0.52, 0.48, 0.10), 0.045, 2, TEAL)
    back = Matrix.Translation((0, 0.43, 0.80)) @ Matrix.Rotation(radians(-12), 4, 'X')
    shell.rbox(Vector((0, 0, 0)), (0.52, 0.11, 0.60), 0.05, 2, TEAL, matrix=back)
    shell.rbox(Vector((0, 0.50, 1.17)), (0.30, 0.10, 0.15), 0.04, 2, TEAL)
    plates.box(Vector((0, 0.47, 1.06)), (0.06, 0.04, 0.12), INK)
    # dashboard with a dark display and a glowing teal readout
    shell.rbox(Vector((0, -0.44, 0.845)), (1.02, 0.20, 0.20), 0.06, 2, PEARL)
    disp = rounded_rect(0.42, 0.10, 0.03, 2)
    Md = Matrix.Translation((0, -0.336, 0.84)) @ Matrix.Rotation(radians(90), 4, 'X') @ \
        Matrix.Rotation(radians(180), 4, 'Y')
    plates.prism(disp, 0.012, INK, matrix=Md)
    plates.box(Vector((0.08, -0.331, 0.855)), (0.16, 0.006, 0.022), GLOW)
    # small curved windscreen on the dash (thin glass slab, leaning back)
    scr = rounded_rect(0.92, 0.30, 0.05, 2)
    dense = []
    for (x0, y0), (x1, y1) in zip(scr, scr[1:] + scr[:1]):
        for k in range(2):
            t = k / 2
            dense.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    Mw = Matrix.Translation((0, -0.585, 1.088)) @ Matrix.Rotation(radians(90), 4, 'X')
    vs, fs = plates.prism(dense, 0.012, GLASS, matrix=Mw)
    plates.deform(vs, lambda v: v + Vector((0, -0.07 * (v.x / 0.46) ** 2 + 0.30 * (v.z - 0.938), 0)))
    # canopy frame (ink): A-pillars, rear hoop, roof ring
    frame = [Vector((0.505, -0.56, 0.88)), Vector((0.49, -0.47, 1.25)), Vector((0.47, -0.40, 1.565))]
    for sx in (1, -1):
        shell.tube([Vector((sx * p.x, p.y, p.z)) for p in C.spline3(frame, 2)], 0.032, 8, INK,
                   caps='flat')
        shell.tube([Vector((sx * 0.50, 0.70, 0.84)), Vector((sx * 0.485, 0.62, 1.25)),
                    Vector((sx * 0.47, 0.56, 1.565))], 0.032, 8, INK, caps='flat')
    ring = [Vector((x, y + 0.08, 1.565)) for (x, y) in rounded_rect(0.94, 0.96, 0.16, 2)]
    shell.tube(ring, 0.03, 6, INK, closed=True)
    # canopy roof: soft rounded slab, teal underside + teal edge band, pearl top
    roof = [(1.566, -0.45, 0.61, 0.53), (1.578, -0.48, 0.64, 0.56), (1.612, -0.48, 0.64, 0.56),
            (1.636, -0.45, 0.61, 0.53), (1.650, -0.36, 0.52, 0.44)]
    fs = C.loft_z(shell, roof, nu, PEARL, n=3.0, band_mats={0: TEAL, 1: TEAL})
    shell.assign(fs[4 * nu:5 * nu], TEAL)          # underside fan
    # open cargo cradle on the rear deck: dark base, glowing ring, brass posts + top ring
    shell.lathe([(0.0, 0.0), (0.115, 0.0), (0.122, 0.012), (0.115, 0.024), (0.0, 0.024)], 12, INK,
                matrix=Matrix.Translation(CARGO - Vector((0, 0, 0.024))))
    shell.torus(0.096, 0.007, 12, 3, GLOW, matrix=Matrix.Translation(CARGO + Vector((0, 0, 0.002))))
    for k in range(4):
        a = radians(45 + 90 * k)
        p0 = CARGO + Vector((cos(a) * 0.105, sin(a) * 0.105, -0.01))
        shell.tube([p0, p0 + Vector((0, 0, 0.215))], 0.012, 5, BRASS, caps='flat')
    shell.torus(0.105, 0.012, 16, 4, BRASS, matrix=Matrix.Translation(CARGO + Vector((0, 0, 0.205))))
    temps = [shell.to_temp(), plates.to_temp(bevel=(0.006, 1, 40))]
    body = C.merge_to_object("Body", temps, pivot=(0, 0, 0), parent=root, sharp_deg=56)
    return body


def build_steering(body):
    p = C.Part()
    W = Matrix.Translation(HUB) @ Matrix.Rotation(radians(COLUMN_TILT), 4, 'X')
    # rim in the local XZ plane (axis = local Y), coral marker at 12 o'clock
    vr, fs = p.torus(0.165, 0.021, 22, 6, INK, matrix=W @ Matrix.Rotation(radians(90), 4, 'X'))
    top = [f for f in fs if (W.inverted() @ f.calc_center_median()).z > 0.150]
    p.assign(top, CORAL)
    # spokes (pearl): left, right, down
    for a in (0, 180, 270):
        d = Vector((cos(radians(a)), 0, sin(radians(a))))
        p.tube([W @ (d * 0.03), W @ (d * 0.155)], 0.014, 6, PEARL, caps='flat',
               scale_xy=(1.0, 0.6), up=W.to_3x3() @ Vector((0, 1, 0)))
    # hub + brass cap facing the driver, short column into the dash
    p.lathe([(0.0, -0.02), (0.045, -0.02), (0.048, 0.015), (0.040, 0.028), (0.0, 0.031)], 12,
            PEARL, matrix=W @ Matrix.Rotation(radians(-90), 4, 'X'))
    p.lathe([(0.0, 0.027), (0.030, 0.027), (0.026, 0.036), (0.0, 0.038)], 12, BRASS,
            matrix=W @ Matrix.Rotation(radians(-90), 4, 'X'))
    p.cylinder(0.024, 0.20, 8, INK, matrix=W @ Matrix.Rotation(radians(90), 4, 'X') @
               Matrix.Translation((0, 0, 0.01)), caps=False)
    temp = p.to_temp()
    return C.merge_to_object("SteeringWheel", [temp], pivot=HUB,
                             rot=Euler((radians(COLUMN_TILT), 0, 0)), parent=body, sharp_deg=45)


# ---------------------------------------------------------------------------- wheels
def wheel_part(sx, seg=16):
    """Wheel at the origin, axle along X, outer face toward +X (mirrored for the right)."""
    p = C.Part()
    tyre = [(0.190, -0.112), (0.250, -0.130), (0.300, -0.126), (0.320, -0.095), (0.322, -0.020),
            (0.312, 0.0), (0.322, 0.020), (0.320, 0.095), (0.300, 0.126), (0.250, 0.130),
            (0.190, 0.112)]
    vr, fs = p.lathe(tyre, seg, RUBBER, axis='X')
    # rim barrel + hub dish (pearl) with a brass centre cap; dark inner face
    hub = [(0.0, 0.134), (0.045, 0.128), (0.064, 0.118), (0.120, 0.100), (0.175, 0.108),
           (0.192, 0.098), (0.192, -0.100), (0.0, -0.100)]
    vr, fs = p.lathe(hub, seg, PEARL, axis='X')
    p.assign(fs[0:seg], BRASS)                                       # cap ring
    p.assign(fs[4 * seg:5 * seg], INK)                               # inner barrel
    p.assign(fs[(len(hub) - 3) * seg:(len(hub) - 2) * seg], BRASS)   # cap pole fan
    p.assign(fs[(len(hub) - 2) * seg:(len(hub) - 1) * seg], INK)     # inner pole fan
    # five turbine spokes on the dish
    for k in range(5):
        a = 2 * pi * k / 5
        M = Matrix.Rotation(a, 4, 'X') @ Matrix.Translation((0.108, 0.0, 0.118))
        p.box(Vector((0, 0, 0)), (0.020, 0.028, 0.110), PEARL, matrix=M)
    if sx < 0:
        p.mirror_x()
    return p


def build_wheels(root):
    out = []
    for name, sx, sy in (("Wheel_FL", 1, -1), ("Wheel_FR", -1, -1), ("Wheel_RL", 1, 1),
                         ("Wheel_RR", -1, 1)):
        p = wheel_part(sx)
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
