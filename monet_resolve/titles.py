"""Titles and Fusion compositions on the timeline: exact-length inserts, Text+ styling, a vignette layer."""
import textwrap
from typing import Dict, Optional, Sequence, Tuple

from ._util import clean_name, items, save, tc, timeline_fps, track_locks
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
    `ClearMarkInOut`. Lock the other tracks first (`track_locks`) so it lands where you want; the
    Edit page must be open. Returns the TimelineItem, or False/None when the insert failed.
    """
    return _insert_marked(timeline, start, duration, fps, lambda: timeline.InsertFusionTitleIntoTimeline(template))


def insert_fusion_composition(timeline, start: int, duration: int, fps: Optional[int] = None):
    """Insert an empty native Fusion composition of exact length at `start` on the unlocked track.

    Same marks recipe as `insert_fusion_title` with `InsertFusionCompositionIntoTimeline()`. Returns the
    TimelineItem, or False/None when the insert failed.
    """
    return _insert_marked(timeline, start, duration, fps, timeline.InsertFusionCompositionIntoTimeline)


def style_text_plus(comp, text: str, font: str = "Inter 28pt", style: str = "Medium", size: float = 0.045,
                    rgb: Tuple[float, float, float] = (1, 1, 1)) -> bool:
    """Set text, font, style, size and color on the TextPlus tool of a Fusion comp. The Fusion page must be open.

    There is no Inspector call; this finds the tool with `ID == "TextPlus"` and calls `SetInput` for
    StyledText, Font, Style, Size, Red1, Green1, Blue1. Colors are 0 to 1. A `style` that matches no face
    falls back silently. Returns False when the comp has no TextPlus tool.
    """
    tools = [x for x in comp.GetToolList().values() if x.ID == "TextPlus"]
    if not tools:
        return False
    tp = tools[0]
    tp.SetInput("StyledText", text)
    tp.SetInput("Font", font)
    tp.SetInput("Style", style)
    tp.SetInput("Size", size)
    tp.SetInput("Red1", rgb[0])
    tp.SetInput("Green1", rgb[1])
    tp.SetInput("Blue1", rgb[2])
    return True


def text_placeholders(resolve, project, timeline, track: int, spans: Sequence[Tuple[int, int, str]], other=None,
                      font: str = "Inter 28pt", style: str = "Medium", size: float = 0.045,
                      rgb: Tuple[float, float, float] = (1, 0.85, 0.35), heading: str = "B-ROLL\n",
                      name_prefix: str = "BROLL · ", color: str = "Orange", wrap: int = 30,
                      fps: Optional[int] = None) -> Dict:
    """Insert a Text+ placeholder on `track` for each span and style its text in the Fusion comp.

    `spans` is [(start, end, text)] in frames from the timeline start (end exclusive). Pass `other` (any
    other Timeline) to switch away and back first; inserts return False on a freshly built timeline until
    Resolve reloads it. Locks every other video track and all audio so the insert lands on `track`.
    The Text+ reads `heading + wrapped text` (Text+ does not wrap scripted text; `textwrap` does it at
    `wrap` columns). Items are named `name_prefix + text` (cleaned of ':' and '/') and colored. Saves.
    Returns {"placed": [(start, duration)] or (start, "FAILED"), "texts_set": count}.
    """
    resolve.OpenPage("edit")
    if other is not None:
        refresh_timeline(project, timeline, other)
    s = timeline.GetStartFrame()
    fps = fps or timeline_fps(timeline)
    placed = []
    with track_locks(timeline, track):
        for a, b, text in spans:
            it = insert_fusion_title(timeline, a, b - a, fps)
            if not it:
                placed.append((a, "FAILED"))
                continue
            it.SetName(clean_name(name_prefix + text))
            it.SetClipColor(color)
            placed.append((it.GetStart() - s, it.GetDuration()))
    resolve.OpenPage("fusion")
    by = {a: text for a, b, text in spans}
    n = 0
    for it in items(timeline, "video", track):
        text = by.get(it.GetStart() - s)
        c = it.GetFusionCompByIndex(1)
        if text is None or c is None:
            continue
        if style_text_plus(c, heading + "\n".join(textwrap.wrap(text, wrap)), font, style, size, rgb):
            n += 1
    resolve.OpenPage("edit")
    save(resolve)
    return {"placed": placed, "texts_set": n}


def title_fitted_to_clip(resolve, project, timeline, clip_track: int, clip_name: str, track: int, text: str,
                         other=None, font: str = "Inter 28pt", style: str = "Medium", size: float = 0.045,
                         rgb: Tuple[float, float, float] = (1, 1, 1), color: str = "Violet",
                         name_prefix: str = "TITLE - ") -> Dict:
    """Insert a Text+ title on `track` spanning exactly one clip's extent (found by name on `clip_track`).

    Same locking and marks choreography as `text_placeholders`; `other` triggers the switch-away refresh.
    The item is named `name_prefix + text`, colored, and its TextPlus tool styled. Saves.
    Returns {"title": (name, start, duration), "clip": (name, start, duration), "fits": bool}.
    """
    resolve.OpenPage("edit")
    if other is not None:
        refresh_timeline(project, timeline, other)
    s = timeline.GetStartFrame()
    fps = timeline_fps(timeline)
    clip = [x for x in items(timeline, "video", clip_track) if x.GetName() == clip_name][0]
    start, dur = clip.GetStart() - s, clip.GetDuration()
    with track_locks(timeline, track):
        it = insert_fusion_title(timeline, start, dur, fps)
    it.SetName(f"{name_prefix}{text}")
    it.SetClipColor(color)
    resolve.OpenPage("fusion")
    style_text_plus(it.GetFusionCompByIndex(1), text, font, style, size, rgb)
    resolve.OpenPage("edit")
    save(resolve)
    return {"title": (it.GetName(), it.GetStart() - s, it.GetDuration()), "clip": (clip.GetName(), start, dur), "fits": it.GetDuration() == dur}


def retrim_title(resolve, project, timeline, track: int, start: int, duration: int, other=None,
                 font: str = "Inter 28pt", style: str = "Medium", size: float = 0.045,
                 rgb: Tuple[float, float, float] = (1, 0.85, 0.35), color: str = "Orange") -> Dict:
    """Give the Text+ title that starts at `start` on `track` a new `duration`, leaving every other title in place.

    The workaround for the missing duration setter, done without disturbing the track: an
    `InsertFusionTitleIntoTimeline` is a ripple on its track, so every title to the right of `start` is
    snapshotted (name, start, duration, StyledText read on the Fusion page), deleted together with the
    target, the timeline is refreshed (`other`), then the target and the snapshotted titles are re-inserted
    in ascending order with `insert_fusion_title` (nothing sits to their right, so nothing ripples) and
    restyled with `style_text_plus`. Saves. Returns {"title": (name, start, end), "restored": n,
    "misplaced": [(name, wanted, got)]}.
    """
    resolve.OpenPage("edit")
    s = timeline.GetStartFrame()
    fps = timeline_fps(timeline)
    right = [x for x in items(timeline, "video", track) if x.GetStart() - s >= start]
    if not right or right[0].GetStart() - s != start:
        return {"title": None, "restored": 0, "misplaced": [], "error": f"no title starts at {start}"}
    resolve.OpenPage("fusion")
    snap = []
    for x in right:
        tools = [q for q in x.GetFusionCompByIndex(1).GetToolList().values() if q.ID == "TextPlus"]
        snap.append({"name": x.GetName(), "start": x.GetStart() - s, "dur": x.GetDuration(),
                     "color": x.GetClipColor(), "text": tools[0].GetInput("StyledText") if tools else None})
    snap[0]["dur"] = duration
    resolve.OpenPage("edit")
    timeline.DeleteClips(right, False)
    if other is not None:
        refresh_timeline(project, timeline, other)
        resolve.OpenPage("edit")
    misplaced = []
    with track_locks(timeline, track):
        for c in snap:
            it = insert_fusion_title(timeline, c["start"], c["dur"], fps)
            if not it:
                misplaced.append((c["name"], c["start"], None))
                continue
            it.SetName(c["name"])
            it.SetClipColor(c["color"] or color)
            if it.GetStart() - s != c["start"] or it.GetDuration() != c["dur"]:
                misplaced.append((c["name"], c["start"], it.GetStart() - s))
    resolve.OpenPage("fusion")
    for c in snap:
        hit = [q for q in items(timeline, "video", track) if q.GetStart() - s == c["start"]]
        if hit and c["text"] is not None:
            style_text_plus(hit[0].GetFusionCompByIndex(1), c["text"], font, style, size, rgb)
    resolve.OpenPage("edit")
    save(resolve)
    head = [q for q in items(timeline, "video", track) if q.GetStart() - s == start]
    title = (head[0].GetName(), start, head[0].GetEnd() - s) if head else None
    return {"title": title, "restored": len(snap) - 1, "misplaced": misplaced}


def fusion_vignette_layer(resolve, project, timeline, track_name: str = "GFX", center: Tuple[float, float] = (0.5, 0.5),
                          width: float = 1.0, height: float = 1.0, soft: float = 0.25, opacity: float = 70.0,
                          fps: Optional[int] = None, name: str = "GFX · Vignette", color: str = "Teal") -> Dict:
    """Add a vignette as a Fusion composition on a new top video track spanning the whole of V1.

    No call draws a power window or adds a ResolveFX, so the comp is built by hand: a black `Background`
    masked by an inverted soft `EllipseMask` (`Center`, `Width`, `Height`, `SoftEdge`, `Invert`) wired into
    `MediaOut`, with the item's `Opacity` lowered. Adds the track, names it, switches cut -> edit (inserts
    need the Edit page and the track layout reads stale until a page switch), locks the other tracks,
    inserts from frame 0 to the end of the last V1 item, builds the comp on the Fusion page. Saves.
    Returns {"track", "item": (name, start, duration), "opacity"} or {"error": "insert failed"}.
    """
    project.SetCurrentTimeline(timeline)
    s = timeline.GetStartFrame()
    fps = fps or timeline_fps(timeline)
    resolve.OpenPage("edit")
    timeline.AddTrack("video")
    nv = timeline.GetTrackCount("video")
    timeline.SetTrackName("video", nv, track_name)
    resolve.OpenPage("cut")
    resolve.OpenPage("edit")
    with track_locks(timeline, nv):
        end = items(timeline, "video", 1)[-1].GetEnd() - s
        vg = insert_fusion_composition(timeline, 0, end, fps)
    if not vg:
        return {"error": "insert failed"}
    vg.SetName(name)
    vg.SetClipColor(color)
    resolve.OpenPage("fusion")
    c = vg.GetFusionCompByIndex(1) or vg.AddFusionComp()
    mo = [x for x in c.GetToolList().values() if x.ID == "MediaOut"][0]
    bg = c.AddTool("Background", 0, 0)
    bg.SetAttrs({"TOOLS_Name": "BgVig"})
    for k in ("TopLeftRed", "TopLeftGreen", "TopLeftBlue"):
        bg.SetInput(k, 0.0)
    bg.SetInput("TopLeftAlpha", 1.0)
    el = c.AddTool("EllipseMask", 0, 0)
    el.SetAttrs({"TOOLS_Name": "EllVig"})
    el.SetInput("Center", {1: center[0], 2: center[1]})
    el.SetInput("Width", width)
    el.SetInput("Height", height)
    el.SetInput("SoftEdge", soft)
    el.SetInput("Invert", 1)
    bg.ConnectInput("EffectMask", el)
    mo.ConnectInput("Input", bg)
    resolve.OpenPage("edit")
    vg.SetProperty("Opacity", opacity)
    save(resolve)
    return {"track": nv, "item": (vg.GetName(), vg.GetStart() - s, vg.GetDuration()), "opacity": vg.GetProperty("Opacity")}
