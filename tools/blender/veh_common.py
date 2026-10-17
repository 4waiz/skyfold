"""SKYFOLD vehicle helpers (courier car, shuttle, ambient cars, aircraft, power cell) built on
chars_common.

Original procedural work for SKYFOLD: The Last Flight (Awaiz Ahmed / Team Kanban).

Geometry conventions (same as chars_common.Part):
  * lathe profiles are (r, h) pairs listed counter-clockwise in the (r, h) half plane
    (axis -> out -> up -> back to the axis) so face normals point outward;
  * swept sections are 2D (side, up) points listed counter-clockwise for outward normals;
  * every helper takes an optional 4x4 `M` placing its local frame in the asset.
"""
import math
import bpy, bmesh
import chars_common as C
from chars_common import Vector, Matrix, Quaternion, radians, sin, cos, pi, sqrt

PEARL, TEAL, CORAL, LIGHT, INK, RUBBER, BRASS, GLASS, GLOW, SAND, METAL = (
    'SKY_Pearl', 'SKY_Teal', 'SKY_Coral', 'SKY_Light', 'SKY_Ink', 'SKY_Rubber', 'SKY_Brass',
    'SKY_Glass', 'SKY_TealGlow', 'SKY_Sandstone', 'SKY_Metal')
IVORY, TEAL_L, GOLD, SAND_D = 'SKY_Ivory', 'SKY_TealLight', 'SKY_Gold', 'SKY_SandstoneDeep'


# ============================================================================ small math
def frame(center, normal, up=(0, 0, 1)):
    """4x4 matrix with origin `center`, local Z = normal, local Y = `up` projected."""
    z = Vector(normal).normalized()
    u = Vector(up)
    y = u - z * u.dot(z)
    if y.length < 1e-6:
        alt = Vector((0, 1, 0)) if abs(z.y) < 0.9 else Vector((1, 0, 0))
        y = alt - z * alt.dot(z)
    y.normalize()
    x = y.cross(z)
    c = Vector(center)
    return Matrix(((x.x, y.x, z.x, c.x), (x.y, y.y, z.y, c.y), (x.z, y.z, z.z, c.z), (0, 0, 0, 1)))


def rot_x(deg):
    return Matrix.Rotation(radians(deg), 4, 'X')


def rot_y(deg):
    return Matrix.Rotation(radians(deg), 4, 'Y')


def rot_z(deg):
    return Matrix.Rotation(radians(deg), 4, 'Z')


def T(x, y=None, z=None):
    if y is None:
        return Matrix.Translation(Vector(x))
    return Matrix.Translation((x, y, z))


def rounded_rect(w, h, r, n=3):
    """CCW rounded rectangle (4 * (n + 1) points) centred on the origin."""
    pts = []
    for (cx, cy, a0) in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                         (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(n + 1):
            a = radians(a0 + 90 * k / n)
            pts.append((cx + r * cos(a), cy + r * sin(a)))
    return pts


def rrect_dense(w, h, r, n=3, max_seg=0.06):
    """Rounded rectangle (CCW) whose long straight edges are subdivided to <= max_seg."""
    base = rounded_rect(w, h, r, n)
    out = []
    m = len(base)
    for i in range(m):
        a, b = base[i], base[(i + 1) % m]
        out.append(a)
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        k = int(L / max_seg)
        for s in range(1, k + 1):
            t = s / (k + 1)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def pane(part, outline, thick, mat, M=None, deform=None, scales=(1.0, 0.66, 0.33), rim_mat=None):
    """Closed thin pane (glass, screens): concentric scaled copies of the CCW 2D `outline` on
    both faces joined by a rim band. deform(Vector) -> Vector is applied to every vertex."""
    M = M or Matrix.Identity(4)
    cx = sum(p[0] for p in outline) / len(outline)
    cy = sum(p[1] for p in outline) / len(outline)
    rings = []
    for s in reversed(scales):
        rings.append([M @ Vector((cx + (x - cx) * s, cy + (y - cy) * s, -thick / 2))
                      for (x, y) in outline])
    for s in scales:
        rings.append([M @ Vector((cx + (x - cx) * s, cy + (y - cy) * s, thick / 2))
                      for (x, y) in outline])
    c0 = M @ Vector((cx, cy, -thick / 2))
    c1 = M @ Vector((cx, cy, thick / 2))
    vr, fs = part.grid(rings, mat, True, c0, c1)
    if rim_mat:
        k = (len(scales) - 1) * len(outline)
        part.assign(fs[k:k + len(outline)], rim_mat)
    if deform:
        for v in {v for f in fs for v in f.verts}:
            v.co = deform(v.co.copy())
    return vr, fs


def circle2(r, n, phase=0.0, sx=1.0, sy=1.0):
    return [(r * sx * cos(phase + 2 * pi * k / n), r * sy * sin(phase + 2 * pi * k / n))
            for k in range(n)]


def _pchip_slopes(h, d):
    n = len(d) + 1
    m = [0.0] * n
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    return m


def pchip_curve(keys, steps):
    """Monotone (no overshoot) cubic through keys (tuples), parameterised by key index.
    steps[i] = number of output samples in interval i (>= 1). Returns list of tuples."""
    n = len(keys)
    dim = len(keys[0])
    h = [1.0] * (n - 1)
    out = []
    slopes = []
    for c in range(dim):
        ys = [k[c] for k in keys]
        d = [(ys[i + 1] - ys[i]) for i in range(n - 1)]
        slopes.append(_pchip_slopes(h, d))
    for i in range(n - 1):
        for s in range(steps[i]):
            t = s / steps[i]
            h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
            h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
            out.append(tuple(h00 * keys[i][c] + h10 * slopes[c][i] + h01 * keys[i + 1][c] +
                             h11 * slopes[c][i + 1] for c in range(dim)))
    out.append(tuple(keys[-1]))
    return out


def densify(keys, step=0.03):
    """Smooth monotone resampling of loft keys. step: float (interval i gets
    ceil(change / step) samples) or a list with the sample count of every interval."""
    if isinstance(step, (list, tuple)):
        return pchip_curve(keys, [max(1, int(s)) for s in step])
    steps = []
    for a, b in zip(keys, keys[1:]):
        ch = sum(abs(x - y) for x, y in zip(a, b))
        steps.append(max(1, int(math.ceil(ch / step))))
    return pchip_curve(keys, steps)


def ccw(pts):
    """Return the 2D polygon counter-clockwise (shoelace)."""
    a = sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(pts, pts[1:] + pts[:1]))
    return list(pts) if a > 0 else list(pts)[::-1]


# ============================================================================ part utilities
def part_add(dst, src, M=None):
    """Append Part `src` (consumed) into Part `dst`, optionally transformed by M."""
    if M is not None:
        bmesh.ops.transform(src.bm, matrix=M, verts=src.bm.verts)
        if M.determinant() < 0:
            bmesh.ops.reverse_faces(src.bm, faces=src.bm.faces)
    me = bpy.data.meshes.new("tmp_add")
    src.bm.to_mesh(me)
    src.bm.free()
    n0 = len(dst.bm.faces)
    dst.bm.from_mesh(me)
    dst.bm.faces.ensure_lookup_table()
    for k in range(n0, len(dst.bm.faces)):
        f = dst.bm.faces[k]
        f.material_index = dst.mi(src.mats[f.material_index]) if src.mats else 0
    bpy.data.meshes.remove(me)
    return dst


def add_mirror_x(part):
    """Append a copy of everything in `part` mirrored across X = 0 (winding fixed)."""
    bm2 = part.bm.copy()
    bmesh.ops.transform(bm2, matrix=Matrix.Diagonal((-1, 1, 1, 1)), verts=bm2.verts)
    bmesh.ops.reverse_faces(bm2, faces=bm2.faces)
    me = bpy.data.meshes.new("tmp_mirror")
    bm2.to_mesh(me)
    bm2.free()
    part.bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    return part


