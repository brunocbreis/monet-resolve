"""Run testbed checks against the open "monet-testbed" project.

    python3 -m testbed.run                 # every check
    python3 -m testbed.run freeze_item     # only the named checks
    python3 -m testbed.run --ui            # also the checks that drive Resolve's menu bar (Accessibility)

Verifies the base timelines against the frozen baseline first, then prints a PASS / FAIL table and
writes testbed/out/report.json.
"""
import json
import os
import sys
import traceback

import monet_resolve as mr

from . import baseline
from .build import PROJECT
from .checks import CHECKS, UI_CHECKS


def main(names=None) -> int:
    resolve, project = mr.connect()
    if project.GetName() != PROJECT:
        raise SystemExit(f"open {PROJECT!r} first (python3 -m testbed.build)")
    drifted = baseline.verify(resolve, project)
    if drifted:
        raise SystemExit(f"base timelines differ from the frozen baseline: {drifted}. "
                         "Run `python3 -m testbed.baseline restore` (or rebuild and freeze again).")
    mp = project.GetMediaPool()
    ctx = {"resolve": resolve, "project": project, "mp": mp, "checks_bin": mr.find_bin(mp, ["timelines", "checks"])}
    results = []
    ui = "--ui" in (names or [])
    names = [n for n in (names or []) if n != "--ui"]
    for name in names or [n for n in CHECKS if ui or n not in UI_CHECKS]:
        try:
            results.append(CHECKS[name](ctx))
        except Exception:
            results.append({"name": name, "ok": False, "expected": "", "got": traceback.format_exc()})
        r = results[-1]
        print(f"{'PASS' if r['ok'] else 'FAIL'}  {name}", flush=True)
    mr.save(resolve)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "report.json"), "w") as fh:
        json.dump({"resolve": resolve.GetVersionString(), "results": results}, fh, indent=1, default=str)
    print(f"{sum(r['ok'] for r in results)}/{len(results)} passed")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
