"""Speech-to-text through Resolve."""
from typing import Dict


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
