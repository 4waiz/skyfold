"""Builds the SKYFOLD brag trailers from the captured shots and edits.py:

  brag-output/<format>/composition/index.html          Hyperframes composition (picture + graphics)
  brag-output/<format>/composition/assets/footage/     the clips it uses
  brag-output/<format>/composition/assets/audio/       music.wav (ducked bed + ambience), vo.wav, sfx.wav

Usage: python build_trailer.py <ffmpeg.exe> [landscape|vertical|all]
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audio_mix as am  # noqa: E402
import edits  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "brag-output"
CLIPS = OUT / "footage" / "clips"
GAME_AUDIO = ROOT / "Assets" / "Skyfold" / "Audio"
SKILL_SFX = Path.home() / ".claude" / "skills" / "brag" / "assets" / "sfx"
VO_DIR = OUT / "vo"
FFMPEG = sys.argv[1]
WHICH = sys.argv[2] if len(sys.argv) > 2 else "all"

LETTERS = "SKYFOLD"
LETTER_STEP = 0.13


def sound_path(name):
    if "/" in name:
        return SKILL_SFX / f"{name}.ogg"
    for sub in ("SFX", "Music", "Ambience"):
        p = GAME_AUDIO / sub / f"{name}.wav"
        if p.exists():
            return p
    raise FileNotFoundError(name)


def load(name):
    return am.load(FFMPEG, sound_path(name))


def loudness(path):
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    i = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)[-1])
    tp = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr)[-1])
    return i, tp


# --------------------------------------------------------------------------------------------- audio
def build_audio(cfg, assets):
    dur = cfg["duration"]
    g = cfg["graphics"]
    vo = am.Track(dur)
    spans = []
    for name, at in cfg["vo"]:
        clip = am.load(FFMPEG, VO_DIR / f"{name}.wav")
        vo.add(clip, at)
        spans.append((at + 0.05, at + len(clip) / am.SR - 0.2))

    music = am.Track(dur)
    for name, at, src, d, fi, fo, gain in cfg["music"]:
        music.add(load(name), at, gain=gain, src=src, dur=d, fade_in=fi, fade_out=fo, loop=True)
    music.apply(am.automation(dur, cfg["music_lane"]))
    music.apply(am.duck_envelope(dur, spans, depth=0.3))

    amb = am.Track(dur)
    for name, at, d, fi, fo, gain in cfg["ambience"]:
        amb.add(load(name), at, gain=gain, dur=d, fade_in=fi, fade_out=fo, loop=True)
    amb.apply(am.duck_envelope(dur, spans, depth=0.55))
    music.buf += amb.buf

    sfx = am.Track(dur)
    for item in cfg["sfx"]:
        name, at, gain = item[:3]
        extra = item[3] if len(item) > 3 else {}
        sfx.add(load(name), at, gain=gain, **extra)
    # Runway beacons: one tick per pair as the sweep races away, rising slightly in pitch.
    for i, t in enumerate(edits.beacon_ticks(cfg["beacon_sweep"])):
        sfx.add(load("beacon_on"), t, gain=0.42 - i * 0.02, rate=1.0 + 0.035 * i, dur=0.6, fade_out=0.25)
    # Title letters fold in like paper cards.
    for i in range(len(LETTERS)):
        sfx.add(load(f"casino/card-slide-{i % 8 + 1}"), cfg["letters_at"] + i * LETTER_STEP, gain=0.34)

    # Level the whole mix to about -14 LUFS (YouTube) with one shared gain, so the stems keep their balance.
    tmp = assets / "_sum.wav"
    am.write_wav(tmp, music.buf + vo.buf + sfx.buf, peak=10.0)
    lufs, peak = loudness(tmp)
    tmp.unlink()
    gain = 10 ** ((-14.0 - lufs) / 20.0)
    for tr in (music, vo, sfx):
        tr.buf *= gain
    am.write_wav(assets / "music.wav", music.buf)
    am.write_wav(assets / "vo.wav", vo.buf)
    am.write_wav(assets / "sfx.wav", sfx.buf)
    total = assets / "_check.wav"
    am.write_wav(total, music.buf + vo.buf + sfx.buf)
    lufs2, peak2 = loudness(total)
    total.unlink()
    print(f"  mix: {lufs:.1f} LUFS -> {lufs2:.1f} LUFS, true peak {peak2:.1f} dBFS (gain {20*np.log10(gain):+.1f} dB)")

    # Audio-reactive data for the title section: per-frame [bass, treble] of the music bed.
    t0 = g["title"][0]
    bands = am.band_frames(music.buf[int(t0 * am.SR):], fps=30)
    return {"fps": 30, "start": t0, "frames": [[round(float(b), 3), round(float(t), 3)] for b, t in bands]}


# --------------------------------------------------------------------------------------------- html
CSS = r"""
@font-face { font-family: 'Unbounded'; src: url('assets/fonts/Unbounded-SemiBold.ttf') format('truetype'); font-weight: 600; }
@font-face { font-family: 'Atkinson'; src: url('assets/fonts/AtkinsonHyperlegible-Regular.ttf') format('truetype'); font-weight: 400; }
@font-face { font-family: 'Atkinson'; src: url('assets/fonts/AtkinsonHyperlegible-Bold.ttf') format('truetype'); font-weight: 700; }
:root { --pearl: #F4EFE6; --sand: #D9B98C; --teal: #0F6F73; --tealL: #36E0D1; --coral: #F2714B; --gold: #D9A441; --ink: #22333B; }
html, body { margin: 0; background: #0b1114; }
#root { position: relative; width: 100%; height: 100%; overflow: hidden; background: #0b1114; font-family: 'Atkinson', sans-serif; color: var(--pearl); }
.shot { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.ov { position: absolute; inset: 0; pointer-events: none; box-sizing: border-box; }
.black { background: #000; }
.flash { background: #fff; opacity: 0; }

/* big statement captions */
.cap-big { display: flex; align-items: center; justify-content: center; }
.cap-big .cap-inner { display: flex; flex-direction: column; align-items: center; }
.cap-big .ln { display: block; font-family: 'Unbounded'; font-weight: 600; font-size: 112px; line-height: 1.06; letter-spacing: 0.035em;
  color: var(--pearl); text-shadow: 0 4px 30px rgba(8, 18, 22, 0.6), 0 1px 3px rgba(8, 18, 22, 0.45); text-align: center; white-space: nowrap; }
.cap-big .ln.accent { color: var(--tealL); }
.cap-big.left { align-items: flex-end; justify-content: flex-start; padding: 0 0 120px 120px; }
.cap-big.left .cap-inner { align-items: flex-start; }
.cap-big.left .ln { font-size: 88px; text-align: left; }
.cap-big.low { align-items: flex-end; padding-bottom: 110px; }
.cap-big.low .ln { font-size: 84px; }
.cap-big.high { align-items: flex-start; padding-top: 330px; }

/* objective tracker (top right), styled like the game's HUD panels */
.obj-wrap { display: flex; justify-content: flex-end; align-items: flex-start; padding: 64px 72px 0 0; }
.obj { display: flex; align-items: center; gap: 22px; background: rgba(244, 239, 230, 0.95); color: var(--ink); border-radius: 28px;
  padding: 16px 34px 16px 16px; box-shadow: 0 18px 50px rgba(8, 18, 22, 0.35); }
.obj-num { position: relative; width: 66px; height: 66px; flex: 0 0 66px; border-radius: 50%; background: var(--teal);
  display: flex; align-items: center; justify-content: center; }
.obj-num .n { font-family: 'Unbounded'; font-weight: 600; font-size: 26px; color: var(--pearl); }
.obj-num svg { position: absolute; left: 0; top: 0; width: 66px; height: 66px; }
.obj-num .tick { fill: none; stroke: var(--pearl); stroke-width: 6; stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 44; stroke-dashoffset: 44; }
.obj-num .pulse { position: absolute; left: -4px; top: -4px; width: 74px; height: 74px; border-radius: 50%; border: 3px solid var(--tealL); opacity: 0; box-sizing: border-box; }
.obj-text { display: flex; flex-direction: column; gap: 4px; }
.obj-label { position: relative; height: 22px; font-family: 'Atkinson'; font-weight: 700; font-size: 19px; letter-spacing: 0.24em; }
.obj-label span { position: absolute; left: 0; top: 0; white-space: nowrap; }
.obj-label .todo { color: var(--teal); }
.obj-label .done { color: #14918F; opacity: 0; }
.obj-title { font-family: 'Unbounded'; font-weight: 600; font-size: 34px; letter-spacing: 0.02em; white-space: nowrap; }

/* radio caller badge (top left) */
.radio-wrap { display: flex; justify-content: flex-start; align-items: flex-start; padding: 60px 0 0 70px; }
.radio { display: flex; align-items: center; gap: 20px; background: rgba(34, 51, 59, 0.84); border-radius: 60px; padding: 12px 36px 12px 12px;
  box-shadow: 0 18px 50px rgba(8, 18, 22, 0.35); }
.badge { position: relative; width: 84px; height: 84px; flex: 0 0 84px; }
.badge .face { width: 84px; height: 84px; border-radius: 50%; background: url('assets/img/noor_badge.png') center / cover no-repeat; }
.badge .ico { width: 84px; height: 84px; border-radius: 50%; background: var(--gold); display: flex; align-items: center; justify-content: center; }
.badge .ico svg { width: 46px; height: 46px; }
.badge .ring { position: absolute; left: -7px; top: -7px; width: 98px; height: 98px; border-radius: 50%; border: 3px solid var(--tealL); opacity: 0; box-sizing: border-box; }
.who .name { font-family: 'Unbounded'; font-weight: 600; font-size: 30px; letter-spacing: 0.08em; }
.who .role { font-family: 'Atkinson'; font-size: 22px; color: var(--tealL); letter-spacing: 0.05em; margin-top: 2px; }

/* in-game style hint chips (bottom centre) */
.chip-wrap { display: flex; align-items: flex-end; justify-content: center; padding-bottom: 86px; }
.chip { font-family: 'Atkinson'; font-size: 34px; color: var(--pearl); background: rgba(34, 51, 59, 0.92); border-radius: 22px; padding: 18px 32px;
  box-shadow: 0 16px 44px rgba(8, 18, 22, 0.42); border: 2px solid transparent; text-align: center; }
.chip.warn { border-color: rgba(242, 113, 75, 0.55); }
.chip.warn b { color: var(--coral); margin-right: 10px; }
.chip.ok { border-color: rgba(54, 224, 209, 0.6); }
.chip.ok b { color: var(--tealL); margin-right: 10px; }

/* opening location card (bottom left) */
.loc-wrap { display: flex; align-items: flex-end; justify-content: flex-start; padding: 0 0 80px 80px; }
.loc { padding: 26px 64px 24px 30px; border-radius: 20px; background: linear-gradient(90deg, rgba(11, 17, 20, 0.62) 0%, rgba(11, 17, 20, 0.38) 70%, rgba(11, 17, 20, 0) 100%); }
.loc .place { font-family: 'Unbounded'; font-weight: 600; font-size: 46px; letter-spacing: 0.34em; }
.loc .line { width: 440px; height: 3px; background: var(--gold); margin: 16px 0 14px; transform-origin: 0% 50%; }
.loc .warn { font-family: 'Atkinson'; font-weight: 700; font-size: 24px; letter-spacing: 0.3em; color: #FF8A63; display: flex; align-items: center; }
.loc .warn .dot { width: 13px; height: 13px; border-radius: 50%; background: var(--coral); margin-right: 14px; }

/* paper-fold transition */
.fold-stage { perspective: 2400px; }
.leaf { position: absolute; inset: 0; background: linear-gradient(118deg, #F4EFE6 0%, #ECE3D3 58%, #DCC7A4 100%); backface-visibility: hidden;
  display: flex; align-items: center; justify-content: center; }
.leaf .mark { font-family: 'Unbounded'; font-weight: 600; font-size: 40px; letter-spacing: 0.6em; color: var(--teal); padding-left: 0.6em; }
.leaf .edge { position: absolute; top: 0; bottom: 0; width: 10px; background: var(--tealL); }
.leaf .shade { position: absolute; inset: 0; background: linear-gradient(90deg, rgba(34, 51, 59, 0.45), rgba(34, 51, 59, 0)); opacity: 0; }

/* title section */
.bgwrap { position: absolute; inset: -60px; }
.tbg { filter: blur(18px) brightness(0.42) saturate(1.2); }
.tgrad { background: radial-gradient(ellipse at 50% 52%, rgba(15, 111, 115, 0.38) 0%, rgba(11, 17, 20, 0.88) 72%); }
.tglow-wrap { display: flex; align-items: center; justify-content: center; }
.tglow { width: 1200px; height: 560px; border-radius: 50%; background: radial-gradient(ellipse, rgba(217, 164, 65, 0.5) 0%, rgba(217, 164, 65, 0) 70%); opacity: 0.35; }
.title-wrap { display: flex; align-items: center; justify-content: center; }
.title-stack { display: flex; flex-direction: column; align-items: center; }
.word { display: flex; perspective: 1400px; font-family: 'Unbounded'; font-weight: 600; font-size: 188px; letter-spacing: 0.1em; padding-left: 0.1em;
  color: var(--pearl); text-shadow: 0 12px 46px rgba(15, 111, 115, 0.7); }
.word .L { display: block; transform-origin: 50% 0%; backface-visibility: hidden; }
.rule { width: 600px; height: 4px; background: var(--gold); margin: 30px 0 24px; transform-origin: 50% 50%; box-shadow: 0 0 0 rgba(217, 164, 65, 0); }
.sub { font-family: 'Unbounded'; font-weight: 600; font-size: 54px; letter-spacing: 0.42em; padding-left: 0.42em; color: var(--gold); white-space: nowrap; }
.plat-wrap { display: flex; align-items: center; justify-content: center; }
.plat { display: flex; flex-direction: column; align-items: center; gap: 26px; }
.pill { display: flex; align-items: center; gap: 20px; font-family: 'Unbounded'; font-weight: 600; font-size: 36px; letter-spacing: 0.08em;
  padding: 20px 40px 20px 26px; border-radius: 60px; background: rgba(15, 111, 115, 0.9); color: var(--pearl); box-shadow: 0 16px 44px rgba(0, 0, 0, 0.35); white-space: nowrap; }
.pill.alt { background: rgba(244, 239, 230, 0.94); color: var(--ink); }
.pill svg { width: 56px; height: 56px; flex: 0 0 56px; }
.credit-wrap { display: flex; flex-direction: column; align-items: center; justify-content: center; }
.credit { display: flex; flex-direction: column; align-items: center; }
.credit .small { font-family: 'Atkinson'; font-weight: 700; font-size: 30px; letter-spacing: 0.5em; padding-left: 0.5em; color: var(--tealL); }
.credit .name { font-family: 'Unbounded'; font-weight: 600; font-size: 122px; letter-spacing: 0.08em; padding-left: 0.08em; margin-top: 14px; white-space: nowrap;
  text-shadow: 0 10px 40px rgba(15, 111, 115, 0.6); }
.credit .bar { width: 120px; height: 4px; background: var(--gold); margin-top: 26px; transform-origin: 50% 50%; }
.foot { position: absolute; left: 0; right: 0; bottom: 56px; text-align: center; font-family: 'Atkinson'; font-size: 22px; letter-spacing: 0.14em; color: rgba(244, 239, 230, 0.62); }

/* vertical (Shorts) layout: keep text out of the top 15% and bottom 20% */
.fmt-v .cap-big .ln { font-size: 108px; }
.fmt-v .obj-wrap { justify-content: center; padding: 330px 0 0 0; }
.fmt-v .obj-title { font-size: 30px; }
.fmt-v .radio-wrap { align-items: flex-end; padding: 0 0 430px 60px; }
.fmt-v .chip-wrap { padding: 0 60px 560px 60px; }
.fmt-v .chip { font-size: 32px; max-width: 860px; }
.fmt-v .loc-wrap { padding: 0 0 420px 56px; }
.fmt-v .word { font-size: 132px; letter-spacing: 0.06em; padding-left: 0.06em; }
.fmt-v .rule { width: 460px; }
.fmt-v .sub { font-size: 40px; letter-spacing: 0.32em; padding-left: 0.32em; }
.fmt-v .pill { font-size: 28px; }
.fmt-v .pill svg { width: 46px; height: 46px; flex-basis: 46px; }
.fmt-v .credit .name { font-size: 92px; }
.fmt-v .foot { bottom: 420px; }
"""

ICON_PA = ('<svg viewBox="0 0 48 48"><path d="M8 19h7l11-8v26l-11-8H8z" fill="#22333B"/>'
           '<path d="M31 17c3 2 4.5 4.6 4.5 7s-1.5 5-4.5 7M35 12c5 3.5 7.5 7.6 7.5 12S40 32.5 35 36" fill="none" stroke="#22333B" stroke-width="3.4" stroke-linecap="round"/></svg>')
ICON_HEADSET = ('<svg viewBox="0 0 56 56"><rect x="6" y="17" width="44" height="23" rx="10" fill="#F4EFE6"/>'
                '<rect x="12" y="23" width="13" height="11" rx="4" fill="#0F6F73"/><rect x="31" y="23" width="13" height="11" rx="4" fill="#0F6F73"/>'
                '<path d="M25 40c1-3 5-3 6 0" fill="#0F6F73"/><path d="M10 17c2-6 8-9 18-9s16 3 18 9" fill="none" stroke="#F4EFE6" stroke-width="3"/></svg>')
ICON_LAPTOP = ('<svg viewBox="0 0 56 56"><rect x="11" y="12" width="34" height="23" rx="3" fill="#22333B"/>'
               '<rect x="14" y="15" width="28" height="17" rx="1.5" fill="#36E0D1"/><path d="M5 39h46l-4 5H9z" fill="#22333B"/></svg>')
TICK = '<svg viewBox="0 0 66 66"><path class="tick" d="M20 34 L29 43 L46 24"/></svg>'


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_html(cfg, audio_data):
    g = cfg["graphics"]
    v = cfg["name"] == "vertical"
    dur = cfg["duration"]
    asp = cfg["aspect"]
    el = []
    # Footage.
    for vid, shot, start, d, ms in cfg["shots"]:
        el.append(f'<video id="{vid}" class="clip shot" src="assets/footage/{shot}_{asp}.mp4" data-start="{start}" data-duration="{d}" '
                  f'data-media-start="{ms}" data-track-index="0" muted playsinline></video>')
    bg_shot, bg_at, bg_d, bg_ms = cfg["title_bg"]
    el.append(f'<div id="tbg-wrap" class="bgwrap"><video id="tbg" class="clip shot tbg" src="assets/footage/{bg_shot}_{asp}.mp4" '
              f'data-start="{bg_at}" data-duration="{bg_d}" data-media-start="{bg_ms}" data-track-index="1" muted playsinline></video></div>')
    T0 = g["title"][0]
    el.append(f'<div id="tgrad" class="clip ov tgrad" data-start="{T0}" data-duration="{dur - T0}" data-track-index="2"></div>')
    el.append(f'<div id="tglow" class="clip ov tglow-wrap" data-start="{T0}" data-duration="{dur - T0}" data-track-index="3"><div id="tglow-in" class="tglow"></div></div>')

    # Opening fade and location card.
    a, b = g["fade_in"]
    el.append(f'<div id="fadein" class="clip ov black" data-start="{a}" data-duration="{b - a}" data-track-index="9"></div>')
    a, b = g["location"]
    el.append(f'<div id="loc" class="clip ov loc-wrap" data-start="{a}" data-duration="{b - a}" data-track-index="4"><div class="loc">'
              f'<div class="place">NACRE BAY</div><div class="line"></div><div class="warn"><span class="dot"></span>STORM WARNING</div></div></div>')

    # Radio callers.
    for i, (line, a, b) in enumerate(g["radio"]):
        el.append(f'<div id="rn{i}" class="clip ov radio-wrap" data-start="{a}" data-duration="{b - a}" data-track-index="5"><div class="radio">'
                  f'<div class="badge"><div class="face"></div><div class="ring"></div></div>'
                  f'<div class="who"><div class="name">NOOR</div><div class="role">{esc(edits.NOOR_ROLE)}</div></div></div></div>')
    a, b = g["tower"]
    el.append(f'<div id="rtower" class="clip ov radio-wrap" data-start="{a}" data-duration="{b - a}" data-track-index="5"><div class="radio">'
              f'<div class="badge"><div class="ico">{ICON_PA}</div><div class="ring"></div></div>'
              f'<div class="who"><div class="name">{edits.TOWER_NAME}</div><div class="role">{esc(edits.TOWER_ROLE)}</div></div></div></div>')

    # Statement captions.
    for c in g["big"]:
        lines = "".join(f'<span class="ln{" accent" if (c["id"] == "cb4" and k > 0) else ""}">{esc(t)}</span>'
                        for k, (t, _) in enumerate(c["lines"]))
        cls = {"left": "cap-big left", "low": "cap-big low", "high": "cap-big high"}.get(c.get("align"), "cap-big")
        el.append(f'<div id="{c["id"]}" class="clip ov {cls}" data-start="{c["in"]}" data-duration="{round(c["out"] - c["in"], 3)}" data-track-index="6">'
                  f'<div class="cap-inner">{lines}</div></div>')

    # Objectives.
    for oid, num, title, a, chk, b in g["objectives"]:
        el.append(f'<div id="{oid}" class="clip ov obj-wrap" data-start="{a}" data-duration="{round(b - a, 3)}" data-track-index="7"><div class="obj">'
                  f'<div class="obj-num"><span class="n">{num:02d}</span>{TICK}<div class="pulse"></div></div>'
                  f'<div class="obj-text"><div class="obj-label"><span class="todo">OBJECTIVE</span><span class="done">DONE</span></div>'
                  f'<div class="obj-title">{esc(title)}</div></div></div></div>')

    # Hint chips.
    for cid, kind, a, b in g["chips"]:
        if kind == "warn":
            body = f'<b>{esc(edits.CHIP_WRONG[0])}</b>{esc(edits.CHIP_WRONG[1])}'
        else:
            body = f'<b>\u2713</b>{esc(edits.CHIP_RIGHT)}'
        el.append(f'<div id="{cid}" class="clip ov chip-wrap" data-start="{a}" data-duration="{round(b - a, 3)}" data-track-index="8"><div class="chip {kind}">{body}</div></div>')

    # Fold transition, lightning, flash.
    f = g["fold"]
    el.append(f'<div id="fold" class="clip ov fold-stage" data-start="{round(f - 0.5, 3)}" data-duration="1.0" data-track-index="10">'
              f'<div id="leaf" class="leaf"><div class="mark">SKYFOLD</div><div class="edge" id="leaf-edge"></div><div class="shade" id="leaf-shade"></div></div></div>')
    l0, l1 = g["lightning"]
    el.append(f'<div id="lightning" class="clip ov flash" data-start="{round(l0 - 0.05, 3)}" data-duration="{round(l1 - l0 + 0.6, 3)}" data-track-index="11"></div>')
    fa = cfg["flash_at"]
    el.append(f'<div id="flash" class="clip ov flash" data-start="{fa}" data-duration="{round(T0 - fa + 0.8, 3)}" data-track-index="12"></div>')

    # Title, platforms, credit, fade out.
    a, b = g["title"]
    letters = "".join(f'<span class="L">{ch}</span>' for ch in LETTERS)
    el.append(f'<div id="ttitle" class="clip ov title-wrap" data-start="{a}" data-duration="{b - a}" data-track-index="13"><div class="title-stack" id="tstack">'
              f'<div class="word" id="word">{letters}</div><div class="rule" id="trule"></div><div class="sub" id="tsub">THE LAST FLIGHT</div></div></div>')
    a, b = g["platforms"]
    el.append(f'<div id="tplat" class="clip ov plat-wrap" data-start="{a}" data-duration="{round(b - a, 3)}" data-track-index="13"><div class="plat">'
              f'<div class="pill">{ICON_HEADSET}<span>{esc(edits.PLATFORM_VR)}</span></div>'
              f'<div class="pill alt">{ICON_LAPTOP}<span>{esc(edits.PLATFORM_PC)}</span></div></div></div>')
    a, b = g["credit"]
    el.append(f'<div id="tcredit" class="clip ov credit-wrap" data-start="{a}" data-duration="{round(b - a, 3)}" data-track-index="14"><div class="credit">'
              f'<div class="small">{edits.CREDIT_SMALL}</div><div class="name">{edits.CREDIT_NAME}</div><div class="bar" id="cbar"></div></div>'
              f'<div class="foot">{esc(edits.FOOTER)}</div></div>')
    a, b = g["fade_out"]
    el.append(f'<div id="fadeout" class="clip ov black" data-start="{a}" data-duration="{round(b - a, 3)}" data-track-index="15"></div>')

    # Sound.
    for i, stem in enumerate(("music", "vo", "sfx")):
        el.append(f'<audio id="{stem}" src="assets/audio/{stem}.wav" data-start="0" data-duration="{dur}" data-track-index="{20 + i}" data-volume="1"></audio>')

    events = {
        "id": f"skyfold-{cfg['name']}",
        "fadeIn": g["fade_in"], "location": g["location"],
        "radio": [[f"#rn{i}", a, b] for i, (_, a, b) in enumerate(g["radio"])] + [["#rtower", *g["tower"]]],
        "big": [{"id": c["id"], "in": c["in"], "out": c["out"], "delays": [d for _, d in c["lines"]]} for c in g["big"]],
        "objectives": [[o[0], o[3], o[4], o[5]] for o in g["objectives"]],
        "chips": [[c[0], c[2], c[3]] for c in g["chips"]],
        "fold": g["fold"], "lightning": g["lightning"], "flash": cfg["flash_at"],
        "title": g["title"], "letters": cfg["letters_at"], "letterStep": LETTER_STEP,
        "platforms": g["platforms"], "credit": g["credit"], "fadeOut": g["fade_out"], "duration": dur,
    }
    html = TEMPLATE
    html = html.replace("%%W%%", str(cfg["w"])).replace("%%H%%", str(cfg["h"])).replace("%%DUR%%", str(dur))
    html = html.replace("%%TITLE%%", f"SKYFOLD trailer ({cfg['name']})").replace("%%ID%%", events["id"])
    html = html.replace("%%FMT%%", "fmt-v" if v else "fmt-h").replace("%%CSS%%", CSS)
    html = html.replace("%%ELEMENTS%%", "\n      ".join(el))
    html = html.replace("%%EVENTS%%", json.dumps(events)).replace("%%AUDIO%%", json.dumps(audio_data, separators=(",", ":")))
    return html


TEMPLATE = r"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=%%W%%, height=%%H%%" />
    <title>%%TITLE%%</title>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>%%CSS%%</style>
  </head>
  <body>
    <div id="root" class="%%FMT%%" data-composition-id="%%ID%%" data-start="0" data-width="%%W%%" data-height="%%H%%" data-duration="%%DUR%%">
      %%ELEMENTS%%
    </div>
    <script>
      (function () {
        const EV = %%EVENTS%%;
        const AUDIO = %%AUDIO%%;
        const tl = gsap.timeline({ paused: true });

        // Opening: out of black.
        tl.fromTo("#fadein", { opacity: 1 }, { opacity: 0, duration: EV.fadeIn[1] - EV.fadeIn[0], ease: "power1.inOut" }, EV.fadeIn[0]);

        // Location card.
        const L0 = EV.location[0], L1 = EV.location[1];
        tl.fromTo("#loc .place", { opacity: 0, x: -30 }, { opacity: 1, x: 0, duration: 0.7, ease: "power3.out" }, L0);
        tl.fromTo("#loc .line", { scaleX: 0 }, { scaleX: 1, duration: 0.8, ease: "power3.inOut" }, L0 + 0.15);
        tl.fromTo("#loc .warn", { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 0.5, ease: "power2.out" }, L0 + 0.45);
        tl.to("#loc .warn .dot", { opacity: 0.2, duration: 0.45, ease: "sine.inOut", yoyo: true, repeat: Math.max(1, Math.floor((L1 - L0 - 1.4) / 0.45)) }, L0 + 0.9);
        tl.to("#loc .loc", { opacity: 0, y: 10, duration: 0.4, ease: "power2.in" }, L1 - 0.4);

        // Radio callers: slide in, a listening ring pulses, slide out.
        EV.radio.forEach(function (r) {
          const sel = r[0], a = r[1], b = r[2];
          tl.fromTo(sel + " .radio", { opacity: 0, x: -40 }, { opacity: 1, x: 0, duration: 0.45, ease: "power3.out" }, a);
          tl.fromTo(sel + " .ring", { scale: 0.92, opacity: 0.85 }, { scale: 1.3, opacity: 0, duration: 0.9, ease: "power1.out", repeat: Math.max(0, Math.floor((b - a - 0.9) / 0.9)) }, a + 0.3);
          tl.to(sel + " .radio", { opacity: 0, x: -24, duration: 0.35, ease: "power2.in" }, b - 0.35);
        });

        // Statement captions: each line lands out of a blur; all leave together.
        EV.big.forEach(function (c) {
          const lines = document.querySelectorAll("#" + c.id + " .ln");
          lines.forEach(function (ln, k) {
            tl.fromTo(ln, { opacity: 0, y: 34, scale: 1.06, filter: "blur(14px)" },
              { opacity: 1, y: 0, scale: 1, filter: "blur(0px)", duration: 0.5, ease: "power3.out" }, c.in + c.delays[k]);
          });
          tl.to(lines, { opacity: 0, y: -18, filter: "blur(10px)", duration: 0.32, ease: "power2.in" }, c.out - 0.32);
        });
        // The storm line shudders with the lightning.
        tl.fromTo("#cb5 .cap-inner", { x: 0 }, { x: 7, duration: 0.04, ease: "none", yoyo: true, repeat: 5 }, EV.lightning[0]);

        // Objectives: in, checked off when the action lands, out.
        EV.objectives.forEach(function (o) {
          const s = "#" + o[0], a = o[1], c = o[2], b = o[3];
          tl.fromTo(s + " .obj", { opacity: 0, x: 70 }, { opacity: 1, x: 0, duration: 0.5, ease: "power3.out" }, a);
          tl.to(s + " .n", { opacity: 0, scale: 0.6, duration: 0.18, ease: "power2.in" }, c);
          tl.to(s + " .obj-num", { backgroundColor: "#14918F", duration: 0.2 }, c);
          tl.to(s + " .tick", { strokeDashoffset: 0, duration: 0.32, ease: "power2.out" }, c + 0.06);
          tl.fromTo(s + " .pulse", { scale: 1, opacity: 0.9 }, { scale: 1.9, opacity: 0, duration: 0.6, ease: "power2.out" }, c);
          tl.to(s + " .todo", { opacity: 0, duration: 0.2 }, c);
          tl.to(s + " .done", { opacity: 1, duration: 0.2 }, c + 0.1);
          tl.to(s + " .obj", { opacity: 0, x: 40, duration: 0.35, ease: "power2.in" }, b - 0.35);
        });

        // Hint chips, like the in-game toast.
        EV.chips.forEach(function (ch) {
          const s = "#" + ch[0] + " .chip";
          tl.fromTo(s, { opacity: 0, y: 26 }, { opacity: 1, y: 0, duration: 0.35, ease: "power3.out" }, ch[1]);
          tl.fromTo(s, { x: ch[0] === "ch1" ? -12 : 0 }, { x: 0, duration: 0.45, ease: "elastic.out(1, 0.35)" }, ch[1] + 0.05);
          tl.to(s, { opacity: 0, y: 12, duration: 0.22, ease: "power2.in" }, ch[2] - 0.22);
        });

        // Paper fold: a pearl leaf swings in over the cut and folds away on the other side.
        const F = EV.fold;
        tl.set("#leaf", { transformOrigin: "100% 50%", rotationY: -90 }, F - 0.5);
        tl.set("#leaf-edge", { left: 0, right: "auto" }, F - 0.5);
        tl.to("#leaf", { rotationY: 0, duration: 0.42, ease: "power2.in" }, F - 0.46);
        tl.fromTo("#leaf-shade", { opacity: 0.55 }, { opacity: 0, duration: 0.42, ease: "power2.in" }, F - 0.46);
        tl.set("#leaf", { transformOrigin: "0% 50%" }, F);
        tl.set("#leaf-edge", { left: "auto", right: 0 }, F);
        tl.to("#leaf", { rotationY: 90, duration: 0.44, ease: "power2.out" }, F + 0.02);
        tl.to("#leaf-shade", { opacity: 0.55, duration: 0.44, ease: "power2.out" }, F + 0.02);

        // Lightning: a double strike.
        const LA = EV.lightning[0], LB = EV.lightning[1];
        tl.fromTo("#lightning", { opacity: 0 }, { opacity: 0.85, duration: 0.04, ease: "none" }, LA);
        tl.to("#lightning", { opacity: 0.08, duration: 0.09, ease: "none" }, LA + 0.05);
        tl.to("#lightning", { opacity: 0.6, duration: 0.04, ease: "none" }, LB);
        tl.to("#lightning", { opacity: 0, duration: 0.4, ease: "power2.out" }, LB + 0.05);

        // White-out into the title.
        const T0 = EV.title[0], T1 = EV.title[1];
        tl.fromTo("#flash", { opacity: 0 }, { opacity: 1, duration: 0.14, ease: "power2.in" }, EV.flash);
        tl.to("#flash", { opacity: 0, duration: 0.65, ease: "power2.out" }, T0 + 0.05);

        // Title: blurred miniature behind, letters fold down like paper, then the gold line and subtitle.
        tl.fromTo("#tbg-wrap", { scale: 1.04 }, { scale: 1.13, duration: EV.duration - T0, ease: "none" }, T0);
        tl.fromTo("#tgrad", { opacity: 0 }, { opacity: 1, duration: 0.6, ease: "power1.out" }, T0);
        tl.fromTo("#word .L", { rotationX: -100, opacity: 0, y: -24 },
          { rotationX: 0, opacity: 1, y: 0, duration: 0.6, ease: "back.out(1.7)", stagger: EV.letterStep }, EV.letters);
        const subAt = EV.letters + 7 * EV.letterStep + 0.3;
        tl.fromTo("#trule", { scaleX: 0 }, { scaleX: 1, duration: 0.6, ease: "power3.inOut" }, subAt - 0.2);
        tl.fromTo("#tsub", { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.8, ease: "power3.out" }, subAt);
        tl.to("#tstack", { opacity: 0, y: -20, duration: 0.4, ease: "power2.in" }, T1 - 0.4);

        // Platforms, then the credit.
        const P0 = EV.platforms[0], P1 = EV.platforms[1];
        tl.fromTo("#tplat .pill", { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.5, ease: "power3.out", stagger: 0.35 }, P0 + 0.1);
        tl.to("#tplat .pill", { opacity: 0, y: -12, duration: 0.3, ease: "power2.in" }, P1 - 0.3);
        const C0 = EV.credit[0];
        tl.fromTo("#tcredit .small", { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.5, ease: "power2.out" }, C0 + 0.05);
        tl.fromTo("#tcredit .name", { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.9, ease: "power3.out" }, C0 + 0.15);
        tl.fromTo("#cbar", { scaleX: 0 }, { scaleX: 1, duration: 0.6, ease: "power3.inOut" }, C0 + 0.45);
        tl.fromTo("#tcredit .foot", { opacity: 0 }, { opacity: 1, duration: 0.6 }, C0 + 0.6);
        tl.fromTo("#fadeout", { opacity: 0 }, { opacity: 1, duration: EV.fadeOut[1] - EV.fadeOut[0], ease: "power1.in" }, EV.fadeOut[0]);

        // Audio-reactive warmth behind the title: the music's low end swells the glow, its top end lights the gold line.
        const glow = document.getElementById("tglow-in"), rule = document.getElementById("trule");
        AUDIO.frames.forEach(function (fr, i) {
          tl.call(function () {
            glow.style.opacity = (0.22 + 0.5 * fr[0]).toFixed(3);
            glow.style.transform = "scale(" + (1 + 0.07 * fr[0]).toFixed(3) + ")";
            rule.style.boxShadow = "0 0 " + (6 + 26 * fr[1]).toFixed(1) + "px rgba(217, 164, 65, " + (0.25 + 0.6 * fr[1]).toFixed(2) + ")";
          }, [], AUDIO.start + i / AUDIO.fps);
        });

        window.__timelines[EV.id] = tl;
      })();
    </script>
  </body>
</html>
"""


# --------------------------------------------------------------------------------------------- main
def build(cfg):
    comp = OUT / cfg["name"] / "composition"
    assets = comp / "assets"
    (assets / "footage").mkdir(parents=True, exist_ok=True)
    (assets / "audio").mkdir(parents=True, exist_ok=True)
    used = {s[1] for s in cfg["shots"]} | {cfg["title_bg"][0]}
    for shot in sorted(used):
        src = CLIPS / f"{shot}_{cfg['aspect']}.mp4"
        dst = assets / "footage" / src.name
        if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            shutil.copy2(src, dst)
    print(f"{cfg['name']}: {len(used)} clips")
    audio = build_audio(cfg, assets / "audio")
    (comp / "index.html").write_text(build_html(cfg, audio), encoding="utf-8")
    print(f"  wrote {comp / 'index.html'}")


for key, cfg in edits.FORMATS.items():
    if WHICH in ("all", key):
        build(cfg)
