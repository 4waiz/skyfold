#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy"]
# ///
"""SKYFOLD original music (offline synthesis, deterministic, no samples).

    python tools/audio/make_music.py                 # all pieces -> Assets/Skyfold/Audio/Music/
    python tools/audio/make_music.py music_menu_loop stinger_success

Emotional arc: calm wonder (menu, D lydian) -> curious puzzle (architect, B dorian) ->
warm adventure (street, G major) -> upbeat drive (drive, A major) -> tension layer (storm,
D minor) -> triumphant release (finale D major lifting to E major) + three stingers.
A shared five-note "Skyfold" motif (1-2-3-5, with a lydian #4 colour) links the pieces.

Loops are built bar-aligned on an exact sample grid: every note, delay tap and reverb tail
that runs past the loop end is wrapped onto the start (circular convolution), drones use
whole-cycle frequencies, and the limiter runs circularly, so file end -> file start is a
seamless continuation. Masters: stereo 48 kHz 16-bit, -20 LUFS integrated, <= -1.5 dBTP.
"""

from __future__ import annotations

import json
import sys
import zlib
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skyaudio as sa  # noqa: E402
import skysynth as ss  # noqa: E402
from skyaudio import SR, nm  # noqa: E402

OUT = sa.AUDIO / "Music"
REPORT = sa.TOOLS / "reports" / "music.json"
TARGET_LUFS, TP = -20.0, -1.5
DUR = {"w": 4.0, "h": 2.0, "q": 1.0, "e": 0.5, "s": 0.25, "t": 1 / 3}


def mel(text, start=0.0):
    """'D5:q E5:e r:e A5:h.' -> [(beat, dur_beats, midi)] starting at `start` beats."""
    out, b = [], start
    for tok in text.split():
        name, d = tok.split(":")
        dot = d.endswith(".")
        dur = DUR[d.rstrip(".")] * (1.5 if dot else 1.0)
        if name != "r":
            out.append((b, dur, nm(name)))
        b += dur
    return out


def arp_tones(pad, lo=60, hi=86):
    s = set()
    for p in pad:
        for k in range(-2, 4):
            q = p + 12 * k
            if lo <= q <= hi:
                s.add(q)
    return sorted(s)


def loop_freq(f, seconds):
    return round(f * seconds) / seconds


# --------------------------------------------------------------------------- sequencer
class Track:
    def __init__(self, name, bpm, bars, loop=True, tail=0.0, seed=0, rt60=2.2, verb_gain=1.0):
        self.name, self.bpm, self.bars, self.loop = name, bpm, bars, loop
        self.beat = 60.0 / bpm
        self.bar = 4 * self.beat
        self.n_body = int(round(bars * self.bar * SR))
        self.n = self.n_body if loop else self.n_body + int(tail * SR)
        self.rng = np.random.default_rng(seed)
        self.buses = {}
        self.rt60, self.verb_gain = rt60, verb_gain

    def bus(self, name, level=-10.0, verb=0.2, delay=None):
        """level: target loudness of this bus in LU relative to the mix reference (gated BS.1770, so a
        part that only plays in one section is judged while it plays)."""
        self.buses[name] = {"buf": np.zeros((self.n, 2)), "level": level, "verb": verb, "delay": delay}

    def s(self, bar, beat=0.0):
        return (bar * self.bar + beat * self.beat) * SR

    def put(self, bus, x, at, pan=0.0, gain_db=0.0, jitter=0.004):
        if x.ndim == 1:
            x = sa.pan(x, pan)
        j = self.rng.normal(0, jitter) * SR if jitter else 0.0
        at = at + j
        if not self.loop:
            at = max(0.0, at)
        sa.place(self.buses[bus]["buf"], x * sa.db2a(gain_db), int(round(at)), wrap=self.loop)

    def vel(self, base, spread=0.08):
        return float(np.clip(base * (1 + self.rng.normal(0, spread)), 0.05, 1.2))

    # ---- instrument helpers
    def pad(self, bus, bar, bars, notes, attack=1.0, release=1.8, bright=1.0, amp=1.0, gain_db=0.0):
        for m in notes:
            x = ss.pad_note(m, bars * self.bar, self.rng, attack=attack, release=release, bright=bright, amp=amp)
            self.put(bus, x, self.s(bar), gain_db=gain_db, jitter=0)

    def strings(self, bus, bar, beats, notes, attack=0.6, release=1.0, bright=1.0, amp=1.0, gain_db=0.0, beat=0.0):
        for m in notes:
            x = ss.strings_note(m, beats * self.beat, self.rng, attack=attack, release=release, bright=bright, amp=amp)
            self.put(bus, x, self.s(bar, beat), gain_db=gain_db, jitter=0)

    def notes(self, bus, bar, seq, kind="kanun", vel=0.8, pan=0.0, gain_db=0.0, legato=False):
        for b, d, m in seq:
            v = self.vel(vel)
            if kind == "marimba":
                x = ss.marimba(m, self.rng, v)
            elif kind == "bell":
                x = ss.bell(m, self.rng, tau=1.4, vel=v)
            elif kind == "glass":
                x = ss.glass(m, self.rng, v)
            elif kind == "fm":
                x = ss.fm_bell(m, self.rng, tau=1.2, ratio=1.0, index=1.4, vel=v)
            elif kind == "brass":
                x = ss.brass_note(m, d * self.beat, self.rng, amp=v)
            elif kind == "strings":
                x = ss.strings_note(m, d * self.beat, self.rng, attack=0.25, release=0.6, amp=v)
            else:
                x = ss.pluck(m, self.rng, kind, vel=v)
            self.put(bus, x, self.s(bar, b), pan=pan, gain_db=gain_db)

    def arp(self, bus, bar, tones, pattern, step=0.5, vel=0.7, accent=1.25, kind="kanun", pan=0.0, beats=4.0,
            gain_db=0.0):
        k, b = 0, 0.0
        while b < beats - 1e-9:
            idx = pattern[k % len(pattern)]
            if idx is not None:
                m = tones[idx % len(tones)]
                v = vel * (accent if abs(b % 1.0) < 1e-9 and abs(b) < 1e-9 else 1.0)
                self.notes(bus, bar, [(b, step, m)], kind=kind, vel=v, pan=pan, gain_db=gain_db)
            k += 1
            b += step

    def bass(self, bus, bar, seq, kind="round", vel=0.8, gain_db=0.0):
        for b, d, m in seq:
            v = self.vel(vel, 0.05)
            if kind == "pluck":
                x = ss.pluck_bass(m, d * self.beat * 0.9, self.rng, amp=v)
            elif kind == "pizz":
                x = ss.pluck(m, self.rng, "pizz", vel=v)
            else:
                x = ss.bass_note(m, d * self.beat * 0.95, self.rng, amp=v)
            self.put(bus, x, self.s(bar, b), gain_db=gain_db)

    def drums(self, bus, bar, pattern, kit, step=0.25, vel=0.8, pan=0.0, gain_db=0.0):
        """pattern string, one char per step: kit maps char -> callable(rng, vel)."""
        for i, ch in enumerate(pattern):
            if ch in kit:
                fn, v0 = kit[ch]
                self.put(bus, fn(self.rng, self.vel(vel * v0, 0.1)), self.s(bar, i * step), pan=pan, gain_db=gain_db,
                         jitter=0.003)

    # ---- render
    def render(self, ir_seed=11):
        n = self.n
        dry = np.zeros((n, 2))
        send = np.zeros((n, 2))
        levels = {}
        for name, b in self.buses.items():
            x = b["buf"]
            if b["delay"]:
                t_s, fb, taps, lp = b["delay"]
                x = x + sa.delay(x, t_s, fb=fb, taps=taps, lp_hz=lp, pingpong=True, circular=self.loop)
            if not np.any(x):
                continue
            L = sa.lufs(x)
            g = (b["level"] - 20.0) - L
            x = x * sa.db2a(g)
            levels[name] = {"target_lu": b["level"], "measured_lufs": round(L, 1), "gain_db": round(g, 1)}
            dry += x
            send += x * b["verb"]
        ir = sa.reverb_ir(self.rt60, seed=ir_seed)
        wet = sa.convolve(send, ir, circular=self.loop)[:n] * self.verb_gain
        mix = dry + wet
        if self.loop:
            mix = sa.filt_circ(mix - mix.mean(axis=0), sa.sos("highpass", 28, 2))
        else:
            mix = sa.hp(mix, 28, 2)
        return mix, levels


