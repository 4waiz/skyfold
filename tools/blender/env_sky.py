"""SKYFOLD environment kit - P1 (detail pass): sky dressing (clouds, storm cell, skyline ring), sea rocks,
headland, small dhow, buoy, small fountain, crate stack.

Clouds are polygonised unions of stiff metaballs (round distinct puffs joined by soft fillets) with a
flattened base, decimated to budget. Rocks and the headland are stacks of jittered strata slabs: coherent vertical facets,
lit ledges and cracks. Everything else is built from the shared MB primitives.
"""
from env_common import *

SKY_AO = dict(ground_z=None, dist=6.0, rays=20, strength=0.5, floor=0.6, inset=0.5)
SKY_RENDER = dict(az=30.0, el=12.0)


# --------------------------------------------------------------------------- generic helpers

def cham_rect(w, h, c, cx=0.0, cy=0.0):
    hw, hh = w / 2.0, h / 2.0
    c = max(0.0, min(c, hw * 0.45, hh * 0.45))
    if c <= 1e-6:
        return [(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)]
    return [(cx - hw + c, cy - hh), (cx + hw - c, cy - hh), (cx + hw, cy - hh + c), (cx + hw, cy + hh - c),
            (cx + hw - c, cy + hh), (cx - hw + c, cy + hh), (cx - hw, cy + hh - c), (cx - hw, cy - hh + c)]


def bar(mb, p0, p1, w, h, mat, c=0.0, up=Vector((0, 0, 1))):
    """Straight (optionally chamfered) rectangular bar from p0 to p1 (w across, h along `up`)."""
    return mb.sweep([Vector(p0), Vector(p1)], cham_rect(w, h, c), mat, up=up)


def line(mb, p0, p1, r, mat, sides=4):
    """Thin rope / rigging line."""
    return mb.sweep([Vector(p0), Vector(p1)], circle(r, sides, a0=45), mat)


def ring(mb, r_in, r_out, z0, z1, seg, mat, cx=0.0, cy=0.0, ch=0.0, a0=0.0):
    prof = [(r_in, z0), (r_out, z0 + ch), (r_out, z1 - ch), (r_in, z1)]
    return mb.lathe(prof, seg, mat, cx=cx, cy=cy, a0=a0, closed=True)


def torus(mb, R, r, seg, sides, mat, M=None):
    prof = [(R + r * math.cos(2 * math.pi * k / sides), r * math.sin(2 * math.pi * k / sides)) for k in range(sides)]
    fs = mb.lathe(prof, seg, mat, closed=True)
    if M is not None:
        mb.transform(M, fs)
    return fs


def bezier3(p0, p1, p2, p3, n):
    P = [Vector(p) for p in (p0, p1, p2, p3)]
    out = []
    for i in range(n + 1):
        t = i / n
        s = 1 - t
        out.append(P[0] * s ** 3 + P[1] * 3 * s * s * t + P[2] * 3 * s * t * t + P[3] * t ** 3)
    return out


def ico(mb, c, r, mat, level=2, sz=1.0, sx=1.0, sy=1.0, noise=0.0, seed=0, flat_z=None):
    tmp = bmesh.new()
    bmesh.ops.create_icosphere(tmp, subdivisions=level, radius=1.0)
    rnd = random.Random(seed)
    L = [(Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.3, 1))).normalized(), rnd.uniform(0.5, 1))
         for _ in range(5)]
    vm = {}
    for v in tmp.verts:
        d = v.co.normalized()
        k = 1.0
        for (ld, amp) in L:
            k += noise * amp * (max(0.0, d.dot(ld)) ** 4 - 0.12)
        p = Vector((c[0] + d.x * r * k * sx, c[1] + d.y * r * k * sy, c[2] + d.z * r * k * sz))
        if flat_z is not None and p.z < flat_z:
            p.z = flat_z + (p.z - flat_z) * 0.2
        vm[v] = mb.v(p)
    fs = [mb.f([vm[v] for v in f.verts], mat) for f in tmp.faces]
    tmp.free()
    return fs


# --------------------------------------------------------------------------- clouds (metaballs)

def meta_mesh(elements, res, threshold=0.6, stiffness=8.0):
    """Polygonise metaball elements -> temporary Mesh. elements: (x, y, z, R[, (sx, sy, sz)[, negative]])."""
    md = bpy.data.metaballs.new("sky_meta")
    md.resolution = res
    md.render_resolution = res
    md.threshold = threshold
    for e in elements:
        x, y, z, R = e[:4]
        size = e[4] if len(e) > 4 and e[4] else None
        el = md.elements.new(type='ELLIPSOID' if size else 'BALL')
        el.co = (x, y, z)
        el.radius = R
        el.stiffness = stiffness
        if size:
            el.size_x, el.size_y, el.size_z = size
        if len(e) > 5 and e[5]:
            el.use_negative = True
    ob = bpy.data.objects.new("sky_meta", md)
    link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.metaballs.remove(md)
    return me


def decimate(me, target):
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    if tris <= target:
        return me
    ob = bpy.data.objects.new("sky_dec", me)
    link(ob)
    md = ob.modifiers.new("dec", 'DECIMATE')
    md.ratio = target / tris
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.meshes.remove(me)
    return me2


def mesh_into(mb, me, mat, flat_z=None, squash=0.1, mat_fn=None):
    """Copy a temporary mesh into an MB (optionally squashing everything below flat_z into a soft flat base)."""
    bm = bmesh.new()
    bm.from_mesh(me)
    if flat_z is not None:
        for v in bm.verts:
            if v.co.z < flat_z:
                v.co.z = flat_z + (v.co.z - flat_z) * squash
    # weld slivers left by decimation / the squashed base (no zero-area faces)
    for _ in range(3):
        bmesh.ops.dissolve_degenerate(bm, dist=0.01, edges=bm.edges[:])
        bad = [f for f in bm.faces if f.calc_area() < 1e-5]
        if not bad:
            break
        bmesh.ops.collapse(bm, edges=list({e for f in bad for e in f.edges if e.calc_length() < 0.05}) or
                           [min(bad[0].edges, key=lambda e: e.calc_length())])
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.002)
    vm = {v: mb.v(v.co.copy()) for v in bm.verts}
    fs = []
    for f in bm.faces:
        m = mat_fn(f) if mat_fn else mat
        fs.append(mb.f([vm[v] for v in f.verts], m))
    bm.free()
    bpy.data.meshes.remove(me)
    mb._recalc(fs)
    return fs


def cloud(a, puffs, mat='SKY_Pearl', res=0.9, target=2200, base=0.0, threshold=0.6, stiffness=8.0):
    """puffs: (x, y, z, visual radius[, (sx, sy, sz)]). Stiff metaballs (surface ~0.76 R) keep every puff
    round and distinct while the creases between them get a soft fillet instead of a hard seam."""
    els = []
    for p in puffs:
        x, y, z, rho = p[:4]
        size = p[4] if len(p) > 4 else None
        els.append((x, y, z, rho / 0.76, size) + tuple(p[5:6]))
    me = decimate(meta_mesh(els, res, threshold, stiffness), target)
    mb = MB()
    mesh_into(mb, me, mat, flat_z=base + 0.35, squash=0.08)
    a.part(mb, name="puffs")
    a.set_target(a.name, weighted=False, smooth=80.0)


@asset("cloud_puff_a", "Sky", "p1", ao=SKY_AO, render=SKY_RENDER)
def cloud_puff_a(a):
    """Stylised cumulus (~26 m): soft flat base, a row of big rounded puffs, a second tier and a domed
    crown; stiff metaballs keep each puff round with soft fillets between them."""
    cloud(a, [(-8.5, 0.0, 2.1, 3.1), (-4.4, 0.5, 2.6, 4.0), (0.2, 0.0, 2.8, 4.4), (4.6, -0.5, 2.6, 4.0),
              (8.6, 0.0, 2.1, 3.1), (-11.3, 0.2, 1.5, 1.9), (11.4, -0.2, 1.5, 1.9),
              (-2.6, -3.6, 2.1, 3.0), (2.8, 3.6, 2.1, 3.0), (3.4, -3.2, 1.9, 2.6), (-3.2, 3.2, 1.9, 2.6),
              (-3.0, 0.2, 5.4, 3.5), (2.4, 0.4, 5.8, 3.7), (6.6, 0.0, 4.4, 2.7), (-7.0, 0.0, 4.2, 2.5),
              (-0.2, 0.2, 7.4, 2.8), (3.4, -0.4, 7.4, 2.0), (-3.6, 0.4, 7.0, 1.8)], res=0.7, target=2300)


