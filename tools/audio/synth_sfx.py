#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy"]
# ///
"""SKYFOLD sound effects and NURI chirps (offline, deterministic).

    python tools/audio/synth_sfx.py              # every SFX into Assets/Skyfold/Audio/SFX/
    python tools/audio/synth_sfx.py socket_snap nuri_happy_01

Sources: original numpy synthesis, plus a few Kenney.nl CC0 sounds from the
kanban-motion skill library (assets/sfx/...), always re-processed (pitch, filters,
layering, trims). The Kenney files used by each id are written to
tools/audio/reports/sfx_sources.json for the manifest.
Format: mono, 48 kHz, 16-bit PCM, peak -3 dBFS, DC-blocked, faded, low-passed (no harsh highs).
*_loop ids are built periodic (integer cycles / circular filters) so the seam is exact.
"""

from __future__ import annotations

import json
import sys
import zlib
from fractions import Fraction
from pathlib import Path

import numpy as np
from scipy import signal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skyaudio as sa  # noqa: E402
import skysynth as ss  # noqa: E402

SR = sa.SR
OUT = sa.AUDIO / "SFX"
REPORT = sa.TOOLS / "reports" / "sfx_sources.json"
_CACHE: dict = {}
USED: dict = {}
CUR = [None]


# --------------------------------------------------------------------------- helpers
def R(name):
    return np.random.default_rng(zlib.crc32(name.encode()))


def rate_shift(x, rate):
    fr = Fraction(rate).limit_denominator(64)
    return signal.resample_poly(x, fr.denominator, fr.numerator)


def K(rel, rate=1.0, lp=None, hp=None, gain_db=0.0, rev=False):
    """Kenney CC0 sample from the kanban-motion library, normalised to peak 1 then gained."""
    USED.setdefault(CUR[0], [])
    if rel not in USED[CUR[0]]:
        USED[CUR[0]].append(rel)
    if rel not in _CACHE:
        _CACHE[rel] = sa.load_lib(rel)
    x = _CACHE[rel].copy()
    if rate != 1.0:
        x = rate_shift(x, rate)
    if hp:
        x = sa.hp(x, hp, 2)
    if lp:
        x = sa.lp(x, lp, 4)
    if rev:
        x = x[::-1].copy()
    return x / (np.max(np.abs(x)) or 1) * sa.db2a(gain_db)


def layer(parts, extra=0.0):
    """parts: [(mono array, start_s, gain_db)] -> summed buffer."""
    end = max(int(round(t0 * SR)) + len(x) for x, t0, _ in parts) + int(extra * SR)
    buf = np.zeros(end)
    for x, t0, g in parts:
        x = sa.fade(x, 0.0005, 0.004) if len(x) > int(0.01 * SR) else x   # no truncation clicks
        sa.place(buf, x * sa.db2a(g), int(round(t0 * SR)))
    return buf


def T(dur):
    n = int(dur * SR)
    return n, np.arange(n) / SR


def sweep_tone(f, amps=(1.0,), phase=0.0):
    ph = 2 * np.pi * np.cumsum(f) / SR + phase
    return sum(a * np.sin((k + 1) * ph) for k, a in enumerate(amps))


def tick(r, f=1800.0, tau=0.006, ms=25, noise_amt=0.5):
    n, t = T(ms / 1000)
    y = np.sin(2 * np.pi * f * t) * np.exp(-t / tau) + 0.5 * np.sin(2 * np.pi * f * 1.73 * t) * np.exp(-t / (tau * 0.6))
    y += noise_amt * sa.fft_shape(r.standard_normal(n), sa.band_curve(1000, 6000)) * np.exp(-t / 0.0018)
    y[:16] *= np.linspace(0, 1, 16)
    return y / np.max(np.abs(y))


def stft_tv(x, gain_fn, nper=1024, hop=128):
    f, t, Z = signal.stft(x, fs=SR, nperseg=nper, noverlap=nper - hop, boundary="even", padded=True)
    G = gain_fn(t[None, :], f[:, None])
    _, y = signal.istft(Z * G, fs=SR, nperseg=nper, noverlap=nper - hop, boundary=True)
    y = y[: len(x)]
    return np.pad(y, (0, len(x) - len(y))) if len(y) < len(x) else y


def logbp(fc_fn, bw_oct):
    def g(t, f):
        return np.exp(-0.5 * (np.log2(np.maximum(f, 1.0) / fc_fn(t)) / bw_oct) ** 2)
    return g


def whoosh(dur, fc_fn, r, bw=0.8, amp_pts=None, color="pink"):
    n = int(dur * SR)
    x = sa.noise(n, r, color)
    if amp_pts:
        x = x * sa.env_points(n, amp_pts)
    y = stft_tv(x, logbp(fc_fn, bw))
    return y / (np.max(np.abs(y)) or 1)


def verb(x, wet=0.25, rt60=1.0, tail=None, seed=7):
    ir = sa.reverb_ir(rt60, predelay=0.008, seed=seed, length=rt60 * 1.1)[:, 0]
    tail = rt60 if tail is None else tail
    xx = np.concatenate([x, np.zeros(int(tail * SR))])
    w = signal.fftconvolve(xx, ir)[: len(xx)]
    return xx + wet * w * 0.35


def harm_tone(f0, n, amps, rng, f_traj=None):
    """Harmonic stack with optional per-sample frequency trajectory."""
    f = np.full(n, f0) if f_traj is None else f_traj
    ph = 2 * np.pi * np.cumsum(f) / SR
    return sum(a * np.sin((k + 1) * ph + rng.random() * 6.28) for k, a in enumerate(amps))


def mono(st):
    return st.mean(axis=1)


def trim_tail(y, floor_db=-62):
    a = np.abs(y)
    idx = np.where(a > a.max() * sa.db2a(floor_db))[0]
    end = min(len(y), (idx[-1] if len(idx) else len(y) - 1) + int(0.02 * SR))
    return y[:end]


def finish(y, lp=11000, hp=30, fin=0.0015, fout=0.012, peak=-3.0, max_dur=None):
    y = sa.hp(y, hp, 2)
    if lp:
        y = sa.lp(y, lp, 4)
    y = trim_tail(y)
    if max_dur and len(y) > max_dur * SR:
        y = y[: int(max_dur * SR)]
        fout = max(fout, min(0.35, max_dur * 0.2))
    y = sa.fade(y, fin, fout)
    w = np.hanning(len(y))                     # remove residual mean of very short transients without
    y = y - np.mean(y) * w / np.mean(w)        # moving the (zero) end points
    return sa.peak_normalize(y, peak)