def master(tr: Track, mix):
    y = sa.normalize_lufs(mix, TARGET_LUFS, TP, circular=tr.loop, window_ms=8.0)
    if not tr.loop:
        y = sa.fade(y, 0.002, 0.8)
    return y


# --------------------------------------------------------------------------- loop-safe drone
def loop_drone(tr, bus, midis, bright=0.6, amp=1.0, gain_db=0.0, wobble_cycles=3):
    T = tr.n / SR
    n = tr.n
    out = np.zeros((n, 2))
    for m in midis:
        f0 = float(sa.midi_hz(m))
        dark = ss.make_table(ss.saw_amps(f0, 220 * bright + f0, 4.0, even=0.4))
        lite = ss.make_table(ss.saw_amps(f0, 900 * bright + f0, 4.0, even=0.4))
        for c, p in ((-4, -0.5), (4, 0.5)):
            f = loop_freq(f0 * 2 ** (c / 1200), T)
            mod = 0.5 + 0.5 * sa.periodic_lfo(n, wobble_cycles + (c > 0), tr.rng)
            ph = tr.rng.random()
            v = ss.wt_play(dark, f, n, ph) * (1 - mod) + ss.wt_play(lite, f, n, ph) * mod
            out += sa.pan(v, p)
    tr.buses[bus]["buf"] += out * amp / (2 * len(midis)) * sa.db2a(gain_db)


def noise_swell(tr, dur_s, rng, lo=300, hi=2500, rise=True):
    n = int(dur_s * SR)
    x = sa.noise(n, rng, "pink")
    x = sa.fft_shape(x, sa.band_curve(lo, hi))
    t = np.arange(n) / n
    e = t ** 2.2 if rise else (1 - t) ** 2.2
    x = x * e
    x = sa.fade(x, 0.01, 0.05)
    return x / (np.max(np.abs(x)) or 1)


