# SKYFOLD: The Last Flight — QA and performance report

Every result below comes from a run on this machine. Anything that was not actually exercised is marked **NOT TESTED**.

## Build and machine

| | |
| --- | --- |
| Build | SKYFOLD 0.9.0 release player: Mono, D3D11, URP 17.6 Forward+, MSAA 4×, Linear colour. 178 MB, 0 build errors, 4 build warnings (all Unity / TextMesh Pro package shader deprecation notices). |
| Package | `Release\SKYFOLD_v0.9.0_win64.zip` (about 72 MB), unpacked copy in `Release\SKYFOLD\` |
| Engine | Unity 6000.6.2f1; OpenXR 1.18 (XR started only on request, never at launch); XR Interaction Toolkit 3.6 |
| Machine | NVIDIA GeForce RTX 5080 Laptop GPU (16 GB), Intel Core Ultra 9 275HX (24 threads), 32 GB RAM, Windows 11 (10.0.26200), 2560×1600 @ 240 Hz panel at 150% scaling |
| Headset | **None connected at any point.** No Quest 3 test of any kind has been run. |
| Date | 2026-10-17 |

## How it was tested

The game has built-in QA scenarios, started with `SKYFOLD.exe --qa=<scenario>` (runner: `tools\qa\run_qa.ps1`). Each one runs the real release build at 1920×1080 windowed, writes screenshots and a `qa_report.txt` to `qa\_captures\<scenario>\`, and exits with 0 only if every check passed. QA runs use a separate, fresh save folder each time, so they never touch your progress.

What the bots do:
- **Keys and mouse:** real Input System events for Esc, Tab, Q, E, R, W, A, S, D, Shift, Space, F5 and mouse movement.
- **Interactions:** the same entry points the mouse, E key and controllers call (grab, rotate and release a piece; pick up the cell; press switches).
- **Driving:** a pure-pursuit bot follows the right-hand lane, slows for corners and for vehicles ahead, backs up if stuck (counted as a failure), and parks.
- **Walking:** the `walk` scenario walks with real keys; the long episode runs teleport to where a player would walk.

What they cannot do: judge fun, feel or readability, listen to the audio, or test anything in a headset. A human playthrough is still worth doing, and the headset checklist in `docs\QUEST_LINK_SETUP.md` is required.

## Automated scenarios on the final build

| Scenario | What it covers | Result |
| --- | --- | --- |
| `smoke` | Launch to title, start Episode 1 in the Atelier, Esc pauses and resumes | PASSED 5/5 |
| `menus` | Episodes, controls, comfort, audio, display and credits screens open, and Esc backs out; settings survive save + reload; launcher shows | PASSED 14/14 |
| `walk` | W walks 5.4 m in 1.5 s, Shift walks 2.6 m, mouse turns the view 26°, E picks up the cell, F5 restarts the demo in the Atelier | PASSED 9/9 |
| `demo` | The 3-minute demo end to end: bridge, fold, cell into the cradle, drive, E climbs out, deliver, beacons, lever, taxi, takeoff, results; the demo never writes campaign progress | PASSED 20/20 |
| `episode1` | West route: one bridge, the long drive over the west causeway, success, Silver medal (344 s left, 1 hint) | PASSED 19/19 |
| `episode1east` | Wrong rotation rejected and piece returned; straight piece into the water rejected; harbour corner + bridge make the east shortcut; Q folds down; enter the car; hold R puts the car back on the road; drive; success, results screen, Gold medal, shortcut recorded | PASSED 26/26 |
| `fullcampaign` | Episodes 1 → 2 → 3 back to back with real saved progress. Episode 2: carry, drive, deliver, convoy departs. Episode 3: fold at the airfield kiosk, tee rejected at the terminal link, straight accepted, fold back, three beacon switches, convoy arrives over the player's roads, boarding, lever, takeoff | PASSED 65/65; Gold in all three (350 s / 284 s / 254 s storm time left) |
| `fail` | Storm runs out → failure screen → Retry from checkpoint restores play with at least 75 s | PASSED 5/5 |
| `restarts` | 10 start / restart / quit-to-menu cycles: city listeners stable, one GameRoot, exactly one audio listener | PASSED 30/30 |
| `perf` | Frame timing across a whole demo (table below) | PASSED 12/12 |
| `tour` | Screenshot tour of the city for the docs | PASSED 1/1 |
| `lookdev` | Re-creates the Episode 1 street frame and checks what is drawn in the sky (used to find the floating overlook disc) | PASSED 5/5 |
| `soak` | 15 minutes of back-to-back demos | see "Soak" below |

The older `campaign` scenario (Episode 1 unlocks Episode 2 and saves the route) passed 27/27 on an earlier build. `fullcampaign` now covers the same checks.

## Launch tests through the real shortcuts

Run with `tools\qa\launch_test.ps1` on the packaged folder `Release\SKYFOLD\`, fullscreen at 2560×1600. Each test captures only the game window and reads the log.

| Test | Result |
| --- | --- |
| Desktop shortcut **SKYFOLD** (`--mode=desktop`): starts on the RTX GPU in desktop mode and shows the title menu | PASSED (`qa\_captures\launch\shortcut_desktop.png`) |
| Desktop shortcut **SKYFOLD - Quest 3** (`--mode=vr`) with no headset: tries OpenXR, then shows "VR did not start", the reason, a checklist, the log path, **Retry** and **Play on this laptop**. No black screen | PASSED (`shortcut_vr_no_headset.png`) |
| `Play Demo (3 min).cmd` (`--demo`): asks laptop or VR, then starts the demo | PASSED: the launcher appears with the demo queued (`launcher_demo.png`); the demo start itself is shown in the next row |
| `SKYFOLD.exe --mode=desktop --demo`: goes straight into the demo | PASSED ("Mission begin: demo" in the log) |
| Shortcut properties (target, arguments, laptop / headset icons, working folder) | PASSED (read back from both .lnk files) |
| F5 operator reset sent from outside the game | Not usable: Unity reads raw keyboard input, so a posted key message is ignored. F5 is covered by the `walk` scenario instead (real Input System key, PASSED). |

## Feature checklist

### Laptop (desktop mode)

| Area | Status | Evidence |
| --- | --- | --- |
| Launcher, title, episode select, pause, resume, quit to menu | PASSED | smoke, menus, restarts |
| On-foot controls with real input (WASD, Shift, mouse look, E) | PASSED | walk |
| Architect: grab, rotate, snap, rejection with a plain reason, piece returned | PASSED | episode1east, fullcampaign |
| Fold up / down at kiosks and the plinth | PASSED | all episode runs |
| Courier car: enter, drive, brake, park, climb out with E, cell cradle | PASSED | demo, fullcampaign |
| Car reset (hold R) | PASSED | episode1east |
| Traffic gives way to the courier car | PASSED (no rear-end bumps and no stuck events after the fix) | episode1 drive telemetry |
| Aircraft states: boarding, lever, taxi, roll, climb, departed; laptop takeoff camera | PASSED | demo, fullcampaign (`e3_05_takeoff.png`) |
| Storm timer, failure, retry from checkpoint | PASSED | fail |
| Medals computed from the run (time left, rejections, hints, route) | PASSED | Gold (east), Silver (west) |
| Campaign progress and unlocks; demo progress kept separate; F5 operator reset | PASSED | fullcampaign, demo, walk |
| Subtitles with speaker badge; key hints | PASSED (screenshots) | `docs\screenshots\` |
| Audio actually audible and mixed well | **NOT TESTED** (nobody listened; the validator confirms 125 clips load) | |
| Feel of mouse sensitivity and driving handling for a human | **NOT TESTED** | |

### Meta Quest 3 through Link (VR mode)

| Area | Status |
| --- | --- |
| VR start with a headset (OpenXR loader, display, rig switch) | **NOT TESTED** (no headset) |
| VR start failure without a headset | PASSED (clear message, Retry and Play on this laptop; see launch tests) |
| Controller bindings (stick move, snap turn, A teleport, grip, trigger, X fold, Y wrist, B back, Menu pause) | **NOT TESTED** |
| Courier glove alignment on the controllers | **NOT TESTED** (offset set from the OpenXR grip-pose convention) |
| Driving in VR (cockpit and Remote overlook), comfort vignette | **NOT TESTED** |
| Recenter, height calibration, seated mode, headset-off pause | **NOT TESTED** |
| Spectator view on the laptop while in VR | **NOT TESTED** |
| VR performance through Link | **NOT TESTED** |

## Performance (laptop, measured)

`perf` scenario on the final build: 1920×1080 windowed, vsync off (uncapped), quality "PC", MSAA 4×.

| Moment | Average | 1% low | Worst frame |
| --- | --- | --- | --- |
| Title screen | 904 fps (1.11 ms) | 487 fps (2.06 ms) | 3.8 ms |
| Atelier with the miniature city | 765 fps (1.31 ms) | 396 fps (2.53 ms) | 4.6 ms |
| Street: avenue | 885 fps (1.13 ms) | 469 fps (2.13 ms) | 3.9 ms |
| Street: airfield | 945 fps (1.06 ms) | 554 fps (1.81 ms) | 3.5 ms |
| Driving across the bridge | 928 fps (1.08 ms) | 487 fps (2.05 ms) | 8.1 ms |
| Takeoff roll and climb | 892 fps (1.12 ms) | 516 fps (1.94 ms) | 5.3 ms |
| Results screen | 901 fps (1.11 ms) | 567 fps (1.76 ms) | 5.8 ms |

Managed heap after a full demo: 6 MB. In normal play vsync is on, so the laptop runs at the display refresh rate.

VR through Link renders two eyes at a much higher resolution (Quest 3 default is about 2064×2208 per eye). These numbers suggest plenty of headroom, but that is an estimate: **VR frame timing is NOT TESTED.**

## Soak

_Pending: filled in after the 15-minute run._

## Bugs found and fixed in this QA pass

- **Car would not move with the cell loaded.** The socketed cell collided with its own car. It now ignores the car's colliders while in the cradle.
- **Parked cars crept backwards.** Parked, entering and exiting cars now hold a parking brake.
- **Climbing out failed beside kerbs and bollards.** The exit check now finds the real ground first and tries six spots around the car.
- **Plane orbited a taxi waypoint forever.** It now slows for sharp turns, so the takeoff always happens.
- **Lamps, headlights and beacons lit nothing.** The stylized shader now uses URP's Forward+ cluster light loop.
- **Teal disc in the sky.** The VR Remote Drive platforms floated over the city at all times. They now appear only while in use.
- **Fold Atelier terrace floated with nothing under it.** The headland cliff was placed underwater; it now sits under the terrace.
- **Noor trailed behind the player.** Instructions for steps already done are dropped, and the results screen no longer waits for a backlog.
- **Episode 1 storm timer never ran.** The intro hold now ends once the welcome lines finish.
- **Traffic boxed in the courier car.** Traffic now pulls over for it.

## Known issues and limitations

- **No headset testing.** Everything in the VR table needs the checklist run on a real Quest 3.
- **Bot coverage, not human coverage.** The bots prove the flows work; they do not prove the game is fun or comfortable.
- **ChatGPT images not made.** Claude in Chrome was not connected, so there is no key art and no portrait. Noor's badge uses a drawn radio glyph.
- **Episode 1's storm timer mostly waits.** With Full tutorial guidance, most of Episode 1 holds the timer, so its medal mostly reflects the route and placements. This is intentional.
- **Build warnings.** 4 warnings, all deprecation notices from Unity / TextMesh Pro package shaders.
