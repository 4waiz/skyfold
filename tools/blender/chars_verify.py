"""Verify the character / vehicle FBX exports and write source-art/models_manifest_chars.json.

Original tooling for SKYFOLD (Awaiz Ahmed / Team Kanban).
    blender -b --factory-startup -P tools/blender/chars_verify.py

For every FBX it
  1. parses the raw FBX (io_scene_fbx.parse_fbx) and derives what Unity will see: node names,
     parenting, local pivot positions / rotations in Unity axes (x_u=-x_fbx, metres);
  2. re-imports the FBX into a fresh scene and checks names, parenting, world pivot positions
     against the build script's intent (sidecar written by chars_common.export_fbx), palette
     materials (SKY_*), the 'Col' colour attribute on every mesh, required empties, tri budgets;
  3. writes the manifest (per file: path, hierarchy with Unity-axis local pivots, empties,
     bounds, tris).
"""
import bpy, os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C
from mathutils import Vector, Matrix, Euler, Quaternion

MANIFEST = os.path.join(C.PROJECT, "source-art", "models_manifest_chars.json")

ASSETS = [
    ("Characters/nuri.fbx", "tools/blender/chars_nuri.py", 16000,
     ["Nuri", "Body", "Head", "Lens", "Beak", "Wing_L", "Wing_R", "Tail", "Thruster"],
     "NURI companion (hovering mechanical falcon)"),
    ("Characters/glove_L.fbx", "tools/blender/chars_gloves.py", 14000,
     ["glove_L", "Open", "Grip", "ANCHOR_wristui"], "Left courier glove + folding-city bracer"),
    ("Characters/glove_R.fbx", "tools/blender/chars_gloves.py", 14000,
     ["glove_R", "Open", "Grip"], "Right courier glove"),
    ("Vehicles/courier_car.fbx", "tools/blender/veh_courier_car.py", 24000,
     ["courier_car", "Body", "SteeringWheel", "Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR",
      "ANCHOR_driver_eye", "ANCHOR_exit_left", "ANCHOR_exit_right", "ANCHOR_door", "SOCKET_cargo"],
     "Player courier buggy (Episode 2)"),
    ("Vehicles/convoy_shuttle.fbx", "tools/blender/veh_convoy_shuttle.py", 18000,
     ["convoy_shuttle", "Body", "Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR"],
     "Convoy minibus (Episodes 2-3)"),
    ("Vehicles/city_car_a.fbx", "tools/blender/veh_city_cars.py", 12000,
     ["city_car_a", "Body", "Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR"], "Ambient traffic"),
    ("Vehicles/city_car_b.fbx", "tools/blender/veh_city_cars.py", 12000,
     ["city_car_b", "Body", "Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR"], "Ambient traffic"),
    ("Vehicles/aircraft.fbx", "tools/blender/veh_aircraft.py", 40000,
     ["aircraft", "Body", "Door", "Prop_L", "Prop_R", "LIGHT_nav_L", "LIGHT_nav_R",
      "LIGHT_beacon", "LIGHT_landing", "ANCHOR_door"], "'The last flight' aircraft (Episode 3)"),
    ("Props/power_cell.fbx", "tools/blender/veh_power_cell.py", 2500,
     ["PowerCell", "Core", "ANCHOR_handle"], "Grabbable power cell (Episode 2)"),
    ("Characters/passenger_a.fbx", "tools/blender/chars_passengers.py", 7000,
     ["passenger_a", "Body"], "Terminal queue figure (P1)"),
    ("Characters/passenger_b.fbx", "tools/blender/chars_passengers.py", 7000,
     ["passenger_b", "Body"], "Terminal queue figure (P1)"),
    ("Characters/passenger_c.fbx", "tools/blender/chars_passengers.py", 7000,
     ["passenger_c", "Body"], "Terminal queue figure (P1)"),
]


def r6(v):
    return [round(float(x), 5) for x in v]


def b2u(v):
    return [-v[0], v[2], -v[1]]


