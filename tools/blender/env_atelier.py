"""SKYFOLD environment kit - Fold Station kiosk and the Fold Atelier set
(terrace platform, pergola with sails, miniature-city plinth and its piece tray).

Unity north (+Z) = Blender -Y. The atelier pieces share one origin: the terrace centre at Z0
(platform top). The plinth and the tray share the plinth origin (floor centre under the table).

Detail pass: brass-framed portal kiosk with a segmented lens ring, console and canopy; terrace floor
with flush brass / teal / sandstone inlays (the floor stays flat for the mesh collider), turned-baluster
balustrade, stepped approach; pergola columns with bases and capitals, shaped rafter ends, purlins and
climbing bougainvillea; ornate layered pedestal under the miniature city; slotted piece tray with brass
rims. Helpers that used to come from env_buildings are local, so this file only depends on env_common
and env_tiles.
"""
from env_common import *
from env_tiles import reg, surf, KPath, kerb_layout, kerb_stones, extrude, circle_pts, seg_strip, ring_poly

AT_AO = dict(ground_z=0.0, dist=1.0, rays=28, strength=0.7, floor=0.48, inset=0.12, power=1.2)
AT_RENDER = dict(az=35.0, el=24.0)


# --------------------------------------------------------------------------- local helpers

def arch_band(w, h, t, kind='round', seg=8):
    """Band polygon around an arch opening of width w and height h (thickness t)."""
    O = arch_pts(w + 2 * t, h + t, kind, seg)
    I = arch_pts(w, h, kind, seg)
    return [O[1]] + O[2:] + [O[0]] + [I[0]] + list(reversed(I[2:])) + [I[1]]


def loft_outline(a, outline, profile, cap_top='SKY_Pearl', name="shell", bevel=0.0, target=None):
    """profile: list of (offset_out, z, mat_of_band_above). Rings offset from a CCW outline."""
    rings, mats = [], []
    for i, (off, z, m) in enumerate(profile):
        ring2 = offset_line(outline, -off, closed=True) if abs(off) > 1e-6 else outline
        rings.append([(p[0], p[1], z) for p in ring2])
        if i < len(profile) - 1:
            mats.append(m)
    mb = MB()
    mb.loft(rings, mats[0], mats=mats + [cap_top])
    a.part(mb, bevel=bevel, seg=1, name=name, target=target)


def sail_mesh(mb, corners, mat='SKY_Fabric', sag=0.25, n=4, t=0.03):
    """Tensioned shade sail over 3 or 4 corner points: sagging surface with thickness (closed solid)."""
    C = [Vector(c) for c in corners]
    nrm = (C[1] - C[0]).cross(C[2] - C[0])
    if nrm.length < 1e-9:
        nrm = Vector((0, 0, 1))
    nrm.normalize()
    if nrm.z < -1e-3:
        nrm = -nrm
    pts, faces = {}, []
    for i in range(n + 1):
        for j in range(n + 1):
            u, v = i / n, j / n
            p = C[0].lerp(C[1], u).lerp(C[3].lerp(C[2], u), v)
            pts[(i, j)] = p - nrm * (sag * 16 * u * (1 - u) * v * (1 - v))
    for i in range(n):
        for j in range(n):
            faces.append([(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)])
    T = {k: mb.v(p) for k, p in pts.items()}
    B = {k: mb.v(p - nrm * t) for k, p in pts.items()}
    fs, edge_count = [], {}
    for f in faces:
        fs.append(mb.f([T[k] for k in f], mat))
        fs.append(mb.f([B[k] for k in reversed(f)], mat))
        for k in range(len(f)):
            key = tuple(sorted((f[k], f[(k + 1) % len(f)])))
            edge_count[key] = edge_count.get(key, 0) + 1
    for f in faces:
        for k in range(len(f)):
            a_, b_ = f[k], f[(k + 1) % len(f)]
            if edge_count[tuple(sorted((a_, b_)))] == 1:
                fs.append(mb.f([T[b_], T[a_], B[a_], B[b_]], mat))
    mb._recalc(fs)
    return fs