# --------------------------------------------------------------------------- 1. menu
def music_menu_loop():
    tr = Track("music_menu_loop", 72, 24, loop=True, seed=101, rt60=2.6)
    tr.bus("pad", -10, 0.4)
    tr.bus("kanun", -10, 0.3, delay=(0.75 * tr.beat, 0.28, 4, 3200))
    tr.bus("mar", -7, 0.3)
    tr.bus("bell", -18, 0.6)
    tr.bus("bass", -13, 0.05)
    tr.bus("perc", -17, 0.2)
    C = {
        "Dmaj9": (38, [50, 57, 61, 64, 66]), "E/D": (38, [50, 56, 59, 64, 68]), "Bm9": (35, [47, 54, 57, 61, 62]),
        "Gmaj9": (43, [47, 54, 57, 59, 62]), "Asus4": (45, [50, 52, 57, 62, 64]), "A": (45, [49, 52, 57, 61, 64]),
        "Gmaj7": (43, [47, 50, 54, 57, 62]), "A/G": (43, [49, 52, 57, 61, 64]), "F#m7": (42, [45, 49, 52, 57, 61]),
        "A6": (45, [49, 54, 57, 61, 64]), "D/F#": (42, [50, 57, 62, 66]), "Em9": (40, [50, 55, 59, 62, 66]),
    }
    tl = [(0, 2, "Dmaj9"), (2, 2, "E/D"), (4, 2, "Bm9"), (6, 1, "Gmaj9"), (7, .5, "Asus4"), (7.5, .5, "A"),
          (8, 1, "Gmaj7"), (9, 1, "A/G"), (10, 1, "F#m7"), (11, 1, "Bm9"), (12, 1, "Gmaj9"), (13, 1, "A6"),
          (14, 1, "D/F#"), (15, .5, "Asus4"), (15.5, .5, "A"),
          (16, 1, "Dmaj9"), (17, 1, "E/D"), (18, 1, "Dmaj9"), (19, 1, "E/D"), (20, 1, "Bm9"), (21, 1, "Gmaj9"),
          (22, 1, "Em9"), (23, .5, "Asus4"), (23.5, .5, "A")]
    for bar, length, ch in tl:
        b, pad = C[ch]
        tr.pad("pad", bar, length, pad, attack=1.1, release=2.0, bright=0.85)
        vb = 0.5 if bar < 8 else (0.7 if bar < 16 else 0.6)
        tr.bass("bass", bar, [(0, length * 4, b)], vel=vb)
    # kanun arpeggios in A and A' (lighter in B)
    pats = [[0, 2, 4, 3, 5, 4, 6, 4], [7, 5, 6, 4, 5, 3, 4, 2], [0, 3, 5, 4, 6, 5, 7, 5], [6, 4, 5, 2, 4, 1, 3, 2]]
    for bar in range(24):
        ch = [c for (b0, L, c) in tl if b0 <= bar + 0.01 < b0 + L][0]
        tones = arp_tones(C[ch][1], 62, 86)
        if bar < 8 or bar >= 16:
            tr.arp("kanun", bar, tones, pats[bar % 4], step=0.5, vel=0.55 if bar % 8 else 0.62, pan=0.25)
        elif bar % 2 == 1:
            tr.arp("kanun", bar, tones, [None, None, None, None, 4, 5, 6, 7], step=0.5, vel=0.42, pan=0.3)
    # marimba theme (B section) - the Skyfold motif and its answer
    theme = ["B4:q D5:e F#5:e A5:h", "E5:q C#5:e D5:e E5:h", "F#5:q E5:e C#5:e A4:h", "B4:q. C#5:e D5:h",
             "D5:q E5:e F#5:e A5:q B5:q", "A5:h F#5:q E5:q", "F#5:q E5:e D5:e E5:h", "D5:h C#5:h"]
    for i, phrase in enumerate(theme):
        tr.notes("mar", 8 + i, mel(phrase), kind="marimba", vel=0.75, pan=-0.2)
    # motif echo on kanun in A' (bars 16-19), up high and soft
    tr.notes("kanun", 18, mel("D6:e E6:e F#6:e A6:e G#6:q F#6:q"), vel=0.4, pan=0.35)
    for bar, m in [(0, 93), (8, 90), (16, 86), (16, 93), (20, 88)]:
        tr.notes("bell", bar, [(0, 4, m)], kind="glass", vel=0.7)
    for bar in range(16, 24):
        for beat in (1.0, 3.0):
            if tr.rng.random() < 0.45:
                ch = [c for (b0, L, c) in tl if b0 <= bar + 0.01 < b0 + L][0]
                tones = [t for t in arp_tones(C[ch][1], 86, 98)]
                tr.notes("bell", bar, [(beat, 1, int(tr.rng.choice(tones)))], kind="glass", vel=0.35)
    kit = {"D": (lambda r, v: ss.doum(r, v, f1=70), 0.6), "d": (lambda r, v: ss.doum(r, v, f1=70), 0.35),
           "s": (lambda r, v: ss.shaker(r, v), 0.5), "x": (lambda r, v: ss.shaker(r, v), 0.25)}
    for bar in range(8, 16):
        tr.drums("perc", bar, "D.......d.......", kit, vel=0.7)
        if bar >= 12:
            tr.drums("perc", bar, "..x.s.x...x.s.x.", kit, vel=0.6 + 0.05 * (bar - 12), pan=-0.3)
    return tr


# --------------------------------------------------------------------------- 2. architect
def music_architect_loop():
    tr = Track("music_architect_loop", 90, 24, loop=True, seed=202, rt60=2.0)
    tr.bus("pad", -13, 0.35)
    tr.bus("mar", -9, 0.22, delay=(0.75 * tr.beat, 0.22, 3, 2800))
    tr.bus("kanun", -8, 0.3, delay=(0.5 * tr.beat, 0.25, 3, 3000))
    tr.bus("bass", -12, 0.08)
    tr.bus("drums", -12, 0.12)
    tr.bus("bell", -19, 0.5)
    C = {"Bm9": (35, [47, 54, 57, 61, 62]), "E/B": (35, [52, 56, 59, 64]), "Gmaj7": (43, [47, 50, 54, 57]),
         "A": (45, [49, 52, 57, 61]), "F#m7": (42, [45, 49, 52, 54]), "F#7sus4": (42, [47, 49, 52, 54]),
         "Bm/A": (45, [47, 50, 54, 59])}
    A = ["Bm9", "E/B", "Bm9", "E/B", "Gmaj7", "A", "F#m7", "F#7sus4"]
    Cs = ["Gmaj7", "A", "Bm9", "Bm/A", "Gmaj7", "A", "F#m7", "F#7sus4"]
    tl = A + A + Cs
    for bar, ch in enumerate(tl):
        b, pad = C[ch]
        tr.pad("pad", bar, 1, pad, attack=0.6, release=1.4, bright=0.7)
        tones = arp_tones(pad, 59, 79)
        sec = bar // 8
        pat = [0, 3, 1, 3, 2, 3, 1, 3] if bar % 2 == 0 else [0, 3, 2, 4, 1, 3, 2, 4]
        if sec == 2 and bar % 2 == 1:
            pat = [0, None, 2, None, 1, None, 3, None]
        tr.arp("mar", bar, tones, pat, step=0.5, vel=0.55, kind="marimba", pan=-0.25)
        root = b
        five = root + 7
        bl = [(0, 0.5, root), (1.5, 0.5, root), (2, 0.5, five), (3, 0.5, root), (3.5, 0.5, root + 12)]
        if sec == 2:
            bl = [(0, 0.5, root), (2, 0.5, five), (3.5, 0.5, root)]
        tr.bass("bass", bar, bl, kind="pizz", vel=0.85)
        tr.bass("bass", bar, [(0, 4, root)], vel=0.25)
    theme = ["F#5:e B5:e A5:q F#5:q E5:e F#5:e", "G#5:q. F#5:e E5:h", "D5:e F#5:e B5:q C#6:q B5:q",
             "A5:q G#5:q E5:h", "F#5:q D5:e B4:e D5:h", "E5:q C#5:e A4:e E5:h", "A5:q. G#5:e F#5:q E5:q",
             "F#5:h E5:q C#5:q"]
    for i, ph in enumerate(theme):
        tr.notes("kanun", 8 + i, mel(ph), kind="kanun", vel=0.7, pan=0.2)
    # answer phrase in C section, oud-like and lower
    for i, ph in enumerate(["B4:q D5:q F#5:h", "E5:q C#5:q A4:h", "D5:q F#5:e A5:e B5:h", "A5:q F#5:q D5:h"]):
        tr.notes("kanun", 18 + i, mel(ph), kind="oud", vel=0.6, pan=0.1)
    kit = {"K": (lambda r, v: ss.soft_kick(r, v), 0.8), "k": (lambda r, v: ss.soft_kick(r, v), 0.5),
           "T": (lambda r, v: ss.tek(r, v, f=520), 0.55), "t": (lambda r, v: ss.tek(r, v, f=520), 0.25),
           "s": (lambda r, v: ss.shaker(r, v), 0.45), "x": (lambda r, v: ss.shaker(r, v), 0.22),
           "w": (lambda r, v: ss.woodblock(r, v, f=1180), 0.5)}
    for bar in range(24):
        sec = bar // 8
        if sec == 0:
            tr.drums("drums", bar, "K...T.......T...", kit)
        elif sec == 1:
            tr.drums("drums", bar, "K...T..tk...T.t.", kit)
            tr.drums("drums", bar, "x.s.x.s.x.s.x.s.", kit, pan=-0.35, gain_db=-2)
        else:
            tr.drums("drums", bar, "K.......T.......", kit)
            tr.drums("drums", bar, "x...s...x...s...", kit, pan=-0.35, gain_db=-3)
        if bar % 2 == 1:
            tr.drums("drums", bar, "..............w.", kit, pan=0.4)
    for bar, m in [(0, 90), (8, 95), (16, 86), (20, 93)]:
        tr.notes("bell", bar, [(0, 4, m)], kind="glass", vel=0.7)
    return tr


