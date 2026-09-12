"""GFX timelines: rendered b-roll files as nested timelines in the cut."""
import time
from typing import Dict

from ._util import items, list_timelines, save, track_locks
from .media import import_file_once


def create_gfx_timeline_from_clip(resolve, project, path: str, gfx_bin, timeline_bin, gfx_timeline: str, cut,
                                  track: int, record: int, frames: int) -> Dict:
    """Import a rendered GFX file, make a timeline from it, and nest that timeline on a track of the cut.

    `gfx_bin` and `timeline_bin` are Folders. The file is imported into `gfx_bin` unless a clip with that
    'File Path' exists. A timeline named `gfx_timeline` is created in `timeline_bin` with
    `CreateTimelineFromClips` when no timeline has that name. Then on `cut`: video tracks are added until
    `track` exists, every other video track and all audio are locked, an existing nested item with the
    timeline's name on `track` is deleted (no ripple), and the timeline's pool item is appended from
    frame 0 to `frames` at `record` (frames from the cut start). Re-render later with
    `media.replace_clip_file` or `assembly.swap_gfx_clip`. Saves.
    Returns {"clip", "frames_in_file", "timeline_created", "appended", "track": [(name, start, duration)]}.
    Worked 2026-09-11.
    """
    mp = project.GetMediaPool()
    root = mp.GetRootFolder()
    clip = import_file_once(mp, gfx_bin, path)
    tls = list_timelines(project)
    made = None
    if gfx_timeline not in [x.GetName() for x in tls]:
        mp.SetCurrentFolder(timeline_bin)
        made = mp.CreateTimelineFromClips(gfx_timeline, [clip])
    mp.SetCurrentFolder(root)
    project.SetCurrentTimeline(cut)
    s = cut.GetStartFrame()
    time.sleep(1)
    tl_item = [c for c in timeline_bin.GetClipList() if c.GetName() == gfx_timeline][0]
    while cut.GetTrackCount("video") < track:
        cut.AddTrack("video")
    with track_locks(cut, track):
        old = [x for x in items(cut, "video", track) if x.GetName() == gfx_timeline]
        if old:
            cut.DeleteClips(old, False)
        ok = mp.AppendToTimeline([{"mediaPoolItem": tl_item, "startFrame": 0, "endFrame": frames, "trackIndex": track, "recordFrame": s + record}])
    save(resolve)
    return {"clip": clip.GetName(), "frames_in_file": clip.GetClipProperty("Frames"), "timeline_created": bool(made), "appended": bool(ok),
            "track": [(x.GetName(), x.GetStart() - s, x.GetDuration()) for x in items(cut, "video", track)]}
