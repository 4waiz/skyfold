"""SKYFOLD environment kit - ground tiles: roads, plaza, paving, runway, apron, quays, bridges.

All tiles: 16 m x 16 m cell centred on the origin, road surface at Z 0, 0.3 m slab.
Remember: Unity N = Blender -Y, Unity E = Blender -X (S = +Y, W = +X).
"""
from env_common import *

H = 8.0          # half cell
RW = 4.0         # half asphalt width
KW = 0.3         # kerb stone width
SWZ = 0.15       # sidewalk / kerb top
LW = 0.075       # half line width
SQ = [(-H, -H), (H, -H), (H, H), (-H, H)]

ROAD_AO = dict(ground_z=None, dist=0.45, rays=24, strength=0.7, floor=0.55, inset=0.12)
TILE_RENDER = dict(az=30.0, el=42.0)


def rect(x0, x1, y0, y1):
    return [(min(x0, x1), min(y0, y1)), (max(x0, x1), min(y0, y1)), (max(x0, x1), max(y0, y1)), (min(x0, x1), max(y0, y1))]


def reg(pts, z, mat, prio, side=None):
    d = dict(pts=pts, z=z, mat=mat, prio=prio)
    if side:
        d['side'] = side
    return d


def asphalt():
    return reg(SQ, 0.0, 'SKY_Road', 0)


def sidewalk(pts):
    return reg(pts, SWZ, 'SKY_Kerb', 1)


def kerb(pts):
    return reg(pts, SWZ, 'SKY_Pearl', 2)


def line(pts, mat='SKY_RoadLine'):
    return reg(pts, 0.0, mat, 5)


def mapq(pts, sx, sy):
    return [(sx * x, sy * y) for (x, y) in pts]


def swapxy(pts):
    return [(y, x) for (x, y) in pts]


def sw_joint(pts):
    return reg(pts, SWZ, 'SKY_SandstoneDeep', 1.5)


def side_strip(side, joints=True, y_lo=-H, y_hi=H):
    """Straight sidewalk + kerb along a closed side. side in 'W' (+X) or 'E' (-X) for N-S roads."""
    s = 1 if side == 'W' else -1
    out = [sidewalk(rect(s * RW, s * H, y_lo, y_hi)), kerb(rect(s * RW, s * (RW + KW), y_lo, y_hi))]
    if joints:
        for y in (-7.0, -5.0, -3.0, -1.0, 1.0, 3.0, 5.0, 7.0):
            if y_lo < y < y_hi:
                out.append(sw_joint(rect(s * (RW + KW), s * H, y - 0.03, y + 0.03)))
        # longitudinal joint 1.6 m from the cell edge (building line band)
        out.append(sw_joint(rect(s * (H - 1.6) - 0.03, s * (H - 1.6) + 0.03, y_lo, y_hi)))
    return out


def corner_block(sx, sy, R=2.0):
    """Sidewalk block in quadrant (sx, sy) with rounded convex corner facing the junction."""
    c = RW + R
    blk = [(H, RW), (c, RW)] + arc(c, c, R, 270, 180, 6)[1:-1] + [(RW, c), (RW, H), (H, H)]
    kb = [(H, RW), (c, RW)] + arc(c, c, R, 270, 180, 6)[1:-1] + [(RW, c), (RW, H), (RW + KW, H), (RW + KW, c)] + \
        arc(c, c, R - KW, 180, 270, 6)[1:-1] + [(c, RW + KW), (H, RW + KW)]
    out = [sidewalk(mapq(blk, sx, sy)), kerb(mapq(kb, sx, sy))]
    # building-line joints continue the straight tiles' joint 1.6 m from the cell edge
    out.append(sw_joint(mapq(rect(H - 1.6 - 0.03, H - 1.6 + 0.03, RW + KW, H), sx, sy)))
    out.append(sw_joint(mapq(rect(RW + KW, H, H - 1.6 - 0.03, H - 1.6 + 0.03), sx, sy)))
    return out


def dashes_y(spans, x=0.0, w=LW):
    return [line(rect(x - w, x + w, a, b)) for (a, b) in spans]


def dashes_x(spans, y=0.0, w=LW):
    return [line(rect(a, b, y - w, y + w)) for (a, b) in spans]


def zebra_y(y0, y1, n=5, sw=0.7, gap=0.65):
    """Zebra across a N-S road: stripes elongated along Y, spaced along X."""
    tot = n * sw + (n - 1) * gap
    out = []
    for k in range(n):
        x0 = -tot / 2 + k * (sw + gap)
        out.append(line(rect(x0, x0 + sw, y0, y1)))
    return out


def zebra_x(x0, x1, n=5, sw=0.7, gap=0.65):
    tot = n * sw + (n - 1) * gap
    out = []
    for k in range(n):
        y0 = -tot / 2 + k * (sw + gap)
        out.append(line(rect(x0, x1, y0, y0 + sw)))
    return out


def drain(x0, x1, y0, y1):
    return reg(rect(x0, x1, y0, y1), 0.0, 'SKY_Ink', 4)


DASH_STD = [(-7, -5), (-3, -1), (1, 3), (5, 7)]


# --------------------------------------------------------------------------- roads

