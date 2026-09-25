"""One check per library function, each on a `<check> · before` / `<check> · after` timeline pair.

A check duplicates a base timeline twice into `timelines/checks`, leaves "before" untouched, runs the
function on "after", and compares the two. On "after" it drops a marker at the spot that matters: green
when the check passed, red when it failed, with the expectation written in the marker's note, so an
editor can open both timelines, scrub, and judge by eye.

Every check returns {"name", "ok", "expected", "got"}. Frames are relative to the timeline start.
"""
import os
import tempfile
from typing import Callable, Dict, List

import monet_resolve as mr

from . import media

CHECKS: Dict[str, Callable] = {}


def check(fn):
    CHECKS[fn.__name__] = fn
    return fn


# ---------------------------------------------------------------- helpers

def snapshot(timeline) -> List[tuple]:
    """(kind, track, name, start, duration, first source frame) for every item, sorted."""
    s = timeline.GetStartFrame()
    out = []
    for kind in ("video", "audio"):
        for tr in range(1, timeline.GetTrackCount(kind) + 1):
            for x in mr.items(timeline, kind, tr):
                out.append((kind, tr, x.GetName(), x.GetStart() - s, x.GetDuration(), mr.source_frames(x)[0]))
    return sorted(out)


def markers(timeline) -> Dict[int, str]:
    return {int(f): m["name"] for f, m in (timeline.GetMarkers() or {}).items()}


def pair(ctx, base: str, name: str):
    """Fresh `<name> · before` and `<name> · after` copies of `base` in timelines/checks; returns (before, after)."""
    project, mp = ctx["project"], ctx["mp"]
    stale = [t for t in mr.list_timelines(project) if t.GetName() in (f"{name} · before", f"{name} · after")]
    if stale:
        mp.DeleteTimelines(stale)
    src = mr.find_timeline(project, base)
    before = src.DuplicateTimeline(f"{name} · before")
    after = src.DuplicateTimeline(f"{name} · after")
    mp.MoveClips([before.GetMediaPoolItem(), after.GetMediaPoolItem()], ctx["checks_bin"])
    project.SetCurrentTimeline(after)
    return before, after


def verdict(timeline, frame: int, name: str, ok: bool, expected: str, got) -> Dict:
    timeline.AddMarker(frame, "Green" if ok else "Red", f"{'PASS' if ok else 'FAIL'} · {name}", expected, 1)
    return {"name": name, "ok": ok, "expected": expected, "got": got}


def colors_at(ctx, timeline, frame: int, points):
    """RGB at each (x, y) of a one-frame Deliver render (1920x1080 coordinates)."""
    import subprocess
    out = tempfile.mkdtemp(prefix="monet-testbed-")
    mr.render_frame_tiff(ctx["project"], timeline, out, {"f": frame})
    tif = [os.path.join(out, f) for f in os.listdir(out) if f.lower().endswith((".tif", ".tiff"))][0]
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", tif, "-vf", "scale=1920:1080", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return [tuple(raw[(y * 1920 + x) * 3:(y * 1920 + x) * 3 + 3]) for x, y in points]


def _is(rgb, hex_color, tol=40):
    want = bytes.fromhex(hex_color[2:])
    return all(abs(a - b) <= tol for a, b in zip(rgb, want))


def frame_at(ctx, timeline, frame: int):
    """(source ID, source frame) visible at `frame`, read from a one-frame Deliver render."""
    out = tempfile.mkdtemp(prefix="monet-testbed-")
    mr.render_frame_tiff(ctx["project"], timeline, out, {"f": frame})
    tif = [os.path.join(out, f) for f in os.listdir(out) if f.lower().endswith((".tif", ".tiff"))]
    return media.decode_frame(tif[0]) if tif else None


def moved(before, after, at: int, delta: int, tracks=None) -> List:
    """Items of `before` expected in `after`: those starting at/after `at` shifted by `delta`, the rest unchanged.
    Returns the differences as (expected, found-or-None) pairs; empty means the timeline matches."""
    want = sorted((k, tr, n, st + delta if st >= at and (tracks is None or (k, tr) in tracks) else st, d, src)
                  for k, tr, n, st, d, src in before)
    have = set(after)
    return [(w, None) for w in want if w not in have] + [(None, h) for h in after if h not in set(want)]


# ---------------------------------------------------------------- checks

def _gap_check(ctx, name, tracks, expected, picture):
    """Close the 48-frame V1 gap at 336 on `tracks` of `base · layered`; items after it on those tracks move
    48 left, everything else stays. `picture` is the (source, frame) expected at 336 afterward."""
    before, after = pair(ctx, "base · layered", name)
    b = snapshot(before)
    dummy = mr.find_clip(ctx["mp"].GetRootFolder(), "cam_a_24p.mov")
    r = mr.close_gap_ripple(ctx["resolve"], ctx["project"], after, 336, 48, dummy, tracks=tracks)
    diff = moved(b, snapshot(after), 384, -48, tracks=set(tracks))
    pic = frame_at(ctx, after, 336)
    ok = "error" not in r and not diff and pic == picture
    return verdict(after, 336, name, ok, expected, {"result": r, "differences": diff, "frame_336": pic})


def _gap_refusal(ctx, name, start, tracks, expected):
    before, after = pair(ctx, "base · layered", name)
    b = snapshot(before)
    dummy = mr.find_clip(ctx["mp"].GetRootFolder(), "cam_a_24p.mov")
    r = mr.close_gap_ripple(ctx["resolve"], ctx["project"], after, start, 48, dummy, tracks=tracks)
    ok = "error" in r and snapshot(after) == b
    return verdict(after, start, name, ok, expected, {"result": r})


ALL_BUT_A2 = [("video", 1), ("video", 2), ("video", 3), ("audio", 1)]