def tile(part, center, w, d, h, mat, M=None, ch=0.0015, sunk=0.002):
    """Cheap raised tile (10 tris): chamfered top quad + 4 sloped sides, open bottom.
    Local plan w x d, rises h along local +Z from `center` (bottom sunk by `sunk`)."""
    M = (M or Matrix.Identity(4)) @ Matrix.Translation(center)
    bm = part.bm
    b = [bm.verts.new(M @ Vector((x, y, -sunk))) for (x, y) in
         ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2))]
    c = min(ch, w / 3, d / 3)
    t = [bm.verts.new(M @ Vector((x, y, h))) for (x, y) in
         ((-w / 2 + c, -d / 2 + c), (w / 2 - c, -d / 2 + c), (w / 2 - c, d / 2 - c),
          (-w / 2 + c, d / 2 - c))]
    fs = [bm.faces.new(t)]
    for i in range(4):
        j = (i + 1) % 4
        fs.append(bm.faces.new((b[i], b[j], t[j], t[i])))
    part.assign(fs, mat)
    return fs


def lathe_m(part, prof, segs, mats, M=None, axis='Z', phase=0.0):
    """Lathe with one material per profile segment (len(prof) - 1 names, or one name).
    A profile point with r ~ 0 at either end becomes a pole fan."""
    if isinstance(mats, str):
        mats = [mats] * (len(prof) - 1)
    assert len(mats) == len(prof) - 1, (len(mats), len(prof))
    pole0 = 1 if prof[0][0] < 1e-7 else 0
    pole1 = 1 if prof[-1][0] < 1e-7 else 0
    vr, fs = part.lathe(prof, segs, mats[0], matrix=M, phase=phase, axis=axis)
    nb = len(prof) - pole0 - pole1 - 1
    for b in range(nb):
        part.assign(fs[b * segs:(b + 1) * segs], mats[b + pole0])
    k = nb * segs
    if pole0:
        part.assign(fs[k:k + segs], mats[0])
        k += segs
    if pole1:
        part.assign(fs[k:k + segs], mats[-1])
    return vr, fs


def rr_lathe(part, w, d, r, prof, mats, M=None, nc=3, cap=True):
    """'Lathe' of rounded rectangles: prof = [(grow, z), ...] (ring = w x d rounded rect grown
    by `grow`), listed back -> front (outer to inner over the top) for outward normals; the
    last ring is closed with a fan when cap=True. mats: one per profile segment (+1 for cap)."""
    M = M or Matrix.Identity(4)
    if isinstance(mats, str):
        mats = [mats] * len(prof)
    rings = []
    for (g, z) in prof:
        rr = max(r + g, 0.0008)
        ww, dd = max(w + 2 * g, 2 * rr + 1e-4), max(d + 2 * g, 2 * rr + 1e-4)
        rings.append([M @ Vector((x, y, z)) for (x, y) in rounded_rect(ww, dd, rr, nc)])
    npts = len(rings[0])
    c1 = None
    if cap:
        c1 = M @ Vector((0, 0, prof[-1][1]))
    vr, fs = part.grid(rings, mats[0], True, None, c1)
    for b in range(len(prof) - 1):
        part.assign(fs[b * npts:(b + 1) * npts], mats[b])
    if cap:
        part.assign(fs[(len(prof) - 1) * npts:], mats[min(len(mats) - 1, len(prof) - 1)])
    return vr, fs


def slab(part, w, d, h, rp, re, mat, M=None, nc=3, ne=2, top=None, side=None, bottom=None,
         cap_bottom=True):
    """Rounded slab: plan w x d (local XY) with corner radius rp, thickness h along local Z
    (centred), top and bottom edges rounded with radius re. Returns face groups."""
    M = M or Matrix.Identity(4)
    re = max(1e-4, min(re, h / 2 - 1e-4))
    rp = max(rp, re + 0.0012)
    prof = []
    for k in range(ne + 1):
        a = (pi / 2) * k / ne
        prof.append((re - re * sin(a), -h / 2 + re - re * cos(a)))
    for k in range(ne + 1):
        a = (pi / 2) * k / ne
        prof.append((re - re * cos(a), h / 2 - re + re * sin(a)))
    rings = []
    for (ins, z) in prof:
        rings.append([M @ Vector((x, y, z)) for (x, y) in
                      rounded_rect(w - 2 * ins, d - 2 * ins, max(rp - ins, 0.0008), nc)])
    npts = len(rings[0])
    c0 = M @ Vector((0, 0, -h / 2)) if cap_bottom else None
    c1 = M @ Vector((0, 0, h / 2))
    vr, fs = part.grid(rings, mat, True, c0, c1)
    nbands = len(prof) - 1
    g_bot = fs[:ne * npts]
    g_side = fs[ne * npts:(ne + 1) * npts]
    g_top = fs[(ne + 1) * npts:nbands * npts]
    k = nbands * npts
    if cap_bottom:
        g_bot = g_bot + fs[k:k + npts]
        k += npts
    g_top = g_top + fs[k:k + npts]
    if top:
        part.assign(g_top, top)
    if side:
        part.assign(g_side, side)
    if bottom:
        part.assign(g_bot, bottom)
    return dict(top=g_top, side=g_side, bottom=g_bot, all=fs)


def section_rrect(w, h, r, n=2):
    return rounded_rect(w, h, min(r, w / 2 - 1e-4, h / 2 - 1e-4), n)


def sweep(part, path, section, mat, up=None, closed=False, caps=True, scales=None, twist=0.0,
          sec_mats=None, cap_mat=None):
    """Sweep a closed 2D section [(side, up), ...] (CCW for outward normals) along a polyline
    with parallel-transported frames. scales: per-point (sx, sy). sec_mats: material per section
    edge (face column). Returns (rings, faces)."""
    vr, fs = _sweep(part, path, section, mat, up, closed, caps, scales, twist)
    ns = len(section)
    nb = (len(path) if closed else len(path) - 1) * ns
    if sec_mats:
        for i in range(nb):
            m = sec_mats[i % ns]
            if m:
                part.assign([fs[i]], m)
    if cap_mat and caps and not closed:
        part.assign(fs[nb:], cap_mat)
    return vr, fs


def _sweep(part, path, section, mat, up=None, closed=False, caps=True, scales=None, twist=0.0):
    P = [Vector(p) for p in path]
    n = len(P)
    Tn = []
    for i in range(n):
        if closed:
            d = P[(i + 1) % n] - P[(i - 1) % n]
        elif i == 0:
            d = P[1] - P[0]
        elif i == n - 1:
            d = P[-1] - P[-2]
        else:
            d = (P[i + 1] - P[i]).normalized() + (P[i] - P[i - 1]).normalized()
        Tn.append(d.normalized())
    if up is not None:
        u0 = Vector(up)
        u0 = (u0 - Tn[0] * u0.dot(Tn[0])).normalized()
    else:
        _, u0, _ = C._frame_from_normal(Tn[0])
    U = [u0]
    for i in range(1, n):
        u = U[-1] - Tn[i] * U[-1].dot(Tn[i])
        if u.length < 1e-8:
            _, u, _ = C._frame_from_normal(Tn[i])
        U.append(u.normalized())
    rings = []
    for i in range(n):
        t, u = Tn[i], U[i]
        s = u.cross(t).normalized()
        if twist:
            q = Quaternion(t, twist * i / max(1, n - 1))
            s, u = q @ s, q @ u
        sx, sy = scales[i] if scales else (1.0, 1.0)
        rings.append([P[i] + s * (x * sx) + u * (y * sy) for (x, y) in section])
    if closed:
        return part.grid(rings, mat, True, closed_v=True)
    c0 = c1 = None
    if caps:
        c0 = sum(rings[0], Vector()) / len(section)
        c1 = sum(rings[-1], Vector()) / len(section)
    return part.grid(rings, mat, True, c0, c1)


