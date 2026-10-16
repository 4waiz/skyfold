#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy"]
# ///
"""Final technical QA over every shipped SKYFOLD audio file.

    python tools/audio/qa_audio.py

Checks per file: WAV PCM format (48 kHz, 16-bit, mono for VO/SFX, stereo for Music/Ambience),
duration, sample peak, true peak (4x), integrated loudness (BS.1770-4), DC offset, hard
clipping, start/end sample (click risk) for one-shots, and seams for every *_loop file
(rendered twice back-to-back: sample step, curvature and short-window RMS jump across the
junction; music loops are also compared with their own bar lines).
Category targets: VO -16 LUFS +-0.5 & <= -1.5 dBTP; Music -20 LUFS +-0.5 & <= -1.5 dBTP;
Ambience -24 LUFS +-0.5 & <= -1.5 dBTP; SFX peak -3.0 dBFS +-0.1; NURI 0.15-0.9 s.
Also verifies that every expected id exists (VO from vo_lines.json, SFX/Music/Ambience lists).
Writes tools/audio/reports/qa.json and qa.md, prints the summary table.
"""

from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skyaudio as sa  # noqa: E402

REPORTS = sa.TOOLS / "reports"
LINES_JSON = sa.ROOT / "Assets" / "Skyfold" / "Resources" / "Dialogue" / "vo_lines.json"
SPEC = {
    "VO": {"ch": 1, "lufs": -16.0, "tp": -1.5},
    "Music": {"ch": 2, "lufs": -20.0, "tp": -1.5},
    "Ambience": {"ch": 2, "lufs": -24.0, "tp": -1.5},
    "SFX": {"ch": 1, "peak": -3.0},
}
EXPECTED_SFX = (
    ["nuri_happy_0%d" % i for i in range(1, 5)] + ["nuri_curious_0%d" % i for i in range(1, 4)]
    + ["nuri_concern_0%d" % i for i in range(1, 4)] + ["nuri_celebrate_0%d" % i for i in range(1, 3)]
    + ["nuri_point_0%d" % i for i in range(1, 3)]
    + "piece_pickup piece_drop piece_rotate socket_snap socket_reject bridge_assemble route_complete fold_out "
      "fold_in cell_pickup cell_insert power_transfer substation_on switch_lever beacon_on warning_chime "
      "checkpoint objective_complete hint_ping ui_hover ui_click ui_back ui_toggle ui_slider_tick car_enter "
      "car_start car_motor_loop car_roll_loop car_bump car_horn plane_idle_loop plane_spoolup plane_takeoff "
      "plane_flyby convoy_beep splash respawn teleport door_chime".split()
    + ["thunder_far_0%d" % i for i in range(1, 4)] + ["footstep_stone_0%d" % i for i in range(1, 5)])
EXPECTED_MUSIC = ["music_menu_loop", "music_architect_loop", "music_street_loop", "music_drive_loop",
                  "music_storm_loop", "music_finale", "stinger_success", "stinger_fail", "stinger_episode"]
EXPECTED_AMB = ["amb_coast_loop", "amb_city_loop", "amb_atelier_loop", "amb_storm_loop"]


def check(path: Path, cat: str, bars: dict):
    with wave.open(str(path), "rb") as w:
        comp = w.getcomptype()
    x, sr, ch, sw = sa.read_wav(path)
    X = sa.as2d(x)
    n = X.shape[0]
    sid = path.stem
    loop = sid.endswith("_loop")
    r = {"id": sid, "file": f"{cat}/{path.name}", "category": cat, "loop": loop, "sr": sr, "channels": ch,
         "bits": sw * 8, "pcm": comp == "NONE", "duration_s": round(n / sr, 3),
         "peak_dbfs": round(float(sa.a2db(sa.sample_peak(X))), 2), "tp_dbtp": round(float(sa.a2db(sa.true_peak(X))), 2),
         "lufs": round(sa.lufs(X, sr), 2), "dc": float(np.max(np.abs(X.mean(axis=0)))),
         "clipped": int(np.sum(np.abs(X) >= 32767 / 32768)), "edge": float(max(np.max(np.abs(X[0])), np.max(np.abs(X[-1]))))}
    spec = SPEC[cat]
    issues = []
    if sr != 48000:
        issues.append(f"sr {sr}")
    if sw != 2 or not r["pcm"]:
        issues.append("not 16-bit PCM")
    if ch != spec["ch"]:
        issues.append(f"{ch} ch")
    if r["dc"] > 1e-3:
        issues.append(f"DC {r['dc']:.4f}")
    if r["clipped"]:
        issues.append(f"{r['clipped']} clipped samples")
    if "lufs" in spec and abs(r["lufs"] - spec["lufs"]) > 0.5:
        issues.append(f"LUFS {r['lufs']}")
    if "tp" in spec and r["tp_dbtp"] > spec["tp"] + 0.05:
        issues.append(f"TP {r['tp_dbtp']}")
    if "peak" in spec and abs(r["peak_dbfs"] - spec["peak"]) > 0.1:
        issues.append(f"peak {r['peak_dbfs']}")
    if not loop and r["edge"] > 0.01:
        issues.append(f"edge sample {r['edge']:.3f}")
    if sid.startswith("nuri_") and not (0.15 <= r["duration_s"] <= 0.9):
        issues.append(f"nuri length {r['duration_s']}")
    if loop:
        b = bars.get(sid)
        bounds = [round(k * b["bar_s"] * sr) for k in range(1, b["bars"])] if b else None
        s = sa.seam_report(X, sr, boundaries=bounds)
        r["seam"] = {k: (round(v, 5) if isinstance(v, float) else v) for k, v in s.items()}
        if not s["ok"]:
            issues.append("seam")
    r["issues"] = issues
    r["ok"] = not issues
    return r