@asset("road_straight", "Roads", "roads", ao=ROAD_AO, render=TILE_RENDER)
def road_straight(a):
    R = [asphalt()] + side_strip('W') + side_strip('E') + dashes_y(DASH_STD)
    R += [drain(3.45, 3.95, -0.45, 0.45), drain(-3.95, -3.45, 3.55, 4.45), drain(-3.95, -3.45, -4.45, -3.55)]
    tile_surface(a, R)


@asset("road_corner", "Roads", "roads", ao=ROAD_AO, render=TILE_RENDER)
def road_corner(a):
    # openings Unity N (-Y) and E (-X): quarter-annulus bend centred on Blender (-8,-8)
    P = (-H, -H)
    r_in, r_out = RW, 3 * RW
    inner = [P] + arc(P[0], P[1], r_in, 0, 90, 8)
    inner_k = arc(P[0], P[1], r_in, 0, 90, 8) + arc(P[0], P[1], r_in - KW, 90, 0, 8)
    outer = [(r_out - H, -H), (H, -H), (H, H), (-H, H), (-H, r_out - H)] + arc(P[0], P[1], r_out, 90, 0, 16)[1:-1]
    outer_k = arc(P[0], P[1], r_out, 0, 90, 16) + arc(P[0], P[1], r_out + KW, 90, 0, 16)
    R = [asphalt(), sidewalk(inner), kerb(inner_k), sidewalk(outer), kerb(outer_k)]
    L = (math.pi / 2) * 8.0
    for k in (-1, 0, 1):
        s0 = L / 2 + 4 * k - 1
        s1 = s0 + 2
        a0, a1 = math.degrees(s0 / 8.0), math.degrees(s1 / 8.0)
        R.append(line(arc(P[0], P[1], 8 + LW, a0, a1, 4) + arc(P[0], P[1], 8 - LW, a1, a0, 4)))
    # paving joints: building-line arcs continue the straight tiles' joint at 1.6 m from the cell edge
    jw = 0.03
    R.append(sw_joint(arc(P[0], P[1], 1.6 + jw, 0, 90, 6) + arc(P[0], P[1], 1.6 - jw, 90, 0, 6)))
    R.append(sw_joint(arc(P[0], P[1], 14.4 + jw, 0, 90, 18) + arc(P[0], P[1], 14.4 - jw, 90, 0, 18)))
    for ang in (22.5, 45.0, 67.5):
        ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        nx, ny = -sa * jw, ca * jw
        r0, r1 = 0.4, r_in - KW - 0.02
        R.append(sw_joint([(P[0] + ca * r0 - nx, P[1] + sa * r0 - ny), (P[0] + ca * r1 - nx, P[1] + sa * r1 - ny),
                           (P[0] + ca * r1 + nx, P[1] + sa * r1 + ny), (P[0] + ca * r0 + nx, P[1] + sa * r0 + ny)]))
    for ang in (4.6, 22.5, 45.0, 67.5, 85.4):
        ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        nx, ny = -sa * jw, ca * jw
        r0 = r_out + KW + 0.02
        r1 = min(2 * H / max(ca, 1e-6), 2 * H / max(sa, 1e-6)) - 0.01
        R.append(sw_joint([(P[0] + ca * r0 - nx, P[1] + sa * r0 - ny), (P[0] + ca * r1 - nx, P[1] + sa * r1 - ny),
                           (P[0] + ca * r1 + nx, P[1] + sa * r1 + ny), (P[0] + ca * r0 + nx, P[1] + sa * r0 + ny)]))
    tile_surface(a, R)


@asset("road_tee", "Roads", "roads", ao=ROAD_AO, render=TILE_RENDER)
def road_tee(a):
    # openings N, E, S (Unity) -> Blender -Y, -X, +Y ; closed side W = +X
    R = [asphalt()] + side_strip('W') + corner_block(-1, -1) + corner_block(-1, 1)
    R += dashes_y([(-7, -5), (5, 7)])
    R += zebra_x(-6.9, -4.9)
    R += [drain(3.45, 3.95, -0.45, 0.45)]
    tile_surface(a, R)


@asset("road_cross", "Roads", "roads", ao=ROAD_AO, render=TILE_RENDER)
def road_cross(a):
    R = [asphalt()]
    for sx in (-1, 1):
        for sy in (-1, 1):
            R += corner_block(sx, sy)
    R += zebra_y(-6.9, -4.9) + zebra_y(4.9, 6.9) + zebra_x(-6.9, -4.9) + zebra_x(4.9, 6.9)
    tile_surface(a, R)


def _road_end_outline():
    """Asphalt outline (CCW) of the N arm + turning bulb, and the open kerb polyline."""
    C_ = (0.0, 1.5)
    Rb, rf = 5.5, 1.5
    yf = C_[1] - math.sqrt((Rb + rf) ** 2 - (RW + rf) ** 2)
    F = (RW + rf, yf)
    dx, dy = F[0] - C_[0], F[1] - C_[1]
    dl = math.hypot(dx, dy)
    T = (C_[0] + Rb * dx / dl, C_[1] + Rb * dy / dl)
    a_f = math.degrees(math.atan2(T[1] - F[1], T[0] - F[0]))
    a_b = math.degrees(math.atan2(T[1] - C_[1], T[0] - C_[0]))
    right = [(RW, -H), (RW, yf)] + arc(F[0], F[1], rf, 180, a_f, 4)[1:]
    bulb = arc(C_[0], C_[1], Rb, a_b, 180 - a_b, 24)[1:-1]
    left = arc(-F[0], F[1], rf, 180 - a_f, 0, 4)[:-1] + [(-RW, yf), (-RW, -H)]
    path = right + bulb + left
    return path


