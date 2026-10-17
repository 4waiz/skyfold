"""'The last flight' - original small twin-turboprop commuter plane for SKYFOLD.

Original procedural model (Awaiz Ahmed / Team Kanban), not AI-generated, no real type copied.
    blender -b --factory-startup -P tools/blender/veh_aircraft.py [-- --no-render]

~13 m long, 16 m span, high wing, T-tail, tricycle gear, pearl livery with a deep teal
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
Detail pass: grooved fuselage panel lines, livery as exact face colouring, recessed framed
cockpit glazing with an anti-glare panel, recessed cabin windows (glass glows when powered),
emergency-exit and cargo-door outlines, flush rounded airstair door in a dark door frame with
handle, window, treads and handrails; wing with real flap / aileron gaps, flap-track fairings,
wingtip light housings and strobes; T-tail with rudder / elevator gaps, dorsal fillet and
static wicks; nacelles with inlet lips, chin intakes, exhaust stacks and louvres; twisted
4-blade propellers with root cuffs and coral tips; tricycle gear with oleo struts, torque
links, gear doors and dished wheels; beacons, landing light, blade antennas, pitot tubes.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C
import veh_common as V
from veh_common import (frame, T, rot_x, rot_y, sweep, slab, lathe_m, tile, surface_skin,
                        surface_patch, ccw, densify2, poly_loop, rr_lathe)
from chars_common import Vector, Matrix, Euler, radians, sin, cos, pi, sqrt
import bpy, bmesh

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS
OUT = os.path.join(C.MODELS, 'Vehicles', 'aircraft.fbx')

PEARL, TEAL, GOLD, INK, GLASS, LIGHT, CORAL, GLOW, RUBBER, BRASS, METAL = (
    'SKY_Pearl', 'SKY_Teal', 'SKY_Gold', 'SKY_Ink', 'SKY_Glass', 'SKY_Light', 'SKY_Coral',
    'SKY_TealGlow', 'SKY_Rubber', 'SKY_Brass', 'SKY_Metal')

# gameplay points (unchanged from the previous model, Blender coordinates)
NAV_L = Vector((8.08, -0.605, 3.0335))
NAV_R = Vector((-8.08, -0.605, 3.0335))
BEACON = Vector((0.0, 2.30, 2.84))
LANDING = Vector((0.0, -5.58, 1.3767))
ANCHOR_DOOR = Vector((2.45, -2.56, 0.0))

# ---------------------------------------------------------------------------- fuselage
Y_NOSE, Y_CAB0, Y_CAB1, Y_TAIL = -5.82, -3.95, 2.35, 7.25
A_CAB, ZC_CAB, HT_CAB, HB_CAB = 0.95, 1.78, 0.96, 0.98
N_SEC = 2.25
GROOVES = (-4.62, -3.66, -2.02, -0.52, 0.98, 2.47, 4.30, 6.08)   # panel joints (y)


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


def fus_n(y, phi):
    return (fus_pt(y, phi, 0.01) - fus_pt(y, phi)).normalized()


def phi_at_z(y, z, side=1):
    """Angle on the +X (side=1) or -X flank where the surface reaches height z."""
    zc, a, ht, hb = section(y)
    h = ht if z >= zc else hb
    u = max(-1.0, min(1.0, (z - zc) / max(h, 1e-6)))
    s = sp(u, N_SEC / 2.0)
    ph = math.asin(max(-1.0, min(1.0, s)))
    return ph if side > 0 else pi - ph


def side_map(side, off=0.0):
    """(u = y, v = z) -> (point, normal) on a flank."""
    def m(u, v):
        ph = phi_at_z(u, v, side)
        return fus_pt(u, ph, off), fus_n(u, ph)
    return m


def polar_map(off=0.0):
    """(u = y, v = phi) -> (point, normal)."""
    def m(u, v):
        return fus_pt(u, v, off), fus_n(u, v)
    return m


LIVERY_Y = (-5.05, 6.90)      # cheatline runs from under the cockpit to the fin root


def CHEAT_LO(y):
    u = max(0.0, (y - 3.2) / 4.0)
    return 1.30 + 1.05 * u ** 1.4


def CHEAT_HI(y):
    u = max(0.0, (y - 3.2) / 4.0)
    return 1.62 + 0.95 * u ** 1.3


def ring_angles(y):
    """46 column angles per ring. Columns follow the cheatline / pinstripe heights on both
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
    left = arc(-pi / 2, a1, 10) + arc(a1, a2, 3) + arc(a2, a3, 1) + arc(a3, a4, 1) + \
        arc(a4, pi / 2, 8)
    right = arc(pi / 2, pi - a4, 8) + arc(pi - a4, pi - a3, 1) + arc(pi - a3, pi - a2, 1) + \
        arc(pi - a2, pi - a1, 3) + arc(pi - a1, 1.5 * pi, 10)
    return left + right


TEAL_COLS, GOLD_COLS = (10, 11, 12, 33, 34, 35), (14, 31)