@check
def close_gap_all_but_a2(ctx):
    return _gap_check(ctx, "close_gap_all_but_a2", ALL_BUT_A2,
                      "Every track except A2 closes: A3, B2 and the GFX start 48 earlier with their audio. "
                      "The long A2 clip plays straight through, unchanged.", (1, 400))


@check
def close_gap_dialogue_only(ctx):
    return _gap_check(ctx, "close_gap_dialogue_only", [("video", 1), ("audio", 1)],
                      "Only V1 and A1 close: A3 and B2 move 48 earlier with their audio. "
                      "The GFX card stays at 400 and the A2 clip is unchanged.", (1, 400))


@check
def close_gap_video_only(ctx):
    return _gap_check(ctx, "close_gap_video_only", [("video", 1), ("video", 2), ("video", 3)],
                      "Only video closes: pictures after 336 move 48 earlier, their sound stays where it was "
                      "(deliberately out of sync).", (1, 400))


@check
def close_gap_audio_only(ctx):
    return _gap_check(ctx, "close_gap_audio_only", [("audio", 1)],
                      "Only A1 closes: the dialogue sound after 336 moves 48 earlier, every picture stays, "
                      "so V1 still shows black from 336 to 384.", None)


@check
def close_gap_refuses_item_across_gap(ctx):
    return _gap_refusal(ctx, "close_gap_refuses_item_across_gap", 336, None,
                        "Refused: closing every track would cut the A2 clip that runs across the gap. "
                        "Timeline identical to before.")


@check
def close_gap_refuses_occupied(ctx):
    return _gap_refusal(ctx, "close_gap_refuses_occupied", 300, [("video", 1)],
                        "Refused: C1 sits at 288-336 on V1, so there is no gap there. Timeline identical to before.")


@check
def ripple_insert(ctx):
    """48 frames open at 216 on every track; clips and markers after 216 move 48 later."""
    before, after = pair(ctx, "base · layered", "ripple_insert")
    b, bm = snapshot(before), markers(before)
    r = mr.ripple_insert(ctx["resolve"], ctx["project"], after, 216, 48)
    a = snapshot(after)
    spanning = [x for x in b if x[3] < 216 < x[3] + x[4]]
    diff = [d for d in moved(b, a, 216, 48) if not any(d[i] and d[i][2] == s[2] for s in spanning for i in (0, 1))]
    marks_ok = markers(after) == {f + 48 if f >= 216 else f: n for f, n in bm.items()}
    ok = not diff and marks_ok and not any(x[3] < 264 and x[3] + x[4] > 216 for x in a)
    return verdict(after, 216, "ripple_insert", ok,
                   "48 empty frames at 216 on every track. A2 and everything after start 48 later, markers too. "
                   "The A2 clip that spans 216 is split with a 48-frame hole.",
                   {"result": r, "differences": diff, "markers": markers(after), "spanning": spanning})


@check
def extend_take(ctx):
    """ripple_insert + continue_clip: B1 plays 48 frames longer with no jump in its picture or sound."""
    before, after = pair(ctx, "base · a-roll", "extend_take")
    s = after.GetStartFrame()
    ending = [x for k in ("video", "audio") for x in mr.items(after, k, 1) if x.GetEnd() - s == 216]
    mr.ripple_insert(ctx["resolve"], ctx["project"], after, 216, 48)
    added = [mr.continue_clip(ctx["resolve"], ctx["project"], after, x, 48, record=216) for x in ending]
    last, first = frame_at(ctx, after, 215), frame_at(ctx, after, 216)
    ok = len([a for a in added if a]) == 2 and last and first and last[0] == first[0] == 2 and 1 <= first[1] - last[1] <= 2
    return verdict(after, 216, "extend_take", ok,
                   "B1 continues for 48 more frames: CAM B's counter keeps counting across 216, voice uninterrupted.",
                   {"continued": [(a.GetName(), a.GetStart() - s, a.GetDuration()) for a in added if a],
                    "frame_215": last, "frame_216": first})


@check
def freeze_item(ctx):
    """A2 becomes a freeze of its first frame and keeps its 72-frame length."""
    before, after = pair(ctx, "base · a-roll", "freeze_item")
    s = after.GetStartFrame()
    item = [x for x in mr.items(after, "video", 1) if x.GetStart() - s == 216][0]
    r = mr.freeze_item(after, item)
    first, last = frame_at(ctx, after, 216), frame_at(ctx, after, 287)
    ok = r["ok"] and r["duration"] == 72 and first == last == (1, 240) and snapshot(after) == snapshot(before)
    return verdict(after, 216, "freeze_item", ok,
                   "A2 holds one frame (CAM A frame 240) for its whole 72 frames; nothing else moves.",
                   {"result": r, "frame_216": first, "frame_287": last})


@check
def insert_fusion_comp_at(ctx):
    """A 48-frame Fusion composition fills the V1 gap at 336; nothing else on the timeline moves."""
    before, after = pair(ctx, "base · layered", "insert_fusion_comp_at")
    b = snapshot(before)
    r = mr.insert_fusion_comp_at(ctx["resolve"], ctx["project"], after, track=1, start=336, duration=48, name="COMP · test")
    a = snapshot(after)
    new = [x for x in a if x not in b]
    missing = [x for x in b if x not in a]
    ok = "error" not in r and not missing and [(x[0], x[1], x[3], x[4]) for x in new] == [("video", 1, 336, 48)]
    return verdict(after, 336, "insert_fusion_comp_at", ok,
                   "A Fusion composition fills V1 from 336 to 384; every other item, audio included, is where it was.",
                   {"result": r, "new_items": new, "missing": missing})


@check
def insert_fusion_comp_at_refuses_other_track(ctx):
    """With the destination toggle on V1, asking for V2 returns an error and changes nothing."""
    before, after = pair(ctx, "base · layered", "insert_fusion_comp_at_refuses_other_track")
    b = snapshot(before)
    r = mr.insert_fusion_comp_at(ctx["resolve"], ctx["project"], after, track=2, start=300, duration=48, name="COMP · test")
    ok = "error" in r and snapshot(after) == b
    return verdict(after, 300, "insert_fusion_comp_at_refuses_other_track", ok,
                   "Refused: the destination toggle is on V1 and the API cannot move it. Timeline identical to before.",
                   {"result": r})


