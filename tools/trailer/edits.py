"""Edit decision lists for the two SKYFOLD brag cuts. One source of timing for picture, graphics and sound.

Times are seconds on the trailer timeline. Shot media offsets refer to the captured clips
(brag-output/footage/clips/<id>_<aspect>.mp4, 30 fps, captured by CineDirector).
"""

# Copy shared by both cuts. Every product line is quoted or trimmed from the game itself.
CHIP_WRONG = ("Not quite.", "The east end runs into the water. Turn it a quarter.")   # RouteValidator + HUD toast
CHIP_RIGHT = "Let go to set it in place."                                             # TabletopController hint
NOOR_ROLE = "City engineer · radio"                                              # e1.welcome
TOWER_NAME, TOWER_ROLE = "NACRE TOWER", "Airfield announcement"                       # e3.takeoff "Nacre tower"
PLATFORM_VR = "PLAY IN VR · META QUEST 3 VIA LINK"                               # README / Desktop shortcut
PLATFORM_PC = "OR ON YOUR LAPTOP"
CREDIT_SMALL, CREDIT_NAME = "MADE BY", "AWAIZ AHMED"
FOOTER = "Captured in engine · Hobby project"


def beacon_ticks(sweep_at, speed=60.0):
    """Times the runway beacon pairs light (x = 24..168 m, sweep from x = 22 m at `speed` m/s)."""
    return [sweep_at + (24 + 16 * i - 22) / speed for i in range(10)]