# --------------------------------------------------------------------------- 3. street
def music_street_loop():
    tr = Track("music_street_loop", 100, 32, loop=True, seed=303, rt60=1.8)
    tr.bus("pad", -13, 0.35)
    tr.bus("oud", -7, 0.25, delay=(0.75 * tr.beat, 0.2, 3, 2600))
    tr.bus("kanun", -13, 0.3, delay=(0.5 * tr.beat, 0.25, 3, 3200))
    tr.bus("str", -14, 0.45)
    tr.bus("bass", -11, 0.05)
    tr.bus("drums", -9, 0.12)
    C = {"G": (43, [50, 55, 57, 59, 62]), "D/F#": (42, [50, 54, 57, 62]), "Em7": (40, [50, 55, 59, 62]),
         "Cadd9": (36, [48, 52, 55, 62]), "D": (38, [50, 54, 57, 62]), "Dsus4": (38, [50, 55, 57, 62]),
         "Em": (40, [52, 55, 59, 64]), "C": (36, [48, 52, 55, 60]), "Am7": (45, [48, 52, 55, 57]),
         "Cmaj7": (36, [48, 52, 55, 59]), "Bm7": (35, [50, 54, 57, 59]), "G/B": (35, [50, 55, 59, 62])}
    A = ["G", "D/F#", "Em7", "Cadd9", "G", "D", "Cadd9", "Dsus4|D"]
    Cc = ["Em", "C", "G", "D", "Em", "C", "Am7", "Dsus4|D"]
    D = ["Cmaj7", "D", "Bm7", "Em7", "Cadd9", "D/F#", "Am7", "Dsus4|D"]
    tl = A + A + Cc + D
    for bar, chs in enumerate(tl):
        parts = chs.split("|")
        for k, ch in enumerate(parts):
            L = 4 / len(parts)
            b, pad = C[ch]
            tr.pad("pad", bar + k * L / 4, L / 4, pad, attack=0.5, release=1.2, bright=0.9)
        sec = bar // 8
        b0 = C[parts[0]][0]
        b1 = C[parts[-1]][0]
        nxt = C[tl[(bar + 1) % 32].split("|")[0]][0]
        approach = nxt - 2 if nxt - 2 > 30 else nxt + 2
        bl = [(0, 1.5, b0), (1.5, 0.5, b0 + 12), (2, 1.0, b1 + 7 if b1 + 7 < 52 else b1 - 5), (3, 0.5, b1),
              (3.5, 0.5, approach)]
        if sec == 3 and bar % 2 == 0:
            bl = [(0, 2, b0), (2, 2, b1 + 7 if b1 + 7 < 52 else b1 - 5)]
        tr.bass("bass", bar, bl, vel=0.9)
        tones = arp_tones(C[parts[0]][1], 62, 84)
        if sec in (0, 3):
            pat = [0, 2, 4, 2, 5, 4, 3, 1] if bar % 2 == 0 else [4, 3, 5, 2, 4, 1, 3, 0]
            tr.arp("kanun", bar, tones, pat, step=0.5, vel=0.5, pan=0.3)
        if sec >= 2:
            tr.strings("str", bar, 4, [t for t in tones if 66 <= t <= 79][:3], attack=0.8, release=1.2, bright=0.8,
                       amp=0.7)
    themeB = ["D5:q G5:e A5:e B5:q A5:e G5:e", "A5:q. F#5:e D5:h", "E5:q G5:e A5:e B5:q D6:q", "D6:q. B5:e G5:q E5:q",
              "D5:q G5:e A5:e B5:q A5:e B5:e", "A5:h F#5:q A5:q", "G5:q E5:e D5:e E5:q G5:q", "A5:h F#5:h"]
    themeC = ["B5:q G5:q E5:q G5:q", "A5:q. G5:e E5:h", "D5:q G5:q B5:q D6:q", "A5:h. F#5:q",
              "G5:q E5:e G5:e B5:q A5:q", "G5:q E5:q C5:q E5:q", "E5:q G5:q A5:h", "G5:h F#5:h"]
    for i, ph in enumerate(themeB):
        tr.notes("oud", 8 + i, mel(ph), kind="oud", vel=0.85, pan=-0.12)
    for i, ph in enumerate(themeC):
        seq = mel(ph)
        tr.notes("oud", 16 + i, seq, kind="oud", vel=0.85, pan=-0.12)
        tr.notes("kanun", 16 + i, [(b, d, m + 12) for b, d, m in seq], kind="kanun", vel=0.4, pan=0.35)
    kit = {"D": (lambda r, v: ss.doum(r, v, f1=78), 0.9), "d": (lambda r, v: ss.doum(r, v, f1=78), 0.55),
           "T": (lambda r, v: ss.tek(r, v), 0.7), "t": (lambda r, v: ss.tek(r, v), 0.35),
           "K": (lambda r, v: ss.soft_kick(r, v), 0.7), "s": (lambda r, v: ss.shaker(r, v), 0.5),
           "x": (lambda r, v: ss.shaker(r, v), 0.28), "r": (lambda r, v: ss.riq(r, v), 0.5)}
    for bar in range(32):
        sec = bar // 8
        if sec == 3 and bar < 30:
            tr.drums("drums", bar, "D.......d...T...", kit, step=0.25)
            tr.drums("drums", bar, "x...x...x...x...", kit, pan=-0.35, gain_db=-3)
            continue
        tr.drums("drums", bar, "D.T...T.D.t.T.tt", kit)          # maqsum: D T - T D - T -
        tr.drums("drums", bar, "K.......K.......", kit, gain_db=-4)
        tr.drums("drums", bar, "x.s.x.s.x.s.x.s.", kit, pan=-0.35, gain_db=-2)
        if bar % 4 == 3:
            tr.drums("drums", bar, "............r.r.", kit, pan=0.3, gain_db=-4)
    return tr