# ---------------------------------------------------------------- placement

def _clip(ctx, name):
    return mr.find_clip(ctx["mp"].GetRootFolder(), name)


@check
def append_exact_mixed_rates(ctx):
    """50 frames of each source (24, 25, 30, 60p) land on V2 with the exact duration and first source frame asked for."""
    before, after = pair(ctx, "base · a-roll", "append_exact_mixed_rates")
    mr.add_tracks_until(after, "video", 2)
    plan = [("cam_a_24p.mov", 0, 100, 1), ("cam_b_25p.mov", 120, 200, 2), ("cam_c_30p.mov", 240, 150, 3),
            ("screen_60p.mov", 360, 300, 4)]
    placed = [mr.append_exact(ctx["mp"], after, _clip(ctx, fname), 2, record, 50, src) for fname, record, src, _ in plan]
    got, ok = [], True
    for (fname, record, src, sid), it in zip(plan, placed):
        row = (fname, it.GetDuration() if it else None, mr.source_frames(it)[0] if it else None, frame_at(ctx, after, record))
        got.append(row)
        ok &= row[1:] == (50, src, (sid, src))
    return verdict(after, 0, "append_exact_mixed_rates", ok,
                   "V2 holds four 50-frame pieces at 0, 120, 240, 360 starting on CAM A 100, CAM B 200, CAM C 150 "
                   "and SCREEN 300 (each card's counter shows that number on the first frame).", got)


@check
def place_clips_on_track(ctx):
    """Screen-recording ranges land on a new V2 at their record frames, named, colored and zoomed, video only."""
    before, after = pair(ctx, "base · a-roll", "place_clips_on_track")
    b = snapshot(before)
    clips = [("REC · first", 96, 300, 540), ("REC · second", 384, 600, 900)]
    r = mr.place_clips_on_track(ctx["resolve"], ctx["project"], after, _clip(ctx, "screen_60p.mov"), 2, clips,
                                zoom=1.2, color="Navy", track_name="SCREEN")
    v2 = [(x.GetName(), x.GetStart() - after.GetStartFrame(), x.GetDuration(), x.GetClipColor(), x.GetProperty("ZoomX"))
          for x in mr.items(after, "video", 2)]
    audio_same = [x for x in snapshot(after) if x[0] == "audio"] == [x for x in b if x[0] == "audio"]
    ok = v2 == [("REC · first", 96, 96, "Navy", 1.2), ("REC · second", 384, 120, "Navy", 1.2)] and audio_same
    return verdict(after, 96, "place_clips_on_track", ok,
                   "V2 'SCREEN' holds REC · first at 96 (96 frames) and REC · second at 384 (120 frames), Navy, "
                   "zoomed 1.2; the audio tracks are unchanged.", {"result": r, "v2": v2})


@check
def place_shots(ctx):
    """A shot list: a wide shot, a zoomed close-up and a freeze frame, each at its record frame."""
    before, after = pair(ctx, "base · a-roll", "place_shots")
    mr.add_tracks_until(after, "video", 2)
    clip = _clip(ctx, "screen_60p.mov")
    shots = [{"name": "wide", "record": 0, "clip": clip, "src_in": 0, "src_out": 240},
             {"name": "close-up", "record": 96, "clip": clip, "src_in": 240, "src_out": 480,
              "props": {"ZoomX": 2.0, "ZoomY": 2.0, "Pan": 200.0}},
             {"name": "freeze", "record": 216, "clip": clip, "src_in": 480, "src_out": 660, "freeze": True}]
    r = mr.place_shots(ctx["resolve"], ctx["project"], after, 2, shots)
    s = after.GetStartFrame()
    v2 = {x.GetName(): x for x in mr.items(after, "video", 2)}
    got = {n: (x.GetStart() - s, x.GetDuration(), x.GetClipColor(), x.GetProperty("ZoomX")) for n, x in v2.items()}
    frozen = frame_at(ctx, after, 216) == frame_at(ctx, after, 287)
    ok = (got == {"wide": (0, 96, "Navy", 1.0), "close-up": (96, 96, "Navy", 2.0), "freeze": (216, 72, "Navy", 1.0)}
          and frozen)
    return verdict(after, 0, "place_shots", ok,
                   "V2: 'wide' 0-96, 'close-up' 96-192 at 2x zoom, 'freeze' 216-288 holding SCREEN frame 480. All Navy.",
                   {"result": r, "v2": got, "freeze_holds": frozen})


@check
def place_still(ctx):
    """A still image placed for 96 frames becomes one 96-frame item (appends alone stop at the still duration)."""
    before, after = pair(ctx, "base · a-roll", "place_still")
    mr.add_tracks_until(after, "video", 2)
    it = mr.place_still(ctx["resolve"], ctx["project"], after, _clip(ctx, "icon.png"), 2, 100, 96)
    v2 = [(x.GetStart() - after.GetStartFrame(), x.GetDuration()) for x in mr.items(after, "video", 2)]
    ok = bool(it) and v2 == [(100, 96)]
    return verdict(after, 100, "place_still", ok, "V2 holds one 96-frame STILL card from 100 to 196.", {"v2": v2})


