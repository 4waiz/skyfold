#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy"]
# ///
"""SKYFOLD ambience beds (offline synthesis, deterministic, seamless loops).

    python tools/audio/make_ambience.py              # all beds -> Assets/Skyfold/Audio/Ambience/
    python tools/audio/make_ambience.py amb_coast_loop

Every component is periodic over the loop length: FFT-coloured noise and FFT filters are
circular, slow modulations complete whole cycles, discrete events (waves, gusts, chimes,
birds, rumbles) wrap around the loop end, time-varying filters run on a tiled copy, and the
reverb is a circular convolution. The file end therefore continues into the file start.
Masters: stereo 48 kHz 16-bit, -24 LUFS integrated, <= -1.5 dBTP (calm, non-fatiguing beds).
"""

from __future__ import annotations

import json
import sys
import zlib
from pathlib import Path

import numpy as np
from scipy import signal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skyaudio as sa  # noqa: E402
import skysynth as ss  # noqa: E402
from skyaudio import SR  # noqa: E402

OUT = sa.AUDIO / "Ambience"
REPORT = sa.TOOLS / "reports" / "ambience.json"
TARGET_LUFS, TP = -24.0, -1.5


def R(name):
    return np.random.default_rng(zlib.crc32(name.encode()))


def stereo_noise(n, rng, color="pink", corr=0.35):
    a, b, c = sa.noise(n, rng, color), sa.noise(n, rng, color), sa.noise(n, rng, color)
    k = np.sqrt(corr)
    return np.stack([k * c + np.sqrt(1 - corr) * a, k * c + np.sqrt(1 - corr) * b], 1)


def tv_filter(x, gain_fn, nper=2048, hop=256, period=None):
    """Time-varying STFT filter. With `period` (s) the clip is a loop: process a tiled copy so
    the result is continuous across the seam (gain_fn must be periodic in t)."""
    X = sa.as2d(x)
    n = X.shape[0]
    out = np.zeros_like(X)
    for c in range(X.shape[1]):
        src = np.concatenate([X[:, c]] * 3) if period else X[:, c]
        f, t, Z = signal.stft(src, fs=SR, nperseg=nper, noverlap=nper - hop, boundary="even", padded=True)
        tt = (t - (n / SR if period else 0.0))
        G = gain_fn(tt[None, :], f[:, None])
        _, y = signal.istft(Z * G, fs=SR, nperseg=nper, noverlap=nper - hop, boundary=True)
        y = y[n:2 * n] if period else y[:n]
        out[: len(y), c] = y
    return sa.like(out, x)


def event_times(rng, total, count, jitter=0.35):
    """`count` event start times spread over `total` seconds with irregular spacing."""
    base = (np.arange(count) + rng.uniform(0, 1)) / count * total
    base += rng.uniform(-jitter, jitter, count) * total / count
    return np.sort(base % total)


def finish(name, y):
    y = y - y.mean(axis=0)
    y = sa.filt_circ(y, sa.sos("highpass", 25, 2))
    y = sa.filt_circ(y, sa.sos("lowpass", 9000, 2))
    return sa.normalize_lufs(y, TARGET_LUFS, TP, circular=True, window_ms=20.0)


def bird_call(rng, kind=0):
    """Small original songbird phrase (far away): a few quick sweeps or a short trill."""
    parts = []
    if kind == 0:
        f0 = rng.uniform(2600, 3600)
        for i in range(rng.integers(3, 6)):
            d = rng.uniform(0.04, 0.08)
            n = int(d * SR)
            t = np.arange(n) / SR
            f = f0 * (1.15 - 0.3 * t / d) * (1 + 0.05 * i)
            y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / d) ** 2
            parts.append(np.concatenate([y, np.zeros(int(rng.uniform(0.03, 0.07) * SR))]))
    else:
        d = rng.uniform(0.35, 0.6)
        n = int(d * SR)
        t = np.arange(n) / SR
        f = rng.uniform(3000, 4000) * (1 + 0.08 * np.sin(2 * np.pi * rng.uniform(18, 26) * t))
        y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / d) ** 1.5
        parts.append(y)
    y = np.concatenate(parts)
    return sa.lp(sa.fade(y, 0.003, 0.01), 6000, 2)


