"""SKYFOLD environment kit - P1: sky dressing (clouds, storm, skyline ring), sea rocks, headland,
small dhow, buoy, small fountain, crate stack.
"""
from env_common import *

SKY_AO = dict(ground_z=None, dist=6.0, rays=20, strength=0.5, floor=0.6, inset=0.5)
SKY_RENDER = dict(az=30.0, el=12.0)


def blob_mesh(mb, centers, mat, seg=10, rings=6, flat_z=None):
    """Union-looking cluster of squashed spheres; optional flattened underside."""
    for (cx, cy, cz, r, sz) in centers:
        prof = []
        for i in range(rings + 1):
            ang = -math.pi / 2 + math.pi * i / rings
            rr = r * math.cos(ang)
            zz = cz + r * math.sin(ang) * sz
            if flat_z is not None and zz < flat_z:
                zz = flat_z + (zz - flat_z) * 0.15
            prof.append((max(rr, 0.0), zz))
        prof[0] = (0.0, prof[0][1]); prof[-1] = (0.0, prof[-1][1])
        mb.lathe(prof, seg, mat, cx=cx, cy=cy)


def cloud(a, puffs, mat='SKY_Pearl', seg=10, rings=6, flat=0.0):
    mb = MB()
    blob_mesh(mb, puffs, mat, seg, rings, flat_z=flat)
    a.part(mb, name="puffs")
    a.set_target(a.name, weighted=False, smooth=80.0)


@asset("cloud_puff_a", "Sky", "p1", ao=SKY_AO, render=SKY_RENDER)
def cloud_puff_a(a):
    """Soft stylised cumulus (~26 m wide), flattened base at Z0."""
    cloud(a, [(0, 0, 4.5, 7.0, 0.8), (7.5, 1.0, 3.2, 5.2, 0.8), (-7.0, -0.5, 3.0, 5.0, 0.8),
              (2.5, -3.0, 2.6, 4.6, 0.75), (-2.5, 3.2, 3.0, 4.6, 0.75), (11.5, 0.0, 2.0, 3.2, 0.8)], flat=0.0)


@asset("cloud_puff_b", "Sky", "p1", ao=SKY_AO, render=SKY_RENDER)
def cloud_puff_b(a):
    """Long low cloud bank (~34 m)."""
    cloud(a, [(-10, 0, 2.6, 4.6, 0.75), (-3.5, 0.8, 3.6, 6.0, 0.75), (4.0, -0.5, 3.2, 5.4, 0.75),
              (10.5, 0.5, 2.4, 4.2, 0.75), (14.5, -0.6, 1.6, 2.8, 0.8), (0.5, -3.0, 2.0, 3.6, 0.75)], flat=0.0)


@asset("cloud_puff_c", "Sky", "p1", ao=SKY_AO, render=SKY_RENDER)
def cloud_puff_c(a):
    """Small tufted puff (~14 m)."""
    cloud(a, [(0, 0, 3.0, 4.4, 0.85), (4.2, 0.6, 2.0, 3.0, 0.85), (-3.8, -0.4, 2.1, 3.1, 0.85),
              (0.6, 2.4, 2.2, 2.6, 0.85)], flat=0.0)


@asset("storm_cloud", "Sky", "p1", ao=dict(SKY_AO, strength=0.6), render=SKY_RENDER)
def storm_cloud(a):
    """Dark towering storm cell (~48 m wide, ~30 m tall) with a flat heavy base, SKY_Ink."""
    puffs = [(0, 0, 9, 13, 0.85), (13, 2, 7, 10, 0.85), (-13, -1, 7, 10, 0.85), (5, -8, 6, 9, 0.8),
             (-6, 8, 6, 9, 0.8), (2, 1, 20, 9, 0.9), (-3, -2, 26, 7, 0.8), (6, 3, 25, 6, 0.8), (21, 0, 4.5, 6.5, 0.8),
             (-21, 1, 4.5, 6.5, 0.8)]
    cloud(a, puffs, mat='SKY_Ink', seg=11, rings=6, flat=0.0)
    # anvil top
    mb = MB()
    blob_mesh(mb, [(0, 0, 31, 12, 0.28), (10, 2, 30, 8, 0.3), (-9, -1, 30, 8, 0.3)], 'SKY_Ink', 12, 5)
    a.part(mb, name="anvil")


