"""Let a moment run longer on every track: ripple-insert space after it, continue each clip there. See mr.clips."""
TIMELINE = "Interview - Cut v1"; AT = 6584; FRAMES = 108   # relative frame of the join, frames to add
TRACKS = (("video", 1), ("video", 2), ("audio", 1), ("audio", 2), ("audio", 3))
t = mr.find_timeline(project, TIMELINE); s = t.GetStartFrame()
mr.backup_timeline(resolve, project, t, TIMELINE + " - backup before extend")
ending = [x for kind, tr in TRACKS for x in (t.GetItemListInTrack(kind, tr) or []) if x.GetMediaPoolItem() and x.GetEnd() - s == AT]
mr.ripple_insert(resolve, project, t, AT, FRAMES)
added = [mr.continue_clip(resolve, project, t, x, FRAMES, record=AT) for x in ending]
result = {"continued": len([a for a in added if a]), "of": len(ending)}