@asset("road_end", "Roads", "roads", ao=ROAD_AO, render=TILE_RENDER)
def road_end(a):
    path = _road_end_outline()
    off = offset_line(path, -KW)
    R = [reg(SQ, SWZ, 'SKY_Kerb', 0), reg(path, 0.0, 'SKY_Road', 3), reg(path + list(reversed(off)), SWZ, 'SKY_Pearl', 2)]
    R += dashes_y([(-7, -5)])
    R += [drain(-0.3, 0.3, 5.9, 6.6)]
    # paving joints matching the straight tiles at the open (N) edge
    for s in (-1, 1):
        R.append(sw_joint(rect(s * (H - 1.6) - 0.03, s * (H - 1.6) + 0.03, -H, H)))
        for y in (-7.0, -5.0, -3.0, -1.0, 1.0, 3.0, 5.0, 7.0):
            x0 = RW + KW if y < -3.2 else H - 1.6
            R.append(sw_joint(rect(s * x0, s * H, y - 0.03, y + 0.03)))
    R.append(sw_joint(rect(-H + 1.6, H - 1.6, H - 0.6 - 0.03, H - 0.6 + 0.03)))
    tile_surface(a, R)


@asset("road_plaza", "Roads", "roads", ao=ROAD_AO, render=TILE_RENDER)
def road_plaza(a):
    R = [reg(SQ, 0.0, 'SKY_Sandstone', 0)]
    # concentric ring inlay and 8 spokes
    ring = circle(5.35, 40) + list(reversed(circle(5.0, 40)))
    R.append(reg(circle(5.35, 40), 0.0, 'SKY_SandstoneDeep', 1))
    R.append(reg(circle(5.0, 40), 0.0, 'SKY_Sandstone', 2))
    for k in range(8):
        ang = math.radians(22.5 + 45 * k)
        ca, sa = math.cos(ang), math.sin(ang)
        pts = []
        for (u, v) in ((2.7, -0.16), (5.0, -0.16), (5.0, 0.16), (2.7, 0.16)):
            pts.append((u * ca - v * sa, u * sa + v * ca))
        R.append(reg(pts, 0.0, 'SKY_SandstoneDeep', 3))
    # corner diamonds
    for (sx, sy) in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        cx, cy = 6.6 * sx, 6.6 * sy
        R.append(reg([(cx - 0.55, cy), (cx, cy - 0.55), (cx + 0.55, cy), (cx, cy + 0.55)], 0.0, 'SKY_SandstoneDeep', 3))
    # kerb ring island (raised)
    R.append(reg(circle(2.6, 36), SWZ, 'SKY_Pearl', 6))
    R.append(reg(circle(2.25, 36), SWZ - 0.03, 'SKY_PalmLeaf', 7, side='SKY_Pearl'))
    # edge border so the plaza reads as a field
    tile_surface(a, R)


@asset("ground_paving", "Roads", "roads", ao=ROAD_AO, render=TILE_RENDER)
def ground_paving(a):
    R = [reg(SQ, 0.0, 'SKY_Sandstone', 0)]
    jw = 0.04
    for c in (-4.0, 0.0, 4.0):
        R.append(reg(rect(c - jw, c + jw, -H, H), 0.0, 'SKY_SandstoneDeep', 1))
        R.append(reg(rect(-H, H, c - jw, c + jw), 0.0, 'SKY_SandstoneDeep', 1))
    for c in (-H, H):
        s = 1 if c < 0 else -1
        R.append(reg(rect(c, c + s * jw * 0.5, -H, H), 0.0, 'SKY_SandstoneDeep', 1))
        R.append(reg(rect(-H, H, c, c + s * jw * 0.5), 0.0, 'SKY_SandstoneDeep', 1))
    # offset slab pattern: extra half joints in alternate bands
    for (y0, y1) in ((-4, 0), (4, 8)):
        for x in (-6.0, -2.0, 2.0, 6.0):
            R.append(reg(rect(x - jw, x + jw, y0, y1), 0.0, 'SKY_SandstoneDeep', 1))
    for (y0, y1) in ((-8, -4), (0, 4)):
        for x in (-6.0, -2.0, 2.0, 6.0):
            R.append(reg(rect(x - jw, x + jw, y0, y1), 0.0, 'SKY_SandstoneDeep', 1))
    tile_surface(a, R)


# --------------------------------------------------------------------------- runway / apron

RUN_HALF = 6.0


def runway_base():
    R = [reg(SQ, 0.0, 'SKY_Kerb', 0), reg(rect(-RUN_HALF, RUN_HALF, -H, H), 0.0, 'SKY_Road', 1)]
    # shoulder joints
    for x in (-7.0, 7.0):
        R.append(reg(rect(x - 0.03, x + 0.03, -H, H), 0.0, 'SKY_SandstoneDeep', 2))
    return R


@asset("runway_section", "Roads", "runway", ao=ROAD_AO, render=TILE_RENDER)
def runway_section(a):
    R = runway_base()
    for s in (-1, 1):
        R.append(line(rect(s * 5.5, s * 5.85, -H, H)))
    R += dashes_y([(-6, -2), (2, 6)], w=0.2)
    tile_surface(a, R)