def torus(mb, R, r, seg, sides, mat, center=(0, 0, 0), axis='Y', a0=0.0, a1=360.0):
    """Torus (or a capped torus arc a0..a1 deg) whose ring lies in the plane perpendicular to `axis`."""
    cx, cy, cz = center
    full = abs(a1 - a0) >= 359.999
    n = seg if full else max(1, seg)
    rings = []
    for i in range(n if full else n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        ring = []
        for j in range(sides):
            b = 2 * math.pi * j / sides
            rr = R + r * math.cos(b)
            if axis == 'Y':
                p = (cx + rr * math.cos(a), cy + r * math.sin(b), cz + rr * math.sin(a))
            else:
                p = (cx + rr * math.cos(a), cy + rr * math.sin(a), cz + r * math.sin(b))
            ring.append(p)
        rings.append(ring)
    V = [[mb.v(p) for p in ring] for ring in rings]
    fs = []
    m = len(V) if full else len(V) - 1
    for i in range(m):
        A, B = V[i], V[(i + 1) % len(V)]
        for j in range(sides):
            j2 = (j + 1) % sides
            fs.append(mb.f([A[j], B[j], B[j2], A[j2]], mat))
    if not full:
        fs.append(mb.f(list(reversed(V[0])), mat))
        fs.append(mb.f(list(V[-1]), mat))
    mb._recalc(fs)
    return fs


def cyl_y(mb, r, y0, y1, seg, mat, x=0.0, z=0.0):
    """Closed cylinder with its axis along Y from y0 to y1, centred on (x, z)."""
    fs = mb.lathe([(0, 0), (r, 0), (r, abs(y1 - y0)), (0, abs(y1 - y0))], seg, mat)
    M = M_tr(x, min(y0, y1), z) @ Matrix.Rotation(math.radians(-90), 4, 'X')
    mb.transform(M, fs)
    return fs


# --------------------------------------------------------------------------- fold station

@asset("foldstation_kiosk", "Atelier", "atelier", ao=AT_AO, render=dict(AT_RENDER, el=16.0))
def foldstation_kiosk(a):
    """Street Fold Station: pearl arched stele (~3 m) on a stepped base, brass-framed portal niche holding
    a layered teal lens, segmented brass bezel and a segmented glowing ring ('LensRing', separate object,
    pivot at its centre) facing Unity north, angled console with a glowing palm pad, curved pearl canopy
    with a brass lip, teal side light slots, brass finial. ANCHOR_player 1.8 m in front on an inlaid plate."""
    W, D, H_ = 1.5, 0.62, 2.75
    Z0 = 0.3
    yf = -D / 2
    lz = 1.72
    # stepped base with a brass trim band
    mb = MB()
    mb.prism(rrect(2.1, 1.3, 0.35, 4), 0.0, 0.12, 'SKY_SandstoneDeep')
    a.part(mb, bevel=0.03, seg=2, name="base0")
    mb = MB()
    mb.prism(rrect(1.9, 1.1, 0.3, 4), 0.12, 0.24, 'SKY_Sandstone')
    a.part(mb, bevel=0.025, seg=2, name="base1")
    mb = MB()
    mb.prism(rrect(1.74, 0.94, 0.26, 4), 0.24, Z0, 'SKY_Pearl')
    a.part(mb, bevel=0.02, seg=2, name="base2")
    mb = MB()
    mb.prism(rrect(1.935, 1.135, 0.31, 4), 0.2, 0.225, 'SKY_Brass')
    a.part(mb, name="base_trim")
    # stele body with a front portal niche and a shallow back panel (booleans before the bevel)
    nw, nh, nb = 1.2, 2.08, 0.62
    mb = MB()
    mb.prism_frame(arch_pts(nw, nh, 'round', 16, base=nb), (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0),
                   yf - 0.2, yf + 0.07, 'SKY_Ivory')
    cut_f = a.cutter(mb, "niche_cut")
    mb = MB()
    mb.prism_frame(arch_pts(1.0, 1.75, 'round', 12, base=0.75), (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0),
                   -yf - 0.05, -yf + 0.2, 'SKY_TealLight')
    cut_b = a.cutter(mb, "back_cut")
    mb = MB()
    mb.prism_frame(arch_pts(W, H_, 'round', 20, base=Z0), (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), yf, -yf,
                   'SKY_Pearl')
    a.part(mb, bevel=0.03, seg=2, cutters=[cut_f, cut_b], name="body")
    # brass portal frames (front niche, back panel)
    mb = MB()
    band = [(p[0], p[1] + nb) for p in arch_band(nw, nh, 0.065, 'round', 16)]
    mb.prism_frame(band, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), yf - 0.022, yf + 0.01, 'SKY_Brass')
    band = [(p[0], p[1] + 0.75) for p in arch_band(1.0, 1.75, 0.04, 'round', 12)]
    mb.prism_frame(band, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), -yf - 0.01, -yf + 0.016, 'SKY_Brass')
    a.part(mb, bevel=0.006, seg=1, name="frame")
    star = []
    for k in range(16):
        ang = math.radians(90 + 22.5 * k)
        rr = (0.34 if k % 4 == 0 else 0.2) if k % 2 == 0 else 0.09
        star.append((rr * math.cos(ang), 1.55 + rr * math.sin(ang)))
    mb = MB()
    mb.prism_frame(star, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), -yf - 0.058, -yf - 0.045, 'SKY_Brass')
    a.part(mb, name="back_star")
    # layered lens in the niche: ink surround, teal lens, light-teal iris, ink pupil
    mb = MB()
    yn = yf + 0.07
    for (r, d, mat) in ((0.5, 0.015, 'SKY_Ink'), (0.44, 0.03, 'SKY_Teal'), (0.27, 0.042, 'SKY_TealLight'),
                        (0.09, 0.05, 'SKY_Ink')):
        cyl_y(mb, r, yn, yn - d, 24, mat, 0.0, lz)
    a.part(mb, name="lens")
    # segmented brass bezel (8 arcs) just proud of the face
    mb = MB()
    for k in range(8):
        a0_ = 45 * k + 2.5
        torus(mb, 0.6, 0.045, 5, 6, 'SKY_Brass', center=(0, yf - 0.03, lz), axis='Y', a0=a0_, a1=a0_ + 40)
    a.part(mb, name="bezel")
    # LensRing (separate object, pivot at the ring centre): 12 glowing segments held by brass clips
    mb = MB()
    for k in range(12):
        a0_ = 30 * k + 2.0
        torus(mb, 0.52, 0.07, 3, 8, 'SKY_TealGlow', center=(0, yf - 0.08, lz), axis='Y', a0=a0_, a1=a0_ + 26)
    a.part(mb, target="LensRing", name="ring")
    a.set_target("LensRing", pivot=(0, yf - 0.08, lz))
    mb = MB()
    for k in range(12):
        ang = math.radians(30 * k)
        cx_, cz_ = 0.52 * math.cos(ang), lz + 0.52 * math.sin(ang)
        fs = mb.box(-0.022, 0.022, -0.06, 0.06, -0.085, 0.085, 'SKY_Brass')
        mb.transform(M_tr(cx_, yf - 0.08, cz_) @ Matrix.Rotation(-ang, 4, 'Y'), fs)
    a.part(mb, bevel=0.008, seg=1, name="ring_clips")
    # console: angled pearl lectern under the lens, ink panel with a glowing palm pad
    yb_ = yf + 0.075                       # console back sits on the niche floor
    prof = [(yb_, Z0), (-0.6, Z0), (-0.6, Z0 + 0.06), (-0.56, Z0 + 0.09), (-0.56, 0.9), (-0.66, 0.96),
            (-0.66, 1.0), (yb_, 1.13)]
    mb = MB()
    mb.prism_frame([(p[0], p[1]) for p in prof], (0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), -0.27, 0.27, 'SKY_Pearl')
    a.part(mb, bevel=0.015, seg=2, angle=25.0, name="console")
    slope = math.atan2(1.13 - 1.0, yb_ - (-0.66))
    cy0, cz0 = (-0.66 + yb_) / 2, (1.0 + 1.13) / 2
    Mp = M_tr(0, cy0, cz0) @ Matrix.Rotation(slope, 4, 'X')
    mb = MB()
    fs = mb.box(-0.21, 0.21, -0.15, 0.15, 0.0, 0.012, 'SKY_Brass')
    mb.transform(Mp, fs)
    a.part(mb, bevel=0.005, seg=1, name="console_frame")
    mb = MB()
    fs = mb.box(-0.18, 0.18, -0.125, 0.125, 0.008, 0.018, 'SKY_Ink')
    fs += mb.lathe([(0, 0.016), (0.075, 0.016), (0.075, 0.024), (0, 0.024)], 16, 'SKY_TealGlow')
    mb.transform(Mp, fs)
    a.part(mb, name="console_panel")
    # curved canopy hood over the arch top with a brass lip
    sc = Z0 + H_ - W / 2
    mb = MB()
    hood = arc(0, sc, 0.86, -14, 194, 20) + arc(0, sc, 0.74, 194, -14, 20)
    mb.prism_frame(hood, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), yf - 0.42, yf + 0.16, 'SKY_Pearl')
    a.part(mb, bevel=0.012, seg=1, angle=25.0, name="canopy")
    mb = MB()
    lip = arc(0, sc, 0.875, -14, 194, 20) + arc(0, sc, 0.735, 194, -14, 20)
    mb.prism_frame(lip, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), yf - 0.45, yf - 0.42, 'SKY_Brass')
    a.part(mb, name="canopy_lip")
    mb = MB()
    glow = arc(0, sc, 0.738, -8, 188, 20) + arc(0, sc, 0.726, 188, -8, 20)
    mb.prism_frame(glow, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), yf - 0.4, yf - 0.37, 'SKY_TealGlow')
    a.part(mb, name="canopy_glow")
    # finial on the hood crown
    mb = MB()
    zt = sc + 0.86
    mb.lathe([(0, zt - 0.03), (0.11, zt - 0.03), (0.11, zt + 0.0), (0.06, zt + 0.03), (0.085, zt + 0.075),
              (0.06, zt + 0.115), (0.016, zt + 0.142), (0, 3.31)], 10, 'SKY_Brass', cy=yf - 0.12)
    a.part(mb, name="finial")
    # teal light slots on the stele sides
    mb = MB()
    for s in (-1, 1):
        mb.box(s * (W / 2) - 0.03, s * (W / 2) + 0.03, -0.1, 0.1, 0.55, 1.95, 'SKY_TealGlow')
    a.part(mb, name="side_glow")
    mb = MB()
    for s in (-1, 1):
        for z in (0.5, 1.95):
            mb.box(s * (W / 2) - 0.04, s * (W / 2) + 0.04, -0.13, 0.13, z - 0.025, z + 0.025, 'SKY_Brass')
    a.part(mb, bevel=0.008, seg=1, name="side_glow_caps")
    # standing plate where the player stands: brass ring, pearl disc, light-teal ring and brass spokes
    mb = MB()
    mb.lathe([(0, 0.0), (0.55, 0.0), (0.55, 0.018), (0.53, 0.024), (0, 0.024)], 32, 'SKY_Brass', cy=-1.8)
    a.part(mb, name="plate_ring")
    mb = MB()
    mb.lathe([(0, 0.0), (0.48, 0.0), (0.48, 0.03), (0, 0.03)], 32, 'SKY_Pearl', cy=-1.8)
    a.part(mb, name="plate")
    mb = MB()
    mb.lathe([(0.3, 0.03), (0.35, 0.03), (0.35, 0.033), (0.3, 0.033)], 32, 'SKY_TealLight', cy=-1.8, closed=True)
    for k in range(8):
        ang = math.radians(22.5 + 45 * k)
        fs = mb.box(0.36, 0.46, -0.008, 0.008, 0.03, 0.033, 'SKY_Brass')
        mb.transform(M_tr(0, -1.8, 0) @ Matrix.Rotation(ang, 4, 'Z'), fs)
    a.part(mb, name="plate_inlay")
    a.empty("ANCHOR_player", (0.0, -1.8, 0.0), rot_z=180.0)
    a.notes.append("LensRing pivot at the ring centre (Blender (0,-0.39,1.72)). ANCHOR_player is yawed 180 deg so its "
                   "forward faces the kiosk.")


