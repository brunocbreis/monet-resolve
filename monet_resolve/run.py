"""Run a script file with `resolve`, `project`, and `mr` (this package) pre-bound, like the MCP's run_script.

    python -m monet_resolve.run path/to/script.py

The script's `result` variable, if set, is printed as JSON at the end.
"""
import json
import sys

from . import connect
import monet_resolve as mr


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__)
        return 2
    resolve, project = connect()
    ns = {"resolve": resolve, "project": project, "mr": mr, "__name__": "__main__"}
    with open(argv[0]) as f:
        code = compile(f.read(), argv[0], "exec")
    exec(code, ns)
    if "result" in ns:
        print(json.dumps(ns["result"], default=str, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
