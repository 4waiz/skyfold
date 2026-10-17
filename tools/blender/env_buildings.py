"""SKYFOLD environment kit - buildings and points of interest.

Footprints <= 12 x 12 m centred in the 16 m cell, pivot at ground centre (Z 0).
Fronts face Unity north (+Z) = Blender -Y. Face names use Unity directions:
'N' = Blender -Y face, 'S' = +Y, 'E' = -X, 'W' = +X.

Detail pass: every wall block goes through solid() (bevel -> booleans -> bevel evaluated here, then the big
faces are sliced on a coarse grid so the corner-sampled AO bake has no long slivers). Openings are described
by Op and dressed by dress(): deep reveals, inner frames and glazing bars, two-tier sills, keystones / hood
moulds / lintels, louvred shutters, lattice screens, Juliet balconies, panelled doors with fanlights, steps
and lanterns, and a dark backing behind every SKY_Glass pane (the glass is translucent in Unity).
Detail geometry is grouped per feature into Kits (one part per bevel class) to keep part counts low.
"""
from env_common import *
import bmesh

BLD_AO = dict(ground_z=0.0, dist=1.8, rays=28, strength=0.72, floor=0.48, inset=0.25, power=1.25)
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
    """One opening. The first fields drive the wall cut; the rest drive dress() (detail pass).
    inner: inner frame material; bars: 'cross' | 'fan' | 'mull' | 'transom'; head: 'key' | 'hood' | 'lintel';
    shutter / screen / balconette: materials; door: leaves + fanlight; steps: count; plane: explicit plane
    (courtyard faces)."""

    def __init__(self, face, u, z, w, h, kind='round', depth=0.3, back='SKY_Glass', seg=8,
                 sill=True, frame=None, frame_t=0.12, through=False, reveal=None, mullion=False, key=False,
                 inner=None, bars=None, bar_mat=None, head=None, head_mat=None, shutter=None, screen=None,
                 backing=True, curtain=None, door=False, lamp=False, steps=0, step_mat='SKY_Pearl',
                 balconette=None, plane=None, sill_mat=None, iframe='rect'):
        self.__dict__.update(locals())
        del self.__dict__['self']


# --------------------------------------------------------------------------- shared shells
# (env_atelier, env_props and env_sky import fbox / fpt / fprism / arch_band / shift_uv / loft_outline /
#  sail_quad / sail_mesh from this module: keep their signatures and behaviour stable)

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


# --------------------------------------------------------------------------- legacy helpers
# Pre-detail-pass building helpers, unused by the buildings below; kept verbatim so any kit script that
# imports them keeps working.

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


# =========================================================================== detail kit (v2)
#
# Detail pass helpers. Geometry is collected into a few bevel classes per feature group (Kit) so
# a building stays a handful of parts. Big walls go through solid(): booleans and bevels are
# evaluated here, then the result is re-triangulated so no triangle edge is longer than ~1.2 m
# (the AO bake samples face corners; long slivers smeared it into diagonal bands).

BEV = {'big': (0.05, 2), 'trim': (0.03, 2), 'mid': (0.02, 1), 'small': (0.012, 1), 'none': (0.0, 1)}


class Kit:
    """Per-feature geometry buckets keyed by bevel class; flush() turns each into one part."""

    def __init__(self, a, target=None, tag="kit_"):
        self.a, self.target, self.tag, self.mbs = a, target, tag, {}

    def __getitem__(self, cls):
        mb = self.mbs.get(cls)
        if mb is None:
            mb = self.mbs[cls] = MB()
        return mb

    def flush(self):
        for cls, mb in list(self.mbs.items()):
            if not len(mb.bm.faces):
                mb.bm.free()
                continue
            bev, seg = BEV[cls]
            self.a.part(mb, bevel=bev, seg=seg, name=f"{self.tag}{cls}", target=self.target)
        self.mbs = {}


class _Rec:
    """MB proxy that records the faces every builder call returns."""

    def __init__(self, mb, out):
        self.mb, self.out = mb, out

    def __getattr__(self, k):
        fn = getattr(self.mb, k)

        def call(*args, **kw):
            r = fn(*args, **kw)
            if isinstance(r, list):
                self.out.extend(r)
            return r
        return call


class Local:
    """Build a small object in local coordinates into kit classes, then place it with one matrix."""

    def __init__(self, kit, M):
        self.kit, self.M, self.groups = kit, M, {}

    def __call__(self, cls):
        return _Rec(self.kit[cls], self.groups.setdefault(cls, []))

    def move(self, cls, faces, M):
        """Pre-transform faces just built (local space) before the final placement."""
        self.kit[cls].transform(M, faces=faces)

    def done(self):
        for cls, fs in self.groups.items():
            if fs:
                self.kit[cls].transform(self.M, faces=fs)
        self.groups = {}


def frange(a, b, step):
    n = max(1, int(round(abs(b - a) / step)))
    return [a + (b - a) * i / n for i in range(n + 1)]


def refine_bm(bm, L=1.5, off=0.37, amin=0.45, Lz=None):
    """Slice the big flat faces (area > amin) with an axis-aligned grid of planes (spacing L) so walls and
    roofs carry evenly spaced corners (the AO bake samples face corners; long slivers smeared it into
    diagonal bands). Runs after all bevels, so the extra edges never clamp a bevel."""
    if not len(bm.verts):
        return bm
    for axis in range(3):
        LL = (Lz or L) if axis == 2 else L
        cs = [v.co[axis] for v in bm.verts]
        lo, hi = min(cs), max(cs)
        no = Vector((0.0, 0.0, 0.0))
        no[axis] = 1.0
        k = math.floor((lo - off) / LL) + 1
        while off + k * LL < hi - 0.08:
            c = off + k * LL
            k += 1
            if c < lo + 0.08:
                continue
            faces = []
            for f in bm.faces:
                if f.calc_area() < amin:
                    continue
                vs = [v.co[axis] for v in f.verts]
                if min(vs) < c - 0.06 and max(vs) > c + 0.06:
                    faces.append(f)
            if not faces:
                continue
            edges = {e for f in faces for e in f.edges}
            verts = {v for f in faces for v in f.verts}
            co = Vector((0.0, 0.0, 0.0))
            co[axis] = c
            bmesh.ops.bisect_plane(bm, geom=list(verts) + list(edges) + faces, dist=0.004, plane_co=co, plane_no=no)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-4, edges=bm.edges[:])
    return bm


_TMPN = [0]


def _tmp_obj(mb, name):
    _TMPN[0] += 1
    ob = mb.to_object(f"tmp_{name}_{_TMPN[0]}")
    ob.hide_render = True
    ob.display_type = 'WIRE'
    return ob


def _drop(ob):
    me = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    if me is not None and me.users == 0:
        bpy.data.meshes.remove(me)


def _bevel_mod(ob, width, seg, angle):
    md = ob.modifiers.new("bevel", 'BEVEL')
    md.width = width
    md.segments = seg
    md.limit_method = 'ANGLE'
    md.angle_limit = math.radians(angle)
    md.use_clamp_overlap = True
    md.profile = 0.5
    md.harden_normals = False
    return md


REFINE = (3.0, 1.5, 1.2)     # wall slicing: x/y spacing, z spacing, min face area


def solid(a, mb, cutters=(), pre=(0.06, 2), post=(0.035, 1), name="solid", target=None, refine=REFINE,
          post_angle=50.0):
    """Evaluate bevel -> booleans -> bevel on a closed solid now, re-triangulate it and add it as a part.
    pre rounds the solid's own edges (2 segments), post softens the cut openings (1 segment)."""
    ob = _tmp_obj(mb, name)
    if pre and pre[0] > 0:
        _bevel_mod(ob, pre[0], pre[1], 30.0)
    for c in cutters:
        md = ob.modifiers.new("cut", 'BOOLEAN')
        md.operation = 'DIFFERENCE'
        md.solver = 'EXACT'
        md.object = c
        md.material_mode = 'TRANSFER'
    if post and post[0] > 0 and cutters:
        _bevel_mod(ob, post[0], post[1], post_angle)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    out = MB()
    out.bm.from_mesh(me)
    out.mats = [m.name if m else 'SKY_Pearl' for m in me.materials]
    bpy.data.meshes.remove(me)
    _drop(ob)
    for c in cutters:
        _drop(c)
    bmesh.ops.dissolve_degenerate(out.bm, dist=1e-5, edges=out.bm.edges[:])
    if refine:
        if isinstance(refine, tuple):
            refine_bm(out.bm, refine[0], Lz=refine[1], amin=refine[2])
        else:
            refine_bm(out.bm, refine)
    return a.part(out, bevel=0.0, name=name, target=target)


def part_r(a, mb, bevel=0.0, seg=1, name="part", target=None, L=0.0, angle=30.0):
    """Part; with L > 0 the bevel is evaluated first and the result sliced on an L grid (big slabs)."""
    if L:
        return solid(a, mb, (), pre=(bevel, seg), post=None, name=name, target=target, refine=L)
    return a.part(mb, bevel=bevel, seg=seg, angle=angle, name=name, target=target)


def box_cutter(x0, x1, y0, y1, z0, z1, mat, fm=None):
    mb = MB()
    mb.box(x0, x1, y0, y1, z0, z1, mat, fm)
    return _tmp_obj(mb, "cut")


def op_cutter(op, plane, wall_mat):
    mb = MB()
    pts = shift_uv(arch_pts(op.w, op.h, op.kind, op.seg, base=op.z), op.u, 0.0)
    rev = op.reveal or wall_mat
    depth = op.depth if not op.through else 3.0
    fprism(mb, op.face, plane, pts, 0.6, -depth, rev, front=rev, back=op.back)
    return _tmp_obj(mb, "cut")


def spring_of(w, h, kind, base):
    hw = w / 2.0
    if kind == 'round' and h < hw + 0.05:
        kind = 'segment'
    if kind == 'flat':
        return base + h
    if kind == 'round':
        return base + h - hw
    if kind == 'pointed':
        rr = w * 0.8
        return base + h - math.sqrt(rr * rr - (rr - hw) ** 2)
    rise = min(h * 0.25, hw * 0.5)
    return base + h - rise


def _band_uv(w, h, t, kind, seg, u, base):
    return [(p[0] + u, p[1] + base) for p in arch_band(w, h, t, kind, seg)]


def bar2d(mb, face, plane, p0, p1, bw, d0, d1, mat):
    (xa, ya), (xb, yb) = p0, p1
    L = math.hypot(xb - xa, yb - ya)
    if L < 1e-4:
        return []
    nx, ny = -(yb - ya) / L * bw / 2, (xb - xa) / L * bw / 2
    return fprism(mb, face, plane, [(xa - nx, ya - ny), (xb - nx, yb - ny), (xb + nx, yb + ny), (xa + nx, ya + ny)],
                  d0, d1, mat)


def fprism_side(mb, face, plane, pts_dv, u0, u1, mat):
    """Extrude a (d, v) profile along the facade u axis from u0 to u1."""
    uax, vax, out = faxes(face)
    o = fpt(face, plane, 0.0, 0.0, 0.0)
    origin = (o[0] if face in ('E', 'W') else 0.0, o[1] if face in ('N', 'S') else 0.0, 0.0)
    return mb.prism_frame(pts_dv, origin, out, (0, 0, 1), uax, u0, u1, mat)


def louvre_leaf(kit, face, plane, u0, u1, v0, v1, mat, d0=0.004, t=0.055, pitch=0.13):
    """Open louvred shutter leaf lying against the wall: frame + raked slats (one sawtooth prism per panel)."""
    nb = kit['none']
    st = 0.06
    fbox(nb, face, plane, u0, u0 + st, v0, v1, d0, d0 + t, mat)
    fbox(nb, face, plane, u1 - st, u1, v0, v1, d0, d0 + t, mat)
    rails = [(v0, v0 + 0.1), (v1 - 0.08, v1)]
    if v1 - v0 > 1.3:
        vm = v0 + (v1 - v0) * 0.42
        rails.insert(1, (vm - 0.04, vm + 0.04))
    for (ra, rb) in rails:
        fbox(nb, face, plane, u0 + st - 0.01, u1 - st + 0.01, ra, rb, d0, d0 + t - 0.006, mat)
    db, dl, dh = d0 + 0.008, d0 + 0.016, d0 + t - 0.01
    for i in range(len(rails) - 1):
        va, vb = rails[i][1] - 0.005, rails[i + 1][0] + 0.005
        n = max(2, int(round((vb - va) / pitch)))
        s = (vb - va) / n
        pts = [(db, va), (dl, va)]
        for k in range(n):
            pts.append((dh, va + k * s + 0.72 * s))
            pts.append((dl, va + (k + 1) * s))
        pts.append((db, vb))
        fprism_side(nb, face, plane, pts, u0 + st - 0.005, u1 - st + 0.005, mat)


def wall_lamp(kit, face, plane, u, v, arm=0.27):
    """Brass bracket lantern with a warm SKY_Light glass body."""
    fbox(kit['small'], face, plane, u - 0.07, u + 0.07, v - 0.14, v + 0.12, -0.01, 0.035, 'SKY_Brass')
    fbox(kit['none'], face, plane, u - 0.022, u + 0.022, v + 0.03, v + 0.075, 0.03, arm, 'SKY_Brass')
    c = fpt(face, plane, u, v, arm)
    zb = c[2] - 0.25
    kit['none'].lathe([(0.0, zb), (0.035, zb), (0.062, zb + 0.05), (0.062, zb + 0.23), (0.09, zb + 0.26),
                       (0.03, zb + 0.34), (0.0, zb + 0.37)], 6, 'SKY_Brass',
                      mats=['SKY_Brass', 'SKY_Brass', 'SKY_Light', 'SKY_Brass', 'SKY_Brass', 'SKY_Brass'],
                      cx=c[0], cy=c[1])


def dress(kit, op, plane):
    """Everything around one opening: surround, head, inner frame, glazing bars, sill, backing,
    shutters, lattice screen, balconette, door leaves / fanlight / steps / lamps."""
    f, u, z, w, h = op.face, op.u, op.z, op.w, op.h
    hw = w / 2.0
    D = op.depth
    kind = op.kind
    sp = spring_of(w, h, kind, z)
    fts = op.frame_t if op.frame else 0.0
    fd = 0.065 if op.frame else 0.0
    # --- surround band on the wall face (overhangs the reveal by 1.5 cm: no coplanar faces)
    if op.frame:
        band = [(p[0], max(p[1], 0.0)) for p in _band_uv(w - 0.03, h - 0.015, op.frame_t, kind, op.seg, u, z)]
        fprism(kit['mid'], f, plane, band, -0.03, fd, op.frame)
    # --- head
    hm = op.head_mat or op.frame or 'SKY_Pearl'
    if op.head in ('key', 'keylite') and kind != 'flat':
        top = z + h + fts
        kb, kt = (0.17, 0.27) if w < 1.3 else (0.2, 0.32)
        pts = [(u - kb / 2, z + h - 0.012), (u + kb / 2, z + h - 0.012), (u + kt / 2, top + 0.1), (u - kt / 2, top + 0.1)]
        fprism(kit['small' if op.head == 'key' else 'none'], f, plane, pts, -0.03, fd + 0.035, hm)
    elif op.head == 'hood' and kind != 'flat':
        g = fts + 0.05
        ht = 0.09
        sp_i = spring_of(w + 2 * g, h + g, kind, z)
        sp_o = spring_of(w + 2 * g + 2 * ht, h + g + ht, kind, z)
        vcut = min(sp - 0.12, sp_i - 0.03, sp_o - 0.03)
        band = [(p[0], max(p[1], vcut)) for p in _band_uv(w + 2 * g, h + g, ht, kind, min(op.seg, 6), u, z)]
        dd = fd + 0.07
        fprism(kit['none'], f, plane, band, -0.03, dd, hm)
        for s in (-1, 1):
            ua, ub = u + s * (hw + g + ht - 0.01), u + s * (hw + g + ht + 0.09)
            fbox(kit['none'], f, plane, min(ua, ub), max(ua, ub), vcut, vcut + 0.08, -0.03, dd, hm)
    elif op.head == 'lintel':
        e = fts + 0.13
        top = z + h + fts
        fbox(kit['mid'], f, plane, u - hw - e, u + hw + e, top - 0.02, top + 0.17, -0.03, fd + 0.08, hm)
    # --- inner frame (sits on the glass, embedded 2 cm into the reveal)
    if op.inner:
        ft = 0.065 if w < 1.5 else 0.085
        d0, d1 = -D - 0.03, -D + 0.06
        mb = kit['none']
        if op.iframe == 'arch' or kind == 'flat':
            fprism(mb, f, plane, _band_uv(w - 2 * ft, h - ft + 0.02, ft + 0.02, kind, op.seg, u, z - 0.02), d0, d1,
                   op.inner)
        else:
            # rectangular sash up to the springline; the arch head is glazed with bars only
            for s_ in (-1, 1):
                ua, ub = u + s_ * (hw + 0.02), u + s_ * (hw - ft)
                fbox(mb, f, plane, min(ua, ub), max(ua, ub), z - 0.02, sp + 0.02, d0, d1, op.inner)
            fbox(mb, f, plane, u - hw + ft - 0.005, u + hw - ft + 0.005, sp - 0.035, sp + 0.035, d0, d1, op.inner)
        if not op.door:
            fbox(mb, f, plane, u - hw - 0.02, u + hw + 0.02, z - 0.02, z + ft, d0, d1, op.inner)
    # --- glazing bars
    if op.bars:
        mb = kit['none']
        bm_ = op.bar_mat or op.inner or 'SKY_Ink'
        bw = 0.04
        d0, d1 = -D - 0.01, -D + 0.035
        if op.bars in ('cross', 'fan', 'mull'):
            fbox(mb, f, plane, u - bw / 2, u + bw / 2, z - 0.01, z + h + 0.01, d0, d1, bm_)
        if kind == 'flat':
            if op.bars != 'mull':
                tz = z + h * 0.62
                fbox(mb, f, plane, u - hw - 0.02, u + hw + 0.02, tz - bw / 2, tz + bw / 2, d0, d1, bm_)
        else:
            fbox(mb, f, plane, u - hw - 0.02, u + hw + 0.02, sp - bw / 2, sp + bw / 2, d0, d1, bm_)
            if sp - z > 2.3:
                tz = z + (sp - z) * 0.5
                fbox(mb, f, plane, u - hw - 0.02, u + hw + 0.02, tz - bw / 2, tz + bw / 2, d0, d1, bm_)
            if op.bars == 'fan' and kind == 'round':
                for ang in (45.0, 135.0):
                    ar = math.radians(ang)
                    bar2d(mb, f, plane, (u, sp), (u + (hw + 0.02) * math.cos(ar), sp + (hw + 0.02) * math.sin(ar)),
                          bw, d0, d1, bm_)
    # --- sill (two tiers: nose + drip)
    if op.sill:
        sm_ = op.sill_mat or 'SKY_Pearl'
        e = fts + 0.12
        fbox(kit['small'], f, plane, u - hw - e, u + hw + e, z - 0.09, z + 0.025, -0.07, 0.13, sm_)
        if op.sill != 'simple':
            fbox(kit['none'], f, plane, u - hw - e + 0.07, u + hw + e - 0.07, z - 0.17, z - 0.08, -0.03, 0.075, sm_)
    # --- dark room behind the glass (SKY_Glass is translucent in Unity) + optional curtains
    if op.back == 'SKY_Glass' and op.backing and not op.through:
        fbox(kit['none'], f, plane, u - hw - 0.06, u + hw + 0.06, z - 0.06, z + h + 0.06, -D - 0.34, -D - 0.3,
             op.backing if isinstance(op.backing, str) else 'SKY_Ink')
        if op.curtain:
            cw = w * 0.3
            for s in (-1, 1):
                uc = u + s * (hw - cw / 2 + 0.02)
                fbox(kit['none'], f, plane, uc - cw / 2, uc + cw / 2, z + 0.03, sp + (0.0 if kind == 'flat' else 0.12),
                     -D - 0.2, -D - 0.16, op.curtain)
    # --- open louvred shutters
    if op.shutter:
        g = fts + 0.05
        sw = hw + 0.02
        top = (sp if kind != 'flat' else z + h) - 0.02
        for s in (-1, 1):
            ua, ub = u + s * (hw + g), u + s * (hw + g + sw)
            louvre_leaf(kit, f, plane, min(ua, ub), max(ua, ub), z + 0.05, top, op.shutter)
    # --- geometric lattice screen over the lower half of the glass
    if op.screen:
        top = z + ((sp - z) * 0.5 if kind != 'flat' else h * 0.5)
        lattice_bars(kit['none'], f, plane, (u - hw - 0.02, u + hw + 0.02, z - 0.02, top), -D + 0.07, -D + 0.105,
                     op.screen, spacing=0.17, bw=0.032)
        fbox(kit['small'], f, plane, u - hw - 0.02, u + hw + 0.02, top - 0.015, top + 0.05, -D + 0.06, -D + 0.12,
             op.screen)
    # --- Juliet balcony
    if op.balconette:
        rm = op.balconette
        dp = 0.36
        e = hw + fts + 0.14
        fbox(kit['mid'], f, plane, u - e, u + e, z - 0.13, z + 0.03, -0.05, dp, 'SKY_Pearl')
        fbox(kit['mid'], f, plane, u - e + 0.07, u + e - 0.07, z - 0.24, z - 0.12, -0.03, dp - 0.08, 'SKY_Pearl')
        nb = kit['none']
        rz = z + 0.95
        fbox(kit['small'], f, plane, u - e + 0.02, u + e - 0.02, rz, rz + 0.05, dp - 0.1, dp - 0.04, rm)
        fbox(nb, f, plane, u - e + 0.04, u + e - 0.04, z + 0.12, z + 0.16, dp - 0.09, dp - 0.05, rm)
        for s in (-1, 1):
            ua, ub = u + s * (e - 0.08), u + s * (e - 0.02)
            fbox(kit['small'], f, plane, min(ua, ub), max(ua, ub), rz, rz + 0.05, -0.02, dp - 0.04, rm)
        n = max(4, int((2 * e - 0.1) / 0.13))
        for i in range(n + 1):
            uu = u - e + 0.05 + i * (2 * e - 0.1) / n
            fbox(nb, f, plane, uu - 0.014, uu + 0.014, z + 0.03, rz + 0.01, dp - 0.085, dp - 0.055, rm)
        for s in (-1, 1):
            for k in (1, 2):
                dd = (dp - 0.07) * k / 3
                uu = u + s * (e - 0.05)
                fbox(nb, f, plane, uu - 0.014, uu + 0.014, z + 0.03, rz + 0.01, dd - 0.015, dd + 0.015, rm)
    # --- doors: leaves, panels, fanlight, handles, steps, lamps
    if op.door:
        leaf = op.back
        hr = (sp if kind != 'flat' else z + h) - z
        dl = -D
        n = 2 if w >= 1.25 else 1
        lw = w / n
        sm, nb = kit['small'], kit['none']
        for k in range(n):
            ua, ub = u - hw + k * lw, u - hw + (k + 1) * lw
            ia = ua + (0.1 if (k == 0) else 0.075)
            ib = ub - (0.1 if (k == n - 1) else 0.075)
            fbox(sm, f, plane, ia, ib, z + 0.17, z + 0.17 + hr * 0.3, dl - 0.01, dl + 0.03, leaf)
            fbox(sm, f, plane, ia, ib, z + 0.17 + hr * 0.3 + 0.12, z + hr - 0.13, dl - 0.01, dl + 0.03, leaf)
            fbox(nb, f, plane, ua + 0.04, ub - 0.04, z + 0.015, z + 0.11, dl - 0.005, dl + 0.012, 'SKY_Brass')
        if n == 2:
            fbox(sm, f, plane, u - 0.035, u + 0.035, z, z + hr, dl - 0.01, dl + 0.045, leaf)
            hus = (u - 0.1, u + 0.1)
        else:
            hus = (u + hw - 0.15,)
        for uh in hus:
            fbox(nb, f, plane, uh - 0.02, uh + 0.02, z + 0.88, z + 1.22, dl + 0.035, dl + 0.075, 'SKY_Brass')
        if kind != 'flat':
            tm = op.frame or 'SKY_Pearl'
            fbox(sm, f, plane, u - hw - 0.02, u + hw + 0.02, sp - 0.045, sp + 0.045, dl - 0.01, dl + 0.06, tm)
            head = shift_uv(arch_pts(w + 0.04, h + 0.02, kind, op.seg, base=z - 0.01), u, 0.0)[2:]
            fprism(nb, f, plane, head, dl + 0.002, dl + 0.009, 'SKY_Ink')
            fprism(nb, f, plane, head, dl + 0.009, dl + 0.017, 'SKY_Glass')
            if kind == 'round':
                for ang in (30, 60, 90, 120, 150):
                    ar = math.radians(ang)
                    bar2d(nb, f, plane, (u, sp), (u + (hw + 0.02) * math.cos(ar), sp + (hw + 0.02) * math.sin(ar)),
                          0.035, dl + 0.01, dl + 0.04, 'SKY_Brass')
    if op.steps and z > 0.05:
        n = op.steps
        tread = 0.34
        for k in range(1, n + 1):
            top = z * k / n + (0.012 if k == n else 0.0)
            dk = (n - k + 1) * tread
            ext = 0.16 + (n - k) * 0.12 + fts
            fbox(kit['mid'], f, plane, u - hw - ext, u + hw + ext, 0.0, top, -0.08 if k == n else -0.04, dk,
                 op.step_mat)
    if op.lamp:
        lu = hw + fts + 0.36
        lv = min(sp, z + 2.2) + 0.08
        for s in (-1, 1):
            wall_lamp(kit, f, plane, u + s * lu, lv)


def mass(a, x0, x1, y0, y1, z0, z1, mat, ops=(), name="mass", target=None, fm=None, kit=None, cutters=(),
         pre=(0.06, 2), post=(0.035, 1), refine=REFINE, well=None, roof='SKY_Kerb'):
    """Wall block with openings (+ optional roof well cut from the top, which leaves parapets)."""
    planes = {'N': y0, 'S': y1, 'E': x0, 'W': x1}
    mb = MB()
    mb.box(x0, x1, y0, y1, z0, z1, mat, fm)
    cuts = [op_cutter(op, op.plane if op.plane is not None else planes[op.face], mat) for op in ops]
    if well:
        t, zr = well
        cuts.append(box_cutter(x0 + t, x1 - t, y0 + t, y1 - t, zr, z1 + 1.0, mat, {'bottom': roof}))
    cuts += list(cutters)
    solid(a, mb, cuts, pre=pre, post=post, name=name, target=target, refine=refine)
    k = kit if kit is not None else Kit(a, target, tag=name + "_")
    for op in ops:
        dress(k, op, op.plane if op.plane is not None else planes[op.face])
    if kit is None:
        k.flush()
    return planes