# --------------------------------------------------------------------------- terrace

TER_R = 7.0
BAL_R = 6.75
GAP = 14.0


def baluster_turned(mb, x, y, z0, h=0.74, sides=6):
    """Turned (lathe) pearl baluster: foot, swelling belly, neck, flared collar."""
    prof = [(0, z0), (0.056, z0), (0.068, z0 + 0.24 * h), (0.031, z0 + 0.6 * h), (0.052, z0 + h), (0, z0 + h)]
    mb.lathe(prof, sides, 'SKY_Pearl', cx=x, cy=y, a0=30)


def balustrade_arc(a, r, a0, a1, post_angs, zt=0.0, h=1.0, name="bal", spacing=0.5):
    """Circular balustrade between angles a0..a1 (deg) at radius r: moulded plinth rail, turned balusters,
    pedestal posts with brass finials, rounded handrail."""
    n = max(6, int(abs(a1 - a0) / 7.0))
    path = [(r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), r * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
            for i in range(n + 1)]
    nrm = [(p[0] / r, p[1] / r) for p in path]
    # plinth rail (d = radial offset outward, z): chamfered pearl band
    plinth = [(-0.12, zt), (0.12, zt), (0.12, zt + 0.07), (0.08, zt + 0.1), (-0.08, zt + 0.1), (-0.12, zt + 0.07)]
    rail = [(-0.09, zt + h - 0.14), (0.09, zt + h - 0.14), (0.09, zt + h - 0.07), (0.0, zt + h - 0.015),
            (-0.09, zt + h - 0.07)]
    mb = MB()
    extrude(mb, path, nrm, plinth, 'SKY_Pearl')
    extrude(mb, path, nrm, rail, 'SKY_Pearl')
    a.part(mb, name=name + "_rails")
    mb = MB()
    mbf = MB()
    for ang in post_angs:
        c = (r * math.cos(math.radians(ang)), r * math.sin(math.radians(ang)))
        M = M_tr(c[0], c[1], 0) @ M_rot(ang)
        fs = mb.box(-0.15, 0.15, -0.15, 0.15, zt, zt + 0.16, 'SKY_Pearl')
        fs += mb.box(-0.125, 0.125, -0.125, 0.125, zt + 0.16, zt + h + 0.04, 'SKY_Pearl')
        fs += mb.box(-0.16, 0.16, -0.16, 0.16, zt + h + 0.04, zt + h + 0.1, 'SKY_Pearl')
        mb.transform(M, fs)
        mbf.lathe([(0, zt + h + 0.1), (0.075, zt + h + 0.1), (0.05, zt + h + 0.14), (0.07, zt + h + 0.2),
                   (0.03, zt + h + 0.26), (0, zt + h + 0.29)], 6, 'SKY_Brass', cx=c[0], cy=c[1], a0=ang + 30)
    a.part(mb, bevel=0.018, seg=1, name=name + "_posts")
    a.part(mbf, name=name + "_caps")
    # balusters between posts
    mb = MB()
    stops = sorted([a0] + list(post_angs) + [a1])
    for k in range(len(stops) - 1):
        g0 = stops[k] + math.degrees((0.2 if stops[k] in post_angs else 0.12) / r)
        g1 = stops[k + 1] - math.degrees((0.2 if stops[k + 1] in post_angs else 0.12) / r)
        span = math.radians(g1 - g0) * r
        nb = max(1, int(round(span / spacing)) + 1)
        for i in range(nb):
            t = math.radians(g0 + (g1 - g0) * (i / (nb - 1) if nb > 1 else 0.5))
            baluster_turned(mb, r * math.cos(t), r * math.sin(t), zt + 0.1, h - 0.24)
    a.part(mb, name=name + "_balusters")


