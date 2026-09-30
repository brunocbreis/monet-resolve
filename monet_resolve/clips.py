"""Timeline item surgery the API lacks: split, extend and join clips, ripple-insert with markers,
stills longer than 24 frames.

The API has no trim, extend or join. Every one of these is "append the same source range at the right
record frame, then delete what it replaces", with the source frame checked after the append: appending
a 25p or 30p source into a 24 fps timeline can land one source frame early. `append_exact` retries
neighboring start frames until the item's source start (`source_frames`) equals the one asked for.
"""
import json
from typing import Dict, List, Optional, Sequence, Tuple

from ._util import VIDEO_PROPS, append_exact, items, save, source_frames  # noqa: F401 (append_exact lives in _util)
from .timelines import refresh_timeline
from .titles import insert_fusion_title


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
    if any((src_snapshot.get("fades") or {}).values()):
        n.SetFades(src_snapshot["fades"])


def snapshot(item, kind: str) -> Dict:
    """Everything `extend_clip`/`join_clips` restore on a re-appended item."""
    first, end = source_frames(item)
    snap = {"clip": item.GetMediaPoolItem(), "source_start": first, "source_end": end,
            "enabled": item.GetClipEnabled(), "color": item.GetClipColor(), "name": item.GetName(),
            "fades": {k: round(v) for k, v in (item.GetFades() or {}).items()}}
    if kind == "video":
        snap["props"] = {k: item.GetProperty(k) for k in VIDEO_PROPS}
    else:
        snap["mapping"] = item.GetSourceAudioChannelMapping()
        snap["volume"] = item.GetProperty("AudioVolume")
    return snap


def extend_clip(resolve, project, timeline, item, frames: int, record: Optional[int] = None, join: bool = False):
    """Make `item` run `frames` longer: append the next `frames` of its source right after it (or at `record`), on the same track,
    with its Inspector properties, audio mapping, volume, enabled state and color. A fade-out moves from
    `item` to the new piece, capped at the new piece's length; a fade-in stays on `item`. The join is a
    through-edit: same source, no jump. Use it after `ripple_insert` to fill the opened space, one call
    per track, so a performance or a sentence runs longer in sync on every track. Multicam items come
    back on the multicam's first angle.

    The result is a through-edit: two items that play as one, with everything on `item` kept. `join=True`
    makes them one clip with `join_clips`, which re-appends it and loses what the API cannot copy
    (keyframes, clip effects, grades, comps); the API cannot tell whether a clip has any, so joining is opt-in.
    Saves. Returns the new item (the joined item with `join`) or None."""
    kind, tr = item.GetTrackTypeAndIndex()
    snap = snapshot(item, kind)
    s = timeline.GetStartFrame()
    at = item.GetEnd() - s if record is None else record
    n = append_exact(project.GetMediaPool(), timeline, snap["clip"], tr, at, frames, snap["source_end"],
                     media_type=1 if kind == "video" else 2)
    if n:
        fades = snap.pop("fades")
        _copy_attrs(snap, n)
        if fades.get("FadeOut"):
            n.SetFades({"FadeIn": 0, "FadeOut": min(fades["FadeOut"], n.GetDuration())})
            item.SetFades({"FadeIn": fades.get("FadeIn", 0), "FadeOut": 0})
        if join:
            a, b = item.GetStart() - s, n.GetEnd() - s
            join_clips(resolve, project, timeline, a, b, tracks=((kind, tr),), keep_names_prefix=snap["name"])
            n = next((x for x in items(timeline, kind, tr) if x.GetStart() - s == a), None)
    save(resolve)
    return n


