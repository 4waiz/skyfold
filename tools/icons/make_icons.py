"""Draws the SKYFOLD app icons (base emblem + laptop / VR headset badges).

Usage: python tools/icons/make_icons.py <out_dir>
Writes skyfold_icon.png (1024), skyfold_desktop.ico, skyfold_vr.ico, skyfold_demo.ico and PNG previews.
Original artwork for SKYFOLD (Awaiz Ahmed / Team Kanban); drawn procedurally, not AI-generated.
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

S = 4096  # supersampled canvas, downsampled to 1024 for clean anti-aliasing
PEARL = (244, 239, 230, 255)
SAND = (217, 185, 140, 255)
SAND_DEEP = (196, 154, 108, 255)
TEAL = (15, 111, 115, 255)
TEAL_DARK = (9, 70, 76, 255)
TEAL_GLOW = (53, 224, 208, 255)
GOLD = (217, 164, 65, 255)
INK = (34, 51, 59, 255)
CORAL = (242, 113, 75, 255)


def P(x, y):
    return (x * S, y * S)


def rounded_tile(img):
    d = ImageDraw.Draw(img)
    r = int(0.2 * S)
    # vertical teal gradient inside a rounded square
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / S
        c = tuple(int(TEAL[i] * (1 - t) + TEAL_DARK[i] * t) for i in range(3)) + (255,)
        gd.line([(0, y), (S, y)], fill=c)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([int(0.04 * S), int(0.04 * S), int(0.96 * S), int(0.96 * S)], r, fill=255)
    img.paste(grad, (0, 0), mask)
    # pearl inner hairline
    d.rounded_rectangle([int(0.07 * S), int(0.07 * S), int(0.93 * S), int(0.93 * S)], int(0.17 * S), outline=(244, 239, 230, 70), width=int(0.008 * S))


def emblem(img, scale=1.0, ox=0.0, oy=0.0):
    d = ImageDraw.Draw(img)

    def Q(x, y):
        return P(ox + 0.5 + (x - 0.5) * scale, oy + 0.5 + (y - 0.5) * scale)

    # Warm sun disc behind the wing.
    cx, cy = Q(0.62, 0.36)
    rr = 0.13 * S * scale
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(242, 190, 120, 255))
    # Miniature city skyline on a plinth.
    d.rounded_rectangle([*Q(0.2, 0.74), *Q(0.8, 0.8)], int(0.012 * S * scale), fill=PEARL)
    blocks = [(0.24, 0.62, 0.32), (0.33, 0.57, 0.41), (0.42, 0.65, 0.49), (0.5, 0.53, 0.56), (0.57, 0.6, 0.66), (0.67, 0.66, 0.76)]
    for i, (x0, y0, x1) in enumerate(blocks):
        d.rectangle([*Q(x0, y0), *Q(x1, 0.745)], fill=SAND if i % 2 == 0 else SAND_DEEP)
        d.rectangle([*Q(x0, y0), *Q(x1, y0 + 0.018)], fill=PEARL)
    # small dome
    dx0, dy0 = Q(0.5, 0.49)
    dx1, dy1 = Q(0.56, 0.57)
    d.pieslice([dx0, dy0, dx1, dy1 + (dy1 - dy0)], 180, 360, fill=PEARL)
    # teal canal line
    d.rectangle([*Q(0.2, 0.705), *Q(0.8, 0.72)], fill=TEAL_GLOW)
    # Folded paper wing / last flight (two facets and a gold fold line).
    wing_top = [Q(0.17, 0.47), Q(0.83, 0.2), Q(0.5, 0.44)]
    wing_low = [Q(0.17, 0.47), Q(0.5, 0.44), Q(0.42, 0.56)]
    d.polygon(wing_top, fill=PEARL)
    d.polygon(wing_low, fill=(222, 214, 200, 255))
    d.line([Q(0.17, 0.47), Q(0.5, 0.44)], fill=GOLD, width=int(0.016 * S * scale))
    d.line([Q(0.5, 0.44), Q(0.83, 0.2)], fill=GOLD, width=int(0.008 * S * scale))


def laptop_badge(img):
    d = ImageDraw.Draw(img)
    cx, cy, r = 0.76 * S, 0.76 * S, 0.2 * S
    d.ellipse([cx - r - 0.02 * S, cy - r - 0.02 * S, cx + r + 0.02 * S, cy + r + 0.02 * S], fill=TEAL_DARK)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PEARL)
    # screen
    d.rounded_rectangle([cx - 0.11 * S, cy - 0.095 * S, cx + 0.11 * S, cy + 0.045 * S], int(0.015 * S), fill=INK)
    d.rectangle([cx - 0.09 * S, cy - 0.077 * S, cx + 0.09 * S, cy + 0.027 * S], fill=TEAL)
    # base
    d.polygon([(cx - 0.145 * S, cy + 0.07 * S), (cx + 0.145 * S, cy + 0.07 * S), (cx + 0.12 * S, cy + 0.1 * S), (cx - 0.12 * S, cy + 0.1 * S)], fill=INK)


def vr_badge(img):
    d = ImageDraw.Draw(img)
    cx, cy, r = 0.76 * S, 0.76 * S, 0.2 * S
    d.ellipse([cx - r - 0.02 * S, cy - r - 0.02 * S, cx + r + 0.02 * S, cy + r + 0.02 * S], fill=TEAL_DARK)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PEARL)
    # headset body
    d.rounded_rectangle([cx - 0.13 * S, cy - 0.07 * S, cx + 0.13 * S, cy + 0.06 * S], int(0.05 * S), fill=INK)
    # strap stubs
    d.rectangle([cx - 0.155 * S, cy - 0.025 * S, cx - 0.125 * S, cy + 0.015 * S], fill=INK)
    d.rectangle([cx + 0.125 * S, cy - 0.025 * S, cx + 0.155 * S, cy + 0.015 * S], fill=INK)
    # lenses + nose notch
    for sx in (-1, 1):
        lx = cx + sx * 0.058 * S
        d.ellipse([lx - 0.036 * S, cy - 0.04 * S, lx + 0.036 * S, cy + 0.032 * S], fill=TEAL_GLOW)
    d.polygon([(cx - 0.025 * S, cy + 0.06 * S), (cx + 0.025 * S, cy + 0.06 * S), (cx, cy + 0.02 * S)], fill=PEARL)


def demo_badge(img):
    d = ImageDraw.Draw(img)
    cx, cy, r = 0.76 * S, 0.76 * S, 0.2 * S
    d.ellipse([cx - r - 0.02 * S, cy - r - 0.02 * S, cx + r + 0.02 * S, cy + r + 0.02 * S], fill=TEAL_DARK)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GOLD)
    d.polygon([(cx - 0.06 * S, cy - 0.1 * S), (cx - 0.06 * S, cy + 0.1 * S), (cx + 0.11 * S, cy)], fill=PEARL)


def build(kind):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    rounded_tile(img)
    if kind == "base":
        emblem(img)
    else:
        emblem(img, 0.86, -0.06, -0.06)
        {"desktop": laptop_badge, "vr": vr_badge, "demo": demo_badge}[kind](img)
    return img.resize((1024, 1024), Image.LANCZOS)


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    for kind, name in (("base", "skyfold_icon"), ("desktop", "skyfold_desktop"), ("vr", "skyfold_vr"), ("demo", "skyfold_demo")):
        img = build(kind)
        img.save(out / f"{name}.png")
        img.save(out / f"{name}.ico", sizes=sizes)
        print("wrote", out / f"{name}.ico")


if __name__ == "__main__":
    main()
