"""Assembly: build a cut from a list, close gaps, no-ripple inserts, nesting, GFX swaps.

Nothing in the API moves, trims or splits a timeline item. Every change of position or extent here is
"delete it, re-append the source range at the new record frame", which keeps the media pool link and
loses whatever lived on the item unless restored.
"""
from typing import Dict, List, Optional, Sequence, Tuple

from ._util import clean_name, items, save, tc, timeline_fps, track_locks
from .media import import_file_once

SNAPSHOT_KEYS = ["ZoomX", "ZoomY", "Pan", "Tilt", "AnchorPointX", "AnchorPointY", "RotationAngle", "Opacity",
                 "CropLeft", "CropRight", "CropTop", "CropBottom", "CompositeMode"]


def build_cut_from_list(resolve, project, timeline_name: str, cut: Sequence[Dict], footage_clip, timeline_bin,
                        video_tracks: Sequence[str] = ("A-ROLL", "B-ROLL placeholders"),
                        audio_tracks: Sequence[Tuple[str, str]] = (("stereo", "VO ext mic"), ("stereo", "Camera mic (backup)"))) -> Dict:
    """Build a new timeline from a cut list of source ranges on one footage clip.

    Each `cut` entry is {"id", "label", "src_in", "src_out", "section", "broll", "gap", "jump"}: one
    `AppendToTimeline` of `footage_clip` from src_in to src_out (inclusive) at the running position on V1,
    named "<id> · <label>" (cleaned of ':' and '/'), Green when on camera, Orange and disabled when
    `broll` names a b-roll slot, followed by `gap` empty frames. A Blue marker marks the first entry of each
    `section`, a Red "JUMP CUT" marker each entry with `jump`. Markers are added after the build with the
    measured positions (a 25p clip in a 24p timeline lands as int(n * 0.96) frames).
    The timeline is created in `timeline_bin` (a Folder); `video_tracks` are names for V1.., `audio_tracks`
    are (subtype, name) with the first describing the default A1 (always stereo from `CreateEmptyTimeline`;
    mono A1 needs `backup_timeline` of a timeline with the layout, or a UI track-type change). A2 is disabled.
    Saves. Returns {"placed": [(id, start, duration|"FAILED")], "spans": b-roll spans for
    `titles.text_placeholders`, "sections": {name: start}, "length", "audio_subtypes"}. Worked 2026-09-11.
    """
    mp = project.GetMediaPool()
    root = mp.GetRootFolder()
    resolve.OpenPage("edit")
    mp.SetCurrentFolder(timeline_bin)
    t = mp.CreateEmptyTimeline(timeline_name)
    mp.SetCurrentFolder(root)
    project.SetCurrentTimeline(t)
    s = t.GetStartFrame()
    while t.GetTrackCount("video") < len(video_tracks):
        t.AddTrack("video")
    for i, n in enumerate(video_tracks):
        t.SetTrackName("video", i + 1, n)
    for kind, _ in list(audio_tracks)[1:]:
        t.AddTrack("audio", kind)
    for i, (_, n) in enumerate(audio_tracks):
        t.SetTrackName("audio", i + 1, n)
    pos = 0
    spans: List[Dict] = []
    placed = []
    sections: Dict[str, int] = {}
    for e in cut:
        new = mp.AppendToTimeline([{"mediaPoolItem": footage_clip, "startFrame": e["src_in"], "endFrame": e["src_out"], "trackIndex": 1, "recordFrame": s + pos}])
        if not new:
            placed.append((e["id"], pos, "FAILED"))
            continue
        it = new[0]
        d = it.GetDuration()
        it.SetName(clean_name(f'{e["id"]} · {e["label"]}'))
        if e["broll"]:
            it.SetClipEnabled(False)
            it.SetClipColor("Orange")
            if spans and spans[-1]["text"] == e["broll"] and spans[-1]["end"] == pos:
                spans[-1]["end"] = pos + d + e["gap"]
            else:
                spans.append({"text": e["broll"], "start": pos, "end": pos + d + e["gap"]})
        else:
            it.SetClipColor("Green")
            if e["gap"]:
                spans.append({"text": "(space for b-roll)", "start": pos + d, "end": pos + d + e["gap"]})
        sections.setdefault(e["section"], pos)
        if e.get("jump"):
            t.AddMarker(pos, "Red", "JUMP CUT", f'{e["id"]} - trimmed pause', 1)
        placed.append((e["id"], pos, d))
        pos += d + e["gap"]
    for name, f in sections.items():
        t.AddMarker(f, "Blue", name, "", 1)
    if len(audio_tracks) > 1:
        t.SetTrackEnable("audio", 2, False)
    save(resolve)
    return {"placed": placed, "spans": spans, "sections": sections, "length": pos,
            "audio_subtypes": [t.GetTrackSubType("audio", i + 1) for i in range(t.GetTrackCount("audio"))]}