def fuselage(part):
    ys = []
    for k in range(1, 15):
        u = 1 - (k / 14) ** 1.6
        ys.append(Y_CAB0 - (Y_CAB0 - Y_NOSE) * u)
    for k in range(1, 8):
        ys.append(Y_CAB0 + (Y_CAB1 - Y_CAB0) * k / 7)
    for k in range(1, 15):
        u = (k / 14) ** 1.15
        ys.append(Y_CAB1 + (Y_TAIL - Y_CAB1) * u * 0.985)
    ys = sorted(set([round(y, 5) for y in ys] + list(LIVERY_Y)))
    G = 0.006
    specs = [(y, 0.0) for y in ys if all(abs(y - g) > 0.05 for g in GROOVES) or y in LIVERY_Y]
    for g in GROOVES:
        specs += [(g - G, 0.0), (g, -0.0045), (g + G, 0.0)]
    specs.sort()
    rings = [[fus_pt(y, ph, off) for ph in ring_angles(y)] for (y, off) in specs]
    nphi = len(rings[0])
    zc0 = section(Y_NOSE + 0.001)[0]
    zc1 = section(Y_TAIL - 0.02)[0]
    vr, fs = part.grid(rings, PEARL, True, Vector((0, Y_NOSE, zc0)), Vector((0, Y_TAIL, zc1)))
    for i in range(len(rings) - 1):
        band = fs[i * nphi:(i + 1) * nphi]
        if specs[i][1] < 0 or specs[i + 1][1] < 0:
            part.assign(band, INK)
            continue
        ym = (specs[i][0] + specs[i + 1][0]) / 2
        if not (LIVERY_Y[0] <= ym <= LIVERY_Y[1]):
            continue
        for j in TEAL_COLS:
            part.assign([band[j]], TEAL)
        for j in GOLD_COLS:
            part.assign([band[j]], GOLD)


# ---------------------------------------------------------------------------- glazing / door
COCKPIT = [(-5.18, -4.64, 0.73, 1.50), (-5.18, -4.64, 1.64, 2.41),       # (y0, y1, phi0, phi1)
           (-4.52, -3.96, 0.42, 0.98), (-4.52, -3.96, 2.16, 2.72)]
CABIN_L = (-1.62, -0.86, -0.10, 0.66, 1.42, 2.18)
CABIN_R = (-2.38, -1.62, -0.86, -0.10, 0.66, 1.42, 2.18)
DOOR = dict(y0=-2.95, y1=-2.17, z0=0.98, z1=2.50)


def rrect_uv(u0, u1, v0, v1, r, n=2):
    cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
    return [(cu + x, cv + y) for (x, y) in V.rounded_rect(u1 - u0, v1 - v0, r, n)]


def glazing(cut, glass, frames):
    pm = polar_map()
    for (y0, y1, p0, p1) in COCKPIT:
        o = densify2(rrect_uv(y0, y1, p0, p1, 0.06, 2), 0.10, closed=True)
        o = ccw(o)
        surface_patch(cut, o, pm, 0.022, 0.10, INK, scales=(1.0, 0.66, 0.33))
        small = densify2(rrect_uv(y0 + 0.012, y1 - 0.012, p0 + 0.015, p1 - 0.015, 0.05, 2), 0.10,
                         closed=True)
        surface_skin(glass, ccw(small), pm, -0.008, GLASS, scales=(1.0, 0.66, 0.33))
        # raised ink frame round each pane
        fr = densify2(rrect_uv(y0 - 0.012, y1 + 0.012, p0 - 0.02, p1 + 0.02, 0.07, 2), 0.08,
                      closed=True)
        P = [fus_pt(u, v) for (u, v) in fr]
        N = [fus_n(u, v) for (u, v) in fr]
        V.ribbon(frames, P, N, 0.030, 0.004, 0.012, INK, closed=True)
    # anti-glare panel ahead of the windscreen
    ag = [(-5.20, 0.92), (-5.20, 2.22), (-5.36, 2.02), (-5.47, 1.571), (-5.36, 1.12)]
    surface_skin(glass, ccw(densify2(ag, 0.08, closed=True)), polar_map(), 0.0025, INK,
                 scales=(1.0, 0.5))
    # cabin windows
    for side, ys in ((1, CABIN_L), (-1, CABIN_R)):
        m = side_map(side)
        for y in ys:
            o = densify2(rrect_uv(y - 0.15, y + 0.15, 1.84, 2.20, 0.09, 2), 0.09, closed=True)
            surface_patch(cut, ccw(o), m, 0.020, 0.10, INK, scales=(1.0, 0.5))
            s = densify2(rrect_uv(y - 0.138, y + 0.138, 1.852, 2.188, 0.08, 2), 0.09, closed=True)
            surface_skin(glass, ccw(s), m, -0.007, GLASS, scales=(1.0, 0.5))
    # doorway: dark frame the flush door closes into
    d = DOOR
    o = densify2(rrect_uv(d['y0'], d['y1'], d['z0'], d['z1'], 0.10, 3), 0.12, closed=True)
    surface_patch(cut, ccw(o), side_map(1), 0.040, 0.10, INK, scales=(1.0, 0.5))


