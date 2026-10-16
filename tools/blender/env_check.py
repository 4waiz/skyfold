"""SKYFOLD environment kit - export verification, manifests and seam test.

  build_env.py -- check   : re-import every env FBX into a fresh scene, validate materials / Col /
                            empties / transforms / dimensions, write source-art/models_manifest_env.json
                            and docs/manifest/art_env.md
  build_env.py -- seam    : import road tiles side by side and render a seam test
"""
import bpy, os, json, math, time
from mathutils import Vector, Matrix
import env_common as C

MANIFEST_JSON = os.path.join(C.ROOT, "source-art", "models_manifest_env.json")
MANIFEST_MD = os.path.join(C.ROOT, "docs", "manifest", "art_env.md")
SCRIPT_FOR = {
    "env_tiles": "tools/blender/env_tiles.py", "env_buildings": "tools/blender/env_buildings.py",
    "env_atelier": "tools/blender/env_atelier.py", "env_props": "tools/blender/env_props.py",
    "env_nature": "tools/blender/env_nature.py", "env_sky": "tools/blender/env_sky.py",
}
WHERE_USED = {
    "Roads": "Full-scale city grid and the 1:160 miniature (module/socket tiles, quays, bridge socket)",
    "Buildings": "Full-scale city blocks and the 1:160 miniature",
    "Atelier": "Fold Atelier terrace and street Fold Stations",
    "Props": "Street dressing and gameplay props (beacons, switch, cell dock)",
    "Nature": "Street and courtyard greenery, atelier dressing",
    "Sky": "Sky dome dressing, storm and horizon",
}
EXPECTED = {
    "bridge_span": ["LIGHT_lantern_0", "LIGHT_lantern_1", "LIGHT_lantern_2", "LIGHT_lantern_3"],
    "bldg_depot": ["ANCHOR_cell_dock"],
    "bldg_substation": ["SOCKET_cell", "PowerLights"],
    "bldg_terminal": ["ANCHOR_convoy_stop"],
    "bldg_tower_control": ["ANCHOR_lever"],
    "foldstation_kiosk": ["LensRing", "ANCHOR_player"],
    "plinth": ["PlinthRim", "ANCHOR_minicity", "ANCHOR_player"],
    "plinth_tray": ["SOCKET_slot_1", "SOCKET_slot_6"],
    "runway_beacon": ["Lens", "LIGHT_beacon"],
    "switch_box": ["Lever"],
    "cell_dock": ["SOCKET_cell"],
    "street_lamp": ["LIGHT_lamp"],
}


def to_unity(v):
    return [round(-v[0], 4) + 0.0, round(v[2], 4) + 0.0, round(-v[1], 4) + 0.0]


def bounds_unity(lo, hi):
    a = to_unity(lo); b = to_unity(hi)
    return {"min": [min(a[i], b[i]) for i in range(3)], "max": [max(a[i], b[i]) for i in range(3)]}


def module_of(name):
    fn = C.REGISTRY[name]['fn']
    return fn.__module__