def close_gap_ripple(resolve, project, timeline, gap_start: int, gap_len: int, dummy_clip, video_track: int = 1,
                     lock_video: Sequence[int] = (), source_fps_ratio: float = 25 / 24) -> Dict:
    """Close a gap (or remove an empty range): fill it with a dummy clip and ripple-delete the dummy.

    The API has no gap selection, so `dummy_clip` (any MediaPoolItem) is appended on `video_track` from
    source frame 0 for `int(gap_len * source_fps_ratio + 0.5)` frames at `gap_start`, then the dummy and
    its linked audio are removed with `DeleteClips(items, True)`: everything after the gap on unlocked
    tracks moves left by the gap length. Pass the video track indexes that must stay put in `lock_video`.
    Refuses when the range is occupied on `video_track` and returns {"error", "clips"} instead. Saves.
    Returns {"dummy_len", "expected_shift", "first_clip_before_after"} for checking the shift.
    Status: assembled on 2026-09-11 from recipes that ran piecemeal; not yet run as a whole.
    """
    mp = project.GetMediaPool()
    project.SetCurrentTimeline(timeline)
    s = timeline.GetStartFrame()
    before = [(x.GetName(), x.GetStart() - s) for x in items(timeline, "video", video_track) if x.GetStart() - s > gap_start]
    occupied = [x.GetName() for x in items(timeline, "video", video_track) if x.GetStart() - s < gap_start + gap_len and x.GetEnd() - s > gap_start]
    if occupied:
        return {"error": "range is not empty on the video track", "clips": occupied}
    for ti in lock_video:
        timeline.SetTrackLock("video", ti, True)
    mp.AppendToTimeline([{"mediaPoolItem": dummy_clip, "startFrame": 0, "endFrame": int(gap_len * source_fps_ratio + 0.5), "trackIndex": video_track, "recordFrame": s + gap_start}])
    dummy = [x for x in items(timeline, "video", video_track) if x.GetStart() - s == gap_start]
    dummy += [x for ai in range(1, timeline.GetTrackCount("audio") + 1) for x in items(timeline, "audio", ai) if x.GetStart() - s == gap_start and x.GetType() == "audio"]
    dlen = dummy[0].GetDuration() if dummy else 0
    timeline.DeleteClips(dummy, True)
    for ti in lock_video:
        timeline.SetTrackLock("video", ti, False)
    after = [(x.GetName(), x.GetStart() - s) for x in items(timeline, "video", video_track) if x.GetStart() - s > gap_start - 1]
    save(resolve)
    return {"dummy_len": dlen, "expected_shift": gap_len, "first_clip_before_after": (before[:1], after[:1])}


