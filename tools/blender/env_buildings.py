"""SKYFOLD environment kit - buildings and points of interest.

Footprints <= 12 x 12 m centred in the 16 m cell, pivot at ground centre (Z 0).
Fronts face Unity north (+Z) = Blender -Y. Face names use Unity directions:
'N' = Blender -Y face, 'S' = +Y, 'E' = -X, 'W' = +X.
"""
from env_common import *

BLD_AO = dict(ground_z=0.0, dist=2.2, rays=28, strength=0.82, floor=0.4, inset=0.25)
BLD_RENDER = dict(az=35.0, el=24.0)

# --------------------------------------------------------------------------- facade frames

OUT = {'N': (0, -1), 'S': (0, 1), 'E': (-1, 0), 'W': (1, 0)}


def fpt(face, plane, u, v, d=0.0):
    """Facade coords -> world. u = world x (N/S faces) or world y (E/W faces); v = z;
    d = distance OUTWARD from the facade plane."""
    if face == 'N':
        return (u, plane - d, v)
    if face == 'S':
        return (u, plane + d, v)
    if face == 'E':
        return (plane - d, u, v)
    return (plane + d, u, v)


def fbox(mb, face, plane, u0, u1, v0, v1, d0, d1, mat, fm=None):
    a = fpt(face, plane, u0, v0, d0)
    b = fpt(face, plane, u1, v1, d1)
    return mb.box(a[0], b[0], a[1], b[1], a[2], b[2], mat, fm)


def faxes(face):
    """(u_axis, v_axis, outward) world vectors for prism_frame."""
    if face in ('N', 'S'):
        u = (1, 0, 0)
    else:
        u = (0, 1, 0)
    o = OUT[face]
    return u, (0, 0, 1), (o[0], o[1], 0)


def fprism(mb, face, plane, pts_uv, d0, d1, mat, front=None, back=None):
    """Extrude a (u,v) polygon from d0 to d1 (outward distances) on a facade."""
    u, v, w = faxes(face)
    origin = fpt(face, plane, 0.0, 0.0, 0.0)
    origin = (origin[0] if face in ('E', 'W') else 0.0, origin[1] if face in ('N', 'S') else 0.0, 0.0)
    return mb.prism_frame(pts_uv, origin, u, v, w, d0, d1, mat, front=front, back=back)


def shift_uv(pts, du, dv):
    return [(p[0] + du, p[1] + dv) for p in pts]


def arch_band(w, h, t, kind='round', seg=8):
    O = arch_pts(w + 2 * t, h + t, kind, seg)
    I = arch_pts(w, h, kind, seg)
    return [O[1]] + O[2:] + [O[0]] + [I[0]] + list(reversed(I[2:])) + [I[1]]


# --------------------------------------------------------------------------- openings

class Op:
    def __init__(self, face, u, z, w, h, kind='round', depth=0.3, back='SKY_Glass', seg=6,
                 sill=True, frame=None, frame_t=0.12, through=False, reveal=None, mullion=False, key=False):
        self.__dict__.update(locals())
        del self.__dict__['self']


def make_cutter(a, op, plane, wall_mat):
    mb = MB()
    pts = shift_uv(arch_pts(op.w, op.h, op.kind, op.seg, base=op.z), op.u, 0.0)
    rev = op.reveal or wall_mat
    depth = op.depth if not op.through else 3.0
    fprism(mb, op.face, plane, pts, 0.6, -depth, rev, front=rev, back=op.back)
    return a.cutter(mb, "cut")


def block(a, x0, x1, y0, y1, z0, z1, mat, ops=(), bevel=0.06, seg=1, name="block", target=None, fm=None):
    planes = {'N': y0, 'S': y1, 'E': x0, 'W': x1}
    cutters = [make_cutter(a, op, planes[op.face], mat) for op in ops]
    mb = MB()
    mb.box(x0, x1, y0, y1, z0, z1, mat, fm)
    a.part(mb, bevel=bevel, seg=seg, cutters=cutters, name=name, target=target)
    deco(a, ops, planes, target=target)
    return planes


def deco(a, ops, planes, target=None):
    """Sills, arch frames, mullions for a list of openings."""
    mbs = MB(); mbf = MB(); mbm = MB(); any_s = any_f = any_m = False
    for op in ops:
        pl = planes[op.face]
        if op.sill:
            fbox(mbs, op.face, pl, op.u - op.w / 2 - 0.12, op.u + op.w / 2 + 0.12, op.z - 0.14, op.z + 0.02,
                 -0.05, 0.1, 'SKY_Pearl')
            any_s = True
        if op.frame:
            band = shift_uv(arch_band(op.w, op.h, op.frame_t, op.kind, op.seg), op.u, op.z)
            fprism(mbf, op.face, pl, band, -0.05, 0.06, op.frame)
            any_f = True
        if op.mullion:
            fbox(mbm, op.face, pl, op.u - 0.035, op.u + 0.035, op.z, op.z + op.h - 0.05, -op.depth + 0.02,
                 -op.depth + 0.1, op.mullion)
            fbox(mbm, op.face, pl, op.u - op.w / 2, op.u + op.w / 2, op.z + op.h * 0.55, op.z + op.h * 0.55 + 0.06,
                 -op.depth + 0.02, -op.depth + 0.1, op.mullion)
            any_m = True
    if any_s:
        a.part(mbs, name="sills", target=target)
    if any_f:
        a.part(mbf, name="frames", target=target)
    if any_m:
        a.part(mbm, name="mullions", target=target)


# --------------------------------------------------------------------------- details

def ring_band(a, x0, x1, y0, y1, z0, z1, p, mat, bevel=0.02, seg=1, name="band", target=None):
    mb = MB(); mb.box(x0 - p, x1 + p, y0 - p, y1 + p, z0, z1, mat)
    a.part(mb, bevel=bevel, seg=seg, name=name, target=target)


def plinth(a, x0, x1, y0, y1, h=0.45, p=0.08, mat='SKY_SandstoneDeep'):
    ring_band(a, x0, x1, y0, y1, 0.0, h, p, mat, bevel=0.04, seg=1, name="plinth")


def merlons(a, face, plane, u0, u1, z, h=0.55, w=0.6, gap=0.45, t=0.3, mat='SKY_Pearl', stepped=True, inset=0.0):
    """Row of stepped merlons along a parapet top (Gulf-style stepped crenellation)."""
    mb = MB()
    L = u1 - u0
    n = max(1, int((L + gap) / (w + gap)))
    tot = n * w + (n - 1) * gap
    s0 = u0 + (L - tot) / 2
    for i in range(n):
        c = s0 + i * (w + gap) + w / 2
        if stepped:
            hw = w / 2
            pts = [(c - hw, z), (c + hw, z), (c + hw, z + h * 0.5), (c + hw * 0.45, z + h * 0.5),
                   (c + hw * 0.45, z + h), (c - hw * 0.45, z + h), (c - hw * 0.45, z + h * 0.5),
                   (c - hw, z + h * 0.5)]
        else:
            pts = [(c - w / 2, z), (c + w / 2, z), (c + w / 2, z + h), (c - w / 2, z + h)]
        fprism(mb, face, plane, pts, -inset - t, -inset, mat)
    a.part(mb, name="merlons")


def parapet(a, x0, x1, y0, y1, z, h, t, mat, cap='SKY_Pearl', faces='NSEW', cap_p=0.05):
    """Parapet walls around a roof edge with a coping cap."""
    mb = MB(); mbc = MB()
    if 'N' in faces:
        mb.box(x0, x1, y0, y0 + t, z, z + h, mat); mbc.box(x0 - cap_p, x1 + cap_p, y0 - cap_p, y0 + t + cap_p, z + h, z + h + 0.12, cap)
    if 'S' in faces:
        mb.box(x0, x1, y1 - t, y1, z, z + h, mat); mbc.box(x0 - cap_p, x1 + cap_p, y1 - t - cap_p, y1 + cap_p, z + h, z + h + 0.12, cap)
    if 'E' in faces:
        mb.box(x0, x0 + t, y0 + t, y1 - t, z, z + h, mat); mbc.box(x0 - cap_p, x0 + t + cap_p, y0 + t + cap_p, y1 - t - cap_p, z + h, z + h + 0.12, cap)
    if 'W' in faces:
        mb.box(x1 - t, x1, y0 + t, y1 - t, z, z + h, mat); mbc.box(x1 - t - cap_p, x1 + cap_p, y0 + t + cap_p, y1 - t - cap_p, z + h, z + h + 0.12, cap)
    a.part(mb, name="parapet")
    a.part(mbc, bevel=0.03, seg=1, name="coping")


def shrub_blob(mb, x, y, z, r, mat='SKY_PalmLeaf', seg=7):
    mb.sphere(r, seg, 4, mat, c=(x, y, z + r * 0.75), sz=0.8)


def planter(a, x, y, w, d, h=0.5, shrub=True, mat='SKY_Terracotta', leaf='SKY_PalmLeaf', target=None):
    mb = MB(); mb.box(x - w / 2, x + w / 2, y - d / 2, y + d / 2, 0.0 + h * 0, h, mat)
    a.part(mb, bevel=0.03, seg=1, name="planter", target=target)
    if shrub:
        mb = MB()
        n = max(1, int(round(w / 0.7)))
        for i in range(n):
            px = x - w / 2 + (i + 0.5) * w / n
            shrub_blob(mb, px, y, h - 0.05, min(0.42, d * 0.48))
        a.part(mb, name="shrubs", target=target)


def planter_at(a, x, y, z, w, d, h=0.5, mat='SKY_Terracotta'):
    mb = MB(); mb.box(x - w / 2, x + w / 2, y - d / 2, y + d / 2, z, z + h, mat)
    a.part(mb, bevel=0.03, seg=1, name="planter")
    mb = MB()
    n = max(1, int(round(max(w, d) / 0.75)))
    for i in range(n):
        if w >= d:
            px, py = x - w / 2 + (i + 0.5) * w / n, y
        else:
            px, py = x, y - d / 2 + (i + 0.5) * d / n
        shrub_blob(mb, px, py, z + h - 0.05, min(0.4, min(w, d) * 0.5))
    a.part(mb, name="shrubs")


def pergola(a, x0, x1, y0, y1, z, h=2.5, post=0.18, beam_dir='x', slats=8, sail=None, mat='SKY_Wood'):
    """Timber pergola on a roof terrace; optional shade sail (Fabric) below the slats."""
    mb = MB()
    for (x, y) in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        mb.box(x - post / 2, x + post / 2, y - post / 2, y + post / 2, z, z + h, mat)
    a.part(mb, bevel=0.02, seg=1, name="pergola_posts")
    mb = MB()
    bt = 0.16
    if beam_dir == 'x':
        for y in (y0, y1):
            mb.box(x0 - 0.3, x1 + 0.3, y - bt / 2, y + bt / 2, z + h - 0.02, z + h + 0.22, mat)
        for i in range(slats):
            x = x0 + (x1 - x0) * (i + 0.5) / slats
            mb.box(x - 0.05, x + 0.05, y0 - 0.35, y1 + 0.35, z + h + 0.22, z + h + 0.34, mat)
    else:
        for x in (x0, x1):
            mb.box(x - bt / 2, x + bt / 2, y0 - 0.3, y1 + 0.3, z + h - 0.02, z + h + 0.22, mat)
        for i in range(slats):
            y = y0 + (y1 - y0) * (i + 0.5) / slats
            mb.box(x0 - 0.35, x1 + 0.35, y - 0.05, y + 0.05, z + h + 0.22, z + h + 0.34, mat)
    a.part(mb, name="pergola_beams")
    if sail:
        sail_quad(a, [(x0 + 0.1, y0 + 0.1, z + h - 0.05), (x1 - 0.1, y0 + 0.1, z + h - 0.25),
                      (x1 - 0.1, y1 - 0.1, z + h - 0.05), (x0 + 0.1, y1 - 0.1, z + h - 0.25)], sail)


