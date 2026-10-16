"""Shared offline DSP helpers for the SKYFOLD audio tools (numpy + scipy only).

Everything here is deterministic: random sources take explicit seeds, so every
script in tools/audio regenerates bit-identical files.

Conventions
  * float64 arrays in [-1, 1]; mono is (n,), stereo is (n, 2)
  * SR = 48000 for every shipped file
  * loudness = ITU-R BS.1770-4 integrated loudness (K-weighting, 400 ms blocks,
    -70 LUFS absolute and -10 LU relative gates). Mono files are measured as a
    single channel. Clips shorter than one 400 ms block are measured ungated
    over their whole length.
  * true peak = 4x oversampled peak (scipy polyphase resampler)
"""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.ndimage import minimum_filter1d, uniform_filter1d

SR = 48000
TOOLS = Path(__file__).resolve().parent                     # tools/audio
ROOT = TOOLS.parents[1]                                     # project root
AUDIO = ROOT / "Assets" / "Skyfold" / "Audio"
SKILL = Path.home() / ".claude" / "skills" / "kanban-motion"
SFX_LIB = SKILL / "assets" / "sfx"


# --------------------------------------------------------------------------- basics
def db2a(d):
    return 10.0 ** (np.asarray(d, dtype=float) / 20.0)


def a2db(a):
    return 20.0 * np.log10(np.maximum(np.abs(np.asarray(a, dtype=float)), 1e-12))


def secs(n, sr=SR):
    return int(round(n * sr))


def t_axis(n, sr=SR):
    return np.arange(n) / sr


def as2d(x):
    return x[:, None] if x.ndim == 1 else x


def like(y2d, x):
    return y2d[:, 0] if x.ndim == 1 else y2d


def midi_hz(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=float) - 69.0) / 12.0)


NOTE_OFFS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def nm(name: str) -> int:
    """'D4' -> 62, 'F#5' -> 78, 'Bb3' -> 58."""
    letter = name[0].upper()
    i = 1
    acc = 0
    while i < len(name) and name[i] in "#b":
        acc += 1 if name[i] == "#" else -1
        i += 1
    octave = int(name[i:])
    return 12 * (octave + 1) + NOTE_OFFS[letter] + acc


