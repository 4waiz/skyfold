"""SKYFOLD environment kit - ground tiles: roads, plaza, paving, runway, apron, quays, bridges.

All tiles: 16 m x 16 m cell centred on the origin, road surface at Z 0, 0.3 m slab.
Remember: Unity N = Blender -Y, Unity E = Blender -X (S = +Y, W = +X).

Detail pass (tactile miniature-city craftsmanship, detail from geometry):
- `surf` is a manifold 2.5D surface builder (constrained Delaunay). Walls between heights are stitched
  through every intermediate level present at a column (no T-junctions); a skirt and a triangulated
  bottom close the solid. Used for recessed paving joints, flush gutters / drain grates / manholes and
  4 mm raised road markings.
- Kerbs are separate extruded stones with a rounded road-side nosing and real 12 mm joints. Stones and
  surface outlines are sampled at the same stations, so stone faces and paving edges coincide exactly.
- The Unity validator derives road openings from the SKY_Road submesh bounds: SKY_Road is used for the
  asphalt only (gutters, drains, manholes and markings use other palette materials).
"""
from env_common import *

H = 8.0          # half cell
RW = 4.0         # half asphalt width
KW = 0.3         # kerb stone width
SWZ = 0.15       # sidewalk / kerb top
LW = 0.075       # half line width
SQ = [(-H, -H), (H, -H), (H, H), (-H, H)]

GW = 0.3         # flush gutter channel in front of the kerbs
JW = 0.012       # paving joint width
JZ = SWZ - 0.012 # paving joint floor on sidewalks
JZ0 = -0.012     # paving joint floor on ground-level paving
KG = 0.012       # kerb stone joint
BL = 6.4         # building-line band (distance from the road axis); street lamps stand on it
MZ = 0.004       # raised road markings (<= 5 mm)
CR = 2.0         # junction corner kerb radius (front edge)

ROAD_AO = dict(ground_z=None, dist=0.45, rays=24, strength=0.7, floor=0.55, inset=0.12)
TILE_RENDER = dict(az=30.0, el=42.0)


def rect(x0, x1, y0, y1):
    return [(min(x0, x1), min(y0, y1)), (max(x0, x1), min(y0, y1)), (max(x0, x1), max(y0, y1)), (min(x0, x1), max(y0, y1))]


def reg(pts, z, mat, prio, side=None, **kw):
    d = dict(pts=pts, z=z, mat=mat, prio=prio)
    if side:
        d['side'] = side
    d.update(kw)
    return d


def mapq(pts, sx, sy):
    return [(sx * x, sy * y) for (x, y) in pts]


def swapxy(pts):
    return [(y, x) for (x, y) in pts]


def orect(c, u, hl, hw):
    """Oriented rectangle centred at c, half-length hl along u, half-width hw across."""
    u = Vector(u).normalized()
    v = Vector((-u.y, u.x))
    c = Vector(c)
    return [tuple(c - u * hl - v * hw), tuple(c + u * hl - v * hw), tuple(c + u * hl + v * hw), tuple(c - u * hl + v * hw)]


def seg_strip(p0, p1, w):
    """Thin strip polygon of width w along p0 -> p1."""
    p0 = Vector(p0); p1 = Vector(p1)
    return orect((p0 + p1) / 2, p1 - p0, (p1 - p0).length / 2, w / 2)


def ring_poly(c, r0, r1, a0, a1, seg):
    """Annular sector outline (r0 < r1), angles in degrees."""
    return arc(c[0], c[1], r1, a0, a1, seg) + arc(c[0], c[1], r0, a1, a0, seg)


# --------------------------------------------------------------------------- 2.5D surface builder

def _pip(x, y, poly):
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i][0], poly[i][1]
        xj, yj = poly[j][0], poly[j][1]
        if (yi > y) != (yj > y):
            if x < xi + (y - yi) * (xj - xi) / (yj - yi):
                inside = not inside
        j = i
    return inside


def surf(a, regions, base_z=-0.3, target=None, side_mat="SKY_SandstoneDeep", bevel=0.0, seg=2,
         min_step=0.06, bounds=None, name="surface", extra_pts=(), profile=0.5, xform=None, bottom=True):
    """Manifold 2.5D tile surface from prioritised flat regions {pts, z, mat, prio, side?, flat?}.

    Walls are created between neighbouring triangles of different height and stitched through every
    intermediate level present at a vertex column; boundary edges get a skirt down to base_z and the
    boundary loop is triangulated as the bottom. With bevel > 0, convex top edges of steps taller than
    min_step get a bevel weight (never on the bounds outline), so shallow joints stay crisp."""
    verts2, vmap = [], {}

    def vid(p):
        key = (round(p[0], 5), round(p[1], 5))
        i = vmap.get(key)
        if i is None:
            i = vmap[key] = len(verts2)
            verts2.append(Vector(key))
        return i

    faces_in = []
    for r in regions:
        idx = []
        for p in r['pts']:
            i = vid(p)
            if not idx or idx[-1] != i:
                idx.append(i)
        while len(idx) > 1 and idx[0] == idx[-1]:
            idx.pop()
        faces_in.append(idx)
    for p in extra_pts:
        vid(p)
    res = delaunay_2d_cdt(verts2, [], faces_in, 0, 1e-5)
    ov, of = res[0], res[2]
    order = sorted(range(len(regions)), key=lambda k: -regions[k]['prio'])
    bbs = []
    for r in regions:
        xs = [p[0] for p in r['pts']]
        ys = [p[1] for p in r['pts']]
        bbs.append((min(xs) - 1e-6, max(xs) + 1e-6, min(ys) - 1e-6, max(ys) + 1e-6))
    tris = []
    for f in of:
        f = list(f)
        pts = [(ov[i].x, ov[i].y) for i in f]
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        rr = None
        for k in order:
            b = bbs[k]
            if b[0] <= cx <= b[1] and b[2] <= cy <= b[3] and _pip(cx, cy, regions[k]['pts']):
                rr = regions[k]
                break
        if rr is None:
            continue
        if poly_area(pts) < 0:
            f.reverse()
        tris.append((f, rr))
    edge_tris, levels = {}, {}
    for (f, rr) in tris:
        for k in range(len(f)):
            p, q = f[k], f[(k + 1) % len(f)]
            edge_tris.setdefault((min(p, q), max(p, q)), []).append((p, q, rr))
            levels.setdefault(p, set()).add(rr['z'])
    boundary = [lst[0] for lst in edge_tris.values() if len(lst) == 1]
    for (p, q, rr) in boundary:
        levels[p].add(base_z)
        levels[q].add(base_z)
    mb = MB()
    bm = mb.bm
    bwl = bm.edges.layers.float.new('bevel_weight_edge')
    vc = {}

    def bv(i, z):
        k = (i, round(z, 6))
        v = vc.get(k)
        if v is None:
            v = vc[k] = mb.v((ov[i].x, ov[i].y, z))
        return v

    for (f, rr) in tris:
        mb.f([bv(i, rr['z']) for i in f], rr['mat'])

    def column(i, zh, zl):
        mid = sorted([z for z in levels.get(i, ()) if zl + 1e-6 < z < zh - 1e-6], reverse=True)
        return [zh] + mid + [zl]

    def wall(p, q, zh, zl, mat):
        L = [bv(p, z) for z in column(p, zh, zl)]
        R = [bv(q, z) for z in column(q, zh, zl)]
        if len(L) == 2 and len(R) == 2:
            mb.f([L[0], L[1], R[1], R[0]], mat)
            return
        i = j = 0
        while i < len(L) - 1 or j < len(R) - 1:
            if j >= len(R) - 1 or (i < len(L) - 1 and L[i + 1].co.z >= R[j + 1].co.z):
                mb.f([L[i], L[i + 1], R[j]], mat)
                i += 1
            else:
                mb.f([L[i], R[j + 1], R[j]], mat)
                j += 1

    tops = []
    for lst in edge_tris.values():
        if len(lst) != 2:
            continue
        (p1, q1, r1), (p2, q2, r2) = lst
        if abs(r1['z'] - r2['z']) < 1e-7:
            continue
        (p, q, rh), rl = ((p1, q1, r1), r2) if r1['z'] > r2['z'] else ((p2, q2, r2), r1)
        wall(p, q, rh['z'], rl['z'], rh.get('side', rh['mat']))
        if rh['z'] - rl['z'] >= min_step and not rh.get('flat') and not rl.get('nobev'):
            tops.append((p, q, rh['z']))
    for (p, q, rr) in boundary:
        wall(p, q, rr['z'], base_z, side_mat)
    if bottom and boundary:
        nxt = {p: q for (p, q, rr) in boundary}
        seen = set()
        for st in list(nxt):
            if st in seen:
                continue
            loop, cur = [], st
            while cur not in seen and cur in nxt:
                seen.add(cur)
                loop.append(cur)
                cur = nxt[cur]
            if len(loop) < 3:
                continue
            r2_ = delaunay_2d_cdt([Vector((ov[i].x, ov[i].y)) for i in loop], [], [list(range(len(loop)))], 1, 1e-6)
            bfs, borig = r2_[2], r2_[3]
            m = {oi: loop[orig[0]] for oi, orig in enumerate(borig) if len(orig)}
            for bf in bfs:
                if not all(i in m for i in bf):
                    continue
                ids = [m[i] for i in bf]
                if poly_area([(ov[i].x, ov[i].y) for i in ids]) > 0:
                    ids.reverse()
                mb.f([bv(i, base_z) for i in ids], side_mat)
    if bevel > 0 and tops:
        bx0, bx1, by0, by1 = bounds if bounds else (-H, H, -H, H)
        eps = 1e-4

        def onb(v):
            c = v.co
            return (abs(c.x - bx0) < eps, abs(c.x - bx1) < eps, abs(c.y - by0) < eps, abs(c.y - by1) < eps)
        for (p, q, z) in tops:
            e = bm.edges.get((bv(p, z), bv(q, z)))
            if e is None:
                continue
            ba, bb = onb(e.verts[0]), onb(e.verts[1])
            if any(ba[k] and bb[k] for k in range(4)):
                continue
            e[bwl] = 1.0
    if xform is not None:
        bmesh.ops.transform(bm, matrix=xform, verts=bm.verts[:])
        if xform.to_3x3().determinant() < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    return a.part(mb, target=target, bevel=bevel, seg=seg, weight_limit=True, name=name, profile=profile)


# --------------------------------------------------------------------------- kerb stones

