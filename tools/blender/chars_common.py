"""SKYFOLD - character / vehicle art stream: shared Blender 5.2 helpers.

Original procedural work for SKYFOLD: The Last Flight (Awaiz Ahmed / Team Kanban).
Not AI-generated art. Imported by the chars_*.py / veh_*.py build scripts, e.g.

    blender -b --factory-startup -P tools/blender/chars_nuri.py

Conventions (docs/ART_SPEC.md):
  * metres, Z up, assets face Blender -Y  (-> Unity +Z), asset left = Blender +X.
  * Unity axes:  x_u = -x_b,  y_u = z_b,  z_u = -y_b.
  * palette materials SKY_*, vertex colour AO in attribute "Col" (white = open).
"""
import bpy, bmesh, math, os, sys, json, random
from math import radians, degrees, sin, cos, pi, sqrt, atan2
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree

PROJECT = r"C:\UnityProjects\SKYFOLD"
MODELS = os.path.join(PROJECT, "Assets", "Skyfold", "Art", "Models")
RENDERS = os.path.join(PROJECT, "source-art", "renders")
TOOLS = os.path.join(PROJECT, "tools", "blender")

PALETTE = {
    "SKY_Pearl": "#F4EFE6", "SKY_Ivory": "#EFE6D2", "SKY_Sandstone": "#D9B98C",
    "SKY_SandstoneDeep": "#C49A6C", "SKY_Terracotta": "#C8754F", "SKY_Teal": "#0F6F73",
    "SKY_TealLight": "#3FA7A3", "SKY_TealGlow": "#35E0D0", "SKY_Coral": "#F2714B",
    "SKY_Gold": "#D9A441", "SKY_Brass": "#B8893B", "SKY_Ink": "#22333B",
    "SKY_Glass": "#6FB7C4", "SKY_Road": "#3E4A52", "SKY_RoadLine": "#F4EFE6",
    "SKY_Kerb": "#CDBFA9", "SKY_Wood": "#9A6B45", "SKY_PalmTrunk": "#8B6B4A",
    "SKY_PalmLeaf": "#5E8C4A", "SKY_Flower": "#E0557A", "SKY_Fabric": "#F7F1E6",
    "SKY_Metal": "#AEB6BA", "SKY_Rubber": "#2B2F33", "SKY_Light": "#FFD9A0",
}
# Preview-only shading hints. Unity remaps every material by name.
SHADING = {
    "SKY_Brass": dict(metal=0.85, rough=0.30),
    "SKY_Gold": dict(metal=1.0, rough=0.28),
    "SKY_Metal": dict(metal=0.8, rough=0.35),
    "SKY_Ivory": dict(rough=0.36, coat=0.3),
    "SKY_Pearl": dict(rough=0.30, coat=0.45),
    "SKY_Teal": dict(rough=0.32, coat=0.35),
    "SKY_TealLight": dict(rough=0.35),
    "SKY_Coral": dict(rough=0.38, coat=0.2),
    "SKY_Ink": dict(rough=0.45),
    "SKY_Rubber": dict(rough=0.78),
    "SKY_Glass": dict(rough=0.04, transmission=0.9),
    "SKY_TealGlow": dict(rough=0.2, emit=6.0),
    "SKY_Light": dict(rough=0.2, emit=8.0),
    "SKY_Fabric": dict(rough=0.85),
    "SKY_Wood": dict(rough=0.6),
}

AXES_NOTE = "unity = (-x_b, z_b, -y_b)"


def log(*a):
    print("[skyfold]", *a)
    sys.stdout.flush()


def b2u(v):
    """Blender vector -> Unity axes tuple."""
    return (-v[0], v[2], -v[1])


# ----------------------------------------------------------------------------
# scene / materials
# ----------------------------------------------------------------------------
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0
    return sc