# --------------------------------------------------------------------------- I/O
def write_wav(path, x, sr=SR, dither=True, seed=0):
    """16-bit PCM WAV via the stdlib wave module. TPDF dither (1 LSB) is added only
    where the signal is non-zero, so digital silence stays digital silence."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 2 and x.shape[1] == 1:
        x = x[:, 0]
    y = x * 32767.0
    if dither:
        rng = np.random.default_rng(seed)
        d = rng.random(y.shape) - rng.random(y.shape)
        y = y + d * (np.abs(x) > 1e-7)
    y = np.clip(np.round(y), -32768, 32767).astype("<i2")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1 if y.ndim == 1 else y.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(y.tobytes())
    return path


def read_wav(path):
    """-> (float64 array, sr, channels, sample_width_bytes). PCM 16/24/32 only."""
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw == 2:
        x = np.frombuffer(raw, "<i2").astype(np.float64) / 32768.0
    elif sw == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
        v = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
        v = np.where(v >= 1 << 23, v - (1 << 24), v)
        x = v.astype(np.float64) / float(1 << 23)
    elif sw == 4:
        x = np.frombuffer(raw, "<i4").astype(np.float64) / float(1 << 31)
    else:
        raise ValueError(f"unsupported sample width {sw}")
    if ch > 1:
        x = x.reshape(-1, ch)
    return x, sr, ch, sw


def load_lib(rel, sr=SR):
    """Decode a file from the kanban-motion Kenney CC0 library to mono float at sr."""
    p = SFX_LIB / rel
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)


# --------------------------------------------------------------------------- loudness
def _biquad(kind, G, Q, fc, fs):
    A = 10 ** (G / 40.0)
    w0 = 2 * np.pi * fc / fs
    alpha = np.sin(w0) / (2 * Q)
    c = np.cos(w0)
    if kind == "high_shelf":
        sa = 2 * np.sqrt(A) * alpha
        b = [A * ((A + 1) + (A - 1) * c + sa), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - sa)]
        a = [(A + 1) - (A - 1) * c + sa, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - sa]
    else:  # high_pass
        b = [(1 + c) / 2, -(1 + c), (1 + c) / 2]
        a = [1 + alpha, -2 * c, 1 - alpha]
    b, a = np.array(b) / a[0], np.array(a) / a[0]
    return b, a


def k_filter(x, sr=SR):
    b1, a1 = _biquad("high_shelf", 3.99984385397, 0.7071752369554193, 1681.9744509555319, sr)
    b2, a2 = _biquad("high_pass", 0.0, 0.5003270373253953, 38.13547087613982, sr)
    return signal.lfilter(b2, a2, signal.lfilter(b1, a1, x, axis=0), axis=0)


def lufs(x, sr=SR):
    X = as2d(np.asarray(x, dtype=float))
    y = k_filter(X, sr)
    n = y.shape[0]
    blk, hop = int(round(0.4 * sr)), int(round(0.1 * sr))
    if n < blk:
        z = np.mean(y ** 2, axis=0)
        return float(-0.691 + 10 * np.log10(max(float(np.sum(z)), 1e-20)))
    cs = np.vstack([np.zeros((1, y.shape[1])), np.cumsum(y ** 2, axis=0)])
    st = np.arange(0, n - blk + 1, hop)
    z = (cs[st + blk] - cs[st]) / blk
    lv = -0.691 + 10 * np.log10(np.maximum(z.sum(axis=1), 1e-20))
    gabs = lv > -70
    if not np.any(gabs):
        return -70.0
    gr = -0.691 + 10 * np.log10(z[gabs].mean(axis=0).sum()) - 10
    g = gabs & (lv > gr)
    return float(-0.691 + 10 * np.log10(z[g].mean(axis=0).sum()))


def true_peak(x, os_=4):
    X = as2d(np.asarray(x, dtype=float))
    up = signal.resample_poly(X, os_, 1, axis=0)
    return float(max(np.max(np.abs(up)), np.max(np.abs(X))))


def sample_peak(x):
    return float(np.max(np.abs(x)))


# --------------------------------------------------------------------------- dynamics
def limit(x, ceiling_db=-1.5, sr=SR, window_ms=5.0, circular=False, os_=4):
    """Look-ahead true-peak limiter. Gain = moving average of a moving minimum of the
    required gain over the same window, which guarantees gain <= required at every
    peak with smooth ramps of `window_ms` on either side. `circular` treats the clip
    as a loop so the gain curve is continuous across the seam."""
    X = as2d(np.asarray(x, dtype=float))
    n = X.shape[0]
    pad = min(n, 8192) if circular else 0
    Xp = np.concatenate([X[-pad:], X, X[:pad]]) if circular else X
    up = signal.resample_poly(Xp, os_, 1, axis=0)
    pk = np.abs(up).max(axis=1)[: Xp.shape[0] * os_].reshape(-1, os_).max(axis=1)
    pk = np.maximum(pk, np.abs(Xp).max(axis=1))
    if circular:
        pk = pk[pad:pad + n]
    g = np.minimum(1.0, db2a(ceiling_db) / np.maximum(pk, 1e-12))
    if g.min() >= 1.0:
        return np.array(x, dtype=float, copy=True)
    h = max(1, int(window_ms * 1e-3 * sr))
    mode = "wrap" if circular else "nearest"
    g = minimum_filter1d(g, 2 * h + 1, mode=mode)
    g = uniform_filter1d(g, 2 * h + 1, mode=mode)
    return like(X * g[:, None], x)


def normalize_lufs(x, target, tp_db=-1.5, sr=SR, circular=False, window_ms=5.0):
    y = np.array(x, dtype=float, copy=True)
    for _ in range(10):
        y = y * db2a(target - lufs(y, sr))
        y = limit(y, tp_db - 0.05, sr=sr, circular=circular, window_ms=window_ms)
        if abs(lufs(y, sr) - target) < 0.05 and a2db(true_peak(y)) <= tp_db:
            break
    return y


def peak_normalize(x, peak_db=-3.0):
    p = np.max(np.abs(x))
    return x * (db2a(peak_db) / p) if p > 0 else x


def soft_clip(x, drive=1.0):
    return np.tanh(x * drive) / np.tanh(drive)


# --------------------------------------------------------------------------- filters
def sos(kind, f, order=2, sr=SR):
    return signal.butter(order, f, btype=kind, fs=sr, output="sos")


def filt(x, s, zero_phase=False):
    return signal.sosfiltfilt(s, x, axis=0) if zero_phase else signal.sosfilt(s, x, axis=0)


def lp(x, f, order=2, sr=SR, zero_phase=False):
    return filt(x, sos("lowpass", f, order, sr), zero_phase)


def hp(x, f, order=2, sr=SR, zero_phase=False):
    return filt(x, sos("highpass", f, order, sr), zero_phase)


def bp(x, lo, hi, order=2, sr=SR, zero_phase=False):
    return filt(x, sos("bandpass", [lo, hi], order, sr), zero_phase)


def filt_circ(x, s, sr=SR):
    """Periodic steady-state response of an IIR filter (exact for loops)."""
    n = x.shape[0]
    X = np.fft.rfft(x, axis=0)
    w = np.fft.rfftfreq(n, 1 / sr)
    _, H = signal.sosfreqz(s, worN=w, fs=sr)
    if x.ndim == 2:
        H = H[:, None]
    return np.fft.irfft(X * H, n=n, axis=0)


def fft_shape(x, gain_fn, sr=SR):
    """Zero-phase circular EQ: gain_fn(freqs_hz) -> linear gain."""
    n = x.shape[0]
    X = np.fft.rfft(x, axis=0)
    g = gain_fn(np.fft.rfftfreq(n, 1 / sr))
    if x.ndim == 2:
        g = g[:, None]
    return np.fft.irfft(X * g, n=n, axis=0)


def lp_curve(fc, slope=2.0):
    return lambda f: 1.0 / (1.0 + (np.maximum(f, 0) / fc) ** (2 * slope))


def hp_curve(fc, slope=2.0):
    return lambda f: 1.0 - 1.0 / (1.0 + (np.maximum(f, 1e-9) / fc) ** (2 * slope))


def band_curve(lo, hi, slope=2.0):
    a, b = hp_curve(lo, slope), lp_curve(hi, slope)
    return lambda f: a(f) * b(f)


def peak_eq(x, f0, gain_db, q=1.0, sr=SR, circular=False):
    A = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * f0 / sr
    al = np.sin(w0) / (2 * q)
    b = np.array([1 + al * A, -2 * np.cos(w0), 1 - al * A])
    a = np.array([1 + al / A, -2 * np.cos(w0), 1 - al / A])
    s = signal.tf2sos(b / a[0], a / a[0])
    return filt_circ(x, s, sr) if circular else filt(x, s)


def dc_block(x, f=20.0, sr=SR, circular=False):
    if circular:
        y = x - np.mean(x, axis=0)
        return filt_circ(y, sos("highpass", f, 2, sr), sr)
    return hp(x, f, 2, sr)


# --------------------------------------------------------------------------- envelopes
def fade(x, fin=0.005, fout=0.005, sr=SR):
    y = np.array(x, dtype=float, copy=True)
    a, b = int(fin * sr), int(fout * sr)
    if a > 1:
        r = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, a))
        y[:a] *= r if y.ndim == 1 else r[:, None]
    if b > 1:
        r = 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, b))
        y[-b:] *= r if y.ndim == 1 else r[:, None]
    return y


def env_ar(n, attack, release, sr=SR, hold=None):
    """Raised-cosine attack, sustain, raised-cosine release (all seconds)."""
    e = np.ones(n)
    a = min(n, max(1, int(attack * sr)))
    e[:a] = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, a))
    r = min(n, max(1, int(release * sr)))
    e[n - r:] *= 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, r))
    return e


def env_exp(n, tau, attack=0.002, sr=SR):
    t = np.arange(n) / sr
    a = max(1, int(attack * sr))
    e = np.exp(-t / tau)
    e[:a] *= 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, a))
    return e


def env_points(n, pts, sr=SR, curve="cos"):
    """Piecewise envelope through (time_s, value) points with cosine segments."""
    t = np.arange(n) / sr
    ts = np.array([p[0] for p in pts], dtype=float)
    vs = np.array([p[1] for p in pts], dtype=float)
    out = np.empty(n)
    idx = np.clip(np.searchsorted(ts, t, side="right") - 1, 0, len(ts) - 2)
    t0, t1 = ts[idx], ts[idx + 1]
    v0, v1 = vs[idx], vs[idx + 1]
    u = np.clip((t - t0) / np.maximum(t1 - t0, 1e-9), 0, 1)
    if curve == "cos":
        u = 0.5 - 0.5 * np.cos(np.pi * u)
    out[:] = v0 + (v1 - v0) * u
    out[t < ts[0]] = vs[0]
    out[t >= ts[-1]] = vs[-1]
    return out


# --------------------------------------------------------------------------- oscillators
def osc(freq, n=None, sr=SR, phase=0.0, kind="sine"):
    """Phase-accumulating oscillator. freq: scalar or per-sample array."""
    f = np.full(n, float(freq)) if np.isscalar(freq) else np.asarray(freq, dtype=float)
    ph = 2 * np.pi * np.cumsum(f) / sr + phase
    if kind == "sine":
        return np.sin(ph)
    if kind == "tri":
        return 2 / np.pi * np.arcsin(np.sin(ph))
    raise ValueError(kind)


def additive(f0, n, amps, ratios=None, sr=SR, phases=None, fmax=16000.0, decays=None, rng=None):
    """Sum of partials f0*ratio with amplitude amps[k]; optional per-partial exp decay (s)."""
    t = np.arange(n) / sr
    ratios = np.arange(1, len(amps) + 1) if ratios is None else ratios
    y = np.zeros(n)
    for k, (r, a) in enumerate(zip(ratios, amps)):
        f = f0 * r
        if a == 0 or f >= min(fmax, 0.45 * sr):
            continue
        p = phases[k] if phases is not None else (rng.random() * 2 * np.pi if rng is not None else 0.0)
        part = np.sin(2 * np.pi * f * t + p)
        if decays is not None:
            part *= np.exp(-t / decays[k])
        y += a * part
    return y


def noise(n, rng, color="white"):
    w = rng.standard_normal(n)
    if color == "white":
        return w
    W = np.fft.rfft(w)
    f = np.fft.rfftfreq(n, 1 / SR)
    f[0] = f[1]
    if color == "pink":
        W /= np.sqrt(f / 1000.0)
    elif color == "brown":
        W /= f / 100.0
    y = np.fft.irfft(W, n=n)
    return y / (np.std(y) or 1)


def periodic_lfo(n, cycles, rng=None, phase=None):
    """Sine LFO with an integer number of cycles over n samples (loop-safe)."""
    ph = (rng.random() * 2 * np.pi) if (phase is None and rng is not None) else (phase or 0.0)
    return np.sin(2 * np.pi * cycles * np.arange(n) / n + ph)


def smooth_random(n, n_points, rng, circular=True, lo=0.0, hi=1.0):
    """Smooth random curve through n_points random values (periodic if circular)."""
    v = rng.uniform(lo, hi, n_points)
    if circular:
        xp = np.linspace(0, n, n_points, endpoint=False)
        xp = np.concatenate([xp - n, xp, xp + n])
        vp = np.concatenate([v, v, v])
    else:
        xp = np.linspace(0, n - 1, n_points)
        vp = v
    xs = np.arange(n)
    # cosine interpolation between control points
    idx = np.clip(np.searchsorted(xp, xs, side="right") - 1, 0, len(xp) - 2)
    u = (xs - xp[idx]) / np.maximum(xp[idx + 1] - xp[idx], 1e-9)
    u = 0.5 - 0.5 * np.cos(np.pi * u)
    return vp[idx] + (vp[idx + 1] - vp[idx]) * u


# --------------------------------------------------------------------------- space
def pan(x, p):
    """Constant-power pan of mono x to stereo, p in [-1, 1]."""
    a = (np.clip(p, -1, 1) + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], axis=1)


def place(buf, x, start, wrap=False):
    """Add x into buf at sample index start; with wrap the buffer is treated as a loop."""
    n = buf.shape[0]
    i = int(round(start))
    if wrap:
        i %= n
        pos = 0
        while pos < len(x):
            seg = min(len(x) - pos, n - i)
            buf[i:i + seg] += x[pos:pos + seg]
            pos += seg
            i = 0
        return buf
    if i < 0:
        x, i = x[-i:], 0
    m = min(len(x), n - i)
    if m > 0:
        buf[i:i + m] += x[:m]
    return buf


def reverb_ir(rt60=2.2, sr=SR, predelay=0.018, seed=1, hf=0.45, lf=1.15, length=None, density_ms=4.0):
    """Synthetic stereo hall IR: band-split decorrelated noise with per-band decay."""
    L = length or rt60 * 1.25
    n = int(L * sr)
    t = np.arange(n) / sr
    rng = np.random.default_rng(seed)
    nz = rng.standard_normal((n, 2))
    lo = fft_shape(nz, lp_curve(350, 1.5))
    hi = fft_shape(nz, hp_curve(4500, 1.5))
    mid = nz - lo - hi
    ir = (lo * np.exp(-6.9078 * t / (rt60 * lf))[:, None]
          + mid * np.exp(-6.9078 * t / rt60)[:, None]
          + hi * np.exp(-6.9078 * t / (rt60 * hf))[:, None])
    ir *= (1 - np.exp(-t / (density_ms * 1e-3)))[:, None]
    ir = np.vstack([np.zeros((int(predelay * sr), 2)), ir])
    ir /= np.sqrt(np.sum(ir ** 2) / 2)
    return ir


def convolve(x, ir, circular=False):
    X = np.stack([x, x], 1) if x.ndim == 1 else x
    n = X.shape[0]
    if circular:
        m = ir.shape[0]
        irw = np.zeros((n, ir.shape[1]))
        for k in range(0, m, n):
            seg = ir[k:k + n]
            irw[: len(seg)] += seg
        return np.fft.irfft(np.fft.rfft(X, axis=0) * np.fft.rfft(irw, axis=0), n=n, axis=0)
    return signal.fftconvolve(X, ir, axes=0)


def delay(x, t_s, fb=0.35, taps=5, lp_hz=3500.0, pingpong=True, circular=True, sr=SR):
    """Feedback-style delay built from darkening taps (stereo in, stereo out)."""
    X = np.stack([x, x], 1) if x.ndim == 1 else x
    n = X.shape[0]
    out = np.zeros_like(X)
    tap = X.copy()
    s = sos("lowpass", lp_hz, 1, sr)
    for k in range(1, taps + 1):
        tap = (filt_circ(tap, s, sr) if circular else filt(tap, s)) * fb
        d = int(round(k * t_s * sr))
        src = tap[:, ::-1] if (pingpong and k % 2 == 1) else tap
        if circular:
            out += np.roll(src, d, axis=0)
        elif d < n:
            out[d:] += src[: n - d]
    return out


def stereo_widen(x, amount=0.2):
    m = (x[:, 0] + x[:, 1]) / 2
    s = (x[:, 0] - x[:, 1]) / 2 * (1 + amount)
    return np.stack([m + s, m - s], 1)


# --------------------------------------------------------------------------- analysis
def seam_report(x, sr=SR, win=0.05):
    """Seam metrics for a loop: render twice back-to-back and inspect the junction."""
    X = as2d(np.asarray(x, dtype=float))
    n, ch = X.shape
    xx = np.concatenate([X, X])
    j = n                                                    # junction index in xx
    d1 = np.abs(np.diff(X, axis=0))
    seam1 = np.abs(xx[j] - xx[j - 1])
    d2 = np.abs(X[2:] - 2 * X[1:-1] + X[:-2])
    seam2 = np.maximum(np.abs(xx[j + 1] - 2 * xx[j] + xx[j - 1]), np.abs(xx[j] - 2 * xx[j - 1] + xx[j - 2]))
    p1 = np.percentile(d1, 99.9, axis=0)
    p2 = np.percentile(d2, 99.9, axis=0)
    w = int(win * sr)
    rms = lambda s: np.sqrt(np.mean(s ** 2) + 1e-20)
    jump = abs(20 * np.log10(rms(xx[j:j + w]) / rms(xx[j - w:j])))
    w10 = int(0.01 * sr)
    jump10 = abs(20 * np.log10(rms(xx[j:j + w10]) / rms(xx[j - w10:j])))
    nb = n // w
    r = np.sqrt(np.mean(X[: nb * w].reshape(nb, w, ch) ** 2, axis=(1, 2)) + 1e-20)
    internal = np.abs(np.diff(20 * np.log10(r)))
    nb10 = n // w10
    r10 = np.sqrt(np.mean(X[: nb10 * w10].reshape(nb10, w10, ch) ** 2, axis=(1, 2)) + 1e-20)
    internal10 = np.abs(np.diff(20 * np.log10(r10)))
    lim = max(1.5, float(np.percentile(internal, 99)))
    lim10 = max(2.0, float(np.percentile(internal10, 99)))
    ok = bool(np.all(seam1 <= np.maximum(p1, 2e-4)) and np.all(seam2 <= np.maximum(p2, 2e-4))
              and jump <= lim and jump10 <= lim10)
    return {
        "seam_step": float(seam1.max()), "p999_step": float(p1.max()),
        "seam_curv": float(seam2.max()), "p999_curv": float(p2.max()),
        "rms_jump_50ms_db": float(jump), "rms_jump_50ms_limit": lim,
        "rms_jump_10ms_db": float(jump10), "rms_jump_10ms_limit": lim10,
        "ok": ok,
    }


def describe(x, sr=SR):
    X = as2d(np.asarray(x, dtype=float))
    return {
        "dur": X.shape[0] / sr, "lufs": lufs(X, sr), "tp": float(a2db(true_peak(X))),
        "peak": float(a2db(sample_peak(X))), "dc": float(np.max(np.abs(np.mean(X, axis=0)))),
    }