@asset("cloud_puff_b", "Sky", "p1", ao=SKY_AO, render=SKY_RENDER)
def cloud_puff_b(a):
    """Long low cloud bank (~31 m): a rolling row of round puffs with a gentle raised middle."""
    cloud(a, [(-13.0, 0.0, 1.6, 2.4), (-8.6, 0.3, 2.1, 3.2), (-4.2, -0.2, 2.4, 3.8), (0.4, 0.2, 2.5, 4.0),
              (5.0, -0.3, 2.3, 3.6), (9.4, 0.2, 2.0, 3.0), (13.4, -0.2, 1.5, 2.2),
              (-6.0, 0.0, 4.5, 2.8), (-1.2, 0.3, 5.0, 3.1), (3.8, 0.0, 4.4, 2.6), (8.4, -0.3, 3.6, 2.0),
              (-10.2, 0.0, 3.4, 1.8), (0.2, 3.0, 1.8, 2.6), (-0.6, -3.0, 1.8, 2.5), (-8.0, 2.6, 1.6, 2.1),
              (7.6, -2.6, 1.6, 2.1)], res=0.7, target=2200)


@asset("cloud_puff_c", "Sky", "p1", ao=SKY_AO, render=SKY_RENDER)
def cloud_puff_c(a):
    """Small tufted puff (~14 m): one rounded head on a cushion of smaller puffs."""
    cloud(a, [(0.0, 0.0, 2.3, 3.4), (3.6, 0.4, 1.7, 2.5), (-3.5, -0.3, 1.8, 2.6), (0.5, 2.3, 1.7, 2.2),
              (-0.3, -2.3, 1.7, 2.1), (0.4, 0.0, 4.6, 2.4), (-1.8, 0.5, 3.9, 1.8), (2.4, -0.3, 3.8, 1.7),
              (5.4, 0.0, 1.2, 1.4), (-5.3, 0.3, 1.2, 1.4)], res=0.55, target=1800)


@asset("storm_cloud", "Sky", "p1", ao=dict(SKY_AO, strength=0.6), render=SKY_RENDER)
def storm_cloud(a):
    """Towering storm cell (~56 m wide, ~35 m tall), SKY_Ink: lumpy flat-based skirt with a lowering shelf,
    a lobed cauliflower column, a puffy anvil streaming downwind (+X) with an overshooting dome, and
    mammatus pouches hanging under the anvil overhang."""
    E = (1.2, 1.15, 0.8)
    k = 0.92
    raw = [
        # base skirt
        (-19, 0, 3.4, 4.6), (-12, -3, 3.9, 5.6), (-5, 2, 4.4, 6.2), (2, -2, 4.4, 6.2), (9, 1, 4.1, 5.8),
        (16, -1, 3.6, 5.0), (23, 1, 3.0, 3.8), (-25, -1, 2.8, 3.4), (-9, 6, 3.4, 4.6), (6, 7, 3.4, 4.6),
        (-2, -8, 3.2, 4.6), (12, -6, 3.0, 4.0), (-15, -6, 2.9, 3.6), (19, 5, 3.0, 3.6),
        # shelf cloud: a low rolling row along the front (Blender -Y = Unity north)
        (-10, -11.2, 2.2, 2.6, (1.9, 1.0, 0.85)), (0, -12.0, 2.2, 2.8, (1.9, 1.0, 0.85)),
        (10, -11.2, 2.2, 2.6, (1.9, 1.0, 0.85)),
        # broad lobed column (cauliflower), tapering only a little
        (-10, 1, 9.0, 6.0), (-4, -2, 9.5, 6.4), (2, 2, 9.5, 6.4), (8, -1, 9.0, 6.0), (13, 1, 8.5, 5.0),
        (-8, -1, 14.0, 5.6), (-2, 2, 14.5, 5.8), (4, -2, 14.5, 5.8), (10, 1, 14.0, 5.2),
        (-6, 1, 19.0, 5.0), (0, -1, 19.5, 5.4), (6, 2, 19.5, 5.2), (11, -1, 19.0, 4.6),
        (-4, 0, 23.5, 4.6), (2, 2, 24.0, 4.8), (8, -1, 24.0, 4.6), (13, 1, 23.5, 4.2),
        # anvil: thick layer of round lobes spreading downwind (+X), wider than the column
        (-14, 0, 27.5, 4.0, E), (-8, 2, 28.0, 4.6, E), (-2, -1, 28.2, 5.0, E), (4, 1, 28.4, 5.0, E),
        (10, -1, 28.6, 5.0, E), (16, 1, 28.8, 4.8, E), (22, -1, 29.0, 4.4, E), (28, 1, 29.2, 3.6, E),
        (-4, 6, 28.0, 4.0, E), (4, -6, 28.2, 4.0, E), (12, 6, 28.5, 4.0, E), (20, -6, 28.8, 3.6, E),
        (-4, -6, 28.0, 3.8, E), (12, -6, 28.5, 3.8, E), (20, 6, 28.8, 3.4, E),
        (-5, 1, 31.4, 3.0), (3, -1, 31.8, 3.4), (11, 1, 31.6, 3.0), (18, -1, 31.4, 2.8), (24, 1, 31.2, 2.4),
        # overshooting top
        (2, 0, 33.0, 3.2),
        # mammatus pouches under the downwind overhang
        (17, -3, 24.6, 1.9), (20, 2, 24.5, 2.0), (23, -4, 24.8, 1.8), (25, 1, 24.7, 2.0), (28, -2, 25.0, 1.7),
        (30, 2, 25.2, 1.6), (21, 6, 24.8, 1.7), (26, 5, 25.0, 1.6), (18, 5, 24.7, 1.7), (29, -5, 25.2, 1.5),
    ]
    puffs = [(p[0] * k, p[1], p[2], p[3]) + tuple(p[4:]) for p in raw]
    cloud(a, puffs, mat='SKY_Ink', res=1.0, target=4700)


# --------------------------------------------------------------------------- skyline

def _bld_box(mb, x0, x1, y0, y1, z0, z1, mat, M):
    fs = mb.box(x0, x1, y0, y1, z0, z1, mat)
    mb.transform(M, fs)


def _bld_lathe(mb, prof, seg, mat, M, a0=0.0, mats=None):
    fs = mb.lathe(prof, seg, mat, a0=a0, mats=mats)
    mb.transform(M, fs)


