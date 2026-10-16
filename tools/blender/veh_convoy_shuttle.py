"""Convoy shuttle - friendly passenger minibus for SKYFOLD: The Last Flight.

Original procedural model (Awaiz Ahmed / Team Kanban), not AI-generated.
    blender -b --factory-startup -P tools/blender/veh_convoy_shuttle.py [-- --no-render]

~5.2 m long x 2.0 m wide x 2.5 m tall, pearl and teal, big glass windows (SKY_Glass over a
dark SKY_Ink window band so the cabin never reads see-through). Faces Blender -Y (Unity +Z).
Hierarchy (pivots):
    convoy_shuttle (empty)   ground level, centred between the axles
      Body                   same as root
      Wheel_FL/FR/RL/RR      hub centres (r = 0.40 m), spin about local X
The passenger door is on the right-hand flank (Blender -X = Unity -X... the vehicle's right).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C
import veh_common as V
from chars_common import Vector, Matrix, radians, sin, cos, pi

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS
OUT = os.path.join(C.MODELS, 'Vehicles', 'convoy_shuttle.fbx')

AXLE = 1.65
TRACK = 0.84
WR = 0.40
WIN = (1.24, 2.10)       # window band


def build():
    C.reset_scene()
    root = C.new_empty("convoy_shuttle", None, (0, 0, 0), size=0.6)
    shell = C.Part()
    glass = C.Part()
    # upper body: full-width loft overhanging the tucked-in wheels
    slices = [(0.80, -2.42, 2.42, 0.95), (0.86, -2.49, 2.49, 0.995), (1.10, -2.50, 2.50, 1.00),
              (WIN[0], -2.50, 2.50, 1.00), (WIN[1], -2.36, 2.49, 0.985), (2.28, -2.27, 2.44, 0.95),
              (2.41, -2.10, 2.32, 0.86), (2.48, -1.85, 2.12, 0.68)]
    body = V.LoftBody(slices, n=4.6)
    body.build(shell, 36, V.PEARL, band_mats={0: V.TEAL, 1: V.TEAL, 3: V.INK})
    # inset chassis (dark), teal side skirts between the wheels, teal bumpers
    shell.rbox(Vector((0, 0, 0.56)), (1.36, 4.60, 0.56), 0.12, 2, V.INK)
    for sx in (1, -1):
        shell.rbox(Vector((sx * 0.93, 0.0, 0.64)), (0.12, 2.24, 0.40), 0.05, 2, V.TEAL)
    for sy in (-1, 1):
        shell.rbox(Vector((0, sy * 2.50, 0.60)), (1.74, 0.20, 0.26), 0.09, 2, V.PEARL)
    # lamps: big round headlights, coral tail lights, small amber-ish marker = SKY_Light
    for sx in (1, -1):
        V.lamp(shell, body.point(body.t_of_x(sx * 0.66, 0.98, -1), 0.98) + Vector((0, 0.01, 0)),
               (sx * 0.15, -1, 0), 0.150, V.LIGHT, bezel=V.PEARL, depth=0.05, segs=16)
        V.lamp(shell, body.point(body.t_of_x(sx * 0.70, 1.02, 1), 1.02) - Vector((0, 0.01, 0)),
               (sx * 0.15, 1, 0), 0.085, V.CORAL, bezel=V.PEARL, depth=0.04, segs=12)
    # roof pod (air conditioning) with a teal stripe
    vs, fs = shell.superellipsoid(Vector((0, 0.30, 2.47)), (0.58, 0.95, 0.12), 0.45, 0.45, 18, 8,
                                  V.PEARL)
    shell.assign([f for f in fs if 2.50 < f.calc_center_median().z < 2.535], V.TEAL)
    # glass: windscreen, rear window, side windows; passenger door on the right flank
    body.panel_end(glass, -1, -0.86, 0.86, WIN[0] + 0.06, WIN[1] - 0.04, V.GLASS, nt=10, nz=3)
    body.panel_end(glass, 1, -0.72, 0.72, WIN[0] + 0.14, WIN[1] - 0.06, V.GLASS, nt=8, nz=3)
    left = [(-1.98, -1.36), (-1.24, -0.28), (-0.16, 0.80), (0.92, 1.88), (2.00, 2.28)]
    right = [(-1.12, -0.28), (-0.16, 0.80), (0.92, 1.88), (2.00, 2.28)]
    for (a, b) in left:
        body.panel_side(glass, 1, a, b, WIN[0] + 0.07, WIN[1] - 0.06, V.GLASS, nt=4, nz=2)
    for (a, b) in right:
        body.panel_side(glass, -1, a, b, WIN[0] + 0.07, WIN[1] - 0.06, V.GLASS, nt=4, nz=2)
    # passenger door (right flank): tall glass leaf over a teal frame
    body.panel_side(glass, -1, -2.02, -1.40, 0.90, WIN[1] - 0.06, V.GLASS, off=0.012, nt=4, nz=4)
    door_frame = []
    for (y, z) in V.rounded_rect(0.78, 1.28, 0.08, 2):
        door_frame.append(body.point(body.t_of_y(-1.71 + y, 1.50 + z, -1), 1.50 + z, 0.006))
    shell.tube(door_frame, 0.022, 6, V.TEAL, closed=True)
    # small step under the door
    shell.rbox(Vector((-0.94, -1.71, 0.36)), (0.20, 0.80, 0.08), 0.03, 1, V.INK)
    temps = [shell.to_temp(), glass.to_temp(recalc=False)]
    bodyob = C.merge_to_object("Body", temps, pivot=(0, 0, 0), parent=root, sharp_deg=50)
    wheels = []
    for name, sx, sy in (("Wheel_FL", 1, -1), ("Wheel_FR", -1, -1), ("Wheel_RL", 1, 1),
                         ("Wheel_RR", -1, 1)):
        c = Vector((sx * TRACK, sy * AXLE, WR))
        w = V.wheel(c, WR, 0.28, sx, seg=16, hub_ratio=0.58)
        wheels.append(C.merge_to_object(name, [w.to_temp(recalc=False)], pivot=c, parent=root,
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
