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
| `episode1` | West route: one bridge, the long drive over the west causeway, success, Silver medal | PASSED 19/19 |
| `episode1east` | Wrong rotation rejected and piece returned; straight piece into the water rejected; harbour corner + bridge make the east shortcut; Q folds down; enter the car; hold R puts the car back on the road; drive; success, results screen, Gold medal, shortcut recorded | PASSED 26/26 |
| `fullcampaign` | Episodes 1 → 2 → 3 back to back with real saved progress. Episode 2: carry, drive, deliver, convoy departs. Episode 3: fold at the airfield kiosk, tee rejected at the terminal link, straight accepted, fold back, three beacon switches, convoy arrives over the player's roads, boarding, lever, takeoff | PASSED 65/65; Gold in all three (350 s / 284 s / 254 s storm time left) |
| `fail` | Storm runs out → failure screen → Retry from checkpoint restores play with at least 75 s | PASSED 5/5 |
| `restarts` | 10 start / restart / quit-to-menu cycles: city listeners stable, one GameRoot, exactly one audio listener | PASSED 30/30 |
| `perf` | Frame timing across a whole demo (table below) | PASSED 12/12 |
| `tour` | Screenshot tour of the city for the docs | PASSED 1/1 |
| `soak` | 15 minutes of back-to-back demos | see "Soak" below |

Earlier runs on the same code also passed `campaign` (Episode 1 unlocks Episode 2 and saves the route; 27/27).

## Launch tests through the real shortcuts

| Test | Result |
| --- | --- |
| Desktop shortcut **SKYFOLD** (`--mode=desktop`): game starts on the RTX GPU, desktop rig, title menu | see "Launch" below |
| Desktop shortcut **SKYFOLD - Quest 3** (`--mode=vr`) with no headset: clear message plus Retry / Play on this laptop, no black screen | see "Launch" below |
| `Play Demo (3 min).cmd` (`--demo`): demo starts straight away | see "Launch" below |
| Shortcut properties (target, arguments, laptop / headset icons, working folder) | PASSED (read back from both .lnk files) |

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
| VR start failure without a headset | see "Launch" below |
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
| Title screen | 787 fps (1.27 ms) | 451 fps (2.22 ms) | 5.3 ms |
| Atelier with the miniature city | 618 fps (1.62 ms) | 337 fps (2.97 ms) | 6.5 ms |
| Street: avenue | 782 fps (1.28 ms) | 380 fps (2.63 ms) | 4.8 ms |
| Street: airfield | 910 fps (1.10 ms) | 488 fps (2.05 ms) | 4.4 ms |
| Driving across the bridge | 869 fps (1.15 ms) | 419 fps (2.39 ms) | 6.4 ms |
| Takeoff roll and climb | 835 fps (1.20 ms) | 445 fps (2.25 ms) | 5.3 ms |
| Results screen | 839 fps (1.19 ms) | 491 fps (2.03 ms) | 6.9 ms |

Managed heap after a full demo: 6 MB. In normal play vsync is on, so the laptop runs at the display refresh rate.

VR through Link renders two eyes at a much higher resolution (Quest 3 default is about 2064×2208 per eye). These numbers suggest plenty of headroom, but that is an estimate: **VR frame timing is NOT TESTED.**

## Soak

_Pending: filled in after the 15-minute run._

## Launch

_Pending: filled in after the shortcut launch tests._

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
