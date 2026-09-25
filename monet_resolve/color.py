"""Color page: DRX grades and CDL, input color space, stills."""
import time
from typing import Dict, Sequence

from ._util import items, save, tc, timeline_fps


def grade_all_clips(resolve, project, timeline, drx: str, nodes: int, cdls: Sequence[Dict], track: int = 1,
                    settle: float = 1.5) -> Dict:
    """Apply a saved DRX node tree to every clip on a track that lacks it, then set CDL values on chosen nodes.

    Saves first. Opens the Color page and sleeps `settle` seconds: `GetNodeGraph` is None right after the
    page switch and Resolve crashed twice in that state, so when the attribute is missing on the first item
    this returns {"attr_ok": False} without grading; re-run instead of looping. A clip gets
    `ApplyGradeFromDRX(drx, 0)` when `GetNumNodes() != nodes`; every clip gets each `SetCDL(cdl)` where a
    cdl is {"NodeIndex", "Slope", "Offset", "Power", "Saturation"}. Saves and returns to the Edit page.
    A DRX built for log footage expects the clips' input color space to be set first (`set_input_color_space`).
    Returns {"attr_ok", "clips", "drx_applied", "cdl_set", "node_counts"}.
    """
    pm = resolve.GetProjectManager()
    pm.SaveProject()
    project.SetCurrentTimeline(timeline)
    resolve.OpenPage("color")
    time.sleep(settle)
    its = items(timeline, "video", track)
    out = {"attr_ok": bool(its) and getattr(its[0], "GetNodeGraph", None) is not None, "clips": len(its)}
    if out["attr_ok"]:
        applied = 0
        cdl = 0
        for it in its:
            g = it.GetNodeGraph()
            if g.GetNumNodes() != nodes and g.ApplyGradeFromDRX(drx, 0):
                applied += 1
            if all(it.SetCDL(dict(c)) for c in cdls):
                cdl += 1
        out["drx_applied"] = applied
        out["cdl_set"] = cdl
        out["node_counts"] = sorted({x.GetNodeGraph().GetNumNodes() for x in its})
        pm.SaveProject()
    resolve.OpenPage("edit")
    return out


def set_input_color_space(resolve, clip, candidates: Sequence[str]) -> Dict:
    """Set a clip's input color space, trying the name variants in order until one is accepted.

    `SetClipProperty("Input Color Space", name)` returns False on the wrong spelling and lists no accepted
    names, so pass the variants (for Sony S-Log2: "Sony S-Gamut/S-Log2", "Sony S-Gamut S-Log2",
    "S-Gamut/S-Log2"). Saves. Returns {"clip", "tried": {name: bool}, "input_color_space"}.
    """
    tried = {}
    for cs in candidates:
        tried[cs] = clip.SetClipProperty("Input Color Space", cs)
        if tried[cs]:
            break
    save(resolve)
    return {"clip": clip.GetName(), "tried": tried, "input_color_space": clip.GetClipProperty("Input Color Space")}


def export_stills(resolve, project, timeline, out_dir: str, frames: Dict[str, int], fps: int = None,
                  settle: float = 1.2) -> Dict:
    """Export graded frames of a timeline as PNG stills from the Color page, one file per entry named after its key.

    `frames` maps name to frame relative to the timeline start; `out_dir` must exist and end with "/".
    Moves the playhead with `SetCurrentTimecode`, sleeps `settle` seconds, then
    `Project.ExportCurrentFrameAsStill(path)`. Color-page stills show the current clip's grade alone, with
    no upper tracks; `render.render_frame_tiff` is the ground truth for titles. Returns to the Edit page.
    Returns {name: (ok, timecode)}.
    """
    project.SetCurrentTimeline(timeline)
    s = timeline.GetStartFrame()
    fps = fps or timeline_fps(timeline)
    resolve.OpenPage("color")
    out = {}
    for name, f in frames.items():
        timeline.SetCurrentTimecode(tc(s + f, fps))
        time.sleep(settle)
        out[name] = (project.ExportCurrentFrameAsStill(out_dir + name + ".png"), timeline.GetCurrentTimecode())
    resolve.OpenPage("edit")
    return out