@check
def merge_through_edits(ctx):
    """A3 cut into two pieces with continuous source merges back into one 120-frame clip, video and audio."""
    before, after = pair(ctx, "base · a-roll", "merge_through_edits")
    s = after.GetStartFrame()
    clip = _clip(ctx, "cam_a_24p.mov")
    for kind, mt in (("video", 1), ("audio", 2)):
        a3 = [x for x in mr.items(after, kind, 1) if x.GetStart() - s == 384][0]
        src, name = mr.source_frames(a3)[0], a3.GetName()
        after.DeleteClips([a3], False)
        for rec, off, n in ((384, 0, 50), (434, 50, 70)):
            p = mr.append_exact(ctx["mp"], after, clip, 1, rec, n, src + off, media_type=mt)
            p.SetName(name)
    split = [(x.GetStart() - s, x.GetDuration()) for x in mr.items(after, "video", 1) if 384 <= x.GetStart() - s < 504]
    r = mr.merge_through_edits(ctx["resolve"], ctx["project"], after, 384, 504, tracks=(("video", 1), ("audio", 1)),
                               keep_names_prefix="A3")
    merged = {k: [(x.GetStart() - s, x.GetDuration(), mr.source_frames(x)[0]) for x in mr.items(after, k, 1)
                  if 384 <= x.GetStart() - s < 504] for k in ("video", "audio")}
    ok = split == [(384, 50), (434, 70)] and merged == {"video": [(384, 120, 400)], "audio": [(384, 120, 400)]}
    return verdict(after, 384, "merge_through_edits", ok,
                   "A3 is one clip again, 384-504, video and audio, starting on CAM A frame 400.",
                   {"split": split, "result": r, "merged": merged})


# ---------------------------------------------------------------- markers and Edit-page attributes

@check
def beat_markers(ctx):
    """Every marker is replaced by one per beat, at round(seconds x 24) frames."""
    before, after = pair(ctx, "base · a-roll", "beat_markers")
    mr.beat_markers(after, [(0.0, "one", "Blue"), (1.5, "two", "Yellow"), (10.25, "three", "Pink")])
    got = markers(after)
    ok = got == {0: "one", 36: "two", 246: "three"}
    return verdict(after, 1, "beat_markers", ok, "Markers only at 0 'one', 36 'two', 246 'three'.", got)


@check
def punch_in_clips(ctx):
    """The clips starting at 96 and 384 get zoom 1.3 / tilt -250 and a PUNCH-IN marker; the others stay wide."""
    before, after = pair(ctx, "base · a-roll", "punch_in_clips")
    r = mr.punch_in_clips(ctx["resolve"], ctx["project"], after, [(96, "B1"), (384, "A3")])
    s = after.GetStartFrame()
    zooms = {x.GetStart() - s: (x.GetProperty("ZoomX"), x.GetProperty("Tilt")) for x in mr.items(after, "video", 1)}
    want = {f: ((1.3, -250.0) if f in (96, 384) else (1.0, 0.0)) for f in zooms}
    mk = markers(after)
    ok = zooms == want and mk.get(96) == "PUNCH-IN 1.3x" and mk.get(384) == "PUNCH-IN 1.3x"
    return verdict(after, 96, "punch_in_clips", ok, "B1 and A3 are punched in (1.3x, tilted); the rest are wide.",
                   {"result": r, "zoom_tilt": zooms, "markers": mk})


@check
def alternate_punch_ins(ctx):
    """Wide and punched-in framing alternate at each touching cut; after the gap the camera starts wide again."""
    before, after = pair(ctx, "base · a-roll", "alternate_punch_ins")
    r = mr.alternate_punch_ins(ctx["resolve"], ctx["project"], after)
    got = [(st, fr) for st, _, fr in r["camera"]]
    ok = got == [(0, "W"), (96, "P"), (216, "W"), (288, "P"), (384, "W"), (504, "P")]
    return verdict(after, 96, "alternate_punch_ins", ok,
                   "A1 wide, B1 punched in, A2 wide, C1 punched in, A3 wide (after the gap), B2 punched in.", r)


# ---------------------------------------------------------------- timelines

@check
def backup_timeline(ctx):
    """The backup copy lands in timelines/backups with every item identical to the original."""
    before, after = pair(ctx, "base · a-roll", "backup_timeline")
    name = "backup_timeline · copy"
    stale = [t for t in mr.list_timelines(ctx["project"]) if t.GetName() == name]
    if stale:
        ctx["mp"].DeleteTimelines(stale)
    r = mr.backup_timeline(ctx["resolve"], ctx["project"], after, name, timeline_bin="timelines", backups_bin="backups")
    copy = mr.find_timeline(ctx["project"], name)
    in_bin = name in [c.GetName() for c in mr.find_bin(ctx["mp"], ["timelines", "backups"]).GetClipList()]
    ok = r["backup"] and in_bin and snapshot(copy) == snapshot(after)
    ctx["mp"].DeleteTimelines([copy])
    return verdict(after, 0, "backup_timeline", ok, "A copy appeared in timelines/backups, identical item for item.",
                   {"result": r, "in_backups_bin": in_bin})


@check
def place_playhead(ctx):
    before, after = pair(ctx, "base · a-roll", "place_playhead")
    r = mr.place_playhead(ctx["resolve"], ctx["project"], after, "01:00:10:12")
    ok = r["tc"] == "01:00:10:12"
    return verdict(after, 252, "place_playhead", ok, "The playhead sits at 01:00:10:12 (frame 252).", r)


@check
def items_in_range_and_shift_markers(ctx):
    """items_in_range picks items by 'within', 'starts' and 'overlaps'; shift_markers moves markers from a frame on."""
    before, after = pair(ctx, "base · layered", "items_in_range_and_shift_markers")
    tr = (("video", 1), ("video", 2), ("audio", 2))
    got = {m: sorted(x.GetName() for x in mr.items_in_range(after, 100, 300, tr, mode=m))
           for m in ("within", "starts", "overlaps")}
    moved_n = mr.shift_markers(after, 200, 10)
    want = {"within": ["A2 · follow-up", "SCREEN · demo"],
            "starts": ["A2 · follow-up", "C1 · reaction", "SCREEN · demo"],
            "overlaps": ["A2 · follow-up", "A2 · long clip", "B1 · answer", "C1 · reaction", "SCREEN · demo"]}
    ok = got == want and moved_n == 2 and markers(after) == {0: "INTRO", 226: "MIDDLE", 514: "CLOSING"}
    return verdict(after, 100, "items_in_range_and_shift_markers", ok,
                   "Range 100-300: within = A2, SCREEN; starts = A2, C1, SCREEN; overlaps adds B1 and the A2 clip. "
                   "Markers from 200 on moved 10 later (MIDDLE 226, CLOSING 514).", {"ranges": got, "markers": markers(after)})