def outlines(lines):
    """Emergency exits over the wing and a cargo door: thin ink seam strips."""
    for side in (1, -1):
        m = side_map(side, 0.0015)
        pts = densify2(rrect_uv(0.66 - 0.30, 0.66 + 0.30, 1.42, 2.40, 0.10, 3), 0.08,
                       closed=True)
        P, N = [], []
        for (u, v) in pts:
            p, n = m(u, v)
            P.append(p)
            N.append(n)
        V.surface_strip(lines, P, N, 0.008, 0.0, INK, closed=True)
    m = side_map(-1, 0.0015)
    pts = densify2(rrect_uv(3.05, 3.75, 1.45, 2.35, 0.08, 3), 0.08, closed=True)
    P, N = [], []
    for (u, v) in pts:
        p, n = m(u, v)
        P.append(p)
        N.append(n)
    V.surface_strip(lines, P, N, 0.008, 0.0, INK, closed=True)


def build_door(body):
    """Flush airstair door: livery-aligned rows, rounded corners, window, recessed handle,
    hinge barrel; inner face carries treads and brass handrails (the stair when lowered)."""
    p = C.Part()
    d = DOOR
    gap = 0.012
    y0, y1, z0, z1 = d['y0'] + gap, d['y1'] - gap, d['z0'] + gap, d['z1'] - gap
    yc = (y0 + y1) / 2
    lo, hi = CHEAT_LO(yc), CHEAT_HI(yc)
    rc = 0.09
    zs = sorted(set([round(z0 + (z1 - z0) * j / 8, 4) for j in range(9)] +
                    [lo, hi, hi + 0.035, hi + 0.075, z0 + rc * 0.3, z1 - rc * 0.3]))
    ny = 8

    def yspan(z):
        dz = 0.0
        if z < z0 + rc:
            dz = z0 + rc - z
        elif z > z1 - rc:
            dz = z - (z1 - rc)
        cut_ = rc - sqrt(max(0.0, rc * rc - dz * dz))
        return y0 + cut_, y1 - cut_
    bm = p.bm
    vo, vi = [], []
    for z in zs:
        a, b = yspan(z)
        ro, ri = [], []
        for i in range(ny + 1):
            y = a + (b - a) * i / ny
            ph = phi_at_z(y, z, 1)
            ro.append(bm.verts.new(fus_pt(y, ph, -0.004)))
            ri.append(bm.verts.new(fus_pt(y, ph, -0.030)))
        vo.append(ro)
        vi.append(ri)
    nz = len(zs) - 1
    fs = []
    for j in range(nz):
        for i in range(ny):
            fs.append(bm.faces.new((vo[j][i], vo[j][i + 1], vo[j + 1][i + 1], vo[j + 1][i])))
            fs.append(bm.faces.new((vi[j][i + 1], vi[j][i], vi[j + 1][i], vi[j + 1][i + 1])))
    rim = []
    for j in range(nz):
        rim.append(bm.faces.new((vo[j][0], vo[j + 1][0], vi[j + 1][0], vi[j][0])))
        rim.append(bm.faces.new((vo[j + 1][ny], vo[j][ny], vi[j][ny], vi[j + 1][ny])))
    for i in range(ny):
        rim.append(bm.faces.new((vo[0][i + 1], vo[0][i], vi[0][i], vi[0][i + 1])))
        rim.append(bm.faces.new((vo[nz][i], vo[nz][i + 1], vi[nz][i + 1], vi[nz][i])))
    p.assign(fs + rim, PEARL)
    for f in fs:
        c = f.calc_center_median()
        f.normal_update()
        if f.normal.x > 0.3 and lo < c.z < hi:
            p.assign([f], TEAL)
        elif f.normal.x > 0.3 and hi + 0.035 < c.z < hi + 0.075:
            p.assign([f], GOLD)
    p.assign(rim, INK)
    # window: dark backing + glass + pearl frame ring
    m = side_map(1)
    wo = densify2(rrect_uv(yc - 0.15, yc + 0.15, 1.88, 2.22, 0.10, 3), 0.07, closed=True)
    surface_skin(p, ccw(wo), side_map(1, 0.0005), 0.0, INK, scales=(1.0,))
    surface_skin(p, ccw(wo), side_map(1, 0.0035), 0.0, GLASS, scales=(1.0, 0.5))
    fr = densify2(rrect_uv(yc - 0.162, yc + 0.162, 1.868, 2.232, 0.11, 3), 0.07, closed=True)
    P = [m(u, v)[0] for (u, v) in fr]
    N = [m(u, v)[1] for (u, v) in fr]
    V.ribbon(p, P, N, 0.022, 0.006, 0.006, PEARL, closed=True)
    # recessed handle (ink pocket + metal lever) near the aft edge
    hp, hn = m(y1 - 0.12, 1.62)
    Mh = frame(hp, hn, (0, 0, 1))
    slab(p, 0.050, 0.15, 0.010, 0.020, 0.003, INK, M=Mh, nc=2, ne=1)
    p.tube([Mh @ Vector((0, -0.05, 0.010)), Mh @ Vector((0, 0.05, 0.012))], 0.007, 8, METAL,
           caps='round', cap_segs=1)
    # inner face: treads with rubber pads + brass handrails
    for k in range(4):
        z = d['z0'] + 0.30 + k * 0.32
        q = fus_pt(yc, phi_at_z(yc, z, 1), -0.060)
        p.rbox(q, (0.07, 0.64, 0.05), 0.012, 1, INK)
        p.rbox(q + Vector((-0.036, 0, 0.0)), (0.008, 0.58, 0.040), 0.003, 1, RUBBER)
    for yy in (y0 + 0.035, y1 - 0.035):
        pts = [fus_pt(yy, phi_at_z(yy, z, 1), -0.085) for z in (z0 + 0.10, (z0 + z1) / 2,
                                                                  z1 - 0.12)]
        p.tube(pts, 0.011, 8, BRASS, caps='round', cap_segs=1)
        for z in (z0 + 0.10, z1 - 0.12):
            p.tube([fus_pt(yy, phi_at_z(yy, z, 1), -0.085), fus_pt(yy, phi_at_z(yy, z, 1), -0.03)],
                   0.007, 6, BRASS, caps='flat')
    # hinge barrel along the bottom edge (pivot axis)
    yb = (d['y0'] + d['y1']) / 2
    hb = fus_pt(yb, phi_at_z(yb, d['z0'], 1), 0.012)
    p.tube([Vector((hb.x, d['y0'] + 0.05, hb.z)), Vector((hb.x, d['y1'] - 0.05, hb.z))], 0.028,
           10, METAL, caps='round', cap_segs=1)
    temps = [p.to_temp(recalc=True)]
    door = C.merge_to_object("Door", temps, pivot=hb, parent=body, sharp_deg=50)
    return door, hb