def sail_mesh(mb, corners, mat='SKY_Fabric', sag=0.25, n=4, t=0.03):
    """Tensioned shade sail over 3 or 4 corner points: sagging surface with thickness (closed solid)."""
    C = [Vector(c) for c in corners]
    nrm = (C[1] - C[0]).cross(C[2] - C[0])
    if nrm.length < 1e-9:
        nrm = Vector((0, 0, 1))
    nrm.normalize()
    if nrm.z < -1e-3:
        nrm = -nrm
    pts = {}
    faces = []
    if len(C) == 4:
        for i in range(n + 1):
            for j in range(n + 1):
                u, v = i / n, j / n
                p = C[0].lerp(C[1], u).lerp(C[3].lerp(C[2], u), v)
                p = p - nrm * (sag * 16 * u * (1 - u) * v * (1 - v))
                pts[(i, j)] = p
        for i in range(n):
            for j in range(n):
                faces.append([(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)])
    else:
        for i in range(n + 1):
            for j in range(n + 1 - i):
                u, v = i / n, j / n
                w = 1 - u - v
                p = C[0] + (C[1] - C[0]) * u + (C[2] - C[0]) * v
                p = p - nrm * (sag * 27 * u * v * w)
                pts[(i, j)] = p
        for i in range(n):
            for j in range(n - i):
                faces.append([(i, j), (i + 1, j), (i, j + 1)])
                if i + j + 2 <= n:
                    faces.append([(i + 1, j), (i + 1, j + 1), (i, j + 1)])
    T = {k: mb.v(p) for k, p in pts.items()}
    B = {k: mb.v(p - nrm * t) for k, p in pts.items()}
    fs = []
    edge_count = {}
    for f in faces:
        fs.append(mb.f([T[k] for k in f], mat))
        fs.append(mb.f([B[k] for k in reversed(f)], mat))
        for k in range(len(f)):
            e = (f[k], f[(k + 1) % len(f)])
            key = tuple(sorted(e))
            edge_count[key] = edge_count.get(key, 0) + 1
    for f in faces:
        for k in range(len(f)):
            a_, b_ = f[k], f[(k + 1) % len(f)]
            if edge_count[tuple(sorted((a_, b_)))] == 1:
                fs.append(mb.f([T[b_], T[a_], B[a_], B[b_]], mat))
    mb._recalc(fs)
    return fs


def sail_quad(a, corners, mat='SKY_Fabric', sag=0.25, n=4, t=0.03, target=None):
    mb = MB()
    sail_mesh(mb, corners, mat, sag, n, t)
    a.part(mb, name="sail", target=target)


def door(a, face, plane, u, w=1.4, h=2.6, kind='round', frame='SKY_Pearl', leaf='SKY_Wood', depth=0.3,
         wall='SKY_Sandstone', z=0.45, steps=True):
    """Raised arched entrance: returns the Op for the wall cut, adds pearl steps and a brass knob."""
    op = Op(face, u, z, w, h, kind, depth=depth, back=leaf, sill=False, frame=frame, frame_t=0.16)
    if steps and z > 0.05:
        mb = MB()
        fbox(mb, face, plane, u - w / 2 - 0.35, u + w / 2 + 0.35, 0.0, z * 0.5, 0.05, 0.7, 'SKY_Pearl')
        fbox(mb, face, plane, u - w / 2 - 0.2, u + w / 2 + 0.2, 0.0, z, 0.05, 0.45, 'SKY_Pearl')
        a.part(mb, bevel=0.02, seg=1, name="steps")
    mb = MB()
    c = fpt(face, plane, u + w * 0.22, z + 1.05, -depth + 0.04)
    mb.cbox(c[0], c[1], c[2], 0.09 if face in 'NS' else 0.06, 0.06 if face in 'NS' else 0.09, 0.09, 'SKY_Brass')
    a.part(mb, name="knob")
    return op


def clip_seg(p0, p1, r):
    x0, y0 = p0; x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - r[0]), (dx, r[1] - x0), (-dy, y0 - r[2]), (dy, r[3] - y0)):
        if abs(p) < 1e-12:
            if q < 0:
                return None
        else:
            tt = q / p
            if p < 0:
                t0 = max(t0, tt)
            else:
                t1 = min(t1, tt)
    if t1 - t0 < 1e-3:
        return None
    return (x0 + dx * t0, y0 + dy * t0), (x0 + dx * t1, y0 + dy * t1)


def lattice_bars(mb, face, plane, rect_uv, d0, d1, mat, spacing=0.3, bw=0.045):
    """Two families of diagonal bars clipped to a (u,v) rectangle: original geometric screen."""
    u0, u1, v0, v1 = rect_uv
    hgt = v1 - v0
    k0 = int(math.floor((u0 - hgt - u1) / spacing)) - 1
    k1 = int(math.ceil((u1 + hgt - u0) / spacing)) + 1
    for fam, (dd0, dd1) in ((1, (d0, d1)), (-1, (d0 + 0.012, d1 + 0.012))):
        for k in range(k0, k1 + 1):
            c = (u0 + u1) / 2 + k * spacing
            p0 = (c - fam * hgt, v0 - 0.0)
            p1 = (c + fam * hgt * 0.0, v0 + hgt)
            p0 = (c - fam * hgt / 2, v0)
            p1 = (c + fam * hgt / 2, v1)
            seg_ = clip_seg(p0, p1, rect_uv)
            if not seg_:
                continue
            (xa, ya), (xb, yb) = seg_
            L = math.hypot(xb - xa, yb - ya)
            if L < 0.08:
                continue
            nx, ny = -(yb - ya) / L * bw / 2, (xb - xa) / L * bw / 2
            pts = [(xa - nx, ya - ny), (xb - nx, yb - ny), (xb + nx, yb + ny), (xa + nx, ya + ny)]
            fprism(mb, face, plane, pts, dd0, dd1, mat)


def lattice(a, face, plane, u, z, w, h, d=0.45, mat='SKY_Wood', frame='SKY_Pearl', spacing=0.32):
    """Projecting lattice oriel (screened bay) with pearl frame and dark backing."""
    mb = MB()
    fbox(mb, face, plane, u - w / 2 - 0.06, u + w / 2 + 0.06, z - 0.16, z, 0.0, d + 0.1, frame)
    fbox(mb, face, plane, u - w / 2 - 0.06, u + w / 2 + 0.06, z + h, z + h + 0.16, 0.0, d + 0.1, frame)
    fbox(mb, face, plane, u - w / 2, u - w / 2 + 0.1, z, z + h, 0.0, d, frame)
    fbox(mb, face, plane, u + w / 2 - 0.1, u + w / 2, z, z + h, 0.0, d, frame)
    a.part(mb, bevel=0.025, seg=1, name="lattice_frame")
    mb = MB()
    lattice_bars(mb, face, plane, (u - w / 2 + 0.1, u + w / 2 - 0.1, z, z + h), d - 0.07, d - 0.02, mat, spacing)
    a.part(mb, name="lattice")
    mb = MB()
    fbox(mb, face, plane, u - w / 2 + 0.1, u + w / 2 - 0.1, z, z + h, d - 0.32, d - 0.28, 'SKY_Ink')
    fbox(mb, face, plane, u - w / 2 + 0.1, u + w / 2 - 0.1, z, z + 0.04, 0.0, d - 0.28, frame)
    a.part(mb, name="lattice_back")


def wind_tower(a, x, y, z0, z1, s=2.0, mat='SKY_Pearl', trim='SKY_Sandstone', slots=2):
    """Slender square wind-tower-like vent with tall slots near the top on all faces."""
    hs = s / 2
    ops = []
    slot_h = min(2.4, (z1 - z0) * 0.45)
    sz = z1 - 0.5 - slot_h
    sw = (s - 0.5) / slots - 0.18
    for f in 'NSEW':
        for k in range(slots):
            c = (-hs + 0.25 + (k + 0.5) * (s - 0.5) / slots)
            uu = (x if f in 'NS' else y) + c
            ops.append(Op(f, uu, sz, sw, slot_h, 'pointed', depth=0.35, back='SKY_Ink', sill=False, seg=4))
    block(a, x - hs, x + hs, y - hs, y + hs, z0, z1, mat, ops, bevel=0.05, seg=1, name="windtower")
    mb = MB()
    mb.box(x - hs - 0.12, x + hs + 0.12, y - hs - 0.12, y + hs + 0.12, z1, z1 + 0.18, trim)
    mb.box(x - hs + 0.15, x + hs - 0.15, y - hs + 0.15, y + hs - 0.15, z1 + 0.18, z1 + 0.42, mat)
    a.part(mb, bevel=0.03, seg=1, name="windtower_cap")
    mb = MB()
    mb.box(x - hs - 0.06, x + hs + 0.06, y - hs - 0.06, y + hs + 0.06, sz - 0.25, sz - 0.12, 'SKY_Brass')
    a.part(mb, name="windtower_trim")


def dome(a, cx, cy, z, r, mat='SKY_Pearl', seg=16, rings=6, finial=True, drum_h=0.0, drum_mat='SKY_TealLight',
         onion=1.0):
    prof = []
    if drum_h > 0:
        pass
    for i in range(rings + 1):
        t = i / rings
        ang = t * math.pi / 2
        rr = r * math.cos(ang)
        zz = z + r * math.sin(ang) * onion
        prof.append((rr, zz))
    prof[-1] = (0.0, prof[-1][1])
    prof = [(0.0, z)] + prof
    mb = MB(); mb.lathe(prof, seg, mat, cx=cx, cy=cy)
    a.part(mb, name="dome")
    if finial:
        mb = MB()
        zt = z + r * onion
        mb.lathe([(0, zt - 0.05), (0.14, zt - 0.05), (0.14, zt + 0.08), (0.05, zt + 0.15), (0.11, zt + 0.32),
                  (0.03, zt + 0.5), (0.0, zt + 0.75)], 6, 'SKY_Brass', cx=cx, cy=cy)
        a.part(mb, name="finial")


def awning(a, face, plane, u, z, w, depth=1.0, drop=0.45, mats=('SKY_Coral', 'SKY_Pearl'), stripes=6,
           target=None, valance=0.26, t=0.04):
    """Sloped striped fabric awning: stripes run down the slope, with a front valance and a brass rail."""
    mb = MB()
    uax, vax, out = faxes(face)
    origin = fpt(face, plane, 0.0, 0.0, 0.0)
    origin = (origin[0] if face in ('E', 'W') else 0.0, origin[1] if face in ('N', 'S') else 0.0, 0.0)
    prof = [(0.0, z), (depth, z - drop), (depth, z - drop - valance), (depth - t, z - drop - valance),
            (depth - t, z - drop - t), (0.0, z - t)]
    for i in range(stripes):
        u0 = u - w / 2 + w * i / stripes
        u1 = u - w / 2 + w * (i + 1) / stripes
        mb.prism_frame(prof, origin, out, (0, 0, 1), uax, u0, u1, mats[i % len(mats)])
    a.part(mb, name="awning", target=target)
    mb = MB()
    fbox(mb, face, plane, u - w / 2 - 0.05, u + w / 2 + 0.05, z - 0.02, z + 0.1, 0.0, 0.1, 'SKY_Brass')
    a.part(mb, name="awning_rail", target=target)