def _skyline_building(mb, kind, M, w, d, h, mat, k, rnd):
    """One distant building in local coords (front face = +Y, toward the ring centre)."""
    hw, hd = w / 2, d / 2
    if kind == 'block':
        _bld_box(mb, -hw, hw, -hd, hd, 0, h, mat, M)
        _bld_box(mb, -hw - 0.6, hw + 0.6, -hd - 0.6, hd + 0.6, h, h + 1.2, 'SKY_Pearl', M)
        for f in ((0.45,) if h < 16 else (0.35, 0.68)):
            _bld_box(mb, -hw * 0.82, hw * 0.82, hd - 0.2, hd + 0.35, h * f, h * f + 1.6, 'SKY_Teal', M)
        if rnd.random() < 0.5:
            _bld_box(mb, -hw * 0.3, hw * 0.3, -hd * 0.4, hd * 0.4, h + 1.2, h + 4.5, mat, M)
    elif kind == 'stepped':
        _bld_box(mb, -hw, hw, -hd, hd, 0, h * 0.55, mat, M)
        _bld_box(mb, -hw * 0.72, hw * 0.72, -hd * 0.75, hd * 0.75, h * 0.55, h * 0.82, mat, M)
        _bld_box(mb, -hw * 0.42, hw * 0.42, -hd * 0.5, hd * 0.5, h * 0.82, h, mat, M)
        _bld_box(mb, -hw - 0.5, hw + 0.5, -hd - 0.5, hd + 0.5, h * 0.55 - 0.9, h * 0.55, 'SKY_Pearl', M)
        _bld_box(mb, -hw * 0.62, hw * 0.62, hd * 0.75 - 0.2, hd * 0.75 + 0.35, h * 0.64, h * 0.64 + 1.6, 'SKY_Teal', M)
    elif kind == 'tower':
        _bld_box(mb, -hw, hw, -hd * 0.7, hd * 0.7, 0, h, mat, M)
        for f in (0.3, 0.55, 0.8):
            _bld_box(mb, -hw - 0.4, hw + 0.4, -hd * 0.7 - 0.4, hd * 0.7 + 0.4, h * f, h * f + 2.2, 'SKY_Teal', M)
        _bld_box(mb, -hw - 1.0, hw + 1.0, -hd * 0.7 - 1.0, hd * 0.7 + 1.0, h, h + 1.4, 'SKY_Pearl', M)
        _bld_box(mb, -hw * 0.35, hw * 0.35, -hd * 0.3, hd * 0.3, h + 1.4, h + 6.0, 'SKY_Pearl', M)
        _bld_lathe(mb, [(0, h + 6.0), (hw * 0.32, h + 6.0), (0, h + 10.0)], 4, 'SKY_Brass', M, a0=45)
    elif kind == 'dome':
        _bld_box(mb, -hw, hw, -hd, hd, 0, h, mat, M)
        _bld_box(mb, -hw - 0.5, hw + 0.5, -hd - 0.5, hd + 0.5, h, h + 1.0, 'SKY_Pearl', M)
        rd = min(hw, hd) * 0.72
        prof = [(0, h + 1.0), (rd, h + 1.0), (rd, h + 3.2)]
        for i in range(1, 4):
            t = i / 4
            prof.append((rd * math.cos(t * math.pi / 2), h + 3.2 + rd * 0.95 * math.sin(t * math.pi / 2)))
        prof.append((0, h + 3.2 + rd * 0.95))
        dmat = 'SKY_TealLight' if k % 2 else 'SKY_Pearl'
        _bld_lathe(mb, prof, 8, dmat, M, mats=['SKY_Pearl', 'SKY_Pearl', dmat, dmat, dmat, dmat])
        _bld_lathe(mb, [(0, h + 3.0 + rd * 0.95), (0.6, h + 3.0 + rd * 0.95), (0, h + 6.0 + rd * 0.95)], 4,
                   'SKY_Brass', M)
    elif kind == 'wind':
        _bld_box(mb, -hw, hw, -hd, hd, 0, h, mat, M)
        tw = min(hw, 3.0)
        th = h + rnd.uniform(9, 14)
        _bld_box(mb, -tw, tw, -tw, tw, h, th, mat, M)
        for (sx, sy) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            _bld_box(mb, sx * tw - (0.0 if sx < 0 else 0.9), sx * tw + (0.9 if sx < 0 else 0.0),
                     sy * tw - (0.0 if sy < 0 else 0.9), sy * tw + (0.9 if sy < 0 else 0.0), th, th + 3.2, mat, M)
        _bld_box(mb, -tw - 0.5, tw + 0.5, -tw - 0.5, tw + 0.5, th + 3.2, th + 4.2, 'SKY_Pearl', M)
    elif kind == 'arcade':
        _bld_box(mb, -hw, hw, -hd, hd, 0, h, mat, M)
        _bld_box(mb, -hw - 0.5, hw + 0.5, -hd - 0.5, hd + 0.5, h, h + 0.9, 'SKY_Pearl', M)
        n = max(3, int(w / 5.0))
        for i in range(n):
            x = -hw + (i + 0.5) * w / n
            pts = [(x + px, pz) for (px, pz) in arch_pts(w / n * 0.62, h * 0.62, 'round', 4, base=0.0)]
            fs = mb.prism_frame(pts, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), hd - 0.2, hd + 0.3, 'SKY_Teal')
            mb.transform(M, fs)
    else:  # spire
        _bld_box(mb, -hw, hw, -hw, hw, 0, 8, mat, M)
        _bld_lathe(mb, [(0, 8), (2.2, 8), (1.7, h * 0.72), (2.7, h * 0.72 + 0.6), (2.7, h * 0.72 + 1.6),
                        (1.4, h * 0.72 + 2.0), (1.2, h * 0.92), (1.9, h * 0.92 + 0.5), (1.9, h * 0.92 + 2.0),
                        (0.0, h * 0.92 + 4.6)], 8, 'SKY_Pearl', M, a0=22.5,
                   mats=['SKY_Pearl', 'SKY_Pearl', 'SKY_Pearl', 'SKY_Brass', 'SKY_Pearl', 'SKY_Pearl',
                         'SKY_Pearl', 'SKY_Teal', 'SKY_TealLight'])
        _bld_lathe(mb, [(0, h * 0.92 + 4.4), (0.35, h * 0.92 + 4.4), (0, h * 0.92 + 8.0)], 4, 'SKY_Brass', M)


@asset("skyline_ring_piece", "Sky", "p1", ao=dict(SKY_AO, dist=8.0), render=dict(az=0.0, el=8.0))
def skyline_ring_piece(a):
    """Distant skyline: a 30 deg arc (radius ~320 m) of low-poly Nacre Bay silhouettes in two rows on a
    harbour terrace - pearl and sandstone blocks with parapets and teal glass bands, stepped terraces,
    arcaded halls, glass-banded towers, domed halls, slender wind towers and lantern spires; faces the
    ring centre (pivot). Twelve copies close the ring."""
    rnd = random.Random(42)
    R = 320.0
    mb = MB()
    n = 10
    for k in range(n):
        a0 = math.radians(-15 + 30 * k / n - 90)
        a1 = math.radians(-15 + 30 * (k + 1) / n - 90)
        ri, ro = R - 14.0, R + 17.0
        q = [(ri * math.cos(a0), ri * math.sin(a0)), (ro * math.cos(a0), ro * math.sin(a0)),
             (ro * math.cos(a1), ro * math.sin(a1)), (ri * math.cos(a1), ri * math.sin(a1))]
        mb.prism(q, 0.0, 3.0, 'SKY_SandstoneDeep')
        qi = [(p[0] * (R - 12.5) / ri, p[1] * (R - 12.5) / ri) if i in (0, 3) else p for i, p in enumerate(q)]
        mb.prism(qi, 3.0, 3.8, 'SKY_Pearl')
    # back row: tall silhouettes
    back = ['tower', 'stepped', 'spire', 'block', 'dome', 'tower', 'block', 'stepped', 'spire', 'tower']
    ang, k = -14.5, 0
    while ang < 14.2:
        kind = back[k % len(back)]
        w = {'block': rnd.uniform(12, 18), 'stepped': rnd.uniform(16, 24), 'tower': rnd.uniform(9, 13),
             'dome': rnd.uniform(16, 22), 'spire': rnd.uniform(5, 7)}[kind]
        h = {'block': rnd.uniform(22, 34), 'stepped': rnd.uniform(26, 40), 'tower': rnd.uniform(40, 62),
             'dome': rnd.uniform(16, 22), 'spire': rnd.uniform(48, 64)}[kind]
        dang = math.degrees(w / R)
        mid = math.radians(ang + dang / 2 - 90)
        r0 = R + rnd.uniform(6, 10)
        M = M_tr(r0 * math.cos(mid), r0 * math.sin(mid), 3.0) @ M_rot(math.degrees(mid) + 90)
        _skyline_building(mb, kind, M, w, rnd.uniform(10, 14), h,
                          ['SKY_Sandstone', 'SKY_Pearl', 'SKY_Ivory', 'SKY_Pearl'][k % 4], k, rnd)
        ang += dang + rnd.uniform(0.6, 1.6)
        k += 1
    # front row: low waterfront buildings
    front = ['arcade', 'block', 'dome', 'wind', 'stepped', 'block', 'arcade', 'wind', 'block', 'dome']
    ang = -14.8
    while ang < 14.3:
        kind = front[k % len(front)]
        w = {'block': rnd.uniform(11, 16), 'stepped': rnd.uniform(14, 20), 'arcade': rnd.uniform(22, 30),
             'dome': rnd.uniform(14, 18), 'wind': rnd.uniform(7, 10)}[kind]
        h = {'block': rnd.uniform(9, 16), 'stepped': rnd.uniform(14, 20), 'arcade': rnd.uniform(8, 11),
             'dome': rnd.uniform(10, 14), 'wind': rnd.uniform(8, 12)}[kind]
        dang = math.degrees(w / R)
        mid = math.radians(ang + dang / 2 - 90)
        r0 = R - rnd.uniform(4, 7)
        M = M_tr(r0 * math.cos(mid), r0 * math.sin(mid), 3.0) @ M_rot(math.degrees(mid) + 90)
        _skyline_building(mb, kind, M, w, rnd.uniform(9, 12), h,
                          ['SKY_Pearl', 'SKY_Sandstone', 'SKY_Pearl', 'SKY_Ivory'][k % 4], k, rnd)
        ang += dang + rnd.uniform(0.25, 0.9)
        k += 1
    a.part(mb, name="blocks")
    a.notes.append("Pivot at the ring centre; geometry spans a 30 deg arc at r~320 m centred on Unity north.")