def join_clips(resolve, project, timeline, start: int, end: int, tracks: Sequence = (("video", 1), ("video", 2),
               ("audio", 1), ("audio", 2), ("audio", 3)), keep_names_prefix: str = "B-ROLL") -> List[Dict]:
    """Join neighboring items that are really one piece of source into single clips, between `start` and
    `end` (relative): the undo of `split_at`, like Timeline > Join Clips.

    Two items merge only when they touch on the timeline, share the source clip, the name (so the same
    multicam angle), properties and enabled state, and the second starts on exactly the source frame
    where the first ends. Exactly: a one or two frame tolerance also swallows real edits between two
    takes and slides the second one out of sync. Merged items keep their name when it starts with
    `keep_names_prefix` (others, such as multicam angle names, come from the source). Multicam merges come
    back on the first angle. The merged item gets the first piece's fade-in and the last piece's fade-out.
    Deleting the pieces deletes the transitions on their outer edges (a crossfade into the next clip); they
    are read first and added back with `AddTransition` (same name, duration and alignment; category "audio"
    on audio tracks, "simple" on video). Saves.
    Returns [{"kind", "track", "start", "end", "pieces", "ok", "transitions": added, "lost": [names not re-added]}].
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
            if groups and groups[-1][0] == key and groups[-1][-1].GetEnd() == x.GetStart() and source_frames(x)[0] == source_frames(groups[-1][-1])[1]:
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
            snap["fades"]["FadeOut"] = round((pieces[-1].GetFades() or {}).get("FadeOut", 0))
            edges = _edge_transitions(timeline, kind, tr, a, b)
            timeline.DeleteClips(pieces, False)
            n = append_exact(mp, timeline, snap["clip"], tr, a, b - a, snap["source_start"], media_type=1 if kind == "video" else 2)
            added = []
            if n:
                _copy_attrs(snap, n)
                if snap["name"].startswith(keep_names_prefix):
                    n.SetName(snap["name"])
                added = [opts for opts in edges if n.AddTransition(opts)]
            out.append({"kind": kind, "track": tr, "start": a, "end": b, "pieces": len(pieces), "ok": bool(n),
                        "transitions": len(added), "lost": [o["type"] for o in edges if o not in added]})
    save(resolve)
    return out


def _edge_transitions(timeline, kind: str, tr: int, a: int, b: int) -> List[Dict]:
    """`AddTransition` options for the transitions touching the edges `a` and `b` (relative) on one track."""
    s = timeline.GetStartFrame()
    out = []
    for x in items(timeline, kind, tr):
        if x.GetType() != "transition":
            continue
        ts, te = x.GetStart() - s, x.GetEnd() - s
        for edge, position in ((a, "start"), (b, "end")):
            if ts <= edge <= te and ts < te:
                out.append({"type": x.GetName(), "category": "audio" if kind == "audio" else "simple", "position": position,
                            "alignment": "center" if ts < edge < te else ("left" if te == edge else "right"),
                            "duration": te - ts})
    return out


def shift_markers(timeline, from_frame: int, delta: int) -> int:
    """Move every timeline marker at or after `from_frame` (relative) by `delta` frames. Returns the count moved."""
    mk = timeline.GetMarkers() or {}
    moved = 0
    for f in sorted(mk, reverse=delta > 0):
        if f >= from_frame:
            m = mk[f]
            timeline.DeleteMarkerAtFrame(f)
            timeline.AddMarker(f + delta, m["color"], m["name"], m["note"], m["duration"], m.get("customData", ""))
            moved += 1
    return moved


def ripple_insert(resolve, project, timeline, at: int, frames: int, other=None, fps: Optional[int] = None) -> Dict:
    """Open `frames` of empty space at `at` (relative) on every track, moving clips and markers after it later.

    The inverse of `close_gap_ripple`. The API has no insert-gap call, but `InsertFusionTitleIntoTimeline`
    is a true insert edit: with every video and audio track unlocked it ripples all of them (with the other
    tracks locked it ripples only its own). So: unlock everything,
    insert a `frames`-long Text+ at `at` on the destination track, delete it without ripple. Clips that
    span `at` on other tracks (a music cue) are split there with an empty stretch between the halves; re-lay
    them afterwards (`extend_clip` fills the space with the same take). Markers after `at` move with the
    clips; grades and comps stay on the moved items. An insert that fails (a timeline a script just built)
    is retried once after a timeline refresh; `other` names the timeline to switch to for it.

    Only tracks with auto-select on take part: a track with it off (a UI-only toggle the API cannot read or
    set) neither moves nor splits. The clips spanning `at` are read before the insert and checked after it;
    any that did not split come back under "unsplit" with an "error". Saves.
    Returns {"inserted_on": (track type, index), "end_before", "end_after", "unsplit": [(kind, index, name)]}.
    """
    project.SetCurrentTimeline(timeline)
    if other is not None:
        refresh_timeline(project, timeline, other)
    resolve.OpenPage("edit")
    s = timeline.GetStartFrame()
    end_before = timeline.GetEndFrame() - s
    every = _every_track(timeline)
    spanning = _spanning(timeline, at, every)
    for t in every:
        timeline.SetTrackLock(*t, False)
    it = insert_fusion_title(timeline, at, frames, fps)
    if not it:
        refresh_timeline(project, timeline, other)
        resolve.OpenPage("edit")
        it = insert_fusion_title(timeline, at, frames, fps)
    where = it.GetTrackTypeAndIndex() if it else None
    if it:
        timeline.DeleteClips([it], False)
    save(resolve)
    out = {"inserted_on": where, "end_before": end_before, "end_after": timeline.GetEndFrame() - s,
           "unsplit": _unsplit(timeline, at, frames, spanning)}
    if not it:
        out["error"] = "the title insert failed, also after a timeline refresh"
    elif out["unsplit"]:
        out["error"] = "clips spanning the insert did not split; turn on auto-select for their tracks"
    return out


def split_at(resolve, project, timeline, at: int, tracks: Sequence[Tuple[str, int]], other=None,
             fps: Optional[int] = None) -> Dict:
    """Cut every clip that spans `at` (relative) on `tracks` into two, in place, like the blade tool.

    The API has no split. A 1-frame Text+ inserted at `at` is a true insert edit, and an insert cuts every
    clip spanning its frame on the tracks it ripples; deleting the title with ripple closes the frame again.
    Both halves are Resolve's own pieces of the original clip: keyframes, effects, grades, comps and
    speed survive, which no delete-and-re-append route keeps. Fades stay on the outer edges.

    `tracks` lists the tracks to cut, as ("video" | "audio", index) pairs. Every other track is locked
    during the edit and gets its lock state back. The title needs a video track: when `tracks` has none,
    the first video track with nothing spanning `at` is unlocked too. Titles land on an unlocked video
    track only after `refresh_timeline` (it empties the media pool selection and switches timelines), so
    the function runs it first; `other` names the timeline to switch to, any other one when left out.
    Tracks with auto-select off (UI only) are not cut. The timeline is compared before and after: clips on
    `tracks` that did not split come back under "unsplit", anything else that changed under "changed",
    either with an "error". Saves.
    Returns {"split": [(kind, index, left item, right item)], "unsplit": [...], "changed": [...]}.
    """
    project.SetCurrentTimeline(timeline)
    refresh_timeline(project, timeline, other)
    resolve.OpenPage("edit")
    s = timeline.GetStartFrame()
    every = _every_track(timeline)
    chosen = list(tracks)
    unknown = [t for t in chosen if t not in every]
    if not chosen or unknown:
        return {"error": "no such track" if unknown else "no tracks chosen", "tracks": unknown}
    spanning = _spanning(timeline, at, chosen)
    unlocked = list(chosen)
    if not any(k == "video" for k, _ in chosen):
        free = [t for t in every if t[0] == "video" and not _spanning(timeline, at, [t])]
        if not free:
            return {"error": "no video track is free at the split frame to carry the title"}
        unlocked.append(free[0])

    def positions():
        return {(k, i, x.GetName(), x.GetStart() - s, x.GetEnd() - s) for k, i in every for x in items(timeline, k, i)}

    before = positions()
    locks = {t: timeline.GetIsTrackLocked(*t) for t in every}
    try:
        for t in every:
            timeline.SetTrackLock(*t, t not in unlocked)
        it = insert_fusion_title(timeline, at, 1, fps)
        if not it:
            return {"error": "the title insert failed after a timeline refresh"}
        timeline.DeleteClips([it], True)
    finally:
        for t, locked in locks.items():
            timeline.SetTrackLock(*t, locked)
    save(resolve)
    unsplit = _unsplit(timeline, at, 0, spanning)
    cut = {(k, i, name, a, b) for k, i, name, a, b in spanning if (k, i, name) not in unsplit}
    halves = {(k, i, name, a, at) for k, i, name, a, b in cut} | {(k, i, name, at, b) for k, i, name, a, b in cut}
    out = {"split": [], "unsplit": unsplit, "changed": sorted((before - cut) ^ (positions() - halves))}
    for k, i, name, a, b in sorted(cut):
        pieces = {x.GetStart() - s: x for x in items(timeline, k, i) if x.GetName() == name}
        out["split"].append((k, i, pieces.get(a), pieces.get(at)))
    if unsplit or out["changed"]:
        out["error"] = ("clips on the chosen tracks did not split; turn on auto-select for their tracks" if unsplit
                        else "items outside the split changed; restore from a backup")
    return out


def _every_track(timeline) -> List[Tuple[str, int]]:
    return [(k, i) for k in ("video", "audio") for i in range(1, timeline.GetTrackCount(k) + 1)]


def _spanning(timeline, at: int, tracks) -> List[Tuple[str, int, str, int, int]]:
    """(kind, index, name, start, end) of the clips on `tracks` that start before `at` and end after it."""
    s = timeline.GetStartFrame()
    return [(k, i, x.GetName(), x.GetStart() - s, x.GetEnd() - s) for k, i in tracks for x in items(timeline, k, i)
            if x.GetType() != "transition" and x.GetStart() - s < at < x.GetEnd() - s]


def _unsplit(timeline, at: int, gap: int, spanning) -> List[Tuple[str, int, str]]:
    """The `spanning` clips that are not now two pieces: one ending at `at`, one starting at `at + gap`."""
    s = timeline.GetStartFrame()
    out = []
    for k, i, name, a, b in spanning:
        now = {(x.GetStart() - s, x.GetEnd() - s) for x in items(timeline, k, i) if x.GetName() == name}
        if not {(a, at), (at + gap, b + gap)} <= now:
            out.append((k, i, name))
    return out


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
