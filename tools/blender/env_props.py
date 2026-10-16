"""SKYFOLD environment kit - street and airfield props (< 500 tris each).

Pivot at ground centre unless noted. Fronts face Unity north (+Z) = Blender -Y.
"""
from env_common import *
from env_buildings import sail_quad, fbox

PROP_AO = dict(ground_z=0.0, dist=0.5, rays=24, strength=0.75, floor=0.45, inset=0.04)
PROP_RENDER = dict(az=35.0, el=22.0)


def stripe_lathe(mb, prof, seg, mats, cx=0.0, cy=0.0, a0=0.0):
    mb.lathe(prof, seg, mats[0], mats=mats, cx=cx, cy=cy, a0=a0)


@asset("street_lamp", "Props", "props", ao=PROP_AO, render=dict(PROP_RENDER, el=12.0))
def street_lamp(a):
    """5 m pearl-and-brass street lantern on a crook arm; lamp glass uses SKY_Light. LIGHT_lamp at the lantern."""
    mb = MB()
    mb.lathe([(0, 0), (0.24, 0), (0.24, 0.12), (0.19, 0.18), (0.19, 0.55), (0.13, 0.62), (0.0, 0.62)], 8, 'SKY_Pearl',
             a0=22.5)
    a.part(mb, bevel=0.012, seg=1, name="base")
    mb = MB()
    mb.lathe([(0, 0.62), (0.075, 0.62), (0.055, 4.25), (0.0, 4.25)], 8, 'SKY_Brass', a0=22.5)
    for z in (1.4, 3.1):
        mb.lathe([(0, z), (0.085, z), (0.085, z + 0.07), (0, z + 0.07)], 8, 'SKY_Brass', a0=22.5)
    # crook arm toward Unity north (Blender -Y)
    path = [(0, 0, 4.15)] + [(0, -0.42 * math.sin(math.radians(t)), 4.15 + 0.45 * (1 - math.cos(math.radians(t))) * 0.9)
                             for t in range(30, 181, 30)]
    path = [Vector((0, 0, 4.15)), Vector((0, -0.18, 4.5)), Vector((0, -0.48, 4.66)), Vector((0, -0.78, 4.6)),
            Vector((0, -0.92, 4.42))]
    mb.sweep(path, circle(0.035, 6), 'SKY_Brass')
    mb.sphere(0.07, 6, 3, 'SKY_Brass', c=(0, 0, 4.3))
    a.part(mb, name="pole")
    # lantern hanging from the arm end
    lx, ly = 0.0, -0.92
    mb = MB()
    mb.lathe([(0, 4.36), (0.05, 4.36), (0.05, 4.3), (0.2, 4.24), (0.22, 4.18), (0.0, 4.18)], 6, 'SKY_Brass', cx=lx, cy=ly)
    mb.lathe([(0, 3.8), (0.17, 3.8), (0.14, 3.72), (0.05, 3.66), (0, 3.64)], 6, 'SKY_Brass', cx=lx, cy=ly)
    a.part(mb, name="lantern_frame")
    mb = MB()
    mb.lathe([(0, 3.8), (0.15, 3.8), (0.19, 4.18), (0, 4.18)], 6, 'SKY_Light', cx=lx, cy=ly)
    a.part(mb, name="lamp")
    a.empty("LIGHT_lamp", (lx, ly, 3.98))


@asset("bench", "Props", "props", ao=PROP_AO, render=PROP_RENDER)
def bench(a):
    """2 m stone-and-timber bench (backless), long axis along Unity X."""
    mb = MB()
    for x in (-0.75, 0.75):
        mb.box(x - 0.11, x + 0.11, -0.22, 0.22, 0.0, 0.38, 'SKY_Pearl')
    a.part(mb, bevel=0.02, seg=1, name="legs")
    mb = MB()
    for x in (-0.75, 0.75):
        mb.box(x - 0.14, x + 0.14, -0.25, 0.25, 0.0, 0.06, 'SKY_SandstoneDeep')
    a.part(mb, bevel=0.01, seg=1, name="feet")
    mb = MB()
    for i in range(4):
        y = -0.21 + i * 0.14
        mb.box(-1.0, 1.0, y - 0.055, y + 0.055, 0.38, 0.45, 'SKY_Wood')
    a.part(mb, bevel=0.012, seg=1, name="slats")
    mb = MB()
    for x in (-0.75, 0.75):
        mb.box(x - 0.13, x + 0.13, -0.26, 0.26, 0.355, 0.38, 'SKY_Brass')
    a.part(mb, name="brackets")


