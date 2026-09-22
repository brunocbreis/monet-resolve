"""Fusion transitions built and applied through the API, so a cut gets the same push every time."""
import time
from typing import Dict, Optional

from ._util import save

DIRECTIONS = {  # axis driven by the progress, sign of travel for the outgoing clip; names follow the Direction
    # control of Resolve's simple Push: "right" = the incoming clip comes in from the right and pushes the
    # outgoing one out to the left (Bruno's push, 2026-09-22).
    "right": ("X", -1), "left": ("X", 1), "up": ("Y", -1), "down": ("Y", 1),
}


def build_push(comp, direction: str = "right", ease_in: str = "Cubic", ease_out: str = "Cubic") -> Dict:
    """Turn a Fusion transition comp into a push: the outgoing clip slides out, the incoming slides in behind it.

    Works on the comp of a transition item created with `AddTransition({"type": "Cross Dissolve",
    "category": "fusion", ...})`: Resolve gives it `MediaIn1` (outgoing), `MediaIn2` (incoming) and
    `MediaOut1`; the dissolve group and its lookup are deleted and replaced by an Anim Curves modifier
    (`LUTLookup`, Source "Transition" so it follows the transition length, Curve "Easing", cubic in and out)
    driving an XY Path on a Transform per clip (outgoing centre 0.5 → -0.5 on the travel axis for "right",
    incoming one frame behind via the expression `PushOutPath.X + 1`), merged and sent to MediaOut. `direction`
    is right/left/up/down in the sense of Resolve's Push Direction control: the side the incoming clip enters from. Call with the Fusion page open. Returns the tool names.
    Worked 2026-09-22 (Resolve 21.1) on a 16-frame transition.
    """
    axis, sign = DIRECTIONS[direction]
    other = "Y" if axis == "X" else "X"
    comp.Lock()
    for name in ("CrossDissolve", "AnimCurves1Lookup"):
        t = comp.FindTool(name)
        if t:
            t.Delete()
    mi1, mi2, mo = comp.FindTool("MediaIn1"), comp.FindTool("MediaIn2"), comp.FindTool("MediaOut1")
    def named(tool, name):
        tool.SetAttrs({"TOOLS_Name": name})
        return tool
    prog = named(comp.AddTool("LUTLookup", -1, -1), "PushProgress")
    # a negative Scale is ignored by the modifier, so the reverse travel uses Invert (1 - progress)
    for k, v in (("Source", "Transition"), ("Curve", "Easing"), ("EaseIn", ease_in), ("EaseOut", ease_out),
                 ("Scaling", 1), ("Scale", 1), ("Invert", 0 if sign > 0 else 1), ("Offset", 0.5 if sign > 0 else -0.5)):
        prog.SetInput(k, v)
    xf_out = named(comp.AddTool("Transform", 0, 0), "PushOut")
    xf_in = named(comp.AddTool("Transform", 0, 2), "PushIn")
    xy_out = named(comp.AddTool("XYPath", -1, -1), "PushOutPath")
    xy_in = named(comp.AddTool("XYPath", -1, -1), "PushInPath")
    xf_out.Center.ConnectTo(xy_out)
    xf_in.Center.ConnectTo(xy_in)
    getattr(xy_out, axis).ConnectTo(prog)
    xy_out.SetInput(other, 0.5)
    getattr(xy_in, axis).SetExpression(f"PushOutPath.{axis} {'-' if sign > 0 else '+'} 1")
    xy_in.SetInput(other, 0.5)
    mg = named(comp.AddTool("Merge", 2, 1), "PushMerge")
    xf_out.Input.ConnectTo(mi1.Output)
    xf_in.Input.ConnectTo(mi2.Output)
    mg.Background.ConnectTo(xf_out.Output)
    mg.Foreground.ConnectTo(xf_in.Output)
    mo.Input.ConnectTo(mg.Output)
    comp.Unlock()
    return {"tools": [t.Name for t in comp.GetToolList(False).values()],
            "progress": (prog.GetInput("Source"), prog.GetInput("Curve"), prog.GetInput("EaseIn"), prog.GetInput("EaseOut"))}


def add_push_transition(resolve, project, timeline, item, position: str = "end", duration: int = 16,
                        alignment: str = "center", direction: str = "right", ease_in: str = "Cubic",
                        ease_out: str = "Cubic", replace_existing: bool = True, save_comp_to: Optional[str] = None) -> Dict:
    """Put a push transition on one edge of `item`, built in Fusion so direction and ease are set by code.

    Steps: with `replace_existing` any transition item touching that edge of `item` on its track is deleted;
    `item.AddTransition({"type": "Cross Dissolve", "category": "fusion", position, alignment, duration})`
    creates the Fusion transition (that name is the only Fusion transition the API resolves without a
    restart; a user template dropped in Fusion/Templates/Edit/Transitions is not found by `AddTransition`
    until Resolve restarts); the Fusion page is opened, the comp rebuilt with `build_push`, the item renamed
    "Push <direction>", and the comp optionally written to `save_comp_to` (`Composition.Save`) as the text
    record of the transition (`TimelineItem.ExportFusionComp` returns False on transition items). Back on the
    Edit page, saves. Returns {"transition": (name, start, duration), "build": ...}. Worked 2026-09-22.
    """
    s = timeline.GetStartFrame()
    project.SetCurrentTimeline(timeline)
    kind, idx = item.GetTrackTypeAndIndex()
    edge = item.GetEnd() if position == "end" else item.GetStart()
    if replace_existing:
        for x in timeline.GetItemListInTrack(kind, idx):
            if x.GetType() == "transition" and x.GetStart() <= edge <= x.GetEnd():
                timeline.DeleteClips([x], False)
    tr = item.AddTransition({"type": "Cross Dissolve", "category": "fusion", "position": position,
                             "alignment": alignment, "duration": duration})
    if not tr:
        return {"error": "AddTransition returned None"}
    resolve.OpenPage("fusion")
    time.sleep(1)
    comp = tr.GetFusionCompByIndex(1)
    built = build_push(comp, direction, ease_in, ease_out)
    saved = comp.Save(save_comp_to) if save_comp_to else None
    tr.SetName(f"Push {direction}")
    resolve.OpenPage("edit")
    save(resolve)
    return {"transition": (tr.GetName(), tr.GetStart() - s, tr.GetDuration()), "build": built, "saved": saved}
