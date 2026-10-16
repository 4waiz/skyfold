#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Write Assets/Skyfold/Audio/audio_index.json and docs/manifest/audio.md.

    python tools/audio/build_index.py        # run after qa_audio.py

Reads tools/audio/reports/qa.json (measured duration / loudness / peak per file),
vo_lines.json (captions, TTS text), reports/vo_build.json (voice, speed),
reports/sfx_sources.json (Kenney CC0 files used per SFX) and the music/ambience reports.

suggested_db = gain that puts the clip at its intended playback loudness when Noor's VO
plays at 0 dB (VO is mastered to -16 LUFS). Targets are role based (see TARGETS), rounded to
0.5 dB and clamped to [-40 dB, the gain that keeps the sample peak at or below -1 dBFS].
Short clips (< 0.4 s) use ungated whole-clip loudness.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skyaudio as sa  # noqa: E402

REPORTS = sa.TOOLS / "reports"
INDEX = sa.AUDIO / "audio_index.json"
MANIFEST = sa.ROOT / "docs" / "manifest" / "audio.md"
LINES_JSON = sa.ROOT / "Assets" / "Skyfold" / "Resources" / "Dialogue" / "vo_lines.json"
DATE = "2026-10-17"

# ---- intended playback loudness (LUFS) per clip, VO = -16 reference ----------------------------
TARGETS = {
    "music_menu_loop": -25, "music_architect_loop": -25, "music_street_loop": -25, "music_drive_loop": -25,
    "music_storm_loop": -28, "music_finale": -21, "stinger_success": -21, "stinger_fail": -23,
    "stinger_episode": -20,
    "amb_coast_loop": -30, "amb_city_loop": -32, "amb_atelier_loop": -31, "amb_storm_loop": -28,
    "ui_hover": -33, "ui_click": -28, "ui_back": -28, "ui_toggle": -28, "ui_slider_tick": -34,
    "checkpoint": -23, "objective_complete": -22, "hint_ping": -25, "warning_chime": -19, "route_complete": -20,
    "socket_snap": -22, "socket_reject": -23, "door_chime": -23, "respawn": -22, "teleport": -24,
    "piece_pickup": -25, "piece_drop": -24, "piece_rotate": -26, "bridge_assemble": -20, "fold_out": -21,
    "fold_in": -21, "cell_pickup": -24, "cell_insert": -21, "power_transfer": -20, "substation_on": -19,
    "switch_lever": -22, "beacon_on": -23, "car_enter": -22, "car_start": -21, "car_motor_loop": -25,
    "car_roll_loop": -27, "car_bump": -22, "car_horn": -20, "convoy_beep": -24, "splash": -19,
    "plane_idle_loop": -24, "plane_spoolup": -20, "plane_takeoff": -16, "plane_flyby": -18,
}
PREFIX_TARGETS = {"thunder_far_": -24, "footstep_stone_": -29, "nuri_concern_": -23, "nuri_celebrate_": -21,
                  "nuri_": -22}
SPATIAL_PREFIX = ("piece_", "socket_", "bridge_assemble", "cell_", "power_transfer", "substation_on", "switch_lever",
                  "beacon_on", "thunder_far_", "car_", "plane_", "convoy_beep", "splash", "footstep_stone_",
                  "door_chime", "nuri_")

