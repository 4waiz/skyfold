"""SKYFOLD environment kit - nature: date palms, shrubs, bougainvillea (detail pass).

Pivot at ground centre. Stylised date palms: a trunk of stacked leaf-base cups that spiral by half a
step per ring (zig-zag "boot" pattern), a pineapple crown, pinnate fronds (tapered rachis plus folded
leaflets), a dried frond skirt, young spear leaves and date bunches. Every leaf is a small closed
4-tri wedge, so foliage renders from both sides with back-face culling and stays manifold.
Shrubs are domes of small lumpy leaf florets (deep crevices read as dense foliage); bougainvillea
adds woody canes and papery magenta bract rosettes.

Helpers here (leaf_tet, leaf_out, ico_blob, floret_layout, bract_cluster, palm) are reused by env_props
(planter) and env_buildings (courtyard palm: keep palm()'s keyword signature compatible).
"""
from env_common import *

NAT_AO = dict(ground_z=0.0, dist=1.2, rays=24, strength=0.7, floor=0.5, inset=0.08)
NAT_RENDER = dict(az=35.0, el=18.0)
UP = Vector((0.0, 0.0, 1.0))


def bezier(p0, p1, p2, n):
    out = []
    for i in range(n + 1):
        t = i / n
        out.append(p0 * (1 - t) ** 2 + p1 * 2 * t * (1 - t) + p2 * t * t)
    return out


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


# --------------------------------------------------------------------------- leaves

def leaf_tet(mb, base, d, wdir, nrm, length, width, fold, mat, mid=0.36):
    """One leaf as a closed 4-tri wedge: diamond outline from base to tip; the two side corners sit
    `fold` along nrm (negative = arched blade with a raised midrib, positive = cupped)."""
    B = Vector(base)
    T = B + d * length
    M = B + d * (length * mid)
    L = M + wdir * (width * 0.5) + nrm * fold
    R = M - wdir * (width * 0.5) + nrm * fold
    vb, vt, vl, vr = mb.v(B), mb.v(T), mb.v(L), mb.v(R)
    fs = [mb.f([vb, vt, vl], mat), mb.f([vb, vr, vt], mat), mb.f([vb, vl, vr], mat), mb.f([vl, vt, vr], mat)]
    mb._recalc(fs)
    return fs


def leaf_out(mb, base, d, length, width, mat, fold=None, up=UP, mid=0.36):
    """Leaf pointing along d with its blade as level as possible (width axis horizontal-ish)."""
    d = Vector(d).normalized()
    w = d.cross(up)
    if w.length < 1e-4:
        w = d.orthogonal()
    w.normalize()
    n = w.cross(d).normalized()
    if n.dot(up) < 0:
        n = -n
    return leaf_tet(mb, base, d, w, n, length, width, -width * 0.2 if fold is None else fold, mat, mid)


def ico_blob(mb, c, r, mat, level=3, sz=1.0, noise=0.16, seed=0, flat_z=None, lobes=7, sharp=4.0):
    """Lumpy leaf mass: an icosphere (level 1 = 20 tris, 2 = 80, 3 = 320) with soft radial bulges.
    Returns the new BMVerts (for placing leaves exactly on the surface)."""
    tmp = bmesh.new()
    bmesh.ops.create_icosphere(tmp, subdivisions=level, radius=1.0)
    rnd = random.Random(seed)
    L = [(Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.35, 1.0))).normalized(),
          rnd.uniform(0.55, 1.0)) for _ in range(lobes)]
    c = Vector(c)
    vm = {}
    for v in tmp.verts:
        d = v.co.normalized()
        k = 1.0
        for (ld, amp) in L:
            k += noise * amp * (max(0.0, d.dot(ld)) ** sharp - 0.12)
        p = Vector((c.x + d.x * r * k, c.y + d.y * r * k, c.z + d.z * r * k * sz))
        if flat_z is not None and p.z < flat_z:
            p.z = flat_z + (p.z - flat_z) * 0.22
        vm[v] = mb.v(p)
    for f in tmp.faces:
        mb.f([vm[v] for v in f.verts], mat)
    out = list(vm.values())
    tmp.free()
    return out