def roof_slab(a, x0, x1, y0, y1, z, mat='SKY_Kerb', t=0.25):
    mb = MB(); mb.box(x0, x1, y0, y1, z - t, z, mat)
    a.part(mb, name="roof")


def glow_strip(a, face, plane, u0, u1, z, h=0.08, d=0.05, mat='SKY_TealGlow'):
    mb = MB(); fbox(mb, face, plane, u0, u1, z, z + h, 0.0, d, mat)
    a.part(mb, name="glow")


def solar_panels(a, x0, x1, y0, y1, z, rows=2, tilt=18.0, frame='SKY_Teal', panel='SKY_Ink'):
    mb = MB(); mbf = MB()
    dy = (y1 - y0) / rows
    for r in range(rows):
        ya, yb = y0 + r * dy + 0.15, y0 + (r + 1) * dy - 0.15
        hgt = (yb - ya) * math.tan(math.radians(tilt))
        # panel slab tilted toward Unity south (+Y) is irrelevant; tilt up toward north (-Y) side low
        pts = [(ya, z + 0.25), (yb, z + 0.25 + hgt), (yb, z + 0.33 + hgt), (ya, z + 0.33)]
        mb.prism_frame(pts, (0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), x0, x1, panel, front=frame, back=frame)
        for x in (x0 + 0.2, (x0 + x1) / 2, x1 - 0.2):
            mbf.box(x - 0.05, x + 0.05, yb - 0.1, yb, z, z + 0.25 + hgt, frame)
            mbf.box(x - 0.05, x + 0.05, ya, ya + 0.1, z, z + 0.25, frame)
    a.part(mb, bevel=0.015, seg=1, name="panels")
    a.part(mbf, name="panel_legs")


# =========================================================================== buildings

@asset("bldg_house_a", "Buildings", "buildings", ao=BLD_AO, render=BLD_RENDER)
def bldg_house_a(a):
    """2-storey courtyard house: sandstone wings around a small open courtyard, arched door,
    lattice oriel, stepped crenellation, roof terrace with a timber pergola and sail."""
    X0, X1, Y0, Y1 = -5.5, 5.5, -5.5, 5.5
    zr = 6.9              # roof
    wall = 'SKY_Sandstone'
    plinth(a, X0, X1, Y0, Y1)
    # courtyard void (x -2..2, y -1..3)
    cx0, cx1, cy0, cy1 = -2.0, 2.0, -1.0, 3.0
    # front (north) wing with door and windows
    dop = door(a, 'N', Y0, 0.0, w=1.5, h=2.8, wall=wall)
    ops = [dop,
           Op('N', -3.6, 1.1, 1.1, 1.9, 'round', frame=None),
           Op('N', 3.6, 1.1, 1.1, 1.9, 'round'),
           Op('N', -3.6, 4.2, 1.0, 1.7, 'pointed', seg=6),
           Op('N', 3.6, 4.2, 1.0, 1.7, 'pointed', seg=6),
           Op('E', -3.3, 1.1, 1.0, 1.8, 'round'), Op('E', 3.3, 1.1, 1.0, 1.8, 'round'),
           Op('E', -3.3, 4.2, 1.0, 1.7, 'pointed', seg=6), Op('E', 0.0, 4.2, 1.0, 1.7, 'pointed', seg=6),
           Op('E', 3.3, 4.2, 1.0, 1.7, 'pointed', seg=6),
           Op('W', 0.0, 1.1, 1.2, 1.8, 'round'), Op('W', -3.3, 4.2, 1.0, 1.7, 'pointed', seg=6),
           Op('W', 3.3, 4.2, 1.0, 1.7, 'pointed', seg=6),
           Op('S', -3.0, 1.1, 1.0, 1.8, 'round'), Op('S', 3.0, 1.1, 1.0, 1.8, 'round'),
           Op('S', 0.0, 4.2, 1.6, 1.8, 'round')]
    # main mass with courtyard cut as a through-cutter from the roof
    mb = MB(); mb.box(cx0, cx1, cy0, cy1, 0.25, zr + 2.0, wall)
    court = a.cutter(mb, "court")
    planes = {'N': Y0, 'S': Y1, 'E': X0, 'W': X1}
    cutters = [make_cutter(a, op, planes[op.face], wall) for op in ops] + [court]
    # courtyard-side loggia arches (cut into the inner faces) - inner faces are created by the court cutter
    mb = MB(); mb.box(X0, X1, Y0, Y1, 0.0, zr, wall, fm={'top': 'SKY_Kerb'})
    a.part(mb, bevel=0.06, seg=1, cutters=cutters, name="mass")

    deco(a, [o for o in ops if o is not dop], planes)
    deco(a, [dop], planes)
    # string course between floors and the brass/teal futurist trim
    ring_band(a, X0, X1, Y0, Y1, 3.45, 3.62, 0.07, 'SKY_Pearl', name="course")
    # courtyard floor + small planter tree
    mb = MB(); mb.box(cx0, cx1, cy0, cy1, 0.0, 0.3, 'SKY_Kerb')
    a.part(mb, name="court_floor")
    planter_at(a, 0.0, 1.0, 0.3, 1.0, 1.0, 0.55)
    # inner loggia frame (pearl columns at the courtyard corners)
    mb = MB()
    for (x, y) in ((cx0 + 0.18, cy0 + 0.18), (cx1 - 0.18, cy0 + 0.18), (cx0 + 0.18, cy1 - 0.18), (cx1 - 0.18, cy1 - 0.18)):
        mb.box(x - 0.16, x + 0.16, y - 0.16, y + 0.16, 0.3, zr, 'SKY_Pearl')
    a.part(mb, bevel=0.03, seg=1, name="court_cols")
    # lattice oriel above the door
    lattice(a, 'N', Y0, 0.0, 3.85, 2.2, 1.9, d=0.55)
    # roof: terrace floor, parapets with stepped merlons on the front
    parapet(a, X0, X1, Y0, Y1, zr, 0.75, 0.28, wall)

    merlons(a, 'N', Y0, X0 + 0.4, X1 - 0.4, zr + 0.87, h=0.55, w=0.55, gap=0.42, t=0.24, inset=0.02)
    # inner courtyard parapet
    parapet(a, cx0 - 0.25, cx1 + 0.25, cy0 - 0.25, cy1 + 0.25, zr, 0.45, 0.25, 'SKY_Pearl', faces='NSEW')
    # pergola over the rear terrace + shade sail
    pergola(a, -4.6, 4.6, 3.6, 5.0, zr, h=2.3, beam_dir='y', slats=10, sail='SKY_Fabric')
    # stair head / roof kiosk with small dome
    block(a, 2.8, 4.9, -4.9, -2.6, zr, zr + 2.4, 'SKY_Pearl',
          [Op('N', 3.85, zr + 0.05, 0.9, 2.0, 'round', back='SKY_Wood', sill=False)], bevel=0.05, seg=1, name="stairhead")
    dome(a, 3.85, -3.75, zr + 2.4, 0.85, seg=12, rings=4)
    # roof planters
    planter_at(a, -3.6, -4.4, zr + 0.05, 2.2, 0.6, 0.5)
    planter_at(a, -4.6, 1.0, zr + 0.05, 0.6, 2.0, 0.5)
    # futurist accent: thin teal glow line under the parapet coping on the front
    glow_strip(a, 'N', Y0, X0 + 0.2, X1 - 0.2, zr - 0.25, h=0.07, d=0.04)


def balcony(a, face, plane, u, z, w, d=1.0, rail='SKY_Brass', glass='SKY_TealLight'):
    mb = MB()
    fbox(mb, face, plane, u - w / 2, u + w / 2, z - 0.22, z, 0.0, d, 'SKY_Pearl')
    a.part(mb, bevel=0.03, seg=1, name="balcony_slab")
    mb = MB()
    # brass rail on three sides + teal glass panels
    fbox(mb, face, plane, u - w / 2 + 0.05, u + w / 2 - 0.05, z + 0.95, z + 1.02, d - 0.1, d - 0.03, rail)
    fbox(mb, face, plane, u - w / 2 + 0.05, u - w / 2 + 0.12, z + 0.95, z + 1.02, 0.0, d - 0.03, rail)
    fbox(mb, face, plane, u + w / 2 - 0.12, u + w / 2 - 0.05, z + 0.95, z + 1.02, 0.0, d - 0.03, rail)
    for uu in (u - w / 2 + 0.085, u + w / 2 - 0.085):
        fbox(mb, face, plane, uu - 0.035, uu + 0.035, z, z + 0.95, d - 0.1, d - 0.03, rail)
    a.part(mb, name="balcony_rail")
    mb = MB()
    fbox(mb, face, plane, u - w / 2 + 0.12, u + w / 2 - 0.12, z + 0.1, z + 0.9, d - 0.085, d - 0.05, glass)
    fbox(mb, face, plane, u - w / 2 + 0.07, u - w / 2 + 0.1, z + 0.1, z + 0.9, 0.05, d - 0.12, glass)
    fbox(mb, face, plane, u + w / 2 - 0.1, u + w / 2 - 0.07, z + 0.1, z + 0.9, 0.05, d - 0.12, glass)
    a.part(mb, name="balcony_glass")


def shutters(a, face, plane, u, z, w, h, mat='SKY_Teal'):
    mb = MB()
    for s in (-1, 1):
        fbox(mb, face, plane, u + s * (w / 2 + 0.06) - 0.2, u + s * (w / 2 + 0.06) + 0.2, z, z + h * 0.82,
             0.0, 0.05, mat)
    a.part(mb, name="shutters")