def finish_loop(y, lp=9000, hp=30, peak=-3.0):
    y = y - np.mean(y)
    y = sa.filt_circ(y, sa.sos("highpass", hp, 2))
    if lp:
        y = sa.filt_circ(y, sa.sos("lowpass", lp, 4))
    return sa.peak_normalize(y, peak)


# --------------------------------------------------------------------------- NURI
def nuri_syl(f_pts, dur, amp_pts=None, vib=(0.0, 0.0), trill=(0.0, 0.0), h=(1.0, 0.14, 0.04), shimmer=0.06):
    n, t = T(dur)
    f = sa.env_points(n, f_pts)
    if vib[0]:
        f = f * (1 + vib[1] * np.sin(2 * np.pi * vib[0] * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = h[0] * np.sin(ph) + h[1] * np.sin(2 * ph + 0.3) + h[2] * np.sin(3 * ph + 0.7)
    if trill[0]:
        y *= (1 - trill[1]) + trill[1] * (0.5 + 0.5 * np.sin(2 * np.pi * trill[0] * t - np.pi / 2))
    y += shimmer * np.sin(2.76 * ph + 1.1) * np.exp(-t / 0.022)          # tiny metallic glint
    amp = sa.env_points(n, amp_pts or [(0, 0), (0.008, 1), (dur * 0.75, 0.85), (dur, 0)])
    return sa.fade(y * amp, 0.003, 0.006)          # every syllable starts and ends at zero


def nuri_seq(syls):
    """syls: [(syllable array, gap_after_s)]"""
    parts, t0 = [], 0.0
    for s, gap in syls:
        parts.append((s, t0, 0.0))
        t0 += len(s) / SR + gap
    return layer(parts, 0.01)


def nuri_post(y):
    y = sa.hp(y, 900, 2)
    y = sa.lp(y, 9000, 4)
    return y


def nuri_happy_01(r):
    return nuri_post(nuri_seq([
        (nuri_syl([(0, 1900), (0.07, 3000)], 0.075), 0.04),
        (nuri_syl([(0, 2100), (0.07, 3400), (0.1, 3150)], 0.1), 0.0)]))


def nuri_happy_02(r):
    return nuri_post(nuri_seq([
        (nuri_syl([(0, 2800), (0.3, 3150)], 0.3, vib=(26, 0.07), trill=(26, 0.6),
                  amp_pts=[(0, 0), (0.02, 0.7), (0.15, 1), (0.3, 0.3)]), 0.02),
        (nuri_syl([(0, 2600), (0.08, 3600)], 0.085), 0.0)]))


def nuri_happy_03(r):
    return nuri_post(nuri_seq([
        (nuri_syl([(0, 2450), (0.05, 2350)], 0.05), 0.045),
        (nuri_syl([(0, 2450), (0.05, 2350)], 0.05), 0.05),
        (nuri_syl([(0, 2000), (0.12, 3500), (0.16, 3300)], 0.16, vib=(14, 0.02)), 0.0)]))


def nuri_happy_04(r):
    return nuri_post(nuri_seq([
        (nuri_syl([(0, 2200), (0.25, 2800)], 0.25, vib=(12, 0.06),
                  amp_pts=[(0, 0), (0.015, 0.9), (0.2, 1), (0.25, 0.2)]), 0.03),
        (nuri_syl([(0, 2400), (0.07, 3500)], 0.07), 0.0)]))


def nuri_curious_01(r):
    return nuri_post(nuri_seq([
        (nuri_syl([(0, 2250), (0.06, 2200)], 0.06), 0.05),
        (nuri_syl([(0, 1800), (0.15, 2100), (0.26, 2950)], 0.26, vib=(7, 0.012),
                  amp_pts=[(0, 0), (0.02, 0.7), (0.2, 1), (0.26, 0)]), 0.0)]))


def nuri_curious_02(r):
    return nuri_post(nuri_seq([
        (nuri_syl([(0, 2000), (0.15, 2050)], 0.15, trill=(30, 0.7), amp_pts=[(0, 0), (0.02, 0.8), (0.15, 0.6)]), 0.01),
        (nuri_syl([(0, 2000), (0.18, 3200)], 0.18, amp_pts=[(0, 0), (0.02, 0.7), (0.14, 1), (0.18, 0)]), 0.0)]))


def nuri_curious_03(r):
    return nuri_post(nuri_seq([
        (nuri_syl([(0, 2600), (0.08, 2550)], 0.08), 0.02),
        (nuri_syl([(0, 2300), (0.08, 2250)], 0.08), 0.03),
        (nuri_syl([(0, 2400), (0.2, 3400)], 0.2, amp_pts=[(0, 0), (0.02, 0.8), (0.16, 1), (0.2, 0)]), 0.0)]))


def nuri_concern_01(r):
    return nuri_post(nuri_seq([
        (nuri_syl([(0, 3000), (0.3, 1800)], 0.32, vib=(8, 0.015),
                  amp_pts=[(0, 0), (0.03, 0.8), (0.2, 0.7), (0.32, 0)]), 0.0)]))


def nuri_concern_02(r):
    return nuri_post(nuri_seq([
        (nuri_syl([(0, 2600), (0.15, 2200)], 0.15, amp_pts=[(0, 0), (0.02, 0.9), (0.15, 0.2)]), 0.06),
        (nuri_syl([(0, 2300), (0.22, 1700)], 0.22, amp_pts=[(0, 0), (0.02, 0.8), (0.22, 0)]), 0.0)]))


def nuri_concern_03(r):
    return nuri_post(nuri_seq([
        (nuri_syl([(0, 2100), (0.4, 1700)], 0.42, vib=(6, 0.055),
                  amp_pts=[(0, 0), (0.05, 0.6), (0.3, 0.7), (0.42, 0)]), 0.02),
        (nuri_syl([(0, 2000), (0.09, 1650)], 0.09, amp_pts=[(0, 0), (0.01, 0.5), (0.09, 0)]), 0.0)]))


def nuri_celebrate_01(r):
    syls = []
    for k, f0 in enumerate([2000, 2300, 2600, 3000, 3400]):
        syls.append((nuri_syl([(0, f0), (0.055, f0 * 1.25)], 0.06), 0.03))
    syls.append((nuri_syl([(0, 3200), (0.22, 3350)], 0.22, vib=(28, 0.06), trill=(28, 0.55), shimmer=0.1,
                          amp_pts=[(0, 0), (0.02, 1), (0.16, 0.9), (0.22, 0)]), 0.0))
    return nuri_post(nuri_seq(syls))


def nuri_celebrate_02(r):
    return nuri_post(nuri_seq([
        (nuri_syl([(0, 2400), (0.42, 3400)], 0.42, vib=(24, 0.05), trill=(24, 0.6), shimmer=0.1,
                  amp_pts=[(0, 0), (0.03, 0.8), (0.3, 1), (0.42, 0.4)]), 0.04),
        (nuri_syl([(0, 2600), (0.07, 3600)], 0.07), 0.035),
        (nuri_syl([(0, 2800), (0.09, 3900), (0.12, 3700)], 0.12), 0.0)]))


def nuri_point_01(r):
    s = lambda: nuri_syl([(0, 3600), (0.04, 2600)], 0.045, amp_pts=[(0, 0), (0.005, 1), (0.045, 0)], shimmer=0.09)
    return nuri_post(nuri_seq([(s(), 0.06), (s(), 0.0)]))


def nuri_point_02(r):
    return nuri_post(nuri_seq([
        (nuri_syl([(0, 2000), (0.09, 3800), (0.14, 3100)], 0.14, shimmer=0.09,
                  amp_pts=[(0, 0), (0.008, 0.8), (0.07, 1), (0.095, 0.55), (0.11, 0.7), (0.14, 0)]), 0.0)]))


# --------------------------------------------------------------------------- puzzle
def piece_pickup(r):
    a = K("impact/impactWood_light_002.ogg", rate=1.35, lp=6500, gain_db=-5)
    n, t = T(0.12)
    blip = np.sin(2 * np.pi * np.cumsum(520 + 380 * (1 - np.exp(-t / 0.04))) / SR) * sa.env_exp(n, 0.045, 0.004)
    sw = whoosh(0.16, lambda tt: 900 + 1600 * np.clip(tt / 0.16, 0, 1), r, bw=0.8,
                amp_pts=[(0, 0), (0.06, 1), (0.16, 0)])
    return layer([(a, 0, 0), (blip, 0.005, -9), (sw, 0, -20)])


def piece_drop(r):
    return layer([(K("impact/impactSoft_medium_002.ogg"), 0, 0),
                  (K("impact/impactWood_light_001.ogg", rate=0.92, lp=5000), 0.003, -5),
                  (K("interface/click_003.ogg", lp=5000), 0.062, -16)])


def piece_rotate(r):
    parts = []
    for i, (t0, f) in enumerate([(0.0, 1650), (0.048, 1800), (0.096, 1950)]):
        parts.append((sa.lp(tick(r, f, 0.005, noise_amt=0.25), 6000, 2), t0, -8 + 2 * i))
        parts.append((K(["interface/click_002.ogg", "interface/click_003.ogg", "interface/click_005.ogg"][i],
                        lp=6000), t0 + 0.001, -16))
    sw = whoosh(0.22, lambda tt: 1200 + 900 * np.clip(tt / 0.22, 0, 1), r, bw=0.6,
                amp_pts=[(0, 0), (0.1, 1), (0.22, 0)])
    parts.append((sw, 0.0, -19))
    return layer(parts)


def socket_snap(r):
    n, t = T(0.15)
    body = np.sin(2 * np.pi * 160 * t) * np.exp(-t / 0.04)
    body[:48] *= np.linspace(0, 1, 48)
    chime = (ss.bell(81, r, tau=0.55, vel=1.0, partials=ss.BELL_GLASS, attack=0.006, dur=1.0)
             + 0.6 * ss.bell(88, r, tau=0.45, vel=1.0, partials=ss.BELL_GLASS, attack=0.006, dur=1.0))
    chime = verb(chime, wet=0.3, rt60=0.9)
    return layer([(K("impact/impactMetal_medium_002.ogg", lp=6000), 0, -2),
                  (tick(r, 2300, 0.008), 0.022, -6),
                  (body, 0.0, -8),
                  (chime, 0.035, -7)])


def _nope_note(m, dur, r):
    n, t = T(dur)
    f0 = float(sa.midi_hz(m)) * 2 ** ((-30 * np.clip((t - dur * 0.6) / (dur * 0.4), 0, 1)) / 1200)
    y = harm_tone(0, n, [1, 0, 0.3, 0, 0.15, 0, 0.08], r, f_traj=f0)
    y = sa.lp(y, 1600, 2) * sa.env_ar(n, 0.012, 0.05)
    return y


def socket_reject(r):
    n, t = T(0.2)
    low = np.sin(2 * np.pi * np.cumsum(110 + 40 * np.exp(-t / 0.02)) / SR) * np.exp(-t / 0.07)
    low[:48] *= np.linspace(0, 1, 48)
    return layer([(K("impact/impactSoft_medium_001.ogg"), 0, 0), (low, 0, -6),
                  (_nope_note(64, 0.12, r), 0.05, -5), (_nope_note(60, 0.18, r), 0.19, -5)])


def bridge_assemble(r):
    n, t = T(1.5)
    f = 180 + 240 * (0.5 - 0.5 * np.cos(np.pi * np.clip(t / 1.4, 0, 1)))
    servo = harm_tone(0, n, [1, 0.5, 0.33, 0.25, 0.2, 0.16], r, f_traj=f)
    servo *= 0.75 + 0.25 * np.sin(2 * np.pi * 28 * t)
    servo = sa.lp(servo, 3000, 2) * sa.env_points(n, [(0, 0), (0.1, 0.7), (1.2, 1), (1.5, 0)])
    parts = [(servo, 0.0, -13)]
    N = 12
    clicks = ["interface/click_002.ogg", "interface/click_003.ogg", "interface/click_005.ogg"]
    for k in range(N):
        tk = 0.08 + 1.3 * (k / N) ** 0.7
        parts.append((sa.lp(tick(r, 1600 + 40 * k, 0.005, noise_amt=0.25), 6000, 2), tk, -15))
        parts.append((K(clicks[k % 3], lp=6000), tk, -19))
    for rel, tk in [("impact/impactPlank_medium_001.ogg", 0.32), ("impact/impactPlank_medium_002.ogg", 0.78),
                    ("impact/impactPlank_medium_003.ogg", 1.12)]:
        parts.append((K(rel, rate=1.25, lp=5000), tk, -8))
    parts.append((K("impact/impactSoft_heavy_001.ogg"), 1.42, -1))
    parts.append((K("impact/impactWood_medium_000.ogg", lp=4000), 1.425, -9))
    chime = np.zeros(int(1.4 * SR))
    for i, m in enumerate([74, 78, 81, 86]):
        sa.place(chime, ss.bell(m, r, tau=0.7, partials=ss.BELL_SOFT, attack=0.004, dur=1.2) * (0.8 + 0.07 * i),
                 int(i * 0.07 * SR))
    parts.append((verb(chime, 0.35, 1.2), 1.46, -8))
    return layer(parts)


def route_complete(r):
    buf = np.zeros(int(2.0 * SR))
    for i, m in enumerate([74, 78, 81, 86, 90]):
        x = ss.fm_bell(m, r, tau=0.9, ratio=1.0, index=1.6, itau=0.15, dur=1.5) \
            + 0.4 * sa.lp(ss.pluck(m, r, "harp", vel=0.6, dur=1.5), 6000, 2)
        sa.place(buf, x * (0.75 + 0.06 * i), int(i * 0.09 * SR))
    padn = int(1.3 * SR)
    pad = sum(mono(ss.pad_note(m, 0.6, r, attack=0.2, release=0.7, bright=0.7)) for m in (62, 66, 69))[:padn]
    sh = np.zeros(int(1.0 * SR))
    sa.place(sh, ss.glass(93, r, 0.6, tau=0.6), 0)
    sa.place(sh, ss.glass(98, r, 0.5, tau=0.5), int(0.1 * SR))
    return verb(layer([(buf, 0, 0), (pad, 0, -14), (sh, 0.4, -20)]), 0.3, 1.6, tail=0.4)


def fold_out(r):
    w = whoosh(1.0, lambda tt: 450 + 2750 * np.exp(-tt / 0.3), r, bw=0.9,
               amp_pts=[(0, 0), (0.3, 1), (0.65, 0.6), (1.0, 0)])
    n, t = T(0.3)
    settle = np.sin(2 * np.pi * 90 * t) * np.exp(-t / 0.1)
    settle[:96] *= np.linspace(0, 1, 96)
    return layer([(w, 0, 0), (K("casino/card-slide-1.ogg", lp=5500), 0.12, -11),
                  (K("casino/card-fan-1.ogg", rate=0.9, lp=5000), 0.35, -15),
                  (settle, 0.8, -14), (K("impact/impactSoft_medium_000.ogg"), 0.8, -14)])


def fold_in(r):
    w = whoosh(0.95, lambda tt: 450 + 2750 * (np.clip(tt / 0.9, 0, 1) ** 2), r, bw=0.9,
               amp_pts=[(0, 0), (0.55, 0.6), (0.85, 1), (0.95, 0)])
    paper = K("casino/card-slide-1.ogg", lp=5500, rev=True)
    sparkle = verb(ss.glass(93, r, 0.7, tau=0.5), 0.4, 1.0)
    return layer([(w, 0, 0), (paper, max(0.0, 0.88 - len(paper) / SR), -11), (sparkle, 0.88, -20)])


# --------------------------------------------------------------------------- power
def cell_pickup(r):
    n, t = T(0.12)
    bloop = np.sin(2 * np.pi * np.cumsum(380 + 340 * (1 - np.exp(-t / 0.03))) / SR) * sa.env_exp(n, 0.08, 0.004)
    n2, t2 = T(0.5)
    hum = harm_tone(120, n2, [1, 0.5, 0.3, 0.2], r) * sa.env_points(n2, [(0, 0), (0.05, 1), (0.3, 0.6), (0.5, 0)])
    return layer([(bloop, 0, -6), (K("impact/impactGlass_light_001.ogg", lp=6000), 0, -12), (hum, 0.01, -16)])


def cell_insert(r):
    n, t = T(1.15)
    u = np.clip((t - 0.05) / 0.9, 0, 1)
    f = 55 + 55 * (0.5 - 0.5 * np.cos(np.pi * u))
    ph = 2 * np.pi * np.cumsum(f) / SR
    fc = 400 + 2000 * u
    hum = np.zeros(n)
    for k in range(1, 11):
        a = (1 / k ** 1.2) * (1.4 if k % 2 else 1.0) / (1 + (k * f / fc) ** 4)
        hum += a * np.sin(k * ph + r.random() * 6.28)
    hum *= sa.env_points(n, [(0.05, 0), (0.25, 0.5), (0.9, 1), (1.15, 0)])
    return layer([(K("impact/impactMetal_medium_000.ogg", lp=6500), 0, -2),
                  (K("interface/switch_007.ogg", lp=5000), 0.015, -8),
                  (hum, 0.0, -6), (ss.bell(81, r, tau=0.4, dur=0.8), 0.95, -16)])


def power_transfer(r):
    n, t = T(2.15)
    u = np.clip(t / 1.8, 0, 1)
    f = 80 + 160 * u ** 1.3
    ph = 2 * np.pi * np.cumsum(f) / SR
    fc = 500 + 2500 * u
    hum = np.zeros(n)
    for k in range(1, 15):
        hum += (1 / k) / (1 + (k * f / fc) ** 4) * np.sin(k * ph + r.random() * 6.28)
    trem_rate = 4 + 10 * u
    hum *= 1 - 0.25 * (0.5 + 0.5 * np.sin(2 * np.pi * np.cumsum(trem_rate) / SR))
    hum *= sa.env_points(n, [(0, 0), (0.3, 0.5), (1.7, 1), (2.1, 0)])
    parts = [(hum, 0, -6)]
    notes = [93, 95, 97, 98, 100, 102]
    for k in range(40):
        tk = 0.4 + 1.55 * r.random() ** 0.6
        parts.append((ss.glass(int(r.choice(notes)), r, 0.5 + 0.4 * r.random(), tau=0.15 + 0.15 * r.random()),
                      tk, -20 - 4 * r.random()))
    parts.append((ss.bell(86, r, tau=0.6, dur=1.2) + 0.6 * ss.bell(93, r, tau=0.5, dur=1.2), 1.9, -12))
    return layer(parts)


def substation_on(r):
    n, t = T(0.9)
    thunk = np.sin(2 * np.pi * np.cumsum(48 + 47 * np.exp(-t / 0.05)) / SR) * np.exp(-t / 0.3)
    thunk[:96] *= np.linspace(0, 1, 96)
    n2, t2 = T(2.6)
    hum = harm_tone(100, n2, [1, 0.6, 0.35, 0.25, 0.15, 0.1, 0.08], r) + 0.3 * np.sin(2 * np.pi * 50 * t2)
    hum *= (0.9 + 0.1 * np.sin(2 * np.pi * 0.7 * t2)) * sa.env_points(n2, [(0.08, 0), (0.6, 1), (2.0, 0.8), (2.6, 0)])
    parts = [(thunk, 0, -2), (K("impact/impactSoft_heavy_002.ogg"), 0, -3),
             (K("impact/impactMetal_heavy_000.ogg", lp=5000), 0.002, -10), (sa.lp(hum, 2500, 2), 0, -10)]
    for tk, g in [(0.35, -12), (0.47, -14), (0.6, -13), (0.9, -16)]:
        parts.append((sa.lp(tick(r, 2000, 0.006, noise_amt=0.3), 6000, 2), tk, g))
        parts.append((K("interface/click_001.ogg", lp=6000), tk, g - 4))
    return layer(parts)


def switch_lever(r):
    n, t = T(0.25)
    th = np.sin(2 * np.pi * 85 * t) * np.exp(-t / 0.06)
    th[:48] *= np.linspace(0, 1, 48)
    ring = (np.sin(2 * np.pi * 620 * t) + 0.5 * np.sin(2 * np.pi * 1500 * t)) * np.exp(-t / 0.12)
    ring[:48] *= np.linspace(0, 1, 48)
    return layer([(K("interface/switch_007.ogg", lp=6000), 0, -6),
                  (K("impact/impactMetal_heavy_004.ogg", lp=6000), 0.03, -2), (th, 0.03, -8), (ring, 0.04, -24)])


def beacon_on(r):
    n, t = T(1.4)
    hum = harm_tone(220, n, [1, 0.4, 0.2, 0.1], r) * (1 - 0.08 * (0.5 + 0.5 * np.sin(2 * np.pi * 6 * t)))
    hum *= sa.env_points(n, [(0.03, 0), (0.3, 1), (1.0, 0.7), (1.4, 0)])
    ping = ss.bell(86, r, tau=0.55, attack=0.005, dur=1.4) + 0.3 * ss.fm_bell(86, r, tau=0.4, ratio=2.0, index=1.0, dur=1.4)
    return layer([(ping, 0, -4), (hum, 0, -14)])


def warning_chime(r):
    def ding(m):
        return ss.fm_bell(m, r, tau=0.6, ratio=1.0, index=1.2, itau=0.12, dur=1.2) \
            + 0.8 * ss.bell(m, r, tau=0.8, partials=ss.BELL_TUBE, dur=1.2)
    return verb(layer([(ding(81), 0, 0), (ding(77), 0.38, 0)]), 0.15, 1.0, tail=0.3)


def _thunder(r, dur, bursts, crack=0.4, lp_hz=420):
    n, t = T(dur)
    br = sa.noise(n, r, "brown")
    env = np.zeros(n)
    for t0, a, att, tau in bursts:
        e = np.where(t >= t0, (1 - np.exp(-(t - t0) / att)) * np.exp(-(t - t0) / tau), 0.0)
        env += a * e
    rumble = sa.lp(br * env, lp_hz, 4)
    mid = sa.lp(sa.hp(sa.noise(n, r, "pink"), 150, 2), 900, 4) * env * crack
    t0 = bursts[0][0]
    crackle = mid * np.exp(-np.maximum(t - t0, 0) / 0.6)
    tail = sa.lp(sa.noise(n, r, "brown"), 120, 4) * np.where(t >= t0, np.exp(-(t - t0) / 1.8), 0) * 0.5 \
        * (1 - np.exp(-np.maximum(t - t0, 0) / 0.3))
    y = rumble + crackle + tail
    return sa.fade(y, 0.05, 0.6)


def thunder_far_01(r):
    return _thunder(r, 5.0, [(0.15, 1.0, 0.12, 0.9), (0.6, 0.7, 0.2, 1.2), (1.4, 0.45, 0.3, 1.4)])


def thunder_far_02(r):
    return _thunder(r, 6.0, [(0.1, 0.6, 0.15, 0.6), (0.5, 1.0, 0.1, 0.8), (1.8, 0.8, 0.25, 1.1),
                             (2.6, 0.4, 0.3, 1.5)], crack=0.5)


def thunder_far_03(r):
    return _thunder(r, 4.2, [(0.2, 1.0, 0.25, 1.1), (1.0, 0.5, 0.3, 1.2)], crack=0.25, lp_hz=320)


def checkpoint(r):
    def n_(m):
        return ss.bell(m, r, tau=0.7, dur=1.2) + 0.25 * sa.lp(ss.pluck(m, r, "harp", vel=0.6, dur=1.2), 5000, 2)
    return verb(layer([(n_(81), 0, -1), (n_(86), 0.11, 0)]), 0.2, 1.2, tail=0.3)


def objective_complete(r):
    parts = []
    for i, m in enumerate([86, 90, 93]):
        x = layer([(ss.glass(m, r, 0.9, tau=0.6), 0, 0),
                   (ss.fm_bell(m - 12, r, tau=0.5, ratio=1.0, index=0.8, dur=1.0), 0, -8)])
        parts.append((x, i * 0.08, -2 - (i == 1)))
    return verb(layer(parts), 0.25, 1.2, tail=0.3)


def hint_ping(r):
    p = ss.fm_bell(88, r, tau=0.35, ratio=2.0, index=0.8, itau=0.1, dur=0.6)
    p = sa.lp(p, 6000, 2)
    return layer([(p, 0, 0), (p, 0.17, -10), (p, 0.34, -18)])


# --------------------------------------------------------------------------- UI
def ui_hover(r):
    n, t = T(0.055)
    y = np.sin(2 * np.pi * 2000 * t) * np.exp(-t / 0.012) + 0.25 * np.sin(2 * np.pi * 3000 * t) * np.exp(-t / 0.006)
    y[:72] *= np.linspace(0, 1, 72)
    return y


def ui_click(r):
    n, t = T(0.08)
    body = np.sin(2 * np.pi * 1100 * t) * np.exp(-t / 0.018) + 0.16 * np.sin(2 * np.pi * 2200 * t) * np.exp(-t / 0.008)
    body[:48] *= np.linspace(0, 1, 48)
    return layer([(K("interface/click_003.ogg", lp=7000), 0, -3), (body, 0, -6)])


def ui_back(r):
    def blip(f, dur, tau):
        n, t = T(dur)
        y = np.sin(2 * np.pi * f * t) * np.exp(-t / tau)
        y[:72] *= np.linspace(0, 1, 72)
        return y
    return layer([(blip(1250, 0.05, 0.02), 0, 0), (blip(900, 0.075, 0.03), 0.055, -1)])


def ui_toggle(r):
    s = K("interface/switch_007.ogg", lp=6500)[: int(0.18 * SR)]
    s = sa.fade(s, 0.001, 0.05)
    n, t = T(0.06)
    bl = np.sin(2 * np.pi * 1500 * t) * np.exp(-t / 0.02)
    bl[:48] *= np.linspace(0, 1, 48)
    return layer([(s, 0, 0), (bl, 0.0, -10)])


def ui_slider_tick(r):
    n, t = T(0.03)
    y = np.sin(2 * np.pi * 2600 * t) * np.exp(-t / 0.004) + 0.6 * np.sin(2 * np.pi * 1300 * t) * np.exp(-t / 0.006)
    y[:24] *= np.linspace(0, 1, 24)
    return y


# --------------------------------------------------------------------------- car
def car_enter(r):
    n, t = T(0.5)
    clunk = np.sin(2 * np.pi * np.cumsum(75 + 35 * np.exp(-t / 0.03)) / SR) * np.exp(-t / 0.12)
    clunk[:96] *= np.linspace(0, 1, 96)
    swing = whoosh(0.22, lambda tt: 600 + 300 * np.clip(tt / 0.22, 0, 1), r, bw=1.0,
                   amp_pts=[(0, 0), (0.12, 1), (0.22, 0)])
    n3, t3 = T(0.42)
    creak = sa.fft_shape(r.standard_normal(n3), sa.band_curve(250, 700)) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t3)) \
        * sa.env_points(n3, [(0, 0), (0.08, 1), (0.42, 0)])
    return layer([(tick(r, 1500, 0.006), 0, -12), (swing, 0.02, -20), (clunk, 0.25, -2),
                  (K("impact/impactSoft_heavy_004.ogg"), 0.25, -3),
                  (K("impact/impactMetal_medium_001.ogg", lp=4000), 0.252, -12), (creak, 0.33, -22)])


