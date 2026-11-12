# API recipes that worked (Resolve 21.1)

Raw API calls behind the monet-resolve functions, for when no function covers a case yet. `resolve`, `project` are pre-bound by `python3 -m monet_resolve.run`.

## Map the project
```python
tls=[project.GetTimelineByIndex(i+1) for i in range(project.GetTimelineCount())]
cut=[t for t in tls if t.GetName()=="Pricing Video - Cut v1"][0]; s=cut.GetStartFrame()
for ti in range(1,cut.GetTrackCount("video")+1):
    print(ti, cut.GetTrackName("video",ti), [(x.GetName(),x.GetStart()-s,x.GetDuration()) for x in cut.GetItemListInTrack("video",ti)])
markers={int(k):v for k,v in cut.GetMarkers().items()}; io=cut.GetMarkInOut()
```
Frame → timecode at 24 fps: `f"01:{f//24//60:02d}:{f//24%60:02d}:{f%24:02d}"` (timeline starts 01:00:00:00).

## Insert a native Fusion composition (`mr.insert_fusion_composition` does the choreography)
```python
resolve.OpenPage("edit"); nt=cut.GetTrackCount("video"); na=cut.GetTrackCount("audio")
# empty the media pool selection and switch timelines, lock, insert: lands on `target`
mp=project.GetMediaPool(); here=mp.GetCurrentFolder(); mp.SetCurrentFolder(mp.GetRootFolder()); mp.SetCurrentFolder(here)   # deselects (from the root, go through a subfolder)
project.SetCurrentTimeline(other); time.sleep(1); project.SetCurrentTimeline(cut); time.sleep(1)
# lock the others, clear the right side of the target track, insert
for ti in range(1,nt+1): cut.SetTrackLock("video",ti, ti!=target)
for ai in range(1,na+1): cut.SetTrackLock("audio",ai,True)
cut.SetMarkInOut(start,start+dur-1); cut.SetCurrentTimecode(tc(start)); it=cut.InsertFusionCompositionIntoTimeline(); cut.ClearMarkInOut()
for ti in range(1,nt+1): cut.SetTrackLock("video",ti,False)
for ai in range(1,na+1): cut.SetTrackLock("audio",ai,False)
it.SetName("TITLE 10 - ..."); it.SetClipColor("Violet")
resolve.OpenPage("fusion"); it.ImportFusionComp(path); resolve.OpenPage("edit")
```

## Snapshot / restore items on a track
```python
keys=["ZoomX","ZoomY","Pan","Tilt","AnchorPointX","AnchorPointY","RotationAngle","Opacity","CropLeft","CropRight","CropTop","CropBottom","CompositeMode"]
snap=[{"mpi":x.GetMediaPoolItem(),"start":x.GetStart(),"dur":x.GetDuration(),"src":(x.GetSourceStartFrame(),x.GetSourceEndFrame()),
       "color":x.GetClipColor(),"props":{k:x.GetProperty(k) for k in keys},"comp":(x.ExportFusionComp(f"/tmp/{x.GetName()}.comp",1) and f"/tmp/{x.GetName()}.comp") if x.GetFusionCompCount() else None} for x in items]
# restore a plain clip
project.GetMediaPool().AppendToTimeline([{"mediaPoolItem":c["mpi"],"startFrame":c["src"][0],"endFrame":c["src"][1],"trackIndex":ti,"recordFrame":c["start"],"mediaType":1}])
# then SetProperty for each key, SetClipColor; confirm GetDuration()==c["dur"] and the source range (mind ±1 on endFrame)
```
Retimed clips carry their retime in the timeline, so leave them in place; `AppendToTimeline` recreates plain clips only.

## Close a gap with a ripple-delete
```python
mp.AppendToTimeline([{"mediaPoolItem":anyclip,"startFrame":0,"endFrame":int(gap/0.8+0.5),"trackIndex":1,"recordFrame":s+gap_start}])
dummy=[x for x in cut.GetItemListInTrack("video",1) if x.GetStart()-s==gap_start]+[x for x in cut.GetItemListInTrack("audio",1) if x.GetStart()-s==gap_start and x.GetType()=="audio"]
cut.DeleteClips(dummy,True)   # ripple; lock the tracks that must stay put first
```

## Fusion clip of an exact length + comp import

