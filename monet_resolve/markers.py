"""Markers."""
from typing import Dict, Sequence, Tuple


def beat_markers(timeline, beats: Sequence[Tuple[float, str, str]], fps: int = 24, note: str = "beat") -> Dict:
    """Replace every marker on a timeline with one named, colored marker per beat.

    `beats` is [(seconds, name, color)]; seconds become `round(sec * fps)` frames relative to the timeline
    start. Deletes all existing markers first (`DeleteMarkerAtFrame`), then `AddMarker` with duration 1.
    Returns `timeline.GetMarkers()`. Worked 2026-09-11.
    """
    for k in list(timeline.GetMarkers().keys()):
        timeline.DeleteMarkerAtFrame(int(k))
    for sec, name, color in beats:
        timeline.AddMarker(round(sec * fps), color, name, note, 1)
    return timeline.GetMarkers()
