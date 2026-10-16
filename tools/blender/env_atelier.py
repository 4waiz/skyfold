"""SKYFOLD environment kit - Fold Station kiosk and the Fold Atelier set
(terrace platform, pergola with sails, miniature-city plinth and its piece tray).

Unity north (+Z) = Blender -Y. The atelier pieces share one origin: the terrace centre at Z0
(platform top). The plinth and the tray share the plinth origin (floor centre under the table).
"""
from env_common import *
from env_buildings import fbox, fpt, fprism, arch_band, shift_uv, loft_outline, sail_quad, sail_mesh

AT_AO = dict(ground_z=0.0, dist=1.0, rays=28, strength=0.8, floor=0.42, inset=0.12)
AT_RENDER = dict(az=35.0, el=24.0)


def torus(mb, R, r, seg, sides, mat, center=(0, 0, 0), axis='Y'):
    """Torus whose ring lies in the plane perpendicular to `axis` (default: faces Blender -Y/+Y)."""
    cx, cy, cz = center
    rings = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
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
    rings.append(rings[0])
    V = [[mb.v(p) for p in ring] for ring in rings[:-1]]
    V.append(V[0])
    fs = []
    for i in range(seg):
        for j in range(sides):
            j2 = (j + 1) % sides
            fs.append(mb.f([V[i][j], V[i + 1][j], V[i + 1][j2], V[i][j2]], mat))
    mb._recalc(fs)
    return fs


@asset("foldstation_kiosk", "Atelier", "atelier", ao=AT_AO, render=dict(AT_RENDER, el=16.0))
def foldstation_kiosk(a):
    """Street Fold Station: pearl arched stele (~3 m) in a brass frame with a large teal lens ring
    (separate object 'LensRing', pivot at its centre) facing Unity north. ANCHOR_player 1.8 m in front."""
    W, D, H = 1.5, 0.62, 2.75
    # base plinth (two steps)
    mb = MB()
    mb.prism(rrect(2.1, 1.3, 0.35, 4), 0.0, 0.14, 'SKY_SandstoneDeep')
    mb.prism(rrect(1.85, 1.05, 0.3, 4), 0.14, 0.26, 'SKY_Sandstone')
    a.part(mb, bevel=0.025, seg=1, name="base")
    # stele body: arch-topped slab (extruded along Y)
    body = arch_pts(W, H, 'round', 12, base=0.26)
    mb = MB()
    mb.prism_frame(body, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), -D / 2, D / 2, 'SKY_Pearl')
    a.part(mb, bevel=0.03, seg=2, name="body")
    # brass frame following the arch on the front and back faces
    band = arch_band(W - 0.02, H - 0.01, 0.07, 'round', 12)
    band = [(p[0], p[1] + 0.26) for p in band]
    mb = MB()
    for y0, y1 in ((-D / 2 - 0.03, -D / 2 + 0.02), (D / 2 - 0.02, D / 2 + 0.03)):
        mb.prism_frame(band, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), y0, y1, 'SKY_Brass')
    a.part(mb, name="frame")
    # lens: recessed teal disc behind the ring + brass bezel
    lz = 1.72
    mb = MB()
    mb.lathe([(0, 0), (0.46, 0), (0.46, 0.04), (0.0, 0.04)], 28, 'SKY_Teal')
    mb.transform(M_tr(0, -D / 2 - 0.0, lz) @ Matrix.Rotation(math.radians(90), 4, 'X'))
    a.part(mb, name="lens_disc")
    mb = MB()
    torus(mb, 0.6, 0.045, 28, 6, 'SKY_Brass', center=(0, -D / 2 - 0.02, lz))
    a.part(mb, name="bezel")
    # LensRing (separate object, pivot at ring centre) - the game makes it glow
    mb = MB()
    torus(mb, 0.52, 0.07, 32, 8, 'SKY_TealGlow', center=(0, -D / 2 - 0.08, lz))
    a.part(mb, target="LensRing", name="ring")
    a.set_target("LensRing", pivot=(0, -D / 2 - 0.08, lz))
    # small brass hood on top + side fins with teal light lines
    mb = MB()
    mb.lathe([(0, H + 0.24), (0.2, H + 0.24), (0.16, H + 0.36), (0.05, H + 0.48), (0, H + 0.56)], 8, 'SKY_Brass')
    a.part(mb, name="finial")
    mb = MB()
    for s in (-1, 1):
        mb.box(s * (W / 2 + 0.0) - 0.04, s * (W / 2 + 0.0) + 0.04, -0.12, 0.12, 0.5, 1.9, 'SKY_TealGlow')
    a.part(mb, name="side_glow")
    # standing plate where the player stands (thin, brass ring + pearl disc)
    mb = MB()
    mb.lathe([(0, 0.0), (0.55, 0.0), (0.55, 0.025), (0, 0.025)], 24, 'SKY_Brass', cy=-1.8)
    a.part(mb, name="plate_ring")
    mb = MB()
    mb.lathe([(0, 0.0), (0.47, 0.0), (0.47, 0.03), (0, 0.03)], 24, 'SKY_Pearl', cy=-1.8)
    a.part(mb, name="plate")
    a.empty("ANCHOR_player", (0.0, -1.8, 0.0), rot_z=180.0)
    a.notes.append("LensRing pivot at the ring centre (Blender (0,-0.39,1.72)). ANCHOR_player is yawed 180 deg so its "
                   "forward faces the kiosk.")