def bract_cluster(mb, c, nd, size, seed, mat='SKY_Flower', petals=4, open_=0.5):
    """Bougainvillea-style bract head: a rosette of papery petals opening around nd."""
    rnd = random.Random(seed)
    nd = Vector(nd).normalized()
    t = nd.orthogonal().normalized()
    b = nd.cross(t)
    a0 = rnd.uniform(0, 2 * math.pi)
    for k in range(petals):
        a = a0 + 2 * math.pi * k / petals + rnd.uniform(-0.25, 0.25)
        sd = (t * math.cos(a) + b * math.sin(a))
        d = (sd * 0.82 + nd * open_).normalized()
        wd = nd.cross(d).normalized()
        n2 = d.cross(wd).normalized()
        if n2.dot(nd) < 0:
            n2 = -n2
        leaf_tet(mb, c - nd * size * 0.12, d, wd, n2, size * rnd.uniform(0.85, 1.1), size * 0.9, size * 0.14, mat,
                 mid=0.5)


# --------------------------------------------------------------------------- palm parts

def _band(mb, A, B, mat, shift):
    """Connect ring A to ring B (same count). shift=0 -> quads; shift=1 -> B[k] lies between A[k] and
    A[k+1] (half-step rotated ring) -> zig-zag triangles."""
    n = len(A)
    fs = []
    for k in range(n):
        k2 = (k + 1) % n
        if shift == 0:
            fs.append(mb.f([A[k], A[k2], B[k2], B[k]], mat))
        else:
            fs.append(mb.f([A[k], A[k2], B[k]], mat))
            fs.append(mb.f([A[k2], B[k2], B[k]], mat))
    return fs


def palm_trunk(mb, base, ctrl, top, r0, r1, n=8, seg_h=0.3, seed=0, mat='SKY_PalmTrunk', cup=0.15, segs=None,
               crown_mat='SKY_PalmLeaf'):
    """Trunk of stacked leaf-base cups. Each cup flares wider at its top; consecutive cups are rotated by
    half a step so the ledges zig-zag into a spiral of diamond boots. Ends in a pineapple crown bulb and a
    low green cap. Returns (top point, top tangent, crown height)."""
    rnd = random.Random(seed)
    base, ctrl, top = Vector(base), Vector(ctrl), Vector(top)
    length = (top - base).length
    S = segs or max(4, int(round(length / seg_h)))

    def P(t):
        return base * (1 - t) ** 2 + ctrl * 2 * t * (1 - t) + top * t * t

    def D(t):
        return ((ctrl - base) * 2 * (1 - t) + (top - ctrl) * 2 * t).normalized()

    def ring(t, r, off, zoff=0.0, tips=0.0, flat=False):
        c = P(t) + Vector((0, 0, zoff))
        T = UP if flat else D(t)
        e1 = Vector((1, 0, 0)) - T * T.x
        e1.normalize()
        e2 = T.cross(e1)
        out = []
        for k in range(n):
            a_ = off + 2 * math.pi * k / n
            f = 1.0
            if tips and not (n % 2 and k == n - 1):
                f = 1.0 + tips if k % 2 == 0 else 1.0 - tips * 0.4
            out.append(mb.v(c + (e1 * math.cos(a_) + e2 * math.sin(a_)) * r * f))
        return out

    def R(t):
        flare = 1.0 + 0.26 * (1.0 - smoothstep(0.0, 0.26, t)) ** 1.6
        return lerp(r0, r1, t) * flare

    step = math.pi / n
    rings = []          # (verts, offset_index)
    jit = rnd.uniform(0, 2 * math.pi)
    # root ring at the ground, then the cups: a lit zig-zag shoulder (30 %) rising into a shaded,
    # outward-flaring boot wall (70 %)
    rings.append((ring(0.0, R(0.0), jit, flat=True), 0))
    for s in range(S):
        t0, t1 = s / S, (s + 1) / S
        c = cup * (0.1 + 0.9 * smoothstep(0.1, 0.6, t0))
        rm = R((t0 + t1) / 2)
        off = jit + s * step
        rings.append((ring(min(t0 + 0.32 / S, 1.0), rm * (1.0 - c), off), s))
        rings.append((ring(t1, rm * (1.0 + c * 0.45), off, tips=c * 0.7), s))
    fs = []
    for i in range(len(rings) - 1):
        (A, sa), (B, sb) = rings[i], rings[i + 1]
        fs += _band(mb, A, B, mat, 1 if sb != sa else 0)
    # bottom cap
    fs.append(mb.f(list(reversed(rings[0][0])), mat))
    # pineapple crown: three fatter cups, then a green dome cap
    T1 = D(1.0)
    last, ls = rings[-1]
    hk = min(1.0, r1 / 0.24)
    cr = [(1.18, 1.32, 0.16 * hk), (1.30, 1.42, 0.17 * hk), (1.22, 1.30, 0.15 * hk)]
    z = 0.0
    prev, prev_s = last, ls
    for j, (lo_k, hi_k, h) in enumerate(cr):
        s_idx = S + j
        off = jit + s_idx * step
        lo = ring(1.0, r1 * lo_k * 0.9, off, z + 0.03)
        fs += _band(mb, prev, lo, mat, 1)
        hi = ring(1.0, r1 * hi_k, off, z + h, tips=0.12)
        fs += _band(mb, lo, hi, mat, 0)
        prev, prev_s = hi, s_idx
        z += h
    cap0 = ring(1.0, r1 * 0.95, jit + (S + len(cr)) * step, z + 0.05)
    fs += _band(mb, prev, cap0, mat, 1)
    cap1 = ring(1.0, r1 * 0.5, jit + (S + len(cr)) * step, z + 0.16)
    fs += _band(mb, cap0, cap1, crown_mat, 0)
    apex = mb.v(P(1.0) + Vector((0, 0, z + 0.26)))
    for k in range(n):
        fs.append(mb.f([cap1[k], cap1[(k + 1) % n], apex], crown_mat))
    mb._recalc(fs)
    return P(1.0), T1, z