@asset("runway_end", "Roads", "runway", ao=ROAD_AO, render=TILE_RENDER)
def runway_end(a):
    # connects to runway_section on Unity N (-Y); the runway ends at Unity S (+Y)
    R = runway_base()
    for s in (-1, 1):
        R.append(line(rect(s * 5.5, s * 5.85, -H, 4.6)))
    R += dashes_y([(-6.5, -4.5)], w=0.2)
    # piano keys
    for s in (-1, 1):
        for k in range(4):
            xc = s * (0.95 + k * 1.3)
            R.append(line(rect(xc - 0.3, xc + 0.3, -3.2, 3.2)))
    # threshold bar
    R.append(line(rect(-5.5, 5.5, 3.8, 4.6)))
    # blast pad chevrons (coral = hazard)
    for y0 in (5.4, 6.9):
        pts = [(-5.2, y0 + 0.9), (0.0, y0), (5.2, y0 + 0.9), (5.2, y0 + 1.35), (0.0, y0 + 0.45), (-5.2, y0 + 1.35)]
        R.append(reg(pts, 0.0, 'SKY_Coral', 6))
    tile_surface(a, R)


@asset("apron_tile", "Roads", "runway", ao=ROAD_AO, render=TILE_RENDER)
def apron_tile(a):
    R = [reg(SQ, 0.0, 'SKY_Kerb', 0)]
    jw = 0.035
    for c in (-4.0, 0.0, 4.0):
        R.append(reg(rect(c - jw, c + jw, -H, H), 0.0, 'SKY_SandstoneDeep', 1))
        R.append(reg(rect(-H, H, c - jw, c + jw), 0.0, 'SKY_SandstoneDeep', 1))
    for c in (-H, H):
        s = 1 if c < 0 else -1
        R.append(reg(rect(c, c + s * jw * 0.5, -H, H), 0.0, 'SKY_SandstoneDeep', 1))
        R.append(reg(rect(-H, H, c, c + s * jw * 0.5), 0.0, 'SKY_SandstoneDeep', 1))
    # tie-down points
    for (x, y) in ((-2, -2), (2, 2), (-2, 2), (2, -2)):
        R.append(reg(circle(0.12, 8, x, y), 0.0, 'SKY_Ink', 3))
    tile_surface(a, R)


# --------------------------------------------------------------------------- quays

QT = 1.5          # wall thickness: lies OUTSIDE the land cell, in the 1.5 m water margin
Q_COPE = 0.6      # pearl coping width
Q_LIP = 0.1       # coping overhang over the water face
COURSES = [(-0.95, -0.3), (-1.6, -0.95)]   # rusticated block courses above the waterline


def _band(p0, p1, o0, o1):
    """Polygon of the band between LEFT offsets o0..o1 of segment p0->p1."""
    p0 = Vector(p0); p1 = Vector(p1)
    t = (p1 - p0).normalized()
    nl = Vector((-t.y, t.x))
    return [tuple(p0 + nl * o0), tuple(p1 + nl * o0), tuple(p1 + nl * o1), tuple(p0 + nl * o1)]


def _wedge(c, r0, r1, a0, a1, seg):
    if r0 <= 1e-4:
        return [c] + arc(c[0], c[1], r1, a0, a1, seg)
    return arc(c[0], c[1], r1, a0, a1, seg) + arc(c[0], c[1], r0, a1, a0, seg)


def quay_run(a, p0, p1, cutters=(), stagger=0.0, blocks=4.0):
    """Wall run whose water face is the line p0->p1; land (and the cell) is on the LEFT."""
    p0v, p1v = Vector(p0), Vector(p1)
    L = (p1v - p0v).length
    t = (p1v - p0v) / L
    mb = MB(); mb.prism(_band(p0, p1, 0.08, QT), -4.0, COURSES[-1][0], 'SKY_SandstoneDeep')
    a.part(mb, cutters=cutters, name="core")
    for ci, (z0, z1) in enumerate(COURSES):
        off = (blocks / 2.0 if ci % 2 else 0.0) + stagger
        cuts = [0.0]
        x = off % blocks
        if x < 0.6:
            x += blocks
        while x < L - 0.6:
            cuts.append(x)
            x += blocks
        cuts.append(L)
        mb = MB()
        for k in range(len(cuts) - 1):
            mb.prism(_band(p0v + t * cuts[k], p0v + t * cuts[k + 1], 0.0, QT), z0, z1, 'SKY_SandstoneDeep')
        a.part(mb, bevel=0.04, seg=1, cutters=cutters, name=f"course{ci}")
    mb = MB(); mb.prism(_band(p0, p1, -Q_LIP, Q_COPE), -0.3, 0.0, 'SKY_Pearl')
    a.part(mb, bevel=0.04, seg=1, cutters=cutters, name="coping")
    mb = MB(); mb.prism(_band(p0, p1, Q_COPE, QT), -0.3, 0.0, 'SKY_Sandstone')
    a.part(mb, cutters=cutters, name="top")