# --------------------------------------------------------------------------- terrace

TER_R = 7.0


def balustrade_arc(a, r, a0, a1, posts, zt=0.0, h=1.0, name="bal"):
    """Circular balustrade between angles a0..a1 (deg) at radius r."""
    mb = MB(); mbc = MB(); mbb = MB(); mbr = MB()
    pa = [a0 + (a1 - a0) * i / (posts - 1) for i in range(posts)]
    for ang in pa:
        c = (r * math.cos(math.radians(ang)), r * math.sin(math.radians(ang)))
        M = M_tr(c[0], c[1], 0) @ M_rot(ang)
        fs = mb.box(-0.14, 0.14, -0.14, 0.14, zt, zt + h, 'SKY_Pearl')
        mb.transform(M, fs)
        mbc.lathe([(0, zt + h), (0.13, zt + h), (0.06, zt + h + 0.13), (0, zt + h + 0.2)], 6, 'SKY_Brass',
                  cx=c[0], cy=c[1], a0=ang + 30)
    a.part(mb, bevel=0.025, seg=1, name=name + "_posts")
    a.part(mbc, name=name + "_caps")
    # top rail (swept along the arc) and bottom rail
    n = max(6, int(abs(a1 - a0) / 6))
    path_t = [(r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), r * math.sin(math.radians(a0 + (a1 - a0) * i / n)),
               zt + h - 0.08) for i in range(n + 1)]
    mbr.sweep(path_t, [(-0.08, -0.06), (0.08, -0.06), (0.08, 0.06), (-0.08, 0.06)], 'SKY_Pearl')
    path_b = [(p[0], p[1], zt + 0.08) for p in path_t]
    mbr.sweep(path_b, [(-0.07, -0.05), (0.07, -0.05), (0.07, 0.05), (-0.07, 0.05)], 'SKY_Pearl')
    a.part(mbr, name=name + "_rails")
    # balusters
    span = math.radians(abs(a1 - a0)) * r
    nb = int(span / 0.42)
    for i in range(nb):
        ang = math.radians(a0 + (a1 - a0) * (i + 0.5) / nb)
        if min(abs(math.degrees(ang) - p) for p in pa) * math.pi / 180 * r < 0.22:
            continue
        cx, cy = r * math.cos(ang), r * math.sin(ang)
        r0, r1 = 0.045, 0.03
        ring0 = [(cx - r0, cy - r0, zt + 0.13), (cx + r0, cy - r0, zt + 0.13), (cx + r0, cy + r0, zt + 0.13), (cx - r0, cy + r0, zt + 0.13)]
        ring1 = [(cx - r1, cy - r1, zt + h - 0.14), (cx + r1, cy - r1, zt + h - 0.14), (cx + r1, cy + r1, zt + h - 0.14), (cx - r1, cy + r1, zt + h - 0.14)]
        mbb.loft([ring0, ring1], 'SKY_Pearl', cap0=False, cap1=False, recalc=False)
    a.part(mbb, name=name + "_balusters")


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