# ---------------------------------------------------------------------------- wing / tail
def foil(n, tc, m=0.0, pp=0.4, u0=0.0, u1=1.0):
    """Cosine-spaced NACA-style section between u0 and u1: (upper, lower) (u, v) lists."""
    us = [u0 + (u1 - u0) * (1 - cos(pi * k / (n - 1))) / 2 for k in range(n)]

    def yt(u):
        u = max(u, 0.0)
        return 5 * tc * (0.2969 * sqrt(u) - 0.1260 * u - 0.3516 * u ** 2 + 0.2843 * u ** 3 -
                         0.1036 * u ** 4)

    def yc(u):
        if m == 0:
            return 0.0
        if u < pp:
            return m / pp ** 2 * (2 * pp * u - u * u)
        return m / (1 - pp) ** 2 * ((1 - 2 * pp) + 2 * pp * u - u * u)
    return [(u, yc(u) + yt(u)) for u in us], [(u, yc(u) - yt(u)) for u in us]


def box_ring(n, tc, m, us):
    """Closed section of the fixed part (LE .. spar at us)."""
    up, lo = foil(n, tc, m, u1=us)
    return up[::-1] + lo[1:]


def surf_ring(n, tc, m, uc):
    """Closed section of a control surface (rounded nose at uc .. trailing edge)."""
    up, lo = foil(n, tc, m, u0=uc, u1=1.0)
    t = (up[0][1] - lo[0][1]) / 2
    cv = (up[0][1] + lo[0][1]) / 2
    arc = [(uc - t * sin(radians(a)), cv + t * cos(radians(a))) for a in (45, 90, 135)]
    return up[::-1] + arc + lo[:-1]


WING_Z = 2.80
WING_LE = -1.22
WTC, WCAM = 0.15, 0.022
SPAR = 0.735
HINGE = 0.755


def wing_section(x):
    """Leading-edge y, chord, z of the wing at span station x (|x| <= 8)."""
    t = min(1.0, abs(x) / 8.0)
    chord = 1.95 - 0.80 * t
    le = WING_LE + 0.22 * t
    z = WING_Z + abs(x) * math.tan(radians(1.6))
    return le, chord, z


def wing_pt(x, u, v):
    le, ch, z = wing_section(x)
    return Vector((x, le + u * ch, z + v * ch))


def loft_x(part, xs, ring, mat, mapf, teal_from=None):
    rings = [[mapf(x, u, v) for (u, v) in ring] for x in xs]
    c0 = sum(rings[0], Vector()) / len(ring)
    c1 = sum(rings[-1], Vector()) / len(ring)
    vr, fs = part.grid(rings, mat, True, c0, c1)
    if teal_from is not None:
        for f in fs:
            if abs(f.calc_center_median().x) > teal_from:
                part.assign([f], TEAL)
    return fs


