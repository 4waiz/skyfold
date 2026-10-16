# SKYFOLD audio tools

Everything under `Assets/Skyfold/Audio/` is generated offline by the scripts in this folder.
No online TTS, no paid services, no voice cloning. All randomness is seeded, so a rerun
reproduces the same files (SFX were checked bit-identical between `python` and `uv run`).

## Requirements (already on the dev laptop)

- uv (`%USERPROFILE%\.local\bin\uv.exe`); each script carries PEP 723 metadata (numpy, scipy;
  `make_vo.py` also faster-whisper). Plain Python 3.12 with numpy + scipy + faster-whisper works too.
- FFmpeg on PATH (decodes the Kenney `.ogg` files).
- The `kanban-motion` skill at `%USERPROFILE%\.claude\skills\kanban-motion` (its `scripts/voiceover.py`
  and the Kenney CC0 library in `assets/sfx/`).
- Kokoro-82M model files cached at `%USERPROFILE%\.cache\kanban-motion\kokoro`
  (`kokoro-v1.0.onnx`, `voices-v1.0.bin`).
- faster-whisper `small.en` in the Hugging Face cache (VO QA only; run with `HF_HUB_OFFLINE=1` implied).

## Regenerate everything (run from `C:\UnityProjects\SKYFOLD`)

```powershell
# 1. Noor voiceover: optional voice audition, then build and QA every line in vo_lines.json
uv run --offline tools/audio/make_vo.py audition                              # ~1 min -> reports/vo_audition.json
uv run --offline tools/audio/make_vo.py build --voice af_heart --speed 0.8   # ~1 min -> Audio/VO/<id>.wav
uv run --offline tools/audio/make_vo.py qa                                    # ~1 min -> reports/vo_qa.json, vo_qa.md

# 2. Sound effects + NURI chirps                                              # ~15 s  -> Audio/SFX/
uv run --offline tools/audio/synth_sfx.py

# 3. Music (5 loops, finale, 3 stingers)                                       # ~5 min -> Audio/Music/
uv run --offline tools/audio/make_music.py

# 4. Ambience loops                                                           # ~1 min -> Audio/Ambience/
uv run --offline tools/audio/make_ambience.py

# 5. Technical QA, then index + manifest (always run both after any change)
uv run --offline tools/audio/qa_audio.py       # -> reports/qa.json, qa.md (exit summary printed)
uv run --offline tools/audio/build_index.py    # -> Assets/Skyfold/Audio/audio_index.json, docs/manifest/audio.md
```

`--offline` only stops uv from contacting PyPI; drop it on a machine whose uv cache lacks the packages.
`python tools/audio/<script>.py ...` is equivalent when numpy/scipy/faster-whisper are installed.

### Single items

```powershell
uv run --offline tools/audio/synth_sfx.py socket_snap nuri_happy_01
uv run --offline tools/audio/make_music.py music_menu_loop stinger_fail
uv run --offline tools/audio/make_ambience.py amb_coast_loop
uv run --offline tools/audio/make_vo.py build --voice af_heart --speed 0.8 --only t.grab.vr t.grab.desktop
uv run --offline tools/audio/make_vo.py qa --only t.grab.vr t.grab.desktop
```

A partial VO build is functionally identical to a full one (Kokoro is deterministic per line; only
the 16-bit intermediate scaling inside voiceover.py differs at LSB level before re-normalisation).

## Changing a voice line

1. Edit `Assets/Skyfold/Resources/Dialogue/vo_lines.json`. `text` is the caption (WER reference);
   put pronunciation fixes only in `spoken`.
2. Rebuild that line and run `make_vo.py qa`. A line fails QA if WER > 15 % or a control letter
   (A B X Y E Q R W S D) is not heard as a letter name.
3. Run `qa_audio.py` and `build_index.py`.

Respellings that are known to work with Kokoro's espeak phonemizer: letter A = `eh` (`ay` is read
as "I"), E = `ee`, X = `ex`, Q = `cue`, W = `double-you`, S = `ess`, D = `dee`, R = `R`;
Noor = `Nuur` (`Noor` is read as "nor"); Nacre = `Nay-ker`. Check phonemes with
`kokoro_onnx.tokenizer.Tokenizer().phonemize(text, lang="en-us")`.

## Files

| Script | Output | Notes |
|---|---|---|
| `skyaudio.py` | - | Shared DSP: WAV I/O (16-bit, TPDF dither), BS.1770-4 loudness (verified against FFmpeg ebur128), 4x true peak, look-ahead limiter, circular filters/reverb, seam report |
| `skysynth.py` | - | Original instruments: wavetable pad/strings/brass/drone, additive kanun/oud/harp/pizz plucks, marimba, bells, frame drums |
| `make_vo.py` | `Audio/VO/` | Kokoro via kanban-motion `voiceover.py`; 48 kHz mono, -16 LUFS, <= -1.5 dBTP, 40 ms lead / 150 ms tail |
| `synth_sfx.py` | `Audio/SFX/` | 60 files, mono 48 kHz, peak -3 dBFS; Kenney sources per id in `reports/sfx_sources.json` |
| `make_music.py` | `Audio/Music/` | Stereo 48 kHz, -20 LUFS, <= -1.5 dBTP; bus balance by loudness targets; loops wrap notes/reverb |
| `make_ambience.py` | `Audio/Ambience/` | Stereo 48 kHz, -24 LUFS, <= -1.5 dBTP, periodic by construction |
| `qa_audio.py` | `reports/qa.*` | Format, duration, peak, true peak, LUFS, DC, clipping, edges, loop seams (file rendered twice back-to-back) |
| `build_index.py` | index + manifest | `suggested_db` = gain to each clip's role loudness with VO at 0 dB, never above -1 dBFS peak |

`reports/` holds the evidence: `vo_audition.json`, `vo_build.json`, `vo_qa.json|md`, `sfx_sources.json`,
`music.json` (bus levels, bar length, seam metrics), `ambience.json`, `qa.json|md`.