# --------------------------------------------------------------------------- bands and trims

def ring(mb, x0, x1, y0, y1, z0, z1, p, mat, faces='NSEW', embed=0.05):
    """Band projecting p around a rectangular wall outline (closed boxes; N/S own the corners)."""
    xa = x0 - p if 'E' in faces else x0 - 0.012
    xb = x1 + p if 'W' in faces else x1 + 0.012
    if 'N' in faces:
        mb.box(xa, xb, y0 - p, y0 + embed, z0, z1, mat)
    if 'S' in faces:
        mb.box(xa, xb, y1 - embed, y1 + p, z0, z1, mat)
    ya = y0 + embed if 'N' in faces else y0 - 0.012
    yb = y1 - embed if 'S' in faces else y1 + 0.012
    if 'E' in faces:
        mb.box(x0 - p, x0 + embed, ya, yb, z0, z1, mat)
    if 'W' in faces:
        mb.box(x1 - embed, x1 + p, ya, yb, z0, z1, mat)


def tiers(a, x0, x1, y0, y1, z_top, spec, mat, faces='NSEW', name="cornice", bevel=(0.025, 1), target=None):
    """Stacked bands from z_top downward: spec = [(height, projection), ...] (corbelled cornice,
    stepped plinth, string course with drip)."""
    mb = MB()
    zt = z_top
    for i, (hh, p) in enumerate(spec):
        ring(mb, x0, x1, y0, y1, zt - hh, zt + (0.01 if i else 0.0), p, mat, faces)
        zt -= hh
    part_r(a, mb, bevel[0], bevel[1], name, target=target)


def coping(mb, x0, x1, y0, y1, t, z, h, p, mat, faces='NSEW'):
    """Cap strips over parapet walls of thickness t, overhanging p on both sides."""
    if 'N' in faces:
        mb.box(x0 - p, x1 + p, y0 - p, y0 + t + p, z, z + h, mat)
    if 'S' in faces:
        mb.box(x0 - p, x1 + p, y1 - t - p, y1 + p, z, z + h, mat)
    ya = y0 + t + p if 'N' in faces else y0 - p
    yb = y1 - t - p if 'S' in faces else y1 + p
    if 'E' in faces:
        mb.box(x0 - p, x0 + t + p, ya, yb, z, z + h, mat)
    if 'W' in faces:
        mb.box(x1 - t - p, x1 + p, ya, yb, z, z + h, mat)


def merlons2(mb, face, plane, u0, u1, z, h=0.5, w=0.52, gap=0.4, t=0.26, mat='SKY_Pearl', inset=0.0, style='step'):
    """Row of stepped (Gulf) merlons standing on a parapet top."""
    L = u1 - u0
    n = max(1, int((L + gap) / (w + gap)))
    tot = n * w + (n - 1) * gap
    s0 = u0 + (L - tot) / 2
    for i in range(n):
        c = s0 + i * (w + gap) + w / 2
        hw = w / 2
        if style == 'step':
            pts = [(c - hw, z - 0.01), (c + hw, z - 0.01), (c + hw, z + h * 0.48), (c + hw * 0.46, z + h * 0.48),
                   (c + hw * 0.46, z + h), (c - hw * 0.46, z + h), (c - hw * 0.46, z + h * 0.48), (c - hw, z + h * 0.48)]
        elif style == 'tri':
            pts = [(c - hw, z - 0.01), (c + hw, z - 0.01), (c + hw, z + h * 0.45), (c, z + h), (c - hw, z + h * 0.45)]
        else:
            pts = [(c - hw, z - 0.01), (c + hw, z - 0.01), (c + hw, z + h), (c - hw, z + h)]
        fprism(mb, face, plane, pts, -inset - t, -inset, mat)


def quoins(mb, x0, x1, y0, y1, z0, z1, corners='NE NW SE SW', mat='SKY_Pearl', p=0.04, hb=0.42, gap=0.08,
           la=0.62, lb=0.36):
    """Alternating long/short corner blocks."""
    n = max(1, int((z1 - z0 + gap) / (hb + gap)))
    hb2 = (z1 - z0 + gap) / n - gap
    for c in corners.split():
        cx, sx = (x0, -1) if 'E' in c else (x1, 1)
        cy, sy = (y0, -1) if 'N' in c else (y1, 1)
        for i in range(n):
            zb = z0 + i * (hb2 + gap)
            lx, ly = (la, lb) if i % 2 == 0 else (lb, la)
            xa, xb = sorted((cx + sx * p, cx - sx * lx))
            ya, yb = sorted((cy + sy * p, cy - sy * ly))
            mb.box(xa, xb, ya, yb, zb, zb + hb2, mat)


def drainpipe(kit, face, plane, u, z_top, z_bot=0.45, r=0.055, d=0.1, mat='SKY_Metal'):
    """Rainwater head, down pipe with straps; enters the plinth at the bottom."""
    fbox(kit['small'], face, plane, u - 0.12, u + 0.12, z_top - 0.05, z_top + 0.2, -0.01, d + 0.085, mat)
    fbox(kit['small'], face, plane, u - 0.085, u + 0.085, z_top - 0.16, z_top - 0.03, -0.01, d + 0.06, mat)
    c = fpt(face, plane, u, 0.0, d)
    kit['none'].cyl(r, z_bot, z_top - 0.1, 8, mat, cx=c[0], cy=c[1])
    zz = z_bot + 0.75
    while zz < z_top - 0.5:
        fbox(kit['none'], face, plane, u - r - 0.022, u + r + 0.022, zz, zz + 0.05, -0.01, d + r + 0.018, mat)
        zz += 1.45


def scupper(kit, face, plane, u, z, mat='SKY_Metal'):
    fbox(kit['none'], face, plane, u - 0.07, u + 0.07, z, z + 0.08, -0.05, 0.16, mat)


# --------------------------------------------------------------------------- roof furniture

def ac_unit(kit, x, y, z, rot=0.0, w=0.95, dd=0.55, h=0.6, body='SKY_Pearl'):
    """Condenser: feet, body, fan disk with rim and guard bars, side grille."""
    L = Local(kit, M_tr(x, y, z) @ M_rot(rot))
    for sx in (-1, 1):
        L('none').box(sx * (w / 2 - 0.09) - 0.045, sx * (w / 2 - 0.09) + 0.045, -dd / 2 + 0.02, dd / 2 - 0.02,
                      0.0, 0.08, 'SKY_Metal')
    L('mid').box(-w / 2, w / 2, -dd / 2, dd / 2, 0.08, 0.08 + h, body)
    zc, xc, r = 0.08 + h / 2, -w * 0.17, h * 0.35
    Mf = M_tr(xc, -dd / 2 + 0.005, zc) @ M_rot(90.0, 'X')
    fs = L('none').lathe([(0.0, 0.0), (r, 0.0), (r, 0.025), (0.0, 0.025)], 10, 'SKY_Ink')
    L.move('none', fs, Mf)
    fs = L('none').lathe([(r - 0.005, 0.0), (r + 0.035, 0.0), (r + 0.035, 0.045), (r - 0.005, 0.045)], 10, 'SKY_Metal',
                         closed=True)
    L.move('none', fs, Mf)
    for ang in (45.0, -45.0):
        fs = L('none').box(-r, r, -0.008, 0.008, 0.03, 0.05, 'SKY_Metal')
        L.move('none', fs, Mf @ M_rot(ang, 'Z'))
    fs = L('none').cyl(0.06, 0.02, 0.06, 8, 'SKY_Metal')
    L.move('none', fs, Mf)
    L('none').box(w * 0.14, w / 2 - 0.07, -dd / 2 - 0.012, -dd / 2 + 0.01, 0.16, 0.08 + h - 0.08, 'SKY_Ink')
    L.done()


def water_tank(kit, x, y, z, r=0.42, h=0.8, legs=0.5, body='SKY_Pearl', band='SKY_Teal'):
    """Rooftop water tank on a steel stand."""
    L = Local(kit, M_tr(x, y, z))
    o = r * 0.72
    for sx in (-1, 1):
        for sy in (-1, 1):
            L('none').box(sx * o - 0.035, sx * o + 0.035, sy * o - 0.035, sy * o + 0.035, 0.0, legs, 'SKY_Metal')
    L('none').box(-o - 0.06, o + 0.06, -o - 0.06, o + 0.06, legs - 0.07, legs, 'SKY_Metal')
    for s in (-1, 1):
        L('none').box(-o, o, s * o - 0.02, s * o + 0.02, legs * 0.35, legs * 0.35 + 0.04, 'SKY_Metal')
    L('none').lathe([(0.0, legs), (r, legs), (r, legs + h), (r * 0.86, legs + h + 0.1), (0.13, legs + h + 0.17),
                     (0.13, legs + h + 0.24), (0.0, legs + h + 0.24)], 10, body)
    zz = legs + h * 0.62
    L('none').lathe([(r - 0.01, zz), (r + 0.025, zz), (r + 0.025, zz + 0.06), (r - 0.01, zz + 0.06)], 10, band,
                    closed=True)
    L.done()


def roof_hatch(kit, x, y, z, s=0.85, rot=0.0):
    L = Local(kit, M_tr(x, y, z) @ M_rot(rot))
    L('mid').box(-s / 2, s / 2, -s / 2, s / 2, 0.0, 0.32, 'SKY_Pearl')
    L('mid').box(-s / 2 - 0.05, s / 2 + 0.05, -s / 2 - 0.05, s / 2 + 0.05, 0.32, 0.4, 'SKY_Metal')
    L('none').box(-0.14, 0.14, -s / 2 - 0.09, -s / 2 - 0.05, 0.26, 0.36, 'SKY_Brass')
    L.done()


def vent_stack(kit, x, y, z, h=0.7, r=0.075, mat='SKY_Metal'):
    nb = kit['none']
    nb.cyl(r, z, z + h, 8, mat, cx=x, cy=y)
    nb.lathe([(0.0, z + h - 0.03), (r + 0.09, z + h + 0.02), (r + 0.09, z + h + 0.06), (0.05, z + h + 0.14),
              (0.0, z + h + 0.15)], 8, mat, cx=x, cy=y)


def blob(mb, x, y, z, r, mat='SKY_PalmLeaf', seg=7, sz=0.85):
    mb.sphere(r, seg, 4, mat, c=(x, y, z + r * sz * 0.8), sz=sz)


def pot(kit, x, y, z, r=0.2, h=0.36, plant='leaf', mat='SKY_Terracotta', seed=0):
    rnd = random.Random(seed)
    kit['none'].lathe([(0.0, z), (r * 0.7, z), (r, z + h * 0.84), (r + 0.03, z + h * 0.86), (r + 0.03, z + h),
                       (r - 0.025, z + h), (r - 0.025, z + h * 0.9), (0.0, z + h * 0.9)], 8, mat,
                      mats=[mat] * 6 + ['SKY_PalmTrunk'])
    if plant:
        zt = z + h * 0.86
        blob(kit['none'], x, y, zt, r * 1.25, 'SKY_PalmLeaf')
        if plant == 'flower':
            for k in range(3):
                a_ = rnd.uniform(0, 6.28)
                blob(kit['none'], x + math.cos(a_) * r * 0.7, y + math.sin(a_) * r * 0.7, zt + r * 0.9, r * 0.55,
                     'SKY_Flower', seg=5)


def planter2(kit, x, y, z, w, d, h=0.5, mat='SKY_Terracotta', rim='SKY_Pearl', flowers=True, seed=0, cls='mid'):
    """Box planter with a pearl cap rim, soil and a row of shrubs (with bougainvillea dots)."""
    rnd = random.Random(seed)
    kit[cls].box(x - w / 2, x + w / 2, y - d / 2, y + d / 2, z, z + h - 0.05, mat)
    kit[cls].box(x - w / 2 - 0.04, x + w / 2 + 0.04, y - d / 2 - 0.04, y + d / 2 + 0.04, z + h - 0.07, z + h, rim)
    kit['none'].box(x - w / 2 + 0.05, x + w / 2 - 0.05, y - d / 2 + 0.05, y + d / 2 - 0.05, z + h - 0.01, z + h + 0.03,
                    'SKY_PalmTrunk')
    L_ = max(w, d)
    rr = min(0.38, max(0.17, min(w, d) * 0.55))
    n = max(1, int(round(L_ / (1.75 * rr))))
    for i in range(n):
        t = (i + 0.5) / n
        px, py = (x - w / 2 + t * w, y) if w >= d else (x, y - d / 2 + t * d)
        px += rnd.uniform(-0.05, 0.05)
        py += rnd.uniform(-0.05, 0.05)
        r_ = rr * rnd.uniform(0.85, 1.1)
        blob(kit['none'], px, py, z + h - 0.02, r_, 'SKY_PalmLeaf')
        if flowers and i % 2 == 0:
            blob(kit['none'], px + rnd.uniform(-0.1, 0.1), py + rnd.uniform(-0.1, 0.1), z + h + r_ * 0.9, r_ * 0.5,
                 'SKY_Flower', seg=5)


def vine(kit, pts, r=0.22, seed=0, flower_every=2):
    """Bougainvillea clump: overlapping leaf blobs with magenta flower blobs along a path."""
    rnd = random.Random(seed)
    for i, p in enumerate(pts):
        r_ = r * rnd.uniform(0.8, 1.15)
        blob(kit['none'], p[0], p[1], p[2] - r_ * 0.7, r_, 'SKY_PalmLeaf', seg=6)
        if i % flower_every == 0:
            blob(kit['none'], p[0] + rnd.uniform(-0.1, 0.1), p[1] + rnd.uniform(-0.1, 0.1), p[2] - r_ * 0.2,
                 r_ * 0.62, 'SKY_Flower', seg=5)


def pergola2(kit, x0, x1, y0, y1, z, h=2.4, post=0.2, beam_dir='x', slats=9, sail='SKY_Fabric',
             mat='SKY_Wood', post_mat='SKY_Pearl', over=0.3, mid_posts=0):
    """Pearl-post timber pergola with shaped beam ends, slats and a sagging shade sail."""
    pp = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
    for k in range(1, mid_posts + 1):
        if beam_dir == 'x':
            xm = x0 + (x1 - x0) * k / (mid_posts + 1)
            pp += [(xm, y0), (xm, y1)]
        else:
            ym = y0 + (y1 - y0) * k / (mid_posts + 1)
            pp += [(x0, ym), (x1, ym)]
    for (x, y) in pp:
        kit['mid'].box(x - post / 2, x + post / 2, y - post / 2, y + post / 2, z, z + h, post_mat)
        kit['none'].box(x - post / 2 - 0.05, x + post / 2 + 0.05, y - post / 2 - 0.05, y + post / 2 + 0.05, z - 0.01,
                        z + 0.2, post_mat)
    bt, bh = 0.14, 0.24
    if beam_dir == 'x':
        for y in (y0, y1):
            pts = [(x0 - over, z + h + bh * 0.35), (x0 - over + 0.12, z + h), (x1 + over - 0.12, z + h),
                   (x1 + over, z + h + bh * 0.35), (x1 + over, z + h + bh), (x0 - over, z + h + bh)]
            kit['small'].prism_frame(pts, (0, y - bt / 2, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), 0.0, bt, mat)
        for i in range(slats):
            x = x0 + (x1 - x0) * (i + 0.5) / slats
            kit['none'].box(x - 0.05, x + 0.05, y0 - over - 0.05, y1 + over + 0.05, z + h + bh, z + h + bh + 0.1, mat)
    else:
        for x in (x0, x1):
            pts = [(y0 - over, z + h + bh * 0.35), (y0 - over + 0.12, z + h), (y1 + over - 0.12, z + h),
                   (y1 + over, z + h + bh * 0.35), (y1 + over, z + h + bh), (y0 - over, z + h + bh)]
            kit['small'].prism_frame(pts, (x - bt / 2, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), 0.0, bt, mat)
        for i in range(slats):
            y = y0 + (y1 - y0) * (i + 0.5) / slats
            kit['none'].box(x0 - over - 0.05, x1 + over + 0.05, y - 0.05, y + 0.05, z + h + bh, z + h + bh + 0.1, mat)
    if sail:
        sail_mesh(kit['none'], [(x0 + 0.12, y0 + 0.12, z + h - 0.06), (x1 - 0.12, y0 + 0.12, z + h - 0.3),
                                (x1 - 0.12, y1 - 0.12, z + h - 0.06), (x0 + 0.12, y1 - 0.12, z + h - 0.3)], sail,
                  sag=0.18, n=4, t=0.025)


def finial(mb, x, y, z, s=1.0, mat='SKY_Brass'):
    mb.lathe([(0.0, z), (0.12 * s, z), (0.12 * s, z + 0.06 * s), (0.05 * s, z + 0.12 * s), (0.1 * s, z + 0.18 * s),
              (0.12 * s, z + 0.25 * s), (0.1 * s, z + 0.32 * s), (0.04 * s, z + 0.38 * s), (0.025 * s, z + 0.55 * s),
              (0.0, z + 0.72 * s)], 8, mat, cx=x, cy=y)


def dome2(kit, cx, cy, z, r, mat='SKY_Teal', rib='SKY_Pearl', seg=24, rings=8, ribs=8, onion=1.0,
          base='SKY_Brass', top=True, rib_stop=0.86, fin=1.0):
    """Ribbed dome: smooth shell, raised meridian ribs, brass base ring and finial."""
    prof = [(0.0, z)]
    for i in range(rings + 1):
        ang = (i / rings) * math.pi / 2
        prof.append((r * math.cos(ang), z + r * math.sin(ang) * onion))
    prof[-1] = (0.0, prof[-1][1])
    kit['none'].lathe(prof, seg, mat, cx=cx, cy=cy)
    kit['none'].lathe([(r - 0.03, z - 0.03), (r + 0.06, z - 0.03), (r + 0.06, z + 0.09), (r - 0.03, z + 0.09)], seg,
                      base, cx=cx, cy=cy, closed=True)
    if ribs:
        rw, ro = max(0.03, r * 0.035), max(0.022, r * 0.025)
        n = 5 if r < 1.5 else 8
        for k in range(ribs):
            az = 2 * math.pi * k / ribs + math.pi / ribs
            e = Vector((math.cos(az), math.sin(az), 0.0))
            q = Vector((-math.sin(az), math.cos(az), 0.0))
            rings_ = []
            for i in range(n + 1):
                ph = (i / n) * (math.pi / 2) * rib_stop
                nrm = (e * math.cos(ph) + Vector((0, 0, math.sin(ph) * onion))).normalized()
                c = Vector((cx, cy, z)) + e * (r * math.cos(ph)) + Vector((0, 0, r * math.sin(ph) * onion))
                wq = rw * (1.0 - 0.55 * i / n)
                rings_.append([c - q * wq - nrm * 0.03, c + q * wq - nrm * 0.03, c + q * wq + nrm * ro,
                               c - q * wq + nrm * ro])
            kit['none'].loft(rings_, rib)
    if top:
        zt = z + r * onion
        finial(kit['none'], cx, cy, zt - 0.04, fin)


def oriel(kit, face, plane, u, z, w, h, d=0.55, mat='SKY_Wood', frame='SKY_Pearl', spacing=0.22):
    """Projecting mashrabiya bay: corbelled base, pearl frame and cheeks, wood lattice, stepped cap."""
    hw = w / 2
    fbox(kit['mid'], face, plane, u - hw - 0.08, u + hw + 0.08, z - 0.14, z, -0.03, d + 0.1, frame)
    fbox(kit['mid'], face, plane, u - hw + 0.02, u + hw - 0.02, z - 0.27, z - 0.13, -0.03, d - 0.02, frame)
    fbox(kit['mid'], face, plane, u - hw + 0.22, u + hw - 0.22, z - 0.38, z - 0.26, -0.03, d - 0.18, frame)
    for s in (-1, 1):
        ua, ub = u + s * (hw - 0.02), u + s * (hw + 0.08)
        fbox(kit['mid'], face, plane, min(ua, ub), max(ua, ub), z, z + h, -0.03, d + 0.06, frame)
    fbox(kit['mid'], face, plane, u - hw - 0.12, u + hw + 0.12, z + h, z + h + 0.12, -0.03, d + 0.14, frame)
    fbox(kit['mid'], face, plane, u - hw - 0.18, u + hw + 0.18, z + h + 0.12, z + h + 0.2, -0.03, d + 0.2, frame)
    fbox(kit['mid'], face, plane, u - 0.45, u + 0.45, z + h + 0.2, z + h + 0.36, -0.03, d - 0.02, frame)
    fbox(kit['mid'], face, plane, u - 0.2, u + 0.2, z + h + 0.36, z + h + 0.5, -0.03, d - 0.06, frame)
    lattice_bars(kit['none'], face, plane, (u - hw - 0.02, u + hw + 0.02, z - 0.02, z + h + 0.02), d - 0.06, d - 0.02,
                 mat, spacing, bw=0.04)
    fbox(kit['none'], face, plane, u - hw, u + hw, z + h * 0.42 - 0.03, z + h * 0.42 + 0.03, d - 0.08, d - 0.0, mat)
    fbox(kit['none'], face, plane, u - hw - 0.02, u + hw + 0.02, z - 0.02, z + h + 0.02, d - 0.36, d - 0.32, 'SKY_Ink')


def balcony2(kit, face, plane, u, z, w, dp=1.0, style='glass', rail='SKY_Brass', glass='SKY_TealLight',
             slab='SKY_Pearl', corbels=3, pots=True, seed=0):
    """Balcony: stepped slab edge, console brackets, balustrade (glass / lattice / bars), pots."""
    hw = w / 2
    fbox(kit['trim'], face, plane, u - hw, u + hw, z - 0.16, z, -0.04, dp, slab)
    fbox(kit['mid'], face, plane, u - hw + 0.08, u + hw - 0.08, z - 0.27, z - 0.15, -0.04, dp - 0.09, slab)
    for i in range(corbels):
        uu = u - hw + 0.32 + i * (w - 0.64) / max(1, corbels - 1)
        pts = [(-0.03, z - 0.265), (dp - 0.2, z - 0.265), (dp - 0.2, z - 0.33), (0.16, z - 0.64), (-0.03, z - 0.64)]
        fprism_side(kit['small'], face, plane, pts, uu - 0.07, uu + 0.07, slab)
    sm, nb = kit['small'], kit['none']
    rz = z + 0.98
    # handrail front + sides
    fbox(sm, face, plane, u - hw + 0.03, u + hw - 0.03, rz, rz + 0.07, dp - 0.12, dp - 0.03, rail)
    for s in (-1, 1):
        ua, ub = u + s * (hw - 0.12), u + s * (hw - 0.03)
        fbox(nb, face, plane, min(ua, ub), max(ua, ub), rz, rz + 0.07, -0.02, dp - 0.12, rail)
    # posts
    for uu in (u - hw + 0.075, u + hw - 0.075):
        fbox(nb, face, plane, uu - 0.03, uu + 0.03, z, rz, dp - 0.105, dp - 0.045, rail)
    if style == 'glass':
        fbox(nb, face, plane, u - hw + 0.1, u + hw - 0.1, z + 0.07, rz - 0.02, dp - 0.085, dp - 0.065, glass)
        for s in (-1, 1):
            ua, ub = u + s * (hw - 0.085), u + s * (hw - 0.065)
            fbox(nb, face, plane, min(ua, ub), max(ua, ub), z + 0.07, rz - 0.02, 0.02, dp - 0.1, glass)
        fbox(nb, face, plane, u - hw + 0.08, u + hw - 0.08, z + 0.02, z + 0.07, dp - 0.1, dp - 0.05, rail)
    elif style == 'lattice':
        lattice_bars(nb, face, plane, (u - hw + 0.1, u + hw - 0.1, z + 0.02, rz + 0.01), dp - 0.09, dp - 0.06, rail,
                     spacing=0.2, bw=0.035)
        for s in (-1, 1):
            # side cheeks as solid panels
            ua, ub = u + s * (hw - 0.1), u + s * (hw - 0.05)
            fbox(sm, face, plane, min(ua, ub), max(ua, ub), z, rz, -0.02, dp - 0.08, slab)
    else:
        n = max(4, int((w - 0.2) / 0.14))
        for i in range(n + 1):
            uu = u - hw + 0.1 + i * (w - 0.2) / n
            fbox(nb, face, plane, uu - 0.016, uu + 0.016, z, rz, dp - 0.09, dp - 0.06, rail)
        for s in (-1, 1):
            for k in (1, 2, 3):
                dd = (dp - 0.1) * k / 4
                uu = u + s * (hw - 0.075)
                fbox(nb, face, plane, uu - 0.016, uu + 0.016, z, rz, dd - 0.016, dd + 0.016, rail)
    if pots:
        for k, s in enumerate((-1, 1) if pots is True else (-1,)):
            c = fpt(face, plane, u + s * (hw - 0.32), z, dp - 0.36)
            pot(kit, c[0], c[1], z, r=0.15, h=0.3, plant='flower' if k == 0 else 'leaf', seed=seed + k)


