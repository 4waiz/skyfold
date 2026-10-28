"""SKYFOLD environment kit - clean-energy infrastructure for the Nacre Bay energy transition.

Original procedural models, built headless like the rest of the kit:
    blender -b --factory-startup -P tools/blender/build_env.py -- build group:energy

Pivot at ground centre unless noted. Fronts face Unity north (+Z) = Blender -Y.
Lot-sized assets keep inside +/-5.8 m so the plot corners stay free for planting (16 m cells).
Gameplay contracts: wind turbines keep their rotor as a separate 'Rotor' object with its pivot at the
hub centre; the game spins it about the turbine's forward (Unity +Z) axis.
"""
from env_common import *
from env_props import cham_rect, ring, rod

ENERGY_AO = dict(ground_z=0.0, dist=1.2, rays=24, strength=0.7, floor=0.48, inset=0.06, power=1.2)
ENERGY_RENDER = dict(az=35.0, el=24.0)

P, IV, T, TL, G, L, M, I, B, C, R, SO, GL, SD, LI = (
    'SKY_Pearl', 'SKY_Ivory', 'SKY_Teal', 'SKY_TealLight', 'SKY_TealGlow', 'SKY_Leaf', 'SKY_Metal', 'SKY_Ink',
    'SKY_Brass', 'SKY_Coral', 'SKY_Rubber', 'SKY_Solar', 'SKY_Glass', 'SKY_SandstoneDeep', 'SKY_Light')


# --------------------------------------------------------------------------- helpers

def pv_panel(mb, w, d, tilt, cx, cy, z_low, strips=8, frame=P):
    """Tilted photovoltaic panel facing Unity south (+Y), low edge at +Y. Cell strips run across it."""
    t = 0.07
    fs = mb.box(-w / 2, w / 2, -d / 2, d / 2, 0.0, t, frame, fm={'top': SO})
    for k in range(1, strips):
        x = -w / 2 + w * k / strips
        fs += mb.box(x - 0.025, x + 0.025, -d / 2 + 0.04, d / 2 - 0.04, t, t + 0.012, frame)
    fs += mb.box(-w / 2 + 0.04, w / 2 - 0.04, -0.02, 0.02, t, t + 0.012, frame)
    zc = z_low + d / 2 * math.sin(math.radians(tilt))
    mb.transform(M_tr(cx, cy, zc) @ M_rot(-tilt, 'X'), fs)
    return zc


def fan_ring(mb, r, depth, center, axis='-Y', blades=3, shroud=I, hub=M):
    """Ducted fan seen through a shroud: annular shroud, hub and flat blades; axis along Blender -Y."""
    fs = ring(mb, r * 0.88, r, 0.0, depth, 20, shroud, ch=0.02)
    fs += mb.cyl(r * 0.22, depth * 0.2, depth * 0.75, 10, hub)
    for k in range(blades):
        ang = 360.0 * k / blades
        bf = mb.box(-0.06 * r * 3, 0.06 * r * 3, r * 0.2, r * 0.82, depth * 0.4, depth * 0.55, hub)
        mb.transform(M_rot(ang, 'Z'), bf)
        fs += bf
    rot = M_rot(90, 'X') if axis == '-Y' else M_rot(-90, 'X')
    mb.transform(M_tr(*center) @ rot, fs)
    return fs