def quay_corner_wedge(a, c, r, a0, a1, seg=8):
    mb = MB(); mb.prism(_wedge(c, 0.0, r - 0.08, a0, a1, seg), -4.0, COURSES[-1][0], 'SKY_SandstoneDeep')
    a.part(mb, name="wcore")
    for ci, (z0, z1) in enumerate(COURSES):
        mb = MB(); mb.prism(_wedge(c, 0.0, r, a0, a1, seg), z0, z1, 'SKY_SandstoneDeep')
        a.part(mb, bevel=0.04, seg=1, name=f"wcourse{ci}")
    mb = MB(); mb.prism(_wedge(c, r - Q_COPE, r + Q_LIP, a0, a1, seg), -0.3, 0.0, 'SKY_Pearl')
    a.part(mb, bevel=0.04, seg=1, name="wcoping")
    mb = MB(); mb.prism(_wedge(c, 0.0, r - Q_COPE, a0, a1, seg), -0.3, 0.0, 'SKY_Sandstone')
    a.part(mb, name="wtop")


def bollard_mooring(mb, x, y, z=0.0):
    prof = [(0, z), (0.22, z), (0.22, z + 0.07), (0.14, z + 0.14), (0.13, z + 0.4), (0.2, z + 0.48),
            (0.2, z + 0.56), (0, z + 0.6)]
    mb.lathe(prof, 10, 'SKY_Ink', cx=x, cy=y)


def fender(mb, x, y_face, z0=-1.9, z1=-0.4, outward=1):
    mb.box(x - 0.18, x + 0.18, y_face, y_face + outward * 0.16, z0, z1, 'SKY_Wood')


QUAY_AO = dict(ground_z=None, dist=1.0, rays=24, strength=0.75, floor=0.45, inset=0.15)
QUAY_RENDER = dict(az=205.0, el=26.0, water=True, seabed=-4.0)


@asset("quay_straight", "Roads", "quays", ao=QUAY_AO, render=QUAY_RENDER)
def quay_straight(a):
    """Seawall for the Unity SOUTH edge of a land cell. The 1.5 m thick wall lies just OUTSIDE the
    cell (Blender y 8..9.5, in the water margin) so it never overlaps the land cell's ground tile."""
    yf = H + QT
    sx0, sx1 = 1.4, 6.4                      # harbour steps cut into the wall (descend toward Unity W)
    mb = MB(); mb.box(sx0, sx1, H + 0.3, yf + 0.5, -1.45, 0.5, 'SKY_SandstoneDeep')
    cut = a.cutter(mb, "stair_cut")
    quay_run(a, (H, yf), (-H, yf), cutters=[cut])
    mb = MB()
    run = 0.6
    for i in range(6):
        x0 = sx0 + run * i
        x1 = sx1 if i == 5 else sx0 + run * (i + 1)
        mb.box(x0, x1, H + 0.3, yf, -1.45, -0.235 * (i + 1), 'SKY_Sandstone' if i % 2 == 0 else 'SKY_Kerb')
    a.part(mb, bevel=0.03, seg=1, name="steps")
    mb = MB()
    for x in (-5.5, -1.5):
        bollard_mooring(mb, x, yf - 0.3)
    a.part(mb, name="bollards")
    mb = MB()
    for x in (-5.5, -1.5, -7.3):
        fender(mb, x, yf)
    a.part(mb, bevel=0.03, seg=1, name="fenders")
    a.notes.append("Wall occupies Blender y 8..9.5 (Unity z -8..-9.5), i.e. the 1.5 m water margin outside the "
                   "cell's south edge; top flush at Z0; face drops to Z-4.")


@asset("quay_corner_outer", "Roads", "quays", ao=QUAY_AO, render=dict(QUAY_RENDER, az=230.0))
def quay_corner_outer(a):
    """Convex land corner: water to the Unity S (+Y) and E (-X) of the land cell."""
    yf = H + QT
    xf = -H - QT
    quay_run(a, (H, yf), (-H, yf))
    quay_run(a, (xf, H), (xf, -H), stagger=1.0)
    quay_corner_wedge(a, (-H, H), QT, 90, 180, 8)
    mb = MB()
    bollard_mooring(mb, -H - 0.8, H + 0.8)
    bollard_mooring(mb, 2.5, yf - 0.3)
    bollard_mooring(mb, xf + 0.3, -2.5)
    a.part(mb, name="bollards")
    mb = MB()
    for x in (2.5, -4.0):
        fender(mb, x, yf)
    for y in (-2.5, 4.0):
        mb.box(xf - 0.16, xf, y - 0.18, y + 0.18, -1.9, -0.4, 'SKY_Wood')
    a.part(mb, bevel=0.03, seg=1, name="fenders")
    a.notes.append("Walls lie outside the cell on the Unity S and E sides plus the rounded corner square.")


@asset("quay_corner_inner", "Roads", "quays", ao=QUAY_AO, render=QUAY_RENDER)
def quay_corner_inner(a):
    """Concave corner: south-edge run shortened by 1.5 m at its Unity-EAST end (Blender -X) so it butts
    against the perpendicular run of the neighbouring land cell instead of overlapping it."""
    yf = H + QT
    quay_run(a, (H, yf), (-H + QT, yf))
    mb = MB()
    for x in (-3.0, 4.0):
        bollard_mooring(mb, x, yf - 0.3)
    a.part(mb, name="bollards")
    mb = MB()
    for x in (-3.0, 4.0):
        fender(mb, x, yf)
    a.part(mb, bevel=0.03, seg=1, name="fenders")
    mb = MB()
    lx = -H + QT + 0.9
    for xx in (lx - 0.25, lx + 0.25):
        mb.box(xx - 0.03, xx + 0.03, yf, yf + 0.12, -2.0, 0.05, 'SKY_Brass')
    for z in [-1.8 + 0.3 * i for i in range(6)]:
        mb.box(lx - 0.25, lx + 0.25, yf + 0.06, yf + 0.1, z - 0.02, z + 0.02, 'SKY_Brass')
    a.part(mb, name="ladder")
    a.notes.append("Use on the land cell whose wall runs into the concave corner at its local Unity-east end; "
                   "the neighbouring cell keeps a quay_straight.")


