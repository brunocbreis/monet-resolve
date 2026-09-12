"""Close a gap by filling it with a dummy clip and ripple-deleting the dummy. See mr.assembly.close_gap_ripple."""
TIMELINE = "Raycast AI Update - Cut v2"; GAP_START = 2051; GAP_LEN = 36; DUMMY_CLIP = "C0421.MP4"
VIDEO_TRACK = 1; LOCK_VIDEO = []; SOURCE_FPS_RATIO = 25 / 24
mp = project.GetMediaPool()
dummy = mr.find_clip(mp.GetRootFolder(), DUMMY_CLIP)
cut = mr.find_timeline(project, TIMELINE)
result = mr.assembly.close_gap_ripple(resolve, project, cut, GAP_START, GAP_LEN, dummy, video_track=VIDEO_TRACK, lock_video=LOCK_VIDEO, source_fps_ratio=SOURCE_FPS_RATIO)
