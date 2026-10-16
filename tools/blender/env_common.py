"""SKYFOLD environment kit - shared helpers for headless Blender 5.2.

Everything here is procedural: palette materials, a small bmesh builder,
2D outline helpers, bevel/boolean part pipeline, a 2.5D tile surface
builder (constrained Delaunay), soft ray-cast AO into the corner colour
attribute "Col", box UVs, empties, FBX export (exact ART_SPEC settings)
and preview rendering.

Axes (ART_SPEC): Unity north (+Z) = Blender -Y, Unity east (+X) = Blender -X.
Side names used in this kit follow UNITY directions:
    'N' -> Blender -Y face, 'S' -> +Y, 'E' -> -X, 'W' -> +X.
"""
import bpy, bmesh, math, os, sys, json, random, time
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree
from mathutils.geometry import delaunay_2d_cdt

ROOT = r"C:\UnityProjects\SKYFOLD"
MODEL_DIR = os.path.join(ROOT, "Assets", "Skyfold", "Art", "Models")
RENDER_DIR = os.path.join(ROOT, "source-art", "renders")

PALETTE = {
    "SKY_Pearl": "F4EFE6", "SKY_Ivory": "EFE6D2", "SKY_Sandstone": "D9B98C",
    "SKY_SandstoneDeep": "C49A6C", "SKY_Terracotta": "C8754F", "SKY_Teal": "0F6F73",
    "SKY_TealLight": "3FA7A3", "SKY_TealGlow": "35E0D0", "SKY_Coral": "F2714B",
    "SKY_Gold": "D9A441", "SKY_Brass": "B8893B", "SKY_Ink": "22333B",
    "SKY_Glass": "6FB7C4", "SKY_Road": "3E4A52", "SKY_RoadLine": "F4EFE6",
    "SKY_Kerb": "CDBFA9", "SKY_Wood": "9A6B45", "SKY_PalmTrunk": "8B6B4A",
    "SKY_PalmLeaf": "5E8C4A", "SKY_Flower": "E0557A", "SKY_Fabric": "F7F1E6",
    "SKY_Metal": "AEB6BA", "SKY_Rubber": "2B2F33", "SKY_Light": "FFD9A0",
}
# preview-only surface response: (roughness, metallic, emission strength)
SURF = {
    "SKY_Brass": (0.32, 0.9, 0.0), "SKY_Metal": (0.38, 0.85, 0.0), "SKY_Gold": (0.28, 0.95, 0.0),
    "SKY_Glass": (0.05, 0.0, 0.0), "SKY_TealGlow": (0.35, 0.0, 5.0), "SKY_Light": (0.4, 0.0, 5.0),
    "SKY_Road": (0.85, 0.0, 0.0), "SKY_Rubber": (0.8, 0.0, 0.0), "SKY_Teal": (0.35, 0.05, 0.0),
    "SKY_TealLight": (0.18, 0.05, 0.0), "SKY_Ink": (0.45, 0.05, 0.0), "SKY_Fabric": (0.75, 0.0, 0.0),
    "SKY_PalmLeaf": (0.6, 0.0, 0.0), "SKY_Wood": (0.62, 0.0, 0.0), "SKY_Coral": (0.5, 0.0, 0.0),
}

N, S, E, W = 'N', 'S', 'E', 'W'


