"""Treats the trailer voice lines (Kokoro TTS output) for the SKYFOLD brag videos.

Narrator: close, warm, slight low-end lift.
Noor:     radio band-pass; "radio" lines also get a squelch burst and a static bed.
Tower:    airfield PA (narrow EQ, slap echo).
Every line is trimmed, treated, then loudness-matched (two-pass loudnorm, -16 LUFS).

Usage: python process_vo.py <ffmpeg.exe> <raw_dir> <out_dir>
"""
import json
import re
import subprocess
import sys
from pathlib import Path

FF, RAW, OUT = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)

TRIM = ("silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
        "silenceremove=start_periods=1:start_threshold=-50dB,areverse,aresample=48000")
NARRATOR = ("highpass=f=55,equalizer=f=130:t=q:w=1.1:g=3,equalizer=f=3200:t=q:w=1.4:g=1.5,"
            "acompressor=threshold=-20dB:ratio=3:attack=6:release=90:makeup=2")
NOOR = ("highpass=f=280,lowpass=f=3600,equalizer=f=1700:t=q:w=1:g=4,"
        "acompressor=threshold=-22dB:ratio=4:attack=3:release=60:makeup=4,asoftclip=type=tanh")
NOOR_NEAR = ("highpass=f=170,lowpass=f=6500,equalizer=f=2000:t=q:w=1.2:g=2,"
             "acompressor=threshold=-20dB:ratio=3:attack=4:release=70:makeup=3")
TOWER = ("highpass=f=380,lowpass=f=4600,equalizer=f=2400:t=q:w=1:g=5,"
         "acompressor=threshold=-22dB:ratio=5:attack=2:release=50:makeup=4,asoftclip=type=tanh,"
         "aecho=0.85:0.55:95|190:0.32|0.16")

LINES = {
    "n2": NARRATOR, "n5": NARRATOR, "n7": NARRATOR, "n9": NARRATOR, "n10": NARRATOR,
    "noor1": "radio", "noor1v": "radio", "noor6": "radio",
    "noor3": NOOR_NEAR, "noor4": NOOR_NEAR,
    "tower8": TOWER,
}


def run(args):
    return subprocess.run([FF, "-hide_banner", "-nostats", "-y", *args], capture_output=True, text=True)


def duration(path):
    r = run(["-i", str(path), "-f", "null", "-"])
    m = re.findall(r"time=(\d+):(\d+):([\d.]+)", r.stderr)
    h, mi, s = m[-1]
    return int(h) * 3600 + int(mi) * 60 + float(s)


def loudnorm(src, dst):
    first = run(["-i", str(src), "-af", "loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json", "-f", "null", "-"])
    stats = json.loads(first.stderr[first.stderr.rindex("{"):first.stderr.rindex("}") + 1])
    second = (f"loudnorm=I=-16:TP=-1.5:LRA=7:measured_I={stats['input_i']}:measured_TP={stats['input_tp']}:"
              f"measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}:"
              f"offset={stats['target_offset']}:linear=true,aresample=48000")
    r = run(["-i", str(src), "-af", second, "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)])
    if r.returncode != 0:
        raise SystemExit(r.stderr)


for name, chain in LINES.items():
    src = RAW / f"{name}.wav"
    tmp = OUT / f"_{name}.wav"
    if chain == "radio":
        # Squelch burst, the voice through the radio chain, a quiet static bed, and a closing click.
        voice_len = duration(src)
        total = voice_len + 0.55
        graph = (
            f"[0:a]{TRIM},{NOOR},adelay=180:all=1,apad=whole_dur={total:.3f}[v];"
            f"anoisesrc=d={total:.3f}:c=pink:r=48000:a=0.5,highpass=f=900,lowpass=f=4800,volume=0.018[bed];"
            f"anoisesrc=d=0.14:c=white:r=48000:a=0.6,highpass=f=1200,lowpass=f=5200,afade=t=out:st=0.04:d=0.1,volume=0.22[sq];"
            f"anoisesrc=d=0.08:c=white:r=48000:a=0.6,highpass=f=1500,lowpass=f=5200,afade=t=out:st=0.02:d=0.06,volume=0.16,"
            f"adelay={int((total - 0.2) * 1000)}:all=1[cl];"
            f"[v][bed][sq][cl]amix=inputs=4:normalize=0:duration=first[out]"
        )
        r = run(["-i", str(src), "-filter_complex", graph, "-map", "[out]", "-ar", "48000", "-ac", "1", str(tmp)])
    else:
        r = run(["-i", str(src), "-af", f"{TRIM},{chain},apad=pad_dur=0.25", "-ar", "48000", "-ac", "1", str(tmp)])
    if r.returncode != 0:
        raise SystemExit(f"{name}: {r.stderr[-2000:]}")
    loudnorm(tmp, OUT / f"{name}.wav")
    tmp.unlink()
    print(f"{name}: {duration(OUT / f'{name}.wav'):.2f}s")