def find_destination_track(timeline, fps: Optional[int] = None) -> int:
    """Find which video track holds the destination toggle with a throwaway Fusion composition insert at the tail.

    Inserts a 10-frame composition 10 frames after the last item on any video track, finds the track it
    landed on by `GetUniqueId`, deletes it without ripple, clears the marks. The Edit page must be open.
    Returns the video track index. Worked 2026-09-11.
    """
    s = timeline.GetStartFrame()
    fps = fps or timeline_fps(timeline)
    nt = timeline.GetTrackCount("video")
    end = max(x.GetEnd() for ti in range(1, nt + 1) for x in items(timeline, "video", ti)) - s
    timeline.SetMarkInOut(end + 10, end + 19)
    timeline.SetCurrentTimecode(tc(s + end + 10, fps))
    p = timeline.InsertFusionCompositionIntoTimeline()
    target = [ti for ti in range(1, nt + 1) if any(x.GetUniqueId() == p.GetUniqueId() for x in items(timeline, "video", ti))][0]
    timeline.DeleteClips([p], False)
    timeline.ClearMarkInOut()
    return target


def insert_fusion_comp_at(resolve, project, timeline, track: int, start: int, duration: int, name: str,
                          color: str = "Violet", comp_path: Optional[str] = None, snapshot_dir: str = "/tmp") -> Dict:
    """Insert a native Fusion composition of exact length at `start` on `track` without rippling what follows.

    Steps: probe the destination toggle (`find_destination_track`) and stop with an error when it is on
    another track; refuse when a retimed clip (Speed not 100) sits at or right of `start` on the track,
    since `AppendToTimeline` cannot recreate it; snapshot every plain clip from `start` on (pool item,
    source range, record frame, name, color, SNAPSHOT_KEYS properties, comp exported to `snapshot_dir`);
    lock every other video track and all audio; `DeleteClips` those items (no ripple); insert with the
    marks recipe; re-append each snapshot at its original record frame, restore properties, color, name
    and comp; verify durations; name and color the new item; optionally `ImportFusionComp(comp_path)`.
    Items without a media pool item (other Fusion compositions) cannot be re-appended and are skipped.
    Saves. Returns {"inserted": (name, start, duration), "restored": [(name, duration_ok|reason)]} or
    {"error", ...}. Status: the pattern ran piecemeal on 2026-09-11 and 2026-09-12; not yet run as a whole.
    """
    mp = project.GetMediaPool()
    project.SetCurrentTimeline(timeline)
    resolve.OpenPage("edit")
    s = timeline.GetStartFrame()
    fps = timeline_fps(timeline)
    target = find_destination_track(timeline, fps)
    if target != track:
        return {"error": f"destination toggle is on V{target}, not V{track}: set it in the UI and rerun"}
    right = [x for x in items(timeline, "video", track) if x.GetStart() - s >= start]
    retimed = [x.GetName() for x in right if x.GetProperty("Speed") not in (None, 100, 100.0)]
    if retimed:
        return {"error": "retimed clips to the right cannot be restored by script", "clips": retimed}
    snap = []
    for x in right:
        comp = None
        if x.GetFusionCompCount():
            path = f"{snapshot_dir}/restore_{x.GetUniqueId()}.comp"
            comp = path if x.ExportFusionComp(path, 1) else None
        snap.append({"mpi": x.GetMediaPoolItem(), "start": x.GetStart(), "dur": x.GetDuration(),
                     "src": (x.GetSourceStartFrame(), x.GetSourceEndFrame()), "name": x.GetName(), "color": x.GetClipColor(),
                     "props": {k: x.GetProperty(k) for k in SNAPSHOT_KEYS}, "comp": comp})
    restored = []
    with track_locks(timeline, track):
        if right:
            timeline.DeleteClips(right, False)
        timeline.SetMarkInOut(start, start + duration - 1)
        timeline.SetCurrentTimecode(tc(s + start, fps))
        it = timeline.InsertFusionCompositionIntoTimeline()
        timeline.ClearMarkInOut()
        for c in snap:
            if c["mpi"] is None:
                restored.append((c["name"], "SKIPPED: no media pool item (Fusion composition)"))
                continue
            mp.AppendToTimeline([{"mediaPoolItem": c["mpi"], "startFrame": c["src"][0], "endFrame": c["src"][1], "trackIndex": track, "recordFrame": c["start"], "mediaType": 1}])
            x = [y for y in items(timeline, "video", track) if y.GetStart() == c["start"]][0]
            for k, v in c["props"].items():
                if v is not None:
                    x.SetProperty(k, v)
            x.SetClipColor(c["color"])
            x.SetName(c["name"])
            if c["comp"]:
                resolve.OpenPage("fusion")
                x.ImportFusionComp(c["comp"])
                resolve.OpenPage("edit")
            restored.append((c["name"], x.GetDuration() == c["dur"]))
    it.SetName(name)
    it.SetClipColor(color)
    if comp_path:
        resolve.OpenPage("fusion")
        it.ImportFusionComp(comp_path)
        resolve.OpenPage("edit")
    save(resolve)
    return {"inserted": (it.GetName(), it.GetStart() - s, it.GetDuration()), "restored": restored}


