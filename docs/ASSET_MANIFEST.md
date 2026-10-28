# SKYFOLD: The Clean Flight — Asset manifest

By **Awaiz Ahmed and Huda Mueen / Team Kanban** (ADIPEC 2026 edition). Everything shipped in the build is listed here with its source, licence and AI status. Per-file tables (every model, every sound) live in the detailed manifests:

- `docs/manifest/art_env.md`: 67 environment models (city kit, roads, bridges, Atelier, props, nature, sky, and the energy set: wind turbines, solar farm and carport, grid batteries, green-hydrogen works, carbon-capture unit, EV charger).
- `docs/manifest/art_chars.md`: 12 character and vehicle models (NURI, gloves, cars, hydrogen-electric aircraft, hydrogen fuel cell, passengers).
- `docs/manifest/audio.md`: 125 audio files (Noor voice lines, SFX, music, ambience), with licence verification notes.

Verification status wording: **Verified** means the licence text was read from the source files on this machine. **Stated by source** means the source documents the licence but no licence file came with the local copy.

## Summary by category

| Category | What | Source / provider | Licence | Verification | AI status |
| --- | --- | --- | --- | --- | --- |
| 3D models (79 files) | City kit, roads, bridge, Atelier, props, palms, sky, energy set (wind turbines, solar, grid batteries, green hydrogen, carbon capture, EV charger), NURI, gloves, courier car, convoy shuttle, city cars, hydrogen-electric aircraft, hydrogen fuel cell, passengers | Original procedural Blender 5.2 Python scripts in `tools/blender/` (written in an AI-assisted coding session) | Original work for SKYFOLD | Verified (built from repo scripts) | Not AI-generated: geometry comes only from the scripts. No external models, scans or generative 3D. |
| Materials and shaders | `SKY_*` palette materials; Skyfold Stylized Lit, Water, Sky, Unlit and Fade shaders | Written for this project (`Assets/Skyfold/Shaders`, `Scripts/Editor/Art/MaterialLibrary.cs`) | Original work | Verified | Not AI-generated output. Code was written in an AI-assisted session. |
| Voice (52 lines, Noor) | Narration and tutorial lines | Kokoro-82M TTS (hexgrad), stock voice `af_heart`, run locally (the ADIPEC lines through `tools/audio/voiceover_local.py`) | Model: Apache-2.0; output owned by the project | Verified (package metadata) | **AI-generated speech** (local TTS). Stock voice, no voice cloning, no imitation of a real person. |
| Sound effects | UI, car, cell, switches, aircraft, storm, NURI chirps | Original DSP synthesis (`tools/audio/*.py`) layered with processed Kenney.nl recordings (impact, interface and casino packs) | Original + **CC0 1.0** (Kenney) | Synthesis: verified. Kenney: **stated by source** (the kanban-motion skill documents them as public-domain Kenney.nl sounds, and Kenney publishes its packs under CC0; no licence file was bundled with the local copy) | Not AI-generated |
| Music and ambience | Menu, architect, street, drive, storm and finale music plus three stingers; coast, city, Atelier and storm ambience loops | Original composition and synthesis (`tools/audio/make_music.py`, `tools/audio/make_ambience.py`) | Original work | Verified | Not AI-generated (deterministic DSP) |
| Fonts | Unbounded (headings, SemiBold instance), Atkinson Hyperlegible Regular and Bold (body) | google/fonts GitHub repository (`ofl/unbounded`, `ofl/atkinsonhyperlegible`) | SIL Open Font License 1.1 | Verified (OFL.txt downloaded with each font; copies in `Assets/Skyfold/Fonts` and the release `licenses` folder) | Not AI-generated. The Unbounded SemiBold static instance was cut locally from the variable font with fontTools (allowed by the OFL; no Reserved Font Name). |
| Fallback font | LiberationSans SDF (TextMesh Pro Essential Resources) | Unity TextMesh Pro package | LiberationSans: SIL OFL 1.1 (licence file included); TMP resources: Unity Companion License | Verified | Not AI-generated |
| App icons | SKYFOLD emblem plus laptop / VR headset / demo badges (`.png`, `.ico`) | Drawn procedurally with Pillow by `tools/icons/make_icons.py` | Original work | Verified | Not AI-generated |
| UI sprites | Rounded panels, circles, check / cross, arrow, Noor's radio glyph (now only a fallback, shown if the portrait badge is missing) | Generated at runtime in code (`UIKit.cs`) | Original work | Verified | Not AI-generated |
| Noor's subtitle badge | 256 px circular portrait shown beside Noor's subtitles (`Assets/Skyfold/Art/Images/noor_badge.png`) | ChatGPT image generation (OpenAI), then cropped, scaled and masked into a circle by `tools/images/make_image_derivatives.py`. Details below. | Output of the team's ChatGPT account. OpenAI's terms of use assign rights in output to the user. | Stated by source (OpenAI terms of use; not re-read for this build) | **AI-generated (ChatGPT image generation)** |
| Screenshots (`docs\screenshots`) | Ten frames of the menus, Atelier, city, car, takeoff and results. `key_art.jpg` in the same folder is not a screenshot (see Images from ChatGPT). | Captured by the release build during automated QA, then resized and saved as JPG by `tools\qa\curate_screenshots.py`. No other editing. | Original work | Verified | Not AI-generated (real game frames) |
| XR rig | XR Interaction Toolkit 3.6.0 *Starter Assets* sample (XR Origin, interactors, tunneling vignette, controller models hidden behind the courier gloves) | Unity Technologies | Unity Companion License | Verified (package licence) | Not AI-generated |
| Engine and packages | Unity 6000.6.2f1 player, URP 17.6, Input System 1.20, XR Management 4.7, OpenXR 1.18, XRI 3.6, uGUI / TextMesh Pro 2.6 | Unity Technologies | Unity Terms of Service / Unity Companion License | Verified (Package Manager) | Not AI-generated |