def blade_rings(length, root=0.9):
    """Airfoil sections along +Z (span), chord along X, thickness along Y, with twist."""
    secs = [(root, 0.95, 0.95, 0.0), (2.0, 1.75, 0.78, 14.0), (3.3, 1.9, 0.52, 11.0),
            (length * 0.38, 1.6, 0.33, 8.0), (length * 0.58, 1.22, 0.22, 5.0), (length * 0.78, 0.86, 0.14, 3.0),
            (length - 1.3, 0.56, 0.09, 1.5), (length, 0.24, 0.045, 0.0)]
    rings = []
    for (z, c, th, tw) in secs:
        a = math.radians(tw)
        ca, sa = math.cos(a), math.sin(a)
        pts = []
        for k in range(10):
            u = 2 * math.pi * k / 10
            # rounded leading edge at -X, sharper trailing edge at +X
            x = c * (0.5 * math.cos(u) + (0.12 if math.cos(u) > 0 else 0.0) * math.cos(u) ** 2) - c * 0.12
            y = th * 0.5 * math.sin(u) * (0.75 if math.cos(u) > 0 else 1.0)
            pts.append(Vector((x * ca - y * sa, x * sa + y * ca, z)))
        rings.append(pts)
    mats = [P] * (len(secs) - 2) + [C]
    return rings, mats


def _turbine(a, z0, hub, blade):
    """Three-blade turbine on a tapered tower whose base is at z0. Rotor faces Unity north (-Y)."""
    # tower: pearl taper with a teal band and an ink service door
    mb = MB()
    prof = [(0, z0), (1.34, z0), (1.34, z0 + 0.42), (1.24, z0 + 0.52), (1.16, z0 + 6.0), (0.98, z0 + (hub - z0) * 0.55),
            (0.78, hub - 1.5), (0.0, hub - 1.5)]
    mb.lathe(prof, 24, P)
    ring(mb, 1.13, 1.22, z0 + 2.7, z0 + 3.2, 24, T, ch=0.03)
    ring(mb, 1.12, 1.19, z0 + 3.35, z0 + 3.5, 24, L)
    a.part(mb, name="tower")
    mb = MB()
    mb.box(-0.42, 0.42, -1.3, -1.12, z0 + 0.55, z0 + 2.45, I)
    mb.box(-0.5, 0.5, -1.36, -1.18, z0 + 2.45, z0 + 2.58, T)
    mb.cbox(0.26, -1.33, z0 + 1.5, 0.06, 0.06, 0.18, B)
    mb.box(-0.62, 0.62, -1.9, -1.2, z0 + 0.42, z0 + 0.55, SD)
    a.part(mb, name="door", bevel=0.02)
    # yaw bearing + nacelle
    mb = MB()
    mb.cyl(0.86, hub - 1.55, hub - 1.2, 20, M)
    a.part(mb, name="yaw")
    mb = MB()
    mb.box(-1.15, 1.15, -2.05, 3.3, hub - 1.2, hub + 1.35, P)
    a.part(mb, name="nacelle", bevel=0.42, seg=3)
    mb = MB()
    for sx in (-1, 1):
        mb.box(sx * 1.13, sx * 1.19, -1.6, 2.9, hub + 0.05, hub + 0.32, T)
        mb.box(sx * 1.13, sx * 1.19, -1.6, 2.9, hub - 0.12, hub - 0.02, L)
    for k in range(4):
        y = 1.4 + k * 0.42
        mb.box(-0.7, 0.7, y, y + 0.16, hub + 1.33, hub + 1.48, M)
    rod(mb, [(0.0, 2.9, hub + 1.35), (0.0, 2.9, hub + 2.5)], 0.04, 6, M)
    mb.box(-0.5, 0.5, 2.85, 2.95, hub + 2.45, hub + 2.5, M)
    mb.sphere(0.09, 8, 4, C, c=(0.5, 2.9, hub + 2.56))
    mb.sphere(0.09, 8, 4, C, c=(-0.5, 2.9, hub + 2.56))
    a.part(mb, name="nacelle_trim")
    # rotor: spinner + three twisted blades with coral tips, about the hub centre
    hy, hz = -2.6, hub + 0.12
    mb = MB()
    fs = mb.lathe([(0, 0.0), (1.02, 0.0), (1.06, 0.3), (0.98, 0.95), (0.74, 1.55), (0.38, 2.0), (0, 2.18)], 18, P,
                  mats=[P, T, P, P, P, P])
    mb.transform(M_tr(0, -2.0, hz) @ M_rot(90, 'X'), fs)
    rings, mats = blade_rings(blade)
    for k in range(3):
        bf = mb.loft(rings, P, mats=mats)
        bf += mb.cyl(0.62, 0.55, 1.05, 12, M)
        mb.transform(M_tr(0, hy, hz) @ M_rot(120.0 * k + 30.0, 'Y'), bf)
    a.part(mb, target="Rotor", name="rotor")
    a.set_target("Rotor", pivot=(0, hy, hz), smooth=55.0)


