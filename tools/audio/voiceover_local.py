# /// script
# requires-python = ">=3.10"
# dependencies = ["kokoro-onnx==0.6.1", "soundfile", "numpy"]
# ///
"""Local Kokoro-82M narration for SKYFOLD (offline, no cloud TTS).

Reads one line of text per row, speaks them in order with silences between, and writes a 24 kHz WAV
plus a JSON file with each line's start/end time, which make_vo.py uses to split the take.

    uv run tools/audio/voiceover_local.py script.txt -o out.wav --lines out.lines.json --voice af_heart

Model files (kokoro-v1.0.onnx, voices-v1.0.bin from the kokoro-onnx releases) live in KOKORO_DIR,
default %USERPROFILE%/.cache/kokoro-onnx.
"""
import argparse, json, os
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

MODEL_DIR = Path(os.environ.get("KOKORO_DIR", Path.home() / ".cache" / "kokoro-onnx"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--lines", required=True)
    ap.add_argument("--voice", default="af_heart")
    ap.add_argument("--speed", type=float, default=0.8)
    ap.add_argument("--gap", type=float, default=0.6)
    ap.add_argument("--lead", type=float, default=0.3)
    ap.add_argument("--tail", type=float, default=0.6)
    a = ap.parse_args()

    texts = [t.strip() for t in Path(a.script).read_text(encoding="utf-8").splitlines() if t.strip()]
    k = Kokoro(str(MODEL_DIR / "kokoro-v1.0.onnx"), str(MODEL_DIR / "voices-v1.0.bin"))
    chunks, meta, t, sr = [], [], 0.0, 24000
    for i, text in enumerate(texts):
        pad = a.lead if i == 0 else a.gap
        chunks.append(np.zeros(int(pad * sr), dtype=np.float32))
        t += pad
        audio, sr = k.create(text, voice=a.voice, speed=a.speed, lang="en-us")
        audio = np.asarray(audio, dtype=np.float32)
        meta.append({"text": text, "s": round(t, 4), "e": round(t + len(audio) / sr, 4)})
        chunks.append(audio)
        t += len(audio) / sr
    chunks.append(np.zeros(int(a.tail * sr), dtype=np.float32))
    sf.write(a.out, np.concatenate(chunks), sr, subtype="PCM_24")
    Path(a.lines).write_text(json.dumps({"sr": sr, "voice": a.voice, "speed": a.speed, "lines": meta}, indent=1),
                             encoding="utf-8")
    print(f"wrote {len(meta)} lines, {t:.1f}s -> {a.out}")


if __name__ == "__main__":
    main()
