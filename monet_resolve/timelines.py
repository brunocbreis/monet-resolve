"""Timelines: map, back up, refresh, park the playhead."""
import time
from typing import Dict

from ._util import items, save


def map_timeline(timeline) -> Dict:
    """Every video track of a timeline with its items and the markers.

    Returns {"tracks": {"V1 <name>": [(name, start, duration, color), ...]}, "markers": {frame: name}}.
    Starts are frames relative to the timeline start.
    """
    s = timeline.GetStartFrame()
    tracks = {}
    for ti in range(1, timeline.GetTrackCount("video") + 1):
        tracks[f"V{ti} {timeline.GetTrackName('video', ti)}"] = [
            (x.GetName(), x.GetStart() - s, x.GetDuration(), x.GetClipColor()) for x in items(timeline, "video", ti)
        ]
    return {"tracks": tracks, "markers": {k: v["name"] for k, v in timeline.GetMarkers().items()}}


def backup_timeline(resolve, project, timeline, backup_name: str, timeline_bin: str = "timelines",
                    backups_bin: str = "backups") -> Dict:
    """Duplicate a timeline under `backup_name` and move the copy into `timeline_bin/backups_bin`.

    `DuplicateTimeline` drops the copy next to the source (in the current bin), so the copy is found in
    `timeline_bin` by name and moved with `MoveClips`; the backups bin is created when missing. Saves.
    Returns {"backup": bool, "moved": MoveClips result or None, "backups": [names in the backups bin]}.
    This is the only undo the API offers: run it before any delete-and-re-append step.
    """
    mp = project.GetMediaPool()
    sub = {f.GetName(): f for f in mp.GetRootFolder().GetSubFolderList()}
    tl = sub[timeline_bin]
    tsub = {f.GetName(): f for f in tl.GetSubFolderList()}
    bk_bin = tsub.get(backups_bin) or mp.AddSubFolder(tl, backups_bin)
    project.SetCurrentTimeline(timeline)
    bk = timeline.DuplicateTimeline(backup_name)
    project.SetCurrentTimeline(timeline)
    c = [x for x in tl.GetClipList() if x.GetName() == backup_name]
    moved = mp.MoveClips(c, bk_bin) if c else None
    save(resolve)
    return {"backup": bool(bk), "moved": moved, "backups": [x.GetName() for x in bk_bin.GetClipList()]}


def place_playhead(resolve, project, timeline, timecode: str) -> Dict:
    """Switch to `timeline`, park the playhead at an absolute `timecode` ('01:00:38:08'), save.

    Returns {"timeline": name, "tc": the timecode read back}.
    """
    project.SetCurrentTimeline(timeline)
    timeline.SetCurrentTimecode(timecode)
    save(resolve)
    return {"timeline": timeline.GetName(), "tc": timeline.GetCurrentTimecode()}


def refresh_timeline(project, timeline, other, pause: float = 1.0) -> None:
    """Switch to `other` and back to `timeline`, sleeping `pause` seconds after each switch.

    Workaround: `Insert*IntoTimeline` returns False on a timeline a script just built or emptied, and
    retries, lock variants, and page switches did not fix it; switching timelines does.
    """
    project.SetCurrentTimeline(other)
    time.sleep(pause)
    project.SetCurrentTimeline(timeline)
    time.sleep(pause)