@asset("skyline_ring_piece", "Sky", "p1", ao=dict(SKY_AO, dist=8.0), render=dict(az=0.0, el=8.0))
def skyline_ring_piece(a):
    """Very low-detail distant skyline: a 30 deg arc of block silhouettes at radius 320 m, facing the ring
    centre (pivot). Twelve copies rotated in 30 deg steps close the ring."""
    rnd = random.Random(42)
    R = 320.0
    mb = MB(); mbd = MB()
    ang = -15.0
    k = 0
    while ang < 15.0:
        w = rnd.uniform(9, 22)
        dang = math.degrees(w / R)
        mid = math.radians(ang + dang / 2 - 90)     # centred on Blender -Y (Unity north)
        h = rnd.choice([10, 14, 18, 24, 30, 42, 58]) * rnd.uniform(0.8, 1.15)
        d = rnd.uniform(10, 18)
        r0 = R + rnd.uniform(-8, 12)
        cx, cy = r0 * math.cos(mid), r0 * math.sin(mid)
        mat = 'SKY_Pearl' if k % 3 else 'SKY_Sandstone'
        fs = mb.box(-w / 2, w / 2, -d / 2, d / 2, 0.0, h, mat)
        mb.transform(M_tr(cx, cy, 0) @ M_rot(math.degrees(mid) + 90), fs)
        if h > 40 and rnd.random() < 0.7:
            fs = mb.box(-w * 0.3, w * 0.3, -d * 0.3, d * 0.3, h, h + h * 0.18, mat)
            mb.transform(M_tr(cx, cy, 0) @ M_rot(math.degrees(mid) + 90), fs)
        if 18 <= h <= 30 and rnd.random() < 0.35:
            mbd.sphere(min(w, d) * 0.35, 8, 4, 'SKY_Pearl', c=(cx, cy, h), sz=0.9)
        ang += dang + rnd.uniform(0.2, 1.2)
        k += 1
    a.part(mb, name="blocks")
    a.part(mbd, name="domes")
    a.notes.append("Pivot at the ring centre; geometry spans a 30 deg arc at r~320 m centred on Unity north.")


def rock(mb, n_seg, rings, mat, seed, jitter=0.25):
    rnd = random.Random(seed)
    pts = []
    for ri, (r, z) in enumerate(rings):
        ring = []
        for k in range(n_seg):
            ang = 2 * math.pi * (k + rnd.uniform(-0.25, 0.25)) / n_seg
            rr = r * (1 + rnd.uniform(-jitter, jitter))
            ring.append((rr * math.cos(ang), rr * math.sin(ang), z + rnd.uniform(-0.12, 0.12) * r))
        pts.append(ring)
    return mb.loft(pts, mat)


ROCK_AO = dict(ground_z=0.0, dist=1.5, rays=20, strength=0.7, floor=0.45, inset=0.2)


@asset("rock_sea_a", "Nature", "p1", ao=ROCK_AO, render=dict(az=30.0, el=20.0, water=True, seabed=0.0))
def rock_sea_a(a):
    """Sea rock ~5.5 m tall from its base (place the base on the seabed at Z-4)."""
    mb = MB()
    rock(mb, 9, [(3.2, 0.0), (3.0, 1.6), (2.4, 3.2), (1.5, 4.6), (0.5, 5.5)], 'SKY_SandstoneDeep', 3)
    a.part(mb, name="rock")
    mb = MB()
    rock(mb, 7, [(1.6, 0.0), (1.4, 1.2), (0.9, 2.6), (0.3, 3.3)], 'SKY_Sandstone', 5)
    mb.transform(M_tr(2.9, 1.4, 0))
    a.part(mb, name="rock2")
    a.set_target(a.name, weighted=False, smooth=25.0)