def rock_ring(mb, rings, seg, mat, seed=1, jitter=0.35, zjit=0.15, calm_first=True):
    rnd = random.Random(seed)
    pts = []
    for ri, (r, z) in enumerate(rings):
        ring = []
        calm = calm_first and ri == 0
        for k in range(seg):
            ang = 2 * math.pi * (k + (0 if calm else rnd.uniform(-0.2, 0.2))) / seg
            rr = r + (0 if calm else rnd.uniform(-jitter, jitter))
            ring.append((rr * math.cos(ang), rr * math.sin(ang), z + (0 if calm else rnd.uniform(-zjit, zjit))))
        pts.append(ring)
    return mb.loft(pts, mat)


def urn_planter(a, x, y, z=0.0, s=1.0, seed=3):
    """Terracotta urn on a pearl foot with a clipped shrub and bougainvillea blossoms."""
    mb = MB()
    mb.lathe([(0, z), (0.24 * s, z), (0.24 * s, z + 0.08 * s), (0.17 * s, z + 0.12 * s)], 10, 'SKY_Pearl', cx=x, cy=y)
    a.part(mb, name="urn_foot")
    mb = MB()
    mb.lathe([(0.17 * s, z + 0.12 * s), (0.3 * s, z + 0.3 * s), (0.33 * s, z + 0.5 * s), (0.3 * s, z + 0.62 * s),
              (0.36 * s, z + 0.66 * s), (0.36 * s, z + 0.72 * s), (0.0, z + 0.72 * s)], 12, 'SKY_Terracotta', cx=x, cy=y)
    a.part(mb, name="urn")
    mb = MB()
    mb.sphere(0.42 * s, 8, 5, 'SKY_PalmLeaf', c=(x, y, z + 0.98 * s), sz=0.85)
    a.part(mb, name="urn_shrub")
    rnd = random.Random(seed)
    mb = MB()
    for k in range(5):
        t = rnd.uniform(0, 2 * math.pi)
        e = rnd.uniform(0.2, 0.9)
        p = (x + 0.4 * s * math.cos(t) * math.cos(e), y + 0.4 * s * math.sin(t) * math.cos(e),
             z + 0.98 * s + 0.36 * s * math.sin(e))
        mb.sphere(0.09 * s, 6, 3, 'SKY_Flower', c=p)
    a.part(mb, name="urn_flowers")