# --------------------------------------------------------------------------- coast
def amb_coast_loop():
    rng = R("amb_coast_loop")
    T = 48.0
    n = int(T * SR)
    t = np.arange(n) / SR
    bed = stereo_noise(n, rng, "brown", 0.5)
    bed = sa.fft_shape(bed, sa.lp_curve(450, 1.5))
    bed *= (0.8 + 0.2 * sa.periodic_lfo(n, 3, rng))[:, None]
    out = bed / np.std(bed) * 0.35
    waves = np.zeros((n, 2))
    starts = event_times(rng, T, 7, 0.25)
    for k, t0 in enumerate(starts):
        d = rng.uniform(7.0, 9.5)
        m = int(d * SR)
        tw = np.arange(m) / SR
        sw, br = rng.uniform(2.2, 3.0), rng.uniform(0.25, 0.45)
        amp = np.where(tw < sw, (tw / sw) ** 2,
                       np.exp(-np.maximum(tw - sw - br, 0) / rng.uniform(1.2, 1.8)))
        amp = sa.fade(amp, 0.05, 0.6) * rng.uniform(0.7, 1.0)
        fc_pts = [(0, 280), (sw, 2600), (sw + br, 3400), (sw + br + 1.5, 1100), (d, 450)]
        fc_t = np.array([p[0] for p in fc_pts])
        fc_v = np.log(np.array([p[1] for p in fc_pts]))
        x = stereo_noise(m, rng, "pink", 0.55) * amp[:, None]
        x = tv_filter(x, lambda tt, f: 1 / (1 + (f / np.exp(np.interp(tt, fc_t, fc_v))) ** 2.5))
        foam = stereo_noise(m, rng, "white", 0.3)
        foam = sa.fft_shape(foam, sa.band_curve(2500, 7000, 1.5))
        foam *= (np.where(tw > sw, np.exp(-(tw - sw) / 2.2), 0) * (1 - np.exp(-np.maximum(tw - sw, 0) / 0.2)))[:, None]
        x = x / (np.max(np.abs(x)) or 1) + 0.06 * foam / (np.std(foam) or 1)
        p = rng.uniform(-0.35, 0.35)
        x = x * np.array([1 - max(p, 0), 1 + min(p, 0)])
        sa.place(waves, x, int(t0 * SR), wrap=True)
    out += waves * 0.55
    wind = stereo_noise(n, rng, "pink", 0.2)
    wind = sa.fft_shape(wind, sa.band_curve(300, 1500, 1.5))
    gust = sa.smooth_random(n, 9, rng, lo=0.35, hi=1.0)
    out += wind / np.std(wind) * 0.07 * gust[:, None]
    lap = np.zeros((n, 2))
    for t0 in event_times(rng, T, 18, 0.45):
        m = int(rng.uniform(0.25, 0.5) * SR)
        x = sa.fft_shape(sa.noise(m, rng, "pink"), sa.band_curve(180, 900))
        x = x * np.sin(np.pi * np.arange(m) / m) ** 2 * rng.uniform(0.3, 0.7)
        sa.place(lap, sa.pan(x / np.std(x), rng.uniform(-0.6, 0.6)), int(t0 * SR), wrap=True)
    out += lap * 0.05
    ir = sa.reverb_ir(1.6, seed=31)
    out = out + 0.15 * sa.convolve(out, ir, circular=True)
    return out