class KPath:
    """Kerb FRONT-edge path of lines ('L', p0, p1) and arcs ('A', c, r, a0, a1) in degrees.
    back: side of the travel direction where the sidewalk lies ('left' or 'right')."""

    def __init__(self, prims, back='left', max_deg=11.25):
        self.prims = prims
        self.sgn = 1.0 if back == 'left' else -1.0
        self.max_deg = max_deg
        self.lens = []
        for p in prims:
            if p[0] == 'L':
                self.lens.append((Vector(p[2]) - Vector(p[1])).length)
            else:
                self.lens.append(abs(math.radians(p[4] - p[3])) * p[2])
        self.total = sum(self.lens)

    def at(self, s):
        s = max(0.0, min(self.total, s))
        acc = 0.0
        for k, (p, L) in enumerate(zip(self.prims, self.lens)):
            if s <= acc + L + 1e-9 or k == len(self.prims) - 1:
                t = (s - acc) / L if L > 1e-12 else 0.0
                break
            acc += L
        if p[0] == 'L':
            a_, b_ = Vector(p[1]), Vector(p[2])
            pt = a_.lerp(b_, t)
            tan = (b_ - a_).normalized()
        else:
            c, r = Vector(p[1]), p[2]
            ang = math.radians(p[3] + (p[4] - p[3]) * t)
            pt = c + Vector((math.cos(ang), math.sin(ang))) * r
            tan = Vector((-math.sin(ang), math.cos(ang))) * (1.0 if p[4] > p[3] else -1.0)
        return pt, Vector((-tan.y, tan.x)) * self.sgn

    def subdiv(self):
        """Primitive boundaries and arc subdivision stations (arc pieces <= max_deg)."""
        out, acc = [], 0.0
        for p, L in zip(self.prims, self.lens):
            if p[0] == 'A':
                n = max(1, int(math.ceil(abs(p[4] - p[3]) / self.max_deg - 1e-6)))
                out += [acc + L * i / n for i in range(1, n)]
            acc += L
            out.append(acc)
        return out

    def pts(self, stations, d):
        out = []
        for s in stations:
            p, b = self.at(s)
            q = p + b * d
            out.append((q.x, q.y))
        return out


def kerb_layout(kp, joints=(), gap0=True, gap1=True, inlets=()):
    """Stones between joints (arc-length stations) -> [(s0, s1, inlet)], plus the shared station list."""
    inl = [(min(p, q), max(p, q)) for (p, q) in inlets]
    cuts = [0.0, kp.total]
    for j in joints:
        if 0.1 < j < kp.total - 0.1 and not any(p - 0.1 < j < q + 0.1 for (p, q) in inl):
            cuts.append(j)
    for (p, q) in inl:
        cuts += [p, q]
    cuts = sorted(set(round(c, 6) for c in cuts))
    stones = []
    for i in range(len(cuts) - 1):
        s0, s1 = cuts[i], cuts[i + 1]
        a0 = s0 + (KG / 2 if (i > 0 or gap0) else 0.0)
        a1 = s1 - (KG / 2 if (i < len(cuts) - 2 or gap1) else 0.0)
        inlet = any(abs(s0 - p) < 1e-5 and abs(s1 - q) < 1e-5 for (p, q) in inl)
        stones.append((a0, a1, inlet))
    # stone-end stations next to a path end (half joint on a cell edge) are left out of the shared
    # outline: they would sit 0.5 mm from the cell-edge half joints and only create slivers
    ends = sorted(set([0.0, round(kp.total, 6)] + [round(x, 6) for st in stones for x in st[:2]
                                                    if 0.02 < x < kp.total - 0.02]))
    st = list(ends)
    for s in kp.subdiv():
        if all(abs(s - x) > 0.06 for x in ends):
            st.append(round(s, 6))
    return stones, sorted(set(st))


def _kprof(w=KW, top=SWZ, bot=-0.01, r=0.05, n=3):
    """Kerb cross-section (d toward the sidewalk, z): front face (segment 0), rounded road-side nosing,
    flat top flush with the sidewalk. The hidden back/bottom is a single diagonal face (cheaper, closed)."""
    pts = [(0.0, bot), (0.0, top - r)]
    for k in range(1, n):
        t = math.radians(180.0 - 90.0 * k / n)
        pts.append((r + r * math.cos(t), top - r + r * math.sin(t)))
    pts += [(r, top), (w, top)]
    return pts


KPROF = _kprof()


def extrude(mb, path, nrm, prof, mat, seg_mats=None):
    """Closed (d, z) profile extruded along a 2D path; nrm[i] = unit 2D direction of +d. Capped solid."""
    rings = [[mb.v((p[0] + n[0] * d, p[1] + n[1] * d, z)) for (d, z) in prof] for p, n in zip(path, nrm)]
    m = len(prof)
    fs = []
    for i in range(len(rings) - 1):
        A, B = rings[i], rings[i + 1]
        for k in range(m):
            k2 = (k + 1) % m
            fs.append(mb.f([A[k], A[k2], B[k2], B[k]], seg_mats[k] if seg_mats else mat))
    fs.append(mb.f(list(reversed(rings[0])), mat))
    fs.append(mb.f(list(rings[-1]), mat))
    mb._recalc(fs)
    return fs


def kerb_stones(mb, kp, stones, stations, prof=KPROF, mat='SKY_Pearl', inlet_mat='SKY_Ink'):
    for (a0, a1, inlet) in stones:
        st = [a0] + [s for s in stations if a0 + 1e-5 < s < a1 - 1e-5] + [a1]
        path, nrm = [], []
        for s in st:
            p, b = kp.at(s)
            path.append(p)
            nrm.append(b)
        sm = [mat] * len(prof)
        if inlet:
            sm[0] = inlet_mat          # dark kerb inlet face over a gutter grate
        extrude(mb, path, nrm, prof, mat, seg_mats=sm)
    return mb


def kerb_regions(kp, st, prio=1):
    """Flush gutter channel in front of the stones, continuing under them as the kerb bed (it shows in the
    stone joints). The stones' front faces dip 10 mm into it, so no outline is needed at the kerb front.
    The back line uses every stone station (the stones' back edges sit exactly on it); the gutter line
    only needs the arc subdivision; straight runs only need their end stations."""
    if len(kp.prims) == 1 and kp.prims[0][0] == 'L':
        st = gst = [0.0, kp.total]
    else:
        gst = sorted(set([0.0, kp.total] + [x for x in kp.subdiv() if 0.0 < x < kp.total]))
    b = kp.pts(st, KW)
    g = kp.pts(gst, -GW)
    return [reg(g + b[::-1], 0.0, 'SKY_Kerb', prio)]


# --------------------------------------------------------------------------- road furniture (flush / raised)

def asphalt():
    return reg(SQ, 0.0, 'SKY_Road', 0)


def line(pts, mat='SKY_RoadLine'):
    return reg(pts, MZ, mat, 8)


def joint(pts, z=JZ, prio=3):
    return reg(pts, z, 'SKY_SandstoneDeep', prio)


def drain(c, u, L=0.8, W=0.42, n=3):
    """Flush gutter grate centred at c, long axis u along the kerb: metal frame + bars, 20 mm ink slots."""
    u = Vector(u).normalized()
    R = [reg(orect(c, u, L / 2, W / 2), 0.0, 'SKY_Metal', 6)]
    sl, bar = 0.14, 0.09
    tot = n * sl + (n - 1) * bar
    for k in range(n):
        off = -tot / 2 + sl / 2 + k * (sl + bar)
        R.append(reg(orect(Vector(c) + u * off, u, sl / 2, W / 2 - 0.06), -0.02, 'SKY_Ink', 7))
    return R


def manhole(cx, cy, r=0.42, n=14):
    """Flush round cover: metal frame, ink seam ring, metal lid with an ink pick boss."""
    return [reg(circle(r, n, cx, cy), 0.0, 'SKY_Metal', 6),
            reg(circle(r - 0.06, n, cx, cy), 0.0, 'SKY_Ink', 7),
            reg(circle(r - 0.09, n, cx, cy), 0.0, 'SKY_Metal', 8),
            reg(circle(0.07, 6, cx, cy), 0.0, 'SKY_Ink', 9)]


def dashes_y(spans, x=0.0, w=LW):
    return [line(rect(x - w, x + w, p, q)) for (p, q) in spans]


def dashes_x(spans, y=0.0, w=LW):
    return [line(rect(p, q, y - w, y + w)) for (p, q) in spans]


def zebra_y(y0, y1, n=5, sw=0.7, gap=0.65):
    """Zebra across a N-S road: stripes elongated along Y, spaced along X (flush paint; lane dashes and
    runway markings are the raised ones)."""
    tot = n * sw + (n - 1) * gap
    out = []
    for k in range(n):
        x0 = -tot / 2 + k * (sw + gap)
        out.append(reg(rect(x0, x0 + sw, y0, y1), 0.0, 'SKY_RoadLine', 8))
    return out


def zebra_x(x0, x1, n=5, sw=0.7, gap=0.65):
    tot = n * sw + (n - 1) * gap
    out = []
    for k in range(n):
        y0 = -tot / 2 + k * (sw + gap)
        out.append(reg(rect(x0, x1, y0, y0 + sw), 0.0, 'SKY_RoadLine', 8))
    return out


DASH_STD = [(-7, -5), (-3, -1), (1, 3), (5, 7)]


# --------------------------------------------------------------------------- sidewalk kit

def side_paving(s, y0=-H, y1=H, edge0=True, edge1=True):
    """Paving on a straight closed side (road along Y): band A pavers 1 m (pearl-grey kerb stone),
    band B 4 m sandstone slabs on the building line, 12 mm recessed joints, half joints on the cell
    edges crossing the sidewalk (so tile seams read as ordinary joints)."""
    X = lambda v: s * v
    R = [reg(rect(X(RW + KW), X(BL), y0, y1), SWZ, 'SKY_Kerb', 1),
         reg(rect(X(BL), X(H), y0, y1), SWZ, 'SKY_Sandstone', 1),
         joint(rect(X(BL - JW / 2), X(BL + JW / 2), y0, y1))]
    for yy in range(-7, 8):
        if y0 + 0.4 < yy < y1 - 0.4:
            R.append(joint(rect(X(RW + KW), X(BL), yy - JW / 2, yy + JW / 2)))
            if yy % 4 == 0:
                R.append(joint(rect(X(BL), X(H), yy - JW / 2, yy + JW / 2)))
    if edge0:
        R.append(joint(rect(X(RW + KW), X(H), y0, y0 + JW / 2)))
    if edge1:
        R.append(joint(rect(X(RW + KW), X(H), y1 - JW / 2, y1)))
    return R


def straight_side(a, s, y0=-H, y1=H, inlets=(), edge0=True, edge1=True):
    """Closed side of a N-S road on Blender +X (s=1, Unity W) or -X (s=-1, Unity E): kerb stones
    (2 m, joints on even metres, half joints on the cell edges), gutter, grates with kerb inlets, paving."""
    kp = KPath([('L', (s * RW, y0), (s * RW, y1))], back='right' if s > 0 else 'left')
    joints = [yy - y0 for yy in range(-6, 7, 2) if y0 < yy < y1]
    stones, st = kerb_layout(kp, joints, edge0, edge1, [(c - 0.45 - y0, c + 0.45 - y0) for c in inlets])
    mb = MB()
    kerb_stones(mb, kp, stones, st)
    a.part(mb, name="kerb")
    R = kerb_regions(kp, st) + side_paving(s, y0, y1, edge0, edge1)
    for c in inlets:
        R += drain((s * (RW - 0.23), c), (0, 1))
    return R


