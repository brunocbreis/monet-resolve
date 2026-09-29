"""Resolve's menu bar, driven through macOS accessibility (System Events).

Some editing actions exist only in the UI: closing a timeline tab, switching pages, running the AI Audio
Assistant. Resolve's menu bar exposes them to accessibility, so a script can press the exact menu item an
editor would, by name. Items that depend on the timeline selection can read disabled to a script and
ignore its press (Clip > Multicam Switch did, while the same item worked by hand).

Requirements: macOS, and the app running the script (a terminal, an agent host) allowed under System
Settings, Privacy & Security, Accessibility. Menu items act on Resolve's current page, current timeline
tab and current selection, so set those first (`resolve.OpenPage`, `project.SetCurrentTimeline`).
"""
import subprocess
import time
from typing import List, Sequence

PROCESS = "Resolve"


def _osa(script: str, timeout: float = 30) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout.strip()


def _item_ref(path: Sequence[str]) -> str:
    """AppleScript reference for a menu path such as ["Clip", "Multicam Switch", "Switch to Angle 2"]."""
    ref = f'menu bar item "{path[0]}" of menu bar 1'
    for name in path[1:]:
        ref = f'menu item "{name}" of menu 1 of {ref}'
    return ref


def activate() -> None:
    """Bring Resolve to the front. Menu clicks do not need it; keystrokes do."""
    _osa('tell application "DaVinci Resolve" to activate')
    time.sleep(0.5)


def menu_items(path: Sequence[str]) -> List[str]:
    """Names of the items in a menu or submenu, e.g. menu_items(["Timeline", "AI Tools"]).

    Separators come back as "missing value" and are dropped. Use it to discover exact spellings
    (Resolve writes "Audio Assistant…" with a real ellipsis).
    """
    if len(path) == 1:
        ref = f'menu 1 of menu bar item "{path[0]}" of menu bar 1'
    else:
        ref = f"menu 1 of {_item_ref(path)}"
    out = _osa(f'tell application "System Events" to tell process "{PROCESS}" to get name of every menu item of {ref}')
    return [n.strip() for n in out.split(",") if n.strip() and n.strip() != "missing value"]


def menu_enabled(path: Sequence[str]) -> bool:
    """True when the menu item is currently enabled. Resolve updates most items live; a few (Clip >
    Link Clips) report disabled to accessibility even when the selection qualifies."""
    return _osa(f'tell application "System Events" to tell process "{PROCESS}" to get enabled of {_item_ref(path)}') == "true"


def menu(path: Sequence[str], require_enabled: bool = True) -> bool:
    """Press a menu item by its path, e.g. menu(["File", "Close Timeline"]), with the accessibility AXPress action.

    With `require_enabled` it returns False instead of pressing an item that reads disabled (pressing one
    can hang System Events).
    """
    if require_enabled and not menu_enabled(path):
        return False
    _osa(f'tell application "System Events" to tell process "{PROCESS}" to perform action "AXPress" of {_item_ref(path)}')
    return True


def switch_page(page: str) -> bool:
    """Workspace > Switch to Page > page ("Edit", "Color", "Deliver", ...). Unlike `resolve.OpenPage`,
    this keeps a timeline tab that only the UI opened (a multicam opened with Open in Timeline)."""
    return menu(["Workspace", "Switch to Page", page])


def focus_panel(panel: str) -> bool:
    """Workspace > Active Panel Selection > panel ("Media Clips", "Timeline", "Source Viewer", ...)."""
    return menu(["Workspace", "Active Panel Selection", panel])


def deselect_all() -> bool:
    return menu(["Edit", "Deselect All"])


def close_current_timeline() -> bool:
    """File > Close Timeline closes the current timeline tab (no API call closes tabs). To close a list
    of tabs: `project.SetCurrentTimeline(t)` then this, per timeline."""
    return menu(["File", "Close Timeline"])


def run_audio_assistant(button: str = "Auto Mix", poll: float = 5.0, timeout: float = 900.0) -> bool:
    """Timeline > AI Tools > Audio Assistant…, press its button, wait until the dialog closes.

    The dialog's delivery standard keeps its last value (YouTube by default); set it once by hand if you
    need another. Returns True when the dialog closed before `timeout`. It classifies every clip, mixes
    dialogue, music and effects, then masters; it changes clip volumes and adds track FX.
    """
    activate()
    if not menu(["Timeline", "AI Tools", "Audio Assistant…"]):
        return False
    time.sleep(2)
    _osa(f'''tell application "System Events" to tell process "{PROCESS}"
  repeat with w in windows
    try
      click (first button of w whose name is "{button}")
      return "ok"
    end try
  end repeat
end tell''')
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(poll)
        try:
            n = _osa(f'tell application "System Events" to tell process "{PROCESS}" to count (buttons of window "Frame" whose name is "Cancel")')
        except RuntimeError:
            n = "0"          # the dialog window is gone
        if n in ("0", ""):
            return True
    return False
