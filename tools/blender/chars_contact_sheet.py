"""Contact sheet of the character / vehicle stream previews -> source-art/renders/contact_chars.png

Original tooling for SKYFOLD (Awaiz Ahmed / Team Kanban).
    blender -b --factory-startup -P tools/blender/chars_contact_sheet.py
Lays the existing preview PNGs out as emissive image planes with text labels and renders them
through an orthographic camera (Cycles, Standard view transform so colours are unchanged).
"""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chars_common as C

TILES = [
    ("nuri_fl", "NURI  3/4 front-left"), ("nuri_br", "NURI  3/4 back-right"),
    ("nuri_front", "NURI  front (ortho)"), ("nuri_side", "NURI  side (ortho)"),
    ("nuri_back", "NURI  back (ortho)"),
    ("glove_L_fl", "glove_L  Grip (top) / Open"), ("glove_L_br", "glove_L  palm side"),
    ("glove_R_fl", "glove_R  Grip (top) / Open"), ("power_cell_fl", "power_cell"),
    ("courier_car_fl", "courier_car  front-left"), ("courier_car_br", "courier_car  back-right"),
    ("convoy_shuttle_fl", "convoy_shuttle"), ("city_car_a_fl", "city_car_a"),
    ("city_car_b_fl", "city_car_b"),
    ("aircraft_fl", "aircraft  front-left"), ("aircraft_br", "aircraft  back-right"),
    ("passenger_a_fl", "passenger_a (P1)"), ("passenger_b_fl", "passenger_b (P1)"),
    ("passenger_c_fl", "passenger_c (P1)"), ("convoy_shuttle_br", "convoy_shuttle  back-right"),
]
COLS = 5
TW, TH, LAB, PAD, HEAD = 4.8, 3.6, 0.42, 0.12, 0.9     # scene units (1 unit = 100 px)


def emission_mat(name, image=None, color=(1, 1, 1), strength=1.0):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = strength
    if image is not None:
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = image
        tex.interpolation = 'Cubic'
        nt.links.new(tex.outputs['Color'], em.inputs['Color'])
    else:
        em.inputs['Color'].default_value = (*color, 1)
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    return m


def plane(name, cx, cy, w, h, mat, z=0.0):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(cx - w / 2, cy - h / 2, z), (cx + w / 2, cy - h / 2, z),
                    (cx + w / 2, cy + h / 2, z), (cx - w / 2, cy + h / 2, z)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    for i, (u, v) in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[i].uv = (u, v)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    return ob


def text(body, x, y, size, mat, align='LEFT'):
    cu = bpy.data.curves.new("t", 'FONT')
    cu.body = body
    cu.size = size
    cu.align_x = align
    ob = bpy.data.objects.new("t", cu)
    ob.location = (x, y, 0.01)
    bpy.context.scene.collection.objects.link(ob)
    cu.materials.append(mat)
    return ob


def main():
    C.reset_scene()
    sc = bpy.context.scene
    rows = (len(TILES) + COLS - 1) // COLS
    W = COLS * (TW + PAD) + PAD
    H = rows * (TH + LAB + PAD) + PAD + HEAD
    bg = emission_mat("bg", color=(0.075, 0.085, 0.095))
    tile_bg = emission_mat("tile", color=(0.13, 0.14, 0.15))
    ink = emission_mat("label", color=(0.93, 0.90, 0.84))
    teal = emission_mat("title", color=(0.21, 0.88, 0.82))
    plane("BG", W / 2, -H / 2, W * 1.02, H * 1.02, bg, z=-0.02)
    text("SKYFOLD - characters & vehicles stream  (Blender 5.2 previews, original procedural models)",
         PAD, -HEAD * 0.62, 0.34, teal)
    for i, (name, label) in enumerate(TILES):
        path = os.path.join(C.RENDERS, name + ".png")
        r, c = divmod(i, COLS)
        x0 = PAD + c * (TW + PAD)
        y0 = -(HEAD + PAD + r * (TH + LAB + PAD))
        cx, cy = x0 + TW / 2, y0 - TH / 2
        plane("tbg%d" % i, cx, cy, TW, TH, tile_bg, z=-0.01)
        if os.path.exists(path):
            img = bpy.data.images.load(path)
            iw, ih = img.size
            s = min(TW / iw, TH / ih)
            plane("img%d" % i, cx, cy, iw * s, ih * s, emission_mat("m%d" % i, img))
        else:
            label += "  (missing)"
        text(label, x0 + 0.06, y0 - TH - LAB * 0.72, 0.24, ink)
    cd = bpy.data.cameras.new("cam")
    cd.type = 'ORTHO'
    cd.ortho_scale = W
    cam = bpy.data.objects.new("cam", cd)
    cam.location = (W / 2, -H / 2, 10)
    sc.collection.objects.link(cam)
    sc.camera = cam
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = 16
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 0
    sc.render.filter_size = 0.7
    sc.view_settings.view_transform = 'Standard'
    sc.render.resolution_x = int(W * 100)
    sc.render.resolution_y = int(H * 100)
    sc.render.resolution_percentage = 100
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = (d.type == 'OPTIX')
        sc.cycles.device = 'GPU'
    except Exception:
        pass
    C.render_to(os.path.join(C.RENDERS, "contact_chars.png"))


if __name__ == "__main__":
    main()