@asset("rock_sea_b", "Nature", "p1", ao=ROCK_AO, render=dict(az=30.0, el=20.0, water=True, seabed=0.0))
def rock_sea_b(a):
    """Low flat sea rock cluster ~4.6 m tall from its base."""
    mb = MB()
    rock(mb, 8, [(3.6, 0.0), (3.4, 1.8), (2.8, 3.4), (1.6, 4.3), (0.6, 4.6)], 'SKY_SandstoneDeep', 11)
    a.part(mb, name="rock")
    mb = MB()
    rock(mb, 7, [(1.8, 0.0), (1.6, 1.6), (1.0, 3.6), (0.3, 4.1)], 'SKY_SandstoneDeep', 13)
    mb.transform(M_tr(-3.2, -1.0, 0))
    a.part(mb, name="rock2")
    mb = MB()
    rock(mb, 6, [(1.0, 0.0), (0.9, 1.4), (0.5, 3.4), (0.2, 3.8)], 'SKY_Sandstone', 17)
    mb.transform(M_tr(2.6, -2.2, 0))
    a.part(mb, name="rock3")
    a.set_target(a.name, weighted=False, smooth=25.0)


@asset("cliff_headland", "Nature", "p1", ao=dict(ROCK_AO, dist=4.0, ground_z=None), render=dict(az=35.0, el=18.0))
def cliff_headland(a):
    """Rocky headland (~30 x 36 m, 26 m drop) for the Fold Atelier. Pivot = atelier origin: the plateau
    sits at Z-2.8 so atelier_platform (deck Z0) placed at the same origin beds its rock plinth into it."""
    rnd = random.Random(8)
    seg = 16
    rings = [(10.5, -2.8, 0.03), (12.5, -4.0, 0.08), (14.0, -8.0, 0.14), (15.5, -14.0, 0.16),
             (16.5, -20.0, 0.16), (17.5, -26.0, 0.12)]
    pts = []
    for (r, z, j) in rings:
        ring = []
        for k in range(seg):
            ang = 2 * math.pi * k / seg
            # elongate toward Unity north (Blender -Y) like a promontory
            stretch = 1.0 + 0.25 * max(0.0, -math.sin(ang))
            rr = r * stretch * (1 + rnd.uniform(-j, j))
            ring.append((rr * math.cos(ang), rr * math.sin(ang), z + rnd.uniform(-1, 1) * (0.0 if z > -3 else 0.9)))
        pts.append(ring)
    mb = MB()
    mb.loft(pts, 'SKY_SandstoneDeep', mats=['SKY_Sandstone', 'SKY_SandstoneDeep', 'SKY_SandstoneDeep',
                                             'SKY_SandstoneDeep', 'SKY_SandstoneDeep', 'SKY_SandstoneDeep'])
    a.part(mb, name="mass")
    # boulders and ledges on the flanks
    mb = MB()
    for i in range(7):
        ang = rnd.uniform(0, 2 * math.pi)
        z = rnd.uniform(-22, -6)
        rr = 15.5 + (z + 14) * -0.12 + 1.2
        fs = rock(mb, 6, [(2.2, 0.0), (2.0, 1.4), (1.2, 2.6), (0.4, 3.0)], 'SKY_SandstoneDeep', 30 + i)
        mb.transform(M_tr(rr * math.cos(ang), rr * math.sin(ang), z), fs)
    a.part(mb, name="boulders")
    # tufts of greenery on the plateau edge
    mb = MB()
    for i in range(6):
        ang = math.radians(40 + i * 18)
        mb.sphere(0.9, 7, 4, 'SKY_PalmLeaf', c=(11.2 * math.cos(ang), 11.2 * math.sin(ang), -2.9), sz=0.6)
    a.part(mb, name="greens")
    a.set_target(a.name, weighted=False, smooth=28.0)
    a.notes.append("Plateau at Z-2.8 around the pivot; cliff foot at about Z-26.")


