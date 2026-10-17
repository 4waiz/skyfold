SKYFOLD: The Last Flight
========================
A hobby project by Awaiz Ahmed / Team Kanban. Version 0.9.0, Windows x64.
Not a SHIFT Game Jam entry: it was made before any jam theme reveal.

Hold a broken coastal city in your hands, repair its roads as a giant, step inside the world you
changed, and get the last flight away before the storm.


HOW TO START (no installation)
------------------------------
- "SKYFOLD" Desktop shortcut ............ play on this laptop (keyboard and mouse)
- "SKYFOLD - Quest 3" Desktop shortcut .. play in VR on Meta Quest 3 through Link
- In this folder:
    Play on this laptop.cmd
    Play in VR (Quest 3 Link).cmd
    Play Demo (3 min).cmd ............... asks laptop or VR, then starts the three-minute demo
                                          (its progress is kept apart from the campaign)
- Or run SKYFOLD.exe directly. It asks whether to play on the laptop or in VR.

Command-line options for SKYFOLD.exe:
  --mode=desktop | --mode=vr   start straight in that mode
  --demo                       open the three-minute demo
  --episode=1|2|3              jump to an episode you have already unlocked
  --windowed                   start in a window
  --diagnostics                show the input diagnostics panel (also F1)


WHAT YOU NEED
-------------
- Windows 10 or 11, 64-bit, with a DirectX 11 GPU. Tested on the creator's laptop with an
  NVIDIA GeForce RTX 5080 Laptop GPU.
- For VR: Meta Quest 3, the Meta Horizon Link app on the PC (set as the active OpenXR runtime),
  and a Link cable or Air Link. See docs\QUEST_LINK_SETUP.md.
  VR STATUS: the VR path was built and configured but NOT TESTED with a headset yet.


CONTROLS (full list: docs\CONTROLS.md)
--------------------------------------
Laptop  walk W A S D + mouse · use / pick up E · fold at a station Q · objectives Tab · pause Esc
        At the plinth: hold left mouse to drag a piece, R to turn it, release to set it down.
        In the car: W accelerate · S brake / reverse · A D steer · Space parking brake
                    E climb out · hold R to put the car back on the road
Quest 3 left stick move · right stick turn · hold A to aim a teleport, release to jump
        grip grab · trigger use · X fold · Y wrist objectives · B back · left Menu pause
        In the car: left stick steer · right trigger throttle · left trigger brake / reverse
                    B climb out · hold X to put the car back on the road


SAVES, SETTINGS AND LOGS
------------------------
%USERPROFILE%\AppData\LocalLow\Team Kanban\SKYFOLD\
  settings.json      comfort, audio, display and subtitle settings
  campaign.json      episode progress and the roads you built
  demo.json          demo progress (separate, never touches the campaign)
  Player.log         the log to send with any bug report
  Screenshots\       F12 screenshots


CREDITS AND LICENCES
--------------------
Design, code and direction: Awaiz Ahmed / Team Kanban.
All 3D models, music, ambience and most sound effects are original, made by scripts for this game.
Noor's voice lines are AI-generated with the open Kokoro TTS model (stock voice, no voice cloning).
Some sound effects layer CC0 Kenney.nl recordings. Fonts: Unbounded and Atkinson Hyperlegible
(SIL Open Font License). Built with Unity.
Details: docs\ASSET_MANIFEST.md and the licenses folder.
Noor and NURI are fictional characters. They do not depict the creator or any real person.