# --------------------------------------------------------------------------- city
def amb_city_loop():
    rng = R("amb_city_loop")
    T = 48.0
    n = int(T * SR)
    t = np.arange(n) / SR
    rumble = sa.fft_shape(stereo_noise(n, rng, "brown", 0.6), sa.lp_curve(240, 1.5))
    rumble *= (0.85 + 0.15 * sa.periodic_lfo(n, 2, rng))[:, None]
    out = rumble / np.std(rumble) * 0.3
    mid = sa.fft_shape(stereo_noise(n, rng, "pink", 0.4), sa.band_curve(150, 1200, 1.5))
    out += mid / np.std(mid) * 0.07 * (0.8 + 0.2 * sa.periodic_lfo(n, 5, rng))[:, None]
    hum = np.zeros(n)
    for f, a in ((98.0, 1.0), (147.0, 0.4), (196.0, 0.5), (294.0, 0.2)):
        f = round(f * T) / T
        hum += a * np.sin(2 * np.pi * f * t + rng.random() * 6.28)
    hum *= 0.7 + 0.3 * sa.smooth_random(n, 6, rng)
    out += sa.pan(hum, 0.0) * 0.012
    murmur = sa.fft_shape(sa.noise(n, rng, "pink"), sa.band_curve(300, 1500))
    syll = sa.smooth_random(n, int(T * 4.5), rng, lo=0.0, hi=1.0) ** 2
    out += sa.pan(murmur / np.std(murmur) * syll, 0.15) * 0.025
    swish = np.zeros((n, 2))
    for t0 in event_times(rng, T, 9, 0.4):
        d = rng.uniform(2.5, 4.0)
        m = int(d * SR)
        tw = np.arange(m) / SR
        x = sa.noise(m, rng, "pink")
        fc_mid = rng.uniform(500, 900)
        x = tv_filter(x, lambda tt, f, d=d, c=fc_mid: np.exp(-0.5 * (np.log2(np.maximum(f, 1) /
                      (c * (1.25 - 0.5 * np.clip(tt / d, 0, 1)))) / 1.1) ** 2))
        x *= np.sin(np.pi * tw / d) ** 2
        p0 = rng.uniform(-0.8, 0.8)
        pan_t = np.clip(p0 + np.sign(-p0 + 1e-3) * 0.6 * tw / d, -1, 1)
        a = (pan_t + 1) * np.pi / 4
        st = np.stack([x * np.cos(a), x * np.sin(a)], 1)
        sa.place(swish, st / (np.std(x) or 1) * rng.uniform(0.5, 1.0), int(t0 * SR), wrap=True)
    out += swish * 0.05
    birds = np.zeros((n, 2))
    for k, t0 in enumerate(event_times(rng, T, 5, 0.4)):
        b = bird_call(rng, kind=k % 2)
        sa.place(birds, sa.pan(b, rng.uniform(-0.8, 0.8)) * rng.uniform(0.5, 0.9), int(t0 * SR), wrap=True)
    birds = birds + 0.6 * sa.convolve(birds, sa.reverb_ir(1.4, seed=41), circular=True)
    out += birds * 0.06
    out = out + 0.12 * sa.convolve(out, sa.reverb_ir(1.8, seed=42), circular=True)
    return out