# --------------------------------------------------------------------------- rocks

def strata_rock(mb, seed, base_r, height, layers, n=12, taper=0.55, jitter=0.2, ledge=0.07, lean=(0.0, 0.0),
                sx=1.0, sy=1.0, z0=0.0, wet=None, peak=0.35, cracks=2, mats=None, top_mat='SKY_Sandstone'):
    """Weathered strata stack: each layer is a slightly bulging wall band topped by a lit inward ledge.
    Angular jitter is shared through the stack so facets and cracks run vertically; each layer drifts and
    breathes a little. Returns the faces."""
    rnd = random.Random(seed)
    angs = [2 * math.pi * (k + rnd.uniform(-0.22, 0.22)) / n for k in range(n)]
    shape = [1.0 + rnd.uniform(-jitter, jitter) for _ in range(n)]
    for _ in range(cracks):
        c = rnd.randrange(n)
        shape[c] *= 0.82
    wall, ledge_m = (mats or ('SKY_SandstoneDeep', top_mat))
    rings, kinds = [], []
    drift = Vector((0, 0))
    for i in range(layers):
        t0, t1 = i / layers, (i + 1) / layers
        za, zb = z0 + height * t0, z0 + height * t1
        ra = base_r * (1 - taper * t0)
        rb = base_r * (1 - taper * t1)
        drift += Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * base_r * 0.035
        off = drift + Vector(lean) * t0
        layer = [m * (1 + rnd.uniform(-0.05, 0.05)) for m in shape]
        bulge = 1.0 + rnd.uniform(0.03, 0.08)

        def R_(r, k, f=1.0):
            return (off.x + r * f * layer[k] * math.cos(angs[k]) * sx, off.y + r * f * layer[k] * math.sin(angs[k]) * sy)
        if i == 0:
            rings.append([(*R_(ra, k), za) for k in range(n)])
        lz = zb - (zb - za) * 0.16
        rings.append([(*R_(ra * 0.5 + rb * 0.5, k, bulge), za + (zb - za) * 0.5) for k in range(n)])
        rings.append([(*R_(rb, k, 1.02), lz) for k in range(n)])
        kinds += ['wall', 'wall']
        if i < layers - 1:
            rings.append([(*R_(rb, k, 1.0 - ledge), zb) for k in range(n)])
            kinds.append('ledge')
    # rounded top: shrink to a crest
    zt = z0 + height
    last = rings[-1]
    cxy = Vector((sum(p[0] for p in last) / n, sum(p[1] for p in last) / n))
    rings.append([(cxy.x + (p[0] - cxy.x) * 0.72, cxy.y + (p[1] - cxy.y) * 0.72, zt + height * 0.02) for p in last])
    kinds.append('ledge')
    V = [[mb.v(p) for p in r] for r in rings]
    fs = []
    for i in range(len(V) - 1):
        for k in range(n):
            k2 = (k + 1) % n
            q = [V[i][k], V[i][k2], V[i + 1][k2], V[i + 1][k]]
            zc = sum(v.co.z for v in q) / 4
            m = ledge_m if kinds[i] == 'ledge' else wall
            if wet is not None and zc < wet:
                m = wall
            fs.append(mb.f(q, m))
    top = mb.v((cxy.x, cxy.y, zt + height * peak * 0.12))
    for k in range(n):
        fs.append(mb.f([V[-1][k], V[-1][(k + 1) % n], top], top_mat))
    fs.append(mb.f(list(reversed(V[0])), wall))
    mb._recalc(fs)
    return fs


ROCK_AO = dict(ground_z=0.0, dist=1.5, rays=20, strength=0.7, floor=0.45, inset=0.2)


@asset("rock_sea_a", "Nature", "p1", ao=ROCK_AO, render=dict(az=30.0, el=20.0, water=True, seabed=0.0))
def rock_sea_a(a):
    """Sea rock ~5.6 m tall from its base (place the base on the seabed at Z-4): layered sandstone strata
    with lit ledges and vertical cracks, a leaning companion stack and a few weed tufts on top."""
    mb = MB()
    strata_rock(mb, 3, 3.3, 5.5, 6, n=14, taper=0.62, lean=(0.4, 0.2), sx=1.0, sy=1.08, wet=2.8, cracks=3)
    a.part(mb, name="rock")
    mb = MB()
    fs = strata_rock(mb, 5, 1.55, 3.4, 4, n=11, taper=0.6, lean=(0.3, 0.1), wet=2.8)
    mb.transform(M_tr(2.85, 1.75, 0), fs)
    fs = strata_rock(mb, 9, 1.0, 1.7, 2, n=9, taper=0.5, wet=2.8)
    mb.transform(M_tr(-2.3, -2.6, 0), fs)
    a.part(mb, name="rock2")
    mb = MB()
    for (x, y, z, r) in ((0.55, 0.25, 5.62, 0.42), (0.1, 0.45, 5.55, 0.3), (3.05, 1.85, 3.42, 0.3)):
        ico(mb, (x, y, z), r, 'SKY_PalmLeaf', level=2, sz=0.55, noise=0.2, seed=int(x * 10))
    a.part(mb, name="weed")
    a.set_target(a.name, weighted=False, smooth=25.0)


@asset("rock_sea_b", "Nature", "p1", ao=ROCK_AO, render=dict(az=30.0, el=20.0, water=True, seabed=0.0))
def rock_sea_b(a):
    """Low sea-rock cluster ~4.7 m tall from its base: a broad strata table, a second stack and a pinnacle."""
    mb = MB()
    strata_rock(mb, 11, 3.5, 4.5, 5, n=14, taper=0.5, lean=(-0.3, 0.2), sx=1.05, sy=0.9, wet=2.8, cracks=3)
    a.part(mb, name="rock")
    mb = MB()
    fs = strata_rock(mb, 13, 1.75, 4.1, 5, n=11, taper=0.62, lean=(-0.2, -0.2), wet=2.8)
    mb.transform(M_tr(-3.15, -1.0, 0), fs)
    fs = strata_rock(mb, 17, 0.95, 3.8, 4, n=9, taper=0.66, lean=(0.15, -0.1), wet=2.8)
    mb.transform(M_tr(2.6, -2.2, 0), fs)
    a.part(mb, name="rock2")
    mb = MB()
    for (x, y, z, r) in ((-0.2, 0.3, 4.6, 0.45), (-3.1, -1.0, 4.15, 0.28)):
        ico(mb, (x, y, z), r, 'SKY_PalmLeaf', level=2, sz=0.55, noise=0.2, seed=int(abs(x) * 10))
    a.part(mb, name="weed")
    a.set_target(a.name, weighted=False, smooth=25.0)