SFX_USE = {
    "piece_pickup": "Architect: lifting a road/bridge piece from the tray or model",
    "piece_drop": "Architect: releasing a piece away from a socket (returns to tray/hand)",
    "piece_rotate": "Architect: quarter-turn of a held piece (R / wrist turn)",
    "socket_snap": "Architect: accepted placement in a glowing socket (click + teal chime)",
    "socket_reject": "Architect: rejected placement, friendly 'nope' with the coral cue",
    "bridge_assemble": "Full-scale bridge unfolds after the miniature bridge is placed",
    "route_complete": "Route connected (gold route light) in Episode 1 / Demo",
    "fold_out": "Fold Atelier -> street transition (unfold at a Fold Station)",
    "fold_in": "Street -> Fold Atelier transition (fold up at a Fold Station)",
    "cell_pickup": "Episode 2: picking up the power cell at the dock",
    "cell_insert": "Episode 2: cell latched into the car cradle / substation socket",
    "power_transfer": "Episode 2: substation charging from the delivered cell",
    "substation_on": "Episode 2: airfield substation powers up",
    "switch_lever": "Beacon switches and the departure lever in the tower",
    "beacon_on": "Episode 3 / Demo: a runway beacon lights",
    "warning_chime": "Storm timer warnings (two minutes / thirty seconds)",
    "checkpoint": "Checkpoint reached",
    "objective_complete": "Objective ticked off the list",
    "hint_ping": "Hint highlight (sockets glowing teal, next objective)",
    "ui_hover": "Menu / wrist-UI hover", "ui_click": "Menu / wrist-UI confirm", "ui_back": "Menu back / cancel",
    "ui_toggle": "Settings toggle", "ui_slider_tick": "Settings slider step",
    "car_enter": "Climbing into the courier car", "car_start": "Courier car electric start-up",
    "car_motor_loop": "Courier car motor while driving (pitch 0.6-1.8x by speed)",
    "car_roll_loop": "Courier car tyre/road noise while moving", "car_bump": "Car hits a kerb or barrier",
    "car_horn": "Courier car horn", "convoy_beep": "Passenger convoy vehicles (Episode 2/3)",
    "plane_idle_loop": "Aircraft twin turboprops idling at the terminal",
    "plane_spoolup": "Aircraft engines spooling up for departure",
    "plane_takeoff": "Aircraft takeoff roll and climb (finale)", "plane_flyby": "Aircraft passes overhead",
    "splash": "Car leaves the road into the water (then respawns)", "respawn": "Car / cell respawn at checkpoint",
    "teleport": "VR teleport arrival", "door_chime": "Terminal arrival bell when the convoy arrives",
}
NURI_USE = {"happy": "NURI reacts happily (success, greeting)", "curious": "NURI notices something / asks",
            "concern": "NURI worried (storm close, rejected piece)", "celebrate": "NURI celebrates (route, takeoff)",
            "point": "NURI points the way to the next objective"}
MUSIC_USE = {
    "music_menu_loop": "Main menu / title (calm wonder)", "music_architect_loop": "Fold Atelier puzzle mode (curious)",
    "music_street_loop": "On foot in Nacre Bay streets (warm adventure)",
    "music_drive_loop": "Driving the courier car (upbeat)",
    "music_storm_loop": "Storm pressure layer over gameplay music (or alone when the timer is low)",
    "music_finale": "Aircraft takeoff finale, Episode 3 / Demo ending (non-loop)",
    "stinger_success": "Puzzle / route success", "stinger_fail": "Storm reached the city: gentle retry",
    "stinger_episode": "Episode complete / results"}
AMB_USE = {"amb_coast_loop": "Harbour, causeway and airfield edge", "amb_city_loop": "Old Town streets (subtle)",
           "amb_atelier_loop": "Fold Atelier terrace on the headland", "amb_storm_loop": "Storm approach (late timer)"}
