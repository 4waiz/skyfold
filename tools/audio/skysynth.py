"""Small original instrument set for SKYFOLD (numpy only, deterministic).

Tonal voices
  pad_note / strings_note / brass_note : band-limited wavetable ensembles (stereo)
  bass_note, pluck_bass                : round and plucked bass (mono)
  pluck                                : additive plucked string with 2-3 detuned courses
                                         (kind="kanun" bright zither, "oud" warm lute, "harp")
  marimba, bell, fm_bell, glass        : struck bars / bells (mono)
Percussion (mono)
  doum / tek / slap (frame drum), soft_kick, shaker, riq, timpani, tom, woodblock,
  cymbal_swell
All functions take explicit numpy Generators for any randomness.
"""

from __future__ import annotations

import numpy as np

from skyaudio import SR, env_ar, fft_shape, band_curve, lp_curve, hp_curve, midi_hz, pan

TABLE_N = 4096
_X = np.arange(TABLE_N) / TABLE_N


# --------------------------------------------------------------------------- wavetables
def make_table(amps, phases=None):
    tab = np.zeros(TABLE_N)
    for k, a in enumerate(amps, 1):
        if a:
            p = 0.0 if phases is None else phases[k - 1]
            tab += a * np.sin(2 * np.pi * k * _X + p)
    return tab


def wt_play(tab, freq, n, phase0=0.0):
    f = np.full(n, float(freq)) if np.isscalar(freq) else np.asarray(freq, dtype=float)
    ph = (phase0 + np.cumsum(f) / SR) % 1.0
    idx = ph * TABLE_N
    i0 = idx.astype(np.int64)
    fr = idx - i0
    return tab[i0] + (tab[(i0 + 1) % TABLE_N] - tab[i0]) * fr


def saw_amps(f0, fc, slope=4.0, fmax=15000.0, even=1.0, kmax=200):
    k = np.arange(1, kmax + 1)
    a = (1.0 / k) / (1.0 + (k * f0 / fc) ** slope)
    a[k * f0 > min(fmax, 0.45 * SR)] = 0
    a[1::2] *= even
    a[a < 1e-4 * a[0]] = 0
    return a


# --------------------------------------------------------------------------- sustained voices
def pad_note(m, dur, rng, attack=1.2, release=1.6, bright=1.0, detune=7.0, width=0.7, even=0.55, amp=1.0):
    """Warm detuned pad note (stereo)."""
    f0 = float(midi_hz(m))
    n = int((dur + release) * SR)
    tab = make_table(saw_amps(f0, 900 * bright + 0.8 * f0, 4.0, even=even))
    out = np.zeros((n, 2))
    e = env_ar(n, attack, release)
    t = np.arange(n) / SR
    for c, p in zip((-1.0, 0.0, 1.0), (-width, 0.0, width)):
        f = f0 * 2 ** (c * detune / 1200)
        drift = 1 + 0.0007 * np.sin(2 * np.pi * (0.13 + 0.05 * rng.random()) * t + rng.random() * 6.28)
        v = wt_play(tab, f * drift, n, rng.random())
        lfo = 0.9 + 0.1 * np.sin(2 * np.pi * (0.17 + 0.1 * rng.random()) * t + rng.random() * 6.28)
        out += pan(v * e * lfo, p)
    return out * amp / 3


def strings_note(m, dur, rng, attack=0.5, release=0.9, bright=1.0, vib_cents=7.0, amp=1.0, width=0.6):
    f0 = float(midi_hz(m))
    n = int((dur + release) * SR)
    t = np.arange(n) / SR
    tab = make_table(saw_amps(f0, 1700 * bright + f0, 3.0, even=0.9))
    e = env_ar(n, attack, release)
    out = np.zeros((n, 2))
    vib_on = np.clip((t - 0.25) / 0.6, 0, 1)
    for i, (c, p) in enumerate(zip((-9, -3, 3, 9), (-width, -width / 3, width / 3, width))):
        rate = 5.0 + 0.6 * rng.random()
        vib = 2 ** ((vib_cents * vib_on * np.sin(2 * np.pi * rate * t + rng.random() * 6.28)) / 1200)
        f = f0 * 2 ** (c / 1200) * vib
        out += pan(wt_play(tab, f, n, rng.random()) * e, p)
    bow = fft_shape(rng.standard_normal(n), band_curve(1800, 5000, 2)) * e * 0.015
    out += pan(bow, 0.0)
    return out * amp / 4