@asset("bldg_house_b", "Buildings", "buildings", ao=BLD_AO, render=BLD_RENDER)
def bldg_house_b(a):
    """3-storey pearl town house: balconies with teal glass, a slender wind-tower vent, brass trims."""
    X0, X1, Y0, Y1 = -4.8, 4.8, -5.0, 5.0
    zr = 10.3
    wall = 'SKY_Pearl'
    f1, f2 = 3.75, 7.05
    plinth(a, X0, X1, Y0, Y1, mat='SKY_Sandstone')
    dop = door(a, 'N', Y0, -2.0, w=1.3, h=2.55, frame='SKY_Sandstone', leaf='SKY_Teal', wall=wall)
    ops = [dop, Op('N', 2.2, 1.05, 1.3, 1.8, 'round'),
           Op('N', 0.0, f1, 1.5, 2.35, 'round', back='SKY_Glass', sill=False),
           Op('N', 0.0, f2, 1.5, 2.35, 'round', back='SKY_Glass', sill=False),
           Op('N', -3.4, f1 + 0.5, 0.9, 1.6, 'round'), Op('N', 3.4, f1 + 0.5, 0.9, 1.6, 'round'),
           Op('N', -3.4, f2 + 0.5, 0.9, 1.6, 'round'), Op('N', 3.4, f2 + 0.5, 0.9, 1.6, 'round')]
    for f in ('E', 'W'):
        for zz in (1.05, f1 + 0.45, f2 + 0.45):
            for uu in (-2.2, 2.2):
                ops.append(Op(f, uu, zz, 1.0, 1.7, 'round'))
    for zz in (1.05, f1 + 0.45, f2 + 0.45):
        ops.append(Op('S', -2.0, zz, 1.0, 1.7, 'round'))
        ops.append(Op('S', 2.0, zz, 1.0, 1.7, 'round'))
    planes = block(a, X0, X1, Y0, Y1, 0.0, zr, wall, ops, bevel=0.06, name="mass", fm={'top': 'SKY_Kerb'})
    for zz in (f1 - 0.25, f2 - 0.25):
        ring_band(a, X0, X1, Y0, Y1, zz, zz + 0.16, 0.06, 'SKY_Sandstone', name="course")
    ring_band(a, X0, X1, Y0, Y1, zr - 0.55, zr - 0.47, 0.04, 'SKY_Brass', name="brass")
    balcony(a, 'N', Y0, 0.0, f1, 2.6)
    balcony(a, 'N', Y0, 0.0, f2, 2.6)
    for zz in (f1 + 0.5, f2 + 0.5):
        shutters(a, 'N', Y0, -3.4, zz, 0.9, 1.6)
        shutters(a, 'N', Y0, 3.4, zz, 0.9, 1.6)
    # stepped central parapet on the front, plain elsewhere
    parapet(a, X0, X1, Y0, Y1, zr, 0.8, 0.26, wall, cap='SKY_Sandstone')
    mb = MB()
    fbox(mb, 'N', Y0, -1.6, 1.6, zr + 0.92, zr + 1.45, -0.26, 0.0, wall)
    fbox(mb, 'N', Y0, -0.8, 0.8, zr + 1.45, zr + 1.9, -0.26, 0.0, wall)
    a.part(mb, bevel=0.03, seg=1, name="crest")
    mb = MB()
    fbox(mb, 'N', Y0, -1.66, 1.66, zr + 1.45, zr + 1.52, -0.3, 0.04, 'SKY_Sandstone')
    fbox(mb, 'N', Y0, -0.86, 0.86, zr + 1.9, zr + 1.98, -0.3, 0.04, 'SKY_Sandstone')
    a.part(mb, name="crest_caps")
    wind_tower(a, -3.4, 3.6, zr, zr + 4.3, s=2.0)
    # roof: planters and a slim teal-glow line on the crest
    planter_at(a, 2.6, 3.8, zr, 2.8, 0.7, 0.5)
    planter_at(a, 3.9, -1.0, zr, 0.7, 2.4, 0.5)
    glow_strip(a, 'N', Y0 - 0.0, -1.5, 1.5, zr + 1.0, h=0.06, d=0.03)


@asset("bldg_shoprow", "Buildings", "buildings", ao=BLD_AO, render=BLD_RENDER)
def bldg_shoprow(a):
    """2-storey shop row: arched arcade at street level over glazed shopfronts, coral/teal awnings above."""
    X0, X1, Y0, Y1 = -6.0, 6.0, -4.5, 4.5
    Ya = Y0 + 2.1                    # shopfront line behind the arcade
    z1, zr = 4.1, 7.7
    wall = 'SKY_Sandstone'
    plinth(a, X0, X1, Ya, Y1, h=0.35)
    # ground floor (behind the arcade): big glazed shopfronts with teal frames and doors
    ops = []
    xs = [-4.5, -1.5, 1.5, 4.5]
    for i, x in enumerate(xs):
        ops.append(Op('N', x, 0.35, 2.3, 2.9, 'segment', depth=0.25, back='SKY_Glass', sill=False,
                      frame='SKY_Teal', frame_t=0.1, mullion='SKY_Teal'))
    ops += [Op('E', 0.5, 1.0, 1.0, 1.8, 'round'), Op('W', 0.5, 1.0, 1.0, 1.8, 'round'),
            Op('S', -3.0, 0.35, 1.2, 2.4, 'round', back='SKY_Wood', sill=False), Op('S', 3.0, 1.0, 1.1, 1.8, 'round')]
    block(a, X0, X1, Ya, Y1, 0.0, z1, wall, ops, name="ground")
    # arcade front wall with through arches, carrying the upper floor
    arc_ops = [Op('N', x, 0.0, 2.25, 3.35, 'pointed', through=True, sill=False, back=wall, seg=6, frame='SKY_Pearl',
                  frame_t=0.14) for x in xs]
    planes = {'N': Y0, 'S': Ya, 'E': X0, 'W': X1}
    cuts = [make_cutter(a, op, planes[op.face], 'SKY_Pearl') for op in arc_ops]
    mb = MB()
    mb.box(X0, X1, Y0, Y0 + 0.55, 0.0, z1, 'SKY_Pearl')
    a.part(mb, bevel=0.05, seg=1, cutters=cuts, name="arcade")
    deco(a, arc_ops, planes)
    # end walls of the arcade, each pierced by its own side arch (separate closed solids -> clean booleans)
    for f, x0_, x1_ in (('E', X0, X0 + 0.55), ('W', X1 - 0.55, X1)):
        op = Op(f, (Y0 + 0.55 + Ya) / 2, -0.05, 1.0, 2.85, 'round', depth=1.2, through=False, sill=False, back=wall)
        c = make_cutter(a, op, planes[f], 'SKY_Pearl')
        mb = MB()
        mb.box(x0_, x1_, Y0 + 0.55, Ya, 0.0, z1, 'SKY_Pearl')
        a.part(mb, bevel=0.05, seg=1, cutters=[c], name="arcade_end")
    # arcade floor and soffit glow
    mb = MB(); mb.box(X0 + 0.55, X1 - 0.55, Y0 + 0.55, Ya, 0.0, 0.12, 'SKY_Kerb')
    a.part(mb, name="arcade_floor")
    mb = MB(); mb.box(X0 + 0.6, X1 - 0.6, Ya - 0.06, Ya, z1 - 0.32, z1 - 0.24, 'SKY_TealGlow')
    a.part(mb, name="glow")
    # upper floor
    up_ops = []
    for x in xs:
        up_ops.append(Op('N', x, z1 + 0.75, 1.15, 1.9, 'round', frame='SKY_Pearl', frame_t=0.1))
    for f in ('E', 'W'):
        up_ops += [Op(f, -1.8, z1 + 0.75, 1.0, 1.8, 'round'), Op(f, 1.8, z1 + 0.75, 1.0, 1.8, 'round')]
    up_ops += [Op('S', x, z1 + 0.75, 1.0, 1.8, 'round') for x in (-3.0, 0.0, 3.0)]
    block(a, X0, X1, Y0, Y1, z1, zr, wall, up_ops, name="upper", fm={'top': 'SKY_Kerb'})
    ring_band(a, X0, X1, Y0, Y1, z1, z1 + 0.22, 0.07, 'SKY_Pearl', name="course")
    for i, x in enumerate(xs):
        mats = ('SKY_Coral', 'SKY_Pearl') if i % 2 == 0 else ('SKY_Teal', 'SKY_Pearl')
        awning(a, 'N', Y0, x, z1 + 2.95, 1.6, depth=0.85, drop=0.4, mats=mats, stripes=5)
    # parapet with piers over the arcade columns
    parapet(a, X0, X1, Y0, Y1, zr, 0.7, 0.26, wall)
    mb = MB()
    for x in (-6.0 + 0.3, -3.0, 0.0, 3.0, 6.0 - 0.3):
        fbox(mb, 'N', Y0, x - 0.3, x + 0.3, zr, zr + 1.25, -0.4, 0.06, 'SKY_Pearl')
    a.part(mb, bevel=0.03, seg=1, name="piers")
    mb = MB()
    for x in (-6.0 + 0.3, -3.0, 0.0, 3.0, 6.0 - 0.3):
        c = fpt('N', Y0, x, zr + 1.25, 0.17)
        mb.lathe([(0, c[2]), (0.22, c[2]), (0.12, c[2] + 0.18), (0, c[2] + 0.3)], 6, 'SKY_Brass', cx=c[0], cy=c[1])
    a.part(mb, name="pier_caps")
    # roof terrace: shade sail on masts + planters
    mb = MB()
    for (x, y) in ((-4.8, 0.6), (-0.6, 3.6), (-4.6, 3.8)):
        mb.cyl(0.07, zr, zr + 2.6, 6, 'SKY_Brass', cx=x, cy=y)
    a.part(mb, name="masts")
    sail_quad(a, [(-4.8, 0.6, zr + 2.5), (-0.6, 3.6, zr + 2.3), (-4.6, 3.8, zr + 2.6)], sag=0.15, n=3)
    planter_at(a, 3.5, 3.6, zr, 3.2, 0.7, 0.5)


def loft_outline(a, outline, profile, cap_top='SKY_Kerb', name="shell", bevel=0.0):
    """profile: list of (offset_out, z, mat_of_band_above). Rings offset from a CCW outline."""
    rings, mats = [], []
    for i, (off, z, m) in enumerate(profile):
        ring2 = offset_line(outline, -off, closed=True) if abs(off) > 1e-6 else outline
        rings.append([(p[0], p[1], z) for p in ring2])
        if i < len(profile) - 1:
            mats.append(m)
    mb = MB()
    mb.loft(rings, mats[0], mats=mats + [cap_top])
    a.part(mb, bevel=bevel, seg=1, name=name)


@asset("bldg_tower", "Buildings", "buildings", ao=BLD_AO, render=dict(BLD_RENDER, el=20.0))
def bldg_tower(a):
    """5-storey residential tower: rounded corners, pearl slab bands with brass trims, recessed teal glass."""
    W, D, R = 11.0, 10.4, 2.6
    outline = ccw(rrect(W, D, R, seg=6))
    prof = [(0.1, 0.0, 'SKY_SandstoneDeep'), (0.1, 0.55, 'SKY_SandstoneDeep'), (0.0, 0.55, 'SKY_Pearl')]
    fh = 3.4
    z = 0.55
    for f in range(5):
        zs = z + f * fh
        top_slab = zs + 0.95
        prof += [(0.0, top_slab - 0.12, 'SKY_Brass'), (0.05, top_slab - 0.12, 'SKY_Brass'),
                 (0.05, top_slab - 0.04, 'SKY_Brass'), (0.0, top_slab - 0.04, 'SKY_Pearl'),
                 (0.0, top_slab, 'SKY_Pearl'), (-0.28, top_slab, 'SKY_TealLight'),
                 (-0.28, zs + fh, 'SKY_Pearl'), (0.0, zs + fh, 'SKY_Pearl')]
    ztop = z + 5 * fh
    prof += [(0.0, ztop + 1.0, 'SKY_Pearl'), (0.08, ztop + 1.0, 'SKY_Brass'), (0.08, ztop + 1.12, 'SKY_Brass'),
             (-0.25, ztop + 1.12, 'SKY_Kerb'), (-0.25, ztop + 0.3, 'SKY_Kerb')]
    loft_outline(a, outline, prof, cap_top='SKY_Kerb', name="shell")
    # vertical pearl fins across the glass bands (straight runs only)
    mb = MB()
    hw = D / 2
    for f in range(5):
        zs = z + f * fh
        z0, z1 = zs + 0.95, zs + fh
        for face in 'NSEW':
            pl = {'N': -D / 2, 'S': D / 2, 'E': -W / 2, 'W': W / 2}[face]
            us = (-2.0, -0.7, 0.7, 2.0) if face in 'NS' else (-1.7, -0.6, 0.6, 1.7)
            for uu in us:
                fbox(mb, face, pl, uu - 0.07, uu + 0.07, z0, z1, -0.28, 0.0, 'SKY_Pearl')
    a.part(mb, name="fins")
    # entrance portal on the north side
    mb = MB()
    band = shift_uv(arch_band(2.4, 3.3, 0.35, 'round', 8), 0.0, 0.0)
    fprism(mb, 'N', -hw, band, 0.0, 0.7, 'SKY_Pearl')
    a.part(mb, bevel=0.04, seg=1, name="portal")
    mb = MB()
    fbox(mb, 'N', -hw, -1.2, 1.2, 0.0, 0.12, 0.0, 0.78, 'SKY_Pearl')
    fbox(mb, 'N', -hw, -1.75, 1.75, 3.65, 3.85, -0.1, 0.78, 'SKY_Brass')
    a.part(mb, bevel=0.02, seg=1, name="canopy")
    mb = MB()
    fbox(mb, 'N', -hw, -1.6, 1.6, 3.6, 3.65, 0.0, 0.74, 'SKY_TealGlow')
    a.part(mb, name="glow")
    # rooftop pavilion with pergola and planters
    rz = ztop + 0.3
    block(a, -2.2, 1.2, 0.8, 3.8, rz, rz + 2.6, 'SKY_Pearl',
          [Op('N', -0.5, rz + 0.05, 1.0, 2.1, 'round', back='SKY_Glass', sill=False)], name="pavilion",
          fm={'top': 'SKY_Kerb'})
    ring_band(a, -2.2, 1.2, 0.8, 3.8, rz + 2.6, rz + 2.75, 0.08, 'SKY_Brass', name="pav_cap")
    pergola(a, -3.2, 2.6, -3.4, -0.4, rz, h=2.4, beam_dir='x', slats=9, sail='SKY_Fabric')
    planter_at(a, 3.4, 1.5, rz, 0.7, 3.2, 0.5)