def awning2(kit, face, plane, u, z, w, depth=0.9, drop=0.42, mats=('SKY_Coral', 'SKY_Pearl'), stripes=6,
            valance=0.24, t=0.035, arms=True):
    """Striped sloped awning with a scalloped valance, side cheeks, brass rail and arms."""
    uax, vax, out = faxes(face)
    o = fpt(face, plane, 0.0, 0.0, 0.0)
    origin = (o[0] if face in ('E', 'W') else 0.0, o[1] if face in ('N', 'S') else 0.0, 0.0)
    nb = kit['none']
    prof = [(0.0, z), (depth, z - drop), (depth, z - drop - t), (0.0, z - t)]
    sw = w / stripes
    for i in range(stripes):
        u0 = u - w / 2 + i * sw
        m = mats[i % len(mats)]
        nb.prism_frame(prof, origin, out, (0, 0, 1), uax, u0, u0 + sw, m)
        vt = z - drop + 0.005
        vb = z - drop - valance
        sh = min(0.09, valance * 0.4)
        pts = [(u0, vt), (u0 + sw, vt)]
        for k in range(7):
            th = -math.pi * k / 6
            pts.append((u0 + sw / 2 + (sw / 2) * math.cos(th), vb + sh + sh * math.sin(th)))
        fprism(nb, face, plane, pts, depth - t, depth, m)
    for s in (-1, 1):
        ue = u + s * (w / 2)
        ua, ub = sorted((ue, ue - s * 0.03))
        side = [(0.0, z), (depth, z - drop), (depth, z - drop - valance * 0.65), (0.0, z - 0.12)]
        nb.prism_frame(side, origin, out, (0, 0, 1), uax, ua, ub, mats[0])
    fbox(kit['small'], face, plane, u - w / 2 - 0.05, u + w / 2 + 0.05, z - 0.03, z + 0.09, -0.01, 0.1, 'SKY_Brass')
    if arms:
        for s in (-1, 1):
            ue = u + s * (w / 2 - 0.05)
            p0 = Vector(fpt(face, plane, ue, z - drop - 0.45, 0.0))
            p1 = Vector(fpt(face, plane, ue, z - drop - 0.02, depth - 0.06))
            nb.sweep([p0, p1], circle(0.018, 5), 'SKY_Brass')


def solar2(kit, x0, x1, y0, y1, z, rows=2, tilt=16.0, legs_mat='SKY_Metal'):
    """Tilted solar rows: ink panels, teal frames and cell lines, metal legs."""
    dy = (y1 - y0) / rows
    for r in range(rows):
        ya, yb = y0 + r * dy + 0.12, y0 + (r + 1) * dy - 0.12
        hgt = (yb - ya) * math.tan(math.radians(tilt))
        za = z + 0.32
        pts = [(ya, za), (yb, za + hgt), (yb, za + hgt + 0.07), (ya, za + 0.07)]
        kit['small'].prism_frame(pts, (0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), x0, x1, 'SKY_Ink', front='SKY_Teal',
                                 back='SKY_Teal')
        n = max(1, int(round((x1 - x0) / 0.62)))
        for k in range(1, n):
            xx = x0 + (x1 - x0) * k / n
            p = [(ya + 0.01, za + 0.07), (yb - 0.01, za + hgt + 0.07), (yb - 0.01, za + hgt + 0.085), (ya + 0.01, za + 0.085)]
            kit['none'].prism_frame(p, (0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), xx - 0.018, xx + 0.018, 'SKY_Teal')
        for ye in (ya + 0.02, yb - 0.02):
            zz = za + (ye - ya) / (yb - ya) * hgt
            kit['none'].box(x0, x1, ye - 0.025, ye + 0.025, zz + 0.06, zz + 0.09, 'SKY_Teal')
        for xx in frange(x0 + 0.25, x1 - 0.25, 1.6):
            kit['none'].box(xx - 0.04, xx + 0.04, yb - 0.12, yb - 0.04, z, za + hgt + 0.01, legs_mat)
            kit['none'].box(xx - 0.04, xx + 0.04, ya + 0.04, ya + 0.12, z, za + 0.01, legs_mat)
            kit['none'].box(xx - 0.03, xx + 0.03, ya + 0.04, yb - 0.04, z + 0.12, z + 0.17, legs_mat)


def wind_tower2(a, kit, x, y, z0, z1, s=1.9, mat='SKY_Pearl', trim='SKY_Sandstone', slots=2, glow=True):
    """Barjeel: slotted shaft, brass band, stepped cornice cap with corner pinnacles, teal glow at the slots."""
    hs = s / 2
    slot_h = min(2.2, (z1 - z0) * 0.48)
    sz = z1 - 0.5 - slot_h
    sw = (s - 0.5) / slots - 0.15
    ops = []
    for f in 'NSEW':
        for k in range(slots):
            c = -hs + 0.25 + (k + 0.5) * (s - 0.5) / slots
            uu = (x if f in 'NS' else y) + c
            ops.append(Op(f, uu, sz, sw, slot_h, 'pointed', depth=0.3, back='SKY_Ink', sill=False, seg=6, backing=False))
    mass(a, x - hs, x + hs, y - hs, y + hs, z0, z1, mat, ops, name="windtower", kit=kit, pre=(0.045, 2),
         post=(0.025, 1))
    planes = {'N': y - hs, 'S': y + hs, 'E': x - hs, 'W': x + hs}
    for op in ops:
        pl = planes[op.face]
        for k in range(2):
            vv = op.z + 0.45 + k * (spring_of(op.w, op.h, 'pointed', op.z) - op.z - 0.55)
            fbox(kit['none'], op.face, pl, op.u - op.w / 2 - 0.02, op.u + op.w / 2 + 0.02, vv, vv + 0.05, -0.2, -0.14,
                 'SKY_Pearl')
        if glow:
            fbox(kit['none'], op.face, pl, op.u - op.w / 2 + 0.02, op.u + op.w / 2 - 0.02, op.z - 0.01, op.z + 0.05,
                 -0.29, -0.2, 'SKY_TealGlow')
    ring(kit['none'], x - hs, x + hs, y - hs, y + hs, sz - 0.3, sz - 0.18, 0.05, 'SKY_Brass')
    ring(kit['mid'], x - hs, x + hs, y - hs, y + hs, z1 - 0.06, z1 + 0.12, 0.1, trim)
    ring(kit['mid'], x - hs, x + hs, y - hs, y + hs, z1 + 0.11, z1 + 0.22, 0.17, trim)
    kit['mid'].box(x - hs + 0.12, x + hs - 0.12, y - hs + 0.12, y + hs - 0.12, z1 + 0.2, z1 + 0.34, mat)
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = x + sx * (hs - 0.05), y + sy * (hs - 0.05)
            kit['mid'].box(px - 0.17, px + 0.17, py - 0.17, py + 0.17, z1 + 0.2, z1 + 0.55, mat)
            kit['mid'].box(px - 0.1, px + 0.1, py - 0.1, py + 0.1, z1 + 0.55, z1 + 0.75, mat)


def palm2(kit, x, y, z, height=6.0, lean=(0.3, 0.0), fronds=8, frond_len=2.6, r0=0.24, r1=0.17, seed=1,
          frond_seg=4, trunk_seg=8, sides=6, blade=0.4):
    """Light stylised date palm for courtyards: ringed curved trunk, crown bulb, arching closed-shell fronds."""
    rnd = random.Random(seed)
    base = Vector((x, y, z))
    top = base + Vector((lean[0], lean[1], height))
    ctrl = base + Vector((lean[0] * 0.15, lean[1] * 0.15, height * 0.55))
    path = []
    for i in range(trunk_seg + 1):
        t = i / trunk_seg
        path.append(base * (1 - t) ** 2 + ctrl * 2 * t * (1 - t) + top * t * t)
    scales = []
    for i in range(trunk_seg + 1):
        t = i / trunk_seg
        r = (r0 * (1 - t) + r1 * t) * (1.0 + 0.35 * max(0.0, 0.25 - t) * 4)
        scales.append(r * (1.0 if i % 2 == 0 else 0.9))
    nb = kit['none']
    nb.sweep(path, circle(1.0, sides, a0=rnd.random() * 30), 'SKY_PalmTrunk', scales=scales)
    nb.sphere(r1 * 1.5, sides, 3, 'SKY_PalmTrunk', c=(top.x, top.y, top.z + 0.05), sz=1.15)
    tang = (path[-1] - path[-2]).normalized()
    for k in range(fronds):
        phi = math.radians(k * 137.5 + rnd.uniform(-12, 12))
        tier = k / max(1, fronds - 1)
        elev = math.radians(lerp(55, -2, tier) + rnd.uniform(-6, 6))
        Lf = frond_len * lerp(0.84, 1.05, 1 - abs(tier - 0.45)) * rnd.uniform(0.92, 1.06)
        d = Vector((math.cos(phi) * math.cos(elev), math.sin(phi) * math.cos(elev), math.sin(elev)))
        d = (d + tang * 0.25).normalized()
        start = top + Vector((0, 0, 0.1)) + Vector((d.x, d.y, 0)).normalized() * r1 * 0.9
        pts = [start]
        step = Lf / frond_seg
        droop = math.radians(lerp(14, 24, tier) + rnd.uniform(0, 4))
        cur = d.copy()
        side_ax = Vector((-math.sin(phi), math.cos(phi), 0.0))
        for s_ in range(frond_seg):
            pts.append(pts[-1] + cur * step)
            cur = (Matrix.Rotation(droop, 3, side_ax) @ cur).normalized()
        T, B = [], []
        for i, p in enumerate(pts):
            t = i / frond_seg
            if i == 0:
                tdir = (pts[1] - pts[0]).normalized()
            elif i == frond_seg:
                tdir = (pts[-1] - pts[-2]).normalized()
            else:
                tdir = (pts[i + 1] - pts[i - 1]).normalized()
            sv = tdir.cross(Vector((0, 0, 1)))
            if sv.length < 1e-4:
                sv = side_ax.copy()
            sv.normalize()
            up = sv.cross(tdir).normalized()
            if up.z < 0:
                up = -up
            w = blade * math.sin(math.pi * min(1.0, t * 1.08) ** 0.75) + 0.02
            if 0 < i < frond_seg:
                w *= 1.25 if i % 2 else 0.7
            fold = 0.22 * w
            ring = [p + sv * w - up * fold * 0.5, p + up * fold, p - sv * w - up * fold * 0.5]
            T.append([nb.v(q) for q in ring])
            B.append([nb.v(q - up * 0.025) for q in ring])
        fs = []
        for i in range(frond_seg):
            for j in range(2):
                fs.append(nb.f([T[i][j], T[i + 1][j], T[i + 1][j + 1], T[i][j + 1]], 'SKY_PalmLeaf'))
                fs.append(nb.f([B[i][j + 1], B[i + 1][j + 1], B[i + 1][j], B[i][j]], 'SKY_PalmLeaf'))
            fs.append(nb.f([T[i][0], B[i][0], B[i + 1][0], T[i + 1][0]], 'SKY_PalmLeaf'))
            fs.append(nb.f([T[i + 1][2], B[i + 1][2], B[i][2], T[i][2]], 'SKY_PalmLeaf'))
        for ri in (0, frond_seg):
            fs.append(nb.f([T[ri][0], T[ri][1], T[ri][2], B[ri][2], B[ri][1], B[ri][0]], 'SKY_PalmLeaf'))
        nb._recalc(fs)
    return top


def fdisc(mb, face, plane, u, v, r, d0, d1, mat, seg=12, r_in=None):
    """Disc (or ring with r_in) standing proud of a facade between outward distances d0..d1."""
    if r_in:
        fs = mb.lathe([(r_in, d0), (r, d0), (r, d1), (r_in, d1)], seg, mat, closed=True)
    else:
        fs = mb.lathe([(0.0, d0), (r, d0), (r, d1), (0.0, d1)], seg, mat)
    R = {'N': M_rot(90.0, 'X'), 'S': M_rot(-90.0, 'X'), 'E': M_rot(-90.0, 'Y'), 'W': M_rot(90.0, 'Y')}[face]
    c = fpt(face, plane, u, v, 0.0)
    mb.transform(M_tr(*c) @ R, faces=fs)
    return fs


def masts_sail(kit, corners, mast_h=None, mat='SKY_Fabric', sag=0.16, n=4):
    """Shade sail on slim brass masts with ball tops and tension cables to the mast heads."""
    for (x, y, z0, zt) in corners:
        kit['none'].cyl(0.06, z0, zt + 0.12, 6, 'SKY_Brass', cx=x, cy=y)
        kit['none'].sphere(0.09, 6, 3, 'SKY_Brass', c=(x, y, zt + 0.16))
    pts = [(x + (0.0), y, zt) for (x, y, z0, zt) in corners]
    cen = Vector((sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts), 0.0))
    inner = []
    for p in pts:
        d = Vector((p[0], p[1], 0.0)) - cen
        q = Vector(p) - d.normalized() * 0.35
        inner.append((q.x, q.y, p[2] - 0.08))
    sail_mesh(kit['none'], inner, mat, sag=sag, n=n, t=0.025)
    for p, q in zip(pts, inner):
        kit['none'].sweep([Vector(p), Vector(q)], circle(0.012, 4), 'SKY_Metal')


def pendant(kit, x, y, z_top, drop=0.6, mat='SKY_Brass'):
    """Hanging lantern: rod, brass cap, warm glass body."""
    kit['none'].box(x - 0.015, x + 0.015, y - 0.015, y + 0.015, z_top - drop + 0.3, z_top + 0.02, mat)
    zb = z_top - drop
    kit['none'].lathe([(0.0, zb), (0.04, zb), (0.085, zb + 0.06), (0.085, zb + 0.24), (0.12, zb + 0.27),
                       (0.04, zb + 0.34), (0.0, zb + 0.36)], 6, mat,
                      mats=[mat, mat, 'SKY_Light', mat, mat, mat], cx=x, cy=y)


def shopfront(kit, face, plane, u, z, w, h, door=False, sign=None, frame='SKY_Teal', depth=2.4, seed=0):
    """Glazed shopfront set into a deep room cut: stall riser, mullions, transom, optional glass door,
    signboard panel above, and a simple interior (shelves with goods, counter, pendant lamp)."""
    rnd = random.Random(seed)
    hw = w / 2
    nb = sm = kit['none']
    zt = z + h
    tz = zt - 0.62
    rz = z + 0.5
    du = w / 3
    for s in (-1, 1):
        ua, ub = u + s * (hw + 0.02), u + s * (hw - 0.07)
        fbox(sm, face, plane, min(ua, ub), max(ua, ub), z - 0.02, zt + 0.02, -0.3, -0.14, frame)
    fbox(sm, face, plane, u - hw - 0.02, u + hw + 0.02, zt - 0.08, zt + 0.02, -0.3, -0.14, frame)
    fbox(nb, face, plane, u - hw, u + hw, tz - 0.035, tz + 0.035, -0.28, -0.16, frame)
    for k in (-1, 1):
        fbox(nb, face, plane, u + k * du / 2 - 0.03, u + k * du / 2 + 0.03, z, zt, -0.28, -0.16, frame)
    if door:
        for s in (-1, 1):
            ua, ub = u + s * (hw + 0.02), u + s * du / 2
            fbox(sm, face, plane, min(ua, ub), max(ua, ub), z - 0.02, rz, -0.32, -0.12, frame)
        fbox(nb, face, plane, u - du / 2 + 0.03, u + du / 2 - 0.03, z + 0.02, z + 0.1, -0.24, -0.18, 'SKY_Brass')
        fbox(nb, face, plane, u - du / 2 + 0.12, u + du / 2 - 0.12, z + 1.0, z + 1.05, -0.17, -0.12, 'SKY_Brass')
    else:
        fbox(sm, face, plane, u - hw - 0.02, u + hw + 0.02, z - 0.02, rz, -0.32, -0.12, frame)
    fbox(nb, face, plane, u - hw - 0.02, u + hw + 0.02, (z if door else rz - 0.02), zt, -0.23, -0.21, 'SKY_Glass')
    if sign:
        fbox(kit['mid'], face, plane, u - hw + 0.05, u + hw - 0.05, zt + 0.16, zt + 0.66, -0.01, 0.06, sign)
        fbox(nb, face, plane, u - hw + 0.02, u + hw - 0.02, zt + 0.13, zt + 0.17, -0.01, 0.075, 'SKY_Brass')
        fbox(nb, face, plane, u - hw + 0.02, u + hw - 0.02, zt + 0.65, zt + 0.69, -0.01, 0.075, 'SKY_Brass')
    db = -depth
    fbox(nb, face, plane, u - hw + 0.12, u + hw - 0.12, z, z + 2.1, db + 0.02, db + 0.38, 'SKY_Wood')
    for lv in (z + 1.1,):
        x_ = u - hw + 0.25
        while x_ < u + hw - 0.35:
            ww = rnd.uniform(0.18, 0.32)
            hh = rnd.uniform(0.18, 0.4)
            m = rnd.choice(('SKY_Coral', 'SKY_TealLight', 'SKY_Pearl', 'SKY_Terracotta', 'SKY_Flower'))
            fbox(nb, face, plane, x_, x_ + ww, lv, lv + hh, db + 0.38, db + 0.5, m)
            x_ += ww + rnd.uniform(0.06, 0.16)
    cu = u + (hw * 0.35 if seed % 2 else -hw * 0.35)
    fbox(nb, face, plane, cu - 0.55, cu + 0.55, z, z + 0.92, db + 1.0, db + 1.5, 'SKY_Wood')
    fbox(nb, face, plane, cu - 0.6, cu + 0.6, z + 0.92, z + 0.98, db + 0.95, db + 1.55, 'SKY_Pearl')
    c = fpt(face, plane, u, 0.0, db + 1.2)
    pendant(kit, c[0], c[1], zt + 0.05, drop=0.7)


def blade_sign(kit, face, plane, u, v, mat='SKY_Teal', w=0.7, h=0.5):
    """Hanging blade sign on a brass bracket, perpendicular to the facade (blank panel, no text)."""
    fbox(kit['none'], face, plane, u - 0.02, u + 0.02, v, v + 0.05, 0.0, w + 0.18, 'SKY_Brass')
    fbox(kit['small'], face, plane, u - 0.03, u + 0.03, v - h - 0.04, v - 0.04, 0.12, 0.12 + w, mat)
    fbox(kit['none'], face, plane, u - 0.04, u + 0.04, v - h - 0.06, v - h - 0.02, 0.1, 0.14 + w, 'SKY_Brass')


def rr_pts(W, D, R, seg=4, step=1.5, cx=0.0, cy=0.0):
    """CCW rounded-rectangle outline with straight runs resampled to <= step."""
    base = ccw(rrect(W, D, R, seg=seg, cx=cx, cy=cy))
    out = []
    n = len(base)
    for i in range(n):
        p, q = Vector(base[i]), Vector(base[(i + 1) % n])
        out.append((p.x, p.y))
        L = (q - p).length
        k = int(L / step)
        for j in range(1, k + 1):
            r = p.lerp(q, j / (k + 1))
            out.append((r.x, r.y))
    return out


def ring_solid(mb, outer, inner, z0, z1, mat, top=None, inner_mat=None):
    """Closed ring wall between two outlines with equal point counts (no caps needed)."""
    n = len(outer)
    A = [mb.v((p[0], p[1], z0)) for p in outer]
    B = [mb.v((p[0], p[1], z1)) for p in outer]
    C = [mb.v((p[0], p[1], z1)) for p in inner]
    Dd = [mb.v((p[0], p[1], z0)) for p in inner]
    fs = []
    for i in range(n):
        j = (i + 1) % n
        fs.append(mb.f([A[i], A[j], B[j], B[i]], mat))
        fs.append(mb.f([B[i], B[j], C[j], C[i]], top or mat))
        fs.append(mb.f([C[i], C[j], Dd[j], Dd[i]], inner_mat or mat))
        fs.append(mb.f([Dd[i], Dd[j], A[j], A[i]], mat))
    mb._recalc(fs)
    return fs


def poly_sweep(mb, path, prof, mat, closed=False):
    """Sweep a (side, up) profile along a horizontal polyline; profile stays upright (no twist)."""
    P = [Vector(p) for p in path]
    n = len(P)
    rings = []
    for i in range(n):
        if closed:
            t = (P[(i + 1) % n] - P[i - 1])
        elif i == 0:
            t = P[1] - P[0]
        elif i == n - 1:
            t = P[-1] - P[-2]
        else:
            t = (P[i + 1] - P[i]).normalized() + (P[i] - P[i - 1]).normalized()
        t.z = 0.0
        t.normalize()
        side = Vector((t.y, -t.x, 0.0))
        k = 1.0
        if 0 < i < n - 1 or closed:
            a_ = (P[(i + 1) % n] - P[i]).normalized()
            b_ = (P[i] - P[i - 1]).normalized()
            c = max(0.5, math.cos(a_.angle(b_, 0.0) / 2))
            k = 1.0 / c
        rings.append([P[i] + side * (s * k) + Vector((0, 0, h)) for (s, h) in prof])
    if closed:
        V = [[mb.v(p) for p in r] for r in rings]
        m = len(prof)
        fs = []
        for i in range(n):
            j = (i + 1) % n
            for k_ in range(m):
                k2 = (k_ + 1) % m
                fs.append(mb.f([V[i][k_], V[i][k2], V[j][k2], V[j][k_]], mat))
        mb._recalc(fs)
        return fs
    return mb.loft(rings, mat)


def tiers_poly(a, outline, z_top, spec, mat, name="cornice", bevel=(0.025, 1), embed=0.05):
    """Stacked bands around any CCW wall outline (L-shaped wings): spec = [(height, projection), ...]."""
    mb = MB()
    zt = z_top
    for i, (hh, p) in enumerate(spec):
        ring_solid(mb, offset_line(outline, -p, closed=True), offset_line(outline, embed, closed=True),
                   zt - hh, zt + (0.01 if i else 0.0), mat)
        zt -= hh
    a.part(mb, bevel=bevel[0], seg=bevel[1], name=name)


def fountain(kit, x, y, z, r=1.15, seg=16):
    """Octagonal-ish basin with teal water, a pearl column with a bowl and a little jet."""
    kit['none'].lathe([(0.0, z), (r, z), (r, z + 0.42), (r + 0.06, z + 0.46), (r + 0.06, z + 0.52), (r - 0.16, z + 0.52),
                      (r - 0.16, z + 0.36), (0.0, z + 0.36)], seg, 'SKY_Pearl', cx=x, cy=y)
    kit['none'].lathe([(0.0, z + 0.36), (r - 0.15, z + 0.36), (r - 0.15, z + 0.43), (0.0, z + 0.43)], seg,
                      'SKY_TealLight', cx=x, cy=y)
    kit['none'].lathe([(0.0, z + 0.43), (0.15, z + 0.43), (0.11, z + 0.9), (0.42, z + 1.04), (0.45, z + 1.12),
                       (0.36, z + 1.12), (0.1, z + 1.06), (0.07, z + 1.3), (0.0, z + 1.38)], 10, 'SKY_Pearl',
                      cx=x, cy=y)
    kit['none'].lathe([(0.0, z + 1.05), (0.37, z + 1.05), (0.0, z + 1.1)], 10, 'SKY_TealLight', cx=x, cy=y)
    kit['none'].lathe([(0.0, z + 1.3), (0.05, z + 1.34), (0.035, z + 1.6), (0.0, z + 1.68)], 6, 'SKY_TealLight',
                      cx=x, cy=y)


def roller_shutter(kit, face, plane, u, z0, z1, w, d=-0.3, mat='SKY_Teal', pitch=0.13):
    """Ribbed roller curtain hanging from z1 down to z0 inside an opening (outward distance d)."""
    n = max(2, int(round((z1 - z0) / pitch)))
    s = (z1 - z0) / n
    db, df, dr = d - 0.035, d, d + 0.028
    pts = [(db, z0), (df, z0)]
    for k in range(n):
        v = z0 + k * s
        pts += [(dr, v + 0.02), (dr, v + s - 0.02), (df, v + s)]
    pts.append((db, z1))
    fprism_side(kit['none'], face, plane, pts, u - w / 2 - 0.02, u + w / 2 + 0.02, mat)
    fbox(kit['none'], face, plane, u - w / 2, u + w / 2, z0 - 0.06, z0 + 0.03, db - 0.01, dr + 0.02, 'SKY_Rubber')


def louvre_vent(kit, face, plane, u, z, w, h, mat='SKY_Metal', d0=-0.02):
    """Wall louvre panel (frame + raked slats) proud of the wall."""
    louvre_leaf(kit, face, plane, u - w / 2, u + w / 2, z, z + h, mat, d0=d0, t=0.08, pitch=0.12)


def crate(kit, x, y, z, s=0.7, h=None, rot=0.0, mat='SKY_Wood'):
    """Wooden crate with darker battens."""
    h = h or s
    L = Local(kit, M_tr(x, y, z) @ M_rot(rot))
    L('small').box(-s / 2, s / 2, -s / 2, s / 2, 0.0, h, mat)
    for zz in (0.06, h - 0.13):
        L('none').box(-s / 2 - 0.015, s / 2 + 0.015, -s / 2 - 0.015, s / 2 + 0.015, zz, zz + 0.07, 'SKY_PalmTrunk')
    L.done()


def pallet(kit, x, y, z, rot=0.0):
    L = Local(kit, M_tr(x, y, z) @ M_rot(rot))
    for yy in (-0.42, 0.0, 0.42):
        L('none').box(-0.6, 0.6, yy - 0.05, yy + 0.05, 0.0, 0.1, 'SKY_Wood')
    L('none').box(-0.6, 0.6, -0.5, 0.5, 0.1, 0.15, 'SKY_Wood')
    L.done()


def bollard(kit, x, y, z=0.0, h=0.95, r=0.12, mats=('SKY_Pearl', 'SKY_Coral')):
    a_, b_ = mats
    kit['none'].lathe([(0.0, z), (r, z), (r, z + h * 0.3), (r, z + h * 0.48), (r, z + h * 0.66), (r, z + h * 0.84),
                       (r * 0.55, z + h * 0.97), (0.0, z + h)], 8, a_, mats=[a_, a_, b_, a_, b_, a_, a_], cx=x, cy=y)


def hazard_stripes(kit, face, plane, u0, u1, v0, v1, d0, d1, n=6, mats=('SKY_Coral', 'SKY_Ink')):
    """Alternating coral/ink bands (diagonal look comes from the AO; no text)."""
    for k in range(n):
        va = v0 + (v1 - v0) * k / n
        vb = v0 + (v1 - v0) * (k + 1) / n
        fbox(kit['none'], face, plane, u0, u1, va, vb, d0, d1, mats[k % 2])


# =========================================================================== buildings

