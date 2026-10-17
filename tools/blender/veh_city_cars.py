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
                        frame, T, sweep, slab, lathe_m, tile, Shell, poly_path, poly_loop, seam,
                        window, arches, bumper, mirror_unit, wiper)
from chars_common import Vector, Matrix, radians, sin, cos, pi

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS


def wheels(root, axle, track, r, width, spokes, hub_mat=PEARL):
    out = []
    for name, sx, sy in (("Wheel_FL", 1, -1), ("Wheel_FR", -1, -1), ("Wheel_RL", 1, 1),
                         ("Wheel_RR", -1, 1)):
        c = Vector((sx * track, sy * axle, r))
        p = V.wheel_hq(r, width, sx, seg=16, lugs=0, grooves=0, spokes=spokes, spoke_w=0.13,
                       spoke_d=0.07, disc=False, caliper=False, nuts=0, hub_seg=10, valve=None,
                       lip=PEARL, spoke=hub_mat, hub=hub_mat, cap=BRASS, rim_r=0.60)
        p.transform(p.bm.verts, Matrix.Translation(c))
        out.append(C.merge_to_object(name, [p.to_temp()], pivot=c, parent=root, sharp_deg=40))
    return out


# ---------------------------------------------------------------------------- city_car_a
LB_A = [(0.26, -1.61, 1.65, 0.74), (0.32, -1.75, 1.79, 0.815), (0.42, -1.82, 1.835, 0.845),
        (0.60, -1.84, 1.84, 0.85), (0.76, -1.825, 1.835, 0.85), (0.86, -1.77, 1.805, 0.84),
        (0.92, -1.66, 1.76, 0.82), (0.955, -1.50, 1.70, 0.79)]
CB_A = [(0.90, -1.00, 1.69, 0.80), (0.96, -0.96, 1.665, 0.795), (1.06, -0.80, 1.61, 0.775),
        (1.19, -0.56, 1.51, 0.73), (1.30, -0.37, 1.40, 0.68), (1.385, -0.22, 1.30, 0.635),
        (1.44, -0.09, 1.19, 0.585), (1.47, 0.03, 1.06, 0.53)]