def frond(mb, root, azim, elev, length, droop, seed, n_seg=7, twist=0.0, n_leaf=10, blade=0.62, leaf_w=0.09,
          fwd=28.0, vang=24.0, start=0.2, rachis_w=0.07, leaf_mat='SKY_PalmLeaf', rachis_mat='SKY_PalmLeaf',
          spines=2, lateral=0.0, tip=True, leaf_droop=0.0, fold=0.2):
    """Pinnate date-palm frond: tapered flat-topped rachis arching down, V-set folded leaflets that
    angle toward the tip (short spines near the base, longest leaflets in the middle third)."""
    rnd = random.Random(seed)
    h = Vector((math.cos(azim), math.sin(azim), 0.0))
    side_ax = Vector((-h.y, h.x, 0.0))
    cur = (h * math.cos(elev) + UP * math.sin(elev)).normalized()
    pts = [Vector(root)]
    step = length / n_seg
    for s in range(n_seg):
        pts.append(pts[-1] + cur * step)
        t = (s + 1) / n_seg
        ang = math.radians(droop) * (0.3 + 1.4 * t) / n_seg
        cur = (Matrix.Rotation(ang, 3, side_ax) @ cur).normalized()
        if lateral:
            cur = (Matrix.Rotation(math.radians(lateral) / n_seg, 3, UP) @ cur).normalized()
    n = len(pts)
    frames = []
    for i in range(n):
        if i == 0:
            T = (pts[1] - pts[0]).normalized()
        elif i == n - 1:
            T = (pts[-1] - pts[-2]).normalized()
        else:
            T = (pts[i + 1] - pts[i - 1]).normalized()
        Sv = T.cross(UP)
        Sv = Sv.normalized() if Sv.length > 1e-3 else -side_ax
        Sv = (Sv - T * Sv.dot(T)).normalized()
        U = Sv.cross(T).normalized()
        tw = math.radians(twist) * (i / (n - 1)) ** 1.5
        Sv, U = Sv * math.cos(tw) + U * math.sin(tw), U * math.cos(tw) - Sv * math.sin(tw)
        frames.append((T, Sv, U))
    # rachis
    rings = []
    for i, p in enumerate(pts):
        t = i / (n - 1)
        T, Sv, U = frames[i]
        w = rachis_w * (1.0 - 0.8 * t)
        rings.append([p + Sv * (w / 2), p - Sv * (w / 2), p - U * (w * 0.7)])
    mb.loft(rings, rachis_mat)

    def at(t):
        x = t * (n - 1)
        i = min(int(x), n - 2)
        f = x - i
        p = pts[i].lerp(pts[i + 1], f)
        T = frames[i][0].lerp(frames[i + 1][0], f).normalized()
        Sv = frames[i][1].lerp(frames[i + 1][1], f).normalized()
        U = frames[i][2].lerp(frames[i + 1][2], f).normalized()
        return p, T, Sv, U

    def leaflet(t, sg, Ll, wl, fw, va, droop_=0.0):
        p, T, Sv, U = at(t)
        w_r = rachis_w * (1.0 - 0.8 * t)
        f_ = math.radians(fw)
        v_ = math.radians(va)
        d = (Sv * sg * math.cos(f_) + T * math.sin(f_)).normalized()
        d = (d * math.cos(v_) + U * math.sin(v_) - UP * droop_).normalized()
        wd = T - d * T.dot(d)
        wd = wd.normalized() if wd.length > 1e-4 else U.cross(d).normalized()
        nr = d.cross(wd).normalized()
        if nr.dot(U) < 0:
            nr = -nr
        base = p + Sv * sg * (w_r * 0.3) - U * (w_r * 0.12)
        leaf_tet(mb, base, d, wd, nr, Ll, wl, -wl * fold, leaf_mat)

    # spines near the base
    for j in range(spines):
        t = 0.07 + (start - 0.07) * (j + 0.5) / max(1, spines)
        for sg in (1, -1):
            leaflet(t, sg, 0.1 + 0.05 * j, max(0.016, leaf_w * 0.22), fwd + 18, vang + 10)
    for j in range(n_leaf):
        tt = (j + 0.5) / n_leaf
        t = start + (1.0 - start) * tt * 0.97
        shape = math.sin(math.pi * (0.1 + 0.9 * tt)) ** 0.65
        for sg in (1, -1):
            Ll = blade * (0.3 + 0.7 * shape) * rnd.uniform(0.9, 1.07)
            wl = leaf_w * (0.62 + 0.38 * shape) * rnd.uniform(0.92, 1.05)
            leaflet(t, sg, Ll, wl, fwd + 14 * tt + rnd.uniform(-4, 4), vang * (1.0 - 0.45 * tt) + rnd.uniform(-5, 5),
                    leaf_droop * tt)
    if tip:
        p, T, Sv, U = at(1.0)
        leaf_tet(mb, p - T * 0.03, T, Sv, U, blade * 0.42, leaf_w * 0.8, -leaf_w * 0.8 * fold, leaf_mat)
    return pts


