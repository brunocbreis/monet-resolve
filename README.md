# monet-resolve

The DaVinci Resolve scripting API plus the functions it is missing. Plain Python functions that take Blackmagic's own objects (Project, Timeline, TimelineItem, MediaPool, MediaPoolItem, Folder) and return plain data.

Resolve's API has no trim, move or split, no duration setter for titles, no track targeting, no gap selection and no multicam angle switch. Each function here closes one of those gaps, and its docstring explains the workaround. `ROADMAP.md` tracks the rest.

## Install

    pip install -e .                # add [qc] for the cut checker

Resolve must be running with external scripting allowed (Preferences > System > General). The package loads `DaVinciResolveScript` from the standard macOS install; set `RESOLVE_SCRIPT_API` and `RESOLVE_SCRIPT_LIB` to use another path.

## Use

    import monet_resolve as mr
    resolve, project = mr.connect()

    t = mr.find_timeline(project, "Cut v2")
    mr.backup_timeline(resolve, project, t, "Cut v2 - backup")
    mr.insert_fusion_comp_at(resolve, project, t, track=2, start=920, duration=274, name="TITLE - Intro")

Or run a script with `resolve`, `project` and `mr` pre-bound; its `result` variable prints as JSON:

    python -m monet_resolve.run scripts/map_project.py

`scripts/` has one ready-made script per task, with its parameters at the top.

## Conventions

- Frames are relative to the timeline start (0 = first frame) unless a parameter says `record_frame`, which is absolute, as in the API. `mr.tc(frame, fps)` converts an absolute frame to `hh:mm:ss:ff`.
- Functions sit next to the API: keep calling `timeline.GetItemListInTrack(...)`, `mp.AppendToTimeline(...)` and the rest directly.
- Functions that change a project save it. Destructive steps sit behind a keyword such as `confirm=True`, `clear_track=True` or `delete_old_versions=True`.
- Anything that deletes and re-appends items loses what the API cannot restore; run `mr.backup_timeline` first.

## Modules

| Module | Covers |
| --- | --- |
| `projects`, `timelines` | load and map projects, back up timelines, park the playhead |
| `media` | find bins and clips, import, repoint files, clean scratch items |
| `assembly` | build cuts from lists or synced recordings, close and open gaps, no-ripple inserts, nesting |
| `clips` | exact appends, continue a clip, merge through-edits, ripple insert with markers, long stills |
| `titles` | exact-length Text+ and Fusion inserts, styling, retrimming, a vignette layer |
| `transitions` | Fusion push transitions with direction and ease set in code |
| `audio` | external sync, channel mapping, crossfades, music cues |
| `transcription` | Resolve speech-to-text for clips and timeline ranges |
| `edit` | punch-ins and freeze frames |
| `color` | DRX grades, CDLs, input color space, stills |
| `render` | frame and timeline renders |
| `gfx` | rendered GFX files as nested timelines |
| `multicam` | swap source clips for a multicam and set angles |
| `ui` | menu-bar actions the API lacks, through macOS accessibility |
| `qc` | editorial checks on a cut plan before building it |

## Testbed

`testbed/` builds a Resolve project from generated media and checks each function against it, frame by frame. See [testbed/README.md](testbed/README.md).

## License

MIT