# --------------------------------------------------------------------------- 4. drive
def music_drive_loop():
    tr = Track("music_drive_loop", 112, 32, loop=True, seed=404, rt60=1.6)
    tr.bus("pad", -14, 0.3)
    tr.bus("lead", -8, 0.22, delay=(0.75 * tr.beat, 0.22, 3, 3000))
    tr.bus("kanun", -15, 0.25, delay=(0.75 * tr.beat, 0.3, 4, 3200))
    tr.bus("bass", -10, 0.03)
    tr.bus("drums", -8, 0.1)
    tr.bus("fx", -19, 0.4)
    C = {"A": (33, [52, 57, 61, 64]), "E/G#": (32, [52, 56, 59, 64]), "F#m7": (30, [54, 57, 61, 64]),
         "Dadd9": (38, [50, 54, 57, 64]), "E": (40, [52, 56, 59, 64]), "D": (38, [50, 54, 57, 62]),
         "Esus4": (40, [52, 57, 59, 64]), "F#m": (30, [54, 57, 61, 66]), "Bm7": (35, [50, 54, 57, 62]),
         "C#m7": (37, [52, 56, 59, 61])}
    A = ["A", "E/G#", "F#m7", "Dadd9", "A", "E", "D", "Esus4|E"]
    Cc = ["F#m", "D", "A", "E", "F#m", "D", "Bm7", "Esus4|E"]
    D = ["D", "E", "C#m7", "F#m7", "D", "E", "Bm7", "Esus4|E"]
    tl = A + A + Cc + D
    for bar, chs in enumerate(tl):
        parts = chs.split("|")
        for k, ch in enumerate(parts):
            L = 4 / len(parts)
            tr.pad("pad", bar + k * L / 4, L / 4, C[ch][1], attack=0.3, release=0.9, bright=1.1)
        root = C[parts[0]][0]
        root = root + 12 if root < 33 else root
        r2 = C[parts[-1]][0]
        r2 = r2 + 12 if r2 < 33 else r2
        seq = [(i * 0.5, 0.5, (root if i < 4 else r2) + (12 if i in (2, 6) else 0)) for i in range(8)]
        tr.bass("bass", bar, seq, kind="pluck", vel=0.85)
        sec = bar // 8
        if sec in (0, 3):
            tones = arp_tones(C[parts[0]][1], 64, 88)
            tr.arp("kanun", bar, tones, [0, 2, 4, 6, 5, 3, 4, 2, 1, 3, 5, 7, 6, 4, 3, 1], step=0.25, vel=0.42,
                   pan=0.4)
    hookB = ["E5:e A5:e B5:e C#6:q B5:e A5:q", "B5:q. G#5:e E5:h", "F#5:e A5:e C#6:e E6:q C#6:e B5:q",
             "A5:q. F#5:e E5:h", "E5:e A5:e B5:e C#6:q E6:e C#6:q", "B5:h G#5:q B5:q", "A5:q F#5:e A5:e D6:q C#6:q",
             "B5:w"]
    hookC = ["C#6:q A5:q F#5:q A5:q", "B5:q. A5:e F#5:h", "E5:q A5:q C#6:q E6:q", "B5:h. G#5:q",
             "A5:q F#5:e A5:e C#6:q B5:q", "A5:q F#5:q D5:q F#5:q", "F#5:q A5:q B5:q D6:q", "A5:h G#5:h"]
    for i, ph in enumerate(hookB):
        seq = mel(ph)
        tr.notes("lead", 8 + i, seq, kind="marimba", vel=0.8, pan=-0.15)
        tr.notes("lead", 8 + i, seq, kind="kanun", vel=0.5, pan=0.15, gain_db=-3)
    for i, ph in enumerate(hookC):
        seq = mel(ph)
        tr.notes("lead", 16 + i, seq, kind="oud", vel=0.8, pan=-0.1)
        tr.notes("lead", 16 + i, seq, kind="marimba", vel=0.5, pan=0.2, gain_db=-5)
    kit = {"K": (lambda r, v: ss.soft_kick(r, v), 0.9), "D": (lambda r, v: ss.doum(r, v, f1=82), 0.7),
           "T": (lambda r, v: ss.tek(r, v), 0.75), "t": (lambda r, v: ss.tek(r, v), 0.3),
           "s": (lambda r, v: ss.shaker(r, v, tau=0.02), 0.5), "x": (lambda r, v: ss.shaker(r, v, tau=0.02), 0.25),
           "o": (lambda r, v: ss.tom(r, v, f1=150), 0.7), "m": (lambda r, v: ss.tom(r, v, f1=120), 0.7),
           "l": (lambda r, v: ss.tom(r, v, f1=95), 0.75)}
    for bar in range(32):
        last = bar % 8 == 7
        tr.drums("drums", bar, "K.....D.K.....K." if bar % 2 else "K.....D.K.......", kit)
        tr.drums("drums", bar, "..t.T..t..t.T..t" if not last else "..t.T..t..t.oomm", kit)
        tr.drums("drums", bar, "sxxxsxxxsxxxsxxx", kit, pan=-0.3, gain_db=-4)
        if last:
            tr.drums("drums", bar, "..............ll", kit)
            tr.put("fx", noise_swell(tr, 2 * tr.beat, tr.rng, 400, 5000), tr.s(bar, 2), pan=0.0)
    return tr


