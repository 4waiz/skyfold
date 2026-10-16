"""Rebuild every character / vehicle asset, verify the FBX files and refresh the contact sheet.

Original tooling for SKYFOLD (Awaiz Ahmed / Team Kanban).
    blender -b --factory-startup -P tools/blender/chars_build_all.py [-- --no-render]
Each build script can also be run on its own.
"""
import os, sys, runpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SCRIPTS = ["chars_nuri.py", "chars_gloves.py", "veh_power_cell.py", "veh_courier_car.py",
           "veh_convoy_shuttle.py", "veh_city_cars.py", "veh_aircraft.py", "chars_passengers.py",
           "chars_verify.py"]
if '--no-render' not in sys.argv:
    SCRIPTS.append("chars_contact_sheet.py")

for s in SCRIPTS:
    print("[skyfold] ===== running", s)
    sys.stdout.flush()
    runpy.run_path(os.path.join(HERE, s), run_name="__main__")
