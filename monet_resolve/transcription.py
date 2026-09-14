"""Speech-to-text through Resolve."""
import os
import subprocess
import time
from typing import Dict, List, Optional, Tuple

from ._util import items


def transcribe_clip(clip, words: bool = False) -> Dict:
    """Transcribe a media pool clip with Resolve's speech-to-text and return segment lines or word timings.

    Reuses an existing transcription when `GetTranscription()` already has segments, otherwise calls
    `TranscribeAudio(False)` first. Word start/end are timecodes at the project frame rate, counted from
    the clip start; "(...)" segments are pauses. Full-clip transcription merges repeated takes: for take
    comparison, transcribe short WAV windows instead. Returns {"clip", "language", "segments", "text"}.
    Worked 2026-09-11.
    """
    tr = clip.GetTranscription()
    if not (tr and tr.get("segments")):
        clip.TranscribeAudio(False)
        tr = clip.GetTranscription()
    segs = tr.get("segments", []) if tr else []
    lines = [f'{s["start"]} - {s["end"]}  {s["text"]}' for s in segs]
    if words:
        lines = [f'{w["start"]} - {w["end"]}  {w["text"].strip()}' for s in segs for w in s["words"]]
    return {"clip": clip.GetName(), "language": tr.get("language") if tr else None, "segments": len(segs), "text": "\n".join(lines)}


def transcribe_words(folder, clip_name: str, timeout: int = 90) -> List[Tuple[str, str, str]]:
    """Word timings of a clip in `folder`, polling with a fresh MediaPoolItem each second.

    `GetTranscription()` on the proxy that called `TranscribeAudio` keeps returning None after the job has
    finished; the same clip fetched again from `folder.GetClipList()` has the segments. So: call
    `TranscribeAudio(False)` once, then re-fetch the clip every second until segments appear (`timeout` s).
    Returns [(start_tc, end_tc, word)] with timecodes counted from the clip start at the project rate.
    Worked 2026-09-14.
    """
    tr = None
    for i in range(timeout):
        c = [x for x in folder.GetClipList() if x.GetName() == clip_name][0]
        tr = c.GetTranscription()
        if tr and tr.get("segments"):
            break
        if i == 0:
            c.TranscribeAudio(False)
        time.sleep(1)
    return [(w["start"], w["end"], w["text"].strip()) for sg in (tr or {}).get("segments", []) for w in sg.get("words", [])]


def transcribe_timeline_range(project, timeline, start: int, end: int, out_dir: str, scratch_folder, tag: str,
                              width: int = 960, height: int = 540, timeout: int = 120) -> Dict:
    """Ground truth for a slot: render frames `start`..`end` (relative, inclusive) of `timeline`, transcribe the audio.

    Renders a small H.264 mp4 through the Deliver page (MarkIn/MarkOut absolute), pulls a mono 48 kHz wav
    with ffmpeg next to it, imports the wav into `scratch_folder` and runs `transcribe_words` on it. Use it
    before cutting takes: word timings from the full camera clip's transcript drift by more than a second
    and merge repeated takes (2026-09-14: a take cut from them started on the previous line and ended
    mid-sentence), while the rendered slot's own transcript is frame-accurate to the slot.
    Returns {"mp4", "wav", "words": [(start_tc, end_tc, word)], "text"}. Worked 2026-09-14.
    """
    mp = project.GetMediaPool()
    root = mp.GetRootFolder()
    project.SetCurrentTimeline(timeline)
    s = timeline.GetStartFrame()
    project.DeleteAllRenderJobs()
    project.SetCurrentRenderFormatAndCodec("mp4", "H264")
    project.SetRenderSettings({"SelectAllFrames": False, "MarkIn": s + start, "MarkOut": s + end, "TargetDir": out_dir, "CustomName": tag,
                               "FormatWidth": width, "FormatHeight": height, "ExportVideo": True, "ExportAudio": True, "UseRenderCachedImages": False})
    job = project.AddRenderJob()
    project.StartRendering([job], False)
    t0 = time.time()
    while project.IsRenderingInProgress() and time.time() - t0 < timeout:
        time.sleep(0.5)
    project.DeleteAllRenderJobs()
    mp4 = os.path.join(out_dir, tag + ".mp4")
    wav = os.path.join(out_dir, tag + ".wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-vn", "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", wav], check=True)
    mp.SetCurrentFolder(scratch_folder)
    have = [c for c in scratch_folder.GetClipList() if c.GetClipProperty("File Path") == wav]
    if not have:
        mp.ImportMedia([wav])
    mp.SetCurrentFolder(root)
    words = transcribe_words(scratch_folder, tag + ".wav")
    return {"mp4": mp4, "wav": wav, "words": words, "text": " ".join(w for _, _, w in words)}
