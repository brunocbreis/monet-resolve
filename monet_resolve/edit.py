"""Edit-page clip attributes: punch-ins and freeze frames."""
import time
from typing import Dict, Optional, Sequence, Tuple

from ._util import items, save, source_frames, tc, timeline_fps


def punch_in_clips(resolve, project, timeline, punches: Sequence[Tuple[int, str]], track: int = 1,
                   zoom: float = 1.3, tilt: float = -250.0, marker_color: str = "Cyan") -> Dict:
    """Punch in (zoom and tilt) on the clips that start at the given frames and mark each with a marker.

    `punches` is [(start_frame, note)] with frames relative to the timeline start; each clip gets
    `SetProperty` for ZoomX, ZoomY and Tilt, and a 1-frame marker named "PUNCH-IN <zoom>x" replaces any
    marker at that frame. Zoom 1.0 / Tilt 0 restores the wide framing. Saves.
    Returns {start: (name, ZoomX, Tilt)}.
    """
    project.SetCurrentTimeline(timeline)
    s = timeline.GetStartFrame()
    out = {}
    for p, note in punches:
        it = [x for x in items(timeline, "video", track) if x.GetStart() - s == p][0]
        it.SetProperty("ZoomX", zoom)
        it.SetProperty("ZoomY", zoom)
        it.SetProperty("Tilt", tilt)
        timeline.DeleteMarkerAtFrame(p)
        timeline.AddMarker(p, marker_color, f"PUNCH-IN {zoom}x", note, 1)
        out[p] = (it.GetName(), it.GetProperty("ZoomX"), it.GetProperty("Tilt"))
    save(resolve)
    return out


def alternate_punch_ins(resolve, project, timeline, track: int = 1, zoom: float = 1.3, tilt: float = -250.0,
                        marker_color: str = "Cyan") -> Dict:
    """Alternate wide and punched-in framing along a track and rewrite the punch-in markers.

    Each cut between touching clips in the same enabled state flips the framing. A continuation of the
    same take keeps it: same id (first word of the clip name) and source frames that continue within 2
    frames. Disabled (b-roll slot) clips alternate too so the camera returns in the other framing.
    Deletes every marker of `marker_color`, then adds one per punched-in enabled clip that starts a take.
    Saves. Returns {"camera": [(start, id, "W"|"P")] for enabled clips}.
    """
    project.SetCurrentTimeline(timeline)
    s = timeline.GetStartFrame()
    resolve.OpenPage("edit")
    prev = None
    plan = []
    for it in items(timeline, "video", track):
        st = it.GetStart() - s
        en = it.GetEnd() - s
        on = it.GetClipEnabled()
        tid = it.GetName().split(" ")[0]
        cont = prev is not None and prev["end"] == st and prev["tid"] == tid and abs(source_frames(it)[0] - prev["src_end"]) <= 2
        if cont:
            fr = prev["fr"]
        elif prev is not None and prev["end"] == st and prev["on"] == on:
            fr = "P" if prev["fr"] == "W" else "W"
        else:
            fr = "W"
        z, tl = (zoom, tilt) if fr == "P" else (1.0, 0.0)
        it.SetProperty("ZoomX", z)
        it.SetProperty("ZoomY", z)
        it.SetProperty("Tilt", tl)
        plan.append((st, tid, on, fr, cont))
        prev = {"end": en, "tid": tid, "on": on, "fr": fr, "src_end": source_frames(it)[1]}
    for k, v in timeline.GetMarkers().items():
        if v["color"] == marker_color:
            timeline.DeleteMarkerAtFrame(int(k))
    for st, tid, on, fr, cont in plan:
        if on and fr == "P" and not cont:
            timeline.AddMarker(st, marker_color, f"PUNCH-IN {zoom}x", tid, 1)
    save(resolve)
    return {"camera": [(st, tid, fr) for st, tid, on, fr, cont in plan if on]}


def freeze_item(timeline, item, fps: Optional[int] = None, settle: float = 0.4) -> Dict:
    """Turn a timeline item into a freeze frame of its first source frame, keeping its duration.

    `TimelineItem.SetSpeed({"Percentage": 0.0})` freezes on the frame under the playhead (clamped to the
    item), so the playhead is parked on the item's first frame first (`SetCurrentTimecode`, absolute) and
    the call waits `settle` seconds. The item keeps its duration and its first and last frame
    render identical. To freeze a chosen frame f for D timeline frames, append the source range [f, f + n) where
    n gives D frames at the clip's rate (n = D * source_fps / timeline_fps), then call this.
    Returns {"ok": bool, "duration", "source_frame"}.
    """
    timeline.SetCurrentTimecode(tc(item.GetStart(), fps or timeline_fps(timeline)))
    time.sleep(settle)
    ok = item.SetSpeed({"Percentage": 0.0})
    return {"ok": bool(ok), "duration": item.GetDuration(), "source_frame": source_frames(item)[0]}