def car_start(r):
    n, t = T(1.65)
    u = np.clip(t / 1.1, 0, 1)
    f = 60 + 200 * (1 - (1 - u) ** 2.2) - 70 * np.clip((t - 1.1) / 0.3, 0, 1) ** 1.5
    whine = harm_tone(0, n, [1, 0.5, 0.3, 0.2, 0.12, 0.08], r, f_traj=f)
    whine += 0.06 * np.sin(2 * np.pi * np.cumsum(7.5 * f) / SR)
    whine *= sa.env_points(n, [(0, 0), (0.15, 0.6), (1.1, 1), (1.3, 0.8), (1.65, 0)])
    chime = layer([(ss.bell(88, r, tau=0.3, dur=0.6), 0, 0), (ss.bell(93, r, tau=0.35, dur=0.6), 0.11, 0)])
    return layer([(tick(r, 1800, 0.006), 0, -10), (sa.lp(whine, 4500, 2), 0.02, -4), (chime, 1.05, -16)])


def car_motor_loop(r):
    n = 2 * SR                                     # 2.000 s; every partial completes whole cycles
    t = np.arange(n) / SR
    y = harm_tone(240.0, n, [1, 0.45, 0.3, 0.18, 0.12, 0.08, 0.05, 0.03], r)
    y += 0.05 * np.sin(2 * np.pi * 1000.0 * t + 0.4) + 0.025 * np.sin(2 * np.pi * 1500.5 * t)
    y *= 1 + 0.04 * np.sin(2 * np.pi * 1.0 * t)
    nz = sa.fft_shape(r.standard_normal(n), sa.band_curve(200, 3000))
    y += 0.05 * nz / np.std(nz) * (1 + 0.3 * np.sin(2 * np.pi * 240.0 * t))
    return finish_loop(y, lp=4500)