def brass_note(m, dur, rng, attack=0.09, release=0.35, amp=1.0, width=0.35):
    f0 = float(midi_hz(m))
    n = int((dur + release) * SR)
    t = np.arange(n) / SR
    dark = make_table(saw_amps(f0, 500 + f0, 3.0, even=1.0))
    bright = make_table(saw_amps(f0, 2600 + f0, 3.0, even=1.0))
    e = env_ar(n, attack, release)
    swell = np.clip(np.minimum(t / (attack * 2.5), 1.0) * (0.75 + 0.25 * np.exp(-t / 0.4)), 0, 1)
    scoop = 2 ** ((-25 * np.exp(-t / 0.035)) / 1200)
    out = np.zeros((n, 2))
    for c, p in zip((-5, 0, 5), (-width, 0, width)):
        f = f0 * 2 ** (c / 1200) * scoop
        ph = rng.random()
        v = wt_play(dark, f, n, ph) * (1 - swell * 0.8) + wt_play(bright, f, n, ph) * swell * 0.8
        out += pan(v * e, p)
    return out * amp / 3


def drone_note(m, dur, rng, attack=3.0, release=3.0, bright=0.6, amp=1.0, mod_rate=0.07):
    f0 = float(midi_hz(m))
    n = int((dur + release) * SR)
    t = np.arange(n) / SR
    dark = make_table(saw_amps(f0, 220 * bright + f0, 4.0, even=0.4))
    lite = make_table(saw_amps(f0, 900 * bright + f0, 4.0, even=0.4))
    e = env_ar(n, attack, release)
    out = np.zeros((n, 2))
    for c, p in zip((-4, 4), (-0.5, 0.5)):
        mod = 0.5 + 0.5 * np.sin(2 * np.pi * mod_rate * t + rng.random() * 6.28)
        ph = rng.random()
        f = f0 * 2 ** (c / 1200)
        out += pan((wt_play(dark, f, n, ph) * (1 - mod) + wt_play(lite, f, n, ph) * mod) * e, p)
    return out * amp / 2


def bass_note(m, dur, rng, amp=1.0, release=0.08, attack=0.006):
    f0 = float(midi_hz(m))
    n = int((dur + release) * SR)
    t = np.arange(n) / SR
    tab = make_table([1.0, 0.32, 0.12, 0.05, 0.02])
    e = env_ar(n, attack, release) * (0.72 + 0.28 * np.exp(-t / 0.25))
    return wt_play(tab, f0, n, rng.random()) * e * amp


def pluck_bass(m, dur, rng, amp=1.0, cutoff=2200.0, tau_f=0.12, release=0.05):
    f0 = float(midi_hz(m))
    n = int((dur + release) * SR)
    t = np.arange(n) / SR
    fc = 260 + cutoff * np.exp(-t / tau_f)
    y = np.zeros(n)
    for k in range(1, 40):
        if k * f0 > 9000:
            break
        y += (1 / k) / (1 + (k * f0 / fc) ** 4) * np.sin(2 * np.pi * k * f0 * t + rng.random() * 6.28)
    e = env_ar(n, 0.004, release) * (0.6 + 0.4 * np.exp(-t / 0.18))
    return y * e * amp