@asset("wind_turbine", "Energy", "energy", ao=dict(ENERGY_AO, dist=3.0),
       render=dict(ENERGY_RENDER, el=14.0))
def wind_turbine(a):
    """Onshore wind turbine, 30 m hub (stylised for the 1:160 diorama): pearl tower with teal and leaf
    bands, service door, bevelled nacelle with cooling fins and a coral-lit anemometer mast, and a separate
    'Rotor' (13.5 m twisted blades, coral tip markings) pivoting at the hub."""
    _turbine(a, 0.0, 30.0, 13.5)


@asset("wind_turbine_offshore", "Energy", "energy", ao=dict(ENERGY_AO, dist=3.0),
       render=dict(ENERGY_RENDER, el=14.0, water=True))
def wind_turbine_offshore(a):
    """Offshore turbine: monopile from the seabed, gold transition piece, railed access platform and boat
    ladder, then the same tower, nacelle and 'Rotor'. Pivot at the sea surface (place at water level)."""
    mb = MB()
    mb.cyl(1.7, -5.0, 0.2, 24, I)
    mb.lathe([(0, 0.2), (1.62, 0.2), (1.62, 3.3), (1.8, 3.4), (0, 3.4)], 24, 'SKY_Gold')
    ring(mb, 1.6, 1.68, 1.3, 1.6, 24, I)
    a.part(mb, name="monopile")
    mb = MB()
    mb.lathe([(0, 3.4), (3.4, 3.4), (3.4, 3.72), (0, 3.72)], 8, M, a0=22.5)
    for k in range(8):
        ang = math.radians(22.5 + 45 * k)
        x, y = 3.25 * math.cos(ang), 3.25 * math.sin(ang)
        rod(mb, [(x, y, 3.72), (x, y, 4.75)], 0.045, 6, 'SKY_Gold')
    ring(mb, 3.18, 3.32, 4.7, 4.8, 8, 'SKY_Gold', a0=22.5)
    for sx in (-0.38, 0.38):
        rod(mb, [(sx, -1.78, -1.0), (sx, -1.78, 3.4)], 0.05, 6, 'SKY_Gold')
    for k in range(9):
        z = -0.6 + k * 0.45
        rod(mb, [(-0.38, -1.78, z), (0.38, -1.78, z)], 0.03, 4, 'SKY_Gold')
    a.part(mb, name="platform")
    _turbine(a, 3.72, 34.0, 14.5)