# ---------------------------------------------------------------- titles and Fusion

def _titles_on(timeline, track):
    s = timeline.GetStartFrame()
    return [(x.GetName(), x.GetStart() - s, x.GetDuration()) for x in mr.items(timeline, "video", track)]


def _other(ctx):
    return mr.find_timeline(ctx["project"], "base · layered")


@check
def text_placeholders(ctx):
    """Two Text+ placeholders land on V2 over exact spans; V1 and the audio stay as they were."""
    before, after = pair(ctx, "base · a-roll", "text_placeholders")
    mr.add_tracks_until(after, "video", 2)
    b = snapshot(before)
    r = mr.text_placeholders(ctx["resolve"], ctx["project"], after, 2, [(96, 216, "B1 cover"), (384, 504, "A3 cover")],
                             other=_other(ctx))
    got = _titles_on(after, 2)
    ok = got == [("BROLL · B1 cover", 96, 120), ("BROLL · A3 cover", 384, 120)] and r["texts_set"] == 2 \
        and [x for x in snapshot(after) if x[1] == 1 or x[0] == "audio"] == b
    return verdict(after, 96, "text_placeholders", ok,
                   "V2 holds two yellow B-ROLL placeholder titles, 96-216 and 384-504, reading 'B1 cover' and 'A3 cover'.",
                   {"result": r, "v2": got})


@check
def title_fitted_to_clip(ctx):
    """A Text+ title on V2 spans exactly the clip 'C1 · reaction' (288-336)."""
    before, after = pair(ctx, "base · a-roll", "title_fitted_to_clip")
    mr.add_tracks_until(after, "video", 2)
    r = mr.title_fitted_to_clip(ctx["resolve"], ctx["project"], after, 1, "C1 · reaction", 2, "Reaction", other=_other(ctx))
    ok = r["fits"] and _titles_on(after, 2) == [("TITLE - Reaction", 288, 48)]
    return verdict(after, 288, "title_fitted_to_clip", ok, "V2 holds a white 'Reaction' title from 288 to 336, exactly over C1.", r)


@check
def retrim_title(ctx):
    """The first of two titles shrinks from 120 to 60 frames; the second stays at 384."""
    before, after = pair(ctx, "base · a-roll", "retrim_title")
    mr.add_tracks_until(after, "video", 2)
    mr.text_placeholders(ctx["resolve"], ctx["project"], after, 2, [(96, 216, "first"), (384, 504, "second")], other=_other(ctx))
    r = mr.retrim_title(ctx["resolve"], ctx["project"], after, 2, 96, 60, other=_other(ctx))
    got = _titles_on(after, 2)
    ok = got == [("BROLL · first", 96, 60), ("BROLL · second", 384, 120)] and not r["misplaced"]
    return verdict(after, 96, "retrim_title", ok, "Title 'first' now runs 96-156; 'second' still runs 384-504.",
                   {"result": r, "v2": got})


@check
def fusion_vignette_layer(ctx):
    """A vignette composition on a new top track spans the whole of V1 (0-600) at 70% opacity."""
    before, after = pair(ctx, "base · a-roll", "fusion_vignette_layer")
    b = snapshot(before)
    r = mr.fusion_vignette_layer(ctx["resolve"], ctx["project"], after)
    ok = "error" not in r and r["item"][1:] == (0, 600) and r["opacity"] == 70.0 \
        and [x for x in snapshot(after) if not (x[0] == "video" and x[1] == r["track"])] == b
    return verdict(after, 0, "fusion_vignette_layer", ok, "Top track 'GFX' holds a vignette from 0 to 600; the picture darkens at the edges.", r)


@check
def add_push_transition(ctx):
    """A 16-frame Fusion push sits centered on the A1/B1 cut at 96; the clips keep their positions."""
    before, after = pair(ctx, "base · a-roll", "add_push_transition")
    s = after.GetStartFrame()
    a1 = [x for x in mr.items(after, "video", 1) if x.GetStart() - s == 0][0]
    r = mr.add_push_transition(ctx["resolve"], ctx["project"], after, a1, duration=16)
    clips = [x[:5] for x in snapshot(after) if x[0] == "video" and x[2] != "Cross Dissolve"]
    left, right = colors_at(ctx, after, 96, [(100, 300), (1800, 300)])
    ok = r.get("transition", (None,))[1:] == (88, 16) and clips == [x[:5] for x in snapshot(before) if x[0] == "video"] \
        and _is(left, "0x1F4E79") and _is(right, "0x2E7D32")
    return verdict(after, 88, "add_push_transition", ok,
                   "Across the cut at 96, B1 (green) pushes A1 (blue) out to the left over 16 frames (88-104). "
                   "Mid-way, blue on the left and green on the right.", {"result": r, "left_right_rgb": (left, right)})


# ---------------------------------------------------------------- audio

@check
def place_music(ctx):
    """Two cues land on a new A2 with names, volumes and fades; A1 is untouched."""
    before, after = pair(ctx, "base · a-roll", "place_music")
    music = mr.find_bin(ctx["mp"], "music")
    cues = [("MUSIC · intro", "music.wav", 0, 240, 0, -12.0, 12, 24), ("MUSIC · outro", "music.wav", 480, 720, 360, -6.0, 0, 48)]
    r = mr.place_music(ctx["resolve"], ctx["project"], after, 2, music, cues)
    got = [(n, st, en, vol) for n, st, en, vol, _ in r["placed"]]
    ok = got == [("MUSIC · intro", 0, 240, -12.0), ("MUSIC · outro", 360, 600, -6.0)] and \
        [x for x in snapshot(after) if x[:2] == ("audio", 1)] == [x for x in snapshot(before) if x[:2] == ("audio", 1)]
    return verdict(after, 0, "place_music", ok,
                   "A2 plays 'intro' 0-240 at -12 dB and 'outro' 360-600 at -6 dB, faded; the dialogue is unchanged.", r)


