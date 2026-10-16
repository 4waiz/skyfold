"""Passenger figures (passenger_a/b/c) for the SKYFOLD terminal queue.

Original procedural models (Awaiz Ahmed / Team Kanban), not AI-generated. Deliberately
simple stylised silhouettes: no faces, no likeness of any real person.
    blender -b --factory-startup -P tools/blender/chars_passengers.py [-- --no-render]

Each FBX:  passenger_x (empty, ground between the feet) > Body (single mesh).
Facing Blender -Y (Unity +Z). ~1.6-1.75 m tall. Palette materials only.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C
from chars_common import Vector, Matrix, radians, sin, cos, pi

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS

VARIANTS = {
    # height scale, top, pants, skin, hair, hair style, accessory, accessory colour
    'passenger_a': dict(h=1.00, top='SKY_Teal', pants='SKY_Ink', skin='SKY_SandstoneDeep',
                        hair='SKY_Ink', style='short', acc='backpack', acc_mat='SKY_Coral'),
    'passenger_b': dict(h=1.03, top='SKY_Coral', pants='SKY_Ink', skin='SKY_Wood',
                        hair='SKY_Ink', style='cap', acc='suitcase', acc_mat='SKY_Teal'),
    'passenger_c': dict(h=0.95, top='SKY_Pearl', pants='SKY_Teal', skin='SKY_Sandstone',
                        hair='SKY_PalmTrunk', style='bun', acc='coat', acc_mat='SKY_TealLight'),
}


def figure(v):
    p = C.Part()
    s = v['h']

    def S(x, y, z):
        return Vector((x * s, y * s, z * s))
    # shoes
    for sx in (1, -1):
        p.rbox(S(sx * 0.090, -0.035, 0.035), (0.105 * s, 0.25 * s, 0.07 * s), 0.03 * s, 1,
               'SKY_Rubber')
    # legs (tapered capsules)
    for sx in (1, -1):
        p.tube([S(sx * 0.090, 0.0, 0.06), S(sx * 0.092, 0.0, 0.45), S(sx * 0.098, 0.0, 0.84)],
               [0.058 * s, 0.066 * s, 0.078 * s], 8, v['pants'], caps='round', cap_segs=2)
    # torso: horizontal slices (hips -> waist -> chest -> shoulders), pants colour below the
    # waist so the trousers run up under the top; a coat extends the slices down to the knee
    def sl(z, hw, hd, yc=0.0):
        return (z * s, (yc - hd) * s, (yc + hd) * s, hw * s)
    secs = [sl(0.78, 0.150, 0.105), sl(0.86, 0.172, 0.118), sl(0.94, 0.165, 0.110),
            sl(1.06, 0.172, 0.118), sl(1.20, 0.192, 0.122), sl(1.31, 0.205, 0.112),
            sl(1.37, 0.170, 0.095), sl(1.41, 0.090, 0.070)]
    bands = {0: v['pants'], 1: v['pants']}
    if v['acc'] == 'coat':
        secs = [sl(0.52, 0.205, 0.140), sl(0.62, 0.198, 0.134), sl(0.78, 0.182, 0.124),
                sl(0.92, 0.170, 0.116), sl(0.97, 0.170, 0.116)] + secs[3:]
        bands = {3: v['acc_mat']}           # coat belt
        # scarf
        p.torus(0.078 * s, 0.03 * s, 14, 6, v['acc_mat'], matrix=Matrix.Translation(S(0, 0, 1.40)))
        p.tube([S(0.045, -0.075, 1.39), S(0.055, -0.115, 1.24)], 0.026 * s, 6, v['acc_mat'],
               caps='round', cap_segs=1, scale_xy=(1.6, 0.6))
    C.loft_z(p, secs, 16, v['top'], n=2.6, band_mats=bands)
    # neck + head (no face). The head's pole axis is tilted back so its latitude rings give a
    # clean hairline (high at the brow, low at the nape); hair faces are pushed out slightly.
    p.cylinder(0.048 * s, 0.10 * s, 10, v['skin'], matrix=Matrix.Translation(S(0, 0, 1.38)))
    hc = S(0, 0.0, 1.565)
    Mh = Matrix.Translation(hc) @ Matrix.Rotation(radians(-28), 4, 'X')
    vs, fs = p.superellipsoid(Vector((0, 0, 0)), (0.100 * s, 0.112 * s, 0.128 * s), 0.85, 0.9,
                              18, 14, v['skin'], matrix=Mh)
    Mi = Mh.inverted()
    line = {'short': 0.030, 'cap': 0.048, 'bun': 0.018}[v['style']]
    hair_mat = 'SKY_Ink' if v['style'] == 'cap' else v['hair']
    hair_faces = [f for f in fs if (Mi @ f.calc_center_median()).z > line * s]
    p.assign(hair_faces, hair_mat)
    puff = 0.010 if v['style'] != 'cap' else 0.008
    hv = {x for f in hair_faces for x in f.verts}
    for x in hv:
        d = (x.co - hc).normalized()
        x.co += d * puff * s
    if v['style'] == 'cap':
        p.rbox(Mh @ Vector((0, -0.112 * s, 0.035 * s)), (0.15 * s, 0.10 * s, 0.016 * s), 0.008 * s,
               1, 'SKY_Ink')
    if v['style'] == 'bun':
        p.superellipsoid(S(0, 0.095, 1.660), (0.052 * s, 0.048 * s, 0.050 * s), 1.0, 1.0, 10, 6,
                         v['hair'])
    # arms + hands
    for sx in (1, -1):
        hold = (v['acc'] == 'suitcase' and sx < 0)
        hand = S(sx * 0.255, -0.01, 0.84) if not hold else S(sx * 0.27, 0.0, 0.80)
        p.tube([S(sx * 0.215, 0.0, 1.33), S(sx * 0.255, 0.01, 1.08), hand + Vector((0, 0, 0.05 * s))],
               [0.056 * s, 0.050 * s, 0.045 * s], 8, v['top'], caps='round', cap_segs=1)
        p.superellipsoid(hand, (0.040 * s, 0.035 * s, 0.050 * s), 1.0, 1.0, 8, 6, v['skin'])
    if v['acc'] == 'backpack':
        p.rbox(S(0, 0.185, 1.13), (0.26 * s, 0.13 * s, 0.34 * s), 0.05 * s, 2, v['acc_mat'])
        for sx in (1, -1):
            p.tube([S(sx * 0.11, 0.12, 1.34), S(sx * 0.12, 0.0, 1.405), S(sx * 0.125, -0.118, 1.31),
                    S(sx * 0.128, -0.132, 1.13), S(sx * 0.122, -0.128, 0.99)], 0.016 * s, 5,
                   'SKY_Ink', caps='round', cap_segs=1)
    if v['acc'] == 'suitcase':
        c = S(-0.30, 0.0, 0.42)
        p.rbox(c, (0.14 * s, 0.42 * s, 0.50 * s), 0.04 * s, 2, v['acc_mat'])
        p.tube([c + S(0.0, -0.05, 0.25), c + S(0.0, -0.05, 0.33), c + S(0.0, 0.05, 0.33),
                c + S(0.0, 0.05, 0.25)], 0.012 * s, 5, 'SKY_Brass', caps='round', cap_segs=1)
        p.box(c + S(0.072, 0.0, 0.0), (0.008 * s, 0.30 * s, 0.03 * s), 'SKY_Brass')
    return p


def build(name):
    C.reset_scene()
    root = C.new_empty(name, None, (0, 0, 0), size=0.3)
    p = figure(VARIANTS[name])
    body = C.merge_to_object("Body", [p.to_temp()], pivot=(0, 0, 0), parent=root, sharp_deg=50)
    C.bake_ao([body], dist=0.12, samples=40, floor=0.45, ground_z=0.0)
    return root


if __name__ == "__main__":
    for name in VARIANTS:
        root = build(name)
        C.summary(root)
        C.export_fbx(root, os.path.join(C.MODELS, 'Characters', name + '.fbx'))
        if RENDER:
            C.render_previews(name, root, res=(720, 900), samples=96, ground_z=0.0, lens=60,
                              margin=1.15, views=(("fl", 38, 12), ("br", -142, 14)))
