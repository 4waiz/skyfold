"""Contact sheet for SKYFOLD environment previews (run with the system Python 3.12 + Pillow).

  python contact_sheet.py                      -> source-art/renders/contact_env.png (all env assets)
  python contact_sheet.py OUT.png a b c --cols 3 --size 420   -> ad-hoc review sheet
"""
import os, sys, json
from PIL import Image, ImageDraw, ImageFont

ROOT = os.environ.get("SKYFOLD_ROOT", os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))
RENDERS = os.path.join(ROOT, "source-art", "renders")

ENV_ORDER = [
    # roads / tiles
    "road_straight", "road_corner", "road_tee", "road_cross", "road_end", "road_plaza", "ground_paving",
    "runway_section", "runway_end", "apron_tile", "bridge_span", "bridge_stub",
    "quay_straight", "quay_corner_outer", "quay_corner_inner",
    # buildings
    "bldg_house_a", "bldg_house_b", "bldg_shoprow", "bldg_tower", "bldg_dome", "bldg_courtyard",
    "bldg_depot", "bldg_substation", "bldg_terminal", "bldg_tower_control", "bldg_hangar",
    # atelier
    "foldstation_kiosk", "atelier_platform", "atelier_pergola", "plinth", "plinth_tray",
    # nature / props
    "palm_date_a", "palm_date_b", "palm_small", "shrub_round", "planter_box", "street_lamp", "bench",
    "bollard", "barrier_coral", "traffic_cone", "runway_beacon", "switch_box", "cell_dock",
    "awning_striped", "shade_sail",
    # P1
    "skyline_ring_piece", "cloud_puff_a", "cloud_puff_b", "cloud_puff_c", "storm_cloud", "rock_sea_a",
    "rock_sea_b", "cliff_headland", "dhow_small", "buoy", "bougainvillea_clump", "fountain_small", "crate_stack",
]


def font(sz):
    for f in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, sz)
        except Exception:
            continue
    return ImageFont.load_default()


def sheet(names, out, cols=6, size=300, title=None):
    names = [n for n in names if os.path.exists(os.path.join(RENDERS, n + ".png"))]
    if not names:
        print("no renders"); return
    rows = (len(names) + cols - 1) // cols
    lab = max(18, size // 14)
    top = 56 if title else 0
    W, Hh = cols * size, rows * (size + lab + 8) + top
    img = Image.new("RGB", (W, Hh), (34, 51, 59))
    d = ImageDraw.Draw(img)
    f = font(lab - 4)
    if title:
        d.text((16, 12), title, fill=(244, 239, 230), font=font(30))
    for i, n in enumerate(names):
        im = Image.open(os.path.join(RENDERS, n + ".png")).convert("RGB")
        im.thumbnail((size, size), Image.LANCZOS)
        x = (i % cols) * size
        y = top + (i // cols) * (size + lab + 8)
        img.paste(im, (x + (size - im.width) // 2, y))
        d.text((x + 8, y + size + 2), n, fill=(244, 239, 230), font=f)
    img.save(out)
    print("wrote", out, img.size)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sheet(ENV_ORDER, os.path.join(RENDERS, "contact_env.png"), cols=6, size=320,
              title="SKYFOLD - Nacre Bay environment kit (original procedural models)")
    else:
        out = args[0]
        cols, size = 3, 420
        names = []
        i = 1
        while i < len(args):
            if args[i] == "--cols":
                cols = int(args[i + 1]); i += 2
            elif args[i] == "--size":
                size = int(args[i + 1]); i += 2
            else:
                names.append(args[i]); i += 1
        sheet(names, out, cols=cols, size=size)