@asset("atelier_platform", "Atelier", "atelier", ao=dict(AT_AO, ground_z=None, dist=1.4), render=dict(AT_RENDER, el=30.0))
def atelier_platform(a):
    """Circular pearl terrace (14 m) on a short rocky plinth, top at Z0, balustrade with a stepped gap
    on the Unity-north edge (Blender -Y) facing the view."""
    from env_tiles import reg, tile_surface
    R_ = TER_R
    regions = [reg(circle(R_, 48), 0.0, 'SKY_Pearl', 0)]
    regions.append(reg(circle(5.45, 40), 0.0, 'SKY_Sandstone', 1))
    regions.append(reg(circle(5.2, 40), 0.0, 'SKY_Pearl', 2))
    regions.append(reg(circle(2.15, 28), 0.0, 'SKY_Sandstone', 3))
    regions.append(reg(circle(1.95, 28), 0.0, 'SKY_Ivory', 4))
    for k in range(12):
        ang = math.radians(15 + 30 * k)
        ca, sa = math.cos(ang), math.sin(ang)
        pts = [(u * ca - v * sa, u * sa + v * ca) for (u, v) in ((2.15, -0.06), (5.2, -0.06), (5.2, 0.06), (2.15, 0.06))]
        regions.append(reg(pts, 0.0, 'SKY_Sandstone', 3))
    tile_surface(a, regions, base_z=-0.55, side_mat='SKY_Pearl', bounds=(-99, 99, -99, 99), name="deck",
                 kerb_bevel=0.0, bottom='loop')

    # rim band
    mb = MB()
    mb.lathe([(R_ - 0.02, -0.6), (R_ + 0.12, -0.6), (R_ + 0.12, -0.42), (R_ - 0.02, -0.42)], 48, 'SKY_Brass',
             closed=True)

    a.part(mb, name="rim_brass")
    # rocky plinth under the deck
    mb = MB()
    rock_ring(mb, [(R_ - 0.3, -0.6), (R_ + 0.3, -1.15), (R_ + 0.6, -1.9), (R_ + 0.9, -2.8), (R_ + 1.1, -3.4)], 18,
              'SKY_SandstoneDeep', seed=4)
    a.part(mb, name="rock")
    a.set_target(a.name, smooth=30.0)
    # balustrade (gap on Blender -Y = Unity north: angles 270 +/- 14)
    gap = 14.0
    balustrade_arc(a, R_ - 0.25, 270 + gap, 270 + 360 - gap, 15, zt=0.0)
    # gateposts and steps down toward the view
    mb = MB()
    for s in (-1, 1):
        ang = math.radians(270 + s * gap)
        c = ((R_ - 0.25) * math.cos(ang), (R_ - 0.25) * math.sin(ang))
        mb.box(c[0] - 0.24, c[0] + 0.24, c[1] - 0.24, c[1] + 0.24, 0.0, 1.35, 'SKY_Pearl')
    a.part(mb, bevel=0.03, seg=1, name="gateposts")
    mb = MB()
    for s in (-1, 1):
        ang = math.radians(270 + s * gap)
        c = ((R_ - 0.25) * math.cos(ang), (R_ - 0.25) * math.sin(ang))
        mb.sphere(0.2, 10, 5, 'SKY_Brass', c=(c[0], c[1], 1.55))
        mb.cyl(0.2, 1.35, 1.42, 10, 'SKY_Brass', cx=c[0], cy=c[1])
    a.part(mb, name="gatepost_orbs")
    hw = (R_ - 0.25) * math.sin(math.radians(gap)) - 0.25
    mb = MB()
    for i in range(4):
        y0 = -R_ - 0.05 - i * 0.42
        mb.box(-hw, hw, y0 - 0.45, y0 + 0.4 if i == 0 else y0, -0.6, -0.17 * (i + 1), 'SKY_Pearl')
    a.part(mb, bevel=0.02, seg=1, name="steps")
    mb = MB()
    mb.box(-hw - 0.3, hw + 0.3, -R_ - 2.6, -R_ - 1.6, -1.6, -0.68, 'SKY_SandstoneDeep')
    a.part(mb, bevel=0.06, seg=1, name="landing")
    a.notes.append("Top of deck at Z0, radius 7 m; balustrade gap + 4 steps on the Unity-north edge.")