def build_a():
    """Compact hatch: low bonnet, raked screen, short sloping hatch, two-tone pearl roof."""
    C.reset_scene()
    root = C.new_empty("city_car_a", None, (0, 0, 0), size=0.5)
    axle, track, r = 1.225, 0.70, 0.31
    paint = SAND
    lo = V.Pod(LB_A, n=3.6, step=[1, 1, 2, 1, 1, 1, 1])
    ca = V.Pod(CB_A, n=3.2, step=[1, 1, 1, 1, 1, 1, 1])
    sh = Shell(lo, ca)
    pb, pc = C.Part(), C.Part()
    lo.build(pb, 32, paint, crown=0.010, fill=2, bottom_mat=INK)
    ca.build(pc, 32, paint, bands=[(1.38, 2.0, PEARL)], crown=0.010, fill=2)
    body = pb.to_temp(name="lo")
    V.boolean(body, [pc.to_temp(name="ca")], op='UNION')
    # cutters: arches + window recesses (glass set inside); seams as ink strips
    cut, glass, lines = C.Part(), C.Part(), C.Part()
    arches(cut, axle, track, 0.375, r)
    window(cut, glass, sh, 'front', [(-0.57, 1.005), (0.57, 1.005), (0.46, 1.32), (-0.46, 1.32)])
    window(cut, glass, sh, 'back', [(-0.53, 1.03), (0.53, 1.03), (0.43, 1.30), (-0.43, 1.30)])
    for side in (1, -1):
        door = [(-0.60, 1.005), (0.33, 1.005), (0.33, 1.31), (-0.14, 1.31)]
        quarter = [(0.45, 1.005), (1.24, 1.005), (0.96, 1.30), (0.45, 1.30)]
        if side < 0:
            door, quarter = door[::-1], quarter[::-1]
        window(cut, glass, sh, 'flank', door, side=side)
        window(cut, glass, sh, 'flank', quarter, side=side)
        u = poly_path([(-0.66, 1.0), (-0.66, 0.40), (0.39, 0.40), (0.39, 1.0)], 0.05)
        seam(lines, sh, 'flank', u, side=side)
    seam(lines, sh, 'back', poly_loop([(-0.62, 0.60), (0.62, 0.60), (0.56, 1.34), (-0.56, 1.34)],
                                      0.07), closed=True)
    seam(lines, sh, 'top', poly_path([(0.64, -1.01), (0.64, -1.46), (-0.64, -1.46), (-0.64, -1.01)],
                                     0.10), step=0.06)
    seam(lines, sh, 'flank', poly_loop([(1.24, 0.78), (1.33, 0.78), (1.33, 0.87), (1.24, 0.87)],
                                       0.02), closed=True, side=-1, step=0.03)
    V.boolean(body, [cut.to_temp(name="cut")])
    for side in (1, -1):
        seam(lines, sh, 'flank', [(-1.50, 0.715), (1.50, 0.715)], side=side, width=0.020,
             step=0.10, mat=PEARL, lift=0.002)
    # ---- details
    d = C.Part()
    for sx in (1, -1):
        p, n = sh.face(sx * 0.56, 0.74, -1)
        V.lamp_round(d, p, (n + Vector((0, -0.5, 0))).normalized(), 0.082, body=paint,
                     bezel=PEARL, segs=14, rings=0, depth=0.04)
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
            rail.append(q + Vector((0, 0, 0.034)))
            lathe_m(d, [(0.016, -0.02), (0.016, 0.010), (0.010, 0.030), (0.0, 0.036)], 6,
                    [INK, INK, INK], M=T(q))
        d.tube(C.spline3(rail, 2), 0.012, 6, PEARL, caps='round', cap_segs=1)
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
    V.plate_recess(d, pp, pn, 0.28, 0.095, frame_mat=PEARL)
    ex = Vector((-0.42, 1.80, 0.30))
    lathe_m(d, [(0.026, -0.10), (0.026, 0.06), (0.020, 0.064), (0.020, 0.0)], 10,
            [METAL, METAL, INK], M=frame(ex, (0, 1, -0.05)))
    for (a, b) in ((0.48, -0.02), (-0.04, -0.54)):
        wiper(d, sh, a, b, 1.02)
    temps = [body, d.to_temp(), glass.to_temp(recalc=False), lines.to_temp(recalc=False)]
    bodyob = C.merge_to_object("Body", temps, pivot=(0, 0, 0), parent=root, sharp_deg=50)
    ws = wheels(root, axle, track, r, 0.21, 6)
    C.bake_ao([bodyob] + ws, dist=0.35, samples=40, floor=0.38, ground_z=0.0)
    return root


# ---------------------------------------------------------------------------- city_car_b
LB_B = [(0.26, -1.61, 1.69, 0.74), (0.32, -1.75, 1.81, 0.815), (0.42, -1.825, 1.845, 0.845),
        (0.62, -1.855, 1.855, 0.85), (0.84, -1.845, 1.855, 0.852), (0.96, -1.80, 1.855, 0.85),
        (1.02, -1.65, 1.855, 0.85)]
CB_B = [(0.98, -1.67, 1.855, 0.85), (1.06, -1.55, 1.855, 0.85), (1.30, -1.28, 1.850, 0.845),
        (1.56, -1.12, 1.84, 0.84), (1.70, -1.00, 1.81, 0.80), (1.80, -0.83, 1.71, 0.71),
        (1.85, -0.68, 1.58, 0.60)]


