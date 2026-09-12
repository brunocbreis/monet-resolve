"""Connect to a running DaVinci Resolve through Blackmagic's own scripting module.

The MCP tool pre-binds `resolve` and `project`; this does the same from any Python:

    from monet_resolve import connect
    resolve, project = connect()

Paths default to the standard macOS install; override with RESOLVE_SCRIPT_API / RESOLVE_SCRIPT_LIB.
Resolve must be running with external scripting allowed (Preferences > System > General).
"""
import os
import sys

MAC_API = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
MAC_LIB = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"


class ResolveNotRunning(RuntimeError):
    pass


def connect(require_project=True):
    api = os.environ.setdefault("RESOLVE_SCRIPT_API", MAC_API)
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", MAC_LIB)
    modules = os.path.join(api, "Modules")
    if modules not in sys.path:
        sys.path.append(modules)
    import DaVinciResolveScript as dvr  # noqa: E402

    resolve = dvr.scriptapp("Resolve")
    if resolve is None:
        raise ResolveNotRunning("DaVinci Resolve is not running or external scripting is off")
    project = resolve.GetProjectManager().GetCurrentProject()
    if require_project and project is None:
        raise ResolveNotRunning("no project is open")
    return resolve, project
