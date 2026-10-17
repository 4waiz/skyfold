# SKYFOLD: The Last Flight — Environment

Inspected 2026-10-17 00:45 GST (Arabian Standard Time, UTC+4) on the target laptop.

## Hardware and OS

| Item | Observed |
| --- | --- |
| Machine | ASUSTeK ROG Strix G18 (G815LW) |
| OS | Windows 11 Home 10.0.26200, 64-bit |
| CPU | Intel Core Ultra 9 275HX, 24 cores / 24 threads |
| RAM | 31.4 GB |
| GPU (discrete) | **NVIDIA GeForce RTX 5080 Laptop GPU, 16,303 MiB**, driver 591.91 |
| GPU (integrated) | Intel Graphics (driver 32.0.101.8826) drives the internal 2560x1600 @ 240 Hz panel, so the laptop runs in hybrid (Optimus) mode |
| Other display adapter | Meta Virtual Monitor (installed by Meta Horizon Link) |
| Free disk | C: 157 GB free |

Correction: the earlier report of an RTX 4070 Laptop GPU with 8 GB VRAM does not match this machine. It has an RTX 5080 Laptop GPU with 16 GB.

## Unity

| Item | Observed |
| --- | --- |
| Unity Hub | 3.21.3 |
| Editor | **6000.6.2f1** (Unity 6.6), the only installed editor. Hub lists it on the **SUPPORTED** stream (recommended), not LTS. The LTS lines are 6000.3 and 6000.0. |
| Modules | Windows Standalone (Mono only, no IL2CPP), WebGL. No Android module, so a Quest APK would need it installed first. |
| License | Hub entitlement license (`C:\ProgramData\Unity\UnityEntitlementLicense.xml`, updated 2026-10-16) |

Decision: use the installed 6000.6.2f1 rather than download a second (LTS) editor of several GB. The brief allows this ("use the existing compatible stable Unity setup if practical"). The packages below are the versions bundled with this editor, so they resolve offline and match what Unity validated for 6.6.

### Pinned packages (`Packages/manifest.json`, lockfile committed)

| Package | Version | Why |
| --- | --- | --- |
| com.unity.render-pipelines.universal | 17.6.0 | URP (core package matching the editor) |
| com.unity.shadergraph | 17.6.0 | Needed by XRI Starter Assets materials |
| com.unity.inputsystem | 1.20.0 | Action-based input |
| com.unity.xr.management | 4.7.0 | Deferred, manual XR start |
| com.unity.xr.openxr | 1.18.0 | OpenXR loader; Oculus Touch and Meta Quest Touch Plus profiles |
| com.unity.xr.interaction.toolkit | 3.6.0 | XR rig, grab, teleport, turn, UI; Starter Assets sample |
| com.unity.ugui | 2.6.0 | uGUI and TextMeshPro (merged into ugui in Unity 6) |
| com.unity.test-framework | 1.8.0 | Edit Mode tests |
| com.unity.ide.visualstudio | 2.0.26 | VS Code / Visual Studio project generation |

Not installed on purpose: com.unity.xr.meta-openxr (AR Foundation features for Quest; not needed for PC Link), com.unity.xr.oculus (deprecated on this editor), SteamVR plugins.

## Tools

| Tool | Observed |
| --- | --- |
| Git | 2.54.0 with Git Credential Manager (system `credential.helper=manager`) |
| Remote | `origin` = https://github.com/4waiz/skyfold.git (empty at inspection) |
| IDE | VS Code; no Visual Studio (not required for Mono builds) |
| Blender | 5.2 (`C:\Program Files\Blender Foundation\Blender 5.2`), plus two running Blender MCP servers |
| FFmpeg | 8.1.1 full build (winget, Gyan) |
| Python | 3.12.10 with Pillow 11.3.0, numpy 2.4.6, scipy 1.18.0; `uv` in `~/.local/bin` |
| Node | 24.16.0 |
| .NET SDK | 8.0.425 |
| adb | `C:\Android\Sdk\platform-tools\adb.exe` |

## XR runtime and headset

