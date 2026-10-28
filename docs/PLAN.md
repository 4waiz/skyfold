# SKYFOLD: The Clean Flight — Plan

**Mode: HOBBY, ADIPEC 2026 edition.** Creator credit: Awaiz Ahmed and Huda Mueen / Team Kanban. Single-player, nonviolent puzzle-adventure for Windows x64, playable on the laptop (desktop mode) and in PC VR on Meta Quest 3 through Link. One executable, two Desktop shortcuts.

## 0. ADIPEC 2026 edition

- **Showcase, not a jam entry.** Shown at ADIPEC 2026 under the theme *accelerating decarbonisation, energy security, resilience and industrial innovation across the global energy value chain*. The SHIFT boundary below still stands: this edition is a showcase build, not a jam submission.
- **Audience:** high school students and recent graduates. Text is short and plain; each results screen adds one simple, real energy fact.
- **Story reframe (same systems, same world):** the storm has cut Nacre Bay's clean power link. The causeway carries the island's power cable (*The Green Corridor*), the courier delivers a green-hydrogen fuel cell to restart the airfield microgrid (*The Hydrogen Run*), and the last flight becomes the city's first zero-emission, hydrogen-electric flight (*The Clean Flight*).
- **Clean-grid meter:** `GridImpact` works out the renewable share (30% base, +30 corridor, +20 microgrid, +10 solar runway, +10 clean flight) from `CityState` facts only, never timers. Shown on the laptop HUD, the VR wrist panel and the results screen; a toast (also on the VR hint card) marks each new source. The percentages are game values, not real measurements.
- **Energy set** (`tools/blender/env_energy.py`, group `energy`): onshore and offshore wind turbines (separate `Rotor`, spun by `WindTurbine`), solar farm, solar carport, grid-battery yard, green-hydrogen works, direct-air carbon-capture unit, EV charger. Street lamps gain a solar head; the aircraft becomes hydrogen-electric (no exhausts); the power cell becomes a hydrogen fuel cell.
- **Both play modes:** every new element works in desktop and VR. Menus and results use the shared panel builder; the HUD meter has a desktop card and a wrist-panel line.

## 1. Event boundary (SHIFT Game Jam)

- KBYG PDF: 17–18 Oct 2026, Abu Dhabi University. Theme reveal 09:00 GST on 17 Oct; submission by 15:30 GST on 18 Oct. The game must be created after the theme reveal. Free or licensed pre-made assets, code and libraries are allowed. AI-generated content must be listed.
- This project started 17 Oct 00:45 GST, before the reveal, so it is **not an eligible SHIFT entry**. It must not be relabelled, reskinned or submitted as one.
- JAM_PREP (if requested): generic tools, packages, hardware checks and reusable documented resources only. JAM_ENTRY (if requested): get the revealed theme and confirmed rules first, then start a new project during the permitted period.
- **Conflict recorded, not resolved.** The PDF weights judging gameplay 30 / theme 20 / creativity 15 / art+audio 15 / technical 10 / presentation 10. The brief reports that the live FAQ describes five equally weighted categories. Build format is "[To confirm]" in the PDF. The brief reports that itch.io accepts Windows builds and prefers WebGL. **You need to confirm the rubric, build requirements and demo slot with the organisers.** PC VR is not being sacrificed for WebXR.

## 2. The game in one line

Hold a broken city in your hands, rebuild the green corridor that carries its clean power, step inside the world you changed, and send the city's first zero-emission flight into the sky before the storm.

## 3. World: Nacre Bay (fictional)

