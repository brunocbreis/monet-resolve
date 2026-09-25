"""Resolve's menu bar, driven through macOS accessibility (System Events).

Some editing actions exist only in the UI: switching a multicam angle, selecting clips by color, closing
a timeline tab, applying a gallery still's grade, running the AI Audio Assistant. Resolve's menu bar
exposes every one of them to accessibility, so a script can press the exact menu item an editor would.
This is precise (a named menu item, never a screen coordinate) and it keeps working while the Mac's
screen is locked. Keystrokes and window contents are the exception: they need an unlocked screen.

Requirements: macOS, and the app running the script (a terminal, an agent host) allowed under System
Settings, Privacy & Security, Accessibility. Menu items act on Resolve's current page, current timeline
tab and current selection, so set those first (`resolve.OpenPage`, `project.SetCurrentTimeline`).

Route order for anything missing from the API: API first, then a menu item here, then a keyboard
shortcut (`keystroke`), and screen coordinates only as a last resort.
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
    """Click a menu item by its path, e.g. menu(["File", "Close Timeline"]).

    With `require_enabled` it checks first and returns False instead of clicking a disabled item (a click
    on a disabled item can hang System Events). Works while the screen is locked.
    """
    if require_enabled and not menu_enabled(path):
        return False
    _osa(f'tell application "System Events" to tell process "{PROCESS}" to click {_item_ref(path)}')
    return True


def keystroke(key: str, modifiers: Sequence[str] = ()) -> None:
    """Send a keystroke to Resolve (e.g. keystroke("t", ["control"])). Needs an unlocked screen: while
    the screen is locked keystrokes go nowhere and the next menu action lands on the wrong target."""
    activate()
    mods = ""
    if modifiers:
        mods = " using {" + ", ".join(f"{m} down" for m in modifiers) + "}"
    _osa(f'tell application "System Events" to tell process "{PROCESS}" to keystroke "{key}"{mods}')


def switch_page(page: str) -> bool:
    """Workspace > Switch to Page > page ("Edit", "Color", "Deliver", ...). Unlike `resolve.OpenPage`,
    this keeps a timeline tab that only the UI opened (a multicam opened with Open in Timeline)."""
    return menu(["Workspace", "Switch to Page", page])


def focus_panel(panel: str) -> bool:
    """Workspace > Active Panel Selection > panel ("Media Clips", "Timeline", "Source Viewer", ...)."""
    return menu(["Workspace", "Active Panel Selection", panel])


def deselect_all() -> bool:
    return menu(["Edit", "Deselect All"])


def select_clips_by_color(color: str) -> bool:
    """Timeline > Select Clips > By Clip Color > color, on the current timeline. Selects video and audio
    items. Pair it with `TimelineItem.SetClipColor` on a spare color to select any set of items from a
    script (there is no API selection call)."""
    deselect_all()
    time.sleep(0.2)
    ok = menu(["Timeline", "Select Clips", "By Clip Color", color])
    time.sleep(0.4)
    return ok


def switch_multicam_angle(angle: int) -> bool:
    """Clip > Multicam Switch > Switch to Angle N on the selected multicam items. Edit page only: the
    item is disabled on the Deliver and Color pages."""
    ok = menu(["Clip", "Multicam Switch", f"Switch to Angle {angle}"])
    time.sleep(0.6)
    return ok


def close_current_timeline() -> bool:
    """File > Close Timeline closes the current timeline tab (no API call closes tabs). To close a list
    of tabs: `project.SetCurrentTimeline(t)` then this, per timeline."""
    return menu(["File", "Close Timeline"])


def apply_grade_from_still() -> bool:
    """Color > Apply Grade: applies the selected gallery still to the current clip on the Color page.
    `timeline.GrabStill()` leaves the new still selected."""
    return menu(["Color", "Apply Grade"])


def open_selected_media_pool_clip_in_timeline(shortcut: Sequence[str] = ("t", "control")) -> None:
    """Open the media pool item selected with `MediaPool.SetSelectedClip` as its own timeline tab, the
    way right-click > Open in Timeline does (for a multicam, compound or Fusion clip).

    The Clip menu's Open in Timeline stays disabled for multicam clips, so this focuses the media pool
    (Active Panel Selection > Media Clips) and sends the Open in Timeline shortcut (`shortcut` is the key
    followed by its modifiers; match your keyboard preset). Needs an unlocked screen. The API cannot see the
    opened timeline: `project.GetCurrentTimeline()` still returns the previous one, so continue with menu
    actions (switch_page, apply_grade_from_still) and verify by rendering the parent timeline.
    """
    focus_panel("Media Clips")
    time.sleep(0.3)
    key, *mods = shortcut
    keystroke(key, mods)
    time.sleep(1.5)


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