def car_roll_loop(r):
    n = 3 * SR
    t = np.arange(n) / SR
    y = sa.noise(n, r, "brown") + 0.3 * sa.noise(n, r, "pink")
    y = sa.fft_shape(y, sa.band_curve(60, 1400))
    hiss = sa.fft_shape(r.standard_normal(n), sa.band_curve(1500, 5000))
    y = y / np.std(y) + 0.08 * hiss / np.std(hiss)
    mod = 1 + 0.08 * np.sin(2 * np.pi * 5 * t / 3.0) + 0.06 * (sa.smooth_random(n, 12, r) - 0.5)
    return finish_loop(y * mod, lp=4500)


def car_bump(r):
    n, t = T(0.35)
    th = np.sin(2 * np.pi * np.cumsum(70 + 40 * np.exp(-t / 0.02)) / SR) * np.exp(-t / 0.1)
    th[:96] *= np.linspace(0, 1, 96)
    return layer([(K("impact/impactSoft_heavy_003.ogg"), 0, 0), (th, 0, -4),
                  (K("impact/impactTin_medium_001.ogg", lp=3500), 0.04, -16),
                  (K("impact/impactSoft_medium_003.ogg"), 0.12, -10)])


def car_horn(r):
    n, t = T(0.32)
    bend = 2 ** ((-40 * np.exp(-t / 0.025)) / 1200)
    amps = [1, 0, 0.33, 0, 0.2, 0, 0.14, 0, 0.11]
    y = harm_tone(0, n, amps, r, f_traj=440.0 * bend) + 0.9 * harm_tone(0, n, amps, r, f_traj=554.37 * bend)
    y = sa.lp(y, 2800, 4)
    y = sa.peak_eq(y, 1200, 3.0, 1.0)
    return y * sa.env_ar(n, 0.008, 0.05)


