"""Assembly: build a cut from a list, close gaps, no-ripple inserts, nesting, GFX swaps.

Nothing in the API moves, trims or splits a timeline item. Every change of position or extent here is
"delete it, re-append the source range at the new record frame", which keeps the media pool link and
loses whatever lived on the item unless restored.
"""
from typing import Dict, List, Optional, Sequence, Tuple

from ._util import VIDEO_PROPS, add_tracks_until, append_exact, clean_name, items, save, source_frames, track_locks
from .edit import freeze_item
from .media import import_file_once
from .timelines import refresh_timeline
from .titles import insert_fusion_composition, insert_fusion_title


def build_cut_from_list(resolve, project, timeline_name: str, cut: Sequence[Dict], footage_clip, timeline_bin,
                        video_tracks: Sequence[str] = ("A-ROLL", "B-ROLL placeholders"),
                        audio_tracks: Sequence[Tuple[str, str]] = (("stereo", "VO ext mic"), ("stereo", "Camera mic (backup)"))) -> Dict:
    """Build a new timeline from a cut list of source ranges on one footage clip.

    Each `cut` entry is {"id", "label", "src_in", "src_out", "section", "broll", "gap", "jump"}: one
    `AppendToTimeline` of `footage_clip` from src_in to src_out (exclusive) at the running position on V1,
    named "<id> · <label>" (cleaned of ':' and '/'), Green when on camera, Orange and disabled when
    `broll` names a b-roll slot, followed by `gap` empty frames. A Blue marker marks the first entry of each
    `section`, a Red "JUMP CUT" marker each entry with `jump`; when both fall on one frame, the section marker
    stays and its note says "JUMP CUT". Markers are added after the build with the measured positions (a 25p
    clip in a 24p timeline lands as int(n * 0.96) frames).
    The timeline is created in `timeline_bin` (a Folder); `video_tracks` are names for V1.., `audio_tracks`
    are (subtype, name) with the first describing the default A1 (always stereo from `CreateEmptyTimeline`;
    mono A1 needs `backup_timeline` of a timeline with the layout, or a UI track-type change). A2 is disabled.
    Saves. Returns {"placed": [(id, start, duration|"FAILED")], "spans": b-roll spans for
    `titles.text_placeholders`, "sections": {name: start}, "length", "audio_subtypes"}.
    """
    mp = project.GetMediaPool()
    root = mp.GetRootFolder()
    resolve.OpenPage("edit")
    mp.SetCurrentFolder(timeline_bin)
    t = mp.CreateEmptyTimeline(timeline_name)
    mp.SetCurrentFolder(root)
    project.SetCurrentTimeline(t)
    s = t.GetStartFrame()
    add_tracks_until(t, "video", len(video_tracks))
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
    jumps: Dict[int, str] = {}
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
            jumps[pos] = f'{e["id"]} - trimmed pause'
        placed.append((e["id"], pos, d))
        pos += d + e["gap"]
    for name, f in sections.items():
        t.AddMarker(f, "Blue", name, f"JUMP CUT: {jumps.pop(f)}" if f in jumps else "", 1)
    for f, note in jumps.items():
        t.AddMarker(f, "Red", "JUMP CUT", note, 1)
    if len(audio_tracks) > 1:
        t.SetTrackEnable("audio", 2, False)
    save(resolve)
    return {"placed": placed, "spans": spans, "sections": sections, "length": pos,
            "audio_subtypes": [t.GetTrackSubType("audio", i + 1) for i in range(t.GetTrackCount("audio"))]}