@asset("bldg_house_a", "Buildings", "buildings", ao=BLD_AO, render=BLD_RENDER)
def bldg_house_a(a):
    """2-storey courtyard house: sandstone walls with pearl quoins, string course and corbelled cornice,
    arched door with fanlight and lanterns, mashrabiya oriel, shuttered pointed windows, loggias around a
    light well with a palm, roof terrace with stepped merlons, teal-domed stair kiosk, pergola, tank, AC."""
    X0, X1, Y0, Y1 = -5.4, 5.4, -5.4, 5.4
    zr, zp, t = 6.9, 7.62, 0.3          # roof terrace, parapet top, parapet thickness
    wall, trim, teal = 'SKY_Sandstone', 'SKY_Pearl', 'SKY_Teal'
    cx0, cx1, cy0, cy1 = -2.0, 2.0, -1.0, 3.0      # light well
    zc, f1 = 0.3, 3.55
    win = Kit(a, tag="win_")

    def gwin(face, u, w=1.05, hero=False):
        if hero:
            return Op(face, u, 1.15, w, 1.95, 'round', depth=0.42, seg=8, frame=trim, frame_t=0.12, head='key',
                      inner=teal, iframe='arch', bars='fan', curtain='SKY_Fabric')
        return Op(face, u, 1.15, w, 1.95, 'round', depth=0.42, seg=8, head='keylite', head_mat=trim, inner=teal,
                  bars='fan', sill='simple')

    def uwin(face, u, shutter=None, w=1.0):
        return Op(face, u, f1 + 0.5, w, 1.75, 'pointed', depth=0.42, seg=8, head='hood' if shutter else None,
                  inner=teal, bars='cross', shutter=shutter, sill=True if shutter else 'simple')

    ops = [Op('N', 0.0, 0.5, 1.5, 2.7, 'round', depth=0.45, back='SKY_Wood', seg=12, sill=False, frame=trim,
              frame_t=0.17, head='key', door=True, steps=2, lamp=True),
           gwin('N', -3.5, hero=True), gwin('N', 3.5, hero=True), uwin('N', -3.5, teal), uwin('N', 3.5, teal),
           gwin('E', -3.0), gwin('E', 3.0), uwin('E', -3.0), uwin('E', 3.0),
           gwin('W', 0.0, w=1.2), uwin('W', -3.0), uwin('W', 3.0),
           gwin('S', -3.0), gwin('S', 3.0),
           Op('S', 0.0, f1 + 0.45, 1.3, 2.0, 'round', depth=0.42, seg=8, inner=teal, bars='fan', frame=trim,
              frame_t=0.11, head='keylite', sill='simple')]
    for face, pl, c in (('S', cy0, 0.0), ('N', cy1, 0.0), ('W', cx0, 1.0), ('E', cx1, 1.0)):
        ops.append(Op(face, c, zc, 1.7, 2.6, 'round', depth=0.8, back=wall, seg=10, sill=False, backing=False,
                      plane=pl, head='keylite', head_mat=trim))
        if face in ('S', 'N'):
            ops.append(Op(face, c, f1 + 0.5, 0.9, 1.5, 'round', depth=0.38, seg=8, sill=False, plane=pl))
    court = box_cutter(cx0, cx1, cy0, cy1, zc, zp + 1.0, wall, {'bottom': 'SKY_Kerb'})
    mass(a, X0, X1, Y0, Y1, 0.0, zp, wall, ops, name="mass", kit=win, cutters=[court], well=(t, zr))
    win.flush()

    # ---- facade trims
    fac = Kit(a, tag="facade_")
    tiers(a, X0, X1, Y0, Y1, 0.5, [(0.08, 0.065), (0.42, 0.12)], 'SKY_SandstoneDeep', name="plinth")
    tiers(a, X0, X1, Y0, Y1, f1 + 0.07, [(0.17, 0.085), (0.08, 0.045)], trim, name="course")
    tiers(a, X0, X1, Y0, Y1, zr + 0.06, [(0.17, 0.17), (0.2, 0.09)], trim, name="cornice")
    fbox(fac['none'], 'N', Y0, X0 + 0.3, X1 - 0.3, zr - 0.43, zr - 0.37, -0.01, 0.035, 'SKY_TealGlow')
    quoins(fac['none'], X0, X1, Y0, Y1, 0.5, f1 - 0.18, 'NE NW', trim, hb=0.48)
    quoins(fac['none'], X0, X1, Y0, Y1, f1 + 0.08, zr - 0.35, 'NE NW', trim, hb=0.48)
    for u_ in (-4.85, 4.85):
        drainpipe(fac, 'S', Y1, u_, zr - 0.62)
    oriel(fac, 'N', Y0, 0.0, f1 + 0.42, 2.1, 1.85, d=0.55, spacing=0.26)
    fac.flush()

    # ---- roof: coping, merlons, corner piers, light-well parapet
    roof = Kit(a, tag="roof_")
    mb = MB()
    coping(mb, X0, X1, Y0, Y1, t, zp, 0.11, 0.07, trim)
    part_r(a, mb, 0.03, 1, "coping")
    merlons2(roof['none'], 'N', Y0, X0 + 0.75, X1 - 0.75, zp + 0.1, h=0.52, w=0.52, gap=0.42, t=0.24, mat=trim,
             inset=0.03)
    for px in (X0 + 0.25, X1 - 0.25):
        for py in (Y0 + 0.25, Y1 - 0.25):
            roof['mid'].box(px - 0.3, px + 0.3, py - 0.3, py + 0.3, zp + 0.08, zp + 0.66, trim)
            roof['mid'].box(px - 0.34, px + 0.34, py - 0.34, py + 0.34, zp + 0.66, zp + 0.78, trim)
    g, tw = 0.07, 0.24
    mb = MB()
    mb.box(cx0 - g - tw, cx1 + g + tw, cy0 - g - tw, cy0 - g, zr - 0.02, zr + 0.46, trim)
    mb.box(cx0 - g - tw, cx1 + g + tw, cy1 + g, cy1 + g + tw, zr - 0.02, zr + 0.46, trim)
    mb.box(cx0 - g - tw, cx0 - g, cy0 - g, cy1 + g, zr - 0.02, zr + 0.46, trim)
    mb.box(cx1 + g, cx1 + g + tw, cy0 - g, cy1 + g, zr - 0.02, zr + 0.46, trim)
    coping(mb, cx0 - g - tw, cx1 + g + tw, cy0 - g - tw, cy1 + g + tw, tw, zr + 0.46, 0.08, 0.04, trim)
    part_r(a, mb, 0.025, 1, "well_parapet")

    # stair kiosk with a ribbed teal dome
    kx0, kx1, ky0, ky1 = 2.55, 4.85, -4.85, -2.55
    kz1 = zr + 2.3
    kops = [Op('S', 3.7, zr, 0.95, 2.0, 'flat', depth=0.3, back='SKY_Wood', sill=False, door=True, frame=trim,
               frame_t=0.1, head='lintel')]
    mass(a, kx0, kx1, ky0, ky1, zr - 0.02, kz1, trim, kops, name="kiosk", kit=roof, pre=(0.05, 2), post=(0.03, 1),
         refine=None)
    tiers(a, kx0, kx1, ky0, ky1, kz1 + 0.04, [(0.14, 0.11)], wall, name="kiosk_cornice")
    kc = ((kx0 + kx1) / 2, (ky0 + ky1) / 2)
    roof['none'].lathe([(0.0, kz1), (0.98, kz1), (0.98, kz1 + 0.22), (0.0, kz1 + 0.22)], 16, trim, cx=kc[0], cy=kc[1])
    dome2(roof, kc[0], kc[1], kz1 + 0.22, 0.9, mat=teal, rib=trim, seg=16, rings=6, ribs=6)

    # terrace furniture
    pergola2(roof, -4.45, 4.45, 3.75, 4.85, zr, h=2.3, beam_dir='x', slats=13, sail='SKY_Fabric', mid_posts=1)
    water_tank(roof, -4.2, -0.4, zr)
    ac_unit(roof, 0.5, -4.55, zr, rot=0.0)
    planter2(roof, -3.3, -4.78, zr, 2.6, 0.5, seed=3)
    vine(roof, [(-4.45, 4.85, zr + 2.3), (-4.45, 4.55, zr + 1.85), (-3.85, 4.9, zr + 2.5)], r=0.26, seed=5)
    roof.flush()

    # ---- light well: paving border and a date palm rising above the roof
    ck = Kit(a, tag="court_")
    b = 0.28
    ck['none'].box(cx0 - 0.02, cx1 + 0.02, cy0 - 0.02, cy0 + b, zc - 0.01, zc + 0.025, 'SKY_SandstoneDeep')
    ck['none'].box(cx0 - 0.02, cx1 + 0.02, cy1 - b, cy1 + 0.02, zc - 0.01, zc + 0.025, 'SKY_SandstoneDeep')
    ck['none'].box(cx0 - 0.02, cx0 + b, cy0 + b, cy1 - b, zc - 0.01, zc + 0.025, 'SKY_SandstoneDeep')
    ck['none'].box(cx1 - b, cx1 + 0.02, cy0 + b, cy1 - b, zc - 0.01, zc + 0.025, 'SKY_SandstoneDeep')
    tx, ty = -0.2, 1.2
    ck['none'].lathe([(0.0, zc), (0.55, zc), (0.55, zc + 0.36), (0.6, zc + 0.4), (0.6, zc + 0.46), (0.48, zc + 0.46),
                     (0.48, zc + 0.4), (0.0, zc + 0.4)], 12, 'SKY_SandstoneDeep',
                    mats=['SKY_SandstoneDeep'] * 6 + ['SKY_PalmTrunk'], cx=tx, cy=ty)
    palm2(ck, tx, ty, zc + 0.38, height=8.4, lean=(0.35, -0.25), fronds=8, frond_len=2.5, seed=21)
    ck.flush()


@asset("bldg_house_b", "Buildings", "buildings", ao=BLD_AO, render=BLD_RENDER)
def bldg_house_b(a):
    """3-storey town house: sandstone ground floor with an arched door and lattice-screened window, pearl
    upper floors with balconies (teal glass, brass rails, pots), louvred teal shutters, sandstone quoins,
    corbelled cornice, stepped crest with a teal-glow ring, slotted wind tower, sail, tank and planters."""
    X0, X1, Y0, Y1 = -4.72, 4.72, -4.85, 4.9
    g0, f2, zr, zp, t = 3.65, 7.0, 10.35, 11.1, 0.28
    pearl, sand, teal = 'SKY_Pearl', 'SKY_Sandstone', 'SKY_Teal'
    win = Kit(a, tag="win_")

    def side(face, u, z, w=1.05, h=1.75):
        return Op(face, u, z, w, h, 'round', depth=0.4, seg=8, bars='cross', bar_mat=teal, sill='simple',
                  head='keylite', head_mat=sand)

    def shut(u, z):
        return Op('N', u, z, 0.95, 1.65, 'round', depth=0.4, seg=8, inner=teal, bars='cross', head='key',
                  head_mat=sand, shutter=teal)

    gops = [Op('N', -2.3, 0.45, 1.3, 2.55, 'round', depth=0.42, back=teal, seg=10, sill=False, frame=pearl,
               frame_t=0.15, head='key', door=True, steps=2, lamp=True),
            Op('N', 2.3, 1.05, 1.25, 1.95, 'round', depth=0.42, seg=8, frame=pearl, frame_t=0.12, head='key',
               inner=teal, iframe='arch', bars='fan', screen=teal, curtain='SKY_Fabric'),
            side('E', 1.0, 1.1), side('W', 1.0, 1.1), side('S', 0.0, 1.1, w=1.2)]
    mass(a, X0, X1, Y0, Y1, 0.0, g0, sand, gops, name="ground", kit=win)
    uops = []
    for zf in (g0, f2):
        uops += [Op('N', 0.0, zf + 0.12, 1.5, 2.45, 'round', depth=0.42, seg=10, sill=False, inner=teal,
                    iframe='arch', bars='fan', curtain='SKY_Fabric'),
                 shut(-3.3, zf + 0.55), shut(3.3, zf + 0.55),
                 side('E', 0.0, zf + 0.55, w=1.15), side('W', 0.0, zf + 0.55, w=1.15),
                 side('S', -2.0, zf + 0.55), side('S', 2.0, zf + 0.55)]
    mass(a, X0, X1, Y0, Y1, g0, zp, pearl, uops, name="upper", kit=win, well=(t, zr))
    for zf in (g0, f2):
        balcony2(win, 'N', Y0, 0.0, zf + 0.132, 2.9, dp=1.0, style='glass', corbels=2, pots=1, seed=int(zf))
    win.flush()

    # ---- trims
    fac = Kit(a, tag="facade_")
    tiers(a, X0, X1, Y0, Y1, 0.45, [(0.07, 0.06), (0.38, 0.11)], 'SKY_SandstoneDeep', name="plinth")
    tiers(a, X0, X1, Y0, Y1, g0 + 0.1, [(0.16, 0.09), (0.08, 0.05)], pearl, name="course")
    tiers(a, X0, X1, Y0, Y1, f2 + 0.05, [(0.13, 0.06)], sand, name="course2")
    tiers(a, X0, X1, Y0, Y1, zr + 0.06, [(0.17, 0.16), (0.2, 0.085)], sand, name="cornice")
    ring(fac['none'], X0, X1, Y0, Y1, zr - 0.42, zr - 0.36, 0.03, 'SKY_Brass')
    fbox(fac['none'], 'N', Y0, X0 + 0.3, X1 - 0.3, zr - 0.5, zr - 0.45, -0.01, 0.03, 'SKY_TealGlow')
    quoins(fac['none'], X0, X1, Y0, Y1, g0 + 0.12, zr - 0.52, 'NE NW', sand, hb=0.46)
    for u_ in (-4.25, 4.25):
        drainpipe(fac, 'S', Y1, u_, zr - 0.62)
    fac.flush()

    # ---- roof
    roof = Kit(a, tag="roof_")
    mb = MB()
    coping(mb, X0, X1, Y0, Y1, t, zp, 0.1, 0.06, sand)
    part_r(a, mb, 0.03, 1, "coping")
    cz = zp + 0.1
    fbox(roof['mid'], 'N', Y0, -1.7, 1.7, cz - 0.02, cz + 0.55, -t + 0.02, 0.0, pearl)
    fbox(roof['mid'], 'N', Y0, -0.95, 0.95, cz + 0.55, cz + 1.05, -t + 0.02, 0.0, pearl)
    fbox(roof['mid'], 'N', Y0, -1.78, 1.78, cz + 0.55, cz + 0.63, -t - 0.02, 0.05, sand)
    fbox(roof['mid'], 'N', Y0, -1.03, 1.03, cz + 1.05, cz + 1.13, -t - 0.02, 0.05, sand)
    fdisc(roof['none'], 'N', Y0, 0.0, cz + 0.8, 0.19, -0.01, 0.035, 'SKY_TealGlow', seg=14, r_in=0.12)
    for px in (X0 + 0.24, X1 - 0.24):
        for py in (Y0 + 0.24, Y1 - 0.24):
            roof['mid'].box(px - 0.27, px + 0.27, py - 0.27, py + 0.27, cz - 0.02, cz + 0.42, pearl)
            roof['mid'].box(px - 0.31, px + 0.31, py - 0.31, py + 0.31, cz + 0.42, cz + 0.52, sand)
    wind_tower2(a, roof, -3.0, 3.1, zr - 0.02, zr + 3.9, s=1.8, mat=pearl, trim=sand)
    masts_sail(roof, [(1.0, -4.2, zr, zr + 2.5), (4.15, -4.15, zr, zr + 2.2), (4.1, -1.3, zr, zr + 2.6)])
    water_tank(roof, 3.35, 3.35, zr)
    ac_unit(roof, 0.4, 3.9, zr, rot=180.0)
    planter2(roof, -4.08, -2.2, zr, 0.5, 2.6, seed=7)
    roof.flush()
    # street planter under the balconies
    st = Kit(a, tag="street_")
    planter2(st, 0.0, Y0 - 0.32, 0.0, 2.2, 0.5, h=0.55, mat='SKY_SandstoneDeep', seed=9)
    st.flush()


@asset("bldg_shoprow", "Buildings", "buildings", ao=BLD_AO, render=BLD_RENDER)
def bldg_shoprow(a):
    """2-storey shop row: pointed-arch arcade (imposts, keystones, hanging lanterns) over glazed shopfronts
    with stall risers, signboards and lit interiors; sandstone upper floor with flower boxes under scalloped
    striped awnings; cornice, parapet piers with brass caps; roof sail, kiosk, tank and planters."""
    X0, X1, Y0, Y1 = -5.92, 5.92, -4.5, 4.4
    Ya = Y0 + 2.1                    # shopfront line behind the arcade
    z1, zr, zp, t = 4.1, 7.7, 8.42, 0.26
    sand, pearl, teal = 'SKY_Sandstone', 'SKY_Pearl', 'SKY_Teal'
    xs = (-4.44, -1.48, 1.48, 4.44)
    win = Kit(a, tag="win_")

    def std(face, u, z, w=1.0, h=1.75):
        return Op(face, u, z, w, h, 'round', depth=0.4, seg=8, bars='cross', bar_mat=teal, sill='simple',
                  head='keylite', head_mat=pearl)

    # ground block behind the arcade: four deep shop rooms + side/back openings
    gops = [Op('N', x, 0.12, 2.4, 3.0, 'flat', depth=2.4, back=sand, reveal=pearl, sill=False, backing=False)
            for x in xs]
    gops += [std('E', 1.2, 1.0), std('W', 1.2, 1.0),
             Op('S', -3.0, 0.12, 1.2, 2.45, 'round', depth=0.38, back='SKY_Wood', seg=8, sill=False, door=True,
                frame=pearl, frame_t=0.12),
             std('S', 0.5, 1.0), std('S', 3.2, 1.0)]
    mass(a, X0, X1, Ya, Y1, 0.0, z1, sand, gops, name="ground", kit=win)
    for i, x in enumerate(xs):
        shopfront(win, 'N', Ya, x, 0.12, 2.4, 3.0, door=(i in (1, 3)),
                  sign=(teal, 'SKY_Coral', 'SKY_TealLight', 'SKY_Coral')[i], seed=i)
    # arcade: front wall with pointed through-arches + side walls with round arches
    aops = [Op('N', x, 0.0, 2.2, 3.3, 'pointed', through=True, sill=False, back=pearl, seg=8, frame=pearl,
               frame_t=0.13, head='key', head_mat=sand) for x in xs]
    mass(a, X0, X1, Y0, Y0 + 0.55, 0.0, z1, pearl, aops, name="arcade", kit=win, pre=(0.05, 2), post=(0.035, 1))
    for f, xa, xb in (('E', X0, X0 + 0.55), ('W', X1 - 0.55, X1)):
        op = Op(f, (Y0 + 0.55 + Ya) / 2, 0.0, 1.0, 2.85, 'round', through=True, sill=False, back=pearl, seg=8)
        mass(a, xa, xb, Y0 + 0.55, Ya, 0.0, z1, pearl, [op], name="arcade_end", kit=win, pre=(0.05, 2),
             post=(0.035, 1), refine=None)
    # imposts and pier bases on the arcade front
    piers = [X0 + 0.27] + [(xs[i] + xs[i + 1]) / 2 for i in range(3)] + [X1 - 0.27]
    sp = spring_of(2.2, 3.3, 'pointed', 0.0)
    for px in piers:
        hwp = 0.3 if abs(px) < 5 else 0.24
        fbox(win['mid'], 'N', Y0, px - hwp - 0.04, px + hwp + 0.04, 0.0, 0.32, -0.02, 0.06, sand)
        fbox(win['mid'], 'N', Y0, px - hwp - 0.03, px + hwp + 0.03, sp - 0.16, sp + 0.02, -0.02, 0.06, sand)
    mb = MB()
    mb.box(X0 + 0.55, X1 - 0.55, Y0 + 0.55, Ya, 0.0, 0.1, 'SKY_Kerb')
    part_r(a, mb, 0.0, 1, "arcade_floor")
    fbox(win['none'], 'N', Ya, X0 + 0.6, X1 - 0.6, z1 - 0.3, z1 - 0.24, -0.01, 0.05, 'SKY_TealGlow')
    for x in xs:
        pendant(win, x, (Y0 + 0.55 + Ya) / 2, z1, drop=0.75)
    blade_sign(win, 'N', Ya, (xs[0] + xs[1]) / 2, 3.05, mat='SKY_Coral')
    blade_sign(win, 'N', Ya, (xs[2] + xs[3]) / 2, 3.05, mat=teal)
    # upper floor
    uops = [Op('N', x, z1 + 0.75, 1.15, 1.85, 'round', depth=0.42, seg=8, inner=teal, iframe='arch', bars='fan',
               sill=False, curtain='SKY_Fabric') for x in xs]
    uops += [std('E', 0.6, z1 + 0.75, w=1.15), std('W', 0.6, z1 + 0.75, w=1.15), std('S', -2.4, z1 + 0.75),
             std('S', 2.4, z1 + 0.75)]
    mass(a, X0, X1, Y0, Y1, z1, zp, sand, uops, name="upper", kit=win, well=(t, zr))
    for i, x in enumerate(xs):
        mats = ('SKY_Coral', pearl) if i % 2 == 0 else (teal, pearl)
        awning2(win, 'N', Y0, x, z1 + 2.95, 1.6, depth=0.82, drop=0.38, mats=mats, stripes=4, valance=0.22)
        c = fpt('N', Y0, x, 0.0, 0.17)
        planter2(win, c[0], c[1], z1 + 0.6, 1.3, 0.3, h=0.26, mat=teal, rim=pearl, seed=i, cls='none')
    win.flush()

    # ---- trims
    fac = Kit(a, tag="facade_")
    tiers(a, X0, X1, Ya, Y1, 0.35, [(0.07, 0.05), (0.28, 0.1)], 'SKY_SandstoneDeep', name="plinth", faces='SEW')
    tiers(a, X0, X1, Y0, Y1, z1 + 0.22, [(0.16, 0.085), (0.08, 0.045)], pearl, name="course")
    tiers(a, X0, X1, Y0, Y1, zr + 0.06, [(0.17, 0.16), (0.2, 0.085)], pearl, name="cornice")
    fbox(fac['none'], 'N', Y0, X0 + 0.3, X1 - 0.3, zr - 0.5, zr - 0.44, -0.01, 0.03, 'SKY_TealGlow')
    for u_ in (-5.4, 5.4):
        drainpipe(fac, 'S', Y1, u_, zr - 0.62, z_bot=0.35)
    fac.flush()

    # ---- roof
    roof = Kit(a, tag="roof_")
    mb = MB()
    coping(mb, X0, X1, Y0, Y1, t, zp, 0.1, 0.06, pearl)
    part_r(a, mb, 0.03, 1, "coping")
    for px in piers:
        fbox(roof['mid'], 'N', Y0, px - 0.28, px + 0.28, zp + 0.08, zp + 0.68, -0.42, 0.07, pearl)
        fbox(roof['mid'], 'N', Y0, px - 0.33, px + 0.33, zp + 0.68, zp + 0.78, -0.47, 0.11, sand)
        c = fpt('N', Y0, px, 0.0, -0.18)
        roof['none'].lathe([(0.0, zp + 0.78), (0.16, zp + 0.78), (0.16, zp + 0.84), (0.07, zp + 0.9),
                            (0.13, zp + 1.0), (0.11, zp + 1.1), (0.04, zp + 1.17), (0.0, zp + 1.3)], 8, 'SKY_Brass',
                           cx=c[0], cy=c[1])
    masts_sail(roof, [(-5.1, -3.6, zr, zr + 2.9), (-1.3, -3.4, zr, zr + 1.9), (-1.1, 2.4, zr, zr + 2.9),
                      (-4.9, 3.6, zr, zr + 1.9)], sag=0.1)
    kx, ky = 4.3, 2.9
    kops = [Op('E', ky, zr, 0.85, 1.95, 'flat', depth=0.3, back='SKY_Wood', sill=False, door=True, frame=pearl,
               frame_t=0.09, head='lintel')]
    mass(a, kx - 0.85, kx + 0.85, ky - 0.85, ky + 0.85, zr - 0.02, zr + 2.3, pearl, kops, name="kiosk", kit=roof,
         pre=(0.05, 2), post=(0.03, 1), refine=None)
    tiers(a, kx - 0.85, kx + 0.85, ky - 0.85, ky + 0.85, zr + 2.34, [(0.14, 0.1)], sand, name="kiosk_cornice")
    water_tank(roof, 1.6, 3.4, zr)
    ac_unit(roof, 2.0, -3.6, zr, rot=0.0)
    ac_unit(roof, 3.4, -3.6, zr, rot=0.0)
    planter2(roof, 4.2, -0.6, zr, 1.9, 0.5, seed=12)
    roof.flush()