@asset("solar_array", "Energy", "energy", ao=ENERGY_AO, render=dict(ENERGY_RENDER, el=34.0))
def solar_array(a):
    """Ground-mount solar farm plot: four rows of tilted panels (22 deg, facing south) on galvanised posts,
    with an inverter cabinet whose teal status strip glows."""
    tilt, d, w = 22.0, 2.3, 10.8
    mb = MB()
    for yc in (-4.2, -1.4, 1.4, 4.2):
        pv_panel(mb, w, d, tilt, 0.0, yc, 0.75, strips=10)
    a.part(mb, name="panels")
    mb = MB()
    s, c = math.sin(math.radians(tilt)), math.cos(math.radians(tilt))
    for yc in (-4.2, -1.4, 1.4, 4.2):
        y_lo, y_hi = yc + d / 2 * c * 0.7, yc - d / 2 * c * 0.7
        z_lo, z_hi = 0.75 + d / 2 * (1 - 0.7) * s, 0.75 + d * s * 0.85
        for x in (-4.6, -1.55, 1.55, 4.6):
            mb.box(x - 0.06, x + 0.06, y_lo - 0.06, y_lo + 0.06, 0.0, z_lo, M)
            mb.box(x - 0.06, x + 0.06, y_hi - 0.06, y_hi + 0.06, 0.0, z_hi, M)
            mb.box(x - 0.08, x + 0.08, y_lo - 0.14, y_lo + 0.14, 0.0, 0.12, SD)
            mb.box(x - 0.08, x + 0.08, y_hi - 0.14, y_hi + 0.14, 0.0, 0.12, SD)
    a.part(mb, name="posts")
    mb = MB()
    mb.box(4.7, 5.7, 5.35, 5.85, 0.0, 1.35, P)
    mb.box(4.82, 5.58, 5.3, 5.36, 1.0, 1.12, G)
    mb.box(4.65, 5.75, 5.3, 5.9, 1.35, 1.42, T)
    rod(mb, [(5.2, 5.6, 0.2), (3.8, 5.6, 0.2), (3.8, 4.6, 0.2)], 0.05, 6, R)
    a.part(mb, name="inverter", bevel=0.03)


@asset("solar_canopy", "Energy", "energy", ao=ENERGY_AO, render=dict(ENERGY_RENDER, el=30.0))
def solar_canopy(a):
    """Solar carport over three parking bays: slim pearl columns and a teal beam carrying a gently tilted
    PV roof; painted bay lines and a leaf-green EV bay mark on the ground."""
    mb = MB()
    pv_panel(mb, 11.4, 6.2, 8.0, 0.0, 0.0, 3.35, strips=12)
    a.part(mb, name="roof")
    mb = MB()
    for x in (-4.6, 0.0, 4.6):
        mb.box(x - 0.14, x + 0.14, -1.0, -0.72, 0.0, 3.62, P)
        mb.box(x - 0.32, x + 0.32, -1.18, -0.54, 0.0, 0.12, SD)
    mb.box(-5.4, 5.4, -1.1, -0.62, 3.55, 3.78, T)
    for x in (-4.6, 0.0, 4.6):
        mb.box(x - 0.1, x + 0.1, -2.9, 2.9, 3.5, 3.7, M)
    a.part(mb, name="frame", bevel=0.03)
    mb = MB()
    for x in (-5.4, -1.8, 1.8, 5.4):
        mb.box(x - 0.06, x + 0.06, -2.6, 2.6, 0.0, 0.015, P)
    for x in (-3.6, 0.0, 3.6):
        mb.box(x - 0.55, x + 0.55, 1.2, 1.32, 0.0, 0.015, L)
        mb.box(x - 0.06, x + 0.06, 0.7, 1.8, 0.0, 0.015, L)
    a.part(mb, name="markings")