def nest_timeline_over_placeholder(resolve, project, cut, nested_item, track: int, placeholder_start: int,
                                   placeholder_track: int, track_name: Optional[str] = None, clear_track: bool = False) -> Dict:
    """Nest a timeline into `cut` on `track`, at the record frame of a placeholder clip and sized to it.

    `nested_item` is the timeline's MediaPoolItem (find it in its bin with `media.find_clip`, or
    `Timeline.GetMediaPoolItem()`). The placeholder is the item on `placeholder_track` that starts at
    `placeholder_start` (frames from the cut start). Video tracks are added until `track` exists and it is
    renamed when `track_name` is given. `clear_track=True` deletes every item already on `track` first
    (destructive). Appends with `endFrame = placeholder duration` (nested timelines take n where media clips
    take n - 1). Saves. Returns {"placeholder": (name, duration), "nested": [(name, start, duration)]}.
    Worked 2026-09-11.
    """
    mp = project.GetMediaPool()
    s = cut.GetStartFrame()
    project.SetCurrentTimeline(cut)
    while cut.GetTrackCount("video") < track:
        cut.AddTrack("video")
    if track_name:
        cut.SetTrackName("video", track, track_name)
    slot = [x for x in items(cut, "video", placeholder_track) if x.GetStart() - s == placeholder_start][0]
    if clear_track:
        for x in items(cut, "video", track):
            cut.DeleteClips([x], False)
    mp.AppendToTimeline([{"mediaPoolItem": nested_item, "startFrame": 0, "endFrame": slot.GetDuration(), "trackIndex": track, "recordFrame": s + placeholder_start, "mediaType": 1}])
    save(resolve)
    return {"placeholder": (slot.GetName(), slot.GetDuration()), "nested": [(x.GetName(), x.GetStart() - s, x.GetDuration()) for x in items(cut, "video", track)]}


def swap_gfx_clip(resolve, project, path: str, folder, gfx_timeline, frames: int, delete_old_versions: bool = False) -> Dict:
    """Replace the clip on a GFX timeline with a newly rendered file; every cut nesting that timeline follows.

    Imports `path` into `folder` unless a clip with that 'File Path' is already there, deletes every item on
    V1 of `gfx_timeline` (no ripple), appends the clip from frame 0 to `frames` at the timeline start.
    `delete_old_versions=True` then deletes every other clip in `folder` from the media pool (destructive).
    For a same-length re-render, `media.replace_clip_file` is the lighter route. Saves.
    Returns {"on_timeline": [(name, duration)], "bin": [clip names]}. Worked 2026-09-11.
    """
    mp = project.GetMediaPool()
    clip = import_file_once(mp, folder, path)
    project.SetCurrentTimeline(gfx_timeline)
    for it in items(gfx_timeline, "video", 1):
        gfx_timeline.DeleteClips([it], False)
    mp.AppendToTimeline([{"mediaPoolItem": clip, "startFrame": 0, "endFrame": frames, "trackIndex": 1, "recordFrame": gfx_timeline.GetStartFrame(), "mediaType": 1}])
    if delete_old_versions:
        old = [c for c in folder.GetClipList() if c.GetName() != clip.GetName()]
        if old:
            mp.DeleteClips(old)
    save(resolve)
    return {"on_timeline": [(i.GetName(), i.GetDuration()) for i in items(gfx_timeline, "video", 1)], "bin": [c.GetName() for c in folder.GetClipList()]}