@asset("atelier_platform", "Atelier", "atelier", ao=dict(AT_AO, ground_z=None, dist=1.4), render=dict(AT_RENDER, el=30.0))
def atelier_platform(a):
    """Circular pearl terrace (14 m) on a short rocky plinth, top at Z0 and perfectly flat (mesh collider):
    flush sandstone / brass / teal radial inlays and a compass-star medallion; moulded cornice and brass
    band at the deck edge; turned-baluster balustrade with a stepped gap on the Unity-north edge (Blender -Y)
    flanked by gateposts and urn planters."""
    R_ = TER_R
    R = [reg(circle(R_, 64), 0.0, 'SKY_Pearl', 0)]
    R.append(reg(circle(R_, 64), 0.0, 'SKY_Sandstone', 1))
    R.append(reg(circle(6.42, 64), 0.0, 'SKY_Brass', 2))
    R.append(reg(circle(6.37, 64), 0.0, 'SKY_Pearl', 3))
    R.append(reg(circle(5.45, 48), 0.0, 'SKY_Sandstone', 4))
    R.append(reg(circle(5.345, 48), 0.0, 'SKY_Teal', 5))
    R.append(reg(circle(5.305, 48), 0.0, 'SKY_Sandstone', 6))
    R.append(reg(circle(5.2, 48), 0.0, 'SKY_Pearl', 7))
    for k in range(16):
        ang = math.radians(11.25 + 22.5 * k)
        u = Vector((math.cos(ang), math.sin(ang)))
        if k % 2 == 0:
            R.append(reg(seg_strip(u * 2.25, u * 5.15, 0.13), 0.0, 'SKY_Sandstone', 8))
            R.append(reg(seg_strip(u * 2.25, u * 5.15, 0.03), 0.0, 'SKY_Brass', 9))
        else:
            R.append(reg(seg_strip(u * 2.6, u * 5.15, 0.035), 0.0, 'SKY_Teal', 8))
    R.append(reg(circle(2.32, 40), 0.0, 'SKY_Sandstone', 10))
    R.append(reg(circle(2.2, 40), 0.0, 'SKY_Brass', 11))
    R.append(reg(circle(2.16, 40), 0.0, 'SKY_Ivory', 12))
    star = []
    for k in range(16):
        ang = math.radians(22.5 * k)
        rr = (1.95 if k % 4 == 0 else 1.35) if k % 2 == 0 else 0.75
        star.append((rr * math.cos(ang), rr * math.sin(ang)))
    R.append(reg(star, 0.0, 'SKY_Sandstone', 13))
    R.append(reg(circle(0.42, 24), 0.0, 'SKY_Brass', 14))
    R.append(reg(circle(0.36, 24), 0.0, 'SKY_Teal', 15))
    surf(a, R, base_z=-0.55, side_mat='SKY_Pearl', bounds=(-99, 99, -99, 99), name="deck")
    a.set_target(a.name, smooth=30.0)
    # deck edge: pearl cornice moulding and the brass band below it
    # (open at the stair gap so the top step stays clear)
    g0, g1 = 270 + GAP - 1.0, 270 + 360 - GAP + 1.0
    n = 40
    dirs = [(math.cos(math.radians(g0 + (g1 - g0) * i / n)), math.sin(math.radians(g0 + (g1 - g0) * i / n)))
            for i in range(n + 1)]
    mb = MB()
    extrude(mb, [(0.0, 0.0)] * (n + 1), dirs, [(R_ - 0.02, -0.16), (R_ + 0.06, -0.16), (R_ + 0.1, -0.11),
                                              (R_ + 0.1, -0.06), (R_ + 0.06, -0.02), (R_ - 0.02, -0.02)], 'SKY_Pearl')
    a.part(mb, name="cornice")
    mb = MB()
    mb.lathe([(R_ - 0.02, -0.6), (R_ + 0.12, -0.6), (R_ + 0.12, -0.42), (R_ - 0.02, -0.42)], 48, 'SKY_Brass',
             closed=True)
    a.part(mb, name="rim_brass")
    # rocky plinth under the deck
    mb = MB()
    rock_ring(mb, [(R_ - 0.3, -0.6), (R_ + 0.25, -1.0), (R_ + 0.45, -1.55), (R_ + 0.75, -2.15), (R_ + 0.95, -2.8),
                   (R_ + 1.1, -3.4)], 22, 'SKY_SandstoneDeep', seed=4)
    a.part(mb, name="rock")
    # balustrade with a gap on Blender -Y (Unity north) at 270 +/- GAP
    posts = [270 + GAP + 332.0 * k / 11 for k in range(1, 11)]
    balustrade_arc(a, BAL_R, 270 + GAP, 270 + 360 - GAP, posts, zt=0.0)
    # gateposts with brass orbs
    mb = MB()
    mbo = MB()
    mbt = MB()
    for s in (-1, 1):
        ang = math.radians(270 + s * GAP)
        c = (BAL_R * math.cos(ang), BAL_R * math.sin(ang))
        fs = mb.box(-0.3, 0.3, -0.3, 0.3, 0.0, 0.18, 'SKY_Pearl')
        fs += mb.box(-0.24, 0.24, -0.24, 0.24, 0.18, 1.3, 'SKY_Pearl')
        fs += mb.box(-0.29, 0.29, -0.29, 0.29, 1.3, 1.38, 'SKY_Pearl')
        mb.transform(M_tr(c[0], c[1], 0) @ Matrix.Rotation(ang, 4, 'Z'), fs)
        fs = mbt.box(-0.246, 0.246, -0.246, 0.246, 1.0, 1.05, 'SKY_Teal')
        mbt.transform(M_tr(c[0], c[1], 0) @ Matrix.Rotation(ang, 4, 'Z'), fs)
        mbo.lathe([(0, 1.38), (0.16, 1.38), (0.1, 1.44), (0.08, 1.46)], 10, 'SKY_Brass', cx=c[0], cy=c[1])
        mbo.sphere(0.19, 10, 5, 'SKY_Brass', c=(c[0], c[1], 1.62))
    a.part(mb, bevel=0.025, seg=1, name="gateposts")
    a.part(mbt, name="gatepost_bands")
    a.part(mbo, name="gatepost_orbs")
    # urn planters flanking the gap, inside the balustrade
    for s in (-1, 1):
        ang = math.radians(270 + s * (GAP + 7.5))
        urn_planter(a, 6.05 * math.cos(ang), 6.05 * math.sin(ang), 0.0, 1.0, seed=5 + s)
    # steps down toward the view: pearl treads with rounded nosings between pearl cheek walls
    hw = BAL_R * math.sin(math.radians(GAP)) - 0.3
    rise, run = 0.17, 0.42
    for i in range(4):
        y_front = -R_ - 0.05 - (i + 1) * run
        y_back = -R_ + 0.35 if i == 0 else y_front + run + 0.02
        z_top = -rise * (i + 1)
        prof = [(y_back, -0.62), (y_front, -0.62), (y_front, z_top - 0.035), (y_front + 0.012, z_top - 0.01),
                (y_front + 0.035, z_top), (y_back, z_top)]
        mb = MB()
        mb.prism_frame(prof, (0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), -hw, hw, 'SKY_Pearl')
        a.part(mb, name="step")
    mb = MB()
    for s in (-1, 1):
        cheek = [(-R_ + 0.3, 0.12), (-R_ + 0.3, -0.75), (-R_ - 0.05 - 4 * run - 0.1, -0.75),
                 (-R_ - 0.05 - 4 * run - 0.1, -0.68 + 0.1), (-R_ - 0.2, 0.12)]
        mb.prism_frame(cheek, (0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), s * hw, s * (hw + 0.26), 'SKY_Pearl')
    a.part(mb, bevel=0.02, seg=1, name="cheeks")
    mb = MB()
    mb.box(-hw - 0.3, hw + 0.3, -R_ - 2.6, -R_ - 1.6, -1.6, -0.68, 'SKY_SandstoneDeep')
    a.part(mb, bevel=0.06, seg=1, name="landing")
    a.notes.append("Top of deck at Z0, radius 7 m, flat (inlays are flush); balustrade gap + 4 steps on the "
                   "Unity-north edge.")


# --------------------------------------------------------------------------- pergola

