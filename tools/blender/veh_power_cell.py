"""Power cell - grabbable courier cargo for SKYFOLD: The Last Flight.

Original procedural model (Awaiz Ahmed / Team Kanban), not AI-generated.
    blender -b --factory-startup -P tools/blender/veh_power_cell.py [-- --no-render]

Hierarchy (pivots, Blender metres, Z up):
    PowerCell        bottom centre (0,0,0) - pearl shell, brass end caps, carry handle
      Core           centre of the glowing core (separate mesh, SKY_TealGlow; the game
                     animates its emission / scale)
      ANCHOR_handle  centre of the handle grip (suggested hand attach point)
Total height 0.35 m (handle included), body diameter 0.14 m. Prop budget < 500 tris.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C
from chars_common import Vector, Matrix, radians, sin, cos, pi

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS
OUT = os.path.join(C.MODELS, 'Props', 'power_cell.fbx')

PEARL, BRASS, TEAL, GLOW, GLASS, INK, CORAL, RUBBER = ('SKY_Pearl', 'SKY_Brass', 'SKY_Teal',
    'SKY_TealGlow', 'SKY_Glass', 'SKY_Ink', 'SKY_Coral', 'SKY_Rubber')
SEG = 14
R = 0.070            # body radius (0.14 m diameter)
WIN0, WIN1 = 0.092, 0.218   # window band
TOP = 0.300          # top of the upper cap (handle rises to 0.35)


def band(faces, k, mat, p):
    p.assign(faces[k * SEG:(k + 1) * SEG], mat)


def build():
    C.reset_scene()
    p = C.Part()
    # lower body: brass base cap -> ink groove -> pearl shell -> teal lip into the window
    lo = [(0.0, 0.0), (0.056, 0.0), (0.0695, 0.014), (0.0695, 0.034), (0.0665, 0.040),
          (0.0665, 0.082), (0.0575, WIN0 + 0.003), (0.0, WIN0 + 0.003)]
    vr, fs = p.lathe(lo, SEG, PEARL)
    for k, m in ((0, BRASS), (1, BRASS), (2, INK), (4, TEAL)):
        band(fs, k, m, p)
    nb = len(lo) - 3
    p.assign(fs[nb * SEG:(nb + 1) * SEG], BRASS)        # bottom pole fan
    p.assign(fs[(nb + 1) * SEG:(nb + 2) * SEG], INK)    # inner floor under the core
    # upper body: teal lip -> pearl shell -> coral warning ring -> brass top cap
    up = [(0.0, WIN1 - 0.003), (0.0575, WIN1 - 0.003), (0.0665, WIN1 + 0.010),
          (0.0665, 0.250), (0.0665, 0.260), (0.0695, 0.272), (0.0600, 0.293), (0.0, TOP)]
    vr, fs = p.lathe(up, SEG, PEARL)
    for k, m in ((0, TEAL), (2, CORAL), (3, BRASS), (4, BRASS)):
        band(fs, k, m, p)
    nb = len(up) - 3
    p.assign(fs[nb * SEG:(nb + 1) * SEG], INK)
    p.assign(fs[(nb + 1) * SEG:(nb + 2) * SEG], BRASS)
    # window: open glass tube between the lips (core glows through it)
    p.lathe([(0.0600, WIN0 - 0.002), (0.0600, WIN1 + 0.002)], SEG, GLASS)
    # three pearl ribs guarding the window (open-ended boxes, ends hidden in the lips)
    for k in range(3):
        a = 2 * pi * k / 3 + pi / 6
        M = Matrix.Rotation(a, 4, 'Z') @ Matrix.Translation((0.0640, 0, (WIN0 + WIN1) / 2))
        vs, fs = p.box((0, 0, 0), (0.0095, 0.013, WIN1 - WIN0 + 0.016), PEARL, matrix=M)
        ends = [f for f in fs if abs(f.normal.z) > 0.9]
        import bmesh as _bm
        _bm.ops.delete(p.bm, geom=ends, context='FACES_ONLY')
    # carry handle: brass arch with a rubber grip
    hp = [Vector((-0.040, 0, 0.292)), Vector((-0.038, 0, 0.326)), Vector((-0.016, 0, 0.343)),
          Vector((0.016, 0, 0.343)), Vector((0.038, 0, 0.326)), Vector((0.040, 0, 0.292))]
    vr, fs = p.tube(hp, 0.0075, 6, BRASS, caps='flat')
    grip = [f for f in fs if abs(f.calc_center_median().x) < 0.026 and
            f.calc_center_median().z > 0.33]
    p.assign(grip, RUBBER)
    shell = C.merge_to_object("PowerCell", [p.to_temp(recalc=False)], pivot=(0, 0, 0),
                              parent=None, sharp_deg=40)
    # core (separate) - glowing capsule inside the window
    q = C.Part()
    q.lathe([(0.0, WIN0 + 0.004), (0.046, WIN0 + 0.024), (0.046, WIN1 - 0.024),
             (0.0, WIN1 - 0.004)], 8, GLOW)
    zc = (WIN0 + WIN1) / 2
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
