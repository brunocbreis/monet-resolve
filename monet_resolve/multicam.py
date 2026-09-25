"""Multicam clips on a timeline: place them in sync, set their angles, swap source clips for them.

The API can create a multicam (`MediaPool.CreateMulticamClip`) and append it, but has no call that
picks the angle of a multicam timeline item: every appended item shows the multicam's first angle, and
`PerformMulticamSmartSwitch` leaves angles unchanged. The angle is set through the menu bar instead
(Clip > Multicam Switch > Switch to Angle N) on items selected by a spare clip color; `set_angles` does
that and restores the colors.

Angle numbers follow the angle names in alphabetical order (with MULTICAM_ANGLE_NAME_ANGLE), whatever the
clip order passed to `CreateMulticamClip`. `angle_numbers` computes that mapping; check one angle on a render.

Timeline item names ("mcam - x - Angle Y") only refresh after the timeline reloads, so verify angles
by rendering a frame, not by `GetName()`.
"""
import time
from typing import Dict, Iterable, List, Optional, Sequence

from . import ui
from ._util import VIDEO_PROPS, items, save, tc_seconds
from .clips import append_exact

SPARE_COLORS = ["Chocolate", "Navy", "Orange", "Pink", "Lime", "Apricot", "Olive", "Tan", "Beige", "Brown"]


def angle_numbers(angle_names: Iterable[str]) -> Dict[str, int]:
    """{angle name: angle number} in Resolve's order (alphabetical by angle name)."""
    return {n: i + 1 for i, n in enumerate(sorted(set(angle_names)))}


def multicam_frame(mcam, clip, source_frame: float, fps: float = 24.0) -> int:
    """Frame in the multicam that shows `clip` at its `source_frame`, for a multicam synced by timecode.

    Uses both Start TCs: (clip start + source_frame / clip fps) - multicam start, in `fps` frames. Exact
    for the clips the multicam was built from with MULTICAM_ANGLE_SYNC_TIMECODE; within one frame for
    25/30 fps angles in a 24 fps multicam.
    """
    cfps = float(clip.GetClipProperty("FPS") or fps)
    t = tc_seconds(clip.GetClipProperty("Start TC"), cfps) + source_frame / cfps
    return round((t - tc_seconds(mcam.GetClipProperty("Start TC"), fps)) * fps)


def place_multicam(media_pool, timeline, mcam, track: int, record: int, frames: int, mcam_start: int,
                   props: Optional[Dict] = None, media_type: int = 1):
    """Append `frames` of the multicam from `mcam_start` at `record` (relative) on `track` with an exact
    duration (`clips.append_exact`), then apply Inspector `props`. The item shows the multicam's first
    angle until `set_angles` runs. Returns the TimelineItem or None."""
    n = append_exact(media_pool, timeline, mcam, track, record, frames, mcam_start, media_type=media_type, exact=False)
    if n:
        for k, v in (props or {}).items():
            if v is not None:
                n.SetProperty(k, v)
    return n


def set_angles(resolve, project, timeline, assignments: Sequence, spare_colors: Sequence[str] = SPARE_COLORS) -> Dict:
    """Switch multicam items to the given angles through the menu bar.

    `assignments` is [(timeline_item, angle_number)]. Items are grouped by angle; each group gets a spare
    clip color no item on the timeline uses, is selected with Select Clips > By Clip Color, and gets
    Switch to Angle N. Original colors come back afterwards. Opens the Edit page (the menu item is
    disabled on Deliver and Color). Works with the screen locked. Saves. Returns {angle: count}.
    """
    project.SetCurrentTimeline(timeline)
    resolve.OpenPage("edit")
    used = {x.GetClipColor() for kind in ("video", "audio") for t in range(1, timeline.GetTrackCount(kind) + 1)
            for x in items(timeline, kind, t)}
    free = [c for c in spare_colors if c not in used]
    groups: Dict[int, List] = {}
    for it, angle in assignments:
        groups.setdefault(angle, []).append(it)
    if len(groups) > len(free):
        raise ValueError("not enough spare clip colors for the angle groups")
    out = {}
    time.sleep(0.5)
    for (angle, its), color in zip(groups.items(), free):
        saved = [(x, x.GetClipColor()) for x in its]
        for x in its:
            x.SetClipColor(color)
        ui.select_clips_by_color(color)
        out[angle] = len(its) if ui.switch_multicam_angle(angle) else 0
        ui.deselect_all()
        for x, c in saved:
            x.SetClipColor(c) if c else x.ClearClipColor()
    save(resolve)
    return out


def swap_to_multicam(resolve, project, timeline, mcam, sources: Dict[str, str], tracks: Sequence[int] = (1, 2),
                     keep_names_prefix: str = "B-ROLL") -> List[Dict]:
    """Replace every video item cut from a multicam's source files with the multicam itself, in place.

    `sources` maps a source clip's File Name to its angle name. For each matching item on `tracks`:
    snapshot position, duration, Inspector properties, color and enabled state; delete it; append the
    multicam at the same record frame from `multicam_frame(...)`; restore everything. Video only: audio
    items are separate and stay untouched (check with GetLinkedItems first; a linked audio item would go
    with the delete). Grades on the old items are not carried; grade the angles inside the multicam.
    Returns [{"item", "angle", "start", "dur", "mf"}] ready for `set_angles` (use `angle_numbers`).
    """
    mp = project.GetMediaPool()
    project.SetCurrentTimeline(timeline)
    resolve.OpenPage("edit")
    s = timeline.GetStartFrame()
    log = []
    for tr in tracks:
        for x in items(timeline, "video", tr):
            m = x.GetMediaPoolItem()
            if not m or m.GetClipProperty("File Name") not in sources:
                continue
            snap = {"start": x.GetStart() - s, "dur": x.GetDuration(), "props": {k: x.GetProperty(k) for k in VIDEO_PROPS},
                    "name": x.GetName(), "color": x.GetClipColor(), "enabled": x.GetClipEnabled(),
                    "angle": sources[m.GetClipProperty("File Name")],
                    "mf": multicam_frame(mcam, m, x.GetSourceStartFrame())}
            timeline.DeleteClips([x], False)
            n = place_multicam(mp, timeline, mcam, tr, snap["start"], snap["dur"], snap["mf"], snap["props"])
            if n is None:
                snap["error"] = "append failed"
                log.append(snap)
                continue
            if snap["name"].startswith(keep_names_prefix):
                n.SetName(snap["name"])
            if snap["color"]:
                n.SetClipColor(snap["color"])
            if not snap["enabled"]:
                n.SetClipEnabled(False)
            snap["item"] = n
            log.append(snap)
    save(resolve)
    return log
