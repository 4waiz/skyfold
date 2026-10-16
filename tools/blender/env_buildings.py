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
    def __init__(self, face, u, z, w, h, kind='round', depth=0.3, back='SKY_Glass', seg=8,
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


def block(a, x0, x1, y0, y1, z0, z1, mat, ops=(), bevel=0.06, seg=2, name="block", target=None, fm=None):
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
        a.part(mbs, bevel=0.02, seg=1, name="sills", target=target)
    if any_f:
        a.part(mbf, bevel=0.02, seg=1, name="frames", target=target)
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
            pts = [(c - hw, z), (c + hw, z), (c + hw, z + h * 0.45), (c + hw * 0.6, z + h * 0.45),
                   (c + hw * 0.6, z + h * 0.78), (c + hw * 0.25, z + h * 0.78), (c + hw * 0.25, z + h),
                   (c - hw * 0.25, z + h), (c - hw * 0.25, z + h * 0.78), (c - hw * 0.6, z + h * 0.78),
                   (c - hw * 0.6, z + h * 0.45), (c - hw, z + h * 0.45)]
        else:
            pts = [(c - w / 2, z), (c + w / 2, z), (c + w / 2, z + h), (c - w / 2, z + h)]
        fprism(mb, face, plane, pts, -inset - t, -inset, mat)
    a.part(mb, bevel=0.02, seg=1, name="merlons")


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
    a.part(mb, bevel=0.04, seg=1, name="parapet")
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
    a.part(mb, bevel=0.015, seg=1, name="pergola_beams")
    if sail:
        sail_quad(a, [(x0 + 0.1, y0 + 0.1, z + h - 0.05), (x1 - 0.1, y0 + 0.1, z + h - 0.25),
                      (x1 - 0.1, y1 - 0.1, z + h - 0.05), (x0 + 0.1, y1 - 0.1, z + h - 0.25)], sail)


def sail_quad(a, corners, mat='SKY_Fabric', sag=0.25, n=4, t=0.03, target=None):
    """Tensioned shade sail (3 or 4 corners), slightly sagging, with thickness so both sides render."""
    mb = MB()
    if len(corners) == 4:
        A, B, C, D = [Vector(c) for c in corners]
        grid = []
        for i in range(n + 1):
            row = []
            for j in range(n + 1):
                u, v = i / n, j / n
                p = A.lerp(B, u).lerp(D.lerp(C, u), v)
                s = 4 * u * (1 - u) * 4 * v * (1 - v)
                p = p - Vector((0, 0, sag * s))
                row.append(p)
            grid.append(row)
    else:
        A, B, C = [Vector(c) for c in corners]
        grid = []
        for i in range(n + 1):
            row = []
            for j in range(n + 1):
                u, v = i / n, j / n
                # map square to triangle (collapsed edge at C)
                p = (A.lerp(B, u)).lerp(C, v)
                s = 4 * u * (1 - u) * 4 * v * (1 - v) * 0.6
                row.append(p - Vector((0, 0, sag * s)))
            grid.append(row)
    top = [[mb.v(p) for p in row] for row in grid]
    bot = [[mb.v(p - Vector((0, 0, t))) for p in row] for row in grid]
    fs = []
    for i in range(n):
        for j in range(n):
            q = [top[i][j], top[i + 1][j], top[i + 1][j + 1], top[i][j + 1]]
            r = [bot[i][j + 1], bot[i + 1][j + 1], bot[i + 1][j], bot[i][j]]
            if len(set(q)) == 4 and len(set(v.co.to_tuple(5) for v in q)) == 4:
                fs.append(mb.f(q, mat)); fs.append(mb.f(r, mat))
            else:
                qq = []
                for v in q:
                    if v.co.to_tuple(5) not in [w.co.to_tuple(5) for w in qq]:
                        qq.append(v)
                rr_ = []
                for v in r:
                    if v.co.to_tuple(5) not in [w.co.to_tuple(5) for w in rr_]:
                        rr_.append(v)
                if len(qq) >= 3:
                    fs.append(mb.f(qq, mat)); fs.append(mb.f(rr_, mat))
    # rim
    loop = [(i, 0) for i in range(n)] + [(n, j) for j in range(n)] + [(i, n) for i in range(n, 0, -1)] + \
           [(0, j) for j in range(n, 0, -1)]
    for k in range(len(loop)):
        i0, j0 = loop[k]; i1, j1 = loop[(k + 1) % len(loop)]
        a0, a1 = top[i0][j0], top[i1][j1]
        b0, b1 = bot[i0][j0], bot[i1][j1]
        if (a0.co - a1.co).length < 1e-5:
            continue
        fs.append(mb.f([a1, a0, b0, b1], mat))
    bmesh.ops.remove_doubles(mb.bm, verts=mb.bm.verts, dist=1e-5)
    a.part(mb, name="sail", target=target)
    a.set_target(target or a.name)


def door(a, face, plane, u, w=1.4, h=2.6, kind='round', frame='SKY_Pearl', leaf='SKY_Wood', depth=0.3,
         wall='SKY_Sandstone'):
    """Arched door: returns an Op for the wall + adds brass ring and step."""
    op = Op(face, u, 0.12, w, h, kind, depth=depth, back=leaf, sill=False, frame=frame, frame_t=0.16)
    mb = MB()
    fbox(mb, face, plane, u - w / 2 - 0.25, u + w / 2 + 0.25, 0.0, 0.14, -0.05, 0.45, 'SKY_Pearl')
    a.part(mb, bevel=0.02, seg=1, name="step")
    mb = MB()
    c = fpt(face, plane, u + w * 0.22, 1.15, -depth + 0.04)
    mb.cbox(c[0], c[1], c[2], 0.09 if face in 'NS' else 0.05, 0.05 if face in 'NS' else 0.09, 0.09, 'SKY_Brass')
    a.part(mb, name="knob")
    return op


def lattice(a, face, plane, u, z, w, h, d=0.45, mat='SKY_Wood', frame='SKY_Pearl', n=5):
    """Projecting lattice screen box (mashrabiya-like, original geometric slats)."""
    mb = MB()
    fbox(mb, face, plane, u - w / 2, u + w / 2, z - 0.12, z, 0.0, d + 0.08, frame)       # base shelf
    fbox(mb, face, plane, u - w / 2, u + w / 2, z + h, z + h + 0.12, 0.0, d + 0.08, frame)  # top cap
    fbox(mb, face, plane, u - w / 2, u - w / 2 + 0.08, z, z + h, 0.0, d, frame)
    fbox(mb, face, plane, u + w / 2 - 0.08, u + w / 2, z, z + h, 0.0, d, frame)
    a.part(mb, bevel=0.02, seg=1, name="lattice_frame")
    mb = MB()
    # diagonal lattice: two families of thin bars in the front plane
    import itertools
    inner_w = w - 0.16
    for k in range(-n, n + 1):
        for sgn in (-1, 1):
            # bar from bottom to top at 45 deg, clipped to the panel
            x0 = k * inner_w / n * 0.5
            p0 = (x0, 0.0); p1 = (x0 + sgn * h, h)
            # clip to [-inner_w/2, inner_w/2]
            def clip(p0, p1):
                (xa, ya), (xb, yb) = p0, p1
                lo, hi = -inner_w / 2, inner_w / 2
                t0, t1 = 0.0, 1.0
                dx = xb - xa
                if abs(dx) < 1e-9:
                    return None
                for bound in (lo, hi):
                    t = (bound - xa) / dx
                    if dx > 0:
                        if bound == lo: t0 = max(t0, t)
                        else: t1 = min(t1, t)
                    else:
                        if bound == lo: t1 = min(t1, t)
                        else: t0 = max(t0, t)
                if t1 - t0 < 0.05:
                    return None
                return (xa + dx * t0, ya + (yb - ya) * t0), (xa + dx * t1, ya + (yb - ya) * t1)
            seg_ = clip(p0, p1)
            if not seg_:
                continue
            (xa, ya), (xb, yb) = seg_
            dirv = Vector((xb - xa, yb - ya)).normalized()
            nv = Vector((-dirv.y, dirv.x)) * 0.03
            pts = [(xa - nv.x + u, ya - nv.y + z), (xb - nv.x + u, yb - nv.y + z), (xb + nv.x + u, yb + nv.y + z),
                   (xa + nv.x + u, ya + nv.y + z)]
            pts = [(p[0], min(max(p[1], z), z + h)) for p in pts]
            fprism(mb, face, plane, pts, d - 0.06 - (0.02 if sgn > 0 else 0.0), d - (0.02 if sgn > 0 else 0.0), mat)
    a.part(mb, name="lattice")
    # dark backing so the screen reads
    mb = MB()
    fbox(mb, face, plane, u - w / 2 + 0.08, u + w / 2 - 0.08, z, z + h, 0.02, 0.06, 'SKY_Ink')
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


def awning(a, face, plane, u, z, w, depth=1.0, drop=0.45, mats=('SKY_Coral', 'SKY_Pearl'), stripes=6, target=None):
    """Sloped striped fabric awning with a scalloped-free valance (stripes along the slope)."""
    mb = MB()
    for i in range(stripes):
        u0 = u - w / 2 + w * i / stripes
        u1 = u - w / 2 + w * (i + 1) / stripes
        m = mats[i % len(mats)]
        p00 = fpt(face, plane, u0, z, 0.02); p10 = fpt(face, plane, u1, z, 0.02)
        p01 = fpt(face, plane, u0, z - drop, depth); p11 = fpt(face, plane, u1, z - drop, depth)
        p02 = fpt(face, plane, u0, z - drop - 0.25, depth); p12 = fpt(face, plane, u1, z - drop - 0.25, depth)
        t = 0.03
        q0 = fpt(face, plane, u0, z - t, 0.02); q1 = fpt(face, plane, u1, z - t, 0.02)
        q2 = fpt(face, plane, u0, z - drop - t, depth - t); q3 = fpt(face, plane, u1, z - drop - t, depth - t)
        mb.loft([[p00, p10, q1, q0], [p01, p11, q3, q2]], m)
        mb.box(*sorted((p01[0], p12[0])), *sorted((p01[1], p12[1])), p02[2], p01[2], m) if False else None
        # valance
        va = fpt(face, plane, u0, z - drop, depth); vb = fpt(face, plane, u1, z - drop - 0.25, depth + 0.03)
        mb.box(min(va[0], vb[0]), max(va[0], vb[0]), min(va[1], vb[1]), max(va[1], vb[1]), vb[2], va[2], m)
    a.part(mb, name="awning", target=target)
    mb = MB()
    pa = fpt(face, plane, u - w / 2, z, 0.0); pb = fpt(face, plane, u + w / 2, z + 0.12, 0.12)
    mb.box(min(pa[0], pb[0]), max(pa[0], pb[0]), min(pa[1], pb[1]), max(pa[1], pb[1]), pa[2], pb[2], 'SKY_Brass')
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
    mb = MB(); mb.box(X0, X1, Y0, Y1, 0.0, zr, wall)
    a.part(mb, bevel=0.06, seg=2, cutters=cutters, name="mass")
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
    roof_slab(a, X0 + 0.3, X1 - 0.3, Y0 + 0.3, Y1 - 0.3, zr + 0.05)
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