def convoy_beep(r):
    def b():
        n, t = T(0.11)
        amps = [1, 0, 0.3, 0, 0.15, 0, 0.08]
        y = harm_tone(349.23, n, amps, r) + harm_tone(440.0, n, amps, r)
        return sa.lp(y, 2200, 4) * sa.env_ar(n, 0.008, 0.03)
    return layer([(b(), 0, 0), (b(), 0.16, 0)])


def splash(r):
    n, t = T(1.8)
    imp = sa.fft_shape(sa.noise(n, r, "pink"), sa.band_curve(150, 3500)) * (1 - np.exp(-t / 0.003)) * np.exp(-t / 0.22)
    th = np.sin(2 * np.pi * 65 * t) * np.exp(-t / 0.12)
    th[:96] *= np.linspace(0, 1, 96)
    spray = sa.fft_shape(r.standard_normal(n), sa.band_curve(1800, 6500)) * (1 - np.exp(-t / 0.01)) * np.exp(-t / 0.45)
    parts = [(imp / np.max(np.abs(imp)), 0, 0), (th, 0, -4), (spray / np.max(np.abs(spray)), 0.02, -8)]
    for k in range(35):
        tk = 0.08 + 1.4 * r.random() ** 1.8
        d = 0.025 + 0.035 * r.random()
        nb, tb = T(d)
        f0 = 300 + 800 * r.random()
        fb = f0 * np.exp(tb / (d * 1.6))
        bub = np.sin(2 * np.pi * np.cumsum(fb) / SR) * np.sin(np.pi * tb / d) ** 2
        parts.append((bub, tk, -12 - 8 * r.random() - 6 * (tk / 1.5)))
    n2, t2 = T(1.4)
    slosh = sa.fft_shape(sa.noise(n2, r, "pink"), sa.band_curve(200, 900)) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t2)) \
        * sa.env_points(n2, [(0, 0), (0.2, 1), (1.4, 0)])
    parts.append((slosh / np.max(np.abs(slosh)), 0.3, -14))
    return layer(parts)


