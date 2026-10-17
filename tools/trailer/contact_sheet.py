"""Builds contact sheets (every saved still per shot, one row per shot) from a --cine-stills run.

Usage: python contact_sheet.py <stills_dir> <landscape|portrait> <out_prefix> [shots per sheet]
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw

stills, aspect, prefix = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
per_sheet = int(sys.argv[4]) if len(sys.argv) > 4 else (6 if aspect == "landscape" else 4)
shots = defaultdict(list)
for f in sorted(stills.glob(f"*_{aspect}_*.jpg")):
    m = re.match(rf"(\w+?)_{aspect}_(\d+)\.jpg", f.name)
    if m:
        shots[m.group(1)].append((int(m.group(2)), f))

tw, th = (384, 216) if aspect == "landscape" else (216, 384)
cols = max(len(v) for v in shots.values())
ids = sorted(shots)
for page in range(0, len(ids), per_sheet):
    chunk = ids[page:page + per_sheet]
    sheet = Image.new("RGB", (40 + cols * tw, len(chunk) * th), (18, 18, 18))
    d = ImageDraw.Draw(sheet)
    for row, sid in enumerate(chunk):
        for col, (_, f) in enumerate(sorted(shots[sid])):
            im = Image.open(f).convert("RGB").resize((tw, th), Image.LANCZOS)
            sheet.paste(im, (40 + col * tw, row * th))
        d.text((6, row * th + 6), sid, fill=(255, 220, 90))
    out = f"{prefix}_{page // per_sheet}.jpg"
    sheet.save(out, quality=85)
    print(out)
