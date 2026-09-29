"""Titles and Fusion compositions on the timeline: exact-length inserts, a title fitted to a clip, retrimming."""
from typing import Dict, Optional

from ._util import items, save, tc, timeline_fps, track_locks
from .timelines import refresh_timeline


def _insert_marked(timeline, start: int, duration: int, fps: Optional[int], insert):
    s = timeline.GetStartFrame()
    fps = fps or timeline_fps(timeline)
    timeline.SetMarkInOut(start, start + duration - 1)
    timeline.SetCurrentTimecode(tc(s + start, fps))
    it = insert()
    timeline.ClearMarkInOut()
    return it


def insert_fusion_title(timeline, start: int, duration: int, fps: Optional[int] = None, template: str = "Text+"):
    """Insert a Fusion title of exact length at `start` (frames from the timeline start) on the unlocked track.

    The workaround for the missing duration setter: `SetMarkInOut(start, start + duration - 1)` (relative
    frames), `SetCurrentTimecode` at the absolute start, `InsertFusionTitleIntoTimeline(template)`,
    `ClearMarkInOut`. To land on a chosen track, refresh the timeline (`refresh_timeline`), then lock the
    other tracks (`track_locks`), then insert; without the refresh it goes to the destination-toggle track,
    or fails when that track is locked. The Edit page must be open. Returns the TimelineItem, or False/None when the insert failed.
    """
    return _insert_marked(timeline, start, duration, fps, lambda: timeline.InsertFusionTitleIntoTimeline(template))


def insert_fusion_composition(timeline, start: int, duration: int, fps: Optional[int] = None):
    """Insert an empty native Fusion composition of exact length at `start` on the unlocked track.

    Same marks recipe as `insert_fusion_title` with `InsertFusionCompositionIntoTimeline()`. Returns the
    TimelineItem, or False/None when the insert failed.
    """
    return _insert_marked(timeline, start, duration, fps, timeline.InsertFusionCompositionIntoTimeline)


def title_fitted_to_clip(resolve, project, timeline, clip_track: int, clip_name: str, track: int,
                         text: Optional[str] = None, name: Optional[str] = None, other=None) -> Dict:
    """Insert a Text+ title on `track` spanning exactly one clip's extent (found by name on `clip_track`).

    Locks every other track so the insert lands on `track`; `other` triggers the switch-away refresh.
    `text` goes into the title's StyledText on the Fusion page (there is no Inspector call); `name` names
    the item. Saves. Returns {"title": (name, start, duration), "clip": (name, start, duration), "fits": bool}.
    """
    resolve.OpenPage("edit")
    if other is not None:
        refresh_timeline(project, timeline, other)
    s = timeline.GetStartFrame()
    clip = [x for x in items(timeline, "video", clip_track) if x.GetName() == clip_name][0]
    start, dur = clip.GetStart() - s, clip.GetDuration()
    with track_locks(timeline, track):
        it = insert_fusion_title(timeline, start, dur)
    if name:
        it.SetName(name)
    if text is not None:
        resolve.OpenPage("fusion")
        tools = [x for x in it.GetFusionCompByIndex(1).GetToolList().values() if x.ID == "TextPlus"]
        if tools:
            tools[0].SetInput("StyledText", text)
        resolve.OpenPage("edit")
    save(resolve)
    return {"title": (it.GetName(), it.GetStart() - s, it.GetDuration()), "clip": (clip.GetName(), start, dur),
            "fits": it.GetDuration() == dur}


def retrim_title(resolve, project, timeline, track: int, start: int, duration: int, other=None,
                 comp_dir: Optional[str] = None) -> Dict:
    """Give the title that starts at `start` on `track` a new `duration`, leaving every other title in place.

    The workaround for the missing duration setter, done without disturbing the track: an
    `InsertFusionTitleIntoTimeline` is a ripple on its track, so every title from `start` on is snapshotted
    (name, start, duration, color, and its whole Fusion comp exported to `comp_dir`, a temporary folder by
    default), deleted, the timeline is refreshed (`other`), then the titles are re-inserted in ascending order
    (nothing sits to their right, so nothing ripples) and each comp is imported back, so text and styling come
    back exactly. Saves. Returns {"title": (name, start, end), "restored": n, "misplaced": [(name, wanted, got)]}.
    """
    import os
    import tempfile
    comp_dir = comp_dir or tempfile.mkdtemp(prefix="retrim-")
    resolve.OpenPage("edit")
    s = timeline.GetStartFrame()
    right = [x for x in items(timeline, "video", track) if x.GetStart() - s >= start]
    if not right or right[0].GetStart() - s != start:
        return {"title": None, "restored": 0, "misplaced": [], "error": f"no title starts at {start}"}
    snap = []
    for i, x in enumerate(right):
        path = os.path.join(comp_dir, f"title_{i}.comp")
        snap.append({"name": x.GetName(), "start": x.GetStart() - s, "dur": x.GetDuration(), "color": x.GetClipColor(),
                     "comp": path if x.ExportFusionComp(path, 1) else None})
    snap[0]["dur"] = duration
    timeline.DeleteClips(right, False)
    if other is not None:
        refresh_timeline(project, timeline, other)
        resolve.OpenPage("edit")
    misplaced, placed = [], []
    with track_locks(timeline, track):
        for c in snap:
            it = insert_fusion_title(timeline, c["start"], c["dur"])
            if not it:
                misplaced.append((c["name"], c["start"], None))
                continue
            it.SetName(c["name"])
            if c["color"]:
                it.SetClipColor(c["color"])
            if it.GetStart() - s != c["start"] or it.GetDuration() != c["dur"]:
                misplaced.append((c["name"], c["start"], it.GetStart() - s))
            placed.append((it, c["comp"]))
    resolve.OpenPage("fusion")
    for it, comp in placed:
        if comp:
            it.ImportFusionComp(comp)
    resolve.OpenPage("edit")
    save(resolve)
    head = [q for q in items(timeline, "video", track) if q.GetStart() - s == start]
    title = (head[0].GetName(), start, head[0].GetEnd() - s) if head else None
    return {"title": title, "restored": len(snap) - 1, "misplaced": misplaced}