def corner_block(a, sx, sy, tactile=None):
    """Junction corner (quadrant sx, sy): kerb rounding the corner (R 2 m) with joints at the tangent
    points and mid-arc, L-shaped band A with a mitre joint, band B square, optional terracotta tactile
    band behind the kerb where zebras land ('x' = along the E-W arm only, 'both')."""
    c = RW + CR
    kp = KPath([('L', (RW, H), (RW, c)), ('A', (c, c), CR, 180.0, 270.0), ('L', (c, RW), (H, RW))], back='left',
               max_deg=15.0)
    L1 = H - c
    stones, st = kerb_layout(kp, [L1, L1 + CR * math.pi / 4, L1 + CR * math.pi / 2], True, True)
    back = kp.pts(st, KW)
    Rc = kerb_regions(kp, st)
    Rc.append(reg(back + [(H, H)], SWZ, 'SKY_Kerb', 1))
    Rc.append(reg(rect(BL, H, BL, H), SWZ, 'SKY_Sandstone', 2))
    Rc.append(joint(rect(BL - JW / 2, BL + JW / 2, BL - JW / 2, H)))
    Rc.append(joint(rect(BL - JW / 2, H, BL - JW / 2, BL + JW / 2)))
    Rc.append(joint(rect(H - JW / 2, H, RW + KW, H)))
    Rc.append(joint(rect(RW + KW, H, H - JW / 2, H)))
    Rc.append(joint(rect(RW + KW, BL + JW / 2, 7.0 - JW / 2, 7.0 + JW / 2)))
    Rc.append(joint(rect(7.0 - JW / 2, 7.0 + JW / 2, RW + KW, BL + JW / 2)))
    p0 = Vector((c, c)) - Vector((1, 1)).normalized() * (CR - KW - (0.68 if tactile else 0.01))
    Rc.append(joint(seg_strip(p0, (BL, BL), JW)))
    if tactile:
        s0 = (H - 6.9) if tactile == 'both' else L1
        s1 = kp.total - (H - 6.9)
        stt = [s0] + [s for s in st if s0 + 1e-4 < s < s1 - 1e-4] + [s1]
        o = kp.pts(stt, KW + 0.06)
        i_ = kp.pts(stt, KW + 0.61)
        Rc.append(reg(o + i_[::-1], SWZ, 'SKY_Terracotta', 4))
    mb = MB()
    kerb_stones(mb, kp, stones, st)
    if sx < 0 or sy < 0:
        mb.transform(Matrix.Diagonal((sx, sy, 1.0, 1.0)))
        mb._recalc(mb.bm.faces[:])
    a.part(mb, name="kerb")
    return [dict(r, pts=mapq(r['pts'], sx, sy)) for r in Rc]


# --------------------------------------------------------------------------- roads

@asset("road_straight", "Roads", "roads", ao=ROAD_AO, render=TILE_RENDER)
def road_straight(a):
    R = [asphalt()]
    R += straight_side(a, 1, inlets=(4.0,))
    R += straight_side(a, -1, inlets=(-4.0,))
    R += dashes_y(DASH_STD)
    R += manhole(-2.0, 2.0)
    surf(a, R)


@asset("road_tee", "Roads", "roads", ao=ROAD_AO, render=TILE_RENDER)
def road_tee(a):
    # openings N, E, S (Unity) -> Blender -Y, -X, +Y ; closed side W = +X
    R = [asphalt()] + straight_side(a, 1, inlets=(0.0,))
    R += corner_block(a, -1, -1, tactile='x') + corner_block(a, -1, 1, tactile='x')
    R += dashes_y([(-7, -5), (5, 7)])
    R += zebra_x(-6.9, -4.9)
    R += manhole(1.6, -2.4)
    surf(a, R)


@asset("road_cross", "Roads", "roads", ao=ROAD_AO, render=TILE_RENDER)
def road_cross(a):
    R = [asphalt()]
    for sx in (-1, 1):
        for sy in (-1, 1):
            R += corner_block(a, sx, sy, tactile='both')
    R += zebra_y(-6.9, -4.9) + zebra_y(4.9, 6.9) + zebra_x(-6.9, -4.9) + zebra_x(4.9, 6.9)
    R += manhole(0.0, 0.0)
    surf(a, R)


@asset("road_corner", "Roads", "roads", ao=ROAD_AO, render=TILE_RENDER)
def road_corner(a):
    # openings Unity N (-Y) and E (-X): quarter-annulus bend centred on Blender (-8,-8)
    P = (-H, -H)
    r_in, r_out = RW, 3 * RW
    R = [asphalt()]
    # inner kerb (sidewalk toward P) and outer kerb (sidewalk away from P), both travelled CCW
    kin = KPath([('A', P, r_in, 0.0, 90.0)], back='left', max_deg=10.0)
    kout = KPath([('A', P, r_out, 0.0, 90.0)], back='right', max_deg=4.5)
    a45i = r_in * math.pi / 4
    a45o = r_out * math.pi / 4
    st_in, ss_in = kerb_layout(kin, [kin.total / 3, 2 * kin.total / 3], True, True, [(a45i - 0.45, a45i + 0.45)])
    jo = [kout.total * k / 10 for k in range(1, 10)]
    st_out, ss_out = kerb_layout(kout, jo, True, True, [(a45o - 0.45, a45o + 0.45)])
    mb = MB()
    kerb_stones(mb, kin, st_in, ss_in)
    kerb_stones(mb, kout, st_out, ss_out)
    a.part(mb, name="kerb")
    R += kerb_regions(kin, ss_in) + kerb_regions(kout, ss_out)
    inner = [P] + kin.pts(ss_in, KW)
    outer = kout.pts(ss_out, KW) + [(-H, H), (H, H), (H, -H)]
    R += [reg(inner, SWZ, 'SKY_Kerb', 1), reg(outer, SWZ, 'SKY_Kerb', 1)]
    # band B (building line) continues the straight tiles' 6.4 m line: r 1.6 inside, r 14.4 outside
    R.append(reg([P] + arc(P[0], P[1], H - BL, 0, 90, 6), SWZ, 'SKY_Sandstone', 2))
    R.append(reg(arc(P[0], P[1], H + BL, 0, 90, 10) + [(-H, H), (H, H), (H, -H)], SWZ, 'SKY_Sandstone', 2))
    R.append(joint(ring_poly(P, H - BL - JW / 2, H - BL + JW / 2, 0, 90, 6)))
    R.append(joint(ring_poly(P, H + BL - JW / 2, H + BL + JW / 2, 0, 90, 10)))
    # radial joints: inner band A every 30 deg, outer bands every 9 deg (~2 m at the kerb)
    for ang in (30.0, 60.0):
        u = Vector((math.cos(math.radians(ang)), math.sin(math.radians(ang))))
        R.append(joint(seg_strip(Vector(P) + u * (H - BL), Vector(P) + u * (r_in - KW - 0.01), JW)))
    for k in range(1, 10):
        ang = 9.0 * k
        u = Vector((math.cos(math.radians(ang)), math.sin(math.radians(ang))))
        R.append(joint(seg_strip(Vector(P) + u * (r_out + KW + 0.01), Vector(P) + u * (H + BL), JW)))
        rmax = min(2 * H / max(u.x, 1e-6), 2 * H / max(u.y, 1e-6)) - 0.015
        R.append(joint(seg_strip(Vector(P) + u * (H + BL), Vector(P) + u * rmax, JW)))
    # half joints where the sidewalks cross the open cell edges (seams read as ordinary joints)
    R.append(joint(rect(-H, -H + r_in - KW, -H, -H + JW / 2)))
    R.append(joint(rect(-H, -H + JW / 2, -H, -H + r_in - KW)))
    R.append(joint(rect(-H + r_out + KW, H, -H, -H + JW / 2)))
    R.append(joint(rect(-H, -H + JW / 2, -H + r_out + KW, H)))
    # lane dashes along the 8 m centre arc
    Lc = (math.pi / 2) * 8.0
    for k in (-1, 0, 1):
        s0 = Lc / 2 + 4 * k - 1
        a0, a1 = math.degrees(s0 / 8.0), math.degrees((s0 + 2) / 8.0)
        R.append(line(arc(P[0], P[1], 8 + LW, a0, a1, 4) + arc(P[0], P[1], 8 - LW, a1, a0, 4)))
    # grates with kerb inlets at mid-bend, manhole in the outer lane
    u45 = Vector((1, 1)).normalized()
    t45 = Vector((-1, 1)).normalized()
    R += drain(Vector(P) + u45 * (r_in + 0.23), t45)
    R += drain(Vector(P) + u45 * (r_out - 0.23), t45)
    R += manhole(P[0] + 10.0 * math.cos(math.radians(25)), P[1] + 10.0 * math.sin(math.radians(25)))
    surf(a, R)


def _road_end_geom():
    C_ = (0.0, 1.5)
    Rb, rf = 5.5, 1.5
    yf = C_[1] - math.sqrt((Rb + rf) ** 2 - (RW + rf) ** 2)
    F = (RW + rf, yf)
    dx, dy = F[0] - C_[0], F[1] - C_[1]
    dl = math.hypot(dx, dy)
    T = (C_[0] + Rb * dx / dl, C_[1] + Rb * dy / dl)
    a_f = math.degrees(math.atan2(T[1] - F[1], T[0] - F[0]))
    a_b = math.degrees(math.atan2(T[1] - C_[1], T[0] - C_[0]))
    return C_, Rb, rf, yf, F, a_f, a_b