def wing(part):
    xs = [-7.6, -7.1, -6.6, -5.6, -4.65, -3.6, -3.05, -2.6, -2.15, -1.5, -0.8, 0.0, 0.8, 1.5,
          2.15, 2.6, 3.05, 3.6, 4.65, 5.6, 6.6, 7.1, 7.6]
    loft_x(part, xs, box_ring(13, WTC, WCAM, SPAR), PEARL, wing_pt, teal_from=6.6)
    cs = surf_ring(7, WTC, WCAM, HINGE)
    for sx in (1, -1):
        for (a, b, n) in ((1.00, 2.18, 2), (3.02, 4.62, 2), (4.68, 7.48, 4)):
            xs2 = [sx * (a + (b - a) * k / n) for k in range(n + 1)]
            if sx < 0:
                xs2 = xs2[::-1]
            loft_x(part, xs2, cs, PEARL, wing_pt, teal_from=6.6)
        # rounded teal wingtip with the nav-light housing and a white strobe
        tip = []
        for (x, k) in ((7.6, 1.0), (7.78, 0.93), (7.92, 0.78), (8.0, 0.52)):
            le, ch, z = wing_section(x)
            ring = []
            for (u, v) in box_ring(13, WTC, WCAM, 0.999):
                uu = 0.30 + (u - 0.30) * k
                ring.append(Vector((sx * x, le + uu * ch, z + v * ch * k)))
            tip.append(ring)
        if sx < 0:
            tip = tip
        c1 = sum(tip[-1], Vector()) / len(tip[-1])
        vr, fs = part.grid(tip, TEAL, True, None, c1)
        nav = NAV_L if sx > 0 else NAV_R
        lens = CORAL if sx > 0 else GLOW
        part.superellipsoid(nav - Vector((sx * 0.05, 0, 0)), (0.075, 0.17, 0.062), 0.7, 0.7, 14,
                            8, lens)
        part.superellipsoid(nav - Vector((sx * 0.06, 0, 0)) + Vector((0, 0, -0.004)),
                            (0.06, 0.20, 0.045), 0.7, 0.7, 12, 6, PEARL)
        le, ch, z = wing_section(7.9)
        part.superellipsoid(Vector((sx * 7.93, le + ch * 0.80, z + 0.01)), (0.03, 0.06, 0.022),
                            0.8, 0.8, 8, 6, LIGHT)
        # flap-track fairings (canoes) under the hinge line
        for x in (1.6, 3.8, 5.9):
            le, ch, z = wing_section(x)
            c = Vector((sx * x, le + ch * 0.80, z - 0.035 * ch - 0.045))
            part.superellipsoid(c, (0.045, 0.42, 0.075), 0.8, 0.9, 10, 6, PEARL, pole_axis='Y')
        # static wicks on the aileron trailing edge
        for x in (5.4, 6.4, 7.3):
            le, ch, z = wing_section(x)
            a = Vector((sx * x, le + ch * 0.99, z + 0.003 * ch))
            part.tube([a, a + Vector((0, 0.11, 0.01))], 0.0055, 5, INK, caps='flat')


def root_fairing(part):
    """Pearl saddle blending the high wing into the fuselage top."""
    pod = V.Pod([(2.42, -0.95, 0.95, 0.62), (2.60, -1.30, 1.15, 0.86), (2.72, -1.40, 1.28, 0.95),
                 (2.80, -1.28, 1.20, 0.90), (2.86, -1.05, 0.85, 0.70)], n=2.6,
                step=[2, 2, 1, 1])
    pod.build(part, 28, PEARL, crown=0.004, fill=1, cap_bottom=True)


FIN_LV = (2.55, 2.95, 3.36, 3.62, 3.78, 4.20, 4.60, 4.98)


def fin_sec(z):
    if z <= 2.95:
        return 4.15 + (4.75 - 4.15) * (z - 2.55) / 0.40, 2.70 + (2.25 - 2.70) * (z - 2.55) / 0.40
    t = (z - 2.95) / (4.98 - 2.95)
    return 4.75 + (6.02 - 4.75) * t, 2.25 + (1.30 - 2.25) * t


def tail(part):
    TCF = 0.11

    def fin_pt(z, u, v):
        le, ch = fin_sec(z)
        return Vector((v * ch, le + u * ch, z))

    def mapz(z, u, v):
        return fin_pt(z, u, v)
    # fin box: z-stations, section in the XY plane
    ring = box_ring(11, TCF, 0.0, 0.70)
    rings = [[fin_pt(z, u, v) for (u, v) in ring] for z in FIN_LV]
    c1 = sum(rings[-1], Vector()) / len(ring)
    vr, fs = part.grid(rings, TEAL, True, None, c1)
    n = len(ring)
    part.assign(fs[3 * n:4 * n], GOLD)
    # rudder with the gold band continued
    rr = surf_ring(6, TCF, 0.0, 0.715)
    lv = (2.98, 3.36, 3.62, 3.78, 4.20, 4.90)
    rings = [[fin_pt(z, u, v) for (u, v) in rr] for z in lv]
    c0 = sum(rings[0], Vector()) / len(rr)
    c1 = sum(rings[-1], Vector()) / len(rr)
    vr, fs = part.grid(rings, TEAL, True, c0, c1)
    m = len(rr)
    part.assign(fs[2 * m:3 * m], GOLD)
    for z in (3.20, 4.10, 4.75):
        le, ch = fin_sec(z)
        a = Vector((0, le + ch * 0.995, z))
        part.tube([a, a + Vector((0, 0.11, 0.012))], 0.0055, 5, INK, caps='flat')
    # dorsal fillet from the spine into the fin leading edge
    fil = []
    for (z, y0, y1, w) in ((2.50, 3.10, 4.95, 0.10), (2.80, 3.95, 4.95, 0.085),
                           (3.08, 4.55, 4.98, 0.06), (3.25, 4.80, 5.00, 0.035)):
        fil.append([Vector((w * sp(cos(a), 0.7), (y0 + y1) / 2 + (y1 - y0) / 2 * sp(sin(a), 0.9),
                            z)) for a in [2 * pi * k / 12 for k in range(12)]])
    c1 = sum(fil[-1], Vector()) / 12
    part.grid(fil, TEAL, True, None, c1)
    # T-tail stabiliser (pearl, teal tips) + elevators
    def stab_pt(x, u, v):
        t = abs(x) / 2.9
        ch = 1.30 - 0.50 * t
        le = 6.00 + 0.38 * t
        th = 1.0 if abs(x) < 2.6 else 0.6
        k = 1.0 if abs(x) < 2.6 else 0.7
        uu = u * k + (1 - k) * 0.3
        return Vector((x, le + ch * uu, 5.02 + v * ch * th))
    xs = [-2.9, -2.65, -2.1, -1.4, -0.7, 0.0, 0.7, 1.4, 2.1, 2.65, 2.9]
    loft_x(part, xs, box_ring(11, 0.12, 0.0, 0.70), PEARL, stab_pt, teal_from=2.5)
    er = surf_ring(6, 0.12, 0.0, 0.715)
    for sx in (1, -1):
        xs2 = [sx * x for x in (0.14, 0.9, 1.7, 2.55)]
        if sx < 0:
            xs2 = xs2[::-1]
        loft_x(part, xs2, er, PEARL, stab_pt, teal_from=2.5)
        for x in (1.2, 2.2):
            ch = 1.30 - 0.50 * x / 2.9
            le = 6.00 + 0.38 * x / 2.9
            a = Vector((sx * x, le + ch * 0.995, 5.02))
            part.tube([a, a + Vector((0, 0.10, 0.0))], 0.005, 5, INK, caps='flat')
    # fin-top bullet fairing
    part.superellipsoid(Vector((0, 6.55, 5.02)), (0.13, 0.95, 0.13), 1.0, 1.0, 16, 10, PEARL,
                        pole_axis='Y')