@asset("bldg_tower", "Buildings", "buildings", ao=BLD_AO, render=dict(BLD_RENDER, el=20.0))
def bldg_tower(a):
    """5-storey streamline residential tower: rounded teal glass core with pearl fins, cantilevered pearl
    floor slabs with brass edges, wrap-around corner balconies (glass balustrades, brass rails), colonnaded
    glass lobby with an arched portal and ribbed glowing canopy, crown parapet with a glow ring, rooftop
    pavilion with a wind-tower vent, pergola and sail, tanks, solar and planters."""
    pearl, teal, brass = 'SKY_Pearl', 'SKY_TealLight', 'SKY_Brass'
    Wc, Dc, Rc = 10.0, 9.4, 2.3          # glass core
    Ws, Ds, Rs = 11.1, 10.5, 1.3         # slab outline
    core = rr_pts(Wc, Dc, Rc, seg=6, step=1.6)
    slab = rr_pts(Ws, Ds, Rs, seg=4, step=1.6)
    z_lobby, fh, nf = 4.1, 3.3, 4
    levels = [z_lobby + i * fh for i in range(nf + 1)]      # slab tops; last one is the roof
    zroof = levels[-1]
    kit = Kit(a, tag="det_")

    # ---- base plinth + floor slabs (bevel first, then sliced for AO)
    mb = MB()
    mb.prism(rr_pts(Ws + 0.1, Ds + 0.1, Rs + 0.05, seg=4, step=1.6), 0.0, 0.3, 'SKY_SandstoneDeep')
    solid(a, mb, (), pre=(0.04, 2), post=None, name="base")
    for i, zt in enumerate(levels):
        mb = MB()
        rings = [[(p[0], p[1], z_) for p in slab] for z_ in (zt - 0.36, zt - 0.25, zt - 0.18, zt)]
        mb.loft(rings, pearl, mats=[pearl, brass, 'SKY_Kerb' if i == nf else pearl])
        solid(a, mb, (), pre=(0.06, 1), post=None, name="slab")
    # ---- glass core per storey, with fins and a rail line
    for i in range(nf):
        z0, z1 = levels[i], levels[i + 1] - 0.36
        mb = MB()
        mb.prism(core, z0 - 0.02, z1 + 0.02, teal)
        a.part(mb, name="glass")
    # lobby glass (translucent in Unity) with a dark interior core behind it
    lob = rr_pts(Wc - 0.2, Dc - 0.2, Rc - 0.1, seg=6, step=1.6)
    mb = MB()
    mb.prism(lob, 0.28, z_lobby - 0.34, 'SKY_Glass')
    a.part(mb, name="lobby_glass")
    mb = MB()
    mb.prism(rr_pts(Wc - 1.4, Dc - 1.4, Rc - 0.6, seg=4, step=3.0), 0.28, z_lobby - 0.34, 'SKY_Ink')
    a.part(mb, name="lobby_core")
    # fins on straight runs and around the corners
    for i in range(nf):
        z0, z1 = levels[i], levels[i + 1] - 0.36
        for face, pl, us in (('N', -Dc / 2, (-1.75, -0.6, 0.6, 1.75)), ('S', Dc / 2, (-1.75, -0.6, 0.6, 1.75)),
                             ('E', -Wc / 2, (-1.45, 0.0, 1.45)), ('W', Wc / 2, (-1.45, 0.0, 1.45))):
            for uu in us:
                fbox(kit['none'], face, pl, uu - 0.05, uu + 0.05, z0, z1, -0.03, 0.12, pearl)
        for sx in (-1, 1):
            for sy in (-1, 1):
                cx_, cy_ = sx * (Wc / 2 - Rc), sy * (Dc / 2 - Rc)
                for ang in (45.0,):
                    ar = math.radians(ang)
                    dx, dy = sx * math.cos(ar), sy * math.sin(ar)
                    c = Vector((cx_ + dx * (Rc + 0.04), cy_ + dy * (Rc + 0.04), 0.0))
                    M = M_tr(c.x, c.y, z0) @ Matrix.Rotation(math.atan2(dy, dx), 4, 'Z')
                    fs = kit['none'].box(-0.07, 0.08, -0.05, 0.05, 0.0, z1 - z0, pearl)
                    kit['none'].transform(M, faces=fs)
    # ---- wrap-around corner balconies on every upper floor
    hx, hy = Ws / 2 - 0.08, Ds / 2 - 0.08
    for zt in levels[1:-1]:
        for sx in (-1, 1):
            for sy in (-1, 1):
                ccx, ccy = sx * (Ws / 2 - Rs), sy * (Ds / 2 - Rs)
                path = [(sx * (Wc / 2 - 0.02), sy * (Dc / 2 - Rc + 0.05)), (sx * hx, sy * (Dc / 2 - Rc + 0.05))]
                for k in range(5):
                    ph = math.radians(90.0 * k / 4)
                    path.append((ccx + sx * (Rs - 0.08) * math.cos(ph), ccy + sy * (Rs - 0.08) * math.sin(ph)))
                path += [(sx * (Wc / 2 - Rc + 0.05), sy * hy), (sx * (Wc / 2 - Rc + 0.05), sy * (Dc / 2 - 0.02))]
                p3 = [(x, y, zt) for (x, y) in path]
                poly_sweep(kit['none'], p3, [(-0.012, 0.06), (0.012, 0.06), (0.012, 0.92), (-0.012, 0.92)],
                           'SKY_Glass')
                poly_sweep(kit['none'], p3, [(-0.035, 0.92), (0.035, 0.92), (0.035, 1.0), (-0.035, 1.0)], brass)
                for q in (path[1], path[4], path[7]):
                    kit['none'].box(q[0] - 0.025, q[0] + 0.025, q[1] - 0.025, q[1] + 0.025, zt, zt + 0.93, brass)
                if (sx, sy) == ((-1, -1), (1, -1), (1, 1), (-1, 1))[levels.index(zt) % 4]:
                    c = (ccx + sx * 0.25, ccy + sy * 0.25)
                    pot(kit, c[0], c[1], zt, r=0.17, h=0.32, plant='flower', seed=int(zt * 3))
    # ---- lobby: corner columns, arched portal, ribbed canopy, doors, planters, lamps
    for sx in (-1, 1):
        for sy in (-1, 1):
            ar = math.radians(45.0)
            px = sx * (Ws / 2 - Rs + (Rs - 0.35) * math.cos(ar))
            py = sy * (Ds / 2 - Rs + (Rs - 0.35) * math.sin(ar))
            kit['none'].lathe([(0.0, 0.3), (0.26, 0.3), (0.26, 0.45), (0.18, 0.55), (0.16, z_lobby - 0.55),
                               (0.24, z_lobby - 0.42), (0.24, z_lobby - 0.36), (0.0, z_lobby - 0.36)], 10, pearl,
                              cx=px, cy=py)
    yN = -Dc / 2
    band = arch_band(2.3, 3.2, 0.32, 'round', 12)
    fprism(kit['mid'], 'N', yN, band, -0.05, 0.62, pearl)
    fbox(kit['small'], 'N', yN, -0.15, 0.15, 3.12, 3.62, -0.05, 0.7, brass)
    # canopy over the portal: slab, brass fascia, glow underside, three fins on top
    fbox(kit['trim'], 'N', yN, -1.9, 1.9, 3.6, 3.78, 0.0, 1.22, pearl)
    fbox(kit['none'], 'N', yN, -1.94, 1.94, 3.56, 3.62, 1.1, 1.26, brass)
    fbox(kit['none'], 'N', yN, -1.75, 1.75, 3.565, 3.6, 0.1, 1.1, 'SKY_TealGlow')
    for uu in (-1.35, 0.0, 1.35):
        fprism_side(kit['small'], 'N', yN, [(0.0, 3.77), (1.15, 3.77), (1.15, 3.86), (0.0, 4.25 - 0.36)],
                    uu - 0.05, uu + 0.05, pearl)
    # glazed double doors in the portal (frame drawn on the lobby glass)
    dl = yN + 0.12
    for uu in (-1.15, -0.03, 0.03, 1.15):
        fbox(kit['none'], 'N', dl, uu - 0.04, uu + 0.04, 0.3, 2.75, 0.0, 0.07, 'SKY_Teal')
    fbox(kit['none'], 'N', dl, -1.19, 1.19, 2.7, 2.78, 0.0, 0.07, 'SKY_Teal')
    for uu in (-0.14, 0.14):
        fbox(kit['none'], 'N', dl, uu - 0.02, uu + 0.02, 0.9, 1.5, 0.05, 0.11, brass)
    for uu in (-3.3, 3.3):
        planter2(kit, uu, -Dc / 2 - 0.35, 0.3, 1.8, 0.5, h=0.5, seed=int(uu * 10))
    for uu in (-1.31, 1.31):
        wall_lamp(kit, 'N', yN - 0.62, uu, 2.35, arm=0.2)

    # ---- crown parapet with brass cap and glow ring, roof furniture
    outer = rr_pts(Ws - 0.24, Ds - 0.24, Rs - 0.1, seg=4, step=1.6)
    inner = offset_line(outer, 0.24, closed=True)
    mb = MB()
    ring_solid(mb, outer, inner, zroof - 0.02, zroof + 0.95, pearl)
    solid(a, mb, (), pre=(0.04, 1), post=None, name="crown")
    mb = MB()
    ring_solid(mb, offset_line(outer, -0.06, closed=True), offset_line(inner, 0.05, closed=True), zroof + 0.95,
               zroof + 1.06, brass)
    a.part(mb, name="crown_cap")
    ring_solid(kit['none'], offset_line(outer, -0.02, closed=True), offset_line(outer, 0.03, closed=True),
               zroof + 0.72, zroof + 0.78, 'SKY_TealGlow')
    roof = Kit(a, tag="roof_")
    pz = zroof
    pops = [Op('S', -0.5, pz, 1.0, 2.1, 'round', depth=0.3, back='SKY_Wood', seg=8, sill=False, door=True,
               frame=pearl, frame_t=0.1),
            Op('N', -0.5, pz + 0.9, 2.2, 0.8, 'flat', depth=0.25, sill='simple', bars='mull', bar_mat='SKY_Teal')]
    mass(a, -2.2, 1.2, 0.8, 3.8, pz - 0.02, pz + 2.6, pearl, pops, name="pavilion", kit=roof, pre=(0.05, 2),
         post=(0.03, 1), refine=None)
    tiers(a, -2.2, 1.2, 0.8, 3.8, pz + 2.66, [(0.14, 0.1)], brass, name="pav_cap")
    wind_tower2(a, roof, 2.7, 3.25, pz - 0.02, pz + 3.3, s=1.35, slots=1, glow=True)
    pergola2(roof, -3.2, 2.6, -3.4, -0.6, pz, h=2.35, beam_dir='x', slats=11, sail='SKY_Fabric')
    water_tank(roof, 4.3, 0.9, pz, r=0.45)
    solar2(roof, 3.15, 4.65, -4.0, -1.4, pz, rows=2)
    planter2(roof, -4.4, 0.7, pz, 0.55, 2.6, seed=31)
    ac_unit(roof, -3.4, 4.25, pz, rot=180.0)
    roof.flush()
    kit.flush()


@asset("bldg_dome", "Buildings", "buildings", ao=BLD_AO, render=BLD_RENDER)
def bldg_dome(a):
    """Civic hall: pearl walls with sandstone pilasters and tall arched windows, columned portico with
    entablature, glowing frieze and stepped crest, arched drum with teal glazing under a ribbed teal dome with
    a glowing lantern and brass finial, domed corner kiosks."""
    X0, X1, Y0, Y1 = -4.45, 4.45, -3.2, 5.45
    zr, zp, t = 6.6, 7.25, 0.26
    pearl, sand, teal = 'SKY_Pearl', 'SKY_Sandstone', 'SKY_Teal'
    win = Kit(a, tag="win_")
    ym = (Y0 + Y1) / 2

    def tall(face, u):
        return Op(face, u, 1.5, 1.2, 3.3, 'round', depth=0.42, seg=10, inner='SKY_Ink', bars='fan',
                  sill='simple', head='keylite', head_mat=sand)

    ops = [Op('N', 0.0, 0.6, 1.8, 3.4, 'round', depth=0.45, back='SKY_Wood', seg=12, sill=False, frame=sand,
              frame_t=0.16, head='key', head_mat=pearl, door=True, lamp=True),
           Op('N', -3.3, 1.5, 0.85, 2.6, 'round', depth=0.42, seg=8, inner='SKY_Ink', bars='cross', frame=sand,
              frame_t=0.1, head='key', head_mat=pearl),
           Op('N', 3.3, 1.5, 0.85, 2.6, 'round', depth=0.42, seg=8, inner='SKY_Ink', bars='cross', frame=sand,
              frame_t=0.1, head='key', head_mat=pearl)]
    for f in ('E', 'W'):
        ops += [tall(f, ym + du) for du in (-2.7, 0.0, 2.7)]
    ops += [tall('S', u) for u in (-2.75, 0.0, 2.75)]
    mass(a, X0, X1, Y0, Y1, 0.0, zp, pearl, ops, name="hall", kit=win, well=(t, zr))
    win.flush()

    # ---- pilasters, plinth, frieze, cornice
    fac = Kit(a, tag="facade_")
    tiers(a, X0, X1, Y0, Y1, 0.6, [(0.08, 0.07), (0.52, 0.12)], sand, name="plinth")
    pil = {'E': (X0, [Y0 + 0.3, ym - 1.35, ym + 1.35, Y1 - 0.3]), 'W': (X1, [Y0 + 0.3, ym - 1.35, ym + 1.35, Y1 - 0.3]),
           'S': (Y1, [X0 + 0.3, -1.375, 1.375, X1 - 0.3]), 'N': (Y0, [X0 + 0.3, X1 - 0.3])}
    for f, (pl, us) in pil.items():
        for uu in us:
            fbox(fac['mid'], f, pl, uu - 0.24, uu + 0.24, 0.62, zr - 0.62, -0.02, 0.11, sand)
            fbox(fac['none'], f, pl, uu - 0.3, uu + 0.3, 0.6, 0.8, -0.02, 0.15, sand)
            fbox(fac['none'], f, pl, uu - 0.3, uu + 0.3, zr - 0.8, zr - 0.62, -0.02, 0.16, sand)
    tiers(a, X0, X1, Y0, Y1, zr + 0.06, [(0.16, 0.22), (0.12, 0.15), (0.4, 0.08)], sand, name="cornice")
    ring(fac['none'], X0, X1, Y0, Y1, zr - 0.5, zr - 0.44, 0.105, 'SKY_Brass')
    fbox(fac['none'], 'N', Y0, X0 + 0.6, X1 - 0.6, zr - 0.6, zr - 0.55, -0.01, 0.1, 'SKY_TealGlow')
    fac.flush()

    # ---- portico: steps, columns, entablature, crest
    por = Kit(a, tag="portico_")
    py0 = Y0 - 2.0
    for k, (ext, dy, zt) in enumerate(((3.35, 0.85, 0.2), (3.15, 0.42, 0.4), (2.95, 0.0, 0.6))):
        por['mid'].box(-ext, ext, py0 - dy, Y0 + 0.05, 0.0, zt, sand)
    cy_ = py0 + 0.45
    for x in (-2.55, -0.85, 0.85, 2.55):
        por['mid'].box(x - 0.33, x + 0.33, cy_ - 0.33, cy_ + 0.33, 0.6, 0.78, pearl)
        por['none'].lathe([(0.0, 0.78), (0.3, 0.78), (0.31, 0.86), (0.27, 0.95), (0.25, 1.05), (0.23, 4.25),
                           (0.26, 4.3), (0.26, 4.36), (0.22, 4.4), (0.3, 4.62), (0.0, 4.62)], 10, pearl, cx=x, cy=cy_)
        por['mid'].box(x - 0.36, x + 0.36, cy_ - 0.36, cy_ + 0.36, 4.62, 4.78, pearl)
    por['trim'].box(-3.05, 3.05, py0 - 0.05, Y0 + 0.02, 4.78, 5.18, pearl)
    por['mid'].box(-3.0, 3.0, py0 + 0.0, Y0 + 0.02, 5.18, 5.56, sand)
    por['none'].box(-2.9, 2.9, py0 - 0.01, py0 + 0.05, 5.3, 5.36, 'SKY_TealGlow')
    por['none'].box(-3.0, 3.0, py0 - 0.02, py0 + 0.02, 5.46, 5.5, 'SKY_Brass')
    por['trim'].box(-3.18, 3.18, py0 - 0.18, Y0 + 0.02, 5.56, 5.74, pearl)
    por['mid'].box(-2.1, 2.1, py0 + 0.05, Y0 + 0.02, 5.74, 6.3, pearl)
    por['mid'].box(-1.1, 1.1, py0 + 0.05, Y0 + 0.02, 6.3, 6.78, pearl)
    por['none'].box(-2.16, 2.16, py0 - 0.0, Y0 + 0.02, 6.3, 6.37, sand)
    por['none'].box(-1.16, 1.16, py0 - 0.0, Y0 + 0.02, 6.78, 6.85, sand)
    fdisc(por['none'], 'N', py0 + 0.05, 0.0, 6.42, 0.2, -0.01, 0.035, 'SKY_TealGlow', seg=14, r_in=0.13)
    for x in (-3.0, 3.0):
        por['none'].lathe([(0.0, 0.6), (0.2, 0.6), (0.26, 0.75), (0.3, 0.95), (0.22, 1.12), (0.25, 1.17),
                           (0.0, 1.17)], 10, 'SKY_Terracotta', cx=x, cy=py0 + 0.2)
        blob(por['none'], x, py0 + 0.2, 1.1, 0.3, 'SKY_PalmLeaf', seg=7)
        blob(por['none'], x + 0.12, py0 + 0.15, 1.38, 0.15, 'SKY_Flower', seg=5)
    por.flush()

    # ---- drum with arched teal windows, ribbed teal dome, glowing lantern
    cx, cy = 0.0, ym
    zd0, zd1, rd = zr - 0.02, zr + 1.85, 3.0
    mb = MB()
    mb.lathe([(0.0, zd0), (rd + 0.25, zd0), (rd + 0.25, zd0 + 0.45), (rd, zd0 + 0.45), (rd, zd1), (0.0, zd1)],
             30, sand, mats=[sand, sand, sand, pearl, pearl], cx=cx, cy=cy)
    cuts = []
    nwin = 10
    for k in range(nwin):
        ang = math.radians(360.0 * k / nwin + 3.0)     # jambs and apex clear of the 30-gon's vertices
        e = Vector((math.cos(ang), math.sin(ang), 0.0))
        q = Vector((-math.sin(ang), math.cos(ang), 0.0))
        mbc = MB()
        mbc.prism_frame(arch_pts(0.62, 0.95, 'round', 8, base=zd0 + 0.62), (cx, cy, 0.0), q, (0, 0, 1), e,
                        rd + 0.6, rd - 0.32, pearl, front=pearl, back=teal)
        cuts.append(_tmp_obj(mbc, "cut"))
    solid(a, mb, cuts, pre=(0.04, 2), post=(0.03, 1), name="drum", refine=None)
    dk = Kit(a, tag="dome_")
    dk['mid'].lathe([(rd - 0.1, zd1 - 0.02), (rd + 0.14, zd1 - 0.02), (rd + 0.14, zd1 + 0.14), (rd - 0.1, zd1 + 0.14)],
                    30, 'SKY_Brass', cx=cx, cy=cy, closed=True)
    rdome, onion = 2.75, 1.05
    dome2(dk, cx, cy, zd1 + 0.1, rdome, mat=teal, rib=pearl, seg=28, rings=9, ribs=10, onion=onion, top=False,
          rib_stop=0.84)
    zt = zd1 + 0.1 + rdome * onion
    dk['none'].lathe([(0.0, zt - 0.12), (0.62, zt - 0.12), (0.62, zt + 0.02), (0.5, zt + 0.08), (0.0, zt + 0.08)], 16,
                     pearl, cx=cx, cy=cy)
    dk['none'].cyl(0.3, zt + 0.06, zt + 0.52, 8, 'SKY_TealGlow', cx=cx, cy=cy)
    for k in range(6):
        ang = 2 * math.pi * k / 6
        px, py = cx + 0.44 * math.cos(ang), cy + 0.44 * math.sin(ang)
        dk['none'].box(px - 0.05, px + 0.05, py - 0.05, py + 0.05, zt + 0.06, zt + 0.54, pearl)
    dk['none'].lathe([(0.0, zt + 0.5), (0.56, zt + 0.5), (0.56, zt + 0.6), (0.0, zt + 0.6)], 16, pearl, cx=cx, cy=cy)
    dome2(dk, cx, cy, zt + 0.6, 0.42, mat=teal, rib=pearl, seg=16, rings=5, ribs=0, fin=0.8)
    # domed corner kiosks on the parapet corners
    for sx in (-1, 1):
        for sy in (-1, 1):
            px = X0 + 0.42 if sx < 0 else X1 - 0.42
            py = Y0 + 0.42 if sy < 0 else Y1 - 0.42
            dk['mid'].box(px - 0.38, px + 0.38, py - 0.38, py + 0.38, zp - 0.02, zp + 0.62, pearl)
            dk['mid'].box(px - 0.44, px + 0.44, py - 0.44, py + 0.44, zp + 0.62, zp + 0.72, sand)
            dome2(dk, px, py, zp + 0.72, 0.36, mat=teal, rib=pearl, seg=12, rings=4, ribs=0, fin=0.6)
    dk.flush()
    mb = MB()
    coping(mb, X0, X1, Y0, Y1, t, zp, 0.1, 0.07, sand)
    part_r(a, mb, 0.03, 1, "coping")


@asset("bldg_courtyard", "Buildings", "buildings", ao=BLD_AO, render=dict(BLD_RENDER, az=42.0, el=30.0))
def bldg_courtyard(a):
    """L-shaped 2-storey house around a shaded courtyard: arcaded loggias on both court faces, mashrabiya
    oriel, shuttered windows, pearl quoins and corbelled cornice; walled court with a gate portal and open
    timber gates, fountain, date palm, bougainvillea, tensioned shade sail; roof with stepped merlons."""
    X0, X1, Y0, Y1 = -5.9, 5.9, -5.3, 5.9
    xb, ya = -1.5, 1.5                   # inner faces of wing B (east) and wing A (south)
    zr, zp, t = 7.0, 7.7, 0.26
    f1, zc = 3.6, 0.12
    wall, pearl, teal, deep = 'SKY_Sandstone', 'SKY_Pearl', 'SKY_Teal', 'SKY_SandstoneDeep'
    L = ccw([(X0, Y0), (xb, Y0), (xb, ya), (X1, ya), (X1, Y1), (X0, Y1)])
    win = Kit(a, tag="win_")

    def std(face, u, z, w=1.0, h=1.75, kind='round', plane=None):
        return Op(face, u, z, w, h, kind, depth=0.4, seg=8, bars='cross', bar_mat=teal, sill='simple',
                  head='keylite', head_mat=pearl, plane=plane)

    def shut(face, u, plane=None):
        return Op(face, u, f1 + 0.5, 1.0, 1.75, 'round', depth=0.42, seg=8, inner=teal, bars='cross', head='key',
                  head_mat=pearl, shutter=teal, plane=plane)

    ops = [Op('N', -3.7, 0.45, 1.4, 2.65, 'round', depth=0.42, back='SKY_Wood', seg=10, sill=False, frame=pearl,
              frame_t=0.15, head='key', door=True, steps=2, lamp=True),
           shut('N', -3.7),
           std('E', -3.0, 1.1), std('E', 3.4, 1.1), std('E', -3.0, f1 + 0.5), std('E', 3.4, f1 + 0.5),
           std('S', -3.4, 1.1), std('S', 3.4, 1.1), std('S', -3.4, f1 + 0.5), std('S', 0.0, f1 + 0.5),
           std('S', 3.4, f1 + 0.5),
           std('W', 3.7, 1.1), std('W', 3.7, f1 + 0.5),
           std('N', 0.0, f1 + 0.5, plane=ya), std('N', 4.5, f1 + 0.5, plane=ya),
           std('W', -3.8, f1 + 0.5, plane=xb), std('W', -1.9, f1 + 0.5, plane=xb), std('W', 0.0, f1 + 0.5, plane=xb)]
    # loggias: hidden recess + arches through the front skin + openings in the back wall
    for x in (0.3, 2.2, 4.1):
        ops.append(Op('N', x, 0.3, 1.4, 2.5, 'round', depth=0.5, back=wall, seg=10, sill=False, head='keylite',
                      head_mat=pearl, backing=False, plane=ya))
    for y in (-3.8, -1.9, 0.0):
        ops.append(Op('W', y, 0.3, 1.4, 2.5, 'round', depth=0.5, back=wall, seg=10, sill=False, head='keylite',
                      head_mat=pearl, backing=False, plane=xb))
    ops += [Op('N', 2.2, 0.3, 1.1, 2.2, 'round', depth=0.25, back='SKY_Wood', seg=8, sill=False, plane=ya + 1.6),
            Op('W', -1.9, 0.3, 1.1, 2.2, 'round', depth=0.25, back='SKY_Wood', seg=8, sill=False, plane=xb - 1.6)]
    cuts = [box_cutter(xb, X1 + 1.0, Y0 - 1.0, ya, -0.5, zp + 1.0, wall),
            box_cutter(X0 + t, X1 - t, ya + t, Y1 - t, zr, zp + 1.0, wall, {'bottom': 'SKY_Kerb'}),
            box_cutter(X0 + t, xb - t, Y0 + t, ya + t + 0.4, zr, zp + 1.0, wall, {'bottom': 'SKY_Kerb'}),
            box_cutter(-1.05, 5.45, ya + 0.36, ya + 1.6, 0.3, 3.15, wall, {'bottom': 'SKY_Kerb', 'top': pearl}),
            box_cutter(xb - 1.6, xb - 0.36, -4.9, 1.05, 0.3, 3.15, wall, {'bottom': 'SKY_Kerb', 'top': pearl})]
    mass(a, X0, X1, Y0, Y1, 0.0, zp, wall, ops, name="wings", kit=win, cutters=cuts)
    oriel(win, 'N', ya, 2.2, f1 + 0.45, 1.9, 1.75, d=0.5, spacing=0.26)
    win.flush()

    # ---- trims
    fac = Kit(a, tag="facade_")
    tiers_poly(a, L, 0.45, [(0.07, 0.06), (0.38, 0.11)], deep, name="plinth")
    tiers_poly(a, L, f1 + 0.08, [(0.16, 0.08), (0.08, 0.045)], pearl, name="course")
    tiers_poly(a, L, zr + 0.06, [(0.16, 0.17), (0.2, 0.085)], pearl, name="cornice")
    fbox(fac['none'], 'N', Y0, X0 + 0.3, xb - 0.3, zr - 0.48, zr - 0.42, -0.01, 0.035, 'SKY_TealGlow')
    fbox(fac['none'], 'N', ya, xb + 0.3, X1 - 0.3, zr - 0.48, zr - 0.42, -0.01, 0.035, 'SKY_TealGlow')
    quoins(fac['none'], X0, X1, Y0, Y1, 0.45, f1 - 0.1, 'NE SE', pearl, hb=0.46)
    quoins(fac['none'], X0, X1, Y0, Y1, f1 + 0.1, zr - 0.38, 'NE SE', pearl, hb=0.46)
    for u_ in (-4.9, 4.9):
        drainpipe(fac, 'S', Y1, u_, zr - 0.62)
    fac.flush()

    # ---- roof: L coping, merlons on the street faces, corner piers, furniture
    roof = Kit(a, tag="roof_")
    mb = MB()
    ring_solid(mb, offset_line(L, -0.07, closed=True), offset_line(L, t + 0.07, closed=True), zp, zp + 0.1, pearl)
    a.part(mb, bevel=0.025, seg=1, name="coping")
    merlons2(roof['none'], 'N', Y0, X0 + 0.65, xb - 0.45, zp + 0.09, h=0.5, w=0.5, gap=0.4, t=0.22, mat=pearl,
             inset=0.02)
    merlons2(roof['none'], 'E', X0, Y0 + 0.65, Y1 - 0.65, zp + 0.09, h=0.5, w=0.52, gap=0.5, t=0.22, mat=pearl,
             inset=0.02)
    for (px, py) in ((X0 + 0.22, Y0 + 0.22), (xb - 0.22, Y0 + 0.22), (X0 + 0.22, Y1 - 0.22), (X1 - 0.22, Y1 - 0.22),
                     (X1 - 0.22, ya + 0.22)):
        roof['mid'].box(px - 0.28, px + 0.28, py - 0.28, py + 0.28, zp + 0.06, zp + 0.62, pearl)
        roof['mid'].box(px - 0.32, px + 0.32, py - 0.32, py + 0.32, zp + 0.62, zp + 0.72, wall)
    solar2(roof, 0.6, 4.6, 2.2, 5.4, zr, rows=2)
    water_tank(roof, -4.6, 4.6, zr)
    ac_unit(roof, -2.6, 4.9, zr, rot=180.0)
    roof_hatch(roof, -4.4, -2.0, zr)
    planter2(roof, -4.0, 2.7, zr, 2.4, 0.5, seed=41)
    roof.flush()

    # ---- court: paving, walls with gate portal, fountain, palm, bougainvillea, sail
    ck = Kit(a, tag="court_")
    mb = MB()
    mb.box(xb - 0.02, 5.6, -5.08, ya + 0.02, 0.0, zc, 'SKY_Kerb')
    solid(a, mb, (), pre=None, post=None, name="paving")
    ck['none'].box(xb - 0.02, 5.6, ya - 0.3, ya + 0.02, zc - 0.01, zc + 0.02, deep)
    ck['none'].box(xb - 0.02, xb + 0.3, -5.08, ya - 0.3, zc - 0.01, zc + 0.02, deep)
    gx, gw = 2.3, 1.7
    wz = 1.6
    mb = MB()
    mb.box(xb - 0.05, gx - gw / 2 - 0.25, -5.4, -5.05, 0.0, wz, wall)
    mb.box(gx + gw / 2 + 0.25, X1, -5.4, -5.05, 0.0, wz, wall)
    mb.box(5.55, X1, -5.05, ya + 0.05, 0.0, wz, wall)
    solid(a, mb, [box_cutter(5.3, 6.2, -2.8, -1.0, 0.45, 1.35, wall)], pre=(0.04, 2), post=(0.025, 1),
          name="court_walls")
    mb = MB()
    coping(mb, xb - 0.05, X1, -5.4, ya + 0.05, 0.35, wz, 0.1, 0.05, pearl, faces='NW')
    a.part(mb, bevel=0.02, seg=1, name="court_coping")
    # gate portal: piers, arch band, crest, lantern, open timber gate leaves
    gp = MB()
    for s in (-1, 1):
        px = gx + s * (gw / 2 + 0.14)
        gp.box(px - 0.16, px + 0.16, -5.48, -4.97, 0.0, 2.6, pearl)
    gp.box(gx - 1.2, gx + 1.2, -5.48, -4.97, 2.55, 2.97, pearl)
    a.part(gp, bevel=0.03, seg=1, name="gate_piers")
    fprism(ck['mid'], 'N', -5.4, _band_uv(gw, 2.45, 0.24, 'round', 10, gx, 0.0), -0.43, 0.08, pearl)
    fbox(ck['mid'], 'N', -5.4, gx - 1.25, gx + 1.25, 2.95, 3.08, -0.48, 0.12, wall)
    fbox(ck['mid'], 'N', -5.4, gx - 0.6, gx + 0.6, 3.08, 3.42, -0.43, 0.08, pearl)
    fbox(ck['none'], 'N', -5.4, gx - 0.66, gx + 0.66, 3.42, 3.5, -0.46, 0.11, wall)
    fbox(ck['small'], 'N', -5.4, gx - 0.11, gx + 0.11, 2.3, 2.6, -0.02, 0.15, pearl)
    for s in (-1, 1):
        hx = gx + s * gw / 2
        M = M_tr(hx, -5.12, 0.0) @ M_rot(-s * 72.0)
        fs = ck['small'].box(-s * 0.82 if s > 0 else 0.0, 0.0 if s > 0 else 0.82, -0.03, 0.03, 0.1, 2.1, 'SKY_Wood')
        ck['small'].transform(M, faces=fs)
        for zz in (0.5, 1.6):
            fs = ck['none'].box(-s * 0.8 if s > 0 else 0.02, -0.02 if s > 0 else 0.8, -0.05, 0.05, zz, zz + 0.07,
                                'SKY_Ink')
            ck['none'].transform(M, faces=fs)
    pendant(ck, gx, -5.22, 2.2, drop=0.55)
    lattice_bars(ck['none'], 'W', X1, (-2.82, -0.98, 0.43, 1.37), -0.2, -0.16, 'SKY_Wood', spacing=0.2, bw=0.035)
    fountain(ck, 2.2, -2.2, zc)
    ck['none'].lathe([(0.0, zc), (0.62, zc), (0.62, zc + 0.36), (0.68, zc + 0.4), (0.68, zc + 0.46), (0.54, zc + 0.46),
                      (0.54, zc + 0.4), (0.0, zc + 0.4)], 12, deep, mats=[deep] * 6 + ['SKY_PalmTrunk'], cx=4.35,
                     cy=-0.2)
    palm2(ck, 4.35, -0.2, zc + 0.38, height=5.2, lean=(-0.3, -0.25), fronds=8, frond_len=2.3, seed=21)
    vine(ck, [(5.7, -4.5, wz + 0.25), (5.72, -3.7, wz + 0.3), (4.8, -5.2, wz + 0.25)], r=0.28, seed=8)
    planter2(ck, -0.95, -4.55, zc, 0.6, 0.6, h=0.55, seed=6)
    masts_sail(ck, [(xb + 0.06, -4.3, 4.1, 4.45), (3.85, -4.72, zc, 3.7), (xb + 0.06, 0.2, 4.6, 4.95)], sag=0.2)
    ck.flush()