| Item | Observed |
| --- | --- |
| Meta Link app | Meta Horizon installed at `C:\Program Files\Meta Horizon\` (driver 1.78), `OVRService` running |
| Active OpenXR runtime | `C:\Program Files\Meta Horizon\Support\oculus-runtime\oculus_openxr_64.json` (the only registered runtime) |
| SteamVR | Not installed (the Steam client is present but registers no OpenXR runtime) |
| Quest 3 | **Not connected** at inspection: no Quest USB device, `adb devices` empty, no Link session |

## Folders

| Item | Path |
| --- | --- |
| Desktop known folder | `C:\Users\awaiz\OneDrive\Desktop` (redirected by OneDrive; `OneDrive.exe` is running) |
| Unity project (non-synced) | `C:\UnityProjects\SKYFOLD` |
| Original session folder | `C:\Users\awaiz\OneDrive\Desktop\skyfold` (empty git clone of the same remote; not used for the project, to keep Unity's Library out of OneDrive) |

## Project scripts

| Script | What it does |
| --- | --- |
| `tools\build.ps1` | One command: configure the project, build the scene from code, validate, build the release player. `-QA smoke demo ...` adds QA runs, `-Package` adds packaging |
| `tools\qa\run_qa.ps1` | Runs QA scenarios against the built player (`smoke`, `menus`, `demo`, `episode1`, `episode1east`, `fullcampaign`, `campaign`, `fail`, `restarts`, `perf`, `tour`, `soak`, `lookdev`). Writes reports and screenshots to `qa\_captures\` |
| `tools\qa\launch_test.ps1` | Launches the game through a shortcut, captures only the game window, prints the log lines, closes the game |
| `tools\package.ps1` | Stages `Release\SKYFOLD\` (game, README, licences, docs, icons, launchers), writes `Release\SKYFOLD_v<version>_win64.zip`, creates the two Desktop shortcuts |
| `tools\autosync.ps1` | Commits and pushes to `origin` every 3 minutes (your request) |
| `tools\icons\make_icons.py` | Draws the app and shortcut icons |
| `tools\images\make_image_derivatives.py` | Crops the ChatGPT portrait into Noor's 256 px subtitle badge and resizes the key art for the README |
| `tools\blender\*.py`, `tools\audio\*.py` | Rebuild every model and sound from scripts |

## Agent tools and skills

| Tool / skill | Status |
| --- | --- |
| Claude in Chrome (your real Chrome) | **Not connected.** Still no connected browsers on 2026-10-17, even with the extension installed and signed in to the Awaiz profile; most likely it uses a different Claude account from this app's. |
| Built-in browser pane | Available, isolated; it has no ChatGPT sign-in, so I'm not relying on it for your ChatGPT session |
| chrome-devtools MCP | Opens its own Chrome window with a separate profile. Used, with your go-ahead, for the ChatGPT images on 2026-10-17; you signed in to ChatGPT there yourself (see `docs/ASSET_MANIFEST.md`) |
| Unity MCP | None found. Automation uses Unity batch mode plus C# editor scripts (`Assets/Skyfold/Editor`) |
| Blender MCP | Available; asset generation uses reproducible Blender CLI scripts in `tools/blender` |
| `kanban-motion` skill | Reused for audio: `scripts/voiceover.py` (Kokoro-82M local TTS; model already cached at `~/.cache/kanban-motion/kokoro`), `scripts/bed.py` (original music beds), `assets/sfx` (CC0 Kenney library), `scripts/mix.py` |
| `brag` / `brag-slim` | Launch-video skills; they use the same Kokoro voice path. Not used for gameplay audio. |
| `media-use` | Uses HeyGen (sign-in or billed API); not used |
| "draft-type" skill | No skill by that name exists. The narration workflow you meant is the voiceover part of `kanban-motion` |

## Jam boundary

Work started 2026-10-17 00:45 GST, before the SHIFT theme reveal at 09:00 GST the same day. The KBYG PDF requires a jam game to be created after the reveal. This project is therefore a **HOBBY** build and is **not an eligible SHIFT entry**. See `docs/PLAN.md`.