SFX_HOW = {
    "piece_pickup": "Kenney wood tick (+35% pitch) + rising sine blip + air swish",
    "piece_drop": "Kenney soft impact + wood tick + tiny click", "piece_rotate": "3 synthesized ratchet ticks + Kenney clicks + swish",
    "socket_snap": "Kenney metal click + synthesized latch + low body + glass-partial chime (A5/E6) with room",
    "socket_reject": "Kenney soft thunk + low sine + two soft square-ish notes E4 -> C4",
    "bridge_assemble": "Servo whir sweep, 12 accelerating ratchet ticks, Kenney plank clacks, soft thunk, D-major bell arpeggio",
    "route_complete": "FM 'golden' bells + harp plucks D5-F#5-A5-D6-F#6, pad swell, glass shimmer, reverb",
    "fold_out": "Descending filtered-noise whoosh + Kenney card slides (paper fold), soft landing",
    "fold_in": "Rising whoosh, reversed Kenney card slide, glass sparkle",
    "cell_pickup": "Rising sine bloop + Kenney glass tick + 120 Hz hum blip",
    "cell_insert": "Kenney metal latch + switch, harmonic hum rising 55 -> 110 Hz, ready ping",
    "power_transfer": "Hum rising 80 -> 240 Hz with tremolo, glass sparkle grains, closing chord ping",
    "substation_on": "Pitched-down sine thunk + Kenney heavy impacts, 100 Hz hum swell, 4 relay clicks",
    "switch_lever": "Kenney switch + heavy metal impact, low thump, spring ring",
    "beacon_on": "Soft bell ping D6 + FM tine + 220 Hz hum",
    "warning_chime": "Two-tone FM/tubular bell A5 -> F5", "checkpoint": "Two-note bell A5 -> D6 with harp layer",
    "objective_complete": "Three glass bells D6-F#6-A6 + FM tine", "hint_ping": "FM bell E6 with two echoes",
    "ui_hover": "2 kHz sine blip", "ui_click": "Kenney click + 1.1 kHz sine body", "ui_back": "Two descending sine blips",
    "ui_toggle": "Kenney switch (trimmed) + 1.5 kHz blip", "ui_slider_tick": "2.6 kHz / 1.3 kHz micro tick",
    "car_enter": "Handle tick, door swing whoosh, sine clunk + Kenney impacts, suspension creak",
    "car_start": "Relay tick, electric whine spin-up with overshoot, two-note ready chime",
    "car_motor_loop": "240 Hz harmonic whine + inverter tones + filtered noise, whole-cycle 2 s loop",
    "car_roll_loop": "Brown/pink road noise 60-1400 Hz + soft tyre hiss, 3 s circular loop",
    "car_bump": "Kenney soft impacts + tin rattle + sine thump", "car_horn": "Two-tone A4 + C#5 square-ish, low-passed",
    "convoy_beep": "Two short F4 + A4 beeps", "plane_idle_loop": "Twin prop blade-pass harmonics 62 / 62.75 Hz, turbine whine, chopped roar; 4 s whole-cycle loop",
    "plane_spoolup": "Turboprop model with rising blade-pass and whine", "plane_takeoff": "Full-power turboprop model, swell, Doppler drop and air-absorption filter",
    "plane_flyby": "Turboprop model with Doppler and distance filtering", "splash": "Noise impact, low thump, spray, 35 synthesized bubbles, slosh",
    "respawn": "Rising glass-bell shimmer + soft pad + whoosh", "teleport": "Rising whoosh + pitch-drop pop + sparkle",
    "door_chime": "Three-note tubular/FM bell F#5-A5-D6",
}


def target_for(cid):
    if cid in TARGETS:
        return TARGETS[cid]
    for p, v in PREFIX_TARGETS.items():
        if cid.startswith(p):
            return v
    return -22


def suggested(cid, lufs, cat, peak_dbfs):
    """Gain to the role target, never boosting a clip above -1 dBFS sample peak."""
    t = -16 if cat == "vo" else target_for(cid)
    v = round((t - lufs) * 2) / 2
    ceiling = max(0.0, -1.0 - peak_dbfs)
    return max(-40.0, min(ceiling, v))


def group_key(cid):
    for p in ("thunder_far_", "footstep_stone_", "nuri_happy_", "nuri_curious_", "nuri_concern_",
              "nuri_celebrate_", "nuri_point_"):
        if cid.startswith(p):
            return p
    return None