# ---------------------------------------------------------------------------- raw FBX
def raw_fbx(path):
    from io_scene_fbx import parse_fbx
    root, ver = parse_fbx.parse(path)

    def find(el, name):
        for c in el.elems:
            if c.id == name:
                return c
        return None
    gs = {}
    for p in find(find(root, b'GlobalSettings'), b'Properties70').elems:
        gs[p.props[0].decode()] = p.props[4:]
    unit = float(gs.get('UnitScaleFactor', [1.0])[0]) / 100.0
    models, mats = {}, {}
    for o in find(root, b'Objects').elems:
        if o.id == b'Model':
            uid = o.props[0]
            name = o.props[1].split(b'\x00')[0].decode()
            T, R, S = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [1.0, 1.0, 1.0]
            p70 = find(o, b'Properties70')
            if p70:
                for p in p70.elems:
                    k = p.props[0]
                    if k == b'Lcl Translation':
                        T = [float(x) for x in p.props[4:7]]
                    elif k == b'Lcl Rotation':
                        R = [float(x) for x in p.props[4:7]]
                    elif k == b'Lcl Scaling':
                        S = [float(x) for x in p.props[4:7]]
            models[uid] = dict(name=name, type=o.props[2].decode(), T=T, R=R, S=S, parent=None)
        elif o.id == b'Material':
            mats[o.props[0]] = o.props[1].split(b'\x00')[0].decode()
    for c in find(root, b'Connections').elems:
        if c.props[0] == b'OO' and c.props[1] in models:
            par = c.props[2]
            models[c.props[1]]['parent'] = models[par]['name'] if par in models else None
    return dict(version=ver, unit=unit, axes=dict(up=gs.get('UpAxis'), front=gs.get('FrontAxis'),
                                                  coord=gs.get('CoordAxis')),
                models=list(models.values()), materials=sorted(set(mats.values())))


def unity_local(m, unit):
    """Unity sees the FBX right-handed scene mirrored on X."""
    t = m['T']
    pos = [-t[0] * unit, t[1] * unit, t[2] * unit]
    rx, ry, rz = (math.radians(a) for a in m['R'])
    Rf = Euler((rx, ry, rz), 'XYZ').to_matrix()       # FBX default rotation order XYZ
    q = Rf.to_quaternion()
    qu = Quaternion((q.w, q.x, -q.y, -q.z))             # mirror X
    Ru = qu.to_matrix()
    ex = math.degrees(math.asin(max(-1.0, min(1.0, -Ru[1][2]))))
    ey = math.degrees(math.atan2(Ru[0][2], Ru[2][2]))
    ez = math.degrees(math.atan2(Ru[1][0], Ru[1][1]))
    axes = dict(right=r6(Ru.col[0]), up=r6(Ru.col[1]), forward=r6(Ru.col[2]))
    return pos, [round(ex, 3) % 360, round(ey, 3) % 360, round(ez, 3) % 360], axes, list(m['S'])