@asset("road_end", "Roads", "roads", ao=ROAD_AO, render=TILE_RENDER)
def road_end(a):
    """Cul-de-sac: N arm into a 5.5 m turning circle with filleted kerbs all the way round."""
    C_, Rb, rf, yf, F, a_f, a_b = _road_end_geom()
    kp = KPath([('L', (RW, -H), (RW, yf)), ('A', F, rf, 180.0, a_f), ('A', C_, Rb, a_b, 180.0 - a_b),
                ('A', (-F[0], F[1]), rf, 180.0 - a_f, 0.0), ('L', (-RW, yf), (-RW, -H))], back='right', max_deg=12.0)
    s_top = kp.lens[0] + kp.lens[1] + Rb * math.radians(90.0 - a_b)
    n = 12
    stones, st = kerb_layout(kp, [kp.total * k / n for k in range(1, n)], True, True, [(s_top - 0.45, s_top + 0.45)])
    mb = MB()
    kerb_stones(mb, kp, stones, st)
    a.part(mb, name="kerb")
    gst = sorted(set([0.0, kp.total] + [x for x in kp.subdiv() if 0.0 < x < kp.total]))
    R = [reg(SQ, SWZ, 'SKY_Kerb', 0), reg(kp.pts(gst, -GW), 0.0, 'SKY_Road', 2)]
    R += kerb_regions(kp, st, prio=3)
    # band B along both sides, band line + half joints on the cell edges
    for s in (-1, 1):
        R.append(reg(rect(s * BL, s * H, -H, H), SWZ, 'SKY_Sandstone', 1))
        R.append(joint(rect(s * (BL - JW / 2), s * (BL + JW / 2), -H, H)))
        R.append(joint(rect(s * (RW + KW), s * H, -H, -H + JW / 2)))
        for yy in range(-7, -2):
            R.append(joint(rect(s * (RW + KW), s * BL, yy - JW / 2, yy + JW / 2)))
        for yy in (-4, 0, 4):
            R.append(joint(rect(s * BL, s * H, yy - JW / 2, yy + JW / 2)))
    # radial joints fanning around the turning circle (end in the band line or short of the cell edge)
    for k in range(-1, 10):
        ang = math.radians(22.5 * k)
        u = Vector((math.cos(ang), math.sin(ang)))
        rs = []
        if abs(u.x) > 1e-6:
            rs.append((BL + JW / 2) / abs(u.x))
        if u.y > 1e-6:
            rs.append((H - C_[1]) / u.y - 0.015)
        r1 = min(rs)
        r0 = Rb + KW + 0.01
        if r1 - r0 > 0.3:
            R.append(joint(seg_strip(Vector(C_) + u * r0, Vector(C_) + u * r1, JW)))
    R += dashes_y([(-7, -5)])
    R += drain(Vector(C_) + Vector((0, 1)) * (Rb - 0.23), (1, 0))
    R += manhole(C_[0], C_[1])
    surf(a, R)


# --------------------------------------------------------------------------- plaza and lot paving

@asset("road_plaza", "Roads", "roads", ao=ROAD_AO, render=TILE_RENDER)
def road_plaza(a):
    """Civic square at road level: raised fountain island (pearl ring of eight stones with real joints,
    recessed planting, paved seat for the fountain), brass collar, pearl compass-star inlay,
    deep-sandstone ring band, 16 radial joints out to a kerb-stone border; raised planting beds in the
    corners and two bench pads under the benches (the scene builder places dressing props and benches at
    +0.15 m; benches stand at Unity (+-4, -4) = Blender (-+4, +4))."""
    B = 5.62                       # joints stop inside the corner beds (beds span 5.55..7.75)
    o, i = 7.4 + JW / 2, 7.4 - JW / 2
    R = [reg(SQ, 0.0, 'SKY_Kerb', 0), reg(rect(-i, i, -i, i), 0.0, 'SKY_Sandstone', 1)]
    J0 = lambda pts: joint(pts, JZ0, 3)
    R += [J0(q) for q in (rect(-B, B, -o, -i), rect(-B, B, i, o), rect(-o, -i, -B, B), rect(i, o, -B, B))]
    for k in (-2, 2):
        for s in (-1, 1):
            R.append(J0(rect(k - JW / 2, k + JW / 2, s * o, s * H)))
            R.append(J0(rect(s * o, s * H, k - JW / 2, k + JW / 2)))
    for k in range(16):
        ang = math.radians(11.25 + 22.5 * k)
        u = Vector((math.cos(ang), math.sin(ang)))
        r1 = min(o / max(abs(u.x), 1e-6), o / max(abs(u.y), 1e-6))
        R.append(J0(seg_strip(u * 5.37, u * r1, JW)))
    R.append(reg(circle(5.35, 32), 0.0, 'SKY_SandstoneDeep', 4))
    R.append(reg(circle(5.0, 32), 0.0, 'SKY_Sandstone', 5))
    star = []
    for k in range(32):
        ang = math.radians(11.25 * k)
        rr = (4.6 if k % 4 == 0 else 3.7) if k % 2 == 0 else 3.0
        star.append((rr * math.cos(ang), rr * math.sin(ang)))
    R.append(reg(star, 0.0, 'SKY_Pearl', 6))
    R.append(reg(circle(2.74, 28), 0.0, 'SKY_Brass', 7))
    r_o, r_i = 2.6, 2.25
    jang = [22.5 + 45.0 * k for k in range(8)]
    d_o = math.degrees(math.asin(KG / 2 / r_o))
    d_i = math.degrees(math.asin(KG / 2 / r_i))
    R.append(reg(circle_pts(r_o, 28, extra=[t + e for t in jang for e in (-d_o, d_o)]), SWZ, 'SKY_Pearl', 8,
                 side='SKY_Pearl'))
    for t in jang:
        q = [(r_i, t - d_i), (r_o, t - d_o), (r_o, t + d_o), (r_i, t + d_i)]
        R.append(reg([(r * math.cos(math.radians(g)), r * math.sin(math.radians(g))) for (r, g) in q], SWZ,
                     'SKY_SandstoneDeep', 9))
    R.append(reg(circle_pts(r_i, 28, extra=[t + e for t in jang for e in (-d_i, d_i)]), SWZ - 0.03, 'SKY_PalmLeaf',
                 10, side='SKY_Pearl', flat=True))
    R.append(reg(circle(1.1, 20), SWZ, 'SKY_Kerb', 11, side='SKY_Pearl'))
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = 6.65 * sx, 6.65 * sy
            R.append(reg(rrect(2.2, 2.2, 0.35, 1, cx, cy), SWZ, 'SKY_Pearl', 12, side='SKY_Pearl'))
            R.append(reg(rrect(1.84, 1.84, 0.2, 1, cx, cy), SWZ, 'SKY_PalmLeaf', 13))
        R.append(reg(rrect(0.8, 2.4, 0.12, 1, sx * 4.0, 4.0), SWZ, 'SKY_Kerb', 12, side='SKY_SandstoneDeep', flat=True))
    surf(a, R, bevel=0.03, seg=1)


def square_ring(h, w):
    """Four strips of width w along the square of half size h."""
    o, i = h + w / 2, h - w / 2
    return [rect(-o, o, -o, -i), rect(-o, o, i, o), rect(-o, -i, -o, o), rect(i, o, -o, o)]


def circle_pts(r, n, cx=0.0, cy=0.0, extra=()):
    """Circle polyline with n uniform vertices plus extra vertices at the given angles (degrees)."""
    angs = sorted(set([round(360.0 * i / n, 6) for i in range(n)] + [round(e % 360.0, 6) for e in extra]))
    return [(cx + r * math.cos(math.radians(t)), cy + r * math.sin(math.radians(t))) for t in angs]


@asset("ground_paving", "Roads", "roads", ao=ROAD_AO, render=TILE_RENDER)
def ground_paving(a):
    """Lot paving (placed at +0.15 m): kerb-stone edging band (4 m stones), ring of 2 m slabs in alternating
    sandstone / light stone (dressing props stand here), 4 m field slabs under the building footprint; half
    joints on the cell edges so neighbouring lots read as one continuous pavement."""
    R = [reg(SQ, 0.0, 'SKY_Kerb', 0), reg(rect(-7.4, 7.4, -7.4, 7.4), 0.0, 'SKY_Sandstone', 1)]
    J0 = lambda pts: joint(pts, JZ0, 3)
    R.append(J0(rect(-H, H, -H, -H + JW / 2)))
    R.append(J0(rect(-H, H, H - JW / 2, H)))
    R.append(J0(rect(-H, -H + JW / 2, -H, H)))
    R.append(J0(rect(H - JW / 2, H, -H, H)))
    R += [J0(q) for q in square_ring(7.4, JW) + square_ring(6.0, JW)]
    for k in (-6, -2, 2, 6):
        for s in (-1, 1):
            R.append(J0(rect(k - JW / 2, k + JW / 2, s * (7.4 + JW / 2), s * (H - JW / 2))))
            R.append(J0(rect(s * (7.4 + JW / 2), s * (H - JW / 2), k - JW / 2, k + JW / 2)))
    for k in (-4, -2, 0, 2, 4):
        for s in (-1, 1):
            R.append(J0(rect(k - JW / 2, k + JW / 2, s * (6.0 + JW / 2), s * (7.4 - JW / 2))))
            R.append(J0(rect(s * (6.0 + JW / 2), s * (7.4 - JW / 2), k - JW / 2, k + JW / 2)))
    for k in (-2.0, 2.0):
        R.append(J0(rect(k - JW / 2, k + JW / 2, -6.0, 6.0)))
        R.append(J0(rect(-6.0, 6.0, k - JW / 2, k + JW / 2)))
    # every other ring slab in a lighter stone (edges sit under the joints, so no extra outlines show)
    for k in (-6, -2, 2):
        for s in (-1, 1):
            R.append(reg(rect(k, k + 2, s * 6.0, s * 7.4), 0.0, 'SKY_Kerb', 2))
            R.append(reg(rect(s * 6.0, s * 7.4, -k - 2, -k), 0.0, 'SKY_Kerb', 2))
    surf(a, R)


# --------------------------------------------------------------------------- runway / apron

RUN_HALF = 6.0


def runway_base(y_hi=H):
    """Dark runway pavement |x|<6 with 8 m x 2.9 m slab joints; concrete shoulders with 1 x 2 m slabs,
    pearl edge kerb strip, half joints on the cell edges."""
    R = [reg(SQ, 0.0, 'SKY_Kerb', 0), reg(rect(-RUN_HALF, RUN_HALF, -H, H), 0.0, 'SKY_Road', 1)]
    jr = lambda pts: reg(pts, -0.006, 'SKY_Ink', 3)
    for s in (-1, 1):
        R.append(reg(rect(s * RUN_HALF, s * (RUN_HALF + 0.12), -H, H), 0.0, 'SKY_Pearl', 2))
        R.append(joint(rect(s * (7.0 - JW / 2), s * (7.0 + JW / 2), -H, H), JZ0))
        R.append(joint(rect(s * (H - JW / 2), s * H, -H, H), JZ0))
        for yy in range(-6, 7, 2):
            R.append(joint(rect(s * (RUN_HALF + 0.12), s * H, yy - JW / 2, yy + JW / 2), JZ0))
        R.append(jr(rect(s * (2.9 - 0.008), s * (2.9 + 0.008), -H, y_hi)))
        R.append(joint(rect(s * (RUN_HALF + 0.12), s * H, -H, -H + JW / 2), JZ0))
        R.append(joint(rect(s * (RUN_HALF + 0.12), s * H, H - JW / 2, H), JZ0))
    for yy in (-H, 0.0, H):
        if yy <= y_hi:
            R.append(jr(rect(-RUN_HALF, RUN_HALF, max(-H, yy - 0.008), min(H, yy + 0.008))))
    return R


