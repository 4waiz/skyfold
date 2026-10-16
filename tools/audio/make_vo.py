#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.14"
# dependencies = ["numpy", "scipy", "faster-whisper>=1.0"]
# ///
"""Noor voiceover for SKYFOLD: audition voices, build one WAV per line, QA every line.

Speech is synthesised OFFLINE by Kokoro-82M through the kanban-motion skill's
scripts/voiceover.py (run with uv). No online TTS, no voice cloning.

    python tools/audio/make_vo.py audition            # 4 candidate voices x 3 lines, objective metrics
    python tools/audio/make_vo.py build --voice af_heart --speed 1.0
    python tools/audio/make_vo.py qa                  # faster-whisper small.en WER + letter-name checks

Source of truth: Assets/Skyfold/Resources/Dialogue/vo_lines.json
  text   = on-screen caption (WER reference, never changed by this tool)
  spoken = optional respelling sent to TTS
Output: Assets/Skyfold/Audio/VO/<id>.wav  (mono, 48 kHz, 16-bit, -16 LUFS, <= -1.5 dBTP,
        ~40 ms lead, ~150 ms tail, 5 ms fades). Reports: tools/audio/reports/vo_*.json|md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.ndimage import uniform_filter1d

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skyaudio as sa  # noqa: E402

LINES_JSON = sa.ROOT / "Assets" / "Skyfold" / "Resources" / "Dialogue" / "vo_lines.json"
VO_DIR = sa.AUDIO / "VO"
REPORTS = sa.TOOLS / "reports"
VOICEOVER = sa.SKILL / "scripts" / "voiceover.py"
TARGET_LUFS, TP_CEIL = -16.0, -1.5
LEAD, TAIL, FADE = 0.040, 0.150, 0.005
AUDITION_VOICES = ["af_heart", "bf_emma", "af_bella", "af_heart:0.6,bf_emma:0.4"]
AUDITION_LINES = ["e1.welcome", "t.walk.desktop", "g.fail"]


def uv_exe():
    return shutil.which("uv") or str(Path.home() / ".local" / "bin" / "uv.exe")


def load_lines():
    return json.loads(LINES_JSON.read_text(encoding="utf-8"))["lines"]


def tts_text(line):
    return line.get("spoken") or line["text"]


# --------------------------------------------------------------------------- synthesis
def synth(texts, voice, speed, work: Path, tag: str, offline=True):
    """Run voiceover.py once for all texts; split the result by its exact line bounds."""
    work.mkdir(parents=True, exist_ok=True)
    script = work / f"{tag}.txt"
    script.write_text("\n".join(texts) + "\n", encoding="utf-8")
    out, lines = work / f"{tag}.wav", work / f"{tag}.lines.json"
    cmd = [uv_exe(), "run"] + (["--offline"] if offline else []) + [
        str(VOICEOVER), str(script), "-o", str(out), "--lines", str(lines),
        "--voice", voice, "--speed", str(speed), "--gap", "0.6", "--lead", "0.3", "--tail", "0.6"]
    print("  $", " ".join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True)
    x, sr, _, _ = sa.read_wav(out)
    meta = json.loads(lines.read_text())["lines"]
    if len(meta) != len(texts):
        sys.exit(f"voiceover.py returned {len(meta)} lines for {len(texts)} texts")
    segs = []
    for m in meta:
        s, e = int(round((m["s"] - 0.25) * sr)), int(round((m["e"] + 0.25) * sr))
        segs.append(x[max(0, s):min(len(x), e)].copy())
    return segs, sr


def flat_tops(x, tol=1e-3, run=3):
    """Count runs of >= run consecutive samples within tol of the clip's max |x| (hard clipping)."""
    p = np.max(np.abs(x))
    hit = np.abs(x) >= p * (1 - tol)
    if not hit.any():
        return 0
    d = np.diff(np.concatenate([[0], hit.astype(int), [0]]))
    starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
    return int(np.sum((ends - starts) >= run))