# ---------------------------------------------------------------------------- nacelles
NAC_X, NAC_Z = 2.60, 2.62
HUB_Y = -3.18


def nacelle(part, sx):
    x = sx * NAC_X
    prof = [(0.0, -2.952), (0.235, -2.962), (0.262, -2.990), (0.300, -2.992), (0.332, -2.972),
            (0.356, -2.930), (0.385, -2.80), (0.398, -2.665), (0.392, -2.640), (0.401, -2.615),
            (0.412, -2.10), (0.406, -1.50), (0.385, -0.75), (0.345, -0.10), (0.270, 0.45),
            (0.165, 0.98), (0.0, 1.30)]
    mats = [INK, INK, METAL, PEARL, TEAL, TEAL, TEAL, INK, INK, PEARL, PEARL, PEARL, PEARL, PEARL,
            PEARL, PEARL]
    M = T(x, 0, NAC_Z) @ Matrix.Diagonal((1.0, 1.0, 1.06, 1.0))
    lathe_m(part, prof, 28, mats, M=M, axis='Y')
    # chin intake scoop with a dark mouth
    Mi = T(x, -2.70, NAC_Z - 0.375)
    slab(part, 0.26, 0.42, 0.13, 0.08, 0.05, PEARL, M=Mi @ rot_x(90) @ rot_x(-90), nc=2, ne=2)
    Mm = frame(Vector((x, -2.915, NAC_Z - 0.372)), (0, -1, 0), (0, 0, 1))
    slab(part, 0.19, 0.075, 0.03, 0.03, 0.008, INK, M=Mm, nc=2, ne=1)
    # exhaust stacks either side, pointing aft and down
    for side in (1, -1):
        base = Vector((x + side * 0.37, -2.05, NAC_Z - 0.06))
        d = Vector((side * 0.35, 1.0, -0.25)).normalized()
        Me = frame(base, d, (0, 0, 1))
        lathe_m(part, [(0.060, -0.10), (0.060, 0.10), (0.052, 0.115), (0.043, 0.112),
                       (0.043, 0.0), (0.0, 0.0)], 12, [METAL, METAL, METAL, INK, INK], M=Me)
        # cooling louvres behind the teal cowl band
        for k in range(3):
            y = -2.45 + k * 0.11
            ph = 0.35 if side > 0 else pi - 0.35
            q = Vector((x + side * 0.37, y, NAC_Z + 0.16))
            Ml = frame(q, (side, 0, 0.45), (0, 1, 0))
            tile(part, (0, 0, -0.004), 0.10, 0.030, 0.007, INK, M=Ml, ch=0.004, sunk=0.0)