@asset("runway_section", "Roads", "runway", ao=ROAD_AO, render=TILE_RENDER)
def runway_section(a):
    R = runway_base()
    for s in (-1, 1):
        R.append(line(rect(s * 5.5, s * 5.85, -H, H)))
    R += dashes_y([(-6, -2), (2, 6)], w=0.2)
    surf(a, R)


@asset("runway_end", "Roads", "runway", ao=ROAD_AO, render=TILE_RENDER)
def runway_end(a):
    # connects to runway_section on Unity N (-Y); the runway ends at Unity S (+Y)
    R = runway_base(y_hi=4.6)
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
    for y0 in (5.25, 6.45):
        pts = [(-5.2, y0 + 0.9), (0.0, y0), (5.2, y0 + 0.9), (5.2, y0 + 1.35), (0.0, y0 + 0.45), (-5.2, y0 + 1.35)]
        R.append(reg(pts, MZ, 'SKY_Coral', 8))
    surf(a, R)


@asset("apron_tile", "Roads", "runway", ao=ROAD_AO, render=TILE_RENDER)
def apron_tile(a):
    """Concrete apron: 4 m slabs with dark sealed expansion joints (half joints on the cell edges), brass
    tie-down rings with recessed eyes, and a slot drain along Blender y +4.8 that runs on across a row."""
    R = [reg(SQ, 0.0, 'SKY_Kerb', 0)]
    js = lambda pts: reg(pts, -0.006, 'SKY_Ink', 3)
    for c in (-4.0, 0.0, 4.0):
        R.append(js(rect(c - 0.01, c + 0.01, -H, H)))
        R.append(js(rect(-H, H, c - 0.01, c + 0.01)))
    for c in (-H, H):
        s = 1 if c < 0 else -1
        R.append(js(rect(c, c + s * 0.01, -H, H)))
        R.append(js(rect(-H, H, c, c + s * 0.01)))
    for (x, y) in ((-2, -2), (2, 2), (-2, 2), (2, -2)):
        R.append(reg(circle(0.17, 10, x, y), 0.0, 'SKY_Brass', 5))
        R.append(reg(circle(0.1, 10, x, y), -0.01, 'SKY_Ink', 6))
    R.append(reg(rect(-H, H, 4.6, 4.98), 0.0, 'SKY_Metal', 5))
    for k in range(-8, 8):
        x0 = k + 0.15
        R.append(reg(rect(x0, x0 + 0.7, 4.69, 4.89), -0.02, 'SKY_Ink', 6))
    surf(a, R)
# --------------------------------------------------------------------------- quays

QT = 1.5          # wall thickness: lies OUTSIDE the land cell, in the 1.5 m water margin
Q_COPE = 0.6      # pearl coping width
Q_LIP = 0.1       # coping overhang over the water face
QJ = 0.025        # block joint width on the wall face
QJD = 0.035       # block joint depth
# dressed block courses above / around the waterline (Z -1.2): dry sandstone on top, a darker wet band
# and the submerged course below it read as a tide line
QCOURSES = [(-0.75, -0.3, 'SKY_Sandstone'), (-1.2, -0.75, 'SKY_SandstoneDeep'), (-1.65, -1.2, 'SKY_SandstoneDeep')]
QBLK = 2.0        # block length (running bond)


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


def _run_frame(p0, p1):
    p0v, p1v = Vector(p0), Vector(p1)
    L = (p1v - p0v).length
    t = (p1v - p0v) / L
    return p0v, t, Vector((-t.y, t.x)), L


def quay_face(a, p0, p1, u0=0.0, u1=None, v_top=-0.3, blk=QBLK, phase=0.0, name="wall"):
    """Quay wall body for u0..u1 along the run p0->p1 (water face on the line, land on the LEFT), built
    with `surf` in the wall plane: three courses of chamfered dressed blocks in running bond (25 mm joints
    recessed 35 mm), recessed core below, projecting toe on the seabed; 1.5 m deep to the land edge."""
    p0v, t, nl, L = _run_frame(p0, p1)
    u1 = L if u1 is None else u1
    nw = -nl
    M = Matrix(((t.x, 0.0, nw.x, p0v.x), (t.y, 0.0, nw.y, p0v.y), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)))
    R = [reg(rect(u0, u1, -4.0, v_top), -0.08, 'SKY_SandstoneDeep', 0),
         reg(rect(u0, u1, -4.0, -3.45), 0.15, 'SKY_SandstoneDeep', 1, flat=True)]
    for ci, (c0, c1, mat) in enumerate(QCOURSES):
        if c0 >= v_top:
            continue
        c1 = v_top if ci == 0 else min(c1, v_top)
        R.append(reg(rect(u0, u1, c0, c1), -QJD, 'SKY_SandstoneDeep', 2, flat=True))
        off = phase + (blk / 2 if ci % 2 else 0.0)
        k0 = math.floor((u0 - off) / blk) - 1
        k1 = math.ceil((u1 - off) / blk) + 1
        for k in range(k0, k1 + 1):
            ra, rb = off + k * blk, off + (k + 1) * blk          # joint stations of this block
            ua, ub = max(ra, u0), min(rb, u1)
            if ub - ua < 0.05:
                continue
            ja = jb = QJ / 2       # blocks never touch the segment ends: seams and cuts always read as joints
            vt = c1 - (QJ / 2 if c1 < v_top - 1e-6 else 0.0)
            R.append(reg(rect(ua + ja, ub - jb, c0 + QJ / 2, vt), 0.0, mat, 3))
    surf(a, R, base_z=-QT, side_mat='SKY_SandstoneDeep', bevel=0.022, seg=1, min_step=0.03,
         bounds=(u0, u1, -4.0, v_top), name=name, xform=M)


def _cprof():
    """Coping cross-section (d toward land from the wall face, z): drip chamfer under the lip, rounded
    water-side nosing, flat top to the back of the stone."""
    r = 0.06
    pts = [(Q_COPE, -0.3), (-Q_LIP + 0.03, -0.3), (-Q_LIP, -0.27), (-Q_LIP, -r)]
    for k in (1, 2):
        t = math.radians(180.0 - 30.0 * k)
        pts.append((-Q_LIP + r + r * math.cos(t), -r + r * math.sin(t)))
    pts += [(-Q_LIP + r, 0.0), (Q_COPE, 0.0)]
    return pts


CPROF = _cprof()


def quay_coping(a, p0, p1, u0=0.0, u1=None, blk=QBLK, gap0=True, gap1=True, dz=0.0):
    """Pearl coping stones (2 m in run coordinates, rounded nosing, 12 mm joints) on u0..u1 of the run
    p0->p1 (land on the left). gap0/gap1: half joints at the ends (run ends on cell edges). dz lifts it."""
    p0v, t, nl, L = _run_frame(p0, p1)
    u1 = L if u1 is None else u1
    kp = KPath([('L', tuple(p0v + t * u0), tuple(p0v + t * u1))], back='left')
    joints = [k * blk - u0 for k in range(-20, 21) if u0 + 0.2 < k * blk < u1 - 0.2]
    stones, st = kerb_layout(kp, joints, gap0, gap1)
    mb = MB()
    kerb_stones(mb, kp, stones, st, prof=[(d, z + dz) for (d, z) in CPROF], mat='SKY_Pearl')
    a.part(mb, name="coping")


def quay_top(a, p0, p1, u0=0.0, u1=None, d0=Q_COPE, d1=QT, joints=None, name="quaytop", dz=0.0):
    """Sandstone paving behind the coping (Z0, 0.3 m thick) with joints in line with the coping joints and
    a half joint on the land edge."""
    p0v, t, nl, L = _run_frame(p0, p1)
    u1 = L if u1 is None else u1
    M = Matrix(((t.x, nl.x, 0.0, p0v.x), (t.y, nl.y, 0.0, p0v.y), (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0)))
    R = [reg(rect(u0, u1, d0, d1), dz, 'SKY_Sandstone', 0),
         reg(rect(u0, u1, d1 - JW / 2, d1), JZ0 + dz, 'SKY_SandstoneDeep', 2)]
    for u in (joints if joints is not None else [k * QBLK for k in range(-20, 21)]):
        if u0 + 0.1 < u < u1 - 0.1:
            R.append(reg(rect(u - JW / 2, u + JW / 2, d0, d1 - JW / 2), JZ0 + dz, 'SKY_SandstoneDeep', 2))
    surf(a, R, base_z=-0.3 + dz, side_mat='SKY_SandstoneDeep', bounds=(u0, u1, d0, d1), name=name, xform=M)


def quay_run(a, p0, p1, u0=0.0, u1=None, phase=0.0):
    """Complete wall run: block face, coping, paved top."""
    p0v, t, nl, L = _run_frame(p0, p1)
    u1 = L if u1 is None else u1
    quay_face(a, p0, p1, u0, u1, phase=phase)
    quay_coping(a, p0, p1, u0, u1)
    quay_top(a, p0, p1, u0, u1)


def quay_corner_wedge(a, c, r, a0, a1, seg=8):
    """Rounded convex corner: core, chamfered course blocks split mid-arc, toe, coping arc and paved top."""
    mb = MB()
    mb.prism(_wedge(c, 0.0, r - 0.08, a0, a1, seg), -4.0, -0.3, 'SKY_SandstoneDeep')
    a.part(mb, name="wcore")
    mb = MB()
    mb.prism(_wedge(c, 0.0, r + 0.15, a0, a1, seg), -4.0, -3.45, 'SKY_SandstoneDeep')
    a.part(mb, bevel=0.022, seg=1, name="wtoe")
    am = (a0 + a1) / 2
    for ci, (z0, z1, mat) in enumerate(QCOURSES):
        cuts = [(a0, am), (am, a1)] if ci % 2 == 0 else [(a0, a1)]
        mb = MB()
        for (b0, b1) in cuts:
            g0 = math.degrees(QJ / 2 / r) if b0 != a0 else 0.0
            g1 = math.degrees(QJ / 2 / r) if b1 != a1 else 0.0
            n = max(2, int(round(seg * (b1 - b0) / (a1 - a0))))
            mb.prism(_wedge(c, 0.0, r, b0 + g0, b1 - g1, n), z0 + QJ / 2, z1 - (QJ / 2 if z1 < -0.31 else 0.0), mat)
        a.part(mb, bevel=0.022, seg=1, angle=40.0, name=f"wcourse{ci}")
    mb = MB()
    mb.prism(_wedge(c, 0.0, r - Q_COPE, a0, a1, seg), -0.3, 0.0, 'SKY_Sandstone')
    a.part(mb, name="wtop")
    kp = KPath([('A', c, r, a0, a1)], back='left', max_deg=11.25)
    stones, st = kerb_layout(kp, [], True, True)
    mb = MB()
    kerb_stones(mb, kp, stones, st, prof=CPROF, mat='SKY_Pearl')
    a.part(mb, name="coping")


