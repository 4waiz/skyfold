"""Copies a curated set of real QA screenshots into docs/screenshots as compressed JPGs.

Usage: python tools/qa/curate_screenshots.py
Every image is an unedited frame captured by the release build during automated QA
(qa/_captures/<scenario>/), only resized/re-encoded.
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
CAP = ROOT / "qa" / "_captures"
OUT = ROOT / "docs" / "screenshots"

PICKS = [
    ("menus/menu_launcher.png", "01_launcher.jpg"),
    ("tour/tour_02_atelier.png", "02_atelier_plinth.jpg"),
    ("episode1east/e1_02_rejected.png", "03_rejected_piece.jpg"),
    ("episode1east/e1_03_route.png", "04_route_built.jpg"),
    ("tour/tour_05_causeway_east.png", "05_causeway.jpg"),
    ("episode1east/e1_06_island.png", "06_courier_car.jpg"),
    ("fullcampaign/e3_02_link.png", "07_terminal_link.jpg"),
    ("fullcampaign/e3_05_takeoff.png", "08_takeoff.jpg"),
    ("episode1east/e1_07_results.png", "09_results.jpg"),
    ("menus/menu_controls.png", "10_controls.jpg"),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for src, dst in PICKS:
        p = CAP / src
        if not p.exists():
            print("missing", src)
            continue
        im = Image.open(p).convert("RGB")
        if im.width > 1600:
            im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
        im.save(OUT / dst, "JPEG", quality=86, optimize=True, progressive=True)
        print("wrote", dst, round((OUT / dst).stat().st_size / 1024), "KB")


if __name__ == "__main__":
    main()