def bolt(part, center, normal, r, h, mat, segs=6, up=(0, 0, 1), sunk=None):
    """Hex bolt head (segs=6) or round screw head (segs>6), base sunk below `center`."""
    sunk = h * 0.6 if sunk is None else sunk
    M = frame(center, normal, up)
    prof = [(r, -sunk), (r, h * 0.62), (r * 0.80, h), (0.0, h)]
    return lathe_m(part, prof, segs, mat, M=M)


def rivet(part, center, normal, r, h, mat, segs=8, up=(0, 0, 1)):
    M = frame(center, normal, up)
    prof = [(r, -h * 0.6), (r, 0.0), (r * 0.78, h * 0.72), (0.0, h)]
    return lathe_m(part, prof, segs, mat, M=M)


def bevel_edges_of(part, faces, width, segs=1):
    """Bevel the boundary edges between `faces` and the rest (bmesh, applied immediately)."""
    fs = set(faces)
    edges = [e for f in faces for e in f.edges
             if any(lf not in fs for lf in e.link_faces)]
    edges = list(set(edges))
    if edges:
        bmesh.ops.bevel(part.bm, geom=edges, offset=width, offset_type='OFFSET', segments=segs,
                        profile=0.5, affect='EDGES', clamp_overlap=True)


# ============================================================================ booleans
def boolean(obj, cutters, op='DIFFERENCE', solver='EXACT', use_self=False):
    """Apply one exact boolean between `obj` and the cutter objects (consumed). New faces take
    the cutter's material (material_mode TRANSFER), so ink cutters make ink arch liners,
    recess walls and seams. Result is re-triangulated (no n-gons)."""
    coll = bpy.data.collections.new("cutters_tmp")
    bpy.context.scene.collection.children.link(coll)
    for c in cutters:
        for uc in list(c.users_collection):
            uc.objects.unlink(c)
        coll.objects.link(c)
    md = obj.modifiers.new("Bool", 'BOOLEAN')
    md.operation = op
    md.operand_type = 'COLLECTION'
    md.collection = coll
    md.solver = solver
    md.material_mode = 'TRANSFER'
    if solver == 'EXACT':
        md.use_self = use_self
    C.apply_modifiers(obj)
    for c in cutters:
        me = c.data
        bpy.data.objects.remove(c)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    bpy.data.collections.remove(coll)
    # clean slivers: merge near-coincident verts, dissolve zero-area faces, re-triangulate
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-5)
    bmesh.ops.dissolve_degenerate(bm, dist=2e-5, edges=bm.edges)
    ng = [f for f in bm.faces if len(f.verts) > 4]
    if ng:
        bmesh.ops.triangulate(bm, faces=ng, quad_method='BEAUTY', ngon_method='BEAUTY')
    bad = [f for f in bm.faces if f.calc_area() < 1e-9]
    if bad:
        bmesh.ops.delete(bm, geom=bad, context='FACES')
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def surface_strip(part, pts, normals, width, lift, mat, closed=False):
    """Flat strip lying `lift` above a surface curve (2 tris per segment): cheap panel seam
    lines and pinstripes. Faces point along the surface normal."""
    P = [Vector(p) for p in pts]
    N = [Vector(n).normalized() for n in normals]
    n = len(P)
    bm = part.bm
    left, right = [], []
    for i in range(n):
        if closed:
            t = P[(i + 1) % n] - P[(i - 1) % n]
        elif i == 0:
            t = P[1] - P[0]
        elif i == n - 1:
            t = P[-1] - P[-2]
        else:
            t = P[i + 1] - P[i - 1]
        t.normalize()
        s = N[i].cross(t).normalized()
        q = P[i] + N[i] * lift
        left.append(bm.verts.new(q + s * (width / 2)))
        right.append(bm.verts.new(q - s * (width / 2)))
    fs = []
    m = n if closed else n - 1
    for i in range(m):
        j = (i + 1) % n
        f = bm.faces.new((right[i], right[j], left[j], left[i]))
        fs.append(f)
    for f in fs:
        f.normal_update()
    # orient along the surface normal
    for f, i in zip(fs, range(m)):
        if f.normal.dot(N[i]) < 0:
            f.normal_flip()
    part.assign(fs, mat)
    return fs


def ribbon(part, pts, normals, width, d_in, d_out, mat, closed=False):
    """Thin closed solid along a surface curve: width across the curve (tangent plane), from
    d_in below to d_out above the surface along each point's normal. Use as a boolean seam
    cutter (or, with d_in = 0, as a raised strip)."""
    P = [Vector(p) for p in pts]
    N = [Vector(n).normalized() for n in normals]
    n = len(P)
    rings = []
    for i in range(n):
        if closed:
            t = P[(i + 1) % n] - P[(i - 1) % n]
        elif i == 0:
            t = P[1] - P[0]
        elif i == n - 1:
            t = P[-1] - P[-2]
        else:
            t = P[i + 1] - P[i - 1]
        t.normalize()
        s = t.cross(N[i]).normalized()
        rings.append([P[i] + s * (width / 2) - N[i] * d_in, P[i] + s * (width / 2) + N[i] * d_out,
                      P[i] - s * (width / 2) + N[i] * d_out, P[i] - s * (width / 2) - N[i] * d_in])
    if closed:
        return part.grid(rings, mat, True, closed_v=True)
    c0 = sum(rings[0], Vector()) / 4
    c1 = sum(rings[-1], Vector()) / 4
    return part.grid(rings, mat, True, c0, c1)


def surface_skin(part, outline, mapfn, offset, mat, scales=(1.0, 0.5)):
    """Single-sided skin over a 2D outline (u, v) hugging a surface at `offset` along its normal
    (window glass seen only from outside). Concentric rings about the centroid + centre fan;
    faces are oriented along the surface normal. Convert with to_temp(recalc=False)."""
    cx = sum(p[0] for p in outline) / len(outline)
    cy = sum(p[1] for p in outline) / len(outline)
    bm = part.bm
    rings, norms = [], []
    for s in scales:
        ring, nr = [], []
        for (u, v) in outline:
            p, n = mapfn(cx + (u - cx) * s, cy + (v - cy) * s)
            ring.append(bm.verts.new(p + n * offset))
            nr.append(n)
        rings.append(ring)
        norms.append(nr)
    pc, nc = mapfn(cx, cy)
    cv = bm.verts.new(pc + nc * offset)
    m = len(outline)
    fs = []
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(m):
            j2 = (j + 1) % m
            fs.append((bm.faces.new((a[j], a[j2], b[j2], b[j])), norms[i][j]))
    for j in range(m):
        fs.append((bm.faces.new((rings[-1][j], rings[-1][(j + 1) % m], cv)), nc))
    out = []
    for f, n in fs:
        f.normal_update()
        if f.normal.dot(n) < 0:
            f.normal_flip()
        out.append(f)
    part.assign(out, mat)
    return out


def surface_patch(part, outline, mapfn, d_in, d_out, mat, scales=(1.0, 0.62, 0.25)):
    """Closed solid hugging a surface over a 2D outline (CCW in (u, v)): mapfn(u, v) ->
    (point, normal). Back face d_in below, front face d_out above the surface. Boolean recess
    cutter (windows, grilles, lamp pockets) or, with negative values, an inset panel."""
    def deform(v):
        p, n = mapfn(v.x, v.y)
        return p + n * (d_out if v.z > 0 else -d_in)
    return pane(part, outline, 2.0, mat, deform=deform, scales=scales)