@asset("cliff_headland", "Nature", "p1", ao=dict(ROCK_AO, dist=4.0, ground_z=None), render=dict(az=35.0, el=18.0))
def cliff_headland(a):
    """Rocky headland (~38 x 42 m, 26 m drop) for the Fold Atelier: gently dipping sandstone strata with
    overhanging lips and lit ledges of varying depth, vertical cracks, grass tufts on the ledges, a rim of
    shrubs and boulders at the foot. Pivot = atelier origin: the flat plateau sits at Z-2.8 so
    atelier_platform (deck Z0) beds its rock plinth into it."""
    rnd = random.Random(8)
    n = 32
    angs = [2 * math.pi * (k + rnd.uniform(-0.18, 0.18)) / n for k in range(n)]
    shape = [1.0 + rnd.uniform(-0.07, 0.07) for _ in range(n)]
    for c in (3, 11, 17, 24, 29):
        shape[c] *= 0.88
    layers = [(-26.0, 17.6), (-22.8, 17.0), (-19.0, 16.3), (-16.2, 15.4), (-12.6, 14.4), (-9.6, 13.4),
              (-6.6, 12.3), (-4.2, 11.4), (-2.8, 10.9)]
    dip_dir = 0.7

    def dip(k, z):
        # strata dip ~1 m across the headland, fading to zero at the flat plateau
        f = max(0.0, min(1.0, (-3.6 - z) / 3.0))
        return 1.1 * math.cos(angs[k] - dip_dir) * f

    def P(r, k, z, f=1.0):
        ang = angs[k]
        stretch = 1.0 + 0.24 * max(0.0, -math.sin(ang))          # promontory toward Unity north
        rr = r * stretch * shape[k] * f
        return (rr * math.cos(ang), rr * math.sin(ang), z + dip(k, z))
    rings, kinds = [], []
    for i in range(len(layers) - 1):
        (za, ra), (zb, rb) = layers[i], layers[i + 1]
        jit = [1.0 + rnd.uniform(-0.03, 0.03) for _ in range(n)]
        lipf = [1.02 + rnd.uniform(0.0, 0.07) ** 1.5 * 2.2 for _ in range(n)]
        if i == 0:
            rings.append([P(ra * 1.02, k, za - 0.4) for k in range(n)])
            kinds.append('wall')
        rings.append([P(ra * 0.985 * jit[k], k, za + (zb - za) * 0.12) for k in range(n)])
        rings.append([P((ra * 0.55 + rb * 0.45) * 1.01 * jit[k], k, za + (zb - za) * 0.62) for k in range(n)])
        rings.append([P(rb * lipf[k] * jit[k], k, zb - (zb - za) * 0.06) for k in range(n)])
        kinds += ['wall', 'wall', 'lip' if i < len(layers) - 2 else 'rim']
    rings.append([P(10.9, k, -2.8) for k in range(n)])
    kinds.append('top')
    mb = MB()
    VV = [[mb.v(p) for p in r] for r in rings]
    fs = []
    for i in range(len(VV) - 1):
        for k in range(n):
            k2 = (k + 1) % n
            q = [VV[i][k], VV[i][k2], VV[i + 1][k2], VV[i + 1][k]]
            m = 'SKY_Sandstone' if kinds[i] in ('lip', 'rim') else 'SKY_SandstoneDeep'
            fs.append(mb.f(q, m))
    fs.append(mb.f(list(VV[-1]), 'SKY_Sandstone'))
    fs.append(mb.f(list(reversed(VV[0])), 'SKY_SandstoneDeep'))
    mb._recalc(fs)
    a.part(mb, name="mass")
    # boulders at the foot and on two ledges
    mb = MB()
    for i in range(10):
        ang = rnd.uniform(0, 2 * math.pi)
        z = -26.0 if i < 7 else rnd.choice([-16.2, -9.6])
        r_l = {-26.0: 18.3, -16.2: 15.9, -9.6: 13.8}[z]
        stretch = 1.0 + 0.24 * max(0.0, -math.sin(ang))
        fs = strata_rock(mb, 30 + i, rnd.uniform(1.4, 2.5), rnd.uniform(1.6, 3.0), 2, n=8, taper=0.45, jitter=0.25)
        kk = min(range(n), key=lambda j: abs(math.remainder(angs[j] - ang, 2 * math.pi)))
        mb.transform(M_tr(r_l * stretch * math.cos(ang), r_l * stretch * math.sin(ang), z - 0.3 + dip(kk, z)), fs)
    a.part(mb, name="boulders")
    # greenery: grass tufts along ledges and a rim of shrubs on the plateau edge
    mb = MB()
    for i in range(24):
        k = rnd.randrange(n)
        li = rnd.randrange(2, len(layers) - 1)
        z, r = layers[li]
        p = P(r * 1.0, k, z)
        ico(mb, (p[0], p[1], p[2] + 0.12), rnd.uniform(0.55, 1.0), 'SKY_PalmLeaf', level=2, sz=0.42, noise=0.25,
            seed=100 + i)
    for i in range(16):
        k = (i * 2 + 1) % n
        p = P(10.4, k, -2.8)
        if math.sin(angs[k]) < -0.55:      # keep the view side (Unity north) open
            continue
        ico(mb, (p[0], p[1], -2.75), rnd.uniform(0.7, 1.0), 'SKY_PalmLeaf', level=2, sz=0.7, noise=0.22,
            seed=200 + i)
    a.part(mb, name="greens")
    a.set_target(a.name, weighted=False, smooth=28.0)
    a.notes.append("Plateau at Z-2.8 around the pivot (flat to r~10.5); cliff foot at about Z-26.")


# --------------------------------------------------------------------------- dhow

def _hull_frame(t, L=7.6):
    """Station t (0 stern .. 1 bow): (y, half-beam, sheer z, keel z)."""
    y = L / 2 - t * L
    beam = 1.15 * math.sin(math.pi * (0.12 + 0.88 * t)) ** 0.75 + 0.04
    sheer = 0.95 + 0.6 * (t ** 3) + 0.28 * ((1 - t) ** 4)
    keel = -0.75 * math.sin(math.pi * min(1.0, 0.08 + t)) ** 0.55
    return y, beam, sheer, keel


def _half_width(t, z, L=7.6, inset=0.0):
    """Hull half-width at station t and height z (outer skin minus inset)."""
    y, beam, sheer, keel = _hull_frame(t, L)
    prev = (0.0, keel)
    for i in range(1, 41):
        th = i / 40 * math.pi / 2
        x = beam * math.sin(th) ** 0.62
        zz = keel + (sheer - keel) * (1 - math.cos(th)) ** 1.05
        if zz >= z:
            f = (z - prev[1]) / max(1e-6, zz - prev[1])
            return max(0.0, prev[0] + (x - prev[0]) * f - inset)
        prev = (x, zz)
    return max(0.0, beam - inset)


def _section(beam, sheer, keel, phis):
    """Half-section points (x >= 0) from keel to sheer for the given bilge parameters."""
    pts = []
    for ph in phis:
        th = ph * math.pi / 2
        x = beam * math.sin(th) ** 0.62
        z = keel + (sheer - keel) * (1 - math.cos(th)) ** 1.05
        pts.append((x, z))
    return pts


@asset("dhow_small", "Props", "p1", ao=dict(ground_z=None, dist=0.8, rays=24, strength=0.75, floor=0.45, inset=0.08),
       render=dict(az=60.0, el=16.0, water=True, seabed=-4.0))
