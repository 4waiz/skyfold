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


# ============================================================================ lamps
def lamp_round(part, center, normal, R, body=PEARL, bezel=BRASS, refl=METAL, lens=LIGHT,
               gap=INK, segs=20, depth=0.03, up=(0, 0, 1), proud=1.0, rings=1):
    """Round lamp: body-coloured housing flange, raised bezel ring, recessed reflector cone and
    a domed lens with `rings` concentric steps. ~300 tris at segs=20."""
    M = frame(center, normal, up)
    s = R / 0.11 * proud
    prof = [(1.28 * R, -depth), (1.28 * R, 0.004 * s), (1.18 * R, 0.014 * s),
            (1.12 * R, 0.023 * s), (1.03 * R, 0.026 * s), (0.95 * R, 0.015 * s),
            (0.66 * R, 0.002 * s), (0.60 * R, 0.008 * s)]
    mats = [body, body, bezel, bezel, bezel, refl, gap]
    if rings:
        prof += [(0.46 * R, 0.017 * s), (0.42 * R, 0.014 * s), (0.36 * R, 0.020 * s)]
        mats += [lens, lens, lens]
    else:
        prof += [(0.36 * R, 0.020 * s)]
        mats += [lens]
    prof += [(0.16 * R, 0.0245 * s), (0.0, 0.025 * s)]
    mats += [lens, lens]
    return lathe_m(part, prof, segs, mats, M=M)


def lamp_rrect(part, center, normal, w, h, r, body=PEARL, bezel=PEARL, lens=CORAL,
               inner=None, depth=0.03, up=(0, 0, 1), nc=3, proud=1.0, ribs=0, rib_mat=None):
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
    rr_lathe(part, w, h, 0.02, prof, mats, M=M, nc=3)
    for sx in (-1, 1):
        p = M @ Vector((sx * (w / 2 - 0.035), 0.0, -0.006))
        n = (M.to_3x3() @ Vector((0, 0, 1))).normalized()
        bolt(part, p, n, 0.0075, 0.005, screw_mat, segs=8, up=M.to_3x3() @ Vector((0, 1, 0)))
    return M


# ============================================================================ wheels
def wheel_hq(R, W, outer=1, seg=40, rim_r=0.62, lugs=18, lug_h=0.010, spokes=5, spoke_w=0.11,
             spoke_d=0.075, spoke_flare=1.35, twist=0.0, disc=True, caliper=True, nuts=5,
             hub_seg=20, tyre=RUBBER, lip=PEARL, barrel=INK, spoke=PEARL, hub=PEARL, cap=BRASS,
             nut=BRASS, disc_mat=METAL, caliper_mat=CORAL, caliper_angle=60.0, grooves=0,
             sidewall_ring=None, lug_skew=0.65, lug_len=0.50, valve=BRASS, spoke_ridge=True):
    """Detailed wheel as a Part at the origin: axle along X, outer face toward +X (mirrored when
    outer < 0). R = tyre radius, W = tyre width. Sizes of the rim parts scale with R.
    lugs: tread blocks per side (chevron pairs; 0 = smooth tread, use grooves= for ribs)."""
    p = C.Part()
    w = W / 2
    rr = rim_r * R
    Rt = R - (lug_h if lugs else 0.0)
    # ---- tyre (open lathe; inner side coarse because it faces the car)
    prof = [(rr - 0.012 * R, -0.80 * w), (0.80 * R, -0.985 * w), (0.935 * R, -0.90 * w),
            (Rt, -0.74 * w)]
    mats = [tyre, tyre, tyre]
    if grooves:
        # circumferential ribs: shallow grooves across the tread
        xs = [-0.74 + 1.48 * (k + 0.5) / (grooves + 1) for k in range(grooves + 1)]
        gpos = [-0.74 + 1.48 * (k + 1) / (grooves + 1) for k in range(grooves)]
        for g in gpos:
            prof += [(Rt, (g - 0.07) * w), (Rt - 0.018 * R, (g - 0.04) * w),
                     (Rt - 0.018 * R, (g + 0.04) * w), (Rt, (g + 0.07) * w)]
            mats += [tyre, tyre, tyre, tyre]
    prof += [(Rt, 0.74 * w), (0.935 * R, 0.90 * w), (0.875 * R, 0.975 * w)]
    mats += [tyre, tyre, tyre]
    if sidewall_ring:
        prof += [(0.80 * R, 0.99 * w), (0.775 * R, 1.005 * w), (0.745 * R, 0.995 * w)]
        mats += [tyre, sidewall_ring, sidewall_ring]
    else:
        prof += [(0.78 * R, 0.99 * w)]
        mats += [tyre]
    prof += [(0.70 * R, 0.955 * w), (rr + 0.012 * R, 0.86 * w), (rr - 0.012 * R, 0.80 * w)]
    mats += [tyre, tyre, tyre]
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
                        vs.append(bm.verts.new(Vector((hh, 0, 0)) + rad * rad_r + tan * tt))
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
           (rr - 0.012 * R, 0.90 * w), (rr - 0.045 * R, 0.80 * w), (rr - 0.058 * R, 0.70 * w),
           (rr - 0.058 * R, -0.55 * w), (0.0, -0.55 * w)]
    lathe_m(p, rim, seg, [lip, lip, lip, lip, barrel, barrel, barrel], axis='X')
    # ---- brake disc + hat
    if disc:
        dr0, dr1 = 0.22 * R, rr - 0.11 * R
        dprof = [(dr1 + 0.004 * R, -0.02 * w), (dr1, 0.07 * w), (dr0, 0.09 * w),
                 (0.17 * R, 0.30 * w), (0.0, 0.32 * w)]
        lathe_m(p, dprof, max(16, seg * 3 // 5), [disc_mat, disc_mat, INK, INK], axis='X')
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
               caps='round', cap_segs=1)
    # ---- spokes (hub -> lip), slightly dished, flared toward the rim
    hub_r = 0.21 * R
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
    hp = [(hub_r * 1.05, 0.70 * w), (hub_r * 1.05, 0.90 * w), (hub_r * 0.93, 1.00 * w),
          (hub_r * 0.62, 1.03 * w), (hub_r * 0.52, 1.06 * w), (hub_r * 0.50, 1.11 * w),
          (hub_r * 0.30, 1.16 * w), (0.0, 1.18 * w)]
    lathe_m(p, hp, hub_seg, [hub, hub, hub, cap, cap, cap, cap], axis='X')
    # ---- lug nuts on the hub face
    for k in range(nuts):
        th = 2 * pi * k / nuts + pi / nuts + pi / 2
        c = Vector((1.02 * w, cos(th) * hub_r * 0.72, sin(th) * hub_r * 0.72))
        bolt(p, c, (1, 0, 0), 0.034 * R, 0.07 * w, nut, segs=6, up=(0, cos(th), sin(th)))
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

    # -- mesh ------------------------------------------------------------------------
    def build(self, part, nu, mat, grooves=(), bands=(), groove_mat=INK, crown=0.006,
              fill=3, cap_bottom=True, phase=0.0, ribs=()):
        """grooves: [(z, depth, half_width)] V-grooves; ribs: [(z0, z1, height)] raised bands
        with steep edges; bands: [(z0, z1, mat)] material by band mid height."""
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