# ============================================================================ body surfaces
class Shell:
    """Several Pods (e.g. lower body + cabin, already unioned) treated as one surface: lookups
    pick whichever pod is outermost at that height."""

    def __init__(self, *pods):
        self.pods = pods
        self.lo = pods[0]

    def _pods(self, z):
        out = [p for p in self.pods if p.s[0][0] <= z <= p.s[-1][0]]
        if out:
            return out
        return [min(self.pods, key=lambda p: min(abs(z - p.s[0][0]), abs(z - p.s[-1][0])))]

    def flank(self, y, z, side, off=0.0):
        best = None
        for p in self._pods(z):
            q, n = p.flank(y, z, side)
            if best is None or abs(q.x) > abs(best[0].x):
                best = (q, n)
        return best[0] + best[1] * off, best[1]

    def face(self, x, z, face, off=0.0):
        best = None
        for p in self._pods(z):
            q, n = p.face(x, z, face)
            if best is None or q.y * face > best[0].y * face:
                best = (q, n)
        return best[0] + best[1] * off, best[1]

    def top(self, x, y):
        best = None
        for p in self.pods:
            r = p.top(x, y)
            if r is not None and (best is None or r[0].z > best[0].z):
                best = r
        return best


def poly_path(pts, r=0.04, n=3):
    """Rounded polyline corners (open path) -> dense 2D points."""
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[i + 1])
        d1, d2 = (a - b).normalized(), (c - b).normalized()
        rr = min(r, (a - b).length * 0.45, (c - b).length * 0.45)
        p0, p1 = b + d1 * rr, b + d2 * rr
        for k in range(n + 1):
            t = k / n
            q = p0 * (1 - t) ** 2 + b * 2 * t * (1 - t) + p1 * t * t
            out.append((q.x, q.y))
    out.append(pts[-1])
    return out


def poly_loop(pts, r=0.05, n=3):
    """Closed rounded polygon (CCW input) -> dense 2D points."""
    m = len(pts)
    out = []
    for i in range(m):
        a, b, c = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[(i + 1) % m])
        d1, d2 = (a - b).normalized(), (c - b).normalized()
        rr = min(r, (a - b).length * 0.45, (c - b).length * 0.45)
        p0, p1 = b + d1 * rr, b + d2 * rr
        for k in range(n + 1):
            t = k / n
            q = p0 * (1 - t) ** 2 + b * 2 * t * (1 - t) + p1 * t * t
            out.append((q.x, q.y))
    return out


def densify2(pts, step, closed=False):
    out = []
    m = len(pts)
    rng = range(m) if closed else range(m - 1)
    for i in rng:
        a, b = Vector(pts[i]), Vector(pts[(i + 1) % m])
        k = max(1, int((b - a).length / step))
        for s in range(k):
            q = a + (b - a) * (s / k)
            out.append((q.x, q.y))
    if not closed:
        out.append(pts[-1])
    return out


def seam(lines, shell, kind, pts2d, closed=False, side=1, width=0.006, step=0.07, mat=INK,
         lift=0.0015):
    """Panel seam: thin ink strip lying 1.5 mm above a surface curve. kind: 'flank'
    (u=y, v=z), 'back'/'front' (u=x, v=z) or 'top' (u=x, v=y)."""
    d = densify2(pts2d, step, closed)
    P, N = [], []
    for (u, v) in d:
        if kind == 'flank':
            p, n = shell.flank(u, v, side)
        elif kind == 'top':
            p, n = shell.top(u, v)
        else:
            p, n = shell.face(u, v, 1 if kind == 'back' else -1)
        P.append(p)
        N.append(n)
    surface_strip(lines, P, N, width, lift, mat, closed=closed)


def mapper(shell, kind, side=1, off=0.0):
    if kind == 'flank':
        return lambda u, v: shell.flank(u, v, side, off)
    if kind == 'top':
        return lambda u, v: shell.top(u, v)
    f = 1 if kind == 'back' else -1
    return lambda u, v: shell.face(u, v, f, off)


def window(cut, glass, shell, kind, outline, side=1, inset=0.016, depth=0.014, pane_mat=GLASS,
           rings=(1.0, 0.5)):
    """Recess cutter (ink walls) + glass pane set 4-8 mm below the body surface. The cutter
    reaches 8 cm proud of the surface so it always cuts through on curved panels; use more
    `rings` where the surface bends a lot under the window."""
    loop = poly_loop(outline, 0.05, 2)
    loop = densify2(loop, 0.16, closed=True)
    loop = ccw(loop)
    m = mapper(shell, kind, side)
    surface_patch(cut, loop, m, depth, 0.08, INK, scales=rings)
    cx = sum(p[0] for p in loop) / len(loop)
    cy = sum(p[1] for p in loop) / len(loop)
    small = []
    for (u, v) in loop:
        du, dv = u - cx, v - cy
        L = math.hypot(du, dv)
        k = max(0.0, (L - inset)) / L if L > 1e-9 else 0.0
        small.append((cx + du * k, cy + dv * k))
    # glass: single-sided skin 5 mm below the body surface (inside the dark recess)
    surface_skin(glass, small, m, -0.005, pane_mat, scales=rings)


def arches(cut, axle, track, r_arch, z_hub, x_in=0.47):
    for sx in (1, -1):
        for sy in (1, -1):
            M = T(0, sy * axle, z_hub)
            p = C.Part()
            lathe_m(p, [(0.0, x_in), (r_arch, x_in), (r_arch, 1.2), (0.0, 1.2)], 24, INK,
                    M=M, axis='X')
            if sx < 0:
                p.mirror_x()
            part_add(cut, p)


def bumper(part, shell, face, z, sec_w, sec_h, mat, strip_mat=RUBBER, span=0.78, n=8,
           off=0.026):
    base = -pi / 2 if face < 0 else pi / 2
    pod = shell.lo
    ts = [base - span + 2 * span * k / (n - 1) for k in range(n)]
    pts = [pod.point(t, z, off) for t in ts]
    a, b = pts[0], pts[-1]
    ea = a + Vector((-math.copysign(0.025, a.x), -face * 0.06, 0))
    eb = b + Vector((-math.copysign(0.025, b.x), -face * 0.06, 0))
    sec = section_rrect(sec_w, sec_h, min(sec_w, sec_h) * 0.42, 2)
    scl = [(0.78, 0.76)] + [(1.0, 1.0)] * len(pts) + [(0.78, 0.76)]
    sweep(part, [ea] + pts + [eb], sec, mat, up=(0, 0, 1), scales=scl)
    if strip_mat:
        st = [(x - sec_w / 2 - 0.002, y) for (x, y) in
              ccw([(0.008, -0.014), (0.008, 0.014), (0.0, 0.018), (-0.008, 0.014),
                     (-0.008, -0.014), (0.0, -0.018)])]
        sweep(part, pts[1:-1], st, strip_mat, up=(0, 0, 1))


def mirror_unit(part, shell, y, z, side, body_mat, reach=0.10):
    p, n = shell.flank(y, z, side)
    hc = p + Vector((side * reach, 0.02, 0.03))
    part.tube([p - Vector((side * 0.01, 0, 0)), hc - Vector((side * 0.03, 0, 0.01))], 0.010, 6,
              INK, caps='flat')
    M = frame(hc, (-side * 0.25, 1, 0.05), (0, 0, 1))
    g = slab(part, 0.085, 0.060, 0.040, 0.024, 0.014, body_mat, M=M, nc=2, ne=1)
    part.assign(g['top'][-12:], METAL)


def wiper(part, shell, x0, x1, z):
    pts = []
    for k in range(4):
        x = x0 + (x1 - x0) * k / 3
        p, n = shell.face(x, z + 0.012 * k / 3, -1, 0.006)
        pts.append(p)
    sweep(part, pts, section_rrect(0.010, 0.007, 0.002, 1), INK, up=(0, -0.6, 1))