def bollard_mooring(mb, x, y, z=0.0):
    """Cast mooring bollard: ink base plate, waisted post, flared rounded head."""
    prof = [(0, z), (0.24, z), (0.24, z + 0.035), (0.16, z + 0.06), (0.135, z + 0.13), (0.125, z + 0.36),
            (0.17, z + 0.44), (0.2, z + 0.48), (0.2, z + 0.52), (0.15, z + 0.565), (0, z + 0.58)]
    mb.lathe(prof, 10, 'SKY_Ink', cx=x, cy=y, a0=18.0)


def cleat(mb, p, t, z=0.0):
    """Brass horn cleat: waisted base block and a horn bar with tapered tips (one closed loft), horn along t."""
    t = Vector(t).normalized()
    n = Vector((-t.y, t.x))
    c = Vector(p)
    prof = [(-0.21, 0.07, 0.09), (-0.16, 0.085, 0.11), (-0.06, 0.085, 0.11), (-0.05, 0.0, 0.06),
            (0.05, 0.0, 0.06), (0.06, 0.085, 0.11), (0.16, 0.085, 0.11), (0.21, 0.07, 0.09)]
    rings = []
    for (u, z0_, z1_) in prof:
        hw = 0.032 if abs(u) > 0.1 else 0.045
        rings.append([(u, -hw, z + z0_), (u, hw, z + z0_), (u, hw, z + z1_), (u, -hw, z + z1_)])
    fs = mb.loft(rings, 'SKY_Brass')
    fs += mb.box(-0.13, 0.13, -0.05, 0.05, z - 0.005, z + 0.02, 'SKY_Brass')
    M = Matrix(((t.x, n.x, 0, c.x), (t.y, n.y, 0, c.y), (0, 0, 1, 0), (0, 0, 0, 1)))
    mb.transform(M, fs)


def fender(mb, p, t, nw, z0=-1.75, z1=-0.38):
    """Rubber D-fender hung on the wall face (p on the face line, nw toward the water) with ink straps."""
    t = Vector(t).normalized(); nw = Vector(nw).normalized(); p = Vector(p)
    prof = [(0.17 * math.cos(math.radians(a_)), 0.15 * math.sin(math.radians(a_))) for a_ in range(0, 181, 30)]
    lo = [mb.v((p.x + t.x * u + nw.x * w, p.y + t.y * u + nw.y * w, z0)) for (u, w) in prof]
    hi = [mb.v((p.x + t.x * u + nw.x * w, p.y + t.y * u + nw.y * w, z1)) for (u, w) in prof]
    fs = [mb.f(list(reversed(lo)), 'SKY_Rubber'), mb.f(hi, 'SKY_Rubber')]
    for i in range(len(prof)):
        j = (i + 1) % len(prof)
        fs.append(mb.f([lo[i], lo[j], hi[j], hi[i]], 'SKY_Rubber'))
    mb._recalc(fs)
    for zz in (z1 - 0.12, z0 + 0.18):
        q = p + nw * 0.075
        fb = mb.box(-0.2, 0.2, -0.09, 0.09, zz - 0.035, zz + 0.035, 'SKY_Ink')
        M = Matrix(((t.x, nw.x, 0, q.x), (t.y, nw.y, 0, q.y), (0, 0, 1, 0), (0, 0, 0, 1)))
        mb.transform(M, fb)


def ladder(a, p, t, nw, z0=-2.1, top=0.0, w=0.5):
    """Brass quay ladder standing off the wall face (p on the face line, nw toward the water): round
    stiles rising into goose-neck grab rails that land on the coping, round rungs every 0.3 m, brackets."""
    t = Vector(t).normalized(); nw = Vector(nw).normalized(); p = Vector(p)
    off = 0.14
    mb = MB()
    for s in (-1, 1):
        b = p + t * (s * w / 2)
        prof = [(off, z0), (off, top + 0.1), (0.12, top + 0.36), (0.02, top + 0.5), (-0.12, top + 0.5),
                (-0.25, top + 0.38), (-0.3, top + 0.2), (-0.3, top + 0.005)]
        pts = [(b + nw * d).to_3d() + Vector((0, 0, z)) for (d, z) in prof]
        mb.sweep(pts, circle(0.022, 6), 'SKY_Brass')
    a.part(mb, name="ladder_rails")
    mb = MB()
    c = p + nw * off
    zz = z0 + 0.15
    while zz < top - 0.1:
        q0 = (c - t * (w / 2)).to_3d() + Vector((0, 0, zz))
        q1 = (c + t * (w / 2)).to_3d() + Vector((0, 0, zz))
        mb.sweep([q0, q1], circle(0.016, 6), 'SKY_Brass')
        zz += 0.3
    for s in (-1, 1):
        b = p + t * (s * w / 2)
        for zb in (z0 + 0.35, top - 0.5):
            fb = mb.box(-0.025, 0.025, 0.0, off, zb - 0.025, zb + 0.025, 'SKY_Brass')
            M = Matrix(((t.x, nw.x, 0, b.x), (t.y, nw.y, 0, b.y), (0, 0, 1, 0), (0, 0, 0, 1)))
            mb.transform(M, fb)
    a.part(mb, name="ladder_rungs")


QUAY_AO = dict(ground_z=None, dist=1.0, rays=24, strength=0.75, floor=0.45, inset=0.15)
QUAY_RENDER = dict(az=205.0, el=26.0, water=True, seabed=-4.0)


@asset("quay_straight", "Roads", "quays", ao=QUAY_AO, render=QUAY_RENDER)
def quay_straight(a):
    """Seawall for the Unity SOUTH edge of a land cell. The 1.5 m thick wall lies just OUTSIDE the
    cell (Blender y 8..9.5, in the water margin) so it never overlaps the land cell's ground tile.
    Harbour steps descend along the wall toward Unity W inside a 1.2 m recess."""
    yf = H + QT
    p0, p1 = (H, yf), (-H, yf)                 # u runs toward Blender -X
    ua, ub = 1.6, 6.6                          # steps recess (Blender x 6.4 .. 1.4)
    quay_face(a, p0, p1, 0.0, ua)
    quay_face(a, p0, p1, ub, 2 * H)
    quay_face(a, p0, p1, ua, ub, v_top=-1.45, name="wall_low")
    quay_coping(a, p0, p1, 0.0, ua, gap1=False)
    quay_coping(a, p0, p1, ub, 2 * H, gap0=False)
    quay_top(a, p0, p1, 0.0, ua)
    quay_top(a, p0, p1, ub, 2 * H)
    quay_top(a, p0, p1, ua, ub, d0=1.2, joints=[2.6, 3.6, 4.6, 5.6])
    # steps: one chamfered staircase block across the recess (water face to the back wall)
    rise = 0.217
    st = [(ua, -1.45), (ub, -1.45), (ub, -rise)]
    for i in range(5):
        u_ = ub - 0.6 * (i + 1)
        st += [(u_, -rise * (i + 1)), (u_, -rise * (i + 2))]
    st += [(ua, -rise * 6)]
    mb = MB()                                  # u -> world x = H - u ; across from the face to the back wall
    mb.prism_frame([(H - u, z) for (u, z) in st], (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0), -yf, -(H + 0.3),
                   'SKY_Kerb')
    a.part(mb, bevel=0.025, seg=1, angle=40.0, name="steps")
    mb = MB()
    mb.box(H - ub, H - ua, H, H + 0.3, -1.45, -0.3, 'SKY_Sandstone')
    a.part(mb, name="step_wall")
    # brass handrail along the back wall following the flight
    mb = MB()
    xr0, xr1 = H - ub + 0.15, H - ua - 0.6
    zr0, zr1 = 0.5, -0.217 * 6 + 0.5
    yr = H + 0.38
    rail = [(xr0 - 0.15, yr, 0.05), (xr0, yr, zr0)]
    rail += [(xr0 + (xr1 - xr0) * f, yr, zr0 + (zr1 - zr0) * f) for f in (0.25, 0.5, 0.75, 1.0)]
    rail += [(xr1 + 0.25, yr, zr1), (xr1 + 0.35, yr, zr1 - 0.25)]
    mb.sweep(rail, circle(0.025, 6), 'SKY_Brass')
    for f in (0.0, 0.5, 1.0):
        x_ = xr0 + (xr1 - xr0) * f
        z_ = zr0 + (zr1 - zr0) * f
        z_floor = -0.217 * min(6, math.ceil((x_ - (H - ub)) / 0.6 + 1e-6))
        mb.cyl(0.03, z_floor, z_ - 0.02, 6, 'SKY_Brass', cx=x_, cy=yr)
    a.part(mb, name="handrail")
    mb = MB()
    for x in (-5.5, -1.5):
        bollard_mooring(mb, x, yf - 0.3)
    a.part(mb, name="bollards")
    mb = MB()
    cleat(mb, (-3.5, yf - 0.28), (1, 0))
    cleat(mb, (-7.0, yf - 0.28), (1, 0))
    a.part(mb, name="cleats")
    mb = MB()
    for x in (-5.5, -1.5, -7.3):
        fender(mb, (x, yf), (1, 0), (0, 1))
    a.part(mb, name="fenders")
    a.notes.append("Wall occupies Blender y 8..9.5 (Unity z -8..-9.5), i.e. the 1.5 m water margin outside the "
                   "cell's south edge; top flush at Z0; face drops to Z-4.")


@asset("quay_corner_outer", "Roads", "quays", ao=QUAY_AO, render=dict(QUAY_RENDER, az=230.0))
def quay_corner_outer(a):
    """Convex land corner: water to the Unity S (+Y) and E (-X) of the land cell."""
    yf = H + QT
    xf = -H - QT
    quay_run(a, (H, yf), (-H, yf))
    quay_run(a, (xf, H), (xf, -H), phase=1.0)
    quay_corner_wedge(a, (-H, H), QT, 90, 180, 8)
    mb = MB()
    bollard_mooring(mb, -H - 0.75, H + 0.75)
    bollard_mooring(mb, 2.5, yf - 0.3)
    bollard_mooring(mb, xf + 0.3, -2.5)
    a.part(mb, name="bollards")
    mb = MB()
    cleat(mb, (-3.0, yf - 0.28), (1, 0))
    cleat(mb, (xf + 0.28, 1.5), (0, 1))
    a.part(mb, name="cleats")
    mb = MB()
    for x in (2.5, -4.0):
        fender(mb, (x, yf), (1, 0), (0, 1))
    for y in (-2.5, 4.0):
        fender(mb, (xf, y), (0, 1), (-1, 0))
    a.part(mb, name="fenders")
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
    cleat(mb, (0.5, yf - 0.28), (1, 0))
    a.part(mb, name="cleats")
    mb = MB()
    for x in (-3.0, 4.0):
        fender(mb, (x, yf), (1, 0), (0, 1))
    a.part(mb, name="fenders")
    ladder(a, (-H + QT + 0.9, yf), (1, 0), (0, 1))
    a.notes.append("Use on the land cell whose wall runs into the concave corner at its local Unity-east end; "
                   "the neighbouring cell keeps a quay_straight.")