@asset("bollard", "Props", "props", ao=PROP_AO, render=PROP_RENDER)
def bollard(a):
    """0.9 m pearl street bollard with a brass band."""
    mb = MB()
    mb.lathe([(0, 0), (0.15, 0), (0.15, 0.08), (0.12, 0.12), (0.12, 0.72), (0.14, 0.76), (0.11, 0.86), (0.05, 0.9),
              (0, 0.91)], 10, 'SKY_Pearl')
    a.part(mb, name="body")
    mb = MB()
    mb.lathe([(0, 0.6), (0.127, 0.6), (0.127, 0.67), (0, 0.67)], 10, 'SKY_Brass')
    a.part(mb, name="band")


@asset("barrier_coral", "Props", "props", ao=PROP_AO, render=PROP_RENDER)
def barrier_coral(a):
    """2 m road barrier: coral/pearl striped beam on pearl A-frame legs with ink feet."""
    from env_tiles import striped_beam_x
    mb = MB()
    striped_beam_x(mb, -1.0, 1.0, -0.06, 0.06, 0.7, 1.0, 8, ['SKY_Coral', 'SKY_Pearl'])
    striped_beam_x(mb, -0.9, 0.9, -0.05, 0.05, 0.32, 0.5, 7, ['SKY_Pearl', 'SKY_Coral'])
    a.part(mb, name="beams")
    mb = MB()
    for x in (-0.82, 0.82):
        for s in (-1, 1):
            p0 = Vector((x, s * 0.32, 0.06)); p1 = Vector((x, s * 0.04, 1.02))
            mb.sweep([p0, p1], [(-0.04, -0.03), (0.04, -0.03), (0.04, 0.03), (-0.04, 0.03)], 'SKY_Pearl')
    a.part(mb, name="legs")
    mb = MB()
    for x in (-0.82, 0.82):
        mb.box(x - 0.09, x + 0.09, -0.4, 0.4, 0.0, 0.07, 'SKY_Ink')
    a.part(mb, bevel=0.01, seg=1, name="feet")
    mb = MB()
    mb.cyl(0.06, 1.0, 1.12, 8, 'SKY_Light', cx=-0.82)
    a.part(mb, name="warning_lamp")


@asset("traffic_cone", "Props", "props", ao=PROP_AO, render=PROP_RENDER)
def traffic_cone(a):
    mb = MB()
    mb.box(-0.21, 0.21, -0.21, 0.21, 0.0, 0.04, 'SKY_Ink')
    a.part(mb, bevel=0.012, seg=1, name="base")
    mb = MB()
    prof = [(0, 0.04), (0.17, 0.04), (0.145, 0.2), (0.12, 0.3), (0.095, 0.42), (0.04, 0.68), (0.0, 0.7)]
    mb.lathe(prof, 12, 'SKY_Coral', mats=['SKY_Coral', 'SKY_Coral', 'SKY_Pearl', 'SKY_Coral', 'SKY_Coral', 'SKY_Coral'])
    a.part(mb, name="cone")


@asset("runway_beacon", "Props", "props", ao=PROP_AO, render=dict(PROP_RENDER, el=26.0))
def runway_beacon(a):
    """Low runway edge light: frangible post on a base plate, separate 'Lens' object (pivot at lens centre)."""
    mb = MB()
    mb.lathe([(0, 0), (0.2, 0), (0.2, 0.05), (0.08, 0.08), (0, 0.08)], 10, 'SKY_Ink')
    a.part(mb, name="plate")
    mb = MB()
    mb.lathe([(0, 0.08), (0.04, 0.08), (0.035, 0.3), (0.0, 0.3)], 8, 'SKY_Metal')
    mb.lathe([(0, 0.14), (0.05, 0.14), (0.05, 0.17), (0, 0.17)], 8, 'SKY_Coral')
    mb.lathe([(0, 0.29), (0.1, 0.29), (0.1, 0.34), (0, 0.34)], 10, 'SKY_Brass')
    a.part(mb, name="post")
    mb = MB()
    mb.lathe([(0, 0.34), (0.085, 0.34), (0.085, 0.4), (0.06, 0.45), (0.0, 0.47)], 10, 'SKY_Light')
    a.part(mb, target="Lens", name="lens")
    a.set_target("Lens", pivot=(0, 0, 0.4))
    a.empty("LIGHT_beacon", (0, 0, 0.42))