# --------------------------------------------------------------------------- bridges

DECK_HW = 5.0       # deck half width (8 m asphalt + 1 m walkways)
DECK_T = 0.55
ABUT = 6.5          # abutment face |y| (quay line)
PIER = 5.8          # pier face |y| (arch springing)
FASCIA_BOT = -0.45


def bridge_deck_surface(a, y0=-H, y1=H, dash=True):
    R = [reg(rect(-DECK_HW, DECK_HW, y0, y1), 0.0, 'SKY_Road', 0)]
    for s in (-1, 1):
        R.append(reg(rect(s * RW, s * DECK_HW, y0, y1), SWZ, 'SKY_Kerb', 1))
        R.append(reg(rect(s * RW, s * (RW + KW), y0, y1), SWZ, 'SKY_Pearl', 2))
    if dash:
        R += [line(rect(-LW, LW, p, q)) for (p, q) in DASH_STD if p >= y0 - 1e-6 and q <= y1 + 1e-6]
    tile_surface(a, R, base_z=-DECK_T, bounds=(-DECK_HW, DECK_HW, y0, y1), side_mat='SKY_SandstoneDeep',
                 name="deck")


def bridge_fascia(a, y0, y1):
    mb = MB()
    for s in (-1, 1):
        mb.box(s * DECK_HW, s * (DECK_HW + 0.25), y0, y1, FASCIA_BOT, 0.28, 'SKY_Pearl')
    a.part(mb, bevel=0.04, seg=1, name="fascia")
    mb = MB()
    for s in (-1, 1):
        mb.box(s * (DECK_HW + 0.25), s * (DECK_HW + 0.29), y0 + 0.05, y1 - 0.05, -0.2, -0.1, 'SKY_TealGlow')
    a.part(mb, name="glow")


def balustrade(a, y0, y1, posts, x_side, ends=(), spacing=0.5):
    """Pearl balustrade on the fascia top: posts with brass caps, top rail, slim balusters."""
    s = x_side
    xc = s * (DECK_HW + 0.125)
    zt = 0.28
    if posts:
        mb = MB()
        for py in posts:
            mb.box(xc - 0.12, xc + 0.12, py - 0.12, py + 0.12, zt, zt + 1.0, 'SKY_Pearl')
        a.part(mb, bevel=0.025, seg=1, name="posts")
        mb = MB()
        for py in posts:
            mb.lathe([(0, zt + 1.0), (0.11, zt + 1.0), (0.09, zt + 1.08), (0.04, zt + 1.15), (0, zt + 1.19)], 6,
                     'SKY_Brass', cx=xc, cy=py, a0=30)
        a.part(mb, name="caps")
    mb = MB()
    mb.box(xc - 0.075, xc + 0.075, y0, y1, zt + 0.86, zt + 0.98, 'SKY_Pearl')
    a.part(mb, bevel=0.02, seg=1, name="rail")
    mb = MB()
    ps = sorted(list(posts) + list(ends))
    for k in range(len(ps) - 1):
        p = ps[k] + (0.3 if ps[k] in ends else 0.12)
        q = ps[k + 1] - (0.3 if ps[k + 1] in ends else 0.12)
        n = max(1, int((q - p) / spacing))
        for i in range(n):
            by = p + (q - p) * (i + 0.5) / n
            r0, r1 = 0.045, 0.03
            z0, z1 = zt, zt + 0.86
            ring0 = [(xc - r0, by - r0, z0), (xc + r0, by - r0, z0), (xc + r0, by + r0, z0), (xc - r0, by + r0, z0)]
            ring1 = [(xc - r1, by - r1, z1), (xc + r1, by - r1, z1), (xc + r1, by + r1, z1), (xc - r1, by + r1, z1)]
            mb.loft([ring0, ring1], 'SKY_Pearl', cap0=False, cap1=False, recalc=False)
    a.part(mb, name="balusters")