def _srgb2lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def palette_linear(name):
    h = PALETTE[name].lstrip('#')
    return tuple(_srgb2lin(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


def get_mat(name):
    """Palette material; preview shader multiplies the base colour by the Col attribute
    (like Unity will)."""
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    if name not in PALETTE:
        raise KeyError("not a palette material: " + name)
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    rgb = palette_linear(name)
    m.diffuse_color = (*rgb, 1.0)
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    sh = SHADING.get(name, {})
    bsdf.inputs['Base Color'].default_value = (*rgb, 1.0)
    bsdf.inputs['Roughness'].default_value = sh.get('rough', 0.45)
    bsdf.inputs['Metallic'].default_value = sh.get('metal', 0.0)
    m.roughness = sh.get('rough', 0.45)
    m.metallic = sh.get('metal', 0.0)
    if 'coat' in sh:
        try:
            bsdf.inputs['Coat Weight'].default_value = sh['coat']
            bsdf.inputs['Coat Roughness'].default_value = 0.15
        except Exception:
            pass
    if 'transmission' in sh:
        try:
            bsdf.inputs['Transmission Weight'].default_value = sh['transmission']
            bsdf.inputs['IOR'].default_value = 1.45
        except Exception:
            pass
    if 'emit' in sh:
        bsdf.inputs['Emission Color'].default_value = (*rgb, 1.0)
        bsdf.inputs['Emission Strength'].default_value = sh['emit']
    # base colour x Col (vertex AO) for the preview renders
    vc = nt.nodes.new('ShaderNodeVertexColor')
    vc.layer_name = 'Col'
    rgbn = nt.nodes.new('ShaderNodeRGB')
    rgbn.outputs[0].default_value = (*rgb, 1.0)
    mul = nt.nodes.new('ShaderNodeVectorMath')
    mul.operation = 'MULTIPLY'
    nt.links.new(rgbn.outputs[0], mul.inputs[0])
    nt.links.new(vc.outputs['Color'], mul.inputs[1])
    nt.links.new(mul.outputs[0], bsdf.inputs['Base Color'])
    return m


# ----------------------------------------------------------------------------
# geometry builder
# ----------------------------------------------------------------------------
def _frame_from_normal(n):
    n = Vector(n).normalized()
    a = Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((1, 0, 0))
    t = a.cross(n).normalized()
    b = n.cross(t)
    return t, b, n


class Part:
    """Accumulates bmesh geometry (in design/world space) with per-face palette materials."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    # -- materials ---------------------------------------------------------
    def mi(self, name):
        if name not in self.mats:
            get_mat(name)
            self.mats.append(name)
        return self.mats.index(name)

    def assign(self, faces, name):
        i = self.mi(name)
        for f in faces:
            f.material_index = i
        return faces

    def assign_where(self, faces, fn):
        """fn(center, normal, face) -> material name or None."""
        for f in faces:
            r = fn(f.calc_center_median(), f.normal, f)
            if r:
                f.material_index = self.mi(r)

    # -- primitives ----------------------------------------------------------
    def grid(self, rings, mat, closed=True, cap0=None, cap1=None, closed_v=False):
        """rings: list of equal-length point lists. cap0/cap1: None | 'ngon' | Vector pole.
        closed_v connects the last ring back to the first (torus-like)."""
        bm = self.bm
        vr = [[bm.verts.new(Vector(p)) for p in ring] for ring in rings]
        n = len(rings[0])
        faces = []
        nr = len(vr) if closed_v else len(vr) - 1
        for i in range(nr):
            a, b = vr[i], vr[(i + 1) % len(vr)]
            for j in range(n if closed else n - 1):
                j2 = (j + 1) % n
                faces.append(bm.faces.new((a[j], a[j2], b[j2], b[j])))

        def cap(ring, c, rev):
            if c is None:
                return
            if isinstance(c, str):
                faces.append(bm.faces.new(ring[::-1] if rev else ring))
                return
            cv = bm.verts.new(Vector(c))
            for j in range(n):
                j2 = (j + 1) % n
                tri = (ring[j2], ring[j], cv) if not rev else (ring[j], ring[j2], cv)
                faces.append(bm.faces.new(tri))
        cap(vr[0], cap0, False)
        cap(vr[-1], cap1, True)
        self.assign(faces, mat)
        return vr, faces

    def lathe(self, profile, segs, mat, matrix=None, phase=0.0, axis='Z'):
        """profile: [(r, h), ...]; r ~ 0 at an end -> pole. Revolved about local axis."""
        pts = list(profile)
        p0 = p1 = None
        if pts[0][0] < 1e-7:
            p0 = pts.pop(0)
        if pts[-1][0] < 1e-7:
            p1 = pts.pop()
        M = matrix or Matrix.Identity(4)

        def ap(x, y, h):
            if axis == 'Z':
                v = Vector((x, y, h))
            elif axis == 'Y':
                v = Vector((x, h, y))
            else:
                v = Vector((h, x, y))
            return M @ v
        angs = [phase + 2 * pi * k / segs for k in range(segs)]
        rings = [[ap(r * cos(a), r * sin(a), h) for a in angs] for (r, h) in pts]
        c0 = ap(0, 0, p0[1]) if p0 else None
        c1 = ap(0, 0, p1[1]) if p1 else None
        return self.grid(rings, mat, True, c0, c1)

    def cylinder(self, r, h, segs, mat, matrix=None, caps=True, bevel=0.0):
        if bevel > 0:
            prof = [(0, 0), (r - bevel, 0), (r, bevel), (r, h - bevel), (r - bevel, h), (0, h)]
        else:
            prof = [(0, 0), (r, 0), (r, h), (0, h)] if caps else [(r, 0), (r, h)]
        return self.lathe(prof, segs, mat, matrix)

    def tube(self, path, radius, segs, mat, caps='round', cap_segs=3, closed=False,
             scale_xy=(1.0, 1.0), up=None, twist=0.0):
        """Sweep a circle along a polyline. radius: float or per-point list.
        scale_xy squashes the section (x = side vector, y = up vector)."""
        P = [Vector(p) for p in path]
        n = len(P)
        R = radius if isinstance(radius, (list, tuple)) else [radius] * n
        SX = scale_xy if isinstance(scale_xy[0], (list, tuple)) else [scale_xy] * n
        T = []
        for i in range(n):
            if closed:
                d = P[(i + 1) % n] - P[(i - 1) % n]
            elif i == 0:
                d = P[1] - P[0]
            elif i == n - 1:
                d = P[-1] - P[-2]
            else:
                d = (P[i + 1] - P[i]).normalized() + (P[i] - P[i - 1]).normalized()
            T.append(d.normalized())
        # parallel transport
        if up is not None:
            u0 = Vector(up)
            u0 = (u0 - T[0] * u0.dot(T[0])).normalized()
        else:
            _, u0, _ = _frame_from_normal(T[0])
        U = [u0]
        for i in range(1, n):
            u = U[-1] - T[i] * U[-1].dot(T[i])
            if u.length < 1e-8:
                _, u, _ = _frame_from_normal(T[i])
            U.append(u.normalized())
        rings = []
        for i in range(n):
            t, u = T[i], U[i]
            s = u.cross(t).normalized()
            if twist:
                q = Quaternion(t, twist * i / max(1, n - 1))
                s = q @ s
                u = q @ u
            ring = []
            for k in range(segs):
                a = 2 * pi * k / segs
                ring.append(P[i] + (s * cos(a) * SX[i][0] + u * sin(a) * SX[i][1]) * R[i])
            rings.append(ring)
        c0 = c1 = None
        if not closed and caps == 'round':
            # hemispherical caps
            pre, post = [], []
            for k in range(1, cap_segs + 1):
                ang = (pi / 2) * k / (cap_segs + 1)
                f = cos(ang)
                off = sin(ang)
                for (idx, sign, lst) in ((0, -1, pre), (n - 1, 1, post)):
                    t = T[idx]
                    ring = [P[idx] + (q - P[idx]) * f + t * sign * off * R[idx] * 0.85
                            for q in rings[idx]]
                    lst.append(ring)
            rings = pre[::-1] + rings + post
            c0 = P[0] - T[0] * R[0] * 0.85
            c1 = P[-1] + T[-1] * R[-1] * 0.85
        elif not closed and caps == 'flat':
            c0 = sum(rings[0], Vector()) / segs
            c1 = sum(rings[-1], Vector()) / segs
        if closed:
            return self.grid(rings, mat, True, closed_v=True)
        return self.grid(rings, mat, True, c0, c1)

    def prism(self, outline, thickness, mat, matrix=None, side_mat=None):
        """Extrude a 2D outline (CCW, local XY) by thickness along local +Z (centred)."""
        M = matrix or Matrix.Identity(4)
        bm = self.bm
        h = thickness / 2
        bot = [bm.verts.new(M @ Vector((x, y, -h))) for (x, y) in outline]
        top = [bm.verts.new(M @ Vector((x, y, h))) for (x, y) in outline]
        faces = [bm.faces.new(top), bm.faces.new(bot[::-1])]
        n = len(outline)
        sides = []
        for i in range(n):
            j = (i + 1) % n
            sides.append(bm.faces.new((bot[i], bot[j], top[j], top[i])))
        self.assign(faces + sides, mat)
        if side_mat:
            self.assign(sides, side_mat)
        return bot + top, faces + sides

    def box(self, center, size, mat, matrix=None):
        bm = self.bm
        res = bmesh.ops.create_cube(bm, size=1.0)
        vs = res['verts']
        M = (matrix or Matrix.Identity(4)) @ Matrix.Translation(center) @ Matrix.Diagonal((*size, 1))
        bmesh.ops.transform(bm, matrix=M, verts=vs)
        faces = list({f for v in vs for f in v.link_faces})
        self.assign(faces, mat)
        return vs, faces

    def rbox(self, center, size, radius, segs, mat, matrix=None):
        """Box with every edge rounded (bmesh bevel, applied immediately)."""
        bm = self.bm
        res = bmesh.ops.create_cube(bm, size=1.0)
        vs = res['verts']
        bmesh.ops.transform(bm, matrix=Matrix.Diagonal((*size, 1)), verts=vs)
        edges = list({e for v in vs for e in v.link_edges})
        r = min(radius, min(size) * 0.499)
        out = bmesh.ops.bevel(bm, geom=vs + edges, offset=r, offset_type='OFFSET',
                              segments=segs, profile=0.5, affect='EDGES', clamp_overlap=True)
        allv = list({v for f in out['faces'] for v in f.verts} | set(vs))
        allv = [v for v in allv if v.is_valid]
        # collect connected verts
        island = set(allv)
        stack = list(allv)
        while stack:
            v = stack.pop()
            for e in v.link_edges:
                o = e.other_vert(v)
                if o not in island:
                    island.add(o)
                    stack.append(o)
        M = (matrix or Matrix.Identity(4)) @ Matrix.Translation(center)
        bmesh.ops.transform(bm, matrix=M, verts=list(island))
        faces = list({f for v in island for f in v.link_faces})
        self.assign(faces, mat)
        return list(island), faces

    def superellipsoid(self, center, radii, e_lat, e_lon, nu, nv, mat, matrix=None,
                       pole_axis='Z', deform=None):
        """Superellipsoid; e=1 ellipsoid, e<1 boxier. pole_axis = axis through the poles."""
        def sc(w, e):
            c = cos(w)
            return math.copysign(abs(c) ** e, c)

        def ss(w, e):
            s = sin(w)
            return math.copysign(abs(s) ** e, s)
        M = (matrix or Matrix.Identity(4)) @ Matrix.Translation(center)
        rings = []
        for i in range(1, nv):
            v = -pi / 2 + pi * i / nv
            ring = []
            for j in range(nu):
                u = -pi + 2 * pi * j / nu
                a = sc(v, e_lat) * sc(u, e_lon)
                b = sc(v, e_lat) * ss(u, e_lon)
                c = ss(v, e_lat)
                ring.append(self._pole_map(a, b, c, radii, pole_axis))
            rings.append(ring)
        p0 = self._pole_map(0, 0, -1, radii, pole_axis)
        p1 = self._pole_map(0, 0, 1, radii, pole_axis)
        if deform:
            rings = [[deform(p) for p in ring] for ring in rings]
            p0, p1 = deform(p0), deform(p1)
        rings = [[M @ p for p in ring] for ring in rings]
        return self.grid(rings, mat, True, M @ p0, M @ p1)

    @staticmethod
    def _pole_map(a, b, c, radii, pole_axis):
        rx, ry, rz = radii
        if pole_axis == 'Z':
            return Vector((a * rx, b * ry, c * rz))
        if pole_axis == 'Y':
            return Vector((b * rx, c * ry, a * rz))
        return Vector((c * rx, a * ry, b * rz))

    def torus(self, R, r, nu, nv, mat, matrix=None, scale_minor=(1.0, 1.0)):
        M = matrix or Matrix.Identity(4)
        rings = []
        for i in range(nu):
            a = 2 * pi * i / nu
            ca, sa = cos(a), sin(a)
            ring = []
            for j in range(nv):
                b = 2 * pi * j / nv
                rr = R + r * cos(b) * scale_minor[0]
                ring.append(M @ Vector((rr * ca, rr * sa, r * sin(b) * scale_minor[1])))
            rings.append(ring)
        bm = self.bm
        vr = [[bm.verts.new(p) for p in ring] for ring in rings]
        faces = []
        for i in range(nu):
            a, b = vr[i], vr[(i + 1) % nu]
            for j in range(nv):
                j2 = (j + 1) % nv
                faces.append(bm.faces.new((a[j], b[j], b[j2], a[j2])))
        self.assign(faces, mat)
        return vr, faces

    # -- utilities -------------------------------------------------------------
    def transform(self, verts, matrix):
        bmesh.ops.transform(self.bm, matrix=matrix, verts=list(verts))

    def deform(self, verts, fn):
        for v in verts:
            v.co = fn(v.co.copy())

    def mirror_x(self):
        """Mirror all geometry across X (x -> -x) and fix winding."""
        bmesh.ops.transform(self.bm, matrix=Matrix.Diagonal((-1, 1, 1, 1)), verts=self.bm.verts)
        bmesh.ops.reverse_faces(self.bm, faces=self.bm.faces)

    def recalc(self):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)

    def to_temp(self, bevel=None, recalc=True, name="tmp"):
        """Turn into a temporary world-space object with bevel (+ngon triangulation) applied.
        bevel = (width, segments[, angle_deg])"""
        bm = self.bm
        if recalc:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new(name + "_tmp")
        bm.to_mesh(me)
        bm.free()
        for m in self.mats:
            me.materials.append(get_mat(m))
        ob = bpy.data.objects.new(name + "_tmp", me)
        bpy.context.scene.collection.objects.link(ob)
        if bevel:
            md = ob.modifiers.new("Bevel", 'BEVEL')
            md.width = bevel[0]
            md.segments = bevel[1]
            md.limit_method = 'ANGLE'
            md.angle_limit = radians(bevel[2] if len(bevel) > 2 else 30)
            md.use_clamp_overlap = True
            md.profile = 0.5
            md.miter_outer = 'MITER_ARC'
        tri = ob.modifiers.new("Tri", 'TRIANGULATE')
        tri.min_vertices = 5
        tri.quad_method = 'BEAUTY'
        tri.ngon_method = 'BEAUTY'
        apply_modifiers(ob)
        return ob


def apply_modifiers(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return ob


def merge_to_object(name, temps, pivot=(0, 0, 0), parent=None, rot=None, sharp_deg=38.0,
                    weighted=True, merge_dist=0.0):
    """Merge temp objects (world space) into one mesh object whose origin is the pivot.
    rot: optional Euler/Matrix3 orientation of the object (world). Parent must have identity
    rotation (or be given) - local transform = parent_world^-1 @ T(pivot) @ R."""
    bm = bmesh.new()
    mats = []
    for o in temps:
        me = o.data.copy()
        me.transform(o.matrix_world)
        idx = []
        for m in me.materials:
            if m.name not in mats:
                mats.append(m.name)
            idx.append(mats.index(m.name))
        n0 = len(bm.faces)
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        for k in range(n0, len(bm.faces)):
            f = bm.faces[k]
            f.material_index = idx[f.material_index] if idx else 0
        bpy.data.meshes.remove(me)
    for o in temps:
        m = o.data
        bpy.data.objects.remove(o)
        if m.users == 0:
            bpy.data.meshes.remove(m)
    if merge_dist > 0:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_dist)
    R = Matrix.Identity(4)
    if rot is not None:
        R = (rot.to_matrix() if hasattr(rot, 'to_matrix') else rot).to_4x4()
    W = Matrix.Translation(pivot) @ R
    bmesh.ops.transform(bm, matrix=W.inverted(), verts=bm.verts)
    # shading: all smooth + sharp edges by angle
    bm.normal_update()
    thr = radians(sharp_deg)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        lf = e.link_faces
        if len(lf) == 2:
            e.smooth = lf[0].normal.angle(lf[1].normal, 0.0) < thr
        else:
            e.smooth = False
    me = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(bpy.data.materials[m])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if weighted:
        md = ob.modifiers.new("WN", 'WEIGHTED_NORMAL')
        md.mode = 'FACE_AREA'
        md.weight = 50
        md.keep_sharp = True
        md.thresh = 0.01
        apply_modifiers(ob)
    place(ob, parent, W)
    return ob


def place(ob, parent, world_matrix):
    ob.parent = parent
    ob.matrix_parent_inverse = Matrix.Identity(4)
    if parent is not None:
        ob.matrix_basis = parent.matrix_world.inverted() @ world_matrix
    else:
        ob.matrix_basis = world_matrix
    bpy.context.view_layer.update()


def new_empty(name, parent=None, pos=(0, 0, 0), rot=None, size=0.05, kind='PLAIN_AXES'):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = kind
    ob.empty_display_size = size
    bpy.context.scene.collection.objects.link(ob)
    R = Matrix.Identity(4)
    if rot is not None:
        R = (rot.to_matrix() if hasattr(rot, 'to_matrix') else rot).to_4x4()
    place(ob, parent, Matrix.Translation(pos) @ R)
    return ob


def descendants(ob):
    out = [ob]
    for c in ob.children:
        out += descendants(c)
    return out


# ----------------------------------------------------------------------------
# vertex-colour AO ("Col")
# ----------------------------------------------------------------------------
def _hemi_dirs(n):
    """Cosine-weighted Fibonacci hemisphere directions (local z up)."""
    ga = pi * (3 - sqrt(5))
    out = []
    for i in range(n):
        r = sqrt((i + 0.5) / n)
        a = i * ga
        out.append(Vector((r * cos(a), r * sin(a), sqrt(max(0.0, 1 - r * r)))))
    return out


def bake_ao(objs, dist, samples=48, strength=1.0, floor=0.32, ground_z=None, ground_strength=1.0,
            smooth=2, gamma=1.0, occluders=(), white=()):
    """Bake a soft ambient-occlusion term into a POINT colour attribute 'Col' on each object.
    objs: objects baked together (they occlude each other). occluders: extra objects that
    only occlude. white: objects that get Col = 1."""
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    verts, tris = [], []
    for o in list(objs) + list(occluders):
        me = o.data
        mw = o.matrix_world
        me.calc_loop_triangles()
        base = len(verts)
        verts.extend([mw @ v.co for v in me.vertices])
        tris.extend([(base + t.vertices[0], base + t.vertices[1], base + t.vertices[2])
                     for t in me.loop_triangles])
    if ground_z is not None and verts:
        xs = [v.x for v in verts]
        ys = [v.y for v in verts]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        S = max(max(xs) - min(xs), max(ys) - min(ys)) * 2 + 2 * dist
        base = len(verts)
        verts += [Vector((cx - S, cy - S, ground_z)), Vector((cx + S, cy - S, ground_z)),
                  Vector((cx + S, cy + S, ground_z)), Vector((cx - S, cy + S, ground_z))]
        tris += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
    bvh = BVHTree.FromPolygons(verts, tris, all_triangles=True)
    dirs = _hemi_dirs(samples)
    eps = dist * 0.002 + 1e-5
    for o in objs:
        me = o.data
        mw = o.matrix_world
        nm = mw.to_3x3().inverted().transposed()
        nv = len(me.vertices)
        vals = [1.0] * nv
        if o not in white:
            for i, v in enumerate(me.vertices):
                p = mw @ v.co
                n = (nm @ v.normal).normalized()
                t, b, n = _frame_from_normal(n)
                o0 = p + n * eps
                occ = 0.0
                for d in dirs:
                    wd = t * d.x + b * d.y + n * d.z
                    hit = bvh.ray_cast(o0, wd, dist)
                    if hit[0] is not None:
                        occ += 1.0 - (hit[3] / dist) ** 1.2
                vals[i] = max(0.0, 1.0 - strength * occ / samples)
            # smooth over edges
            if smooth:
                nb = [[] for _ in range(nv)]
                for e in me.edges:
                    a, c = e.vertices
                    nb[a].append(c)
                    nb[c].append(a)
                for _ in range(smooth):
                    vals = [(vals[i] * 2 + sum(vals[j] for j in nb[i])) / (2 + len(nb[i]))
                            if nb[i] else vals[i] for i in range(nv)]
            vals = [floor + (1 - floor) * (max(0.0, min(1.0, x)) ** gamma) for x in vals]
        for a in list(me.color_attributes):
            me.color_attributes.remove(a)
        attr = me.color_attributes.new(name="Col", type='BYTE_COLOR', domain='POINT')
        flat = []
        for x in vals:
            flat += [x, x, x, 1.0]
        attr.data.foreach_set("color", flat)
        me.color_attributes.active_color = attr
        try:
            me.color_attributes.render_color_index = 0
        except Exception:
            pass


# ----------------------------------------------------------------------------
# FBX export (exact ART_SPEC call) + fix for nested bake_space_transform
# ----------------------------------------------------------------------------
_PATCHED = False


def _patch_fbx_exporter():
    """Blender 5.2's FBX exporter computes wrong local matrices for objects nested two or
    more levels below the root when bake_space_transform=True (the parent's 'local' FBX
    matrix is mixed with its Blender-space matrix, adding a stray -90deg X rotation and an
    unconverted offset). For mesh/empty chains the correct FBX local matrix is simply
    G @ local @ G^-1. We patch only that case and leave every other path untouched."""
    global _PATCHED
    if _PATCHED:
        return
    import io_scene_fbx.fbx_utils as fu
    orig = fu.ObjectWrapper.fbx_object_matrix

    def fixed(self, scene_data, rest=False, local_space=False, global_space=False):
        parent = self.parent
        try:
            ok = (self._tag == 'OB' and parent is not None and parent._tag == 'OB'
                  and not self.parented_to_armature
                  and self.bdata.type in {'MESH', 'EMPTY'}
                  and parent.bdata.type in {'MESH', 'EMPTY'}
                  and self.use_bake_space_transform(scene_data)
                  and parent.use_bake_space_transform(scene_data)
                  and self.has_valid_parent(scene_data.objects))
        except Exception:
            ok = False
        if not ok:
            return orig(self, scene_data, rest, local_space, global_space)
        G = scene_data.settings.global_matrix
        Gi = scene_data.settings.global_matrix_inv
        if global_space and not local_space:
            m = parent.matrix_rest_global if rest else parent.matrix_global
            return G @ m @ (self.matrix_rest_local if rest else self.matrix_local) @ Gi
        m = self.matrix_rest_local if rest else self.matrix_local
        return G @ m @ Gi
    fu.ObjectWrapper.fbx_object_matrix = fixed
    _PATCHED = True


def export_fbx(root, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _patch_fbx_exporter()
    for o in bpy.context.scene.objects:
        o.select_set(False)
    objs = descendants(root)
    for o in objs:
        o.hide_set(False)
        o.hide_viewport = False
        o.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={'EMPTY', 'MESH'},
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z',
        axis_up='Y', bake_space_transform=True, use_mesh_modifiers=True,
        mesh_smooth_type='FACE', add_leaf_bones=False, use_armature_deform_only=True,
        colors_type='SRGB', path_mode='AUTO', embed_textures=False)
    log("exported", path)
    return path


def tri_count(ob):
    me = ob.data
    me.calc_loop_triangles()
    return len(me.loop_triangles)


def summary(root):
    rows = []
    total = 0
    for o in descendants(root):
        t = tri_count(o) if o.type == 'MESH' else 0
        total += t
        rows.append((o.name, o.type, o.parent.name if o.parent else None,
                     tuple(round(x, 4) for x in o.location), t))
    for r in rows:
        log("  %-18s %-6s parent=%-12s loc=%s tris=%d" % r)
    log("  TOTAL tris", total)
    return total


# ----------------------------------------------------------------------------
# preview rendering
# ----------------------------------------------------------------------------
def world_bbox(objs):
    mn = Vector((1e9, 1e9, 1e9))
    mx = -mn
    for o in objs:
        if o.type != 'MESH':
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            mn = Vector(map(min, mn, w))
            mx = Vector(map(max, mx, w))
    return mn, mx


def setup_render(res=(960, 720), samples=96):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = (d.type == 'OPTIX')
        sc.cycles.device = 'GPU'
    except Exception as e:
        log("GPU setup failed, CPU render", e)
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.cycles.max_bounces = 6
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = 'Medium High Contrast'
    except Exception:
        pass
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = 'PNG'
    return sc


def _preview_mat(name, rgb, rough=0.8):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = rough
    return m


def studio(center, size, ground_z=0.0, sun_az=-40.0, sun_el=32.0, sun_strength=5.0,
           backdrop=True):
    """Warm late-afternoon studio: warm low sun, cool sky fill, pale sandstone ground."""
    sc = bpy.context.scene
    world = bpy.data.worlds.new("PreviewWorld")
    sc.world = world
    try:
        world.use_nodes = True
    except Exception:
        pass
    nt = world.node_tree
    bg = next(n for n in nt.nodes if n.type == 'BACKGROUND')
    # vertical gradient: warm haze near horizon, soft teal-blue above
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    nt.links.new(sep.outputs['Z'], ramp.inputs[0])
    ramp.color_ramp.elements[0].position = 0.02
    ramp.color_ramp.elements[0].color = (0.80, 0.62, 0.45, 1)
    ramp.color_ramp.elements[1].position = 0.45
    ramp.color_ramp.elements[1].color = (0.28, 0.42, 0.55, 1)
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 0.65
    # sun
    sd = bpy.data.lights.new("Sun", 'SUN')
    sd.energy = sun_strength
    sd.color = (1.0, 0.80, 0.60)
    sd.angle = radians(4.0)
    sun = bpy.data.objects.new("Sun", sd)
    sc.collection.objects.link(sun)
    # cool rim/fill from the opposite side
    ad = bpy.data.lights.new("Rim", 'AREA')
    ad.energy = 40.0 * size * size
    ad.color = (0.75, 0.88, 1.0)
    ad.size = size * 1.5
    rim = bpy.data.objects.new("Rim", ad)
    sc.collection.objects.link(rim)
    rig = dict(sun=sun, rim=rim, center=Vector(center), size=size)
    aim_lights(rig, sun_az, sun_el)
    if backdrop:
        me = bpy.data.meshes.new("Ground")
        bm = bmesh.new()
        S = size * 30
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=S)
        bm.to_mesh(me)
        bm.free()
        g = bpy.data.objects.new("Ground", me)
        g.location = (center[0], center[1], ground_z)
        sc.collection.objects.link(g)
        me.materials.append(_preview_mat("PreviewGround", (0.46, 0.36, 0.26), 0.9))
    return rig


def aim_lights(rig, sun_az, sun_el):
    """Sun from azimuth (deg, 0 = from the front (-Y), positive toward +X) and elevation;
    rim light from the opposite side."""
    az, el = radians(sun_az), radians(sun_el)
    d = Vector((sin(az) * cos(el), -cos(az) * cos(el), sin(el)))  # towards the light
    rig['sun'].rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    c, size = rig['center'], rig['size']
    p = c + Vector((-sin(az), cos(az), 0.7)).normalized() * size * 2.2
    rig['rim'].location = p
    rig['rim'].rotation_euler = (c - p).to_track_quat('-Z', 'Y').to_euler()


def frame_camera(objs, az_deg, el_deg, lens=55.0, margin=1.12, ortho=False, target=None,
                 res=None):
    """Camera looking at the bbox from azimuth/elevation (0 az = from front (-Y); positive
    az rotates toward +X (= the asset's left side))."""
    sc = bpy.context.scene
    res = res or (sc.render.resolution_x, sc.render.resolution_y)
    mn, mx = world_bbox(objs)
    c = (mn + mx) / 2 if target is None else Vector(target)
    # fit to real silhouette points (subsampled vertices), not the AABB corners
    corners = []
    for o in objs:
        if o.type != 'MESH':
            continue
        vs = o.data.vertices
        step = max(1, len(vs) // 600)
        mw = o.matrix_world
        corners += [mw @ vs[i].co for i in range(0, len(vs), step)]
    if not corners:
        corners = [Vector((x, y, z)) for x in (mn.x, mx.x) for y in (mn.y, mx.y)
                   for z in (mn.z, mx.z)]
    az, el = radians(az_deg), radians(el_deg)
    d = Vector((sin(az) * cos(el), -cos(az) * cos(el), sin(el))).normalized()
    cd = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cd.lens = lens
    cd.sensor_fit = 'HORIZONTAL'
    cd.sensor_width = 36.0
    aspect = res[0] / res[1]
    q = (-d).to_track_quat('-Z', 'Y')
    Rm = q.to_matrix()
    Rt = Rm.transposed()
    if ortho:
        cd.type = 'ORTHO'
        xs, ys = [], []
        for p in corners:
            v = Rt @ (p - c)
            xs.append(v.x)
            ys.append(v.y)
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        w = max(max(xs) - min(xs), (max(ys) - min(ys)) * aspect) * margin
        cd.ortho_scale = w
        R = max((mx - mn).length, 1.0)
        cam.location = c + Rm @ Vector((cx, cy, 0)) + d * R * 3
        cd.clip_end = R * 10
        cam.rotation_euler = q.to_euler()
        return cam
    tx = 18.0 / lens  # tan(half fov x) for 36 mm sensor
    ty = tx / aspect
    D = (mx - mn).length * 1.5
    for _ in range(40):
        pos = c + d * D
        xs, ys = [], []
        for p in corners:
            v = Rt @ (p - pos)
            z = max(-v.z, 1e-6)
            xs.append(v.x / z / tx)
            ys.append(v.y / z / ty)
        ext = max(max(xs) - min(xs), max(ys) - min(ys)) / 2
        # recenter
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        dist_c = (c - pos).length
        c = c + Rm @ Vector((cx * tx * dist_c, cy * ty * dist_c, 0)) * 0.9
        D *= (ext * margin) ** 0.7
    cam.location = c + d * D
    cam.rotation_euler = q.to_euler()
    cd.clip_start = D * 0.01
    cd.clip_end = D * 20
    return cam


def render_to(path):
    sc = bpy.context.scene
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    log("render", path)


FL_BR = (("fl", 38, 20), ("br", -142, 22))   # front-left, back-right 3/4 views


def render_previews(name, root, views=FL_BR, res=(960, 720), samples=96, ground_z=0.0,
                    lens=55.0, margin=1.12, sun_rel=42.0, sun_el=30.0, objs=None):
    """3/4 previews. The warm sun sits sun_rel degrees to the camera's left-front so every
    view gets the same late-afternoon key/rim relationship."""
    objs = objs or [o for o in descendants(root) if o.type == 'MESH']
    setup_render(res, samples)
    mn, mx = world_bbox(objs)
    size = (mx - mn).length
    rig = studio((mn + mx) / 2, size, ground_z=ground_z, sun_el=sun_el)
    out = []
    for (tag, az, el) in views:
        aim_lights(rig, az + sun_rel, sun_el)
        cam = frame_camera(objs, az, el, lens=lens, margin=margin)
        p = os.path.join(RENDERS, "%s_%s.png" % (name, tag))
        render_to(p)
        out.append(p)
        bpy.data.objects.remove(cam)
    return out


def render_ortho(name, root, views, res=(800, 800), samples=64, ground_z=None, margin=1.1,
                 objs=None):
    """Clean orthographic views: views = [(tag, az, el), ...]."""
    objs = objs or [o for o in descendants(root) if o.type == 'MESH']
    setup_render(res, samples)
    mn, mx = world_bbox(objs)
    size = (mx - mn).length
    rig = studio((mn + mx) / 2, size, ground_z=(ground_z if ground_z is not None else mn.z - size),
                 backdrop=ground_z is not None)
    out = []
    for (tag, az, el) in views:
        aim_lights(rig, az + 35, 35)
        cam = frame_camera(objs, az, el, margin=margin, ortho=True)
        p = os.path.join(RENDERS, "%s_%s.png" % (name, tag))
        render_to(p)
        out.append(p)
        bpy.data.objects.remove(cam)
    return out