@check
def audio_crossfades(ctx):
    """A 4-frame crossfade on each of the four touching cuts of A1; the gap at 336 gets none."""
    before, after = pair(ctx, "base · a-roll", "audio_crossfades")
    r = mr.audio_crossfades(ctx["resolve"], ctx["project"], after, track=1, frames=4)
    fades = [x for x in mr.items(after, "audio", 1) if not x.GetMediaPoolItem()]
    s = after.GetStartFrame()
    ok = r == {"crossfades": 4, "clips": 6} and sorted(x.GetStart() - s for x in fades) == [94, 214, 286, 502]
    return verdict(after, 96, "audio_crossfades", ok, "Short crossfades at 96, 216, 288 and 504 on A1; none at the gap.",
                   {"result": r, "fades": [(x.GetStart() - s, x.GetDuration()) for x in fades]})


# ---------------------------------------------------------------- nesting and GFX

def _gfx_timeline(ctx, name, clip_name):
    mp = ctx["mp"]
    stale = [t for t in mr.list_timelines(ctx["project"]) if t.GetName() == name]
    if stale:
        mp.DeleteTimelines(stale)
    mp.SetCurrentFolder(ctx["checks_bin"])
    t = mp.CreateTimelineFromClips(name, [_clip(ctx, clip_name)])
    mp.SetCurrentFolder(mp.GetRootFolder())
    return t


@check
def nest_timeline_over_placeholder(ctx):
    """A GFX timeline nests on V4 at the SCREEN placeholder (120) and takes its length (96)."""
    before, after = pair(ctx, "base · layered", "nest_timeline_over_placeholder")
    gfx = _gfx_timeline(ctx, "nest_timeline_over_placeholder · gfx", "gfx_v1.mov")
    ctx["project"].SetCurrentTimeline(after)
    r = mr.nest_timeline_over_placeholder(ctx["resolve"], ctx["project"], after, gfx.GetMediaPoolItem(), 4, 120, 2,
                                          track_name="NESTED")
    pic = frame_at(ctx, after, 150)
    ok = r["nested"] == [("nest_timeline_over_placeholder · gfx", 120, 96)] and pic == (5, 30)
    return verdict(after, 120, "nest_timeline_over_placeholder", ok,
                   "V4 'NESTED' shows the GFX v1 card from 120 to 216, over the screen recording.", {"result": r, "frame_150": pic})


@check
def swap_gfx_clip(ctx):
    """The GFX timeline's clip is replaced by GFX v2 for 288 frames; the nesting cut shows v2."""
    before, after = pair(ctx, "base · layered", "swap_gfx_clip")
    gfx = _gfx_timeline(ctx, "swap_gfx_clip · gfx", "gfx_v1.mov")
    ctx["project"].SetCurrentTimeline(after)
    mr.nest_timeline_over_placeholder(ctx["resolve"], ctx["project"], after, gfx.GetMediaPoolItem(), 4, 120, 2)
    path = _clip(ctx, "gfx_v2.mov").GetClipProperty("File Path")
    r = mr.swap_gfx_clip(ctx["resolve"], ctx["project"], path, mr.find_bin(ctx["mp"], "gfx"), gfx, 288)
    pic = frame_at(ctx, after, 150)
    ok = r["on_timeline"] == [("gfx_v2.mov", 288)] and pic == (6, 30)
    return verdict(after, 120, "swap_gfx_clip", ok, "The nested GFX at 120 now shows the purple GFX v2 card.",
                   {"result": r, "frame_150": pic})


@check
def create_gfx_timeline_from_clip(ctx):
    """A GFX file becomes its own timeline and lands nested on V4 of the cut at 500 for 72 frames."""
    before, after = pair(ctx, "base · layered", "create_gfx_timeline_from_clip")
    name = "create_gfx_timeline_from_clip · gfx"
    stale = [t for t in mr.list_timelines(ctx["project"]) if t.GetName() == name]
    if stale:
        ctx["mp"].DeleteTimelines(stale)
    path = _clip(ctx, "gfx_v2.mov").GetClipProperty("File Path")
    r = mr.create_gfx_timeline_from_clip(ctx["resolve"], ctx["project"], path, mr.find_bin(ctx["mp"], "gfx"),
                                         ctx["checks_bin"], name, after, 4, 500, 72)
    pic = frame_at(ctx, after, 510)
    ok = r["track"] == [(name, 500, 72)] and pic == (6, 10)
    return verdict(after, 500, "create_gfx_timeline_from_clip", ok,
                   "V4 shows the purple GFX v2 card from 500 to 572, as a nested timeline.", {"result": r, "frame_510": pic})


# ---------------------------------------------------------------- multicam

def _swap_angles(ctx, name):
    before, after = pair(ctx, "base · angles", name)
    probe = [10, 150, 250, 330]
    want = [frame_at(ctx, before, f) for f in probe]
    ctx["project"].SetCurrentTimeline(after)
    mcam = mr.find_clip(mr.find_bin(ctx["mp"], "multicam"), "mcam · wide+close")
    sources = {"mc_wide_24p.mov": "mc_wide_24p.mov", "mc_close_25p.mov": "mc_close_25p.mov"}
    log = mr.swap_to_multicam(ctx["resolve"], ctx["project"], after, mcam, sources, tracks=(1,))
    return after, probe, want, sources, log


