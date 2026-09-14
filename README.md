# monet-resolve

The DaVinci Resolve scripting API plus the functions it is missing. Plain Python functions that take Blackmagic's own objects (Project, Timeline, TimelineItem, MediaPool, MediaPoolItem, Folder) and return dicts, lists, tuples and booleans. Named after Monet, a different artist from da Vinci. Written by Claude for Bruno Reis.

## Why

Resolve's scripting API covers a lot and skips the steps an editor does all day. Nothing moves, trims or splits a timeline item: every change of position or extent is "delete it, re-append the source range at the new record frame", which keeps the media pool link and loses whatever lived on the item unless you restore it yourself (comps through `ExportFusionComp`/`ImportFusionComp`, grades through `CopyGrades`, speed through `SetSpeed`; Edit-page keyframes are gone). There is no duration setter for titles, no call that picks the destination track, no gap selection, no Inspector call for Text+, no way to read a node's grade, and the Fairlight mixer is out of reach entirely. Frame references are mixed: `SetMarkInOut` and `AddMarker` count from the timeline start while `recordFrame`, `SetCurrentTimecode` and render marks are absolute.

Each function here is one of those gaps closed the way it actually ran during an edit, with the workaround written down in its docstring. `ROADMAP.md` is the full checklist; every line there that is not solved is a function still to write.

## Install

    pip install -e .

Python 3.9 or newer. Resolve must be running with external scripting allowed (Preferences, System, General). The package imports Blackmagic's `DaVinciResolveScript` module from the standard macOS install path; set `RESOLVE_SCRIPT_API` and `RESOLVE_SCRIPT_LIB` to point elsewhere.

## Connect

    import monet_resolve as mr
    resolve, project = mr.connect()

Importing the package does not connect; `connect()` does, and raises `ResolveNotRunning` when it cannot.

## Run a script

    python -m monet_resolve.run scripts/map_project.py

The script runs with `resolve`, `project` and `mr` pre-bound, the same shape as the `run_script` MCP tool, and its `result` variable prints as JSON. The `scripts/` folder holds 31 task scripts with their parameters as UPPERCASE constants at the top; edit the constants and run.

## Frames

Frames are relative to the timeline start (0 = first frame) unless a parameter is named `record_frame`, which is absolute, matching the API. `mr.tc(frame, fps)` turns an absolute frame into `hh:mm:ss:ff`; pass `timeline.GetStartFrame() + relative` for a relative one.

## Examples

Timelines and projects:

    t = mr.find_timeline(project, "Raycast AI Update - Cut v2")
    mr.map_project(project, "Raycast AI Update - Cut v2")
    mr.backup_timeline(resolve, project, t, "Cut v2 - backup 01")
    mr.place_playhead(resolve, project, t, "01:00:38:08")

Media:

    mp = project.GetMediaPool()
    mr.import_to_bin(mp, ["/path/a.wav", "/path/b.wav"], "music")
    mr.replace_clip_file(resolve, mr.find_bin(mp, "gfx"), {"harness-4k-v1.mov": "/path/harness-4k-v2.mov"})
    mr.cleanup_scratch(resolve, project, timelines=["_probe"], scratch_bin="_scratch", stray_prefix="Fusion Clip", confirm=True)

Assembly:

    footage = mr.find_bin(mp, "footage").GetClipList()[0]
    mr.build_cut_from_list(resolve, project, "Cut v1", CUT, footage, mr.find_bin(mp, "timelines"))
    mr.close_gap_ripple(resolve, project, t, gap_start=2051, gap_len=36, dummy_clip=mr.find_clip(mp.GetRootFolder(), "C0421.MP4"))
    mr.insert_fusion_comp_at(resolve, project, t, track=2, start=920, duration=274, name="TITLE - Harness")
    mr.nest_timeline_over_placeholder(resolve, project, t, nested_item, track=3, placeholder_start=920, placeholder_track=2)
    mr.swap_gfx_clip(resolve, project, "/path/harness-4k-v20.mov", mr.find_bin(mp, "gfx"), gfx_timeline, frames=274)
    mr.place_clips_on_track(resolve, project, t, rec_clip, track=4, clips=[("REC - Automations tab", 2051, 1638, 1926)], zoom=1.155, color="Cyan", track_name="SCREEN RECS")