def dhow_small(a):
    """Small fictional wooden sailing boat (~8 m): open lapstrake hull (plank steps, pearl boot-top, teal
    sheer strake, gunwale), ribs, thwarts and floorboards inside, foredeck, raised stern deck with a shade
    canopy, rudder and tiller, raked stem post, forward-raked mast, long lateen yard with a billowing sail,
    shrouds, forestay, sheet and a pennant. Pivot on the waterline at mid-length (place at Z-1.2); bow
    toward Unity north (Blender -Y)."""
    L = 7.6
    NS = 20
    strakes = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    step = 0.018
    t_wall = 0.05
    loops, info = [], []
    for i in range(NS + 1):
        t = i / NS
        y, beam, sheer, keel = _hull_frame(t, L)
        half = _section(beam, sheer, keel, strakes)
        # outer half with lapstrake steps: at every inner boundary, a point stepped outward
        outer = []
        for j, (x, z) in enumerate(half):
            if 0 < j < len(half) - 1:
                outer.append((x, z))
                outer.append((x + step, z + 0.004))
            else:
                outer.append((x, z))
        inner = _section(max(0.02, beam - t_wall), sheer - 0.02, keel + t_wall, [0.0, 0.35, 0.7, 1.0])
        # loop: port outer (sheer -> keel), starboard outer (keel -> sheer), starboard inner (sheer -> keel),
        # port inner (keel -> sheer)
        port_out = [(-x, z) for (x, z) in reversed(outer)]
        stb_out = [(x, z) for (x, z) in outer[1:]]
        stb_in = [(x, z) for (x, z) in reversed(inner)]
        port_in = [(-x, z) for (x, z) in inner[1:]]
        loop = port_out + stb_out + stb_in + port_in
        loops.append([(x, y, z) for (x, z) in loop])
        info.append((len(port_out), len(stb_out), len(stb_in)))
    mb = MB()
    VV = [[mb.v(p) for p in lp] for lp in loops]
    n = len(VV[0])
    n_out = info[0][0] + info[0][1]
    fs = []
    for i in range(NS):
        for k in range(n):
            k2 = (k + 1) % n
            q = [VV[i][k], VV[i][k2], VV[i + 1][k2], VV[i + 1][k]]
            zc = sum(v.co.z for v in q) / 4
            if k < n_out - 1:                         # outer skin
                if k in (0, n_out - 2):               # top strake on both sides
                    m = 'SKY_Teal'
                elif zc < 0.02:
                    m = 'SKY_Pearl'
                else:
                    m = 'SKY_Wood'
            else:
                m = 'SKY_Wood'
            fs.append(mb.f(q, m))
    fs.append(mb.f(list(reversed(VV[0])), 'SKY_Wood'))      # transom
    fs.append(mb.f(list(VV[-1]), 'SKY_Wood'))               # stem face (hidden by the stem post)
    mb._recalc(fs)
    a.part(mb, name="hull")
    # gunwale rails and the raked stem post with a brass finial
    mb = MB()
    for s in (-1, 1):
        path = []
        for i in range(0, NS + 1, 2):
            t = i / NS
            y, beam, sheer, keel = _hull_frame(t, L)
            path.append(Vector((s * (beam - 0.012), y, sheer + 0.018)))
        mb.sweep(path, cham_rect(0.085, 0.055, 0.0), 'SKY_Wood')
    y1, b1, s1, k1 = _hull_frame(1.0, L)
    stem = bezier3((0, y1 + 0.5, k1 + 0.05), (0, y1 - 0.04, k1 + 0.3), (0, y1 - 0.2, s1 - 0.2), (0, y1 - 0.34, s1 + 0.5), 7)
    mb.sweep(stem, cham_rect(0.12, 0.1, 0.02), 'SKY_Wood')
    mb.sphere(0.07, 6, 3, 'SKY_Brass', c=tuple(stem[-1] + Vector((0, 0, 0.03))))
    a.part(mb, name="rails")
    # inside: ribs, thwarts, floorboards, decks
    mb = MB()
    for i in (5, 8, 11, 14):
        t = i / NS
        y, beam, sheer, keel = _hull_frame(t, L)
        inner = _section(max(0.02, beam - t_wall - 0.02), sheer - 0.06, keel + t_wall + 0.02, [0.0, 0.25, 0.5, 0.75, 1.0])
        path = [Vector((-x, y, z)) for (x, z) in reversed(inner)] + [Vector((x, y, z)) for (x, z) in inner[1:]]
        mb.sweep(path, cham_rect(0.06, 0.045, 0.0), 'SKY_Wood', up=Vector((0, 1, 0)))
    for t in (0.38, 0.62):
        y, beam, sheer, keel = _hull_frame(t, L)
        bar(mb, (-(beam - 0.06), y, sheer - 0.24), ((beam - 0.06), y, sheer - 0.24), 0.26, 0.06, 'SKY_Wood', c=0.015)
    fl_l, fl_r = [], []
    for j in range(7):
        t = 0.28 + 0.48 * j / 6
        y = _hull_frame(t, L)[0]
        hw = min(0.5, _half_width(t, -0.32, L, inset=0.07))
        fl_r.append((hw, y))
        fl_l.append((-hw, y))
    mb.prism(fl_r + list(reversed(fl_l)), -0.36, -0.32, 'SKY_Wood')
    # stern deck and foredeck (follow the hull plan)
    for (ta, tb, dz) in ((0.0, 0.22, -0.16), (0.84, 0.98, -0.1)):
        pts_l, pts_r = [], []
        for j in range(5):
            t = ta + (tb - ta) * j / 4
            y, beam, sheer, keel = _hull_frame(t, L)
            pts_l.append((-(beam - 0.04), y))
            pts_r.append(((beam - 0.04), y))
        poly = pts_r + list(reversed(pts_l))
        y_, b_, s_, k_ = _hull_frame((ta + tb) / 2, L)
        mb.prism(poly, s_ + dz - 0.06, s_ + dz, 'SKY_Wood')
    a.part(mb, name="interior")
    # stern shade canopy on four posts, rudder and tiller
    mb = MB()
    yc0, bc0, sc0, kc0 = _hull_frame(0.04, L)
    yc1, bc1, sc1, kc1 = _hull_frame(0.2, L)
    deck_z = _hull_frame(0.11, L)[2] - 0.16
    roof_z = deck_z + 1.35
    for (xx, yy) in ((-0.62, yc0 - 0.12), (0.62, yc0 - 0.12), (-0.72, yc1 + 0.1), (0.72, yc1 + 0.1)):
        bar(mb, (xx, yy, deck_z - 0.05), (xx, yy, roof_z), 0.06, 0.06, 'SKY_Wood', c=0.012, up=Vector((0, 1, 0)))
    a.part(mb, name="canopy_posts")
    mb = MB()
    arch = []
    for j in range(7):
        u = -1 + 2 * j / 6
        arch.append((0.86 * u, roof_z + 0.18 * (1 - u * u)))
    shell = arch + [(x * 0.97, z - 0.04) for (x, z) in reversed(arch)]
    mb.prism_frame(shell, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), yc1 + 0.02, yc0 - 0.02, 'SKY_Fabric')
    a.part(mb, name="canopy")
    mb = MB()
    ys = L / 2 + 0.02
    mb.prism_frame([(0.0, 0.35), (0.1, 0.35), (0.34, -0.2), (0.3, -0.6), (0.0, -0.64)], (0, ys, 0), (0, 1, 0),
                   (0, 0, 1), (1, 0, 0), -0.035, 0.035, 'SKY_Wood')
    bar(mb, (0, ys + 0.06, 0.62), (0, ys - 0.95, 1.02), 0.05, 0.05, 'SKY_Wood', c=0.01, up=Vector((0, 0, 1)))
    mb.cyl(0.03, 0.3, 0.66, 6, 'SKY_Brass', cx=0.0, cy=ys + 0.06)
    a.part(mb, name="rudder")
    # mast (raked forward), yard, sail, rigging, pennant
    mt = 0.56
    ym, bm_, sm, km = _hull_frame(mt, L)
    foot = Vector((0.0, ym, km + 0.1))
    head = Vector((0.0, ym - 0.75, 6.0))
    mb = MB()
    mb.sweep([foot, head], circle(1.0, 8), 'SKY_Wood', scales=[0.085, 0.05])
    mb.sphere(0.075, 8, 4, 'SKY_Brass', c=tuple(head + Vector((0, -0.02, 0.06))))
    a.part(mb, name="mast")
    tack = Vector((0.0, -3.55, 1.45))
    peak = Vector((0.0, 2.75, 7.3))
    mid_y = head + Vector((0, 0, -0.2))
    mb = MB()
    yard = bezier3(tack, tack.lerp(mid_y, 0.6), mid_y.lerp(peak, 0.4) + Vector((0, 0, 0.1)), peak, 10)
    mb.sweep(yard, circle(1.0, 6), 'SKY_Wood', scales=[0.04 + 0.03 * math.sin(math.pi * i / 10) for i in range(11)])
    a.part(mb, name="yard")
    # lateen sail: triangle tack / peak / clew, head lashed along the yard, billowing to starboard,
    # teal tabling along the foot
    mb = MB()
    clew = Vector((0.06, 2.2, 1.6))
    C0, C1, C2 = tack + Vector((0.07, 0, -0.06)), peak + Vector((0.07, 0, -0.06)), clew
    n = 8

    def yard_at(f):
        idx = f * 10
        i0 = min(int(idx), 9)
        return yard[i0].lerp(yard[i0 + 1], idx - i0) + Vector((0.07, 0, -0.06))
    Pt = {}
    for i in range(n + 1):
        for j in range(n + 1 - i):
            u, v = i / n, j / n
            w_ = 1 - u - v
            flat = C0 * w_ + C1 * u + C2 * v
            if u + w_ > 1e-6:
                f = u / (u + w_)
                head_off = yard_at(f) - C0.lerp(C1, f)
                flat = flat + head_off * (1 - v) ** 2
            Pt[(i, j)] = flat + Vector((0.55 * 27 * u * v * w_, 0, 0))
    faces = []
    for i in range(n):
        for j in range(n - i):
            faces.append([(i, j), (i + 1, j), (i, j + 1)])
            if i + j + 2 <= n:
                faces.append([(i + 1, j), (i + 1, j + 1), (i, j + 1)])
    T = {k: mb.v(p) for k, p in Pt.items()}
    B = {k: mb.v(p + Vector((-0.03, 0, 0))) for k, p in Pt.items()}
    fs = []
    cnt = {}
    for f in faces:
        m = 'SKY_Teal' if all(k[0] <= 1 for k in f) else 'SKY_Fabric'
        fs.append(mb.f([T[k] for k in f], m))
        fs.append(mb.f([B[k] for k in reversed(f)], m))
        for e in range(3):
            key = tuple(sorted((f[e], f[(e + 1) % 3])))
            cnt[key] = cnt.get(key, 0) + 1
    for f in faces:
        for e in range(3):
            a_, b_ = f[e], f[(e + 1) % 3]
            if cnt[tuple(sorted((a_, b_)))] == 1:
                fs.append(mb.f([T[b_], T[a_], B[a_], B[b_]], 'SKY_Fabric'))
    mb._recalc(fs)
    a.part(mb, name="sail")
    mb = MB()
    for s in (-1, 1):
        yy, bb, ss, kk = _hull_frame(0.48, L)
        line(mb, head + Vector((0, 0, -0.15)), (s * (bb - 0.02), yy, ss + 0.04), 0.014, 'SKY_Kerb')
        yy, bb, ss, kk = _hull_frame(0.66, L)
        line(mb, head + Vector((0, 0, -0.25)), (s * (bb - 0.02), yy, ss + 0.04), 0.014, 'SKY_Kerb')
    line(mb, head + Vector((0, -0.05, -0.1)), stem[-2], 0.014, 'SKY_Kerb')
    line(mb, clew, (0.4, L / 2 - 0.45, _hull_frame(0.06, L)[2] + 0.05), 0.016, 'SKY_Kerb')
    tip = head + Vector((0, -0.02, 0.14))
    pen = [(tip.y, tip.z), (tip.y + 0.7, tip.z - 0.12), (tip.y, tip.z - 0.24)]
    mb.prism_frame(pen, (0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), -0.012, 0.012, 'SKY_Coral')
    a.part(mb, name="rigging")
    a.set_target(a.name, smooth=50.0)
    a.notes.append("Pivot on the waterline (Z0) at mid-length; hull draft ~0.75 m.")