def close_gap_ripple(resolve, project, timeline, gap_start: int, gap_len: int, dummy_clip,
                     tracks: Optional[Sequence[Tuple[str, int]]] = None) -> Dict:
    """Close an empty stretch on the chosen tracks: everything after it on those tracks moves left by `gap_len`.

    `tracks` lists the tracks that close, as ("video" | "audio", index) pairs, in any combination
    (`[("video", 1), ("audio", 1)]` closes the dialogue and leaves V2, V3 and the music in place); None means
    every track. Every other track is locked for the ripple and gets its lock state back afterward.

    The API has no gap selection, so `dummy_clip` (any MediaPoolItem) is appended into the gap on the first
    chosen track with an exact length (`append_exact`) and ripple-deleted with `DeleteClips([dummy], True)`.
    Refuses, changing nothing, when a chosen track has any item inside the gap (a music cue running across it
    included: leave that track out to keep it playing) and returns {"error", "occupied": [(kind, index, name)]}.
    The locks are read back before the delete, and the tracks left out are compared before and after it; either
    failing returns an "error". Saves. Returns {"closed": tracks, "moved": items that moved, "stayed": items after
    the gap that stayed}.
    """
    project.SetCurrentTimeline(timeline)
    s = timeline.GetStartFrame()
    every = [(k, i) for k in ("video", "audio") for i in range(1, timeline.GetTrackCount(k) + 1)]
    chosen = list(every if tracks is None else tracks)
    unknown = [t for t in chosen if t not in every]
    if not chosen or unknown:
        return {"error": "no such track" if unknown else "no tracks chosen", "tracks": unknown}
    occupied = [(k, i, x.GetName()) for k, i in chosen for x in items(timeline, k, i)
                if x.GetStart() - s < gap_start + gap_len and x.GetEnd() - s > gap_start]
    if occupied:
        return {"error": "the gap is not empty on a chosen track", "occupied": occupied}

    def positions(tracks):
        return {(k, i, x.GetName(), x.GetStart() - s, x.GetDuration()) for k, i in tracks for x in items(timeline, k, i)}

    others = [t for t in every if t not in chosen]
    kept = positions(others)
    before = sorted(p for p in positions(chosen) if p[3] >= gap_start + gap_len)
    locks = {t: timeline.GetIsTrackLocked(*t) for t in every}
    try:
        for t in every:
            timeline.SetTrackLock(*t, t not in chosen)
        if any(timeline.GetIsTrackLocked(*t) != (t not in chosen) for t in every):
            return {"error": "track locks did not take; nothing was changed"}
        kind, index = chosen[0]
        dummy = append_exact(project.GetMediaPool(), timeline, dummy_clip, index, gap_start, gap_len, 0,
                             media_type=1 if kind == "video" else 2, exact=False)
        if not dummy:
            return {"error": "could not place a dummy clip of the gap's length"}
        timeline.DeleteClips([dummy], True)
    finally:
        for t, locked in locks.items():
            timeline.SetTrackLock(*t, locked)
    now = positions(chosen)
    out = {"closed": chosen,
           "moved": [p[:4] for p in before if (p[0], p[1], p[2], p[3] - gap_len, p[4]) in now],
           "stayed": [p[:4] for p in before if p in now]}
    changed = sorted(kept ^ positions(others))
    if changed:
        out["error"] = "tracks that were not chosen changed; restore from a backup"
        out["changed"] = changed
    save(resolve)
    return out


def find_destination_track(timeline, fps: Optional[int] = None) -> int:
    """Find which video track holds the destination toggle with a throwaway Fusion composition insert at the tail.

    Inserts a 10-frame composition 10 frames after the last item on any video track, finds the track it
    landed on by `GetUniqueId`, deletes it without ripple, clears the marks. The Edit page must be open.
    Returns the video track index.
    """
    s = timeline.GetStartFrame()
    nt = timeline.GetTrackCount("video")
    end = max(x.GetEnd() for ti in range(1, nt + 1) for x in items(timeline, "video", ti)) - s
    p = insert_fusion_composition(timeline, end + 10, 10, fps)
    target = [ti for ti in range(1, nt + 1) if any(x.GetUniqueId() == p.GetUniqueId() for x in items(timeline, "video", ti))][0]
    timeline.DeleteClips([p], False)
    return target