@asset("battery_storage", "Energy", "energy", ao=ENERGY_AO, render=dict(ENERGY_RENDER, el=28.0))
def battery_storage(a):
    """Grid battery (BESS) yard: three pearl battery containers with teal doors, leaf-green bands and
    glowing status strips, rear cooling units with fans, and a finned ink transformer with brass bushings,
    all on a concrete pad."""
    mb = MB()
    mb.box(-5.6, 5.6, -5.4, 4.6, 0.0, 0.2, SD)
    a.part(mb, name="pad", bevel=0.05)
    mb = MB()
    for x in (-3.6, 0.0, 3.6):
        mb.box(x - 1.2, x + 1.2, -3.4, 2.6, 0.2, 2.85, P, fm={'top': IV})
    a.part(mb, name="containers", bevel=0.06)
    mb = MB()
    for x in (-3.6, 0.0, 3.6):
        for sx in (-1, 1):
            for k in range(3):
                y0 = -3.0 + k * 1.85
                mb.box(x + sx * 1.2, x + sx * 1.24, y0, y0 + 1.6, 0.45, 2.45, T)
            mb.box(x + sx * 1.2, x + sx * 1.25, -3.3, 2.5, 2.55, 2.68, L)
        mb.box(x - 0.9, x + 0.9, -3.44, -3.4, 2.62, 2.72, G)
        mb.box(x - 1.0, x + 1.0, -3.44, -3.4, 0.45, 2.45, T)
        mb.box(x - 0.04, x + 0.04, -3.47, -3.43, 0.45, 2.45, I)
        # rear cooling unit + fan
        mb.box(x - 0.9, x + 0.9, 2.6, 3.25, 0.4, 2.1, M)
    a.part(mb, name="trim", bevel=0.01)
    mb = MB()
    for x in (-3.6, 0.0, 3.6):
        fan_ring(mb, 0.55, 0.12, (x, 3.38, 1.25), axis='+Y')
    a.part(mb, name="fans")
    mb = MB()
    mb.box(3.6, 5.2, -5.1, -3.9, 0.2, 2.0, I)
    for k in range(6):
        y = -5.0 + k * 0.2
        mb.box(5.2, 5.42, y, y + 0.06, 0.4, 1.8, M)
    for k in range(3):
        mb.cyl(0.09, 2.0, 2.55, 8, B, cx=3.95 + k * 0.45, cy=-4.5)
        mb.cyl(0.14, 2.32, 2.4, 8, B, cx=3.95 + k * 0.45, cy=-4.5)
    a.part(mb, name="transformer", bevel=0.02)