def build_b():
    """Small van: short nose, tall boxy body, cab windows only, sliding door, split rear
    doors, pearl roof with a roof rack."""
    C.reset_scene()
    root = C.new_empty("city_car_b", None, (0, 0, 0), size=0.5)
    axle, track, r = 1.20, 0.70, 0.30
    paint = TEAL
    lo = V.Pod(LB_B, n=4.4, step=[1, 1, 2, 1, 1, 1])
    ca = V.Pod(CB_B, n=4.4, step=[1, 2, 2, 1, 1, 1])
    sh = Shell(lo, ca)
    pb, pc = C.Part(), C.Part()
    lo.build(pb, 32, paint, bands=[(0.80, 0.86, PEARL)], ribs=[(0.80, 0.86, 0.004)],
             crown=0.008, fill=2, bottom_mat=INK)
    ca.build(pc, 32, paint, bands=[(1.67, 2.0, PEARL)], crown=0.010, fill=2)
    body = pb.to_temp(name="lo")
    V.boolean(body, [pc.to_temp(name="ca")], op='UNION')
    cut, glass, lines = C.Part(), C.Part(), C.Part()
    arches(cut, axle, track, 0.36, r)
    window(cut, glass, sh, 'front', [(-0.66, 1.10), (0.66, 1.10), (0.60, 1.50), (-0.60, 1.50)])
    for side in (1, -1):
        cab = [(-1.14, 1.10), (-0.50, 1.10), (-0.50, 1.53), (-0.96, 1.53)]
        if side < 0:
            cab = cab[::-1]
        window(cut, glass, sh, 'flank', cab, side=side)
        # cab door seam, sliding door outline and its rail groove
        seam(lines, sh, 'flank', poly_path([(-1.00, 1.57), (-1.19, 1.06), (-1.19, 0.42),
                                            (-0.44, 0.42), (-0.44, 1.58)], 0.05), side=side)
        seam(lines, sh, 'flank', poly_loop([(-0.36, 0.40), (0.62, 0.40), (0.62, 1.58),
                                            (-0.36, 1.58)], 0.05), closed=True, side=side)
        seam(lines, sh, 'flank', [(0.66, 1.42), (1.66, 1.42)], side=side, width=0.010)
    seam(lines, sh, 'back', poly_loop([(-0.70, 0.40), (0.70, 0.40), (0.70, 1.62), (-0.70, 1.62)],
                                      0.06), closed=True)
    seam(lines, sh, 'back', [(0.0, 0.40), (0.0, 1.62)])
    window(cut, glass, sh, 'back', [(-0.62, 1.20), (-0.06, 1.20), (-0.06, 1.55), (-0.62, 1.55)])
    window(cut, glass, sh, 'back', [(0.06, 1.20), (0.62, 1.20), (0.62, 1.55), (0.06, 1.55)])
    V.boolean(body, [cut.to_temp(name="cut")])
    d = C.Part()
    for sx in (1, -1):
        p, n = sh.face(sx * 0.58, 0.76, -1)
        V.lamp_round(d, p, (n + Vector((0, -0.5, 0))).normalized(), 0.085, body=paint,
                     bezel=PEARL, segs=14, rings=0, depth=0.04)
        p, n = sh.face(sx * 0.72, 0.62, -1)
        V.lamp_round(d, p, n, 0.024, body=paint, bezel=PEARL, lens=LIGHT, segs=8, simple=True,
                     proud=0.7, depth=0.02)
        p, n = sh.face(sx * 0.74, 0.80, 1)
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
    V.plate_recess(d, pp, pn, 0.28, 0.095, frame_mat=PEARL)
    ex = Vector((-0.45, 1.82, 0.30))
    lathe_m(d, [(0.026, -0.10), (0.026, 0.06), (0.020, 0.064), (0.020, 0.0)], 10,
            [METAL, METAL, INK], M=frame(ex, (0, 1, -0.05)))
    for (a, b) in ((0.55, -0.02), (-0.05, -0.60)):
        wiper(d, sh, a, b, 1.12)
    temps = [body, d.to_temp(), glass.to_temp(recalc=False), lines.to_temp(recalc=False)]
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