def srgb2lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_lin(h):
    return tuple(srgb2lin(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


# --------------------------------------------------------------------------- scene

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0
    return sc


def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def get_mat(name):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    col = hex_lin(PALETTE[name])
    rough, metal, emis = SURF.get(name, (0.62, 0.0, 0.0))
    m.diffuse_color = (*col, 1.0)
    m.roughness = rough
    m.metallic = metal
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*col, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emis > 0:
        bsdf.inputs["Emission Color"].default_value = (*col, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emis
    if name == "SKY_Glass":
        bsdf.inputs["Coat Weight"].default_value = 0.4
    # preview only: multiply albedo by the AO colour attribute (stored as sRGB, used raw by Unity)
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "Col"
    attr.attribute_type = 'GEOMETRY'
    gam = nt.nodes.new("ShaderNodeGamma")
    gam.inputs[1].default_value = 1.0 / 2.2
    vm = nt.nodes.new("ShaderNodeVectorMath")
    vm.operation = 'MULTIPLY'
    vm.inputs[0].default_value = col
    nt.links.new(attr.outputs["Color"], gam.inputs[0])
    nt.links.new(gam.outputs[0], vm.inputs[1])
    nt.links.new(vm.outputs[0], bsdf.inputs["Base Color"])
    return m


# --------------------------------------------------------------------------- 2D helpers

def arc(cx, cy, r, a0, a1, seg, include_end=True):
    """Points on a circular arc, angles in degrees (a0 -> a1)."""
    pts = []
    n = max(1, seg)
    rng = range(n + 1) if include_end else range(n)
    for i in rng:
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def rrect(w, d, r, seg=4, cx=0.0, cy=0.0):
    """Rounded rectangle outline (CCW), w along X, d along Y."""
    r = min(r, w / 2 - 1e-4, d / 2 - 1e-4)
    hx, hy = w / 2 - r, d / 2 - r
    pts = []
    if r <= 1e-4:
        return [(cx - w / 2, cy - d / 2), (cx + w / 2, cy - d / 2), (cx + w / 2, cy + d / 2), (cx - w / 2, cy + d / 2)]
    for (ox, oy, a0) in ((hx, -hy, -90), (hx, hy, 0), (-hx, hy, 90), (-hx, -hy, 180)):
        pts += arc(cx + ox, cy + oy, r, a0, a0 + 90, seg)
    return pts


def circle(r, seg, cx=0.0, cy=0.0, a0=0.0):
    return [(cx + r * math.cos(math.radians(a0) + 2 * math.pi * i / seg),
             cy + r * math.sin(math.radians(a0) + 2 * math.pi * i / seg)) for i in range(seg)]


def arch_pts(w, h, kind='round', seg=8, base=0.0):
    """Opening outline in (u, v): width w centred on u=0, from v=base to apex base+h."""
    hw = w / 2.0
    if kind == 'flat':
        return [(-hw, base), (hw, base), (hw, base + h), (-hw, base + h)]
    if kind == 'round' and h < hw + 0.05:
        kind = 'segment'
    if kind == 'round':
        sp = base + h - hw
        pts = [(-hw, base), (hw, base)]
        pts += arc(0, sp, hw, 0, 180, seg)
        return pts
    if kind == 'pointed':
        # two arcs of radius ~0.85w centred inside -> gentle pointed arch
        rr = w * 0.8
        sp = base + h - math.sqrt(rr * rr - (rr - hw) ** 2)
        pts = [(-hw, base), (hw, base)]
        cxr = hw - rr  # centre of right arc (left of the right jamb)
        a_top = math.degrees(math.acos((0 - cxr) / rr))
        pts += arc(cxr, sp, rr, 0, a_top, max(2, seg // 2))
        cxl = -hw + rr
        a_top_l = math.degrees(math.acos((0 - cxl) / rr))
        pl = arc(cxl, sp, rr, a_top_l, 180, max(2, seg // 2))
        pts += pl[1:]
        return pts
    if kind == 'segment':
        rise = min(h * 0.25, hw * 0.5)
        sp = base + h - rise
        rr = (hw * hw + rise * rise) / (2 * rise)
        cyc = base + h - rr
        a0 = math.degrees(math.atan2(sp - cyc, hw))
        pts = [(-hw, base), (hw, base)]
        pts += arc(0, cyc, rr, a0, 180 - a0, seg)
        return pts
    return [(-hw, base), (hw, base), (hw, base + h), (-hw, base + h)]


def poly_area(pts):
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i][0], pts[i][1]
        x1, y1 = pts[(i + 1) % len(pts)][0], pts[(i + 1) % len(pts)][1]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def ccw(pts):
    return pts if poly_area(pts) > 0 else list(reversed(pts))


def offset_line(pts, d, closed=False):
    """Offset a 2D polyline to its LEFT by d (miter, clamped)."""
    out = []
    n = len(pts)
    for i in range(n):
        p = Vector(pts[i])
        if closed:
            a = Vector(pts[i - 1]); b = Vector(pts[(i + 1) % n])
        else:
            a = Vector(pts[i - 1]) if i > 0 else None
            b = Vector(pts[i + 1]) if i < n - 1 else None
        ns = []
        if a is not None:
            t = (p - a).normalized(); ns.append(Vector((-t.y, t.x)))
        if b is not None:
            t = (b - p).normalized(); ns.append(Vector((-t.y, t.x)))
        nn = ns[0] if len(ns) == 1 else (ns[0] + ns[1])
        if nn.length < 1e-8:
            nn = ns[0]
        nn.normalize()
        c = nn.dot(ns[0])
        k = d / max(c, 0.3)
        q = p + nn * k
        out.append((q.x, q.y))
    return out


def lerp(a, b, t):
    return a + (b - a) * t


# --------------------------------------------------------------------------- mesh builder

class MB:
    """Thin bmesh wrapper that tracks material names per face."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def v(self, co):
        return self.bm.verts.new(co)

    def f(self, vs, mat):
        fc = self.bm.faces.new(vs)
        fc.material_index = self.mi(mat)
        fc.smooth = True
        return fc

    def _recalc(self, faces):
        bmesh.ops.recalc_face_normals(self.bm, faces=faces)

    # --- solids -----------------------------------------------------------
    def box(self, x0, x1, y0, y1, z0, z1, mat, fm=None):
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        z0, z1 = min(z0, z1), max(z0, z1)
        fm = fm or {}
        c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        q = [self.v(p) for p in c]
        spec = [((0, 3, 2, 1), 'bottom'), ((4, 5, 6, 7), 'top'), ((0, 1, 5, 4), 'N'),
                ((2, 3, 7, 6), 'S'), ((3, 0, 4, 7), 'E'), ((1, 2, 6, 5), 'W')]
        fs = []
        for idx, key in spec:
            m = fm.get(key, fm.get('sides', mat) if key in 'NSEW' else mat)
            fs.append(self.f([q[i] for i in idx], m))
        return fs

    def cbox(self, cx, cy, cz, sx, sy, sz, mat, fm=None):
        return self.box(cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, cz - sz / 2, cz + sz / 2, mat, fm)

    def prism(self, pts, z0, z1, mat, top=None, bottom=None, sides=None):
        """Extrude a 2D polygon (any winding) along Z."""
        pts = ccw(list(pts))
        n = len(pts)
        lo = [self.v((p[0], p[1], z0)) for p in pts]
        hi = [self.v((p[0], p[1], z1)) for p in pts]
        fs = [self.f(list(reversed(lo)), bottom or mat), self.f(hi, top or mat)]
        for i in range(n):
            j = (i + 1) % n
            fs.append(self.f([lo[i], lo[j], hi[j], hi[i]], sides or mat))
        return fs

    def prism_frame(self, pts, origin, u, v, w, w0, w1, mat, front=None, back=None):
        """Extrude polygon given in (u,v) coords of a frame along w from w0 to w1.
        front = cap at w0, back = cap at w1."""
        o = Vector(origin); u = Vector(u); v = Vector(v); w = Vector(w)
        n = len(pts)
        a = [self.v(o + u * p[0] + v * p[1] + w * w0) for p in pts]
        b = [self.v(o + u * p[0] + v * p[1] + w * w1) for p in pts]
        fs = [self.f(list(a), front or mat), self.f(list(reversed(b)), back or mat)]
        for i in range(n):
            j = (i + 1) % n
            fs.append(self.f([a[j], a[i], b[i], b[j]], mat))
        self._recalc(fs)
        return fs

    def lathe(self, prof, seg, mat, mats=None, cx=0.0, cy=0.0, a0=0.0, z_off=0.0, smooth=True):
        """Surface of revolution. prof = [(r, z), ...] bottom -> top (CCW in r-z plane).
        r == 0 at an end collapses to a pole. mats: per-segment material list."""
        rings = []
        for (r, z) in prof:
            if r <= 1e-6:
                rings.append([self.v((cx, cy, z + z_off))])
            else:
                rings.append([self.v((cx + r * math.cos(math.radians(a0) + 2 * math.pi * k / seg),
                                      cy + r * math.sin(math.radians(a0) + 2 * math.pi * k / seg), z + z_off))
                              for k in range(seg)])
        fs = []
        for i in range(len(rings) - 1):
            A, B = rings[i], rings[i + 1]
            m = mats[i] if mats else mat
            if len(A) == 1 and len(B) == 1:
                continue
            for k in range(seg):
                k2 = (k + 1) % seg
                if len(A) == 1:
                    fs.append(self.f([A[0], B[k], B[k2]], m))
                elif len(B) == 1:
                    fs.append(self.f([A[k], A[k2], B[0]], m))
                else:
                    fs.append(self.f([A[k], A[k2], B[k2], B[k]], m))
        # caps for open ends
        if len(rings[0]) > 1:
            fs.append(self.f(list(reversed(rings[0])), mats[0] if mats else mat))
        if len(rings[-1]) > 1:
            fs.append(self.f(list(rings[-1]), mats[-1] if mats else mat))
        self._recalc(fs)
        return fs

    def cyl(self, r, z0, z1, seg, mat, cx=0.0, cy=0.0, r_top=None):
        rt = r if r_top is None else r_top
        return self.lathe([(0, z0), (r, z0), (rt, z1), (0, z1)], seg, mat, cx=cx, cy=cy)

    def loft(self, rings, mat, mats=None, closed=True, cap0=True, cap1=True, recalc=True):
        """rings: list of lists of 3D points with equal counts."""
        R = [[self.v(p) for p in ring] for ring in rings]
        n = len(R[0])
        fs = []
        for i in range(len(R) - 1):
            m = mats[i] if mats else mat
            rng = range(n) if closed else range(n - 1)
            for k in rng:
                k2 = (k + 1) % n
                fs.append(self.f([R[i][k], R[i][k2], R[i + 1][k2], R[i + 1][k]], m))
        if closed and cap0:
            fs.append(self.f(list(reversed(R[0])), mats[0] if mats else mat))
        if closed and cap1:
            fs.append(self.f(list(R[-1]), mats[-1] if mats else mat))
        if recalc:
            self._recalc(fs)
        return fs

    def sweep(self, path, profile, mat, scales=None, closed_profile=True, cap=True, up=Vector((0, 0, 1)),
              mats=None, twist=None):
        """Sweep a 2D profile along a 3D path (parallel transport frame)."""
        path = [Vector(p) for p in path]
        n = len(path)
        tangents = []
        for i in range(n):
            if i == 0:
                t = path[1] - path[0]
            elif i == n - 1:
                t = path[-1] - path[-2]
            else:
                t = (path[i + 1] - path[i - 1])
            tangents.append(t.normalized())
        # initial normal
        ref = Vector(up)
        if abs(ref.dot(tangents[0])) > 0.95:
            ref = Vector((1, 0, 0))
        nrm = (ref - tangents[0] * ref.dot(tangents[0])).normalized()
        rings = []
        for i in range(n):
            if i > 0:
                # parallel transport
                t0, t1 = tangents[i - 1], tangents[i]
                ax = t0.cross(t1)
                if ax.length > 1e-8:
                    ang = t0.angle(t1)
                    nrm = Matrix.Rotation(ang, 3, ax.normalized()) @ nrm
                nrm = (nrm - t1 * nrm.dot(t1)).normalized()
            t = tangents[i]
            bn = t.cross(nrm)
            s = scales[i] if scales else 1.0
            sx, sy = (s if isinstance(s, (tuple, list)) else (s, s))
            tw = math.radians(twist[i]) if twist else 0.0
            ct, st = math.cos(tw), math.sin(tw)
            ring = []
            for (px, py) in profile:
                x = (px * ct - py * st) * sx
                y = (px * st + py * ct) * sy
                ring.append(path[i] + bn * x + nrm * y)
            rings.append(ring)
        return self.loft(rings, mat, mats=mats, closed=closed_profile, cap0=cap, cap1=cap,
                         recalc=closed_profile and cap)

    def sphere(self, r, seg, rings_n, mat, c=(0, 0, 0), sz=1.0):
        prof = [(0, -r * sz)]
        for i in range(1, rings_n):
            a = -math.pi / 2 + math.pi * i / rings_n
            prof.append((r * math.cos(a), r * math.sin(a) * sz))
        prof.append((0, r * sz))
        return self.lathe(prof, seg, mat, cx=c[0], cy=c[1], z_off=c[2])

    def quad(self, a, b, c, d, mat):
        return self.f([self.v(a), self.v(b), self.v(c), self.v(d)], mat)

    def transform(self, M, faces=None):
        if faces is None:
            verts = self.bm.verts[:]
        else:
            vs = set()
            for fc in faces:
                vs.update(fc.verts)
            verts = list(vs)
        bmesh.ops.transform(self.bm, matrix=M, verts=verts)

    def to_object(self, name):
        me = bpy.data.meshes.new(name)
        self.bm.normal_update()
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(get_mat(m))
        ob = bpy.data.objects.new(name, me)
        link(ob)
        return ob


def M_rot(deg, axis='Z'):
    return Matrix.Rotation(math.radians(deg), 4, axis)


def M_tr(x, y, z):
    return Matrix.Translation((x, y, z))


# --------------------------------------------------------------------------- parts

class Asset:
    """Collects parts per target object and empties for one exported FBX."""

    def __init__(self, name, category):
        self.name = name
        self.category = category
        self.targets = {}      # target name -> list of part objects
        self.pivots = {}       # target name -> pivot location (hinge parts)
        self.smooth = {}       # target name -> smooth angle
        self.weighted = {}     # target name -> bool
        self.empties = []      # (name, loc, rot_z)
        self.cutters = []
        self.notes = []
        self.final = []

    def part(self, mb, target=None, bevel=0.0, seg=2, angle=30.0, cutters=(), weight_limit=False,
             profile=0.5, name="part"):
        target = target or self.name
        ob = mb.to_object(f"{target}__{name}")
        for c in cutters:
            md = ob.modifiers.new("cut", 'BOOLEAN')
            md.operation = 'DIFFERENCE'
            md.solver = 'EXACT'
            md.object = c
            md.material_mode = 'TRANSFER'
        if bevel > 0:
            md = ob.modifiers.new("bevel", 'BEVEL')
            md.width = bevel
            md.segments = seg
            md.limit_method = 'WEIGHT' if weight_limit else 'ANGLE'
            md.angle_limit = math.radians(angle)
            md.use_clamp_overlap = True
            md.profile = profile
            md.harden_normals = False
        self.targets.setdefault(target, []).append(ob)
        return ob

    def cutter(self, mb, name="cutter"):
        ob = mb.to_object(f"{self.name}__{name}")
        ob.hide_render = True
        ob.display_type = 'WIRE'
        self.cutters.append(ob)
        return ob

    def empty(self, name, loc, rot_z=0.0):
        self.empties.append((name, tuple(loc), rot_z))

    def set_target(self, target, pivot=None, smooth=None, weighted=None):
        if pivot is not None:
            self.pivots[target] = Vector(pivot)
        if smooth is not None:
            self.smooth[target] = smooth
        if weighted is not None:
            self.weighted[target] = weighted


def _bake_object(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    return me


def _merge_meshes(name, meshes):
    bm = bmesh.new()
    mats = []
    for me in meshes:
        n0 = len(bm.faces)
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        remap = []
        for m in me.materials:
            nm = m.name if m else "SKY_Pearl"
            if nm not in mats:
                mats.append(nm)
            remap.append(mats.index(nm))
        for fi in range(n0, len(bm.faces)):
            fc = bm.faces[fi]
            if remap:
                fc.material_index = remap[min(fc.material_index, len(remap) - 1)]
    out = bpy.data.meshes.new(name)
    bm.to_mesh(out)
    bm.free()
    for m in mats:
        out.materials.append(get_mat(m))
    return out


def assemble(asset, ao=True, ao_kw=None):
    """Apply part modifiers, merge per target, normals, triangulate, AO, UVs."""
    finals = []
    for target, parts in asset.targets.items():
        dg = bpy.context.evaluated_depsgraph_get()
        meshes = [_bake_object(p) for p in parts]
        if os.environ.get("SKY_PART_STATS"):
            stats = {}
            for p, m in zip(parts, meshes):
                key = p.name.split("__")[-1]
                stats[key] = stats.get(key, 0) + sum(len(pg.vertices) - 2 for pg in m.polygons)
            print("  parts:", ", ".join(f"{k}={v}" for k, v in sorted(stats.items(), key=lambda kv: -kv[1])))
        me = _merge_meshes(target, meshes)
        for p in parts:
            bpy.data.objects.remove(p, do_unlink=True)
        for m in meshes:
            bpy.data.meshes.remove(m)
        ob = bpy.data.objects.new(target, me)
        link(ob)
        # smooth + sharp by angle
        n = len(me.polygons)
        me.polygons.foreach_set("use_smooth", [True] * n)
        me.set_sharp_from_angle(angle=math.radians(asset.smooth.get(target, 48.0)))
        if asset.weighted.get(target, True):
            wn = ob.modifiers.new("wn", 'WEIGHTED_NORMAL')
            wn.mode = 'FACE_AREA'
            wn.weight = 50
            wn.keep_sharp = True
        tri = ob.modifiers.new("tri", 'TRIANGULATE')
        tri.min_vertices = 5
        tri.quad_method = 'BEAUTY'
        tri.ngon_method = 'BEAUTY'
        try:
            tri.keep_custom_normals = True
        except Exception:
            pass
        me2 = _bake_object(ob)
        ob.modifiers.clear()
        old = ob.data
        ob.data = me2
        me2.name = target
        bpy.data.meshes.remove(old)
        # pivot for hinge parts: move origin, keep world geometry
        if target in asset.pivots:
            pv = asset.pivots[target]
            ob.data.transform(Matrix.Translation(-pv))
            ob.location = pv
        finals.append(ob)
    for c in asset.cutters:
        bpy.data.objects.remove(c, do_unlink=True)
    asset.cutters = []
    bpy.context.view_layer.update()
    if ao:
        bake_ao(finals, **(ao_kw or {}))
    for ob in finals:
        box_uv(ob)
    # empties
    for (nm, loc, rz) in asset.empties:
        e = bpy.data.objects.new(nm, None)
        e.empty_display_type = 'ARROWS'
        e.empty_display_size = 0.4
        e.location = loc
        e.rotation_euler = (0, 0, math.radians(rz))
        link(e)
        finals.append(e)
    asset.final = finals
    return finals


# --------------------------------------------------------------------------- AO

def _hemi_dirs(k):
    dirs = []
    golden = math.pi * (3 - math.sqrt(5))
    for i in range(k):
        u = (i + 0.5) / k
        r = math.sqrt(u)
        phi = i * golden
        dirs.append((r * math.cos(phi), r * math.sin(phi), math.sqrt(max(0.0, 1 - u))))
    return dirs


def bake_ao(objs, ground_z=0.0, dist=1.6, rays=32, strength=0.8, floor=0.42, inset=0.22,
            power=1.0, extra=(), smooth_deg=50.0, ground_size=300.0):
    """Soft ray-cast AO per face corner -> BYTE_COLOR corner attribute 'Col' (sRGB, white = open)."""
    t0 = time.time()
    meshes = [o for o in objs if o.type == 'MESH']
    co, polys = [], []
    for o in list(meshes) + list(extra):
        mw = o.matrix_world
        base = len(co)
        co.extend([mw @ v.co for v in o.data.vertices])
        polys.extend([[base + i for i in p.vertices] for p in o.data.polygons])
    if ground_z is not None:
        g = ground_z - 0.004
        b = len(co)
        s = ground_size
        co.extend([Vector((-s, -s, g)), Vector((s, -s, g)), Vector((s, s, g)), Vector((-s, s, g))])
        polys.append([b, b + 1, b + 2, b + 3])
    bvh = BVHTree.FromPolygons(co, polys, epsilon=0.0)
    dirs = _hemi_dirs(rays)
    cos_s = math.cos(math.radians(smooth_deg))
    total_rays = 0
    for o in meshes:
        me = o.data
        mw = o.matrix_world
        rot = mw.to_3x3().normalized()
        vco = [mw @ v.co for v in me.vertices]
        lv = [0] * len(me.loops)
        me.loops.foreach_get("vertex_index", lv)
        vals = [1.0] * len(me.loops)
        lnorm = [None] * len(me.loops)
        for p in me.polygons:
            nrm = (rot @ p.normal).normalized()
            c = mw @ p.center
            t = nrm.orthogonal().normalized()
            bt = nrm.cross(t)
            for li in p.loop_indices:
                lnorm[li] = nrm
                v = vco[lv[li]]
                d = c - v
                L = d.length
                p0 = v + d * (min(inset, 0.45 * L) / L) if L > 1e-6 else v.copy()
                p0 = p0 + nrm * 0.004
                ang = (li * 2.399963) % 6.283185
                ca, sa = math.cos(ang), math.sin(ang)
                tr = t * ca + bt * sa
                br = nrm.cross(tr)
                occ = 0.0
                for (x, y, z) in dirs:
                    hit = bvh.ray_cast(p0, tr * x + br * y + nrm * z, dist)
                    if hit[0] is not None:
                        occ += 1.0 - hit[3] / dist
                total_rays += len(dirs)
                vals[li] = 1.0 - occ / len(dirs)
        # smooth across corners of the same vertex with similar normals
        groups = {}
        for li, vi in enumerate(lv):
            groups.setdefault(vi, []).append(li)
        out = [1.0] * len(vals)
        for vi, lis in groups.items():
            for li in lis:
                acc = 0.0; cnt = 0
                ni = lnorm[li]
                for lj in lis:
                    if ni is None or lnorm[lj] is None or ni.dot(lnorm[lj]) >= cos_s:
                        acc += vals[lj]; cnt += 1
                a = acc / max(cnt, 1)
                a = 1.0 - strength * ((1.0 - a) ** power)
                out[li] = max(floor, min(1.0, a))
        for name in [a.name for a in me.color_attributes]:
            me.color_attributes.remove(me.color_attributes[name])
        ca_ = me.color_attributes.new("Col", 'BYTE_COLOR', 'CORNER')
        flat = []
        for a in out:
            flat.extend((a, a, a, 1.0))
        ca_.data.foreach_set("color_srgb", flat)
        me.color_attributes.active_color = ca_
        me.color_attributes.render_color_index = 0
    print(f"  AO: {total_rays} rays in {time.time() - t0:.1f}s")


def box_uv(ob, scale=1.0):
    me = ob.data
    if me.uv_layers:
        return
    uv = me.uv_layers.new(name="UVMap")
    lv = [0] * len(me.loops)
    me.loops.foreach_get("vertex_index", lv)
    data = [0.0] * (2 * len(me.loops))
    for p in me.polygons:
        nx, ny, nz = abs(p.normal.x), abs(p.normal.y), abs(p.normal.z)
        for li in p.loop_indices:
            c = me.vertices[lv[li]].co
            if nz >= nx and nz >= ny:
                u, v = c.x, c.y
            elif nx >= ny:
                u, v = c.y, c.z
            else:
                u, v = c.x, c.z
            data[2 * li] = u * scale
            data[2 * li + 1] = v * scale
    uv.data.foreach_set("uv", data)


# --------------------------------------------------------------------------- 2.5D tile surface

def tile_surface(asset, regions, base_z=-0.3, target=None, side_mat="SKY_SandstoneDeep",
                 kerb_bevel=0.04, kerb_seg=1, half=8.0, name="surface", skirt=True, extra_pts=(),
                 bounds=None):
    """Build a watertight ground tile from 2D regions using constrained Delaunay.

    regions: list of dicts {pts, z, mat, prio, (kerb: bool)} - highest prio wins where they overlap.
    The first region should cover the full cell square. Vertical faces are created where
    neighbouring triangles have different heights (kerb faces) and a skirt down to base_z
    along the cell boundary. Top edges of height steps get bevel weight (kerb chamfer)."""
    verts2 = []
    vmap = {}

    def vid(p):
        key = (round(p[0], 5), round(p[1], 5))
        if key not in vmap:
            vmap[key] = len(verts2)
            verts2.append(Vector(key))
        return vmap[key]

    faces_in = []
    for r in regions:
        pts = r['pts']
        idx = []
        for p in pts:
            i = vid(p)
            if not idx or idx[-1] != i:
                idx.append(i)
        if idx[0] == idx[-1]:
            idx.pop()
        faces_in.append(idx)
    for p in extra_pts:
        vid(p)
    out = delaunay_2d_cdt(verts2, [], faces_in, 0, 1e-5)
    ov, oe, of, ov_orig, oe_orig, of_orig = out
    # NOTE: faces_orig is unreliable for overlapping input polygons, so region membership is
    # resolved with a point-in-polygon test on each triangle centroid (triangles never cross
    # constraint edges, so the centroid is representative).
    order = sorted(range(len(regions)), key=lambda k: -regions[k]['prio'])
    bbs = []
    for r in regions:
        xs = [p[0] for p in r['pts']]; ys = [p[1] for p in r['pts']]
        bbs.append((min(xs) - 1e-6, max(xs) + 1e-6, min(ys) - 1e-6, max(ys) + 1e-6))

    def pip(x, y, poly):
        inside = False
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i][0], poly[i][1]
            x2, y2 = poly[(i + 1) % n][0], poly[(i + 1) % n][1]
            if (y1 > y) != (y2 > y):
                if x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                    inside = not inside
        return inside
    tris = []
    for fi, f in enumerate(of):
        cx = sum(ov[i].x for i in f) / len(f)
        cy = sum(ov[i].y for i in f) / len(f)
        reg = None
        for k in order:
            b = bbs[k]
            if b[0] <= cx <= b[1] and b[2] <= cy <= b[3] and pip(cx, cy, regions[k]['pts']):
                reg = regions[k]
                break
        if reg is None:
            continue
        # ensure CCW
        pts = [ov[i] for i in f]
        if poly_area([(p.x, p.y) for p in pts]) < 0:
            f = list(reversed(f))
        tris.append((list(f), reg))
    mb = MB()
    bm = mb.bm
    bw = bm.edges.layers.float.new('bevel_weight_edge')
    vcache = {}

    def bv(i, z):
        k = (i, round(z, 5))
        if k not in vcache:
            vcache[k] = mb.v((ov[i].x, ov[i].y, z))
        return vcache[k]

    edge_tris = {}
    for (f, reg) in tris:
        mb.f([bv(i, reg['z']) for i in f], reg['mat'])
        for k in range(len(f)):
            a, b = f[k], f[(k + 1) % len(f)]
            edge_tris.setdefault((min(a, b), max(a, b)), []).append((a, b, reg))
    boundary = []
    for key, lst in edge_tris.items():
        if len(lst) == 2:
            (a1, b1, r1), (a2, b2, r2) = lst
            if abs(r1['z'] - r2['z']) > 1e-6:
                hi, lo = ((a1, b1, r1), r2) if r1['z'] > r2['z'] else ((a2, b2, r2), r1)
                a, b, rh = hi
                A_hi, B_hi = bv(a, rh['z']), bv(b, rh['z'])
                A_lo, B_lo = bv(a, lo['z']), bv(b, lo['z'])
                mb.f([A_hi, A_lo, B_lo, B_hi], rh.get('side', rh['mat']))
        elif len(lst) == 1 and skirt:
            a, b, r = lst[0]
            boundary.append((a, b, r))
    # skirt
    if skirt and boundary:
        for (a, b, r) in boundary:
            A_hi, B_hi = bv(a, r['z']), bv(b, r['z'])
            A_lo, B_lo = bv(a, base_z), bv(b, base_z)
            mb.f([A_hi, A_lo, B_lo, B_hi], side_mat)
        # bottom: a single quad over the bounds (never visible; avoids a large n-gon fan)
        bx0, bx1, by0, by1 = bounds if bounds else (-half, half, -half, half)
        q = [mb.v((bx0, by0, base_z)), mb.v((bx0, by1, base_z)), mb.v((bx1, by1, base_z)), mb.v((bx1, by0, base_z))]
        mb.f(q, side_mat)
    bm.edges.ensure_lookup_table()
    # bevel weights on kerb top edges (step edges, upper side) but never on cell boundary
    if kerb_bevel > 0:
        bx0, bx1, by0, by1 = bounds if bounds else (-half, half, -half, half)
        eps = 1e-4
        bm.normal_update()

        def on_b(c):
            return (abs(c.x - bx0) < eps, abs(c.x - bx1) < eps, abs(c.y - by0) < eps, abs(c.y - by1) < eps)
        for e in bm.edges:
            if len(e.link_faces) != 2:
                continue
            f1, f2 = e.link_faces
            ang = f1.normal.angle(f2.normal, 0)
            if ang < math.radians(60):
                continue
            z = e.verts[0].co.z
            if abs(e.verts[1].co.z - z) > 1e-5 or z <= base_z + 1e-4:
                continue
            ba, bb = on_b(e.verts[0].co), on_b(e.verts[1].co)
            if any(ba[k] and bb[k] for k in range(4)):
                continue
            # only top edges of steps (convex)
            c1 = f1.calc_center_median(); c2 = f2.calc_center_median()
            if (c1.z <= z + 1e-5 and c2.z <= z + 1e-5):
                e[bw] = 1.0
    return asset.part(mb, target=target, bevel=kerb_bevel, seg=kerb_seg, weight_limit=True, name=name)


# --------------------------------------------------------------------------- export

FBX_KW = dict(use_selection=True, object_types={'EMPTY', 'MESH'}, apply_unit_scale=True,
              apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z', axis_up='Y',
              bake_space_transform=True, use_mesh_modifiers=True, mesh_smooth_type='FACE',
              add_leaf_bones=False, use_armature_deform_only=True, colors_type='SRGB',
              path_mode='AUTO', embed_textures=False)


def export_fbx(asset):
    folder = os.path.join(MODEL_DIR, asset.category)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, asset.name + ".fbx")
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in asset.final:
        o.select_set(True)
    bpy.context.view_layer.objects.active = asset.final[0]
    bpy.ops.export_scene.fbx(filepath=path, **FBX_KW)
    return path


def tri_count(objs):
    n = 0
    for o in objs:
        if o.type == 'MESH':
            o.data.calc_loop_triangles()
            n += len(o.data.loop_triangles)
    return n


# --------------------------------------------------------------------------- preview render

def _world(sc, strength=1.0):
    w = bpy.data.worlds.new("PreviewSky")
    sc.world = w
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = (0.62, 0.55, 0.47, 1)
    cr.elements[1].position = 1.0
    cr.elements[1].color = (0.30, 0.48, 0.78, 1)
    e = cr.elements.new(0.5)
    e.color = (0.95, 0.80, 0.62, 1)
    e2 = cr.elements.new(0.62)
    e2.color = (0.68, 0.76, 0.86, 1)
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -1.0
    mr.inputs["From Max"].default_value = 1.0
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


def _setup_cycles(sc, res, samples):
    sc.render.engine = 'CYCLES'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for dev_type in ('OPTIX', 'CUDA'):
            try:
                prefs.compute_device_type = dev_type
                prefs.get_devices()
                ok = False
                for d in prefs.devices:
                    d.use = (d.type == dev_type)
                    ok = ok or d.use
                if ok:
                    sc.cycles.device = 'GPU'
                    break
            except Exception:
                continue
    except Exception as ex:
        print("GPU setup failed", ex)
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.cycles.max_bounces = 6
    sc.cycles.transparent_max_bounces = 8
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    sc.view_settings.exposure = 0.0


def _plane(name, z, size, mat_rgb, rough=0.9, water=False):
    me = bpy.data.meshes.new(name)
    s = size
    me.from_pydata([(-s, -s, z), (s, -s, z), (s, s, z), (-s, s, z)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new(name, me)
    link(ob)
    m = bpy.data.materials.new(name + "_mat")
    if m.node_tree is None:
        m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*mat_rgb, 1)
    b.inputs["Roughness"].default_value = rough
    if water:
        b.inputs["Transmission Weight"].default_value = 0.75
        b.inputs["IOR"].default_value = 1.33
    me.materials.append(m)
    return ob


def bbox_of(objs):
    lo = Vector((1e9, 1e9, 1e9)); hi = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        if o.type != 'MESH':
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            lo = Vector((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
            hi = Vector((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))
    return lo, hi


def render_preview(objs, out_path, ground_z=None, water=False, az=35.0, el=30.0, res=900, samples=64,
                   lens=50.0, margin=1.04, seabed=None, ground_rgb=(0.20, 0.24, 0.25), target=None):
    sc = bpy.context.scene
    _setup_cycles(sc, res, samples)
    _world(sc, 0.65)
    lo, hi = bbox_of(objs)
    if ground_z is None:
        ground_z = lo.z
    _plane("PreviewGround", (seabed if seabed is not None else ground_z) - 0.002, 600, ground_rgb)
    if water:
        _plane("PreviewWater", -1.2, 600, (0.10, 0.36, 0.40), rough=0.05, water=True)
    # sun - warm late afternoon from front-left
    sd = bpy.data.lights.new("Sun", 'SUN')
    sd.energy = 4.6
    sd.color = (1.0, 0.80, 0.58)
    sd.angle = math.radians(2.5)
    sun = bpy.data.objects.new("Sun", sd)
    link(sun)
    saz, sel = math.radians(58.0), math.radians(30.0)
    sdir = Vector((-math.sin(saz) * math.cos(sel), -math.cos(saz) * math.cos(sel), math.sin(sel)))
    sun.rotation_euler = sdir.to_track_quat('Z', 'Y').to_euler()
    # camera
    cd = bpy.data.cameras.new("Cam")
    cd.lens = lens
    cd.sensor_width = 36
    cam = bpy.data.objects.new("Cam", cd)
    link(cam)
    sc.camera = cam
    tgt = (lo + hi) / 2 if target is None else Vector(target)
    a, e = math.radians(az), math.radians(el)
    c = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
    rotq = (-c).to_track_quat('-Z', 'Y')
    cam.rotation_euler = rotq.to_euler()
    R = rotq.to_matrix()
    u = R @ Vector((1, 0, 0)); v = R @ Vector((0, 1, 0))
    tan_h = math.tan(math.atan(18.0 / lens)) / margin
    D = 0.0
    for x in (lo.x, hi.x):
        for y in (lo.y, hi.y):
            for z in (lo.z, hi.z):
                rel = Vector((x, y, z)) - tgt
                D = max(D, abs(rel.dot(u)) / tan_h + rel.dot(c), abs(rel.dot(v)) / tan_h + rel.dot(c))
    cam.location = tgt + c * D
    cd.clip_end = max(1000, D * 4)
    cd.clip_start = 0.05
    sc.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    return out_path


# --------------------------------------------------------------------------- registry / runner

REGISTRY = {}


def asset(name, category, group, ao=None, render=None):
    def deco(fn):
        REGISTRY[name] = dict(fn=fn, category=category, group=group, ao=ao or {}, render=render or {})
        return fn
    return deco


def build_one(name, do_render=True, report=None):
    info = REGISTRY[name]
    reset_scene()
    t0 = time.time()
    a = Asset(name, info['category'])
    info['fn'](a)
    finals = assemble(a, ao_kw=info['ao'])
    path = export_fbx(a)
    tris = tri_count(finals)
    rec = dict(name=name, category=info['category'], path=path, tris=tris,
               objects=[o.name for o in finals], seconds=round(time.time() - t0, 1), notes=a.notes)
    print(f"[built] {name}: {tris} tris -> {path}")
    if do_render:
        os.makedirs(RENDER_DIR, exist_ok=True)
        rkw = dict(info['render'])
        render_preview([o for o in finals if o.type == 'MESH'], os.path.join(RENDER_DIR, name + ".png"), **rkw)
    if report is not None:
        report.append(rec)
    return rec
