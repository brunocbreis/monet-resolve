"""Timeline item surgery the API lacks: continue a clip, merge through-edits, ripple-insert with markers,
stills longer than 24 frames.

The API has no trim, extend or join. Every one of these is "append the same source range at the right
record frame, then delete what it replaces", with the source frame checked after the append: appending
a 25p or 30p source into a 24 fps timeline can land one source frame early. `append_exact` retries
neighboring start frames until the item's `GetSourceStartFrame()` equals the one asked for.
"""
import json
from typing import Dict, List, Optional, Sequence

from ._util import VIDEO_PROPS, items, save
from .assembly import insert_gap_ripple


def append_exact(media_pool, timeline, clip, track: int, record: int, frames: int, source_start: int,
                 media_type: int = 1, exact: bool = True, tries: Sequence[int] = (0, 1, -1, 2)):
    """Append `frames` of `clip` from `source_start` at `record` (relative) on `track`, exact in duration
    and, with `exact`, in source start. For audio (`media_type=2`) source frames are in the clip's own
    frame rate. Returns the item (the closest one when no try lands exactly; check its source start),
    or None when no append reached the duration."""
    s = timeline.GetStartFrame()
    tl_fps = float(timeline.GetSetting("timelineFrameRate") or 24)
    ratio = float(clip.GetClipProperty("FPS") or tl_fps) / tl_fps if media_type == 2 else 1.0
    last = None
    for off in (tries if exact else (0,)):
        sf = source_start + off
        end = sf + round(frames * ratio) - 1
        n = None
        for _ in range(6):
            r = media_pool.AppendToTimeline([{"mediaPoolItem": clip, "startFrame": sf, "endFrame": end, "trackIndex": track,
                                              "recordFrame": s + record, "mediaType": media_type}])
            n = r[0] if r else None
            if not n:
                break
            if n.GetDuration() == frames:
                break
            d = n.GetDuration()
            timeline.DeleteClips([n], False)
            end += round((frames - d) * ratio) or (1 if frames > d else -1)
            n = None
        if n is None:
            continue
        if not exact or n.GetSourceStartFrame() == source_start:
            return n
        if last is not None:
            timeline.DeleteClips([last], False)
        last = n
    return last


def _copy_attrs(src_snapshot: Dict, n) -> None:
    for k, v in src_snapshot.get("props", {}).items():
        if v is not None and v is not False:
            n.SetProperty(k, v)
    if src_snapshot.get("mapping"):
        n.SetSourceAudioChannelMapping(json.dumps({"track_mapping": json.loads(src_snapshot["mapping"])["track_mapping"]}))
    if src_snapshot.get("volume"):
        n.SetProperty("AudioVolume", src_snapshot["volume"])
    if src_snapshot.get("enabled") is False:
        n.SetClipEnabled(False)
    if src_snapshot.get("color"):
        n.SetClipColor(src_snapshot["color"])


def snapshot(item, kind: str) -> Dict:
    """Everything `continue_clip`/`merge_through_edits` restore on a re-appended item."""
    snap = {"clip": item.GetMediaPoolItem(), "source_start": item.GetSourceStartFrame(), "source_end": item.GetSourceEndFrame(),
            "enabled": item.GetClipEnabled(), "color": item.GetClipColor(), "name": item.GetName()}
    if kind == "video":
        snap["props"] = {k: item.GetProperty(k) for k in VIDEO_PROPS}
    else:
        snap["mapping"] = item.GetSourceAudioChannelMapping()
        snap["volume"] = item.GetProperty("AudioVolume")
    return snap


def continue_clip(resolve, project, timeline, item, frames: int, record: Optional[int] = None):
    """Append the next `frames` of `item`'s source right after it (or at `record`), on the same track,
    with its Inspector properties, audio mapping, volume, enabled state and color. The join is a
    through-edit: same source, no jump. Use it after `ripple_insert` to fill the opened space, one call
    per track, so a performance or a sentence runs longer in sync on every track. Multicam items come
    back on the multicam's first angle; set it with `multicam.set_angles`. Saves. Returns the new item or None."""
    kind, tr = item.GetTrackTypeAndIndex()
    snap = snapshot(item, kind)
    s = timeline.GetStartFrame()
    at = item.GetEnd() - s if record is None else record
    n = append_exact(project.GetMediaPool(), timeline, snap["clip"], tr, at, frames, snap["source_end"],
                     media_type=1 if kind == "video" else 2)
    if n:
        _copy_attrs(snap, n)
    save(resolve)
    return n