def main():
    music = json.loads((REPORTS / "music.json").read_text(encoding="utf-8")) if (REPORTS / "music.json").exists() else {}
    bars = {k: {"bar_s": v["bar_s"], "bars": v["bars"]} for k, v in music.items() if v.get("loop")}
    rows = []
    for cat in ("VO", "SFX", "Music", "Ambience"):
        for p in sorted((sa.AUDIO / cat).glob("*.wav")):
            rows.append(check(p, cat, bars))
    have = {r["id"] for r in rows}
    vo_ids = [L["id"] for L in json.loads(LINES_JSON.read_text(encoding="utf-8"))["lines"]]
    missing = [i for i in vo_ids + EXPECTED_SFX + EXPECTED_MUSIC + EXPECTED_AMB if i not in have]
    extra = sorted(have - set(vo_ids + EXPECTED_SFX + EXPECTED_MUSIC + EXPECTED_AMB))
    summary = []
    for cat in ("VO", "SFX", "Music", "Ambience"):
        rs = [r for r in rows if r["category"] == cat]
        loops = [r for r in rs if r["loop"]]
        summary.append({
            "category": cat, "files": len(rs), "pass": sum(r["ok"] for r in rs),
            "format": f"{rs[0]['sr'] // 1000} kHz / {rs[0]['bits']}-bit / {'mono' if rs[0]['channels'] == 1 else 'stereo'}"
            if rs else "-",
            "duration_s": f"{min(r['duration_s'] for r in rs):.2f}-{max(r['duration_s'] for r in rs):.2f}" if rs else "-",
            "lufs": f"{min(r['lufs'] for r in rs):.1f} .. {max(r['lufs'] for r in rs):.1f}" if rs else "-",
            "max_tp_dbtp": max(r["tp_dbtp"] for r in rs) if rs else None,
            "peak_dbfs": f"{min(r['peak_dbfs'] for r in rs):.2f} .. {max(r['peak_dbfs'] for r in rs):.2f}" if rs else "-",
            "max_dc": max(r["dc"] for r in rs) if rs else None,
            "loops_seam_ok": f"{sum(r['seam']['ok'] for r in loops)}/{len(loops)}" if loops else "-",
        })
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = {"summary": summary, "missing": missing, "unexpected": extra, "files": rows}
    (REPORTS / "qa.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    md = ["| Category | Files | Pass | Format | Duration s | LUFS | Max dBTP | Peak dBFS | Max DC | Loop seams |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for s in summary:
        md.append(f"| {s['category']} | {s['files']} | {s['pass']} | {s['format']} | {s['duration_s']} | {s['lufs']} | "
                  f"{s['max_tp_dbtp']} | {s['peak_dbfs']} | {s['max_dc']:.1e} | {s['loops_seam_ok']} |")
    md += ["", "| File | Dur s | LUFS | dBTP | Peak dBFS | DC | Seam (step / p99.9, jump50 dB / limit) | Result |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        sm = r.get("seam")
        seam = (f"{sm['seam_step']:.4f} / {sm['p999_step']:.4f}, {sm['rms_jump_50ms_db']:.2f} / "
                f"{sm['rms_jump_50ms_limit']:.2f}") if sm else "-"
        md.append(f"| {r['file']} | {r['duration_s']} | {r['lufs']} | {r['tp_dbtp']} | {r['peak_dbfs']} | "
                  f"{r['dc']:.1e} | {seam} | {'PASS' if r['ok'] else 'FAIL: ' + ', '.join(r['issues'])} |")
    md += ["", f"Missing ids: {missing or 'none'}", f"Unexpected files: {extra or 'none'}"]
    (REPORTS / "qa.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:2 + len(summary)]))
    bad = [r for r in rows if not r["ok"]]
    for r in bad:
        print(f"FAIL {r['file']}: {', '.join(r['issues'])}")
    print(f"\n{len(rows)} files, {len(rows) - len(bad)} pass, missing: {missing or 'none'}, unexpected: {extra or 'none'}")
    for r in rows:
        if r["loop"]:
            s = r["seam"]
            print(f"  seam {r['file']:32s} step {s['seam_step']:.4f} (p99.9 {s['p999_step']:.4f})  "
                  f"jump50 {s['rms_jump_50ms_db']:.2f}/{s['rms_jump_50ms_limit']:.2f} dB  "
                  f"jump10 {s['rms_jump_10ms_db']:.2f}/{s['rms_jump_10ms_limit']:.2f} dB  {'OK' if s['ok'] else 'FAIL'}")


if __name__ == "__main__":
    main()
