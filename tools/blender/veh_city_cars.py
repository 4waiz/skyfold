"""Ambient city traffic for SKYFOLD: The Last Flight.

Original procedural models (Awaiz Ahmed / Team Kanban), not AI-generated.
    blender -b --factory-startup -P tools/blender/veh_city_cars.py [-- --no-render]

city_car_a.fbx  compact hatch, SKY_Sandstone paint, ~3.8 m
city_car_b.fbx  small van,     SKY_Teal paint,      ~3.8 m
Same family as the courier car / shuttle: pearl trim, round SKY_Light headlights, coral tail
lights, SKY_Glass windows over a dark SKY_Ink window band. Kept light (< 4k tris).
Hierarchy (pivots):
    city_car_a | city_car_b (empty)   ground level, centred between the axles
      Body
      Wheel_FL/FR/RL/RR               hub centres, spin about local X
Faces Blender -Y (Unity +Z).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C
import veh_common as V
from chars_common import Vector, Matrix, radians, sin, cos, pi

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS


def wheels(root, axle, track, r, width):
    out = []
    for name, sx, sy in (("Wheel_FL", 1, -1), ("Wheel_FR", -1, -1), ("Wheel_RL", 1, 1),
                         ("Wheel_RR", -1, 1)):
        c = Vector((sx * track, sy * axle, r))
        w = V.wheel_lite(c, r, width, sx, seg=12)
        out.append(C.merge_to_object(name, [w.to_temp(recalc=False)], pivot=c, parent=root,
                                     sharp_deg=40))
    return out


def common_details(shell, lower, z_lamp, front_x, rear_x, paint):
    for sx in (1, -1):
        V.lamp(shell, lower.point(lower.t_of_x(sx * front_x, z_lamp, -1), z_lamp),
               (sx * 0.2, -1, 0.05), 0.095, V.LIGHT, bezel=V.PEARL, depth=0.04, segs=12)
        V.lamp(shell, lower.point(lower.t_of_x(sx * rear_x, z_lamp + 0.05, 1), z_lamp + 0.05),
               (sx * 0.2, 1, 0.0), 0.062, V.CORAL, bezel=V.PEARL, depth=0.03, segs=10)


def build_a():
    """Compact hatch: low bonnet, raked screen, short sloping hatch."""
    C.reset_scene()
    root = C.new_empty("city_car_a", None, (0, 0, 0), size=0.5)
    shell, glass = C.Part(), C.Part()
    SAND = V.SAND
    axle, track, r = 1.225, 0.70, 0.31
    shell.rbox(Vector((0, 0, 0.42)), (1.18, 3.30, 0.40), 0.10, 1, V.INK)       # tucked chassis
    lower = V.LoftBody([(0.58, -1.78, 1.78, 0.80), (0.64, -1.87, 1.87, 0.845),
                        (0.84, -1.90, 1.90, 0.85), (0.90, -1.84, 1.86, 0.835),
                        (0.93, -1.72, 1.78, 0.80)], n=3.6)
    lower.build(shell, 28, SAND)
    cabin = V.LoftBody([(0.90, -0.98, 1.72, 0.80), (0.94, -0.92, 1.70, 0.79),
                        (1.33, -0.30, 1.46, 0.70), (1.43, -0.16, 1.32, 0.64),
                        (1.50, 0.02, 1.10, 0.52)], n=3.4)
    cabin.build(shell, 28, SAND, band_mats={1: V.INK})
    # bumpers (pearl) + headlights / tail lights
    for sy in (-1, 1):
        shell.rbox(Vector((0, sy * 1.835, 0.50)), (1.56, 0.13, 0.20), 0.065, 2, V.PEARL)
    common_details(shell, lower, 0.74, 0.55, 0.60, SAND)
    # glass
    zg0, zg1 = 0.97, 1.30
    cabin.panel_end(glass, -1, -0.62, 0.62, zg0, zg1, V.GLASS, nt=8, nz=2)
    cabin.panel_end(glass, 1, -0.54, 0.54, zg0 + 0.02, zg1 - 0.02, V.GLASS, nt=6, nz=2)
    for side in (1, -1):
        cabin.panel_side(glass, side, -0.62, 0.30, zg0, zg1, V.GLASS, nt=5, nz=2)
        cabin.panel_side(glass, side, 0.42, 1.22, zg0, zg1, V.GLASS, nt=4, nz=2)
    # pearl roof rails
    for sx in (1, -1):
        shell.tube([Vector((sx * 0.50, -0.05, 1.475)), Vector((sx * 0.52, 0.55, 1.485)),
                    Vector((sx * 0.50, 1.10, 1.46))], 0.022, 6, V.PEARL, caps='round', cap_segs=1)
    temps = [shell.to_temp(), glass.to_temp(recalc=False)]
    body = C.merge_to_object("Body", temps, pivot=(0, 0, 0), parent=root, sharp_deg=50)
    ws = wheels(root, axle, track, r, 0.21)
    C.bake_ao([body] + ws, dist=0.35, samples=40, floor=0.38, ground_z=0.0)
    return root


def build_b():
    """Small van: short nose, tall boxy body, cab windows only, pearl roof."""
    C.reset_scene()
    root = C.new_empty("city_car_b", None, (0, 0, 0), size=0.5)
    shell, glass = C.Part(), C.Part()
    TEAL = V.TEAL
    axle, track, r = 1.20, 0.70, 0.30
    shell.rbox(Vector((0, 0, 0.41)), (1.18, 3.30, 0.38), 0.10, 1, V.INK)
    body = V.LoftBody([(0.58, -1.78, 1.82, 0.80), (0.64, -1.87, 1.89, 0.845),
                       (0.90, -1.90, 1.90, 0.85), (0.98, -1.84, 1.90, 0.85),
                       (1.04, -1.66, 1.90, 0.85), (1.56, -1.18, 1.89, 0.84),
                       (1.74, -1.02, 1.86, 0.80), (1.84, -0.80, 1.72, 0.66)], n=4.4)
    fs = body.build(shell, 30, TEAL, band_mats={3: V.PEARL, 4: V.INK, 5: V.PEARL, 6: V.PEARL})
    shell.assign(fs[8 * 30:9 * 30], V.PEARL)          # roof cap
    # the dark window band only exists around the cab; the cargo box stays solid teal
    shell.assign([f for f in fs[4 * 30:5 * 30] if f.calc_center_median().y > -0.33], TEAL)
    # cab-only glass, cargo flanks stay solid (teal) with a pearl belt line
    zg0, zg1 = 1.08, 1.52
    body.panel_end(glass, -1, -0.64, 0.64, zg0, zg1, V.GLASS, nt=8, nz=2)
    for side in (1, -1):
        body.panel_side(glass, side, -1.22, -0.42, zg0, zg1, V.GLASS, nt=4, nz=2)
    # rear door seam (ink) + bumpers + lamps
    shell.box(Vector((0, 1.905, 1.10)), (0.018, 0.012, 0.86), V.INK)
    for sy in (-1, 1):
        shell.rbox(Vector((0, sy * 1.84, 0.50)), (1.56, 0.13, 0.20), 0.065, 2, V.PEARL)
    common_details(shell, body, 0.76, 0.56, 0.62, TEAL)
    # roof rack (pearl)
    for sy in (0.0, 0.9):
        shell.tube([Vector((-0.62, sy, 1.88)), Vector((0.62, sy, 1.88))], 0.022, 6, V.PEARL,
                   caps='round', cap_segs=1)
    for sx in (1, -1):
        shell.tube([Vector((sx * 0.62, -0.25, 1.86)), Vector((sx * 0.62, 1.15, 1.86))], 0.02, 6,
                   V.PEARL, caps='round', cap_segs=1)
    temps = [shell.to_temp(), glass.to_temp(recalc=False)]
    bodyob = C.merge_to_object("Body", temps, pivot=(0, 0, 0), parent=root, sharp_deg=50)
    ws = wheels(root, axle, track, r, 0.21)
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
