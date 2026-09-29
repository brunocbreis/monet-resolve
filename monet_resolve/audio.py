"""Audio: external sync, channel mapping, crossfades, music cues."""
import json
from typing import Dict, Sequence, Tuple

from ._util import add_tracks_until, items, save


def sync_external_audio(resolve, media_pool, video_clip, audio_clip, channel_number: int = 1) -> bool:
    """Sync an external audio recording to a camera clip by waveform (`MediaPool.AutoSyncAudio`).

    Afterward the camera clip carries the external channels after its own (ch 1-2 camera mic, ch 3-4
    external mic) and keeps its embedded audio (`retainEmbeddedAudio`, `retainVideoMetadata` both True).
    Returns the API's boolean.
    """
    return media_pool.AutoSyncAudio([video_clip, audio_clip], {
        "syncMode": resolve.AUDIO_SYNC_WAVEFORM,
        "channelNumber": channel_number,
        "retainEmbeddedAudio": True,
        "retainVideoMetadata": True,
    })


def set_clip_audio_mapping(clip, mapping: Dict) -> Dict:
    """Set a media pool clip's `track_mapping` so every later append lands the right channels on the right tracks.

    `mapping` is Resolve's track_mapping JSON as a dict, e.g. {"1": {"channel_idx": [3], "type": "mono"}}
    for a mono track 1 fed by channel 3. Reads `GetAudioMapping()` as JSON, swaps `track_mapping`, writes it
    back with `SetAudioMapping`. Items already on a timeline keep their mapping. Returns {"clip_set": bool, "map": the mapping read back}.
    """
    m = json.loads(clip.GetAudioMapping())
    m["track_mapping"] = mapping
    return {"clip_set": clip.SetAudioMapping(json.dumps(m)), "map": json.loads(clip.GetAudioMapping())["track_mapping"]}


def audio_crossfades(resolve, project, timeline, track: int = 1, frames: int = 4,
                     transition_type: str = "Cross Fade +3 dB") -> Dict:
    """Add a short centered audio crossfade between every pair of touching clips on one audio track.

    Iterates items that have a media pool item (transitions have none), and where `x.GetEnd() ==
    y.GetStart()` calls `x.AddTransition({"type", "category": "audio", "position": "end", "alignment":
    "center", "duration": frames})`. Saves. Returns {"crossfades": added, "clips": count}.
    """
    project.SetCurrentTimeline(timeline)
    resolve.OpenPage("edit")
    a = [x for x in items(timeline, "audio", track) if x.GetMediaPoolItem()]
    n = 0
    for x, y in zip(a, a[1:]):
        if x.GetEnd() == y.GetStart() and x.AddTransition({"type": transition_type, "category": "audio", "position": "end", "alignment": "center", "duration": frames}):
            n += 1
    save(resolve)
    return {"crossfades": n, "clips": len(a)}


def place_music(resolve, project, timeline, track: int, music_bin,
                cues: Sequence[Tuple[str, str, int, int, int, float, int, int]],
                color: str = "Purple", clear_track: bool = False) -> Dict:
    """Lay music cues on an audio track with name, color, volume and fades.

    `cues` is [(name, clip_name, src_in, src_out, record, volume_db, fade_in, fade_out)]; `clip_name` is
    looked up in `music_bin` (a Folder); `record` is frames from the timeline start; `src_out` is exclusive (`endFrame`).
    Adds stereo audio tracks until `track` exists. `clear_track=True` deletes every clip already on the
    track first (destructive). Each cue is `AppendToTimeline` with `mediaType: 2`, then `SetName`,
    `SetClipColor`, `SetProperty("AudioVolume", dB)`, `SetFades({"FadeIn", "FadeOut"})`. Saves.
    Returns {"placed": [(name, start, end, volume, fades)] or (name, "FAILED"), "cut_end": frames}.
    """
    mp = project.GetMediaPool()
    music = {c.GetName(): c for c in music_bin.GetClipList()}
    project.SetCurrentTimeline(timeline)
    s = timeline.GetStartFrame()
    resolve.OpenPage("edit")
    add_tracks_until(timeline, "audio", track, "stereo")
    if clear_track:
        old = [x for x in items(timeline, "audio", track) if x.GetMediaPoolItem()]
        if old:
            timeline.DeleteClips(old, False)
    placed = []
    for name, clip, si, so, rec, vol, fi, fo in cues:
        new = mp.AppendToTimeline([{"mediaPoolItem": music[clip], "startFrame": si, "endFrame": so, "trackIndex": track, "recordFrame": s + rec, "mediaType": 2}])
        if not new:
            placed.append((name, "FAILED"))
            continue
        it = new[0]
        it.SetName(name)
        it.SetClipColor(color)
        it.SetProperty("AudioVolume", vol)
        it.SetFades({"FadeIn": fi, "FadeOut": fo})
        placed.append((it.GetName(), it.GetStart() - s, it.GetEnd() - s, it.GetProperty("AudioVolume"), it.GetFades()))
    save(resolve)
    return {"placed": placed, "cut_end": timeline.GetEndFrame() - s}