@asset("bldg_dome", "Buildings", "buildings", ao=BLD_AO, render=BLD_RENDER)
def bldg_dome(a):
    """Small civic hall: pearl cube with tall arched windows, columned portico, teal-glazed drum and dome."""
    X0, X1, Y0, Y1 = -4.6, 4.6, -3.2, 5.6
    zr = 6.6
    wall = 'SKY_Pearl'
    plinth(a, X0, X1, Y0, Y1, h=0.6, mat='SKY_Sandstone')
    dop = door(a, 'N', Y0, 0.0, w=1.8, h=3.4, frame='SKY_Sandstone', z=0.6, steps=False)
    ops = [dop]
    for f in ('E', 'W'):
        for uu in (-1.8, 0.8, 3.4):
            ops.append(Op(f, uu, 1.5, 1.2, 3.3, 'round', frame='SKY_Sandstone', frame_t=0.12))
    for uu in (-2.6, 0.0, 2.6):
        ops.append(Op('S', uu, 1.5, 1.2, 3.3, 'round', frame='SKY_Sandstone', frame_t=0.12))
    for uu in (-3.1, 3.1):
        ops.append(Op('N', uu, 1.5, 0.9, 2.6, 'round', frame='SKY_Sandstone', frame_t=0.1))
    block(a, X0, X1, Y0, Y1, 0.0, zr, wall, ops, name="hall", fm={'top': 'SKY_Kerb'})
    ring_band(a, X0, X1, Y0, Y1, zr - 0.6, zr - 0.35, 0.08, 'SKY_Sandstone', name="frieze")
    ring_band(a, X0, X1, Y0, Y1, zr - 0.3, zr - 0.22, 0.05, 'SKY_Brass', name="brass")
    parapet(a, X0, X1, Y0, Y1, zr, 0.6, 0.25, wall, cap='SKY_Sandstone')
    # portico: steps, 4 columns, entablature, pediment-free flat cornice
    py0, py1 = Y0 - 2.0, Y0
    mb = MB()
    mb.box(-3.3, 3.3, py0 - 0.9, py1, 0.0, 0.2, 'SKY_Sandstone')
    mb.box(-3.1, 3.1, py0 - 0.45, py1, 0.0, 0.4, 'SKY_Sandstone')
    mb.box(-2.9, 2.9, py0, py1, 0.0, 0.6, 'SKY_Sandstone')
    a.part(mb, bevel=0.03, seg=1, name="portico_steps")
    mb = MB()
    for x in (-2.4, -0.8, 0.8, 2.4):
        mb.lathe([(0, 0.6), (0.36, 0.6), (0.36, 0.78), (0.27, 0.86), (0.24, 4.6), (0.32, 4.72), (0.36, 4.86),
                  (0, 4.86)], 12, 'SKY_Pearl', cx=x, cy=py0 + 0.45)
    a.part(mb, name="columns")
    mb = MB()
    mb.box(-3.0, 3.0, py0 - 0.05, py1, 4.86, 5.6, 'SKY_Pearl')
    a.part(mb, bevel=0.05, seg=1, name="entablature")
    mb = MB()
    mb.box(-3.12, 3.12, py0 - 0.17, py1, 5.6, 5.72, 'SKY_Brass')
    mb.box(-2.7, 2.7, py0 + 0.1, py1, 5.72, 6.3, 'SKY_Pearl')
    a.part(mb, bevel=0.02, seg=1, name="cornice")
    mb = MB()
    mb.box(-2.9, 2.9, py0 + 0.0, py0 + 0.06, 4.95, 5.03, 'SKY_TealGlow')
    a.part(mb, name="glow")
    # drum with teal glass band, dome, finial
    cx, cy = 0.0, (Y0 + Y1) / 2
    mb = MB()
    mb.lathe([(0, zr), (3.25, zr), (3.25, zr + 0.5), (3.05, zr + 0.5), (3.05, zr + 0.55)], 16, 'SKY_Sandstone',
             cx=cx, cy=cy)
    a.part(mb, name="drum_base")
    mb = MB()
    mb.lathe([(0, zr + 0.5), (2.9, zr + 0.5), (2.9, zr + 1.55), (0, zr + 1.55)], 16, 'SKY_TealLight', cx=cx, cy=cy)
    a.part(mb, name="drum_glass")
    mb = MB()
    for k in range(16):
        ang = 2 * math.pi * (k + 0.5) / 16
        x, y = cx + 2.95 * math.cos(ang), cy + 2.95 * math.sin(ang)
        mb.cbox(x, y, zr + 1.02, 0.16, 0.16, 1.05, 'SKY_Pearl')
    a.part(mb, name="drum_piers")
    mb = MB()
    mb.lathe([(0, zr + 1.55), (3.12, zr + 1.55), (3.12, zr + 1.75), (0, zr + 1.75)], 16, 'SKY_Brass', cx=cx, cy=cy)
    a.part(mb, name="drum_cap")
    dome(a, cx, cy, zr + 1.75, 2.85, seg=16, rings=6, onion=1.05)
    # corner pinnacles
    mb = MB()
    for (x, y) in ((X0 + 0.35, Y0 + 0.35), (X1 - 0.35, Y0 + 0.35), (X0 + 0.35, Y1 - 0.35), (X1 - 0.35, Y1 - 0.35)):
        mb.box(x - 0.32, x + 0.32, y - 0.32, y + 0.32, zr + 0.6, zr + 1.5, 'SKY_Pearl')
        mb.lathe([(0, zr + 1.5), (0.36, zr + 1.5), (0.32, zr + 1.62), (0.2, zr + 1.85), (0.06, zr + 2.05),
                  (0, zr + 2.15)], 8, 'SKY_Sandstone', cx=x, cy=y)
    a.part(mb, name="pinnacles")


@asset("bldg_courtyard", "Buildings", "buildings", ao=BLD_AO, render=dict(BLD_RENDER, az=42.0, el=30.0))
def bldg_courtyard(a):
    """L-shaped 2-storey house around a shaded courtyard (palm, fountain, sail) open to Unity N/W."""
    from env_nature import palm
    zr = 7.0
    wall = 'SKY_Sandstone'
    # wing A along the Unity south (Blender +Y): x -6..6, y 1.5..6 ; wing B along Unity east (Blender -X)
    A = (-6.0, 6.0, 1.5, 6.0)
    B = (-6.0, -1.5, -5.4, 1.5)
    plinth(a, *A)
    plinth(a, B[0], B[1], B[2], A[2])
    opsA = [Op('N', x, 0.35, 1.7, 2.9, 'round', depth=1.4, back=wall, sill=False, frame='SKY_Pearl', frame_t=0.12)
            for x in (0.5, 2.6, 4.7)]
    opsA += [Op('N', x, 4.0, 1.0, 1.75, 'pointed', seg=4) for x in (0.5, 2.6, 4.7)]
    opsA += [Op('S', x, z, 1.0, 1.75, 'round') for x in (-3.0, 3.0) for z in (1.0, 4.0)]
    opsA += [Op('W', 3.75, 1.0, 1.0, 1.75, 'round'), Op('W', 3.75, 4.0, 1.0, 1.75, 'pointed', seg=4)]
    opsA += [Op('E', 3.75, 4.0, 1.0, 1.75, 'round')]
    block(a, A[0], A[1], A[2], A[3], 0.0, zr, wall, opsA, name="wingA", fm={'top': 'SKY_Kerb'})
    opsB = [Op('W', y, 0.35, 1.7, 2.9, 'round', depth=1.4, back=wall, sill=False, frame='SKY_Pearl', frame_t=0.12)
            for y in (-4.3, -2.2)]
    opsB += [Op('W', y, 4.0, 1.0, 1.75, 'pointed', seg=4) for y in (-4.3, -2.2, -0.1)]
    opsB += [Op('E', y, z, 1.0, 1.75, 'round') for y in (-4.0, -0.5) for z in (1.0, 4.0)]
    dop = door(a, 'N', B[2], -3.75, w=1.4, h=2.6, wall=wall)
    opsB += [dop, Op('N', -3.75, 4.0, 1.2, 1.75, 'round')]
    block(a, B[0], B[1], B[2], A[2], 0.0, zr, wall, opsB, name="wingB", fm={'top': 'SKY_Kerb'})
    ring_band(a, *A, 3.45, 3.62, 0.07, 'SKY_Pearl', name="courseA")
    ring_band(a, B[0], B[1], B[2], A[2], 3.45, 3.62, 0.07, 'SKY_Pearl', name="courseB")
    parapet(a, *A, zr, 0.7, 0.26, wall)
    parapet(a, B[0], B[1], B[2], A[2] + 0.26, zr, 0.7, 0.26, wall, faces='NEW')
    merlons(a, 'N', B[2], B[0] + 0.3, B[1] - 0.3, zr + 0.82, h=0.5, w=0.5, gap=0.4, t=0.22, inset=0.02)
    merlons(a, 'W', A[1], A[2] + 0.3, A[3] - 0.3, zr + 0.82, h=0.5, w=0.5, gap=0.4, t=0.22, inset=0.02)
    # courtyard: paving, low perimeter wall with gate on Unity N and W, fountain, palm, sail, planters
    cx0, cx1, cy0, cy1 = -1.5, 6.0, -5.4, 1.5
    mb = MB(); mb.box(cx0, cx1, cy0, cy1, 0.0, 0.12, 'SKY_Kerb')
    a.part(mb, name="court_paving")
    gx, gw, gt = 2.8, 1.6, 0.35
    mb = MB()
    mb.box(cx0, gx - gw / 2 - gt, cy0, cy0 + 0.35, 0.0, 1.5, 'SKY_Sandstone')
    mb.box(gx + gw / 2 + gt, cx1, cy0, cy0 + 0.35, 0.0, 1.5, 'SKY_Sandstone')
    mb.box(cx1 - 0.35, cx1, cy0 + 0.35, cy1, 0.0, 1.5, 'SKY_Sandstone')
    a.part(mb, bevel=0.04, seg=1, name="court_walls")
    mb = MB()
    fprism(mb, 'N', cy0, shift_uv(arch_band(gw, 2.3, gt, 'round', 8), gx, 0.0), -0.4, 0.05, 'SKY_Pearl')
    a.part(mb, bevel=0.03, seg=1, name="gate")
    mb = MB()
    mb.box(cx0, gx - gw / 2 - gt, cy0 - 0.05, cy0 + 0.4, 1.5, 1.62, 'SKY_Pearl')
    mb.box(gx + gw / 2 + gt, cx1 + 0.05, cy0 - 0.05, cy0 + 0.4, 1.5, 1.62, 'SKY_Pearl')
    mb.box(cx1 - 0.4, cx1 + 0.05, cy0 + 0.4, cy1, 1.5, 1.62, 'SKY_Pearl')
    a.part(mb, bevel=0.025, seg=1, name="court_wall_caps")
    # fountain
    fx, fy = 2.6, -2.4
    mb = MB()
    mb.lathe([(0, 0.12), (1.25, 0.12), (1.25, 0.55), (1.08, 0.55), (1.08, 0.4), (0, 0.4)], 16, 'SKY_Pearl', cx=fx, cy=fy)
    a.part(mb, name="fountain_basin")
    mb = MB()
    mb.lathe([(0, 0.4), (1.09, 0.4), (1.09, 0.47), (0, 0.47)], 16, 'SKY_TealLight', cx=fx, cy=fy)
    a.part(mb, name="fountain_water")
    mb = MB()
    mb.lathe([(0, 0.47), (0.16, 0.47), (0.12, 0.9), (0.45, 1.05), (0.42, 1.12), (0.1, 1.08), (0.08, 1.35),
              (0.0, 1.42)], 10, 'SKY_Pearl', cx=fx, cy=fy)
    a.part(mb, name="fountain_jet")
    mb = MB()
    mb.lathe([(0, 1.05), (0.4, 1.05), (0, 1.1)], 10, 'SKY_TealLight', cx=fx, cy=fy)
    a.part(mb, name="fountain_bowl_water")
    # palm (separate shell parts merged into the building mesh)
    palm(a, x=3.7, y=-0.6, z=0.12, height=4.4, lean=(0.3, -0.3), fronds=9, frond_len=2.25, r0=0.26, r1=0.18,
         seed=21, dates=False, frond_seg=6, trunk_seg=8, sides=7)
    a.set_target(a.name, weighted=True, smooth=48.0)
    mb = MB()
    mb.lathe([(0, 0.12), (0.55, 0.12), (0.55, 0.45), (0, 0.45)], 10, 'SKY_SandstoneDeep', cx=3.7, cy=-0.6)

    a.part(mb, name="palm_bed")
    # shade sail from the wing corners to a brass mast
    mb = MB()
    mb.cyl(0.08, 0.12, 4.1, 6, 'SKY_Brass', cx=5.5, cy=-5.0)
    a.part(mb, name="mast")
    sail_quad(a, [(-1.4, -5.0, 4.6), (5.5, -5.0, 4.0), (-1.4, 1.4, 5.0)], sag=0.2, n=4)
    planter_at(a, -0.9, -4.7, 0.12, 0.8, 0.8, 0.55)
    planter_at(a, 0.6, 1.0, 0.12, 2.0, 0.7, 0.5)