- One compact authored district on a 12 x 9 grid of 16 m cells (192 m x 144 m). Rows 0–3 are the mainland Old Town, row 4 is a sea channel, and rows 5–8 are the island airfield (the runway is row 8).
- **The Fold Atelier**: a pearl-white terrace on a headland above the bay, holding a waist-height plinth. The **miniature** sits on the plinth at 1:160 (one cell is 10 cm), oriented to match the real city below, so you can look past the plinth and see the real causeway.
- **Fold Stations**: kiosks in the street (Depot, Airfield). Folding at one takes you to the Atelier. Unfolding returns you to the station you came from, after a short fade to a validated anchor. The camera never zooms.
- One authoritative `CityState` drives three things: the full-scale city at 1:1 meters with real colliders the car drives on, the miniature (a lightweight proxy that mirrors entities by stable ID), and the UI.

## 4. Puzzle rules

- Fixed sockets on the road graph and a limited module inventory: Straight, Corner, Tee and Bridge (over water only). Each module has openings (N/E/S/W) and four rotations.
- A placement is **accepted** when the module suits the terrain, every opening faces a road, a placed module or an open socket (never a building or open water), and at least one opening touches existing road.
- A rejected placement gives a short visual cue (coral flash plus a ✗ icon, not colour alone) and a plain-language reason ("That end points into a building — turn it a quarter."). The piece goes back to the hand or tray, never consumed.
- Connectivity is re-evaluated by a BFS only when a placement changes, never per frame.
- **Choice in Episode 1**: the west crossing needs only the bridge (a long drive). The east crossing also needs the harbour corner, correctly turned (a short drive, and it earns the *Shortcut* medal). There is one bridge, so you build one route.

## 5. Episodes (same world, same systems)