def build_prop(name, sx, body):
    p = C.Part()
    hub = Vector((sx * NAC_X, HUB_Y, NAC_Z))
    M = T(hub) @ rot_x(90)   # local +Z -> -Y (forward)
    lathe_m(p, [(0.0, -0.14), (0.292, -0.14), (0.292, -0.06), (0.290, 0.02), (0.272, 0.10),
                (0.232, 0.19), (0.172, 0.27), (0.105, 0.34), (0.052, 0.39), (0.022, 0.415),
                (0.0, 0.425)], 28,
            [INK, TEAL, PEARL, PEARL, PEARL, PEARL, PEARL, PEARL, GOLD, GOLD], M=M)
    fwd = Vector((0, -1, 0))
    for k in range(4):
        a = radians(45 + 90 * k)
        d = Vector((cos(a), 0, sin(a)))
        tng = Vector((-sin(a), 0, cos(a)))
        # root cuff
        p.tube([hub + d * 0.24 + Vector((0, 0.02, 0)), hub + d * 0.36 + Vector((0, 0.02, 0))],
               0.052, 10, INK, caps='flat')
        rings = []
        stations = [(0.30, 0.110, 0.30, 48), (0.40, 0.150, 0.20, 42), (0.55, 0.178, 0.14, 35),
                    (0.72, 0.182, 0.115, 28), (0.88, 0.168, 0.10, 23), (1.00, 0.146, 0.095, 19),
                    (1.09, 0.118, 0.09, 16), (1.15, 0.078, 0.09, 14), (1.185, 0.034, 0.10, 13)]
        sec = None
        for (r, chd, tcb, beta) in stations:
            up, lo = foil(6, tcb / 2.0 * 2.0, 0.03, u1=1.0)
            sec = up[::-1] + lo[1:-1]
            b = radians(beta)
            cdir = tng * cos(b) + fwd * sin(b)
            ndir = d.cross(cdir).normalized()
            cen = hub + d * r + Vector((0, 0.02, 0))
            rings.append([cen + cdir * ((u - 0.38) * chd) + ndir * (v * chd) for (u, v) in sec])
        c0 = sum(rings[0], Vector()) / len(sec)
        c1 = sum(rings[-1], Vector()) / len(sec)
        vr, fs = p.grid(rings, INK, True, c0, c1)
        for f in fs:
            if (f.calc_center_median() - hub).length > 1.05:
                p.assign([f], CORAL)
    temp = p.to_temp()
    return C.merge_to_object(name, [temp], pivot=hub, parent=body, sharp_deg=50)


# ---------------------------------------------------------------------------- gear
def oleo(part, top, bot, r_cyl, r_pis, split=0.58):
    """Strut: dark upper cylinder, chrome piston, seal ring, small torque link in front."""
    a, b = Vector(top), Vector(bot)
    m = a + (b - a) * split
    part.tube([a, m], r_cyl, 12, INK, caps='flat')
    part.tube([m - (b - a).normalized() * 0.02, b], r_pis, 12, METAL, caps='flat')
    part.torus(r_cyl * 0.98, r_cyl * 0.22, 14, 4, INK,
               matrix=frame(m, (b - a).normalized(), (0, -1, 0)))
    f = Vector((0, -1, 0))
    k1 = m + (a - m) * 0.25 + f * (r_cyl + 0.01)
    knee = (m + b) / 2 + f * (r_cyl + 0.075)
    k2 = b + (m - b) * 0.15 + f * (r_pis + 0.01)
    part.tube([k1, knee], 0.012, 6, INK, caps='round', cap_segs=1)
    part.tube([knee, k2], 0.012, 6, INK, caps='round', cap_segs=1)


def gear(part, wheels_part):
    for sx in (1, -1):
        # sponson fairing (pearl, teal belly) on the fuselage side
        vs, fs = part.superellipsoid(Vector((sx * 0.86, 0.05, 1.02)), (0.30, 0.98, 0.25), 0.75,
                                     0.75, 22, 10, PEARL)
        part.assign([f for f in fs if f.calc_center_median().z < 0.90], TEAL)
        # leg with oleo down to the axle stub inboard of the wheel
        oleo(part, (sx * 1.00, 0.05, 0.96), (sx * 1.36, 0.0, 0.43), 0.068, 0.050)
        part.tube([Vector((sx * 1.33, 0.0, 0.38)), Vector((sx * 1.50, 0.0, 0.38))], 0.040, 12,
                  METAL, caps='flat')
        part.rbox(Vector((sx * 1.355, 0.0, 0.405)), (0.07, 0.16, 0.12), 0.02, 1, INK)
        # inboard gear door hanging open below the sponson
        Md = frame(Vector((sx * 0.74, 0.05, 0.66)), (sx, 0, -0.10), (0, 0, 1))
        slab(part, 0.62, 0.36, 0.024, 0.06, 0.008, PEARL, M=Md, nc=2, ne=1, bottom=INK)
        part.tube([Vector((sx * 0.75, -0.18, 0.84)), Vector((sx * 0.86, -0.18, 0.94))], 0.012, 6,
                  METAL, caps='flat')
        w = V.wheel_hq(0.38, 0.24, sx, seg=24, lugs=0, grooves=2, spokes=0, dish=PEARL,
                       disc=False, caliper=False, nuts=8, hub_seg=14, valve=BRASS, hub=PEARL,
                       cap=BRASS, rim_r=0.56)
        V.part_add(wheels_part, w, T(sx * 1.55, 0.0, 0.38))
    # nose gear: twin wheels on a fork, oleo leg, doors either side of the well
    oleo(part, (0, -4.44, 1.06), (0, -4.44, 0.47), 0.058, 0.042, split=0.50)
    for sx in (1, -1):
        part.rbox(Vector((sx * 0.035, -4.44, 0.40)), (0.03, 0.10, 0.16), 0.01, 1, INK)
        w = V.wheel_hq(0.30, 0.13, sx, seg=22, lugs=0, grooves=1, spokes=0, dish=PEARL,
                       disc=False, caliper=False, nuts=5, hub_seg=12, valve=None, hub=PEARL,
                       cap=BRASS, rim_r=0.56)
        V.part_add(wheels_part, w, T(sx * 0.115, -4.45, 0.30))
        Md = frame(Vector((sx * 0.19, -4.45, 0.83)), (sx, 0, 0), (0, 0, 1))
        slab(part, 0.62, 0.26, 0.020, 0.05, 0.007, PEARL, M=Md, nc=2, ne=1, bottom=INK)
    part.tube([Vector((-0.06, -4.45, 0.30)), Vector((0.06, -4.45, 0.30))], 0.030, 10, METAL,
              caps='flat')
    # dark nose-wheel well between the doors
    surface_skin(part, ccw(densify2(rrect_uv(-4.76, -4.14, 4.30, 5.12, 0.05, 2), 0.10,
                                    closed=True)), polar_map(), 0.003, INK, scales=(1.0, 0.5))