def vine(a, base, top, turns=1.6, r=0.2, seed=1, leaves=20, name="vine"):
    """Climbing bougainvillea: a thin twisting stem around a column with leaf clumps and blossoms."""
    rnd = random.Random(seed)
    b = Vector(base)
    t = Vector(top)
    pts = []
    n = 16
    for i in range(n + 1):
        f = i / n
        ang = 2 * math.pi * turns * f + seed
        pts.append(Vector((b.x + r * math.cos(ang), b.y + r * math.sin(ang), b.z + (t.z - b.z) * f)))
    mb = MB()
    mb.sweep(pts, circle(0.022, 4), 'SKY_PalmTrunk')
    a.part(mb, name=name + "_stem")
    mb = MB()
    mbf = MB()
    for k in range(leaves):
        f = (k + 0.5) / leaves
        p = pts[int(f * n)]
        out = Vector((p.x - b.x, p.y - b.y, 0)).normalized() * rnd.uniform(0.06, 0.14)
        q = p + out + Vector((0, 0, rnd.uniform(-0.1, 0.1)))
        mb.sphere(rnd.uniform(0.08, 0.13), 6, 3, 'SKY_PalmLeaf', c=tuple(q), sz=0.8)
        if k % 3 == 1:
            mbf.sphere(0.055, 5, 3, 'SKY_Flower', c=tuple(q + out * 0.8 + Vector((0, 0, 0.05))))
    a.part(mb, name=name + "_leaves")
    a.part(mbf, name=name + "_flowers")


@asset("atelier_pergola", "Atelier", "atelier", ao=dict(AT_AO, dist=1.4), render=dict(AT_RENDER, el=34.0))
def atelier_pergola(a):
    """Crescent pergola over the southern half of the terrace (Blender +Y): pearl columns with square
    plinths, torus bases, brass collars and capitals; curved timber beams; radial rafters with shaped
    (ogee) ends; purlins; three tensioned shade sails; climbing bougainvillea; terracotta planters.
    Leaves the central plinth area and the north view open."""
    r_in, r_out, hgt = 4.3, 6.5, 3.1
    angs = [32.0, 69.0, 111.0, 148.0]
    mb = MB()
    mbc = MB()
    mbs = MB()
    for ang in angs:
        for r in (r_in, r_out):
            x, y = r * math.cos(math.radians(ang)), r * math.sin(math.radians(ang))
            fs = mbs.box(-0.24, 0.24, -0.24, 0.24, 0.0, 0.12, 'SKY_Sandstone')
            fs += mbs.box(-0.2, 0.2, -0.2, 0.2, hgt - 0.1, hgt, 'SKY_Pearl')
            mbs.transform(M_tr(x, y, 0) @ M_rot(ang), fs)
            mb.lathe([(0, 0.12), (0.2, 0.12), (0.2, 0.15), (0.175, 0.19), (0.16, 0.22), (0.15, 0.27),
                      (0.135, hgt - 0.42), (0.125, hgt - 0.3), (0.15, hgt - 0.22), (0.19, hgt - 0.14),
                      (0.19, hgt - 0.1), (0, hgt - 0.1)], 12, 'SKY_Pearl', cx=x, cy=y)
            mbc.lathe([(0.128, hgt - 0.36), (0.148, hgt - 0.36), (0.148, hgt - 0.31), (0.128, hgt - 0.31)], 12,
                      'SKY_Brass', cx=x, cy=y, closed=True)
    a.part(mb, name="columns")
    a.part(mbs, bevel=0.02, seg=1, name="column_blocks")
    a.part(mbc, name="collars")
    # curved timber beams on the column heads
    a0, a1 = angs[0] - 7.0, angs[-1] + 7.0
    mb = MB()
    for r in (r_in, r_out):
        n = 22
        path = [(r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), r * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
                for i in range(n + 1)]
        nrm = [(p[0] / r, p[1] / r) for p in path]
        prof = [(-0.1, hgt), (0.1, hgt), (0.1, hgt + 0.24), (-0.1, hgt + 0.24)]
        extrude(mb, path, nrm, prof, 'SKY_Wood')
    a.part(mb, bevel=0.012, seg=1, angle=40.0, name="beams")
    # radial rafters with ogee-cut ends resting on the beams
    zr = hgt + 0.24
    mb = MB()
    nraft = 15
    for k in range(nraft):
        ang = a0 + 1.5 + (a1 - a0 - 3.0) * k / (nraft - 1)
        ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        rr0, rr1 = r_in - 0.55, r_out + 0.55
        side = [(rr0, zr + 0.2), (rr0, zr + 0.12), (rr0 + 0.05, zr + 0.06), (rr0 + 0.16, zr + 0.03), (rr0 + 0.3, zr),
                (rr1 - 0.3, zr), (rr1 - 0.16, zr + 0.03), (rr1 - 0.05, zr + 0.06), (rr1, zr + 0.12), (rr1, zr + 0.2)]
        fs = mb.prism_frame(side, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), -0.045, 0.045, 'SKY_Wood')
        mb.transform(Matrix.Rotation(math.radians(ang), 4, 'Z'), fs)
    a.part(mb, name="rafters")
    # purlins along the arcs on top of the rafters
    mb = MB()
    for r in (r_in - 0.2, (r_in + r_out) / 2, r_out + 0.2):
        n = 16
        path = [(r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), r * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
                for i in range(n + 1)]
        nrm = [(p[0] / r, p[1] / r) for p in path]
        extrude(mb, path, nrm, [(-0.035, zr + 0.2), (0.035, zr + 0.2), (0.035, zr + 0.27), (-0.035, zr + 0.27)],
                'SKY_Wood')
    a.part(mb, name="purlins")
    # three sails, one per bay, alternating tilt, hung under the rafters
    for k in range(3):
        b0, b1 = math.radians(angs[k] + 3), math.radians(angs[k + 1] - 3)
        hi, lo = hgt - 0.02, hgt - 0.4
        c = [(r_in * math.cos(b0), r_in * math.sin(b0), lo if k % 2 else hi),
             (r_in * math.cos(b1), r_in * math.sin(b1), hi if k % 2 else lo),
             (r_out * math.cos(b1), r_out * math.sin(b1), lo if k % 2 else hi),
             (r_out * math.cos(b0), r_out * math.sin(b0), hi if k % 2 else lo)]
        mb = MB()
        sail_mesh(mb, c, sag=0.22, n=4)
        a.part(mb, name="sail")
        mb = MB()
        for p in c:
            torus(mb, 0.05, 0.013, 6, 3, 'SKY_Brass', center=p, axis='Z')
        a.part(mb, name="sail_rings")
    # climbing bougainvillea on the outer end columns
    for (ang, seed) in ((angs[0], 2), (angs[-1], 5), (angs[1], 9)):
        x, y = r_out * math.cos(math.radians(ang)), r_out * math.sin(math.radians(ang))
        vine(a, (x, y, 0.15), (x, y, hgt - 0.2), turns=1.4, r=0.19, seed=seed, name="vine")
    # the vines creep along the outer beam from the end columns
    rnd = random.Random(21)
    mb = MB()
    mbf = MB()
    for (g0, g1) in ((angs[0] - 4.0, angs[0] + 16.0), (angs[-1] - 16.0, angs[-1] + 4.0), (angs[1] - 3.0, angs[1] + 9.0)):
        for k in range(9):
            g = math.radians(g0 + (g1 - g0) * (k + rnd.random() * 0.6) / 9)
            rr = r_out + rnd.uniform(0.04, 0.16)
            z = hgt + rnd.uniform(-0.04, 0.3)
            p = (rr * math.cos(g), rr * math.sin(g), z)
            mb.sphere(rnd.uniform(0.09, 0.15), 6, 3, 'SKY_PalmLeaf', c=p, sz=0.75)
            if k % 2 == 0:
                mbf.sphere(0.055, 5, 3, 'SKY_Flower', c=(p[0] * 1.012, p[1] * 1.012, z + 0.07))
    a.part(mb, name="garland")
    a.part(mbf, name="garland_flowers")
    # planters at the column feet (outer ring)
    mb = MB()
    mbr = MB()
    mbl = MB()
    mbf = MB()
    rnd = random.Random(8)
    for ang in (50.5, 90.0, 129.5):
        x, y = (r_out + 0.05) * math.cos(math.radians(ang)), (r_out + 0.05) * math.sin(math.radians(ang))
        M = M_tr(x, y, 0) @ M_rot(ang + 90)
        fs = mb.box(-0.68, 0.68, -0.26, 0.26, 0.06, 0.5, 'SKY_Terracotta')
        fs += mb.box(-0.62, 0.62, -0.2, 0.2, 0.0, 0.06, 'SKY_Terracotta')
        mb.transform(M, fs)
        fs = mbr.box(-0.72, 0.72, -0.3, 0.3, 0.5, 0.56, 'SKY_Pearl')
        mbr.transform(M, fs)
        for dx in (-0.42, 0.0, 0.42):
            px = x + dx * math.cos(math.radians(ang + 90))
            py = y + dx * math.sin(math.radians(ang + 90))
            mbl.sphere(0.3, 8, 4, 'SKY_PalmLeaf', c=(px, py, 0.7), sz=0.85)
            if rnd.random() > 0.3:
                mbf.sphere(0.08, 5, 3, 'SKY_Flower', c=(px + 0.12, py - 0.05, 0.93))
    a.part(mb, bevel=0.025, seg=1, name="planters")
    a.part(mbr, bevel=0.015, seg=1, name="planter_rims")
    a.part(mbl, name="greens")
    a.part(mbf, name="blossoms")
    a.notes.append("Shares the terrace origin with atelier_platform (centre, Z0).")