# --------------------------------------------------------------------------- 5. storm (tension layer)
def music_storm_loop():
    tr = Track("music_storm_loop", 90, 24, loop=True, seed=505, rt60=2.6)
    tr.bus("drone", -10, 0.3)
    tr.bus("ost", -8, 0.2)
    tr.bus("pad", -15, 0.4)
    tr.bus("perc", -10, 0.18)
    tr.bus("str", -17, 0.5)
    tr.bus("wind", -16, 0.4)
    loop_drone(tr, "drone", [26, 38, 45], bright=0.55)
    cyc = ["Dm", "Dm", "Bb", "A"]
    P = {"Dm": [50, 50, 53, 50, 52, 50, 45, 50], "Bb": [46, 46, 50, 46, 48, 46, 41, 46],
         "A": [45, 45, 49, 45, 52, 45, 40, 45]}
    PADS = {"Dm": [50, 53, 57], "Bb": [46, 50, 53], "A": [45, 49, 52]}
    alt = {"Dm": [50, 50, 53, 50, 55, 53, 52, 50]}
    acc = [1.0, 0.45, 0.6, 0.85, 0.45, 0.55, 0.8, 0.5]
    for bar in range(24):
        ch = cyc[bar % 4]
        pat = alt["Dm"] if (ch == "Dm" and bar % 8 == 1) else P[ch]
        for i, m in enumerate(pat):
            x = ss.pluck(m, tr.rng, "pizz", vel=0.85 * acc[i])
            x = sa.lp(x, 2000, 2)
            tr.put("ost", x, tr.s(bar, i * 0.5), pan=-0.1 if i % 2 else 0.1)
        tr.pad("pad", bar, 1, PADS[ch], attack=0.9, release=1.6, bright=0.45)
        tr.drums("perc", bar, "D..d..d.", {"D": (lambda r, v: ss.doum(r, v, f1=62, tau=0.4), 0.8),
                                           "d": (lambda r, v: ss.doum(r, v, f1=62, tau=0.3), 0.5)}, step=0.5)
        if bar >= 12:
            tr.drums("perc", bar, "...t...t", {"t": (lambda r, v: ss.tek(r, v, f=360), 0.25)}, step=0.5, pan=0.3)
        if bar % 8 == 7:
            tr.put("perc", ss.roll(tr.rng, dur=4 * tr.beat, vel=0.6, f1=58, rate=12), tr.s(bar), gain_db=-4)
            tr.put("perc", ss.timpani(38, tr.rng, vel=0.9), tr.s(bar + 1), gain_db=-2)
        if bar % 4 == 0:
            tr.put("wind", noise_swell(tr, 3 * tr.beat, tr.rng, 250, 1400), tr.s(bar, 1.0), pan=-0.4)
            tr.put("wind", noise_swell(tr, 2 * tr.beat, tr.rng, 300, 1600, rise=False), tr.s(bar, 4.0), pan=0.4)
    # tremolo minor-second rub in the second half
    n = int(12 * tr.bar * SR)
    t = np.arange(n) / SR
    for m in (69, 70):
        x = ss.strings_note(m, 12 * tr.bar - 1.0, tr.rng, attack=3.0, release=1.0, bright=0.6, amp=0.8)[:n]
        trem = 0.65 + 0.35 * np.sin(2 * np.pi * 12.0 * t)[: len(x)]
        tr.put("str", x * trem[:, None], tr.s(12), jitter=0)
    return tr