LANDSCAPE = {
    "name": "landscape", "aspect": "landscape", "w": 1920, "h": 1080, "duration": 90.0,
    "shots": [  # (element id, shot, start, duration, media start)
        ("v01", "A1", 0.0, 7.0, 0.0),
        ("v02", "A2", 7.0, 7.0, 0.0),
        ("v03", "A3", 14.0, 7.0, 0.0),
        ("v04", "A4", 21.0, 7.0, 0.0),
        ("v05", "B1", 28.0, 5.0, 0.0),
        ("v06", "B2", 33.0, 4.0, 0.0),
        ("v07", "B3", 37.0, 3.6, 0.0),
        ("v08", "B4", 40.6, 2.7, 0.2),
        ("v09", "B5", 43.3, 2.7, 1.3),
        ("v10", "B6", 46.0, 1.8, 0.2),
        ("v11", "B7", 47.8, 3.2, 0.6),
        ("v12", "C1", 51.0, 7.0, 0.0),
        ("v13", "C2", 58.0, 4.0, 0.6),
        ("v14", "C3", 62.0, 4.0, 0.5),
        ("v15", "C4", 66.0, 3.0, 0.0),
        ("v16", "C5", 69.0, 4.5, 0.0),
        ("v17", "C6", 73.5, 6.5, 0.5),
    ],
    "title_bg": ("A1", 80.0, 10.0, 0.4),
    "vo": [("noor1", 0.8), ("n2", 7.4), ("noor3", 15.2), ("noor4", 23.2), ("n5", 28.4), ("noor6", 47.6),
           ("n7", 52.0), ("tower8", 58.8), ("n9", 75.6), ("n10", 80.6)],
    "music": [  # (file, at, src, dur, fade in, fade out, gain)
        ("music_menu_loop", 0.0, 0.0, 28.6, 1.6, 1.0, 1.0),
        ("music_drive_loop", 27.6, 0.0, 24.0, 0.5, 1.2, 0.95),
        ("music_storm_loop", 50.6, 0.0, 14.6, 0.8, 2.2, 1.0),
        ("music_finale", 63.25, 12.0, 26.75, 1.4, 2.6, 1.08),
    ],
    "music_lane": [(0, 1), (20.2, 1), (20.9, 0.12), (21.9, 0.12), (22.6, 1), (90, 1)],  # hush before the bridge rises
    "ambience": [  # (file, at, dur, fade in, fade out, gain)
        ("amb_atelier_loop", 0.0, 21.4, 1.2, 0.8, 0.55),
        ("amb_coast_loop", 20.6, 7.8, 0.4, 0.8, 0.6),
        ("amb_city_loop", 27.8, 23.6, 1.0, 1.4, 0.5),
        ("amb_storm_loop", 50.4, 31.0, 2.0, 2.5, 0.85),
    ],
    "sfx": [  # (sound, at, gain[, extra])
        ("impact/impactSoft_heavy_000", 7.40, 0.42), ("impact/impactSoft_heavy_001", 8.60, 0.42),
        ("impact/impactSoft_heavy_002", 10.0, 0.48),
        ("piece_pickup", 14.25, 0.55), ("socket_reject", 15.45, 0.8), ("piece_rotate", 17.08, 0.9),
        ("socket_snap", 19.32, 1.0),
        ("bridge_assemble", 22.2, 1.0),
        ("impact/impactSoft_heavy_003", 23.2, 0.36), ("impact/impactSoft_heavy_004", 24.4, 0.36),
        ("fold_out", 27.5, 0.95),
        ("cell_pickup", 33.25, 0.7), ("cell_insert", 35.56, 0.9),
        ("car_roll_loop", 37.0, 0.32, {"dur": 9.0, "loop": True, "fade_in": 0.4, "fade_out": 0.8}),
        ("car_motor_loop", 37.0, 0.26, {"dur": 9.0, "loop": True, "fade_in": 0.4, "fade_out": 0.8}),
        ("cell_insert", 47.36, 0.8), ("substation_on", 48.2, 0.95), ("power_transfer", 48.25, 0.55),
        ("thunder_far_01", 55.5, 1.0),
        ("door_chime", 62.3, 0.5),
        ("switch_lever", 66.9, 1.0),
        ("plane_spoolup", 68.4, 0.8), ("plane_takeoff", 69.4, 1.0), ("plane_flyby", 71.0, 1.0),
        ("thunder_far_02", 77.2, 0.6),
        ("impact/impactSoft_heavy_000", 79.85, 0.75),
        ("impact/impactSoft_heavy_002", 81.75, 0.6),
        ("casino/card-place-2", 85.15, 0.45), ("casino/card-place-3", 87.45, 0.55),
    ],
    "beacon_sweep": 58.4,
    "letters_at": 80.25,
    "flash_at": 79.85,
    "graphics": {
        "fade_in": (0.0, 1.5),
        "location": (1.6, 6.7),
        "radio": [("noor1", 0.6, 5.5), ("noor3", 15.0, 18.1), ("noor4", 23.0, 25.7), ("noor6", 47.4, 51.4)],
        "tower": (58.6, 62.9),
        "big": [
            {"id": "cb1", "in": 7.4, "out": 8.55, "lines": [("ONE STORM.", 0)]},
            {"id": "cb2", "in": 8.6, "out": 9.95, "lines": [("ONE LAST FLIGHT.", 0)]},
            {"id": "cb3", "in": 10.0, "out": 13.7, "lines": [("ONE CITY", 0), ("IN YOUR HANDS.", 0.12)]},
            {"id": "cb4", "in": 23.2, "out": 27.2, "align": "left", "lines": [("CHANGE ONE.", 0), ("CHANGE THE OTHER.", 1.2)]},
            {"id": "cb5", "in": 52.1, "out": 57.2, "lines": [("THE STORM", 0), ("WON'T WAIT.", 0.55)]},
            {"id": "cb6", "in": 75.7, "out": 79.5, "lines": [("GET THEM HOME.", 0)]},
        ],
        "objectives": [  # (id, number, title, in, check, out)
            ("ob1", 1, "HOLD THE CITY", 14.4, 19.32, 20.8),
            ("ob2", 2, "FOLD DOWN", 28.5, 31.7, 32.85),
            ("ob3", 3, "CARRY THE POWER", 33.3, 35.56, 36.85),
            ("ob4", 4, "DRIVE THE ROADS YOU BUILT", 37.3, 44.9, 45.85),
            ("ob5", 5, "POWER THE AIRFIELD", 46.2, 48.2, 50.85),
            ("ob6", 6, "LIGHT THE RUNWAY", 58.5, 60.85, 61.9),
            ("ob7", 7, "SEND THE LAST FLIGHT", 66.1, 66.9, 68.85),
        ],
        "chips": [("ch1", "warn", 15.5, 17.05), ("ch2", "ok", 17.15, 19.3)],
        "fold": 27.8,
        "lightning": [55.5, 55.72],
        "title": (80.0, 85.0),
        "platforms": (85.0, 87.55),
        "credit": (87.45, 90.0),
        "fade_out": (89.2, 90.0),
    },
}

