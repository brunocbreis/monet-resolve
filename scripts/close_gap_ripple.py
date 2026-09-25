"""Close a gap on the chosen tracks by filling it with a dummy clip and ripple-deleting it. See mr.assembly.close_gap_ripple."""
TIMELINE = "Cut v2"; GAP_START = 2051; GAP_LEN = 36; DUMMY_CLIP = "C0421.MP4"
TRACKS = [("video", 1), ("audio", 1)]   # None closes every track
dummy = mr.find_clip(project.GetMediaPool().GetRootFolder(), DUMMY_CLIP)
result = mr.close_gap_ripple(resolve, project, mr.find_timeline(project, TIMELINE), GAP_START, GAP_LEN, dummy, tracks=TRACKS)