# ---------------------------------------------------------------------------- small details
def details(part):
    # beacon (top) and belly anti-collision light
    b0 = BEACON - Vector((0, 0, 0.10))
    lathe_m(part, [(0.0, -0.03), (0.105, -0.03), (0.105, 0.0), (0.090, 0.018), (0.072, 0.022),
                   (0.070, 0.050), (0.052, 0.088), (0.0, 0.100)], 16,
            [PEARL, PEARL, PEARL, INK, CORAL, CORAL, CORAL], M=T(b0))
    bb = fus_pt(1.40, 1.5 * pi, 0.0)
    lathe_m(part, [(0.0, -0.03), (0.085, -0.03), (0.085, 0.0), (0.060, 0.016), (0.044, 0.050),
                   (0.0, 0.062)], 14, [PEARL, PEARL, INK, CORAL, CORAL], M=T(bb) @ rot_x(180))
    # landing light under the nose
    land = LANDING + Vector((0, 0.03, 0.02))
    V.lamp_round(part, land, (0, -0.8, -0.6), 0.085, body=PEARL, bezel=BRASS, segs=16,
                 depth=0.05, rings=0)
    # blade antennas (top x2, belly x1)
    for (y, phi) in ((-2.9, pi / 2), (1.65, pi / 2), (-1.0, 1.5 * pi)):
        base = fus_pt(y, phi, -0.01)
        up = fus_n(y, phi)
        secs = []
        for (h, c, yoff) in ((0.0, 0.20, 0.0), (0.12, 0.13, 0.06), (0.21, 0.07, 0.12)):
            ring = []
            for (u, v) in box_ring(5, 0.12, 0.0, 0.999):
                ring.append(base + up * h + Vector((v * c, (u - 0.5) * c + yoff, 0)))
            secs.append(ring)
        c1 = sum(secs[-1], Vector()) / len(secs[-1])
        part.grid(secs, INK, True, None, c1)
    # pitot tubes either side of the nose
    for side in (1, -1):
        ph = 0.18 if side > 0 else pi - 0.18
        b = fus_pt(-4.95, ph, -0.005)
        n = fus_n(-4.95, ph)
        m = b + n * 0.07
        part.tube([b, m], 0.010, 6, METAL, caps='flat')
        part.tube([m, m + Vector((0, -0.13, 0))], 0.008, 6, METAL, caps='round', cap_segs=1)


def build():
    C.reset_scene()
    root = C.new_empty("aircraft", None, (0, 0, 0), size=1.0)
    fus = C.Part()
    fuselage(fus)
    fob = fus.to_temp(name="fus")
    cut, glass, frames, lines = C.Part(), C.Part(), C.Part(), C.Part()
    glazing(cut, glass, frames)
    V.boolean(fob, [cut.to_temp(name="cut")])
    outlines(lines)
    shell = C.Part()
    wing(shell)
    root_fairing(shell)
    tail(shell)
    for sx in (1, -1):
        nacelle(shell, sx)
    whl = C.Part()
    gear(shell, whl)
    details(shell)
    temps = [fob, shell.to_temp(), whl.to_temp(), frames.to_temp(),
             glass.to_temp(recalc=False), lines.to_temp(recalc=False)]
    body = C.merge_to_object("Body", temps, pivot=(0, 0, 0), parent=root, sharp_deg=48)
    door, hinge = build_door(body)
    pl = build_prop("Prop_L", 1, body)
    pr = build_prop("Prop_R", -1, body)
    C.new_empty("LIGHT_nav_L", body, NAV_L, size=0.3)
    C.new_empty("LIGHT_nav_R", body, NAV_R, size=0.3)
    C.new_empty("LIGHT_beacon", body, BEACON, size=0.3)
    C.new_empty("LIGHT_landing", body, LANDING, size=0.3)
    C.new_empty("ANCHOR_door", root, ANCHOR_DOOR, size=0.5)
    C.bake_ao([body, door, pl, pr], dist=0.9, samples=40, floor=0.40)
    return root


if __name__ == "__main__":
    root = build()
    C.summary(root)
    C.export_fbx(root, OUT)
    if RENDER:
        C.render_previews("aircraft", root, res=(960, 720), samples=128, ground_z=0.0, lens=45,
                          margin=1.06)
