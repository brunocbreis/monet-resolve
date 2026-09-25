"""Build the testbed project from nothing: generate media, create the project, import, lay out the base timelines.

    python3 -m testbed.build           # create "monet-testbed"; stops if it already exists
    python3 -m testbed.build --fresh   # delete "monet-testbed" first and rebuild it

Base timelines (24p, 1920x1080), both in `timelines/base`:

- `base · a-roll`: one video and one audio track of camera pieces from 24p, 25p and 30p sources, one
  gap and section markers.
- `base · layered`: the a-roll pieces on V1/A1, a screen recording over part of it on V2, a GFX clip
  on V3 and one long audio clip on A2 that runs across several edits.
- `base · angles`: WIDE and CLOSE pieces cut from the two raw angle files that make up the multicam
  clip `mcam · wide+close` (synced by their shared timecode, in the `multicam` bin).

Every piece is listed in PIECES / LAYERS with its record frame, so a check knows what "before" was.
"""
import os
import sys

import monet_resolve as mr

from . import media

PROJECT = "monet-testbed"
MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")
BINS = {"cam_a_24p.mov": "footage", "cam_b_25p.mov": "footage", "cam_c_30p.mov": "footage", "cam_d_4ch.mov": "footage",
        "mc_wide_24p.mov": "multicam", "mc_close_25p.mov": "multicam", "ext_mic.wav": "audio",
        "screen_60p.mov": "screen", "gfx_v1.mov": "gfx", "gfx_v2.mov": "gfx", "music.wav": "music", "icon.png": "stills"}
MULTICAM = "mcam · wide+close"
# `base · angles` on V1/A1: (name, clip file, source in as 24p position, timeline frames, record frame)
ANGLES = [
    ("WIDE · one", "mc_wide_24p.mov", 0, 96, 0),
    ("CLOSE · two", "mc_close_25p.mov", 96, 120, 96),
    ("WIDE · three", "mc_wide_24p.mov", 216, 72, 216),
    ("CLOSE · four", "mc_close_25p.mov", 288, 96, 288),
]

# a-roll on V1/A1: (name, clip file, source in, timeline frames, record frame)
PIECES = [
    ("A1 · intro", "cam_a_24p.mov", 0, 96, 0),
    ("B1 · answer", "cam_b_25p.mov", 50, 120, 96),
    ("A2 · follow-up", "cam_a_24p.mov", 240, 72, 216),
    ("C1 · reaction", "cam_c_30p.mov", 60, 48, 288),
    # gap from 336 to 384
    ("A3 · second part", "cam_a_24p.mov", 400, 120, 384),
    ("B2 · closing", "cam_b_25p.mov", 400, 96, 504),
]
GAP = (336, 48)
MARKERS = [(0, "Blue", "INTRO"), (216, "Blue", "MIDDLE"), (504, "Blue", "CLOSING")]
# layers of `base · layered`: (name, clip file, source in, timeline frames, record frame, track kind, track)
LAYERS = [
    ("SCREEN · demo", "screen_60p.mov", 120, 96, 120, "video", 2),
    ("GFX · title card", "gfx_v1.mov", 0, 72, 400, "video", 3),
    ("A2 · long clip", "music.wav", 0, 480, 48, "audio", 2),
]


def _fresh_project(resolve, fresh: bool):
    pm = resolve.GetProjectManager()
    cur = pm.GetCurrentProject()
    if PROJECT in (pm.GetProjectListInCurrentFolder() or []):
        if not fresh:
            raise SystemExit(f"{PROJECT!r} exists; pass --fresh to delete and rebuild it")
        if cur and cur.GetName() == PROJECT:
            pm.CloseProject(cur)
        if not pm.DeleteProject(PROJECT):
            raise SystemExit(f"could not delete {PROJECT!r} (close it in Resolve first)")
    project = pm.CreateProject(PROJECT)
    if not project:
        raise SystemExit(f"CreateProject({PROJECT!r}) failed")
    for k, v in {"timelineFrameRate": "24", "timelinePlaybackFrameRate": "24",
                 "timelineResolutionWidth": "1920", "timelineResolutionHeight": "1080"}.items():
        project.SetSetting(k, v)
    return project