@asset("switch_box", "Props", "props", ao=PROP_AO, render=dict(PROP_RENDER, el=16.0))
def switch_box(a):
    """Beacon switch pedestal ~1.1 m. 'Lever' is a separate object pivoting at its hinge on the north
    face; modelled UP (= off). Rotate about the lever's local X (+90 deg in Unity Euler swings it toward
    Unity north / down) for ON."""
    mb = MB()
    mb.prism(rrect(0.56, 0.44, 0.07, 3), 0.0, 0.08, 'SKY_SandstoneDeep')
    a.part(mb, bevel=0.01, seg=1, name="foot")
    mb = MB()
    mb.prism(rrect(0.42, 0.32, 0.06, 3), 0.08, 1.0, 'SKY_Pearl')
    a.part(mb, bevel=0.015, seg=1, name="body")
    mb = MB()
    mb.prism(rrect(0.48, 0.38, 0.07, 3), 1.0, 1.08, 'SKY_Brass')
    a.part(mb, bevel=0.008, seg=1, name="cap")
    mb = MB()
    mb.box(-0.15, 0.15, -0.17, -0.155, 0.55, 0.92, 'SKY_Teal')
    for k in range(3):
        z0 = 0.2 + k * 0.08
        mb.box(-0.15, 0.15, -0.165, -0.155, z0, z0 + 0.04, 'SKY_Coral')
    a.part(mb, name="panel")
    mb = MB()
    mb.box(-0.06, 0.06, -0.21, -0.16, 0.66, 0.78, 'SKY_Brass')
    a.part(mb, bevel=0.006, seg=1, name="hinge_block")
    hz, hy = 0.72, -0.235
    mb = MB()

    mb.sweep([Vector((-0.07, hy, hz)), Vector((0.07, hy, hz))], circle(0.028, 6), 'SKY_Brass')
    mb.sweep([Vector((0, hy, hz)), Vector((0, hy, hz + 0.32))], circle(0.018, 6), 'SKY_Brass')
    mb.sphere(0.045, 8, 4, 'SKY_Coral', c=(0, hy, hz + 0.36))
    a.part(mb, target="Lever", name="lever")
    a.set_target("Lever", pivot=(0, hy, hz))
    a.notes.append("Lever pivot = hinge (Blender (0,-0.235,0.72)); modelled up = OFF.")


@asset("cell_dock", "Props", "props", ao=PROP_AO, render=dict(PROP_RENDER, el=24.0))
def cell_dock(a):
    """Power-cell charging dock 0.6 m tall: pearl pedestal, brass/teal cradle, glow ring.
    SOCKET_cell at the seat point (cradle floor centre)."""
    mb = MB()
    mb.lathe([(0, 0), (0.3, 0), (0.3, 0.06), (0.24, 0.1), (0.2, 0.36), (0.24, 0.4), (0, 0.4)], 12, 'SKY_Pearl')
    a.part(mb, bevel=0.01, seg=1, name="pedestal")
    mb = MB()
    mb.lathe([(0, 0.4), (0.2, 0.4), (0.2, 0.44), (0, 0.44)], 12, 'SKY_Brass')
    a.part(mb, name="seat")
    mb = MB()
    mb.lathe([(0.17, 0.44), (0.21, 0.44), (0.21, 0.6), (0.19, 0.6), (0.19, 0.46), (0.17, 0.46)], 12, 'SKY_Teal',
             closed=True)
    a.part(mb, name="cradle")
    mb = MB()
    mb.lathe([(0.205, 0.5), (0.218, 0.5), (0.218, 0.53), (0.205, 0.53)], 12, 'SKY_TealGlow', closed=True)
    mb.lathe([(0.195, 0.22), (0.212, 0.22), (0.212, 0.25), (0.195, 0.25)], 12, 'SKY_TealGlow', closed=True)
    a.part(mb, name="glow")
    a.empty("SOCKET_cell", (0.0, 0.0, 0.44))