@asset("atelier_pergola", "Atelier", "atelier", ao=dict(AT_AO, dist=1.4), render=dict(AT_RENDER, el=34.0))
def atelier_pergola(a):
    """Crescent pergola over the southern half of the terrace (Blender +Y), pearl columns, timber
    rafters and three tensioned shade sails. Leaves the central plinth area and the north view open."""
    r_in, r_out, hgt = 4.3, 6.5, 3.1
    angs = [32.0, 69.0, 111.0, 148.0]
    mb = MB(); mbc = MB()
    for ang in angs:
        for r in (r_in, r_out):
            x, y = r * math.cos(math.radians(ang)), r * math.sin(math.radians(ang))
            mb.lathe([(0, 0.0), (0.24, 0.0), (0.24, 0.12), (0.15, 0.2), (0.12, hgt - 0.15), (0.17, hgt - 0.05),
                      (0.17, hgt), (0, hgt)], 10, 'SKY_Pearl', cx=x, cy=y)
            mbc.lathe([(0, hgt - 0.32), (0.135, hgt - 0.32), (0.135, hgt - 0.26), (0, hgt - 0.26)], 10, 'SKY_Brass', cx=x, cy=y)
    a.part(mb, name="columns")
    a.part(mbc, name="collars")
    # radial rafters (wood) and curved purlins
    mb = MB()
    for ang in angs:
        ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        p0 = Vector((ca * (r_in - 0.5), sa * (r_in - 0.5), hgt + 0.12))
        p1 = Vector((ca * (r_out + 0.5), sa * (r_out + 0.5), hgt + 0.12))
        mb.sweep([p0, p1], [(-0.09, -0.12), (0.09, -0.12), (0.09, 0.12), (-0.09, 0.12)], 'SKY_Wood')
    for r in (r_in, (r_in + r_out) / 2, r_out):
        n = 14
        pts = [(r * math.cos(math.radians(angs[0] - 6 + (angs[-1] - angs[0] + 12) * i / n)),
                r * math.sin(math.radians(angs[0] - 6 + (angs[-1] - angs[0] + 12) * i / n)), hgt + 0.3) for i in range(n + 1)]
        mb.sweep(pts, [(-0.07, -0.07), (0.07, -0.07), (0.07, 0.07), (-0.07, 0.07)], 'SKY_Wood')
    a.part(mb, name="timber")
    # three sails, one per bay, alternating tilt
    for k in range(3):
        a0, a1 = math.radians(angs[k] + 3), math.radians(angs[k + 1] - 3)
        hi, lo = hgt + 0.05, hgt - 0.35
        c = [(r_in * math.cos(a0), r_in * math.sin(a0), lo if k % 2 else hi),
             (r_in * math.cos(a1), r_in * math.sin(a1), hi if k % 2 else lo),
             (r_out * math.cos(a1), r_out * math.sin(a1), lo if k % 2 else hi),
             (r_out * math.cos(a0), r_out * math.sin(a0), hi if k % 2 else lo)]
        sail_quad(a, c, sag=0.22, n=4)
    # planters at the column feet (outer ring)
    mb = MB(); mbl = MB()
    for ang in (50.5, 90.0, 129.5):
        x, y = (r_out + 0.05) * math.cos(math.radians(ang)), (r_out + 0.05) * math.sin(math.radians(ang))
        fs = mb.box(-0.7, 0.7, -0.28, 0.28, 0.0, 0.5, 'SKY_Terracotta')
        mb.transform(M_tr(x, y, 0) @ M_rot(ang + 90), fs)
        for dx in (-0.4, 0.0, 0.4):
            px = x + dx * math.cos(math.radians(ang + 90))
            py = y + dx * math.sin(math.radians(ang + 90))
            mbl.sphere(0.3, 7, 4, 'SKY_PalmLeaf', c=(px, py, 0.62), sz=0.85)
    a.part(mb, bevel=0.03, seg=1, name="planters")
    a.part(mbl, name="greens")
    a.notes.append("Shares the terrace origin with atelier_platform (centre, Z0).")


# --------------------------------------------------------------------------- plinth + tray

PL_W, PL_D, PL_Z = 1.6, 1.2, 0.9