# ============================================================================ lamps
def lamp_round(part, center, normal, R, body=PEARL, bezel=BRASS, refl=METAL, lens=LIGHT,
               gap=INK, segs=20, depth=0.03, up=(0, 0, 1), proud=1.0, rings=1, simple=False):
    """Round lamp: body-coloured housing flange, raised bezel ring, recessed reflector cone and
    a domed lens with an optional concentric step (rings=1). simple=True: small indicator
    (flange, bezel, dark gap, dome lens). ~380 tris at segs=20 with a ring."""
    M = frame(center, normal, up)
    s = R / 0.11 * proud
    if simple:
        prof = [(1.30 * R, -depth), (1.30 * R, 0.004 * s), (1.08 * R, 0.014 * s),
                (0.90 * R, 0.013 * s), (0.82 * R, 0.006 * s), (0.0, 0.016 * s)]
        return lathe_m(part, prof, segs, [body, bezel, bezel, gap, lens], M=M)
    prof = [(1.28 * R, -depth), (1.28 * R, 0.004 * s), (1.16 * R, 0.016 * s),
            (1.10 * R, 0.025 * s), (1.02 * R, 0.025 * s), (0.95 * R, 0.014 * s),
            (0.64 * R, 0.002 * s), (0.58 * R, 0.010 * s)]
    mats = [body, body, bezel, bezel, bezel, refl, gap]
    if rings:
        prof += [(0.40 * R, 0.019 * s), (0.36 * R, 0.0165 * s), (0.31 * R, 0.0215 * s)]
        mats += [lens, lens, lens]
    prof += [(0.0, 0.025 * s)]
    mats += [lens]
    return lathe_m(part, prof, segs, mats, M=M)


def lamp_rrect(part, center, normal, w, h, r, body=PEARL, bezel=PEARL, lens=CORAL,
               inner=None, depth=0.03, up=(0, 0, 1), nc=2, proud=1.0, ribs=0, rib_mat=None):
    """Rounded-rectangle lamp cluster: housing flange, bezel, inset lens; optional horizontal
    lens ribs and an `inner` (w, h, mat) second lens segment at the inner end."""
    M = frame(center, normal, up)
    s = proud
    prof = [(0.016, -depth), (0.016, 0.003 * s), (0.010, 0.012 * s), (0.004, 0.016 * s),
            (-0.002, 0.016 * s), (-0.006, 0.008 * s), (-0.008, 0.006 * s), (-0.012, 0.011 * s)]
    mats = [body, body, bezel, bezel, bezel, INK, lens, lens]
    rr_lathe(part, w, h, r, prof, mats, M=M, nc=nc)
    lz = 0.011 * s
    if ribs:
        for k in range(ribs):
            yk = -h / 2 + 0.02 + (h - 0.04) * (k + 0.5) / ribs
            slab(part, w - 0.04, 0.006, 0.006, 0.0025, 0.0024, rib_mat or lens,
                 M=M @ T(0, yk, lz + 0.001), nc=1, ne=1, cap_bottom=False)
    if inner:
        iw, ih, im, ix = inner
        slab(part, iw, ih, 0.008, min(iw, ih) * 0.3, 0.003, im, M=M @ T(ix, 0, lz + 0.001),
             nc=2, ne=1, cap_bottom=False)
    return M


def plate_recess(part, center, normal, w, h, frame_mat=PEARL, plate_mat=IVORY, screw_mat=BRASS,
                 up=(0, 0, 1), depth=0.03):
    """Blank number-plate recess (no text): raised frame, recessed blank plate, two screws."""
    M = frame(center, normal, up)
    prof = [(0.018, -depth), (0.018, 0.002), (0.014, 0.010), (0.006, 0.012), (0.0, 0.006),
            (-0.002, -0.004), (-0.004, -0.006)]
    mats = [frame_mat, frame_mat, frame_mat, frame_mat, INK, plate_mat, plate_mat]
    rr_lathe(part, w, h, 0.02, prof, mats, M=M, nc=2)
    for sx in (-1, 1):
        p = M @ Vector((sx * (w / 2 - 0.035), 0.0, -0.006))
        n = (M.to_3x3() @ Vector((0, 0, 1))).normalized()
        bolt(part, p, n, 0.0075, 0.005, screw_mat, segs=8, up=M.to_3x3() @ Vector((0, 1, 0)))
    return M