The custom 24 fps / 4K setup below belongs to an explicitly requested standalone GFX timeline.
For assembly work, preserve Bruno's existing settings and custom-settings flag.
```python
t=mp.CreateEmptyTimeline("GFX - X"); project.SetCurrentTimeline(t)
t.SetSetting("useCustomSettings","1"); t.SetSetting("timelineFrameRate","24"); t.SetSetting("timelineResolutionWidth","3840"); t.SetSetting("timelineResolutionHeight","2160")
mp.AppendToTimeline([{"mediaPoolItem":footage,"startFrame":0,"endFrame":int(frames/0.8+0.5),"recordFrame":t.GetStartFrame(),"mediaType":1}])  # 30fps source → 24fps timeline
it=t.GetItemListInTrack("video",1)[0]; t.CreateFusionClip([it]); it=t.GetItemListInTrack("video",1)[0]
resolve.OpenPage("fusion"); it.ImportFusionComp(path); resolve.OpenPage("edit")
```

## Fusion comp editing
```python
comp=item.GetFusionCompByIndex(1) or item.AddFusionComp(); comp.Lock(); ... ; comp.Unlock()
T={t.Name:t for t in comp.GetToolList().values()}
tool=comp.AddTool("TextPlus",x,y); tool.SetAttrs({"TOOLS_Name":"TxtTitle"}); tool.SetInput("StyledText","...")
tool.ConnectInput("Input", other); tool.Input.GetConnectedOutput().GetTool()
inp.SetExpression("..."); inp.ConnectTo(modifier); inp[frame]=value   # keyframe once a spline is connected
comp.CurrentFrame.FlowView.SetPos(tool,x,y)   # only while the Fusion page is open; GetPosTable(tool) reads
E=int(comp.GetAttrs()["COMPN_RenderEnd"])     # follows the clip length for native comps and Fusion clips
```
Text+ inputs: StyledText, Font, Style, Size, CharacterSpacing, HorizontalLeftCenterRight, VerticalTopCenterBottom, Red1/Green1/Blue1/Alpha1, Opacity1, Center.
Fonts: `resolve.Fusion().FontManager.GetFontList()` — this Mac has "Inter 18pt/24pt/28pt".
OFX in Fusion: `comp.AddTool("ofx.com.rubbermonkey.FilmConvertNitrate")`; inputs by name ("Film Luma", ...).
Anim Curves: `comp.AddTool("LUTLookup")`; XY Path: `comp.AddTool("XYPath")`; Bezier: `comp.AddTool("BezierSpline")`.
Modifier IDs come from `resolve.Fusion().GetRegList(fu.CT_Modifier)`.

## Background MediaIn (native comps only)
```python
mi=comp.AddTool("MediaIn",0,0); mi.SetAttrs({"TOOLS_Name":"MiBackground"})
mi.SetInput("MediaSource","Background"); mi.SetInput("MediaID","BACKGROUND"); mi.SetInput("Layer","0"); mi.SetInput("ClipName","Background")
```
Check it in the timeline viewer (Color-page stills of the comp show the comp alone).

## Grade / audio / render
```python
item.GetNodeGraph().SetLUT(1,"MCP/SubtleFilm.cube"); item.SetCDL({"NodeIndex":1,"Slope":"r g b","Offset":"0 0 0","Power":"1 1 1","Saturation":1.0})
mediaPoolItem.SetClipProperty("Super Scale",3); project.SetSetting("superScaleSharpness","Low"); project.SetSetting("superScaleNoiseReduction","High")
prev.AddTransition({"type":"Cross Fade +3 dB","category":"audio","position":"end","alignment":"center","duration":4})
cut.SetVoiceIsolationState(1,{"isEnabled":False,"amount":60})   # tracks must be unlocked
project.LoadRenderPreset("YouTube 4K"); project.SetRenderSettings({"SelectAllFrames":True,"TargetDir":d,"CustomName":n,"ExportVideo":True,"ExportAudio":True,"UseRenderCachedImages":False})
job=project.AddRenderJob(); project.StartRendering([job],False)   # poll GetRenderJobStatus(job) in ≤55 s scripts
```

## Pixel checks
```python
project.ExportCurrentFrameAsStill("/tmp/x.png")            # on the Color page, after SetCurrentTimecode + a short sleep
subprocess.run(["sips","-s","format","bmp","-Z","480","/tmp/x.png","--out","/tmp/x.bmp"])
# BMP: offset at byte 10, width at 18, height at 22 (negative = top-down), bpp at 28; rows padded to 4 bytes; B,G,R order
```
Ground truth: a 1-frame Deliver render (`SetCurrentRenderFormatAndCodec("tif","RGB8")`, MarkIn=MarkOut).

## Media pool
```python
mp.AddSubFolder(parent,"name"); mp.MoveClips([clips],folder); mp.MoveFolders([folder],parent); mp.DeleteClips([clip]) (timelines too); mp.ImportMedia([paths])
```

## Confirmed on the Raycast AI Update edit (Resolve 21.1, 2026-09-11)