@asset("plinth", "Atelier", "atelier", ao=dict(AT_AO, dist=0.5, inset=0.05), render=dict(AT_RENDER, el=26.0))
def plinth_table(a):
    """Miniature-city table: top 1.6 (E-W) x 1.2 (N-S) at Z0.9, brass edge band, separate teal rim
    'PlinthRim', elegant tapered pedestal. ANCHOR_minicity at the top centre, ANCHOR_player 0.55 m south."""
    top_t = 0.07
    # top slab (ivory) with brass edge band
    mb = MB()
    mb.prism(rrect(PL_W, PL_D, 0.06, 3), PL_Z - top_t, PL_Z, 'SKY_Ivory')
    a.part(mb, bevel=0.012, seg=1, name="top")
    mb = MB()
    mb.prism(rrect(PL_W + 0.03, PL_D + 0.03, 0.075, 3), PL_Z - top_t - 0.06, PL_Z - top_t + 0.035, 'SKY_Brass')
    a.part(mb, bevel=0.008, seg=1, name="edge_band")
    # PlinthRim: thin glow rim just under the brass band
    out = rrect(PL_W + 0.05, PL_D + 0.05, 0.08, 3)
    inn = rrect(PL_W - 0.06, PL_D - 0.06, 0.04, 3)
    mb = MB()
    mb.prism(out, PL_Z - top_t - 0.085, PL_Z - top_t - 0.06, 'SKY_TealGlow')
    a.part(mb, target="PlinthRim", name="rim")
    # apron under the top
    mb = MB()
    mb.prism(rrect(PL_W - 0.12, PL_D - 0.12, 0.05, 3), PL_Z - 0.26, PL_Z - top_t - 0.085, 'SKY_Pearl')
    a.part(mb, bevel=0.012, seg=1, name="apron")
    # pedestal: tapered rounded-rect loft (pearl) with brass waist ring and base
    base = ccw(rrect(1.0, 0.72, 0.18, 4))
    prof = [(0.12, 0.0, 'SKY_SandstoneDeep'), (0.12, 0.08, 'SKY_SandstoneDeep'), (0.06, 0.12, 'SKY_Pearl'),
            (0.0, 0.18, 'SKY_Pearl'), (-0.12, 0.42, 'SKY_Pearl'), (-0.16, 0.5, 'SKY_Brass'), (-0.12, 0.53, 'SKY_Brass'),
            (-0.12, 0.55, 'SKY_Pearl'), (-0.06, PL_Z - 0.3, 'SKY_Pearl'), (0.05, PL_Z - 0.26, 'SKY_Pearl')]
    loft_outline(a, base, prof, cap_top='SKY_Pearl', name="pedestal")
    # teal light lines on the pedestal front/back (Unity N/S)
    mb = MB()
    for s in (-1, 1):
        mb.box(-0.2, 0.2, s * 0.375 - 0.01, s * 0.375 + 0.01, 0.62, 0.66, 'SKY_TealGlow')
    a.part(mb, name="glow")
    a.empty("ANCHOR_minicity", (0.0, 0.0, PL_Z))
    a.empty("ANCHOR_player", (0.0, PL_D / 2 + 0.55, 0.0))
    a.notes.append("Top surface Z0.9, 1.6 x 1.2 m. ANCHOR_player 0.55 m south of the south edge, facing north.")


@asset("plinth_tray", "Atelier", "atelier", ao=dict(AT_AO, dist=0.15, inset=0.02, ground_z=None),
       render=dict(AT_RENDER, el=40.0))
def plinth_tray(a):
    """Piece tray 1.1 x 0.18 m mounting on the plinth's south edge, top flush at Z0.9, six shallow slots.
    Modelled in plinth space: place it with the same transform as 'plinth'."""
    L, Dd, T = 1.1, 0.18, 0.06
    y0 = PL_D / 2 + 0.025
    y1 = y0 + Dd
    n = 6
    pitch = L / n
    sw, sd, depth = 0.15, 0.13, 0.025
    cutters = []
    for i in range(n):
        cx = -L / 2 + pitch * (i + 0.5)
        mb = MB()
        mb.box(cx - sw / 2, cx + sw / 2, (y0 + y1) / 2 - sd / 2, (y0 + y1) / 2 + sd / 2, PL_Z - depth, PL_Z + 0.2,
               'SKY_Ink')
        cutters.append(a.cutter(mb, "slot"))
    mb = MB()
    mb.box(-L / 2, L / 2, y0, y1, PL_Z - T, PL_Z, 'SKY_Pearl')
    a.part(mb, bevel=0.008, seg=1, cutters=cutters, name="tray")
    mb = MB()
    mb.box(-L / 2 - 0.015, L / 2 + 0.015, y0 - 0.005, y1 + 0.015, PL_Z - T - 0.02, PL_Z - T + 0.012, 'SKY_Brass')
    a.part(mb, bevel=0.005, seg=1, name="trim")
    mb = MB()
    for s in (-1, 1):
        mb.box(s * 0.42 - 0.03, s * 0.42 + 0.03, y0 - 0.03, y1 - 0.04, PL_Z - T - 0.12, PL_Z - T - 0.02, 'SKY_Brass')
    a.part(mb, bevel=0.005, seg=1, name="brackets")
    mb = MB()
    mb.box(-L / 2 + 0.01, L / 2 - 0.01, y1 - 0.004, y1 + 0.002, PL_Z - T + 0.012, PL_Z - 0.012, 'SKY_TealGlow')
    a.part(mb, name="glow")
    for i in range(n):
        cx = -L / 2 + pitch * (i + 0.5)
        a.empty(f"SOCKET_slot_{i + 1}", (cx, (y0 + y1) / 2, PL_Z - depth))
    a.notes.append("Shares the plinth origin. SOCKET_slot_1..6 at each slot floor, west->east in Blender +X order.")
