"""Color page: input color space, stills."""
import time
from typing import Dict, Sequence

from ._util import save, tc, timeline_fps


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