Titles and Fusion:

    mr.text_placeholders(resolve, project, t, track=2, spans=[(920, 1194, "Harness b-roll")], other=selects)
    mr.title_fitted_to_clip(resolve, project, t, clip_track=1, clip_name="L06b · Harness", track=2, text="Harness")
    mr.fusion_vignette_layer(resolve, project, t, opacity=70.0)
    with mr.track_locks(t, video_track=2):
        item = mr.insert_fusion_title(t, start=100, duration=48)

Markers:

    mr.beat_markers(t, [(0.0, "A runtime", "Blue"), (1.8, "B window forms", "Cyan")], fps=24)

Audio:

    mr.sync_external_audio(resolve, mp, camera_clip, wav_clip)
    mr.set_clip_audio_mapping(camera_clip)
    mr.audio_crossfades(resolve, project, t, track=1, frames=4)
    mr.place_music(resolve, project, t, 3, mr.find_bin(mp, "music"), CUES, clear_track=True)

Transcription:

    mr.transcribe_clip(camera_clip, words=True)

Edit-page attributes:

    mr.punch_in_clips(resolve, project, t, [(898, "L04b pickup")], zoom=1.3, tilt=-250.0)
    mr.alternate_punch_ins(resolve, project, t)

Color:

    mr.grade_all_clips(resolve, project, t, "/path/look.drx", nodes=7, cdls=[{"NodeIndex": 1, "Slope": "0.69 0.69 0.69", "Offset": "0 0 0", "Power": "1 1 1", "Saturation": 1.0}])
    mr.set_input_color_space(resolve, camera_clip, ["Sony S-Gamut/S-Log2", "Sony S-Gamut S-Log2"])
    mr.export_stills(resolve, project, t, "/path/stills/", {"wide": 100, "punch": 3300})

Render:

    mr.render_frame_tiff(project, t, "/path/frames/", {"wide": 100, "punch": 3300})
    mr.render_timeline_mp4(resolve, project, t, "/path/export", "Cut v2 review", width=1920, height=1080)

GFX:

    mr.create_gfx_timeline_from_clip(resolve, project, "/path/projects-4k-v1.mov", mr.find_bin(mp, "gfx"), mr.find_bin(mp, ["timelines", "gfx"]), "GFX - Projects b-roll", t, track=3, record=1378, frames=303)

## Relation to the official API

Nothing here wraps or subclasses the API proxies. You keep calling `timeline.GetItemListInTrack(...)`, `mp.AppendToTimeline(...)` and the rest yourself; these functions sit next to them and take the same objects. Where a function needs a page switch, a track lock or a save it does it the way the API requires (`resolve.OpenPage`, `SetTrackLock`, `resolve.GetProjectManager().SaveProject()`), and says so in its docstring. Destructive calls (`DeleteClips`, `DeleteTimelines`, `DeleteAllRenderJobs`, wiping a track) are named in the docstring and, where a function would otherwise do them silently, sit behind a keyword such as `confirm=True`, `clear_track=True` or `delete_old_versions=True`.

## Status

Everything here ran on Resolve 21.1 on 2026-09-11 during a real edit, with three exceptions. `insert_fusion_comp_at`, `close_gap_ripple` and `title_fitted_to_clip` were assembled after the fact from recipes that each ran piecemeal; they have not run as whole functions yet. Their docstrings say so. Back up the timeline before trying them.

Resolve's proxies return `None` in places the stubs do not mention (an empty track, an item's Fusion comp from the Edit page, `GetNodeGraph` right after opening the Color page). The functions handle the cases that bit during the edit; `ROADMAP.md` lists the rest under Quirks.

## License

MIT, Bruno Reis, 2026.