def merge_through_edits(resolve, project, timeline, start: int, end: int, tracks: Sequence = (("video", 1), ("video", 2),
                        ("audio", 1), ("audio", 2), ("audio", 3)), keep_names_prefix: str = "B-ROLL") -> List[Dict]:
    """Join neighboring items that are really one piece of source into single clips, between `start` and
    `end` (relative).

    Two items merge only when they touch on the timeline, share the source clip, the name (so the same
    multicam angle), properties and enabled state, and the second starts on exactly the source frame
    where the first ends. Exactly: a one or two frame tolerance also swallows real edits between two
    takes and slides the second one out of sync. Merged items keep their name when it starts with
    `keep_names_prefix` (others, such as multicam angle names, come from the source). Multicam merges come
    back on the first angle; set it again with `multicam.set_angles`. Saves.
    Returns [{"kind", "track", "start", "end", "pieces", "ok"}].
    """
    mp = project.GetMediaPool()
    s = timeline.GetStartFrame()
    out = []
    for kind, tr in tracks:
        its = [x for x in items(timeline, kind, tr) if x.GetMediaPoolItem() and start <= x.GetStart() - s < end]
        groups: List[List] = []
        for x in its:
            key = (x.GetMediaPoolItem().GetUniqueId(), x.GetName(), x.GetClipEnabled(),
                   tuple(round(x.GetProperty(k) or 0, 3) for k in VIDEO_PROPS) if kind == "video" else x.GetProperty("AudioVolume"))
            if groups and groups[-1][0] == key and groups[-1][-1].GetEnd() == x.GetStart() and x.GetSourceStartFrame() == groups[-1][-1].GetSourceEndFrame():
                groups[-1].append(x)
            else:
                groups.append([key, x])
        for g in groups:
            pieces = g[1:]
            if len(pieces) < 2:
                continue
            f = pieces[0]
            a, b = f.GetStart() - s, pieces[-1].GetEnd() - s
            snap = snapshot(f, kind)
            timeline.DeleteClips(pieces, False)
            n = append_exact(mp, timeline, snap["clip"], tr, a, b - a, snap["source_start"], media_type=1 if kind == "video" else 2)
            if n:
                _copy_attrs(snap, n)
                if snap["name"].startswith(keep_names_prefix):
                    n.SetName(snap["name"])
            out.append({"kind": kind, "track": tr, "start": a, "end": b, "pieces": len(pieces), "ok": bool(n)})
    save(resolve)
    return out


def shift_markers(timeline, from_frame: int, delta: int) -> int:
    """Move every timeline marker at or after `from_frame` (relative) by `delta` frames (ripple edits leave
    markers in place). Returns the count moved."""
    mk = timeline.GetMarkers() or {}
    moved = 0
    for f in sorted(mk, reverse=delta > 0):
        if f >= from_frame:
            m = mk[f]
            timeline.DeleteMarkerAtFrame(f)
            timeline.AddMarker(f + delta, m["color"], m["name"], m["note"], m["duration"], m.get("customData", ""))
            moved += 1
    return moved


def ripple_insert(resolve, project, timeline, at: int, frames: int) -> Dict:
    """Open `frames` of space at `at` on every track, moving clips and markers after it. Clips that span
    `at` are split with an empty stretch between the halves; fill it with `continue_clip`.
    `assembly.insert_gap_ripple` moves the clips, `shift_markers` the markers. Saves."""
    r = insert_gap_ripple(resolve, project, timeline, at, frames)
    shift_markers(timeline, at, frames)
    save(resolve)
    return r


def items_in_range(timeline, start: int, end: int, tracks: Sequence = (("video", 1), ("audio", 1)), mode: str = "within") -> List:
    """Items with a media pool item between `start` and `end` (relative).

    mode "within": item fully inside. "starts": item starts inside (an audio item that starts inside a
    range as a J-cut belongs to the next shot). "overlaps": any overlap. Prefer "within" when deleting a
    block, and list the items first."""
    s = timeline.GetStartFrame()
    out = []
    for kind, tr in tracks:
        for x in items(timeline, kind, tr):
            if not x.GetMediaPoolItem():
                continue
            a, b = x.GetStart() - s, x.GetEnd() - s
            if (mode == "within" and a >= start and b <= end) or (mode == "starts" and start <= a < end) or (mode == "overlaps" and a < end and b > start):
                out.append(x)
    return out


def place_still(resolve, project, timeline, still, track: int, record: int, frames: int, piece: int = 24):
    """Put a still image on the timeline for `frames` frames as one item.

    `AppendToTimeline` gives a still at most the project's standard still duration (set `piece` to it),
    whatever endFrame says. This appends `piece`-frame copies back to back and turns them into one
    Fusion clip with `CreateFusionClip`, so the result is a single item to scale and position.
    Returns the item or None."""
    mp = project.GetMediaPool()
    s = timeline.GetStartFrame()
    project.SetCurrentTimeline(timeline)
    resolve.OpenPage("edit")
    placed = []
    p = record
    while p < record + frames:
        n = min(piece, record + frames - p)
        r = mp.AppendToTimeline([{"mediaPoolItem": still, "startFrame": 0, "endFrame": n - 1, "trackIndex": track,
                                  "recordFrame": s + p, "mediaType": 1}])
        if r and r[0]:
            placed.append(r[0])
        p += n
    if len(placed) > 1:
        timeline.CreateFusionClip(placed)
    its = [x for x in items(timeline, "video", track) if x.GetStart() - s == record]
    return its[0] if its else None