# --------------------------------------------------------------------------- 6. finale (one-shot)
def music_finale():
    tr = Track("music_finale", 96, 16, loop=False, tail=4.5, seed=606, rt60=2.8)
    tr.bus("pad", -10, 0.4)
    tr.bus("kanun", -12, 0.3, delay=(0.75 * tr.beat, 0.25, 3, 3200))
    tr.bus("mar", -9, 0.3)
    tr.bus("str", -11, 0.45)
    tr.bus("brass", -13, 0.35)
    tr.bus("lead", -7, 0.35)
    tr.bus("bass", -12, 0.05)
    tr.bus("perc", -11, 0.15)
    tr.bus("bell", -16, 0.6)
    C = {"Dmaj9": (38, [50, 57, 61, 64, 66]), "Bm9": (35, [47, 54, 57, 61, 62]), "Gmaj9": (43, [47, 54, 57, 59, 62]),
         "Asus4": (45, [50, 52, 57, 62]), "A": (45, [49, 52, 57, 61]), "G": (43, [50, 55, 59, 62]),
         "Bm": (35, [50, 54, 59, 62]), "A/C#": (37, [52, 57, 61, 64]), "Bsus4": (47, [52, 54, 59, 64]),
         "B7": (47, [51, 54, 57, 63]), "E": (40, [52, 56, 59, 64, 68]), "B/D#": (39, [54, 59, 63, 66]),
         "C#m7": (37, [52, 56, 59, 61, 64]), "Aadd9": (45, [52, 57, 59, 61, 64]), "E/G#": (44, [52, 56, 59, 64, 68]),
         "B": (47, [51, 54, 59, 63])}
    tl = [(0, 1, "Dmaj9"), (1, 1, "Bm9"), (2, 1, "Gmaj9"), (3, .5, "Asus4"), (3.5, .5, "A"),
          (4, 1, "G"), (5, 1, "A"), (6, 1, "Bm"), (7, .5, "A/C#"), (7.5, .25, "Bsus4"), (7.75, .25, "B7"),
          (8, 1, "E"), (9, 1, "B/D#"), (10, 1, "C#m7"), (11, 1, "Aadd9"), (12, 1, "E/G#"), (13, .5, "Bsus4"),
          (13.5, .5, "B"), (14, 1, "Aadd9"), (15, 1, "E")]
    for bar, L, ch in tl:
        b, pad = C[ch]
        amp = 0.6 if bar < 4 else (0.8 if bar < 8 else 1.0)
        rel = 4.0 if bar >= 15 else 1.6
        tr.pad("pad", bar, L, pad, attack=0.8 if bar < 8 else 0.3, release=rel, bright=0.8 + 0.02 * bar, amp=amp)
        if bar >= 4:
            tr.bass("bass", bar, [(0, L * 4, b)], vel=0.75 if bar < 8 else 0.9)
        if 4 <= bar < 15:
            ups = [t + 12 for t in pad if 55 <= t + 12 <= 80][:4]
            amp_s = 0.45 + 0.05 * (bar - 4) if bar < 8 else 0.85
            tr.strings("str", bar, L * 4, ups, attack=0.5 if bar < 8 else 0.2, release=0.9, bright=0.9, amp=amp_s,
                       beat=0)
    tr.strings("str", 15, 4, [64, 68, 71, 76], attack=0.4, release=4.0, bright=0.7, amp=0.55)
    # section 1: soft kanun arps + marimba motif
    for bar in range(4):
        ch = [c for (b0, L, c) in tl if b0 <= bar + 0.01 < b0 + L][0]
        tr.arp("kanun", bar, arp_tones(C[ch][1], 62, 86), [0, 2, 4, 3, 5, 4, 6, 4], step=0.5, vel=0.45, pan=0.3)
    for i, ph in enumerate(["D5:q E5:q F#5:q A5:q", "B5:q A5:q F#5:q E5:q", "D5:q E5:q F#5:q B5:q", "E5:h C#5:h"]):
        tr.notes("mar", i, mel(ph), kind="marimba", vel=0.7, pan=-0.2)
    # section 2: build - rising kanun 16ths, frame drum crescendo
    for bar in range(4, 8):
        ch = [c for (b0, L, c) in tl if b0 <= bar + 0.01 < b0 + L][0]
        tr.arp("kanun", bar, arp_tones(C[ch][1], 62, 88), [0, 1, 2, 3, 4, 5, 6, 7], step=0.25 if bar >= 6 else 0.5,
               vel=0.4 + 0.05 * (bar - 4), pan=0.3)
        kit = {"D": (lambda r, v: ss.doum(r, v, f1=74), 0.7), "d": (lambda r, v: ss.doum(r, v, f1=74), 0.4),
               "T": (lambda r, v: ss.tek(r, v), 0.5)}
        tr.drums("perc", bar, "D.d.T.d.D.d.T.d." if bar >= 6 else "D...T...D...T...", kit, vel=0.5 + 0.1 * (bar - 4))
    tr.put("perc", ss.roll(tr.rng, dur=2 * tr.beat, vel=0.8, f1=70, rate=16), tr.s(7, 2), gain_db=-2)
    tr.put("perc", ss.cymbal_swell(tr.rng, dur=4 * tr.beat, vel=1.0), tr.s(7), pan=0.0, jitter=0)
    tr.notes("brass", 7, mel("A4:h B4:q B4:q"), kind="brass", vel=0.6)
    # section 3: takeoff uplift in E major
    lead = ["E5:q F#5:q G#5:q B5:q", "B5:h A5:q G#5:q", "G#5:h F#5:q E5:q", "F#5:w", "G#5:q B5:q E6:h",
            "E6:h D#6:h", "C#6:h B5:h", "G#5:w"]
    for i, ph in enumerate(lead):
        seq = mel(ph)
        tr.notes("lead", 8 + i, seq, kind="strings", vel=0.9 if i < 6 else 0.6)
        tr.notes("lead", 8 + i, seq, kind="fm", vel=0.55 if i < 6 else 0.35, gain_db=-8)
        if i < 6:
            tr.notes("brass", 8 + i, [(b, d, m - 12) for b, d, m in seq], kind="brass", vel=0.7)
    for bar in (8, 12):
        tr.put("perc", ss.timpani(40, tr.rng, vel=1.0), tr.s(bar), jitter=0)
    tr.put("perc", ss.timpani(47, tr.rng, vel=0.8), tr.s(13, 2), jitter=0)
    kit = {"D": (lambda r, v: ss.doum(r, v, f1=78), 0.85), "d": (lambda r, v: ss.doum(r, v, f1=78), 0.5),
           "T": (lambda r, v: ss.tek(r, v), 0.7), "t": (lambda r, v: ss.tek(r, v), 0.35),
           "s": (lambda r, v: ss.shaker(r, v), 0.4)}
    for bar in range(8, 14):
        tr.drums("perc", bar, "D.tdT.t.D.tdT.tt", kit, vel=0.8)
        tr.drums("perc", bar, "s.s.s.s.s.s.s.s.", kit, pan=-0.3, gain_db=-4)
        ch = [c for (b0, L, c) in tl if b0 <= bar + 0.01 < b0 + L][0]
        tr.arp("kanun", bar, arp_tones(C[ch][1], 64, 90), [0, 2, 4, 6, 5, 3, 4, 2], step=0.5, vel=0.45, pan=0.35)
    # section 4: gentle resolve
    tr.arp("kanun", 15, arp_tones(C["E"][1], 64, 92), [0, 2, 4, 5, 7, 9, None, None], step=0.5, vel=0.4, pan=0.3)
    tr.notes("bell", 15, [(0, 4, 88), (1.5, 4, 92), (3, 4, 95)], kind="glass", vel=0.6)
    tr.notes("bell", 8, [(0, 4, 88)], kind="glass", vel=0.8)
    return tr