# --------------------------------------------------------------------------- buoy

@asset("buoy", "Props", "p1", ao=dict(ground_z=None, dist=0.4, rays=20, strength=0.7, floor=0.5, inset=0.05),
       render=dict(az=35.0, el=18.0, water=True, seabed=-4.0))
def buoy(a):
    """Channel buoy (~2.4 m): ink-bottomed coral float with a pearl band and a rubber fender, mooring eye
    below, a four-leg coral lattice tower with ring braces, brass lantern with a warm ribbed lamp and a coral
    cone topmark. Pivot on the waterline (Z0)."""
    I, C, P, B = 'SKY_Ink', 'SKY_Coral', 'SKY_Pearl', 'SKY_Brass'
    mb = MB()
    prof = [(0, -0.56), (0.22, -0.54), (0.42, -0.46), (0.55, -0.3), (0.6, -0.1), (0.6, 0.1), (0.58, 0.16),
            (0.58, 0.24), (0.5, 0.31), (0.34, 0.36), (0.0, 0.38)]
    mb.lathe(prof, 16, C, mats=[I, I, I, I, C, C, P, P, C, C])
    a.part(mb, name="float")
    mb = MB()
    torus(mb, 0.6, 0.05, 16, 6, 'SKY_Rubber')
    torus(mb, 0.06, 0.016, 8, 4, 'SKY_Metal', M=M_tr(0, 0, -0.62) @ M_rot(90, 'X'))
    mb.cyl(0.03, -0.585, -0.54, 6, 'SKY_Metal')
    a.part(mb, name="fender")
    # lattice tower
    mb = MB()
    for k in range(4):
        ang = math.radians(45 + 90 * k)
        c, s = math.cos(ang), math.sin(ang)
        mb.sweep([Vector((0.3 * c, 0.3 * s, 0.3)), Vector((0.15 * c, 0.15 * s, 1.27))], circle(0.022, 4, a0=45), C)
    for (z, r) in ((0.72, 0.235), (1.24, 0.165)):
        ring(mb, r - 0.02, r + 0.02, z - 0.025, z + 0.025, 8, C, ch=0.01, a0=22.5)
    for k in range(4):
        ang0 = math.radians(45 + 90 * k)
        ang1 = math.radians(45 + 90 * (k + 1))
        p0 = Vector((0.3 * math.cos(ang0), 0.3 * math.sin(ang0), 0.32))
        p1 = Vector((0.2 * math.cos(ang1), 0.2 * math.sin(ang1), 0.98))
        mb.sweep([p0, p1], circle(0.012, 4, a0=45), P)
    mb.lathe([(0, 1.24), (0.2, 1.24), (0.2, 1.27), (0.18, 1.29), (0, 1.29)], 8, C)
    a.part(mb, name="tower")
    # lantern + topmark
    mb = MB()
    mb.lathe([(0, 1.28), (0.1, 1.28), (0.12, 1.31), (0.0, 1.31)], 10, B)
    mb.lathe([(0, 1.5), (0.13, 1.5), (0.13, 1.52), (0.06, 1.58), (0.0, 1.6)], 10, B)
    for k in range(4):
        ang = math.radians(45 + 90 * k)
        mb.sweep([Vector((0.112 * math.cos(ang), 0.112 * math.sin(ang), 1.3)),
                  Vector((0.112 * math.cos(ang), 0.112 * math.sin(ang), 1.51))], circle(0.012, 4), B)
    mb.cyl(0.02, 1.58, 1.64, 6, B)
    mb.lathe([(0, 1.63), (0.075, 1.63), (0.0, 1.76)], 8, C)
    a.part(mb, name="lantern")
    mb = MB()
    L_ = 'SKY_Light'
    mb.lathe([(0, 1.3), (0.095, 1.3), (0.1, 1.34), (0.088, 1.36), (0.1, 1.39), (0.088, 1.41), (0.1, 1.44),
              (0.088, 1.46), (0.095, 1.5), (0, 1.5)], 10, L_)
    a.part(mb, name="lamp")
    a.empty("LIGHT_buoy", (0, 0, 1.4))


# --------------------------------------------------------------------------- fountain

@asset("fountain_small", "Props", "p1", ao=dict(ground_z=0.0, dist=0.5, rays=24, strength=0.75, floor=0.45, inset=0.05),
       render=dict(az=35.0, el=26.0))