# --------------------------------------------------------------------------- plinth + tray

PL_W, PL_D, PL_Z = 1.6, 1.2, 0.9


@asset("plinth", "Atelier", "atelier", ao=dict(AT_AO, dist=0.5, inset=0.05), render=dict(AT_RENDER, el=26.0))
def plinth_table(a):
    """Miniature-city table: flat ivory top 1.6 (E-W) x 1.2 (N-S) at Z0.9 with a rounded nosing and a
    brass edge band, separate teal rim 'PlinthRim', moulded pearl frieze with brass beads, ornate waisted
    pedestal of layered mouldings with brass rings and teal light lines, stepped sandstone base with a
    brass kick band. ANCHOR_minicity at the top centre, ANCHOR_player 0.55 m south."""
    top_t = 0.07
    mb = MB()
    mb.prism(rrect(PL_W, PL_D, 0.06, 4), PL_Z - top_t, PL_Z, 'SKY_Ivory')
    a.part(mb, bevel=0.014, seg=2, name="top")
    mb = MB()
    mb.prism(rrect(PL_W + 0.03, PL_D + 0.03, 0.075, 4), PL_Z - top_t - 0.06, PL_Z - top_t + 0.035, 'SKY_Brass')
    a.part(mb, bevel=0.008, seg=2, name="edge_band")
    # PlinthRim: thin glow rim just under the brass band (separate object)
    mb = MB()
    mb.prism(rrect(PL_W + 0.05, PL_D + 0.05, 0.08, 4), PL_Z - top_t - 0.085, PL_Z - top_t - 0.06, 'SKY_TealGlow')
    a.part(mb, target="PlinthRim", name="rim")
    # frieze under the rim: pearl cavetto with a brass bead line
    fo = ccw(rrect(PL_W - 0.1, PL_D - 0.1, 0.05, 4))
    zf1 = PL_Z - top_t - 0.085
    loft_outline(a, fo, [(0.0, zf1 - 0.14, 'SKY_Pearl'), (-0.02, zf1 - 0.1, 'SKY_Pearl'), (-0.02, zf1 - 0.06, 'SKY_Brass'),
                         (0.0, zf1 - 0.055, 'SKY_Brass'), (0.0, zf1 - 0.04, 'SKY_Pearl'), (-0.02, zf1 - 0.035, 'SKY_Pearl'),
                         (-0.01, zf1, 'SKY_Pearl')], cap_top='SKY_Pearl', name="frieze")
    # brass diamond studs along the frieze
    mb = MB()
    zs_ = zf1 - 0.078
    for (xs, ys, ux, uy) in [(x, s_ * 0.55, 1, 0) for x in (-0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6) for s_ in (-1, 1)] + \
                            [(s_ * 0.75, y, 0, 1) for y in (-0.3, -0.1, 0.1, 0.3) for s_ in (-1, 1)]:
        nx, ny = (0, 1 if ys > 0 else -1) if ux else (1 if xs > 0 else -1, 0)
        d = [(0.0, 0.022), (0.022, 0.0), (0.0, -0.022), (-0.022, 0.0)]
        lo = [(xs + ux * u - nx * 0.004, ys + uy * u - ny * 0.004, zs_ + v) for (u, v) in d]
        hi = [(xs + ux * u * 0.4 + nx * 0.012, ys + uy * u * 0.4 + ny * 0.012, zs_ + v * 0.4) for (u, v) in d]
        mb.loft([lo, hi], 'SKY_Brass')
    a.part(mb, name="studs")
    # pedestal: classical layered mouldings on a rounded-rectangle section
    base = ccw(rrect(0.9, 0.62, 0.18, 4))
    zt_ = zf1 - 0.14
    prof = [(0.2, 0.0, 'SKY_SandstoneDeep'), (0.2, 0.06, 'SKY_SandstoneDeep'), (0.17, 0.065, 'SKY_SandstoneDeep'),
            (0.17, 0.115, 'SKY_Brass'), (0.185, 0.12, 'SKY_Brass'), (0.185, 0.145, 'SKY_Brass'),
            (0.14, 0.15, 'SKY_Pearl'), (0.155, 0.17, 'SKY_Pearl'), (0.14, 0.195, 'SKY_Pearl'),
            (0.08, 0.215, 'SKY_Pearl'), (0.03, 0.25, 'SKY_Pearl'), (0.035, 0.29, 'SKY_Pearl'),
            (0.02, 0.38, 'SKY_Pearl'), (-0.02, 0.45, 'SKY_Pearl'), (-0.04, 0.49, 'SKY_Brass'),
            (-0.02, 0.495, 'SKY_Brass'), (-0.02, 0.52, 'SKY_Brass'), (-0.04, 0.525, 'SKY_Pearl'),
            (-0.06, 0.535, 'SKY_Pearl'), (-0.06, 0.57, 'SKY_Pearl'), (-0.02, zt_ - 0.022, 'SKY_Pearl'),
            (0.06, zt_ - 0.01, 'SKY_Pearl'), (0.12, zt_ - 0.004, 'SKY_Pearl'), (0.12, zt_, 'SKY_Pearl')]
    loft_outline(a, base, prof, cap_top='SKY_Pearl', name="pedestal")
    # teal light ring around the neck
    loft_outline(a, base, [(-0.054, 0.541, 'SKY_TealGlow'), (-0.054, 0.562, 'SKY_TealGlow')], cap_top='SKY_TealGlow',
                 name="glow")
    a.empty("ANCHOR_minicity", (0.0, 0.0, PL_Z))
    a.empty("ANCHOR_player", (0.0, PL_D / 2 + 0.55, 0.0))
    a.notes.append("Top surface Z0.9, 1.6 x 1.2 m, flat. ANCHOR_player 0.55 m south of the south edge, facing north.")


