"""Markers."""
from typing import Dict, Optional, Sequence, Tuple

from ._util import timeline_fps


def beat_markers(timeline, beats: Sequence[Tuple[float, str, str]], fps: Optional[int] = None, note: str = "beat") -> Dict:
    """Replace every marker on a timeline with one named, colored marker per beat.

    `beats` is [(seconds, name, color)]; seconds become `round(sec * fps)` frames relative to the timeline
    start. Deletes all existing markers first (`DeleteMarkerAtFrame`), then `AddMarker` with duration 1.
    Returns `timeline.GetMarkers()`.
    """
    fps = fps or timeline_fps(timeline)
    for k in list(timeline.GetMarkers().keys()):
        timeline.DeleteMarkerAtFrame(int(k))
    for sec, name, color in beats:
        timeline.AddMarker(round(sec * fps), color, name, note, 1)
    return timeline.GetMarkers()
