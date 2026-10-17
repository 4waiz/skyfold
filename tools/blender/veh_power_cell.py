"""Power cell - grabbable courier cargo for SKYFOLD: The Last Flight.

Original procedural model (Awaiz Ahmed / Team Kanban), not AI-generated.
    blender -b --factory-startup -P tools/blender/veh_power_cell.py [-- --no-render]

Hierarchy (pivots, Blender metres, Z up):
    PowerCell        bottom centre (0,0,0) - pearl shell, brass end caps, glass window, handle
      Core           centre of the glowing core (separate mesh, SKY_TealGlow only; the game
                     animates its emission with a property block, so it stays one material)
      ANCHOR_handle  centre of the handle grip (suggested hand attach point)
Total height 0.35 m (handle included), body diameter 0.14 m. Budget < 2.5k tris.
Detail pass (it is held in the hand in VR, ~30 cm from the eye): diamond-knurled brass base
with a recessed contact disc, ink seal grooves, pearl shell with teal lips, glass window with
four brass guard bars, three indicator lights, coral warning ring, fluted brass top cap with a
grooved top face and two connector pins, brass handle on mounts with a rubber grip and ink
wraps; the core has raised energy rings.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C
import veh_common as V
from veh_common import lathe_m, frame, T
from chars_common import Vector, Matrix, radians, sin, cos, pi

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS
OUT = os.path.join(C.MODELS, 'Props', 'power_cell.fbx')

PEARL, BRASS, TEAL, GLOW, GLASS, INK, CORAL, RUBBER, LIGHT = (
    'SKY_Pearl', 'SKY_Brass', 'SKY_Teal', 'SKY_TealGlow', 'SKY_Glass', 'SKY_Ink', 'SKY_Coral',
    'SKY_Rubber', 'SKY_Light')
SEG = 32
WIN0, WIN1 = 0.092, 0.218   # window band (core centre at 0.155)
TOP = 0.300                 # top of the upper cap (handle rises to 0.35)


def build():
    C.reset_scene()
    p = C.Part()
    # ---- lower body: recessed contact disc, brass foot, knurled band, seal groove, flange,
    #      pearl shell, teal lip into the window, ink chamber floor
    lo = [(0.0, 0.008), (0.040, 0.008), (0.046, 0.0), (0.064, 0.0), (0.0695, 0.007),
          (0.0695, 0.038), (0.0662, 0.041), (0.0662, 0.045), (0.0695, 0.049), (0.0665, 0.054),
          (0.0665, 0.083), (0.0610, WIN0), (0.0, WIN0 - 0.002)]
    mats = [BRASS, INK, BRASS, BRASS, BRASS, INK, INK, BRASS, PEARL, PEARL, TEAL, INK]
    lathe_m(p, lo, SEG, mats)
    # crisp raised grip ribs round the brass base band
    for k in range(16):
        a = 2 * pi * (k + 0.5) / 16
        d = Vector((cos(a), sin(a), 0))
        M = frame(d * 0.0693 + Vector((0, 0, 0.0225)), d, (0, 0, 1))
        V.tile(p, (0, 0, 0), 0.0058, 0.024, 0.0020, BRASS, M=M, ch=0.0009, sunk=0.0006)
    # four rivets on the lower pearl shell
    for k in range(4):
        a = 2 * pi * k / 4
        d = Vector((cos(a), sin(a), 0))
        V.rivet(p, d * 0.0665 + Vector((0, 0, 0.068)), d, 0.0042, 0.0022, BRASS, segs=6)
    # ---- upper body: ink chamber ceiling, teal lip, pearl band (lights), coral ring,
    #      fluted brass cap, chamfer, grooved top face
    up = [(0.0, WIN1 + 0.002), (0.0610, WIN1), (0.0665, WIN1 + 0.009),
          (0.0665, 0.246), (0.0665, 0.252), (0.0695, 0.256), (0.0695, 0.287), (0.0620, 0.297),
          (0.0500, TOP), (0.0460, TOP - 0.003), (0.0420, TOP), (0.0, TOP)]
    mats = [INK, TEAL, PEARL, CORAL, BRASS, BRASS, BRASS, BRASS, INK, INK, BRASS]
    lathe_m(p, up, SEG, mats)
    # ---- glass window tube (the core glows through it)
    lathe_m(p, [(0.0600, WIN0 - 0.002), (0.0600, WIN1 + 0.002)], SEG, [GLASS])
    # ---- four brass guard bars outside the glass
    for k in range(4):
        a = 2 * pi * k / 4 + pi / 4
        d = Vector((cos(a), sin(a), 0))
        p.tube([d * 0.0642 + Vector((0, 0, WIN0 - 0.006)), d * 0.0642 + Vector((0, 0, WIN1 + 0.006))],
               0.0042, 6, BRASS, caps=None)
    # ---- indicator lights on the upper pearl band
    for k, m in enumerate((GLOW, GLOW, CORAL)):
        a = radians(-90 + 30 * (k - 1))
        d = Vector((cos(a), sin(a), 0))
        c = d * 0.0665 + Vector((0, 0, 0.233))
        lathe_m(p, [(0.0056, -0.002), (0.0056, 0.0010), (0.0, 0.0034)], 8,
                [INK, m], M=frame(c, d, (0, 0, 1)))
    # ---- connector pins on the top face
    for sx in (1, -1):
        c = Vector((0.0, sx * 0.024, TOP))
        lathe_m(p, [(0.0045, -0.002), (0.0045, 0.006), (0.0, 0.0085)], 6, [BRASS, BRASS],
                M=T(c))
    # ---- handle: brass mounts, brass arch, rubber grip with ink wraps
    for sx in (1, -1):
        p.box(Vector((sx * 0.040, 0, 0.300)), (0.016, 0.022, 0.012), BRASS)
    arch = [Vector((-0.040, 0, 0.298)), Vector((-0.039, 0, 0.318)), Vector((-0.031, 0, 0.333)),
            Vector((-0.014, 0, 0.339)), Vector((0.014, 0, 0.339)), Vector((0.031, 0, 0.333)),
            Vector((0.039, 0, 0.318)), Vector((0.040, 0, 0.298))]
    p.tube(arch, 0.0068, 8, BRASS, caps=None)
    p.tube([Vector((-0.020, 0, 0.3385)), Vector((0.020, 0, 0.3385))], 0.0103, 10, RUBBER,
           caps='round', cap_segs=1)
    for x in (-0.011, 0.011):
        p.torus(0.0104, 0.0019, 8, 3, INK, matrix=T(x, 0, 0.3385) @ V.rot_y(90))
    shell = C.merge_to_object("PowerCell", [p.to_temp()], pivot=(0, 0, 0), parent=None,
                              sharp_deg=40)
    # ---- core (separate, single material): capsule with three raised energy rings
    q = C.Part()
    zc = (WIN0 + WIN1) / 2
    prof = [(0.0, WIN0 + 0.006), (0.024, WIN0 + 0.010), (0.038, WIN0 + 0.020),
            (0.043, zc - 0.034), (0.047, zc - 0.029), (0.043, zc - 0.024), (0.043, zc - 0.005),
            (0.047, zc), (0.043, zc + 0.005), (0.043, zc + 0.024), (0.047, zc + 0.029),
            (0.043, zc + 0.034), (0.038, WIN1 - 0.020), (0.024, WIN1 - 0.010),
            (0.0, WIN1 - 0.006)]
    lathe_m(q, prof, 10, GLOW)
    core = C.merge_to_object("Core", [q.to_temp()], pivot=(0, 0, zc), parent=shell,
                             sharp_deg=50)
    C.new_empty("ANCHOR_handle", shell, (0.0, 0.0, 0.336), size=0.03)
    C.bake_ao([shell, core], dist=0.05, samples=48, floor=0.42, white=[core])
    return shell


if __name__ == "__main__":
    root = build()
    C.summary(root)
    C.export_fbx(root, OUT)
    if RENDER:
        C.render_previews("power_cell", root, res=(900, 900), samples=128, ground_z=0.0,
                          lens=70, margin=1.25, views=(("fl", 38, 16), ("br", -142, 18)))