@check
def swap_to_multicam(ctx):
    """Pieces cut from the raw angle files become multicam items at the same positions, in sync.

    Every new item shows the multicam's first angle (CLOSE, first by name), on the CLOSE frame recorded at the
    same moment as the original picture: WIDE frame f becomes CLOSE frame round(f x 25 / 24).
    """
    after, probe, want, _, log = _swap_angles(ctx, "swap_to_multicam")
    got = [frame_at(ctx, after, f) for f in probe]
    expect = [(8, round(w[1] * 25 / 24)) if w and w[0] == 7 else w for w in want]
    ok = [(r["start"], r["dur"]) for r in log if "item" in r] == [(0, 96), (96, 120), (216, 72), (288, 96)] \
        and not [r for r in log if "error" in r] and got == expect
    return verdict(after, 0, "swap_to_multicam", ok,
                   "Four multicam items at 0, 96, 216, 288, all showing CLOSE in sync with the original pictures "
                   "(set_angles picks the angles afterward).", {"before": want, "after": got, "expected": expect})


@check
def set_angles(ctx):
    """After the swap, the menu-bar angle switch brings back WIDE, CLOSE, WIDE, CLOSE on the original frames.

    Drives Resolve's menu bar through Accessibility, so it only runs with `--ui`.
    """
    after, probe, want, sources, log = _swap_angles(ctx, "set_angles")
    nums = mr.angle_numbers(sources.values())
    switched = mr.set_angles(ctx["resolve"], ctx["project"], after, [(r["item"], nums[r["angle"]]) for r in log if "item" in r])
    got = [frame_at(ctx, after, f) for f in probe]
    ok = all(g and w and g[0] == w[0] and abs(g[1] - w[1]) <= 1 for g, w in zip(got, want))
    return verdict(after, 0, "set_angles", ok, "WIDE, CLOSE, WIDE, CLOSE, each on the frame it showed before the swap.",
                   {"before": want, "after": got, "switched": switched})


UI_CHECKS = {"set_angles"}


# ---------------------------------------------------------------- audio routing

@check
def sync_external_audio(ctx):
    """CAM D and the external mic sync by waveform; CAM D then carries the external recording as linked audio."""
    import json
    before, after = pair(ctx, "base · a-roll", "sync_external_audio")
    cam, ext = _clip(ctx, "cam_d_4ch.mov"), _clip(ctx, "ext_mic.wav")
    ok_call = mr.sync_external_audio(ctx["resolve"], ctx["mp"], cam, ext)
    mapping = json.loads(cam.GetAudioMapping() or "{}")
    ok = bool(mapping.get("linked_audio"))
    return verdict(after, 0, "sync_external_audio", ok,
                   "CAM D's audio mapping now lists the external mic as linked audio (pool clip change, no timeline change).",
                   {"call": ok_call, "mapping": mapping})


@check
def set_clip_audio_mapping(ctx):
    """CAM D's pool mapping becomes track 1 = mono channel 3, track 2 = stereo channels 1-2, read back identical."""
    before, after = pair(ctx, "base · a-roll", "set_clip_audio_mapping")
    mapping = {"1": {"channel_idx": [3], "mute": False, "type": "mono"},
               "2": {"channel_idx": [1, 2], "mute": False, "type": "stereo"}}
    r = mr.set_clip_audio_mapping(_clip(ctx, "cam_d_4ch.mov"), mapping)
    ok = bool(r["clip_set"]) and {k: {kk: v[kk] for kk in ("channel_idx", "type")} for k, v in r["map"].items()} == \
        {k: {kk: v[kk] for kk in ("channel_idx", "type")} for k, v in mapping.items()}
    return verdict(after, 0, "set_clip_audio_mapping", ok, "CAM D's clip mapping reads back as set (pool clip change).", r)


# ---------------------------------------------------------------- building cuts

def _fresh_timeline_slot(ctx, name):
    stale = [t for t in mr.list_timelines(ctx["project"]) if t.GetName() == name]
    if stale:
        ctx["mp"].DeleteTimelines(stale)


@check
def build_cut_from_list(ctx):
    """A cut list of three CAM A ranges becomes a timeline: exact lengths, a gap, a disabled b-roll slot, markers."""
    name = "build_cut_from_list · after"
    _fresh_timeline_slot(ctx, name)
    cut = [{"id": "L1", "label": "open", "src_in": 0, "src_out": 48, "section": "ONE", "broll": "", "gap": 0},
           {"id": "L2", "label": "cover", "src_in": 100, "src_out": 160, "section": "ONE", "broll": "b-roll here", "gap": 12},
           {"id": "L3", "label": "close", "src_in": 300, "src_out": 372, "section": "TWO", "broll": "", "gap": 0, "jump": True}]
    r = mr.build_cut_from_list(ctx["resolve"], ctx["project"], name, cut, _clip(ctx, "cam_a_24p.mov"), ctx["checks_bin"])
    t = mr.find_timeline(ctx["project"], name)
    s = t.GetStartFrame()
    v1 = [(x.GetName(), x.GetStart() - s, x.GetDuration(), x.GetClipEnabled()) for x in mr.items(t, "video", 1)]
    pics = [frame_at(ctx, t, f) for f in (0, 48, 120)]
    notes = {int(f): m["note"] for f, m in t.GetMarkers().items()}
    ok = v1 == [("L1 · open", 0, 48, True), ("L2 · cover", 48, 60, False), ("L3 · close", 120, 72, True)] \
        and markers(t) == {0: "ONE", 120: "TWO"} and notes[120].startswith("JUMP CUT") \
        and pics == [(1, 0), None, (1, 300)]
    return verdict(t, 0, "build_cut_from_list", ok,
                   "L1 0-48, L2 48-108 disabled (orange b-roll slot), 12 empty frames, L3 120-192 from CAM A frame 300; "
                   "section markers ONE at 0 and TWO at 120, TWO's note flags the jump cut.", {"result": r, "v1": v1, "pictures": pics, "notes": notes,
                                                                 "markers": markers(t)})