@asset("bldg_depot", "Buildings", "poi", ao=BLD_AO, render=BLD_RENDER)
def bldg_depot(a):
    """Courier depot: sandstone garage hall with a teal-framed bay, half-raised ribbed roller shutter, lit
    workshop interior (charging post, bench, shelving), hazard-striped jambs, dock bumpers and bollards, blank
    teal signboard, wall louvres, solar roof; pearl two-storey office annex; solar canopy over the front-right
    apron where ANCHOR_cell_dock sits."""
    HX0, HX1, Y0, Y1 = -5.9, 2.4, -3.0, 5.9
    zh, zp = 6.0, 6.6
    AX1 = 5.9
    sand, pearl, teal = 'SKY_Sandstone', 'SKY_Pearl', 'SKY_Teal'
    win = Kit(a, tag="win_")
    bx, bw, bh = -1.75, 5.6, 4.6
    ops = [Op('N', bx, -0.1, bw, bh + 0.1, 'flat', depth=7.4, back=pearl, reveal=pearl, sill=False, frame=teal,
              frame_t=0.22, backing=False),
           Op('E', 0.6, 3.6, 1.6, 0.9, 'segment', depth=0.35, seg=6, bars='mull', bar_mat=teal, sill='simple'),
           Op('E', 3.6, 0.3, 1.1, 2.3, 'flat', depth=0.32, back=teal, sill=False, door=True, frame=pearl,
              frame_t=0.1, head='lintel'),
           Op('E', -1.55, 0.35, 2.3, 2.05, 'flat', depth=0.42, back='SKY_Ink', sill=False, frame=teal, frame_t=0.1,
              backing=False),
           Op('S', -3.6, 3.6, 1.6, 0.9, 'segment', depth=0.35, seg=6, bars='mull', bar_mat=teal, sill='simple'),
           Op('S', -0.4, 3.6, 1.6, 0.9, 'segment', depth=0.35, seg=6, bars='mull', bar_mat=teal, sill='simple')]
    mass(a, HX0, HX1, Y0, Y1, 0.0, zp, sand, ops, name="hall", kit=win, well=(0.25, zh))
    # ---- bay: shutter, rails, housing, hazard jambs, bumpers, bollards, sign
    roller_shutter(win, 'N', Y0, bx, 3.45, bh + 0.02, bw - 0.1, d=-0.32)
    for s in (-1, 1):
        uu = bx + s * (bw / 2 - 0.05)
        fbox(win['none'], 'N', Y0, uu - 0.06, uu + 0.06, 0.02, bh, -0.42, -0.24, 'SKY_Metal')
        ua, ub = sorted((bx + s * (bw / 2 + 0.24), bx + s * (bw / 2 + 0.02)))
        hazard_stripes(win, 'N', Y0, ua, ub, 0.02, 1.1, 0.0, 0.075, n=5)
        uu = bx + s * (bw / 2 + 0.55)
        fbox(win['small'], 'N', Y0, uu - 0.16, uu + 0.16, 0.55, 1.05, -0.02, 0.16, 'SKY_Rubber')
        c = fpt('N', Y0, bx + s * (bw / 2 + 0.15), 0.0, 0.55)
        bollard(win, c[0], c[1])
    fbox(win['mid'], 'N', Y0, bx - 2.0, bx + 2.0, bh + 0.36, bh + 0.9, -0.02, 0.07, teal)
    fbox(win['none'], 'N', Y0, bx - 2.06, bx + 2.06, bh + 0.32, bh + 0.36, -0.02, 0.09, 'SKY_Brass')
    fbox(win['none'], 'N', Y0, bx - 2.06, bx + 2.06, bh + 0.9, bh + 0.94, -0.02, 0.09, 'SKY_Brass')
    fbox(win['none'], 'N', Y0, bx - 1.8, bx + 1.8, bh + 0.41, bh + 0.46, 0.06, 0.09, 'SKY_TealGlow')
    # ---- parcel locker bank in the east wall recess
    lu0, lz0, lw, lh, nc, nr = -1.55 - 1.15, 0.35, 2.3, 2.05, 4, 4
    for i in range(nc):
        for j in range(nr):
            ua = lu0 + 0.04 + i * (lw - 0.08) / nc
            ub = ua + (lw - 0.08) / nc - 0.035
            va = lz0 + 0.06 + j * (lh - 0.12) / nr
            vb = va + (lh - 0.12) / nr - 0.035
            m = 'SKY_TealGlow' if (i, j) == (3, 2) else (teal if (i + j) % 2 == 0 else 'SKY_TealLight')
            fbox(win['none'], 'E', HX0, ua, ub, va, vb, -0.42, -0.385, m)
            if m != 'SKY_TealGlow':
                fbox(win['none'], 'E', HX0, ub - 0.09, ub - 0.05, (va + vb) / 2 - 0.05, (va + vb) / 2 + 0.05, -0.39,
                     -0.36, 'SKY_Brass')
    # ---- workshop interior seen through the bay
    ix0, ix1, iy0, iy1 = bx - bw / 2, bx + bw / 2, Y0, Y0 + 7.4
    win['none'].box(ix0 - 0.02, ix1 + 0.02, iy0 - 0.02, iy1 + 0.02, 0.0, 0.05, 'SKY_Kerb')
    for xx in (bx - 1.1, bx + 1.1):
        win['none'].box(xx - 0.05, xx + 0.05, iy0 + 0.6, iy1 - 1.2, 0.05, 0.06, 'SKY_RoadLine')
    win['none'].box(bx - 1.1, bx + 1.1, iy1 - 1.25, iy1 - 1.15, 0.05, 0.06, 'SKY_RoadLine')
    win['none'].box(ix0 + 0.2, ix1 - 0.2, iy1 - 0.45, iy1 - 0.02, 0.05, 2.4, 'SKY_Ink')
    rnd = random.Random(5)
    for lv in (0.6, 1.5):
        xx = ix0 + 0.4
        while xx < ix1 - 0.6:
            ww = rnd.uniform(0.35, 0.6)
            crate_h = rnd.uniform(0.3, 0.55)
            win['none'].box(xx, xx + ww, iy1 - 0.85, iy1 - 0.45, lv, lv + crate_h,
                            rnd.choice(('SKY_Wood', 'SKY_Coral', 'SKY_TealLight', 'SKY_Pearl')))
            xx += ww + rnd.uniform(0.1, 0.3)
    win['none'].box(ix0 + 0.15, ix0 + 0.75, iy0 + 2.0, iy0 + 4.2, 0.05, 0.92, teal)
    win['none'].box(ix0 + 0.1, ix0 + 0.8, iy0 + 1.95, iy0 + 4.25, 0.92, 0.98, 'SKY_Wood')
    win['none'].box(ix1 - 0.6, ix1 - 0.2, iy0 + 2.6, iy0 + 3.0, 0.05, 1.5, teal)
    win['none'].box(ix1 - 0.62, ix1 - 0.58, iy0 + 2.65, iy0 + 2.95, 1.1, 1.4, 'SKY_TealGlow')
    for yy in (iy0 + 2.0, iy0 + 4.8):
        pendant(win, bx, yy, bh + 0.0, drop=0.6)
    # wall louvres, crates and a pallet by the left jamb
    louvre_vent(win, 'E', HX0, -1.6, 3.8, 1.1, 0.8)
    louvre_vent(win, 'S', Y1, -2.0 + 0.0, 4.6, 1.1, 0.7)
    crate(win, -5.45, -3.55, 0.0, s=0.75, rot=8.0)
    crate(win, -5.4, -3.55, 0.75, s=0.6, rot=-6.0)
    pallet(win, -5.2, -4.5, 0.0, rot=90.0)
    crate(win, -5.15, -4.6, 0.15, s=0.55, h=0.5, rot=4.0)
    win.flush()
    # ---- hall trims and roof
    fac = Kit(a, tag="facade_")
    tiers(a, HX0, HX1, Y0, Y1, 0.3, [(0.3, 0.08)], 'SKY_SandstoneDeep', name="plinth", faces='NSE')
    tiers(a, HX0, HX1, Y0, Y1, zh - 0.25, [(0.18, 0.07)], teal, name="teal_band", faces='NSE')
    tiers(a, HX0, HX1, Y0, Y1, zh + 0.06, [(0.14, 0.12)], pearl, name="cornice", faces='NSE')
    drainpipe(fac, 'S', Y1, -5.4, zh - 0.6, z_bot=0.3)
    mb = MB()
    coping(mb, HX0, HX1, Y0, Y1, 0.25, zp, 0.09, 0.05, pearl, faces='NSE')
    a.part(mb, bevel=0.02, seg=1, name="coping")
    solar2(fac, -5.3, 1.7, -2.4, 3.2, zh, rows=3)
    for xx in (-4.0, -0.5):
        louvre_vent(fac, 'N', 4.35, xx, zh + 0.02, 1.0, 0.5)
        fac['mid'].box(xx - 0.55, xx + 0.55, 4.35, 5.2, zh - 0.02, zh + 0.55, 'SKY_Metal')
    ac_unit(fac, 1.3, 4.7, zh, rot=180.0)
    fac.flush()

    # ---- office annex
    ann = Kit(a, tag="annex_")
    aops = [Op('N', 4.15, 0.3, 1.1, 2.4, 'flat', depth=0.36, back=teal, sill=False, door=True, frame=pearl,
               frame_t=0.1, head='lintel', head_mat=teal, steps=1, step_mat='SKY_SandstoneDeep'),
            Op('N', 4.15, 4.1, 2.2, 1.5, 'flat', depth=0.38, inner=teal, bars='mull', sill=True, head='lintel',
               head_mat=teal, curtain='SKY_Fabric'),
            Op('W', -1.0, 1.1, 1.0, 1.7, 'round', depth=0.38, seg=8, bars='cross', bar_mat=teal, sill='simple'),
            Op('W', 2.6, 1.1, 1.0, 1.7, 'round', depth=0.38, seg=8, bars='cross', bar_mat=teal, sill='simple'),
            Op('W', -1.0, 4.1, 1.0, 1.7, 'round', depth=0.38, seg=8, bars='cross', bar_mat=teal, sill='simple'),
            Op('W', 2.6, 4.1, 1.0, 1.7, 'round', depth=0.38, seg=8, bars='cross', bar_mat=teal, sill='simple'),
            Op('S', 4.15, 4.1, 1.0, 1.7, 'round', depth=0.38, seg=8, bars='cross', bar_mat=teal, sill='simple')]
    mass(a, HX1, AX1, Y0, Y1, 0.0, 7.8, pearl, aops, name="annex", kit=ann, well=(0.22, 7.2))
    tiers(a, HX1, AX1, Y0, Y1, 0.3, [(0.3, 0.08)], 'SKY_SandstoneDeep', name="annex_plinth", faces='NSW')
    tiers(a, HX1, AX1, Y0, Y1, 3.62, [(0.16, 0.07)], teal, name="annex_band", faces='NSW')
    tiers(a, HX1, AX1, Y0, Y1, 7.26, [(0.14, 0.1)], pearl, name="annex_cornice", faces='NSW')
    mb = MB()
    coping(mb, HX1, AX1, Y0, Y1, 0.22, 7.8, 0.08, 0.05, teal, faces='NSW')
    a.part(mb, bevel=0.02, seg=1, name="annex_coping")
    water_tank(ann, 4.6, 4.4, 7.2, r=0.4, h=0.7, legs=0.45)
    ann['none'].cyl(0.035, 7.2, 8.52, 6, 'SKY_Brass', cx=3.0, cy=4.9)
    ann['none'].sphere(0.07, 6, 3, 'SKY_TealGlow', c=(3.0, 4.9, 8.58))
    for zz in (8.0, 8.35):
        ann['none'].box(2.75, 3.25, 4.88, 4.92, zz, zz + 0.03, 'SKY_Brass')
    roof_hatch(ann, 4.4, 1.6, 7.2, s=0.75)
    ann.flush()

    # ---- solar canopy over the dock bay (ANCHOR_cell_dock stays clear underneath)
    can = Kit(a, tag="canopy_")
    for x in (2.85, 5.65):
        can['mid'].box(x - 0.1, x + 0.1, -5.75, -5.55, 0.0, 3.0, pearl)
        can['none'].box(x - 0.15, x + 0.15, -5.8, -5.5, 0.0, 0.25, pearl)
        p0 = Vector((x, -5.62, 2.2))
        p1 = Vector((x, -4.6, 2.98))
        can['none'].sweep([p0, p1], circle(0.03, 5), 'SKY_Brass')
    can['mid'].box(2.6, 5.95, -5.82, -5.5, 2.95, 3.15, teal)
    for x in (2.85, 5.65):
        can['mid'].box(x - 0.1, x + 0.1, -5.6, Y0 + 0.02, 2.95, 3.15, teal)
    pts = [(-5.9, 3.15), (Y0, 3.15), (Y0, 3.5), (-5.9, 3.22)]
    can['small'].prism_frame(pts, (0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), 2.62, 5.92, 'SKY_Ink', front=teal,
                             back=teal)
    for xx in (3.45, 4.27, 5.1):
        p = [(-5.88, 3.22), (Y0 - 0.02, 3.5), (Y0 - 0.02, 3.515), (-5.88, 3.235)]
        can['none'].prism_frame(p, (0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), xx - 0.018, xx + 0.018, teal)
    can['none'].box(2.65, 5.9, -5.86, -5.8, 2.97, 3.05, 'SKY_TealGlow')
    can.flush()
    a.empty("ANCHOR_cell_dock", (4.4, -4.8, 0.0))
    a.notes.append("ANCHOR_cell_dock under the solar canopy at the front-right (viewer facing the door; Unity -X side).")


def transformer2(kit, lights, x, y):
    """Pad-mounted transformer: striped concrete pad, finned tank with radiator headers, conservator on
    brackets, ribbed HV bushings, LV bushings, cable box, brass plate; status lamp goes to PowerLights."""
    kit['mid'].box(x - 1.2, x + 1.2, y - 0.98, y + 0.98, 0.0, 0.28, 'SKY_Kerb')
    n = 12
    for i in range(n):
        x0, x1 = x - 1.2 + 2.4 * i / n, x - 1.2 + 2.4 * (i + 1) / n
        m = 'SKY_Coral' if i % 2 == 0 else 'SKY_Pearl'
        kit['none'].box(x0, x1, y - 1.0, y - 0.96, 0.06, 0.24, m)
        kit['none'].box(x0, x1, y + 0.96, y + 1.0, 0.06, 0.24, m)
    kit['mid'].box(x - 0.7, x + 0.7, y - 0.56, y + 0.56, 0.27, 2.02, 'SKY_Metal')
    kit['mid'].box(x - 0.76, x + 0.76, y - 0.62, y + 0.62, 2.02, 2.12, 'SKY_Metal')
    kit['none'].box(x - 0.74, x + 0.74, y - 0.6, y + 0.6, 0.27, 0.36, 'SKY_Ink')
    # radiator fin banks (comb prisms) with top/bottom headers
    for side in (-1, 1):
        xb_, xt_ = x + side * 0.68, x + side * 0.98
        pts = [(xb_, y - 0.5)]
        k = 0
        yy = y - 0.5
        while yy < y + 0.46:
            pts += [(xt_, yy), (xt_, yy + 0.035), (x + side * 0.72, yy + 0.035), (x + side * 0.72, yy + 0.11)]
            yy += 0.11
        pts[-1] = (x + side * 0.72, y + 0.5)
        pts.append((xb_, y + 0.5))
        kit['none'].prism(pts, 0.5, 1.82, 'SKY_Metal')
        for zz in (0.48, 1.84):
            kit['none'].sweep([(x + side * 0.88, y - 0.52, zz), (x + side * 0.88, y + 0.52, zz)], circle(0.045, 6),
                              'SKY_Metal')
    # conservator on brackets
    for xx in (x - 0.45, x + 0.45):
        kit['none'].box(xx - 0.04, xx + 0.04, y + 0.25, y + 0.33, 2.12, 2.45, 'SKY_Metal')
    kit['none'].sweep([(x - 0.62, y + 0.29, 2.58), (x + 0.62, y + 0.29, 2.58)], circle(0.17, 10), 'SKY_Metal')
    # HV bushings on top, LV bushings on the front
    for k in (-0.38, 0.0, 0.38):
        kit['none'].lathe([(0.0, 2.12), (0.1, 2.12), (0.1, 2.2), (0.15, 2.24), (0.08, 2.32), (0.14, 2.38),
                           (0.07, 2.47), (0.12, 2.53), (0.05, 2.62), (0.0, 2.7)], 6, 'SKY_Pearl', cx=x + k, cy=y - 0.18)
    for k in (-0.3, 0.0, 0.3):
        c = (x + k, y - 0.56)
        fs = kit['none'].lathe([(0.0, 0.0), (0.055, 0.0), (0.07, 0.05), (0.05, 0.12), (0.06, 0.16), (0.0, 0.22)], 6,
                               'SKY_Pearl')
        kit['none'].transform(M_tr(c[0], c[1], 1.62) @ M_rot(90.0, 'X'), faces=fs)
    kit['small'].box(x - 0.55, x - 0.15, y - 0.75, y - 0.56, 0.5, 1.05, 'SKY_Teal')
    kit['none'].box(x + 0.18, x + 0.5, y - 0.575, y - 0.555, 1.1, 1.32, 'SKY_Brass')
    lights['none'].box(x + 0.32, x + 0.44, y - 0.6, y - 0.555, 1.72, 1.84, 'SKY_TealGlow')


def fence_run(kit, p0, p1, z0=0.0, h=1.7, post_every=1.4, mat='SKY_Metal', bar=0.22):
    """Low pearl kerb wall with a metal post-and-bar fence on top, straight run p0 -> p1 (XY)."""
    P0, P1 = Vector((p0[0], p0[1], 0.0)), Vector((p1[0], p1[1], 0.0))
    d = P1 - P0
    L = d.length
    t = d.normalized()
    nrm = Vector((-t.y, t.x, 0.0))
    ang = math.degrees(math.atan2(t.y, t.x))
    M = M_tr(P0.x, P0.y, z0) @ M_rot(ang)
    fs = kit['mid'].box(-0.06, L + 0.06, -0.08, 0.08, 0.0, 0.3, 'SKY_Kerb')
    kit['mid'].transform(M, faces=fs)
    nposts = max(1, int(round(L / post_every)))
    for i in range(nposts + 1):
        xx = L * i / nposts
        fs = kit['none'].box(xx - 0.04, xx + 0.04, -0.04, 0.04, 0.29, h, mat)
        kit['none'].transform(M, faces=fs)
    for zz in (0.45, h - 0.06):
        fs = kit['none'].box(0.0, L, -0.025, 0.025, zz, zz + 0.05, mat)
        kit['none'].transform(M, faces=fs)
    nb = max(1, int(L / bar))
    for i in range(1, nb):
        xx = L * i / nb
        fs = kit['none'].box(xx - 0.012, xx + 0.012, -0.012, 0.012, 0.29, h - 0.06, mat)
        kit['none'].transform(M, faces=fs)


