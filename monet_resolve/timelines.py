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

    `DuplicateTimeline` drops the copy next to the source, so the copy's media pool item is moved with
    `MoveClips`; the backups bin is created when missing. Saves.
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
    moved = mp.MoveClips([bk.GetMediaPoolItem()], bk_bin) if bk else None
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


def clear_media_pool_selection(media_pool) -> bool:
    """Leave nothing selected in the media pool. Returns True when the selection reads empty afterward.

    No call deselects; changing the current folder and coming back does. A selected clip or timeline acts as
    the source of the next insert edit, and then a title or composition insert follows the destination
    toggle instead of the track locks (see `refresh_timeline`). A root folder without subfolders gets a
    temporary one for the switch.
    """
    if not media_pool.GetSelectedClips():
        return True
    here, root = media_pool.GetCurrentFolder(), media_pool.GetRootFolder()
    temp = None
    if here.GetUniqueId() != root.GetUniqueId():
        away = root
    else:
        subs = root.GetSubFolderList() or []
        away = subs[0] if subs else None
        if away is None:
            away = temp = media_pool.AddSubFolder(root, "selection (temporary)")
    media_pool.SetCurrentFolder(away)
    media_pool.SetCurrentFolder(here)
    if temp is not None:
        media_pool.DeleteFolders([temp])
    return not media_pool.GetSelectedClips()


def refresh_timeline(project, timeline, other=None, pause: float = 1.0) -> None:
    """Clear the media pool selection, then switch to another timeline and back to `timeline`, sleeping
    `pause` seconds after each switch.

    These two steps are what make track locks steer a title or composition insert onto the one unlocked
    video track. Both are needed: with a clip or timeline selected in the media pool the insert goes to the
    destination-toggle track (None when that track is locked), and so it does without the timeline switch.
    The order of locking and switching does not matter; a page switch does not replace the timeline switch.

    `other` is the timeline to switch to; left out, the first other timeline in the project is used, and a
    project with a single timeline gets a temporary empty one that is deleted afterward.

    The switch is also the workaround for `Insert*IntoTimeline` returning False on a timeline a script
    just built or emptied.
    """
    clear_media_pool_selection(project.GetMediaPool())
    temp = None
    if other is None:
        uid = timeline.GetUniqueId()
        others = [t for t in (project.GetTimelineByIndex(i) for i in range(1, project.GetTimelineCount() + 1))
                  if t and t.GetUniqueId() != uid]
        other = others[0] if others else None
        if other is None:
            other = temp = project.GetMediaPool().CreateEmptyTimeline("refresh (temporary)")
    project.SetCurrentTimeline(other)
    time.sleep(pause)
    project.SetCurrentTimeline(timeline)
    time.sleep(pause)
    if temp is not None:
        project.GetMediaPool().DeleteTimelines([temp])
