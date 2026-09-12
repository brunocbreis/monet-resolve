"""Helpers shared by the area modules: timecode, timeline lookup, track locks, name cleaning.

Frames in this package are relative to the timeline start (0 = first frame) unless a parameter is
named `record_frame`, which is absolute, matching the Resolve API. `tc()` takes an absolute frame.
"""
from contextlib import contextmanager
from typing import Iterator, List, Optional


def tc(frame: int, fps: int = 24) -> str:
    """Absolute frame number to 'hh:mm:ss:ff' at an integer frame rate.

    Pass `timeline.GetStartFrame() + relative_frame` for a frame counted from the timeline start.
    `SetCurrentTimecode` wants this absolute form; `SetMarkInOut` and `AddMarker` want relative frames.
    """
    fps = int(fps)
    return f"{frame // fps // 3600:02d}:{frame // fps // 60 % 60:02d}:{frame // fps % 60:02d}:{frame % fps:02d}"


def timeline_fps(timeline) -> int:
    """Integer frame rate of a timeline, read from its 'timelineFrameRate' setting."""
    return int(float(timeline.GetSetting("timelineFrameRate")))


def list_timelines(project) -> List:
    """Every Timeline of the project, in index order (the API has no list call)."""
    return [project.GetTimelineByIndex(i + 1) for i in range(project.GetTimelineCount())]


def find_timeline(project, name: str):
    """Return the Timeline named `name`. Raises LookupError when no timeline has that name.

    The API has no lookup by name; this iterates `GetTimelineByIndex(1..GetTimelineCount())`.
    """
    for t in list_timelines(project):
        if t.GetName() == name:
            return t
    raise LookupError(f"no timeline named {name!r}")


def items(timeline, kind: str, index: int) -> List:
    """`GetItemListInTrack` with the None-for-empty-track quirk folded into an empty list."""
    return timeline.GetItemListInTrack(kind, index) or []


def clean_name(name: str) -> str:
    """Make a name `SetName` accepts: ':' and '/' fail silently, so swap them for ' - ' and ' + '."""
    return name.replace(": ", " - ").replace(":", " -").replace("/", " + ")


@contextmanager
def track_locks(timeline, video_track: Optional[int] = None, lock_audio: bool = True) -> Iterator[None]:
    """Lock every video track except `video_track` (and all audio tracks), unlock all of them on exit.

    This is the stand-in for the destination toggle: `Insert*IntoTimeline` lands on the one unlocked
    video track. `video_track=None` locks every video track. The unlock runs even when the body raises.
    """
    nv = timeline.GetTrackCount("video")
    na = timeline.GetTrackCount("audio")
    for i in range(1, nv + 1):
        timeline.SetTrackLock("video", i, i != video_track)
    if lock_audio:
        for i in range(1, na + 1):
            timeline.SetTrackLock("audio", i, True)
    try:
        yield
    finally:
        for i in range(1, nv + 1):
            timeline.SetTrackLock("video", i, False)
        if lock_audio:
            for i in range(1, na + 1):
                timeline.SetTrackLock("audio", i, False)


def save(resolve) -> bool:
    """Save the current project. `Project.SaveProject` does not exist; the call lives on the ProjectManager."""
    return resolve.GetProjectManager().SaveProject()
