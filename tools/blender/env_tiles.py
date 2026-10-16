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