| Episode | Goal | Key mechanics |
| --- | --- | --- |
| 1 · The Green Corridor | Rebuild the causeway (road plus the island's power cable) to connect the Depot to the island | Tutorial grab/rotate/snap, route choice, fold, unlock the courier car |
| 2 · The Hydrogen Run | Carry a green-hydrogen fuel cell into the car and deliver it to the airfield microgrid | Physical carry, arcade car, checkpoints, comfort *Remote Drive* from a fixed overlook; afterwards a convoy follows the repaired route |
| 3 · The Clean Flight | Repair the terminal access link, switch on three solar runway beacons, let the electric shuttles arrive, clear the hydrogen-electric plane for take-off | Fold from the Airfield station, switches, aircraft state machine and takeoff payoff |
| Demo (3 min) | Bridge → fold → cell + car → beacons → takeoff | Shorter route, generous hints, real input, no auto-win, separate progress |

Target is 10–15 min for a first full playthrough. The storm timer is the failure state. It starts only after the tutorial steps complete, and it pauses in menus, settings, tutorials, on tracking loss and on headset removal.

## 6. Mission state machine

`Boot → Menu → Briefing → Tutorial → Active ⇄ Checkpoint → Success → Results`, with `Active → Failed → Retry` (the retry restores the last checkpoint snapshot).

- **Start conditions**: the episode is unlocked (or it's Demo). `CityState` is reset to the episode's initial layout plus the carried-over campaign state.
- **Completion conditions**: evaluated from `CityState` facts (route exists, cell delivered, beacons lit, convoy arrived, departure cleared). They are never set directly by timers.
- **Failure conditions**: the storm timer reaches zero. Nothing else fails the run. A lost cell or a car in the water just respawns at the last checkpoint.
- **Medals**: computed from recorded time left, pieces used, route length and hints used. Nothing is hard-coded.

## 7. Architecture (Assets/Skyfold/Scripts)

`GameBootstrap` (args, settings, managers) · `LaunchOptions` (`--mode=desktop|vr`, `--demo`, `--windowed`, `--diagnostics`, `--qa=`) · `XRBootstrap` (manual XR Management lifecycle, readiness checks, retry/fallback) · `PlayerRigs` (exactly one active rig; anchor moves with fade) · `InputRouter` (one context map active: Menu / OnFoot / Architect / Driving / Paused) · `CityLayout` + `CityState` + `RouteValidator` · `TileSocket` / `ModulePiece` / `FullScaleSlot` / `MiniatureMirror` · `FoldStation` + `FoldController` · `MissionDirector` + `MissionDefinition` · `TutorialDirector` (shared step IDs for predicate, caption, VO clip, highlight, hint, skip) · `CourierVehicle` · `PowerCell` · `ConvoyDirector` · `AircraftSequence` · `NuriCompanion` · `StormDirector` · `AudioDirector` (mixer, ducking, pooling) · `SettingsStore` (versioned JSON; campaign and demo saved separately) · `SpectatorDirector` (mirror view plus laptop-only overlay).

Scenes, prefabs, materials, input assets, XR settings and build settings are generated or validated by editor code (`Skyfold/Editor`) run in batch mode. `tools/build.ps1` runs the whole pipeline.

## 8. Controls (shipped bindings; full list in `docs/CONTROLS.md`)

- **VR, on foot / architect**: left stick moves (Smooth comfort mode). Right stick X turns (snap by default). Grip grabs, trigger is UI / contextual. Hold **A** to aim a teleport and release to confirm. **B** is back. **X** folds at a station, **Y** toggles the wrist objectives, the **left menu** button pauses.
- **VR, car**: left stick X steers, right trigger is throttle, left trigger brakes then reverses. **B** exits when stopped. Teleport, grab and fold are disabled while driving.
- **Desktop**: WASD and mouse look, E interact, mouse drag for pieces, R rotate, Q fold, Tab objectives, Esc pause. In the car: WASD drive, Space brake, E exit.

## 9. Launch and XR

- One `SKYFOLD.exe`. XR is **not** initialised at startup (`InitManagerOnStart = false`). **Enter VR** calls `InitializeLoader → check activeLoader and XRDisplaySubsystem running → StartSubsystems`, then activates the XR rig and disables the desktop rig. If it fails, it shows Retry / Desktop plus the log path, never a black screen.
- Shortcuts: **SKYFOLD** (laptop badge, `--mode=desktop`) and **SKYFOLD - Quest 3** (headset badge, `--mode=vr`) on the Desktop, created by `tools\package.ps1`. The release folder also has portable launchers that keep working wherever the ZIP is extracted: `Play on this laptop.cmd`, `Play in VR (Quest 3 Link).cmd` and `Play Demo (3 min).cmd` (`--demo`).
- The spectator gets a mirrored eye view on the laptop, plus a screen-space overlay (objectives, subtitles, timer) that renders only to the laptop window.

## 10. Art and audio

- Palette: pearl `#F4EFE6`, sandstone `#D9B98C`, deep teal `#0F6F73`, coral `#F2714B`, reward gold `#D9A441`, shadow ink `#22333B`.
- 3D: original procedural Blender meshes (beveled architecture kit, roads/bridges, palms, courier car, aircraft, NURI with separable parts, gloves), all assigned shared palette materials. ChatGPT images (when Chrome is connected) serve as references, the Noor radio portrait and key art. All UI text is real TextMeshPro.
- Audio: Noor narration through Kokoro (local, from the `kanban-motion` skill). NURI chirps, ambience and SFX are synthesised or taken from the skill's CC0 Kenney library. Music beds come from `bed.py` and are made loopable. Everything goes through a mixer with dialogue ducking.

## 11. Checkpoints

1. Windows exe with menu, desktop controls and an XR test space (diagnostics).
2. Bridge interaction plus persistent fold between scales.
3. One full win/retry mission.
4. Car, cell, aircraft states, demo mode, spectator.
5. Art, images, narration, audio, UI polish.
6. Three episodes, profiling, QA, packaging (ZIP and shortcuts).

## 12. Known risks

- No headset was connected during development. Every physical-controller, comfort and Link-performance check stays **NOT TESTED** until you run the headset checklist.
- Hybrid-GPU laptop: Unity players export `NvOptimusEnablement`, so the RTX GPU should be chosen. The GPU name is logged at startup to verify it.
- Re-initialising OpenXR in the same process after a failed attempt is runtime-dependent. The fallback is restarting through the VR shortcut into the same save.