VERTICAL = {
    "name": "vertical", "aspect": "portrait", "w": 1080, "h": 1920, "duration": 60.0,
    "shots": [
        ("v01", "A1", 0.0, 5.0, 0.3),
        ("v02", "A2", 5.0, 4.0, 1.5),
        ("v03", "A3", 9.0, 6.0, 0.0),
        ("v04", "A4", 15.0, 6.0, 0.0),
        ("v05", "B1", 21.0, 4.0, 0.5),
        ("v06", "B2", 25.0, 2.9, 0.6),
        ("v07", "B3", 27.9, 3.5, 0.3),
        ("v08", "B5", 31.4, 2.6, 0.9),
        ("v09", "C1", 34.0, 5.0, 0.5),
        ("v10", "C2", 39.0, 3.0, 0.4),
        ("v11", "C4", 42.0, 2.0, 0.2),
        ("v12", "C5", 44.0, 3.6, 0.0),
        ("v13", "C6", 47.6, 4.4, 1.0),
    ],
    "title_bg": ("A1", 52.0, 8.0, 0.3),
    "vo": [("noor1v", 0.6), ("noor4", 16.7), ("n5", 21.3), ("n7", 34.6), ("tower8", 39.3), ("n9", 48.4), ("n10", 52.6)],
    "music": [
        ("music_menu_loop", 0.0, 0.0, 21.4, 1.0, 0.8, 1.0),
        ("music_drive_loop", 20.8, 0.0, 13.8, 0.5, 1.0, 0.95),
        ("music_storm_loop", 33.8, 0.0, 9.8, 0.6, 1.8, 1.0),
        ("music_finale", 41.6, 14.0, 18.4, 1.2, 2.2, 1.08),
    ],
    "music_lane": [(0, 1), (14.4, 1), (15.0, 0.12), (15.9, 0.12), (16.6, 1), (60, 1)],
    "ambience": [
        ("amb_atelier_loop", 0.0, 15.4, 1.0, 0.8, 0.5),
        ("amb_coast_loop", 14.8, 6.4, 0.4, 0.6, 0.6),
        ("amb_city_loop", 20.9, 13.3, 0.8, 1.0, 0.5),
        ("amb_storm_loop", 33.6, 19.0, 1.5, 2.0, 0.85),
    ],
    "sfx": [
        ("impact/impactSoft_heavy_000", 0.45, 0.4),
        ("socket_reject", 10.25, 0.8), ("piece_rotate", 11.64, 0.9), ("socket_snap", 13.56, 1.0),
        ("bridge_assemble", 15.9, 1.0),
        ("impact/impactSoft_heavy_003", 16.7, 0.36), ("impact/impactSoft_heavy_004", 17.9, 0.36),
        ("fold_out", 20.7, 0.95),
        ("cell_insert", 26.64, 0.9),
        ("car_roll_loop", 27.9, 0.32, {"dur": 6.1, "loop": True, "fade_in": 0.3, "fade_out": 0.6}),
        ("car_motor_loop", 27.9, 0.26, {"dur": 6.1, "loop": True, "fade_in": 0.3, "fade_out": 0.6}),
        ("thunder_far_01", 37.3, 1.0),
        ("switch_lever", 42.55, 1.0),
        ("plane_spoolup", 43.2, 0.8), ("plane_takeoff", 44.0, 1.0), ("plane_flyby", 45.0, 1.0),
        ("thunder_far_02", 49.6, 0.6),
        ("impact/impactSoft_heavy_000", 51.85, 0.75),
        ("impact/impactSoft_heavy_002", 53.75, 0.6),
        ("casino/card-place-2", 56.05, 0.45), ("casino/card-place-3", 57.65, 0.55),
    ],
    "beacon_sweep": 39.4,
    "letters_at": 52.25,
    "flash_at": 51.85,
    "graphics": {
        "fade_in": (0.0, 1.0),
        "location": (5.3, 8.8),
        "radio": [("noor1v", 0.45, 4.4), ("noor4", 16.5, 19.2)],
        "tower": (39.1, 43.4),
        "big": [
            {"id": "cb1", "in": 0.5, "out": 4.75, "lines": [("THIS CITY", 0), ("FITS IN", 0.2), ("YOUR HANDS", 0.4)]},
            {"id": "cb4", "in": 16.7, "out": 20.4, "lines": [("CHANGE ONE.", 0), ("CHANGE", 1.2), ("THE OTHER.", 1.3)]},
            {"id": "cb5", "in": 34.8, "out": 38.8, "lines": [("THE STORM", 0), ("WON'T WAIT.", 0.55)]},
            {"id": "cb6", "in": 48.5, "out": 51.6, "lines": [("GET THEM", 0), ("HOME.", 0.15)]},
        ],
        "objectives": [
            ("ob1", 1, "HOLD THE CITY", 9.3, 13.56, 14.75),
            ("ob2", 2, "FOLD DOWN", 21.4, 24.0, 24.9),
            ("ob3", 3, "CARRY THE POWER", 25.2, 26.64, 27.8),
            ("ob4", 4, "DRIVE THE ROADS YOU BUILT", 28.1, 33.0, 33.9),
            ("ob6", 6, "LIGHT THE RUNWAY", 39.5, 41.85, 41.98),
            ("ob7", 7, "SEND THE LAST FLIGHT", 42.05, 42.55, 43.9),
        ],
        "chips": [("ch1", "warn", 10.25, 11.6), ("ch2", "ok", 11.7, 13.5)],
        "fold": 21.0,
        "lightning": [37.3, 37.52],
        "title": (52.0, 56.0),
        "platforms": (56.0, 57.75),
        "credit": (57.65, 60.0),
        "fade_out": (59.3, 60.0),
    },
}

FORMATS = {"landscape": LANDSCAPE, "vertical": VERTICAL}