def bridge_abutment(a, sgn):
    """Abutment along the cell edge (|y| 6.5..8): quay-style face toward the channel, copings outside the deck."""
    if sgn > 0:
        p0, p1 = (-H, ABUT), (H, ABUT)
    else:
        p0, p1 = (H, -ABUT), (-H, -ABUT)
    p0v, p1v = Vector(p0), Vector(p1)
    t = (p1v - p0v).normalized()
    mb = MB(); mb.prism(_band(p0, p1, 0.08, QT), -4.0, COURSES[-1][0], 'SKY_SandstoneDeep')
    a.part(mb, name="acore")
    mb = MB()
    cuts = [0.0, 3.0, 8.0, 13.0, 16.0]
    for k in range(len(cuts) - 1):
        mb.prism(_band(p0v + t * cuts[k], p0v + t * cuts[k + 1], 0.0, QT), COURSES[-1][0], -0.3, 'SKY_SandstoneDeep')
    a.part(mb, bevel=0.04, seg=1, name="acourse")
    for (xa, xb) in ((DECK_HW + 0.3, H), (-H, -DECK_HW - 0.3)):
        yf_ = ABUT * sgn
        ya, yb = yf_ - sgn * Q_LIP, yf_ + sgn * Q_COPE
        mb = MB(); mb.box(xa, xb, ya, yb, -0.3, 0.0, 'SKY_Pearl')
        a.part(mb, bevel=0.04, seg=1, name="acope")
        mb = MB(); mb.box(xa, xb, yb, sgn * H, -0.3, 0.0, 'SKY_Sandstone')
        a.part(mb, name="atop")
    # piers carrying the arch springing (in front of the abutment face)
    mb = MB(); mbc = MB()
    for s in (-1, 1):
        x0, x1 = s * 4.2, s * 5.4
        yA, yB = ABUT * sgn, PIER * sgn
        mb.box(x0, x1, yA, yB, -4.0, -0.75, 'SKY_Sandstone')
        mbc.box(x0 - s * 0.07, x1 + s * 0.07, yA, yB - sgn * 0.07, -0.75, -0.6, 'SKY_Pearl')
    a.part(mb, bevel=0.05, seg=1, name="piers")
    a.part(mbc, bevel=0.03, seg=1, name="pier_caps")


def arch_curve(y_spring, z_spring, z_crown, n=14):
    """Segmental circular arch from +y_spring to -y_spring through the crown at y=0."""
    hw = y_spring
    rise = z_crown - z_spring
    rr = (hw * hw + rise * rise) / (2 * rise)
    cz = z_crown - rr
    a0 = math.degrees(math.atan2(z_spring - cz, hw))
    return [(rr * math.cos(math.radians(a)), cz + rr * math.sin(math.radians(a))) for a in
            [a0 + (180 - 2 * a0) * i / n for i in range(n + 1)]], (rr, cz)


ARCH_ZS, ARCH_ZC, RING_T = -2.4, -0.85, 0.38


def bridge_arch(a, keep=None):
    """Spandrel body (sandstone) + pearl arch rings on both faces. keep: keep only |y| >= keep (broken)."""
    crv, (rr, cz) = arch_curve(PIER, ARCH_ZS, ARCH_ZC, 14)
    ext = []
    for (y, z) in crv:
        ang = math.atan2(z - cz, y)
        ext.append(((rr + RING_T) * math.cos(ang), cz + (rr + RING_T) * math.sin(ang)))
    if keep is None:
        body = [(-PIER, -DECK_T), (PIER, -DECK_T)] + crv
        mb = MB()
        mb.prism_frame(body, (0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), -4.8, 4.8, 'SKY_SandstoneDeep',
                       front='SKY_Sandstone', back='SKY_Sandstone')
        a.part(mb, bevel=0.04, seg=1, name="spandrel")
        ring = crv + list(reversed(ext))
        for s in (-1, 1):
            mb = MB()
            mb.prism_frame(ring, (0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), s * 4.75, s * 5.2, 'SKY_Pearl')
            a.part(mb, bevel=0.035, seg=1, name="ring")
        mb = MB()
        for s in (-1, 1):
            mb.box(s * 4.75, s * 5.23, -0.32, 0.32, ARCH_ZC - 0.08, FASCIA_BOT + 0.01, 'SKY_Pearl')
        a.part(mb, bevel=0.03, seg=1, name="keystone")
        return
    for sgn in (-1, 1):
        idx = [i for i, p in enumerate(crv) if p[0] * sgn >= keep]
        inner = [crv[i] for i in idx]
        outer = [ext[i] for i in idx]
        if sgn < 0:
            inner, outer = list(reversed(inner)), list(reversed(outer))
        mid = ((inner[-1][0] + outer[-1][0]) / 2 - sgn * 0.25, (inner[-1][1] + outer[-1][1]) / 2 + 0.05)
        poly = inner + [mid] + list(reversed(outer))
        mb = MB()
        mb.prism_frame(poly, (0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), -4.9, 4.9, 'SKY_Pearl',
                       front='SKY_SandstoneDeep', back='SKY_SandstoneDeep')
        a.part(mb, bevel=0.03, seg=1, name="springer")


BR_AO = dict(ground_z=None, dist=1.2, rays=24, strength=0.75, floor=0.45, inset=0.15)
BR_RENDER = dict(az=62.0, el=18.0, water=True, seabed=-4.0)


def pylon(a, x, y):
    mb = MB()
    mb.box(x - 0.26, x + 0.26, y - 0.26, y + 0.26, 0.28, 1.62, 'SKY_Pearl')
    a.part(mb, bevel=0.03, seg=1, name="pylon")
    mb = MB()
    mb.lathe([(0, 1.62), (0.27, 1.62), (0.27, 1.69), (0.15, 1.72), (0, 1.72)], 6, 'SKY_Brass', cx=x, cy=y, a0=30)
    mb.lathe([(0, 2.02), (0.25, 2.02), (0.1, 2.18), (0.03, 2.26), (0, 2.3)], 6, 'SKY_Brass', cx=x, cy=y, a0=30)
    a.part(mb, name="lantern_frame")
    mb = MB()
    mb.cyl(0.15, 1.72, 2.02, 6, 'SKY_Light', cx=x, cy=y, r_top=0.18)
    a.part(mb, name="lantern")