# --------------------------------------------------------------------------- atelier
def amb_atelier_loop():
    rng = R("amb_atelier_loop")
    T = 60.0
    n = int(T * SR)
    gust = sa.smooth_random(n, 11, rng, lo=0.15, hi=1.0) ** 1.5
    breeze = sa.fft_shape(stereo_noise(n, rng, "pink", 0.3), sa.band_curve(250, 2000, 1.5))
    out = breeze / np.std(breeze) * 0.22 * (0.35 + 0.65 * gust)[:, None]
    air = sa.fft_shape(stereo_noise(n, rng, "white", 0.2), sa.band_curve(2000, 6000, 1.5))
    out += air / np.std(air) * 0.02 * (0.5 + 0.5 * gust)[:, None]
    whistle = sa.fft_shape(sa.noise(n, rng, "white"), sa.band_curve(700, 820, 4.0))
    out += sa.pan(whistle / np.std(whistle) * 0.012 * gust ** 2, -0.2)
    chimes = np.zeros((n, 2))
    notes = [86, 88, 90, 93, 95]
    peaks = np.argsort(gust[:: SR // 4])[::-1] / 4.0           # loudest gust moments first
    picked = []
    for p in peaks:
        if all(abs(p - q) > 1.2 for q in picked):
            picked.append(p)
        if len(picked) >= 9:
            break
    for p in picked:
        for j in range(rng.integers(1, 4)):
            m = int(rng.choice(notes))
            x = ss.bell(m, rng, tau=rng.uniform(1.6, 2.6), vel=rng.uniform(0.3, 0.8), partials=ss.BELL_GLASS,
                        attack=0.004)
            sa.place(chimes, sa.pan(x, rng.uniform(-0.5, 0.5)), int((p + j * rng.uniform(0.15, 0.5)) * SR), wrap=True)
    chimes = chimes + 0.7 * sa.convolve(chimes, sa.reverb_ir(2.2, seed=51), circular=True)
    out += chimes * 0.05
    out = out + 0.1 * sa.convolve(out, sa.reverb_ir(1.6, seed=52), circular=True)
    return out


# --------------------------------------------------------------------------- storm
def amb_storm_loop():
    rng = R("amb_storm_loop")
    T = 60.0
    n = int(T * SR)
    gust = sa.smooth_random(n, 16, rng, lo=0.1, hi=1.0) ** 2
    slow = 0.6 + 0.4 * sa.periodic_lfo(n, 3, rng)
    low = sa.fft_shape(stereo_noise(n, rng, "brown", 0.5), sa.band_curve(50, 300, 1.5))
    mid = sa.fft_shape(stereo_noise(n, rng, "pink", 0.3), sa.band_curve(300, 1300, 1.5))
    out = low / np.std(low) * 0.35 * (0.6 + 0.4 * gust)[:, None]
    out += mid / np.std(mid) * 0.22 * (0.25 + 0.75 * gust * slow)[:, None]
    howl_src = stereo_noise(n, rng, "pink", 0.4)
    gust_frames = lambda tt: np.interp(np.mod(tt, T), np.arange(0, T, 0.05), gust[:: int(0.05 * SR)][: len(np.arange(0, T, 0.05))])
    howl = tv_filter(howl_src, lambda tt, f: np.exp(-0.5 * (np.log2(np.maximum(f, 1) / (380 + 520 * gust_frames(tt))) / 0.18) ** 2),
                     nper=4096, hop=512, period=T)
    out += howl / np.std(howl) * 0.09 * (0.2 + 0.8 * gust)[:, None]
    rum = np.zeros((n, 2))
    for t0 in event_times(rng, T, 4, 0.3):
        d = rng.uniform(6.0, 9.0)
        m = int(d * SR)
        tw = np.arange(m) / SR
        env = np.zeros(m)
        for k in range(rng.integers(2, 4)):
            s0 = rng.uniform(0, d * 0.4)
            env += np.where(tw >= s0, (1 - np.exp(-(tw - s0) / rng.uniform(0.2, 0.5))) *
                            np.exp(-(tw - s0) / rng.uniform(1.0, 2.0)), 0) * rng.uniform(0.5, 1.0)
        x = sa.fft_shape(stereo_noise(m, rng, "brown", 0.7), sa.lp_curve(260, 2.0)) * env[:, None]
        x = sa.fade(x, 0.2, 1.0)
        sa.place(rum, x / (np.max(np.abs(x)) or 1), int(t0 * SR), wrap=True)
    out += rum * 0.5
    bed = sa.fft_shape(stereo_noise(n, rng, "brown", 0.7), sa.lp_curve(110, 2.0))
    out += bed / np.std(bed) * 0.18
    out = out + 0.12 * sa.convolve(out, sa.reverb_ir(2.0, seed=61), circular=True)
    return out


BEDS = {"amb_coast_loop": (amb_coast_loop, "gentle waves + soft wind"),
        "amb_city_loop": (amb_city_loop, "distant city murmur/hum + far birds"),
        "amb_atelier_loop": (amb_atelier_loop, "terrace breeze + faint chimes"),
        "amb_storm_loop": (amb_storm_loop, "gusty wind + distant rumble")}


def main():
    ids = sys.argv[1:] or list(BEDS)
    OUT.mkdir(parents=True, exist_ok=True)
    rep = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
    for aid in ids:
        fn, desc = BEDS[aid]
        y = finish(aid, fn())
        sa.write_wav(OUT / f"{aid}.wav", y, seed=zlib.crc32(aid.encode()))
        x, _, _, _ = sa.read_wav(OUT / f"{aid}.wav")
        d = sa.describe(x)
        seam = sa.seam_report(x)
        rep[aid] = {"desc": desc, "duration_s": round(d["dur"], 3), "lufs": round(d["lufs"], 2),
                    "tp_dbtp": round(d["tp"], 2), "seam": seam}
        print(f"  {aid:18s} {d['dur']:5.1f}s {d['lufs']:6.2f} LUFS {d['tp']:6.2f} dBTP  seam "
              f"{'OK' if seam['ok'] else 'CHECK'} (step {seam['seam_step']:.4f}/{seam['p999_step']:.4f}, "
              f"jump50 {seam['rms_jump_50ms_db']:.2f} dB)", file=sys.stderr)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rep, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