### Audio tracks and mono dialogue
```python
t.AddTrack("audio","mono"); t.AddTrack("audio","stereo")          # works; read the layout back only after a page switch
resolve.OpenPage("cut"); resolve.OpenPage("edit"); [t.GetTrackSubType("audio",i) for i in range(1,t.GetTrackCount("audio")+1)]
t.DeleteTrack("audio",1)          # only when empty and other audio tracks exist; V1 deletes leave linked audio behind, delete it first
m=json.loads(clip.GetAudioMapping()); m["track_mapping"]={"1":{"channel_idx":[3],"mute":False,"type":"mono"},"2":{"channel_idx":[1,2],"mute":False,"type":"stereo"}}; clip.SetAudioMapping(json.dumps(m))
# channels 3,4 = the synced external file after AutoSyncAudio(waveform, retainEmbeddedAudio); appends then land mono dialogue on A1 (mono track), camera on A2
item.SetSourceAudioChannelMapping(json)   # same shape, fixes items already on the timeline
```
A timeline that needs this layout is quickest as `DuplicateTimeline` of one that has it, then emptied (`DeleteClips` on V1, V2, A3 and on the leftover A1/A2 audio).

### Titles on V2, marks, markers, names
```python
p.SetCurrentTimeline(other); time.sleep(1); p.SetCurrentTimeline(t); time.sleep(1)   # reliable refresh after a scripted build; a cut→edit page switch only sometimes works
t.SetTrackLock("video",1,True); [t.SetTrackLock("audio",i,True) for i in (1,2,3)]
t.SetMarkInOut(start,end-1)      # RELATIVE frames (0 = timeline start); SetCurrentTimecode stays absolute
t.SetCurrentTimecode(tc(start)); it=t.InsertFusionTitleIntoTimeline("Text+"); t.ClearMarkInOut()   # lands on V2
resolve.OpenPage("fusion"); tp=[x for x in it.GetFusionCompByIndex(1).GetToolList().values() if x.ID=="TextPlus"][0]; tp.SetInput("StyledText","...")
t.AddMarker(frame_relative,"Blue","name","",1)              # add after the build; frames relative to the start
it.SetName("L07 - Automations")                             # ":" and "/" make SetName fail silently
```
Re-creating a clip from `GetSourceStartFrame()/GetSourceEndFrame()` needs `endFrame+1`; a fresh plan value does not.

### Grades safely
```python
resolve.OpenPage("color"); time.sleep(1.5); items=t.GetItemListInTrack("video",1)
if getattr(items[0],"GetNodeGraph",None) is None: raise SystemExit("re-fetch, do not loop")   # Resolve crashed twice right after this None
g=items[0].GetNodeGraph(); g.ApplyGradeFromDRX(path,0); items[0].SetCDL({"NodeIndex":1,"Slope":"0.72 0.72 0.72","Offset":"0 0 0","Power":"1 1 1","Saturation":1.0})
```
Ground truth for any look check is a 1-frame Deliver render (tif); Color-page stills do not composite upper tracks.

### Iterating on an existing cut (do this instead of rebuilding)
```python
for i in range(1,nv+1): t.SetTrackLock("video",i,i in keep_still)     # lock what must not move; leave V2 titles / A3 music unlocked when they should follow
t.DeleteClips([item]+linked_audio, True)                                 # ripple delete: everything to the right slides left
mp.AppendToTimeline([{"mediaPoolItem":v,"startFrame":new_in,"endFrame":new_out,"trackIndex":1,"recordFrame":slot_start}])   # take swap into the same slot, same length
# length change = delete + re-append the new range at the same recordFrame, then ripple the gap (dummy clip + DeleteClips ripple) or delete the overlap
```

## Audio Assistant ("auto mix") through the menu (confirmed 2026-09-23)

The scripting API has no Audio Assistant call. Drive the menu with System Events; this is what
Bruno means by "run the auto mix". Needs Accessibility for both **Claude** and the lowercase
**claude** CLI process (System Settings → Privacy & Security → Accessibility).

1. `project.SetCurrentTimeline(t)` via `run_script`, Edit page.
2. Click the menu item, wait for the dialog, press Return (the default button is **Auto Mix**;
   Delivery Standard is already **YouTube**):
```bash
osascript -e 'tell application "DaVinci Resolve" to activate' \
  -e 'tell application "System Events" to tell process "DaVinci Resolve" to click menu item "Audio Assistant…" of menu 1 of menu item "AI Tools" of menu 1 of menu bar item "Timeline" of menu bar 1'
sleep 2; osascript -e 'tell application "System Events" to key code 36'
```
3. The dialog is an AX window named "Frame" (about 400×328). Done when it is gone
   (`count (windows whose name is "Frame")` = 0). A1 becomes "Dialogue 1" with fx.
   The Return can start playback afterwards: stop it with Space, then save.