def fountain_small(a):
    """Small street fountain (1.85 m): octagonal pearl basin with teal tile panels and a brass-lipped rim
    on a deep-sandstone step, rippled teal pool, baluster pedestal with four brass spouts arcing water into
    the pool, a scalloped middle bowl, a top cup and a rising water plume (water arcs/plume in SKY_Glass)."""
    P, D, B, T, G = 'SKY_Pearl', 'SKY_SandstoneDeep', 'SKY_Brass', 'SKY_TealLight', 'SKY_Glass'
    mb = MB()
    mb.lathe([(0, 0), (0.94, 0), (0.94, 0.045), (0.915, 0.065), (0, 0.065)], 8, D, a0=22.5)
    a.part(mb, name="step")
    mb = MB()
    prof = [(0.0, 0.06), (0.86, 0.06), (0.86, 0.1), (0.835, 0.13), (0.835, 0.4), (0.86, 0.425), (0.9, 0.455),
            (0.9, 0.5), (0.875, 0.522), (0.79, 0.522), (0.77, 0.5), (0.77, 0.41), (0.0, 0.41)]
    mb.lathe(prof, 8, P, a0=22.5, mats=[P, P, P, P, P, B, B, P, P, P, P, P])
    a.part(mb, name="basin")
    # teal tile panels on the eight faces
    mb = MB()
    for k in range(8):
        ang = math.radians(45 * k)
        ca, sa = math.cos(ang), math.sin(ang)
        apo = 0.835 * math.cos(math.radians(22.5))
        w = 2 * 0.835 * math.sin(math.radians(22.5)) * 0.72
        o = Vector((apo * ca, apo * sa, 0.265))
        u = Vector((-sa, ca, 0))
        mb.prism_frame(cham_rect(w, 0.2, 0.025), o, u, (0, 0, 1), (ca, sa, 0), -0.003, 0.009, T)
    a.part(mb, name="tiles")
    # pool surface with a ripple ring
    mb = MB()
    mb.lathe([(0, 0.4), (0.78, 0.4), (0.78, 0.442), (0, 0.442)], 16, T)
    ring(mb, 0.36, 0.44, 0.438, 0.452, 16, T, ch=0.006)
    a.part(mb, name="pool")
    # baluster pedestal + middle bowl (scalloped) + top cup
    mb = MB()
    ped = [(0, 0.44), (0.17, 0.44), (0.15, 0.5), (0.1, 0.56), (0.13, 0.66), (0.135, 0.72), (0.1, 0.8), (0.075, 0.86),
           (0.075, 0.93), (0.0, 0.93)]
    mb.lathe(ped, 12, P)
    ring(mb, 0.07, 0.145, 0.7, 0.74, 12, B, ch=0.012)
    a.part(mb, name="pedestal")
    mb = MB()
    lobes, nn = 8, 32
    rings = []
    for (rr, z, amp) in ((0.1, 0.9, 0.0), (0.26, 0.94, 0.25), (0.4, 1.0, 0.5), (0.44, 1.04, 0.6), (0.42, 1.065, 0.6),
                         (0.36, 1.05, 0.5)):
        ring_ = []
        for j in range(nn):
            th = 2 * math.pi * j / nn
            r_ = rr * (1 + 0.08 * amp * math.cos(lobes * th))
            ring_.append((r_ * math.cos(th), r_ * math.sin(th), z))
        rings.append(ring_)
    mb.loft(rings, P)
    mb.lathe([(0, 1.04), (0.37, 1.04), (0.37, 1.056), (0, 1.056)], 16, T)
    a.part(mb, name="bowl")
    mb = MB()
    mb.lathe([(0, 1.04), (0.05, 1.04), (0.045, 1.12), (0.08, 1.16), (0.19, 1.22), (0.2, 1.245), (0.17, 1.25),
              (0.0, 1.235)], 12, P, mats=[P, P, P, P, B, B, T])
    mb.lathe([(0, 1.23), (0.045, 1.23), (0.035, 1.29), (0.0, 1.31)], 8, B)
    a.part(mb, name="cup")
    # brass spouts on the pedestal + water arcs into the pool
    mb = MB()
    mw = MB()
    for k in range(4):
        ang = math.radians(45 + 90 * k)
        c, s = math.cos(ang), math.sin(ang)
        p0 = Vector((0.09 * c, 0.09 * s, 0.66))
        p1 = Vector((0.2 * c, 0.2 * s, 0.67))
        mb.sweep([p0, p1], circle(0.022, 6), B)
        mb.sweep([p1 - (p1 - p0).normalized() * 0.01, p1 + Vector((0.025 * c, 0.025 * s, -0.012))], circle(0.03, 6), B)
        arc = []
        for i in range(7):
            t = i / 6
            r_ = 0.22 + 0.32 * t
            z_ = 0.665 + 0.04 * t - 0.26 * t * t
            arc.append(Vector((r_ * c, r_ * s, z_)))
        mw.sweep(arc, circle(0.018, 5), G, scales=[1.0, 1.0, 1.05, 1.1, 1.15, 1.2, 1.25])
    a.part(mb, name="spouts")
    mw.lathe([(0, 1.27), (0.03, 1.28), (0.045, 1.36), (0.032, 1.44), (0.0, 1.49)], 8, G)
    a.part(mw, name="water")


# --------------------------------------------------------------------------- crates

def crate(mb, size, seed, planks=3):
    """Timber crate (bottom centre at the origin): dark core, planks with gaps on the four sides,
    chamfered corner posts, three lid planks, brass corner brackets."""
    rnd = random.Random(seed)
    s = size
    h = s / 2
    W, K, B = 'SKY_Wood', 'SKY_PalmTrunk', 'SKY_Brass'
    mb.box(-h + 0.03, h - 0.03, -h + 0.03, h - 0.03, 0.02, s - 0.02, K)
    gap = 0.022
    ph = (s - 0.06 - (planks - 1) * gap) / planks
    for side in range(4):
        M = M_rot(90 * side)
        for k in range(planks):
            z0 = 0.03 + k * (ph + gap)
            dz = rnd.uniform(-0.004, 0.004)
            fs = mb.box(-h + 0.055, h - 0.055, -h - 0.004, -h + 0.03, z0 + dz, z0 + ph + dz, W)
            mb.transform(M, fs)
    for (sx, sy) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        c = (sx * (h - 0.032), sy * (h - 0.032))
        mb.prism(cham_rect(0.075, 0.075, 0.016, cx=c[0], cy=c[1]), 0.0, s, W)
    lw = (s - 0.12 - 2 * 0.018) / 3
    for k in range(3):
        x0 = -h + 0.06 + k * (lw + 0.018)
        mb.box(x0, x0 + lw, -h + 0.04, h - 0.04, s - 0.025, s + 0.012, W)
    for (sx, sy) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        xa, xb = sorted((sx * (h + 0.012), sx * (h - 0.09)))
        ya, yb = sorted((sy * (h + 0.012), sy * (h - 0.09)))
        for (za, zb) in ((-0.002, 0.075), (s - 0.075, s + 0.018)):
            mb.box(xa, xb, ya, yb, za, zb, B)


@asset("crate_stack", "Props", "p1", ao=dict(ground_z=0.0, dist=0.5, rays=24, strength=0.75, floor=0.45, inset=0.05),
       render=dict(az=35.0, el=22.0))
def crate_stack(a):
    """Three timber crates (0.8 / 0.8 / 0.72 m): planks with gaps over a dark core, chamfered corner posts,
    lid planks, brass corner brackets, and a rope lashing around the top crate."""
    mb = MB()
    tops = []
    for (x, y, z, rot, size, seed) in ((-0.42, 0.0, 0.0, 0.0, 0.8, 1), (0.42, 0.05, 0.0, 6.0, 0.8, 2),
                                         (0.0, 0.02, 0.812, -8.0, 0.72, 3)):
        before = len(mb.bm.faces)
        crate(mb, size, seed)
        mb.bm.faces.ensure_lookup_table()
        fs = [mb.bm.faces[i] for i in range(before, len(mb.bm.faces))]
        mb.transform(M_tr(x, y, z) @ M_rot(rot), fs)
        tops.append((x, y, z, rot, size))
    a.part(mb, name="crates")
    # rope lashing around the top crate (closed loop at mid height) with a knot
    x, y, z, rot, size = tops[2]
    mb = MB()
    h = size / 2 + 0.012
    pts = []
    for (cx, cy, a0) in ((h, -h, -90), (h, h, 0), (-h, h, 90), (-h, -h, 180)):
        for j in range(4):
            ang = math.radians(a0 + 90 * j / 3)
            pts.append(Vector((cx - math.copysign(0.03, cx) + 0.03 * math.cos(ang),
                               cy - math.copysign(0.03, cy) + 0.03 * math.sin(ang), size * 0.55)))
    pts.append(pts[0] + (pts[1] - pts[0]) * 0.5)
    fs = mb.sweep(pts, circle(0.016, 5), 'SKY_Sandstone')
    knot = Vector((0.0, -h - 0.01, size * 0.55))
    fs += mb.sphere(0.035, 6, 3, 'SKY_Sandstone', c=tuple(knot))
    fs += mb.sweep([knot, knot + Vector((0.05, -0.02, -0.18))], circle(0.014, 5), 'SKY_Sandstone')
    mb.transform(M_tr(x, y, z) @ M_rot(rot))
    a.part(mb, name="rope")