## Images from ChatGPT

- **Date:** all made on 2026-10-17, in one ChatGPT chat ("Create Key Art").
- **Account:** the team's ChatGPT workspace account, signed in by Awaiz Ahmed. The address is left out because this repository is public.
- **How:** the chat ran in a separate Chrome window opened by the chrome-devtools tool, and Awaiz signed in there directly.
- **Files:** each PNG is byte-for-byte what ChatGPT returned and still carries OpenAI's C2PA content-credentials chunk.
- **Prompt rules:** every prompt forbade text, real people's likenesses and imitation of named artists.
- **AI status of every file in this section:** AI-generated (ChatGPT image generation).

| File | What | Where it is used | In the game build |
| --- | --- | --- | --- |
| `Assets/Skyfold/Art/Images/key_art.png` (1672×941) | Key art: the miniature city on its plinth above the bay, a small plane taking off from the island airfield, a storm front on the horizon | README header, as `docs/screenshots/key_art.jpg` (resized to 1600×900 by `tools/images/make_image_derivatives.py`). It is key art, not an in-game screenshot. | No |
| `Assets/Skyfold/Art/Images/noor_portrait.png` (1254×1254, transparent) | Noor, head and shoulders, with a radio headset | Source for the subtitle badge | No (only the badge below) |
| `Assets/Skyfold/Art/Images/noor_badge.png` (256×256) | Circular crop of that portrait on a pearl disc with a TealLight ring | Beside Noor's subtitles (`HUDController.noorPortrait`, assigned in `SceneBuilder.Systems.cs`). Made by `tools/images/make_image_derivatives.py`, which only crops, scales and masks the generated pixels. | **Yes** |
| `Assets/Skyfold/Art/Images/nuri_reference_sheet.png` (1536×1024) | NURI, front and side views, with one glowing teal lens eye | Art reference for the NURI model | No |

Prompts, exactly as sent:

**key_art.png**

