# Playing SKYFOLD on Meta Quest 3 (PC VR through Link)

SKYFOLD runs on the laptop and streams to the headset through **Meta Horizon Link** (cable or Air Link). There is no Quest APK; the game itself runs on the PC's RTX GPU.

> Status: the VR path was built and configured, but **no headset was connected during development**. Every step below is **NOT TESTED** on real hardware until you run it. The checklist at the end is what to try first.

## What you need

- Meta Quest 3 with its Touch Plus controllers, updated and paired to your Meta account.
- The **Meta Horizon Link** app for Windows (formerly the Oculus app), signed in. Download it from Meta's site and let it finish its setup and device check.
- Either a **USB-C Link cable** (USB 3, data-capable) plugged into a USB 3 port, or **Air Link** on a 5 GHz / 6 GHz Wi-Fi network with the laptop wired to the router if possible.
- The laptop on mains power. Link performance drops a lot on battery.

## One-time setup (you do these; the game does not change system settings)

1. **Make Meta Horizon Link the OpenXR runtime.** Meta Horizon Link app → Settings → General → *OpenXR Runtime* → **Set Meta Horizon Link as active**. If SteamVR was the active runtime, this switches it.
2. **Use the RTX GPU for SKYFOLD.** Unity players already ask for the discrete GPU. If the log shows the Intel/AMD integrated GPU instead, open Windows Settings → System → Display → Graphics, add `SKYFOLD.exe` and choose *High performance*. NVIDIA Control Panel → Manage 3D settings → Program settings works too.
3. Optional, for comfort: in the headset, set up a **stationary boundary** for seated play or a **room-scale boundary** of at least 2 m × 2 m for standing play.

## Every time you play

1. Start the **Meta Horizon Link** app on the laptop.
2. Put on the headset and start Link: Quick Settings → **Link** (cable) or **Air Link**, then **Launch**. Wait for the grey Link home environment.
3. Double-click the **SKYFOLD - Quest 3** shortcut on the Desktop. It runs `SKYFOLD.exe --mode=vr`.
4. The laptop shows "Starting VR…". When the headset comes up, you are on the Fold Atelier terrace. The first time, a short comfort screen lets you pick movement and turning (teleport + snap is the most comfortable) and seated or standing play. Driving style is under Comfort.
5. The laptop window becomes the **spectator view**: the left-eye image plus a laptop-only overlay with the objective, subtitles and storm timer. Visitors can follow along without a headset.

You can also start the normal **SKYFOLD** shortcut and choose **Enter VR** from the menu. **Play on the laptop instead** in the VR menu drops back to keyboard and mouse at any time.

## If VR does not start

The game never leaves you with a black screen. It shows the reason plus **Retry** and **Play on this laptop**. The messages mean:

| Message | What to do |
| --- | --- |
| *Meta Horizon Link is not running on this PC.* | Start the Meta Horizon Link app, connect the headset, press **Retry**. |
| *The headset did not answer.* | Put on the headset, start Link (step 2 above), wait for the Link home, press **Retry**. |
| *OpenXR started but no headset display came up.* | Link isn't active in the headset, or another VR app holds it. Close other VR apps and press **Retry**. |
| *XR settings are missing from this build.* | The build is damaged. Re-extract the ZIP. |

If Retry keeps failing after Link is running, quit SKYFOLD and start it again from the **SKYFOLD - Quest 3** shortcut. Re-starting OpenXR in the same process isn't guaranteed on every runtime version.

**Log file:** `%USERPROFILE%\AppData\LocalLow\Team Kanban\SKYFOLD\Player.log`. Lines starting with `[SKYFOLD] XR` show the runtime name, the device, the eye texture size and the refresh rate. Send this file with any bug report.

## While playing

- **Recenter**: Pause (left Menu button) → **Recenter view**, or the Comfort screen. **Set my height** recalibrates standing or seated height.
- Taking the headset off pauses the game. Choose **Resume** when you are back.
- If a controller loses tracking while you drive, the car holds still until both controllers are visible again.

## Headset test checklist (run this once and report back)

Each item is **NOT TESTED** until you try it.

1. Launch from **SKYFOLD - Quest 3**: the headset shows the Atelier within about 10 s, and the laptop shows the spectator view.
2. Both gloves sit in your hands like you are holding the controllers: thumbs up along the handle, knuckles forward, palms facing in. (0.9.0 attached them to the controller's pointing pose, so they pointed the wrong way; 0.9.1 uses the grip pose.) Note if a glove still looks rotated or offset.
2b. Look at each hand: a card above it lists that controller's buttons, with the one you need lit (Grip at the plinth, X once the bridge is in). Press **Y** for the wrist panel; it should read upright just above your left wrist.
3. Left stick moves, right stick snap-turns, and holding A shows the teleport arc. Releasing it moves you.
4. At the plinth: grip a bridge piece, turn it in your hand, set it into a glowing socket. It snaps when correct, and flashes coral with a reason when wrong.
5. **X** at the plinth folds you down to the street. **Y** shows the wrist objectives.
6. Pick up the power cell with grip and place it in the car's rear cradle.
7. Trigger on the car door climbs in. Steering, throttle and brake work, B climbs out when stopped, and hold X resets the car.
8. Comfort → Driving → *Remote, from an overlook*: you steer from a fixed viewpoint while standing still.
9. Pause with the left Menu button, then Recenter, Resume, Retry and Main menu.
10. Performance: the Meta Horizon Link app's performance overlay (or the Oculus Debug Tool) should show 72–90 Hz without many dropped or reprojected frames during the drive and the takeoff.
