"""SKYFOLD vehicle helpers (shuttle, ambient cars, aircraft) built on chars_common.

Original procedural work for SKYFOLD: The Last Flight (Awaiz Ahmed / Team Kanban).
"""
import math
import chars_common as C
from chars_common import Vector, Matrix, radians, sin, cos, pi, sqrt

PEARL, TEAL, CORAL, LIGHT, INK, RUBBER, BRASS, GLASS, GLOW, SAND, METAL = (
    'SKY_Pearl', 'SKY_Teal', 'SKY_Coral', 'SKY_Light', 'SKY_Ink', 'SKY_Rubber', 'SKY_Brass',
    'SKY_Glass', 'SKY_TealGlow', 'SKY_Sandstone', 'SKY_Metal')


def rounded_rect(w, h, r, n=3):
    pts = []
    for (cx, cy, a0) in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                         (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(n + 1):
            a = radians(a0 + 90 * k / n)
            pts.append((cx + r * cos(a), cy + r * sin(a)))
    return pts


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
            # outward normal of the superellipse |x/a|^n + |y/b|^n = 1
            nx = (abs(x / a) ** (self.n - 1)) * math.copysign(1, x) / a if a else 0
            ny = (abs(y / b) ** (self.n - 1)) * math.copysign(1, y) / b if b else 0
            nn = Vector((nx, ny, 0.0))
            if nn.length > 1e-9:
                p += nn.normalized() * off
        return p

    def t_of_y(self, y, z, side):
        """Angle on the +X (side=1) or -X (side=-1) flank for a given y."""
        y0, y1, a = self.section(z)
        cy, b = (y0 + y1) / 2, (y1 - y0) / 2
        u = max(-1.0, min(1.0, (y - cy) / b))
        s = math.copysign(abs(u) ** (self.n / 2), u)
        t = math.asin(max(-1.0, min(1.0, s)))
        return t if side > 0 else pi - t

    def t_of_x(self, x, z, face):
        """Angle on the front (face=-1) or back (face=1) face for a given x."""
        y0, y1, a = self.section(z)
        u = max(-1.0, min(1.0, (x - self.x0) / a))
        c = math.copysign(abs(u) ** (self.n / 2), u)
        t = math.acos(max(-1.0, min(1.0, c)))
        return -t if face < 0 else t

    def panel_side(self, part, side, ya, yb, za, zb, mat, off=0.008, nt=6, nz=3):
        """Conformal single-sided panel (outward normals) on a flank, y = ya..yb, z = za..zb."""
        rows = []
        for j in range(nz + 1):
            z = za + (zb - za) * j / nz
            row = [self.point(self.t_of_y(ya + (yb - ya) * i / nt, z, side), z, off)
                   for i in range(nt + 1)]
            rows.append(row if side > 0 else row[::-1])
        return self._sheet(part, rows, mat)

    def panel_end(self, part, face, xa, xb, za, zb, mat, off=0.008, nt=6, nz=3):
        rows = []
        for j in range(nz + 1):
            z = za + (zb - za) * j / nz
            row = [self.point(self.t_of_x(xa + (xb - xa) * i / nt, z, face), z, off)
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