@check
def build_synced_cut(ctx):
    """Two sources on one session clock (CAM B starts 2 s in) cut by session seconds, frame-exact across 24/25p."""
    name = "build_synced_cut · after"
    _fresh_timeline_slot(ctx, name)
    sources = {"a": {"clip": _clip(ctx, "cam_a_24p.mov"), "offset": 0.0, "fps": 24},
               "b": {"clip": _clip(ctx, "cam_b_25p.mov"), "offset": 2.0, "fps": 25}}
    segments = [{"a": 1.0, "b": 3.0, "video": "a", "audio": [("a", 1)], "name": "A · one"},
                {"a": 3.0, "b": 5.5, "video": "b", "audio": [("b", 1)], "name": "B · two", "gap": 12}]
    r = mr.build_synced_cut(ctx["resolve"], ctx["project"], name, sources, segments, timeline_bin=ctx["checks_bin"],
                            audio_tracks=(("stereo", "Dialogue"),))
    t = mr.find_timeline(ctx["project"], name)
    s = t.GetStartFrame()
    v1 = [(x.GetName(), x.GetStart() - s, x.GetDuration()) for x in mr.items(t, "video", 1)]
    a1 = [(x.GetStart() - s, x.GetDuration()) for x in mr.items(t, "audio", 1)]
    pics = [frame_at(ctx, t, f) for f in (0, 48)]
    ok = r["length"] == 120 and not r["failed"] and v1 == [("A · one", 0, 48), ("B · two", 48, 60)] \
        and a1 == [(0, 48), (48, 60)] and pics == [(1, 24), (2, 25)]
    return verdict(t, 48, "build_synced_cut", ok,
                   "A · one 0-48 from CAM A frame 24 (session 1.0 s), B · two 48-108 from CAM B frame 25 (session 3.0 s), "
                   "audio aligned under both, 12 empty frames after.", {"result": r, "v1": v1, "a1": a1, "pictures": pics})


# ---------------------------------------------------------------- media pool

@check
def import_replace_cleanup(ctx):
    """Import into a scratch bin, repoint the clip to another file, then delete the scratch bin."""
    mp = ctx["mp"]
    before, after = pair(ctx, "base · a-roll", "import_replace_cleanup")
    root_names = [f.GetName() for f in mp.GetRootFolder().GetSubFolderList()]
    if "_scratch_check" in root_names:
        mr.cleanup_scratch(ctx["resolve"], ctx["project"], scratch_bin="_scratch_check", confirm=True)
    v1 = _clip(ctx, "gfx_v1.mov").GetClipProperty("File Path")
    v2 = _clip(ctx, "gfx_v2.mov").GetClipProperty("File Path")
    imported = mr.import_to_bin(mp, [v1], "_scratch_check")
    scratch = mr.find_bin(mp, "_scratch_check")
    name = scratch.GetClipList()[0].GetName() if scratch.GetClipList() else None
    replaced = mr.replace_clip_file(ctx["resolve"], scratch, {name: v2}) if name else []
    try:
        refused = False
        mr.cleanup_scratch(ctx["resolve"], ctx["project"], scratch_bin="_scratch_check")
    except ValueError:
        refused = True
    gone = mr.cleanup_scratch(ctx["resolve"], ctx["project"], scratch_bin="_scratch_check", confirm=True)
    still = "_scratch_check" in [f.GetName() for f in mp.GetRootFolder().GetSubFolderList()]
    ok = bool(imported) and imported[0]["Frames"] == "240" and replaced and replaced[0][1] is True \
        and replaced[0][2] == "288" and refused and not still
    return verdict(after, 0, "import_replace_cleanup", ok,
                   "Scratch bin created with GFX v1 (240 frames), repointed to GFX v2 (288 frames), refused to delete "
                   "without confirm=True, then deleted.", {"imported": imported, "replaced": replaced, "cleanup": gone})


# ---------------------------------------------------------------- render and stills

@check
def render_timeline_mp4(ctx):
    """The whole a-roll renders to a 1280x720 H.264 file of 600 frames."""
    import subprocess
    before, after = pair(ctx, "base · a-roll", "render_timeline_mp4")
    out = tempfile.mkdtemp(prefix="monet-testbed-")
    r = mr.render_timeline_mp4(ctx["resolve"], ctx["project"], after, out, "a-roll", width=1280, height=720, wait=120)
    files = [os.path.join(out, f) for f in os.listdir(out)]
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                            "stream=width,height,nb_read_frames", "-of", "csv=p=0", files[0]],
                           capture_output=True, text=True).stdout.strip() if files else None
    ok = probe == "1280,720,600"
    return verdict(after, 0, "render_timeline_mp4", ok, "a-roll.mp4: 1280x720, 600 frames.", {"result": r, "ffprobe": probe})


@check
def export_stills(ctx):
    """Two graded stills export from the Color page as PNG files named after their keys."""
    before, after = pair(ctx, "base · a-roll", "export_stills")
    out = tempfile.mkdtemp(prefix="monet-testbed-") + "/"
    r = mr.export_stills(ctx["resolve"], ctx["project"], after, out, {"wide": 10, "late": 520})
    files = sorted(os.listdir(out))
    ok = all(v[0] for v in r.values()) and files == ["late.png", "wide.png"]
    return verdict(after, 10, "export_stills", ok, "Stills 'wide' (frame 10) and 'late' (frame 520) exported as PNG.",
                   {"result": r, "files": files})


@check
def map_project(ctx):
    r = mr.map_project(ctx["project"], "base · a-roll")
    ok = r["project"] == "monet-testbed" and [x[0] for x in r["tracks"]["V1 A-ROLL"]] == \
        ["A1 · intro", "B1 · answer", "A2 · follow-up", "C1 · reaction", "A3 · second part", "B2 · closing"]
    return {"name": "map_project", "ok": ok, "expected": "Six a-roll items in order, three markers.", "got": r}