def check_one(name, info):
    path = os.path.join(C.MODEL_DIR, info['category'], name + ".fbx")
    rec = dict(file=os.path.relpath(path, C.ROOT).replace("\\", "/"), name=name, category=info['category'])
    issues = []
    if not os.path.exists(path):
        rec['issues'] = ["missing file"]
        return rec
    C.reset_scene()
    # bake_space_transform bakes the FBX Y-up -> Blender Z-up conversion into the mesh data, so any
    # remaining object rotation/scale would be a real (un-applied) transform stored in the file.
    bpy.ops.import_scene.fbx(filepath=path, bake_space_transform=True)
    objs = list(bpy.context.scene.objects)
    meshes = [o for o in objs if o.type == 'MESH']
    empties = [o for o in objs if o.type == 'EMPTY']
    rec['objects'] = []
    tris = 0
    lo = Vector((1e9, 1e9, 1e9)); hi = Vector((-1e9, -1e9, -1e9))
    mats = set()
    for o in objs:
        entry = dict(name=o.name, type=o.type)
        loc, rot, sca = o.matrix_world.decompose()
        e = rot.to_euler()
        entry['position_unity'] = to_unity(loc)
        if max(abs(e.x), abs(e.y), abs(e.z)) > 1e-3 and not (o.type == 'EMPTY'):
            issues.append(f"{o.name}: rotation not applied {tuple(round(math.degrees(x), 2) for x in e)}")
        if max(abs(s - 1.0) for s in sca) > 1e-3:
            issues.append(f"{o.name}: scale not applied {tuple(round(x, 4) for x in sca)}")
        if o.type == 'EMPTY':
            entry['yaw_deg_blender'] = round(math.degrees(e.z), 2)
        if o.type == 'MESH':
            me = o.data
            me.calc_loop_triangles()
            nt = len(me.loop_triangles)
            tris += nt
            entry['tris'] = nt
            cols = [ca.name for ca in me.color_attributes]
            entry['color_attributes'] = cols
            if "Col" not in cols:
                issues.append(f"{o.name}: no 'Col' colour attribute (found {cols})")
            ms = [m.name for m in me.materials if m]
            entry['materials'] = ms
            for m in ms:
                base = m.split(".")[0]
                if base not in C.PALETTE:
                    issues.append(f"{o.name}: non-palette material {m}")
                mats.add(base)
            if o.name != name and loc.length > 1e-4 and o.name not in ("LensRing", "Lens", "Lever"):
                pass
            for c in o.bound_box:
                w = o.matrix_world @ Vector(c)
                lo = Vector((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
                hi = Vector((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))
        rec['objects'].append(entry)
    names = [o.name for o in objs]
    if name not in names:
        issues.append(f"main object '{name}' missing (found {names})")
    for req in EXPECTED.get(name, []):
        if req not in names:
            issues.append(f"expected object {req} missing")
    rec['tris'] = tris
    rec['materials'] = sorted(mats)
    rec['bounds_unity'] = bounds_unity(lo, hi)
    size = hi - lo
    rec['size_m'] = [round(size.x, 3), round(size.z, 3), round(size.y, 3)]   # Unity x, y, z extents
    rec['empties'] = [dict(name=o.name, position_unity=to_unity(o.matrix_world.translation),
                           yaw_unity_deg=round(-math.degrees(o.matrix_world.to_euler().z), 2) + 0.0)
                      for o in empties]
    # sanity: pivot / footprint per category
    if info['group'] in ('roads', 'runway'):
        if abs(size.x - 16) > 0.05 or abs(size.y - 16) > 0.05:
            issues.append(f"tile footprint {size.x:.2f} x {size.y:.2f} != 16 x 16")
        if abs(hi.z - 0.15) > 0.05 and abs(hi.z) > 0.05:
            pass
    if info['group'] in ('buildings',):
        if size.x > 12.3 or size.y > 12.3:
            issues.append(f"building footprint {size.x:.2f} x {size.y:.2f} exceeds 12 m")
    if lo.z < -0.06 and info['group'] not in ('roads', 'runway', 'quays', 'bridges', 'p1', 'atelier', 'sky')             and name not in ('awning_striped',):
        issues.append(f"geometry below ground: min z {lo.z:.3f}")
    rec['issues'] = issues
    rec['module'] = module_of(name)
    return rec


def write_md(records):
    lines = ["# Art manifest - environment (Nacre Bay kit)", "",
             "All entries are original procedural models generated by Blender 5.2 Python scripts in "
             "`tools/blender/` (run `blender -b --factory-startup -P tools/blender/build_env.py -- build all`). "
             "No external assets, textures, scans or AI generation were used. Materials use the shared "
             "`SKY_*` palette names from `docs/ART_SPEC.md`; vertex colour attribute `Col` holds a soft AO bake.",
             "", "Axes: Unity north (+Z) = Blender -Y, Unity east (+X) = Blender -X. Empty positions and bounds "
             "below are in Unity axes (metres).", "",
             "| Filename | Source / provider | Licence | Date | Modifications | AI status | Prompt / script | Where used |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in records:
        script = SCRIPT_FOR.get(r.get('module', ''), "tools/blender/")
        mods = "Built from script; bevels, AO vertex colours (Col), triangulated n-gons"
        if r.get('notes'):
            mods += "; " + " ".join(r['notes'])
        lines.append(f"| `{r['file']}` | Original procedural model, Blender 5.2 script {script} | "
                     f"Original work for SKYFOLD (Awaiz Ahmed / Team Kanban) | 2026-10-17 | {mods} | "
                     f"Not AI-generated (procedural script) | `build_env.py -- build {r['name']}` | "
                     f"{WHERE_USED.get(r['category'], '')} |")
    lines += ["", "## Gameplay empties (Unity axes)", "", "| File | Empty / part | Position (x, y, z) | Yaw |",
              "| --- | --- | --- | --- |"]
    for r in records:
        for e in r.get('empties', []):
            lines.append(f"| {r['name']} | {e['name']} | {tuple(e['position_unity'])} | {e['yaw_unity_deg']} |")
        for o in r.get('objects', []):
            if o['type'] == 'MESH' and o['name'] != r['name']:
                lines.append(f"| {r['name']} | {o['name']} (separate mesh, pivot) | {tuple(o['position_unity'])} | 0 |")
    os.makedirs(os.path.dirname(MANIFEST_MD), exist_ok=True)
    open(MANIFEST_MD, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")


def cmd_check(args):
    log_path = os.environ.get("SKY_ENV_LOG", "")
    notes = {}
    if log_path and os.path.exists(log_path):
        try:
            for k, v in json.load(open(log_path)).items():
                notes[k] = v.get('notes', [])
        except Exception:
            pass
    records = []
    t0 = time.time()
    for name, info in C.REGISTRY.items():
        rec = check_one(name, info)
        rec['notes'] = notes.get(name, [])
        records.append(rec)
        flag = "OK " if not rec['issues'] else "BAD"
        print(f"[{flag}] {name:<22} {rec.get('tris', 0):>6} tris  size(u) {rec.get('size_m')}  "
              f"{'; '.join(rec['issues'])}")
    out = dict(generated="2026-10-17", tool="Blender 5.2 (headless), tools/blender/build_env.py",
               axes="Unity: x=-x_blender, y=z_blender, z=-y_blender",
               files=[{k: v for k, v in r.items() if k not in ('module',)} for r in records])
    os.makedirs(os.path.dirname(MANIFEST_JSON), exist_ok=True)
    json.dump(out, open(MANIFEST_JSON, "w"), indent=1)
    write_md(records)
    bad = [r['name'] for r in records if r['issues']]
    print(f"checked {len(records)} files in {time.time() - t0:.1f}s; issues in: {bad}")


def _import(name, cat, loc=(0, 0, 0), rot=0.0):
    path = os.path.join(C.MODEL_DIR, cat, name + ".fbx")
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.fbx(filepath=path, bake_space_transform=True)
    new = [o for o in bpy.context.scene.objects if o not in before]
    M = Matrix.Translation(loc) @ Matrix.Rotation(math.radians(rot), 4, 'Z')
    for o in new:
        o.matrix_world = M @ o.matrix_world
    return new


def cmd_seam(args):
    C.reset_scene()
    objs = []
    lay = [("road_cross", 0, 0, 0), ("road_straight", 0, -16, 0), ("road_straight", 0, 16, 0),
           ("road_straight", -16, 0, 90), ("road_tee", 16, 0, 0), ("road_corner", 16, -16, 180),
           ("road_end", 0, -32, 180), ("ground_paving", -16, -16, 0), ("road_plaza", -16, 16, 0),
           ("road_corner", 16, 16, 90), ("ground_paving", 16, -32, 0), ("road_straight", -16, -32, 90)]
    for (n, x, y, r) in lay:
        objs += _import(n, "Roads", (x, y, 0), r)
    meshes = [o for o in objs if o.type == 'MESH']
    C.render_preview(meshes, os.path.join(C.RENDER_DIR, "seam_test_roads.png"), az=25.0, el=48.0, res=1200,
                     samples=96, ground_z=-0.31)
    # close-up of two junction seams
    C.render_preview(meshes, os.path.join(C.RENDER_DIR, "seam_test_closeup.png"), az=20.0, el=35.0, res=900,
                     samples=96, ground_z=-0.31, target=(4.0, -8.0, 0.0), lens=50.0, dist=14.0)