# --------------------------------------------------------------------------- aircraft
def _turboprop(n, f1, f2, whine1, whine2, noise_gain, r, circular=False, chop=0.35):
    """f1/f2/whine*: scalars (loop) or per-sample arrays (one-shots)."""
    def arr(v):
        return np.full(n, float(v)) if np.isscalar(v) else v
    f1, f2, w1, w2 = arr(f1), arr(f2), arr(whine1), arr(whine2)
    y = np.zeros(n)
    for f in (f1, f2):
        ph = 2 * np.pi * np.cumsum(f) / SR
        for k in range(1, 25):
            form = 1 / (1 + ((k * np.mean(f) - 300) / 400) ** 2)
            y += (1 / k ** 0.9) * form * np.sin(k * ph + r.random() * 6.28)
    y *= 0.5
    y += 0.03 * (np.sin(2 * np.pi * np.cumsum(w1) / SR) + np.sin(2 * np.pi * np.cumsum(w2) / SR + 1.0))
    nz = sa.noise(n, r, "pink")
    roar = sa.fft_shape(nz, sa.band_curve(80, 1500)) if circular else sa.bp(nz, 80, 1500, 2)
    air = sa.fft_shape(r.standard_normal(n), sa.band_curve(1500, 4000)) if circular else sa.bp(r.standard_normal(n), 1500, 4000, 2)
    roar = roar / np.std(roar) * (1 + chop * np.sin(2 * np.pi * np.cumsum(f1) / SR))
    y += noise_gain * (0.35 * roar + 0.06 * air / np.std(air))
    return y


