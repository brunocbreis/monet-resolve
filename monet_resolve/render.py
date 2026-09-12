"""Deliver page: frame renders and timeline renders."""
import time
from typing import Dict

from ._util import save


def render_frame_tiff(project, timeline, out_dir: str, frames: Dict[str, int], timeout: float = 80,
                      clear_queue: bool = True) -> Dict:
    """Render single frames of a timeline as TIFF (RGB8) files, one render job per frame, and wait for them.

    `frames` maps file name to frame relative to the timeline start. `clear_queue=True` (default) calls
    `DeleteAllRenderJobs()` first, which drops every job in the Deliver queue. Each job sets `MarkIn ==
    MarkOut` in absolute frames with `SelectAllFrames: False`. Waits up to `timeout` seconds while
    `IsRenderingInProgress()`. This is the ground truth for checking titles and upper tracks as pixels.
    Returns {"format": SetCurrentRenderFormatAndCodec result, "status": [GetRenderJobStatus per job]}.
    Worked 2026-09-11.
    """
    project.SetCurrentTimeline(timeline)
    s = timeline.GetStartFrame()
    if clear_queue:
        project.DeleteAllRenderJobs()
    fmt = project.SetCurrentRenderFormatAndCodec("tif", "RGB8")
    jobs = []
    for name, f in frames.items():
        project.SetRenderSettings({"SelectAllFrames": False, "MarkIn": s + f, "MarkOut": s + f, "TargetDir": out_dir, "CustomName": name,
                                   "ExportVideo": True, "ExportAudio": False, "UseRenderCachedImages": False})
        jobs.append(project.AddRenderJob())
    project.StartRendering(jobs, False)
    t0 = time.time()
    while project.IsRenderingInProgress() and time.time() - t0 < timeout:
        time.sleep(0.5)
    return {"format": fmt, "status": [project.GetRenderJobStatus(j) for j in jobs]}


def render_timeline_mp4(resolve, project, timeline, out_dir: str, name: str, width: int = 1920, height: int = 1080,
                        wait: int = 55, clear_queue: bool = True) -> Dict:
    """Render a whole timeline to H.264 MP4 at `width` x `height` and poll until the job leaves "Rendering".

    Saves first. `clear_queue=True` (default) calls `DeleteAllRenderJobs()`. Uses
    `SetCurrentRenderFormatAndCodec("mp4", "H264")` plus `FormatWidth`/`FormatHeight` because preset names
    vary between machines. Polls `GetRenderJobStatus` once a second for up to `wait` seconds; a long render
    outlives the call, so poll the returned job id again later. Returns {"job", "started", "status"}.
    Worked 2026-09-11.
    """
    project.SetCurrentTimeline(timeline)
    save(resolve)
    if clear_queue:
        project.DeleteAllRenderJobs()
    project.SetCurrentRenderFormatAndCodec("mp4", "H264")
    project.SetRenderSettings({"SelectAllFrames": True, "TargetDir": out_dir, "CustomName": name, "FormatWidth": width, "FormatHeight": height,
                               "ExportVideo": True, "ExportAudio": True, "UseRenderCachedImages": False})
    job = project.AddRenderJob()
    started = project.StartRendering([job], False)
    st = None
    for _ in range(wait):
        st = project.GetRenderJobStatus(job)
        if st.get("JobStatus") != "Rendering":
            break
        time.sleep(1)
    return {"job": job, "started": started, "status": st}
