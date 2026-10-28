"""SKYFOLD environment kit runner (headless Blender 5.2).

Usage (PowerShell):
  & "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup `
      -P tools/blender/build_env.py -- <command> [args]

Commands:
  list                         list registered assets and groups
  build <name|group:G|all>...  build, export FBX and render preview(s)  [--norender]
  seam                         render road tiles side by side (seam check)
  check                        re-import every exported FBX, validate, write manifests
"""
import sys, os, json, time, importlib, traceback
sys.dont_write_bytecode = True      # keep tools/blender free of __pycache__

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import env_common as C

MODULES = ["env_tiles", "env_buildings", "env_atelier", "env_props", "env_nature", "env_sky", "env_energy"]
for m in MODULES:
    if os.path.exists(os.path.join(HERE, m + ".py")):
        importlib.import_module(m)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
LOG = os.environ.get("SKY_ENV_LOG", os.path.join(os.environ.get("TEMP", HERE), "skyfold_env_build_log.json"))


def resolve(args):
    names = []
    for a in args:
        if a.startswith("--"):
            continue
        if a == "all":
            names += list(C.REGISTRY.keys())
        elif a.startswith("group:"):
            g = a.split(":", 1)[1]
            names += [n for n, i in C.REGISTRY.items() if i["group"] == g]
        elif a in C.REGISTRY:
            names.append(a)
        else:
            print("Unknown asset", a)
    seen = []
    for n in names:
        if n not in seen:
            seen.append(n)
    return seen


def cmd_build(args):
    names = resolve(args)
    render = "--norender" not in args
    report = []
    log = {}
    if os.path.exists(LOG):
        try:
            log = json.load(open(LOG))
        except Exception:
            log = {}
    for n in names:
        try:
            rec = C.build_one(n, do_render=render, report=report)
            log[n] = rec
        except Exception:
            traceback.print_exc()
            print(f"[FAILED] {n}")
            log[n] = dict(name=n, error=traceback.format_exc())
    json.dump(log, open(LOG, "w"), indent=1)
    for r in report:
        print(f"  {r['name']:<24} {r['tris']:>6} tris  {r['seconds']:>5}s")


def cmd_list(args):
    for n, i in C.REGISTRY.items():
        print(f"{i['group']:<12} {i['category']:<10} {n}")


if __name__ == "__main__":
    if not argv:
        print(__doc__)
    elif argv[0] == "build":
        cmd_build(argv[1:])
    elif argv[0] == "list":
        cmd_list(argv[1:])
    elif argv[0] in ("seam", "check"):
        import env_check
        getattr(env_check, "cmd_" + argv[0])(argv[1:])
    else:
        print(__doc__)