# --------------------------------------------------------------------------- bridges

DECK_HW = 5.0       # deck half width (8 m asphalt + 1 m walkways)
DECK_T = 0.55
ABUT = 6.5          # abutment face |y| (quay line)
PIER = 5.8          # pier face |y| (arch springing)
FASCIA_BOT = -0.5
ZT = 0.28           # parapet top = balustrade base
SPX = 4.8           # spandrel face |x| (set back under the cornice)
BAL_X = 5.135       # balustrade centreline |x|
ABZ = 0.15          # abutment tops flush with the walkways and the neighbouring quay copings (+0.15)
LAMP_Y = H - 0.45   # lantern pylons (LIGHT_lantern_* empties)
ARCH_ZS, ARCH_ZC, RING_T = -2.4, -0.92, 0.36

BR_AO = dict(ground_z=None, dist=1.2, rays=24, strength=0.75, floor=0.45, inset=0.15)
BR_RENDER = dict(az=62.0, el=18.0, water=True, seabed=-4.0)

# cornice / parapet plinth cross-section (|x|, z): bead, fascia face, moulded cornice with a sloped soffit
FPROF = [(DECK_HW, FASCIA_BOT), (5.26, FASCIA_BOT), (5.29, FASCIA_BOT + 0.03), (5.29, -0.16), (5.38, -0.12),
         (5.42, -0.06), (5.42, 0.0), (5.36, 0.04), (5.27, 0.04), (5.27, ZT - 0.03), (5.24, ZT), (DECK_HW, ZT)]
# square vase baluster: (height above the plinth rail, half width)
BAL_PROF = [(0.0, 0.046), (0.3, 0.057), (0.62, 0.027), (0.78, 0.042)]


def bridge_deck(a, y0=-H, y1=H, dash=True, edge0=True, edge1=True):
    """Deck surface on the road profile: asphalt, gutters, extruded kerb stones (joints on even metres and
    at the expansion joints), paved walkways to the parapet, flush metal expansion plates with an ink seam
    over the abutment faces, raised lane dashes."""
    R = [reg(rect(-DECK_HW, DECK_HW, y0, y1), 0.0, 'SKY_Road', 0)]
    ej = [yj for yj in (-ABUT, ABUT) if y0 + 0.3 < yj < y1 - 0.3]
    mb = MB()
    for s in (-1, 1):
        kp = KPath([('L', (s * RW, y0), (s * RW, y1))], back='right' if s > 0 else 'left')
        joints = [yy - y0 for yy in list(range(-6, 7, 2)) + ej if y0 + 0.3 < yy < y1 - 0.3]
        stones, st = kerb_layout(kp, joints, edge0, edge1)
        kerb_stones(mb, kp, stones, st)
        R += kerb_regions(kp, st)
        R.append(reg(rect(s * (RW + KW), s * DECK_HW, y0, y1), SWZ, 'SKY_Kerb', 1))
        for yy in range(-7, 8):
            if y0 + 0.4 < yy < y1 - 0.4 and all(abs(yy - e) > 0.3 for e in ej):
                R.append(joint(rect(s * (RW + KW), s * DECK_HW, yy - JW / 2, yy + JW / 2)))
        if edge0:
            R.append(joint(rect(s * (RW + KW), s * DECK_HW, y0, y0 + JW / 2)))
        if edge1:
            R.append(joint(rect(s * (RW + KW), s * DECK_HW, y1 - JW / 2, y1)))
        for yj in ej:
            R.append(reg(rect(s * (RW + KW), s * DECK_HW, yj - 0.12, yj + 0.12), SWZ, 'SKY_Metal', 5))
            R.append(reg(rect(s * (RW + KW), s * DECK_HW, yj - 0.015, yj + 0.015), SWZ, 'SKY_Ink', 6))
    a.part(mb, name="kerb")
    for yj in ej:
        R.append(reg(rect(-RW, RW, yj - 0.12, yj + 0.12), 0.0, 'SKY_Metal', 5))
        R.append(reg(rect(-RW, RW, yj - 0.015, yj + 0.015), 0.0, 'SKY_Ink', 6))
    if dash:
        R += dashes_y([(p, q) for (p, q) in DASH_STD if p >= y0 - 1e-6 and q <= y1 + 1e-6])
    surf(a, R, base_z=-DECK_T, bounds=(-DECK_HW, DECK_HW, y0, y1), name="deck")


def bridge_fascia(a, y0, y1, glow=True):
    """Moulded pearl cornice and parapet plinth along both deck edges, soft teal light strip under the
    cornice soffit."""
    mb = MB()
    for s in (-1, 1):
        extrude(mb, [(0.0, y0), (0.0, y1)], [(s, 0.0), (s, 0.0)], FPROF, 'SKY_Pearl')
    a.part(mb, name="fascia")
    if glow:
        mb = MB()
        for s in (-1, 1):
            mb.box(s * 5.29, s * 5.315, y0 + 0.05, y1 - 0.05, -0.225, -0.165, 'SKY_TealGlow')
        a.part(mb, name="glow")


def baluster(mb, x, y, z0):
    rings = [[(x - w, y - w, z0 + dz), (x + w, y - w, z0 + dz), (x + w, y + w, z0 + dz), (x - w, y + w, z0 + dz)]
             for (dz, w) in BAL_PROF]
    mb.loft(rings, 'SKY_Pearl')


def balustrade(a, y0, y1, posts, s, spacing=0.42, margin0=0.32, margin1=0.32, post_h=1.0):
    """Pearl balustrade on the parapet (|x| = BAL_X): plinth rail, square vase balusters, pedestal posts
    with caps and brass finials, rounded handrail. margin0/1 keep balusters clear of the end pedestals."""
    xc = s * BAL_X
    zr = ZT + 0.08
    zh = ZT + 0.86
    mb = MB()
    mb.box(xc - 0.1, xc + 0.1, y0, y1, ZT, zr, 'SKY_Pearl')
    a.part(mb, bevel=0.015, seg=1, name="bal_plinth")
    hp = [(-0.085, 0.0), (0.085, 0.0), (0.085, 0.05), (0.06, 0.095), (0.0, 0.115), (-0.06, 0.095), (-0.085, 0.05)]
    mb = MB()
    mb.loft([[(xc + u, y, zh + v) for (u, v) in hp] for y in (y0, y1)], 'SKY_Pearl')
    a.part(mb, name="handrail")
    if posts:
        mb = MB()
        mbf = MB()
        for py in posts:
            mb.box(xc - 0.13, xc + 0.13, py - 0.13, py + 0.13, ZT, ZT + post_h, 'SKY_Pearl')
            mb.box(xc - 0.17, xc + 0.17, py - 0.17, py + 0.17, ZT + post_h, ZT + post_h + 0.07, 'SKY_Pearl')
            mbf.lathe([(0, ZT + post_h + 0.07), (0.07, ZT + post_h + 0.07), (0.045, ZT + post_h + 0.11),
                       (0.07, ZT + post_h + 0.17), (0.03, ZT + post_h + 0.23), (0, ZT + post_h + 0.26)], 6,
                      'SKY_Brass', cx=xc, cy=py, a0=30)
        a.part(mb, bevel=0.02, seg=1, name="bal_posts")
        a.part(mbf, name="bal_finials")
    mb = MB()
    stops = [(p, 0.25) for p in posts]
    for (e, m) in ((y0, margin0), (y1, margin1)):
        if all(abs(e - p) > 1e-6 for p in posts):
            stops.append((e, m))
    stops.sort()
    for k in range(len(stops) - 1):
        p = stops[k][0] + stops[k][1]
        q = stops[k + 1][0] - stops[k + 1][1]
        n = max(1, int(round((q - p) / spacing)) + 1)
        for i in range(n):
            by = p + (q - p) * (i / (n - 1) if n > 1 else 0.5)
            baluster(mb, xc, by, zr)
    a.part(mb, name="balusters")


def lamp_pylon(a, x, y, lantern=True):
    """Pearl pedestal on the parapet with a brass post and a six-sided brass-framed lantern (SKY_Light
    glass) centred on the LIGHT empty height (1.9 m)."""
    mb = MB()
    mb.box(x - 0.25, x + 0.25, y - 0.25, y + 0.25, SWZ, 1.2, 'SKY_Pearl')
    mb.box(x - 0.3, x + 0.3, y - 0.3, y + 0.3, SWZ, ZT + 0.12, 'SKY_Pearl')
    mb.box(x - 0.31, x + 0.31, y - 0.31, y + 0.31, 1.2, 1.28, 'SKY_Pearl')
    a.part(mb, bevel=0.025, seg=1, name="pylon")
    mb = MB()
    mb.box(x - 0.255, x + 0.255, y - 0.255, y + 0.255, 0.98, 1.03, 'SKY_Teal')
    a.part(mb, name="pylon_band")
    mb = MB()
    if not lantern:
        mb.lathe([(0, 1.28), (0.12, 1.28), (0.08, 1.34), (0.11, 1.42), (0.04, 1.5), (0, 1.53)], 6, 'SKY_Brass',
                 cx=x, cy=y, a0=30)
        a.part(mb, name="pylon_finial")
        return
    mb.lathe([(0, 1.28), (0.12, 1.28), (0.06, 1.37), (0.045, 1.62), (0.17, 1.7), (0.17, 1.74), (0.0, 1.745)], 6,
             'SKY_Brass', cx=x, cy=y, a0=30)
    mb.lathe([(0, 2.03), (0.2, 2.03), (0.2, 2.06), (0.07, 2.18), (0.035, 2.22), (0.06, 2.26), (0, 2.3)], 6,
             'SKY_Brass', cx=x, cy=y, a0=30)
    for k in range(6):
        ang = math.radians(30 + 60 * k)
        cx_, cy_ = x + 0.15 * math.cos(ang), y + 0.15 * math.sin(ang)
        fs = mb.box(-0.014, 0.014, -0.014, 0.014, 1.74, 2.03, 'SKY_Brass')
        mb.transform(M_tr(cx_, cy_, 0) @ M_rot(math.degrees(ang)), fs)
    a.part(mb, name="lantern_frame")
    mb = MB()
    mb.lathe([(0, 1.74), (0.125, 1.74), (0.15, 2.03), (0, 2.03)], 6, 'SKY_Light', cx=x, cy=y, a0=30)
    a.part(mb, name="lantern")


def arch_curve(y_spring, z_spring, z_crown, n=16):
    """Segmental circular arch (y, z) from +y_spring to -y_spring through the crown at y=0."""
    hw = y_spring
    rise = z_crown - z_spring
    rr = (hw * hw + rise * rise) / (2 * rise)
    cz = z_crown - rr
    a0 = math.degrees(math.atan2(z_spring - cz, hw))
    angs = [a0 + (180 - 2 * a0) * i / n for i in range(n + 1)]
    return [(rr * math.cos(math.radians(t)), cz + rr * math.sin(math.radians(t))) for t in angs], (rr, cz, a0, angs)