@asset("bldg_substation", "Buildings", "poi", ao=BLD_AO, render=dict(BLD_RENDER, az=25.0))
def bldg_substation(a):
    """Airfield substation: pearl switch house with the recessed cell socket on its north face (brass
    frame, hazard stripes, seat ring), louvred steel door with hazard plate, wall louvres, conduits and cable
    trays, roof vents and lightning rod; two finned transformers in fenced yards; PowerLights (light bar,
    beacon, status lamps, cornice glow line) stays a separate glow object."""
    X0, X1, Y0, Y1 = -2.8, 2.8, -1.6, 2.6
    zr = 3.6
    pearl, teal, coral = 'SKY_Pearl', 'SKY_Teal', 'SKY_Coral'
    det = Kit(a, tag="det_")
    lights = Kit(a, target="PowerLights", tag="lights_")
    # recess sized for the courier power cell (0.14 m dia x 0.35 m, pivot at its bottom centre)
    sock_u, sock_z = 1.2, 1.02
    sw, sh, fw = 0.42, 0.52, 0.12
    socket = Op('N', sock_u, sock_z, sw, sh, 'flat', depth=0.42, back='SKY_Ink', sill=False, reveal='SKY_Metal')
    ops = [socket,
           Op('N', -1.0, 0.3, 1.25, 2.35, 'flat', depth=0.32, back=teal, sill=False, frame=coral, frame_t=0.1,
              head='lintel', head_mat=pearl, backing=False),
           Op('E', 0.5, 1.4, 1.5, 0.95, 'flat', depth=0.3, back='SKY_Ink', sill='simple', frame=teal, frame_t=0.08),
           Op('W', 0.5, 1.4, 1.5, 0.95, 'flat', depth=0.3, back='SKY_Ink', sill='simple', frame=teal, frame_t=0.08)]
    mass(a, X0, X1, Y0, Y1, 0.0, zr + 0.6, pearl, ops, name="house", kit=det, well=(0.2, zr))
    # louvres in the side openings, steel door detail, hazard plate, lamp
    for f, pl in (('E', X0), ('W', X1)):
        louvre_leaf(det, f, pl, -0.25, 1.25, 1.4, 2.35, 'SKY_Metal', d0=-0.27, t=0.07, pitch=0.12)
    fbox(det['none'], 'N', Y0, -1.55, -0.45, 1.75, 2.35, -0.33, -0.3, 'SKY_Metal')
    for k in range(5):
        vv = 1.82 + k * 0.1
        fbox(det['none'], 'N', Y0, -1.5, -0.5, vv, vv + 0.04, -0.3, -0.27, 'SKY_Ink')
    fbox(det['none'], 'N', Y0, -0.5, -0.44, 1.0, 1.25, -0.3, -0.24, 'SKY_Brass')
    fprism(det['none'], 'N', Y0, [(-2.7, 1.62), (-1.9, 1.62), (-2.3, 2.32)], -0.01, 0.03, coral)
    fprism(det['none'], 'N', Y0, [(-2.25, 2.12), (-2.37, 1.9), (-2.29, 1.9), (-2.35, 1.7), (-2.21, 1.95),
                                   (-2.29, 1.95), (-2.22, 2.12)], 0.02, 0.04, 'SKY_Ink')
    # flat bulkhead lamp (keeps the north face within the footprint)
    fbox(det['small'], 'N', Y0, -2.45, -2.15, 2.62, 2.84, -0.01, 0.06, 'SKY_Brass')
    fbox(det['none'], 'N', Y0, -2.4, -2.2, 2.66, 2.8, 0.05, 0.11, 'SKY_Light')
    for uu in (-2.33, -2.27):
        fbox(det['none'], 'N', Y0, uu - 0.012, uu + 0.012, 2.64, 2.82, 0.05, 0.125, 'SKY_Brass')
    # socket housing frame (brass) + coral warning stripes below it
    hu = sw / 2 + fw
    mb = MB()
    fbox(mb, 'N', Y0, sock_u - hu, sock_u + hu, sock_z - fw, sock_z, 0.0, 0.16, 'SKY_Brass')
    fbox(mb, 'N', Y0, sock_u - hu, sock_u + hu, sock_z + sh, sock_z + sh + fw, 0.0, 0.16, 'SKY_Brass')
    fbox(mb, 'N', Y0, sock_u - hu, sock_u - sw / 2, sock_z, sock_z + sh, 0.0, 0.16, 'SKY_Brass')
    fbox(mb, 'N', Y0, sock_u + sw / 2, sock_u + hu, sock_z, sock_z + sh, 0.0, 0.16, 'SKY_Brass')
    a.part(mb, bevel=0.015, seg=1, name="socket_frame")
    mb = MB()
    for k in range(4):
        z0 = 0.4 + k * 0.13
        m = 'SKY_Coral' if k % 2 == 0 else 'SKY_Ink'
        fbox(mb, 'N', Y0, sock_u - hu, sock_u + hu, z0, z0 + 0.09, 0.0, 0.04, m)
    a.part(mb, name="socket_stripes")
    # seat (cradle ring) inside the recess - SOCKET_cell is the seat point (cell pivot = bottom centre)
    mb = MB()
    fbox(mb, 'N', Y0, sock_u - 0.15, sock_u + 0.15, sock_z, sock_z + 0.08, -0.4, -0.06, 'SKY_Metal')
    seat_c = fpt('N', Y0, sock_u, sock_z + 0.08, -0.23)
    mb.lathe([(0.075, seat_c[2]), (0.1, seat_c[2]), (0.1, seat_c[2] + 0.06), (0.075, seat_c[2] + 0.06)], 10, 'SKY_Teal',
             cx=seat_c[0], cy=seat_c[1], closed=True)
    a.part(mb, name="socket_seat")
    a.empty("SOCKET_cell", seat_c)
    # PowerLights: light bar above the socket, roof beacon, cornice glow line, transformer status lamps
    fbox(lights['none'], 'N', Y0, sock_u - hu, sock_u + hu, sock_z + sh + fw + 0.12, sock_z + sh + fw + 0.24, 0.04,
         0.14, 'SKY_TealGlow')
    lights['none'].lathe([(0, zr + 0.75), (0.16, zr + 0.75), (0.16, zr + 0.88), (0.12, zr + 0.98), (0, zr + 1.02)], 8,
                         'SKY_TealGlow', cx=X1 - 0.6, cy=Y0 + 0.6)
    fbox(lights['none'], 'N', Y0, X0 + 0.3, X1 - 0.3, zr - 0.52, zr - 0.47, 0.0, 0.07, 'SKY_TealGlow')
    mb = MB()
    fbox(mb, 'N', Y0, sock_u - hu - 0.04, sock_u + hu + 0.04, sock_z + sh + fw + 0.08, sock_z + sh + fw + 0.12, 0.0, 0.17,
         'SKY_Brass')
    mb.lathe([(0, zr + 0.6), (0.2, zr + 0.6), (0.2, zr + 0.75), (0, zr + 0.75)], 8, 'SKY_Brass', cx=X1 - 0.6, cy=Y0 + 0.6)
    a.part(mb, name="light_mounts")
    # trims, coping, roof kit
    tiers(a, X0, X1, Y0, Y1, 0.3, [(0.3, 0.075)], 'SKY_SandstoneDeep', name="plinth")
    tiers(a, X0, X1, Y0, Y1, zr - 0.25, [(0.15, 0.05)], teal, name="teal_band")
    tiers(a, X0, X1, Y0, Y1, zr + 0.06, [(0.14, 0.075)], pearl, name="cornice")
    mb = MB()
    coping(mb, X0, X1, Y0, Y1, 0.2, zr + 0.6, 0.09, 0.05, 'SKY_Sandstone')
    a.part(mb, bevel=0.02, seg=1, name="coping")
    for (x, y) in ((-1.5, 1.3), (0.15, 1.3)):
        det['mid'].box(x - 0.45, x + 0.45, y - 0.45, y + 0.45, zr - 0.02, zr + 0.42, 'SKY_Metal')
        louvre_leaf(det, 'N', y - 0.45, x - 0.4, x + 0.4, zr + 0.05, zr + 0.38, 'SKY_Ink', d0=-0.01, t=0.04)
        det['mid'].box(x - 0.55, x + 0.55, y - 0.55, y + 0.55, zr + 0.42, zr + 0.52, 'SKY_Ink')
    det['none'].cyl(0.025, zr - 0.02, zr + 1.3, 6, 'SKY_Brass', cx=X0 + 0.45, cy=Y1 - 0.45)
    det['none'].sphere(0.05, 6, 3, 'SKY_Brass', c=(X0 + 0.45, Y1 - 0.45, zr + 1.33))
    # back wall: louvres and a conduit run
    for uu in (-1.5, 1.5):
        louvre_vent(det, 'S', Y1, uu, 1.55, 1.1, 0.75)
    det['none'].sweep([(-2.0, Y1 + 0.03, 0.3), (-2.0, Y1 + 0.03, 2.9), (2.0, Y1 + 0.03, 2.9), (2.0, Y1 + 0.03, 0.3)],
                      circle(0.045, 6), teal)
    # transformers, fenced yards, conduits and cable trays
    for s in (-1, 1):
        transformer2(det, lights, s * 4.4, 0.5)
        xa, xb = s * 3.05, s * 5.82
        fence_run(det, (xa, -1.66), (xb, -1.66))
        fence_run(det, (xb, -1.66), (xb, 2.56))
        fence_run(det, (xb, 2.56), (xa, 2.56))
        det['none'].sweep([(s * 3.95, 0.5, 1.6), (s * 3.4, 0.5, 2.25), (s * 3.05, 0.5, 2.5), (s * 2.78, 0.5, 2.5)],
                          circle(0.09, 6), teal)
        det['none'].sweep([(s * 3.85, -0.66, 0.75), (s * 3.6, -0.95, 0.3), (s * 3.0, -1.0, 0.3), (s * 2.78, -1.0, 0.3)],
                          circle(0.07, 6), 'SKY_Metal')
        det['small'].box(s * 2.8 - 0.15, s * 2.8 + 0.15, 0.25, 0.75, 2.2, 2.8, 'SKY_Metal')
        # cable tray along the house wall up to the roof
        xa_, xb_ = sorted((s * 2.78, s * 2.92))
        det['none'].box(xa_, xb_, 1.2, 1.5, 2.6, zr + 0.3, teal)
    det.flush()
    lights.flush()
    a.notes.append("SOCKET_cell sits inside the recessed housing on the north face (~1.1 m). PowerLights is a "
                   "separate object (light bar, roof beacon, cornice glow line, transformer status lamps; "
                   "SKY_TealGlow).")


@asset("bldg_terminal", "Buildings", "poi", ao=BLD_AO, render=dict(BLD_RENDER, az=30.0))
def bldg_terminal(a):
    """Small airport terminal: brass-mullioned curtain wall over a lit lobby (blank teal-glow departure board,
    check-in counters, seating, planters), pearl colonnade carrying a ribbed canopy with glowing fascia and
    downlights, ribbed barrel vault with a teal skylight strip and glazed lunettes, arched side windows,
    forecourt with benches, bollards and a blank sign pylon. ANCHOR_convoy_stop at the north kerb."""
    X0, X1, Y0, Y1 = -6.85, 6.85, -2.8, 4.85
    zw = 5.6
    sand, pearl, teal, brass = 'SKY_Sandstone', 'SKY_Pearl', 'SKY_Teal', 'SKY_Brass'
    win = Kit(a, tag="win_")
    gw, gh, gz, gd = 11.6, 4.55, 0.3, 4.4
    ops = [Op('N', 0.0, gz, gw, gh, 'flat', depth=gd, back=pearl, reveal=pearl, sill=False, backing=False)]
    for f in ('E', 'W'):
        for uu in (-0.95, 1.05, 3.05):
            ops.append(Op(f, uu, 1.0, 0.9, 3.2, 'round', depth=0.42, seg=8, frame=pearl, frame_t=0.1,
                          head='keylite', head_mat=pearl, inner=teal, bars='fan', sill='simple'))
    ops += [Op('S', -4.6, 0.3, 1.3, 2.5, 'flat', depth=0.34, back=teal, sill=False, door=True, frame=pearl,
               frame_t=0.1, head='lintel'),
            Op('S', 2.4, 0.3, 3.0, 3.1, 'flat', depth=0.5, back=pearl, reveal=pearl, sill=False, frame=teal,
               frame_t=0.14, backing=False)]
    mass(a, X0, X1, Y0, Y1, 0.0, zw, sand, ops, name="hall", kit=win, fm={'top': 'SKY_Kerb'})
    roller_shutter(win, 'S', Y1, 2.4, 0.32, 3.4, 2.98, d=-0.35)
    # ---- curtain wall: glass, mullion grid, transoms, entrance doors
    yN = Y0
    fbox(win['none'], 'N', yN, -gw / 2 - 0.02, gw / 2 + 0.02, gz - 0.02, gz + gh + 0.02, -0.27, -0.25, 'SKY_Glass')
    nm = 8
    for k in range(nm + 1):
        uu = -gw / 2 + gw * k / nm
        fbox(win['none'], 'N', yN, uu - 0.06, uu + 0.06, gz, gz + gh, -0.3, -0.16, brass)
    for vv in (gz + 0.08, gz + 2.75, gz + gh - 0.08):
        fbox(win['none'], 'N', yN, -gw / 2, gw / 2, vv - 0.05, vv + 0.05, -0.29, -0.17, brass)
    for du in (-0.73, 0.73):
        fbox(win['none'], 'N', yN, du - 0.03, du + 0.03, gz, gz + 2.7, -0.24, -0.2, teal)
        for s in (-1, 1):
            fbox(win['none'], 'N', yN, du + s * 0.12 - 0.015, du + s * 0.12 + 0.015, gz + 0.9, gz + 1.6, -0.22, -0.13,
                 brass)
    # ---- lobby interior (seen through the translucent glass)
    ly0, ly1 = yN, yN + gd
    win['none'].box(-gw / 2 - 0.02, gw / 2 + 0.02, ly0 - 0.02, ly1 + 0.02, gz - 0.02, gz + 0.03, 'SKY_Kerb')
    win['mid'].box(-2.4, 2.4, ly1 - 0.25, ly1 - 0.02, gz + 2.4, gz + 3.5, 'SKY_Ink')
    win['none'].box(-2.28, 2.28, ly1 - 0.28, ly1 - 0.24, gz + 2.5, gz + 3.4, 'SKY_TealGlow')
    for k in range(3):
        win['none'].box(-2.1, 2.1, ly1 - 0.3, ly1 - 0.27, gz + 2.68 + k * 0.25, gz + 2.71 + k * 0.25, 'SKY_Ink')
    for xx in (-4.2, -2.6, 2.6, 4.2):
        win['none'].box(xx - 0.65, xx + 0.65, ly1 - 1.6, ly1 - 1.0, gz, gz + 1.05, 'SKY_Wood')
        win['none'].box(xx - 0.7, xx + 0.7, ly1 - 1.65, ly1 - 0.95, gz + 1.05, gz + 1.12, pearl)
    for row in (0, 1):
        yy = ly0 + 1.4 + row * 0.9
        for xx in (-3.8, -1.0, 1.0, 3.8):
            win['none'].box(xx - 0.9, xx + 0.9, yy - 0.22, yy + 0.22, gz + 0.35, gz + 0.45, teal)
            win['none'].box(xx - 0.9, xx + 0.9, yy + 0.16, yy + 0.24, gz + 0.45, gz + 0.85, teal)
            win['none'].box(xx - 0.75, xx + 0.75, yy - 0.15, yy + 0.15, gz, gz + 0.35, 'SKY_Metal')
    for xx in (-gw / 2 + 0.6, gw / 2 - 0.6):
        planter2(win, xx, ly0 + 1.0, gz, 0.7, 0.7, h=0.6, seed=int(xx), cls='none')
    for xx in (-3.0, 0.0, 3.0):
        pendant(win, xx, ly0 + 2.2, gz + gh, drop=0.9)
    win.flush()

    # ---- facade trims
    fac = Kit(a, tag="facade_")
    tiers(a, X0, X1, Y0, Y1, 0.3, [(0.3, 0.09)], 'SKY_SandstoneDeep', name="plinth", faces='SEW')
    tiers(a, X0, X1, Y0, Y1, zw + 0.04, [(0.16, 0.2), (0.24, 0.1)], pearl, name="cornice")
    ring(fac['none'], X0, X1, Y0, Y1, zw - 0.32, zw - 0.27, 0.13, brass)
    for f, pl in (('E', X0), ('W', X1)):
        for uu in (-2.15, 0.05, 2.05, 4.25):
            fbox(fac['mid'], f, pl, uu - 0.2, uu + 0.2, 0.3, zw - 0.4, -0.02, 0.09, pearl)
    for uu in (-1.0, 0.6):
        louvre_vent(fac, 'S', Y1, uu - 1.6, 3.6, 1.1, 0.7)
    fac.flush()

    # ---- colonnade, ribbed canopy, fascia glow, downlights
    can = Kit(a, tag="canopy_")
    cy = -4.6
    cols = (-6.2, -3.72, -1.24, 1.24, 3.72, 6.2)
    for x in cols:
        can['mid'].box(x - 0.36, x + 0.36, cy - 0.36, cy + 0.36, 0.12, 0.34, pearl)
        can['none'].lathe([(0.0, 0.34), (0.3, 0.34), (0.3, 0.42), (0.25, 0.5), (0.23, 4.7), (0.27, 4.78), (0.27, 4.84),
                           (0.22, 4.88), (0.33, 5.12), (0.0, 5.12)], 10, pearl, cx=x, cy=cy)
        can['none'].lathe([(0.0, 4.76), (0.275, 4.76), (0.275, 4.83), (0.0, 4.83)], 10, brass, cx=x, cy=cy)
        can['mid'].box(x - 0.38, x + 0.38, cy - 0.38, cy + 0.38, 5.12, 5.26, pearl)
        can['mid'].box(x - 0.12, x + 0.12, cy - 0.3, Y0 + 0.02, 5.26, 5.52, pearl)
    mb = MB()
    mb.box(-7.0, 7.0, -5.1, Y0 + 0.25, 5.5, 5.86, pearl)
    solid(a, mb, (), pre=(0.05, 2), post=None, name="canopy_slab", refine=(2.5, 5.0, 1.2))
    can['none'].box(-7.04, 7.04, -5.15, -5.08, 5.47, 5.9, brass)
    can['none'].box(-6.95, 6.95, -5.16, -5.13, 5.55, 5.62, 'SKY_TealGlow')
    for x in (-5.0, -2.5, 0.0, 2.5, 5.0):
        for y in (-4.05, -3.3):
            can['none'].box(x - 0.11, x + 0.11, y - 0.11, y + 0.11, 5.47, 5.505, 'SKY_Light')
    # blank departure board hanging under the canopy (teal glow faces, no text)
    can['mid'].box(-1.05, 1.05, -3.72, -3.56, 4.32, 5.02, 'SKY_Ink')
    can['none'].box(-0.97, 0.97, -3.735, -3.715, 4.4, 4.94, 'SKY_TealGlow')
    can['none'].box(-0.97, 0.97, -3.565, -3.545, 4.4, 4.94, 'SKY_TealGlow')
    for k in range(2):
        zz = 4.58 + k * 0.18
        can['none'].box(-0.9, 0.9, -3.75, -3.73, zz, zz + 0.025, 'SKY_Ink')
    for x in (-0.8, 0.8):
        can['none'].box(x - 0.015, x + 0.015, -3.655, -3.625, 5.0, 5.52, brass)
    # forecourt: paving, border, kerb, bollards, benches, sign pylon, planters
    mb = MB()
    mb.box(-6.85, 6.85, -6.3, Y0 + 0.02, 0.0, 0.12, 'SKY_Kerb')
    solid(a, mb, (), pre=None, post=None, name="forecourt", refine=(2.0, 5.0, 1.0))
    can['none'].box(-6.85, 6.85, -6.33, -6.27, 0.0, 0.135, 'SKY_SandstoneDeep')
    for x in (-4.96, -2.48, 0.0, 2.48, 4.96):
        can['none'].box(x - 0.04, x + 0.04, -6.27, Y0, 0.115, 0.13, 'SKY_SandstoneDeep')
    can['mid'].box(-6.85, 6.85, -6.55, -6.3, 0.0, 0.18, pearl)
    for x in (-6.2, -3.1, 3.1, 6.2):
        bollard(can, x, -6.0, z=0.12, h=0.8, r=0.11, mats=(pearl, brass))
    for x in (-2.48, 2.48):
        can['none'].box(x - 0.8, x + 0.8, -5.0, -4.6, 0.52, 0.6, 'SKY_Wood')
        can['none'].box(x - 0.8, x + 0.8, -4.62, -4.54, 0.6, 0.95, 'SKY_Wood')
        for xx in (x - 0.65, x + 0.65):
            can['none'].box(xx - 0.04, xx + 0.04, -4.95, -4.6, 0.12, 0.52, 'SKY_Metal')
    can['mid'].box(6.25, 6.75, -5.95, -5.75, 0.12, 2.6, teal)
    can['none'].box(6.3, 6.7, -5.97, -5.94, 1.4, 2.45, 'SKY_TealGlow')
    can['none'].box(6.2, 6.8, -6.0, -5.7, 0.12, 0.3, pearl)
    for x in (-5.0, 5.0):
        planter2(can, x, -6.0, 0.12, 1.6, 0.42, h=0.45, seed=int(x) + 9, cls='none')
    can.flush()

    # ---- barrel vault: shell, ribs, teal skylight strip, clerestory, glazed lunettes
    rx, rz, zb = 6.7, 1.75, zw + 0.25
    outer = [(math.cos(math.radians(t)) * rx, zb + rz * math.sin(math.radians(t))) for t in range(0, 181, 10)]
    inner = [(x * 0.97, z - 0.2) for (x, z) in outer]
    yv0, yv1 = Y0 + 0.2, Y1 - 0.2
    mb = MB()
    sk = [i for i in range(len(outer)) if 70 <= i * 10 <= 110]
    poly_l = outer[:sk[0] + 1] + list(reversed(inner[:sk[0] + 1]))
    poly_r = outer[sk[-1]:] + list(reversed(inner[sk[-1]:]))
    for poly in (poly_l, poly_r):
        mb.prism_frame(poly, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), yv0, yv1, pearl)
    solid(a, mb, (), pre=(0.03, 1), post=None, name="vault", refine=(2.0, 1.2, 0.8))
    mb = MB()
    polyc = outer[sk[0]:sk[-1] + 1] + list(reversed(inner[sk[0]:sk[-1] + 1]))
    mb.prism_frame([(x, z - 0.01) for (x, z) in polyc], (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), yv0 + 0.05,
                   yv1 - 0.05, 'SKY_TealLight')
    a.part(mb, name="skylight")
    vk = Kit(a, tag="vault_")
    o2 = [(math.cos(math.radians(t)) * (rx + 0.08), zb + (rz + 0.08) * math.sin(math.radians(t))) for t in range(0, 181, 15)]
    i2 = [(math.cos(math.radians(t)) * rx * 0.96, zb - 0.24 + rz * math.sin(math.radians(t))) for t in range(0, 181, 15)]
    for y in (yv0 + 0.1, -0.2, 1.4, 3.0, yv1 - 0.1):
        vk['mid'].prism_frame(o2 + list(reversed(i2)), (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), y - 0.11, y + 0.11,
                              pearl)
    vk['none'].box(X0 + 0.25, X1 - 0.25, Y0 + 0.3, Y1 - 0.3, zw - 0.02, zb, 'SKY_TealLight')
    lun = [(x * 0.965, z - 0.21) for (x, z) in outer]
    for y in (yv0 + 0.22, yv1 - 0.22):
        vk['none'].prism_frame(lun, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), y - 0.04, y + 0.04, 'SKY_Glass')
        for t in (30, 60, 90, 120, 150):
            ex = math.cos(math.radians(t)) * rx * 0.95
            ez = zb - 0.2 + (rz - 0.05) * math.sin(math.radians(t))
            vk['none'].sweep([(0.0, y, zb - 0.02), (ex, y, ez)], circle(0.045, 4), brass)
        vk['none'].sweep([(math.cos(math.radians(t)) * rx * 0.6, y, zb - 0.2 + rz * 0.6 * math.sin(math.radians(t)) + 0.0)
                          for t in range(0, 181, 30)], circle(0.04, 4), brass)
    vk.flush()
    a.empty("ANCHOR_convoy_stop", (0.0, -7.0, 0.0))
    a.notes.append("ANCHOR_convoy_stop on the road side of the north drop-off kerb (Unity z +7.0).")


def oct_pts(R, a0=22.5, n=8):
    return [(R * math.cos(math.radians(a0 + 360.0 * k / n)), R * math.sin(math.radians(a0 + 360.0 * k / n)))
            for k in range(n)]