@asset("dhow_small", "Props", "p1", ao=dict(ground_z=None, dist=0.8, rays=24, strength=0.75, floor=0.45, inset=0.08),
       render=dict(az=60.0, el=16.0, water=True, seabed=-4.0))
def dhow_small(a):
    """Small fictional wooden sailing boat (~8 m) with a raked bow, a single mast and a triangular
    lateen-style sail. Pivot on the waterline at mid-length (place at Z-1.2); bow toward Unity north."""
    L = 8.0
    n = 10
    rings = []
    for i in range(n + 1):
        t = i / n                       # 0 = stern (Blender +Y), 1 = bow (Blender -Y)
        y = L / 2 - t * L
        beam = 1.15 * math.sin(math.pi * (0.12 + 0.82 * t)) ** 0.8 + 0.05
        sheer = 0.95 + 0.55 * (t ** 3) + 0.25 * ((1 - t) ** 4)
        keel = -0.75 * math.sin(math.pi * min(1.0, 0.1 + t)) ** 0.6
        ring = [(-beam * 0.25, y, keel), (-beam, y, sheer * 0.25), (-beam * 1.02, y, sheer),
                (beam * 1.02, y, sheer), (beam, y, sheer * 0.25), (beam * 0.25, y, keel)]
        rings.append(ring)
    mb = MB()
    mb.loft(rings, 'SKY_Wood', closed=True)
    a.part(mb, name="hull")
    # deck (slightly below the gunwale) and gunwale trim
    mb = MB()
    deck = []
    for i in range(n + 1):
        t = i / n
        y = L / 2 - t * L
        beam = 1.15 * math.sin(math.pi * (0.12 + 0.82 * t)) ** 0.8 + 0.05
        sheer = 0.95 + 0.55 * (t ** 3) + 0.25 * ((1 - t) ** 4)
        deck.append((y, beam * 0.96, sheer - 0.18))
    left = [(-b, y, z) for (y, b, z) in deck]
    right = [(b, y, z) for (y, b, z) in reversed(deck)]
    poly = left + right
    vs = [mb.v(p) for p in poly]
    vs2 = [mb.v((p[0], p[1], p[2] - 0.06)) for p in poly]
    fs = [mb.f(vs, 'SKY_Kerb'), mb.f(list(reversed(vs2)), 'SKY_Kerb')]
    for i in range(len(poly)):
        j = (i + 1) % len(poly)
        fs.append(mb.f([vs[j], vs[i], vs2[i], vs2[j]], 'SKY_Kerb'))
    mb._recalc(fs)
    a.part(mb, name="deck")
    # stern cabin / shade and mast
    mb = MB()
    mb.box(-0.7, 0.7, 2.0, 3.4, 0.7, 1.55, 'SKY_Wood')
    mb.box(-0.8, 0.8, 1.9, 3.5, 1.55, 1.65, 'SKY_Pearl')
    a.part(mb, bevel=0.02, seg=1, name="cabin")
    mb = MB()
    mb.cyl(0.08, 0.7, 6.2, 6, 'SKY_Wood', cx=0.0, cy=-0.6, r_top=0.05)
    a.part(mb, name="mast")
    # lateen yard + sail (Fabric), double thickness via sail_mesh
    from env_buildings import sail_mesh
    mb = MB()
    mb.sweep([Vector((0.0, 2.6, 1.5)), Vector((0.0, -0.6, 5.6)), Vector((0.0, -2.9, 7.2))], circle(0.05, 5), 'SKY_Wood')
    a.part(mb, name="yard")
    mb = MB()
    sail_mesh(mb, [(0.06, 2.45, 1.65), (0.06, -2.75, 7.0), (0.06, -2.6, 1.6)], 'SKY_Fabric', sag=0.3, n=5, t=0.035)

    a.part(mb, name="sail")
    # brass stem cap and coral pennant
    mb = MB()
    mb.sphere(0.07, 6, 3, 'SKY_Brass', c=(0, -0.6, 6.25))
    a.part(mb, name="cap")
    a.set_target(a.name, smooth=50.0)
    a.notes.append("Pivot on the waterline (Z0) at mid-length; hull draft ~0.75 m.")