# --------------------------------------------------------------------------- plucked / struck
PLUCKS = {
    #        pos   tilt  hf-damp  tau@220  inharm   courses det(c) pick
    "kanun": (0.11, 0.85, 0.07, 2.4, 0.00025, 3, 2.5, 0.05),
    "oud":   (0.19, 1.25, 0.16, 1.4, 0.00008, 2, 3.5, 0.035),
    "harp":  (0.15, 1.05, 0.10, 2.8, 0.00010, 1, 0.0, 0.02),
    "pizz":  (0.20, 1.40, 0.30, 0.5, 0.00005, 2, 4.0, 0.02),
}


def pluck(m, rng, kind="kanun", vel=1.0, dur=None, bright=1.0):
    pos, tilt, damp, tau220, B, courses, det, pick = PLUCKS[kind]
    f0 = float(midi_hz(m))
    tau1 = tau220 * (220.0 / f0) ** 0.45
    dur = dur or min(4.0, tau1 * 4.0)
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    kmax = int(min(48, 11000 / f0))
    tilt_v = tilt - 0.25 * (vel - 0.7) - 0.25 * (bright - 1.0)
    for c in range(courses):
        d = 2 ** (((c - (courses - 1) / 2) * det) / 1200)
        for k in range(1, kmax + 1):
            fk = f0 * d * k * np.sqrt(1 + B * k * k)
            if fk > 13000:
                break
            ak = abs(np.sin(np.pi * k * pos)) / k ** tilt_v
            tk = tau1 / (1 + damp * (k - 1) ** 1.35)
            m_ = min(n, int(tk * 7 * SR))
            y[:m_] += ak * np.sin(2 * np.pi * fk * t[:m_] + rng.random() * 6.28) * np.exp(-t[:m_] / tk)
    y /= courses
    a = int(0.0015 * SR)
    y[:a] *= np.linspace(0, 1, a)
    if pick:
        pn = int(0.006 * SR)
        burst = fft_shape(rng.standard_normal(pn), band_curve(1200, 6500, 2)) * np.exp(-np.arange(pn) / (0.0015 * SR))
        y[:pn] += burst * pick * vel * 4
    fade_n = int(0.02 * SR)
    y[-fade_n:] *= np.linspace(1, 0, fade_n)
    return y * vel * 0.5


def marimba(m, rng, vel=1.0, dur=None):
    f0 = float(midi_hz(m))
    tau1 = float(np.clip(0.85 * (330.0 / f0) ** 0.6, 0.25, 1.8))
    dur = dur or tau1 * 5
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = (np.sin(2 * np.pi * f0 * t + rng.random()) * np.exp(-t / tau1)
         + 0.5 * np.sin(2 * np.pi * f0 * 1.003 * t + rng.random()) * np.exp(-t / (tau1 * 1.3))
         + 0.22 * vel * np.sin(2 * np.pi * f0 * 3.99 * t) * np.exp(-t / 0.11)
         + 0.06 * vel * np.sin(2 * np.pi * f0 * 9.6 * t) * np.exp(-t / 0.035))
    a = int(0.0025 * SR)
    y[:a] *= 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, a))
    tn = int(0.01 * SR)
    y[:tn] += fft_shape(rng.standard_normal(tn), lp_curve(1800, 2)) * np.exp(-np.arange(tn) / (0.002 * SR)) * 0.08 * vel
    fade_n = int(0.02 * SR)
    y[-fade_n:] *= np.linspace(1, 0, fade_n)
    return y * vel * 0.45


BELL_SOFT = [(1.0, 1.0, 1.0), (2.0, 0.32, 0.55), (3.0, 0.14, 0.32), (4.16, 0.09, 0.2), (5.43, 0.05, 0.13),
             (6.79, 0.025, 0.08)]
BELL_GLASS = [(1.0, 1.0, 1.0), (2.76, 0.28, 0.4), (5.40, 0.10, 0.18), (8.93, 0.03, 0.08)]
BELL_TUBE = [(1.0, 1.0, 1.0), (2.0, 0.45, 0.6), (3.0, 0.22, 0.45), (4.5, 0.12, 0.25), (5.5, 0.07, 0.18),
             (0.5, 0.18, 1.2)]


