# SKYFOLD: The Last Flight — QA and performance report

Every claim below comes from a run on this machine. Anything that was not actually exercised is marked **NOT TESTED**.

## Build and machine

| | |
| --- | --- |
| Build | SKYFOLD 0.9.0, release player (Mono, D3D11, URP 17.6 Forward+, MSAA 4×, Linear colour), `Builds\Release\SKYFOLD\SKYFOLD.exe` |
| Engine | Unity 6000.6.2f1; OpenXR 1.18 (XR initialised manually, never at startup); XR Interaction Toolkit 3.6 |
| Machine | NVIDIA GeForce RTX 5080 Laptop GPU (16 GB), Intel Core Ultra 9 275HX (24 threads), 32 GB RAM, Windows 11 (10.0.26200), 2560×1600 @ 240 Hz panel |
| Headset | **None connected during development.** No Quest 3 test of any kind has been run. |
| Date | 2026-10-17 |

## How it was tested

The game has built-in QA scenarios, started with `SKYFOLD.exe --qa=<scenario>` (runner: `tools\qa\run_qa.ps1`). Each one runs the real release build at 1920×1080 windowed, writes screenshots and a `qa_report.txt` to `qa\_captures\<scenario>\`, and exits with 0 (all checks passed) or 1. QA runs use their own save folder, so they never touch your progress.

What the bots do:
- **Keys:** real keyboard events go through the Input System (Esc, Tab, Q, E, R, W, A, S, D, Space).
- **Interactions:** the same entry points the mouse, E key and controllers call (grab, rotate and release a piece; pick up the cell; press a switch).
- **Driving:** a pure-pursuit bot follows the right-hand lane, slows for corners and for vehicles ahead, backs up if stuck, and parks.
- **Walking:** replaced by a teleport to where a player would walk. Walking itself is covered by the controls, not by these runs.

What they cannot do: judge fun, feel or readability, listen to audio, or test anything in a headset. A human playthrough is still needed. So is the headset checklist in `docs\QUEST_LINK_SETUP.md`.

## Automated scenarios (final build)

| Scenario | What it covers | Result |
| --- | --- | --- |
| `smoke` | Launch to title, start Episode 1 in the Atelier, Esc pauses and resumes | PASSED 5/5 |
| `menus` | Every menu screen opens, and Esc backs out to the title; settings survive save + reload; launcher shows | _final run pending_ |
| `episode1east` | Wrong rotation rejected and piece returned; straight into the water rejected; harbour corner + bridge make the east shortcut; Q folds down; walk; enter the car; hold R puts the car back on the road; drive to the island; success, results screen, Gold medal, shortcut recorded | PASSED 25/25 (previous build; hold-R check added in final run) |
| `episode1` | West route: one bridge, the long drive across the west causeway, success | PASSED 19/19 |
| `demo` | 3-minute demo end to end: bridge, fold, cell into the cradle, drive, E exits, deliver, beacons, lever, taxi, takeoff, results; demo never writes campaign progress | PASSED 20/20 |
| `fullcampaign` | Episodes 1 → 2 → 3 back to back with saved progress. Episode 2: carry, drive, deliver, convoy departs. Episode 3: fold at the airfield kiosk, tee rejected at the terminal link, straight accepted, fold back, three beacon switches, convoy arrives over the player's roads, boarding, lever, takeoff | PASSED 64/64 (Gold in all three: 354 s / 284 s / 254 s storm time left) |
| `fail` | Storm runs out → failure screen → Retry from checkpoint restores play with at least 75 s | PASSED 5/5 |
| `restarts` | 10 start / restart / quit-to-menu cycles: city listeners stable, one GameRoot, exactly one audio listener | PASSED 30/30 |
| `campaign` | Episode 1 unlocks Episode 2 and saves the built route | PASSED 27/27 |
| `perf` | Frame timing across the whole demo (below) | PASSED 12/12 |
| `soak` | Demo loops for 15 minutes; heap and frame rate per loop | _final run pending_ |

## Feature checklist

### Laptop (desktop mode)

| Area | Status | Evidence |
| --- | --- | --- |
| Launch: shortcut `--mode=desktop` | _pending launch test_ | |
| Launch: `--demo` | _pending launch test_ | |
| Launch: plain exe shows the laptop / VR choice | PASSED (menus run) | `qa\_captures\menus\menu_launcher.png` |
| Title, episode select, pause, resume, quit to menu | PASSED | smoke, restarts |
| Architect: grab, rotate, snap, reject with a reason, piece returned | PASSED | episode1east, fullcampaign |
| Fold up / down at stations and the plinth | PASSED | all episode runs |
| Courier car: enter, drive, brake, park, exit with E, cell cradle | PASSED | demo, fullcampaign |
| Car reset (hold R) | _final run pending_ | |
| Traffic gives way to the courier car | PASSED (no rear-end bumps after the fix; bot never stuck) | episode1 telemetry |
| Storm timer, failure, retry from checkpoint | PASSED | fail |
| Medals computed from the run (time left, rejections, hints, route) | PASSED | results screenshots: Gold (east), Silver (west) |
| Campaign progress and unlocks; demo progress kept separate | PASSED | campaign, fullcampaign, demo |
| Subtitles visible with speaker badge | PASSED (screenshots) | e1_04_street.png |
| Audio actually audible and mixed well | **NOT TESTED** (nobody listened). The audio library loads 125 clips (validator). | |
| Mouse look feel, sensitivity, invert Y | **NOT TESTED** by a person | |

### Meta Quest 3 through Link (VR mode)

| Area | Status |
| --- | --- |
| VR start with a headset (OpenXR loader, display, rig switch) | **NOT TESTED** (no headset) |
| VR start failure handling without a headset (message, Retry, Play on this laptop) | _pending launch test_ |
| Controller bindings (stick move, snap turn, A teleport, grip, trigger, X fold, Y wrist, B back, Menu pause) | **NOT TESTED** |
| Courier glove alignment on the controllers | **NOT TESTED** (offset chosen from the OpenXR grip-pose convention) |
| Driving in VR (cockpit and Remote overlook), comfort vignette | **NOT TESTED** |
| Recenter, height calibration, seated mode, headset-off pause | **NOT TESTED** |
| Spectator view on the laptop while in VR | **NOT TESTED** |
| VR performance through Link | **NOT TESTED** |

## Performance (laptop, measured)

`perf` scenario on the final build: 1920×1080 windowed, vsync off (uncapped), quality "PC", MSAA 4×.

| Moment | Average | 1% low | Worst frame |
| --- | --- | --- | --- |
| Title screen | 866 fps (1.16 ms) | 473 fps (2.11 ms) | 3.7 ms |
| Atelier with the miniature city | 698 fps (1.43 ms) | 449 fps (2.23 ms) | 3.2 ms |
| Street: avenue | 725 fps (1.38 ms) | 435 fps (2.30 ms) | 4.3 ms |
| Street: airfield | 871 fps (1.15 ms) | 471 fps (2.13 ms) | 3.5 ms |
| Driving across the bridge | 868 fps (1.15 ms) | 478 fps (2.09 ms) | 6.5 ms |
| Takeoff roll and climb | 934 fps (1.07 ms) | 520 fps (1.92 ms) | 2.4 ms |
| Results screen | 941 fps (1.06 ms) | 541 fps (1.85 ms) | 9.4 ms |

Managed heap after a full demo: 5 MB. In normal play vsync is on, so the laptop runs at the display refresh rate.

VR through Link renders two eyes at a much higher resolution (Quest 3 default about 2064×2208 per eye). These desktop numbers suggest plenty of headroom, but that is an estimate. **VR frame timing is NOT TESTED.**

## Known issues and limitations

- **No headset testing.** Everything in the VR table needs the checklist run on a real Quest 3.
- **Bot coverage, not human coverage.** Walking is teleported in the scenarios, and nobody has judged the feel.
- **ChatGPT images not made.** Claude in Chrome was not connected, so there is no key art, portrait or reference image. Noor's badge uses a drawn radio glyph.
- **Episode 1's storm timer mostly waits.** With Full tutorial guidance, Episode 1's teaching steps hold the timer, so its medal mostly reflects the route and placements. This is intentional.
- **Build warnings.** 4 warnings, all deprecation notices from Unity/TextMesh Pro package shaders; 0 errors.
