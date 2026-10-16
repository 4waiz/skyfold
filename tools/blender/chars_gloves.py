"""Courier glove pair (glove_L / glove_R) for SKYFOLD: The Last Flight.

Original procedural model (Awaiz Ahmed / Team Kanban), not AI-generated.
    blender -b --factory-startup -P tools/blender/chars_gloves.py [-- --no-render]

Each FBX:
    glove_L (empty)  = controller grip point (centre of the palm where a Quest controller
                       handle sits; the handle axis runs along Unity Y through it)
      Open           relaxed, slightly curled fingers   (pivot = grip point)
      Grip           fingers closed around the handle   (pivot = grip point)
      ANCHOR_wristui (glove_L only) centre of the bracer face; local Unity -Z points out of
                     the face, local +X toward the fingertips, local +Y toward the little finger
Only one of Open / Grip should be visible at a time. glove_L carries the brass-and-teal
folding-city bracer in both meshes.
Fingers point Blender -Y (Unity +Z). Left palm faces Blender -X (Unity +X); the right glove
is the mirror image (palm faces Unity -X). Thumb up (+Z).
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C
from chars_common import Vector, Matrix, radians, sin, cos, pi, sqrt, atan2
import bpy

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS

IVORY, TEAL, BRASS, INK, GLOW, SAND = ('SKY_Ivory', 'SKY_Teal', 'SKY_Brass', 'SKY_Ink',
                                       'SKY_TealGlow', 'SKY_Sandstone')

# name, MCP root (x, y, z), phalanx lengths, radius, open curl (MCP, PIP, DIP deg), spread (+ = toward thumb)
FINGERS = [
    ('index', (0.031, -0.016, 0.0265), (0.036, 0.024, 0.020), 0.0094, (12, 17, 10), 5),
    ('middle', (0.031, -0.014, 0.0090), (0.040, 0.026, 0.021), 0.0098, (14, 19, 11), 0),
    ('ring', (0.030, -0.010, -0.0080), (0.037, 0.025, 0.020), 0.0093, (16, 22, 12), -4),
    ('pinky', (0.028, -0.003, -0.0240), (0.030, 0.020, 0.017), 0.0085, (19, 25, 14), -9),
]
R_WRAP = 0.0290          # finger centre-line radius around the handle in the grip pose
PALM_C = Vector((0.032, 0.033, 0.001))
CUFF_C = Vector((0.032, 0.0, 0.001))
CUFF_SCALE = (0.80, 1.0, 1.10)
DEVICE_Y = 0.090


def rounded_rect(w, h, r, n=3):
    pts = []
    for (cx, cy, a0) in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                         (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(n + 1):
            a = radians(a0 + 90 * k / n)
            pts.append((cx + r * cos(a), cy + r * sin(a)))
    return pts


def back_matrix(x, y, z):
    """Local XY plane -> world (Y, Z) plane, local +Z -> world +X."""
    return Matrix(((0, 0, 1, x), (1, 0, 0, y), (0, 1, 0, z), (0, 0, 0, 1)))


def chain_open(root, lens, curls, spread):
    S = Matrix.Rotation(radians(-spread), 3, 'X')
    A = S @ Vector((0, 0, 1))
    d0 = S @ Vector((0, -1, 0))
    pts = [Vector(root)]
    ang = 0.0
    p = Vector(root)
    for l, c in zip(lens, curls):
        ang += c
        p = p + (Matrix.Rotation(radians(-ang), 3, A) @ d0) * l
        pts.append(p.copy())
    return pts, d0


def chain_grip(root, lens):
    z = root[2]
    K = Vector((root[0], root[1]))
    phi = atan2(K.y, K.x)
    out = [Vector((K.x, K.y, z))]
    X = K
    for l in lens:
        f = phi
        Q = X
        for _ in range(4000):
            f -= 0.001
            Q = Vector((R_WRAP * cos(f), R_WRAP * sin(f)))
            if (Q - X).length >= l:
                break
        out.append(Vector((Q.x, Q.y, z)))
        X, phi = Q, f
    return out, Vector((0, -1, 0))


def finger(part, joints, d0, r):
    root_in = joints[0] - d0 * 0.016
    pts = C.spline3([root_in] + joints, 3)
    radii = C.resample([r * 0.98, r * 1.04, r * 0.98, r * 0.96, r * 0.92, r * 0.86],
                       len(pts))
    part.tube(pts, radii, 9, IVORY, caps='round', cap_segs=2)


def thumb(part, grip):
    if grip:
        pts = [(0.031, 0.034, 0.026), (0.016, 0.014, 0.038), (-0.004, -0.004, 0.044),
               (-0.019, -0.018, 0.043)]
    else:
        pts = [(0.031, 0.034, 0.026), (0.017, 0.010, 0.040), (0.003, -0.012, 0.047),
               (-0.006, -0.030, 0.047)]
    sp = C.spline3(pts, 3)
    radii = C.resample([0.0122, 0.0118, 0.0108, 0.0098], len(sp))
    part.tube(sp, radii, 10, IVORY, caps='round', cap_segs=2)


def build_hand(name, grip, device, parent, mirror=False):
    soft = C.Part()      # smooth organic forms, no bevel
    plates = C.Part()    # beveled panels / plates

    # palm block (a little cupped when gripping)
    vs, fs = soft.superellipsoid(PALM_C, (0.0155, 0.049, 0.039), 0.5, 0.55, 20, 12, IVORY,
                                 pole_axis='Y')
    vs = list({v for f in fs for v in f.verts})
    if grip:
        soft.deform(vs, lambda v: v - Vector((0.0055 * ((v.z - PALM_C.z) / 0.039) ** 2, 0, 0)))
    # thenar (thumb root) pad
    soft.superellipsoid(Vector((0.026, 0.028, 0.024)), (0.012, 0.024, 0.0150), 0.8, 0.8, 12, 8,
                        IVORY)
    for (nm, root, lens, r, curls, spread) in FINGERS:
        if grip:
            joints, d0 = chain_grip(root, lens)
        else:
            joints, d0 = chain_open(root, lens, curls, spread)
        finger(soft, joints, d0, r)
    thumb(soft, grip)
    # cuff (deep teal), elliptical, rolled lip, dark interior
    S = Matrix.Diagonal((*CUFF_SCALE, 1.0))
    Mc = Matrix.Translation(CUFF_C) @ S
    prof = [(0.0, 0.060), (0.0300, 0.060), (0.0318, 0.068), (0.0334, 0.090), (0.0352, 0.106),
            (0.0374, 0.112), (0.0368, 0.1165), (0.0342, 0.1178), (0.0322, 0.1160),
            (0.0312, 0.1080), (0.0, 0.1080)]
    vr, cf = soft.lathe(prof, 18, TEAL, matrix=Mc, axis='Y')
    nb = len(prof) - 3
    soft.assign(cf[(nb + 1) * 18:(nb + 2) * 18], INK)       # wrist opening (dark)
    soft.assign(cf[7 * 18:8 * 18], INK)                      # inner wall
    # brass trim ring where the cuff meets the hand
    Mr = Matrix.Translation(CUFF_C + Vector((0, 0.0695, 0))) @ S @ Matrix.Rotation(radians(90), 4, 'X')
    soft.torus(0.0322, 0.0024, 18, 5, BRASS, matrix=Mr)
    # leather back panel + palm pad + brass knuckle plate
    bp = rounded_rect(0.062, 0.058, 0.012)
    vs, fs = plates.prism([(x + 0.030, y) for (x, y) in bp], 0.0030, IVORY,
                          matrix=back_matrix(0.0470, -0.004, 0.0015))
    plates.deform(vs, lambda v: v - Vector((3.2 * (v.z - 0.0015) ** 2, 0, 0)))
    pp = rounded_rect(0.060, 0.058, 0.013)
    vs, fs = plates.prism([(x + 0.026, y) for (x, y) in pp], 0.0030, SAND,
                          matrix=back_matrix(0.0170, -0.004, 0.0005))
    plates.deform(vs, lambda v: v + Vector((3.2 * (v.z - 0.0005) ** 2, 0, 0)))
    if grip:
        plates.deform(vs, lambda v: v - Vector((0.0055 * ((v.z - PALM_C.z) / 0.039) ** 2, 0, 0)))
    kp = rounded_rect(0.017, 0.068, 0.0065)
    vs, fs = plates.prism(kp, 0.0048, BRASS, matrix=back_matrix(0.0488, -0.0105, 0.0010))
    plates.deform(vs, lambda v: v - Vector((3.0 * (v.z - 0.001) ** 2, 0, 0)))
    if device:
        # folding-city bracer: brass band + teal housing + brass bezel + dark flat face
        Mb = Matrix.Translation(CUFF_C + Vector((0, DEVICE_Y, 0))) @ S @ \
            Matrix.Rotation(radians(90), 4, 'X')
        soft.torus(0.0352, 0.0030, 20, 5, BRASS, matrix=Mb)
        hx = CUFF_C.x + 0.0345 * CUFF_SCALE[0]          # cuff surface on the back of the wrist
        plates.rbox(Vector((hx + 0.0040, DEVICE_Y, CUFF_C.z)), (0.0125, 0.046, 0.040), 0.0045,
                    2, TEAL)
        face_x = hx + 0.0040 + 0.00625
        rr = rounded_rect(0.034, 0.028, 0.006, 2)
        plates.prism(rr, 0.0012, INK, matrix=back_matrix(face_x + 0.0002, DEVICE_Y, CUFF_C.z))
        ring = [Vector((face_x + 0.0008, DEVICE_Y + x, CUFF_C.z + y))
                for (x, y) in rounded_rect(0.037, 0.031, 0.0075, 2)]
        soft.tube(ring, 0.0016, 6, BRASS, closed=True)
        # glowing status strip on the fingertip-side edge of the housing
        plates.box(Vector((hx + 0.0040, DEVICE_Y - 0.0232, CUFF_C.z)), (0.0050, 0.0016, 0.020),
                   GLOW)
        # two small pearl 'fold' ridges on the housing flanks (a nod to the folding city)
        for sz in (1, -1):
            plates.box(Vector((hx + 0.0030, DEVICE_Y, CUFF_C.z + sz * 0.0205)),
                       (0.0060, 0.030, 0.0018), 'SKY_Pearl')
    if mirror:
        soft.mirror_x()
        plates.mirror_x()
    temps = [soft.to_temp(), plates.to_temp(bevel=(0.0010, 1, 40))]
    return C.merge_to_object(name, temps, pivot=(0, 0, 0), parent=parent, sharp_deg=50)


def build(side):
    C.reset_scene()
    root = C.new_empty("glove_%s" % side, None, (0, 0, 0), size=0.04)
    left = side == 'L'
    # the right glove is the mirrored left build (x -> -x: palm faces Blender +X = Unity -X)
    op = build_hand("Open", False, left, root, mirror=not left)
    gp = build_hand("Grip", True, left, root, mirror=not left)
    if left:
        face_x = CUFF_C.x + 0.0345 * CUFF_SCALE[0] + 0.0040 + 0.00625 + 0.0008
        R = Matrix(((0, 1, 0), (1, 0, 0), (0, 0, -1)))   # local X=+Y, Y=+X, Z=-Z (Blender)
        C.new_empty("ANCHOR_wristui", root, (face_x, DEVICE_Y, CUFF_C.z), rot=R, size=0.02,
                    kind='ARROWS')
    C.bake_ao([op], dist=0.03, samples=64, floor=0.42)
    C.bake_ao([gp], dist=0.03, samples=64, floor=0.42)
    return root, op, gp


if __name__ == "__main__":
    for side in ('L', 'R'):
        root, op, gp = build(side)
        C.summary(root)
        C.export_fbx(root, os.path.join(C.MODELS, 'Characters', 'glove_%s.fbx' % side))
        if RENDER:
            # preview: Open on the left, Grip shifted beside it (render only, not exported)
            gp.location.x += (-0.11 if side == 'L' else 0.11)
            gp.location.y += 0.0
            C.render_previews("glove_%s" % side, root, res=(960, 720), samples=128,
                              ground_z=-0.06, lens=70, margin=1.12,
                              views=(("fl", 38, 22), ("br", -142, 24)))