def date_bunch(mbs, mbd, root, out, seed, n_dates=9, drop=0.75, reach=0.4, r=0.075):
    rnd = random.Random(seed)
    h = Vector((out.x, out.y, 0.0)).normalized()
    p0 = Vector(root)
    p1 = p0 + h * reach * 0.9 + Vector((0, 0, 0.06))
    p2 = p0 + h * reach * 1.1 + Vector((0, 0, -drop))
    path = bezier(p0, p1, p2, 5)
    mbs.sweep(path, circle(0.024, 5), 'SKY_PalmTrunk', scales=[1.0, 0.92, 0.84, 0.76, 0.68, 0.6])
    a_ = path[-3]
    b_ = path[-1] + Vector((0, 0, -0.12))
    for i in range(n_dates):
        f = (i + 0.5) / n_dates
        c = a_.lerp(b_, f)
        ang = i * 2.4 + rnd.uniform(-0.3, 0.3)
        rad = r * (1.15 + 0.5 * math.sin(math.pi * f))
        c = c + Vector((math.cos(ang) * rad, math.sin(ang) * rad, rnd.uniform(-0.02, 0.02)))
        ico_blob(mbd, c, r * rnd.uniform(0.9, 1.08), 'SKY_Terracotta', level=1, sz=1.3, noise=0.0, seed=i)


