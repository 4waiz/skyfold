"""Small sample-accurate mixer for the trailer stems (music bed, voice, effects).

Every source is decoded through ffmpeg to 48 kHz stereo float32, so WAV and OGG both work.
"""
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 48000
_cache = {}


def load(ffmpeg, path):
    path = str(path)
    if path not in _cache:
        raw = subprocess.run([ffmpeg, "-v", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                             capture_output=True, check=True).stdout
        _cache[path] = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()
    return _cache[path]


def fades(n, fade_in, fade_out):
    env = np.ones(n, dtype=np.float32)
    a = min(n, int(fade_in * SR))
    b = min(n, int(fade_out * SR))
    if a > 0:
        env[:a] = np.sin(np.linspace(0, np.pi / 2, a)) ** 2  # equal-power style ease
    if b > 0:
        env[n - b:] *= np.cos(np.linspace(0, np.pi / 2, b)) ** 2
    return env


class Track:
    def __init__(self, seconds):
        self.n = int(round(seconds * SR))
        self.buf = np.zeros((self.n, 2), dtype=np.float32)

    def add(self, clip, at, gain=1.0, src=0.0, dur=None, fade_in=0.0, fade_out=0.0, loop=False, rate=1.0, pan=0.0):
        """Places clip at time `at` (s), reading from `src` (s) for `dur` (s), looping if asked."""
        if rate != 1.0:
            idx = np.arange(0, len(clip) - 1, rate)
            clip = np.stack([np.interp(idx, np.arange(len(clip)), clip[:, c]) for c in range(2)], axis=1).astype(np.float32)
        start = int(round(src * SR))
        if dur is None:
            dur = len(clip) / SR - src
        n = int(round(dur * SR))
        if loop:
            reps = int(np.ceil((start + n) / len(clip))) + 1
            seg = np.tile(clip, (reps, 1))[start:start + n]
        else:
            seg = clip[start:start + n]
            n = len(seg)
        seg = seg * fades(n, fade_in, fade_out)[:, None] * gain
        if pan:
            seg = seg * np.array([min(1.0, 1.0 - pan), min(1.0, 1.0 + pan)], dtype=np.float32)
        i = int(round(at * SR))
        j = min(self.n, i + n)
        if j > i:
            self.buf[i:j] += seg[: j - i]

    def apply(self, env):
        self.buf *= env[:, None]


def automation(seconds, points):
    """Piecewise-linear gain lane: points = [(t, gain), ...]."""
    n = int(round(seconds * SR))
    t = np.arange(n) / SR
    ts, gs = zip(*points)
    return np.interp(t, ts, gs).astype(np.float32)


def duck_envelope(seconds, spans, depth=0.3, attack=0.18, release=0.45):
    """Gain lane that dips to `depth` during each (start, end) voice span, with smooth ramps."""
    # One lane per span; overlapping ramps merge by taking the minimum.
    n = int(round(seconds * SR))
    env = np.ones(n, dtype=np.float32)
    for a, b in spans:
        lane = automation(seconds, [(0.0, 1.0), (max(0.0, a - attack), 1.0), (a, depth), (b, depth), (b + release, 1.0), (seconds, 1.0)])
        env = np.minimum(env, lane)
    return env


def write_wav(path, buf, peak=0.97):
    m = float(np.max(np.abs(buf))) if len(buf) else 0.0
    if m > peak:  # gentle safety: soft-knee limit only the loudest samples
        buf = np.tanh(buf / peak * 1.0) * peak
    pcm = (np.clip(buf, -1.0, 1.0) * 32767.0).astype(np.int16)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def rms_frames(buf, fps=30):
    """Per-video-frame RMS (mono) for audio-reactive visuals, normalised 0..1."""
    mono = buf.mean(axis=1)
    hop = SR // fps
    n = len(mono) // hop
    r = np.sqrt(np.mean(mono[: n * hop].reshape(n, hop) ** 2, axis=1))
    lo, hi = np.percentile(r, 5), np.percentile(r, 98)
    return np.clip((r - lo) / max(1e-6, hi - lo), 0, 1)


def band_frames(buf, fps=30):
    """Per-frame [bass, treble] energies, each normalised 0..1 over the track."""
    mono = buf.mean(axis=1)
    hop = SR // fps
    n = len(mono) // hop
    win = np.hanning(hop * 2)
    bass, treble = [], []
    freqs = np.fft.rfftfreq(hop * 2, 1 / SR)
    for i in range(n):
        seg = mono[i * hop: i * hop + hop * 2]
        if len(seg) < hop * 2:
            seg = np.pad(seg, (0, hop * 2 - len(seg)))
        spec = np.abs(np.fft.rfft(seg * win))
        bass.append(spec[(freqs > 30) & (freqs < 180)].mean())
        treble.append(spec[(freqs > 3000) & (freqs < 9000)].mean())
    out = []
    for arr in (np.array(bass), np.array(treble)):
        lo, hi = np.percentile(arr, 5), np.percentile(arr, 98)
        out.append(np.clip((arr - lo) / max(1e-9, hi - lo), 0, 1))
    return np.stack(out, axis=1)