@asset("awning_striped", "Props", "props", ao=PROP_AO, render=dict(PROP_RENDER, el=20.0))
def awning_striped(a):
    """Wall-mounted striped awning 2.4 m wide. Pivot = wall attachment (top back edge centre);
    projects toward Unity north (Blender -Y) and slopes down."""
    w, depth, drop, val, t = 2.4, 1.1, 0.5, 0.28, 0.035
    prof = [(0.0, 0.0), (depth, -drop), (depth, -drop - val), (depth - t, -drop - val), (depth - t, -drop - t),
            (0.0, -t)]
    mb = MB()
    n = 8
    for i in range(n):
        x0 = -w / 2 + w * i / n
        x1 = -w / 2 + w * (i + 1) / n
        mb.prism_frame(prof, (0, 0, 0), (0, -1, 0), (0, 0, 1), (1, 0, 0), x0, x1,
                       'SKY_Coral' if i % 2 == 0 else 'SKY_Pearl')
    a.part(mb, name="canvas")
    mb = MB()
    mb.box(-w / 2 - 0.04, w / 2 + 0.04, -0.06, 0.0, -0.06, 0.06, 'SKY_Brass')
    for s in (-1, 1):
        mb.sweep([Vector((s * (w / 2 - 0.05), 0.0, -0.55)), Vector((s * (w / 2 - 0.05), -depth + 0.06, -drop - 0.02))],
                 circle(0.018, 5), 'SKY_Brass')
    a.part(mb, name="rail")


@asset("shade_sail", "Props", "props", ao=dict(PROP_AO, dist=0.8), render=dict(PROP_RENDER, el=28.0))
def shade_sail(a):
    """Free-standing triangular shade sail (~4.6 m span) on three brass masts with pearl footings."""
    pts = [(-2.3, -1.3, 3.2), (2.3, -1.3, 2.7), (0.0, 2.6, 3.4)]
    mb = MB(); mbf = MB()
    for (x, y, z) in pts:
        mb.cyl(0.055, 0.0, z + 0.25, 6, 'SKY_Brass', cx=x * 1.06, cy=y * 1.06)
        mb.sphere(0.07, 6, 3, 'SKY_Brass', c=(x * 1.06, y * 1.06, z + 0.3))
        mbf.lathe([(0, 0), (0.2, 0), (0.17, 0.22), (0, 0.22)], 8, 'SKY_Pearl', cx=x * 1.06, cy=y * 1.06)
    a.part(mb, name="masts")
    a.part(mbf, name="footings")
    sail_quad(a, pts, sag=0.25, n=5)


@asset("planter_box", "Props", "props", ao=PROP_AO, render=PROP_RENDER)
def planter_box(a):
    """Stone planter 1.2 x 0.6 x 0.55 m with a clipped shrub."""
    mb = MB()
    mb.box(-0.6, 0.6, -0.3, 0.3, 0.0, 0.5, 'SKY_Sandstone')
    a.part(mb, bevel=0.025, seg=1, name="box")
    mb = MB()
    mb.box(-0.64, 0.64, -0.34, 0.34, 0.5, 0.56, 'SKY_Pearl')
    mb.box(-0.62, 0.62, -0.32, 0.32, 0.0, 0.07, 'SKY_SandstoneDeep')
    a.part(mb, bevel=0.012, seg=1, name="trims")
    mb = MB()
    for (x, r) in ((-0.32, 0.3), (0.0, 0.36), (0.32, 0.3)):
        mb.sphere(r, 8, 5, 'SKY_PalmLeaf', c=(x, 0.0, 0.5 + r * 0.55), sz=0.85)
    a.part(mb, name="shrub")