> Create an image. Widescreen 16:9 key art for an original video game (do not draw any title, text, letters, logos or watermark). Style: warm coastal futurism with a premium stylized miniature-city look: smooth clay-like forms, clean bevelled shapes, soft golden-hour light, gentle tilt-shift depth of field. Scene: a hand-sized miniature coastal city, with pearl and sandstone buildings, a few deep-teal domes, tiny roads, a harbour and a causeway bridge to a small island airfield, sits on a pearl-white stone plinth on a sunlit stone terrace high above a wide real bay. On the miniature island airfield a small propeller plane is just lifting off the runway. Far out on the horizon a dark storm front with towering clouds is rolling in over the sea, contrasting with the warm foreground. No people. Palette: pearl #F4EFE6, sandstone #D9B98C, deep teal #0F6F73, coral #F2714B accents, gold #D9A441 highlights, ink #22333B shadows.

**noor_portrait.png** (source of `noor_badge.png`)

> Create an image. Character portrait for the same original game: Noor, an invented city engineer who guides the player over the radio. Head-and-shoulders bust, facing the viewer at a slight three-quarter angle, warm friendly smile, dark hair tied back, wearing a compact radio headset with a small boom microphone and a deep-teal work jacket with a coral collar stripe and a small plain gold badge (no lettering). Illustrated stylized look, not photographic: simple bold shapes, clean outlines, soft cel shading, large clear facial features and high contrast so the face still reads when shrunk to 96 pixels inside a circular badge. Centred in a square frame, head and shoulders filling about 80% of it, transparent background (PNG with alpha), no backdrop, no frame, no shadow. Noor is a made-up character: she must not resemble any real person or celebrity, and do not imitate any named artist's style. No text. Palette: pearl #F4EFE6, sandstone #D9B98C, deep teal #0F6F73, coral #F2714B, gold #D9A441, ink #22333B.

**nuri_reference_sheet.png** (two messages; only the edited result is kept)

> Create an image. Landscape 3:2 character reference sheet for the same game's companion: NURI, a small mechanical falcon. Show exactly two views of the same design side by side at the same scale on a plain flat pearl #F4EFE6 background: on the left a front view, on the right a side profile view, both perched upright with wings folded. Design: sleek stylized falcon with a smooth pearl-ivory shell, sandstone #D9B98C underside panels, deep-teal #0F6F73 wing and tail feathers made of overlapping plates, thin gold #D9A441 trim along the wing edges, small coral #F2714B status lights, ink #22333B joints and talons, a short hooked beak, and one large round glowing teal lens eye in the centre of its face. Premium stylized toy-like 3D render, soft studio lighting, clean shapes, matching warm coastal futurism. No text, no labels, no arrows, no measurements, no grid, no watermark.

The first result gave NURI two eyes, unlike the single lens of the in-game model, so this edit followed:

> Edit the NURI reference sheet you just made: replace the two eyes with one single large round glowing teal lens eye in the centre of the face, directly above the beak, like a camera lens with a thin gold bezel, in both views (in the side view the lens sits at the front of the head, seen from the side). Keep everything else the same: same falcon design, colours, poses, layout and plain pearl background. No text.

## Tools used only to build (not shipped)

Blender 5.2 (GPL; models and previews), Python 3 with numpy / scipy / Pillow / fontTools, FFmpeg 8.1 (decoding Kenney `.ogg` sources), phonemizer / espeak-ng (GPL-3.0, Kokoro text-to-phoneme), faster-whisper with Systran small.en (MIT; transcription QA of the voice lines). None of their code or data is in the build.

## Characters and likeness

Noor (radio guide) and NURI (mechanical falcon) are fictional characters created for this game. They do not represent the creator or any real person. Noor's portrait was generated from a prompt that describes an invented character and forbids any resemblance to a real person or celebrity and any imitation of a named artist's style. No celebrity imitation, no voice cloning and no real person's likeness are used anywhere.