def _poly_z(pts, y):
    """z on a polyline (y descending) at y."""
    for (y0, z0), (y1, z1) in zip(pts, pts[1:]):
        if min(y0, y1) - 1e-9 <= y <= max(y0, y1) + 1e-9:
            t = (y - y0) / (y1 - y0) if abs(y1 - y0) > 1e-12 else 0.0
            return z0 + (z1 - z0) * t
    return pts[-1][1]


def arch_regions(keep=None, seed=7):
    """Elevation regions (u = y, v = z, height = |x|) for one face of the arch: spandrel and piers,
    pearl voussoir ring with 25 mm joints, keystone, impost bands. keep: springer only (y >= keep),
    with a radial break through the ring and a jagged break up the spandrel."""
    crv, (rr, cz, a0, angs) = arch_curve(PIER, ARCH_ZS, ARCH_ZC, 16)
    ext = [(math.cos(math.radians(t)) * (rr + RING_T), cz + math.sin(math.radians(t)) * (rr + RING_T)) for t in angs]
    hs, hr, hj, hk = SPX, SPX + 0.06, SPX + 0.03, SPX + 0.12
    R = []
    if keep is None:
        out = [(-ABUT, -4.0), (-PIER, -4.0)] + list(reversed(crv)) + [(PIER, -4.0), (ABUT, -4.0), (ABUT, FASCIA_BOT),
                                                                      (-ABUT, FASCIA_BOT)]
        R.append(reg(out, hs, 'SKY_Sandstone', 0))
        R.append(reg(crv + list(reversed(ext)), hr, 'SKY_Pearl', 2, side='SKY_Pearl'))
        jl = [i for i in range(1, 16) if i != 8]
        ky = 0.2
        R.append(reg([(-ky, _poly_z(crv, -ky) + 0.03), (ky, _poly_z(crv, ky) + 0.03), (ky + 0.07, FASCIA_BOT - 0.01),
                      (-ky - 0.07, FASCIA_BOT - 0.01)], hk, 'SKY_Pearl', 4, side='SKY_Pearl'))
        sides = (-1, 1)
    else:
        ib = max(i for i, (y, z) in enumerate(crv) if y >= keep)
        rnd = random.Random(seed)
        yb = crv[ib][0]
        out = [(PIER, -4.0), (ABUT, -4.0), (ABUT, FASCIA_BOT)]
        # broken face slopes from the deck break down to the cut through the ring
        y_top = 5.75 + 0.25 * rnd.random()
        ye, ze = ext[ib]
        jag = [(y_top, FASCIA_BOT)]
        for f in (0.33, 0.66):
            yj = y_top + (ye - y_top) * f + 0.15 * (rnd.random() - 0.5)
            zj = FASCIA_BOT + (ze + 0.08 - FASCIA_BOT) * f + 0.1 * (rnd.random() - 0.5)
            jag.append((yj, zj))
        out += jag + [ext[ib]] + list(reversed(crv[:ib + 1]))
        R.append(reg(out, hs, 'SKY_Sandstone', 0))
        R.append(reg(crv[:ib + 1] + list(reversed(ext[:ib + 1])), hr, 'SKY_Pearl', 2, side='SKY_Pearl'))
        jl = list(range(1, ib))
        sides = (1,)
    for i in jl:
        t = math.radians(angs[i])
        u = Vector((math.cos(t), math.sin(t)))
        c0 = Vector((0.0, cz)) + u * (rr + 0.006)
        c1 = Vector((0.0, cz)) + u * (rr + RING_T - 0.006)
        R.append(reg(seg_strip(c0, c1, QJ), hj, 'SKY_SandstoneDeep', 3, flat=True, nobev=True))
    for sg in sides:
        R.append(reg(mapq(rect(PIER + 0.02, ABUT, ARCH_ZS - 0.22, ARCH_ZS - 0.06), sg, 1), hr, 'SKY_Pearl', 1,
                     side='SKY_Pearl'))
        R.append(reg(mapq(rect(PIER + 0.01, ABUT, -1.62, -1.6), sg, 1), hs - 0.02, 'SKY_SandstoneDeep', 1, flat=True,
                     nobev=True))
    return R


def bridge_arch(a, keep=None):
    """Arch elevation built with `surf` in the y-z plane for both faces (height = |x|, the two halves meet
    on the centre plane): the opening's skirt forms the soffit, piers carry the springing; cutwaters with
    pearl caps point up/downstream. keep: broken springers only (bridge_stub)."""
    jobs = [(arch_regions(), 1)] if keep is None else [(arch_regions(keep, 7), 1), (arch_regions(keep, 19), -1)]
    for s in (-1, 1):
        for (R, sg) in jobs:
            M = Matrix(((0.0, 0.0, float(s), 0.0), (float(sg), 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0),
                        (0.0, 0.0, 0.0, 1.0)))
            us = [p[0] for r in R for p in r['pts']]
            surf(a, R, base_z=0.0, side_mat='SKY_SandstoneDeep', bevel=0.02, seg=1, min_step=0.05,
                 bounds=(min(us), max(us), -4.0, FASCIA_BOT), name="arch", xform=M)
    mb = MB()
    mbc = MB()
    for sg in (-1, 1):
        yc = sg * (PIER + ABUT) / 2
        for s in (-1, 1):
            tri = [(s * (SPX - 0.05), sg * PIER), (s * (SPX + 0.75), yc), (s * (SPX - 0.05), sg * ABUT)]
            mb.prism(tri, -4.0, -1.5, 'SKY_SandstoneDeep')
            c = (s * (SPX + 0.05), yc)
            lo = [(p[0], p[1], -1.5) for p in tri]
            hi = [(c[0] + (p[0] - c[0]) * 0.35, c[1] + (p[1] - c[1]) * 0.35, -1.05) for p in tri]
            mbc.loft([lo, hi], 'SKY_Pearl')
    a.part(mb, bevel=0.03, seg=1, name="cutwater")
    a.part(mbc, bevel=0.015, seg=1, name="cutwater_cap")


def bridge_abutment(a, sgn, dz=ABZ):
    """Quay-style abutment along the cell edge (|y| 6.5..8): block faces toward the channel either side of
    the arch piers; pearl coping and paved top outside the parapets, flush with the walkways at +0.15."""
    if sgn > 0:
        p0, p1 = (-H, ABUT), (H, ABUT)
    else:
        p0, p1 = (H, -ABUT), (-H, -ABUT)
    ux = H - SPX
    for (u0, u1) in ((0.0, ux), (2 * H - ux, 2 * H)):
        quay_face(a, p0, p1, u0, u1, v_top=-0.3 + dz, name="abut_face")
    uc = H - 5.3
    for (u0, u1, g0, g1) in ((0.0, uc, True, False), (2 * H - uc, 2 * H, False, True)):
        quay_coping(a, p0, p1, u0, u1, gap0=g0, gap1=g1, dz=dz)
        quay_top(a, p0, p1, u0, u1, dz=dz, name="abut_top")


@asset("bridge_span", "Roads", "bridges", ao=BR_AO, render=BR_RENDER)
def bridge_span(a):
    bridge_deck(a)
    bridge_fascia(a, -H, H)
    for s in (-1, 1):
        balustrade(a, -LAMP_Y, LAMP_Y, [-4.0, 0.0, 4.0], s)
    for sg in (-1, 1):
        bridge_abutment(a, sg)
    bridge_arch(a)
    k = 0
    for s in (-1, 1):
        for sg in (-1, 1):
            x, y = s * (DECK_HW + 0.125), sg * LAMP_Y
            lamp_pylon(a, x, y)
            a.empty(f"LIGHT_lantern_{k}", (x, y, 1.9))
            k += 1
    a.notes.append("Deck top Z0 (8 m asphalt + 1 m walkways at Z0.15). Abutments fill the 1.5 m channel margins "
                   "at both cell edges, continuing the quay line with tops flush at +0.15; arch springs from "
                   "cutwater piers at |y|=5.8.")


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
    """Empty bridge socket: broken deck ends jut ~2.5 m from both cell edges, barriers before the breaks,
    intact abutments and lamp pedestals, broken arch springers, rubble in the channel."""
    for sg in (-1, 1):
        y_edge = sg * H
        y_break = sg * (H - 2.0)
        ya, yb = sorted((y_edge, y_break))
        bridge_deck(a, ya, yb, dash=False, edge0=(sg < 0), edge1=(sg > 0))
        bridge_fascia(a, ya, yb)
        for s in (-1, 1):
            lo, hi = sorted((sg * LAMP_Y, sg * (H - 1.85)))
            balustrade(a, lo, hi, [sg * (H - 1.85)], s, spacing=0.42,
                       margin0=0.32 if sg < 0 else 0.25, margin1=0.32 if sg > 0 else 0.25)
            lamp_pylon(a, s * (DECK_HW + 0.125), sg * LAMP_Y, lantern=False)
        rnd = random.Random(11 + sg)
        xs = [-DECK_HW - 0.25, -1.6, 1.9, DECK_HW + 0.25]
        for k in range(len(xs) - 1):
            poly = jag_poly(xs[k], xs[k + 1], y_break, sg, rnd)
            top = -0.05 - 0.14 * rnd.random()
            bot = -DECK_T - 0.15 - 0.35 * rnd.random()
            mb = MB()
            mb.prism(poly, bot, top, 'SKY_SandstoneDeep', top='SKY_Kerb')
            a.part(mb, bevel=0.03, seg=1, name="break")
        yb_ = sg * (H - 1.35)
        mb = MB()
        striped_beam_x(mb, -RW + 0.25, RW - 0.25, yb_ - 0.07, yb_ + 0.07, 0.55, 0.88, 11, ['SKY_Coral', 'SKY_Pearl'])
        a.part(mb, name="barrier_beam")
        mb = MB()
        for x in (-RW + 0.7, 0.0, RW - 0.7):
            mb.box(x - 0.05, x + 0.05, yb_ - 0.04, yb_ + 0.04, 0.06, 0.6, 'SKY_Pearl')
            mb.box(x - 0.09, x + 0.09, yb_ - 0.32, yb_ + 0.32, 0.0, 0.07, 'SKY_Ink')
        for x in (-RW + 0.7, RW - 0.7):
            mb.cyl(0.07, 0.88, 1.0, 6, 'SKY_Coral', cx=x, cy=yb_)
        a.part(mb, name="barrier_legs")
        bridge_abutment(a, sg)
    bridge_arch(a, keep=3.6)
    mb = MB()
    mb.prism(circle(0.85, 6, 0.4, 0.2), -4.0, -0.95, 'SKY_Sandstone', top='SKY_SandstoneDeep')
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