# ============================================================================ wheels
def wheel_hq(R, W, outer=1, seg=32, rim_r=0.62, lugs=14, lug_h=0.010, spokes=5, spoke_w=0.11,
             spoke_d=0.075, spoke_flare=1.35, twist=0.0, disc=True, caliper=True, nuts=5,
             hub_seg=16, tyre=RUBBER, lip=PEARL, barrel=INK, spoke=PEARL, hub=PEARL, cap=BRASS,
             nut=BRASS, disc_mat=METAL, caliper_mat=CORAL, caliper_angle=60.0, grooves=0,
             sidewall_ring=None, lug_skew=0.65, lug_len=0.50, valve=BRASS, spoke_ridge=True,
             inner_simple=True, nut_segs=6, dish=None):
    """Detailed wheel as a Part at the origin: axle along X, outer face toward +X (mirrored when
    outer < 0). R = tyre radius, W = tyre width. Sizes of the rim parts scale with R.
    lugs: tread blocks per side (chevron pairs; 0 = smooth tread, use grooves= for ribs)."""
    p = C.Part()
    w = W / 2
    rr = rim_r * R
    Rt = R - (lug_h if lugs else 0.0)
    # ---- tyre (open lathe; inner side coarse because it faces the car)
    prof = [(rr - 0.012 * R, -0.80 * w), (0.93 * R, -0.93 * w), (Rt, -0.74 * w)]
    mats = [tyre, tyre]
    if inner_simple:
        prof = [(rr - 0.012 * R, -0.80 * w), (Rt, -0.80 * w)]
        mats = [tyre]
    if grooves:
        # circumferential ribs: shallow grooves across the tread
        gpos = [-0.74 + 1.48 * (k + 1) / (grooves + 1) for k in range(grooves)]
        for g in gpos:
            prof += [(Rt, (g - 0.07) * w), (Rt - 0.018 * R, (g - 0.04) * w),
                     (Rt - 0.018 * R, (g + 0.04) * w), (Rt, (g + 0.07) * w)]
            mats += [tyre, tyre, tyre, tyre]
    prof += [(Rt, 0.74 * w), (0.935 * R, 0.90 * w)]
    mats += [tyre, tyre]
    if sidewall_ring:
        prof += [(0.85 * R, 0.985 * w), (0.80 * R, 1.00 * w), (0.76 * R, 0.99 * w)]
        mats += [tyre, sidewall_ring, sidewall_ring]
    else:
        prof += [(0.84 * R, 0.985 * w)]
        mats += [tyre]
    prof += [(0.72 * R, 0.96 * w), (rr - 0.012 * R, 0.80 * w)]
    mats += [tyre, tyre]
    lathe_m(p, prof, seg, mats, axis='X')
    # ---- chevron tread blocks
    if lugs:
        bm = p.bm
        L = 2 * pi * Rt / lugs * lug_len
        ch = 0.0045 * R / 0.32
        for k in range(lugs):
            th = 2 * pi * k / lugs
            rad = Vector((0, cos(th), sin(th)))
            tan = Vector((0, -sin(th), cos(th)))
            for side in (-1, 1):
                h0, h1 = side * 0.06 * w, side * 0.84 * w
                sk = lug_skew * L
                corners = ((h0, -L / 2), (h1, -L / 2 + sk), (h1, L / 2 + sk), (h0, L / 2))
                hc = (h0 + h1) / 2
                tc = sk / 2
                fh = 1.0 - 2 * ch / abs(h1 - h0)
                ft = 1.0 - 2 * ch / L
                vs = []
                for (rad_r, shrink) in ((Rt - 0.012 * R / 0.32, False), (R, True)):
                    for (hh, tt) in corners:
                        if shrink:
                            hh, tt = hc + (hh - hc) * fh, tc + (tt - tc) * ft
                        a = th + tt / rad_r
                        vs.append(bm.verts.new(Vector((hh, cos(a) * rad_r, sin(a) * rad_r))))
                b, t_ = vs[:4], vs[4:]
                quads = [tuple(t_)]
                for i in range(4):
                    j = (i + 1) % 4
                    quads.append((b[i], b[j], t_[j], t_[i]))
                fs = [bm.faces.new(q) for q in quads]
                # orient outward (convex block): compare with block centre
                cen = sum((v.co for v in vs), Vector()) / 8
                for f in fs:
                    f.normal_update()
                    if f.normal.dot(f.calc_center_median() - cen) < 0:
                        f.normal_flip()
                p.assign(fs, tyre)
    # ---- rim: lip + barrel + dark back wall (open toward the tyre side)
    rim = [(rr + 0.006 * R, 0.78 * w), (rr + 0.030 * R, 0.84 * w), (rr + 0.020 * R, 0.91 * w),
           (rr - 0.014 * R, 0.89 * w), (rr - 0.058 * R, 0.72 * w), (rr - 0.058 * R, -0.55 * w),
           (0.0, -0.55 * w)]
    lathe_m(p, rim, seg, [lip, lip, lip, barrel, barrel, barrel], axis='X')
    # ---- brake disc + hat
    if disc:
        dr0, dr1 = 0.22 * R, rr - 0.11 * R
        dprof = [(dr1 + 0.004 * R, -0.02 * w), (dr1, 0.07 * w), (dr0, 0.09 * w),
                 (0.17 * R, 0.30 * w), (0.0, 0.32 * w)]
        lathe_m(p, dprof, max(14, seg // 2), [disc_mat, disc_mat, INK, INK], axis='X')
        if caliper:
            a = radians(caliper_angle)
            rc = dr1 - 0.035 * R
            c = Vector((0.03 * w, cos(pi / 2 + a) * rc, sin(pi / 2 + a) * rc))
            Mc = Matrix.Translation(c) @ Matrix.Rotation(a, 4, 'X')
            p.rbox(Vector((0, 0, 0)), (0.42 * w, 0.30 * R, 0.17 * R), 0.03 * R, 1, caliper_mat,
                   matrix=Mc)
    # ---- valve stem on the lip
    if valve:
        th = radians(-90 + 180.0 / max(spokes, 1))
        rad = Vector((0, cos(th), sin(th)))
        p.tube([Vector((0.70 * w, 0, 0)) + rad * (rr - 0.020 * R),
                Vector((0.86 * w, 0, 0)) + rad * (rr - 0.034 * R)], 0.012 * R, 6, valve,
               caps='flat')
    # ---- solid dished wheel face (aircraft style) instead of spokes
    hub_r = 0.21 * R
    if dish:
        dp = [(rr - 0.040 * R, 0.86 * w), (rr - 0.070 * R, 0.80 * w), (hub_r * 1.6, 0.74 * w),
              (hub_r * 1.08, 0.80 * w)]
        lathe_m(p, dp, seg, [dish, dish, INK], axis='X')
    # ---- spokes (hub -> lip), slightly dished, flared toward the rim
    if spoke_ridge:
        sw, sd = spoke_w * R / 2, spoke_d * R / 2
        sec = [(sw, -sd), (sw, sd * 0.35), (0.0, sd), (-sw, sd * 0.35), (-sw, -sd), (0.0, -sd * 1.1)]
    else:
        sec = section_rrect(spoke_w * R, spoke_d * R, 0.018 * R, 1)
    for k in range(spokes):
        th = 2 * pi * k / spokes + pi / 2
        rad = Vector((0, cos(th), sin(th)))
        path = [Vector((0.93 * w, 0, 0)) + rad * (hub_r * 0.75),
                Vector((0.95 * w, 0, 0)) + rad * (hub_r + (rr - hub_r) * 0.40),
                Vector((0.91 * w, 0, 0)) + rad * (rr - 0.050 * R)]
        sweep(p, path, sec, spoke, up=(1, 0, 0),
              scales=[(1.0, 1.0), (1.0 + (spoke_flare - 1) * 0.45, 0.95), (spoke_flare, 0.85)],
              twist=radians(twist))
    # ---- hub + centre cap
    hp = [(hub_r * 1.05, 0.70 * w), (hub_r * 1.05, 0.92 * w), (hub_r * 0.86, 1.02 * w),
          (hub_r * 0.52, 1.05 * w), (hub_r * 0.44, 1.13 * w), (0.0, 1.18 * w)]
    lathe_m(p, hp, hub_seg, [hub, hub, hub, cap, cap], axis='X')
    # ---- lug nuts on the hub face
    for k in range(nuts):
        th = 2 * pi * k / nuts + pi / nuts + pi / 2
        c = Vector((1.02 * w, cos(th) * hub_r * 0.72, sin(th) * hub_r * 0.72))
        M = frame(c, (1, 0, 0), (0, cos(th), sin(th)))
        lathe_m(p, [(0.034 * R, -0.04 * w), (0.034 * R, 0.045 * w), (0.0, 0.075 * w)], nut_segs,
                [nut, nut], M=M)
    if outer < 0:
        p.mirror_x()
    return p


# ============================================================================ smooth pods
class Pod:
    """Rounded-box loft from horizontal superellipse slices with smooth (monotone cubic)
    interpolation between hand-placed keys, true V-grooves at chosen heights and a crowned,
    ring-filled top. keys: [(z, y_front, y_back, half_width), ...] bottom -> top."""

    def __init__(self, keys, n=3.4, x0=0.0, step=0.025):
        self.keys = keys
        self.n = n
        self.x0 = x0
        self.s = densify(keys, step)

    # -- analytic surface ------------------------------------------------------------
    def section(self, z):
        S = self.s
        if z <= S[0][0]:
            return S[0][1:]
        for (za, ya0, ya1, aa), (zb, yb0, yb1, ab) in zip(S, S[1:]):
            if za <= z <= zb:
                t = (z - za) / (zb - za) if zb > za else 0.0
                return (ya0 + (yb0 - ya0) * t, ya1 + (yb1 - ya1) * t, aa + (ab - aa) * t)
        return S[-1][1:]

    def point(self, t, z, off=0.0):
        y0, y1, a = self.section(z)
        cy, b = (y0 + y1) / 2, (y1 - y0) / 2
        e = 2.0 / self.n
        c, s = cos(t), sin(t)
        p = Vector((self.x0 + a * math.copysign(abs(c) ** e, c),
                    cy + b * math.copysign(abs(s) ** e, s), z))
        if off:
            p = p + self.normal(t, z) * off
        return p

    def normal(self, t, z, eps=1e-3):
        pt = self.point(t + eps, z) - self.point(t - eps, z)
        pz = self.point(t, z + eps) - self.point(t, z - eps)
        n = pt.cross(pz)
        if n.length < 1e-12:
            return Vector((0, 0, 1))
        return n.normalized()

    def t_of_x(self, x, z, face):
        y0, y1, a = self.section(z)
        u = max(-1.0, min(1.0, (x - self.x0) / a))
        c = math.copysign(abs(u) ** (self.n / 2), u)
        t = math.acos(max(-1.0, min(1.0, c)))
        return -t if face < 0 else t

    def t_of_y(self, y, z, side):
        y0, y1, a = self.section(z)
        cy, b = (y0 + y1) / 2, (y1 - y0) / 2
        u = max(-1.0, min(1.0, (y - cy) / b))
        s = math.copysign(abs(u) ** (self.n / 2), u)
        t = math.asin(max(-1.0, min(1.0, s)))
        return t if side > 0 else pi - t

    def corner45(self, z):
        """(x, dy) of the 45-degree point of the rounded corner at height z."""
        y0, y1, a = self.section(z)
        b = (y1 - y0) / 2
        e = 2.0 / self.n
        lo, hi = 1e-5, pi / 2 - 1e-5
        for _ in range(40):
            t = (lo + hi) / 2
            x = a * cos(t) ** e
            y = b * sin(t) ** e
            nx = (x / a) ** (self.n - 1) / a
            ny = (y / b) ** (self.n - 1) / b
            if nx > ny:
                lo = t
            else:
                hi = t
        t = (lo + hi) / 2
        return a * cos(t) ** e, b * sin(t) ** e

    def flank(self, y, z, side, off=0.0):
        """(point, normal) on the +X (side=1) / -X flank at (y, z); y is clamped to the flank
        (never wraps round the corner onto the front or back)."""
        y0, y1, a = self.section(z)
        cy = (y0 + y1) / 2
        dy = self.corner45(z)[1] * 1.12
        y = max(cy - dy, min(cy + dy, y))
        t = self.t_of_y(y, z, side)
        n = self.normal(t, z)
        return self.point(t, z) + n * off, n

    def face(self, x, z, face, off=0.0):
        """(point, normal) on the front (face=-1) / back (face=1) at (x, z); x is clamped to
        the face region."""
        dx = self.corner45(z)[0] * 1.12
        x = max(self.x0 - dx, min(self.x0 + dx, x))
        t = self.t_of_x(x, z, face)
        n = self.normal(t, z)
        return self.point(t, z) + n * off, n

    def inside(self, x, y, z):
        y0, y1, a = self.section(z)
        cy, b = (y0 + y1) / 2, (y1 - y0) / 2
        if a <= 0 or b <= 0:
            return False
        return abs((x - self.x0) / a) ** self.n + abs((y - cy) / b) ** self.n <= 1.0

    def _ztop(self, x, y):
        S = self.s
        idx = None
        for i in range(len(S) - 1, -1, -1):
            if self.inside(x, y, S[i][0]):
                idx = i
                break
        if idx is None:
            return None
        if idx == len(S) - 1:
            y0, y1, a = self.section(S[-1][0])
            cy, b = (y0 + y1) / 2, (y1 - y0) / 2
            r = (abs((x - self.x0) / a) ** self.n + abs((y - cy) / b) ** self.n) ** (1 / self.n)
            return S[-1][0] + getattr(self, 'crown', 0.0) * max(0.0, 1 - r * r)
        lo, hi = S[idx][0], S[idx + 1][0]
        for _ in range(28):
            m = (lo + hi) / 2
            if self.inside(x, y, m):
                lo = m
            else:
                hi = m
        return (lo + hi) / 2

    def top(self, x, y):
        """(point, normal) on the upper surface above (x, y), or None outside the plan."""
        z = self._ztop(x, y)
        if z is None:
            return None
        e = 0.004
        zs = [self._ztop(x + e, y), self._ztop(x - e, y), self._ztop(x, y + e),
              self._ztop(x, y - e)]
        zs = [z if q is None else q for q in zs]
        gx = (zs[0] - zs[1]) / (2 * e)
        gy = (zs[2] - zs[3]) / (2 * e)
        return Vector((x, y, z)), Vector((-gx, -gy, 1)).normalized()

    # -- mesh ------------------------------------------------------------------------
    def build(self, part, nu, mat, grooves=(), bands=(), groove_mat=INK, crown=0.006,
              fill=3, cap_bottom=True, phase=0.0, ribs=(), bottom_mat=None):
        """grooves: [(z, depth, half_width)] V-grooves; ribs: [(z0, z1, height)] raised bands
        with steep edges; bands: [(z0, z1, mat)] material by band mid height."""
        self.crown = crown
        zs = [(sl[0], 0.0) for sl in self.s]
        for (zg, dep, hw) in grooves:
            zs = [(z, i) for (z, i) in zs if abs(z - zg) > hw * 1.6]
            zs += [(zg - hw, 0.0), (zg, dep), (zg + hw, 0.0)]
        for (z0, z1, hh) in ribs:
            e = 0.0016
            zs = [(z, i) for (z, i) in zs if not (z0 - 2 * e < z < z1 + 2 * e)]
            zs += [(z0, 0.0), (z0 + e, -hh), (z1 - e, -hh), (z1, 0.0)]
        zs.sort()
        rings = []
        for (z, ins) in zs:
            y0, y1, a = self.section(z)
            rings.append(C.superellipse_ring(self.x0, (y0 + y1) / 2, a - ins, (y1 - y0) / 2 - ins,
                                             self.n, nu, z, phase))
        # crowned ring fill on top
        ztop = zs[-1][0]
        y0, y1, a = self.section(ztop)
        cy, b = (y0 + y1) / 2, (y1 - y0) / 2
        top_z = []
        for k in range(1, fill + 1):
            sc = 1.0 - k / (fill + 1.0)
            zk = ztop + crown * (1 - sc ** 2)
            rings.append(C.superellipse_ring(self.x0, cy, a * sc, b * sc, self.n, nu, zk, phase))
            top_z.append(zk)
        c1 = Vector((self.x0, cy, ztop + crown))
        c0 = None
        if cap_bottom:
            zb = zs[0][0]
            yb0, yb1, ab = self.section(zb)
            c0 = Vector((self.x0, (yb0 + yb1) / 2, zb))
        vr, fs = part.grid(rings, mat, True, c0, c1)
        zall = [z for (z, i) in zs] + top_z
        ins_all = [i for (z, i) in zs] + [0.0] * len(top_z)
        for bnd in range(len(rings) - 1):
            zm = (zall[bnd] + zall[bnd + 1]) / 2
            m = None
            if ins_all[bnd] > 0 or ins_all[bnd + 1] > 0:
                m = groove_mat
            else:
                for (z0, z1, bm_) in bands:
                    if z0 <= zm <= z1:
                        m = bm_
            if m:
                part.assign(fs[bnd * nu:(bnd + 1) * nu], m)
        if cap_bottom and bottom_mat:
            k = (len(rings) - 1) * nu
            part.assign(fs[k:k + nu], bottom_mat)
        # the top fan takes whatever band covers the top height
        ktop = (len(rings) - 1) * nu + (nu if cap_bottom else 0)
        zt = ztop + crown
        for (z0, z1, bm_) in bands:
            if z0 <= zt <= z1:
                part.assign(fs[ktop:ktop + nu], bm_)
        self.faces = fs
        self.nu = nu
        self.ring_z = zall
        return fs


# ============================================================================ legacy helpers
def lamp(part, center, normal, r, lens_mat, bezel=PEARL, depth=0.05, segs=14, gap=INK):
    """Round lamp: bezel ring + dark gap + slightly domed emissive lens, facing `normal`."""
    n = Vector(normal).normalized()
    M = Matrix.Translation(center) @ n.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    prof = [(0.0, depth * 0.55), (r * 0.55, depth * 0.50), (r * 0.86, depth * 0.38),
            (r * 0.88, depth * 0.30), (r * 1.0, depth * 0.42), (r * 1.18, depth * 0.30),
            (r * 1.20, -depth), (0.0, -depth)]
    vr, fs = part.lathe(prof, segs, lens_mat, matrix=M)
    part.assign(fs[2 * segs:3 * segs], gap)
    part.assign(fs[3 * segs:5 * segs], bezel)
    nb = len(prof) - 3
    part.assign(fs[(nb + 1) * segs:(nb + 2) * segs], INK)
    return fs


def wheel(center, radius, width, outer, seg=16, hub_ratio=0.60, spokes=5, hub_mat=PEARL,
          cap_mat=BRASS):
    """Chunky stylised wheel as a Part: axle along X, outer face toward outer (+1/-1)."""
    p = C.Part()
    r, w = radius, width / 2
    hr = radius * hub_ratio
    tyre = [(hr, -w * 0.86), (r * 0.78, -w), (r * 0.94, -w * 0.97), (r, -w * 0.73),
            (r * 1.006, -w * 0.15), (r * 0.975, 0.0), (r * 1.006, w * 0.15), (r, w * 0.73),
            (r * 0.94, w * 0.97), (r * 0.78, w), (hr, w * 0.86)]
    p.lathe(tyre, seg, RUBBER, axis='X')
    hub = [(0.0, w * 1.03), (hr * 0.23, w * 0.98), (hr * 0.33, w * 0.91), (hr * 0.62, w * 0.77),
           (hr * 0.91, w * 0.83), (hr, w * 0.75), (hr, -w * 0.77), (0.0, -w * 0.77)]
    vr, fs = p.lathe(hub, seg, hub_mat, axis='X')
    p.assign(fs[0:seg], cap_mat)
    p.assign(fs[4 * seg:5 * seg], INK)
    p.assign(fs[(len(hub) - 3) * seg:(len(hub) - 2) * seg], cap_mat)
    p.assign(fs[(len(hub) - 2) * seg:(len(hub) - 1) * seg], INK)
    for k in range(spokes):
        a = 2 * pi * k / spokes
        M = Matrix.Rotation(a, 4, 'X') @ Matrix.Translation((w * 0.83, 0.0, hr * 0.61))
        p.box(Vector((0, 0, 0)), (w * 0.15, hr * 0.15, hr * 0.57), hub_mat, matrix=M)
    if outer < 0:
        p.mirror_x()
    p.transform(p.bm.verts, Matrix.Translation(center))
    return p


def wheel_lite(center, radius, width, outer, seg=12, hub_ratio=0.58, hub_mat=PEARL,
               cap_mat=PEARL):
    """Lighter wheel for ambient traffic (~250 tris)."""
    p = C.Part()
    r, w = radius, width / 2
    hr = radius * hub_ratio
    tyre = [(hr, -w * 0.85), (r * 0.86, -w), (r, -w * 0.62), (r, w * 0.62), (r * 0.86, w),
            (hr, w * 0.85)]
    p.lathe(tyre, seg, RUBBER, axis='X')
    hub = [(0.0, w * 1.0), (hr * 0.30, w * 0.95), (hr * 0.86, w * 0.80), (hr, w * 0.72),
           (hr, -w * 0.75), (0.0, -w * 0.75)]
    vr, fs = p.lathe(hub, seg, hub_mat, axis='X')
    p.assign(fs[0:seg], cap_mat)
    p.assign(fs[3 * seg:4 * seg], INK)
    p.assign(fs[(len(hub) - 3) * seg:(len(hub) - 2) * seg], cap_mat)
    p.assign(fs[(len(hub) - 2) * seg:(len(hub) - 1) * seg], INK)
    if outer < 0:
        p.mirror_x()
    p.transform(p.bm.verts, Matrix.Translation(center))
    return p


class LoftBody:
    """Horizontal-slice superellipse loft with an analytic surface for conformal panels.
    slices: [(z, y_front, y_back, half_width)] bottom -> top."""

    def __init__(self, slices, n=4.0, x0=0.0):
        self.s = slices
        self.n = n
        self.x0 = x0

    def build(self, part, nu, mat, band_mats=None, cap0=True, cap1=True):
        rings = []
        for (z, y0, y1, a) in self.s:
            rings.append(C.superellipse_ring(self.x0, (y0 + y1) / 2, a, (y1 - y0) / 2, self.n,
                                             nu, z))
        c0 = sum(rings[0], Vector()) / nu if cap0 else None
        c1 = sum(rings[-1], Vector()) / nu if cap1 else None
        vr, faces = part.grid(rings, mat, True, c0, c1)
        if band_mats:
            for b, m in band_mats.items():
                part.assign(faces[b * nu:(b + 1) * nu], m)
        self.faces = faces
        return faces

    def section(self, z):
        S = self.s
        if z <= S[0][0]:
            return S[0][1:]
        for (za, ya0, ya1, aa), (zb, yb0, yb1, ab) in zip(S, S[1:]):
            if za <= z <= zb:
                t = (z - za) / (zb - za) if zb > za else 0.0
                return (ya0 + (yb0 - ya0) * t, ya1 + (yb1 - ya1) * t, aa + (ab - aa) * t)
        return S[-1][1:]

    def point(self, t, z, off=0.0):
        """Surface point at superellipse angle t (0 = +X side, -pi/2 = front, pi/2 = back)."""
        y0, y1, a = self.section(z)
        cy, b = (y0 + y1) / 2, (y1 - y0) / 2
        e = 2.0 / self.n
        c, s = cos(t), sin(t)
        x = a * math.copysign(abs(c) ** e, c)
        y = b * math.copysign(abs(s) ** e, s)
        p = Vector((self.x0 + x, cy + y, z))
        if off:
            nx = (abs(x / a) ** (self.n - 1)) * math.copysign(1, x) / a if a else 0
            ny = (abs(y / b) ** (self.n - 1)) * math.copysign(1, y) / b if b else 0
            nn = Vector((nx, ny, 0.0))
            if nn.length > 1e-9:
                p += nn.normalized() * off
        return p

    def t_of_y(self, y, z, side):
        y0, y1, a = self.section(z)
        cy, b = (y0 + y1) / 2, (y1 - y0) / 2
        u = max(-1.0, min(1.0, (y - cy) / b))
        s = math.copysign(abs(u) ** (self.n / 2), u)
        t = math.asin(max(-1.0, min(1.0, s)))
        return t if side > 0 else pi - t

    def t_of_x(self, x, z, face):
        y0, y1, a = self.section(z)
        u = max(-1.0, min(1.0, (x - self.x0) / a))
        c = math.copysign(abs(u) ** (self.n / 2), u)
        t = math.acos(max(-1.0, min(1.0, c)))
        return -t if face < 0 else t

    def corner45(self, z):
        y0, y1, a = self.section(z)
        b = (y1 - y0) / 2
        e = 2.0 / self.n
        lo, hi = 1e-5, pi / 2 - 1e-5
        for _ in range(40):
            t = (lo + hi) / 2
            x = a * cos(t) ** e
            y = b * sin(t) ** e
            nx = (x / a) ** (self.n - 1) / a
            ny = (y / b) ** (self.n - 1) / b
            if nx > ny:
                lo = t
            else:
                hi = t
        t = (lo + hi) / 2
        return a * cos(t) ** e, b * sin(t) ** e

    def panel_side(self, part, side, ya, yb, za, zb, mat, off=0.008, nt=6, nz=3, margin=0.03):
        rows = []
        for j in range(nz + 1):
            z = za + (zb - za) * j / nz
            y0, y1, a = self.section(z)
            cy = (y0 + y1) / 2
            x45, dy = self.corner45(z)
            ra, rb = max(ya, cy - dy + margin), min(yb, cy + dy - margin)
            row = [self.point(self.t_of_y(ra + (rb - ra) * i / nt, z, side), z, off)
                   for i in range(nt + 1)]
            rows.append(row if side > 0 else row[::-1])
        return self._sheet(part, rows, mat)

    def panel_end(self, part, face, xa, xb, za, zb, mat, off=0.008, nt=6, nz=3, margin=0.03):
        rows = []
        for j in range(nz + 1):
            z = za + (zb - za) * j / nz
            x45, dy = self.corner45(z)
            ra = max(xa, self.x0 - x45 + margin)
            rb = min(xb, self.x0 + x45 - margin)
            row = [self.point(self.t_of_x(ra + (rb - ra) * i / nt, z, face), z, off)
                   for i in range(nt + 1)]
            rows.append(row if face < 0 else row[::-1])
        return self._sheet(part, rows, mat)

    @staticmethod
    def _sheet(part, rows, mat):
        bm = part.bm
        vr = [[bm.verts.new(p) for p in row] for row in rows]
        faces = []
        for j in range(len(vr) - 1):
            for i in range(len(vr[0]) - 1):
                faces.append(bm.faces.new((vr[j][i], vr[j][i + 1], vr[j + 1][i + 1], vr[j + 1][i])))
        part.assign(faces, mat)
        return faces
