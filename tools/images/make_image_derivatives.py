"""Builds the in-game and docs derivatives of the ChatGPT images.

Usage: python tools/images/make_image_derivatives.py
Reads  Assets/Skyfold/Art/Images/noor_portrait.png and key_art.png (AI-generated with ChatGPT image
       generation; prompts and details in docs/ASSET_MANIFEST.md).
Writes Assets/Skyfold/Art/Images/noor_badge.png  (256 px circular subtitle badge, HUDController.noorPortrait)
       docs/screenshots/key_art.jpg               (1600x900 README header)
Only crops, scales, masks and re-encodes the generated pixels; nothing is redrawn.
"""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
IMAGES = ROOT / "Assets" / "Skyfold" / "Art" / "Images"
PEARL = (244, 239, 230, 255)
TEAL_LIGHT = (63, 167, 163, 255)  # UIStyle.TealLight, the colour of Noor's badge in the HUD

BADGE = 256    # output size; the HUD draws it at 96 reference px (about 140 px at 2560x1600)
SS = 4         # supersampling for clean circle edges
RING = 0.07    # teal ring width as a fraction of the badge radius
# Crop circle in source pixels: the whole head, the headset and the jacket collar.
CROP_CENTRE = (640, 545)
CROP_RADIUS = 455


def disc(size, radius, colour):
    """A centred anti-aliasing-ready disc on a transparent canvas (drawn at supersampled size)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    c = size / 2
    ImageDraw.Draw(img).ellipse([c - radius, c - radius, c + radius, c + radius], fill=colour)
    return img


def noor_badge():
    src = Image.open(IMAGES / "noor_portrait.png").convert("RGBA")
    cx, cy = CROP_CENTRE
    r = CROP_RADIUS
    big = BADGE * SS
    inner = round(big / 2 * (1 - RING))

    badge = disc(big, big / 2, TEAL_LIGHT)
    badge.alpha_composite(disc(big, inner, PEARL))
    face = src.crop((cx - r, cy - r, cx + r, cy + r)).resize((2 * inner, 2 * inner), Image.LANCZOS)
    layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    layer.paste(face, (big // 2 - inner, big // 2 - inner))
    # Clip the portrait to the inner disc so the ring stays clean.
    mask = disc(big, inner, (255, 255, 255, 255)).getchannel("A")
    layer.putalpha(Image.composite(layer.getchannel("A"), Image.new("L", (big, big), 0), mask))
    badge.alpha_composite(layer)

    out = IMAGES / "noor_badge.png"
    badge.resize((BADGE, BADGE), Image.LANCZOS).save(out, optimize=True)
    print("wrote", out)


def key_art_jpg():
    im = Image.open(IMAGES / "key_art.png").convert("RGB")
    w = 1600  # same size and encoding as tools/qa/curate_screenshots.py
    im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    out = ROOT / "docs" / "screenshots" / "key_art.jpg"
    im.save(out, "JPEG", quality=86, optimize=True, progressive=True)
    print("wrote", out, im.size)


if __name__ == "__main__":
    noor_badge()
    key_art_jpg()