@asset("hydrogen_plant", "Energy", "energy", ao=dict(ENERGY_AO, dist=1.6), render=dict(ENERGY_RENDER, el=26.0))
def hydrogen_plant(a):
    """Green-hydrogen works: a pearl electrolyser hall with a solar roof and leaf-green band, two horizontal
    hydrogen tanks on saddles, a tall storage column with ladder and platform, a compressor, a water tank,
    teal pipework on a rack and a coral-tipped vent mast."""
    mb = MB()
    mb.box(-5.6, 0.6, -5.6, 0.0, 0.0, 4.8, P, fm={'top': IV})
    a.part(mb, name="hall", bevel=0.08)
    mb = MB()
    mb.box(-5.66, 0.66, -5.66, 0.06, 4.25, 4.55, L)
    for k in range(4):
        x = -5.0 + k * 1.45
        mb.box(x, x + 1.05, -5.64, -5.6, 1.6, 3.6, GL)
        mb.box(x - 0.06, x + 1.11, -5.66, -5.6, 3.6, 3.7, T)
    mb.box(-0.9, 0.3, -5.66, -5.6, 0.0, 2.6, T)
    mb.box(-0.86, 0.26, -5.68, -5.64, 2.62, 2.72, G)
    a.part(mb, name="hall_trim")
    mb = MB()
    pv_panel(mb, 5.6, 2.3, 18.0, -2.5, -4.1, 4.85, strips=6)
    pv_panel(mb, 5.6, 2.3, 18.0, -2.5, -1.4, 4.85, strips=6)
    a.part(mb, name="roof_pv")
    # horizontal H2 tanks on saddles
    mb = MB()
    tank = [(0, -2.6), (0.62, -2.55), (0.95, -2.32), (1.05, -1.95), (1.05, -0.35), (1.05, 0.35), (1.05, 1.95),
            (0.95, 2.32), (0.62, 2.55), (0, 2.6)]
    for x in (2.3, 4.6):
        fs = mb.lathe(tank, 20, P, mats=[P, P, P, P, L, P, P, P, P])
        mb.transform(M_tr(x, -2.7, 1.6) @ M_rot(90, 'X'), fs)
        for y in (-4.4, -1.0):
            mb.box(x - 0.8, x + 0.8, y - 0.25, y + 0.25, 0.0, 0.9, SD)
    a.part(mb, name="tanks")
    # storage column + ladder + platform
    mb = MB()
    mb.lathe([(0, 0), (1.0, 0), (1.0, 0.3), (0.9, 0.4), (0.9, 6.0), (0.78, 6.5), (0.45, 6.82), (0, 6.9)], 20, P,
             cx=3.4, cy=3.5)
    ring(mb, 0.88, 0.96, 2.4, 2.8, 20, L, cx=3.4, cy=3.5)
    ring(mb, 0.88, 0.95, 5.4, 5.55, 20, T, cx=3.4, cy=3.5)
    a.part(mb, name="column")
    mb = MB()
    for sx in (-0.25, 0.25):
        rod(mb, [(3.4 + sx, 2.48, 0.0), (3.4 + sx, 2.48, 6.0)], 0.035, 5, M)
    for k in range(13):
        z = 0.35 + k * 0.45
        rod(mb, [(3.15, 2.48, z), (3.65, 2.48, z)], 0.025, 4, M)
    ring(mb, 0.92, 1.45, 5.9, 6.0, 20, M, cx=3.4, cy=3.5)
    for k in range(10):
        ang = 2 * math.pi * k / 10
        x, y = 3.4 + 1.4 * math.cos(ang), 3.5 + 1.4 * math.sin(ang)
        rod(mb, [(x, y, 6.0), (x, y, 6.85)], 0.03, 4, M)
    ring(mb, 1.36, 1.44, 6.8, 6.88, 20, 'SKY_Gold', cx=3.4, cy=3.5)
    a.part(mb, name="ladder")
    # compressor, water tank, pipe rack, vent mast
    mb = MB()
    mb.box(-4.0, -1.6, 2.4, 4.4, 0.0, 1.7, M)
    for k in range(5):
        y = 2.6 + k * 0.36
        mb.box(-4.04, -1.56, y, y + 0.14, 1.7, 1.8, I)
    mb.box(-3.96, -3.4, 2.36, 2.4, 0.4, 1.2, G)
    a.part(mb, name="compressor", bevel=0.04)
    mb = MB()
    mb.lathe([(0, 0), (0.85, 0), (0.85, 2.1), (0.7, 2.35), (0, 2.42)], 16, TL, cx=-4.7, cy=0.9)
    ring(mb, 0.84, 0.9, 1.6, 1.75, 16, P, cx=-4.7, cy=0.9)
    a.part(mb, name="water")
    mb = MB()
    for x in (-5.0, -1.8, 1.4, 4.6):
        mb.box(x - 0.08, x + 0.08, 1.05, 1.2, 0.0, 3.3, M)
    mb.box(-5.1, 5.0, 1.0, 1.25, 3.3, 3.4, M)
    rod(mb, [(-5.0, 1.13, 3.55), (5.0, 1.13, 3.55)], 0.12, 8, T)
    rod(mb, [(-5.0, 0.95, 3.5), (2.3, 0.95, 3.5), (2.3, -1.0, 3.5), (2.3, -1.0, 2.7)], 0.09, 8, L)
    rod(mb, [(4.6, 1.13, 3.55), (4.6, -0.7, 3.55), (4.6, -0.7, 2.7)], 0.1, 8, T)
    rod(mb, [(0.6, -2.0, 3.0), (1.2, -2.0, 3.0), (1.2, 0.6, 3.0), (1.2, 0.6, 3.45)], 0.09, 8, T)
    rod(mb, [(3.4, 1.25, 3.55), (3.4, 2.55, 3.55), (3.4, 2.55, 3.0)], 0.1, 8, T)
    rod(mb, [(1.35, -0.6, 0.0), (1.35, -0.6, 8.0)], 0.13, 8, M)
    mb.cyl(0.18, 7.8, 8.1, 8, C, cx=1.35, cy=-0.6)
    a.part(mb, name="pipes")


@asset("ev_charger", "Energy", "energy", ao=dict(ENERGY_AO, dist=0.5, inset=0.03),
       render=dict(ENERGY_RENDER, el=14.0))
