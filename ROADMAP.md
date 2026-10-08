# Roadmap

This is the roadmap for monet-resolve: every line below that is not SOLVED is a function to add. It is a copy of the gap checklist kept during the Raycast AI Update edit (Resolve 21.1, 2026-09-11 and 12).

# Resolve scripting API gaps

The checklist of what the Resolve 21.1 scripting API cannot do directly, what we solved, and what is still open. It merges three audits: the gaps hit during the Raycast AI Update edit on 2026-09-11 and 12 (with session evidence), the full API audit by editing area (stubs, README, changelog), and the Fusion scripting audit. Scripts named here live in `scripts/`; their one-line descriptions are in `scripts/README.md`.

Each line is one editing task. The checkbox carries the status, the words before the dash say the task the way an editor says it, the words after the dash give the API fact (call names) and the route or the script that does it. Items hit in a real session end with the session id and timestamps in parentheses.

How we work this list: hit a gap during an edit, add it here as OPEN in the right area, try a workaround, save a script in `scripts/` when the route works as a whole file, then flip the status. A route that ran once but has no whole-file script stays WORKAROUND. A route that reads well in the stubs but never ran stays UNTESTED until someone runs it.

## Status legend

- `[x] SOLVED` - a script in `scripts/` does it; the script is named on the line.
- `[~] WORKAROUND` - the route is known and ran at least once, but there is no script yet, or the script was assembled from pieces and has not run as a whole file; the line says which.
- `[?] UNTESTED` - a plausible route from the stubs, never run here.
- `[ ] OPEN` - no route found yet.
- `[UI] UI-ONLY` - Bruno does one exact action in Resolve; the line names it. The script does the rest where possible.
- `[!] QUIRK` - not a gap, a behavior that bites; the fix sits on the same line. Collected in the Quirks section.

## Summary

| Status | Count |
|---|---|
| `[x] SOLVED` | 39 |
| `[~] WORKAROUND` | 38 |
| `[?] UNTESTED` | 44 |
| `[ ] OPEN` | 1 |
| `[UI] UI-ONLY` | 42 |
| `[!] QUIRK` | 63 |

Three facts shape most routes below. The `run_script` sandbox has no filesystem, but Resolve reads and writes paths on the Mac, so anything file-based (DRX, .comp, LUT, stills, renders, presets) works once the assistant writes the file with Bash and passes the absolute path. Frame references are mixed: `SetMarkInOut` and `AddMarker` take frames relative to the timeline start; `recordFrame`, `SetCurrentTimecode`, render `MarkIn`/`MarkOut`, `GetStart`/`GetEnd` are absolute. No call moves, trims, or splits an existing timeline item. Splits and trims come from Resolve's own editing: a rippling 1-frame title insert cuts the clips under it (`clips.split_at`), and deleting a piece trims, so the clip keeps everything on it. Moving and extending are still "delete it, re-append the source range at the new record frame", which keeps the media pool link but loses whatever lived on the item unless restored (comps via `ExportFusionComp`/`ImportFusionComp`, grades via `CopyGrades`, speed via `SetSpeed`, keyframes lost).

## Checklist

### Project and timelines

- [x] SOLVED Find a timeline by name - no lookup call; iterate `GetTimelineByIndex(1..GetTimelineCount())` and compare `GetName()`. `map_project.py`, `load_project.py`.
- [x] SOLVED Make inserts land on the track I want (destination toggle) - no call sets the toggle. Track locks steer `Insert*IntoTimeline` onto the one unlocked video track when two things hold: nothing is selected in the media pool (a selected clip or timeline acts as the source of the edit, and the insert then follows the toggle), and the timeline was switched away from and back. `refresh_timeline` does both; `insert_fusion_title` and `insert_fusion_composition` take `track` and `project` and do refresh, lock, insert, unlock. A successful steered insert moves the toggle to that track. With a selection to keep, `assembly.set_destination_track` moves the toggle through the menu bar instead.
- [x] SOLVED Protect the cut before a destructive step - no undo from a script; `backup_timeline.py` duplicates the timeline into the backups bin and `map_project.py` snapshots the layout first; `CloseProject` without saving discards everything since the last save.
- [x] SOLVED Get a timeline with a ready track layout - `CreateEmptyTimeline` always ships a stereo A1; `DuplicateTimeline` one that has the layout and empty it (0e05d2ae 09:49:18). `backup_timeline.py` does the duplicate step.
- [?] UNTESTED Duplicate a project - no in-database copy; `ExportProject(name, path)` to a .drp, then `ImportProject(path, newName)`.
- [?] UNTESTED Solo a track - no solo call; `SetTrackEnable('audio', i, False)` on every other audio track.
- [?] UNTESTED Mute an audio track from a script - `SetTrackEnable('audio', i, False)` exists; the stub leaves open whether it equals the Fairlight mute button or the track enable toggle (the same control on the Edit page).
- [UI] UI-ONLY Insert a track at a position or reorder tracks - `AddTrack` only appends on top. Bruno right-clicks the track header and picks Add Track with a position. The scripted substitute (add on top, then delete and re-append every item from the tracks above) is untested and expensive.
- [UI] UI-ONLY Track color and track height - no call. Bruno sets them from the track header.
- [UI] UI-ONLY Undo - no call. Cmd+Z in Resolve; from a script use the backup route above.

### Media pool

- [x] SOLVED Find a bin or clip by name - no lookup call; recurse from `GetRootFolder()` over `GetSubFolderList()` and `GetClipList()` comparing `GetName()`. Every script does this; `import_media_to_bin.py`, `map_project.py`.
- [x] SOLVED Point a clip at a new render version - `MediaPoolItem.ReplaceClip(path)` repoints the pool clip and every timeline that uses it follows. `replace_clip_file.py`. Before this, one session re-imported eleven versions, deleted and re-appended the item each time (b753bc76 16:12:47 to 17:33:36; dc335150 17:31:43).
- [x] SOLVED Decide which audio track an appended clip lands on - `trackIndex` is the video track; the linked audio follows the clip's `track_mapping`. Set it with `MediaPoolItem.SetAudioMapping(json)` before appending; fix existing items with `TimelineItem.SetSourceAudioChannelMapping`. `set_clip_audio_mapping.py`.
- [x] SOLVED Use a subclip range without making a subclip - no call creates a subclip item; append the range with `startFrame`/`endFrame` instead. `clips.append_exact`.
- [x] SOLVED Set the input color space on a camera clip - `SetClipProperty('Input Color Space', name)` returns False on the wrong spelling and lists no accepted names; try variants until one sticks. `set_input_color_space.py` (0e05d2ae 09:22:02).
- [~] WORKAROUND Find where a clip is used - `GetClipProperty('Usage')` gives the count; for positions iterate timelines and compare `TimelineItem.GetMediaPoolItem().GetMediaId()`. No script.
- [?] UNTESTED Rename a bin - `Folder` has `GetName` only. `AddSubFolder` with the new name, `MoveClips` and `MoveFolders` into it, `DeleteFolders([old])`. Or Bruno double-clicks the bin.
- [?] UNTESTED Write other clip attributes (frame rate, alpha mode, data level, PAR) - `SetClipProperty(name, value)` with `ClipProperties` keys; the README says intrinsic ones are read-only. Set it once in the UI and diff `GetClipProperty()` snapshots to learn the key.
  - 2026-10-07: `SetClipProperty('FPS', 30)` on an imported EXR image sequence returned True and `GetClipProperty('FPS')` read 30.0 (sequences import at 24). Alpha mode read `Premultiplied` by default for a premultiplied EXR.
- [?] UNTESTED Set metadata fields by name - `SetMetadata({key: value})` takes the Metadata panel labels; the stubs do not enumerate them. `SetThirdPartyMetadata` for arbitrary keys.
- [UI] UI-ONLY Generate proxy or optimized media - no call. Bruno right-clicks the clips, Generate Proxy Media. Existing proxies link with `LinkProxyMedia(path)`; the project settings `perfProxyMediaMode`, `perfOptimisedMediaOn`, `perfProxyResolutionRatio` are settable.
- [UI] UI-ONLY Duplicate a pool clip - no call. Bruno right-clicks, Duplicate. `ImportMedia` of the same path into another bin may dedupe; untested.
- [UI] UI-ONLY Smart bins, power bins, sort order, list or thumbnail view, keyword filters - no call. Bruno does it in the media pool.