def main():
    qa = json.loads((REPORTS / "qa.json").read_text(encoding="utf-8"))
    lines = json.loads(LINES_JSON.read_text(encoding="utf-8"))["lines"]
    by_line = {L["id"]: L for L in lines}
    vob = json.loads((REPORTS / "vo_build.json").read_text(encoding="utf-8"))
    voqa = {r["id"]: r for r in json.loads((REPORTS / "vo_qa.json").read_text(encoding="utf-8"))["lines"]}
    sfx_src = json.loads((REPORTS / "sfx_sources.json").read_text(encoding="utf-8"))
    music = json.loads((REPORTS / "music.json").read_text(encoding="utf-8"))
    amb = json.loads((REPORTS / "ambience.json").read_text(encoding="utf-8"))
    files = {r["id"]: r for r in qa["files"]}
    cat_of = {"VO": "vo", "SFX": "sfx", "Music": "music", "Ambience": "ambience"}

    clips = []
    order = [L["id"] for L in lines] + sorted(r["id"] for r in qa["files"] if r["category"] != "VO")
    for cid in order:
        r = files[cid]
        cat = cat_of[r["category"]]
        c = {"id": cid, "file": r["file"], "category": cat, "loop": bool(r["loop"]), "duration_s": r["duration_s"],
             "lufs": r["lufs"], "peak_dbfs": r["peak_dbfs"], "suggested_db": suggested(cid, r["lufs"], cat, r["peak_dbfs"]),
             "spatial": cat == "sfx" and cid.startswith(SPATIAL_PREFIX)}
        if cat == "vo":
            c["caption"] = by_line[cid]["text"]
        clips.append(c)
    index = {
        "version": 1,
        "notes": "Generated by tools/audio/build_index.py. file is relative to Assets/Skyfold/Audio. lufs = ITU-R "
                 "BS.1770-4 integrated loudness (mono measured as one channel; clips < 0.4 s ungated). "
                 "suggested_db = gain that places the clip at its intended loudness relative to VO at 0 dB "
                 "(VO mastered to -16 LUFS). Loops are sample-accurate and seam-checked.",
        "clips": clips}
    INDEX.write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------ manifest
    voice, speed = vob["voice"], vob["speed"]
    vo_src = f"Kokoro-82M (Apache-2.0) via kanban-motion voiceover.py, voice {voice}, speed {speed}"
    vo_mod = "VO chain (see note)"
    where_prefix = {"e1": "Episode 1", "e2": "Episode 2", "e3": "Episode 3", "d": "Demo", "g": "Global (storm, retry, hints)",
                    "t": "Tutorial prompt"}
    md = [
        "# Audio manifest",
        "",
        f"All shipped audio for SKYFOLD: The Last Flight. Created {DATE} offline on the development laptop with "
        "local tools only (no online TTS, no paid services, no voice cloning, no imitation of real people). "
        "Regeneration commands: `tools/audio/README.md`. Measured values: `Assets/Skyfold/Audio/audio_index.json`.",
        "",
        "## Licence verification",
        "",
        "- **Kokoro-82M model (hexgrad)**: Apache License 2.0. Verified locally from package metadata in the uv cache: "
        "`kokoro_onnx-0.6.1.dist-info/METADATA` (\"kokoro model: Apache 2.0\") and `kokoro-0.9.4.dist-info` "
        "(LICENSE = Apache License 2.0; README: \"Apache-licensed weights\"). The cached Hugging Face snapshot "
        "`models--hexgrad--Kokoro-82M` holds only config.json, weights and voices (no model card file), so the "
        "licence was confirmed from the package metadata above. The ONNX export used "
        "(`~/.cache/kanban-motion/kokoro/kokoro-v1.0.onnx`, `voices-v1.0.bin`) is the kokoro-onnx v1.0 release of the same model.",
        "- **kokoro-onnx 0.6.1** (inference wrapper): MIT. **phonemizer 3.4.0 / espeak-ng** (G2P via espeakng-loader): "
        "GPL-3.0, used as build-time tools only; nothing from them is shipped. **faster-whisper 1.2.1** (MIT) with "
        "Systran small.en weights: QA transcription only, not shipped. **FFmpeg 8.1**: decodes Kenney .ogg files at build time only.",
        "- **Kenney.nl sound effects**: CC0 1.0 (public domain dedication). Taken from the kanban-motion skill library "
        "`assets/sfx/` (its `references/sound.md` describes them as \"public-domain sounds from Kenney.nl\"; the skill "
        "folder bundles no separate licence file). Kenney publishes these packs under CC0 1.0; attribution not required, given here anyway.",
        "- **Original synthesis** (tools/audio/*.py, numpy/scipy DSP): created for this project; no samples, no AI models.",
        "",
        "AI status: only the Noor voice lines are AI-generated (Kokoro TTS, a stock voice, no voice cloning). "
        "Every other file is deterministic DSP synthesis and/or processed CC0 recordings.",
        "",
        "## Voiceover (Noor) - Audio/VO/",
        "",
        f"Generated by `tools/audio/make_vo.py build --voice {voice} --speed {speed}`, which runs the kanban-motion "
        "skill's `scripts/voiceover.py` (kokoro-onnx 0.6.1, fp32 ONNX export of Kokoro-82M) once for all lines and "
        "splits the result at its exact line bounds. **VO chain**: 24 -> 48 kHz polyphase resample, 60 Hz high-pass, "
        "trim to ~40 ms lead / ~150 ms tail, 5 ms fades, loudness-normalised to -16 LUFS with a look-ahead true-peak "
        "limiter (<= -1.5 dBTP; it only catches sub-millisecond plosive spikes), mono 16-bit with TPDF dither. "
        "Voice chosen by objective audition (reports/vo_audition.json); every line transcribed with faster-whisper "
        "small.en for WER and letter-name checks (reports/vo_qa.json). The 'Script' column is the exact TTS input "
        "(`spoken` if present, else the caption).",
        "",
        "| File | Source / provider | Licence | Created | Modifications | AI status | Script (TTS text) | Where used |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for L in lines:
        cid = L["id"]
        pre = cid.split(".")[0]
        q = voqa.get(cid, {})
        md.append(f"| VO/{cid}.wav | {vo_src} | Apache-2.0 model; output project-owned | {DATE} | {vo_mod} | "
                  f"AI-generated speech (Kokoro TTS), no voice cloning | \"{L.get('spoken') or L['text']}\" | "
                  f"{where_prefix.get(pre, pre)} ({L.get('mode')} mode); QA WER {q.get('wer', 0) * 100:.0f}% |")
    md += ["", "## Sound effects - Audio/SFX/", "",
           "| File | Source / provider | Licence | Created | Modifications | AI status | Script | Where used |",
           "|---|---|---|---|---|---|---|---|"]
    done = set()
    for cid in sorted(sfx_src):
        g = group_key(cid)
        if g and g in done:
            continue
        members = sorted(k for k in sfx_src if g and k.startswith(g)) if g else [cid]
        name = f"SFX/{g}01..{len(members):02d}.wav" if g else f"SFX/{cid}.wav"
        if g:
            done.add(g)
        kenney = sorted({f for k in members for f in sfx_src[k]["kenney"]})
        if kenney:
            src = ("Original synthesis tools/audio/synth_sfx.py + Kenney.nl CC0 via kanban-motion assets/sfx/"
                   + ", assets/sfx/".join(kenney) + ", processed")
            lic = "CC0 1.0 (Kenney source) + original"
        else:
            src = "Original synthesis tools/audio/synth_sfx.py"
            lic = "Original (project-owned)"
        if g == "footstep_stone_":
            how = "Kenney concrete footsteps: pitch 0.94-1.03x, 70 Hz HPF, +2 dB @ 200 Hz, -2 dB @ 3.5 kHz, 6.5 kHz LPF, trimmed"
            use = "Footsteps on stone paving (rotate 01-04)"
        elif g == "thunder_far_":
            how = "Brown-noise rumble bursts, softened crackle, long tail, 3 kHz LPF"
            use = "Distant thunder during the storm"
        elif g and g.startswith("nuri_"):
            mood = g[5:-1]
            how = ("FM/sine sweeps and trills (fundamental 1.6-4 kHz), small 2.76x metallic glint, 900 Hz HPF, 9 kHz LPF; "
                   f"{sum(sfx_src[k].get('energy_1k5_5k', 0) for k in members) / len(members) * 100:.0f}% energy in 1.5-5 kHz")
            use = NURI_USE[mood]
        else:
            how = SFX_HOW.get(cid, "")
            use = SFX_USE.get(cid, "")
        loop_note = " Seamless loop." if any(sfx_src[k]["loop"] for k in members) else ""
        ai = "Not AI-generated (processed CC0 recordings + DSP)" if kenney else "Not AI-generated (procedural DSP)"
        md.append(f"| {name} | {src} | {lic} | {DATE} | {how}; mono 48 kHz 16-bit, peak -3 dBFS, DC-blocked, faded.{loop_note} "
                  f"| {ai} | synth_sfx.py `{members[0] if not g else g + '*'}` | {use} |")
    md += ["", "## Music - Audio/Music/", "",
           "| File | Source / provider | Licence | Created | Modifications | AI status | Script | Where used |",
           "|---|---|---|---|---|---|---|---|"]
    for cid in ["music_menu_loop", "music_architect_loop", "music_street_loop", "music_drive_loop", "music_storm_loop",
                "music_finale", "stinger_success", "stinger_fail", "stinger_episode"]:
        m = music[cid]
        form = (f"{m['bars']} bars at {m['bpm']} BPM, seamless bar-aligned loop" if m["loop"]
                else f"one-shot, {m['duration_s']:.1f} s")
        md.append(f"| Music/{cid}.wav | Original composition and synthesis, tools/audio/make_music.py (wavetable pads/strings/brass, "
                  f"additive kanun/oud/marimba/bells, synthesized frame drums, synthetic hall reverb) | Original (project-owned) | {DATE} "
                  f"| {m['desc']}; {form}; stereo 48 kHz 16-bit, -20 LUFS, <= -1.5 dBTP | Not AI-generated (procedural DSP) "
                  f"| make_music.py `{cid}` | {MUSIC_USE[cid]} |")
    md += ["", "## Ambience - Audio/Ambience/", "",
           "| File | Source / provider | Licence | Created | Modifications | AI status | Script | Where used |",
           "|---|---|---|---|---|---|---|---|"]
    for cid in ["amb_coast_loop", "amb_city_loop", "amb_atelier_loop", "amb_storm_loop"]:
        a = amb[cid]
        md.append(f"| Ambience/{cid}.wav | Original synthesis, tools/audio/make_ambience.py (filtered/modulated noise, "
                  f"wrapped events, circular reverb) | Original (project-owned) | {DATE} | {a['desc']}; {a['duration_s']:.0f} s "
                  f"seamless loop; stereo 48 kHz 16-bit, -24 LUFS, <= -1.5 dBTP | Not AI-generated (procedural DSP) "
                  f"| make_ambience.py `{cid}` | {AMB_USE[cid]} |")
    md += ["", "## Data files", "",
           "| File | Source | Notes |", "|---|---|---|",
           "| Audio/audio_index.json | tools/audio/build_index.py | Per-clip duration, loudness, peak, loop, spatial and suggested mixer level; VO captions |",
           "| Resources/Dialogue/vo_lines.json | project | Only `spoken` respellings were edited for TTS (Noor -> Nuur; letter A \"ay\" -> \"eh\"; Checkpoint -> \"Check point.\"); captions unchanged |",
           ""]
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {INDEX} ({len(clips)} clips) and {MANIFEST}")


if __name__ == "__main__":
    main()