@asset("bldg_depot", "Buildings", "poi", ao=BLD_AO, render=BLD_RENDER)
def bldg_depot(a):
    """Courier depot garage: big open door facing Unity north, teal accents, solar canopy over the
    front-right apron (viewer's right = Blender +X) where ANCHOR_cell_dock sits."""
    HX0, HX1, Y0, Y1 = -6.0, 2.4, -3.0, 6.0
    zh = 6.0
    wall = 'SKY_Sandstone'
    mb = MB()
    p_, h_ = 0.08, 0.3
    mb.box(HX0 - p_, HX1, Y1 - 0.3, Y1 + p_, 0.0, h_, 'SKY_SandstoneDeep')
    mb.box(HX0 - p_, HX0 + 0.3, Y0 - p_, Y1, 0.0, h_, 'SKY_SandstoneDeep')
    a.part(mb, bevel=0.04, seg=1, name="plinth")
    big = Op('N', -1.8, 0.02, 6.0, 4.7, 'segment', depth=8.4, back='SKY_Kerb', sill=False, frame='SKY_Teal',
             frame_t=0.22, reveal='SKY_Kerb')
    ops = [big, Op('E', 0.5, 1.4, 1.0, 1.8, 'round'), Op('E', 3.5, 1.4, 1.0, 1.8, 'round'),
           Op('S', -3.5, 1.4, 1.2, 1.8, 'round'), Op('S', 0.2, 1.4, 1.2, 1.8, 'round')]
    block(a, HX0, HX1, Y0, Y1, 0.0, zh, wall, ops, name="hall", fm={'top': 'SKY_Kerb'})
    # rolled-up teal door + glow strip over the opening
    mb = MB()
    fbox(mb, 'N', Y0, -1.8 - 3.0, -1.8 + 3.0, 4.15, 4.68, -0.75, -0.25, 'SKY_Teal')
    a.part(mb, bevel=0.03, seg=1, name="roller")
    glow_strip(a, 'N', Y0, -1.8 - 3.2, -1.8 + 3.2, 5.35, h=0.1, d=0.06)
    mb = MB()
    fbox(mb, 'N', Y0, -5.95, 2.35, zh - 0.75, zh - 0.5, 0.0, 0.06, 'SKY_Teal')
    for f, pl, u0, u1 in (('E', HX0, Y0 + 0.05, Y1 - 0.05), ('S', Y1, HX0 + 0.05, HX1 - 0.05)):
        fbox(mb, f, pl, u0, u1, zh - 0.75, zh - 0.5, 0.0, 0.06, 'SKY_Teal')
    a.part(mb, name="teal_band")
    # interior details visible through the door: workbench + shelving
    mb = MB()
    mb.box(-4.4, 0.8, 4.75, 5.35, 0.02, 1.0, 'SKY_Teal')
    mb.box(-4.4, 0.8, 5.05, 5.35, 1.0, 2.6, 'SKY_Ink')
    a.part(mb, bevel=0.02, seg=1, name="interior")
    parapet(a, HX0, HX1, Y0, Y1, zh, 0.6, 0.25, wall, cap='SKY_Pearl')
    solar_panels(a, HX0 + 0.6, HX1 - 0.6, Y0 + 1.0, Y1 - 0.8, zh, rows=3)
    # office annex (2 storeys) on Blender +X
    AX0, AX1 = 2.4, 6.0
    aops = [Op('N', 4.2, 0.3, 1.1, 2.4, 'round', back='SKY_Teal', sill=False, frame='SKY_Pearl', frame_t=0.12),
            Op('N', 4.2, 3.9, 1.6, 1.8, 'round'), Op('W', -1.5, 1.2, 1.0, 1.7, 'round'),
            Op('W', 2.0, 1.2, 1.0, 1.7, 'round'), Op('W', -1.5, 3.9, 1.0, 1.7, 'round'),
            Op('W', 2.0, 3.9, 1.0, 1.7, 'round'), Op('S', 4.2, 3.9, 1.0, 1.7, 'round')]
    plinth(a, AX0, AX1, Y0, Y1, h=0.3)
    block(a, AX0, AX1, Y0, Y1, 0.0, 7.2, 'SKY_Pearl', aops, name="annex", fm={'top': 'SKY_Kerb'})
    ring_band(a, AX0, AX1, Y0, Y1, 3.45, 3.6, 0.06, 'SKY_Teal', name="annex_band")
    parapet(a, AX0, AX1, Y0, Y1, 7.2, 0.6, 0.22, 'SKY_Pearl', cap='SKY_Teal')
    # solar canopy over the front-right apron (dock bay)
    mb = MB()
    for (x, y) in ((2.8, -5.7), (5.75, -5.7)):
        mb.box(x - 0.1, x + 0.1, y - 0.1, y + 0.1, 0.0, 3.05, 'SKY_Pearl')
    a.part(mb, bevel=0.02, seg=1, name="canopy_posts")
    mb = MB()
    mb.box(2.5, 6.0, -5.95, Y0, 3.05, 3.25, 'SKY_Teal')
    a.part(mb, bevel=0.03, seg=1, name="canopy_frame")
    mb = MB()
    pts = [(-5.9, 3.25), (Y0, 3.25), (Y0, 3.6), (-5.9, 3.32)]
    mb.prism_frame(pts, (0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), 2.6, 5.9, 'SKY_Ink', front='SKY_Teal',
                   back='SKY_Teal')
    a.part(mb, bevel=0.015, seg=1, name="canopy_panels")
    mb = MB()
    mb.box(2.6, 5.9, -5.98, -5.92, 3.0, 3.06, 'SKY_TealGlow')
    a.part(mb, name="canopy_glow")
    a.empty("ANCHOR_cell_dock", (4.4, -4.8, 0.0))
    a.notes.append("ANCHOR_cell_dock under the solar canopy at the front-right (viewer facing the door; Unity -X side).")


def transformer(a, x, y, flip=1):
    mb = MB()
    mb.box(x - 1.15, x + 1.15, y - 0.95, y + 0.95, 0.0, 0.3, 'SKY_Kerb')
    a.part(mb, bevel=0.03, seg=1, name="pad")
    mb = MB()
    n = 10
    for i in range(n):
        x0 = x - 1.15 + 2.3 * i / n
        x1 = x - 1.15 + 2.3 * (i + 1) / n
        m = 'SKY_Coral' if i % 2 == 0 else 'SKY_Pearl'
        mb.box(x0, x1, y - 0.97, y - 0.93, 0.05, 0.25, m)
        mb.box(x0, x1, y + 0.93, y + 0.97, 0.05, 0.25, m)
    a.part(mb, name="hazard_stripes")
    mb = MB()
    mb.box(x - 0.75, x + 0.75, y - 0.6, y + 0.6, 0.3, 2.1, 'SKY_Metal')
    a.part(mb, bevel=0.04, seg=1, name="tank")
    mb = MB()
    for side in (-1, 1):
        for k in range(6):
            yy = y - 0.5 + k * 0.2
            mb.box(x + side * 0.75, x + side * 1.05, yy - 0.03, yy + 0.03, 0.45, 1.85, 'SKY_Metal')
    a.part(mb, name="fins")
    mb = MB()
    for k in (-0.4, 0.0, 0.4):
        cxx, cyy = x + k, y
        mb.lathe([(0, 2.1), (0.1, 2.1), (0.1, 2.2), (0.14, 2.25), (0.08, 2.35), (0.13, 2.42), (0.07, 2.52),
                  (0.11, 2.6), (0.0, 2.68)], 6, 'SKY_Pearl', cx=cxx, cy=cyy)
    a.part(mb, name="bushings")


