"""Freeze frames."""
import time
from typing import Dict, Optional

from ._util import source_frames, tc, timeline_fps


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
