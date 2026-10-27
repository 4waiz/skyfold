SKYFOLD: Clean Energy Challenge
===============================
A project by Awaiz Ahmed. Showcase build for ADIPEC 2026. Windows x64.
An independent project inspired by ADNOC's public sustainability goals; not an official ADNOC product.

Stand at a lab table above a coastal city and take the island to net zero in three quick
sustainability puzzles. About three minutes from start to finish, for high-school students
and recent graduates:
  1  Power the city 24/7 ... drop energy blocks into the grid: enough by day and by night, zero CO2
  2  Capture the carbon .... turn the pipes so the CO2 flows into the underground storage well
  3  Blue carbon coast ..... plant mangroves on the glowing mudflats before they fade (25 s)
Every puzzle helps you out if you get stuck, so everyone finishes. Each scores up to 1000.


HOW TO START (no installation)
------------------------------
- "SKYFOLD" Desktop shortcut ............ play on this laptop (keyboard and mouse)
- "SKYFOLD - Quest 3" Desktop shortcut .. play in VR on Meta Quest 3 through Link
- In this folder:
    Play on this laptop.cmd
    Play in VR (Quest 3 Link).cmd
    Play Clean Energy Challenge (3 min).cmd ... asks laptop or VR, then starts the challenge
- Or run SKYFOLD.exe directly. It asks whether to play on the laptop or in VR.
- Exhibition operator: F5 (or Pause > Operator: next player) restarts the challenge for the next
  visitor. A finished results screen returns to the title by itself after 90 seconds.

Command-line options for SKYFOLD.exe:
  --mode=desktop | --mode=vr   start straight in that mode
  --demo                       open the Clean Energy Challenge straight away
  --windowed                   start in a window
  --diagnostics                show the input diagnostics panel (also F1)


WHAT YOU NEED
-------------
- Windows 10 or 11, 64-bit, with a DirectX 11 GPU. Tested on the creator's laptop with an
  NVIDIA GeForce RTX 5080 Laptop GPU.
- For VR: Meta Quest 3, the Meta Horizon Link app on the PC (set as the active OpenXR runtime),
  and a Link cable or Air Link. See docs\QUEST_LINK_SETUP.md.
  VR STATUS: the Clean Energy Challenge is checked with a simulated headset (QA scenario
  "energyvr"); test it on the Quest 3 before the event (docs\CLEAN_ENERGY.md has a checklist).


CONTROLS (full list: docs\CONTROLS.md)
--------------------------------------
Laptop  hold left mouse on an energy block to drag it, release over a grid slot
        click a pipe to turn it · click a glowing mudflat to plant a mangrove
        right-drag or W A S D look around the table · wheel zoom · Tab objectives · Esc pause
Quest 3 stand at the table: everything is within reach, no walking needed.
        grip grab an energy block · point the ray + trigger turn a pipe / plant a mangrove
        right stick turn · Y wrist objectives · left Menu pause · trigger presses menu buttons
        Look at a hand: a card above it shows what its buttons do right now (the one you need is lit).


SAVES, SETTINGS AND LOGS
------------------------
%USERPROFILE%\AppData\LocalLow\Team Kanban\SKYFOLD\
  settings.json      comfort, audio, display and subtitle settings
  demo.json          Clean Energy Challenge best score
  campaign.json      progress in the original Last Flight episodes
  Player.log         the log to send with any bug report
  Screenshots\       F12 screenshots


CREDITS AND LICENCES
--------------------
Design, code and direction: Awaiz Ahmed.
All 3D models, music, ambience and most sound effects are original, made by scripts for this game.
Noor's voice lines are AI-generated with the open Kokoro TTS model (stock voice, no voice cloning).
Noor's radio portrait (the subtitle badge) is AI-generated with ChatGPT image generation.
Some sound effects layer CC0 Kenney.nl recordings. Fonts: Unbounded and Atkinson Hyperlegible
(SIL Open Font License). Built with Unity.
Details: docs\ASSET_MANIFEST.md and the licenses folder.
Noor and NURI are fictional characters. They do not depict the creator or any real person.
