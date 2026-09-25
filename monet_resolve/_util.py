"""Helpers shared by the area modules: timecode, timeline lookup, track locks, name cleaning.

Frames in this package are relative to the timeline start (0 = first frame) unless a parameter is
named `record_frame`, which is absolute, matching the Resolve API. `tc()` takes an absolute frame.
"""
from contextlib import contextmanager
from typing import Iterator, List, Optional, Sequence, Tuple

# Edit-page Inspector properties carried over when an item is deleted and re-appended.
VIDEO_PROPS = ["ZoomX", "ZoomY", "Pan", "Tilt", "AnchorPointX", "AnchorPointY", "RotationAngle", "FlipX", "FlipY",
               "Opacity", "CompositeMode", "CropLeft", "CropRight", "CropTop", "CropBottom", "CropSoftness",
               "CropRetain", "DynamicZoomEase"]


def tc(frame: int, fps: int = 24) -> str:
    """Absolute frame number to 'hh:mm:ss:ff' at an integer frame rate.

    Pass `timeline.GetStartFrame() + relative_frame` for a frame counted from the timeline start.
    `SetCurrentTimecode` wants this absolute form; `SetMarkInOut` and `AddMarker` want relative frames.
    """
    fps = int(fps)
    return f"{frame // fps // 3600:02d}:{frame // fps // 60 % 60:02d}:{frame // fps % 60:02d}:{frame % fps:02d}"


def tc_seconds(timecode: str, fps: float) -> float:
    """'hh:mm:ss:ff' (or drop-frame 'hh:mm:ss;ff') to seconds."""
    h, m, sec, f = [int(v) for v in timecode.replace(";", ":").split(":")]
    return h * 3600 + m * 60 + sec + f / round(fps)


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


def source_frames(item) -> Tuple[int, int]:
    """(first, end) source frames of a timeline item at its clip's own rate, end exclusive.

    `GetSourceStartFrame()`/`GetSourceEndFrame()` floor a float and can read one frame early (an item that
    shows source frame 400 reads 399), so this computes the frames from `GetSourceStartTime()` /
    `GetSourceEndTime()` (seconds, counted from the clip's Start TC). Items without a media pool clip fall
    back to the floored values.
    """
    clip = item.GetMediaPoolItem()
    if not clip:
        return item.GetSourceStartFrame(), item.GetSourceEndFrame()
    fps = float(clip.GetClipProperty("FPS") or 24)
    t0 = tc_seconds(clip.GetClipProperty("Start TC") or "00:00:00:00", fps)
    return round((item.GetSourceStartTime() - t0) * fps), round((item.GetSourceEndTime() - t0) * fps)


def add_tracks_until(timeline, kind: str, count: int, subtype: Optional[str] = None) -> None:
    """Add `kind` tracks ("video" or "audio", with `subtype` such as "stereo") until the timeline has `count`."""
    while timeline.GetTrackCount(kind) < count:
        if subtype:
            timeline.AddTrack(kind, subtype)
        else:
            timeline.AddTrack(kind)


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


def append_exact(media_pool, timeline, clip, track: int, record: int, frames: int, source_start: int,
                 media_type: int = 1, exact: bool = True, tries: Sequence[int] = (0, 1, -1, 2)):
    """Append `frames` of `clip` from `source_start` at `record` (relative) on `track`, exact in duration
    and, with `exact`, in source start (`source_start` is in the clip's own frames). `timeline` must be the current timeline: `AppendToTimeline` always
    appends to the current one. Returns the item (the closest one when no try lands exactly; check its source start),
    or None when no append reached the duration."""
    s = timeline.GetStartFrame()
    tl_fps = float(timeline.GetSetting("timelineFrameRate") or 24)
    ratio = float(clip.GetClipProperty("FPS") or tl_fps) / tl_fps
    last = None
    for off in (tries if exact else (0,)):
        sf = source_start + off
        end = sf + round(frames * ratio) - 1
        n = None
        for _ in range(6):
            r = media_pool.AppendToTimeline([{"mediaPoolItem": clip, "startFrame": sf, "endFrame": end, "trackIndex": track,
                                              "recordFrame": s + record, "mediaType": media_type}])
            n = r[0] if r else None
            d = n.GetDuration() if n else None
            if d is None:          # the append failed (for example on a timeline that is not current)
                n = None
                break
            if d == frames:
                break
            timeline.DeleteClips([n], False)
            end += round((frames - d) * ratio) or (1 if frames > d else -1)
            n = None
        if n is None:
            continue
        if not exact or source_frames(n)[0] == source_start:
            return n
        if last is not None:
            timeline.DeleteClips([last], False)
        last = n
    return last