@asset("buoy", "Props", "p1", ao=dict(ground_z=None, dist=0.4, rays=20, strength=0.7, floor=0.5, inset=0.05),
       render=dict(az=35.0, el=18.0, water=True, seabed=-4.0))
def buoy(a):
    """Channel buoy, coral/pearl bands with a small brass lantern. Pivot on the waterline (Z0)."""
    mb = MB()
    prof = [(0, -0.6), (0.45, -0.55), (0.6, -0.3), (0.62, 0.15), (0.5, 0.3), (0.2, 0.36), (0.2, 1.2), (0.25, 1.25),
            (0.0, 1.3)]
    mats = ['SKY_Ink', 'SKY_Coral', 'SKY_Coral', 'SKY_Pearl', 'SKY_Pearl', 'SKY_Coral', 'SKY_Pearl', 'SKY_Pearl']
    mb.lathe(prof, 12, 'SKY_Coral', mats=mats)
    a.part(mb, name="body")
    mb = MB()
    mb.cyl(0.11, 1.3, 1.5, 8, 'SKY_Light')
    mb.lathe([(0, 1.5), (0.16, 1.5), (0.06, 1.62), (0, 1.66)], 8, 'SKY_Brass')
    a.part(mb, name="lamp")
    a.empty("LIGHT_buoy", (0, 0, 1.4))


@asset("fountain_small", "Props", "p1", ao=dict(ground_z=0.0, dist=0.5, rays=24, strength=0.75, floor=0.45, inset=0.05),
       render=dict(az=35.0, el=26.0))
def fountain_small(a):
    """Small street fountain (1.9 m): octagonal pearl basin, teal water, tiered brass-trimmed jet."""
    mb = MB()
    mb.lathe([(0, 0), (0.95, 0), (0.95, 0.5), (0.82, 0.5), (0.82, 0.32), (0, 0.32)], 8, 'SKY_Pearl', a0=22.5)
    a.part(mb, bevel=0.02, seg=1, name="basin")
    mb = MB()
    mb.lathe([(0, 0.32), (0.83, 0.32), (0.83, 0.4), (0, 0.4)], 8, 'SKY_TealLight', a0=22.5)
    a.part(mb, name="water")
    mb = MB()
    mb.lathe([(0, 0.4), (0.14, 0.4), (0.1, 0.85), (0.38, 0.95), (0.36, 1.02), (0.08, 0.98), (0.07, 1.3), (0.0, 1.38)],
             10, 'SKY_Pearl')
    a.part(mb, name="jet")
    mb = MB()
    mb.lathe([(0, 0.95), (0.33, 0.95), (0, 1.0)], 10, 'SKY_TealLight')
    mb.lathe([(0.355, 0.97), (0.39, 0.97), (0.39, 1.0), (0.355, 1.0)], 10, 'SKY_Brass', closed=True)
    a.part(mb, name="bowl")


@asset("crate_stack", "Props", "p1", ao=dict(ground_z=0.0, dist=0.5, rays=24, strength=0.75, floor=0.45, inset=0.05),
       render=dict(az=35.0, el=22.0))
def crate_stack(a):
    """Three timber crates (0.8 m) with brass corner straps."""
    mb = MB(); mbs = MB()
    for (x, y, z, rot) in ((-0.42, 0.0, 0.0, 0.0), (0.42, 0.05, 0.0, 6.0), (0.0, 0.02, 0.8, -8.0)):
        fs = mb.box(-0.4, 0.4, -0.4, 0.4, 0.0, 0.8, 'SKY_Wood')
        mb.transform(M_tr(x, y, z) @ M_rot(rot), fs)
        for zz in (0.1, 0.62):
            fs = mbs.box(-0.41, 0.41, -0.41, 0.41, zz, zz + 0.07, 'SKY_Brass')
            mbs.transform(M_tr(x, y, z) @ M_rot(rot), fs)
    a.part(mb, bevel=0.02, seg=1, name="crates")
    a.part(mbs, name="straps")
