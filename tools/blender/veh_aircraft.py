"""'The last flight' - original small twin-turboprop commuter plane for SKYFOLD.

Original procedural model (Awaiz Ahmed / Team Kanban), not AI-generated, no real type copied.
    blender -b --factory-startup -P tools/blender/veh_aircraft.py [-- --no-render]

~13 m long, 16 m span, high wing, T-tail, fixed tricycle gear, pearl livery with a deep teal
cheatline / fin and restrained gold pinstripes (no text). Faces Blender -Y (Unity +Z),
aircraft left = Blender +X.
Hierarchy (pivots):
    aircraft (empty)        ground level under the main-gear centre
      Body                  same as root
        Door                left airstair door, pivot on its bottom (hinge) edge; opens by
                            rotating about local Unity Z (~ +125 deg swings the top outward/down)
        Prop_L / Prop_R     hub centres; spin about the forward axis (local Unity Z); 4 blades
        LIGHT_nav_L         left wingtip   (red-ish lens, SKY_Coral)
        LIGHT_nav_R         right wingtip  (green-ish lens, SKY_TealGlow)
        LIGHT_beacon        top of the fuselage
        LIGHT_landing       nose
      ANCHOR_door           outside the door at ground level
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C
import veh_common as V
from chars_common import Vector, Matrix, Euler, radians, sin, cos, pi, sqrt
import bpy

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS
OUT = os.path.join(C.MODELS, 'Vehicles', 'aircraft.fbx')

PEARL, TEAL, GOLD, INK, GLASS, LIGHT, CORAL, GLOW, RUBBER, BRASS, METAL = (
    'SKY_Pearl', 'SKY_Teal', 'SKY_Gold', 'SKY_Ink', 'SKY_Glass', 'SKY_Light', 'SKY_Coral',
    'SKY_TealGlow', 'SKY_Rubber', 'SKY_Brass', 'SKY_Metal')

# ---------------------------------------------------------------------------- fuselage
Y_NOSE, Y_CAB0, Y_CAB1, Y_TAIL = -5.82, -3.95, 2.35, 7.25
A_CAB, ZC_CAB, HT_CAB, HB_CAB = 0.95, 1.78, 0.96, 0.98
N_SEC = 2.25


def sp(x, e):
    return math.copysign(abs(x) ** e, x)


def section(y):
    """(zc, a, ht, hb) of the fuselage cross-section at y."""
    if y <= Y_CAB0:
        u = min(1.0, (Y_CAB0 - y) / (Y_CAB0 - Y_NOSE))
        a = A_CAB * (1 - u ** 2.3) ** (1 / 2.3)
        top = (ZC_CAB + HT_CAB) - 0.95 * u ** 1.7          # windscreen slope
        bot = (ZC_CAB - HB_CAB) + 0.62 * u ** 2.2          # chin
        k = (1 - u ** 2.3) ** (1 / 2.3)
        zc = (top + bot) / 2
        return zc, a, (top - zc) * k, (zc - bot) * k
    if y <= Y_CAB1:
        return ZC_CAB, A_CAB, HT_CAB, HB_CAB
    u = min(1.0, (y - Y_CAB1) / (Y_TAIL - Y_CAB1))
    top = (ZC_CAB + HT_CAB) - 0.10 * u
    bot = (ZC_CAB - HB_CAB) + 1.55 * u ** 1.35
    zc = (top + bot) / 2
    k = (1 - u ** 2.2) ** (1 / 2.2)
    a = A_CAB * k * (1 - 0.35 * u)
    return zc, a, (top - zc) * k ** 0.2, (zc - bot) * k ** 0.2


def fus_pt(y, phi, off=0.0):
    """phi: 0 = +X (left flank), pi/2 = top, pi = -X, 3pi/2 = belly."""
    zc, a, ht, hb = section(y)
    e = 2.0 / N_SEC
    c, s = cos(phi), sin(phi)
    x = a * sp(c, e)
    z = zc + (ht if s > 0 else hb) * sp(s, e)
    p = Vector((x, y, z))
    if off:
        n = (p - Vector((0, y, zc)))
        n = Vector((n.x / max(a, 1e-4) ** 2, 0, n.z / max(ht if s > 0 else hb, 1e-4) ** 2))
        if n.length > 1e-9:
            p += n.normalized() * off
    return p


def phi_at_z(y, z, side=1):
    """Angle on the +X (side=1) or -X flank where the surface reaches height z."""
    zc, a, ht, hb = section(y)
    h = ht if z >= zc else hb
    u = max(-1.0, min(1.0, (z - zc) / max(h, 1e-6)))
    s = sp(u, N_SEC / 2.0)
    ph = math.asin(max(-1.0, min(1.0, s)))
    return ph if side > 0 else pi - ph


LIVERY_Y = (-5.05, 6.90)      # cheatline runs from under the cockpit to the fin root


def ring_angles(y):
    """36 column angles per ring. Columns follow the cheatline / pinstripe heights on both
    flanks so the livery is exact face colouring (no floating decals)."""
    lo, hi = CHEAT_LO(y), CHEAT_HI(y)
    a1 = phi_at_z(y, lo, 1)
    a2 = phi_at_z(y, hi, 1)
    a3 = phi_at_z(y, hi + 0.035, 1)
    a4 = phi_at_z(y, hi + 0.075, 1)
    lim0, lim1 = radians(-62), radians(70)
    a1 = min(max(a1, lim0), lim1 - 0.20)
    a2 = min(max(a2, a1 + 0.05), lim1 - 0.10)
    a3 = max(a3, a2 + 0.02)
    a4 = max(a4, a3 + 0.02)

    def arc(a, b, n):
        return [a + (b - a) * k / n for k in range(n)]
    left = arc(-pi / 2, a1, 8) + arc(a1, a2, 2) + arc(a2, a3, 1) + arc(a3, a4, 1) + arc(a4, pi / 2, 6)
    right = arc(pi / 2, pi - a4, 6) + arc(pi - a4, pi - a3, 1) + arc(pi - a3, pi - a2, 1) + \
        arc(pi - a2, pi - a1, 2) + arc(pi - a1, 1.5 * pi, 8)
    return left + right


TEAL_COLS, GOLD_COLS = (8, 9, 26, 27), (11, 24)


def fuselage(part):
    ys = []
    # dense at the nose and the tail, coarse along the cabin
    for k in range(1, 13):
        u = 1 - (k / 12) ** 1.6
        ys.append(Y_CAB0 - (Y_CAB0 - Y_NOSE) * u)
    for k in range(1, 8):
        ys.append(Y_CAB0 + (Y_CAB1 - Y_CAB0) * k / 7)
    for k in range(1, 13):
        u = (k / 12) ** 1.15
        ys.append(Y_CAB1 + (Y_TAIL - Y_CAB1) * u * 0.985)
    # make sure a ring sits exactly where the livery starts / ends
    ys = sorted(set([round(y, 5) for y in ys] + list(LIVERY_Y)))
    rings = [[fus_pt(y, ph) for ph in ring_angles(y)] for y in ys]
    nphi = len(rings[0])
    zc0 = section(Y_NOSE + 0.001)[0]
    zc1 = section(Y_TAIL - 0.02)[0]
    vr, fs = part.grid(rings, PEARL, True, Vector((0, Y_NOSE, zc0)), Vector((0, Y_TAIL, zc1)))
    for i in range(len(rings) - 1):
        ym = (ys[i] + ys[i + 1]) / 2
        if not (LIVERY_Y[0] <= ym <= LIVERY_Y[1]):
            continue
        for j in TEAL_COLS:
            part.assign([fs[i * nphi + j]], TEAL)
        for j in GOLD_COLS:
            part.assign([fs[i * nphi + j]], GOLD)


def strip(part, y0, y1, z_lo, z_hi, mat, side, off, ny=24):
    """Conformal livery strip on one flank between heights z_lo(y)..z_hi(y)."""
    rows = []
    for i in range(ny + 1):
        y = y0 + (y1 - y0) * i / ny
        a, b = phi_at_z(y, z_lo(y), side), phi_at_z(y, z_hi(y), side)
        rows.append([fus_pt(y, a, off), fus_pt(y, (a + b) / 2, off), fus_pt(y, b, off)])
    bm = part.bm
    vr = [[bm.verts.new(p) for p in r] for r in rows]
    faces = []
    for i in range(ny):
        for j in range(2):
            q = (vr[i][j], vr[i + 1][j], vr[i + 1][j + 1], vr[i][j + 1])
            if side < 0:
                q = q[::-1]
            faces.append(bm.faces.new(q))
    part.assign(faces, mat)
    return faces


def window(part, y, z, w, h, side, mats=(INK, GLASS), r=0.07):
    """Rounded cabin window: dark frame + glass pane, conformal to the fuselage."""
    for (mat, off, grow) in ((mats[0], 0.006, 0.05), (mats[1], 0.011, 0.0)):
        ol = V.rounded_rect(w + grow, h + grow, r + grow / 2, 2)
        pts = [fus_pt(y + dy, phi_at_z(y + dy, z + dz, side), off) for (dy, dz) in ol]
        c = fus_pt(y, phi_at_z(y, z, side), off + 0.002)
        bm = part.bm
        cv = bm.verts.new(c)
        vs = [bm.verts.new(p) for p in pts]
        fs = []
        for i in range(len(vs)):
            tri = (vs[i], vs[(i + 1) % len(vs)], cv)
            if side < 0:
                tri = tri[::-1]
            fs.append(bm.faces.new(tri))
        part.assign(fs, mat)


def cockpit(part):
    """Dark cockpit mask with four glass panes on the upper nose."""
    def patch(y0, y1, p0, p1, mat, off, ny=5, npx=6):
        rows = []
        for i in range(ny + 1):
            y = y0 + (y1 - y0) * i / ny
            rows.append([fus_pt(y, p0 + (p1 - p0) * j / npx, off) for j in range(npx + 1)])
        bm = part.bm
        vr = [[bm.verts.new(p) for p in r] for r in rows]
        fs = []
        for i in range(ny):
            for j in range(npx):
                fs.append(bm.faces.new((vr[i][j], vr[i + 1][j], vr[i + 1][j + 1], vr[i][j + 1])))
        part.assign(fs, mat)
    patch(-5.30, -3.80, radians(18), radians(162), INK, 0.006, ny=8, npx=14)
    for (p0, p1) in ((radians(94), radians(140)), (radians(40), radians(86))):
        patch(-5.16, -4.58, p0, p1, GLASS, 0.012)
    for (p0, p1) in ((radians(126), radians(156)), (radians(24), radians(54))):
        patch(-4.48, -3.92, p0, p1, GLASS, 0.012, ny=3, npx=3)


# ---------------------------------------------------------------------------- wing / tail
AIRFOIL = [(0.0, 0.0), (0.015, 0.040), (0.07, 0.078), (0.18, 0.104), (0.33, 0.112),
           (0.52, 0.100), (0.72, 0.068), (0.90, 0.030), (1.0, 0.006), (0.90, -0.012),
           (0.72, -0.024), (0.52, -0.034), (0.33, -0.040), (0.18, -0.040), (0.07, -0.032),
           (0.015, -0.020)]
SYM = [(0.0, 0.0), (0.02, 0.035), (0.08, 0.064), (0.20, 0.084), (0.36, 0.090), (0.56, 0.080),
       (0.76, 0.054), (0.92, 0.022), (1.0, 0.004), (0.92, -0.022), (0.76, -0.054), (0.56, -0.080),
       (0.36, -0.090), (0.20, -0.084), (0.08, -0.064), (0.02, -0.035)]
WING_Z = 2.80
WING_LE = -1.22


def wing_section(x):
    """Leading-edge y, chord, z of the wing at span station x (|x| <= 8)."""
    t = min(1.0, abs(x) / 8.0)
    chord = 1.95 - 0.80 * t
    le = WING_LE + 0.22 * t
    z = WING_Z + abs(x) * math.tan(radians(1.6))
    return le, chord, z


def wing(part):
    stations = [-8.0, -7.6, -6.6, -5.0, -3.4, -2.6, -1.8, -0.9, 0.0, 0.9, 1.8, 2.6, 3.4, 5.0, 6.6,
                7.6, 8.0]
    rings = []
    for x in stations:
        le, ch, z = wing_section(x)
        k = 1.0
        if abs(x) > 7.6:          # rounded tip: shrink the last section
            k = 0.55
        thick = 1.0 if abs(x) < 7.6 else 0.55
        ring = [Vector((x, le + ch * (u * k + (1 - k) * 0.30), z + ch * v * thick)) for (u, v) in AIRFOIL]
        rings.append(ring)
    vr, fs = part.grid(rings, PEARL, True, None, None)
    n = len(AIRFOIL)
    # close the tips
    for ring in (vr[0], vr[-1]):
        c = sum((v.co for v in ring), Vector()) / n
        cv = part.bm.verts.new(c)
        for i in range(n):
            part.assign([part.bm.faces.new((ring[i], ring[(i + 1) % n], cv))], TEAL)
    # teal wingtips (last two spans)
    for b in (0, 1, len(stations) - 3, len(stations) - 2):
        part.assign(fs[b * n:(b + 1) * n], TEAL)


def tail(part):
    # vertical fin (teal), swept, airfoil section in the XY plane
    fin = []

    def fin_sec(z):
        t = (z - 2.95) / (4.98 - 2.95)
        return 4.75 + (6.02 - 4.75) * t, 2.25 + (1.30 - 2.25) * t
    levels = [(2.55, 4.15, 2.70), (2.95,) + fin_sec(2.95), (3.62,) + fin_sec(3.62),
              (3.78,) + fin_sec(3.78), (4.98,) + fin_sec(4.98)]
    for (z, le, ch) in levels:
        th = 0.11 if z < 4.9 else 0.10
        fin.append([Vector((v * ch * th / 0.18, le + u * ch, z)) for (u, v) in SYM])
    vr, fs = part.grid(fin, TEAL, True, None, None)
    n = len(SYM)
    c = sum((v.co for v in vr[-1]), Vector()) / n
    cv = part.bm.verts.new(c)
    for i in range(n):
        part.assign([part.bm.faces.new((vr[-1][i], vr[-1][(i + 1) % n], cv))], TEAL)
    # restrained gold band across the fin
    part.assign(fs[2 * n:3 * n], GOLD)
    # horizontal stabiliser on top of the fin (pearl, teal tips)
    stab = []
    for x in (-2.9, -2.6, -1.5, -0.5, 0.0, 0.5, 1.5, 2.6, 2.9):
        t = abs(x) / 2.9
        ch = 1.30 - 0.50 * t
        le = 6.00 + 0.38 * t
        th = 0.12 if abs(x) < 2.6 else 0.07
        k = 1.0 if abs(x) < 2.6 else 0.7
        stab.append([Vector((x, le + ch * (u * k + (1 - k) * 0.3), 5.02 + v * ch * th / 0.18))
                     for (u, v) in SYM])
    vr, fs = part.grid(stab, PEARL, True, None, None)
    for ring in (vr[0], vr[-1]):
        c = sum((v.co for v in ring), Vector()) / n
        cv = part.bm.verts.new(c)
        for i in range(n):
            part.assign([part.bm.faces.new((ring[i], ring[(i + 1) % n], cv))], TEAL)
    part.assign(fs[0:n] + fs[(len(stab) - 2) * n:(len(stab) - 1) * n], TEAL)
    # fin-top bullet fairing
    part.superellipsoid(Vector((0, 6.55, 5.02)), (0.13, 0.95, 0.13), 1.0, 1.0, 12, 8, PEARL,
                        pole_axis='Y')


NAC_X, NAC_Z = 2.60, 2.62
HUB_Y = -3.18


def nacelle(part, sx):
    x = sx * NAC_X
    ys = [-2.98, -2.90, -2.62, -2.10, -1.30, -0.40, 0.40, 1.00, 1.30]
    rr = [0.30, 0.36, 0.40, 0.41, 0.40, 0.37, 0.28, 0.16, 0.0]
    rings = []
    for y, r in zip(ys, rr):
        if r <= 0:
            continue
        rings.append([Vector((x + r * cos(2 * pi * j / 18), y, NAC_Z + r * 1.06 * sin(2 * pi * j / 18)))
                      for j in range(18)])
    vr, fs = part.grid(rings, PEARL, True, Vector((x, -2.99, NAC_Z)), Vector((x, 1.30, NAC_Z)))
    part.assign(fs[0:18 * 2], TEAL)                     # teal cowl ring at the front
    part.assign(fs[(len(rings) - 1) * 18:len(rings) * 18], INK)   # front face behind spinner
    # intake scoop under the spinner + exhaust stub on the outboard side
    part.superellipsoid(Vector((x, -2.55, NAC_Z - 0.40)), (0.16, 0.32, 0.09), 0.6, 0.6, 10, 6, INK)
    part.tube([Vector((x + sx * 0.36, -1.40, NAC_Z - 0.05)), Vector((x + sx * 0.44, -0.70, NAC_Z - 0.06))],
              0.07, 8, INK, caps='flat')


def gear(part):
    # main gear: sponsons, struts, wheel spats, wheels
    for sx in (1, -1):
        part.superellipsoid(Vector((sx * 0.86, 0.05, 1.02)), (0.28, 0.95, 0.24), 0.8, 0.8, 14, 8, PEARL)
        part.tube([Vector((sx * 0.90, 0.05, 0.98)), Vector((sx * 1.47, 0.05, 0.70))], 0.075, 8,
                  INK, caps='flat')
        vs, fs = part.superellipsoid(Vector((sx * 1.55, 0.06, 0.47)), (0.17, 0.66, 0.40), 0.9, 0.9,
                                     14, 10, PEARL, pole_axis='Y')
        part.assign([f for f in fs if f.calc_center_median().z < 0.30], TEAL)
    part.tube([Vector((0, -4.42, 1.05)), Vector((0, -4.44, 0.55))], 0.065, 8, INK, caps='flat')
    vs, fs = part.superellipsoid(Vector((0, -4.45, 0.38)), (0.14, 0.52, 0.32), 0.9, 0.9, 14, 10,
                                 PEARL, pole_axis='Y')
    part.assign([f for f in fs if f.calc_center_median().z < 0.24], TEAL)


def gear_wheels(part):
    for sx in (1, -1):
        w = V.wheel_lite(Vector((sx * 1.55, 0.0, 0.38)), 0.38, 0.24, sx, seg=14)
        part.bm.from_mesh(_bm_to_mesh(w))
        _remap(part, w)
    w = V.wheel_lite(Vector((0, -4.45, 0.30)), 0.30, 0.20, 1, seg=14)
    part.bm.from_mesh(_bm_to_mesh(w))
    _remap(part, w)


_last_mesh = []


def _bm_to_mesh(p):
    me = bpy.data.meshes.new("tmpw")
    p.bm.to_mesh(me)
    _last_mesh.append((me, list(p.mats)))
    return me


def _remap(part, p):
    me, mats = _last_mesh.pop()
    n_new = len(me.polygons)
    part.bm.faces.ensure_lookup_table()
    tot = len(part.bm.faces)
    for k in range(tot - n_new, tot):
        f = part.bm.faces[k]
        f.material_index = part.mi(mats[f.material_index])
    bpy.data.meshes.remove(me)


# ---------------------------------------------------------------------------- door / props
DOOR = dict(y0=-2.95, y1=-2.17, z0=0.98, z1=2.50)


def build_door(body):
    p = C.Part()
    d = DOOR
    ny = 6
    yc = (d['y0'] + d['y1']) / 2
    lo, hi = CHEAT_LO(yc), CHEAT_HI(yc)
    zs = sorted(set([round(d['z0'] + (d['z1'] - d['z0']) * j / 6, 4) for j in range(7)] +
                    [lo, hi, hi + 0.035, hi + 0.075]))
    nz = len(zs) - 1
    outer, inner = [], []
    for j in range(nz + 1):
        z = zs[j]
        ro, ri = [], []
        for i in range(ny + 1):
            y = d['y0'] + (d['y1'] - d['y0']) * i / ny
            ph = phi_at_z(y, z, 1)
            ro.append(fus_pt(y, ph, 0.040))
            ri.append(fus_pt(y, ph, -0.010))
        outer.append(ro)
        inner.append(ri)
    bm = p.bm
    vo = [[bm.verts.new(q) for q in r] for r in outer]
    vi = [[bm.verts.new(q) for q in r] for r in inner]
    fs = []
    for j in range(nz):
        for i in range(ny):
            fs.append(bm.faces.new((vo[j][i], vo[j][i + 1], vo[j + 1][i + 1], vo[j + 1][i])))
            fs.append(bm.faces.new((vi[j][i + 1], vi[j][i], vi[j + 1][i], vi[j + 1][i + 1])))
    # rim
    for j in range(nz):
        fs.append(bm.faces.new((vo[j][0], vo[j + 1][0], vi[j + 1][0], vi[j][0])))
        fs.append(bm.faces.new((vo[j + 1][ny], vo[j][ny], vi[j][ny], vi[j + 1][ny])))
    for i in range(ny):
        fs.append(bm.faces.new((vo[0][i + 1], vo[0][i], vi[0][i], vi[0][i + 1])))
        fs.append(bm.faces.new((vo[nz][i], vo[nz][i + 1], vi[nz][i + 1], vi[nz][i])))
    p.assign(fs, PEARL)
    # livery on the door follows the fuselage cheatline heights
    for f in fs:
        c = f.calc_center_median()
        if f.normal.x > 0.5 and lo < c.z < hi:
            p.assign([f], TEAL)
        elif f.normal.x > 0.5 and hi + 0.035 < c.z < hi + 0.075:
            p.assign([f], GOLD)
    # airstair steps on the inner face (they become treads when the door is lowered)
    for k in range(4):
        z = d['z0'] + 0.30 + k * 0.32
        yc = (d['y0'] + d['y1']) / 2
        q = fus_pt(yc, phi_at_z(yc, z, 1), -0.04)
        p.box(q, (0.07, 0.66, 0.05), INK)
    # hinge barrel along the bottom edge
    yb = (d['y0'] + d['y1']) / 2
    hb = fus_pt(yb, phi_at_z(yb, d['z0'], 1), 0.012)
    p.tube([Vector((hb.x, d['y0'] + 0.04, hb.z)), Vector((hb.x, d['y1'] - 0.04, hb.z))], 0.03, 8,
           METAL, caps='flat')
    w = C.Part()
    window(w, (d['y0'] + d['y1']) / 2, 2.05, 0.30, 0.34, 1, r=0.10)
    w.transform(w.bm.verts, Matrix.Translation((0.034, 0, 0)))   # sit on the door's outer skin
    temps = [p.to_temp(recalc=True), w.to_temp(recalc=False)]
    door = C.merge_to_object("Door", temps, pivot=hb, parent=body, sharp_deg=50)
    return door, hb


def build_prop(name, sx, body):
    p = C.Part()
    hub = Vector((sx * NAC_X, HUB_Y, NAC_Z))
    # spinner (pearl with a gold tip ring) pointing forward (-Y)
    M = Matrix.Translation(hub) @ Matrix.Rotation(radians(90), 4, 'X')   # local +Z -> -Y
    vr, fs = p.lathe([(0.0, 0.42), (0.10, 0.36), (0.20, 0.24), (0.27, 0.10), (0.29, -0.02),
                      (0.29, -0.14), (0.0, -0.14)], 16, PEARL, matrix=M)
    p.assign(fs[(7 - 3) * 16:(7 - 2) * 16], GOLD)       # gold tip cap (pole fan)
    # four twisted blades (ink, coral tips) in the prop disc (XZ plane)
    for k in range(4):
        a = radians(45 + 90 * k)
        d = Vector((cos(a), 0, sin(a)))
        side = Vector((-sin(a), 0, cos(a)))
        pts, rad, sc = [], [], []
        for t in (0.20, 0.40, 0.70, 0.95, 1.13):
            pts.append(hub + d * t + Vector((0, 0.02, 0)))
        prof = [(0.055, 0.30), (0.080, 0.24), (0.085, 0.20), (0.070, 0.18), (0.045, 0.20)]
        vs, bfs = p.tube(pts, [q[0] for q in prof], 8, INK, caps='round', cap_segs=1,
                         scale_xy=[(1.0, q[1]) for q in prof], up=(0, -1, 0), twist=radians(-28))
        p.assign([f for f in bfs if (f.calc_center_median() - hub).length > 1.0], CORAL)
    temp = p.to_temp()
    return C.merge_to_object(name, [temp], pivot=hub, parent=body, sharp_deg=50)


def CHEAT_LO(y):
    u = max(0.0, (y - 3.2) / 4.0)
    return 1.30 + 1.05 * u ** 1.4


def CHEAT_HI(y):
    u = max(0.0, (y - 3.2) / 4.0)
    return 1.62 + 0.95 * u ** 1.3


def build():
    C.reset_scene()
    root = C.new_empty("aircraft", None, (0, 0, 0), size=1.0)
    shell = C.Part()
    skin = C.Part()       # single-sided conformal livery / windows (no recalc)
    fuselage(shell)
    wing(shell)
    tail(shell)
    for sx in (1, -1):
        nacelle(shell, sx)
    gear(shell)
    gear_wheels(shell)
    # livery (teal cheatline + gold pinstripe) is coloured directly on the fuselage faces
    cockpit(skin)
    # cabin windows
    for side in (1, -1):
        ys = [-1.62, -0.86, -0.10, 0.66, 1.42, 2.18]
        if side < 0:
            ys = [-2.38] + ys
        for y in ys:
            window(skin, y, 2.02, 0.30, 0.36, side)
    # dark doorway behind the airstair door (shows when the door is lowered)
    rows = []
    for j in range(5):
        z = DOOR['z0'] + 0.03 + (DOOR['z1'] - DOOR['z0'] - 0.06) * j / 4
        rows.append([fus_pt(y, phi_at_z(y, z, 1), 0.007)
                     for y in [DOOR['y0'] + 0.03 + (DOOR['y1'] - DOOR['y0'] - 0.06) * i / 4
                               for i in range(5)]])
    V.LoftBody._sheet(skin, rows, INK)
    # lights geometry
    le, ch, z = wing_section(8.0)
    tipL = Vector((8.03, le + ch * 0.30 + 0.05, z + 0.01))
    tipR = Vector((-8.03, tipL.y, tipL.z))
    shell.superellipsoid(tipL, (0.07, 0.16, 0.06), 0.8, 0.8, 10, 6, CORAL)
    shell.superellipsoid(tipR, (0.07, 0.16, 0.06), 0.8, 0.8, 10, 6, GLOW)
    beacon = fus_pt(2.30, pi / 2, 0.0)
    shell.lathe([(0.0, 0.10), (0.06, 0.085), (0.08, 0.03), (0.09, -0.02), (0.0, -0.02)], 12, CORAL,
                matrix=Matrix.Translation(beacon))
    land = fus_pt(-5.55, radians(270), 0.0)
    V.lamp(shell, land, (0, -0.8, -0.6), 0.10, LIGHT, bezel=PEARL, depth=0.05, segs=12)
    temps = [shell.to_temp(), skin.to_temp(recalc=False)]
    body = C.merge_to_object("Body", temps, pivot=(0, 0, 0), parent=root, sharp_deg=48)
    door, hinge = build_door(body)
    pl = build_prop("Prop_L", 1, body)
    pr = build_prop("Prop_R", -1, body)
    C.new_empty("LIGHT_nav_L", body, tipL + Vector((0.05, 0, 0)), size=0.3)
    C.new_empty("LIGHT_nav_R", body, tipR - Vector((0.05, 0, 0)), size=0.3)
    C.new_empty("LIGHT_beacon", body, beacon + Vector((0, 0, 0.10)), size=0.3)
    C.new_empty("LIGHT_landing", body, land + Vector((0, -0.03, -0.02)), size=0.3)
    C.new_empty("ANCHOR_door", root, (2.45, (DOOR['y0'] + DOOR['y1']) / 2, 0.0), size=0.5)
    C.bake_ao([body, door, pl, pr], dist=0.9, samples=40, floor=0.40)
    return root


if __name__ == "__main__":
    root = build()
    C.summary(root)
    C.export_fbx(root, OUT)
    if RENDER:
        C.render_previews("aircraft", root, res=(960, 720), samples=128, ground_z=0.0, lens=45,
                          margin=1.06)