@asset("bldg_substation", "Buildings", "poi", ao=BLD_AO, render=dict(BLD_RENDER, az=25.0))
def bldg_substation(a):
    """Compact airfield substation: pearl switch house with a recessed cell socket on its north face,
    two finned transformers with coral hazard stripes, conduits, and the PowerLights bar."""
    X0, X1, Y0, Y1 = -2.8, 2.8, -1.6, 2.6
    zr = 3.6
    plinth(a, X0, X1, Y0, Y1, h=0.3, mat='SKY_SandstoneDeep')
    sock_u, sock_z = 1.2, 1.02
    socket = Op('N', sock_u, sock_z, 0.85, 0.72, 'flat', depth=0.5, back='SKY_Ink', sill=False, reveal='SKY_Metal')
    ops = [socket, Op('N', -1.0, 0.3, 1.4, 2.4, 'segment', back='SKY_Teal', sill=False, frame='SKY_Coral', frame_t=0.1),
           Op('E', 0.5, 1.3, 1.6, 0.9, 'flat', back='SKY_Ink', sill=False),
           Op('W', 0.5, 1.3, 1.6, 0.9, 'flat', back='SKY_Ink', sill=False)]
    block(a, X0, X1, Y0, Y1, 0.0, zr, 'SKY_Pearl', ops, name="house", fm={'top': 'SKY_Kerb'})
    # socket housing frame (brass) + coral warning chevrons beside it
    mb = MB()
    fbox(mb, 'N', Y0, sock_u - 0.62, sock_u + 0.62, sock_z - 0.2, sock_z - 0.06, 0.0, 0.16, 'SKY_Brass')
    fbox(mb, 'N', Y0, sock_u - 0.62, sock_u + 0.62, sock_z + 0.78, sock_z + 0.92, 0.0, 0.16, 'SKY_Brass')
    fbox(mb, 'N', Y0, sock_u - 0.62, sock_u - 0.48, sock_z - 0.06, sock_z + 0.78, 0.0, 0.16, 'SKY_Brass')
    fbox(mb, 'N', Y0, sock_u + 0.48, sock_u + 0.62, sock_z - 0.06, sock_z + 0.78, 0.0, 0.16, 'SKY_Brass')
    a.part(mb, bevel=0.015, seg=1, name="socket_frame")
    mb = MB()
    for k in range(4):
        z0 = 0.38 + k * 0.14
        m = 'SKY_Coral' if k % 2 == 0 else 'SKY_Ink'
        fbox(mb, 'N', Y0, sock_u - 0.62, sock_u + 0.62, z0, z0 + 0.1, 0.0, 0.04, m)
    a.part(mb, name="socket_stripes")
    # seat inside the recess
    mb = MB()
    fbox(mb, 'N', Y0, sock_u - 0.3, sock_u + 0.3, sock_z, sock_z + 0.08, -0.48, -0.08, 'SKY_Metal')
    a.part(mb, name="socket_seat")
    a.empty("SOCKET_cell", fpt('N', Y0, sock_u, sock_z + 0.08, -0.28))
    # PowerLights: separate light bar above the socket + roof beacon (game makes them emissive)
    mb = MB()
    fbox(mb, 'N', Y0, sock_u - 0.55, sock_u + 0.55, sock_z + 1.02, sock_z + 1.16, 0.04, 0.14, 'SKY_TealGlow')
    mb.lathe([(0, zr + 0.75), (0.16, zr + 0.75), (0.16, zr + 0.88), (0.12, zr + 0.98), (0, zr + 1.02)], 8,
             'SKY_TealGlow', cx=X1 - 0.6, cy=Y0 + 0.6)
    a.part(mb, target="PowerLights", name="lights")
    mb = MB()
    fbox(mb, 'N', Y0, sock_u - 0.62, sock_u + 0.62, sock_z + 0.98, sock_z + 1.02, 0.0, 0.17, 'SKY_Brass')
    mb.lathe([(0, zr + 0.6), (0.2, zr + 0.6), (0.2, zr + 0.75), (0, zr + 0.75)], 8, 'SKY_Brass', cx=X1 - 0.6, cy=Y0 + 0.6)
    a.part(mb, name="light_mounts")
    ring_band(a, X0, X1, Y0, Y1, zr - 0.4, zr - 0.25, 0.05, 'SKY_Teal', name="teal_band")
    parapet(a, X0, X1, Y0, Y1, zr, 0.6, 0.2, 'SKY_Pearl', cap='SKY_Sandstone')
    # roof vents
    mb = MB()
    for (x, y) in ((-1.4, 1.2), (0.2, 1.2)):
        mb.box(x - 0.45, x + 0.45, y - 0.45, y + 0.45, zr, zr + 0.6, 'SKY_Metal')
        mb.box(x - 0.55, x + 0.55, y - 0.55, y + 0.55, zr + 0.6, zr + 0.7, 'SKY_Ink')
    a.part(mb, bevel=0.02, seg=1, name="vents")
    # transformers either side
    transformer(a, -4.4, 0.5)
    transformer(a, 4.4, 0.5)
    # conduits from transformers into the house (teal)
    mb = MB()
    for s in (-1, 1):
        path = [(s * 3.9, 0.5, 1.6), (s * 3.35, 0.5, 2.2), (s * 3.0, 0.5, 2.5), (s * 2.8, 0.5, 2.5)]
        mb.sweep(path, circle(0.09, 6), 'SKY_Teal')
        path = [(s * 4.4, -0.45, 0.3), (s * 4.4, -1.0, 0.18), (s * 3.2, -1.25, 0.18), (s * 2.85, -1.25, 0.18)]
        mb.sweep(path, circle(0.07, 6), 'SKY_Metal')
    a.part(mb, name="conduits")
    # striped bollards at the corners of the compound
    mb = MB()
    for (x, y) in ((-5.8, -1.0), (5.8, -1.0), (-5.8, 2.0), (5.8, 2.0)):
        prof = [(0, 0), (0.13, 0), (0.13, 0.25), (0.13, 0.5), (0.13, 0.75), (0.13, 0.9), (0.06, 0.98), (0, 1.0)]
        mb.lathe(prof, 8, 'SKY_Pearl', mats=['SKY_Pearl', 'SKY_Coral', 'SKY_Pearl', 'SKY_Coral', 'SKY_Pearl',
                                             'SKY_Pearl', 'SKY_Pearl'], cx=x, cy=y)
    a.part(mb, name="bollards")
    a.notes.append("SOCKET_cell sits inside the recessed housing on the north face (~1.1 m). PowerLights is a "
                   "separate object (light bar + roof beacon, SKY_TealGlow).")


@asset("bldg_terminal", "Buildings", "poi", ao=BLD_AO, render=dict(BLD_RENDER, az=30.0))
def bldg_terminal(a):
    """Small airport terminal ~14 x 10 m: glass front behind pearl columns, deep canopy with a teal
    glow edge, gently vaulted roof; ANCHOR_convoy_stop at the north drop-off kerb."""
    X0, X1, Y0, Y1 = -7.0, 7.0, -2.8, 5.0
    zw = 5.6
    plinth(a, X0, X1, Y0, Y1, h=0.3, mat='SKY_SandstoneDeep')
    front = Op('N', 0.0, 0.3, 11.6, 4.6, 'flat', depth=0.45, back='SKY_Glass', sill=False, reveal='SKY_Pearl')
    ops = [front]
    for f in ('E', 'W'):
        for uu in (-1.0, 1.4, 3.8):
            ops.append(Op(f, uu, 1.0, 0.8, 3.4, 'round', frame='SKY_Pearl', frame_t=0.1))
    ops += [Op('S', -4.5, 0.3, 1.4, 2.6, 'flat', back='SKY_Teal', sill=False)]
    block(a, X0, X1, Y0, Y1, 0.0, zw, 'SKY_Sandstone', ops, name="hall", fm={'top': 'SKY_Kerb'})
    # curtain wall mullions + doors
    mb = MB()
    for k in range(9):
        uu = -5.8 + k * 11.6 / 8
        fbox(mb, 'N', Y0, uu - 0.06, uu + 0.06, 0.3, 4.9, -0.4, -0.3, 'SKY_Brass')
    fbox(mb, 'N', Y0, -5.8, 5.8, 2.9, 2.98, -0.4, -0.3, 'SKY_Brass')
    a.part(mb, name="mullions")
    mb = MB()
    fbox(mb, 'N', Y0, -1.3, 1.3, 0.3, 2.85, -0.38, -0.33, 'SKY_Teal')
    a.part(mb, name="doors")
    # colonnade and canopy
    cy = -4.3
    mb = MB()
    for x in (-6.2, -3.7, -1.25, 1.25, 3.7, 6.2):
        mb.lathe([(0, 0.0), (0.38, 0.0), (0.38, 0.3), (0.26, 0.42), (0.22, 5.2), (0.3, 5.35), (0.3, 5.5), (0, 5.5)],
                 12, 'SKY_Pearl', cx=x, cy=cy)
    a.part(mb, name="columns")
    mb = MB()
    for x in (-6.2, -3.7, -1.25, 1.25, 3.7, 6.2):
        mb.lathe([(0, 5.2), (0.27, 5.2), (0.27, 5.3), (0, 5.3)], 12, 'SKY_Brass', cx=x, cy=cy)
    a.part(mb, name="capitals")
    mb = MB()
    mb.box(-7.0, 7.0, -5.0, Y0 + 0.2, 5.5, 5.95, 'SKY_Pearl')
    a.part(mb, bevel=0.05, seg=1, name="canopy")
    mb = MB()
    mb.box(-6.9, 6.9, -5.02, -4.96, 5.5, 5.58, 'SKY_TealGlow')
    a.part(mb, name="glow")
    mb = MB()
    mb.box(-7.05, 7.05, -5.05, -4.85, 5.95, 6.05, 'SKY_Brass')
    a.part(mb, name="canopy_trim")
    # forecourt and drop-off kerb
    mb = MB()
    mb.box(-6.8, 6.8, -6.3, Y0, 0.0, 0.12, 'SKY_Kerb')
    a.part(mb, bevel=0.02, seg=1, name="forecourt")
    mb = MB()
    mb.box(-6.8, 6.8, -6.55, -6.3, 0.0, 0.18, 'SKY_Pearl')
    a.part(mb, bevel=0.03, seg=1, name="kerb")
    mb = MB()
    for x in (-6.2, -3.0, 3.0, 6.2):
        mb.lathe([(0, 0.12), (0.12, 0.12), (0.12, 0.8), (0.08, 0.9), (0, 0.92)], 8, 'SKY_Pearl', cx=x, cy=-6.0)
    a.part(mb, name="bollards")
    mb = MB()
    for x in (-6.2, -3.0, 3.0, 6.2):
        mb.lathe([(0, 0.72), (0.125, 0.72), (0.125, 0.78), (0, 0.78)], 8, 'SKY_Brass', cx=x, cy=-6.0)
    a.part(mb, name="bollard_bands")
    # vaulted roof shell (curved, pearl) over the hall
    crv = [(math.cos(math.radians(t)) * 6.7, zw + 0.25 + 1.4 * math.sin(math.radians(t))) for t in range(0, 181, 15)]
    outer = crv
    inner = [(x * 0.97, z - 0.22) for (x, z) in crv]
    poly = outer + list(reversed(inner))
    mb = MB()
    mb.prism_frame(poly, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), Y0 + 0.2, Y1 - 0.2, 'SKY_Pearl')
    a.part(mb, bevel=0.03, seg=1, name="vault")
    mb = MB()
    mb.box(X0 + 0.25, X1 - 0.25, Y0 + 0.35, Y1 - 0.35, zw, zw + 0.25, 'SKY_TealLight')
    a.part(mb, name="clerestory")
    # glazed lunettes closing both vault ends + radial brass mullions
    lun = [(x * 0.965, z - 0.2) for (x, z) in crv]
    mb = MB()
    for y in (Y0 + 0.32, Y1 - 0.32):
        mb.prism_frame(lun, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), y - 0.05, y + 0.05, 'SKY_Glass')
    a.part(mb, name="lunettes")
    mb = MB()
    for y in (Y0 + 0.25,):
        for t in (30, 60, 90, 120, 150):
            ex = math.cos(math.radians(t)) * 6.4
            ez = zw + 0.05 + 1.33 * math.sin(math.radians(t))
            mb.sweep([(0, y, zw + 0.25), (ex, y, ez)], circle(0.05, 4), 'SKY_Brass')
    a.part(mb, name="lunette_mullions")

    mb = MB()
    for y in (Y0 + 0.2, Y1 - 0.2):
        mb.box(X0, X1, y - 0.12, y + 0.12, zw, zw + 0.25, 'SKY_Sandstone')
    a.part(mb, name="vault_beams")
    a.empty("ANCHOR_convoy_stop", (0.0, -7.0, 0.0))
    a.notes.append("ANCHOR_convoy_stop on the road side of the north drop-off kerb (Unity z +7.0).")