@asset("plinth_tray", "Atelier", "atelier", ao=dict(AT_AO, dist=0.15, inset=0.02, ground_z=None),
       render=dict(AT_RENDER, el=40.0))
def plinth_tray(a):
    """Piece tray 1.1 x 0.18 m mounting on the plinth's south edge, top flush at Z0.9: six rounded slots
    recessed 25 mm with brass rims and teal status lights, rounded front nosing, brass trim, gusset
    brackets and a teal light line. Modelled in plinth space: place it with the same transform as 'plinth'."""
    L, Dd, T = 1.1, 0.18, 0.06
    y0 = PL_D / 2 + 0.025
    y1 = y0 + Dd
    n = 6
    pitch = L / n
    sw, sd, depth = 0.15, 0.13, 0.025
    yc = (y0 + y1) / 2
    R = [reg(rect_(-L / 2, L / 2, y0, y1), PL_Z, 'SKY_Pearl', 0)]
    for i in range(n):
        cx = -L / 2 + pitch * (i + 0.5)
        R.append(reg(rrect(sw + 0.016, sd + 0.016, 0.03, 3, cx, yc), PL_Z, 'SKY_Brass', 2))
        R.append(reg(rrect(sw, sd, 0.022, 3, cx, yc), PL_Z - depth, 'SKY_Ink', 3, side='SKY_Brass'))
    surf(a, R, base_z=PL_Z - T, side_mat='SKY_Pearl', bounds=(-L / 2, L / 2, y0, y1), name="tray")
    # rounded nosing along the front (south) edge
    mb = MB()
    nose = [(-0.002, PL_Z - T), (0.02, PL_Z - T), (0.03, PL_Z - T + 0.012), (0.03, PL_Z - 0.016), (0.022, PL_Z - 0.005),
            (0.008, PL_Z), (-0.002, PL_Z)]
    extrude(mb, [(-L / 2, y1), (L / 2, y1)], [(0, 1), (0, 1)], nose, 'SKY_Pearl')
    a.part(mb, name="nosing")
    mb = MB()
    mb.box(-L / 2 - 0.015, L / 2 + 0.015, y0 - 0.005, y1 + 0.04, PL_Z - T - 0.02, PL_Z - T + 0.008, 'SKY_Brass')
    a.part(mb, bevel=0.005, seg=1, name="trim")
    mb = MB()
    for s in (-1, 1):
        g = [(y0 - 0.03, PL_Z - T - 0.02), (y1 - 0.03, PL_Z - T - 0.02), (y0 - 0.03, PL_Z - T - 0.14)]
        mb.prism_frame(g, (0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), s * 0.42 - 0.025, s * 0.42 + 0.025, 'SKY_Brass')
    a.part(mb, bevel=0.005, seg=1, name="brackets")
    mb = MB()
    mb.box(-L / 2 + 0.02, L / 2 - 0.02, y1 + 0.04, y1 + 0.045, PL_Z - T - 0.016, PL_Z - T + 0.002, 'SKY_TealGlow')
    for i in range(n):
        cx = -L / 2 + pitch * (i + 0.5)
        cyl_y(mb, 0.008, y1 + 0.026, y1 + 0.034, 8, 'SKY_TealGlow', cx, PL_Z - 0.032)
    a.part(mb, name="glow")
    for i in range(n):
        cx = -L / 2 + pitch * (i + 0.5)
        a.empty(f"SOCKET_slot_{i + 1}", (cx, yc, PL_Z - depth))
    a.notes.append("Shares the plinth origin. SOCKET_slot_1..6 at each slot floor, west->east in Blender +X order.")


def rect_(x0, x1, y0, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