def bell(m_or_hz, rng, tau=1.2, vel=1.0, partials=BELL_SOFT, attack=0.003, dur=None, hz=False, fmax=11000):
    f0 = float(m_or_hz) if hz else float(midi_hz(m_or_hz))
    dur = dur or tau * 5
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for r, a, ts in partials:
        if f0 * r > fmax:
            continue
        y += a * np.sin(2 * np.pi * f0 * r * t + rng.random() * 6.28) * np.exp(-t / (tau * ts))
    k = max(2, int(attack * SR))
    y[:k] *= 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, k))
    fade_n = min(n // 4, int(0.03 * SR))
    y[-fade_n:] *= np.linspace(1, 0, fade_n)
    return y * vel * 0.5


def fm_bell(m_or_hz, rng, tau=1.4, ratio=1.0, index=2.2, itau=0.25, vel=1.0, attack=0.002, dur=None, hz=False):
    """Warm 'golden' FM bell/tine. ratio 1.0 = brassy tine, 1.4 = metallic bell, 3.5 = glassy."""
    fc = float(m_or_hz) if hz else float(midi_hz(m_or_hz))
    dur = dur or tau * 5
    n = int(dur * SR)
    t = np.arange(n) / SR
    idx = index * vel * np.exp(-t / itau)
    y = np.sin(2 * np.pi * fc * t + idx * np.sin(2 * np.pi * fc * ratio * t) + rng.random() * 6.28)
    y *= np.exp(-t / tau)
    k = max(2, int(attack * SR))
    y[:k] *= 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, k))
    fade_n = min(n // 4, int(0.03 * SR))
    y[-fade_n:] *= np.linspace(1, 0, fade_n)
    return y * vel * 0.5


def glass(m, rng, vel=1.0, tau=1.6):
    return bell(m, rng, tau=tau, vel=vel, partials=BELL_GLASS, attack=0.006)


# --------------------------------------------------------------------------- percussion
MEMBRANE = [(1.0, 1.0, 1.0), (1.59, 0.5, 0.38), (2.14, 0.34, 0.28), (2.30, 0.26, 0.24), (2.65, 0.18, 0.2),
            (2.92, 0.12, 0.17), (3.16, 0.08, 0.15), (3.50, 0.05, 0.12)]


def _membrane(f1, tau, n, rng, bend=0.12, bend_tau=0.03, modes=MEMBRANE):
    t = np.arange(n) / SR
    pitch = 1 + bend * np.exp(-t / bend_tau)
    y = np.zeros(n)
    for r, a, ts in modes:
        ph = 2 * np.pi * np.cumsum(f1 * r * pitch) / SR + rng.random() * 6.28
        y += a * np.sin(ph) * np.exp(-t / (tau * ts))
    return y


def doum(rng, vel=1.0, f1=76.0, tau=0.34, dur=0.9):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = _membrane(f1, tau, n, rng)
    sk = fft_shape(rng.standard_normal(n), lp_curve(1100, 2)) * np.exp(-t / 0.012) * 0.35
    y = (y + sk) * vel
    y[:48] *= np.linspace(0, 1, 48)
    return y * 0.55


def tek(rng, vel=1.0, f=430.0, dur=0.25):
    n = int(dur * SR)
    t = np.arange(n) / SR
    modes = [(1.0, 1.0, 1.0), (1.62, 0.6, 0.7), (2.31, 0.4, 0.5), (3.07, 0.25, 0.35)]
    y = _membrane(f, 0.055, n, rng, bend=0.04, bend_tau=0.01, modes=modes) * 0.6
    y += fft_shape(rng.standard_normal(n), band_curve(1400, 6500, 2)) * np.exp(-t / 0.014) * 0.9
    y[:24] *= np.linspace(0, 1, 24)
    return y * vel * 0.35


def slap(rng, vel=1.0, dur=0.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = fft_shape(rng.standard_normal(n), band_curve(350, 3200, 2)) * np.exp(-t / 0.02)
    y += 0.5 * np.sin(2 * np.pi * 240 * t) * np.exp(-t / 0.045)
    y[:24] *= np.linspace(0, 1, 24)
    return y * vel * 0.35


def soft_kick(rng, vel=1.0, dur=0.6, f_end=48.0, f_start=115.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f_end + (f_start - f_end) * np.exp(-t / 0.028)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.26)
    y += fft_shape(rng.standard_normal(n), lp_curve(2500, 2)) * np.exp(-t / 0.003) * 0.12
    y[:48] *= np.linspace(0, 1, 48)
    return y * vel * 0.8


def shaker(rng, vel=1.0, dur=0.12, attack=0.008, tau=0.028):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = fft_shape(rng.standard_normal(n), band_curve(3200, 7800, 2))
    e = (1 - np.exp(-t / attack)) * np.exp(-t / tau)
    return y * e * vel * 0.22


def riq(rng, vel=1.0, dur=0.3):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for f in (3150, 3890, 4710, 5620, 6480):
        f = f * (1 + 0.01 * rng.standard_normal())
        y += np.sin(2 * np.pi * f * t + rng.random() * 6.28) * np.exp(-t / (0.05 + 0.04 * rng.random()))
    y = y * 0.15 + fft_shape(rng.standard_normal(n), band_curve(3000, 8000, 2)) * np.exp(-t / 0.02) * 0.4
    y[:24] *= np.linspace(0, 1, 24)
    return y * vel * 0.18


def timpani(m, rng, vel=1.0, dur=2.5):
    f1 = float(midi_hz(m))
    n = int(dur * SR)
    t = np.arange(n) / SR
    modes = [(1.0, 1.0, 1.0), (1.50, 0.6, 0.75), (1.98, 0.38, 0.55), (2.44, 0.22, 0.4), (2.90, 0.12, 0.3)]
    y = _membrane(f1, 1.1, n, rng, bend=0.03, bend_tau=0.05, modes=modes)
    y += fft_shape(rng.standard_normal(n), lp_curve(900, 2)) * np.exp(-t / 0.02) * 0.5
    y[:96] *= np.linspace(0, 1, 96)
    return y * vel * 0.5


def tom(rng, vel=1.0, f1=110.0, dur=0.8):
    return doum(rng, vel, f1=f1, tau=0.28, dur=dur)


def woodblock(rng, vel=1.0, f=880.0, dur=0.15):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = (np.sin(2 * np.pi * f * t) * np.exp(-t / 0.03) + 0.4 * np.sin(2 * np.pi * f * 2.57 * t) * np.exp(-t / 0.012))
    y[:24] *= np.linspace(0, 1, 24)
    return y * vel * 0.35


def cymbal_swell(rng, dur=2.0, vel=1.0, hi=7500.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = fft_shape(rng.standard_normal(n), band_curve(1800, hi, 2))
    e = (t / dur) ** 2.6
    e[-int(0.02 * SR):] *= np.linspace(1, 0, int(0.02 * SR))
    return y * e * vel * 0.12


def roll(rng, dur=1.0, vel=1.0, f1=76.0, rate=16.0, crescendo=True):
    """Frame-drum roll (stereo-free mono): repeated soft doums with rising level."""
    n = int((dur + 0.6) * SR)
    y = np.zeros(n)
    k = int(dur * rate)
    for i in range(k):
        g = (0.25 + 0.75 * (i / max(1, k - 1)) ** 1.5) if crescendo else 1.0
        h = doum(rng, vel * g * (0.85 + 0.15 * rng.random()), f1=f1 * (1 + 0.02 * rng.standard_normal()),
                 tau=0.2, dur=0.6)
        s = int(i / rate * SR)
        y[s:s + len(h)] += h[: n - s]
    return y