def plane_idle_loop(r):
    n = 4 * SR                                     # 4 s: all rates are multiples of 0.25 Hz
    y = _turboprop(n, 62.0, 62.75, 2250.0, 2262.5, 1.0, r, circular=True)
    return finish_loop(y, lp=6000)


def plane_spoolup(r):
    n, t = T(3.2)
    u = 0.5 - 0.5 * np.cos(np.pi * np.clip(t / 2.9, 0, 1))
    f1 = 62 + 42 * u
    y = _turboprop(n, f1, f1 * 1.012, 2250 + 900 * u, 2262 + 905 * u, 1.0 + 1.6 * u, r)
    y *= sa.db2a(-8 + 10 * u) * sa.env_points(n, [(0, 0), (0.15, 1), (2.95, 1), (3.2, 0)])
    return y


def plane_takeoff(r):
    n, t = T(7.5)
    dop = 1 - 0.1 * np.clip((t - 3.5) / 3.5, 0, 1) ** 1.2
    f1 = 106 * dop
    y = _turboprop(n, f1, f1 * 1.011, 3150 * dop, 3162 * dop, 2.8, r, chop=0.25)
    rumble = sa.lp(sa.noise(n, r, "brown"), 150, 4)
    y = y + 0.6 * rumble / np.std(rumble) * sa.env_points(n, [(0, 0.3), (2.5, 1), (5.5, 0.2), (7.5, 0)])
    y = stft_tv(y, lambda tt, f: 1 / (1 + (f / (9000 - 7800 * np.clip((tt - 3.5) / 3.8, 0, 1) ** 0.8)) ** 4))
    y *= sa.env_points(n, [(0, 0), (0.6, 0.6), (2.0, 1), (3.5, 1), (6.2, 0.18), (7.5, 0)])
    return y


def plane_flyby(r):
    n, t = T(4.5)
    t0, d, v, c = 2.2, 60.0, 70.0, 343.0
    x = v * (t - t0)
    rr = np.sqrt(d * d + x * x)
    vr = v * x / rr
    dop = c / (c + vr)
    f1 = 104 * dop
    y = _turboprop(n, f1, f1 * 1.011, 3100 * dop, 3110 * dop, 2.4, r, chop=0.25)
    y *= d / rr
    rr_frames = lambda tt: np.sqrt(d * d + (v * (tt - t0)) ** 2)
    y = stft_tv(y, lambda tt, f: 1 / (1 + (f / (1200 + 7000 * (d / rr_frames(tt)) ** 1.5)) ** 3))
    return sa.fade(y, 0.3, 0.4)


# --------------------------------------------------------------------------- misc
def respawn(r):
    scale = [74, 76, 78, 81, 83, 86, 88, 90, 93, 95, 98, 100]
    parts = []
    for k in range(28):
        tk = 1.1 * (k / 27) ** 0.9 + 0.02 * r.standard_normal()
        idx = int(np.clip(round(k / 27 * (len(scale) - 1) + r.normal(0, 1.2)), 0, len(scale) - 1))
        parts.append((ss.glass(scale[idx], r, 0.5 + 0.3 * r.random(), tau=0.35 + 0.2 * r.random()), max(0, tk),
                      -14 - 5 * r.random()))
    pad = sum(mono(ss.pad_note(m, 0.9, r, attack=0.4, release=0.9, bright=0.6)) for m in (62, 69, 78))
    parts.append((pad, 0, -12))
    parts.append((whoosh(1.2, lambda tt: 400 + 2100 * np.clip(tt / 1.2, 0, 1), r, bw=1.0,
                         amp_pts=[(0, 0), (0.8, 1), (1.2, 0)]), 0, -24))
    return verb(layer(parts), 0.35, 1.8, tail=0.5)