def insert_fusion_comp_at(resolve, project, timeline, track: int, start: int, duration: int, name: str,
                          color: str = "Violet", comp_path: Optional[str] = None, snapshot_dir: str = "/tmp") -> Dict:
    """Insert a native Fusion composition of exact length at `start` on `track` without rippling what follows.

    Steps: probe the destination toggle (`find_destination_track`) and stop with an error when it is on
    another track; refuse when a retimed clip (Speed not 100) sits at or right of `start` on the track,
    since `AppendToTimeline` cannot recreate it; snapshot every plain clip from `start` on (pool item,
    source range, record frame, name, color, VIDEO_PROPS properties, comp exported to `snapshot_dir`);
    lock every other video track and all audio; `DeleteClips` those items (no ripple); insert with the
    marks recipe; re-append each snapshot at its original record frame, restore properties, color, name
    and comp; verify durations; name and color the new item; optionally `ImportFusionComp(comp_path)`.
    Items without a media pool item (other Fusion compositions) cannot be re-appended and are skipped.
    Saves. Returns {"inserted": (name, start, duration), "restored": [(name, duration_ok|reason)]} or
    {"error", ...}.
    """
    mp = project.GetMediaPool()
    project.SetCurrentTimeline(timeline)
    resolve.OpenPage("edit")
    s = timeline.GetStartFrame()
    target = find_destination_track(timeline)
    if target != track:
        return {"error": f"destination toggle is on V{target}, not V{track}: set it in the UI and rerun"}
    right = [x for x in items(timeline, "video", track) if x.GetStart() - s >= start]
    retimed = [x.GetName() for x in right if (x.GetSpeed() or {}).get("Percentage", 100.0) != 100.0]
    if retimed:
        return {"error": "retimed clips to the right cannot be restored by script", "clips": retimed}
    snap = []
    for x in right:
        comp = None
        if x.GetFusionCompCount():
            path = f"{snapshot_dir}/restore_{x.GetUniqueId()}.comp"
            comp = path if x.ExportFusionComp(path, 1) else None
        snap.append({"mpi": x.GetMediaPoolItem(), "start": x.GetStart(), "dur": x.GetDuration(),
                     "src": source_frames(x), "name": x.GetName(), "color": x.GetClipColor(),
                     "props": {k: x.GetProperty(k) for k in VIDEO_PROPS}, "comp": comp})
    restored = []
    with track_locks(timeline, track):
        if right:
            timeline.DeleteClips(right, False)
        it = insert_fusion_composition(timeline, start, duration)
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
    (destructive). Appends from frame 0 with `endFrame = placeholder duration` (`endFrame` is exclusive). Saves. Returns {"placeholder": (name, duration), "nested": [(name, start, duration)]}.
    """
    mp = project.GetMediaPool()
    s = cut.GetStartFrame()
    project.SetCurrentTimeline(cut)
    add_tracks_until(cut, "video", track)
    if track_name:
        cut.SetTrackName("video", track, track_name)
    slot = [x for x in items(cut, "video", placeholder_track) if x.GetStart() - s == placeholder_start][0]
    if clear_track:
        old = items(cut, "video", track)
        if old:
            cut.DeleteClips(old, False)
    mp.AppendToTimeline([{"mediaPoolItem": nested_item, "startFrame": 0, "endFrame": slot.GetDuration(), "trackIndex": track, "recordFrame": s + placeholder_start, "mediaType": 1}])
    save(resolve)
    return {"placeholder": (slot.GetName(), slot.GetDuration()), "nested": [(x.GetName(), x.GetStart() - s, x.GetDuration()) for x in items(cut, "video", track)]}


def swap_gfx_clip(resolve, project, path: str, folder, gfx_timeline, frames: int, delete_old_versions: bool = False) -> Dict:
    """Replace the clip on a GFX timeline with a newly rendered file; every cut nesting that timeline follows.

    Imports `path` into `folder` unless a clip with that 'File Path' is already there, deletes every item on
    V1 of `gfx_timeline` (no ripple), appends the clip from frame 0 to `frames` at the timeline start.
    `delete_old_versions=True` then deletes every other clip in `folder` from the media pool (destructive).
    For a same-length re-render, `media.replace_clip_file` is the lighter route. Saves.
    Returns {"on_timeline": [(name, duration)], "bin": [clip names]}.
    """
    mp = project.GetMediaPool()
    clip = import_file_once(mp, folder, path)
    project.SetCurrentTimeline(gfx_timeline)
    old = items(gfx_timeline, "video", 1)
    if old:
        gfx_timeline.DeleteClips(old, False)
    mp.AppendToTimeline([{"mediaPoolItem": clip, "startFrame": 0, "endFrame": frames, "trackIndex": 1, "recordFrame": gfx_timeline.GetStartFrame(), "mediaType": 1}])
    if delete_old_versions:
        old = [c for c in folder.GetClipList() if c.GetName() != clip.GetName()]
        if old:
            mp.DeleteClips(old)
    save(resolve)
    return {"on_timeline": [(i.GetName(), i.GetDuration()) for i in items(gfx_timeline, "video", 1)], "bin": [c.GetName() for c in folder.GetClipList()]}


def place_clips_on_track(resolve, project, timeline, clip, track: int, clips, zoom: Optional[float] = None,
                         color: Optional[str] = None, track_name: Optional[str] = None) -> List[Tuple[str, int, int, int, int]]:
    """Append source ranges of one media pool clip onto `track` at explicit record frames, video only.

    `clips` is [(name, record_start, source_in, source_out)] with `record_start` relative to the timeline
    start and the source range in the clip's own frames. A 60p clip on a 24p timeline lands
    `int((source_out - source_in) * 0.4)` frames long, so size the source range as `timeline_frames * 2.5`
    (the 25p rule is `int(n * 0.96)`); the item's source end then sits a frame or two short of `source_out`. Video tracks are added until `track` exists and it is renamed when `track_name` is
    given; each item is named with `SetName` (':' and '/' fail silently, `clean_name` swaps them), coloured,
    and given `ZoomX`/`ZoomY` when `zoom` is set (1.155 fills the 4K width with a 3548x2304 screen
    recording that "scaleToFit" would otherwise pillarbox). `mediaType: 1` keeps the clip's audio off the
    timeline. Saves. Returns [(name, start, duration, source_start, source_end)].
    """
    mp = project.GetMediaPool()
    s = timeline.GetStartFrame()
    project.SetCurrentTimeline(timeline)
    add_tracks_until(timeline, "video", track)
    if track_name:
        timeline.SetTrackName("video", track, track_name)
    out = []
    for name, rec, a, b in clips:
        r = mp.AppendToTimeline([{"mediaPoolItem": clip, "startFrame": a, "endFrame": b, "trackIndex": track, "recordFrame": s + rec, "mediaType": 1}])
        it = r[0] if r else None
        if not it:
            out.append((name, rec, 0, a, b))
            continue
        it.SetName(clean_name(name))
        if color:
            it.SetClipColor(color)
        if zoom:
            it.SetProperty("ZoomX", zoom)
            it.SetProperty("ZoomY", zoom)
        out.append((it.GetName(), it.GetStart() - s, it.GetDuration(), *source_frames(it)))
    save(resolve)
    return out


def place_shots(resolve, project, timeline, track: int, shots: Sequence[Dict], color: Optional[str] = "Navy",
                fps: Optional[int] = None) -> List[Dict]:
    """Append a shot list of source ranges onto `track`: wide shots, close-ups (zoom, pan, tilt) and freeze frames.

    Each shot is a dict: `name`, `record` (frame relative to the timeline start), `clip` (MediaPoolItem),
    `src_in`, `src_out` (the clip's own frames; a 60p range lands `int(n * 0.4)` frames on a 24p timeline),
    optional `props` (Edit-page properties for `SetProperties`, e.g. ZoomX/ZoomY/Pan/Tilt) and optional
    `freeze` (True freezes the shot on its first source frame with `edit.freeze_item`, duration unchanged).
    Close-up framing: with the image fitted to the frame at scale f (f = 2160 / source height for a wider-
    than-16:9 source) and zoom z, a source point (cx, cy) is centred with `Pan = -(cx - w/2) * f * z` and
    `Tilt = (cy - h/2) * f * z` (Tilt positive moves the image up). Video only (`mediaType: 1`), names via
    `clean_name`, color `color`. Saves. Returns [{"name", "start", "duration", "source", "frozen"}].
    """
    mp = project.GetMediaPool()
    s = timeline.GetStartFrame()
    project.SetCurrentTimeline(timeline)
    out = []
    for sh in shots:
        r = mp.AppendToTimeline([{"mediaPoolItem": sh["clip"], "startFrame": sh["src_in"], "endFrame": sh["src_out"],
                                  "trackIndex": track, "recordFrame": s + sh["record"], "mediaType": 1}])
        it = r[0] if r else None
        if not it:
            out.append({"name": sh["name"], "start": sh["record"], "duration": 0, "source": None, "frozen": None})
            continue
        it.SetName(clean_name(sh["name"]))
        if color:
            it.SetClipColor(color)
        if sh.get("props"):
            it.SetProperties(sh["props"])
        fz = freeze_item(timeline, it, fps=fps)["ok"] if sh.get("freeze") else None
        out.append({"name": it.GetName(), "start": it.GetStart() - s, "duration": it.GetDuration(),
                    "source": source_frames(it), "frozen": fz})
    save(resolve)
    return out


def insert_gap_ripple(resolve, project, timeline, at: int, frames: int, other=None, fps: Optional[int] = None) -> Dict:
    """Open `frames` of empty space at `at` (relative) on every track, moving everything after it later.

    The inverse of `close_gap_ripple`. The API has no insert-gap call, but `InsertFusionTitleIntoTimeline`
    is a true insert edit: with every video and audio track unlocked it ripples all of them (with the other
    tracks locked it ripples only its own). So: unlock everything,
    insert a `frames`-long Text+ at `at` on the destination track, delete it without ripple. Clips that
    span `at` on other tracks (a music cue) are split there with an empty stretch between the halves; re-lay
    them afterwards. Grades and comps stay on the moved items. Titles need a loaded timeline: pass `other`
    to refresh first. Saves. Returns {"inserted_on": (track type, index), "end_before", "end_after"}.
    """
    project.SetCurrentTimeline(timeline)
    if other is not None:
        refresh_timeline(project, timeline, other)
    resolve.OpenPage("edit")
    s = timeline.GetStartFrame()
    end_before = timeline.GetEndFrame() - s
    for i in range(1, timeline.GetTrackCount("video") + 1):
        timeline.SetTrackLock("video", i, False)
    for i in range(1, timeline.GetTrackCount("audio") + 1):
        timeline.SetTrackLock("audio", i, False)
    it = insert_fusion_title(timeline, at, frames, fps)
    where = it.GetTrackTypeAndIndex() if it else None
    if it:
        timeline.DeleteClips([it], False)
    save(resolve)
    return {"inserted_on": where, "end_before": end_before, "end_after": timeline.GetEndFrame() - s}


def _place_range(mp, timeline, src: Dict, a: float, b: float, record: int, track: int, media_type: int,
                 tl_fps: float = 24.0, frames: Optional[int] = None):
    """Append the session range a..b (seconds) of one source at `record` (absolute) on `track`, `frames` long.

    `src` = {"clip", "offset" (session seconds at source frame 0), "fps"}. The source range is sized so the item
    lands exactly `frames` timeline frames (default round((b - a) * tl_fps)); a rate-mapped append can land one
    frame off, so the end frame is nudged and the item re-appended until the duration matches (three retries,
    the last one kept as is). Returns the TimelineItem or None.
    """
    n = frames if frames is not None else int(round((b - a) * tl_fps))
    f = float(src["fps"])
    sin = int(round((a - src["offset"]) * f))
    send = sin + int(round(n * f / tl_fps)) - 1
    for attempt in range(4):
        new = mp.AppendToTimeline([{"mediaPoolItem": src["clip"], "startFrame": max(sin, 0), "endFrame": send,
                                    "trackIndex": track, "recordFrame": record, "mediaType": media_type}])
        it = new[0] if new else None
        if not it or it.GetDuration() == n or attempt == 3:
            return it
        d = it.GetDuration()
        timeline.DeleteClips([it], False)
        send += n - d


def build_synced_cut(resolve, project, timeline_name: str, sources: Dict[str, Dict], segments: Sequence[Dict],
                     timeline_bin=None, video_tracks: Sequence[str] = ("A-ROLL", "B-ROLL", "TITLES"),
                     audio_tracks: Sequence[Tuple[str, str]] = (("mono", "Dialogue 1"), ("mono", "Dialogue 2"), ("stereo", "Screen audio"))) -> Dict:
    """Build a timeline from synced multi-source recordings (a call recorded as separate files) by session time.

    `sources` maps a key to {"clip": MediaPoolItem, "offset": session seconds at the clip's frame 0, "fps"}: for
    StreamYard isolated recordings the offset is the one in the file name, for a camera it comes from waveform
    correlation against one of the call recordings. A source with its own clock (an intro or outro take) uses offset 0.
    Each segment is {"a", "b" (session seconds), "video": key (V1 angle) or None, "audio": [(key, audio_track)],
    "name", "color", "props" (V1 SetProperty dict, e.g. a punch-in), "marker": (name, color, note),
    "overlays": [{"src", "a", "b", "at" (session second inside the segment where it starts, default a), "track",
    "props", "name", "color", "audio_track"}], "gap": frames of black after}. Segments are laid end to end;
    every item of a segment is placed at an explicit record frame with an exact length, so video and both
    dialogue tracks stay frame-aligned across rate conversions (25p and 30p sources on a 24p timeline).
    Dialogue tracks are mono by default; set each dialogue source clip's track_mapping to its one mic channel
    (`{"1": {"channel_idx": [ch], "type": "mono"}}`) before building. Creates the timeline in `timeline_bin`,
    names tracks, saves. Returns {"length", "placed", "failed"}.
    """
    mp = project.GetMediaPool()
    root = mp.GetRootFolder()
    resolve.OpenPage("edit")
    if timeline_bin is not None:
        mp.SetCurrentFolder(timeline_bin)
    t = mp.CreateEmptyTimeline(timeline_name)
    mp.SetCurrentFolder(root)
    project.SetCurrentTimeline(t)
    fps = float(t.GetSetting("timelineFrameRate"))
    s = t.GetStartFrame()
    add_tracks_until(t, "video", len(video_tracks))
    for i, n in enumerate(video_tracks):
        t.SetTrackName("video", i + 1, n)
    if t.GetTrackSubType("audio", 1) != audio_tracks[0][0]:
        for kind, _ in audio_tracks:
            t.AddTrack("audio", kind)
        t.DeleteTrack("audio", 1)  # the default A1 is stereo and empty; the added tracks shift down
    while t.GetTrackCount("audio") < len(audio_tracks):
        t.AddTrack("audio", audio_tracks[t.GetTrackCount("audio")][0])
    for i, (_, n) in enumerate(audio_tracks):
        t.SetTrackName("audio", i + 1, n)
    pos, placed, failed = 0, [], []
    for sg in segments:
        n = int(round((sg["b"] - sg["a"]) * fps))
        rec = s + pos
        if sg.get("video"):
            it = _place_range(mp, t, sources[sg["video"]], sg["a"], sg["b"], rec, 1, 1, fps, n)
            if it:
                if sg.get("name"):
                    it.SetName(clean_name(sg["name"]))
                if sg.get("color"):
                    it.SetClipColor(sg["color"])
                for k, v in (sg.get("props") or {}).items():
                    it.SetProperty(k, v)
            else:
                failed.append((sg.get("name"), "video"))
        for key, tr in sg.get("audio", []):
            it = _place_range(mp, t, sources[key], sg["a"], sg["b"], rec, tr, 2, fps, n)
            if not it:
                failed.append((sg.get("name"), key))
        for ov in sg.get("overlays", []):
            at = ov.get("at", ov["a"])
            orec = rec + int(round((at - sg["a"]) * fps))
            it = _place_range(mp, t, sources[ov["src"]], ov["a"], ov["b"], orec, ov.get("track", 2), 1, fps)
            if it:
                if ov.get("name"):
                    it.SetName(clean_name(ov["name"]))
                it.SetClipColor(ov.get("color", "Blue"))
                for k, v in (ov.get("props") or {}).items():
                    it.SetProperty(k, v)
            else:
                failed.append((ov.get("name"), "overlay"))
            if ov.get("audio_track"):
                _place_range(mp, t, sources[ov["src"]], ov["a"], ov["b"], orec, ov["audio_track"], 2, fps)
        if sg.get("marker"):
            mn, mc, note = sg["marker"]
            t.AddMarker(pos, mc, mn, note, 1)
        placed.append((sg.get("name"), pos, n))
        pos += n + int(sg.get("gap", 0))
    save(resolve)
    return {"length": pos, "placed": len(placed), "failed": failed}