@asset("bldg_tower_control", "Buildings", "poi", ao=BLD_AO, render=dict(BLD_RENDER, el=18.0))
def bldg_tower_control(a):
    """Airfield control tower: pearl base with arched windows, hooded door and lanterns; banded sandstone
    shaft with a teal stair window ribbon, glow slit and service ladder; octagonal cab with outward-leaning
    glazing, ink mullions, sunshade louvres, consoles inside, catwalk with railing, glowing eave, radar dome
    and antenna mast with a coral beacon. ANCHOR_lever by the door (ground level)."""
    X0, X1, Y0, Y1 = -3.1, 3.1, -2.9, 2.9
    zb, zbp = 4.0, 4.55
    pearl, sand, teal, brass = 'SKY_Pearl', 'SKY_Sandstone', 'SKY_Teal', 'SKY_Brass'
    win = Kit(a, tag="win_")

    def w_(face, u, z=1.2, w=1.0, h=1.7):
        return Op(face, u, z, w, h, 'round', depth=0.4, seg=8, inner=teal, bars='cross', sill='simple',
                  head='keylite', head_mat=sand)

    ops = [Op('N', -0.9, 0.3, 1.25, 2.45, 'flat', depth=0.36, back=teal, sill=False, door=True, frame=sand,
              frame_t=0.12),
           w_('N', 1.6), w_('E', -1.2), w_('E', 1.2), w_('W', -1.2), w_('W', 1.2), w_('S', -1.4), w_('S', 1.4)]
    mass(a, X0, X1, Y0, Y1, 0.0, zbp, pearl, ops, name="base", kit=win, well=(0.22, zb))
    # door hood on brackets with glow + lanterns
    fbox(win['trim'], 'N', Y0, -1.85, 0.05, 2.95, 3.12, -0.02, 0.92, pearl)
    fbox(win['none'], 'N', Y0, -1.82, 0.02, 2.93, 2.96, 0.05, 0.85, 'SKY_TealGlow')
    fbox(win['none'], 'N', Y0, -1.88, 0.08, 3.08, 3.14, 0.88, 0.96, brass)
    for uu in (-1.7, -0.1):
        fprism_side(win['small'], 'N', Y0, [(-0.02, 2.95), (0.8, 2.95), (0.8, 2.88), (0.0, 2.4)], uu - 0.05, uu + 0.05,
                    pearl)
    for uu in (-1.85, 0.05):
        wall_lamp(win, 'N', Y0, uu, 2.3, arm=0.2)
    win.flush()
    fac = Kit(a, tag="facade_")
    tiers(a, X0, X1, Y0, Y1, 0.3, [(0.3, 0.08)], 'SKY_SandstoneDeep', name="plinth")
    tiers(a, X0, X1, Y0, Y1, zb + 0.05, [(0.14, 0.17), (0.2, 0.08)], sand, name="cornice")
    mb = MB()
    coping(mb, X0, X1, Y0, Y1, 0.22, zbp, 0.08, 0.05, sand)
    a.part(mb, bevel=0.02, seg=1, name="coping")
    merlons2(fac['none'], 'N', Y0, X0 + 0.4, X1 - 0.4, zbp + 0.07, h=0.42, w=0.42, gap=0.36, t=0.2, mat=pearl,
             inset=0.01)
    ac_unit(fac, 2.1, 2.1, zb, rot=180.0, w=0.8, dd=0.5, h=0.5)
    ac_unit(fac, -2.1, 2.1, zb, rot=180.0, w=0.8, dd=0.5, h=0.5)
    fac.flush()

    # ---- shaft: banded rounded square with flare, stair window ribbon, glow slit, ladder
    sh = rr_pts(2.6, 2.6, 0.9, seg=4, step=1.0)
    zs0, zs1 = zb - 0.02, 11.4
    prof = [(0.14, zs0), (0.14, zb + 0.45), (0.0, zb + 0.6)]
    mb = MB()
    rings = [[(p[0], p[1], z) for p in (offset_line(sh, -o, closed=True) if o else sh)] for (o, z) in prof]
    zz = zb + 0.6
    for zt in (6.3, 8.6, 10.9):
        rings.append([(p[0], p[1], zt - 0.2) for p in sh])
        rings.append([(p[0], p[1], zt - 0.2) for p in offset_line(sh, -0.07, closed=True)])
        rings.append([(p[0], p[1], zt) for p in offset_line(sh, -0.07, closed=True)])
        rings.append([(p[0], p[1], zt) for p in sh])
    rings.append([(p[0], p[1], zs1) for p in sh])
    mats = [sand] * (len(rings) - 1)
    for i in range(len(mats)):
        if 3 <= i and (i - 3) % 4 != 3:
            mats[i] = pearl
    mb.loft(rings, sand, mats=mats + [pearl])
    solid(a, mb, (), pre=(0.03, 1), post=None, name="shaft", refine=(2.0, 1.2, 0.8))
    sk = Kit(a, tag="shaft_")
    fbox(sk['none'], 'N', -1.3, -0.16, 0.16, zb + 1.0, 11.0, -0.02, 0.04, 'SKY_TealLight')
    fbox(sk['none'], 'N', -1.3, -0.22, 0.22, zb + 0.95, zb + 1.0, -0.02, 0.06, pearl)
    for zz in (zb + 1.0, 6.4, 8.7):
        fbox(sk['none'], 'S', 1.3, -0.32, 0.32, zz + 0.2, zz + 1.6, -0.02, 0.05, teal)
        fbox(sk['none'], 'S', 1.3, -0.36, 0.36, zz + 0.12, zz + 0.2, -0.02, 0.09, pearl)
        for k in range(3):
            vv = zz + 0.55 + k * 0.4
            fbox(sk['none'], 'S', 1.3, -0.32, 0.32, vv, vv + 0.04, 0.03, 0.07, pearl)
    lx = -1.3
    for s in (-1, 1):
        fbox(sk['none'], 'E', lx, s * 0.22 - 0.025, s * 0.22 + 0.025, zb + 0.05, 11.3, 0.12, 0.17, 'SKY_Metal')
    zz = zb + 0.35
    while zz < 11.2:
        fbox(sk['none'], 'E', lx, -0.22, 0.22, zz, zz + 0.035, 0.13, 0.16, 'SKY_Metal')
        zz += 0.38
    for zz in (5.2, 7.7, 10.2):
        fbox(sk['none'], 'E', lx, -0.04, 0.04, zz, zz + 0.05, -0.02, 0.15, 'SKY_Metal')
    sk.flush()

    # ---- cab: floor slab, glazing, mullions, consoles, sunshade, roof, catwalk
    cab0, cab1 = 11.9, 14.3
    ck = Kit(a, tag="cab_")
    R0 = 2.62
    ck['mid'].lathe([(0.0, 11.35), (1.6, 11.35), (R0 + 0.5, cab0 - 0.12), (R0 + 0.5, cab0 + 0.22), (0.0, cab0 + 0.22)],
                    8, pearl, a0=22.5)
    ck['none'].lathe([(R0 + 0.48, cab0 + 0.02), (R0 + 0.53, cab0 + 0.02), (R0 + 0.53, cab0 + 0.1),
                      (R0 + 0.48, cab0 + 0.1)], 8, brass, a0=22.5, closed=True)
    ck['mid'].lathe([(0.0, cab0 + 0.2), (R0 - 0.1, cab0 + 0.2), (R0 - 0.1, cab0 + 0.62), (0.0, cab0 + 0.62)], 8, pearl,
                    a0=22.5)
    ck['none'].lathe([(0.0, cab0 + 0.6), (R0 - 0.16, cab0 + 0.6), (R0 + 0.18, cab1), (0.0, cab1)], 8, 'SKY_Glass',
                     a0=22.5)
    for k in range(8):
        ang = math.radians(22.5 + 45 * k)
        p0 = Vector(((R0 - 0.13) * math.cos(ang), (R0 - 0.13) * math.sin(ang), cab0 + 0.58))
        p1 = Vector(((R0 + 0.2) * math.cos(ang), (R0 + 0.2) * math.sin(ang), cab1 + 0.02))
        ck['none'].sweep([p0, p1], circle(0.07, 4, a0=45.0), 'SKY_Ink')
    zt_ = cab0 + 0.6 + (cab1 - cab0 - 0.6) * 0.42
    rt_ = R0 - 0.16 + (0.34) * 0.42 + 0.02
    ck['none'].lathe([(rt_ - 0.02, zt_), (rt_ + 0.03, zt_), (rt_ + 0.03, zt_ + 0.05), (rt_ - 0.02, zt_ + 0.05)], 8,
                     'SKY_Ink', a0=22.5, closed=True)
    # consoles + core inside the glass (visible through it in Unity)
    ck['none'].lathe([(1.5, cab0 + 0.62), (2.2, cab0 + 0.62), (2.2, cab0 + 1.45), (1.5, cab0 + 1.6)], 8, teal,
                     a0=22.5, closed=True)
    ck['none'].lathe([(1.55, cab0 + 1.6), (2.15, cab0 + 1.46), (2.15, cab0 + 1.5), (1.55, cab0 + 1.64)], 8,
                     'SKY_TealGlow', a0=22.5, closed=True)
    ck['none'].cyl(0.75, cab0 + 0.62, cab1, 8, pearl)
    # roof with eave glow, sunshade louvres
    RR = R0 + 0.58
    ck['mid'].lathe([(0.0, cab1), (RR, cab1), (RR, cab1 + 0.26), (RR - 0.6, cab1 + 0.46), (1.0, cab1 + 0.62),
                     (0.0, cab1 + 0.66)], 8, pearl, a0=22.5)
    ck['none'].lathe([(RR - 0.04, cab1 - 0.03), (RR + 0.02, cab1 - 0.03), (RR + 0.02, cab1 + 0.03),
                      (RR - 0.04, cab1 + 0.03)], 8, 'SKY_TealGlow', a0=22.5, closed=True)
    for k in range(3):
        zz = cab1 - 0.12 - k * 0.14
        rr_ = R0 + 0.36 - k * 0.04
        ck['none'].lathe([(rr_ - 0.12, zz), (rr_, zz), (rr_, zz + 0.04), (rr_ - 0.12, zz + 0.04)], 8, pearl,
                         a0=22.5, closed=True)
    # catwalk railing (posts + two rails) on the floor slab rim
    Rr = R0 + 0.42
    pts = oct_pts(Rr)
    for i, p in enumerate(pts):
        ck['none'].box(p[0] - 0.035, p[0] + 0.035, p[1] - 0.035, p[1] + 0.035, cab0 + 0.22, cab0 + 1.25, brass)
        q = pts[(i + 1) % 8]
        m = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
        ck['none'].box(m[0] - 0.025, m[0] + 0.025, m[1] - 0.025, m[1] + 0.025, cab0 + 0.22, cab0 + 1.25, brass)
    for zz in (cab0 + 0.72, cab0 + 1.22):
        poly_sweep(ck['none'], [(p[0], p[1], zz) for p in pts], [(-0.03, 0.0), (0.03, 0.0), (0.03, 0.06), (-0.03, 0.06)],
                   brass, closed=True)
    # roof gear: radar dome, antenna mast with arms, dish, coral beacon
    zr_ = cab1 + 0.66
    ck['none'].lathe([(0.0, zr_ - 0.2), (0.3, zr_ - 0.2), (0.3, zr_ + 0.3), (0.0, zr_ + 0.3)], 8, 'SKY_Metal', cx=-1.0,
                     cy=0.6)
    ck['none'].sphere(0.48, 12, 6, pearl, c=(-1.0, 0.6, zr_ + 0.62))
    ck['none'].cyl(0.06, zr_ - 0.05, 17.6, 6, brass, cx=0.5, cy=-0.3)
    for zz, L_ in ((16.4, 0.55), (17.0, 0.35)):
        ck['none'].box(0.5 - L_, 0.5 + L_, -0.33, -0.27, zz, zz + 0.05, brass)
    fs = ck['none'].lathe([(0.0, 0.0), (0.24, 0.06), (0.3, 0.12), (0.26, 0.13), (0.0, 0.07)], 10, pearl)
    ck['none'].transform(M_tr(0.5, -0.45, 15.9) @ M_rot(-70.0, 'X'), faces=fs)
    ck['none'].sphere(0.17, 8, 4, 'SKY_Coral', c=(0.5, -0.3, 17.78))
    ck.flush()
    a.empty("ANCHOR_lever", (1.0, -3.75, 0.0))
    a.notes.append("ANCHOR_lever at ground level just right of the door (viewer facing the door).")


@asset("bldg_hangar", "Buildings", "poi", ao=dict(BLD_AO, dist=3.0), render=dict(BLD_RENDER, az=28.0, el=22.0))
def bldg_hangar(a):
    """Curved-roof hangar 22 m wide x 16 m deep x 9 m high, open front facing Unity north: metal barrel roof
    with standing seams, glazed crown skylight and pearl ribs, glowing portal, head beam with a glazed
    lunette, parked sliding door leaves on tracks, buttressed side walls with bulkhead lamps, back wall with
    door and oculus, interior with threshold stripes, guide lines, office pod with mezzanine, tug and lamps."""
    HW, Y0, Y1 = 11.0, -8.0, 8.0
    Yb = Y1 - 0.08                       # back wall face (details stand proud of it)
    zs, ztop = 1.6, 9.0
    pearl, sand, teal, metal, brass = 'SKY_Pearl', 'SKY_Sandstone', 'SKY_Teal', 'SKY_Metal', 'SKY_Brass'
    n = 24

    def arc_o(i, grow=0.0):
        t = math.pi * i / n
        return ((HW + grow) * math.cos(t), zs + (ztop - zs + grow) * math.sin(t))

    outer = [arc_o(i) for i in range(n + 1)]
    inner = [((HW - 0.3) * math.cos(math.pi * i / n), zs + (ztop - zs - 0.3) * math.sin(math.pi * i / n))
             for i in range(n + 1)]
    ys0, ys1 = Y0 + 0.35, Y1 - 0.1
    k0, k1 = 10, 14                      # skylight between these arch indices

    def band(i0, i1, mat, name, refine=(2.2, 1.6, 1.0)):
        poly = outer[i0:i1 + 1] + list(reversed(inner[i0:i1 + 1]))
        mb = MB()
        mb.prism_frame(poly, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), ys0, ys1, mat)
        solid(a, mb, (), pre=None, post=None, name=name, refine=refine)
    band(0, k0, metal, "roof_r")
    band(k1, n, metal, "roof_l")
    mb = MB()
    poly = [(x, z - 0.02) for (x, z) in outer[k0:k1 + 1]] + list(reversed(inner[k0:k1 + 1]))
    mb.prism_frame(poly, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), ys0, ys1, 'SKY_Glass')
    a.part(mb, name="skylight")
    det = Kit(a, tag="det_")
    # standing seams on the metal and glazing bars across the skylight
    for y in frange(ys0 + 0.9, ys1 - 0.9, 1.45):
        for (ia, ib) in ((0, k0), (k1, n)):
            path = [(arc_o(i, -0.012)[0], y, arc_o(i, -0.012)[1]) for i in range(ia, ib + 1)]
            det['none'].sweep(path, [(0.0, -0.028), (0.0, 0.028), (-0.075, 0.0)], metal, up=Vector((0, 1, 0)))
        path = [(arc_o(i, 0.0)[0], y, arc_o(i, 0.0)[1]) for i in range(k0, k1 + 1)]
        det['none'].sweep(path, [(-0.03, -0.03), (0.03, -0.03), (0.03, 0.03), (-0.03, 0.03)], brass, up=Vector((0, 1, 0)))
    # ribs (portal + intermediate + back), legs to the ground
    for (y, t_, name) in ((Y0 + 0.22, 0.6, "portal"), (-3.4, 0.3, "rib"), (1.2, 0.3, "rib"), (5.6, 0.3, "rib"),
                          (Y1 - 0.26, 0.3, "rib")):
        o2 = [arc_o(i, 0.25) for i in range(n + 1)]
        legs = [(o2[0][0], 0.0)] + o2 + [(o2[-1][0], 0.0), (inner[-1][0], 0.0)] + list(reversed(inner)) + \
               [(inner[0][0], 0.0)]
        mb = MB()
        mb.prism_frame(legs, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), y - t_ / 2, y + t_ / 2, pearl)
        solid(a, mb, (), pre=(0.04, 1), post=None, name=name, refine=None)
    gl = [((HW - 0.36) * math.cos(math.pi * i / n), zs + (ztop - zs - 0.38) * math.sin(math.pi * i / n))
          for i in range(n + 1)]
    gl2 = [((HW - 0.44) * math.cos(math.pi * i / n), zs + (ztop - zs - 0.46) * math.sin(math.pi * i / n))
           for i in range(n + 1)]
    det['none'].prism_frame(gl + list(reversed(gl2)), (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), Y0 + 0.5, Y0 + 0.58,
                            'SKY_TealGlow')
    # ---- front: head beam, glazed lunette, jamb infills, parked sliding leaves on tracks
    zh = 6.2
    sb = math.asin((zh - zs) / (ztop - zs - 0.3))
    xh = (HW - 0.3) * math.cos(sb)
    det['trim'].box(-xh - 0.1, xh + 0.1, Y0 + 0.05, Y0 + 0.55, zh, zh + 0.42, pearl)
    det['none'].box(-xh + 0.1, xh - 0.1, Y0 + 0.02, Y0 + 0.06, zh + 0.08, zh + 0.14, 'SKY_TealGlow')
    lun = [(x, z) for (x, z) in inner if z > zh + 0.42]
    sb2 = math.asin((zh + 0.42 - zs) / (ztop - zs - 0.3))
    x2 = (HW - 0.3) * math.cos(sb2)
    lun = [(x2, zh + 0.4)] + lun + [(-x2, zh + 0.4)]
    det['none'].prism_frame(lun, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), Y0 + 0.28, Y0 + 0.34, 'SKY_Glass')
    for xx in (-4.5, -1.5, 1.5, 4.5):
        top = zs + (ztop - zs - 0.3) * math.sqrt(max(0.0, 1 - (xx / (HW - 0.3)) ** 2))
        det['none'].box(xx - 0.05, xx + 0.05, Y0 + 0.25, Y0 + 0.37, zh + 0.4, top + 0.05, brass)
    det['none'].sweep([((HW - 0.3) * 0.62 * math.cos(math.radians(t)), Y0 + 0.31,
                        zh + 0.42 + (ztop - zh - 0.72) * 0.55 * math.sin(math.radians(t))) for t in range(10, 171, 20)],
                      circle(0.045, 4), brass)
    pts_r = [p for p in inner if p[1] <= zh - 1e-4 and p[0] > 0]
    for s in (-1, 1):
        jam = [(xh, 0.0), (HW - 0.3, 0.0)] + pts_r + [(xh, zh)]
        jam = [(s * x, z) for (x, z) in jam]
        det['mid'].prism_frame(jam, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), Y0 + 0.08, Y0 + 0.4, sand)
        # parked door leaves (two per side, on two tracks)
        for j, yy in enumerate((Y0 + 0.62, Y0 + 0.78)):
            xa = s * (xh - 0.05 - j * 0.15)
            xb = xa - s * 2.4
            x0_, x1_ = sorted((xa, xb))
            det['small'].box(x0_, x1_, yy - 0.06, yy + 0.06, 0.12, zh - 0.06, teal)
            for zz in (1.2, 2.4, 3.6):
                det['none'].box(x0_ + 0.08, x1_ - 0.08, yy - 0.085, yy + 0.085, zz, zz + 0.07, metal)
            det['none'].box((x0_ + x1_) / 2 - 0.04, (x0_ + x1_) / 2 + 0.04, yy - 0.085, yy + 0.085, 0.2, 3.6, metal)
            det['none'].box(x0_ + 0.15, x1_ - 0.15, yy - 0.075, yy + 0.075, 4.1, 5.1, 'SKY_Glass')
            for xx in (x0_ + 0.95, x1_ - 0.95):
                det['none'].box(xx - 0.03, xx + 0.03, yy - 0.085, yy + 0.085, 4.1, 5.1, teal)
        det['none'].box(min(s * 5.2, s * xh), max(s * 5.2, s * xh), Y0 + 0.52, Y0 + 0.88, 0.0, 0.06, metal)
    det['none'].box(-xh + 0.1, xh - 0.1, Y0 + 0.55, Y0 + 0.88, zh - 0.06, zh, metal)
    # ---- side walls, buttresses, bulkhead lamps
    mb = MB()
    mb.box(-HW - 0.1, -HW + 0.5, Y0, Yb, 0.0, zs + 0.1, sand)
    mb.box(HW - 0.5, HW + 0.1, Y0, Yb, 0.0, zs + 0.1, sand)
    solid(a, mb, (), pre=(0.04, 1), post=None, name="side_walls", refine=(2.5, 5.0, 1.0))
    for s in (-1, 1):
        for y in (-5.7, -1.1, 3.4):
            x0_, x1_ = sorted((s * (HW + 0.1), s * (HW + 0.45)))
            det['mid'].box(x0_, x1_, y - 0.32, y + 0.32, 0.0, zs + 0.55, pearl)
            det['mid'].box(x0_, x1_, y - 0.37, y + 0.37, 0.0, 0.3, sand)
            for sy in (-1, 1):
                fbox(det['small'], 'S' if sy > 0 else 'N', y + sy * 0.32, (x0_ + x1_) / 2 - 0.1,
                     (x0_ + x1_) / 2 + 0.1, 1.3, 1.48, -0.01, 0.05, brass)
                fbox(det['none'], 'S' if sy > 0 else 'N', y + sy * 0.32, (x0_ + x1_) / 2 - 0.07,
                     (x0_ + x1_) / 2 + 0.07, 1.33, 1.45, 0.04, 0.08, 'SKY_Light')
    # ---- back wall with door, oculus, vents
    back = [(HW - 0.3, 0.0)] + list(inner) + [(-(HW - 0.3), 0.0)]
    door_op = Op('S', 0.0, -0.1, 4.0, 3.7, 'flat', depth=0.3, back=teal, sill=False)
    mbc = MB()
    fprism(mbc, 'S', Yb, circle(1.1, 24, cx=0.0, cy=5.7), 0.6, -0.3, sand, front=sand, back='SKY_Glass')
    cuts = [op_cutter(door_op, Yb, sand), _tmp_obj(mbc, "cut")]
    mb = MB()
    mb.prism_frame(back, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), Yb - 0.37, Yb, sand)
    solid(a, mb, cuts, pre=(0.04, 1), post=(0.03, 1), name="back_wall", refine=(2.5, 2.0, 1.2))
    roller_shutter(det, 'S', Yb, 0.0, 0.07, 3.6, 3.96, d=-0.25)
    for t in range(0, 180, 30):
        c = (0.0, 4.6 + 1.1)
        p1 = (1.1 * math.cos(math.radians(t)), 4.6 + 1.1 + 1.1 * math.sin(math.radians(t)))
        p2 = (-p1[0], 2 * c[1] - p1[1])
        bar2d(det['none'], 'S', Yb, p1, p2, 0.05, -0.27, -0.2, brass)
    fdisc(det['none'], 'S', Yb, 0.0, 5.7, 1.3, -0.02, 0.06, pearl, seg=24, r_in=1.12)
    for xx in (-6.0, 6.0):
        louvre_vent(det, 'S', Yb, xx, 3.2, 1.4, 0.9)
    # ---- floor, threshold stripes, guide lines, interior kit
    mb = MB()
    mb.box(-HW + 0.5, HW - 0.5, Y0, Y1 - 0.4, 0.0, 0.1, 'SKY_Kerb')
    solid(a, mb, (), pre=None, post=None, name="floor", refine=(2.5, 5.0, 1.0))
    nstr = 18
    for i in range(nstr):
        x0_ = -xh + 2 * xh * i / nstr
        det['none'].box(x0_, x0_ + 2 * xh / nstr, Y0 + 0.95, Y0 + 1.25, 0.1, 0.115,
                        'SKY_Coral' if i % 2 == 0 else 'SKY_Ink')
    det['none'].box(-0.1, 0.1, Y0 + 1.4, Y1 - 1.2, 0.1, 0.112, 'SKY_RoadLine')
    for k in range(4):
        y = Y0 + 2.4 + k * 3.4
        det['none'].box(-1.6, 1.6, y - 0.08, y + 0.08, 0.1, 0.112, 'SKY_RoadLine')
    # office pod with mezzanine rail and stair in the back-left corner (the side annex)
    pops = [Op('N', -8.4, 0.12, 0.95, 2.2, 'flat', depth=0.3, back=teal, sill=False, door=True, frame=pearl,
               frame_t=0.08),
            Op('N', -6.9, 1.0, 1.6, 1.2, 'flat', depth=0.3, bars='mull', bar_mat=teal, sill='simple'),
            Op('W', 5.6, 1.0, 1.8, 1.2, 'flat', depth=0.3, bars='mull', bar_mat=teal, sill='simple')]
    mass(a, -10.45, -6.0, 4.0, Y1 - 0.4, 0.1, 3.0, pearl, pops, name="office", kit=det, pre=(0.04, 1),
         post=(0.03, 1), refine=None)
    det['mid'].box(-10.5, -5.95, 3.95, Y1 - 0.4, 3.0, 3.14, teal)
    rail_pts = [(-10.3, 4.1, 3.14), (-6.1, 4.1, 3.14), (-6.1, Y1 - 0.5, 3.14)]
    for p in rail_pts:
        det['none'].box(p[0] - 0.03, p[0] + 0.03, p[1] - 0.03, p[1] + 0.03, 3.14, 4.1, brass)
    for zz in (3.6, 4.05):
        det['none'].sweep([(x, y, zz) for (x, y, _) in rail_pts], circle(0.03, 4), brass)
    for k in range(9):
        z_ = 0.1 + 0.32 * (k + 1)
        y_ = 1.45 + 0.3 * k
        det['none'].box(-5.95, -5.15, y_ - 0.3, y_, 0.1, z_, metal)
    # tug, tool carts, workbench, hanging lamps
    det['small'].box(3.2, 4.8, -3.8, -2.6, 0.35, 1.0, 'SKY_Coral')
    det['small'].box(3.4, 4.0, -3.6, -2.8, 1.0, 1.45, 'SKY_Ink')
    for (wx, wy) in ((3.4, -3.85), (4.6, -3.85), (3.4, -2.55), (4.6, -2.55)):
        fs = det['none'].lathe([(0.0, -0.08), (0.28, -0.08), (0.3, 0.0), (0.28, 0.08), (0.0, 0.08)], 8, 'SKY_Rubber')
        det['none'].transform(M_tr(wx, wy, 0.4) @ M_rot(90.0, 'Y'), faces=fs)
    for (cx_, cy_) in ((8.6, 5.6), (7.4, 6.6)):
        det['none'].box(cx_ - 0.4, cx_ + 0.4, cy_ - 0.3, cy_ + 0.3, 0.3, 0.95, teal)
        det['none'].box(cx_ - 0.42, cx_ + 0.42, cy_ - 0.32, cy_ + 0.32, 0.95, 1.0, metal)
        for (dx, dy) in ((-0.3, -0.2), (0.3, -0.2), (-0.3, 0.2), (0.3, 0.2)):
            det['none'].box(cx_ + dx - 0.04, cx_ + dx + 0.04, cy_ + dy - 0.04, cy_ + dy + 0.04, 0.1, 0.3, 'SKY_Rubber')
    det['none'].box(9.6, 10.4, -6.0, -0.5, 0.1, 0.95, 'SKY_Wood')
    det['none'].box(10.35, 10.45, -6.0, -0.5, 0.95, 2.4, 'SKY_Ink')
    for y in (-3.4, 1.2, 5.6):
        for x in (-5.0, 0.0, 5.0):
            zt = zs + (ztop - zs - 0.3) * math.sqrt(max(0.0, 1 - (x / (HW - 0.3)) ** 2))
            pendant(det, x, y, zt - 0.02, drop=1.4)
    # windsock on a short mast at the portal crown (airfield cue, reads in the miniature)
    mx, my, mz = 0.0, Y0 + 0.22, ztop + 0.24
    det['none'].cyl(0.045, mz - 0.1, mz + 0.85, 6, brass, cx=mx, cy=my)
    det['none'].box(mx - 0.03, mx + 0.03, my - 0.03, my + 0.03, mz + 0.62, mz + 0.82, brass)
    fs = det['none'].lathe([(0.0, 0.0), (0.16, 0.0), (0.15, 0.25), (0.13, 0.5), (0.11, 0.75), (0.09, 1.0),
                            (0.07, 1.2), (0.0, 1.2)], 8, pearl,
                           mats=['SKY_Coral', 'SKY_Coral', pearl, 'SKY_Coral', pearl, 'SKY_Coral', 'SKY_Coral'])
    det['none'].transform(M_tr(mx + 0.05, my, mz + 0.72) @ M_rot(25.0, 'Z') @ M_rot(96.0, 'Y'), faces=fs)
    det.flush()
    a.notes.append("Footprint 22.9 x 16.1 m (spans more than one cell in X); pivot at its own ground centre.")