# ---------------------------------------------------------------------------- re-import
def reimport(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    bpy.context.view_layer.update()
    return {o.name: o for o in bpy.context.scene.objects}


def verify(rel, src, budget, required, purpose):
    path = os.path.join(C.MODELS, rel.replace('/', os.sep))
    res = dict(path="Assets/Skyfold/Art/Models/" + rel, source=src, purpose=purpose)
    issues = []
    if not os.path.exists(path):
        return dict(res, ok=False, issues=["missing file"])
    raw = raw_fbx(path)
    side = os.path.join(C.DEBUG_DIR, os.path.basename(path) + ".expected.json")
    expected = {}
    if os.path.exists(side):
        expected = {r['name']: r for r in json.load(open(side))['objects']}
    else:
        issues.append("no build sidecar (re-run the build script)")
    objs = reimport(path)
    # names / parenting
    names = {m['name'] for m in raw['models']}
    for n in required:
        if n not in names:
            issues.append("missing node " + n)
    for m in raw['models']:
        e = expected.get(m['name'])
        if e and (e['parent'] or None) != (m['parent'] or None):
            issues.append("parent mismatch %s: %s vs %s" % (m['name'], m['parent'], e['parent']))
    # pivots: raw FBX (Unity view) vs build intent, and Blender re-import world positions
    hier = []
    tris_total = 0
    mats_used = set()
    col_ok = True
    for m in raw['models']:
        pos, eul, axes, scl = unity_local(m, raw['unit'])
        ob = objs.get(m['name'])
        node = dict(name=m['name'], type=('Mesh' if m['type'] == 'Mesh' else 'Empty'),
                    parent=m['parent'], local_position=r6(pos), local_rotation_euler=eul)
        if any(abs(a) > 1e-3 and abs(a - 360) > 1e-3 for a in eul):
            node['local_axes_unity'] = axes
        if any(abs(s - 1.0) > 1e-4 for s in scl):
            issues.append("non-unit scale on %s: %s" % (m['name'], scl))
        e = expected.get(m['name'])
        if e:
            want = b2u(e['local'])
            if max(abs(a - b) for a, b in zip(want, pos)) > 2e-4:
                issues.append("local pivot mismatch %s: fbx %s vs intent %s" % (m['name'], r6(pos), r6(want)))
            if ob is not None:
                wb = ob.matrix_world.translation
                if (Vector(e['world']) - wb).length > 2e-4:
                    issues.append("re-import world pivot mismatch %s: %s vs %s" %
                                  (m['name'], r6(wb), r6(e['world'])))
        if ob is not None:
            node['world_position'] = r6(b2u(ob.matrix_world.translation))
            if ob.type == 'MESH':
                me = ob.data
                me.calc_loop_triangles()
                node['tris'] = len(me.loop_triangles)
                tris_total += node['tris']
                node['materials'] = [s.material.name for s in ob.material_slots if s.material]
                mats_used.update(node['materials'])
                cols = [a.name for a in me.color_attributes]
                node['color_attributes'] = cols
                ngons = sum(1 for poly in me.polygons if poly.loop_total > 4)
                if ngons:
                    issues.append("%d n-gons on %s" % (ngons, m['name']))
                if 'Col' not in cols:
                    col_ok = False
                    issues.append("no Col attribute on " + m['name'])
        else:
            issues.append("node %s not found after re-import" % m['name'])
        hier.append(node)
    bad = [mname for mname in mats_used if not (mname in C.PALETTE)]
    if bad:
        issues.append("non-palette materials: %s" % bad)
    if budget and tris_total > budget:
        issues.append("tri budget exceeded: %d > %d" % (tris_total, budget))
    # bounds (Unity axes) from the re-imported meshes
    mn, mx = C.world_bbox([o for o in objs.values() if o.type == 'MESH'])
    umn = [-mx.x, mn.z, -mx.y]
    umx = [-mn.x, mx.z, -mn.y]
    empties = [dict(name=h['name'], parent=h['parent'], local_position=h['local_position'],
                    world_position=h.get('world_position'),
                    local_rotation_euler=h['local_rotation_euler'],
                    **({'local_axes_unity': h['local_axes_unity']} if 'local_axes_unity' in h else {}))
               for h in hier if h['type'] == 'Empty' and h['name'].split('_')[0] in
               ('ANCHOR', 'SOCKET', 'LIGHT')]
    res.update(root=next((h['name'] for h in hier if h['parent'] is None), None),
               fbx_version=raw['version'], fbx_unit_scale_to_m=raw['unit'],
               tris_total=tris_total, tri_budget=budget,
               materials=sorted(mats_used), vertex_color_attribute="Col" if col_ok else None,
               bounds_unity=dict(min=r6(umn), max=r6(umx), size=r6([b - a for a, b in zip(umn, umx)])),
               hierarchy=hier, empties=empties, ok=not issues, issues=issues)
    return res


def main():
    out = []
    for a in ASSETS:
        r = verify(*a)
        C.log("%-34s %-5s tris=%-6s %s" % (a[0], "OK" if r.get('ok') else "FAIL",
                                         r.get('tris_total'), "; ".join(r.get('issues', []))))
        out.append(r)
    data = dict(
        stream="chars", generated="2026-10-17",
        axes="Unity: x_u = -x_blender, y_u = z_blender, z_u = -y_blender; metres; Y up; +Z forward",
        export="Blender 5.2 FBX, ART_SPEC settings (bake_space_transform=True, -Z forward, Y up, "
               "FBX_SCALE_ALL, colors_type=SRGB); nested-hierarchy matrix bug patched at export "
               "time in chars_common._patch_fbx_exporter",
        vertex_color="Col (soft AO, white = open)",
        licence="Original work for SKYFOLD (Awaiz Ahmed / Team Kanban); procedural Blender 5.2 "
                "scripts; not AI-generated",
        files=out)
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    C.log("manifest", MANIFEST, "all ok" if all(r.get('ok') for r in out) else "ISSUES")


if __name__ == "__main__":
    main()
