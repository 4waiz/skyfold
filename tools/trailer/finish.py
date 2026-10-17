"""Finishes a rendered brag video: verify it, pick the poster, bake the poster in as frame 0, QA frames.

Usage: python finish.py <ffmpeg.exe> <format dir (contains brag.mp4)> <poster time s> <qa times comma-separated>
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

FF = sys.argv[1]
FP = str(Path(FF).with_name("ffprobe.exe"))
DIR = Path(sys.argv[2])
POSTER_T = float(sys.argv[3])
QA_T = [float(x) for x in sys.argv[4].split(",")] if len(sys.argv) > 4 else []
MP4, JPG = DIR / "brag.mp4", DIR / "brag.jpg"


def run(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def probe(path):
    r = run([FP, "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames,sample_rate,channels",
             "-of", "json", str(path)])
    return json.loads(r.stdout)


def loudness(path):
    r = run([FF, "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"])
    i = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)[-1])
    tp = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr)[-1])
    return i, tp


before = probe(MP4)
print("render:", json.dumps(before))
# Poster: the strongest settled frame, full resolution.
run([FF, "-y", "-v", "error", "-ss", f"{POSTER_T}", "-i", str(MP4), "-frames:v", "1", "-q:v", "2", str(JPG)], check=True)
# Bake it in as frame 0 (every other frame, the timing and the audio stay as they are).
tmp = DIR / "brag.poster.mp4"
r = run([FF, "-y", "-v", "error", "-i", str(MP4), "-i", str(JPG),
         "-filter_complex", "[0:v][1:v]overlay=0:0:enable='eq(n,0)'[v]",
         "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-movflags", "+faststart", str(tmp)])
if r.returncode != 0:
    raise SystemExit(r.stderr)
tmp.replace(MP4)
after = probe(MP4)
print("final:", json.dumps(after))
lufs, tp = loudness(MP4)
print(f"loudness: {lufs:.1f} LUFS integrated, true peak {tp:.1f} dBFS")

# QA frames from the final file.
if QA_T:
    qa = DIR / "_qa"
    qa.mkdir(exist_ok=True)
    tiles = []
    for t in QA_T:
        out = qa / f"qa_{t:06.2f}.jpg"
        run([FF, "-y", "-v", "error", "-ss", f"{t}", "-i", str(MP4), "-frames:v", "1", "-q:v", "3", str(out)], check=True)
        tiles.append((t, out))
    im0 = Image.open(tiles[0][1])
    w, h = (480, 270) if im0.width > im0.height else (216, 384)
    cols = 5 if w == 480 else 8
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), (18, 18, 18))
    d = ImageDraw.Draw(sheet)
    for k, (t, f) in enumerate(tiles):
        x, y = (k % cols) * w, (k // cols) * h
        sheet.paste(Image.open(f).convert("RGB").resize((w, h), Image.LANCZOS), (x, y))
        d.text((x + 6, y + 4), f"{t:.2f}s", fill=(255, 220, 90))
    sheet.save(qa / "qa_sheet.jpg", quality=85)
    print("qa sheet:", qa / "qa_sheet.jpg")