### Assembly and moving clips

- [x] SOLVED Place a clip at an exact frame on an exact track - `AppendToTimeline([{'mediaPoolItem', 'startFrame', 'endFrame', 'trackIndex', 'recordFrame', 'mediaType': 1|2}])`; `mediaType: 2` with `trackIndex` targets an audio track directly. `place_music.py`, `nest_timeline_over_placeholder.py`, `clips.append_exact`.
- [x] SOLVED Nest a timeline into another - get the timeline's pool item (`Timeline.GetMediaPoolItem()`, or find it in the bin and confirm with `MediaPoolItem.GetTimeline()`), then `AppendToTimeline` with it. `nest_timeline_over_placeholder.py`.
- [~] WORKAROUND Leave a gap or a placeholder slot - marks plus playhead then `InsertGeneratorIntoTimeline('Solid Color')`, or place a disabled clip as the slot. No function.
- [~] WORKAROUND Shorten a take, swap a take, or move a clip without rebuilding the cut - `TimelineItem` has no trim, move, or set-start call. Read the source range and properties, `DeleteClips([it], ripple)`, `AppendToTimeline` at the new `recordFrame`/`trackIndex`, reapply `SetName`, `SetClipColor`, `SetProperties`, `SetSpeed`, `ImportFusionComp`; for grades append the copy first, `CopyGrades([new])`, then delete the old one. Ran piecemeal on every edit that day; the take selector (`AddTake`, `SelectTakeByIndex`, `FinalizeTake`) is the untried alternative (0e05d2ae 09:57 and 10:02).
- [x] SOLVED Insert edit (push everything right by the new clip's length) - no rippling insert. Snapshot every item to the right (pool item, source range, record frame, name, color, properties, comp export), delete them, append the new clip, re-append the snapshot at its record frame, restore properties. `assembly.insert_fusion_comp_at`, checked in the testbed; it refuses when a retimed clip (`GetSpeed()['Percentage'] != 100`) sits to the right.
- [x] SOLVED Close a gap on any combination of tracks - no gap selection; append a dummy clip filling the gap exactly on one chosen track, lock every track left out, `DeleteClips([dummy], True)`, restore the locks. `assembly.close_gap_ripple(tracks=[...])`, checked in the testbed for all tracks, all but one, video only, audio only; it refuses when a chosen track is not empty across the gap.
- [~] WORKAROUND Find gaps - sort `GetItemListInTrack` by `GetStart()` and diff consecutive `GetEnd()`/`GetStart()`. No script.
- [~] WORKAROUND Copy and paste clips or paste attributes - no clipboard. Re-append for clips; `GetProperties()` then `SetProperties()` for attributes. No paste script.
- [?] UNTESTED Overwrite onto occupied space - the stubs do not say what `AppendToTimeline` does when `recordFrame` overlaps an item (fails, overwrites, or shifts). Safe route: delete the items in the range first, then append.
- [?] UNTESTED Three-point, four-point, fit to fill - compute the source range and append; for fit to fill append then `SetSpeed({'Percentage': srcLen / slotLen * 100})`.
- [UI] UI-ONLY Select clips on the timeline from a script - `Timeline.GetSelectedClips()` reads only. Bruno clicks. Nothing in the API consumes a selection anyway; every call takes explicit item lists.

### Trimming

- [x] SOLVED Trim the in or out point of a clip without losing anything on it - `clips.split_at` at the new edge, then `DeleteClips` the unwanted piece. The kept piece is the original clip, so keyframes, effects, grades and fades stay. The older route below loses them.
- [~] WORKAROUND Trim by re-appending - no trim call. Delete and re-append with the new source range; for a head trim also move `recordFrame` by the same amount when the out point must hold; then close the gap with the dummy-clip route or delete the overlapped neighbor range first. Ran on plain clips.
- [~] WORKAROUND Slip a clip (same position and length, different content) - re-append at the same `recordFrame` with `startFrame`/`endFrame` shifted by the slip amount. No script.
- [~] WORKAROUND Join through an edit (remove a split) - delete both halves, append the union source range. `clips.join_clips`; it restores properties, fades and the transitions on the outer edges, and loses keyframes and clip effects.
- [x] SOLVED Ripple trim with some tracks held in place (trim a clip's tail, keep the music running) - lock the tracks to hold, `clips.split_at` at the new edge, then `DeleteClips([title_or_pieces], True)`: everything after moves left by exactly the trimmed length. Or in one insert: a 1-frame title at the edge cuts the clips, and ripple-deleting the title together with the right pieces removes the extra frame with them. A crossfade on the deleted edge goes with the piece; add it back with `AddTransition`.
- [?] UNTESTED Slide a clip between its neighbors - re-append the clip at the new record frame, then re-append both neighbors with adjusted source ranges.
- [?] UNTESTED Roll an edit point - re-append both adjoining clips with one longer and the other shorter, same total span.
- [x] SOLVED Split a clip at a frame (razor), losslessly - no split call. A 1-frame Text+ inserted at the frame is a true insert edit and cuts every clip spanning it on the unlocked tracks; ripple-deleting the title closes the frame. Both halves are Resolve's own pieces: keyframes, effects, grades, comps and speed survive, fades stay on the outer edges. `clips.split_at(tracks=[...])`, which locks the other tracks, borrows a free video track for the title when only audio is cut, and compares the timeline before and after. Tracks with auto-select off are not cut; see Quirks.
- [?] UNTESTED Trim or extend to the playhead - read `GetCurrentTimecode`, compute frames, apply the trim route.
- [?] UNTESTED Trim, move, or split a retimed clip - `AppendToTimeline` cannot recreate a retimed clip; after re-append call `SetSpeed({'Percentage': p})` for a constant speed. Speed ramps cannot be recreated.

### Clip properties and retime

- [~] WORKAROUND Punch in (zoom and reframe) on chosen clips - `SetProperties({'ZoomX', 'ZoomY', 'Pan', 'Tilt', ...})`. One API call; no function.
- [~] WORKAROUND Add a vignette to the picture - no call draws a power window or adds a ResolveFX. A Fusion composition on a new top track (black `Background` masked by an inverted soft `EllipseMask`, item `Opacity` 55 to 70), verified by a 1-frame Deliver render. No function.
- [x] SOLVED Change the duration of a title or generator - no duration setter. `retrim_title.py` snapshots every title to the right (name, extent, StyledText), deletes them with the target, refreshes, re-inserts all in ascending order with the new length and restyles them; the insert is a ripple on its track, so the snapshot is what keeps the rest in place (ran whole 2026-09-14, session 0e05d2ae). `title_fitted_to_clip.py` remains assembled and unrun.
- [~] WORKAROUND Reset a clip's attributes - `SetProperties` with the defaults (Pan 0, Tilt 0, Zoom 1, Rotation 0, Opacity 100, crops 0). No function.
- [?] UNTESTED Reverse a clip - `SetSpeed({'Percentage': p})` documents "0.0 = freeze frame" and says nothing about negatives. Try a negative percentage once; if it fails Bruno uses Change Clip Speed, Reverse.
- [x] SOLVED Freeze frame at a point inside a clip - append the range that starts at the frame to freeze, sized to the wanted duration, park the playhead on its first frame, `SetSpeed({'Percentage': 0.0})`: the item keeps its duration and shows that frame throughout (first and last frame render pixel-identical). `edit.freeze_item`. The frozen frame is the one under the playhead, clamped to the item, so park it first.
- [?] UNTESTED Animate zoom, pan, or opacity on a clip (Inspector keyframes) - no keyframe call on the Edit page. Do the animation in a Fusion comp on the clip: `AddFusionComp()` or `GetFusionCompByIndex(1)`, add a Transform tool between MediaIn and MediaOut, `tool.SetInput(name, value, frame)` with the Fusion page open. Or Bruno clicks the keyframe diamond in the Inspector.
- [?] UNTESTED Add a ResolveFX (blur, glow, drop shadow) to a clip through the grade - no Edit-page call. Save a Color page node with the effect once as a DRX, then `GetNodeGraph().ApplyGradeFromDRX(path, 0)` on each clip; `ApplyGradeFromDRX` applies DRX trees, and a DRX carries ResolveFX nodes. Not yet done for an effect node.
- [?] UNTESTED Where a clip marker's `frameId` counts from - `TimelineItem.AddMarker(frameId, ...)` says "at given frameId position" only; test whether it is the clip's first frame or the source frame.
- [UI] UI-ONLY Adjust a ResolveFX parameter (film grain amount on the film look node) - no call reads or writes an effect parameter; `SetCDL` covers slope, offset, power, saturation only. Bruno adjusts it on the first clip in the Color page, then the grade is copied to the other clips (see Color) (0e05d2ae 10:51).
- [UI] UI-ONLY Speed ramps and retime curves - no call. Bruno uses Retime Controls in the viewer.
- [UI] UI-ONLY Dynamic zoom framing - only `DynamicZoomEnabled` and `DynamicZoomEase` are exposed, which gives the default slight push in. Bruno drags the start and end rectangles in the viewer.
- [UI] UI-ONLY Conform lock, offline reference on a timeline item - no call beyond `SetSourceAudioChannelMapping`. Bruno sets them from the clip's right-click menu.

- [x] SOLVED Frame-accurate take boundaries - the full-clip transcript drifts and merges repeated takes; `transcription.transcribe_timeline_range` renders the slot and transcribes that audio, `transcribe_words` polls with a fresh proxy because `GetTranscription` stays None on the proxy that started the job (2026-09-14).

- [x] SOLVED Insert a gap / lengthen a clip mid-cut with everything moving - `InsertFusionTitleIntoTimeline` with ALL tracks unlocked ripples every track; delete the title without ripple. `clips.ripple_insert`. Before this the tail of the cut was re-appended item by item, which drops grades and crossfades.

### Transitions

- [x] SOLVED Add an audio crossfade at every cut on a track - `AddTransition({'type': 'Cross Fade +3 dB', 'category': 'audio', 'position': 'end', 'alignment': 'center', 'duration': 4})`, iterating pairs where `x.GetEnd() == y.GetStart()`. `audio_crossfades.py`. `'Cross Fade 0 dB'` and `'Cross Fade -3 dB'` follow the UI labels, untested.
- [!] QUIRK Built-in Push runs the wrong way for Bruno - `outgoing.AddTransition({'type': 'Push', 'category': 'simple', 'position': 'end', 'alignment': 'right', 'duration': 12})` adds it (alignment `'right'` = start on the edit, outgoing tail handles only), but it travels left to right: the incoming clip enters from the LEFT and the outgoing exits RIGHT. Bruno's direction is the opposite: outgoing exits to the LEFT, incoming enters from the RIGHT (content moves right to left, like swiping forward). No call sets the direction of a simple transition, so never add the simple Push by script; use the Fusion push with direction `left`, or leave a cut and tell Bruno (calculator-in-raycast, 2026-10-07: he removed them).
- [~] WORKAROUND Check that a transition has handles - `GetRightOffset()` of the outgoing and `GetLeftOffset()` of the incoming; a centered transition of N frames needs N/2 on each side. No script.
- [x] SOLVED Add a video transition - `AddTransition({'type': 'Cross Dissolve', 'category': 'simple'|'fusion', 'position', 'alignment', 'duration'})` ran for both categories (2026-09-22). Only `'Cross Dissolve'` resolved in the fusion category; `Push`, `Slide`, `Blur Dissolve`, `Cross Zoom`, `Circle`, `Dip To Color Dissolve` returned None, and a user `.setting` dropped in `~/Library/.../Fusion/Templates/Edit/Transitions/` was not found by name without a restart.
- [~] WORKAROUND Push transition with direction and ease set by code - Fusion Cross Dissolve item, then rewrite its comp through the Fusion API (Anim Curves `Source='Transition'`, cubic ease, XY Paths on two Transforms, Merge). `Composition.Save(path)` writes the comp text; `TimelineItem.ExportFusionComp` returns False on transition items and `SetName` on a transition item does nothing (stays 'Cross Dissolve'). Replaced both simple pushes on Cut v3 (2556, 5956). No function.
- [?] UNTESTED Remove a transition (back to a cut) - transitions show in `GetItemListInTrack` with `GetType() == 'transition'`; `DeleteClips([transitionItem], False)` is the obvious call.
- [x] SOLVED Smooth Cut by script - `outgoing.AddTransition({'type': 'Smooth Cut', 'category': 'simple', 'position': 'end', 'alignment': 'center', 'duration': 4})` returned the transition (wimr-quotes, 2026-10-07). It morphs head and pose drift well, but anything that disappears between the two sides (a raised hand) ghosts in place. Pick an edit point where the content exists on both sides, or start the incoming clip early while keeping its sync offset, so its own motion carries through.
- [!] QUIRK No alpha from an EXR render - `GetRenderCodecs('exr')` lists only RGB half/float codecs. With `ExportAlpha: True`, the frames have 4 channels but alpha = 1 everywhere, even with V1 disabled over a premultiplied EXR matte (21.1, 2026-10-07). Use QuickTime ProRes 4444 instead: `SetCurrentRenderFormatAndCodec('mov','ProRes4444')` + `ExportAlpha: True` with the background track emptied gives `yuva444p12le` with real alpha (81% alpha=0 on a cutout); re-imported over magenta in Resolve, the magenta shows through (2026-10-08).
- [?] UNTESTED Change the duration or alignment of an existing transition - no setter; delete it and `AddTransition` again with the new values.
- [~] WORKAROUND Transition parameters (dip-to-color color, dissolve curve, wipe angle) - no call for simple/ofx transitions; a Fusion transition's comp is fully scriptable through `GetFusionCompByIndex(1)` with the Fusion page open, which is how the push gets its direction and ease.
- [UI] UI-ONLY Default transition and default duration - no call. Bruno right-clicks in the Effects Library or uses Preferences, Editing. Scripts pass `duration` per call anyway.

### Audio

- [x] SOLVED Make A1 a mono dialogue track on a timeline created with a stereo A1 - `GetTrackSubType` reads the format, `AddTrack('audio', 'mono')` creates a new mono track, nothing changes the format of an existing track, and `DeleteTrack` refuses while A1 is the only audio track. Add the mono and stereo tracks first, delete A1's items (including linked audio), then `DeleteTrack('audio', 1)`; or duplicate a timeline that has the layout and empty it; or map channels per clip (`set_clip_audio_mapping.py`) so dialogue is mono regardless of the track format. Bruno's 2-second alternative: right-click the A1 header, Change Track Type to Mono (0e05d2ae 09:33:55, 09:46:15, 09:47:42, 09:49:18).
- [x] SOLVED Lay music cues with level and fades - `AppendToTimeline` with `mediaType: 2`, then `SetProperties({'AudioVolume': dB})` and `SetFades({'FadeIn', 'FadeOut'})`. `place_music.py`.
- [?] UNTESTED Volume keyframes inside a clip (a manual dip) - no automation call. Segment the clip into consecutive appends (same source, adjacent ranges), give each its own `AudioVolume`, `SetFades` on the segment edges, or a short `'Cross Fade 0 dB'` between segments where the jump is large.
- [?] UNTESTED Duck music under dialogue - no sidechain or auto-duck call. Compute dialogue spans from the A1 items' `GetStart`/`GetEnd`, lay the cue as segments with a lower `AudioVolume` inside the spans and fades at each boundary; this is one extension of `place_music.py`. `AudioDialogueLevelerEnabled` plus `AudioDialogueLevelerBackgroundReduction` on the dialogue clip is a different effect.
- [?] UNTESTED Export per-track stems - `SetRenderSettings({'ExportVideo': False, 'ExportAudio': True})` renders the mix only; one job per track with the others disabled through `SetTrackEnable`.
- [UI] UI-ONLY Track fader level, track EQ, compressor, dynamics, track effects, buses, submixes, bus routing - no track-level audio properties. Bruno works in the Fairlight mixer. `Project.ApplyFairlightPresetToCurrentTimeline(name)` with a preset saved from the UI may carry some of it; the stubs do not say what a Fairlight preset holds, so verify once on a scratch timeline.
- [UI] UI-ONLY Track pan - `AudioPan` exists per clip only. Bruno sets track pan in the mixer.
- [UI] UI-ONLY Per-clip EQ or clip effects, FairlightFX, VST/AU plug-ins - no call. Bruno uses Inspector, Audio, Equalizer, or Fairlight clip FX.
- [UI] UI-ONLY Loudness readout - no meter call; `NormalizeAudioLevel` in a loudness mode is the only loudness-aware operation. Bruno reads the Fairlight meters, or the assistant renders and measures outside Resolve.
- [UI] UI-ONLY ADR, Foley sampler, elastic wave, audio warping - no call. Fairlight page.

### Titles and Fusion

- [UI] UI-ONLY Copy an Edit-page Text title between projects with new words - no call reads or sets a Text title's content or style. Scripted titles use Fusion Text+ (`titles`), which the API fully controls.

- [x] SOLVED Insert a Text+ at a frame with an exact length on a track - lock the other tracks, `SetMarkInOut(start, end - 1)` relative, `SetCurrentTimecode(absoluteTC)`, `InsertFusionTitleIntoTimeline('Text+')`, `ClearMarkInOut`. `titles.insert_fusion_title`; `title_fitted_to_clip.py` (not yet run as a whole file) fits one to a clip found by name.
- [x] SOLVED Set the text, font, style, size, and color of a Text+ - no Inspector call; `resolve.OpenPage('fusion')`, `comp = item.GetFusionCompByIndex(1)` (or `AddFusionComp()` when the count is 0), find the tool with `comp.FindToolByID('TextPlus')` or by `tool.ID`, `tp.SetInput('StyledText', ...)`, `'Font'` (`'Inter 28pt'`), `'Style'`, `'Size'`, `'Red1'/'Green1'/'Blue1'`, then `OpenPage('edit')`. `titles.title_fitted_to_clip` sets the text (0e05d2ae 09:07:14 failed from the Edit page, 09:07:36 fixed).
- [x] SOLVED Insert a native Fusion composition of exact length at a frame - same marks recipe with `InsertFusionCompositionIntoTimeline()`. `titles.insert_fusion_composition`; `assembly.insert_fusion_comp_at` adds the no-ripple snapshot.
- [~] WORKAROUND Build a comp from scratch (background, masks, merges) - `comp.AddTool('Background', 0, 0)`, `SetInput`, `ConnectInput('EffectMask', mask)`, `SetAttrs({'TOOLS_Name': ...})`. No function.
- [~] WORKAROUND Text+ layout (position, alignment, tracking, line spacing, outline) - inputs `Center = {1: x, 2: y}`, `HorizontalLeftCenterRight` (-1/0/1), `VerticalTopCenterBottom`, `CharacterSpacing`, `LineSpacing`, layer 2 `Enabled2`/`Red2`; list them with `tp.GetInputList()`. Used in the library comps; no script. Bruno positions section titles afterwards with the Edit-page Tilt (`item.SetProperty('Tilt', v)`), which stays editable on the cut.
- [~] WORKAROUND List installed fonts and their styles - `resolve.Fusion().FontManager.GetFontList()` lists font files (this Mac has Inter split into "Inter 18pt", "Inter 24pt", "Inter 28pt"); style names come from `fc-list : family style` or `system_profiler SPFontsDataType` through `run_script_unsafe`. No script.
- [~] WORKAROUND Animate a title with keyframes - `tool.AddModifier('Opacity1', 'BezierSpline')` or `tool.Opacity1.ConnectTo(comp.AddTool('BezierSpline', 0, 0))`, then `tool.SetInput('Opacity1', v, frame)`; edit with `BezierSpline.GetKeyFrames`, `SetKeyFrames(table, replace)`, `DeleteKeyFrames`. Ease handles use the .comp table shape (`RH`, `LH`, `Flags`), untested by hand. A plain fade is `SetFades` on the item.
- [~] WORKAROUND Animation that follows the clip length (in and out that survive a trim) - Anim Curves is tool ID `LUTLookup`: `inp.ConnectTo(comp.AddTool('LUTLookup', 0, 0))`, inputs `Source = 'Duration'`, `Curve = 'Easing'`, `EaseOut = 'Cubic'`, and expressions on `TimeScale`/`TimeOffset` using `comp.RenderEnd` (in over N frames is `(comp.RenderEnd+1)/N`). In every library comp; no scripts/ file.
- [~] WORKAROUND Expressions on inputs - `inp.SetExpression('(comp.RenderEnd+1)/14')`, `GetExpression()`, `SetExpression('')` to clear; Lua syntax, other tools by name. Used in the library comps; no script.
- [~] WORKAROUND Import a whole .comp onto an item, or copy a comp between clips - `OpenPage('fusion')`, `item.ImportFusionComp(path)`, `OpenPage('edit')`; export with `item.ExportFusionComp(path, compIndex)`. Import adds a composition; delete the old one with `DeleteFusionCompByName`. Ran on this project; no dedicated script.
- [~] WORKAROUND Lay out nodes without the Fusion page - `comp.CurrentFrame.FlowView.SetPos(tool, x, y)` needs the Fusion page with that comp shown; headless, edit `ViewInfo = OperatorInfo { Pos = { x, y } }` in the exported text and re-import. `AddTool` also takes `xpos`, `ypos`, `autoconnect`.
- [~] WORKAROUND Make a Fusion clip of an exact length - append footage of the wanted length on a fresh timeline, `timeline.CreateFusionClip([item])`, re-fetch the item, `ImportFusionComp`. Changing its length later means building a new one. No script.
- [~] WORKAROUND Find which template titles and generators exist by name - `InsertFusionTitleIntoTimeline(name)` takes the Effects Library name and nothing enumerates them; list the folders on disk (`/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Templates/Edit/Titles` and the user-level `~/Library/.../Fusion/Templates/Edit/{Titles,Generators,Effects,Transitions}`). Bruno's own comps in `library/` are the preferred source.
- [~] WORKAROUND Put my own comp into the Effects Library - no Create Macro call; write the `.setting` (a `MacroOperator` or `GroupOperator` block with `Inputs = ordered() { InstanceInput {...} }`) into the user Templates folder; it shows after a refresh or relaunch. `fu.InstallFile(path, quiet)` installs a `.drfx` bundle, untested.
- [~] WORKAROUND Build a macro from existing nodes - no Macro Editor call; export the comp, wrap the tool blocks into a `MacroOperator` by text, re-import or save as .setting.
- [~] WORKAROUND Add or change custom controls on a tool (Playground) - `tool.UserControls = {...}` then `tool.Refresh()`; a Python dict has no order Fusion respects, so reorder through `UserControls = ordered() {...}` in the exported text and `ImportFusionComp`.
- [?] UNTESTED Import a .setting macro onto an item - no call on `TimelineItem`. Three Fusion routes: `comp.AddSettingAction(filename, x, y)`, `comp.Paste(settings_dict)` (with `comp.CopySettings(toollist)` producing the table), or `fu.SetClipboard(text)` then `comp.Paste()`; single tool `tool.LoadSettings(path)`. Fallback that ran: splice the tool block into an exported .comp and `ImportFusionComp`.
- [?] UNTESTED Measure whether a line of text fits - no text-metrics call; `tp.Output.GetDoD(frame)` gives the rendered bounds, `tp.Output.GetValue(frame)` an `Image` with `Width`, `Height`, `DataWindow`; slow in a 55 s script. The sure check is a 1-frame Deliver render and a pixel read.
- [?] UNTESTED Word-level animation and highlight styles - `TextPlus.UpdateWordAnimation(style_table)` is in the stub, never run.
- [?] UNTESTED Drive a template's exposed controls - the inserted template is a `MacroOperator`; `macro.GetInputList()`, `macro.SetInput('<InstanceInput id>', v)`, internal tools through `macro.GetChildrenList()`.
- [?] UNTESTED Write mask polyline points by script - `PolylineMask.GetBezierPolyline(time)` reads; `SetInput('Polyline', {...})` is untested. Author the `Polyline` block in the .comp text and re-import.
- [?] UNTESTED Retime inside a comp - `TimeStretcher` and `TimeSpeed` tools via `AddTool`; the fusion-composition skill has their settings.
- [?] UNTESTED Buttons and visibility logic on custom controls - `ButtonControl` with `BTNCS_Execute` runs Lua inside Fusion; `INPS_ExecuteOnChange` and the `IC_Visible`/LabelControl pattern work at text level. Writing them through the Python property is plausible; debugging needs the UI.
- [?] UNTESTED Insert an adjustment clip - `InsertGeneratorIntoTimeline('Adjustment Clip')` may or may not accept it.
- [?] UNTESTED Set the color of an Edit-page generator - no Inspector call; use `InsertFusionGeneratorIntoTimeline(name)` and `SetInput` on its tool.
- [UI] UI-ONLY Edit the text of an Edit-page (non-Fusion) title - `InsertTitleIntoTimeline('Text')` inserts it, nothing edits it. Bruno types in the Inspector. Prefer Text+.
- [UI] UI-ONLY Run a tracker, planar tracker, or roto - a `Tracker` or `PlanarTracker` tool can be added and configured by script; the Track button has no scripted equivalent. Bruno presses Track in Fusion.
- [UI] UI-ONLY Dialogs inside Fusion - `comp.AskUser(title, controls)` blocks the script; never call it from an MCP run.

### Color

- [~] WORKAROUND Apply a DRX node tree and CDL values to every clip on a track - `item.GetNodeGraph().ApplyGradeFromDRX(path, 0)`, `item.SetCDL({'NodeIndex', 'Slope', 'Offset', 'Power', 'Saturation'})`, Color page open with a 1.5 s sleep. No function.
- [x] SOLVED Check a graded frame as pixels - `Project.ExportCurrentFrameAsStill(path)` on the Color page, sleep 1.2 s after moving the playhead. `export_stills.py`. Shows the current clip's grade only (see Stills).
- [~] WORKAROUND Read a node's grade values (which node pulls exposure down) - no getter for node primaries; `NodeGraph` has `GetNumNodes`, `GetLUT`, `SetLUT`, `ApplyGradeFromDRX`, and `SetCDL` writes only. Set an identity CDL on one node at a time, export a still, measure luma in Python, re-apply the DRX. Found node 1 as the culprit (0e05d2ae 09:24:17, 09:25).
- [~] WORKAROUND Read exposure numbers (scopes) - no scopes call; measure an exported still in Python as above. `GetCurrentClipThumbnailImage()` returns a small base64 RGB thumbnail of the current Color page clip for a rough check.
- [~] WORKAROUND Apply a LUT to a node - `item.GetNodeGraph().SetLUT(nodeIndex, lutPath)` needs the LUT in a scanned LUT folder; `Project.RefreshLUTList()` after writing one; the MCP `generate_lut` tool writes LUTs into place.
- [?] UNTESTED Copy a grade from the first clip to the other clips - `TimelineItem.CopyGrades([targets])` is in the stub (current node stack layer to the same layer). A `dir(item)` probe for "Grade"/"Copy" ran with no result recorded; the fallback is a DRX export from the graded clip and `ApplyGradeFromDRX` on the rest (0e05d2ae 10:50:54).
- [?] UNTESTED Apply a gallery still's grade to a clip - `ExportStills([still], dir, prefix, 'drx')` then `ApplyGradeFromDRX`; which `format` strings `ExportStills` accepts is undocumented, `'drx'` is the one to try first.
- [?] UNTESTED A grade that changes over time (color keyframes) - no keyframe call; `Resolve.SetKeyframeMode` only picks the mode. `ApplyGradeFromDRX(path, 1|2)` applies a DRX that already holds keyframes, aligned by source timecode or start frame. Or Bruno uses the Color page keyframe panel.
- [UI] UI-ONLY Lift, gamma, gain, contrast, pivot, temperature, tint, curves, qualifiers, hue vs hue, blur, noise reduction as numbers - `SetCDL` is the only numeric grading setter. Bruno grades once in the Color page, saves a DRX (right-click a still, Export, or from the Gallery), and `ApplyGradeFromDRX` applies it to each clip.
- [UI] UI-ONLY Add, delete, rewire, or rename nodes - `Graph` has `GetNumNodes`, `GetNodeLabel`, `GetToolsInNode`, `SetNodeEnabled`, cache and LUT per node. Bruno builds the tree once; the DRX carries the whole tree and its names.
- [UI] UI-ONLY Power windows, tracking, magic mask shapes - no geometry call; `CreateMagicMask('F'|'B'|'BI')` and `RegenerateMagicMask` run with default settings on the current node. Bruno draws the window on the first clip; bake it into the DRX or copy the grade (0e05d2ae 10:50:54).

### Markers

- [~] WORKAROUND Add named, colored markers per beat - `Timeline.AddMarker(relFrame, color, name, note, duration, customData)`, frames relative to the timeline start, added after the build. No function.
- [~] WORKAROUND Edit a marker's name, note, or color, or move it - no setter except `UpdateMarkerCustomData`; read it from `GetMarkers()`, `DeleteMarkerAtFrame`, `AddMarker` with the changed fields. `clips.shift_markers` moves markers this way.
- [~] WORKAROUND Export a marker list, or turn markers into chapters or subtitles - `GetMarkers()` returned from the script, file written with Bash. No script.
- [?] UNTESTED Marker list through the timeline index export - `Timeline.Export(path, resolve.EXPORT_TEXT_CSV, resolve.EXPORT_NONE)`; whether the CSV includes markers is undocumented.
- [UI] UI-ONLY Marker keywords, marker-based chapter export, marker overlay in the viewer - no call. Bruno uses the Edit Index panel or Timeline, Export.

### Compound and nested

- [x] SOLVED Edit inside a nested timeline and have the parent follow - the parent references the timeline, so swapping the clip inside the GFX timeline updates every cut that nests it. `replace_clip_file.py`.
- [?] UNTESTED Decompose a compound clip in place - no call. `GetMediaPoolItem().GetTimeline()` is documented for timeline entries and open for compound clips; read its items, re-append them onto the parent at `compoundStart + itemOffset`, delete the compound item. Or Bruno right-clicks, Decompose in Place.
- [?] UNTESTED Open a compound clip to edit inside - `SetCurrentTimeline(mpi.GetTimeline())` works for timelines; for compound clips the same ambiguity applies.
- [UI] UI-ONLY Set a multicam item's angle - no API call (`dir()` on a timeline item lists every registered method; the only multicam ones are `PerformMulticamSmartSwitch`, automatic switching, and `FlattenMulticam`). Clip > Multicam Switch > Switch to Angle N works by hand and through Raycast, but a scripted accessibility press read the item as disabled and was ignored. Switch angles in the multicam viewer.
- [UI] UI-ONLY Grade a multicam angle once for every use - the API cannot see inside a multicam. Open the multicam in its own timeline (right-click, Open in Timeline), grade the angle there; every use follows.

### Subtitles and transcription

- [x] SOLVED Compare takes of the same line and find the pause to cut in - `GetTranscription()` on the full camera clip collapses repeated attempts and drops short clauses. Extract short WAV windows with ffmpeg (`run_script_unsafe`), import into a scratch bin, `TranscribeAudio(False)` per clip, map word timecodes back with the extraction offset and the 25/24 rate factor. `transcribe_clip.py` (0e05d2ae 09:07:36, 09:43:17, 09:45:27).
- [x] SOLVED Cut by sentences, remove filler words and silences (text-based editing) - compute source ranges from `GetTranscription()` word timings (`'(...)'` segments are silence), then `CreateTimelineFromClips` or `AppendToTimeline`. `assembly.build_synced_cut.py` is the assembler.
- [~] WORKAROUND Export a transcript file - return `GetTranscription()` from the script, write with Bash. No script.
- [?] UNTESTED Read a subtitle's text - `GetItemListInTrack('subtitle', 1)`; the 20.2.1 changelog fixed "getting subtitle text via scripting API", which points at `TimelineItem.GetName()`.
- [?] UNTESTED Edit a subtitle's text - `SetName` is the only candidate; if it fails Bruno edits in Inspector, Caption.
- [?] UNTESTED Import an SRT - `ImportTimelineFromFile` lists AAF/EDL/XML/FCPXML/DRT/ADL/OTIO and no SRT; `ImportMedia([{'FilePath': 'x.srt'}])` may create a pool item and `AppendToTimeline` onto a subtitle track is untested. Or Bruno uses File, Import, Subtitle.
- [?] UNTESTED Export an SRT without rendering the picture - `Timeline.Export` has no SRT type; `SetRenderSettings({'ExportVideo': False, 'ExportSubtitle': True, 'SubtitleFormat': 'SeparateFile'})` on an audio-only job may write it cheaply.
- [UI] UI-ONLY Add a single subtitle at a frame - no subtitle insert call (`AppendToTimeline` takes pool items). Bruno right-clicks the subtitle track, Add Subtitle.
- [UI] UI-ONLY Subtitle style (font, size, position, background) - no call. Bruno sets Inspector, Track Style.

### Render and deliver

- [x] SOLVED Render a timeline to H.264 MP4 - `SetCurrentRenderFormatAndCodec('mp4', 'H264')`, `SetRenderSettings({'FormatWidth', 'FormatHeight', ...})`, `AddRenderJob()`, `StartRendering([job], False)`, poll `GetRenderJobStatus(job)`. `render_timeline_mp4.py`.
- [x] SOLVED Render a single frame as TIFF - `MarkIn == MarkOut` in absolute frames, one job per frame, `SetCurrentRenderFormatAndCodec('tif', 'RGB8')`. `render_frame_tiff.py`.
- [~] WORKAROUND Copy a timeline to another project - `Export(path, resolve.EXPORT_DRT, resolve.EXPORT_NONE)` then `ImportTimelineFromFile(path)` in the other project; DRT keeps grades and Fusion comps. Or `Folder.Export` as DRB for timelines plus media references. No script.
- [?] UNTESTED Filename tokens like `%{Source Name}` in `CustomName` - documented only for `DeblurOptions.FileName`.
- [?] UNTESTED Render from cache - `render_frame_tiff.py` passes `'UseRenderCachedImages': False`, which is absent from the `RenderSettings` stub; unknown whether it is honored.
- [ ] OPEN Choose background render or remote render for a job - `JobStatus` reports them; nothing selects them.
- [UI] UI-ONLY Codec options outside `RenderSettings` (H.264 level, keyframe interval, hardware vs software encoder, audio bit rate, per-codec color tags) - Bruno sets them once in the Deliver page and clicks Save As New Preset; scripts then `LoadRenderPreset(name)`. `ExportRenderPreset`/`ImportRenderPreset` move presets between machines.
- [UI] UI-ONLY Render start and end scripts, render notifications - set in Deliver, Advanced Settings; not reachable from `run_script`.
- [UI] UI-ONLY Upload through Quick Export - `RenderWithQuickExport(preset, {'EnableUpload': True})` runs only after Bruno signs into the YouTube or Vimeo account in Resolve.
- [UI] UI-ONLY Media management (consolidate, trim media to used ranges) - no call. Bruno uses File, Media Management. `ArchiveProject` copies full source media instead.

### Stills

- [x] SOLVED Verify titles and upper tracks with pixels - `ExportCurrentFrameAsStill` on the Color page renders the current clip's grade alone, without V2/V3. A 1-frame Deliver render is the ground truth. `render_frame_tiff.py` (0e05d2ae 09:29:25, 09:30:03).
- [?] UNTESTED Still export formats - `format` in `ExportStills(stills, folder, prefix, format)` is a free string; `'png'`, `'tif'`, `'jpg'`, `'dpx'`, `'drx'` are the UI options to try.
- [UI] UI-ONLY Wipe or compare against a still in the viewer - no call. Bruno uses the Color page viewer wipe.

### UI-only mechanics

- [x] SOLVED Press any menu item from a script - macOS accessibility: `tell application "System Events" to tell process "Resolve" to click menu item ...` with the full menu path. Precise, needs no screen coordinates, and works while the screen is locked. `ui.menu(path)`, `ui.menu_items(path)` to list spellings (2026-09-24).
- [x] SOLVED Close timeline tabs - no API call. `project.SetCurrentTimeline(t)` then File > Close Timeline, per tab. `ui.close_current_timeline()` (2026-09-24).
- [UI] UI-ONLY Select a set of timeline items - no API call sets the selection (`timeline.GetSelectedClips()` only reads it). Timeline > Select Clips > By Clip Color after giving the items a spare color works through the menu bar; no function.
- [x] SOLVED Run the AI Audio Assistant (auto mix) - Timeline > AI Tools > Audio Assistant… and its Auto Mix button, both reachable through accessibility; `ui.run_audio_assistant()` waits for the dialog to close (2026-09-24).
- [?] UNTESTED Link clips from a script - Clip > Link Clips reported disabled to accessibility for every selection tried (two audio items, video plus audio), even though the selection was right; the UI state may refresh only when the menu is opened by a person.

- [~] WORKAROUND Match frame, reveal in media pool - `item.GetMediaPoolItem()` and `GetSourceStartFrame()` give the same information as data. No script.
- [UI] UI-ONLY Play, stop, loop, play around, JKL - no call. Keyboard. (Fusion's `comp:Play()` drives the Fusion viewer only, untested from Resolve.)
- [UI] UI-ONLY Zoom or scroll the timeline, zoom to fit, viewer zoom, safe areas, overlays - no call.
- [UI] UI-ONLY Trigger a keyboard command or menu item - keyboard presets load and save (`LoadKeyboardPreset`), nothing presses a key. Bruno presses it.
- [UI] UI-ONLY Change an individual preference - presets only (`SaveUserPreferencesPreset`, `LoadUserPreferencesPreset`). Bruno opens Preferences.
- [UI] UI-ONLY Redo and history - no call.
- [UI] UI-ONLY Auto-select, snapping, linked selection, timeline view options - no call to read or set any of them (Timeline > Auto Select in the menu bar toggles each track). Locks stand in for the destination toggle (see Project and timelines).
- [UI] UI-ONLY Dialog boxes Resolve pops up (media offline, delete confirmation) - no dismiss call; scripted calls avoid them. If one appears Bruno clicks it.

### Export and import

- [x] SOLVED Snapshot the project before a destructive step - `map_project.py` lists timelines, bins, tracks, items, and markers; `backup_timeline.py` duplicates the cut. Run `map_project.py` first in any session.
- [x] SOLVED Clean up probe timelines and scratch clips - `cleanup_scratch.py` deletes probe timelines by name, a scratch bin with its clips, and stray "Fusion Clip" pool items. Destructive.
- [~] WORKAROUND Export subtitles, markers, or a transcript standalone - through `GetMarkers()`/`GetTranscription()` plus a Bash write (see Markers, Subtitles).

## Quirks

- [!] QUIRK Menu actions and keystrokes differ on a locked screen - accessibility menu clicks work while the Mac is locked; keystrokes do not arrive, and the window list is empty. A keystroke that silently failed makes the next menu action hit the wrong target (an Apply Grade landed on the timeline's current clip). Run keystroke steps with the screen unlocked, and verify the target before the destructive menu step (2026-09-24).
- [!] QUIRK Multicam item names are stale - after an angle switch `GetName()` keeps the old "Angle X" until the timeline reloads. Verify angles on a rendered frame (2026-09-24).
- [!] QUIRK Multicam angle numbers follow angle names alphabetically - whatever order the clips were passed to `CreateMulticamClip`.
- [!] QUIRK Menu items that need the Edit page - Switch to Angle is disabled on the Deliver and Color pages; a render (`render_frame_tiff`) leaves you on Deliver, so switch back before menu actions (2026-09-24).
- [!] QUIRK Stills append at most 24 frames - `AppendToTimeline` ignores a longer endFrame for a still image. `clips.place_still` appends pieces and joins them with `CreateFusionClip` (2026-09-24).
- [ ] OPEN `clips.place_still` overshoots: asked for 191, 184, 177 and 170 frames, it returned a 198-frame item every time (2026-10-07, project at 30 fps). Workaround used: render with MarkIn/MarkOut.
- [!] QUIRK `GetSourceStartFrame()`/`GetSourceEndFrame()` can read one frame early - they floor a float (an item showing source frame 400 reads 399). `GetSourceStartTime()`/`GetSourceEndTime()` are exact seconds from the clip's Start TC; `source_frames(item)` converts them. What looked like appends landing one source frame off was this reading.
- [!] QUIRK Through-edit merges need exact source continuity - a 1-2 frame tolerance also joins two different takes and slides the second out of sync. `clips.join_clips` joins only exact continuations (2026-09-24).
- [!] QUIRK A delete range that picks items by start frame takes J-cut audio of the next shot - an audio item that starts inside the range but belongs to the following picture. List with `clips.items_in_range(mode="within")` and read the list before deleting (2026-09-24).
- [!] QUIRK `SetCDL` replaces a node's primaries - on a node that already holds offsets or gains (a DRX's exposure node) it wipes them; on a node with default primaries it adds cleanly. Put per-shoot exposure on a node whose identity CDL leaves the render unchanged: test with Slope 1, Power 1 first (2026-09-24).
- [!] QUIRK `Timeline.GrabStill()` grabs the topmost visible layer, not V1 - on a frame under a title the exported DRX is an empty grade that `ApplyGradeFromDRX` applies with True and one blank node. Disable upper video tracks around the grab and restore them; check `ConformStartSourceTC` in the DRX blob (2026-10-07).
- [!] QUIRK A ColorGroup's pre-clip graph refuses `ApplyGradeFromDRX` - returned False with the Color page open (2026-09-24).
- [!] QUIRK Audio mapping reads None on transitions - `GetItemListInTrack('audio', n)` includes crossfades; skip items whose `GetSourceAudioChannelMapping()` is None (2026-09-24).
- [!] QUIRK A pool clip's mapping can differ from its items' mappings on purpose - dialogue items set mono per item while the pool clip stays stereo. Copy pool mappings onto items only for clips with `linked_audio` (2026-09-24).

- [!] QUIRK A stereo audio track changed to Mono in the UI becomes a LINKED PAIR of mono tracks (L and R). `DeleteClips` on the clips of one track deletes the partner clips too, and `DeleteTrack` then removes both tracks. It wiped Pedro's dialogue on 2026-09-23 (restored from a snapshot). Never delete from one track of a pair; build dialogue on mono tracks from the start, and move clips with place-verify-then-delete.
- [!] QUIRK `ProjectManager.LoadProject("raycast-ai-updates")` from a script crashed Resolve 21.1 (2026-09-23), with no dialog and no error, only a dead process. Don't switch projects to borrow a grade: use a saved DRX or a still exported by hand.
- [!] QUIRK `MediaPoolItem.TranscribeAudio` returns False immediately while the Deliver page is open (for example right after a render) - `resolve.OpenPage("edit")`, sleep 1.5 s, then transcribe; poll `GetTranscription` on a fresh clip fetched from the bin (2026-09-23).
- [!] QUIRK Text+ element 3 ("Shadow") in `library/components/lower-third-left.comp` is already live on `TxtName` - setting its color or softness recolors the name itself and disabling it hides the name; re-import the library comp to restore (2026-09-23).
- [!] QUIRK Marks are relative, timecode is absolute - `SetMarkInOut(start, end-1)` counts frames from the timeline start (0 = first frame); `SetCurrentTimecode` wants the absolute timecode (timeline starts at 01:00:00:00); `AddMarker(frame)` is relative too. The first title pass added the start offset to the marks and landed wrong (0e05d2ae 09:10:34, 09:11:16, 09:11:44).
- [!] QUIRK Markers added while appending drift after the 25p to 24p duration rounding - rebuild them from `item.GetStart() - start` after the build (0e05d2ae 09:12:28).
- [!] QUIRK Page switches are load-bearing - title and composition inserts need the Edit page (`OpenPage('cut')` then `OpenPage('edit')` before the first insert); comp edits need the Fusion page; `ApplyGradeFromDRX`, `SetCDL`, `ExportCurrentFrameAsStill` need the Color page with a 1 to 1.5 s sleep after the switch (0e05d2ae 09:04:56, 09:07:36, 09:12:51, 09:22:02).
- [!] QUIRK A timeline item's Fusion comp is `None` from the Edit page - `item.GetFusionCompByIndex(1)` returns `None` until `resolve.OpenPage('fusion')`; fetch, edit, then `OpenPage('edit')`. `titles.title_fitted_to_clip` (0e05d2ae 09:07:14, 09:07:36).
- [!] QUIRK Inserts return False on a timeline the script just built or emptied - retries, lock variants, and cut/fusion/deliver page routes did not fix it; `project.SetCurrentTimeline(other)`, sleep 1 s, `SetCurrentTimeline(cut)`, sleep 1 s, then insert works first time (0e05d2ae 09:11:02, 09:11:44, 09:55:37, 09:55:56).
- [!] QUIRK `GetNodeGraph` comes back `None` right after `OpenPage('color')`, and Resolve crashed twice in that state - `OpenPage('color')`, `time.sleep(1.5)`, fetch items, `if getattr(items[0], 'GetNodeGraph', None) is None:` stop and re-fetch, never loop; save before grading (0e05d2ae 09:22:02, 09:22:44, 09:50:13, 09:51:30, 09:51:45).
- [!] QUIRK Color page stills leave out the upper tracks - `ExportCurrentFrameAsStill` renders the current clip's grade alone; a 1-frame Deliver render (`render_frame_tiff.py`) is the truth, stills stay for grade-only checks (0e05d2ae 09:29:25, 09:30:03).
- [!] QUIRK `project.SaveProject()` does not exist - it is `None` on the Project object; use `resolve.GetProjectManager().SaveProject()`. `place_playhead.py` (b753bc76 16:12:55, 16:13:04; dc335150 17:04:29, 17:04:34).
- [!] QUIRK Script output over about 60 KB breaks the MCP transport - `Failed to parse SSE message ... EOF while parsing a string at line 1 column 60082`; keep `result` small, write large output to a scratchpad file and read it with Bash (b753bc76 13:41).
- [!] QUIRK Scripts time out around 55 s and render jobs outlive them - `StartRendering([job], False)` and poll `GetRenderJobStatus(job)` in a follow-up script; `DeleteAllRenderJobs()` first; loop over many comps in chunks and save between chunks (0e05d2ae 09:52:56, 09:57:01, 10:03:18).
- [!] QUIRK Render preset names vary - "YouTube 1080p" was absent; check `GetRenderPresetList()` and fall back to `SetCurrentRenderFormatAndCodec('mp4', 'H264')` plus `FormatWidth`/`FormatHeight` (0e05d2ae 09:52:40).
- [!] QUIRK Track layout reads stale - `GetTrackCount` and `GetTrackSubType` return old values right after `AddTrack` or `DeleteTrack` until a page switch (cut then edit) (0e05d2ae 09:48:48).
- [!] QUIRK `DeleteTrack` refuses the only audio track and any track with items - a loop calling `DeleteTrack` until `GetTrackCount('audio')` was 0 failed the build right after; add the replacement tracks first and delete items before the track (0e05d2ae 09:46:15, 09:47).
- [!] QUIRK Deleting V1 items leaves their linked audio on A1/A2 - delete the audio items explicitly before `DeleteTrack` (0e05d2ae 09:35:53, `audio_left` check).
- [!] QUIRK `SetName` fails silently on ":" and "/" - use " - " and " + "; "·" is fine. Fusion tool names must also be valid Lua identifiers (no spaces, no leading digit) before expressions reference them (0e05d2ae 09:10:08, 09:10:34).
- [!] QUIRK Title and comp inserts land on the destination-toggle track and ripple it - unless the media pool selection is empty and the timeline was switched away from and back; then locks decide, and the insert lands on the one unlocked video track. The toggle is one setting shared by every timeline in the project. Probe with a throwaway insert at the tail when the target track is unknown.
- [!] QUIRK No call deselects media pool clips - `SetCurrentFolder` to another folder and back leaves the selection empty (`timelines.clear_media_pool_selection`). Loading a project also clears it.
- [!] QUIRK Auto-select decides what an insert or ripple delete touches, silently - a track with auto-select off neither moves nor gets cut by a rippling insert, and nothing reports it; its clips simply stay whole. The API cannot read or set it. `clips.ripple_insert` and `clips.split_at` compare the spanning clips before and after and return them under "unsplit". A title insert still lands on a track with auto-select off.
- [!] QUIRK A deleted clip takes its edge transitions with it - ripple-deleting the right half of a clip deletes the crossfade at its old out point, and deleting pieces to re-append them deletes the crossfades on their edges. Read them first and `AddTransition` them back.
- [!] QUIRK `GetItemListInTrack` returns `None` for an empty track - every script uses `or []` (0e05d2ae 09:47, 09:47:24 onward).
- [!] QUIRK `AppendToTimeline` can return a list containing `None` - `if not items` passes and `items[0].SetName` raises; guard with `it = items[0] if items else None; if not it: ...` (0e05d2ae 09:35:53, 09:36:08, 09:36:30).
- [!] QUIRK `GetSourceAudioChannelMapping()` returns `None` on items of a timeline that is not current and on transition items - `SetCurrentTimeline(t)` first and skip `None` (0e05d2ae 09:33:46, 09:33:55, 09:34:04).
- [!] QUIRK `endFrame` is exclusive and frame rates map - `startFrame 0, endFrame 95` gives 95 frames, for media clips and nested timelines alike; a 25p clip appended into a 24p timeline gives `int(n*0.96)` frames. Check `GetDuration()` after every append.
- [!] QUIRK `AppendToTimeline` cannot recreate a retimed clip - `insert_fusion_comp_at.py` stops when one sits to the right of the insert point (b753bc76 2026-09-12 08:28).
- [!] QUIRK `SetProperties` validates all keys together - one bad key and none apply; values beyond range are clipped.
- [!] QUIRK `Timeline.SetSettings` needs `useCustomSettings` first - the other keys fail while it is `'0'`; apply `{'useCustomSettings': '1'}` before resolution or frame rate. `superScale` 2x Enhanced needs the 4-arg `SetSetting` form; `timelineFrameRate` is a string (`'23.976'`, `'29.97 DF'`).
- [!] QUIRK Imports land in the current bin, duplicates next to their source - `ImportMedia` uses `GetCurrentFolder()`; `DuplicateTimeline` puts the copy in the source timeline's bin whatever the current folder. `SetCurrentFolder` before imports, `MoveClips([copy.GetMediaPoolItem()], bin)` after duplicates.
- [!] QUIRK `AppendToTimeline` always targets the current timeline - holding another Timeline object changes nothing; on a timeline that is not current it returns an item whose `GetDuration()` is None. `SetCurrentTimeline` first.
- [!] QUIRK "Cyan" is a marker color, not a clip color - `SetClipColor('Cyan')` leaves the item uncolored. Clip colors: Orange, Apricot, Yellow, Lime, Olive, Green, Teal, Navy, Blue, Purple, Violet, Pink, Tan, Beige, Brown, Chocolate.
- [!] QUIRK A rippling title insert moves markers too - `InsertFusionTitleIntoTimeline` with every track unlocked shifts the timeline markers after the insert along with the clips (`clips.ripple_insert` relies on it).
- [!] QUIRK A ripple delete trims items that span the deleted range on unlocked tracks - closing a gap with a long clip running across it on an unlocked track cuts that range out of the clip. Leave the track out (`close_gap_ripple(tracks=...)`).
- [!] QUIRK A new Edit-page Text title stores no text - its `EffectFiltersBA` stays empty in a DRT until the title is edited in the UI.
- [!] QUIRK The menu bar reports some items disabled while they work in the UI - Clip > Enable/Disable Clip and Clip > Multicam Switch read disabled to Accessibility with a clip selected.
- [!] QUIRK Probe timelines and "Fusion Clip" pool items pile up - `CreateFusionClip` leaves a "Fusion Clip N" item in the current bin; probe timelines stay in the timelines bin. `cleanup_scratch.py` (0e05d2ae 09:11:44).
- [!] QUIRK Full-clip transcription collapses repeated takes - `GetTranscription()` on the whole camera clip merges attempts and drops short clauses; word timecodes are at the clip's frame rate (25), the timeline is 24. Short WAV windows per take fix both. `transcribe_clip.py` (0e05d2ae 09:43:17).
- [!] QUIRK `ImportFusionComp` adds, never replaces - `GetFusionCompNameList()` grows ("Composition 1", "Composition 2") and the imported one becomes active; fetch it by name afterward and `DeleteFusionCompByName` the old one.
- [!] QUIRK `comp.Lock()` without `Unlock()` freezes the Fusion page - wrap the batch in `try/finally: comp.Unlock()`.
- [!] QUIRK `comp.CurrentFrame` is `None` off the Fusion page - `FlowView`, `ViewOn`, `SetActiveTool` fail on any other page; edit positions in the exported text instead.
- [!] QUIRK FuID inputs take the ID, never the UI label - `'Duration'`, `'Cubic'`, `'Soften'`, `'Alpha'`; checkboxes are 0/1; colors 0 to 1; point inputs are `{1: x, 2: y}` and read back as `{1.0: x, 2.0: y}`.
- [!] QUIRK `RenderEnd` is the last frame index - frame count is `RenderEnd + 1`; every library expression assumes it. Setting `COMPN_RenderEnd` through `SetAttrs` is overridden by Resolve; change the clip length instead.
- [!] QUIRK Fusion keyframes sit at absolute comp frames - trim the clip and an out-animation stays where it was; use Anim Curves modifiers on `Duration` for anything tied to clip length.
- [!] QUIRK Exported Text+ blocks carry `GlobalOut` at the export-time length - Anim Curves on `Duration` stay correct after a trim; if a generator ever stops at the old length after extending a clip, strip `GlobalIn`/`GlobalOut` from the tool block before importing (seen in files, never seen to bite).
- [!] QUIRK Fusion clips do not see the tracks below - they wrap their own clips as `MediaIn1..n`; only native compositions and Text+ titles get the Background `MediaIn` layer, and that layer shows in the Edit viewer only.
- [!] QUIRK `GetToolList()` includes modifiers - LUTLookup, XYPath, BezierSpline appear as tools; filter by `tool.ID`. `tool.Delete()` leaves its modifiers as orphans; delete them explicitly. Avoid `fu.Delete()`/`fu.Cut()`, which act on the UI selection.
- [!] QUIRK Text+ does not wrap scripted text - wrap in Python (`textwrap.wrap(text, 30)` at size 0.045). A `Style` string that matches no face falls back silently to the default; read `GetInput('Style')` back when it matters.
- [!] QUIRK Renaming a tool through `SetAttrs` after expressions reference it may not rewrite those expressions - set `TOOLS_Name` before wiring expressions; `SetExpression` replaces any spline connection on that input.
- [!] QUIRK Input color space spelling differs from the UI label - `SetClipProperty` returns False without a hint; `set_input_color_space.py` tries variants (0e05d2ae 09:22:02).

## Stub caveats

- The Fusion stub (`fusion_api.pyi`) has no `Tool`, `Input`, or `Output` class; the closest are `Operator`, `PlainInput`, `PlainOutput`. `GetAttrs` and `SetAttrs` appear nowhere in it, yet `tool.SetAttrs({'TOOLS_Name': ...})` and `comp.GetAttrs()['COMPN_RenderEnd']` run fine. When a method is missing from the stub, try it before calling it a gap.
- The Fusion stub includes Fusion Studio calls that do not apply inside Resolve: `Composition.Render`, `Save`, `SaveAs`, `Close`, `Fusion.QueueComp`, `LoadComp`, `NewComp`. Inside Resolve the comp saves with the project (`resolve.GetProjectManager().SaveProject()`) and renders on the Deliver page. Never call `comp.Close()` on an item's comp.
- `DaVinciResolveScript.pyi` declares `class Fusion: ...` and `class FusionComp: ...` with no members, so every Fusion call in this document rests on Fusion's own scripting, not on the Resolve stubs.
- New in 21 and worth a first run: `Timeline.GetSelectedClips()` (21.0.4, read-only selection), `Timeline.GetMediaPoolItem()` (21.0.4, the pool item of a timeline for nesting), `TimelineItem.AddTransition` (audio and simple categories have run; ofx untested), `TimelineItem.GetFades`/`SetFades` (ran on audio items: frame counts, read back exactly; a fade longer than the clip is refused).
