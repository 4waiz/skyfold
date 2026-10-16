# SKYFOLD: The Last Flight — Asset manifest

Hobby project by **Awaiz Ahmed / Team Kanban**. Everything shipped in the build is listed here with its source, licence and AI status. Per-file tables (every model, every sound) live in the detailed manifests:

- `docs/manifest/art_env.md`: 59 environment models (city kit, roads, bridges, Atelier, props, nature, sky).
- `docs/manifest/art_chars.md`: 12 character and vehicle models (NURI, gloves, cars, aircraft, power cell, passengers).
- `docs/manifest/audio.md`: 125 audio files (Noor voice lines, SFX, music, ambience), with licence verification notes.

Verification status wording: **Verified** means the licence text was read from the source files on this machine. **Stated by source** means the source documents the licence but no licence file came with the local copy.

## Summary by category

| Category | What | Source / provider | Licence | Verification | AI status |
| --- | --- | --- | --- | --- | --- |
| 3D models (71 files) | City kit, roads, bridge, Atelier, props, palms, sky, NURI, gloves, courier car, convoy shuttle, city cars, aircraft, power cell, passengers | Original procedural Blender 5.2 Python scripts in `tools/blender/` (written in an AI-assisted coding session) | Original work for SKYFOLD | Verified (built from repo scripts) | Not AI-generated: geometry comes only from the scripts. No external models, scans or generative 3D. |
| Materials and shaders | `SKY_*` palette materials; Skyfold Stylized Lit, Water, Sky, Unlit and Fade shaders | Written for this project (`Assets/Skyfold/Shaders`, `Scripts/Editor/Art/MaterialLibrary.cs`) | Original work | Verified | Not AI-generated output. Code was written in an AI-assisted session. |
| Voice (52 lines, Noor) | Narration and tutorial lines | Kokoro-82M TTS (hexgrad), stock voice `af_heart`, run locally through the kanban-motion skill | Model: Apache-2.0; output owned by the project | Verified (package metadata) | **AI-generated speech** (local TTS). Stock voice, no voice cloning, no imitation of a real person. |
| Sound effects | UI, car, cell, switches, aircraft, storm, NURI chirps | Original DSP synthesis (`tools/audio/*.py`) layered with processed Kenney.nl recordings (impact, interface and casino packs) | Original + **CC0 1.0** (Kenney) | Synthesis: verified. Kenney: **stated by source** (the kanban-motion skill documents them as public-domain Kenney.nl sounds, and Kenney publishes its packs under CC0; no licence file was bundled with the local copy) | Not AI-generated |
| Music and ambience | Menu, architect, street, drive, storm and finale music plus three stingers; coast, city, Atelier and storm ambience loops | Original composition and synthesis (`tools/audio/make_music.py`, `tools/audio/make_ambience.py`) | Original work | Verified | Not AI-generated (deterministic DSP) |
| Fonts | Unbounded (headings, SemiBold instance), Atkinson Hyperlegible Regular and Bold (body) | google/fonts GitHub repository (`ofl/unbounded`, `ofl/atkinsonhyperlegible`) | SIL Open Font License 1.1 | Verified (OFL.txt downloaded with each font; copies in `Assets/Skyfold/Fonts` and the release `licenses` folder) | Not AI-generated. The Unbounded SemiBold static instance was cut locally from the variable font with fontTools (allowed by the OFL; no Reserved Font Name). |
| Fallback font | LiberationSans SDF (TextMesh Pro Essential Resources) | Unity TextMesh Pro package | LiberationSans: SIL OFL 1.1 (licence file included); TMP resources: Unity Companion License | Verified | Not AI-generated |
| App icons | SKYFOLD emblem plus laptop / VR headset / demo badges (`.png`, `.ico`) | Drawn procedurally with Pillow by `tools/icons/make_icons.py` | Original work | Verified | Not AI-generated |
| UI sprites | Rounded panels, circles, check / cross, arrow, Noor's radio glyph | Generated at runtime in code (`UIKit.cs`) | Original work | Verified | Not AI-generated |
| XR rig | XR Interaction Toolkit 3.6.0 *Starter Assets* sample (XR Origin, interactors, tunneling vignette, controller models hidden behind the courier gloves) | Unity Technologies | Unity Companion License | Verified (package licence) | Not AI-generated |
| Engine and packages | Unity 6000.6.2f1 player, URP 17.6, Input System 1.20, XR Management 4.7, OpenXR 1.18, XRI 3.6, uGUI / TextMesh Pro 2.6 | Unity Technologies | Unity Terms of Service / Unity Companion License | Verified (Package Manager) | Not AI-generated |

## Images from ChatGPT (planned, not in this build)

The brief asked for ChatGPT images (key art, NURI and Noor references, a transparent Noor radio portrait, material references) made in your Chrome through the Claude in Chrome extension. **Not created.** Blocker: no Chrome browser was connected to Claude in Chrome during the build (the connected-browser list was empty). Nothing in the build comes from ChatGPT.

- Noor currently appears as a teal badge with an original broadcast glyph drawn in code. It is not a portrait and not a likeness of anyone.
- When images are made later, add each one here with its prompt, date, the account used, and "AI-generated (ChatGPT image generation)".

## Tools used only to build (not shipped)

Blender 5.2 (GPL; models and previews), Python 3 with numpy / scipy / Pillow / fontTools, FFmpeg 8.1 (decoding Kenney `.ogg` sources), phonemizer / espeak-ng (GPL-3.0, Kokoro text-to-phoneme), faster-whisper with Systran small.en (MIT; transcription QA of the voice lines). None of their code or data is in the build.

## Characters and likeness

Noor (radio guide) and NURI (mechanical falcon) are fictional characters created for this game. They do not represent the creator or any real person. No celebrity imitation, no voice cloning and no real person's likeness are used anywhere.