def ev_charger(a):
    """EV fast-charging post ~1.6 m: pearl body with a teal cap, glowing teal screen and leaf-green halo,
    a holstered connector and a looped rubber cable, on a sandstone plinth."""
    mb = MB()
    mb.box(-0.32, 0.32, -0.24, 0.24, 0.0, 0.09, SD)
    a.part(mb, name="plinth", bevel=0.02)
    mb = MB()
    mb.box(-0.22, 0.22, -0.14, 0.14, 0.09, 1.52, P)
    a.part(mb, name="body", bevel=0.06, seg=3)
    mb = MB()
    mb.box(-0.24, 0.24, -0.16, 0.16, 1.52, 1.62, T)
    mb.box(-0.13, 0.13, -0.15, -0.14, 1.12, 1.34, G)
    mb.box(-0.2, 0.2, -0.15, -0.14, 0.98, 1.04, L)
    mb.box(-0.2, 0.2, -0.15, -0.14, 1.4, 1.44, L)
    mb.box(0.22, 0.27, -0.06, 0.06, 0.82, 1.06, I)
    mb.box(0.24, 0.32, -0.04, 0.04, 0.92, 1.14, R)
    a.part(mb, name="trim", bevel=0.008)
    mb = MB()
    loop = [Vector((0.24, 0.0, 0.5)), Vector((0.4, -0.05, 0.3)), Vector((0.5, -0.12, 0.22)),
            Vector((0.55, -0.12, 0.45)), Vector((0.45, -0.06, 0.8)), Vector((0.32, 0.0, 0.95))]
    mb.sweep(loop, circle(0.022, 6), R)
    a.part(mb, name="cable")


@asset("dac_unit", "Energy", "energy", ao=ENERGY_AO, render=dict(ENERGY_RENDER, el=22.0))
def dac_unit(a):
    """Direct-air carbon capture unit: a pearl collector bank with eight ducted fans on its north face,
    a leaf-green band, a captured-CO2 storage tank and its pipe, on a concrete pad."""
    mb = MB()
    mb.box(-5.5, 5.5, -3.4, 5.2, 0.0, 0.18, SD)
    a.part(mb, name="pad", bevel=0.04)
    mb = MB()
    mb.box(-4.6, 4.6, -2.6, 0.6, 0.18, 4.0, P, fm={'top': IV})
    a.part(mb, name="body", bevel=0.08)
    mb = MB()
    mb.box(-4.66, 4.66, -2.66, 0.66, 3.55, 3.8, L)
    mb.box(-4.62, 4.62, -2.64, -2.6, 0.4, 0.55, T)
    for k in range(4):
        x = -3.45 + k * 2.3
        mb.box(x - 0.08, x + 0.08, -2.72, -2.6, 0.55, 3.55, T)
    a.part(mb, name="trim")
    mb = MB()
    for k in range(4):
        for row in range(2):
            fan_ring(mb, 0.78, 0.22, (-3.45 + k * 2.3, -2.6, 1.3 + row * 1.6), axis='-Y', blades=4)
    a.part(mb, name="fans")
    mb = MB()
    mb.lathe([(0, 0.18), (1.0, 0.18), (1.0, 3.8), (0.86, 4.25), (0.45, 4.5), (0, 4.55)], 18, P, cx=3.2, cy=3.3)
    ring(mb, 0.98, 1.06, 1.6, 2.0, 18, L, cx=3.2, cy=3.3)
    ring(mb, 0.98, 1.05, 3.1, 3.22, 18, T, cx=3.2, cy=3.3)
    rod(mb, [(2.0, 0.6, 3.2), (2.0, 2.0, 3.2), (2.6, 2.6, 3.2)], 0.12, 8, L)
    mb.box(-4.2, -1.8, 1.4, 3.8, 0.18, 1.6, M)
    mb.box(-4.24, -3.0, 1.36, 1.4, 0.5, 1.2, G)
    a.part(mb, name="tank")