@asset("bridge_span", "Roads", "bridges", ao=BR_AO, render=BR_RENDER)
def bridge_span(a):
    bridge_deck_surface(a)
    bridge_fascia(a, -H, H)
    for s in (-1, 1):
        balustrade(a, -H + 0.45, H - 0.45, [-4.0, 0.0, 4.0], s, ends=(-H + 0.45, H - 0.45))
    for sg in (-1, 1):
        bridge_abutment(a, sg)
    bridge_arch(a)
    k = 0
    for s in (-1, 1):
        for sg in (-1, 1):
            x, y = s * (DECK_HW + 0.125), sg * (H - 0.45)
            pylon(a, x, y)
            a.empty(f"LIGHT_lantern_{k}", (x, y, 1.9))
            k += 1
    a.notes.append("Deck top Z0 (8 m asphalt + 1 m walkways at Z0.15). Abutments fill the 1.5 m channel margins "
                   "at both cell edges, continuing the quay line; arch springs from piers at |y|=5.8.")


def jag_poly(x0, x1, y_break, sg, rnd, n=3):
    """Broken slab chunk: from the clean break line (overlapping 2 cm into the deck) outward to jagged teeth."""
    teeth = []
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        d = (0.25 + 0.55 * rnd.random()) if 0 < i < n else 0.15 + 0.2 * rnd.random()
        teeth.append((x, y_break - sg * d))
    return [(x0, y_break + sg * 0.02), (x1, y_break + sg * 0.02)] + list(reversed(teeth))


def striped_beam_x(mb, x0, x1, y0, y1, z0, z1, n, mats):
    rings = []
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        rings.append([(x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1)])
    mb.loft(rings, mats[0], mats=[mats[i % len(mats)] for i in range(n)])


@asset("bridge_stub", "Roads", "bridges", ao=BR_AO, render=dict(BR_RENDER, az=55.0, el=24.0))
def bridge_stub(a):
    """Empty bridge socket: broken deck ends jut ~2.5 m from both cell edges, barriers before the breaks."""
    for sg in (-1, 1):
        y_edge = sg * H
        y_break = sg * (H - 2.0)
        ya, yb = sorted((y_edge, y_break))
        bridge_deck_surface(a, ya, yb, dash=False)
        bridge_fascia(a, ya, yb)
        for s in (-1, 1):
            p_out = sg * (H - 0.3)
            p_in = sg * (H - 1.85)
            balustrade(a, min(p_out, p_in) - 0.12, max(p_out, p_in) + 0.12, [p_out, p_in], s, spacing=0.45)
        rnd = random.Random(11 + sg)
        xs = [-DECK_HW - 0.25, -2.6, 0.3, 2.9, DECK_HW + 0.25]
        for k in range(len(xs) - 1):
            poly = jag_poly(xs[k], xs[k + 1], y_break, sg, rnd)
            top = -0.05 - 0.14 * rnd.random()
            bot = -DECK_T - 0.15 - 0.35 * rnd.random()
            mb = MB(); mb.prism(poly, bot, top, 'SKY_SandstoneDeep', top='SKY_Kerb')
            a.part(mb, bevel=0.03, seg=1, name="break")
        yb_ = sg * (H - 1.35)
        mb = MB()
        striped_beam_x(mb, -RW + 0.25, RW - 0.25, yb_ - 0.07, yb_ + 0.07, 0.55, 0.88, 12, ['SKY_Coral', 'SKY_Pearl'])
        a.part(mb, bevel=0.015, seg=1, name="barrier_beam")
        mb = MB()
        for x in (-RW + 0.7, 0.0, RW - 0.7):
            mb.box(x - 0.05, x + 0.05, yb_ - 0.04, yb_ + 0.04, 0.06, 0.6, 'SKY_Pearl')
            mb.box(x - 0.09, x + 0.09, yb_ - 0.32, yb_ + 0.32, 0.0, 0.07, 'SKY_Ink')
        for x in (-RW + 0.7, RW - 0.7):
            mb.cyl(0.07, 0.88, 1.0, 8, 'SKY_Coral', cx=x, cy=yb_)
        a.part(mb, name="barrier_legs")
        bridge_abutment(a, sg)
    bridge_arch(a, keep=3.6)
    mb = MB()
    mb.prism(circle(0.85, 7, 0.4, 0.2), -4.0, -0.95, 'SKY_Sandstone', top='SKY_SandstoneDeep')
    a.part(mb, bevel=0.06, seg=1, name="stump")
    mb = MB()
    mb.prism([(-0.6, -0.5), (1.1, -0.7), (1.3, 0.55), (-0.2, 0.75)], -1.3, -0.95, 'SKY_Sandstone')
    mb.transform(M_tr(-2.3, 0.9, 0) @ M_rot(20))
    mb2 = MB()
    mb2.prism([(-0.4, -0.3), (0.7, -0.4), (0.6, 0.45), (-0.3, 0.3)], -1.35, -1.05, 'SKY_Pearl')
    mb2.transform(M_tr(2.4, -1.2, 0) @ M_rot(-35))
    a.part(mb, bevel=0.05, seg=1, name="debris")
    a.part(mb2, bevel=0.05, seg=1, name="debris2")
    a.notes.append("Broken deck ends reach ~2.2-2.8 m from each cell edge; coral/pearl barriers at |y|=6.65.")