def palm(a, x=0.0, y=0.0, z=0.0, height=8.0, lean=(0.0, 0.0), fronds=14, frond_len=3.3, r0=0.36, r1=0.25,
         seed=1, target=None, dates=True, frond_seg=7, trunk_seg=None, sides=8, crown_tilt=0.0, blade=None,
         skirt=None, spears=None, n_leaf=None, leaf_w=None, seg_h=0.3):
    """Stylised date palm at (x, y, z). Keyword-compatible with the first-pass signature (env_buildings)."""
    rnd = random.Random(seed)
    base = Vector((x, y, z - 0.03))
    top = Vector((x + lean[0], y + lean[1], z + height))
    ctrl = Vector((x + lean[0] * 0.12, y + lean[1] * 0.12, z + height * 0.55))
    scale = frond_len / 3.3
    blade = blade if blade is not None else 0.8 * scale ** 0.8
    n_leaf = n_leaf if n_leaf is not None else max(7, int(round(13 * min(1.0, scale ** 0.5))))
    leaf_w = leaf_w if leaf_w is not None else 0.2 * scale ** 0.6
    skirt = skirt if skirt is not None else max(3, fronds // 4)
    spears = spears if spears is not None else 2
    mbt = MB()
    ptop, _, zc = palm_trunk(mbt, base, ctrl, top, r0, r1, n=sides, seg_h=seg_h, seed=seed, segs=trunk_seg)
    a.part(mbt, name="trunk", target=target)
    lean_v = Vector((lean[0], lean[1], 0.0))
    lean_az = math.atan2(lean[1], lean[0]) if lean_v.length > 1e-4 else 0.0
    lean_k = min(1.0, lean_v.length / max(0.5, height * 0.2))
    mbl = MB()
    golden = math.radians(137.508)
    for k in range(fronds):
        tier = k / max(1, fronds - 1)
        az = k * golden + rnd.uniform(-0.12, 0.12) + seed
        tilt = 10.0 * lean_k * math.cos(az - lean_az) + crown_tilt
        el = math.radians(lerp(41, -16, tier) + tilt + rnd.uniform(-5, 5))
        ln = frond_len * lerp(0.8, 1.0, min(1.0, tier * 1.6)) * rnd.uniform(0.93, 1.05)
        root = ptop + Vector((math.cos(az), math.sin(az), 0)) * r1 * 0.75 + Vector((0, 0, zc * lerp(0.95, 0.35, tier)))
        frond(mbl, root, az, el, ln, droop=lerp(34, 62, tier) + rnd.uniform(-6, 6), seed=seed * 131 + k,
              n_seg=frond_seg, twist=rnd.uniform(-18, 18), n_leaf=n_leaf, blade=blade, leaf_w=leaf_w,
              rachis_w=0.075 * scale ** 0.7, lateral=rnd.uniform(-10, 10))
    # dried skirt fronds hanging under the crown
    for k in range(skirt):
        az = (k + 0.5) * 2 * math.pi / skirt + rnd.uniform(-0.3, 0.3) + seed * 0.7
        root = ptop + Vector((math.cos(az), math.sin(az), 0)) * r1 * 0.8 + Vector((0, 0, zc * 0.2))
        frond(mbl, root, az, math.radians(rnd.uniform(-48, -38)), frond_len * rnd.uniform(0.55, 0.68),
              droop=rnd.uniform(18, 30), seed=seed * 977 + k, n_seg=max(4, frond_seg - 2), twist=rnd.uniform(-25, 25),
              n_leaf=max(5, n_leaf - 4), blade=blade * 0.7, leaf_w=leaf_w * 0.7, fwd=24.0, vang=-8.0,
              rachis_w=0.06 * scale ** 0.7, leaf_mat='SKY_SandstoneDeep', rachis_mat='SKY_SandstoneDeep',
              spines=0, fold=0.15)
    # young spear leaves at the heart
    for k in range(spears):
        az = k * 2.3 + seed
        root = ptop + Vector((0, 0, zc + 0.12))
        frond(mbl, root, az, math.radians(rnd.uniform(70, 80)), frond_len * rnd.uniform(0.4, 0.5),
              droop=rnd.uniform(14, 24), seed=seed * 577 + k, n_seg=4, n_leaf=max(4, n_leaf - 5),
              blade=blade * 0.45, leaf_w=leaf_w * 0.6, fwd=12.0, vang=55.0, rachis_w=0.05 * scale ** 0.7,
              spines=0, start=0.3)
    a.part(mbl, name="fronds", target=target)
    nd = 0 if dates is False or dates is None else (2 if dates is True else int(dates))
    if nd:
        mbs = MB(); mbd = MB()
        for k in range(nd):
            az = k * (2 * math.pi / nd) + 0.9 + seed * 0.3
            out = Vector((math.cos(az), math.sin(az), 0))
            date_bunch(mbs, mbd, ptop + out * r1 * 1.05 + Vector((0, 0, zc * 0.3)), out, seed * 31 + k,
                       drop=0.7 * scale, reach=0.38 * scale)
        a.part(mbs, name="date_stalks", target=target)
        a.part(mbd, name="dates", target=target)
    a.set_target(target or a.name, weighted=False, smooth=50.0)
    return top


@asset("palm_date_a", "Nature", "nature", ao=NAT_AO, render=NAT_RENDER)
def palm_date_a(a):
    """Tall date palm (~8.4 m): gently leaning trunk, 14 fronds, dried skirt, two date bunches."""
    palm(a, height=6.3, lean=(0.35, -0.2), fronds=14, frond_len=3.25, r0=0.34, r1=0.24, seed=3, dates=2)


@asset("palm_date_b", "Nature", "nature", ao=NAT_AO, render=NAT_RENDER)
def palm_date_b(a):
    """Shorter, strongly leaning date palm (~6.2 m) with 14 fronds and two date bunches."""
    palm(a, height=4.3, lean=(1.05, 0.4), fronds=14, frond_len=2.75, r0=0.32, r1=0.22, seed=7, dates=2)


@asset("palm_small", "Nature", "nature", ao=NAT_AO, render=NAT_RENDER)
def palm_small(a):
    """Young palm (~3.0 m): stout boot-covered trunk, 11 upswept fronds, no dates."""
    palm(a, height=1.85, lean=(0.15, 0.1), fronds=11, frond_len=1.45, r0=0.22, r1=0.17, seed=11, dates=False,
         frond_seg=6, sides=8, seg_h=0.22, skirt=3)


# --------------------------------------------------------------------------- shrubs

def floret_layout(seed, n, rx, ry, h, rmin, rmax, zbase=0.12, sz=0.9):
    """Puffs ("florets") spread over the upper shell of a dome rx x ry x h, biggest near the crown."""
    rnd = random.Random(seed)
    out = []
    golden = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        u = (i + 0.5) / n
        y = 1.0 - u * 1.05                      # from the crown down to just below the equator
        rad = math.sqrt(max(0.0, 1 - min(1.0, y * y)))
        th = i * golden + rnd.uniform(-0.25, 0.25)
        r = lerp(rmax, rmin, u) * rnd.uniform(0.88, 1.12)
        c = (math.cos(th) * rad * (rx - r * 0.6), math.sin(th) * rad * (ry - r * 0.6),
             zbase + max(0.0, y) * (h - zbase - r * 0.7) + r * 0.5 * (1 - max(0.0, y)))
        out.append((c, r, sz))
    return out


@asset("shrub_round", "Nature", "nature", ao=dict(NAT_AO, dist=0.6, inset=0.05), render=NAT_RENDER)
def shrub_round(a):
    """Clipped round shrub (~1.5 m): a leafy core carrying a dome of small lumpy leaf florets
    (deep crevices between them read as dense foliage)."""
    mb = MB()
    ico_blob(mb, (0.0, 0.0, 0.42), 0.52, 'SKY_PalmLeaf', level=3, sz=0.92, noise=0.12, seed=40, flat_z=0.02)
    ico_blob(mb, (0.05, 0.02, 0.18), 0.66, 'SKY_PalmLeaf', level=3, sz=0.42, noise=0.1, seed=41, flat_z=0.02)
    for i, (c, r, sz) in enumerate(floret_layout(31, 21, 0.76, 0.7, 1.06, 0.17, 0.28)):
        ico_blob(mb, c, r, 'SKY_PalmLeaf', level=2, sz=sz, noise=0.16, seed=50 + i, flat_z=0.02, lobes=4)
    a.part(mb, name="leaves")
    a.set_target(a.name, weighted=False, smooth=62.0)


@asset("bougainvillea_clump", "Nature", "p1", ao=dict(NAT_AO, dist=0.6, inset=0.05), render=NAT_RENDER)
def bougainvillea_clump(a):
    """Bougainvillea mound (~1.9 m): woody canes at the root, a leafy dome of florets and cascades of
    papery magenta bract heads over the crown and one flank."""
    rnd = random.Random(5)
    mb = MB()
    for k in range(3):
        az = k * 2.094 + 0.4
        h = Vector((math.cos(az), math.sin(az), 0))
        p0 = Vector((0.04 * h.x, 0.04 * h.y, -0.03))
        p1 = p0 + h * 0.08 + Vector((0, 0, 0.22))
        p2 = p0 + h * rnd.uniform(0.42, 0.52) + Vector((0, 0, 0.42))
        path = bezier(p0, p1, p2, 6)
        mb.sweep(path, circle(0.05, 5, a0=k * 20), 'SKY_PalmTrunk', scales=[1.0, 0.92, 0.84, 0.76, 0.7, 0.64, 0.58])
    a.part(mb, name="stems")
    mb = MB()
    ico_blob(mb, (0.0, 0.0, 0.54), 0.55, 'SKY_PalmLeaf', level=2, sz=0.86, noise=0.1, seed=60, flat_z=0.12)
    ico_blob(mb, (0.0, 0.0, 0.32), 0.7, 'SKY_PalmLeaf', level=2, sz=0.36, noise=0.1, seed=61, flat_z=0.12)
    lay = floret_layout(17, 17, 0.88, 0.82, 1.16, 0.18, 0.27, zbase=0.26)
    rr = random.Random(3)
    heads = []
    for i, (c, r, sz) in enumerate(lay):
        c = Vector(c)
        flank = (c.x * 0.8 - c.y * 0.6)
        ico_blob(mb, c, r, 'SKY_PalmLeaf', level=2, sz=sz, noise=0.18, seed=80 + i, flat_z=0.12, lobes=4)
        if i < 6 or flank > 0.1 or rr.random() < 0.3:
            heads.append((c, r, sz, 3 if (i < 3 or flank > 0.45) else 2))
    a.part(mb, name="masses")
    # papery magenta bract rosettes crowding the crown and cascading down one flank
    mb = MB()
    for i, (c, r, sz, k) in enumerate(heads):
        nd = (c - Vector((0, 0, 0.3))).normalized()
        for j in range(k):
            t = nd.orthogonal().normalized()
            t.rotate(Matrix.Rotation(j * 2.1 + i + rr.uniform(-0.4, 0.4), 3, nd))
            dd = (nd + t * (0.15 if j == 0 else 0.8)).normalized()
            p = c + Vector((dd.x * r, dd.y * r, dd.z * r * sz)) * 0.84
            bract_cluster(mb, p, dd, r * rr.uniform(0.52, 0.64), seed=i * 7 + j, petals=5, open_=0.36)
    a.part(mb, name="bracts")
    a.set_target(a.name, weighted=False, smooth=62.0)