# --------------------------------------------------------------------------- 7-9. stingers
def stinger_success():
    tr = Track("stinger_success", 120, 1, loop=False, tail=2.4, seed=707, rt60=2.0)
    tr.bus("kanun", -7, 0.3)
    tr.bus("pad", -11, 0.4)
    tr.bus("bell", -9, 0.5)
    tr.bus("perc", -14, 0.15)
    for i, m in enumerate([62, 66, 69, 74, 78, 81]):
        tr.notes("kanun", 0, [(i * 0.18, 0.5, m)], vel=0.55 + 0.05 * i, pan=-0.2 + 0.08 * i)
    tr.pad("pad", 1.1 / 4, 0.45, [50, 57, 62, 64, 66, 69], attack=0.15, release=1.8, bright=1.0)   # arrives on beat 1.1
    tr.notes("bell", 0, [(1.1, 4, 86), (1.1, 4, 93)], kind="fm", vel=0.7)
    tr.put("perc", ss.doum(tr.rng, 0.8, f1=74), tr.s(0, 1.1), jitter=0)
    return tr


def stinger_fail():
    tr = Track("stinger_fail", 90, 1, loop=False, tail=0.9, seed=808, rt60=1.8)
    tr.bus("mar", -6, 0.3)
    tr.bus("pad", -11, 0.4)
    tr.bus("kanun", -9, 0.3)
    tr.notes("mar", 0, [(0, 1, 69), (0.45, 1, 66)], kind="marimba", vel=0.7)
    tr.pad("pad", 0.2, 0.5, [55, 59, 62, 67], attack=0.25, release=0.6, bright=0.7)
    tr.pad("pad", 0.6, 0.45, [54, 57, 62, 66], attack=0.35, release=1.2, bright=0.7)
    tr.notes("kanun", 0, [(2.4, 1, 74), (2.7, 1, 76), (3.0, 1, 78)], vel=0.5, pan=0.25)
    return tr


def stinger_episode():
    tr = Track("stinger_episode", 96, 2, loop=False, tail=1.4, seed=909, rt60=2.6)
    tr.bus("pad", -9, 0.4)
    tr.bus("str", -10, 0.45)
    tr.bus("lead", -6, 0.35)
    tr.bus("kanun", -10, 0.3)
    tr.bus("perc", -9, 0.15)
    tr.bus("bell", -12, 0.55)
    tr.put("perc", ss.roll(tr.rng, dur=1.4 * tr.beat, vel=0.75, f1=72, rate=16), tr.s(0, 0.0), jitter=0)
    tr.put("perc", ss.cymbal_swell(tr.rng, dur=1.6 * tr.beat, vel=0.9), tr.s(0, 0.0), jitter=0)
    for start, L, pad in [(1.6, 1.6, [55, 59, 62, 67]), (3.2, 1.6, [57, 61, 64, 69]), (4.8, 3.2, [50, 57, 62, 66, 69])]:
        tr.pad("pad", start / 4, L / 4, pad, attack=0.12, release=2.0 if start > 4 else 0.6, bright=0.9)
        tr.strings("str", 0, L, [p + 12 for p in pad[:3]], attack=0.2, release=1.6 if start > 4 else 0.5, beat=start)
    tr.put("perc", ss.timpani(38, tr.rng, vel=0.9), tr.s(0, 1.6), jitter=0)
    tr.put("perc", ss.timpani(45, tr.rng, vel=0.8), tr.s(0, 3.2), jitter=0)
    tr.put("perc", ss.timpani(38, tr.rng, vel=1.0), tr.s(0, 4.8), jitter=0)
    tr.notes("lead", 0, mel("D5:e E5:e F#5:e A5:e G#5:q. F#5:e", start=1.6), kind="fm", vel=0.75)
    tr.notes("lead", 0, mel("A5:q D6:h.", start=5.6), kind="strings", vel=0.8)
    tr.arp("kanun", 1.2, arp_tones([50, 57, 62, 66], 62, 90), [0, 1, 2, 3, 4, 5, 6, 7], step=0.25, vel=0.45,
           pan=0.3, beats=2.0)
    tr.notes("bell", 1, [(0.8, 4, 86), (1.2, 4, 90), (1.6, 4, 93)], kind="glass", vel=0.6)
    return tr


PIECES = {
    "music_menu_loop": (music_menu_loop, "calm wonder, D lydian, 72 BPM"),
    "music_architect_loop": (music_architect_loop, "curious puzzle, B dorian, 90 BPM"),
    "music_street_loop": (music_street_loop, "warm adventure, G major, 100 BPM"),
    "music_drive_loop": (music_drive_loop, "upbeat drive, A major, 112 BPM"),
    "music_storm_loop": (music_storm_loop, "tension layer, D minor, 90 BPM"),
    "music_finale": (music_finale, "takeoff finale, D major -> E major, 96 BPM"),
    "stinger_success": (stinger_success, "success stinger, D major"),
    "stinger_fail": (stinger_fail, "gentle retry stinger, IV-I in D"),
    "stinger_episode": (stinger_episode, "episode complete, IV-V-I in D"),
}


def main():
    ids = sys.argv[1:] or list(PIECES)
    OUT.mkdir(parents=True, exist_ok=True)
    rep = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
    for pid in ids:
        fn, desc = PIECES[pid]
        tr = fn()
        mix, levels = tr.render(ir_seed=zlib.crc32(pid.encode()) % 1000)
        y = master(tr, mix)
        if pid == "stinger_success":
            y = y[: int(4.4 * SR)]
            y = sa.fade(y, 0.001, 0.6)
        sa.write_wav(OUT / f"{pid}.wav", y, seed=zlib.crc32(pid.encode()))
        x, _, _, _ = sa.read_wav(OUT / f"{pid}.wav")
        d = sa.describe(x)
        info = {"desc": desc, "bpm": tr.bpm, "bars": tr.bars, "loop": tr.loop, "duration_s": round(d["dur"], 3),
                "lufs": round(d["lufs"], 2), "tp_dbtp": round(d["tp"], 2), "bus_rms_db": levels}
        if tr.loop:
            info["bar_s"] = round(tr.bar, 6)
            info["seam"] = sa.seam_report(x)
        rep[pid] = info
        seam = f" seam {'OK' if info.get('seam', {}).get('ok') else 'CHECK'}" if tr.loop else ""
        print(f"  {pid:22s} {d['dur']:6.2f}s  {d['lufs']:6.2f} LUFS  {d['tp']:6.2f} dBTP{seam}  buses {levels}",
              file=sys.stderr)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rep, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