def teleport(r):
    w = whoosh(0.26, lambda tt: 700 + 1900 * np.clip(tt / 0.26, 0, 1), r, bw=0.8, amp_pts=[(0, 0), (0.2, 1), (0.26, 0)])
    n, t = T(0.15)
    pop = np.sin(2 * np.pi * np.cumsum(260 + 690 * np.exp(-t / 0.018)) / SR) * np.exp(-t / 0.05)
    pop[:48] *= np.linspace(0, 1, 48)
    clk = sa.lp(r.standard_normal(n), 3000, 2) * np.exp(-t / 0.002)
    sp = layer([(ss.glass(93, r, 0.6, tau=0.25), 0, 0), (ss.glass(98, r, 0.5, tau=0.25), 0.04, -2),
                (ss.glass(102, r, 0.4, tau=0.2), 0.08, -4)])
    return layer([(w, 0, -6), (pop, 0.24, 0), (clk, 0.24, -12), (verb(sp, 0.3, 0.8), 0.27, -22)])


def door_chime(r):
    parts = []
    for i, m in enumerate([78, 81, 86]):
        x = ss.bell(m, r, tau=1.1, partials=ss.BELL_TUBE, dur=2.0) \
            + 0.4 * ss.fm_bell(m, r, tau=0.9, ratio=1.0, index=1.0, dur=2.0)
        parts.append((x, i * 0.24, 0))
    return verb(layer(parts), 0.3, 1.6, tail=0.4)


def _footstep(src, rate):
    def fn(r):
        x = K(src, rate=rate)
        x = sa.hp(x, 70, 2)
        x = sa.peak_eq(x, 200, 2.0, 0.9)
        x = sa.peak_eq(x, 3500, -2.0, 1.0)
        x = sa.lp(x, 6500, 4)
        a = np.abs(x)
        i0 = max(0, int(np.argmax(a > a.max() * sa.db2a(-40))) - int(0.002 * SR))
        return x[i0:]
    return fn


# --------------------------------------------------------------------------- registry
#  id: (function, loop, lp_hz)
SFX = {
    "piece_pickup": (piece_pickup, False, 10000), "piece_drop": (piece_drop, False, 9000),
    "piece_rotate": (piece_rotate, False, 7000), "socket_snap": (socket_snap, False, 9000),
    "socket_reject": (socket_reject, False, 8000), "bridge_assemble": (bridge_assemble, False, 8000),
    "route_complete": (route_complete, False, 9000), "fold_out": (fold_out, False, 8500),
    "fold_in": (fold_in, False, 8500), "cell_pickup": (cell_pickup, False, 9000),
    "cell_insert": (cell_insert, False, 9000), "power_transfer": (power_transfer, False, 8000),
    "substation_on": (substation_on, False, 7000), "switch_lever": (switch_lever, False, 8000),
    "beacon_on": (beacon_on, False, 10000), "warning_chime": (warning_chime, False, 10000),
    "thunder_far_01": (thunder_far_01, False, 3000), "thunder_far_02": (thunder_far_02, False, 3000),
    "thunder_far_03": (thunder_far_03, False, 3000), "checkpoint": (checkpoint, False, 8000),
    "objective_complete": (objective_complete, False, 9000), "hint_ping": (hint_ping, False, 10000),
    "ui_hover": (ui_hover, False, 8000), "ui_click": (ui_click, False, 8000), "ui_back": (ui_back, False, 8000),
    "ui_toggle": (ui_toggle, False, 6500), "ui_slider_tick": (ui_slider_tick, False, 7000),
    "car_enter": (car_enter, False, 8000), "car_start": (car_start, False, 8000),
    "car_motor_loop": (car_motor_loop, True, None), "car_roll_loop": (car_roll_loop, True, None),
    "car_bump": (car_bump, False, 8000), "car_horn": (car_horn, False, 6000),
    "plane_idle_loop": (plane_idle_loop, True, None), "plane_spoolup": (plane_spoolup, False, 9000),
    "plane_takeoff": (plane_takeoff, False, 9000), "plane_flyby": (plane_flyby, False, 9000),
    "convoy_beep": (convoy_beep, False, 6000), "splash": (splash, False, 9000),
    "respawn": (respawn, False, 9000), "teleport": (teleport, False, 10000),
    "door_chime": (door_chime, False, 10000),
}
for i, (src, rate) in enumerate([("impact/footstep_concrete_000.ogg", 1.0), ("impact/footstep_concrete_001.ogg", 0.96),
                                 ("impact/footstep_concrete_003.ogg", 1.03), ("impact/footstep_concrete_004.ogg", 0.94)], 1):
    SFX[f"footstep_stone_{i:02d}"] = (_footstep(src, rate), False, 6500)
for name in ["happy_01", "happy_02", "happy_03", "happy_04", "curious_01", "curious_02", "curious_03",
             "concern_01", "concern_02", "concern_03", "celebrate_01", "celebrate_02", "point_01", "point_02"]:
    SFX[f"nuri_{name}"] = (globals()[f"nuri_{name}"], False, 9000)


def band_energy(y, lo=1500, hi=5000):
    P = np.abs(np.fft.rfft(y)) ** 2
    f = np.fft.rfftfreq(len(y), 1 / SR)
    return float(P[(f >= lo) & (f <= hi)].sum() / P.sum())


MAX_DUR = {"socket_snap": 1.0, "bridge_assemble": 2.3, "route_complete": 1.7, "fold_in": 1.15,
           "cell_insert": 1.3, "power_transfer": 2.3, "warning_chime": 1.5, "checkpoint": 1.2,
           "objective_complete": 1.3, "hint_ping": 0.8, "respawn": 1.9, "teleport": 0.65, "door_chime": 2.4}


def main():
    ids = sys.argv[1:] or list(SFX)
    OUT.mkdir(parents=True, exist_ok=True)
    prev = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
    for sid in ids:
        fn, loop, lp_hz = SFX[sid]
        CUR[0] = sid
        USED[sid] = []
        y = fn(R(sid))
        y = finish_loop(y, lp=None) if loop else finish(y, lp=lp_hz, max_dur=MAX_DUR.get(sid))
        sa.write_wav(OUT / f"{sid}.wav", y, seed=zlib.crc32(sid.encode()))
        info = {"kenney": USED.get(sid, []), "loop": loop, "duration_s": round(len(y) / SR, 3)}
        if sid.startswith("nuri_"):
            info["energy_1k5_5k"] = round(band_energy(y), 3)
        prev[sid] = info
        extra = f"  1.5-5k energy {info['energy_1k5_5k']*100:.0f}%" if "energy_1k5_5k" in info else ""
        print(f"  {sid:22s} {len(y)/SR:5.2f}s  TP {sa.a2db(sa.true_peak(y)):6.2f} dBTP  "
              f"{'loop' if loop else '    '}  kenney={len(info['kenney'])}{extra}", file=sys.stderr)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(prev, indent=1, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