def post(seg, sr_in):
    """24 kHz TTS chunk -> 48 kHz trimmed, faded, loudness-normalised line. Returns (y, speech_s)."""
    g = np.gcd(sa.SR, sr_in)
    x = signal.resample_poly(seg, sa.SR // g, sr_in // g)
    x = sa.hp(x, 60.0, 2, zero_phase=True)
    env = np.sqrt(np.maximum(uniform_filter1d(x ** 2, size=int(0.003 * sa.SR)), 0.0))
    idx = np.where(env > env.max() * sa.db2a(-45))[0]
    a, b = int(idx[0]), int(idx[-1])
    start, end = a - int(LEAD * sa.SR), b + int(TAIL * sa.SR)
    y = np.zeros(end - start)
    lo, hi = max(0, start), min(len(x), end)
    y[lo - start:hi - start] = x[lo:hi]
    y = sa.fade(y, FADE, FADE)
    y = sa.normalize_lufs(y, TARGET_LUFS, TP_CEIL)
    y = sa.fade(y, FADE, FADE)
    return y, (b - a) / sa.SR


# --------------------------------------------------------------------------- WER
LETTERS = set("ABXYEQRWSD")
LETTER_FORMS = {
    "A": {"ay", "eh", "eigh"}, "B": {"b", "be", "bee"}, "X": {"x", "ex"}, "Y": {"y", "why", "wye"},
    "E": {"e", "ee"}, "Q": {"q", "cue", "queue", "kew"}, "R": {"r", "are", "ar"},
    "W": {"w", "doubleyou", "doubleu"}, "S": {"s", "ess", "es"}, "D": {"d", "dee"},
}
ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen " \
       "sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
SPELL = {"harbour": ["harbor"], "alright": ["all", "right"], "okay": ["ok"], "neighbour": ["neighbor"]}
NAME_FORMS = ("nacre", "naker", "nayker", "neiker")
# Noor = /nu:r/. "nor" (/no:r/, the espeak reading of "Noor") is deliberately NOT accepted.
NOOR_FORMS = {"noor", "nuur", "nur", "nooer", "noer", "newer"}


def num_words(s):
    n = int(s)
    if n < 20:
        return [ONES[n]]
    if n < 100:
        return [TENS[n // 10]] + ([ONES[n % 10]] if n % 10 else [])
    return [s]


def lev(a, b):
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
    return d[-1]


def tokenize(text, caption=False):
    """-> list of (raw, norm, is_letter). Hyphenated words are joined, WASD is expanded."""
    t = text.replace("’", "'").replace("‘", "'")
    t = re.sub(r"(?i)\bdouble[\s-]*you\b", " W ", t)
    t = re.sub(r"(?<=\w)-(?=\w)", "", t)
    raw = re.findall(r"[A-Za-z0-9']+|[.!?:;]", t)
    out, sentence_start = [], True
    for tok in raw:
        if tok in ".!?:;":
            sentence_start = True
            continue
        if tok.upper() == "WASD" and not caption:
            for c in "WASD":
                out.append((c, c.lower(), True))
            sentence_start = False
            continue
        is_letter = (len(tok) == 1 and tok in LETTERS and (tok != "A" or not sentence_start)) if caption else False
        low = tok.lower().strip("'")
        norms = num_words(low) if low.isdigit() else SPELL.get(low, [low])
        for k, nrm in enumerate(norms):
            out.append((tok if k == 0 else nrm, nrm, is_letter))
        sentence_start = False
    return out


def same(c, r):
    craw, cn, cl = c
    rraw, rn, _ = r
    if cl:
        if craw == "A":
            return rraw == "A" or rn in LETTER_FORMS["A"]
        return rn in LETTER_FORMS[craw] or rn == craw.lower()
    if cn == "nacre":
        return any(lev(rn, f) <= 1 for f in NAME_FORMS)
    if cn == "noor":
        return rn in NOOR_FORMS
    return cn == rn


def align(ref, hyp):
    """Levenshtein over tokens with `same`; returns (errors, pairs[(ref_i, hyp_j | None)])."""
    n, m = len(ref), len(hyp)
    D = np.zeros((n + 1, m + 1), dtype=int)
    D[:, 0] = np.arange(n + 1)
    D[0, :] = np.arange(m + 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i, j] = min(D[i - 1, j] + 1, D[i, j - 1] + 1, D[i - 1, j - 1] + (not same(ref[i - 1], hyp[j - 1])))
    pairs, i, j = [], n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and D[i, j] == D[i - 1, j - 1] + (not same(ref[i - 1], hyp[j - 1])):
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i > 0 and D[i, j] == D[i - 1, j] + 1:
            pairs.append((i - 1, None))
            i -= 1
        else:
            j -= 1
    return int(D[n, m]), pairs[::-1]


def score(caption, transcript):
    ref, hyp = tokenize(caption, caption=True), tokenize(transcript)
    err, pairs = align(ref, hyp)
    letters = []
    for i, j in pairs:
        if ref[i][2]:
            heard = hyp[j][0] if j is not None else None
            letters.append({"letter": ref[i][0], "heard": heard,
                            "ok": bool(j is not None and same(ref[i], hyp[j]))})
    return {"wer": err / max(1, len(ref)), "errors": err, "n_ref": len(ref), "letters": letters,
            "letters_ok": all(L["ok"] for L in letters)}


_MODEL = None


def transcribe(path, model_name="small.en"):
    global _MODEL
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    if _MODEL is None:
        from faster_whisper import WhisperModel
        _MODEL = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=8)
    segs, _ = _MODEL.transcribe(str(path), language="en", beam_size=5, condition_on_previous_text=False,
                                vad_filter=False, without_timestamps=True)
    return " ".join(s.text.strip() for s in segs).strip()


def n_words(text):
    return len([t for t in tokenize(text)])


# --------------------------------------------------------------------------- commands
def cmd_audition(a):
    lines = {L["id"]: L for L in load_lines()}
    picks = [lines[i] for i in AUDITION_LINES]
    work = Path(a.work or tempfile.mkdtemp(prefix="skyfold_vo_aud_"))
    rows = []
    for v in a.voices:
        tag = "aud_" + re.sub(r"[^a-z0-9]+", "_", v)
        segs, sr = synth([tts_text(L) for L in picks], v, a.speed, work, tag, offline=not a.allow_network)
        per = []
        for L, seg in zip(picks, segs):
            raw_l = sa.lufs(seg, sr)
            y, speech = post(seg, sr)
            f = work / tag / f"{L['id']}.wav"
            sa.write_wav(f, y)
            tr = transcribe(f)
            sc = score(L["text"], tr)
            per.append({"id": L["id"], "raw_lufs": raw_l, "raw_plr": float(sa.a2db(sa.true_peak(seg)) - raw_l),
                        "flat_tops": flat_tops(seg), "speech_s": speech,
                        "wps": n_words(tts_text(L)) / speech, "wer": sc["wer"], "letters_ok": sc["letters_ok"],
                        "transcript": tr})
        r = {"voice": v, "speed": a.speed, "lines": per,
             "mean_wer": float(np.mean([p["wer"] for p in per])),
             "letters_ok": all(p["letters_ok"] for p in per),
             "mean_wps": float(np.mean([p["wps"] for p in per])),
             "lufs_spread": float(np.ptp([p["raw_lufs"] for p in per])),
             "mean_plr": float(np.mean([p["raw_plr"] for p in per])),
             "flat_tops": int(sum(p["flat_tops"] for p in per))}
        rows.append(r)
        print(f"{v:28s} WER {r['mean_wer']*100:5.1f}%  letters {'ok' if r['letters_ok'] else 'MISREAD'}  "
              f"wps {r['mean_wps']:.2f}  LUFS spread {r['lufs_spread']:.2f} LU  PLR {r['mean_plr']:.1f} dB  "
              f"flat-tops {r['flat_tops']}", file=sys.stderr)
        for p in per:
            print(f"    {p['id']:16s} wer {p['wer']*100:5.1f}% wps {p['wps']:.2f}  | {p['transcript']}", file=sys.stderr)

    def penalty(r):
        pace = max(0.0, 2.3 - r["mean_wps"], r["mean_wps"] - 2.9)
        return (0 if r["letters_ok"] else 1) * 10 + r["mean_wer"] * 10 + pace * 2 + r["lufs_spread"] * 0.1 \
            + (r["flat_tops"] > 0) * 5
    best = min(rows, key=penalty)
    heart = next((r for r in rows if r["voice"] == "af_heart"), None)
    choice = heart if heart and penalty(heart) - penalty(best) <= 0.5 else best
    rep = {"candidates": rows, "penalty": {r["voice"]: penalty(r) for r in rows}, "chosen": choice["voice"],
           "rule": "penalty = 10*letter_misread + 10*mean_WER + 2*pace_outside_2.3-2.9wps + 0.1*LUFS_spread"
                   " + 5*clipping; af_heart preferred when within 0.5 of the best"}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "vo_audition.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(f"chosen: {choice['voice']}  (report: {REPORTS / 'vo_audition.json'})", file=sys.stderr)


def cmd_build(a):
    lines = load_lines()
    if a.only:
        lines = [L for L in lines if L["id"] in set(a.only)]
    work = Path(a.work or tempfile.mkdtemp(prefix="skyfold_vo_"))
    segs, sr = synth([tts_text(L) for L in lines], a.voice, a.speed, work, "vo_all", offline=not a.allow_network)
    VO_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for L, seg in zip(lines, segs):
        y, speech = post(seg, sr)
        f = sa.write_wav(VO_DIR / f"{L['id']}.wav", y, seed=zlib.crc32(L["id"].encode()))
        y2, _, _, _ = sa.read_wav(f)
        rows.append({"id": L["id"], "file": f"VO/{L['id']}.wav", "duration_s": round(len(y2) / sa.SR, 3),
                     "speech_s": round(speech, 3), "wps": round(n_words(tts_text(L)) / speech, 2),
                     "lufs": round(sa.lufs(y2), 2), "tp_dbtp": round(float(sa.a2db(sa.true_peak(y2))), 2),
                     "peak_dbfs": round(float(sa.a2db(sa.sample_peak(y2))), 2), "flat_tops_raw": flat_tops(seg),
                     "tts": tts_text(L)})
        print(f"  {L['id']:22s} {rows[-1]['duration_s']:5.2f}s  {rows[-1]['wps']:.2f} wps  "
              f"{rows[-1]['lufs']:6.2f} LUFS  {rows[-1]['tp_dbtp']:5.2f} dBTP", file=sys.stderr)
    REPORTS.mkdir(parents=True, exist_ok=True)
    rep_path = REPORTS / "vo_build.json"
    old = json.loads(rep_path.read_text(encoding="utf-8")) if (a.only and rep_path.exists()) else {"lines": []}
    keep = [r for r in old["lines"] if r["id"] not in {x["id"] for x in rows}]
    order = {L["id"]: k for k, L in enumerate(load_lines())}
    allrows = sorted(keep + rows, key=lambda r: order.get(r["id"], 999))
    rep_path.write_text(json.dumps({"voice": a.voice, "speed": a.speed, "engine": "Kokoro-82M via kanban-motion "
                                    "voiceover.py (kokoro-onnx 0.6.1, fp32)", "lines": allrows}, indent=1),
                        encoding="utf-8")
    print(f"wrote {len(rows)} lines to {VO_DIR}", file=sys.stderr)


def cmd_qa(a):
    lines = load_lines()
    if a.only:
        lines = [L for L in lines if L["id"] in set(a.only)]
    build = {r["id"]: r for r in json.loads((REPORTS / "vo_build.json").read_text(encoding="utf-8"))["lines"]}
    rows, bad = [], []
    for L in lines:
        f = VO_DIR / f"{L['id']}.wav"
        tr = transcribe(f, a.model)
        sc = score(L["text"], tr)
        b = build.get(L["id"], {})
        row = {"id": L["id"], "mode": L.get("mode"), "duration_s": b.get("duration_s"), "wps": b.get("wps"),
               "lufs": b.get("lufs"), "tp_dbtp": b.get("tp_dbtp"), "wer": round(sc["wer"], 4),
               "letters": sc["letters"], "letters_ok": sc["letters_ok"], "caption": L["text"],
               "tts": tts_text(L), "transcript": tr}
        rows.append(row)
        flag = (sc["wer"] > 0.15) or not sc["letters_ok"]
        if flag:
            bad.append(L["id"])
        lt = " ".join(f"{x['letter']}={x['heard']}{'' if x['ok'] else '!'}" for x in sc["letters"])
        print(f"{'FAIL' if flag else 'ok  '} {L['id']:22s} WER {sc['wer']*100:5.1f}%  {lt:24s} | {tr}", file=sys.stderr)
    REPORTS.mkdir(parents=True, exist_ok=True)
    prev = {}
    qp = REPORTS / "vo_qa.json"
    if a.only and qp.exists():
        prev = {r["id"]: r for r in json.loads(qp.read_text(encoding="utf-8"))["lines"]}
    prev.update({r["id"]: r for r in rows})
    order = {L["id"]: k for k, L in enumerate(load_lines())}
    allrows = sorted(prev.values(), key=lambda r: order.get(r["id"], 999))
    summary = {"model": a.model, "n": len(allrows),
               "mean_wer": float(np.mean([r["wer"] for r in allrows])),
               "max_wer": float(np.max([r["wer"] for r in allrows])),
               "failing": [r["id"] for r in allrows if r["wer"] > 0.15 or not r["letters_ok"]]}
    qp.write_text(json.dumps({"summary": summary, "lines": allrows}, indent=1), encoding="utf-8")
    md = ["| id | duration s | words/s | LUFS | dBTP | WER % | letters |", "|---|---|---|---|---|---|---|"]
    for r in allrows:
        lt = " ".join(f"{x['letter']}:{'ok' if x['ok'] else 'MISREAD'}" for x in r["letters"]) or "-"
        md.append(f"| {r['id']} | {r['duration_s']} | {r['wps']} | {r['lufs']} | {r['tp_dbtp']} | "
                  f"{r['wer']*100:.1f} | {lt} |")
    (REPORTS / "vo_qa.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"mean WER {summary['mean_wer']*100:.2f}%  max {summary['max_wer']*100:.1f}%  "
          f"failing: {summary['failing'] or 'none'}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("audition")
    p.add_argument("--voices", nargs="+", default=AUDITION_VOICES)
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--work")
    p.add_argument("--allow-network", action="store_true")
    p = sub.add_parser("build")
    p.add_argument("--voice", default="af_heart")
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--only", nargs="*")
    p.add_argument("--work")
    p.add_argument("--allow-network", action="store_true")
    p = sub.add_parser("qa")
    p.add_argument("--model", default="small.en")
    p.add_argument("--only", nargs="*")
    a = ap.parse_args()
    {"audition": cmd_audition, "build": cmd_build, "qa": cmd_qa}[a.cmd](a)


if __name__ == "__main__":
    main()
