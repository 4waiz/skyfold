"""Convoy shuttle - friendly passenger minibus for SKYFOLD: The Last Flight.

Original procedural model (Awaiz Ahmed / Team Kanban), not AI-generated.
    blender -b --factory-startup -P tools/blender/veh_convoy_shuttle.py [-- --no-render]

~5.2 m long x 2.0 m wide x 2.55 m tall, teal lower body, brass belt line, pearl upper body
and roof. Faces Blender -Y (Unity +Z).
Hierarchy (pivots):
    convoy_shuttle (empty)   ground level, centred between the axles
      Body                   same as root
      Wheel_FL/FR/RL/RR      hub centres (r = 0.40 m), spin about local X
Detail pass: smooth monotone-cubic body loft with a raised brass belt rib, boolean wheel arches
with ink liners, recessed framed windows with inset glass (two-piece windscreen, five side
windows, rear window), a recessed blank teal-glow destination display (no text), a double
passenger door on the right flank (Blender -X) with segmented glass, brass grab rails and an
entry step, roof AC unit with fans and louvres, bus mirrors on stalks, bumpers with rubber
strips, round headlights, markers, tail-light clusters, grille, battery hatch, wipers, spoked
rims with brass nuts.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C
import veh_common as V
from veh_common import (PEARL, TEAL, CORAL, LIGHT, INK, RUBBER, BRASS, GLASS, GLOW, METAL,
                        frame, T, sweep, slab, lathe_m, tile, rr_lathe, Shell, poly_path,
                        poly_loop, seam, window, arches, bumper, wiper)
from chars_common import Vector, Matrix, radians, sin, cos, pi

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS
OUT = os.path.join(C.MODELS, 'Vehicles', 'convoy_shuttle.fbx')

AXLE = 1.65
TRACK = 0.84
WR = 0.40
BELT = (1.08, 1.115)
BODY = [(0.34, -2.40, 2.40, 0.93), (0.42, -2.50, 2.50, 0.985), (0.56, -2.53, 2.53, 1.00),
        (1.20, -2.53, 2.53, 1.00), (2.02, -2.47, 2.52, 1.00), (2.22, -2.42, 2.47, 0.975),
        (2.36, -2.30, 2.38, 0.90), (2.44, -2.10, 2.22, 0.76)]
WZ = (1.32, 1.98)          # side window band
DOOR = (-1.12, -0.32, 0.44, 2.04)


def door_leaves(d, sh):
    """Two inset teal leaves (right flank) with segmented glass and brass grab rails."""
    y0, y1, z0, z1 = DOOR
    gap = 0.012
    wl = (y1 - y0 - 0.02 - gap) / 2
    for k in range(2):
        yc = y0 + 0.01 + wl / 2 + k * (wl + gap)
        zc = (z0 + z1) / 2 + 0.005
        p, n = sh.flank(yc, zc, -1, -0.020)
        M = frame(p, n, (0, 0, 1))
        h = z1 - z0 - 0.02
        rr_lathe(d, wl, h, 0.03, [(0.0, -0.012), (0.0, 0.012), (-0.045, 0.012),
                                  (-0.045, -0.012), (0.0, -0.012)], [TEAL, TEAL, TEAL, TEAL],
                 M=M, nc=2, cap=False)
        zr = -h / 2 + 0.47
        slab(d, wl - 0.06, 0.06, 0.022, 0.010, 0.006, TEAL, M=M @ T(0, zr, 0), nc=1, ne=1)
        for (a, b) in ((zr + 0.03, h / 2 - 0.045), (-h / 2 + 0.045, zr - 0.03)):
            slab(d, wl - 0.085, b - a, 0.006, 0.012, 0.002, GLASS, M=M @ T(0, (a + b) / 2, -0.004),
                 nc=1, ne=1)
        # brass grab rail on the closing edge of each leaf
        xr = (wl / 2 - 0.07) * (1 if k == 0 else -1)
        a = M @ Vector((xr, -0.20, 0.016))
        b = M @ Vector((xr, 0.35, 0.016))
        d.tube([a, b], 0.010, 8, BRASS, caps='round', cap_segs=1)
        for q in (a, b):
            d.tube([q, q - n * 0.03], 0.0075, 6, BRASS, caps='flat')


def roof_unit(d, sh):
    q = sh.top(0.0, 0.55)[0]
    c = Vector((0, 0.55, q.z + 0.055))
    g = slab(d, 1.10, 1.70, 0.14, 0.20, 0.045, PEARL, M=T(c), nc=3, ne=2, side=TEAL)
    top = c.z + 0.07
    for yf in (0.12, 0.98):
        M = T(0, yf, top)
        lathe_m(d, [(0.215, -0.012), (0.215, 0.006), (0.195, 0.012), (0.180, 0.004),
                    (0.0, 0.004)], 20, [PEARL, PEARL, PEARL, INK], M=M)
        for k in range(4):
            a = radians(45 * k)
            Mb = M @ Matrix.Rotation(a, 4, 'Z')
            tile(d, (0, 0, 0.004), 0.36, 0.014, 0.008, PEARL, M=Mb, ch=0.003, sunk=0.0)
        lathe_m(d, [(0.045, 0.004), (0.045, 0.014), (0.030, 0.022), (0.0, 0.025)], 12,
                [PEARL, PEARL, BRASS], M=M)
    for sx in (1, -1):
        for k in range(5):
            y = 0.55 - 0.48 + k * 0.24
            Ml = frame(Vector((sx * 0.552, y, c.z + 0.005)), (sx, 0, 0), (0, 0, 1))
            tile(d, (0, 0, -0.004), 0.16, 0.050, 0.006, INK, M=Ml, ch=0.004, sunk=0.0)


def bus_mirror(d, side):
    a = Vector((side * 0.965, -2.36, 1.98))
    path = C.spline3([a, Vector((side * 1.005, -2.54, 1.92)), Vector((side * 0.995, -2.60, 1.74))], 3)
    d.tube(path, 0.014, 8, INK, caps='round', cap_segs=1)
    hc = Vector((side * 0.985, -2.615, 1.62))
    M = frame(hc, (0, 1, 0), (0, 0, 1))
    g = slab(d, 0.115, 0.23, 0.060, 0.045, 0.022, PEARL, M=M, nc=2, ne=2, bottom=TEAL)
    d.assign(g['top'][:-12], INK)
    d.assign(g['top'][-12:], METAL)


def build():
    C.reset_scene()
    root = C.new_empty("convoy_shuttle", None, (0, 0, 0), size=0.6)
    pod = V.Pod(BODY, n=4.6, step=[1, 1, 2, 2, 1, 1, 1])
    sh = Shell(pod)
    pb = C.Part()
    pod.build(pb, 40, PEARL, bands=[(0.0, BELT[0], TEAL), (BELT[0], BELT[1], BRASS)],
              ribs=[(BELT[0], BELT[1], 0.005)], crown=0.012, fill=2, bottom_mat=INK)
    body = pb.to_temp(name="body")
    cut, glass, lines, d = C.Part(), C.Part(), C.Part(), C.Part()
    arches(cut, AXLE, TRACK, 0.48, WR, x_in=0.60)
    # windscreen (two panes), destination display, rear window
    for sx in (1, -1):
        w = [(0.045, 1.30), (0.84, 1.30), (0.82, 2.00), (0.045, 2.00)]
        if sx < 0:
            w = [(-x, z) for (x, z) in w][::-1]
        window(cut, glass, sh, 'front', w, depth=0.02)
    window(cut, glass, sh, 'front', [(-0.62, 2.07), (0.62, 2.07), (0.62, 2.205), (-0.62, 2.205)],
           depth=0.02, pane_mat=GLOW)
    window(cut, glass, sh, 'back', [(-0.80, 1.40), (0.80, 1.40), (0.80, 1.98), (-0.80, 1.98)],
           depth=0.02)
    # side windows: five on the left, door + four on the right
    left = [(-2.10, -1.32), (-1.20, -0.42), (-0.30, 0.48), (0.60, 1.38), (1.50, 2.14)]
    right = [(-2.10, -1.32), (-0.16, 0.62), (0.74, 1.52), (1.64, 2.14)]
    for (a, b) in left:
        window(cut, glass, sh, 'flank', [(a, WZ[0]), (b, WZ[0]), (b, WZ[1]), (a, WZ[1])], side=1,
               depth=0.02)
    for (a, b) in right:
        window(cut, glass, sh, 'flank', [(b, WZ[0]), (a, WZ[0]), (a, WZ[1]), (b, WZ[1])], side=-1,
               depth=0.02)
    # door aperture (deep recess, ink)
    y0, y1, z0, z1 = DOOR
    V.surface_patch(cut, V.ccw(V.densify2(poly_loop([(y1, z0), (y0, z0), (y0, z1), (y1, z1)], 0.06,
                                                    2), 0.16, closed=True)),
                    V.mapper(sh, 'flank', -1), 0.045, 0.03, INK, scales=(1.0, 0.5))
    # front grille and rear vent recesses
    V.surface_patch(cut, V.ccw(V.densify2(poly_loop([(-0.42, 0.72), (0.42, 0.72), (0.42, 0.88),
                                                    (-0.42, 0.88)], 0.05, 2), 0.16, closed=True)),
                    V.mapper(sh, 'front'), 0.018, 0.03, INK, scales=(1.0, 0.5))
    V.surface_patch(cut, V.ccw(V.densify2(poly_loop([(-0.50, 0.80), (0.50, 0.80), (0.50, 0.94),
                                                    (-0.50, 0.94)], 0.05, 2), 0.16, closed=True)),
                    V.mapper(sh, 'back'), 0.018, 0.03, INK, scales=(1.0, 0.5))
    V.boolean(body, [cut.to_temp(name="cut")])
    # ---- seams: battery hatch (left), roof hatch outline
    seam(lines, sh, 'flank', poly_loop([(-0.95, 0.47), (0.95, 0.47), (0.95, 0.98), (-0.95, 0.98)],
                                       0.05), closed=True, side=1)
    seam(lines, sh, 'flank', poly_loop([(0.95, 0.47), (-0.95, 0.47), (-0.95, 0.98), (0.95, 0.98)],
                                       0.05), closed=True, side=-1)
    for side in (1, -1):
        for y in (-0.55, 0.55):
            p, n = sh.flank(y, 0.90, side)
            slab(d, 0.10, 0.024, 0.014, 0.010, 0.005, PEARL, M=frame(p, n, (0, 0, 1)), nc=2,
                 ne=1)
    # ---- slats in the grille / vent recesses
    gp, gn = sh.face(0.0, 0.80, -1)
    Mg = frame(gp, gn, (0, 0, 1))
    for k in range(4):
        tile(d, (0, -0.06 + 0.04 * k, -0.018), 0.80, 0.014, 0.016, PEARL, M=Mg, ch=0.004)
    vp, vn = sh.face(0.0, 0.87, 1)
    Mv = frame(vp, vn, (0, 0, 1))
    for k in range(4):
        tile(d, (0, -0.05 + 0.033 * k, -0.018), 0.96, 0.012, 0.016, INK, M=Mv, ch=0.003)
    # ---- lamps
    for sx in (1, -1):
        p, n = sh.face(sx * 0.66, 0.84, -1)
        V.lamp_round(d, p, n, 0.112, body=TEAL, bezel=BRASS, segs=20, depth=0.045)
        p, n = sh.face(sx * 0.83, 0.68, -1)
        V.lamp_round(d, p, n, 0.028, body=TEAL, bezel=BRASS, lens=LIGHT, segs=10, simple=True,
                     proud=0.7, depth=0.02)
        p, n = sh.face(sx * 0.80, 0.98, 1)
        M = V.lamp_rrect(d, p, n, 0.11, 0.34, 0.035, body=TEAL, bezel=BRASS, lens=CORAL,
                         depth=0.035, nc=2)
        tile(d, (0, -0.11, 0.010), 0.07, 0.07, 0.004, LIGHT, M=M, ch=0.004)
        for k in range(2):
            tile(d, (0, 0.02 + 0.07 * k, 0.010), 0.075, 0.008, 0.005, CORAL, M=M, ch=0.002)
        # side marker lights along the teal skirt
        for y in (-1.95, 0.0, 1.95):
            p, n = sh.flank(y, 0.66, sx)
            V.lamp_round(d, p, n, 0.020, body=TEAL, bezel=PEARL, lens=LIGHT, segs=8,
                         simple=True, proud=0.6, depth=0.015)
        bus_mirror(d, sx)
    bp, bn = sh.face(0.0, 1.02, -1)
    lathe_m(d, [(0.034, -0.01), (0.034, 0.005), (0.026, 0.010), (0.0, 0.012)], 12,
            [BRASS, BRASS, BRASS], M=frame(bp, bn))
    # ---- bumpers, plate, wipers
    bumper(d, sh, -1, 0.55, 0.10, 0.17, PEARL, span=0.70)
    bumper(d, sh, 1, 0.55, 0.10, 0.17, PEARL, span=0.70)
    pp, pn = sh.face(0.0, 0.70, 1)
    V.plate_recess(d, pp, pn, 0.34, 0.11, frame_mat=PEARL)
    for (a, b) in ((0.80, 0.10), (-0.06, -0.76)):
        wiper(d, sh, a, b, 1.33)
    # ---- door: leaves, step with rubber tread and brass nosing
    door_leaves(d, sh)
    yc = (DOOR[0] + DOOR[1]) / 2
    slab(d, 0.13, 0.80, 0.055, 0.02, 0.012, INK, M=T(-0.965, yc, 0.315), nc=2, ne=1)
    for k in range(4):
        tile(d, (-0.965, yc - 0.30 + k * 0.2, 0.342), 0.10, 0.12, 0.004, RUBBER, ch=0.003)
    d.tube([Vector((-1.028, yc - 0.39, 0.338)), Vector((-1.028, yc + 0.39, 0.338))], 0.009, 8,
           BRASS, caps='round', cap_segs=1)
    roof_unit(d, sh)
    temps = [body, d.to_temp(), glass.to_temp(), lines.to_temp(recalc=False)]
    bodyob = C.merge_to_object("Body", temps, pivot=(0, 0, 0), parent=root, sharp_deg=50)
    wheels = []
    for name, sx, sy in (("Wheel_FL", 1, -1), ("Wheel_FR", -1, -1), ("Wheel_RL", 1, 1),
                         ("Wheel_RR", -1, 1)):
        c = Vector((sx * TRACK, sy * AXLE, WR))
        w = V.wheel_hq(WR, 0.28, sx, seg=24, lugs=0, grooves=1, spokes=8, spoke_w=0.085,
                       spoke_d=0.06, spoke_flare=1.25, disc=False, caliper=False, nuts=8,
                       hub_seg=14, valve=None, lip=PEARL, spoke=PEARL, hub=TEAL, cap=BRASS,
                       rim_r=0.60)
        w.transform(w.bm.verts, Matrix.Translation(c))
        wheels.append(C.merge_to_object(name, [w.to_temp()], pivot=c, parent=root,
                                        sharp_deg=40))
    C.bake_ao([bodyob] + wheels, dist=0.40, samples=48, floor=0.38, ground_z=0.0)
    return root


if __name__ == "__main__":
    root = build()
    C.summary(root)
    C.export_fbx(root, OUT)
    if RENDER:
        C.render_previews("convoy_shuttle", root, res=(960, 720), samples=128, ground_z=0.0,
                          lens=50, margin=1.08)