def _bins(mp):
    root = mp.GetRootFolder()
    made = {}
    for name in ("footage", "multicam", "audio", "screen", "gfx", "music", "stills", "timelines"):
        made[name] = mp.AddSubFolder(root, name)
    for name in ("base", "checks", "gfx", "backups"):
        made["timelines/" + name] = mp.AddSubFolder(made["timelines"], name)
    return made


def _place(mp, timeline, clip, src_in, frames, record, track, media_type=None):
    """Append `frames` timeline frames of `clip` from 24p position `src_in` at `record`; video and audio stay
    linked when `media_type` is None. Raises when the item does not land exactly."""
    fps = float(clip.GetClipProperty("FPS") or 24)
    a = round(src_in * fps / 24)
    info = {"mediaPoolItem": clip, "startFrame": a, "endFrame": a + round(frames * fps / 24),
            "trackIndex": track, "recordFrame": timeline.GetStartFrame() + record}
    if media_type:
        info["mediaType"] = media_type
    new = [x for x in (mp.AppendToTimeline([info]) or []) if x]
    s = timeline.GetStartFrame()
    if not new or any(x.GetStart() - s != record or x.GetDuration() != frames for x in new):
        raise RuntimeError(f"{clip.GetName()} landed as {[(x.GetStart() - s, x.GetDuration()) for x in new]}, "
                           f"wanted ({record}, {frames})")
    return new


def _a_roll(mp, bins, clips, name, pieces=PIECES):
    mp.SetCurrentFolder(bins["timelines/base"])
    t = mp.CreateEmptyTimeline(name)
    mp.SetCurrentFolder(mp.GetRootFolder())
    t.SetTrackName("video", 1, "A-ROLL")
    t.SetTrackName("audio", 1, "DIALOGUE")
    for label, fname, src_in, frames, record in pieces:
        for it in _place(mp, t, clips[fname], src_in, frames, record, 1):
            it.SetName(label)
            it.SetClipColor("Green")
    if pieces is PIECES:
        for frame, color, label in MARKERS:
            t.AddMarker(frame, color, label, "", 1)
    return t


def build(fresh: bool = False) -> dict:
    paths = media.generate(MEDIA_DIR)
    resolve, _ = mr.connect(require_project=False)
    project = _fresh_project(resolve, fresh)
    mp = project.GetMediaPool()
    bins = _bins(mp)
    clips = {}
    for path in paths:
        mp.SetCurrentFolder(bins[BINS[os.path.basename(path)]])
        imported = mp.ImportMedia([path]) or []
        clips[os.path.basename(path)] = imported[0]
    mp.SetCurrentFolder(mp.GetRootFolder())
    resolve.OpenPage("edit")

    _a_roll(mp, bins, clips, "base · a-roll")
    layered = _a_roll(mp, bins, clips, "base · layered")
    mr.add_tracks_until(layered, "video", 3)
    layered.AddTrack("audio", "stereo")
    layered.SetTrackName("video", 2, "SCREEN")
    layered.SetTrackName("video", 3, "GFX")
    layered.SetTrackName("audio", 2, "LONG")
    colors = {"SCREEN": "Navy", "GFX": "Teal", "A2": "Purple"}
    for label, fname, src_in, frames, record, kind, track in LAYERS:
        for it in _place(mp, layered, clips[fname], src_in, frames, record, track, 1 if kind == "video" else 2):
            it.SetName(label)
            it.SetClipColor(colors[label.split(" ·")[0]])
    mp.SetCurrentFolder(bins["multicam"])
    made = mp.CreateMulticamClip([clips["mc_wide_24p.mov"], clips["mc_close_25p.mov"]], {
        "name": MULTICAM, "startTimecode": "15:00:00:00", "angleSyncMode": resolve.MULTICAM_ANGLE_SYNC_TIMECODE,
        "angleNameMode": resolve.MULTICAM_ANGLE_NAME_CLIP, "createBinForSourceClips": False})
    mp.SetCurrentFolder(mp.GetRootFolder())
    if not made:
        raise RuntimeError("CreateMulticamClip failed")
    _a_roll(mp, bins, clips, "base · angles", ANGLES)
    project.SetCurrentTimeline(layered)
    mr.save(resolve)
    return {"project": project.GetName(), "timelines": [t.GetName() for t in mr.list_timelines(project)],
            "layered": mr.map_timeline(layered)}


if __name__ == "__main__":
    import json
    print(json.dumps(build("--fresh" in sys.argv), indent=1, default=str))