@asset("bldg_tower_control", "Buildings", "poi", ao=BLD_AO, render=dict(BLD_RENDER, el=18.0))
def bldg_tower_control(a):
    """Airfield control tower ~16 m: pearl base, slender shaft with teal slit, glazed octagonal cab,
    brass mullions, coral obstruction beacon. ANCHOR_lever by the door (ground level)."""
    X0, X1, Y0, Y1 = -3.2, 3.2, -3.0, 3.0
    zb = 4.0
    plinth(a, X0, X1, Y0, Y1, h=0.3)
    dop = door(a, 'N', Y0, -0.9, w=1.2, h=2.4, frame='SKY_Sandstone', leaf='SKY_Teal', z=0.3, steps=False)
    ops = [dop, Op('N', 1.6, 1.2, 1.0, 1.6, 'round'), Op('E', 0.0, 1.2, 1.2, 1.6, 'round'),
           Op('W', 0.0, 1.2, 1.2, 1.6, 'round'), Op('S', 0.0, 1.2, 1.2, 1.6, 'round')]
    block(a, X0, X1, Y0, Y1, 0.0, zb, 'SKY_Pearl', ops, name="base", fm={'top': 'SKY_Kerb'})
    parapet(a, X0, X1, Y0, Y1, zb, 0.45, 0.2, 'SKY_Pearl', cap='SKY_Sandstone')
    mb = MB()
    fbox(mb, 'N', Y0, -0.9 - 0.95, -0.9 + 0.95, 2.9, 3.05, 0.0, 0.9, 'SKY_Pearl')
    a.part(mb, bevel=0.02, seg=1, name="door_hood")
    # shaft
    sh = rrect(2.6, 2.6, 0.9, seg=4)
    prof = [(0.12, zb, 'SKY_Sandstone'), (0.12, zb + 0.5, 'SKY_Sandstone'), (0.0, zb + 0.5, 'SKY_Sandstone'),
            (0.0, 11.4, 'SKY_Sandstone'), (0.25, 11.4, 'SKY_Pearl'), (0.25, 11.9, 'SKY_Pearl')]
    loft_outline(a, ccw(sh), prof, cap_top='SKY_Pearl', name="shaft")
    mb = MB()
    fbox(mb, 'N', -1.3, -0.2, 0.2, zb + 1.0, 11.0, -0.02, 0.05, 'SKY_TealLight')
    fbox(mb, 'S', 1.3, -0.2, 0.2, zb + 1.0, 11.0, -0.02, 0.05, 'SKY_TealLight')
    a.part(mb, name="slits")
    # cab: octagonal floor slab, sloped glass, roof
    oct_r = 2.7
    cab0, cab1 = 11.9, 14.3
    mb = MB()
    mb.lathe([(0, cab0 - 0.1), (oct_r + 0.15, cab0 - 0.1), (oct_r + 0.15, cab0 + 0.35), (0, cab0 + 0.35)], 8,
             'SKY_Pearl', a0=22.5)
    a.part(mb, bevel=0.04, seg=1, name="cab_floor")
    mb = MB()
    mb.lathe([(0, cab0 + 0.35), (oct_r - 0.25, cab0 + 0.35), (oct_r + 0.15, cab1), (0, cab1)], 8, 'SKY_Glass', a0=22.5)
    a.part(mb, name="cab_glass")
    mb = MB()
    for k in range(8):
        ang = math.radians(22.5 + 45 * k)
        p0 = Vector(((oct_r - 0.23) * math.cos(ang), (oct_r - 0.23) * math.sin(ang), cab0 + 0.35))
        p1 = Vector(((oct_r + 0.17) * math.cos(ang), (oct_r + 0.17) * math.sin(ang), cab1))
        mb.sweep([p0, p1], circle(0.06, 4), 'SKY_Brass')
    a.part(mb, name="cab_mullions")
    mb = MB()
    mb.lathe([(0, cab1), (oct_r + 0.5, cab1), (oct_r + 0.5, cab1 + 0.3), (oct_r - 0.3, cab1 + 0.5), (1.0, cab1 + 0.75),
              (0, cab1 + 0.8)], 8, 'SKY_Pearl', a0=22.5)
    a.part(mb, bevel=0.03, seg=1, name="cab_roof")
    mb = MB()
    mb.lathe([(0, cab1 + 0.28), (oct_r + 0.52, cab1 + 0.28), (oct_r + 0.52, cab1 + 0.34), (0, cab1 + 0.34)], 8,
             'SKY_TealGlow', a0=22.5)
    a.part(mb, name="cab_glow")
    # gallery railing ring below the cab
    mb = MB()
    ring = [(math.cos(math.radians(22.5 + 45 * k)) * (oct_r + 0.1), math.sin(math.radians(22.5 + 45 * k)) * (oct_r + 0.1),
             cab0 + 1.05) for k in range(9)]
    mb.sweep(ring, circle(0.04, 4), 'SKY_Brass')
    a.part(mb, name="rail")
    # mast + coral beacon
    mb = MB()
    mb.cyl(0.07, cab1 + 0.8, 16.3, 6, 'SKY_Brass')
    mb.box(-0.5, 0.5, -0.03, 0.03, 15.3, 15.36, 'SKY_Brass')
    a.part(mb, name="mast")
    mb = MB()
    mb.sphere(0.16, 8, 4, 'SKY_Coral', c=(0, 0, 16.42))
    a.part(mb, name="beacon")
    a.empty("ANCHOR_lever", (1.0, -3.75, 0.0))
    a.notes.append("ANCHOR_lever at ground level just right of the door (viewer facing the door).")


@asset("bldg_hangar", "Buildings", "poi", ao=dict(BLD_AO, dist=3.0), render=dict(BLD_RENDER, az=28.0, el=22.0))
def bldg_hangar(a):
    """Curved-roof hangar 22 m wide x 16 m deep x 9 m high, open front facing Unity north."""
    HW, Y0, Y1 = 11.0, -8.0, 8.0
    zs, ztop = 1.6, 9.0
    n = 16
    outer = [(HW * math.cos(math.pi * i / n), zs + (ztop - zs) * math.sin(math.pi * i / n)) for i in range(n + 1)]
    inner = [((HW - 0.35) * math.cos(math.pi * i / n), zs + (ztop - zs - 0.35) * math.sin(math.pi * i / n))
             for i in range(n + 1)]
    # shell with glass ridge band: three lofts along Y
    def band(i0, i1, mat, name):
        poly = outer[i0:i1 + 1] + list(reversed(inner[i0:i1 + 1]))
        mb = MB()
        mb.prism_frame(poly, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), Y0 + 0.3, Y1, mat)
        a.part(mb, name=name)
    band(0, 6, 'SKY_Metal', "roof_r")
    band(6, 10, 'SKY_Glass', "skylight")
    band(10, 16, 'SKY_Metal', "roof_l")
    # low side walls
    mb = MB()
    mb.box(-HW - 0.1, -HW + 0.5, Y0, Y1, 0.0, zs + 0.1, 'SKY_Sandstone')
    mb.box(HW - 0.5, HW + 0.1, Y0, Y1, 0.0, zs + 0.1, 'SKY_Sandstone')
    a.part(mb, bevel=0.05, seg=1, name="side_walls")
    # ribs (pearl) incl. the front portal
    for y, t, name in ((Y0 + 0.15, 0.55, "portal"), (-3.0, 0.3, "rib"), (2.5, 0.3, "rib"), (Y1 - 0.2, 0.3, "rib")):
        o2 = [(x * (HW + 0.25) / HW, zs + (z - zs) * (ztop - zs + 0.25) / (ztop - zs)) for (x, z) in outer]
        poly = o2 + list(reversed(inner))
        poly = [(o2[0][0], 0.0)] + poly + [(-o2[0][0], 0.0)]
        poly = o2 + [(inner[-1][0], inner[-1][1]), (inner[-1][0], 0.0), (o2[-1][0], 0.0)][0:0] + list(reversed(inner))
        legs = [(o2[0][0], 0.0)] + o2 + [(o2[-1][0], 0.0), (inner[-1][0], 0.0)] + list(reversed(inner)) + [(inner[0][0], 0.0)]
        mb = MB()
        mb.prism_frame(legs, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), y - t / 2, y + t / 2, 'SKY_Pearl')
        a.part(mb, bevel=0.04, seg=1, name=name)
    # glow strip under the portal arch
    mb = MB()
    gl = [((HW - 0.4) * math.cos(math.pi * i / n), zs + (ztop - zs - 0.42) * math.sin(math.pi * i / n)) for i in range(n + 1)]
    gl2 = [((HW - 0.48) * math.cos(math.pi * i / n), zs + (ztop - zs - 0.5) * math.sin(math.pi * i / n)) for i in range(n + 1)]
    mb.prism_frame(gl + list(reversed(gl2)), (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), Y0 + 0.4, Y0 + 0.5, 'SKY_TealGlow')
    a.part(mb, name="glow")
    # back wall (closed) with a door and an oculus
    back = [(x, z) for (x, z) in inner] + [(-HW + 0.35, 0.0), (HW - 0.35, 0.0)]
    back = [(HW - 0.35, 0.0)] + [(x, z) for (x, z) in inner] + [(-HW + 0.35, 0.0)]
    door_op = Op('S', 0.0, 0.1, 4.0, 3.6, 'flat', depth=0.22, back='SKY_Teal', sill=False)
    ocu = Op('S', 0.0, 5.0, 2.2, 2.2, 'round', depth=0.22, back='SKY_Glass', sill=False, seg=10)

    cuts = [make_cutter(a, door_op, Y1, 'SKY_Sandstone'), make_cutter(a, ocu, Y1, 'SKY_Sandstone')]
    mb = MB()
    mb.prism_frame(back, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), Y1 - 0.4, Y1, 'SKY_Sandstone')
    a.part(mb, bevel=0.04, seg=1, cutters=cuts, name="back_wall")
    # floor with guide line
    mb = MB()
    mb.box(-HW + 0.5, HW - 0.5, Y0, Y1 - 0.4, 0.0, 0.1, 'SKY_Kerb')
    a.part(mb, name="floor")
    mb = MB()
    mb.box(-0.1, 0.1, Y0, Y1 - 1.0, 0.1, 0.115, 'SKY_RoadLine')
    for k in range(4):
        y = Y0 + 1.0 + k * 3.5
        mb.box(-1.6, 1.6, y - 0.08, y + 0.08, 0.1, 0.115, 'SKY_RoadLine')
    a.part(mb, name="floor_lines")
    # side buttress lamps
    mb = MB()
    for x in (-HW - 0.1, HW + 0.1):
        for y in (-5.5, 0.0, 5.5):
            mb.box(x - 0.35, x + 0.35, y - 0.35, y + 0.35, 0.0, zs + 0.5, 'SKY_Pearl')
    a.part(mb, bevel=0.04, seg=1, name="buttresses")
    a.notes.append("Footprint 22.5 x 16 m (spans more than one cell in X); pivot at its own ground centre.")
